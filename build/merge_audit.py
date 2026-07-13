#!/usr/bin/env python3
"""Append completeness-audit new terms (audit-*.yml) into glossary.yml.

Dedups by id AND normalized term/alias, blocks any evidence sourced from book-readings,
re-sorts, validates. Idempotent-ish: re-running skips already-present terms.

Usage:  python3 build/merge_audit.py <local_dir_with_audit_yaml>
"""
from __future__ import annotations
import collections
import pathlib
import re
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib  # noqa: E402

BOOKREAD = re.compile(
    r"(\$100m\s+\w+\s+book\b|\bbook\s*\(|audiobook|lost chapters|"
    r"part\s*\d+\s*[:\-].*\bbook\b|\bbook\b.*part\s*\d+|book launch)", re.I)
KEY_ORDER = ["id", "term", "aliases", "category", "short_def", "full_def", "formula",
             "components", "why_it_matters", "sources", "evidence", "evidence_status",
             "note", "confidence", "first_seen", "last_updated", "status"]
TODAY = "2026-07-09"


def norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", (s or "").lower()).split())


def ordered(e: dict) -> dict:
    return {k: e[k] for k in KEY_ORDER if e.get(k) not in (None, "", [])}


def main() -> int:
    locald = pathlib.Path(sys.argv[1])
    entries = lib.load(lib.GLOSSARY)
    ids = {e["id"] for e in entries}
    names = set()
    for e in entries:
        for n in [e["term"], *(e.get("aliases") or [])]:
            names.add(norm(re.sub(r"\s*\(.*?\)", "", n)))

    added, dup, blocked, bad = [], [], [], []
    for f in sorted(locald.glob("audit-*.yml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        print(f"  {len(data):>3} candidates in {f.name}")
        for n in data:
            if not (n.get("id") and n.get("term") and n.get("short_def")):
                bad.append(n.get("id", "?")); continue
            cand_names = [norm(re.sub(r"\s*\(.*?\)", "", x)) for x in [n["term"], *(n.get("aliases") or [])]]
            if n["id"] in ids or any(cn in names for cn in cand_names if cn):
                dup.append(n["id"]); continue
            srcbits = []
            for ev in (n.get("evidence") or []):
                srcbits += [ev.get("source", "") or "", ev.get("url", "") or ""]
            for s in (n.get("sources") or []):
                srcbits += [s.get("label", "") or "", s.get("url", "") or ""]
            if any(BOOKREAD.search(b) for b in srcbits):
                blocked.append(n["id"]); continue
            n.setdefault("evidence_status", "verified")
            n.setdefault("confidence", "medium")
            n.setdefault("last_updated", TODAY)
            n.setdefault("status", "active")
            entries.append(n); ids.add(n["id"])
            for cn in cand_names:
                if cn:
                    names.add(cn)
            added.append(n["id"])

    order = {c: i for i, c in enumerate(lib.CATEGORY_ORDER)}
    entries.sort(key=lambda e: (order.get(e["category"], 99), e["term"].lower()))

    header = (f"# Alex Hormozi Glossary — source of truth (edit here; generators + sweep read this)\n"
              f"# {len(entries)} terms. Schema: SCHEMA.md. Definitions paraphrased & attributed; evidence\n"
              f"# quotes are short fair-use excerpts of his public SPOKEN statements (books cited, not quoted).\n"
              f"# Last full synthesis + evidence pass: {TODAY}\n")
    body = yaml.dump([ordered(e) for e in entries], sort_keys=False, allow_unicode=True,
                     width=1000, default_flow_style=False)
    lib.GLOSSARY.write_text(header + body, encoding="utf-8")

    errs = lib.validate(entries)
    print(f"\nadded {len(added)} | skipped dup {len(dup)} | blocked book-source {len(blocked)} | malformed {len(bad)}")
    print(f"total terms now: {len(entries)}")
    if added:
        print("added:", added)
    if blocked:
        print("BLOCKED (book source):", blocked)
    print("VALID ✓" if not errs else f"INVALID: {errs[:3]}")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
