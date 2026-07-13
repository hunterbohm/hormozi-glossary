# Coverage & Evidence Report

_Last run: 2026-07-09 (Shorts title-triage pass); prior 2026-07-06. What public Hormozi material was reviewed, how much is transcript-backed,
the evidence behind every term — and, honestly, what is still **not** covered._

## Bottom line

- **243 terms**, and **every one carries evidence**: **223** with a short verbatim quote from his
  own public **spoken** words (source + link), **20** with a **book citation** (chapter cited, not excerpted).
- Built from a **~1,960-transcript** local evidence base of his public spoken content.
- **No book text is reproduced anywhere** — see the copyright section below (re-audited).
- Gaps are tracked openly below; "nothing more in the corpus" is **not** "we have every public definition."

## The evidence base (what was pulled + stored)

| Source | On record | Stored | Notes |
|---|---|---|---|
| **The Game** podcast (his own show) | 1,132 episodes | **~1,066** | ~66 audiobook-chapter episodes (his books read aloud) excluded/deleted as copyrighted. Effectively his whole show. |
| **YouTube long-form** (his channel) | **~507** videos | **~all + 16 new** | His long-form was already ~fully covered via Rosetta; a channel enumeration found only **24 genuinely-new** long-form (16 pulled). Those + 8 newly-pulled guest appearances were **audited → 0 new terms** — long-form marginal yield appears tapped out, though Shorts + a few obscure guest spots remain unprocessed. |
| **YouTube Shorts** | **4,765** | **~350 pulled · all titles triaged** | All 4,765 Shorts titles were triaged against the glossary (4-model agent sweep) → **+23 new terms**, each verified against his spoken corpus (long-form re-cut source or the short's own captions). YouTube rate-limited the IP (429) during the bulk pull; ~350 captions pulled (incl. a gentle re-pull of the flagged candidate clips); rest resumable (see gaps). |
| **Guest appearances** (other shows) | ~90+ | **84 (28 + 56 new)** | Prior 28 audited → 0 new terms; **+56 more pulled this pass** (gentle single-stream, all captioned); term-audit of the new 56 deferred to the sweep (expected low yield). |
| **Books** | 5 books, ~95 definitions | cited, not stored | Full text copyrighted → **cited by chapter, never excerpted**. |

## Copyright posture (re-audited across glossary + corpus)

- **0** book-cited terms contain any quote text (the 20 are plain chapter citations).
- **0** spoken quotes exceed 300 chars; all are short fair-use excerpts of his **public spoken** statements, linked to source.
- **0** evidence or source entries point at a book-reading / audiobook transcript (Deciphr / Lost-Chapters audiobook / Wave URLs were replaced with plain book citations).
- **0** book-reading transcripts remain in the local corpus (the Offers/Leads/Money-Models "Part N" audiobook chapters were detected and deleted).
- **0** transcripts are committed to the public repo (the full corpus is local-only); the site shows only short attributed quotes.
- A hard gate in the merge scripts aborts if any evidence quote traces to a book reading.

## The gaps — tracked honestly

**Gap 1 — definitions missed *inside* the corpus.** Largely closed by the audit waves (+45 earlier,
**+23** from Shorts titles this pass); the bi-daily sweep keeps catching new ones.

**Gap 2 — Shorts transcripts (partial — YouTube rate-limited).** All **4,765** Shorts *titles* were triaged, but
their *transcripts* are ~350 pulled: YouTube rate-limited the shared IP (HTTP 429) mid-pull, so
the bulk Shorts-transcript pull was **stopped** rather than deepen the block. Shorts are re-cut clips
of already-covered long-form, so marginal yield is low. The candidate clips the triage flagged were
recovered with a gentle single-stream re-pull (once the 429 cooled) and audited — a few, like the
"4 C's of leverage" (which he credits to Naval, so out of scope), were correctly dropped. The
remaining ~4,400 un-pulled Shorts are deferred to the incremental sweep. Whisper transcription of
genuinely caption-less Shorts was attempted; YouTube also throttles audio downloads from one IP (one
Short was spot-transcribed → re-cut, already-covered content).

**Gap 3 — guest-appearance term audit.** +56 more guest/interview appearances were **pulled** this pass
(84 total); their term-audit is deferred to the sweep — prior guest pulls added 0 new terms, so expected yield is low.

We do **not** claim "every public definition." Title-level Shorts coverage is complete; full
Shorts-transcript + guest coverage is explicitly partial and resumable.

### Worked example: "resistance"

Force-checked. In the corpus he uses it only in a **video title** ("The Assumed Close: How to Close Deals
Without Resistance"), never as a stated definition — so it was **excluded, not invented.** If he
defines/reframes it, it's in gap-2 material. This is why the two gaps are tracked apart.

## Keeping it current

The bi-daily sweep (`sweep/`) re-runs the pipeline on his newest content; the deferred Shorts + guest-spot
tranches can be pulled and re-audited to push toward full coverage.
