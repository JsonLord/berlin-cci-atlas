# Phase 2 — Technical Findings

Observed architectures, parser feasibility, and the extraction problems that recur.
All statements are backed by a probe recorded in `PHASE2_SOURCE_REGISTRY.json`.

---

## 1. Observed source architectures

| architecture | how to spot it | event surface | parser feasibility |
|---|---|---|---|
| **Simple Calendar → Google Calendar** | `simcal` classes, `li.simcal-event` | `schema.org/Event` **microdata** with ISO dates in `content` attrs | **Easy.** Best case in the sample. |
| **Next.js / per-page JSON-LD** | `application/ld+json` with `@type: Event` on detail pages | JSON-LD on `/programm/<slug>`, **not** on the listing | Easy, but needs listing→detail traversal |
| **berlin.de imperia CMS** | `generator: imperia9/14/...` | dates in HTML prose; **no** JSON-LD or microdata | Medium. Needs a selector per section *plus* the RSS path. |
| **The Events Calendar (Tribe)** | `tribe-events` strings | REST `/wp-json/tribe/events/v1/events`, ICS `?ical=1` | Easy **when wired**; see trap §3.1 |
| **Modern Events Calendar** | `mec-` classes | JSON-LD `Event` | Easy, but see the `priceCurrency` trap from Phase 1 |
| **Events Manager** | `events-manager`, `em-item` | server-rendered `data-date` | Medium (theme-dependent selectors) |
| **Wix** | `generator: Wix.com` | client-rendered | Hard; likely needs browser |
| **Drupal 10/11** | `generator: Drupal` | none found | Not suitable in sample |
| **phpwcms 1.10.2** | `generator: phpwcms` | dates in HTML, no structure | Medium/legacy |

### The important architectural fact

**154 of 251 venues have no own domain.** Their "website" is a berlin.de, kgberlin.net
or bbk-kulturwerk.de page. A per-venue parser design at 251 venues is the wrong shape;
a **per-platform** design is the right one:

| platform | potential venue coverage |
|---|---|
| berlin.de calendar RSS | up to 110 |
| kgberlin WP REST + ACF | 28 |
| bbk-kulturwerk | 6 (shared page, no events — Phase 1 finding) |
| individual sites | ~103 |

---

## 2. Parser feasibility by mechanism

### 2.1 Microdata (Divan) — easiest

```html
<li class="simcal-event" itemscope itemtype="http://schema.org/Event">
  <span itemprop="startDate" content="2026-11-01T12:00:00+01:00">1 November 2026</span>
  <span itemprop="endDate"   content="2026-11-01T22:00:00+01:00">22:00</span>
  <span itemprop="location" itemscope itemtype="http://schema.org/Place">
```

`content` carries a full ISO-8601 timestamp with offset — no date guessing needed.
225 items on one page. **No per-event URL**, so identity = (venue, date, title).

### 2.2 JSON-LD detail pages (Lettrétage) — easy but two-step

```json
{"@type":"Event","name":"Cyprus Inherited",
 "startDate":"2026-11-15T16:00:00.000Z","endDate":"2026-11-15T18:30:00.000Z",
 "url":"https://www.lettretage.de/programm/cyprus-inherited"}
```

Note `Z` suffix — the source emits UTC. Convert to `Europe/Berlin` for display, and be
aware that a `Z` timestamp at 16:00 becomes 17:00 CET in November.

### 2.3 berlin.de RSS — the highest-leverage mechanism

```
GET https://www.berlin.de/land/kalender/index.php?rss&c=320
→ 200, application/rss+xml, 100 items
```

```xml
<item>
  <title>FamilienSamstag | Asja Bonitz - Wünsche werden wahr (14.11.2026 10:00 Uhr)</title>
  <guid isPermaLink="false">baevents:event:297509:2026-11-14:10-00-00</guid>
  <link>https://www.berlin.de/land/kalender/index.php?detail=297509&amp;ls=0&amp;c=320&amp;date_start=14.11.2026</link>
</item>
```

