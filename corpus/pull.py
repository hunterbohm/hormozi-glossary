#!/usr/bin/env python3
"""Pull YouTube auto-captions into corpus/transcripts/<id>.txt as clean, deduped text.

The local corpus is the EVIDENCE BASE only (gitignored); the public site keeps just
short quotes + source links. Idempotent: skips ids already pulled.

Usage:
  python3 corpus/pull.py <url_or_id> [more ...]
  python3 corpus/pull.py --file urls.txt        # one url/id per line (# comments ok)
"""
from __future__ import annotations
import argparse
import json
import os
import pathlib
import re
import subprocess
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
TDIR = HERE / "transcripts"
MANIFEST = HERE / "manifest.jsonl"

ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")


def vid_id(u: str) -> str | None:
    u = u.strip()
    m = ID_RE.search(u)
    if m:
        return m.group(1)
    return u if re.fullmatch(r"[A-Za-z0-9_-]{11}", u) else None


def clean_vtt(vtt: str) -> str:
    """VTT -> plain text: drop cues/tags/headers, dedupe YouTube's rolling repeats."""
    lines: list[str] = []
    for ln in vtt.splitlines():
        if "-->" in ln or not ln.strip():
            continue
        if ln.startswith(("WEBVTT", "Kind:", "Language:", "NOTE", "STYLE")):
            continue
        ln = re.sub(r"<[^>]+>", "", ln)          # inline <c>/karaoke timing tags
        ln = re.sub(r"^\s*\d+\s*$", "", ln)       # bare cue numbers
        ln = ln.strip()
        if ln:
            lines.append(ln)
    out: list[str] = []
    for ln in lines:
        if not out or out[-1] != ln:              # collapse consecutive duplicates
            out.append(ln)
    return re.sub(r"\s+", " ", " ".join(out)).strip()


def pull(u: str, timeout: int = 150) -> dict:
    vid = vid_id(u)
    if not vid:
        return {"url": u, "ok": False, "err": "no video id"}
    TDIR.mkdir(parents=True, exist_ok=True)
    dst = TDIR / f"{vid}.txt"
    if dst.exists():
        return {"id": vid, "ok": True, "skipped": True}
    with tempfile.TemporaryDirectory() as td:
        base = os.path.join(td, vid)
        try:
            subprocess.run(
                ["yt-dlp", "--write-auto-subs", "--write-subs", "--sub-langs", "en.*",
                 "--skip-download", "--sub-format", "vtt", "--write-info-json",
                 "-o", base + ".%(ext)s", f"https://www.youtube.com/watch?v={vid}"],
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            return {"id": vid, "ok": False, "err": "timeout"}
        vtts = [f for f in os.listdir(td) if f.endswith(".vtt")]
        if not vtts:
            return {"id": vid, "ok": False, "err": "no subtitles available"}
        # prefer manual en over auto if both present (shorter filename usually = manual)
        vtts.sort(key=len)
        text = clean_vtt(pathlib.Path(td, vtts[0]).read_text(encoding="utf-8", errors="ignore"))
        meta: dict = {}
        ij = [f for f in os.listdir(td) if f.endswith(".info.json")]
        if ij:
            j = json.loads(pathlib.Path(td, ij[0]).read_text(encoding="utf-8", errors="ignore"))
            meta = {"title": j.get("title"), "date": j.get("upload_date"),
                    "channel": j.get("channel"), "duration": j.get("duration")}
        header = (f"# {meta.get('title', '')}\n# url: https://www.youtube.com/watch?v={vid}\n"
                  f"# date: {meta.get('date', '')}\n# channel: {meta.get('channel', '')}\n\n")
        dst.write_text(header + text, encoding="utf-8")
        rec = {"id": vid, "ok": True, "chars": len(text), **meta}
        with open(MANIFEST, "a", encoding="utf-8") as m:
            m.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


def main() -> int:
    ap = argparse.ArgumentParser(description="Pull YouTube captions into the corpus")
    ap.add_argument("urls", nargs="*")
    ap.add_argument("--file", help="file with one url/id per line")
    args = ap.parse_args()
    items = list(args.urls)
    if args.file:
        for ln in pathlib.Path(args.file).read_text(encoding="utf-8").splitlines():
            ln = ln.split("#", 1)[0].strip()
            if ln:
                items.append(ln)
    ok = skip = fail = 0
    for u in items:
        r = pull(u)
        if r.get("skipped"):
            skip += 1
        elif r.get("ok"):
            ok += 1
            print(f"  ok    {r['id']}  {r.get('chars', 0):>6}c  {str(r.get('title', ''))[:60]}")
        else:
            fail += 1
            print(f"  FAIL  {r.get('id', r.get('url'))}: {r.get('err')}")
    print(f"pulled {ok} new, skipped {skip}, failed {fail} -> {TDIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
