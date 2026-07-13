#!/usr/bin/env python3
"""Harvest transcripts from the cached Rosetta.to catalog into the local corpus.

Rosetta pages carry a full transcript + the original YouTube source link, so this
gives a clean, uniform evidence base for his YouTube content without re-hitting
YouTube. Corpus is gitignored (evidence base only); the public site keeps short quotes.

Usage:
  python3 corpus/pull_rosetta.py                 # all URLs in data/rosetta-index.md
  python3 corpus/pull_rosetta.py <rosetta_url>   # a single page
  python3 corpus/pull_rosetta.py --limit 50      # first N (for testing)
"""
from __future__ import annotations
import argparse
import json
import pathlib
import re
import time

import requests
from bs4 import BeautifulSoup

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
TDIR = HERE / "transcripts"
MANIFEST = HERE / "manifest.jsonl"
INDEX = ROOT / "data" / "rosetta-index.md"
UA = {"User-Agent": "hormozi-glossary-corpus/1.0 (+educational research)"}
URL_RE = re.compile(r"https?://rosetta\.to/u/alexhormozi/[A-Za-z0-9\-]+")
YT_RE = re.compile(r"https?://(?:www\.)?youtube\.com/watch\?v=[A-Za-z0-9_-]{11}")


def index_urls() -> list[str]:
    if not INDEX.exists():
        return []
    seen, out = set(), []
    for u in URL_RE.findall(INDEX.read_text(encoding="utf-8")):
        if u not in seen and not u.endswith("/alexhormozi"):
            seen.add(u)
            out.append(u)
    return out


def slug(url: str) -> str:
    return url.rstrip("/").rsplit("/", 1)[-1]


def harvest(url: str, timeout: int = 30) -> dict:
    sl = slug(url)
    dst = TDIR / f"rosetta_{sl}.txt"
    if dst.exists():
        return {"slug": sl, "ok": True, "skipped": True}
    TDIR.mkdir(parents=True, exist_ok=True)
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        r.raise_for_status()
    except Exception as e:
        return {"slug": sl, "ok": False, "err": f"fetch: {e}"[:80]}
    soup = BeautifulSoup(r.text, "html.parser")
    full = soup.get_text("\n")
    title = (soup.find("h1").get_text(strip=True) if soup.find("h1") else sl)
    yt = ""
    for a in soup.find_all("a", href=True):
        m = YT_RE.search(a["href"])
        if m:
            yt = m.group(0)
            break
    # slice out the transcript body: between the "Full transcript" marker and the
    # "Originally published" / "## Source" footer.
    txt = full
    lo = full.lower().find("full transcript")
    if lo != -1:
        txt = full[lo + len("full transcript"):]
    for marker in ("Originally published on", "\nSource\n", "Generated from captions"):
        hi = txt.find(marker)
        if hi != -1:
            txt = txt[:hi]
    txt = re.sub(r"\n{2,}", "\n", txt)
    txt = re.sub(r"[ \t]+", " ", txt).strip()
    # drop a leading "Show full transcript" toggle + repeated heading echoes
    txt = re.sub(r"^\s*Show full transcript\s*", "", txt, flags=re.I).strip()
    if len(txt) < 60:
        return {"slug": sl, "ok": False, "err": "transcript too short/absent"}
    date_m = re.search(r"([A-Z][a-z]+ \d{1,2}, \d{4})", full)
    date = date_m.group(1) if date_m else ""
    header = (f"# {title}\n# rosetta: {url}\n# youtube: {yt}\n# date: {date}\n\n")
    dst.write_text(header + txt, encoding="utf-8")
    rec = {"slug": sl, "ok": True, "chars": len(txt), "title": title, "youtube": yt, "date": date}
    with open(MANIFEST, "a", encoding="utf-8") as m:
        m.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url", nargs="?")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.3)
    args = ap.parse_args()
    urls = [args.url] if args.url else index_urls()
    if args.limit:
        urls = urls[: args.limit]
    ok = skip = fail = 0
    for i, u in enumerate(urls, 1):
        r = harvest(u)
        if r.get("skipped"):
            skip += 1
        elif r.get("ok"):
            ok += 1
            time.sleep(args.sleep)
        else:
            fail += 1
            print(f"  FAIL {r['slug']}: {r.get('err')}")
        if i % 25 == 0:
            print(f"  .. {i}/{len(urls)}  (ok {ok}, skip {skip}, fail {fail})")
    print(f"harvested {ok} new, skipped {skip}, failed {fail} of {len(urls)} -> {TDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
