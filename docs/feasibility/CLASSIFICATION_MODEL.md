# Venue Classification Model — explicit rules

**Status: Phase 1, implemented and tested.** Code: `pipelines/src/kiez_atlas/classify.py`,
vocabularies: `pipelines/src/kiez_atlas/vocab.py`, tests: `pipelines/tests/test_classify.py`
(49 tests). Generated output report: [`CLASSIFICATION_REPORT.md`](CLASSIFICATION_REPORT.md).

This document is the human-readable specification. If it and the code disagree, the code is
wrong — the rules below are the intent, and three of them exist because a bug proved the
intent was not being met.

---

## 1. The four dimensions, kept strictly separate

| dimension | answers | values |
|---|---|---|
| `venue_type` | What kind of physical place is this? | open vocabulary, 21 values today |
| `community_relevance` | Which community functions does it enable? | open vocabulary, 13 values |
| `product_status` | Is it in the directory? | `included` · `excluded` · `pending_review` |
| `event_source_status` | Can events be retrieved? | `not_assessed` · `candidate` · `qualified` · `temporarily_unavailable` · `not_suitable` |

**The separation is enforced, not merely intended.** `event_source_status` is never read
when computing `product_status`, and a validation check asserts that all 303 records still
carry `not_assessed` at Phase 1 — so directory membership provably cannot have been
influenced by whether an event feed was found.

`venue_type` and `community_relevance` are **not** closed JSON-Schema enums. They are
validated against the registries in `vocab.py`. Adding a type is one dictionary entry; no
schema migration, no data rewrite. A test adds `urban_garden` at runtime and asserts
classification still works, and another asserts the public schema has no `enum` on either
field.

---

## 2. Rule order

First match wins. Every record stores which rule fired and a reason string naming the
evidence, so no decision is silent.

```
R1   non-physical resource              -> excluded
R2   inherently public venue type       -> included
R4   STRONG public-access evidence      -> included     (outranks R3, R3b, R5)
R3   funding / bank / state office      -> excluded
R3b  association or advice desk         -> pending_review
R5   physical, public access unproven   -> pending_review
R6   unmapped                           -> pending_review
```

### Why R4 sits above R3/R3b/R5

An advice centre or studio house that demonstrably serves the public is community-relevant
even though its inherited category is `advice` or `studios`. Ordering R4 first means
*evidence beats category*. Two records are included this way today: **Music Pool Berlin**
(free one-hour consultations) and **Atelierhaus Mengerzeile** (open studios).

### Why R3b is separate from R3

A funding body and a membership association are both "administrative", but they fail
differently. A funding body's purpose is to allocate money — no reading of its description
makes it a venue. An association may genuinely run public sessions; the record just does
not say so. So R3 excludes outright and R3b quarantines for a human.

---

## 3. Rule-by-rule specification

### R1 — non-physical resource → `excluded`

**Trigger:** the venue id is in `NON_PHYSICAL_IDS`, an explicit enumerated map.

**Why enumerated and not pattern-matched:** deciding "is this a real place?" from prose is
exactly the subjective judgement the scope decision forbids. One record qualifies:

| venue | evidence |
|---|---|
| Creative City Berlin | desc: *"Online community portal of Kulturprojekte Berlin"*; address is `Klosterstraße 68 (c/o Kulturprojekte Berlin GmbH)` — a postal c/o for an online service |

**1 record.**

### R2 — inherently public venue type → `included`

**Trigger:** `venue_type ∈ INHERENTLY_PUBLIC_TYPES`.

```
community_centre  cultural_centre  library  adult_education_centre
music_school      youth_arts_school  gallery  event_venue
creative_hub      makerspace      workshop_space
```

**Justification:** these types *are* public community infrastructure. A public library does
not need to prove it is public. This is a deliberate default and it is the single largest
source of inclusions — **249 of 303 records**. That is honest to state: those 249 are
included on the strength of their **type**, not on evidence of actual programming.

**249 records.**

### R4 — STRONG public-access evidence → `included`

**Trigger:** `venue_type ∈ ADMINISTRATIVE_TYPES ∪ EVIDENCE_REQUIRED_TYPES` **and** the
description matches `STRONG_PUBLIC`.

