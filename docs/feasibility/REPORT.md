# Kiez Events Atlas — Repository Assessment and Feasibility Blueprint

**PRELIMINARY — discovery and planning phase only. No product code, no deployment change.**

| | |
|---|---|
| Target repo | `JsonLord/berlin-cci-atlas` (fork), default branch `main` |
| Upstream | `https://github.com/kaitiwu/berlin-cci-atlas` |
| This branch | `docs/kiez-events-feasibility` — documentation only |
| Fieldwork date | 2026-11-13 (CET), single observation window |
| Author | Letta Code, on assignment from Leon Gründling |

**Tag legend used throughout:**
**[V]** Verified by an actual fetch or file read I can point to ·
**[O]** Observation from code/data, not externally tested ·
**[R]** Recommendation, not built ·
**[A]** Assumption, not verified ·
**[Q]** Open question needing a human decision

---

## 0. Executive summary

The fork is a **byte-identical copy of upstream** with two commits and three files
**[V]**. There is no divergence to reconcile, which is the best possible starting
condition.

The single most consequential finding is that **the geography problem is already
solved inside the inherited code**. `index.html` line 695 embeds an official-shaped
LOR layer with exactly **143 Bezirksregionen and 542 Planungsräume**, all geometries
valid, with a clean 6-digit→8-digit id hierarchy **[V]**. The brief asks me to
"investigate the official Berlin geodata required to implement it". That work is
already done. What is *not* done is attribution: `META.sources` lists seven sources
and **does not credit the LOR geography anywhere** **[V]** — see §7.2.

The second consequential finding is that **the venue directory is not a hub
directory**. It holds 303 places, but only **6** carry `cat: "hub"`, and the
directory's purpose is CCI *support services, workspaces and social infrastructure*
**[V]**. Treating "the hubs already in the Atlas" as the event universe means either
accepting 6 venues or redefining what a hub is. This is the central product decision
and it is unresolved **[Q1]**.

Third: **the map layer is adaptable without a rewrite**, and the frontend already
contains the exact pattern the brief wants — it `fetch()`es `data/search.json` and
`data/addr/{c}.json` with graceful fallback **[V]**. Event JSON can be added the same
way. The 3.26 MB inline data blob is the real constraint, not the framework.

Fourth, and most sobering: **the €20 price cap cannot be enforced automatically
today.** Across 7 real extracted events, **zero** had a trustworthy structured price
field **[V]**. Worse, the one source that does emit a structured price emits
`priceCurrency: "$"` with an empty amount for a Berlin community centre **[V]** —
a live trap that would silently corrupt any automated price filter.

**Go / no-go: conditional GO.** The technical pipeline is proven on real sites. The
blockers are legal (no licence file) and definitional (what is a hub), not technical.
Detail in §6.

---

## A. Repository findings

### A.1 Structure and git state

**[V]** `git ls-tree -r HEAD` returns exactly three files:

```
CONTRIBUTORS.md    1,052 bytes
config.js          1,587 bytes
index.html     4,581,536 bytes   (3,193 lines)
```

Two commits: `eeda63b "Add Berlin CCI Atlas"`, `d548d74 "Add files via upload"`.
Default branch `main`. No `README.md`, no `.gitignore`, no `.github/`, no `LICENSE`.

**Fork divergence: none.** I fetched upstream `main` into the fork and ran
`git diff --stat FETCH_HEAD HEAD`, which produced empty output; both heads resolve to
the same SHAs **[V]**. Every line in this repo is inherited. There is no "changes
already made in this fork" category to report — the entire fork-side contribution so
far is the act of forking.

`gh api repos/JsonLord/berlin-cci-atlas` reports `fork: true`,
`parent: kaitiwu/berlin-cci-atlas`, `has_pages: false`, `license: null`,
`homepage: null` **[V]**. Upstream also has `has_pages: false` (the Pages API returns
404 for both) **[V]**. So despite `config.js` naming "GitHub Pages" as host, **Pages
is not currently enabled on either repo**. The brief's instruction not to change Pages
configuration is therefore currently a no-op — there is nothing to preserve yet **[O]**.

No GitHub Actions workflows exist in either repo **[V]**.

### A.2 Frontend architecture

There is no build step, no bundler, no framework, no package manager. `index.html` is
the application. Script layout **[V]**:

| Line | Content |
|---|---|
| 692 | inline `window.ATLAS_CONFIG` defaults (`projectOwner`, `exampleData:false`) |
| 693 | `<script src="config.js">` — operator-editable overlay |
| 694 | `@supabase/supabase-js@2.45.4` from jsDelivr |
| **695** | **`window.ATLAS = {…}` — 3,260,270 chars, all geography + venues** |
| **696** | **`window.ATLAS_SEARCH = {…}` — 1,072,017 chars, search index** |
| 697 | `d3@7.8.5` from cdnjs |
| 698–941 | data layer: `liveBackend()` (Supabase) / `demoBackend()` (localStorage) |
| 942–3193 | the application |

Two lines hold 4.3 MB of the 4.6 MB file. **Line 695 is the whole data tier and line
696 is a derived search index** **[O]**.

`config.js` contains no `supabaseUrl`/`supabaseAnonKey`, so `createBackend()` selects
**demo mode** and all personal features run in localStorage **[O]**. That matters: the
public site today is a read-only map plus a private browser-local journal.

### A.3 Map technology

D3 v7 SVG — **not Leaflet, not Mapbox, not MapLibre** **[V]**:

- `d3.geoMercator()` projection, `d3.geoPath` with a custom `geoTransform` (line 1067–1069)
- fixed Berlin `BBOX` `[[13.0883,52.3383],[13.7612,52.6755]]` (line 1070)
- `d3.zoom().scaleExtent([1,14])` (line 1110)
- layer groups appended in paint order: districts, choropleth, green, water, streets,
  PLR outlines, labels, stations, place symbols (line 1065–1104)
- symbols by layer: circle = support, diamond = space, square = social (line 1102–1103)

This is a **vector choropleth map, not a tile map**. It has no basemap, no
third-party tiles, no API key, and no network dependency for geography. Consequences
**[R]**: adding event markers is a new `<g>` in an existing pattern — genuinely easy;
but there is no clustering library, no tile-level-of-detail, and every marker is DOM.
Rendering 303 venue symbols plus a plausible few hundred event markers is fine;
rendering tens of thousands is not.

### A.4 Existing functionality that matters for events

**[O]**, all read from the shipped file:

- `state.layers` toggles, `buildTypeChips()`, `buildSectorChips()`, `matches()`,
  `visible()`, `applyFilters()` — a working filter system keyed on `layer`/`cat`/
  `sectors`/`q`/`lowcost`.
- `selectPlace(i, fly)` → `renderPlace(i)` builds a detail panel with an `<dl class="facts">`
  block and a `Visit website ↗` button. **This is where "next event" belongs.**
- `selectDistrict(n)` and `selectPlr(id)` fly to a district or Planungsräum and open the
  stats tab. **Bezirksregion selection exists but only at Planungsräum granularity.**
- `kiezPop` — a floating dialog anchored to a clicked LOR polygon (line 2255).
  **This is the natural host for "hubs and event counts in this Bezirksregion".**
- `SCOPE` / `myIds()` / `scopeSet()` / `PLR_NEIGH` — user's Kiez, neighbouring areas,
  whole district, with an adjacency map already computed.
- `centroidOf(lor)` — polygon centroid helper, already used for labels.

**[V]** There is **no event or calendar concept in the UI today**. Grepping
`event|calendar|termin` outside the two data lines returns only: an `event_date` column
on the Supabase `updates` table, an admin form field "Event date (optional)", a `📅`
marker in `updHtml()`, and the label `"Exhibitions & events"` for the `culture` category.

