# Phase 2 — Event-Source Discovery

**Status: feasibility study. No crawler built, no workflow added, no data published.**
Observation window: 2026-11-14. Branch `phase2/source-discovery` (not merged).

---

## 1. Scope and methodology

Phase 2 asks: *do the 251 published Phase 1 venues publish public events, where, and
can we extract them?* It does not build production extraction.

### Population, recalculated from merged `main`

| measure | count |
|---|---|
| Original records | 303 |
| Physical venues | 302 |
| Online portal (excluded) | 1 |
| **Included — study population** | **251** |
| Pending review — kept separate, **not promoted** | 43 |
| Excluded | 9 |

These were recomputed from `data/public/venues.json` and
`data/internal/venue_inventory.json` on `main` at `80a2dbc`, not copied from the
Phase 1 report.

### Sampling

Inspecting 251 sites was not proportionate to a feasibility question, so a **stratified
deterministic sample of 27 venues** was drawn across `venue_type` × `website_kind`, then
sorted by `venue_id` and taken in order — reproducible and not cherry-picked toward
venues already known to publish events.

**27 of 251 inspected (10.8%). 224 remain uninspected.** The sample covers 16 distinct
hosts, including every architecture family found in the population.

Why this framing matters: **154 of 251 venues have no domain of their own.** They sit on
berlin.de (64 libraries + 12 VHS + 27 galleries…), kgberlin.net, or bbk-kulturwerk.de.
Sampling those as if they were independent sites would have been wrong — they are a
handful of shared CMS platforms.

### Method, and its limits

Per the task's preference order, for each in-scope URL: event listing page → RSS/Atom →
ICS → JSON-LD → CMS/REST API → conventional HTML. Browser automation was **not** used.

Access discipline: one request at a time, 1.5 s between requests to the same host,
`robots.txt` fetched and obeyed before any path was requested, a truthful identifying
User-Agent, no auth/paywall/anti-bot circumvention. 188 probes total.

**One observed rate limit:** `berlin.de` returned **HTTP 429** on a second calendar
request within the same minute. That is a hard constraint for any future design.

---

## 2. Findings

### 2.1 Source status distribution (27 inspected)

| status | count |
|---|---|
| `qualified` | **2** |
| `candidate` | 22 |
| `temporarily_unavailable` | 2 |
| `not_suitable` | 1 |

**Only 2 of 27 sources met the qualification bar** — a dated, usable event record
actually extracted and sampled. This is the headline, and it is deliberately strict.
`candidate` is not a euphemism for "probably works": it means a plausible URL exists and
extraction was *not* demonstrated.

### 2.2 The two qualified sources

**Interkulturelles Stadtteilzentrum Divan** — `simcal_microdata`
`https://nachbarschaftszentrum-divan.de/kalender/`

225 `schema.org/Event` microdata items with ISO-8601 `startDate`/`endDate` in `content`
attributes. Samples:

| title | start | end |
|---|---|---|
| Melee e.V. Videospiel-Turnier | 2026-11-01T12:00+01:00 | 2026-11-01T22:00+01:00 |
| VHS Elternkurs Deutsch | 2026-11-02T09:00+01:00 | 2026-11-02T13:00+01:00 |
| Familienwegweiser | 2026-11-02T12:00+01:00 | 2026-11-02T16:00+01:00 |

Caveat: Simple Calendar emits **no per-event permalink**, so event identity must be
derived from venue+date+title. Recurring flags are present (`simcal-event-recurring`).

**Lettrétage** — `jsonld`
`https://www.lettretage.de/programm/`

Per-event JSON-LD on each `/programm/<slug>` page. Samples:

| title | start | end | url |
|---|---|---|---|
| Cyprus Inherited | 2026-11-15T16:00Z | 2026-11-15T18:30Z | `/programm/cyprus-inherited` |
| Quiet Anomalies — Silent Listening Session | 2026-11-21T18:30Z | 2026-11-21T21:00Z | `/programm/quiet-anomalies----silent-listening-session` |

The **listing** page carries no JSON-LD; only detail pages do. So extraction needs
listing→detail traversal, not a single fetch.

### 2.3 The largest lever: berlin.de's calendar RSS

Not a venue site, but the most consequential single finding.

`https://www.berlin.de/land/kalender/index.php?rss&c=<ID>` returns a **100-item RSS
feed of dated events** per city calendar. Verified for two IDs:

- `c=320` (Lichtenberg libraries) → 100 items
- `c=409` (Pankow libraries) → 100 items