STRONG patterns are explicit access constructions only:

```
open to the public          open studio / open day
public programme/events     publicly funded programme
for the public              free|open to all|everyone|residents
drop-in                     for residents
free (one-hour) consultations
Veranstaltungen             öffentliche Veranstaltung/Programm/Zugang
Begegnung                   neighbourhood centre/events
community centre/events     hosts concerts|events|exhibitions
runs a public …
```

**2 records.**

### R3 — funding body / bank / state office → `excluded`

**Trigger:** `venue_type ∈ {funding_body, bank, government_office, university_facility}`
and no STRONG evidence.

**Justification:** the function is to *allocate* resources, not to host public community
activity. These remain valuable to the CCI Atlas itself; they are excluded from the
**event** directory only.

**8 records:** Musicboard Berlin, IBB Ventures, Investitionsbank Berlin, Projekt Zukunft,
Senatsverwaltung für Kultur, initiative neue musik, Initiative Musik, Berlin Career College.

### R3b — association or advice desk → `pending_review`

**Trigger:** `venue_type ∈ ADMINISTRATIVE_TYPES` (association_office, advice_centre) with
only WEAK evidence.

**Justification:** being *about* a scene is not hosting that scene's events. This rule
exists specifically because of a false positive — see §5.

**11 records.**

### R5 — physical, public access unproven → `pending_review`

**Trigger:** `venue_type ∈ EVIDENCE_REQUIRED_TYPES`
(`artist_studio_building`, `rehearsal_space`, `coworking_space`, `advice_centre`) with no
STRONG evidence.

**Justification:** these are physical and often culturally vital, but the record evidences
*letting*, *hire* or *appointment-based service* — not public access. The open question is
factual, not philosophical: does this building hold public programmes?

**32 records.**

### R6 — unmapped → `pending_review`

Never reached in the current data. Exists so a future unmapped category degrades to review
rather than being silently coerced. A test asserts no record currently falls through.

---

## 4. Two evidence tiers

A single "does it mention events?" matcher produced demonstrably wrong answers, so evidence
is graded.

| tier | examples | sufficient to |
|---|---|---|
| **STRONG** | `open to the public`, `free consultations`, `drop-in`, `open studio`, `Veranstaltungen`, `Begegnung` | **include** a record whose type would otherwise be excluded or reviewed |
| **WEAK** | `exhibition`, `workshop`, `courses`, `theatre`, `cinema`, `subsidised` | route to **review** only — never include |

The distinction matters because the weak words are exactly the ones that appear in the
description of an organisation that *talks about* an activity rather than *hosting* it.

---

## 5. Three bugs these rules exist to prevent

Each is pinned by a regression test. They are documented because they show where the model
is fragile, which is more useful than claiming it is not.

### 5.1 A venture-capital fund was classified as a community venue

IBB Ventures was **included** because:

- `early-stage` matched `\bstage\b`
- `public venture capital arm` matched a `public …` construction

Two independent false signals on one record. Fixed by requiring STRONG access
constructions and by putting `funding_body` in `FINANCIAL_OR_STATE_TYPES`, which only
STRONG evidence can overcome.

### 5.2 Two theatre *associations* were included for containing the word "theatre"

LAFT Berlin and Bundesverband Freie Darstellende Künste are membership bodies that
represent theatre makers. Their descriptions contain `theatre`, so a naive matcher included
them. They are about theatre; they do not host it. Now R3b → review.

### 5.3 Twelve public libraries were retyped as makerspaces

The subtlest and most damaging. Type patterns were matched against **name and description**,
so any library whose description mentions a makerspace it hosts was retyped
`makerspace` — silently dropping the library identity of 12 public venues.

**It was invisible in the status totals** (251/9/43 unchanged) and only surfaced because the
type distribution was checked against the inherited categories: `library` had fallen 68→54
while `makerspace` rose 4→19.

**Fix:** types are derived from the **name** only. A description says what a venue *does* or
*contains*; it does not say what the venue *is*. Where a description really is the only
evidence, the record gets an explicit `TYPE_OVERRIDES` entry.

---

## 6. Type derivation precedence

