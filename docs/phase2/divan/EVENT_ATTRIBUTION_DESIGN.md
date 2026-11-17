# Event attribution design — the rules every adapter needs

Status: **design + reference implementation**, covering the venue-attribution case.
Not a production pipeline, and not sufficient for publication.

This exists because two failures in Phase 2 were not source-specific. They recur in every
adapter, so the rules live in one module (`pipelines/src/kiez_atlas/attribution.py`) as pure
functions with tests, rather than being re-invented per venue.

---

## 1. The two failures this design prevents

**Calendar ownership is not venue membership.** Phase 2.1 tested berlin.de: a `v_ort`
venue-scoped feed turned out to be only ~47% venue-precise. Half the records belonged elsewhere.

**Naming a venue is not locating an event.** The Divan audit found 9 records whose location
string named both Divan buildings, classified `divan_hosted` because the target address was
present in the string. That inflates the count of events that appear at a marker.

Both are the same error: substituting an *association* for a *place*.

## 2. Separate the entities

An organisation and a physical venue are not the same thing.

```
Organisation ──< Venue ──< Event occurrence
                  └── Marker (0..1, what the Atlas draws)
```

Divan is one organisation with two buildings (Nehringstr. 8 and 26) and today has one marker.
Attributing building 26's 36 events to marker 8 is the failure mode; the fix is a second venue
record, not a filter bolted onto the adapter.

Consequences for the data model:

- `venue_id` identifies a **place**, and is the only thing a marker may be keyed on.
- An organisation link is separate, so "all events by this organisation" stays answerable
  without contaminating map placement.
- A venue may have **no** marker. Absence is a real state, distinct from "not yet audited".

## 3. Evidence hierarchy

Attribution must come from per-event evidence. Ranked by what each can establish:

| evidence | can establish hosted? | why |
|---|---|---|
| exact verified street **and** house number | **yes** | identifies one physical place |
| official programme page naming the venue | **yes** | publisher's own statement about this event |
| organiser / partner mention | supporting only | says who runs it, not where it is |
| venue name in the event title | **no** | marketing text |
| same district or neighbourhood | **no** | thousands of venues share a district |
| calendar ownership / feed scope | **no** | see §1 |

Weak evidence must never reach `hosted`. This is enforced by code structure, not convention:
only a strong address match returns `hosted`.

## 4. The ambiguity guard

> A location string that identifies multiple physical venues is **ambiguous** unless
> independent evidence identifies the actual event location. Membership of the target venue
> among several named locations is insufficient.

Ordering is the whole point: the guard runs **before** positive matching. A version that matched
first and then noted ambiguity would still emit `hosted` counts inflated by shared-address
records — it would look correct and be wrong.

## 5. Publication gate

`classification` alone cannot express "hosted, but at a different building". Sibling-building
events are genuinely hosted, so a classification-only gate publishes them at the wrong marker.

```python
attribution.is_publishable_at_venue()   # hosted AND site == "mapped_venue"
```

Both halves are required. `PUBLISHABLE_AT_VENUE` is retained for the classification set only;
using it alone is now caught by `test_exactly_175_audited_events_pass_the_publish_gate`.

## 6. Recurrence: series and occurrences

221 Divan records are 58 distinct titles. Instances must be retained for scheduling and
normalised to series before display: the busiest title at the mapped venue occurs 9 times in a
single month, so an un-normalised map draws the same weekly group as 9 separate markers.

```
Series (title + time pattern + venue) ──< Occurrence (concrete date)
```

Required before publication:

- **series identity.** No per-event URL exists, so identity must be derived from
  (title, time pattern, venue). Derived identity is fragile across source edits and must be
  treated as provisional.
- **expiry filtering.** 85 of 175 mapped occurrences are already past. Expiry needs an explicit
  recorded cutoff: 10 records end during the audit day itself, so a cutoff later that day moves
  every "current" count. `DIVAN_ATTRIBUTION_SUMMARY.json` now records `expiry_cutoff`, and the
  generator raises if a stored flag disagrees with its timestamps.
- **de-duplication across pages**, since listing pages repeat occurrences.

## 7. Normalisation rules

German address sources vary freely, and silent non-matching reads as "not our venue":

- `ß` → `ss` (NFKD does not decompose it; sources mix `Straße` / `Strasse` / `Str.`).
- `strasse` ↔ `str` accepted as equivalent street spellings.
- house numbers must match **exactly** — `8` must not match `8a`, `18` or `26`.
- punctuation, case and diacritics folded; whitespace collapsed.

## 8. Scope — what this design does not yet cover

Implemented: location-based attribution, the ambiguity guard, the publication gate, address
normalisation, and a drift-proof summary generator.

Not implemented: the organisation/venue/marker split, series and occurrence models, licence and
robots review, publisher contact, and stable event identity. **The Atlas is not production-ready
on the strength of this document.** Divan is `qualified_with_filter`, which means a filter can
be written — not that it has been.

## 9. Next milestone

A shared recurrence model, then the venue/organisation split, then a second source through the
same module. A design proven on one source is a hypothesis; the second source is the test.

---

*Reference implementation: `pipelines/src/kiez_atlas/attribution.py`.
Tests: `pipelines/tests/test_attribution.py`. Evidence: `DIVAN_ATTRIBUTION_AUDIT.md`.*
