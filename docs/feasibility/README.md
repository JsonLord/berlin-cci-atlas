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
| `artifacts/venue.schema.json` | Proposed public venue schema (v0.2.0) | draft, validates 251 included records |
| `artifacts/venue_inventory.schema.json` | Internal auditable inventory schema | draft, validates all 303 |
| `artifacts/event.schema.json` | Proposed public event schema | draft, validates |
| `CLASSIFICATION_MODEL.md` | Explicit, auditable rule specification (6 ordered rules) | implemented |
| `CLASSIFICATION_REPORT.md` | Generated outcome report (numbers from data, cannot drift) | generated |

## Built products (Phase 1)

| File | What it is |
|---|---|
| `data/public/venues.json` | 251 included venues, public output |
| `data/public/neighbourhoods.geojson` | 143 LOR Bezirksregionen with per-region venue counts |
| `data/public/metadata.json` | Versions, counts, attribution, vocabularies |
| `data/internal/venue_inventory.json` | All 303 records, auditable, never deployed |
| `data/internal/classification.json` | Per-record rule trace |
| `data/internal/review_queue.json` | 43 pending_review records with reasons |
| `data/deploy-allowlist.txt` | Allowlist — the only paths a Pages deploy may publish |

## Evidence discipline

Every claim in the report is tagged:

- **[V] Verified** — I fetched it and can point to the response or file.
- **[O] Observation** — read from the code/data, not externally tested.
- **[R] Recommendation** — my proposal, not yet built.
- **[A] Assumption** — believed, not verified.
- **[Q] Open question** — needs a human decision.

Nothing in this branch is deployed. Nothing here should be read as a claim that a site
"has been scraped" beyond the single fetch recorded in `sample_events.json`.
