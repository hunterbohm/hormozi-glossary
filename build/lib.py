"""Canonical loader + validator for glossary.yml — the single source of truth.

Every generator (build_site, export_vault) and the sweep import from here so they
all share one contract. Run directly to validate:  python build/lib.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
GLOSSARY = ROOT / "glossary.yml"

# category id -> human label (also defines the canonical display order)
CATEGORIES = {
    "mindset": "Mindset & Redefined Words",
    "offers": "Offers & Value",
    "leads": "Leads & Advertising",
    "money-models": "Money Models",
    "sales": "Sales",
    "scaling": "Scaling & Constraints",
    "wealth": "Wealth & Money",
    "meta": "Meta & Method",
}
CATEGORY_ORDER = list(CATEGORIES.keys())
CONFIDENCE = {"high", "medium", "low"}
REQUIRED = ("id", "term", "category", "short_def", "full_def",
            "why_it_matters", "sources", "confidence", "first_seen")


def load(path: pathlib.Path | str = GLOSSARY) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    if not isinstance(data, list):
        raise ValueError("glossary.yml must be a YAML list of entries")
    return data


def validate(entries: list[dict]) -> list[str]:
    errors: list[str] = []
    seen: dict[str, int] = {}
    for i, e in enumerate(entries):
        where = f"entry[{i}] id={e.get('id', '?')!r}"
        for k in REQUIRED:
            if not e.get(k):
                errors.append(f"{where}: missing required field '{k}'")
        if e.get("category") and e["category"] not in CATEGORIES:
            errors.append(f"{where}: invalid category {e['category']!r}")
        if e.get("confidence") and e["confidence"] not in CONFIDENCE:
            errors.append(f"{where}: invalid confidence {e['confidence']!r}")
        _id = e.get("id")
        if _id:
            if _id in seen:
                errors.append(f"{where}: duplicate id (also entry[{seen[_id]}])")
            seen[_id] = i
        for s in (e.get("sources") or []):
            if not (isinstance(s, dict) and s.get("label")):
                errors.append(f"{where}: every source needs a 'label'")
                break
    return errors


def load_valid(path: pathlib.Path | str = GLOSSARY) -> list[dict]:
    entries = load(path)
    errs = validate(entries)
    if errs:
        raise SystemExit("glossary.yml INVALID:\n  " + "\n  ".join(errs))
    return entries


def content_hash(e: dict) -> str:
    """Stable hash of the meaning-bearing fields — the sweep uses this to detect changes."""
    payload = json.dumps(
        {k: e.get(k) for k in ("term", "short_def", "full_def", "formula", "components", "aliases")},
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12]


def by_category(entries: list[dict]) -> dict[str, list[dict]]:
    """Group entries by category in canonical order, terms sorted A→Z within each."""
    out: dict[str, list[dict]] = {c: [] for c in CATEGORY_ORDER}
    for e in entries:
        out.setdefault(e["category"], []).append(e)
    for c in out:
        out[c].sort(key=lambda e: e["term"].lower())
    return {c: v for c, v in out.items() if v}


if __name__ == "__main__":
    entries = load()
    errs = validate(entries)
    if errs:
        print(f"INVALID ({len(errs)} errors):")
        for e in errs:
            print("  -", e)
        sys.exit(1)
    from collections import Counter
    print(f"OK: {len(entries)} terms")
    counts = Counter(e["category"] for e in entries)
    for c in CATEGORY_ORDER:
        if counts.get(c):
            print(f"  {counts[c]:3} {c}")
