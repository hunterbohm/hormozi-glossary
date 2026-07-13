#!/usr/bin/env python3
"""Hormozi Glossary content sweep — discover, diff, and propose definition changes.

Flow (see sweep/README.md):
  discover  -> pull the Rosetta.to listing, diff vs seen-state + catalog baseline
  fetch     -> pull each new page (summary + Q&A + transcript)
  extract   -> pull candidate definitions from the text (pluggable LLM, or offline mock)
  classify  -> NEW term (add) / materially CHANGED def (revision) / skip
  propose   -> write sweep/proposals/<date>.yml + .md   (the default, no glossary writes)
  apply     -> on approval, edit glossary.yml + CHANGELOG.md in place, then re-validate

This module is infra-agnostic: no cron, no Discord, no git, no real model wired in.
The model is a pluggable hook (env SWEEP_LLM_CMD); `--mock` runs it fully offline.
"""
from __future__ import annotations

import argparse
import datetime
import difflib
import json
import os
import re
import shlex
import subprocess
import sys
import pathlib

import yaml

# --- robust lib import (build/ holds the shared contract) ---------------------
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "build"))
import lib  # noqa: E402

try:  # network deps are optional at import time (mock path needs neither)
    import requests
    from bs4 import BeautifulSoup
except Exception:  # pragma: no cover - only hit if deps missing
    requests = None
    BeautifulSoup = None

# --- paths & constants --------------------------------------------------------
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCES_FILE = HERE / "sources.yml"
FIXTURE = HERE / "fixtures" / "rosetta_mock.json"
BASELINE = ROOT / "data" / "rosetta-index.md"
PROPOSALS_DIR = HERE / "proposals"
CHANGELOG = ROOT / "CHANGELOG.md"

SITE_URL = os.environ.get("SWEEP_SITE_URL", "https://hormozi-glossary.pages.dev").rstrip("/")
USER_AGENT = os.environ.get("SWEEP_USER_AGENT", "hormozi-glossary-sweep/1.0 (+educational)")

# key order matches glossary.yml exactly (a full re-dump is byte-identical modulo header)
KEY_ORDER = [
    "id", "term", "aliases", "category", "short_def", "full_def",
    "formula", "components", "why_it_matters", "sources", "confidence",
    "first_seen", "last_updated", "status",
]

# below this difflib ratio, a matched term's definition is treated as MATERIALLY changed
SIMILARITY_THRESHOLD = float(os.environ.get("SWEEP_SIMILARITY", "0.85"))

# keyword -> category, for best-guess when a candidate has no category
CATEGORY_KEYWORDS = {
    "offers": ["offer", "value", "guarantee", "bonus", "scarcity", "urgency", "grand slam"],
    "leads": ["lead", "advertis", "ad ", "traffic", "audience", "content", "outreach", "cold"],
    "money-models": ["price", "pricing", "upsell", "downsell", "cash", "margin", "monetiz", "ltv", "cac"],
    "sales": ["sale", "close", "closing", "objection", "pitch", "prospect", "call"],
    "scaling": ["scal", "retention", "churn", "constraint", "team", "hire", "delegat", "operat", "leverage"],
    "wealth": ["wealth", "rich", "invest", "money", "asset", "equity", "net worth", "billionaire"],
    "mindset": ["mindset", "identity", "habit", "discipline", "fear", "anxiety", "insecur", "boredom"],
    "meta": ["blueprint", "learn", "method", "framework", "principle"],
}


# --- small helpers ------------------------------------------------------------
def _today() -> str:
    return datetime.date.today().isoformat()


