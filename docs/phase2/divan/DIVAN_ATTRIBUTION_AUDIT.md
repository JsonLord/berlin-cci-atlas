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

Fixture integrity is machine-checked, not asserted:

| | |
|---|---|
| decompressed SHA-256 | `d8806e7749ef439624ff1d69092f0f1cfb5814daa4fc2bc86b7376d151eda23e` |
| raw / gzipped bytes | 676682 / 85701 |
| independent recount from fixture | **221** `li.simcal-event` (220 recurring + 1 not) |
| fixture vs results JSON, record-for-record | identical on (title, start, end, location) |

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

## 5. Three defects the audit exposed

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

## 6. Reproducibility

```
PYTHONPATH=./pipelines/src python -m pytest pipelines/tests -v
PYTHONPATH=./pipelines/src python -m kiez_atlas.divan_audit --repo .
PYTHONPATH=./pipelines/src python -m kiez_atlas.cli validate --repo .
```

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

The registry entry (`p2-006`, still `source_status: qualified`, still citing 225) has **not**
been updated in this branch: `qualified_with_filter` is a new status value and the registry has
no schema enforcing its vocabulary. Adopting it is an owner decision, recorded as open below.

## 8. Open items

- Registry status and the 225 figure in `PHASE2_TECHNICAL_FINDINGS.md` / `PHASE2_NEXT_STEPS.md`
  still carry the pre-audit claim.
- Second building needs its own venue record before its 36 events can be shown at all.
- Recurrence/series model is not yet implemented — see `EVENT_ATTRIBUTION_DESIGN.md`.
- **This audit does not make the Atlas production-ready.** It corrects one source's yield.

---

*Supersedes the 225-event claim for `p2-006`. Design rules: `EVENT_ATTRIBUTION_DESIGN.md`.
Machine output: `DIVAN_ATTRIBUTION_RESULTS.json`, `DIVAN_ATTRIBUTION_SUMMARY.json`.*
