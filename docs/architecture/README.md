# Architecture design — organisation, venue, series, occurrence

**Status: proposal index. Nothing here is implemented, and none of the four
documents below has been written yet.** No code, data, frontend, CI or
deployment file depends on this directory. Design only, awaiting owner review.

Base: `main` at `31ed7e3611e63f9146a113a17b80dd3b6ec6dbdc`, verified 2026-11-25 from a
clean clone (137 tests passed, `cli validate` 46/46, worktree clean).

The design is intended to be four documents, read in this order. They are listed
here so the scope is reviewable before anyone writes them; **they do not exist
yet**, and no link is offered that would 404.

| planned document | what it will decide |
|---|---|
| `ORGANISATION_VENUE_MODEL.md` | Organisation vs Venue as separate entities; the relationship entity; evidence and verification rules; cardinality. |
| `EVENT_SERIES_OCCURRENCE_MODEL.md` | Series vs Occurrence; identity and deduplication; recurrence; lifecycle and status transitions. |
| `DATA_MODEL_MIGRATION.md` | Current-to-proposed mapping, backward compatibility, migration stages, risks and rollback. |
| `ARCHITECTURE_DECISIONS.md` | Each decision, the alternatives considered, the trade-off, and what stays unresolved. |

## Ground rules this design keeps

- The existing lightweight Python architecture. No database, broker, cache or vector
  store.
- No LLM as a mandatory identity-resolution dependency. Deterministic rules first,
  human review for everything uncertain.
- The frontend is not changed. `index.html` is byte-checked against its committed blob
  by `cli validate`; that check must stay green.
- No production data change. `docs/phase2/divan/DIVAN_ATTRIBUTION_RESULTS.json`,
  `DIVAN_ATTRIBUTION_SUMMARY.json` and the fixture are historical evidence and stay
  exactly as they are.
- The source registry (`docs/phase2/PHASE2_SOURCE_REGISTRY.{json,csv}`) is not changed.
- No new crawler, no change to the central event scraper, no CI change, no deployment.

## The one-sentence version

An organisation is not a place, a place is not a programme, and a programme is not a
date — four entities where the repository currently has one (`PLACES`) plus an
unimplemented event schema, with a relationship entity between organisation and place
because the Divan audit proved that collapsing them publishes events at the wrong
marker.