That `updates` table is worth noticing: **the inherited schema already has a
place-scoped, date-bearing, URL-bearing content record with an admin publish path**
**[O]**. It is manually entered and not scraped, but it proves the venue↔dated-content
relationship was already anticipated. The event feature should be modelled as its
automated cousin, not bolted on beside it.

### A.5 Deployment and privacy surface

- Serving: nothing configured (see A.1).
- Third-party origins loaded at page view: Google Fonts, cdnjs (D3), jsDelivr
  (Supabase) — each named in the privacy notice as receiving the visitor IP **[V]**.
- Privacy notice is dual-mode and detailed (line 2048–2063), with `CONSENT_VERSION =
  "pilot-2026-11-v1"`, controller *Kai-Ti Wu Consulting*, contact `hello@kaitiwu.de`,
  Impressum at kaitiwu.de. **[O]** I did not audit it for GDPR sufficiency and did not
  touch it.
- `config.js` and `CONTRIBUTORS.md` define a contributor-credit workflow. **[O]**

**Any ingestion pipeline I add must not touch any of this.** The Atlas is a
participant-research instrument with a named controller; the event layer must remain a
read-only addition that never touches consent, check-ins, journal or location code.

### A.6 Licence and data rights — the hard finding

**[V]** There is **no licence file** in the fork or in upstream. The GitHub API
`license` field is `null` for both. No `LICENSE`, `COPYING` or `NOTICE` in either tree.
No licence header in `index.html` or `config.js`.

The only licence statement anywhere is one sentence in the rendered About text
(line 2029):

> "**Open:** code is open source, methods are published, aggregated results are
> released as open data (CC BY 4.0)."

