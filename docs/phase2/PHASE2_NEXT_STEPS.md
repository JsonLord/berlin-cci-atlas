# Phase 2 — Next Steps

Prioritised, evidence-based. Nothing here is a commitment to build; it is what the
findings in `PHASE2_SOURCE_DISCOVERY.md` support.

---

## 1. Is there enough coverage to justify a first pilot?

**Yes — but narrowly, and not for full automation.**

The evidence:

- **2 of 27 sources qualified** with real dated records (Divan, Lettrétage)
- **1 mechanism can potentially reach 110 venues** (berlin.de calendar RSS, 100 dated
  items per feed, verified on 2 calendar IDs)
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
| 1 | **Interkulturelles Stadtteilzentrum Divan** | microdata | 225 events, ISO dates, verified | low |
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

1. **`berlin_de_rss`** — highest reach (potential 110 venues), dated items already
   structured in the guid. **Build this first even though it is third in the source list**,
   because it is the only mechanism whose value scales with discovery effort.
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
| 1 | **berlin.de terms.** robots.txt requires a self-identifying UA *and* full REP compliance, reserves discretionary blocking, and calls non-compliant access "misuse". A 429 has already been observed. | 110 venues depend on this staying permitted |
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

## 7. Recommended single next step

> **Build the `berlin_de_rss` adapter against 3 known calendar IDs (320, 409, and one to
> discover), with the `count > 0`, staleness and date-parse guards, and measure how many
> of the 110 berlin.de venues can be attributed from calendar IDs alone.**

That one task either unlocks the largest venue block in the directory or proves it
cannot be attributed — both are decisive, and both are cheap compared with writing
per-venue HTML parsers for the imperia pages.
