# Changelog

All notable changes to the glossary — newest first. Each change links its source.
Maintained by the content sweep (`sweep/sweep.py`), which crawls Alex Hormozi's latest
content every ~2 days and proposes new or revised definitions.

## 2026-07-10 — Money-model accounting correction

- Corrected Client-Financed Acquisition and the 30-day 2x standard to use the
  current Acquisition.com Money Models definitions: gross profit already subtracts
  direct fulfillment/COGS, so the current rule is first-30-day gross profit > 2x
  fully loaded CAC. Preserved the older cash-collected formulation separately
  instead of mixing its COGS term into a gross-profit equation.
- Rewrote payback period as the first point where cumulative gross profit repays
  CAC; the simple CAC/monthly-GP division is only an even-cash-flow approximation.

## 2026-07-09 — Shorts title-triage coverage pass

- **+23 terms (243 total)** surfaced by triaging **all 4,765 titles** of his YouTube Shorts
  (`@AlexHormozi/shorts`) against the glossary with a 4-model agent sweep, then verifying each
  candidate against his own spoken words in the corpus. New: the swamp ($1M–$3M), the 3 laws of
  advertising, the 3 buckets of content, the 4 shapes of business, information arbitrage, the
  1–10 close, two funnels, the failure resume, the menu upsell, the lonely chapter, the three
  lines of business, ghost products, values-are-skills, niche slap, deals die in the details,
  the magnetic middle, the secretary close, let the fires burn, the selfie strategy, silence
  sells, the damaging admission, exposure therapy for sales, and the marriage-proposal close.
  Each carries a short verbatim spoken quote.
- **Honest scope:** Shorts are re-cut clips of already-covered long-form, so evidence came from
  the long-form/podcast source or the short's own captions. YouTube rate-limited the shared IP
  (HTTP 429) during the bulk pull, so ~350 Shorts captions were pulled (plus a gentle,
  single-stream re-pull to recover the flagged candidate clips once the block cooled). Title-level
  Shorts coverage is complete; full Shorts-transcript coverage is partial and left to the
  incremental sweep. See `COVERAGE.md`.

## 2026-07-06 — Guest-appearance pull + saturation check

- Pulled 8 more long-form guest appearances (28 total) plus 16 new long-form videos; **audited all 24 → 0 new terms.**
  His long-form YouTube + guest spots re-explain frameworks already captured — long-form marginal yield appears tapped out at 220 (Shorts + obscure spots still unprocessed).
- Only untapped source left is Shorts (re-cut clips); deferred as low-yield.

## 2026-07-06 — Copyright cleanup + coverage correction

- Re-audited for book-text: deleted the last book-reading transcript (Money Models "Part 1"), replaced
  audiobook/transcript-site source links on 8 terms with plain book chapter citations, and neutralized one
  definition's "book/audiobook" wording. Verified **0 book-text references** across glossary + corpus.
- Corrected the YouTube scale: his channel is ~507 long-form (already ~covered via Rosetta), not ~5,280 —
  that figure is mostly Shorts (re-cuts, deferred). Pulled 16 genuinely-new long-form (audit pending).

## 2026-07-06 — Completeness audit wave

- **+45 terms** from a 4-agent sweep of the whole corpus for words he DEFINES or REFRAMES that the
  first pass missed — e.g. guilt, shame, standards, courage, cash-flow-is-oxygen, document-don't-create,
  choose-your-regrets, the assumed close. Each carries a short verbatim spoken quote.
- **Total: 220 terms**, every one still evidenced (200 verbatim spoken quotes + 20 book citations).
- Honesty: "resistance" was force-checked and is **not** defined by him in the current corpus (it
  appears only in a video title) — likely lives in content not yet collected. See `COVERAGE.md`'s two-gap split.

## 2026-07-06 — Evidence pass + corpus expansion

- **Every term now carries evidence** — 155 with a short verbatim quote from his own public spoken
  words (source + link), 20 with a book chapter citation. See `COVERAGE.md`.
- **+36 new terms** mined from the full *The Game* podcast (1,067 episodes) + guest appearances —
  coinages like "offer hoppers", "the fallacy of the perfect pick", "the management diamond".
- Built a **1,604-transcript** evidence base (his YouTube + The Game + 20 guest appearances).
  Audiobook chapters (books read aloud) were excluded; book concepts are cited, never excerpted.
- Total: **175 terms**.

## 2026-07-06 — Initial release

- **139 terms** compiled from Alex Hormozi's books (*$100M Offers*, *$100M Leads*,
  *$100M Money Models*), *The Game* podcast, and public talks — sourced via the Rosetta.to catalog.
  - mindset 36 · offers 20 · leads 23 · money-models 12 · sales 17 · scaling 15 · wealth 12 · meta 4
