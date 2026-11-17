# Divan attribution audit — venue-level precision

**Verdict: the 225-event claim is not reproducible, and the source is not publishable raw.**

The extraction works. The **attribution** does not: only 79.2% of the audited records can be
placed at the building the Atlas marker actually represents.

Observation window 2026-11-16. Read-only. No publication, no deployment, no scraper change.

---

## 1. What was claimed

Phase 2 registered `p2-006` (Interkulturelles Stadtteilzentrum Divan) as **qualified** with
**225** `schema.org/Event` items. `PHASE2_NEXT_STEPS.md` flagged the open question honestly:

> 225 items confirmed, but **how many are at Divan vs sibling venues?** Not yet measured.

This audit measures it.

## 2. The claim does not reproduce

The live page yields **221** event instances, not 225. The original 225-record extraction
artefact was never committed, so it cannot be inspected — only re-derived. The population was
reconstructed from the live page and frozen as a fixture, so this audit is reproducible without
re-fetching a third-party site.

Fixture integrity is machine-checked, not asserted. `python -m kiez_atlas.divan_fixture --repo .`
produces every row below and exits non-zero if any of them fail:

| | |
|---|---|
| decompressed SHA-256 | `d8806e7749ef439624ff1d69092f0f1cfb5814daa4fc2bc86b7376d151eda23e` |
| raw / gzipped bytes | 676682 / 85701 |
| independent recount from fixture | **221** `li.simcal-event` (220 recurring + 1 not) |
| fixture vs results JSON, record-for-record | identical on (title, start, end, location) |
| distinct (title, start, end, location) tuples | 220 on both sides — one source duplicate, carried symmetrically |

Until this branch, only the SHA-256 row was machine-checked. The recount and the
record-for-record comparison were assertions in this table with nothing computing them: a digest
proves the archive decompresses to the bytes it recorded, not that anyone counted the events
inside those bytes. The two rows are now output of a command rather than prose.

## 3. Attribution is the real finding

Divan runs **two buildings** at the same street, and the calendar serves both.

| measure | count | share of 221 |
|---|---|---|
| at the mapped venue (Nehringstr. 8) | **175** | **79.2%** |
| at the second building (Nehringstr. 26) | 36 | 16.3% |
| location names **both** buildings | 9 | 4.1% |
| location unusable (`SAAL - Konzertbühne`) | 1 | 0.5% |
| Divan-organised anywhere | 211 | 95.5% |

Two different questions, and they must never share a field:

- **map precision 79.2%** — attributable to the building the marker represents.
  This is the only figure that may decide what appears at that marker.
- **organisation precision 95.5%** — associated with any Divan building.

The first summary carried a single `venue_precision` field. Both numbers were "correct"
depending on the question being asked, which is how a 225-event yield survived review.

## 4. Instance count is not programme count

221 records are **58 distinct titles**. 220 of 221 records are recurring instances.

| | |
|---|---|
| distinct titles, all records | 58 |
| distinct titles, mapped venue | 46 |
| current mapped occurrences / titles | 90 / **40** |
| expired mapped occurrences | 85 |
| individual event permalinks | **0** |

Publishing 221 markers would render one monthly calendar as 221 programmes, of which 85 have
already finished. There is no per-event URL, so no stable event identity is available from
this source.

## 5. Four defects the audit exposed

1. **Multi-venue promotion (a real bug).** 9 records naming both buildings were classified
   `divan_hosted` because the target address appeared in the string. Membership among several
   named locations is not evidence of where an event happens.
2. **A publish gate that could not express the distinction.** `PUBLISHABLE_AT_VENUE` tested
   `classification` alone. A sibling-building event is genuinely *hosted* — just not here — so
   the gate would have published all **36** at the wrong marker. Fixed by
   `Attribution.is_publishable_at_venue()`, which requires `site == "mapped_venue"` as well.
   Gating on classification alone is now a test failure, not a latent bug.
3. **Summary drift.** Two fields described one quantity and disagreed:
   `distinct_titles_current_mapped` said 41, `distinct_titles_current_mapped_venue` said 40;
   the data support **40**. The summary is now generated from the results file
   (`python -m kiez_atlas.divan_audit --repo .`), so counts are computed rather than recalled.