Each item carries a `guid` encoding id+date+time:
`baevents:event:297509:2026-11-14:10-00-00`, and titles embed date and time
(`FamilienSamstag | Asja Bonitz … (14.11.2026 10:00 Uhr)`).

**This mechanism can serve ~17 berlin.de-hosted venues, not 110** — tested and refuted
in `pilot/BERLIN_DE_RSS_PILOT.md`: only 13/86 venue pages expose a venue-scoped `v_ort`,
59% expose no calendar link at all, and a `v_ort` feed is only ~47% venue-precise.

### 2.4 Platform architecture, by venue count

| platform | venues in sample | structured events? |
|---|---|---|
| **imperia** (berlin.de CMS) | 12 | No JSON-LD/microdata. Dates in HTML only. Calendar via separate RSS by ID. |
| WordPress (various) | 6 | Mixed. Divan qualifies; Steglitz TEC markers present but REST returns 0; ExRotaprint has none. |
| TYPO3 | 1 | No event structure found |
| Wix | 1 | Client-rendered, not extracted |
| Drupal (10/11) | 2 | No event listing found |
| phpwcms 1.10.2 | 1 | Legacy, dates present, no structure |

**"It runs WordPress" predicts nothing.** Three WordPress sites produced three different
outcomes. Each must be probed.

### 2.5 Failures and traps worth recording

These are the cases that make the number 2 credible rather than 20.

| venue | trap |
|---|---|
| **Gutshaus Lichterfelde / STZ Steglitz** | Tribe Events markers in HTML, but `wp-json/tribe/events/v1/events` returns **`count: 0`** even with `start_date`, and `/events/?ical=1` is **404**. A "TEC detected → it will work" shortcut would produce an empty feed. |
| **Fahrbereitschaft / ceecee.cc** | `/events/` returns 200 with dates — but the newest is **2023-01-21**. Stale by ~3 years. A parser would report success and a map would show expired events. |
| **Freizeitforum Marzahn** | The inherited URL is a **visitberlin tourism page**, not the venue. Wrong granularity entirely. |
| **FamilienBegegnungsZentrum Altglienicke** | Inherited URL returns **404**. |
| **Ateliers Uferhallen** | Connect/DNS failure from this environment (also seen in Phase 1). Cannot distinguish dead domain from sandbox DNS. |
| **ExRotaprint** | WordPress, no event listing, no structured data: genuinely `not_suitable`. |
| **berlin.de** | **HTTP 429** observed on repeat calendar requests. |

---

## 3. Limitations

1. **10.8% coverage.** 224 venues uninspected. Nothing here supports a claim about the
   population rate.
2. **`candidate` ≠ works.** 22 candidates are a to-do list, not a result.
3. **Only 2 qualified sources.** Too few to estimate a population yield.
4. **No detail-page traversal at scale.** Lettrétage qualified by inspecting two detail
   pages manually; a listing-level parser would still need building.
5. **berlin.de calendar-ID discovery is unproven at venue level** — verified for 2 IDs
   representative of whole districts, not per venue.
6. **No review of site terms** was performed beyond `robots.txt`. A legal review is a
   prerequisite for any extraction beyond study scale.
7. **Prices were not assessed.** Nothing here establishes whether price is extractable —
   Phase 1 already showed structured price fields are largely absent.
8. **One environment.** All fetches came from a single sandbox IP.

---

## 4. Recommendations

1. **Do not estimate a yield from this sample.** 2/27 with a deliberately strict bar is a
   signal to invest in *breadth of discovery*, not a conversion rate.
2. **Prioritise the berlin.de RSS path only for the ~17 venues where `v_ort` exists** —
   the 110-venue reach was tested and refuted (15% coverage, ~47% precision). See
   `pilot/BERLIN_DE_RSS_PILOT.md`.
3. **Promote candidates to `qualified` only by extracting and sampling real records** —
   the same bar Divan and Lettrétage met.
4. **Add a staleness guard** to any extractor before it ships; ceecee.cc is the test case.
5. **Never trust platform detection** as evidence: the Steglitz Tribe case is the test
   case for "declared endpoint, empty result".
6. **Resolve the berlin.de term question** (identifying UA, REP compliance, discretionary
   blocking, observed 429) before any recurring use.

**Pilot follow-up:** `pilot/BERLIN_DE_RSS_PILOT.md` tests the berlin.de reach claim and
revises it downward by an order of magnitude.

Full per-source evidence: `PHASE2_SOURCE_REGISTRY.json` / `.csv`.
Technical detail: `PHASE2_TECHNICAL_FINDINGS.md`. Priorities: `PHASE2_NEXT_STEPS.md`.