```
1. TYPE_OVERRIDES[venue_id]      explicit, keyed, with a quoted reason
2. NAME_PATTERNS                 regex on the NAME only, first match wins
3. CATEGORY_TO_TYPE[inherited cat]
4. "creative_hub" fallback       never reached today; asserted by test
```

`TYPE_OVERRIDES` has 35 entries, each carrying the quoted evidence that justified it, e.g.:

```python
"wabe": ("cultural_centre", "desc: 'District-run cultural centre'"),
"malzfabrik": ("event_venue", "type: converted malting plant used as an event venue"),
```

**A key-integrity test asserts every override key is a real venue id.** This exists because
the first draft had **9 of 37 keys pointing at ids that did not exist** — inert entries that
looked like decisions but changed nothing. Venue ids in the source data are truncated at
~48 characters, which is what made the mistake easy.

---

## 6b. What a `website` value actually means

The inherited `PLACES[].url` is **not** the venue's official website. It is a page
the compiler used to describe the venue. Auditing all 303 records gives three shapes,
implemented in `pipelines/src/kiez_atlas/websites.py`:

| `kind` | meaning | published count |
|---|---|---|
| `directory_reference` | third-party listing/portal (berlin.de, bbk-kulturwerk.de, visitberlin.de, kgberlin.net, erih.net) | **148** |
| `shared_organisation_site` | one URL reused by several venues because it belongs to their umbrella organisation | **6** |
| `venue_site_unverified` | a domain that appears to belong to the venue | **97** |

**No record is ever labelled official.** `verification` is `unverified` for all 251
published records and `metadata.websites.official_claims` is `0`. The strongest claim
the data supports is "this domain appears to belong to the venue" — the feasibility
phase never visited these sites.

The most misleading single case: **19 studio houses share one
`bbk-kulturwerk.de/en/art-spaces-berlin/studio-houses` page** (16 of them are in the
review queue, 3 published). All 19 are `directory_reference`, not their own sites.

Tests that enforce this (`test_websites_and_boundary.py`):

- no published record has `verification: verified_official`
- no record carries an `official` / `is_official` / `official_website` field
- every published URL is byte-identical to the inherited value (catches invented URLs)
- any URL shared by more than one venue is never labelled `venue_site_unverified`
- `shared_by_venue_count` rejoins the source data exactly

## 7. What the model deliberately does not do

1. **It does not verify venues are open or at that address.** Classification derives from
   inherited descriptions. One Atlas URL was already 404 during the feasibility study.
2. **It does not infer from `flag`.** The semantics of `flag: true/null/false` differ by
   layer and are undocumented (open question Q3).
3. **It does not create empty categories.** The scope decision names community kitchens and
   urban gardens, but no record has either as its primary function — two mention a garden or
   kitchen as an amenity. Adding those types now would create empty buckets; the vocabulary
   is built so they can be added later without a data-model change, and a test proves it.
4. **It does not resolve review cases by rule.** 43 records need a human. Guessing would
   satisfy the schema and defeat the purpose.

---

## 8. How to audit any single decision

Every record in `data/internal/venue_inventory.json` carries:

```jsonc
"classification": {
  "venue_type": "advice_centre",
  "community_relevance": ["advice_support", "sector_networking"],
  "product_status": "included",
  "rule": "R4",
  "reason": "Record evidences a public programme, so treated as community-relevant
             despite its category. type_override (...); STRONG evidence
             'free one-hour consultations' in 'Advice and professional-development
             centre for musicians ... offering free one-hour consultations ...'"
}
```

So for any record you can answer: which rule fired, what evidence triggered it, and what
the inherited category was — without reading the code.

To re-derive everything from scratch:

```bash
PYTHONPATH=pipelines/src python -m kiez_atlas.cli all --repo .
PYTHONPATH=pipelines/src python -m kiez_atlas.report
python -m pytest pipelines/tests -q
```

---

## 9. Current outcome

| status | count |
|---|---|
| included | 251 |
| excluded | 9 |
| pending_review | 43 |
| **total** | **303** |

Distribution by type and every exclusion reason are in
[`CLASSIFICATION_REPORT.md`](CLASSIFICATION_REPORT.md), which is generated from the data so
its numbers cannot drift.
