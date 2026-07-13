#!/usr/bin/env python3
"""For every glossary term, scan the local corpus and extract the best short
DEFINITIONAL sentence(s) where Hormozi states it, with the source citation.

Output: corpus/candidates/<id>.json (top snippets per term) + corpus/candidates/_index.json
(coverage). Quotes are capped short (fair-use evidence pointers, never long excerpts).
This front-loads the evidence search so the verification pass is consistent.
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
OUT = HERE / "candidates"
MAXLEN = 340  # cap evidence-quote length (fair use)

CUES = re.compile(
    r"\b(is just|is basically|is essentially|is when|is the|means?|i define|we define|"
    r"definition of|the difference between|refers to|what i mean by|i call (?:it|this|that)|"
    r"which is|is nothing more than)\b", re.I)
SENT = re.compile(r"(?<=[.!?])\s+")


def parse_header(text: str) -> dict:
    h: dict = {}
    for ln in text.splitlines()[:8]:
        if not ln.startswith("#"):
            break
        m = re.match(r"#\s*([A-Za-z]+):\s*(.*)", ln)
        if m:
            h[m.group(1).lower()] = m.group(2).strip()
        elif ln.startswith("# ") and "title" not in h:
            h["title"] = ln[2:].strip()
    return h


def citation(path: pathlib.Path, h: dict) -> tuple[str, str]:
    name = path.name
    title = (h.get("title", "") or name).split("|")[0].strip()
    if name.startswith("thegame_"):
        ep = h.get("ep", "")
        return (f"The Game w/ Alex Hormozi — Ep {ep}: {title}".rstrip(": "), h.get("youtube", "") or "")
    return (title, h.get("youtube") or h.get("rosetta") or h.get("url") or "")


def sentences(t: str) -> list[str]:
    return [s.strip() for s in SENT.split(t) if s.strip()]


def load_corpus() -> list[tuple]:
    docs = []
    for p in sorted(TX.glob("*.txt")):
        raw = p.read_text(encoding="utf-8", errors="ignore")
        body = raw.split("\n\n", 1)[1] if "\n\n" in raw else raw
        docs.append((p, parse_header(raw), body, body.lower()))
    return docs


def patterns(e: dict) -> list[str]:
    out = []
    for n in [e["term"], *(e.get("aliases") or [])]:
        n = re.sub(r"\s*\(.*?\)", "", n).strip().lower()
        if len(n) >= 3:
            out.append(n)
    return out


def candidates_for(e: dict, docs: list[tuple], topn: int = 6) -> list[dict]:
    pats = patterns(e)
    hits = []
    for p, h, body, low in docs:
        if not any(pat in low for pat in pats):
            continue
        for s in sentences(body):
            sl = s.lower()
            if 20 <= len(s) <= MAXLEN and any(pat in sl for pat in pats):
                score = (2 if CUES.search(s) else 0) + sum(1 for q in pats if q in sl)
                hits.append((score, len(s), s, p, h))
    seen, uniq = set(), []
    for sc, _ln, s, p, h in sorted(hits, key=lambda x: (-x[0], x[1])):
        k = s.lower()[:80]
        if k in seen:
            continue
        seen.add(k)
        label, url = citation(p, h)
        uniq.append({"score": sc, "quote": s, "source": label, "url": url, "file": p.name})
        if len(uniq) >= topn:
            break
    return uniq


def main() -> int:
    OUT.mkdir(exist_ok=True)
    docs = load_corpus()
    entries = lib.load_valid()
    index = []
    for e in entries:
        cands = candidates_for(e, docs)
        (OUT / f"{e['id']}.json").write_text(json.dumps({
            "id": e["id"], "term": e["term"], "aliases": e.get("aliases", []),
            "category": e["category"], "short_def": e["short_def"], "full_def": e["full_def"],
            "candidates": cands,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        index.append({"id": e["id"], "term": e["term"], "category": e["category"],
                      "n": len(cands), "best_score": cands[0]["score"] if cands else 0})
    (OUT / "_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    strong = sum(1 for r in index if r["best_score"] >= 3)
    some = sum(1 for r in index if r["n"] > 0)
    print(f"corpus docs: {len(docs)} | terms: {len(index)}")
    print(f"  strong definitional candidate (cue+term): {strong}")
    print(f"  some candidate: {some}")
    print(f"  NO candidate (needs book-cite/web/flag): {len(index) - some}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
