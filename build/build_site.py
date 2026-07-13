#!/usr/bin/env python3
"""Render glossary.yml -> a self-contained static site in dist/ (Cloudflare Pages).

Reads the single source of truth through build/lib.py, then writes:
  dist/index.html      full glossary: hero, sticky search, category chips, 139 term cards
  dist/changelog.html  CHANGELOG.md rendered to HTML
  dist/style.css       editorial styling, light/dark, no network requests
  dist/app.js          vanilla-JS client search + category filter + deep links
  dist/glossary.json   the complete dataset, for anyone who wants the raw data

Run:  python3 build/build_site.py
"""
from __future__ import annotations

import datetime as _dt
import html as _html
import json
import pathlib
import re
import shutil
import sys

# --- robust lib import (build/ is where lib.py lives) ---------------------------
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "build"))
import lib  # noqa: E402

from jinja2 import Environment, FileSystemLoader, select_autoescape  # noqa: E402

# ==============================================================================
# CONFIG — edit these
# ==============================================================================
CONFIG = {
    "title": "The Hormozi Glossary",
    "tagline": "A living, sourced glossary of the words Alex Hormozi defines and redefines — "
               "a lens for understanding business and life.",
    "repo_url": "https://github.com/hunterbohm/hormozi-glossary",
    "canonical_url": "",  # e.g. "https://hormozi-glossary.pages.dev" — leave blank until deploy
}

ROOT = lib.ROOT
TEMPLATES = ROOT / "templates"
ASSETS = TEMPLATES / "assets"           # static passthrough (style.css, app.js)
DIST = ROOT / "dist"
CHANGELOG = ROOT / "CHANGELOG.md"
STATIC_ASSETS = ("style.css", "app.js")


# ==============================================================================
# Markdown -> HTML (uses the `markdown` package if present, else a minimal converter)
# ==============================================================================
def render_markdown(md_text: str) -> str:
    try:
        import markdown as _md  # optional; not a pinned dependency
        return _md.markdown(md_text, extensions=["extra", "sane_lists"])
    except Exception:
        return _minimal_markdown(md_text)


def _inline_md(s: str) -> str:
    """Inline markdown: escape HTML, then apply code / links / bold / italic."""
    s = _html.escape(s, quote=True)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
        s,
    )
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", s)
    return s


def _minimal_markdown(md_text: str) -> str:
    """Small block converter: headings, paragraphs, blockquotes, nested unordered lists."""
    out: list[str] = []
    para: list[str] = []
    li_text: str | None = None   # text of the currently-open <li>, or None
    depth = 0                    # number of open <ul>

    def flush_para() -> None:
        if para:
            out.append("<p>" + _inline_md(" ".join(para).strip()) + "</p>")
            para.clear()

    def flush_li() -> None:
        nonlocal li_text
        if li_text is not None:
            out.append("<li>" + _inline_md(li_text.strip()) + "</li>")
            li_text = None

    def close_lists() -> None:
        nonlocal depth
        flush_li()
        while depth > 0:
            out.append("</ul>")
            depth -= 1

    for raw in md_text.splitlines():
        line = raw.rstrip()

        if not line.strip():
            flush_para()
            close_lists()
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush_para()
            close_lists()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline_md(m.group(2).strip())}</h{lvl}>")
            continue

        m = re.match(r"^>\s?(.*)$", line)
        if m:
            flush_para()
            close_lists()
            out.append(f"<blockquote><p>{_inline_md(m.group(1).strip())}</p></blockquote>")
            continue

        m = re.match(r"^(\s*)(?:[-*+]|\d+\.)\s+(.*)$", line)
        if m:
            flush_para()
            level = len(m.group(1).replace("\t", "  ")) // 2 + 1  # 2 spaces per nesting level
            flush_li()                       # close the previous item
            while depth < level:
                out.append("<ul>")
                depth += 1
            while depth > level:
                out.append("</ul>")
                depth -= 1
            li_text = m.group(2).strip()
            continue

        # Non-marker line: a soft-wrapped continuation of the open list item, else a paragraph.
        if li_text is not None:
            li_text += " " + line.strip()
        else:
            para.append(line.strip())

    flush_para()
    close_lists()
    return "\n".join(out)


# ==============================================================================
# Build
# ==============================================================================
def main() -> None:
    entries = lib.load_valid()
    grouped = lib.by_category(entries)
    groups = [
        {"id": cat, "label": lib.CATEGORIES[cat], "entries": grouped[cat]}
        for cat in grouped
    ]

    today = _dt.date.today().isoformat()
    updates = [e["last_updated"] for e in entries if e.get("last_updated")]
    last_updated = max(updates) if updates else today

    # Lean, searchable term data embedded inline (also written full to glossary.json).
    search_records = [
        {
            "id": e["id"],
            "category": e["category"],
            "term": e["term"],
            "aliases": e.get("aliases") or [],
            "short_def": e["short_def"],
            "full_def": e["full_def"],
        }
        for e in entries
    ]
    search_json = json.dumps(
        search_records, ensure_ascii=False, separators=(",", ":")
    ).replace("</", "<\\/")  # keep it from closing the <script> early

    changelog_md = CHANGELOG.read_text(encoding="utf-8") if CHANGELOG.exists() else "# Changelog\n"
    changelog_html = render_markdown(changelog_md)

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    og_url = CONFIG["canonical_url"].rstrip("/")
    index_desc = CONFIG["tagline"]
    changelog_desc = f"Change history for {CONFIG['title']} — every added or revised definition, newest first."

    index_html = env.get_template("index.html").render(
        cfg=CONFIG,
        page_title=CONFIG["title"],
        page_desc=index_desc,
        og_url=og_url or None,
        groups=groups,
        total=len(entries),
        last_updated=last_updated,
        search_json=search_json,
    )
    changelog_html_page = env.get_template("changelog.html").render(
        cfg=CONFIG,
        page_title=f"Changelog — {CONFIG['title']}",
        page_desc=changelog_desc,
        og_url=(og_url + "/changelog.html") if og_url else None,
        changelog_html=changelog_html,
    )

    # Clean rebuild of dist/.
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)

    (DIST / "index.html").write_text(index_html, encoding="utf-8")
    (DIST / "changelog.html").write_text(changelog_html_page, encoding="utf-8")
    (DIST / "glossary.json").write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    for name in STATIC_ASSETS:
        shutil.copyfile(ASSETS / name, DIST / name)

    # Report.
    print(f"Built {len(entries)} terms across {len(groups)} categories -> {DIST}")
    for p in sorted(DIST.iterdir()):
        print(f"  {p.stat().st_size:>8,} B  {p.name}")


if __name__ == "__main__":
    main()
