# Glossary Entry Schema

`glossary.yml` is the single source of truth. It is a YAML list; each item is one term.
Every generator (`build/*.py`) and the sweep (`sweep/sweep.py`) read it through `build/lib.py`,
so this schema is the contract.

## Fields

| field | type | required | notes |
|---|---|---|---|
| `id` | string | yes | kebab-case, **unique, stable** — URL anchor + the diff key the sweep matches on. Never reuse an id for a different concept. |
| `term` | string | yes | canonical display name |
| `aliases` | list[string] | no | other names/spellings; `[]` or omitted if none |
| `category` | enum | yes | one of: `mindset`, `offers`, `leads`, `money-models`, `sales`, `scaling`, `wealth`, `meta` |
| `short_def` | string | yes | one plain-English sentence |
| `full_def` | string | yes | 2–4 sentence paraphrase — **never a fabricated verbatim quote** |
| `why_it_matters` | string | yes | the frame / lens: why adopting the definition changes how you see or decide |
| `formula` | string | no | e.g. `Value = (Dream Outcome × Perceived Likelihood) ÷ (Time Delay × Effort & Sacrifice)` |
| `components` | list[string] | no | the parts of a multi-part term |
| `sources` | list[{label,url}] | yes | ≥1 source; `url` may be `""`. Book title or a link (Rosetta.to pages are ideal). |
| `confidence` | enum | yes | `high` (book / repeatedly-verbatim framework), `medium` (well-attested video/podcast), `low` (single loose source) |
| `first_seen` | string | yes | `YYYY` or `YYYY-MM` — approx first public use |
| `last_updated` | string | no | `YYYY-MM-DD` — set by the sweep when it changes an entry |
| `status` | enum | no | `active` (default), `revised`, `deprecated` — maintained by the sweep |
| `evidence` | list[{quote,source,url,kind}] | no | short verbatim spoken quote(s) (≤300 chars) backing the definition. `kind` = `verbatim` (his own spoken words) or `book` (chapter cite, no quote text). |
| `evidence_status` | enum | no | `verified` (spoken quote), `book` (book citation), or `unverified`. |

## Rules

- **Definitions are paraphrased and attributed.** No invented quotes; a direct quote must be exact and sourced.
- `category` is exactly one enum value.
- The sweep computes a content hash over `term`, `short_def`, `full_def`, `formula`, `components`, `aliases`
  (see `lib.content_hash`). A hash change → bump `last_updated`, set `status: revised`, and write a `CHANGELOG.md` entry.
- Adding a term is additive and low-risk; **changing** an existing definition is reviewed before it reaches the public site.
