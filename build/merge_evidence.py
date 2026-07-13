#!/usr/bin/env python3
"""Merge evidence YAML (from the verification pass) into glossary.yml.

Each evidence file is a YAML list of {id, evidence:[{quote,source,url,kind}], evidence_status, note?}.
Adds `evidence`, `evidence_status`, `note` to the matching glossary entries, preserving the
canonical key order, then re-validates.

Usage:  python3 build/merge_evidence.py <evidence_dir_or_files...>
"""
from __future__ import annotations
import pathlib
import sys

import yaml

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lib  # noqa: E402

KEY_ORDER = ["id", "term", "aliases", "category", "short_def", "full_def", "formula",
             "components", "why_it_matters", "sources", "evidence", "evidence_status",
             "note", "confidence", "first_seen", "last_updated", "status"]


def _ordered(e: dict) -> dict:
    return {k: e[k] for k in KEY_ORDER if e.get(k) not in (None, "", [])}


def collect(paths: list[str]) -> list[pathlib.Path]:
    out = []
    for p in paths:
        pp = pathlib.Path(p)
        if pp.is_dir():
            out += sorted(pp.glob("evidence-*.yml"))
        elif pp.exists():
            out.append(pp)
    return out


def main() -> int:
    files = collect(sys.argv[1:] or ["."])
    if not files:
        raise SystemExit("no evidence files found")
    ev: dict[str, dict] = {}
    for f in files:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or []
        for r in data:
            if r.get("id"):
                ev[r["id"]] = r
        print(f"  loaded {len(data):>3} from {f.name}")

    entries = lib.load(lib.GLOSSARY)
    hit = miss = 0
    for e in entries:
        r = ev.get(e["id"])
        if not r:
            miss += 1
            continue
        hit += 1
        if r.get("evidence"):
            e["evidence"] = r["evidence"]
        if r.get("evidence_status"):
            e["evidence_status"] = r["evidence_status"]
        if r.get("note"):
            e["note"] = r["note"]

    header = "".join(l for l in lib.GLOSSARY.read_text(encoding="utf-8").splitlines(keepends=True)
                     if l.startswith("#"))
    body = yaml.dump([_ordered(e) for e in entries], sort_keys=False, allow_unicode=True,
                     width=1000, default_flow_style=False)
    lib.GLOSSARY.write_text(header + body, encoding="utf-8")

    errs = lib.validate(entries)
    from collections import Counter
    st = Counter(e.get("evidence_status", "none") for e in entries)
    print(f"merged evidence into {hit} entries ({miss} without evidence record)")
    print(f"evidence_status: {dict(st)}")
    print("VALID" if not errs else f"INVALID: {errs[:3]}")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
