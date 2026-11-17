# Event attribution design — the rules every adapter needs

Status: **design + partial reference implementation**, covering the venue-attribution case only.
Not a production pipeline, and not sufficient for publication.

§8 states exactly which rules exist in code and which are design only. Read that before
quoting any capability of this module.

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

| evidence | should establish hosted? | implemented? | why |
|---|---|---|---|
| exact verified street **and** house number | **yes** | **yes** | identifies one physical place |
| official programme page naming the venue | **yes** | **no — not implemented** | publisher's own statement about this event |
| organiser / partner mention | supporting only | **no — not implemented** | says who runs it, not where it is |
| venue name in the event title | **no** | n/a — deliberately ignored | marketing text |
| same district or neighbourhood | **no** | n/a — never consulted | thousands of venues share a district |
| calendar ownership / feed scope | **no** | n/a — never consulted | see §1 |

Weak evidence must never reach `hosted`. That holds today, but be precise about *why*:
`classify_location` never consults title, description, organiser, district or feed scope at all.
The parameters `title` and `description` are accepted and **ignored** — passing them changes no
output, which `test_title_and_description_are_currently_inert` pins. So weak evidence cannot
reach `hosted` because it is never weighed, not because it is weighed and rejected.

The distinction matters for two reasons. First, `CLASSIFICATIONS` declares
`organised_elsewhere`, `partnered` and `external_event`, but no code path returns them: the only
reachable values are `hosted`, `ambiguous` and `insufficient_data`. Those three are vocabulary
reserved for the evidence tiers above, not delivered behaviour. Second, a future reader who
assumes supporting evidence is already handled will not implement it — the summary's
`divan_organised_elsewhere` and `divan_partnered` counts are 0 because the logic is absent,
which is why they are emitted explicitly rather than omitted.

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
gating on it alone is caught by `test_exactly_175_audited_events_pass_the_publish_gate`, which
replays all 221 audited records through `is_publishable_at_venue()` and requires exactly 175.
A classification-only gate returns 211, so the test fails on the regression rather than passing
silently. `PUBLISHABLE_AT_VENUE` itself is not referenced by any test: it is an internal
component of the gate, not a public API to gate on.

## 5a. Fixture reproducibility

The audit's headline number is only reproducible if the frozen page still yields it. That is
checked separately from the classifier, by `kiez_atlas.divan_fixture`:

```
PYTHONPATH=./pipelines/src python -m kiez_atlas.divan_fixture --repo .
```

It decompresses the fixture, re-extracts all 221 records using the documented rules, and
compares (title, start, end, location) against the committed results — reporting missing,
additional, duplicate and mismatched records, and exiting non-zero on any disagreement. It is
read-only: it cannot write the results file it checks.

This closes a gap that the digest check left open. `divan_audit.verify_fixture()` proves the
gzip still decompresses to a recorded hash, which shows the archive is intact but says nothing
about whether anyone ever counted its records. Before this command, "independent recount from
fixture: 221" in `DIVAN_ATTRIBUTION_AUDIT.md` was prose, not an executed check.

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

## 8. Scope — what the code does and does not do

This section is written as a table because the prose version let a design document read like a
feature list. Each "implemented" row names the code that exists and the test that holds it.
Anything without a named symbol is design only.

### Implemented

| capability | code | held by |
|---|---|---|
| address-based attribution (street + exact house number) | `VenueAddress.parse`, `.matches`, `classify_location` rule 2 | `test_exact_mapped_address_is_hosted_and_publishable`, `test_house_number_must_match_exactly` |
| German address normalisation (`ß`→`ss`, `strasse`↔`str`, case/diacritics/whitespace) | `normalise_address`, `VenueAddress._variants` | `TestAddressNormalisation` |
| sibling-building detection (same organisation, different building → `site="other_site"`) | `OtherVenue`, `classify_location` rule 3 | `test_sibling_building_is_not_publishable_at_mapped_venue` |
| multi-venue ambiguity guard, evaluated **before** positive matching | `classify_location` rule 1 | `TestMultiVenueAmbiguity`, incl. `test_multi_venue_guard_precedes_positive_address_match` |
| publication gate requiring classification **and** site | `Attribution.is_publishable_at_venue` | `test_exactly_175_audited_events_pass_the_publish_gate` (211 without the site half) |
| empty-location rejection | `classify_location` empty-text branch | `test_missing_location_is_not_publishable` |
| drift-proof summary generation (every count computed from the results file) | `divan_audit.summarise` | expiry cross-check raises inside `summarise`; `DIVAN_ATTRIBUTION_SUMMARY.json` regenerates byte-identically |
| fixture integrity (gzip digest) | `divan_audit.verify_fixture`, `divan_fixture.load_fixture_html` | `TestFixtureIntegrity`, `TestSummaryCarriesTrueDigest` |
| **fixture → results reproducibility, record for record** | `divan_fixture.verify` | `TestFixtureMatchesResults` + 6 negative controls |

### Not implemented

Design only. None of these have code, and the module does not approximate them.

| capability | status | consequence if assumed present |
|---|---|---|
| official programme-page evidence | **absent.** No fetcher, no parser, no evidence tier. §3 lists it as strong evidence; nothing reads a programme page. | The only strong evidence available is the location string. Records whose location is unusable can never be rescued, so `SAAL - Konzertbühne` stays `ambiguous` permanently. |
| organisation / venue separation | **absent.** `attribution.py` has no organisation concept; `site` is a 3-valued string on an attribution, not a venue entity. No `organisation_id`, no second `Venue` record for Nehringstr. 26. | The 36 sibling-building records have nowhere correct to go. They are excluded, not relocated — the second building publishes nothing. |
| recurrence model | **absent.** No series entity, no occurrence-to-series grouping, no de-duplication across pages. `data_quality_flags.recurring` is a copied source flag, not a derived structure. | 221 instances would render as 221 markers; the busiest title draws 9 markers in one month. |
| stable event identity | **absent.** `event_id` is `null` for all 221 records and `event_url` is empty for all 221; the source supplies neither. No derived-identity scheme exists or is chosen. | Nothing can be de-duplicated across refreshes, updated in place, or cited. §6's "(title, time pattern, venue)" is a proposal, not an implementation. |
| `organised_elsewhere` / `partnered` / `external_event` | **declared, unreachable.** No code path returns them; only `hosted`, `ambiguous`, `insufficient_data` are reachable. | The summary's zero counts for these read as "audited and none found". They mean "not assessable with current evidence". |
| licence and robots review, publisher contact | **absent.** | Publication legality is unestablished regardless of attribution quality. |

**The Atlas is not production-ready on the strength of this document.** Divan is
`qualified_with_filter`, which means a filter *can* be written — not that it has been. What is
implemented is enough to stop two specific overstatements reaching a public map, and enough to
prove the audited population is real. It is not enough to publish events.

## 9. Next milestone

A shared recurrence model, then the venue/organisation split, then a second source through the
same module. A design proven on one source is a hypothesis; the second source is the test.

---

*Reference implementation: `pipelines/src/kiez_atlas/attribution.py`.
Tests: `pipelines/tests/test_attribution.py`. Evidence: `DIVAN_ATTRIBUTION_AUDIT.md`.*
