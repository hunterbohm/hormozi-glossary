#!/usr/bin/env python3
"""Export the glossary into an Obsidian vault as idiomatic, navigable notes.

Fully MANAGES the folder supplied through ``VAULT_DIR``: writes an index/MOC note
plus one note per term, and deletes stale term notes it did not write this run.
Regenerate every run — idempotent. Never touches files outside that folder.

Run:  VAULT_DIR=~/path/to/vault/Hormozi-Glossary python3 build/export_vault.py
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

# --- robust import of the shared contract (build/lib.py) -------------------
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import lib  # noqa: E402

import yaml  # noqa: E402

INDEX_NAME = "Hormozi Glossary"

DISCLAIMER = (
    "This is an **unofficial, educational** glossary. Definitions are "
    "**paraphrased and attributed** — not verbatim quotes — and this project is "
    "**not affiliated with or endorsed by Alex Hormozi**."
)


def safe_filename(term: str) -> str:
    """Turn a term into a readable, filesystem- and wikilink-safe note name.

    Keeps the result human-readable so it doubles as the wikilink target.
    """
    name = re.sub(r"\s*:\s+", " - ", term)  # "CLOSER: C"  -> "CLOSER - C"
    name = name.replace(":", "-")           # "LTGP:CAC"   -> "LTGP-CAC"
    for ch in "/\\<>":                       # separators  -> dash
        name = name.replace(ch, "-")
    for ch in '"|?*#^[]':                    # wikilink/fs-breaking -> drop
        name = name.replace(ch, "")
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name


def frontmatter(entry: dict, note_name: str) -> str:
    aliases = list(entry.get("aliases") or [])
    if entry["term"] != note_name and entry["term"] not in aliases:
        aliases.insert(0, entry["term"])  # keep canonical name resolvable

    sources = []
    for s in entry.get("sources", []):
        label, url = s.get("label", ""), s.get("url") or ""
        sources.append(f"{label} — {url}" if url else label)

    fm = {
        "aliases": aliases,
        "category": entry["category"],
        "confidence": entry["confidence"],
        "first_seen": entry["first_seen"],
        "last_updated": entry.get("last_updated", ""),
        "status": entry.get("status", "active"),
        "evidence_status": entry.get("evidence_status", ""),
        "sources": sources,
        "tags": ["hormozi-glossary", f"hormozi/{entry['category']}"],
    }
    body = yaml.safe_dump(
        fm, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000
    )
    return f"---\n{body}---\n"


def callout(kind: str, title: str, text: str) -> str:
    head = f"> [!{kind}]" + (f" {title}" if title else "")
    lines = [head]
    for ln in text.splitlines() or [""]:
        lines.append(f"> {ln}".rstrip())
    return "\n".join(lines)


def render_note(entry: dict, note_name: str) -> str:
    parts = [frontmatter(entry, note_name), f"# {entry['term']}\n"]
    parts.append(callout("abstract", "", entry["short_def"]) + "\n")
    parts.append(entry["full_def"] + "\n")

    if entry.get("formula"):
        parts.append(f"**Formula:** `{entry['formula']}`\n")
    if entry.get("components"):
        comp = "**Components:**\n" + "\n".join(f"- {c}" for c in entry["components"])
        parts.append(comp + "\n")

    parts.append(callout("tip", "The frame", entry["why_it_matters"]) + "\n")
    for _ev in (entry.get("evidence") or []):
        if _ev.get("quote"):
            _src = _ev.get("source", "")
            _url = _ev.get("url") or ""
            _cite = f"[{_src}]({_url})" if _url else _src
            parts.append(callout("quote", "In his words", f"\"{_ev['quote']}\"\n\u2014 Alex Hormozi, {_cite}") + "\n")
        elif _ev.get("source"):
            parts.append(f"**Defined in:** {_ev['source']} _(cited, not excerpted)_\n")

    src_lines = ["## Sources"]
    for s in entry.get("sources", []):
        label, url = s.get("label", ""), s.get("url") or ""
        src_lines.append(f"- [{label}]({url})" if url else f"- {label}")
    parts.append("\n".join(src_lines) + "\n")

    parts.append(f"---\nSee also: [[{INDEX_NAME}]]\n")
    return "\n".join(parts)


def render_index(entries: list[dict], grouped: dict[str, list[dict]], names: dict[str, str]) -> str:
    fm = {"tags": ["hormozi-glossary"]}
    out = [f"---\n{yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)}---\n"]
    out.append(f"# {INDEX_NAME}\n")
    out.append(
        "A navigable glossary of the terms, frameworks, and redefined words Alex Hormozi "
        "uses across his books, podcasts, and talks. Each note paraphrases one idea, links "
        "its sources, and explains why the framing matters.\n"
    )
    out.append(callout("warning", "Unofficial & educational", DISCLAIMER) + "\n")

    counts = "\n".join(
        f"- **{lib.CATEGORIES[c]}** — {len(grouped[c])}" for c in grouped
    )
    out.append(f"**{len(entries)} terms** across {len(grouped)} categories:\n\n{counts}\n")

    for cat, items in grouped.items():
        out.append(f"## {lib.CATEGORIES[cat]}\n")
        rows = []
        for e in items:
            nm = names[e["id"]]
            link = f"[[{nm}]]" if nm == e["term"] else f"[[{nm}|{e['term']}]]"
            rows.append(f"- {link} — {e['short_def']}")
        out.append("\n".join(rows) + "\n")

    return "\n".join(out)


def main() -> int:
    raw_target = os.environ.get("VAULT_DIR", "").strip()
    if not raw_target:
        sys.exit(
            "ERROR: VAULT_DIR is required. Point it at the folder this exporter may "
            "fully manage."
        )
    target = pathlib.Path(raw_target).expanduser()
    if not target.parent.exists():
        sys.exit(
            f"ERROR: vault container not found: {target.parent}\n"
            f"       Is the Obsidian vault present? (set VAULT_DIR to override)"
        )
    target.mkdir(exist_ok=True)

    entries = lib.load_valid()
    grouped = lib.by_category(entries)
    names = {e["id"]: safe_filename(e["term"]) for e in entries}

    written: set[str] = set()

    # index / MOC
    idx_file = f"{INDEX_NAME}.md"
    (target / idx_file).write_text(render_index(entries, grouped, names), encoding="utf-8")
    written.add(idx_file)

    # one note per term
    for e in entries:
        fname = f"{names[e['id']]}.md"
        (target / fname).write_text(render_note(e, names[e["id"]]), encoding="utf-8")
        written.add(fname)

    # prune stale notes we did not write this run (only within the managed folder)
    removed = []
    for md in target.glob("*.md"):
        if md.name not in written:
            md.unlink()
            removed.append(md.name)

    print(f"Exported {len(entries)} term notes + index to: {target}")
    print(f"  wrote {len(written)} files ({len(written) - 1} terms + 1 index)")
    if removed:
        print(f"  pruned {len(removed)} stale note(s): {', '.join(sorted(removed))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