def _norm(s: str) -> str:
    """Normalized key for term matching: lowercase, alnum-only, single-spaced."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def slugify(term: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (term or "").lower()).strip("-")
    return re.sub(r"-{2,}", "-", s) or "term"


def _split_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text or "").strip()
    if not text:
        return []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def _year(date_str: str | None) -> str:
    m = re.search(r"(19|20)\d{2}", date_str or "")
    return m.group(0) if m else str(datetime.date.today().year)


def _guess_category(text: str) -> str:
    t = (text or "").lower()
    best, score = "meta", 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        n = sum(t.count(k) for k in kws)
        if n > score:
            best, score = cat, n
    return best


# --- config & state -----------------------------------------------------------
def load_config(path: pathlib.Path = SOURCES_FILE) -> dict:
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg.setdefault("state_file", "sweep/.cache/seen.json")
    cfg.setdefault("sources", [])
    return cfg


def _state_path(cfg: dict) -> pathlib.Path:
    p = pathlib.Path(cfg["state_file"])
    return p if p.is_absolute() else (ROOT / p)


def load_state(cfg: dict) -> dict:
    p = _state_path(cfg)
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("seen", {})
                data.setdefault("hashes", {})
                return data
        except Exception:
            pass
    return {"seen": {}, "hashes": {}}


def save_state(cfg: dict, state: dict) -> None:
    p = _state_path(cfg)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def load_baseline_urls() -> set[str]:
    """URLs already in the shipped Rosetta catalog index — treated as seen."""
    urls: set[str] = set()
    if not BASELINE.exists():
        return urls
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        for m in re.finditer(r"https?://\S+", line):
            urls.add(m.group(0).rstrip(" |)"))
    return urls


# --- discover -----------------------------------------------------------------
def _fetch_listing(url: str) -> list[dict]:
    """Parse the Rosetta creator listing into [{url,title,date,summary}] (newest-first)."""
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    items: list[dict] = []
    for art in soup.select("article.hub-feed-item"):
        link = art.select_one("a.hub-feed-title-link")
        if not link or not link.get("href"):
            continue
        href = link["href"]
        full = href if href.startswith("http") else "https://rosetta.to" + href
        title_el = art.select_one(".hub-feed-title")
        summary_el = art.select_one(".hub-feed-summary")
        meta_el = art.select_one(".hub-feed-meta")
        date = ""
        if meta_el:
            date = meta_el.get_text(" ", strip=True).split("·")[0].strip()
        items.append({
            "url": full,
            "title": title_el.get_text(" ", strip=True) if title_el else "",
            "date": date,
            "summary": summary_el.get_text(" ", strip=True) if summary_el else "",
        })
    return items


def _load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def discover(cfg: dict, state: dict, backfill: int = 0, mock: bool = False) -> list[dict]:
    """Return NEW listing items to process. NEW = url not seen (state + baseline).
    With backfill>0, take the N most-recent items regardless of seen-state."""
    items: list[dict] = []
    if mock:
        items = list(_load_fixture().get("feed", []))
    else:
        if requests is None or BeautifulSoup is None:
            print("[discover] requests/beautifulsoup4 unavailable; nothing fetched", file=sys.stderr)
            return []
        for src in cfg.get("sources", []):
            if not src.get("enabled") or src.get("type") != "rosetta":
                continue
            try:
                items.extend(_fetch_listing(src["url"]))
            except Exception as exc:  # degrade gracefully on fetch errors
                print(f"[discover] fetch failed for {src.get('name', src.get('url'))}: {exc}", file=sys.stderr)

    if backfill and backfill > 0:
        return items[:backfill]

    seen = set(state.get("seen", {})) | load_baseline_urls()
    return [it for it in items if it.get("url") not in seen]


# --- fetch content ------------------------------------------------------------
def fetch_content(url: str, mock: bool = False, fixture_map: dict | None = None) -> str | None:
    """Return the page's meaning-bearing text (summary + Q&A + transcript), or None on failure."""
    if mock:
        item = (fixture_map or {}).get(url)
        if not item:
            return None
        parts = [item.get("summary", ""), item.get("text", "")]
        return "\n".join(p for p in parts if p).strip() or None

    if requests is None or BeautifulSoup is None:
        return None
    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        print(f"[fetch] failed for {url}: {exc}", file=sys.stderr)
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    chunks: list[str] = []
    cap = soup.select_one("p.art-capsule")
    if cap:
        chunks.append(cap.get_text(" ", strip=True))
    for faq in soup.select("div.art-faq"):
        q = faq.select_one("summary")
        a = faq.select_one(".art-faq-answer")
        qt = q.get_text(" ", strip=True) if q else ""
        at = a.get_text(" ", strip=True) if a else ""
        if qt or at:
            chunks.append(f"{qt} {at}".strip())
    prose = soup.select_one("div.prose")
    if prose:
        chunks.append(prose.get_text(" ", strip=True))
    text = "\n".join(c for c in chunks if c).strip()
    return text or None


