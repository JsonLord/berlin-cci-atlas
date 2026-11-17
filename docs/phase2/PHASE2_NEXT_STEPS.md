# Phase 2 — Next Steps

> **CORRECTION (2026-11-14, after `pilot/BERLIN_DE_RSS_PILOT.md`):** the "110 venues"
> reach estimate below was tested and is **substantially refuted**. Only **13/86 (15%)**
> of berlin.de venues expose a venue-scoped `v_ort`, **59%** expose no calendar link at
> all, and where `v_ort` exists the feed is only **~47%** precise. Realistic reach is
> **~17 venues**, not 110. Read the pilot before acting on §2–§3.

Prioritised, evidence-based. Nothing here is a commitment to build; it is what the
findings in `PHASE2_SOURCE_DISCOVERY.md` support.

---

## 1. Is there enough coverage to justify a first pilot?

**Yes — but narrowly, and not for full automation.**

The evidence:

- **2 of 27 sources qualified** with real dated records (Divan, Lettrétage)
- **1 mechanism reaches ~17 venues, not 110** (berlin.de calendar RSS; `v_ort` on 15% of
  venue pages, ~47% feed precision — see `pilot/BERLIN_DE_RSS_PILOT.md`)
- **22 candidates exist but are unproven** — a discovery backlog, not coverage
- **1 mechanism is provably reusable across venue types** (microdata)

So: enough to justify **a first extraction pilot over 3 mechanisms**, not enough to
justify scheduled crawling of 251 venues. The honest yield is unknown; the pilot exists
to measure it.

---

## 2. Strongest 5–10 pilot sources

Ordered by (evidence × reach) / effort.

| # | venue | mechanism | evidence | effort |
|---|---|---|---|---|
| 1 | **Interkulturelles Stadtteilzentrum Divan** | microdata | 221 events, ISO dates, verified; 175 at the mapped venue | low |
| 2 | **Lettrétage** | jsonld | 2 dated events with stable URLs, verified | low |
| 3 | **Anna-Seghers-Bibliothek** (Lichtenberg) | berlin.de RSS `c=320` | 100 dated items verified | low |
| 4 | **Anton-Saefkow-Bibliothek** (same system) | berlin.de RSS `c=320` | same feed; tests venue-level filtering | low |
| 5 | **Bettina-von-Arnim-Bibliothek** (Pankow) | berlin.de RSS `c=409` | 100 dated items verified | low |
| 6 | **Bärenzwinger** | kgberlin WP REST + ACF | verified in Phase 1 (`acf.start_date`) | low |
| 7 | **Gutshaus Lichterfelde** | Tribe REST | **expected to fail** — deliberate negative control | low |
| 8 | **Fahrbereitschaft / ceecee.cc** | HTML | **expected to be stale** — staleness-guard control | medium |
| 9 | **Kiez-Treff West** | WordPress + event page | plausible, unproven | medium |
| 10 | **Brotfabrik** | imperia HTML | dates present, no structure | medium |

**Sources 7 and 8 are included on purpose.** A pilot that only contains sources expected
to succeed cannot tell you whether the guards work. These two are the regression fixtures
for "empty result" and "stale content".

---

## 3. Parser types to implement first

In this order:

1. **`berlin_de_rss`** — real but narrower than assumed: ~17 venue-attributable of 110.
   Cheap to build (guid parsing) and must carry a **venue-match filter** or ~53% of
   records will be misattributed. No longer justifiable *solely* on reach.
2. **`microdata_event`** — simplest correct parser; `content` attrs give full ISO
   timestamps. Covers Divan and likely the library makerspaces.
3. **`jsonld_event`** — needed for Lettrétage and later gallery/hub sites; requires
   listing→detail traversal.
4. **`tec_rest_v1`** — only where a source is genuinely wired (`count > 0`), with a hard
   assertion.

**Deferred:** `html_listing` per-section selectors (imperia, Events Manager), Wix/browser
automation. These are the expensive tail; build them only after the four above are proven
and the pilot has measured a real yield.

---

## 4. Non-negotiable guards

Any extractor ships with these or it does not ship:

