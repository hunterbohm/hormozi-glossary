#!/usr/bin/env python3
"""Mine the corpus for terms Hormozi NAMES/COINS that aren't in the glossary yet.

Targets high-precision naming patterns ("I call this X", "what I call the X",
"I coined the term X") rather than every "X is ...". Dedupes against existing terms,
ranks by how often he uses the coinage. Output feeds a human/agent curation pass.

Usage:  python3 corpus/mine_new.py
"""
from __future__ import annotations
import collections
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build"))
import lib  # noqa: E402

TX = HERE / "transcripts"
OUT = HERE / "new_candidates.json"

NAMING = [
    re.compile(r"\bI call (?:it|this|that|them|these) (?:the |a |an )?([a-z][\w' \-]{2,38}?)[.,;]", re.I),
    re.compile(r"\bwhat I call (?:the |a |an )?([\w' \-]{2,38}?)[.,;]", re.I),
    re.compile(r"\bI coined the (?:term|phrase|word)\s+['\"]?([\w' \-]{2,38}?)['\"]?[.,;]", re.I),
    re.compile(r"\bI (?:refer to|describe) (?:it|this|that) as (?:the |a )?([\w' \-]{2,38}?)[.,;]", re.I),
]
SENT = re.compile(r"(?<=[.!?])\s+")
STOP = {"the", "a", "an", "it", "this", "that", "them", "these", "my", "your", "our", "of"}


def norm(s: str) -> str:
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if w not in STOP)


def existing_names() -> set[str]:
    names = set()
    for e in lib.load(lib.GLOSSARY):
        for n in [e["term"], *(e.get("aliases") or [])]:
            k = norm(re.sub(r"\s*\(.*?\)", "", n))
            if k:
                names.add(k)
    return names


def header(raw: str) -> dict:
    h = {}
    for ln in raw.splitlines()[:8]:
        if not ln.startswith("#"):
            break
        m = re.match(r"#\s*([A-Za-z]+):\s*(.*)", ln)
        if m:
            h[m.group(1).lower()] = m.group(2).strip()
        elif ln.startswith("# ") and "title" not in h:
            h["title"] = ln[2:].strip()
    return h


def main() -> int:
    have = existing_names()
    agg: dict[str, dict] = {}
    for p in sorted(TX.glob("*.txt")):
        raw = p.read_text(encoding="utf-8", errors="ignore")
        h = header(raw)
        body = raw.split("\n\n", 1)[1] if "\n\n" in raw else raw
        src = (h.get("title", p.name)).split("|")[0].strip()
        url = h.get("youtube") or h.get("rosetta") or h.get("url") or ""
        for s in SENT.split(body):
            if not (12 <= len(s) <= 300):
                continue
            for rx in NAMING:
                m = rx.search(s)
                if not m:
                    continue
                term = m.group(1).strip(" '\"-")
                k = norm(term)
                if len(k) < 3 or k in have or k in STOP or len(k.split()) > 6:
                    continue
                rec = agg.setdefault(k, {"term": term, "count": 0, "quote": s.strip(), "source": src, "url": url})
                rec["count"] += 1
                if len(s) < len(rec["quote"]):  # keep the tightest example
                    rec["quote"], rec["source"], rec["url"] = s.strip(), src, url
    ranked = sorted(agg.values(), key=lambda r: -r["count"])
    OUT.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"candidate NEW coinages: {len(ranked)}  (written {OUT.name})")
    print("top 25 by frequency:")
    for r in ranked[:25]:
        print(f"  {r['count']:>3}x  {r['term'][:40]:40}  [{r['source'][:38]}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
