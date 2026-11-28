# Pilot — Lettrétage JSON-LD Source Audit (p2-020)

**Verdict: The "detail pages have 100% venue precision" assumption is refuted.**

The JSON-LD extraction works cleanly and yields stable event permalinks. However, **attribution is not 100%**: 13.3% (4 of 30) of sampled events take place off-site in Schöneberg (*K26 – Raum für Ideen, Kolonnenstraße 26*), not at Lettrétage's mapped venue in Mitte (*Veteranenstraße 21*). 

Furthermore, the source website's CMS exhibits a structural template bug: it hardcodes `Veteranenstr. 21` in `location.address.streetAddress` across all events while editors type the real off-site venue into `location.name`. Without the architecture's pre-match ambiguity guard, all 4 Schöneberg events would have been misattributed to the Mitte map pin.

Observation window: 2026-11-27. Read-only audit.

---

## 1. What was Hypothesised

In `PHASE2_NEXT_STEPS.md` §8:
> *`jsonld_event` (Lettrétage): one event per page, so precision is structurally 100%. Low risk.*

This pilot audited all 30 live events reachable from `https://www.lettretage.de/programm/` to test this hypothesis.

---

## 2. Empirical Findings

### 2.1 Extraction & Structure (What Works)
- **30 / 30 event detail pages** sampled successfully via HTTP GET.
- **100% have valid `schema.org/Event` JSON-LD** scripts.
- **Stable Permalinks:** Unlike Divan (0 permalinks), Lettrétage provides individual canonical URLs for every event (e.g. `https://www.lettretage.de/programm/dead-ladies-show-44`).
- **ISO-8601 UTC Timestamps:** Start and end timestamps are emitted with trailing `Z` (UTC). Conversion to `Europe/Berlin` is required (e.g. `19:00:00.000Z` $\rightarrow$ `20:00:00+01:00` CET).

### 2.2 Attribution Breakdown

| Location / Site | Count | Share | Publishable at Veteranenstr. 21 |
|---|---|---|---|
| **Lettrétage Hauptspielstätte** (Veteranenstr. 21, 10119 Berlin) | **26** | **86.7%** | **YES (26)** |
| **K26 – Raum für Ideen** (Kolonnenstr. 26, 10829 Berlin) | **4** | **13.3%** | **NO (0)** |
| **Total Audited** | **30** | **100%** | **26 / 30 (86.7%)** |

### 2.3 The Webflow CMS Template Trap
The 4 off-site events (including a 3-part quarterly poetry workshop series) revealed a classic CMS defect:
```json
{
  "@type": "Place",
  "name": "K26 Raum für Ideen, Kolonnenstr. 26, 10829 Berlin",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Veteranenstr. 21",
    "addressLocality": "Berlin",
    "postalCode": "10119"
  }
}
```
The Webflow CMS page template injected the organisation's default postal address into `streetAddress`, while the human content editor entered the true event location into `name`.

**Evaluation against `kiez_atlas.attribution`:**
- A naive parser reading `streetAddress` alone would publish Schöneberg events at the Mitte venue pin.
- Running `classify_location(text=f"{name} {streetAddress}", venue=VETERANEN_21, other_venues=[K26])` triggers **Rule 1 (Multi-Venue Ambiguity Guard)**: because both addresses match, the event is classified as `ambiguous` and quarantined for human review.
- Result: **0 off-site events misattributed to the map pin.**

### 2.4 Pricing Analysis
Structured price data (`offers`) is **completely absent** in the JSON-LD.
However, human-readable prices exist in the `<meta name="description">` prose:
- 20 events: `"frei"` (free admission)
- 4 events: `"auf Spendenbasis"` / `"on a donation basis"`
- 3 events: Paid admission under €20 (`"8.-/4.-"`, `"5,-"`, `"5-15 €"`)
- 3 events: Unspecified / other

This corroborates the Phase 1 and Divan finding: structured price filters cannot be automated; events require human review or conservative pricing queues.

### 2.5 Recurrence & Series Confirmation
Lettrétage confirms the necessity of `EventSeries`:
- `Workshop simultan(poesie`: 3 occurrences scheduled across December 2026, March 2027, and June 2027.
- `Dead Ladies Show #44`: Occurrence 44 of a long-running literary series.
- Modeled under our architecture as `EventSeries` linked to concrete `EventOccurrence` records.

---

## 3. Conclusions for the Architecture

1. **Precision Hypothesis Refuted:** Event detail pages do **not** guarantee 100% venue precision. Cultural organisations frequently produce events off-site at partner spaces.
2. **Pre-Match Guard Validated:** Conflicting data within a single CMS page (template default vs editorial text) proves why the pre-match ambiguity guard must precede positive address matching.
3. **Decoupling Holds:** Lettrétage e.V. is the `Organisation`, Veteranenstraße 21 is `Venue A`, and Kolonnenstraße 26 is `Venue B`.