# --- extract definitions (PLUGGABLE) ------------------------------------------
_LLM_PROMPT = """You extract term definitions from a transcript of Alex Hormozi content.
Return ONLY a JSON array (no prose, no markdown fence). Each element is an object:
  {{"term": str, "short_def": str, "full_def": str, "why_it_matters": str, "category": str}}
Rules — follow exactly:
- Include a term ONLY if the text GENUINELY DEFINES or REDEFINES it. If nothing is defined, return [].
- NEVER fabricate. Every field must be supported by the text. No invented quotes, numbers, or claims.
- short_def: one plain-English sentence. full_def: 2-4 sentences paraphrased (not verbatim).
- why_it_matters: why adopting this definition changes how someone sees or decides.
- category: best guess, one of: {categories}.
Source URL: {url}

TEXT:
{text}
"""


def _run_llm(prompt: str) -> str | None:
    cmd = os.environ.get("SWEEP_LLM_CMD")
    if not cmd:
        return None
    try:
        proc = subprocess.run(
            shlex.split(cmd), input=prompt, capture_output=True, text=True,
            timeout=int(os.environ.get("SWEEP_LLM_TIMEOUT", "240")),
        )
    except Exception as exc:
        print(f"[extract] LLM command failed: {exc}", file=sys.stderr)
        return None
    if proc.returncode != 0:
        print(f"[extract] LLM exited {proc.returncode}: {proc.stderr.strip()[:200]}", file=sys.stderr)
        return None
    return proc.stdout


def _parse_json_candidates(raw: str | None) -> list[dict]:
    """Defensively pull a JSON array/object of candidates out of arbitrary model output."""
    if not raw:
        return []
    txt = raw.strip()
    # strip a ```json ... ``` fence if present
    fence = re.search(r"```(?:json)?\s*(.+?)```", txt, re.S)
    if fence:
        txt = fence.group(1).strip()
    data = None
    try:
        data = json.loads(txt)
    except Exception:
        m = re.search(r"\[.*\]", txt, re.S)  # first bracketed array
        if m:
            try:
                data = json.loads(m.group(0))
            except Exception:
                data = None
    if isinstance(data, dict):
        data = data.get("definitions") or data.get("terms") or [data]
    if not isinstance(data, list):
        return []
    out = []
    for d in data:
        if isinstance(d, dict) and d.get("term") and d.get("short_def"):
            out.append(d)
    return out


_DEFINE_RE = re.compile(r"\b(?:defines|redefines|reframes)\b\s+(.+?)\s+\bas\b\s+(.+)", re.I)
_CONCEPT_RE = re.compile(r"\bintroduces the concept of\b\s+(.+)", re.I)


def _clean_term(term: str) -> str | None:
    t = (term or "").strip().strip("'\"“”‘’").strip()
    t = re.sub(r"^(the|a|an)\s+", "", t, flags=re.I)
    t = t.rstrip(".,;:—- ")
    if not re.search(r"[A-Za-z]", t) or len(t.split()) > 8:
        return None
    return t


def _heuristic_extract(text: str, source_url: str) -> list[dict]:
    """Offline stub: pull definitional sentences via cue phrases. Deterministic."""
    sents = _split_sentences(text)
    out: list[dict] = []
    seen: set[str] = set()
    for i, s in enumerate(sents):
        term = defn = None
        m = _DEFINE_RE.search(s)
        if m:
            term, defn = m.group(1), m.group(2)
        else:
            mc = _CONCEPT_RE.search(s)
            if mc:
                term = mc.group(1)
                nxt = sents[i + 1] if i + 1 < len(sents) else s
                dm = _DEFINE_RE.search(nxt)  # unwrap "He defines X as Y" -> "Y"
                defn = dm.group(2) if dm else nxt
        term = _clean_term(term) if term else None
        if not term:
            continue
        key = _norm(term)
        if key in seen:
            continue
        seen.add(key)
        short = defn.strip().rstrip(".") + "." if defn else ""
        short = short[0].upper() + short[1:] if short else short
        context = " ".join(sents[i:i + 3])
        why = next(
            (x for x in sents if re.search(r"\b(argues|because|means|engine|so that|the point|matters)\b", x, re.I)),
            f"Adopting Hormozi's framing of {term} changes how you interpret and act on it.",
        )
        out.append({
            "term": term,
            "short_def": short or context,
            "full_def": context,
            "why_it_matters": why,
            "category": _guess_category(context),
        })
    return out


