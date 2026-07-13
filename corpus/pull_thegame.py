#!/usr/bin/env python3
"""Harvest 'The Game w/ Alex Hormozi' episode transcripts from the podcast RSS feed.

The feed exposes a <podcast:transcript> JSON per episode (Flightcast/Captivate, no auth).
Audiobook-chapter episodes (his book text read aloud) are EXCLUDED as copyrighted — the
glossary cites the books for those. Corpus is a local, gitignored evidence base; the public
site keeps only short attributed quotes.

Usage:
  python3 corpus/pull_thegame.py                 # all non-audiobook episodes
  python3 corpus/pull_thegame.py --limit 5       # first N (testing)
"""
from __future__ import annotations
import argparse
import html
import json
import pathlib
import re
import time

import requests

HERE = pathlib.Path(__file__).resolve().parent
TDIR = HERE / "transcripts"
MANIFEST = HERE / "manifest.jsonl"
FEED = "https://rss2.flightcast.com/zz5nwp81tktx53wb8fw6qq7j.xml"
UA = {"User-Agent": "hormozi-glossary-corpus/1.0 (+educational research)"}

ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
TITLE_RE = re.compile(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", re.S)
DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.S)
TRANSCRIPT_RE = re.compile(r'<podcast:transcript[^>]*\burl="([^"]+)"[^>]*>', re.I)
JSON_TRANSCRIPT_RE = re.compile(
    r'<podcast:transcript[^>]*\burl="([^"]+)"[^>]*type="application/json"', re.I)
EP_RE = re.compile(r"\bEp\.?\s*(\d+)\b", re.I)
# copyrighted book-text-read-aloud episodes — skip
AUDIOBOOK_RE = re.compile(r"audiobook|lost chapters|\baudio ?book\b", re.I)


def slugify(s: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:60] or "ep"


def transcript_text(url: str, timeout: int = 30) -> str | None:
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        r.raise_for_status()
    except Exception:
        return None
    try:
        j = r.json()
    except Exception:
        return None
    segs = j.get("segments") if isinstance(j, dict) else (j if isinstance(j, list) else None)
    if isinstance(segs, list):
        parts = [str(s.get("body") or s.get("text") or "") for s in segs if isinstance(s, dict)]
        text = " ".join(p for p in parts if p)
    else:
        text = ""
    return re.sub(r"\s+", " ", text).strip() or None


def parse_feed(text: str) -> list[dict]:
    items = []
    for block in ITEM_RE.findall(text):
        t = TITLE_RE.search(block)
        title = html.unescape(t.group(1).strip()) if t else ""
        turl = JSON_TRANSCRIPT_RE.search(block) or TRANSCRIPT_RE.search(block)
        d = DATE_RE.search(block)
        ep = EP_RE.search(title)
        items.append({
            "title": title,
            "date": d.group(1).strip() if d else "",
            "ep": int(ep.group(1)) if ep else None,
            "turl": turl.group(1) if turl else None,
        })
    return items


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.2)
    args = ap.parse_args()
    TDIR.mkdir(parents=True, exist_ok=True)
    feed = requests.get(FEED, headers=UA, timeout=60).text
    items = parse_feed(feed)
    total = len(items)
    kept = [it for it in items if it["turl"] and not AUDIOBOOK_RE.search(it["title"])]
    skipped_ab = sum(1 for it in items if AUDIOBOOK_RE.search(it["title"]))
    no_tx = sum(1 for it in items if not it["turl"])
    if args.limit:
        kept = kept[: args.limit]
    print(f"feed items: {total}  | audiobook-excluded: {skipped_ab} | no-transcript: {no_tx} | to pull: {len(kept)}")
    ok = skip = fail = 0
    for i, it in enumerate(kept, 1):
        epn = f"ep{it['ep']:04d}" if it["ep"] else "epx"
        dst = TDIR / f"thegame_{epn}_{slugify(it['title'])}.txt"
        if dst.exists():
            skip += 1
            continue
        text = transcript_text(it["turl"])
        if not text or len(text) < 60:
            fail += 1
            continue
        header = (f"# The Game — {it['title']}\n# ep: {it['ep']}\n# date: {it['date']}\n"
                  f"# source: The Game w/ Alex Hormozi (podcast)\n# transcript: {it['turl']}\n\n")
        dst.write_text(header + text, encoding="utf-8")
        with open(MANIFEST, "a", encoding="utf-8") as m:
            m.write(json.dumps({"src": "thegame", "ep": it["ep"], "title": it["title"],
                                "date": it["date"], "chars": len(text)}, ensure_ascii=False) + "\n")
        ok += 1
        if i % 50 == 0:
            print(f"  .. {i}/{len(kept)} (ok {ok}, skip {skip}, fail {fail})")
        time.sleep(args.sleep)
    print(f"pulled {ok} new, skipped {skip}, failed {fail} -> {TDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
