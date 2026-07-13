#!/usr/bin/env python3
"""Merge evidence + re-sourced overrides + expansion new terms into glossary.yml.

Order: base evidence (7 chunk files) -> re-sourced overrides (evidence-resourced.yml)
-> append expansion new terms. Hard gate: ABORT if any evidence source is a book-reading
(copyrighted book text). Then re-sort + validate.

Usage:  python3 build/merge_all.py <local_dir_with_evidence_yaml>
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
BASE = ["mindsetA", "mindsetB", "offers", "leads", "salesmeta", "moneywealth", "scaling"]
TODAY = "2026-07-06"


def ordered(e: dict) -> dict:
    return {k: e[k] for k in KEY_ORDER if e.get(k) not in (None, "", [])}


def load_yaml(p: pathlib.Path) -> list:
    return yaml.safe_load(p.read_text(encoding="utf-8")) or [] if p.exists() else []


def main() -> int:
    locald = pathlib.Path(sys.argv[1])
    ev: dict[str, dict] = {}
    for name in BASE:
        for r in load_yaml(locald / f"evidence-{name}.yml"):
            if r.get("id"):
                ev[r["id"]] = r
    # overrides applied last (win)
    resourced = {r["id"] for r in load_yaml(locald / "evidence-resourced.yml") if r.get("id")}
    for r in load_yaml(locald / "evidence-resourced.yml"):
        if r.get("id"):
            ev[r["id"]] = r
    print(f"evidence records: {len(ev)} (re-sourced overrides: {len(resourced)})")

    entries = lib.load(lib.GLOSSARY)
    for e in entries:
        r = ev.get(e["id"])
        if r:
            if r.get("evidence"):
                e["evidence"] = r["evidence"]
            if r.get("evidence_status"):
                e["evidence_status"] = r["evidence_status"]
            if r.get("note"):
                e["note"] = r["note"]

    existing = {e["id"] for e in entries}
    added = 0
    for n in load_yaml(locald / "expansion-new-terms.yml"):
        if n.get("id") in existing:
            continue
        r = ev.get(n["id"])  # apply re-sourced override to a new term if present
        if r and r.get("evidence"):
            n["evidence"] = r["evidence"]
            n["evidence_status"] = r.get("evidence_status", n.get("evidence_status", "verified"))
        n.setdefault("evidence_status", "verified")
        n.setdefault("last_updated", TODAY)
        n.setdefault("status", "active")
        entries.append(n)
        existing.add(n["id"])
        added += 1

    order = {c: i for i, c in enumerate(lib.CATEGORY_ORDER)}
    entries.sort(key=lambda e: (order.get(e["category"], 99), e["term"].lower()))

    # HARD GATE: no book-text sources
    bad = [(e["id"], evi.get("source")) for e in entries for evi in (e.get("evidence") or [])
           if BOOKREAD.search(evi.get("source", "") or "")]
    if bad:
        print(f"ABORT: {len(bad)} book-text evidence sources remain:")
        for i, s in bad[:15]:
            print("   ", i, "<-", s)
        return 1

    header = (f"# Alex Hormozi Glossary — source of truth (edit here; generators + sweep read this)\n"
              f"# {len(entries)} terms. Schema: SCHEMA.md. Definitions paraphrased & attributed; evidence\n"
              f"# quotes are short fair-use excerpts of his public SPOKEN statements (books cited, not quoted).\n"
              f"# Last full synthesis + evidence pass: {TODAY}\n")
    body = yaml.dump([ordered(e) for e in entries], sort_keys=False, allow_unicode=True,
                     width=1000, default_flow_style=False)
    lib.GLOSSARY.write_text(header + body, encoding="utf-8")

    errs = lib.validate(entries)
    st = collections.Counter(e.get("evidence_status", "none") for e in entries)
    withev = sum(1 for e in entries if e.get("evidence"))
    print(f"total terms: {len(entries)} (+{added} new) | with evidence: {withev}")
    print("evidence_status:", dict(st))
    print("VALID ✓" if not errs else f"INVALID: {errs[:3]}")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
