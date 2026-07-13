# Content Sweep

`sweep.py` keeps the glossary current: it crawls Alex Hormozi's latest content
(Rosetta.to), diffs it against `glossary.yml`, and proposes new or revised
definitions. It is infra-agnostic pure logic — cron/launchd, Discord, git, and
the real model are wired separately.

> Unofficial / educational. Definitions are paraphrased & attributed, not
> verbatim quotes. Not affiliated with Alex Hormozi.

## Sweep

### Flow

```
discover → fetch → extract → classify → propose   (then, on approval) → apply
```

1. **discover** — pull the Rosetta listing, diff URLs against the seen-state
   (`sweep/.cache/seen.json`) and the shipped catalog baseline
   (`data/rosetta-index.md`, treated as already-ingested). New URLs pass through.
2. **fetch** — pull each new page's summary, "Questions answered", and transcript.
3. **extract** — pull candidate definitions from the text (pluggable, see below).
4. **classify** — a candidate whose term is absent → **new** (proposed add); a
   candidate whose term exists but whose definition materially differs (difflib
   ratio below `SWEEP_SIMILARITY`, default `0.85`) → **revision** (old→new);
   otherwise skipped.
5. **propose** — write `sweep/proposals/<date>.yml` (machine) +
   `sweep/proposals/<date>.md` (human). This is the default; nothing else is touched.
6. **apply** — on approval, edit `glossary.yml` and `CHANGELOG.md` in place, then
   re-validate through `build/lib.py`.

Only successfully-processed items are marked seen; a failed fetch/extract is left
unmarked and retried next run. `--mock` never persists seen-state (keeps runs
reproducible).

### CLI

```bash
python3 sweep/sweep.py --dry-run              # discover→propose; NO glossary/changelog writes (default)
python3 sweep/sweep.py --dry-run --mock       # same, fully offline via the bundled fixture
python3 sweep/sweep.py --backfill 10          # consider the 10 most-recent items, ignoring seen-state
python3 sweep/sweep.py --apply sweep/proposals/2026-07-06.yml   # apply a reviewed proposals file
python3 sweep/sweep.py --auto-additive        # run, then auto-apply only NEW terms carrying a source url
```

### Environment knobs

| var | default | purpose |
|---|---|---|
| `SWEEP_LLM_CMD` | _(unset → offline stub)_ | command the extractor shells out to; the strict-JSON prompt is fed on **stdin** and JSON is read from stdout (e.g. `codex exec`). Unset (or `--mock`) uses a deterministic offline stub. |
| `SWEEP_SIMILARITY` | `0.85` | difflib ratio below which an existing term's definition counts as materially changed. |
| `SWEEP_SITE_URL` | `https://hormozi-glossary.pages.dev` | base for `CHANGELOG.md` links (`.../#<id>`). |
| `SWEEP_USER_AGENT` | `hormozi-glossary-sweep/1.0` | User-Agent for Rosetta requests. |
| `SWEEP_LLM_TIMEOUT` | `240` | seconds before the LLM command is abandoned. |

### Proposal → review → apply

The sweep never publishes on its own. It writes proposals; a human reviews the
`.md`, edits the `.yml` if needed, then runs `--apply <file>`.

**Safety model:** adding a term is additive and low-risk, so `--auto-additive`
may auto-apply **new** terms that carry a source URL. **Changing** an existing
definition is never auto-applied — revisions always land in the proposals file
and reach the public site only after a human approves them.

## Automation and deployment

This repository deliberately stops at the portable sweep engine. Operators may
schedule it with cron, launchd, a CI workflow, or another job runner, then connect
their own model, notification, storage, and deployment systems outside the public
repository.

A conservative unattended job should:

1. update the checkout;
2. verify the catalog baseline is present;
3. run `python3 sweep/sweep.py --auto-additive`;
4. validate with `python3 build/lib.py`;
5. rebuild with `python3 build/build_site.py`;
6. review any revision proposals before publishing them.

Keep credentials, personal notification handles, machine paths, secret-manager
commands, and host-specific scheduler files in private operator configuration.