def extract_definitions(text: str, source_url: str, mock: bool = False,
                        fixture_item: dict | None = None) -> list[dict]:
    """PLUGGABLE. Real path shells out to SWEEP_LLM_CMD; mock/no-cmd uses an offline stub."""
    if not text:
        return []
    if not mock and os.environ.get("SWEEP_LLM_CMD"):
        prompt = _LLM_PROMPT.format(categories=", ".join(lib.CATEGORY_ORDER), url=source_url, text=text[:16000])
        cands = _parse_json_candidates(_run_llm(prompt))
    else:
        # fixture mode (deterministic) if the item pre-declares definitions, else heuristic
        if fixture_item and fixture_item.get("definitions"):
            cands = [dict(d) for d in fixture_item["definitions"]]
        else:
            cands = _heuristic_extract(text, source_url)

    # normalize / sanity-fill each candidate
    clean: list[dict] = []
    for c in cands:
        term = (c.get("term") or "").strip()
        if not term or not (c.get("short_def") or "").strip():
            continue
        cat = c.get("category")
        if cat not in lib.CATEGORIES:
            cat = _guess_category(f"{term} {c.get('short_def','')} {c.get('full_def','')}")
        clean.append({
            "term": term,
            "short_def": c["short_def"].strip(),
            "full_def": (c.get("full_def") or c["short_def"]).strip(),
            "why_it_matters": (c.get("why_it_matters") or "").strip()
            or f"Adopting Hormozi's framing of {term} changes how you interpret and act on it.",
            "category": cat,
        })
    return clean


# --- classify -----------------------------------------------------------------
def _term_index(entries: list[dict]) -> dict[str, dict]:
    idx: dict[str, dict] = {}
    for e in entries:
        idx[_norm(e["term"])] = e
        for a in (e.get("aliases") or []):
            idx[_norm(a)] = e
    return idx


