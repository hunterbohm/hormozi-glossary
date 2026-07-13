#!/usr/bin/env python3
"""Broad definitional miner — find WORDS/CONCEPTS Hormozi DEFINES, not just coinages.

Casts a wide net over strong 'defining' constructions ("X is just...", "I define X as...",
"the way I think about X", "there are N types of X"), dedupes against the current glossary,
ranks by how often he defines each. Output feeds a curation wave.

Usage:  python3 corpus/mine_definitions.py
"""
from __future__ import annotations
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "build"))
import lib  # noqa: E402

TX = HERE / "transcripts"
OUT = HERE / "definition_candidates.json"

# high-precision definitional frames; group(1) = the term/concept being defined
PATTERNS = [
    re.compile(r"\b([a-z][a-z'\-]{3,24}) is (?:just|basically|essentially|really|literally|simply|"
               r"nothing more than|nothing but|the art of|the skill of|the ability to|the process of|"
               r"the willingness to|the gap between|the cost of|the byproduct of|when you|"
               r"not about|not a |not an |not the )", re.I),
    re.compile(r"\bI define ([\w '\-]{3,30}?) as\b", re.I),
    re.compile(r"\bthe way I (?:think about|define|see) ([\w '\-]{3,30}?)(?: is|,)", re.I),
    re.compile(r"\bwhat (?:most )?people (?:get wrong about|don't understand about|"
               r"misunderstand about|don't get about) ([\w '\-]{3,30}?)[.,]", re.I),
    re.compile(r"\bthere are (?:two|three|four|five|\d+) (?:types|kinds) of ([\w '\-]{3,30}?)[.,:]", re.I),
    re.compile(r"\b([a-z][a-z'\-]{3,24}) means (?:that )?(?:you|your|the|a |an |having|being|doing)", re.I),
]
STOP = set(("it this that there here he she we they you i what who a an the my your our their his her "
            "its one thing things people someone something everything nothing anyone everyone them me "
            "us that's there's it's what's and but so because if when then now").split())


def norm(s: str) -> str:
    return " ".join(w for w in re.sub(r"[^a-z0-9 ]", " ", s.lower()).split() if w not in STOP)


def header(raw: str) -> dict:
    h: dict = {}
    for ln in raw.splitlines()[:8]:
        if not ln.startswith("#"):
            break
        m = re.match(r"#\s*([A-Za-z]+):\s*(.*)", ln)
        if m:
            h[m.group(1).lower()] = m.group(2).strip()
        elif ln.startswith("# ") and "title" not in h:
            h["title"] = ln[2:].strip()
    return h


def existing_names() -> set[str]:
    names = set()
    for e in lib.load(lib.GLOSSARY):
        for n in [e["term"], *(e.get("aliases") or [])]:
            names.add(norm(re.sub(r"\s*\(.*?\)", "", n)))
    return names


SENT = re.compile(r"(?<=[.!?])\s+")


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
            if not (16 <= len(s) <= 300):
                continue
            for rx in PATTERNS:
                m = rx.search(s)
                if not m:
                    continue
                term = m.group(1).strip(" '\"-")
                k = norm(term)
                if len(k) < 4 or k in have or len(k.split()) > 4:
                    continue
                rec = agg.setdefault(k, {"term": term, "count": 0, "quote": s.strip(), "source": src, "url": url})
                rec["count"] += 1
                if len(s) < len(rec["quote"]):
                    rec["quote"], rec["source"], rec["url"] = s.strip(), src, url
                break
    ranked = sorted(agg.values(), key=lambda r: -r["count"])
    OUT.write_text(json.dumps(ranked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"definitional candidates NOT already in glossary: {len(ranked)}")
    print("top 40 by frequency:")
    for r in ranked[:40]:
        print(f"  {r['count']:>3}x  {r['term'][:32]:32} [{r['source'][:32]}]")
    res = [r for r in ranked if "resistance" in r["term"].lower()]
    print("\nresistance in candidates:", [(r["term"], r["count"]) for r in res])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