That sentence is **aspirational, not operative**. It declares intent ("code is open
source") without naming a licence for the code, and it scopes CC BY 4.0 to *aggregated
results* — not to the venue directory, not to the geography, not to the source code.

Under most jurisdictions, absence of a licence means **all rights reserved by default**.
Forking on GitHub is permitted by the ToS, but that governs the platform copy, not a
right to redistribute derivatives elsewhere.

**[R] Do not treat the venue data as freely reusable.** Concretely:

1. **[Q2]** Ask Kai-Ti Wu for an explicit code licence and an explicit data licence
   for `PLACES`. Until then, keep all derived artefacts inside this fork.
2. The venue data has **third-party provenance that no fork licence could clear**:
   `src` fields point to berlin.de (104 places), stadtteilzentren.de (56),
   bbk-kulturwerk.de (25), kgberlin.net (18) **[V]**. Those are *references used to
   compile* the records; the underlying facts (names, addresses) are largely
   unprotected facts, but the curated selection, descriptions and compilation may not be.
3. **berlin.de robots.txt contains an explicit terms block** **[V]**: automated
   retrieval is allowed only if the client identifies itself in `User-Agent` **and**
   complies with the Robots Exclusion Protocol, and access "may be blocked at any
   time" at their discretion, and non-compliant access "shall be a misuse". This is a
   contractual-style condition attached to machine access, and it governs 112 of 303
   venues. It must be honoured literally, including a truthful, contactable UA.
4. The About text's "aggregated results … open data (CC BY 4.0)" is the *best* existing
   hook for publishing `events.json` / `venues.json` under CC BY 4.0 — but it needs the
   controller's explicit confirmation, since the controller is upstream, not you.

### A.7 Technical debt and constraints

**[O]** unless marked.

1. **4.6 MB single file, no build step.** Editing means editing a 3,193-line file with
   4.3 MB on two lines. Any tooling must treat lines 695–696 as opaque blobs.
   **[V]** GitHub diff/review on this file is effectively unusable.
2. **No tests, no CI, no linting, no README.** Nothing guards a regression.
   **[V]** (no such files exist)
3. **Data is inline, not fetched.** Line 695 is parsed before the app runs, so the
   whole 303-venue + 542-polygon dataset is always loaded. Adding events inline grows
   the blocking payload; adding them as `data/events.json` follows the existing
   `data/search.json` precedent and is fetched lazily **[V]** — strongly preferable.
4. **`window.ATLAS_SEARCH` is a derived artefact with no generator in the repo.**
   1.07 MB of precomputed search data whose build script is missing **[V]**. If we
   regenerate geography or venues, we cannot regenerate the search index. Treat line
   696 as frozen.
5. **7 venues have an `lor` that contradicts their own coordinates** and **1 falls
   outside every Planungsräum** **[V]** — see §B.3. The Atlas's own LOR join is
   therefore not fully self-consistent.
6. **`PLACES[].url` is not a reliable hub website.** 23 venues share
   `bbk-kulturwerk.de/en/art-spaces-berlin/studio-houses`; 6 share
   `berlin.de/kunst-und-kultur-pankow/einrichtungen/`; Holzmarkt 25's `url` is a
   visitberlin.de page **[V]**. The field is "where we read about this place", not
   "this place's own website". The source registry needs a separate, verified
   `official_website` — and where it cannot be verified, it must stay empty.
7. **429 observed.** `berlin.de/stadtbibliothek-mitte/` returned HTTP 429 during my
   probe **[V]**. Rate limiting on the largest host is real and already active.
8. **DNS failure**: `www.uferhallen.de` did not resolve from this sandbox **[V]**.
   Cannot distinguish sandbox DNS from a dead domain. Flagged, not concluded.

---

## B. Venue inventory

Full machine-readable inventory: **`artifacts/venue_inventory.json`** (303 records) and
**`artifacts/venue_inventory.csv`**. Every record carries the original `src` reference
and both the Atlas's own `lor` and my independently computed point-in-polygon result,
so the two can be audited against each other.

### B.1 Is the venue data structured or must it be extracted?

**It is already structured.** `window.ATLAS.PLACES` is a clean JSON array of 303
objects with **17 fields present on all 303 records** **[V]**:

```
id, layer, name, cat, sectors, desc, address, plz, url, flag, src, d, lor, c, prec, dg, dw
```

| field | meaning |
|---|---|
| `id` | URL-slug identifier — stable, already suitable as `venue_id` |
| `layer` | `support` \| `space` \| `social` |
| `cat` | 15-value category (see B.2) |
| `sectors` | CCI sector tags |
| `desc` | curated 1–2 sentence German description |
| `address`, `plz` | street address and postal code |
| `url` | website — **see caveat A.7.6** |
| `flag` | tri-state: `true` 266 / `null` 28 / `false` 9 — means "free/subsidised" for support, "public" for social **[O]** |
| `src` | the page the record was compiled from — **provenance, preserve it** |
| `d` | district (Bezirk) |
| `lor` | 8-digit LOR Planungsräum id |
| `c` | `[lon, lat]` |
| `prec` | `street` (302) or `postal` (1) |
| `dg`, `dw` | metres to nearest green / water |

**No extraction from the DOM was necessary and no re-entry was performed.** I parsed
line 695 with a brace-matching JSON extractor and re-emitted it. **[V]** All 303
records validate against `artifacts/venue.schema.json` (303 valid, 0 invalid) **[V]**.

### B.2 Coverage statistics

**[V]**

| dimension | value |
|---|---|
| total venues | 303 |
| layers | social 225 · space 44 · support 34 |
| categories | community 81 · library 66 · culture 42 · studios 23 · network 14 · advice 12 · vhs 12 · musicschool 12 · artschool 12 · funding 7 · makerspace 7 · rehearsal 6 · **hub 6** · coworking 2 · incubator 1 |
| **`cat: "hub"`** | **6** |
| coordinate precision | street 302 · postal 1 |
| distinct website domains | 125 |
| top domains | berlin.de 112 · kgberlin.net 28 · bbk-kulturwerk.de 23 |
| Bezirksregionen with ≥1 venue | **112 of 143** (31 empty) |
| LOR assignment agreeing with point-in-polygon | **295 of 303** |

Densest Bezirksregionen: Alexanderplatz 12, Wedding Zentrum 11, Tempelhofer Vorstadt 8,
Nördliche Luisenstadt 8, Spandau Mitte 7, Otto-Suhr-Allee/Kantstraße 6, Moabit West 6,
Pankow Zentrum 6.

### B.3 The "hub" problem — the central definitional gap

The brief says: *"Start with the hubs and venues already represented in the CCI Atlas."*
Those two nouns are not the same set here.

**[V]** Only **6** records carry `cat: "hub"`, and they are the canonical creative
hubs:

| venue | address | website field points to | LOR (BZR) |
|---|---|---|---|
| ZK/U – Zentrum für Kunst und Urbanistik | Siemensstraße 27, 10551 | zku-berlin.org ✔ own site | 01200519 |
| Haus Schwarzenberg | Rosenthaler Str. 39, 10178 | bbk-kulturwerk.de ✘ portal | 01100309 |
| Haus der Statistik – Haus der Materialisierung | Otto-Braun-Str. 72, 10178 | hausderstatistik.org ✔ own site | 01100310 |
| Holzmarkt 25 | Holzmarktstraße 25, 10243 | visitberlin.de ✘ tourism portal | 02400623 |
| Funkhaus Berlin | Nalepastraße 18, 12459 | berlin.de venue page ✘ directory | 09200510 |
| Malzfabrik | Bessemerstraße 2-14, 12103 | erih.net ✘ directory | 07400822 |

**Only 2 of 6 have their own website in the `url` field.** **[V]**

A plausible event-bearing candidate pool is larger — `space` (44) plus `community` (81)
plus `culture` (42) = 167 — but that is a *different product* from "CCI hubs", and it
swallows 66 libraries and 12 VHS centres, which are arguably the best event publishers
in the city and arguably not "CCI hubs" at all.

**[Q1] — this needs your decision before Phase 1 can close.** Options:

- **(a) Strict**: the 6 `cat:"hub"` venues. Clean, honest, tiny. Coverage would be
  poor and geographically lopsided (4 of 6 are in Mitte/F'hain/Schöneberg).
- **(b) Layer-based**: all 44 `layer:"space"` venues (studios, hubs, rehearsal,
  makerspaces, coworking). Coherent concept — "places where cultural work happens" —
  and closest to the CCI Atlas's own framing.
- **(c) Function-based**: venues that actually publish events, discovered empirically
  (my §C suggests this is where the real coverage is, and it is *not* correlated with
  `cat`).
- **(d) Two-tier**: keep a `hub` flag for the 6, and let the map show all venues that
  have qualifying events. My recommendation **[R]**: (d), because it preserves the
  inherited taxonomy instead of overloading it, and because coverage should be an
  *output* of source discovery, not an input.

### B.4 Geography verification

I did not guess assignments from names or postal codes. I ran Shapely point-in-polygon
against the shipped polygons **[V]**:

- 542/542 Planungsräume and 143/143 Bezirksregionen geometries are `is_valid`
- PLR ids are 8-digit; the first 6 digits are always a real BZR id — **0 exceptions**
- geometry types: BZR 141 Polygon + 2 MultiPolygon; PLR 540 + 2
- **BZR names are not unique**: `Heerstraße` is both `042002` (Charlottenburg-Wilmersdorf)
  and `052005` (Spandau). `Schloßstraße` is duplicated among Planungsräume.
  → **Key everything on `lor_id`; never join on `lor_name`.** **[V]**

**Discrepancies found (7 mismatch + 1 outside):**

| venue | Atlas `lor` | point-in-polygon says |
|---|---|---|
| bbk berlin – Berufsverband Bildender Künstler\*innen | 02100101 | 01100102 Großer Tiergarten |
| Kunst in den Gerichtshöfen | 01300836 | 01401043 Antonstraße |
| Medienwerkstatt im kulturwerk des bbk berlin | 02300314 | 02300315 Lausitzer Platz |
| Musikschule Friedrichshain-Kreuzberg | 02300314 | 02300315 Lausitzer Platz |
| Stadtteilzentrum Quäkerkiez | 12200308 | 12200309 Scharnweberstraße |
| Haus am Kleistpark | 07200409 | 07100204 Barbarossaplatz |
| Galerie im Saalbau | 08100314 | 08100206 Flughafenstraße |
| Egon-Erwin-Kisch-Bibliothek (13.48447, 52.51273) | 11300724 | **inside no Planungsräum** |

**[A]** These are mostly boundary-adjacency effects: `prec:"street"` places a pin on a
street segment, and several of these venues sit on streets that form a Bezirksregion
border. The Atlas may have assigned by address/lookup while the pin sits metres off.
The last one is outside the geography entirely and needs its coordinates checked.

**[R] Do not silently overwrite the Atlas's `lor`.** Emit both fields (as the inventory
does: `atlas_lor_plr` and `pip_lor_plr`), keep the Atlas value as the display value,
route the 8 disagreements to the review queue, and let a human decide per venue. The
Atlas's values were curated with address knowledge that a coordinate does not have.

### B.5 What is missing or uncertain

- **No venue has a verified `official_website` distinct from `src`.** 112/303 point at
  berlin.de and 23 share one bbk-kulturwerk portal page **[V]**. Verifying 303 websites
  is a real manual task and has not been done. The inventory leaves the field as-is
  rather than inventing anything.
- **31 Bezirksregionen have zero venues** — mostly outer-city (airport periphery,
  industrial Treptow/Köpenick, Grunewald). Not an error, but it bounds coverage claims:
  a "Kiez Events Atlas" will show empty districts, and the UI must say so honestly.
- **`flag` semantics differ by layer** and are not documented in the data. **[Q3]**
- **1 venue has postal-centroid coordinates** (not street), so its pin is up to
  ~kilometres off. It is marked `data_quality: "missing"` in the inventory.

---

## C. Website source feasibility report

12 sources registered; **all 12 were actually fetched on 2026-11-13**. Registry:
`artifacts/sources.json`. Sample records: `artifacts/sample_events.json`.

I deliberately sampled across *different publishing technologies*, not just different
hubs, because the parser cost is a function of technology, not of venue.

### C.1 Feasibility table

| # | hub | tech | best channel | dates | times | price | recurring | stable URL | HTTP enough | robots | verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Stadtteilzentrum Friedrichsfelde | WordPress + The Events Calendar 6.17.2 | **REST `/wp-json/tribe/events/v1/events`** | ✔ | ✔ | ✘ empty | ✔ | ✔ | ✔ | clean | **verified** |
| 2 | — same hub, alt channel | — | **ICS `/events/?ical=1`** | ✔ | ✔ | ✘ | ✔ | ✔ | ✔ | clean | **verified** |
| 3 | Nachbarschaftszentrum Divan | WP + Simple Calendar 3.5.9 (Google Cal) | **schema.org microdata** | ✔ | ✔ | ✘ | ✔ class flag | ✘ | ✔ | clean | **verified** |
| 4 | Mehrgenerationenhaus Wassertor | WP + Modern Events Calendar | **JSON-LD** (27 events) | ✔ | ✘ date-only | ⚠ **wrong** | ✔ | ✔ | ✔ | no rules | **verified w/ trap** |
| 5 | Kommunale Galerien Berlin (28 venues) | WP + ACF + Polylang | **REST `/wp-json/wp/v2/event`** | ✔ | ✔ | ✘ | partial | ✔ | ✔ | clean | **verified** |
| 6 | berlin.de Landeskalender (112 venues) | berlin.de CMS | **RSS per calendar id** | ✔ in title/guid | ✔ in title | ✘ prose | ✘ | ✔ | ✔ | **strict T&Cs** | **good** |
| 7 | Haus der Statistik | WP, CPT not REST-exposed | HTML listing + detail | ⚠ og:description | ⚠ prose | ✘ | ✔ | ✔ | ✔ | open | good |
| 8 | ZK/U | TYPO3 | HTML `article.event-item` | ⚠ **no year** | ⚠ prose | ✘ | ✔ prose | ✔ | ✔ | open | good |
| 9 | ORWOhaus | WP + Events Manager | HTML `#em-wrapper` links | ✘ in listing | ✘ | ✘ | ✔ | ✔ | ✔ | partial | good |
| 10 | SprengelHaus Wedding | WP + Events Manager 7.4.8 | HTML `.em-item` (178) | ✔ `data-date` | ✔ | ⚠ prose | ✔ | ⚠ | ✔ | clean | **verified, incomplete** |
| 11 | Theaterhaus Berlin | WP, `event`+`venue` CPTs | **REST exists but robots-disallowed** | — | — | — | — | — | — | **`Disallow: /wp-json/`** | **candidate — do not use API** |
| 12 | Uferstudios | headless-ish, client-rendered | **Playwright required** | ✘ static | ✘ | ✘ | ? | ✔ | ✘ | `Allow: /` | candidate |
| 13 | Kotti e.V. | WP + All-in-One Event Calendar | HTML, non-schema markup | ⚠ `dd/mm/yyyy` | ⚠ | ✘ | ? | ✔ | ✔ | 33 rules | candidate |

Negative results, equally important **[V]**:

- **bbk-kulturwerk.de** — the page shared by 23 venues exposes no events at all.
  Those 23 venues have **no resolvable event source** via the Atlas `url` field.
- **visitberlin.de** — city-wide tourism calendar, not venue-scoped. Wrong granularity.
- **interkulturanstalten.de** — `/events/` is titled "Archiv:Events", latest date
  27.05.2021. **Stale source; must be excluded, not adapted.**
- **kiekin.org** — the Atlas URL is now **HTTP 404**. Dead link in the directory.
- **berlin.de `/vhs/kurse/index.php/rss`** — looks like a course feed; it is a
  *category* feed ("Fremdsprachen", "Deutsch und Integration"). **A feed that exists is
  not a feed of events.**
- **uferhallen.de** — DNS did not resolve from the sandbox. Unresolved, not failed.

### C.2 Machine-readability statistics

Of the 12 registered sources **[V]**:

| channel class | sources | share |
|---|---|---|
| Structured API / feed (REST, ICS, RSS, JSON-LD, microdata) | **5** | 42% |
| Server-rendered HTML requiring a per-site selector | **6** | 50% |
| Browser automation genuinely required | **1** | 8% |

Extrapolating to the directory is **not** sound, because the 112 berlin.de venues all
route through *one* RSS mechanism and the 28 kgberlin venues through *one* REST
endpoint. The honest statement is: **~42% of distinct publishing mechanisms found so
far are machine-readable, and those mechanisms cover a disproportionate share of
venues** — kgberlin's single endpoint serves 28 venues and berlin.de's single RSS
pattern potentially serves 112. **[A]**, needs the full crawl to confirm.

### C.3 Sample extracted events (real, with evidence and honest gaps)

All from `artifacts/sample_events.json`, all fetched 2026-11-13.

**1 — The Events Calendar REST + ICS (best case).**
```
title  Neue Dinge aus altem Material: Upcycling-Workshop im Stadtteilzentrum
start  2026-11-17T15:30:00+01:00   end 2026-11-17T17:30:00+01:00   Europe/Berlin
url    .../event/neue-dinge-aus-altem-material-upcycling-workshop-im-stadtteilzentrum-8/
evidence  REST event id 3138; ICS UID 3138-1794929400-1794936600@stadtteilzentrum-friedrichsfelde.de
missing   price  (cost field = "" though cost_details.currency_symbol = "€")
```
REST and ICS return the same three events with identical ids — **two independent
channels cross-validating each other.** This is the reference implementation.

**2 — Simple Calendar microdata.**
```
title  Melee e.V. Videospiel-Turnier
start  2026-11-01T12:00:00+01:00   end 2026-11-01T22:00:00+01:00
evidence  li.simcal-event[itemtype=schema.org/Event] → itemprop=startDate content attr
missing   original_event_url  (Simple Calendar renders no per-event permalink)
          price
note      class "simcal-event-recurring" + "Jeden ersten Sonntag" in description
```
225 events on one page, ISO-8601 with offset in `content` attributes. **But no
per-event URL**, which breaks the brief's "stable original URL" requirement — the
event's identity can only be venue+date+title.

**3 — Modern Events Calendar JSON-LD (the price trap).**
```
title  Malkurs
start  2026-11-16  (date only — no time in JSON-LD)
url    https://mgh-wassertor.de/events/malkurs/
price  JSON-LD says: offers.price = "" , offers.priceCurrency = "$"
       description says: "Kostenlos und ohne Anmeldung"
```
**Every event on this site reports `priceCurrency: "$"`.** It is also the only source
in the sample that emits `eventStatus` — always `EventScheduled` **[V]**. A naive `offers.price <= 20`
filter would either reject everything or, worse, treat USD numbers as EUR. The real
price signal is prose inside `description`. This single site justifies the brief's
insistence on explicit `price_status` over a bare number.

**4 — kgberlin REST + ACF (one source, 28 venues).**
```
title  Finissage with guided tour and concert
start  2026-10-11 18:00   (acf.start_date="20261011", acf.time="18:00")
url    https://kgberlin.net/en/events/finissage-with-guided-tour-and-concert/
evidence  WP post id 4831; acf.galleries=[1473]; acf.custom{lng,lat}
missing   end time, price
dedup     German twin post id 4827 (/events/finissage-2/, galleries [1470]) is the SAME event
```
`acf.galleries[]` is the venue join key into the 28 Atlas venues. Polylang emits a
`translations` map — **de/en pairs must be collapsed or every gallery event double-counts.**

**5 — berlin.de RSS.**
```
title  Book a librarian (13.11.2026 10:00 - 15:00 Uhr)
start  2026-11-13T10:00:00+01:00   end 2026-11-13T15:00:00+01:00
url    https://www.berlin.de/land/kalender/index.php?detail=279628&ls=0&c=409&...
evidence  guid "baevents:event:279628:2026-11-13:10-00-00"
price  free — from description text "kostenloses Beratungsangebot"
```
100 items per feed. **Dates live in the title string and the guid, not in `<pubDate>`
semantics.** The guid `baevents:event:<id>:<date>:<time>` is the stable key. Detail
pages carry **no JSON-LD** (verified), so the feed is the only structured surface.
Discovered via an `index.php?rss&c=409` link inside the HTML — the calendar id `c` must
be discovered per venue.

**6 — ZK/U HTML (must go to review, not publish).**
```
title  Berlin Bike Market 2026
date   .event-item__date = "SO 01.03."  → DAY AND MONTH ONLY, NO YEAR
       p.date = "Sundays from March to November / 10:00 – 15:00"
missing  year, concrete start_datetime, price
```
Cannot produce a valid `start_datetime` without an assumption. **Exactly the case the
brief says must be flagged, not guessed.**

**7 — SprengelHaus (parser not finished — reported as such).**
```
dates/times/location extract cleanly: data-date="2026-10-26", "10:00 - 11:30",
                                     "Nachbarschaftsladen"   (178 items)
title  → null. My .em-item-title selector did not match this theme's markup.
price  → only prose; one item says "Kostenbeitrag: 2,50€" (a contribution, not admission)
```
I am reporting this as **incomplete**, not as a success. 178 items found, titles not yet
extracted.

### C.4 The price finding, stated plainly

**[V] 0 of 7 sample events had a trustworthy structured price field.**

| source | structured price | reality |
|---|---|---|
| The Events Calendar | `cost: ""`, `currency_symbol: "€"` | absent |
| Modern Events Calendar | `price: ""`, `priceCurrency: "$"` | **wrong currency, empty value** |
| kgberlin ACF | no field | absent |
| Simple Calendar | none | absent |
| Events Manager | none | prose "Kostenbeitrag: 2,50€" |
| berlin.de RSS | none | prose "kostenloses Beratungsangebot" |
| MGH Wassertor | `"$"` | prose "€2 (Selbstkostenpreis)" |

Consequences **[R]**:

1. A **€20 cap cannot gate publication today.** It can only *demote*: an event whose
   price is *known* and *above* €20 is excluded; everything else is `unknown`.
2. `price_status: "unknown"` must be **visually distinct** from `free` in the UI, and
   unknown-price events must sit in a review queue rather than being published as free.
3. **Never parse `offers.priceCurrency` as authoritative.** Whitelist `EUR` and discard
   anything else, including `$`.
4. Prose price extraction (`€N`, `N €`, `kostenlos`, `Eintritt frei`, `Spende`,
   `Kostenbeitrag`, `Einlass …`) is feasible and I have working regexes, but German
   pricing prose is genuinely ambiguous ("spendenbasiert", "Solidarpreis", "Eintritt
   frei, Spenden erbeten"). Treat it as **candidate evidence for a human**, never as a
   publishable number.

### C.5 Crawl policy audit

**[V]**, robots.txt read for all 12 sources:

- **Clean / open**: kgberlin.net, stadtteilzentrum-friedrichsfelde, sprengelhaus-wedding,
  mgh-wassertor (no rules at all), nachbarschaftszentrum-divan, nachbarschaftshaus,
  zku-berlin, hausderstatistik, uferstudios (`Allow: /`).
- **Partial**: orwohaus and kotti-berlin disallow only `/calendar/action~*` URL variants
  (infinite-calendar permutations) — the normal listing pages are allowed.
- **`theaterhaus-berlin.com` — `Disallow: /wp-json/` and `Disallow: /?rest_route=`.**
  The REST API *works* (returns 200 with `event` and `venue` post types) and **must not
  be used**. HTML only. This is the compliance case that a "does it work?" test would
  have silently passed.
- **`berlin.de` — explicit terms.** Machine access permitted only with a self-identifying
  `User-Agent` **and** full REP compliance; blocking at their discretion; non-compliant
  access characterised as misuse. 112 venues depend on this staying good.
  **[V]** I already received **HTTP 429** from one berlin.de path.
- **kotti-berlin**: 33 rules, all calendar-permutation variants.

**[R]** Crawler obligations that follow: a permanent, truthful, contactable UA string;
per-host serialisation (never parallel to one host); conditional requests
(`If-None-Match` / `If-Modified-Since`); exponential backoff, and on `429`/`503` a
multiplicative interval increase; respect for any `Crawl-delay` (none seen yet); and a
hard rule that **a disallowed path is never fetched "just to check"**.

---

## D. Proposed technical design

### D.1 Shape of the system

**[R]** Keep the inherited frontend. Add a Python ingestion package beside it. Join
them through static JSON that the existing lazy-`fetch()` pattern already anticipates.

```
┌── collection ────────────────────────────────────────────────┐
│  fetcher.py      httpx, per-host serialisation, ETag cache,  │
│                  backoff, robots gate, truthful UA           │
│  robots.py       parse + enforce; deny wins over "it works" │
├── parse (one adapter per mechanism, not per venue) ──────────┤
│  tec_rest.py     tec_ics.py      wp_acf.py     mec_jsonld.py │
│  microdata.py    rss_berlin.py   em_html.py    html_listing  │
│  playwright.py   ← one adapter, gated, last resort           │
├── normalise ─────────────────────────────────────────────────┤
│  normalise.py    tz→Europe/Berlin, id hashing, dedup,        │
│                  series vs occurrence, price_status, review  │
│  geo.py          Shapely PiP → lor_id (verified, cached)     │
├── publish ───────────────────────────────────────────────────┤
│  publish.py      data/public/*.json   (curated only)         │
│                  data/internal/*.json (never deployed)       │
└──────────────────────────────────────────────────────────────┘
```

**Adapters per mechanism, not per venue.** The evidence supports this: one `tec_rest`
adapter serves every The Events Calendar hub; one `rss_berlin` adapter potentially
serves 112 venues. A per-venue design would be unmaintainable at 303 venues.

### D.2 Repository layout

**[R]** Additive only; nothing inherited is moved or deleted.

```
index.html              (unchanged except a small additive patch — see D.5)
config.js               (unchanged)
CONTRIBUTORS.md         (unchanged)
data/
  public/               venues.json events.json neighbourhoods.geojson metadata.json
  internal/             sources.json source_runs.json review_queue.json   ← gitignored
                        from the Pages deploy, see D.6
pipelines/
  pyproject.toml  README.md
  src/kiez_atlas/   __init__.py cli.py robots.py http.py geo.py
                    normalise.py dedup.py price.py publish.py validate.py
    adapters/       tec_rest.py tec_ics.py wp_acf.py mec_jsonld.py
                    microdata.py rss_berlin.py em_html.py html_listing.py
                    playwright_render.py
  tests/            fixtures/*.har or *.json + one test per adapter
docs/feasibility/     (this study)
.github/workflows/    ingest.yml   deploy.yml     ← Phase 5 only, not now
```

### D.3 Source registry

Implemented as `artifacts/sources.json` (12 entries). Shape, with the fields I found
actually necessary during fieldwork **[R]**:

```jsonc
{
  "source_id": "src-005",
  "venue_id": "kgberlin",              // or "venue_ids": [...] for a portal
  "venue_ids": ["galerie-wedding-…", "…"],   // ← ADDED: one source can serve many venues
  "venue_name": "Kommunale Galerien Berlin",
  "website": "https://kgberlin.net",
  "event_listing_url": "https://kgberlin.net/programm/",
  "source_type": "gallery_network",
  "discovered_endpoints": [
    { "type": "wp_rest_acf", "url": "…/wp-json/wp/v2/event", "status": "tested_ok" }
  ],
  "parser_type": "wp_rest_acf",
  "fetch_interval_hours": 24,
  "crawl_policy": {
    "robots_checked": true,            // ← ADDED: mandatory, and deny beats "it works"
    "robots_disallow": [],
    "terms_reviewed": false,
    "rate_limit_notes": "berlin.de only with self-identifying UA + REP compliance"
  },
  "venue_join": { "field": "acf.galleries", "kind": "wp_term_id" },  // ← ADDED
  "dedup": { "locale_pairs": true, "via": "translations" },          // ← ADDED
  "source_quality": "verified",
  "last_successful_fetch": "2026-11-13",
  "last_http_status": 200,
  "consecutive_failures": 0,
  "scraper_integration_status": "not_integrated",
  "discovery_evidence": "GET /wp-json/wp/v2/event → 200, acf.start_date YYYYMMDD …",
  "notes": "No price field. de/en duplicates."
}
```

Fields I added beyond the brief's illustrative schema, each because fieldwork forced it:
`venue_ids` (portals), `venue_join` (how events map to venues), `dedup` (bilingual
duplicates), `robots_disallow`, `consecutive_failures`, `last_http_status`, and
`discovery_evidence` (so a claim can be checked months later).

`source_quality` is deliberately a closed set: `candidate` → `good` → `verified`, and
**only `verified` may promote to the central scraper.**

### D.4 Canonical event schema

Implemented and validating in `artifacts/event.schema.json`. Public record; `additionalProperties: false`
so internal metadata *cannot* leak into public output by accident **[R]**.

Key decisions:

- **`event_id`** = hash of `(venue_id, original_event_url || normalised title, occurrence
  date)`. Never array position. When `original_event_url` is missing (Simple Calendar),
  the fallback key is weaker and the record carries that weakness in `extraction_evidence`.
- **`series_id` + separate occurrence rows.** Two dates sharing a title are two records.
  This directly implements the brief's "do not collapse two distinct event dates".
- **`price_status`** ∈ `free|donation|fixed|range|unknown`, with `price_amount` /
  `price_amount_max` nullable. `unknown` ≠ free, enforced by the review gate, not by prose.
- **`extraction_evidence`** is a short human-checkable pointer (`"REST event id 3138"`,
  `"itemprop=startDate content attr"`). Cheap to store, and it is what makes an audit
  possible later without re-running the parser.
- **`event_status`** includes `unknown` as a first-class value. Only **one** of 12
  sources exposed any status field at all: `mgh-wassertor` (Modern Events Calendar)
  emits `eventStatus` in JSON-LD — but **every one of its 27 events carried
  `https://schema.org/EventScheduled`** **[V]**, so the capability exists and its
  *cancelled* branch is unproven. The other 11 sources exposed nothing. Treating an
  absent status as "scheduled" would be a lie, so absence maps to `unknown`.
- Internal-only fields (`confidence`, `review_status`, `raw_snapshot_ref`) live in
  `data/internal/review_queue.json` and are **not in the public schema at all**.

### D.5 Map adaptation

**[R]** Three layers, matching the brief, on the existing D3 stack:

1. **Bezirksregion boundaries** — `LOR_BZR` is already loaded and already drawn as
   `path.plz.bzr` (line 1091). Currently decorative (`pointer-events: none`). Making it
   selectable is a small additive change.
2. **Hub markers** — existing `ptSel` symbol layer. Add a count badge; the codebase
   already computes per-layer counts (line 1263–1265).
3. **Events** — a new `<g>` appended after `ptSel`, joined on
   `events_by_venue.get(venue_id)`.

Integration surface, all existing and additive:

| need | existing hook | change |
|---|---|---|
| load events | `loadSearch()` pattern (line 3017) | `loadEvents()` → `fetch("data/events.json")`, same try/catch fallback |
| hub click | `renderPlace()` `<dl class="facts">` | insert "Next event" + `<details>` list before "Visit website" |
| Bezirksregion click | `kiezPop` dialog (line 2255) | add hub list + event counts |
| filters | `state` + `buildTypeChips()` | price + date + category chips, same chip CSS |
| LOR key | `PLR.get(id).bzr` | index events by `lor_id`; **join on id, never name** (§B.4) |

**Fallback behaviour is the important part.** `loadSearch()` already degrades to
`{stops:[],streets:[]}` when `data/search.json` is absent **[V]**. `loadEvents()` must
do the same: **if the event feed is missing, stale or malformed, the Atlas renders
exactly as it does today.** That single property makes the whole feature reversible and
is what allows Phase 4 to ship without risk to the inherited product.

**Accessibility discipline [R]**: only render accessibility info when a source states it.
Missing ≠ inaccessible. No tested source exposed accessibility data, so **v1 renders
none at all** rather than rendering a misleading negative.

### D.6 Publication split

**[R]** `data/public/` is the only thing reachable by the deployed site.
`data/internal/` holds the registry, run telemetry and review queue and must be
**excluded from the Pages deploy path** — enforced by the deploy step copying an
explicit allowlist, not by a denylist. A denylist fails the first time someone adds a
file.

`metadata.json` carries `schema_version`, `generated_at`, per-source `last_successful_fetch`
and `source_freshness`, and counts — so the frontend can render an honest
"data updated …, N sources stale" line instead of implying liveness it does not have.

### D.7 GitHub Actions

**[R]** Phase 5 only. Two workflows, deliberately separated:

- `ingest.yml` — `schedule:` cron + `workflow_dispatch`. Per-host serialisation makes
  the whole crawl latency-bound, so shard by host across a small matrix rather than
  raising concurrency per host. Cache ETags in the Actions cache keyed on host+path.
  Commit **only** `data/public/`. On failure: keep the previous data (never publish a
  partial), write telemetry, alert on N consecutive failures.
- `deploy.yml` — Pages deploy of `data/public/` + `index.html`, unchanged from upstream
  Pages settings.

**[A]** Free-tier Actions on a public repo is unlimited minutes, so a daily crawl of
~12–20 hosts fits comfortably. Runtime is dominated by polite per-host waits, not CPU.
Playwright in Actions is supported but heavy; gate it behind an opt-in flag per source
so one browser source cannot dominate the run.

### D.8 What I deliberately did not propose

No PostgreSQL/PostGIS, no Redis, no vector store, no LLM classification, no backend, no
auth, no personal data. **[R]** Shapely point-in-polygon over 542 polygons with an
`STRtree` completed in **0.3 s** for all 303 venues **[V]** — spatial queries are not a
reason for a database. Static JSON plus SQLite-for-history is sufficient until proven
otherwise.

**On LLM classification specifically**: the brief's "public participatory workshop is
not automatically formal training" distinction is real and hard. But an LLM classifier
would make publication decisions that cannot be defended to a venue owner who asks why
their Repair Café was hidden. **[R]** Use deterministic rules + a human review queue for
anything ambiguous; keep an LLM out of the publication path.

---

## E. Implementation roadmap

Six phases. Each ends with a checkable acceptance criterion, not a vibe.

### Phase 1 — Foundation

| | |
|---|---|
| **Goal** | Canonical venue data + verified geography + schemas + registry skeleton |
| **Files** | `data/public/venues.json`, `data/public/neighbourhoods.geojson`, `data/public/metadata.json`, `pipelines/src/kiez_atlas/geo.py`, `pipelines/src/kiez_atlas/publish.py`, `pipelines/tests/test_geo.py` |
| **Dependencies** | none — everything needed is already in `index.html` line 695 |
| **Risks** | (a) silent divergence from the Atlas's own `lor` values; (b) 31 empty Bezirksregionen read as bugs; (c) touching line 695/696 destroys the un-regenerable search index |
| **Tests** | 303 venues validate against `venue.schema.json`; PiP reproduces the 295/303 agreement I measured; `Heerstraße` resolves to two distinct `lor_id`s; every `lor_id` exists in `neighbourhoods.geojson` |
| **Acceptance** | `venues.json` reproduces all 303 records with `atlas_provenance.source_reference` intact; `neighbourhoods.geojson` has 143 features with unique ids; **zero** edits to `index.html` |

Already partly done: the inventory and both schemas exist on this branch and validate.

### Phase 2 — Source discovery

| | |
|---|---|
| **Goal** | Automated discovery of event endpoints across the directory, plus the 8 remaining adapters |
| **Files** | `pipelines/src/kiez_atlas/robots.py`, `http.py`, `discover.py`, `adapters/*.py`, `data/internal/sources.json` |
| **Dependencies** | Phase 1 registry shape |
| **Risks** | (a) **robots violations** — the theaterhaus case proves a working API can be forbidden; (b) hammering berlin.de (already returning 429); (c) mistaking a category feed for an event feed (the VHS RSS trap); (d) discovery scope creep into 125 domains |
| **Tests** | robots gate unit-tested with the real theaterhaus robots.txt as a fixture and asserting **deny**; per-host serialisation asserted; a 429 fixture triggers backoff not retry-storm; the VHS RSS is asserted *not* to yield events |
| **Acceptance** | every one of the 303 venues has a registry entry with `source_quality` ∈ `candidate|good|verified|none`; **no venue is marked `verified` without a recorded `discovery_evidence` string**; a full run makes ≤1 request/second/host |

### Phase 3 — Event ingestion

| | |
|---|---|
| **Goal** | Collection → normalisation → eligibility → dedup → review queue |
| **Files** | `normalise.py`, `price.py`, `dedup.py`, `validate.py`, `data/internal/review_queue.json`, `data/public/events.json` |
| **Dependencies** | Phase 2 adapters |
| **Risks** | (a) **price inference** — the `$`-currency trap and German prose ambiguity; (b) bilingual double-counting at kgberlin; (c) recurring-series explosion (Divan's 225 rows); (d) cancellation signal exists on only 1 of 12 sources and only in its `scheduled` state; (e) ZK/U's year-less dates |
| **Tests** | `price_status` never `free` from an absent field; `priceCurrency != "EUR"` discarded; kgberlin de/en pair collapses to one `event_id`; two dates with one title stay two records; year-less date → `review_queue`, not `events.json`; every published event has a resolvable `original_event_url` **or** an explicit `extraction_evidence` noting its absence |
| **Acceptance** | all 7 sample events in `artifacts/sample_events.json` reproduce, **including their documented gaps**; `events.json` validates against `event.schema.json`; review queue is non-empty and every ambiguous record is in it |

### Phase 4 — Map integration

| | |
|---|---|
| **Goal** | Events visible by hub and Bezirksregion, with filters, without regressing the Atlas |
| **Files** | `index.html` (additive patch only), `data/public/events.json` |
| **Dependencies** | Phase 3 output |
| **Risks** | (a) the 4.6 MB file resists review — mitigate by keeping the patch small and isolated; (b) payload growth; (c) confusing "no events" with "no data"; (d) breaking the existing filter/scope logic |
| **Tests** | manual: with `data/events.json` absent the Atlas is pixel-identical to today; with it present, hub click shows next event; Bezirksregion click shows counts; price filter never labels `unknown` as `free`; existing layer/type/sector filters still work |
| **Acceptance** | **the Atlas renders and behaves identically when the event feed is missing**; no change to privacy notice, consent, check-in, journal or location code; no new third-party origin |

### Phase 5 — Automation

| | |
|---|---|
| **Goal** | Scheduled refresh, freshness monitoring, failure handling, data-quality report |
| **Files** | `.github/workflows/ingest.yml`, `deploy.yml`, `data/internal/source_runs.json`, `data/public/metadata.json` |
| **Dependencies** | Phase 4 |
| **Risks** | (a) publishing a partial crawl; (b) silent staleness; (c) a source dying quietly (interkulturanstalten is already 5 years stale); (d) Actions minutes |
| **Tests** | simulated source failure leaves previous `events.json` intact; 3 consecutive failures mark source `stale` and surface in `metadata.json`; freshness thresholds (fresh <2× interval, aging <4×, stale beyond) unit-tested |
| **Acceptance** | a scheduled run publishes only on success; `metadata.json` states real freshness; the UI shows an honest "last updated" line |

### Phase 6 — Central scraper integration

| | |
|---|---|
| **Goal** | Export qualified sources to `JsonLord/event-scraper-github-actions` |
| **Files** | `pipelines/src/kiez_atlas/export.py`, `data/internal/scraper_export.json` |
| **Dependencies** | Phases 2–3; **and a decision from you** |
| **Risks** | (a) **the €15 vs €20 policy collision**; (b) duplicate crawling; (c) exporting `candidate` sources and polluting the central matrix |
| **Tests** | export contains only `source_quality: "verified"`; the €20 Atlas cap is not written into any central config; export is a pure artefact (no writes to the other repo) |
| **Acceptance** | export file produced and reviewed by you; **no commit to the central repo in this assignment** |

**[V] On the €15/€20 collision** — I confirmed the central scraper's cap is real and
guarded: `tests/test_community.py:177` asserts `COMMUNITY_MAX_PRICE == 15.0`, and
`scripts/event_utils.py` defines `DEFAULT_MAX_PRICE` **[V]**. These are two separate
publication policies for two separate products, and the Atlas must not touch that
constant. **[Q4]** Which policy wins for a source that feeds both?

---

## F. Go / no-go recommendation

### F.1 Is the inherited map suitable for adaptation?

**Yes, with one caveat.** **[V]** It is D3 + SVG with no basemap, no API key, no tile
dependency, and it already contains the LOR geography, the venue layer, a working filter
system, a district/PLR selection model, an adjacency map, and a lazy-`fetch()` pattern
with graceful fallback. The brief's three map layers map cleanly onto existing code
paths. The caveat is the 4.6 MB single file: adaptation is easy, *review* is hard, and
the un-regenerable search index on line 696 is a landmine. **[R]** Keep the frontend
patch small, additive, and behind a fallback.

### F.2 How complete and usable is the hub directory?

**Complete as a CCI directory; incomplete as a hub directory.** **[V]** 303 venues, 17
fields on all of them, 295/303 LOR-consistent, 112/143 Bezirksregionen covered. But only
**6** are `cat:"hub"`, only **2 of those 6** have their own website in the `url` field,
and 23 venues share a single bbk-kulturwerk page that publishes no events. The directory
is a strong *seed*, not a ready hub list. **[Q1]** is the gate.

### F.3 How many tested hubs expose machine-readable events?

**5 of 12 sources (42%)** expose a structured channel — REST, ICS, RSS, JSON-LD or
schema.org microdata — and all five were fetched successfully with real events
extracted **[V]**. Those five mechanisms cover a disproportionate share of venues: one
kgberlin endpoint serves 28 venues, and the berlin.de RSS pattern potentially serves 112.
**[A]** the true venue-weighted share is materially higher than 42%, but I have not
proven it and will not claim it.

### F.4 How many require HTML or browser extraction?

**6 of 12 (50%)** need a per-site HTML selector; **1 of 12 (8%)** genuinely needs a
browser (Uferstudios — verified: the static HTML contains an empty
`<div slot="calendar">` and the text "Keine Veranstaltungen gefunden") **[V]**. Playwright
is therefore a real but narrow cost, and it should be opt-in per source.

### F.5 Is the architecture practical on GitHub Actions + static hosting?

**Yes.** **[V]** Ingestion is HTTP-bound and small: the entire fieldwork — 12 sources,
~40 requests, Shapely PiP over 542 polygons — ran in seconds from a sandbox with no
special infrastructure. Static JSON + Pages is sufficient; the frontend already knows
how to fetch it. No database is justified by any evidence I gathered.

### F.6 What should be implemented first

**[R] Phase 1 only, and specifically: publish `venues.json` + `neighbourhoods.geojson`
+ `metadata.json` from the data already inside `index.html`, with zero edits to
`index.html`.**

Rationale: it is the only phase with no external dependency, no legal exposure beyond
what the fork already carries, no crawling, and a fully checkable acceptance criterion.
It de-risks everything downstream — every later phase needs canonical venues and
verified `lor_id`s — and it produces something you can look at immediately. It is also
the phase I have already half-completed on this branch.

### F.7 Verdict

**Conditional GO.**

Technically the project is sound and the evidence is good: real events were extracted
from real sites by six different mechanisms, the geography is already correct, and the
frontend has the right seams. Nothing I found requires a rewrite or new infrastructure.

Three conditions, in order of severity:

1. **[Q2] Licence.** No licence file exists anywhere, in the fork or upstream. The only
   licence sentence in the product scopes CC BY 4.0 to *aggregated results* and says
   nothing about the venue data or the code. **Get an explicit licence from the upstream
   controller before publishing derived data anywhere outside this fork.** This is a
   blocker for publication, not for building.
2. **[Q1] Hub definition.** "The hubs already in the CCI Atlas" is 6 venues. Decide
   between strict / layer-based / function-based / two-tier before Phase 1 closes,
   because it determines what the source registry is even *for*.
3. **Price honesty.** The €20 cap cannot gate publication. Ship `price_status` with
   `unknown` as a first-class, visibly distinct state, and never infer `free` from an
   absent field. The `priceCurrency: "$"` case proves this is not hypothetical.

**No-go only if** the answer to [Q2] is that the venue data may not be republished. In
that case the Atlas can still run as an internal discovery tool, but the public JSON
outputs in §D.6 would have to be dropped, and that changes the product.

---

## G. Risks and unresolved questions

### G.1 Questions that need your decision

| id | question | blocks |
|---|---|---|
| **Q1** | Which venues count as "hubs"? 6 strict / 44 `space` / empirically event-publishing / two-tier (my rec) | Phase 1 close, Phase 2 scope |
| **Q2** | Can the upstream controller grant an explicit code + data licence? Until then nothing derived leaves this fork | **publication** |
| **Q3** | What do `flag: true/null/false` mean per layer? Undocumented in the data | price display |
| **Q4** | When a source feeds both products, does the €15 central cap or the €20 Atlas cap apply? | Phase 6 |
| **Q5** | Is `data/internal/` acceptable inside a public repo, or must telemetry live outside git? | Phase 5 |
| **Q6** | Should the event layer live in this fork permanently, or in a separate repo consuming this one's JSON? | architecture |

### G.2 Risk register

| risk | severity | evidence | mitigation |
|---|---|---|---|
| No licence → no right to republish derived data | **high** | [V] no LICENSE in either tree; `license: null` via API | Q2; keep artefacts in-fork |
| berlin.de blocks the crawler | **high** | [V] explicit terms block; [V] HTTP 429 already observed | truthful UA, REP compliance, per-host serialisation, backoff |
| Price data unusable → €20 cap unenforceable | **high** | [V] 0/7 samples had trustworthy price; [V] `"$"` currency | `price_status:unknown` + review queue; never infer free |
| Hub definition wrong → wrong product | **high** | [V] only 6 `cat:"hub"` | Q1 before Phase 1 closes |
| robots violation (theaterhaus) | **medium** | [V] `Disallow: /wp-json/` while API returns 200 | deny-wins gate, fixture-tested |
| Bilingual double-counting (kgberlin) | **medium** | [V] de/en twin posts 4827/4831 | dedup via `translations` |
| Year-less / series-only dates (ZK/U, Divan) | **medium** | [V] `"SO 01.03."`, "Jeden ersten Sonntag" | review queue, never guess |
| Cancellation nearly undetectable | **medium** | [V] 1/12 sources expose `eventStatus`, always `EventScheduled`; 11/12 expose nothing | `event_status:unknown` default; re-check close to event date |
| Stale/dead sources in the directory | **medium** | [V] interkulturanstalten last event 2021; [V] kiekin.org 404 | freshness tracking; exclude, don't adapt |
| 4.6 MB file resists review; line 696 un-regenerable | **medium** | [V] no generator in repo | additive patches only; never touch 695/696 |
| 8 LOR disagreements silently "fixed" | **low** | [V] 7 mismatch + 1 outside | keep both values; review queue |
| Playwright scope creep | **low** | [V] 1/12 sources need it | opt-in flag per source |

### G.3 What I could not determine

- Whether `uferhallen.de` is dead or the sandbox DNS failed **[V]** — unresolved.
- Whether the 112 berlin.de venues each have a discoverable calendar id. I proved the
  mechanism works for `c=409` (Stadtbibliothek Pankow) and found `?c=409` linked from
  that library's own page, which suggests per-venue discovery is feasible. **I did not
  verify it for more than one venue.**
- The true venue-weighted machine-readability share (F.3) — needs a full crawl.
- Whether any source publishes accessibility information. None of the 12 did.
- Whether the LOR polygons are the current official vintage. **[V]** They have the
  official 143/542 structure and valid 6→8 digit ids, but **no version or source is
  recorded anywhere in the repo** — see G.4.

### G.4 Attribution gap — act on this before publishing

**[V]** `META.sources` lists 7 sources: two Amt für Statistik reports, IBB
Wohnungsmarktbericht, `funkeinteraktiv/Berlin-Geodaten` (districts + PLZ), `vbb-stations`,
Kreativ Kultur Berlin, Projekt Zukunft.

**The LOR Bezirksregionen and Planungsräume are not credited.** Grepping `META` and the
rendered About text for `LOR`, `Bezirksregion`, `Planungsraum`, `planning area` returns
**zero hits** **[V]** — even though the app *displays* "Kiez (LOR)" in the venue detail
panel and labels the metric selector "Kiez level (LOR planning areas)".

So the Atlas ships 143 + 542 official Berlin geometries with no attribution and no
recorded vintage. **[R]** Before any Kiez Events Atlas work publishes geography, add an
explicit LOR attribution entry (source: Senatsverwaltung für Stadtentwicklung /
Amt für Statistik Berlin-Brandenburg, LOR vintage, licence) to `META.sources`. This is a
**correction to inherited attribution, not a change to the privacy notice** — the brief
forbids altering the latter, and this is the former. It should be raised with the
upstream controller rather than decided unilaterally.

---

## H. Recommended first implementation task

> **Publish `data/public/venues.json`, `data/public/neighbourhoods.geojson` and
> `data/public/metadata.json` from the data already embedded in `index.html`, with no
> edits to `index.html`, and with `atlas_provenance` preserved on every record.**

Scope: Phase 1 only. Concretely —

1. `pipelines/src/kiez_atlas/extract_embedded.py` — read `index.html` line 695, brace-match
   the `window.ATLAS` object, emit `PLACES` and `LOR_BZR`/`LOR_PLR` as JSON. (Prototype
   exists; it produced `artifacts/venue_inventory.json`.)
2. `geo.py` — Shapely `STRtree` PiP; emit `lor_id`, `lor_name`, and the disagreement flag.
3. `publish.py` — write the three public files with `schema_version`, `generated_at`,
   and counts.
4. `validate.py` — assert all 303 records pass `venue.schema.json`, 143 unique BZR ids,
   every `lor_id` resolvable, and that `index.html` is byte-identical to `HEAD`.
5. `tests/` — the four assertions in Phase 1's acceptance criteria.

Deliverable: three JSON files, a passing test suite, and a diff that touches nothing
inherited. Then Q1 and Q2 can be answered with something concrete on the table.

---

## Appendix — evidence index

| claim | where to check |
|---|---|
| fork == upstream | `git diff --stat FETCH_HEAD HEAD` → empty |
| 3 files, 2 commits | `git ls-tree -r HEAD`, `git log --oneline` |
| no licence | `git ls-tree -r HEAD \| grep -i licen` → empty; `gh api repos/… --jq .license` → null |
| 303 venues, 17 fields | `artifacts/venue_inventory.json` |
| 143 BZR / 542 PLR, all valid | `artifacts/venue_inventory.json` + §B.4 |
| 295/303 LOR agreement | `lor_match` field per record |
| `Heerstraße` duplicated | §B.4; ids `042002` and `052005` |
| 6 `cat:"hub"` venues | `artifacts/venue_inventory.json`, filter `category=="hub"` |
| 5 machine-readable sources | `artifacts/sources.json`, `source_quality` |
| 7 real events with gaps | `artifacts/sample_events.json` |
| `priceCurrency: "$"` | sample 3; source `mgh-wassertor` |
| theaterhaus robots | `https://www.theaterhaus-berlin.com/robots.txt` |
| berlin.de terms | `https://www.berlin.de/robots.txt` |
| Uferstudios needs a browser | sample; `GET /de/dance/veranstaltungen` → empty `slot="calendar"` |
| central cap is 15.0 | `event-scraper-github-actions/tests/test_community.py:177` |
| LOR uncredited | §G.4; grep `META` for `LOR` → 0 hits |

*End of report. Preliminary. Nothing here is deployed.*