def classify(candidates: list[dict], current: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split candidates into (adds, changes, skipped)."""
    idx = _term_index(current)
    used_ids = {e["id"] for e in current}
    adds: list[dict] = []
    changes: list[dict] = []
    skipped: list[dict] = []
    for c in candidates:
        existing = idx.get(_norm(c["term"]))
        if existing is None:
            adds.append(_build_add(c, used_ids))
            used_ids.add(adds[-1]["id"])
            continue
        old_text = f"{existing.get('short_def','')} {existing.get('full_def','')}".strip()
        new_text = f"{c['short_def']} {c['full_def']}".strip()
        ratio = difflib.SequenceMatcher(None, old_text, new_text).ratio()
        if ratio < SIMILARITY_THRESHOLD:
            changes.append(_build_change(c, existing, ratio))
        else:
            skipped.append({"term": c["term"], "id": existing["id"], "reason": f"similar (ratio {ratio:.2f})"})
    return adds, changes, skipped


def _build_add(c: dict, used_ids: set[str]) -> dict:
    base = slugify(c["term"])
    _id = base
    n = 2
    while _id in used_ids:
        _id = f"{base}-{n}"
        n += 1
    return {
        "id": _id,
        "term": c["term"],
        "category": c["category"],
        "short_def": c["short_def"],
        "full_def": c["full_def"],
        "why_it_matters": c["why_it_matters"],
        "source_url": c.get("source_url", ""),
        "source_label": c.get("source_label", ""),
        "confidence": "medium",
        "first_seen": _year(c.get("source_date")),
    }


def _build_change(c: dict, existing: dict, ratio: float) -> dict:
    changed_fields = [f for f in ("short_def", "full_def")
                      if (existing.get(f) or "").strip() != (c.get(f) or "").strip()]
    return {
        "id": existing["id"],
        "term": existing["term"],
        "category": existing["category"],
        "source_url": c.get("source_url", ""),
        "source_label": c.get("source_label", ""),
        "confidence": "medium",
        "similarity": round(ratio, 3),
        "changed_fields": changed_fields,
        "old": {"short_def": existing.get("short_def", ""), "full_def": existing.get("full_def", "")},
        "new": {"short_def": c["short_def"], "full_def": c["full_def"], "why_it_matters": c["why_it_matters"]},
    }


# --- proposals ----------------------------------------------------------------
def write_proposals(adds: list[dict], changes: list[dict], date: str) -> tuple[pathlib.Path, pathlib.Path]:
    PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
    yml_path = PROPOSALS_DIR / f"{date}.yml"
    md_path = PROPOSALS_DIR / f"{date}.md"

    doc = {
        "date": date,
        "generated": datetime.datetime.now().isoformat(timespec="seconds"),
        "site_url": SITE_URL,
        "adds": adds,
        "changes": changes,
    }
    yml_path.write_text(
        yaml.safe_dump(doc, default_flow_style=False, allow_unicode=True, sort_keys=False, width=10 ** 9),
        encoding="utf-8",
    )

    lines = [f"# Sweep proposals — {date}", ""]
    lines.append(f"**{len(adds)} new** · **{len(changes)} revised**  ·  review, then "
                 f"`python3 sweep/sweep.py --apply sweep/proposals/{date}.yml`")
    lines.append("")
    lines.append("> Unofficial / educational. Definitions are paraphrased & attributed, not verbatim quotes.")
    lines.append("")
    if adds:
        lines.append("## New terms")
        lines.append("")
        for a in adds:
            src = f" — source: {a['source_url']}" if a.get("source_url") else ""
            lines.append(f"### {a['term']}  `{a['category']}`  ({a['confidence']}){src}")
            lines.append(f"- **short_def:** {a['short_def']}")
            lines.append(f"- **full_def:** {a['full_def']}")
            lines.append(f"- **why_it_matters:** {a['why_it_matters']}")
            lines.append("")
    if changes:
        lines.append("## Revised definitions (review before publishing)")
        lines.append("")
        for ch in changes:
            src = f" — source: {ch['source_url']}" if ch.get("source_url") else ""
            lines.append(f"### {ch['term']}  `{ch['category']}`  (similarity {ch.get('similarity','?')}){src}")
            lines.append(f"- changed: {', '.join(ch.get('changed_fields') or []) or 'n/a'}")
            lines.append(f"- **old short_def:** {ch['old']['short_def']}")
            lines.append(f"- **new short_def:** {ch['new']['short_def']}")
            lines.append(f"- **old full_def:** {ch['old']['full_def']}")
            lines.append(f"- **new full_def:** {ch['new']['full_def']}")
            lines.append("")
    md_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    return yml_path, md_path


# --- apply --------------------------------------------------------------------
class _Dumper(yaml.SafeDumper):
    pass


def _dump_entries(entries: list[dict]) -> str:
    def ordered(e: dict) -> dict:
        d = {k: e[k] for k in KEY_ORDER if k in e}
        for k in e:  # keep any unexpected keys rather than dropping data
            d.setdefault(k, e[k])
        return d
    return yaml.dump(
        [ordered(e) for e in entries], Dumper=_Dumper,
        default_flow_style=False, allow_unicode=True, sort_keys=False, width=10 ** 9,
    )


def _glossary_header() -> str:
    lines = lib.GLOSSARY.read_text(encoding="utf-8").splitlines(keepends=True)
    hdr = []
    for ln in lines:
        if ln.lstrip().startswith("#"):
            hdr.append(ln)
        else:
            break
    return "".join(hdr)


def _write_glossary(entries: list[dict]) -> None:
    lib.GLOSSARY.write_text(_glossary_header() + _dump_entries(entries), encoding="utf-8")


def _sorted_insert(entries: list[dict], new: dict) -> None:
    order_idx = {c: i for i, c in enumerate(lib.CATEGORY_ORDER)}
    key = (order_idx.get(new["category"], 99), new["term"].lower())
    for i, e in enumerate(entries):
        if (order_idx.get(e["category"], 99), e["term"].lower()) > key:
            entries.insert(i, new)
            return
    entries.append(new)


def _add_to_entry(add: dict, date: str) -> dict:
    src_label = add.get("source_label") or ("Rosetta" if "rosetta.to" in (add.get("source_url") or "") else "source")
    entry = {
        "id": add["id"],
        "term": add["term"],
        "category": add["category"],
        "short_def": add["short_def"],
        "full_def": add["full_def"],
        "why_it_matters": add["why_it_matters"],
        "sources": [{"label": src_label, "url": add.get("source_url", "")}],
        "confidence": add.get("confidence", "medium"),
        "first_seen": add.get("first_seen") or _year(date),
        "last_updated": date,
        "status": "active",
    }
    return entry


def _changelog_lines(adds: list[dict], changes: list[dict]) -> list[str]:
    out = []
    for a in adds:
        src = a.get("source_label") or "source"
        out.append(f"- **Added** [{a['term']}]({SITE_URL}/#{a['id']}) — {a['short_def']} _{'('+src+')'}_")
    for ch in changes:
        src = ch.get("source_label") or "source"
        what = "revised definition (" + ", ".join(ch.get("changed_fields") or ["definition"]) + ")"
        out.append(f"- **Revised** [{ch['term']}]({SITE_URL}/#{ch['id']}) — {what} _{'('+src+')'}_")
    return out


def _append_changelog(new_lines: list[str], date: str) -> None:
    if not new_lines:
        return
    text = CHANGELOG.read_text(encoding="utf-8")
    lines = text.splitlines()
    heading = f"## {date} — Sweep"
    # find an existing sweep section for this date
    idx = next((i for i, ln in enumerate(lines) if ln.strip() == heading), None)
    if idx is not None:
        insert_at = idx + 1
        while insert_at < len(lines) and not lines[insert_at].startswith("## "):
            insert_at += 1
        block = ([""] if lines[insert_at - 1].strip() else []) + new_lines
        lines[insert_at:insert_at] = block
    else:
        first_section = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
        block = [heading, ""] + new_lines + [""]
        lines[first_section:first_section] = block
    CHANGELOG.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def apply(props: dict, mode: str = "apply") -> dict:
    """Apply a reviewed proposals doc to glossary.yml + CHANGELOG.md; re-validate.

    mode="apply"          -> adds + changes
    mode="auto-additive"  -> adds that carry a source url only; changes skipped
    """
    date = props.get("date") or _today()
    entries = lib.load()  # raw list; header preserved separately
    ids = {e["id"] for e in entries}
    term_idx = _term_index(entries)

    adds_in = props.get("adds") or []
    changes_in = props.get("changes") or []
    if mode == "auto-additive":
        adds_in = [a for a in adds_in if (a.get("source_url") or "").strip()]
        changes_in = []

    applied_adds: list[dict] = []
    for a in adds_in:
        if _norm(a["term"]) in term_idx:  # already exists — don't duplicate
            continue
        if a.get("id") in ids:
            a = dict(a, id=f"{a['id']}-{len(ids)}")
        entry = _add_to_entry(a, date)
        _sorted_insert(entries, entry)
        ids.add(entry["id"])
        term_idx[_norm(entry["term"])] = entry
        applied_adds.append(a)

    applied_changes: list[dict] = []
    by_id = {e["id"]: e for e in entries}
    for ch in changes_in:
        e = by_id.get(ch["id"])
        if not e:
            continue
        new = ch.get("new") or {}
        for f in ("short_def", "full_def", "why_it_matters", "formula", "components", "aliases"):
            if f in new and new[f] not in (None, ""):
                e[f] = new[f]
        e["last_updated"] = date
        e["status"] = "revised"
        applied_changes.append(ch)

    _write_glossary(entries)
    _append_changelog(_changelog_lines(applied_adds, applied_changes), date)

    errs = lib.validate(lib.load())
    if errs:
        raise SystemExit("apply produced INVALID glossary.yml:\n  " + "\n  ".join(errs))
    return {"added": len(applied_adds), "revised": len(applied_changes)}


# --- pipeline & CLI -----------------------------------------------------------
def run_pipeline(cfg: dict, state: dict, args) -> dict:
    current = lib.load_valid()
    # {id: content_hash} map — lets a later run detect drift in existing entries
    state.setdefault("hashes", {})
    hashes = {e["id"]: lib.content_hash(e) for e in current}

    items = discover(cfg, state, backfill=args.backfill or 0, mock=args.mock)
    fixture_map = {it["url"]: it for it in items} if args.mock else {}

    candidates: list[dict] = []
    processed_urls: list[str] = []
    for it in items:
        url = it.get("url", "")
        text = fetch_content(url, mock=args.mock, fixture_map=fixture_map)
        if not text:
            continue  # failed fetch -> not marked seen, retried next run
        cands = extract_definitions(text, url, mock=args.mock, fixture_item=it)
        if cands is None:
            continue
        for c in cands:  # attach source metadata for downstream stages
            c["source_url"] = url
            c["source_label"] = (it.get("title") + " (Rosetta)") if it.get("title") else "Rosetta"
            c["source_date"] = it.get("date", "")
        candidates.extend(cands)
        processed_urls.append(url)  # extraction succeeded -> safe to mark seen

    adds, changes, skipped = classify(candidates, current)
    date = _today()
    yml_path, md_path = write_proposals(adds, changes, date)

    auto = {"added": 0, "revised": 0}
    if args.auto_additive and adds:
        auto = apply({"date": date, "adds": adds, "changes": []}, mode="auto-additive")

    # mark successfully-processed items as seen (skip in mock to keep runs reproducible)
    if not args.mock:
        for it in items:
            if it.get("url") in processed_urls:
                state["seen"][it["url"]] = {"title": it.get("title", ""), "date": it.get("date", ""),
                                            "processed_at": _today()}
        state["hashes"] = hashes
        save_state(cfg, state)

    return {
        "new": len(adds), "changed": len(changes), "skipped": len(skipped),
        "processed": len(processed_urls), "discovered": len(items),
        "proposals_yml": yml_path, "proposals_md": md_path, "auto": auto,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Hormozi Glossary content sweep")
    ap.add_argument("--dry-run", action="store_true",
                    help="discover + extract + classify + write proposals; no glossary/changelog writes (default)")
    ap.add_argument("--apply", metavar="PROPOSALS.yml",
                    help="apply a reviewed proposals file (adds + changes) to glossary.yml + CHANGELOG.md")
    ap.add_argument("--auto-additive", action="store_true",
                    help="run the pipeline, then auto-apply only NEW terms that carry a source url")
    ap.add_argument("--backfill", type=int, default=0, metavar="N",
                    help="consider the N most-recent items regardless of seen-state")
    ap.add_argument("--mock", action="store_true", help="run fully offline using the bundled fixture")
    args = ap.parse_args(argv)

    if args.apply:
        p = pathlib.Path(args.apply)
        props = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        res = apply(props, mode="apply")
        print(f"applied {args.apply}: +{res['added']} added, ~{res['revised']} revised "
              f"→ glossary.yml + CHANGELOG.md re-validated OK")
        return 0

    cfg = load_config()
    state = load_state(cfg)
    res = run_pipeline(cfg, state, args)

    print("─" * 60)
    print(f"sweep {'(mock)' if args.mock else ''}: discovered {res['discovered']}, "
          f"processed {res['processed']}")
    print(f"  new: {res['new']}   changed: {res['changed']}   skipped: {res['skipped']}")
    if args.auto_additive:
        print(f"  auto-applied (additive): +{res['auto']['added']} added")
    print(f"  proposals: {res['proposals_yml']}")
    print(f"             {res['proposals_md']}")
    print("─" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