**Date and time are not in RSS date fields.** They live in the `guid` (structured,
machine-readable) and duplicated in the title (human). Parse the guid; treat the title as
a cross-check. Stable identity comes from `baevents:event:<id>`.

The feed is **calendar-scoped, not venue-scoped**: `c=320` covers the Lichtenberg
library system. Venue attribution requires either per-venue calendar IDs or a
`v_ort=` parameter (seen on a Pankow URL) — the latter is unverified.

### 2.4 ICS — not found usable in this sample

The one ICS-shaped endpoint (`stadtteilzentrum-steglitz.de/events/?ical=1`) returned
**404** while Tribe markup was present. Do not plan around ICS until a source actually
serves `text/calendar`.

---

## 3. Common extraction problems

### 3.1 Declared endpoint, empty result

`stadtteilzentrum-steglitz.de` advertises Tribe Events markers. Its REST API:
`/wp-json/tribe/events/v1/events?per_page=5` → **200, `count: 0`**, even with
`start_date`. Its ICS → 404.

**Rule:** a 200 response with zero events is a *failure*, not a success. Any extractor
must assert `count > 0` before marking a source healthy.

### 3.2 Stale content that looks fresh

`ceecee.cc/events/` returns 200 with dates — newest `21.01.2023`. A naive parser reports
success; the map would show events three years expired.

**Rule:** every record needs an expiry check against `now`, and every source a
"newest observed event" freshness signal. Phase 1 already defines `source_freshness`;
this is its event-level analogue.

### 3.3 Wrong-granularity inherited URL

`Freizeitforum Marzahn`'s inherited URL is a **visitberlin tourism page**. It has events,
but they are Berlin-wide, not this venue's programme.

**Rule:** `website_kind: directory_reference` from Phase 1 already predicts this. Directory
references should be treated as discovery hints, not as sources.

### 3.4 Dead and unreachable sources

| venue | symptom |
|---|---|
| FamilienBegegnungsZentrum Altglienicke | inherited URL **404** |
| Ateliers Uferhallen | connect/DNS error from this environment |

The second is ambiguous: it may be the sandbox, not the site. Recording it as
`temporarily_unavailable` rather than `not_suitable` is the honest call.

### 3.5 Rate limiting on the biggest host

`berlin.de` returned **HTTP 429** on a repeat calendar request within a minute.

**Rule:** any berlin.de design needs ≥1 request/minute per client, conditional requests,
and exponential backoff that treats 429 as a first-class signal.

### 3.6 Platform detection is not evidence

Three WordPress sites, three outcomes: Divan (225 events, qualified), Steglitz
(Tribe markers, 0 events), ExRotaprint (no events at all). Detecting a CMS tells you
which parser to *try*; it says nothing about whether events exist.

---

## 4. Reusable technical approach

The smallest thing that would cover the qualified sources plus the berlin.de lever:

```
adapters (one per mechanism, not per venue)
  microdata_event      schema.org/Event in HTML            → Divan, library makerspaces
  jsonld_event         JSON-LD Event on detail pages       → Lettrétage
  berlin_de_rss        guid-parsed RSS per calendar id     → up to 110 venues
  tec_rest_v1          Tribe REST, assert count>0          → if a source is wired
  html_listing         per-section selector fallback       → imperia, Events Manager

guards (applied to every adapter, without exception)
  assert count > 0                    else source is unhealthy
  assert newest_event >= now - 90d    else source is stale
  assert start_datetime parses        else record is quarantined
  never trust offers.priceCurrency    (Phase 1: '$' on a Berlin venue)
```

The guards are not optional extras. Without them the sample would have "succeeded" on
three sources that would have published nothing correct: Steglitz (0 events),
ceecee (2023 events), and any price filter built on `$`.

---

## 5. What this phase did not establish

- Whether price is extractable at all (Phase 1 suggests largely not).
- Whether cancellation/postponement is detectable. **No source in the sample exposed a
  status field.** Phase 1 found exactly one JSON-LD source with `eventStatus`, always
  `EventScheduled`.
- Whether venue-level calendar IDs exist for the other berlin.de venues.
- Any population yield rate.
