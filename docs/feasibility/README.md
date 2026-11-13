# Kiez Events Atlas — Feasibility Study

**Status: PRELIMINARY / DISCOVERY PHASE.** Documentation only. No application code, no
deployment change, no workflow, no data publication.

- Fork: `JsonLord/berlin-cci-atlas`
- Upstream: `kaitiwu/berlin-cci-atlas`
- Branch: `docs/kiez-events-feasibility`
- Observation window: 2026-11-13 (single day, CET)
- Read the full report: [`REPORT.md`](REPORT.md)

## Artifacts

| File | What it is | Status |
|---|---|---|
| `REPORT.md` | Full feasibility report, sections A–F | preliminary |
| `artifacts/venue_inventory.json` / `.csv` | All 303 atlas venues, coordinates, point-in-polygon LOR assignment, provenance | derived, validated |
| `artifacts/sources.json` | Source registry for 12 tested hubs (internal shape) | tested 2026-11-13 |
| `artifacts/sample_events.json` | 7 real extracted sample events with evidence + missing fields | tested 2026-11-13 |
| `artifacts/event.schema.json` | Proposed public event schema | draft, validates |
| `artifacts/venue.schema.json` | Proposed public venue schema | draft, validates all 303 |

## Evidence discipline

Every claim in the report is tagged:

- **[V] Verified** — I fetched it and can point to the response or file.
- **[O] Observation** — read from the code/data, not externally tested.
- **[R] Recommendation** — my proposal, not yet built.
- **[A] Assumption** — believed, not verified.
- **[Q] Open question** — needs a human decision.

Nothing in this branch is deployed. Nothing here should be read as a claim that a site
"has been scraped" beyond the single fetch recorded in `sample_events.json`.