| guard | test case |
|---|---|
| `count > 0` or the source is unhealthy | **Steglitz** returns 200 with 0 events |
| newest event ≥ now − 90 days, else stale | **ceecee.cc** returns 2023 events |
| `start_datetime` must parse, else quarantine | ZK/U-style year-less dates (Phase 1) |
| never trust `offers.priceCurrency` | MGH Wassertor emits `"$"` (Phase 1) |
| `price_status: unknown` ≠ free | Phase 1 policy |
| rate limit ≥1 req/min per host, back off on 429 | **berlin.de** returned 429 |

---

## 5. Unresolved before any public event publication

These block publication, not the pilot.

| # | question | why it matters |
|---|---|---|
| 1 | **berlin.de terms.** robots.txt requires a self-identifying UA *and* full REP compliance, reserves discretionary blocking, and calls non-compliant access "misuse". A 429 has already been observed. | ~17 reachable venues depend on this |
| 2 | **Upstream code/data licence (Phase 1 Q2).** No `LICENSE` in either repo. Permission to publish a *derivative* atlas is unresolved. | Blocks publishing anything derived |
| 3 | **LOR geometry licence + vintage** — still `provisional`, `blocks_publication: true`. | Blocks publishing the map layer |
| 4 | **Event-level suitability.** Phase 1 policy is €20 cap with explicit price states. Phase 2 found **no reliable price source**. | Cannot gate on price; must review |
| 5 | **Cancellation/postponement.** No source in the sample exposes a status field. | Publishing a cancelled event is a correctness failure |
| 6 | **Event deduplication across sources.** berlin.de may already carry a venue's events; a venue may also publish its own. | Double-counting. Also the future central-scraper overlap. |
| 7 | **The 43 pending-review venues** must stay pending. Source discovery must not promote them. | Phase 1 policy |

---

## 6. What should be deferred

- **Scheduled crawling / GitHub Actions ingest.** The task forbids it in this phase, and
  the evidence (`2/27`) does not support it yet.
- **Full 251-venue sweep.** Discover breadth first via the berlin.de RSS path and
  platform grouping; pilot depth on 10.
- **Playwright.** One source in the sample likely needs it (Wix). Not worth the weight
  for one venue.
- **Price extraction.** No structured price source exists. Prose extraction is candidate
  evidence for a human, never a publishable number.
- **Central event-scraper integration.** Must remain untouched. Export qualified sources
  only after the pilot proves extraction.
- **Any claim of population coverage.** 10.8% inspected, 2 qualified.

---

## 7. Recommended single next step — REVISED after the pilot

The original recommendation below **was executed**. Result: `pilot/BERLIN_DE_RSS_PILOT.md`.
Attribution works but covers ~17 venues, not 110.

> **Revised: build a `berlin_de_rss` adapter parameterised by `v_ort`, with a mandatory
> venue-match filter (venue name or alias must appear in title/description, else
> quarantine), and measure the true per-venue event yield on the 13 confirmed `v_ort`
> venues.**

The venue-match filter is not optional. Without it ~53% of records would be attributed to
the wrong venue — worse than showing nothing, because it looks correct.

## 8. What the pilot proved about method

Testing the hypothesis cost one session and changed a headline number by an order of
magnitude. The same treatment should be applied to the remaining Phase 2 assumptions
before any adapter is built:

- `microdata_event` (Divan): **measured — see `divan/DIVAN_ATTRIBUTION_AUDIT.md`.** Of 221
  items (the 225 did not reproduce), 175 are at the mapped venue, 36 at Divan's second
  building, 10 ambiguous: map precision 79.2%, organisation precision 95.5%. The source is
  now `qualified_with_filter`, not `qualified` — extraction works, raw publication does not.
- `jsonld_event` (Lettrétage): one event per page, so precision is structurally 100%.
  Low risk.

<details><summary>Original recommendation (superseded)</summary>

> Build the `berlin_de_rss` adapter against 3 known calendar IDs (320, 409, and one to
> discover), with the `count > 0`, staleness and date-parse guards, and measure how many
> of the 110 berlin.de venues can be attributed from calendar IDs alone.

</details>
