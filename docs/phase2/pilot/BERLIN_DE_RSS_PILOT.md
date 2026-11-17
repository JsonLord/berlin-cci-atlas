# Pilot — berlin_de_rss three-calendar attribution study

**Verdict: the 110-venue hypothesis is substantially refuted.**

The mechanism works. The **coverage** does not: at most ~15% of berlin.de venues are
venue-attributable, and the venue-scoped feed is only ~47% precise even where it exists.

Observation window 2026-11-14. Read-only. No workflow, no crawler, no published data.

---

## 1. What was hypothesised

Phase 2 reported that `https://www.berlin.de/land/kalender/index.php?rss&c=<ID>` returns
~100 dated events per feed, and that this "one mechanism can potentially reach 110
venues". That figure was flagged as **unverified**. This pilot tests it.

## 2. What the pilot found

### 2.1 The mechanism is real

Verified end-to-end. `?rss&v_ort=38489` (Philipp-Schaeffer-Bibliothek):

```
100 items | 8/8 sampled records parsed with event_id + date + time
  event 295742  2026-11-14 11:00  Autorenlesung und Workshop: „Ein singender Baum"
  event 250606  2026-11-16 16:00  Offenes Nähcafé
  event 200762  2026-11-16 17:00  Digital-Sprechstunde in der Philipp-Schaeffer-Bibliothek
  event 287107  2026-11-16 17:00  Vorlesen und Erzählen mit ehrenamtlichen Vorleser*innen
```

Parsing is clean: the `guid` is `baevents:event:<id>:<YYYY-MM-DD>:<HH>-<MM>-<SS>`, which
yields id, date and time without guessing. Titles also embed date/time as a cross-check.
**This part of the hypothesis holds.**

### 2.2 Venue scoping genuinely works — but is not precise

`v_ort` is a real venue parameter, discovered on venue pages as
`/land/kalender/?409&v_ort=37538`.

Proof it scopes: `v_ort=38489` shares only **1 of 100** guids with the unscoped city feed.

Proof it is **not precise**: items mentioning the actual venue:

| v_ort | venue | items | mention venue |
|---|---|---|---|
| 38489 | Philipp-Schaeffer-Bibliothek | 100 | **74%** |
| 45740 | Bibliothek am Luisenbad | 100 | **56%** |
| 37538 | Bettina-von-Arnim-Bibliothek | 80 | **10%** |

Mean precision **~47%**. The feed is venue-*leaning*, not venue-*scoped*. Roughly half
the records belong to somewhere else — plausibly sibling libraries in the same district
system, or events at nearby venues.

**Consequence:** any design that treated a `v_ort` feed as "this venue's events" would
attribute ~53% of records to the wrong venue.

### 2.3 Coverage is the decisive number

**86 of 110** berlin.de venues tested (78%). One representative per section, plus every
venue in the 12 multi-venue sections.

| discovery path | venues | share |
|---|---|---|
| `v_ort` present (venue-scoped) | **13** | **15.1%** |
| `c=` only (calendar-scoped, no venue param) | 22 | 25.6% |
| **neither** — no calendar link at all | **51** | **59.3%** |

Extrapolated to 110:

- ~**17** venues venue-attributable
- ~**28** venues calendar-attributable only (needs prose matching)
- ~**65** venues have **no reachable calendar link** on their page

**59% of berlin.de venues publish nothing the RSS mechanism can reach.** The
"110 venues" figure was wrong by roughly an order of magnitude.

### 2.4 Where v_ort does exist, it is genuinely per-venue

This is the one part of the hypothesis that strengthens:

| section | venues | distinct v_ort |
|---|---|---|
| stadtbibliothek-mitte/bibliotheken-und-besuch | 4 | **4** |
| stadtbibliothek-pankow/bibliotheken | 3 | **3** |

Each venue in a shared section carries its own `v_ort`. So where the parameter exists it
identifies the venue correctly — the problem is how rarely it exists.

### 2.5 Two traps found

**Trap A — the channel title lies.** A venue-scoped feed still reports
`<title>Kalender des Landes Berlin</title>`. Only `?c=` sets a district title. Any
health check that validates the channel title would pass a scoped feed while telling you
nothing about scoping.

**Trap B — 100 items is a cap, not a count.** Both `v_ort=38489` (100 items) and
`c=320` (100 items) hit exactly 100. Treat `len(items) == 100` as "possibly truncated",
not as a complete listing.

### 2.6 Rate limiting is a hard constraint

`berlin.de` returned **HTTP 429** twice during this pilot despite a 6-second
per-request delay. Backoff of 30–60s was required. A 50-page discovery pass took
~5 minutes wall-clock and still tripped the limit.

At 6s/request, discovering all 110 venue pages is ~11 minutes minimum, and each
discovered `v_ort` feed is a further request. This is workable at daily cadence, not at
hourly.

---

## 3. Answering the pilot question directly

> Can berlin.de venues be attributed from calendar IDs alone?

**Partly, for a minority.**

- `v_ort` **does** identify a venue where present — proven by 4-of-4 distinct values in
  one section.
- But it is present on only **15%** of venue pages.
- And even then the feed is only **~47%** precise, so per-record venue attribution still
  needs filtering.
- **59%** of venues expose no calendar link whatsoever.

The honest reachable figure is **~17 venues with acceptably-attributable feeds**, not 110.

---

## 4. What this changes

Phase 2's `PHASE2_NEXT_STEPS.md` recommended building the berlin.de RSS adapter first
because of its reach. **That recommendation is now weakened and should be revised
downward** — but not dropped:

- It is still the cheapest mechanism to implement (guid parsing, no HTML selectors).
- It still yields real dated events for ~17 venues.
- It should **not** be prioritised as a "110 venues" win, and it cannot replace
  per-venue discovery for the other 93.

## 5. Recommended next step, revised

1. **Do not build a berlin.de-wide adapter.** Build a `berlin_de_rss` adapter that takes
   an explicit `v_ort` per venue, discovered by scraping the venue page for
   `v_ort=<digits>`.
2. **Add a venue-match filter** to every record: require the venue name (or a known
   alias) to appear in title or description, else quarantine. Without it, ~53% would be
   misattributed. This is the direct analogue of Phase 1's `price_status: unknown` rule.
3. **Accept 17 venues** from this mechanism and plan per-venue discovery for the rest.
4. **Re-measure** with the venue-match filter applied to know the true per-venue event
   yield — that number is what decides whether the whole Atlas is worth building.

## 6. Limits of this pilot

- **86/110 tested**, not all. Extrapolations carry ±several venues.
- Precision measured on **3 venues only**. The 47% mean could be unrepresentative.
- Only `v_ort` and `c=` were probed; other scoping parameters may exist undiscovered.
- One sandbox IP; berlin.de 429 behaviour on a CI runner is untested.
- No site terms review beyond `robots.txt`, which permits the requests.
- Nothing here assesses event *suitability* (price, category, cancellation).

Machine-readable results: `pilot_results.json`.