4. **A reproducibility claim nothing executed.** §2 asserted an independent recount and a
   record-for-record match, but the only automated check was a gzip digest. Re-deriving the
   extraction from scratch to write `kiez_atlas.divan_fixture` found the rules were not
   recoverable from the repo: reading `data-event-start` instead of `content` shifts all 442
   timestamps by an hour (UTC epoch vs the source's `+01:00`), 31 fields need HTML-entity
   decoding, and one record carries its location only in a `<meta>` element with an empty span.
   None of that was written down, so the audit was reproducible in principle and not in
   practice. The rules are now documented in `kiez_atlas.divan_fixture` and pinned by tests.

## 6. Reproducibility

Setup — every command below needs the pipeline's dependencies, which are not
part of a bare Python install:

```
python -m venv .venv
source .venv/bin/activate                # Windows: .venv\Scripts\activate
python -m pip install -r requirements-dev.txt
```

Then, from the repository root:

```
PYTHONPATH=./pipelines/src python -m pytest pipelines/tests -v
PYTHONPATH=./pipelines/src python -m kiez_atlas.divan_audit --repo .
PYTHONPATH=./pipelines/src python -m kiez_atlas.divan_fixture --repo .
PYTHONPATH=./pipelines/src python -m kiez_atlas.cli validate --repo .
```

All four exit 0 on a clean checkout. Expected: 137 tests passed, and 46/46
validation checks.

`.github/workflows/validate.yml` runs these four commands on every pull request
and on every push to `main`, then asserts `git status --porcelain` is empty. That
last step is the one worth understanding: `divan_audit` **writes** the summary,
and it exits 0 whether or not the bytes it writes match what was committed. So
without the check, a summary that had drifted from its generator would pass CI
silently — the badge stays green while the committed artefact is wrong. The
workflow therefore regenerates and then certifies that regeneration reproduced
the committed bytes, which is the same separation the two commands make
explicitly.

The workflow is a per-change gate, not a crawler: no schedule trigger, no
network fetch of the source site. The frozen fixture exists so that nothing
needs to touch a third-party page on a timer.

The suite used to be unrunnable from a fresh clone: `pytest`, `jsonschema` and
`shapely` were all imported but none were declared anywhere, so `requirements-dev.txt`
is what makes the commands above work on someone else's machine. `jsonschema` and
`shapely` are imported from `pipelines/src`, not from tests, so they are needed by
`cli validate` itself — a pytest-only install still cannot run the 46-check
validation command.

`divan_audit` regenerates the summary **from** the results file and verifies the fixture digest.
`divan_fixture` does the different, harder job: it re-extracts all 221 records from the frozen
HTML and compares them with the results file, failing non-zero on any missing, additional,
duplicate or mismatched record. They are separate commands on purpose — a step that regenerates
an artefact must not also be the check that certifies it. `divan_fixture` has no write path at
all, so it cannot silently repair the file it audits.

`TestDivanAuditRegression` replays the module over all 221 records and asserts
175 / 36 / 10 and exactly 175 publishable. It **fails** rather than skips when the results file
is absent from the checkout.

## 7. Verdict and conditions

**`qualified` → `qualified_with_filter`.** Technically sound extraction, real per-event
locations, reproducible fixture. Not eligible for raw publication.

Publication requires: exact physical-venue attribution; the second building excluded or
represented as its own venue; human review of the 46 flagged records; recurrence normalised to
series; expired occurrences filtered; a stable event identity strategy, which this source
cannot supply.

The registry entry (`p2-006`) **is** updated to `qualified_with_filter` in both
`PHASE2_SOURCE_REGISTRY.json` and `.csv`, with its `evidence` rewritten to the audited 221 and
`last_checked` moved to 2026-11-16.

That correction was previously deferred on the grounds that `qualified_with_filter` was a new
value and nothing enforced the registry's vocabulary — adding an unenforced label would have
been a second unvalidated claim next to the first. The right fix was the enforcement, not the
deferral: `vocab.EVENT_SOURCE_STATUS` now defines the value, and `kiez_atlas.cli validate`
rejects any `source_status` outside that vocabulary, any duplicate `source_id`, and any
disagreement between the JSON and CSV copies. A status no code can interpret now fails the run
instead of sitting quietly among valid ones.

`p2-006`'s `evidence` still names 225 — deliberately, in the clause explaining that the figure
**did not reproduce**. Deleting the superseded number would remove the audit trail that shows
the claim was checked rather than merely replaced, so the validation check targets the claim
phrasing (`"225 schema.org/Event items"`) instead of banning the digits.

## 8. Open items

- ~~Registry status and the 225 figure still carry the pre-audit claim.~~ **Resolved:**
  `p2-006` is `qualified_with_filter` in both registry files, and the 225 in
  `PHASE2_TECHNICAL_FINDINGS.md`, `PHASE2_NEXT_STEPS.md` and `PHASE2_SOURCE_DISCOVERY.md` is
  annotated as a superseded probe observation rather than left standing as a live claim. The
  status-distribution table in `PHASE2_SOURCE_DISCOVERY.md` now splits `qualified` (1) from
  `qualified_with_filter` (1) so it no longer contradicts the registry.
- Second building needs its own venue record before its 36 events can be shown at all.
- Recurrence/series model is not yet implemented — see `EVENT_ATTRIBUTION_DESIGN.md`.
- **This audit does not make the Atlas production-ready.** It corrects one source's yield.

---

*Supersedes the 225-event claim for `p2-006`. Design rules: `EVENT_ATTRIBUTION_DESIGN.md`.
Machine output: `DIVAN_ATTRIBUTION_RESULTS.json`, `DIVAN_ATTRIBUTION_SUMMARY.json`.*
