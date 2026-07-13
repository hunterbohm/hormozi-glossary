# Hormozi Glossary

A living, sourced glossary of the terms **Alex Hormozi has defined or redefined** — his personal
vocabulary, frameworks, and mental models — collected in one place as a frame for understanding
business and life.

> **Unofficial / educational.** Definitions are paraphrased and attributed, with links to the
> original source (his books, *The Game* podcast, public talks). Not affiliated with Alex Hormozi.

## How it works

`glossary.yml` is the **single source of truth**. Everything else is generated from it:

- **Website** — `build/build_site.py` → `dist/` (ready for any static host).
- **Vault copy** — `build/export_vault.py` → a caller-supplied Obsidian folder.
- **Changelog** — `CHANGELOG.md`, appended whenever a definition is added or changed.
- **Sweep** — `sweep/sweep.py` crawls Alex's latest content, diffs against
  `glossary.yml`, and proposes new or changed definitions. Scheduling and deployment
  belong to the operator, not this repository.

## Layout

| path | role |
|---|---|
| `glossary.yml` | source of truth — edit here |
| `SCHEMA.md` | entry schema / contract |
| `build/lib.py` | canonical loader + validator (import this everywhere) |
| `build/build_site.py` | glossary → static site (`dist/`) |
| `build/export_vault.py` | glossary → Obsidian vault notes |
| `sweep/` | portable content sweep + change detection |
| `CHANGELOG.md` | public change history |
| `data/rosetta-index.md` | cached Rosetta.to catalog (sweep source list) |

## Commands

```bash
python build/lib.py                # validate glossary.yml
python build/build_site.py         # regenerate dist/
VAULT_DIR=~/path/to/vault/Hormozi-Glossary python build/export_vault.py
python sweep/sweep.py --dry-run    # preview proposed changes (no writes)
```

## Contributing / editing

Edit `glossary.yml`, run `python build/lib.py` to validate, then `python build/build_site.py`.
Keep definitions paraphrased and sourced (see `SCHEMA.md`).
