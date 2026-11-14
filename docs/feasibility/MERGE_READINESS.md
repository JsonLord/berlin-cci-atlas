# Merge Readiness Report — PR #1 (`phase1/venue-directory`)

**Verdict: READY TO MERGE — 4 open decisions do not block the merge.**

`gh pr view 1` reports `mergeable: MERGEABLE`, 3 commits, 32 files, **0 deletions**.

---

## 1. Verification results

| gate | result |
|---|---|
| Test suite | **80 passed** (was 49; +31 for websites / LOR / deploy boundary) |
| Validation checks | **41/41 passed** (was 27; +14) |
| Build | clean — 303 records, 251 published |
| `index.html` integrity | `927d63a9…` = `HEAD:index.html` — **byte-identical** |
| Inherited files changed | **none** (`index.html`, `config.js`, `CONTRIBUTORS.md` untouched) |
| Deletions | **0** — purely additive |
| Mergeability | `MERGEABLE` |
| `main` modified | no |
| Deployed | no |
| Central event-scraper repo touched | no |

Reproduce:

```bash
PYTHONPATH=pipelines/src python -m kiez_atlas.cli all --repo .
PYTHONPATH=pipelines/src python -m kiez_atlas.report
python -m pytest pipelines/tests -q
```

---

## 2. The four audit items

### 2.1 Website meaning — official vs directory reference

**Finding.** `PLACES[].url` was being published as `"website"`, which reads as "the
venue's official site". It is not. It is *a page the compiler used to describe the
venue*. Audited across all 303 records:

| kind | all 303 | published | meaning |
|---|---|---|---|
| `directory_reference` | 167 | 148 | third-party listing/portal (berlin.de 112, bbk-kulturwerk 23, visitberlin 3, kgberlin, erih) |
| `shared_organisation_site` | 6 | 6 | one URL reused by 2–3 venues under an umbrella org |
| `venue_site_unverified` | 130 | 97 | domain that *appears* to belong to the venue; **not visited** |

**The single most misleading case:** 19 studio houses share one
`bbk-kulturwerk.de/en/art-spaces-berlin/studio-houses` page. Previously all 19 would
have presented that URL as their own website.

**Fix.** New `websites.py`; the public schema's `website` field is now an object:

```json
"website": {
  "url": "https://www.musicpoolberlin.net",
  "kind": "venue_site_unverified",
  "verification": "unverified",
  "shared_by_venue_count": 1
}
```

**No record is ever labelled official.** `verification` is `unverified` for all 251
published records; `metadata.websites.official_claims` is `0`. The strongest claim the
data supports is the honest one.

### 2.2 LOR attribution — provisional status made explicit

The inherited project credits the LOR geography **nowhere** (grep `META` for `LOR` →
0 hits), so this pipeline adds an entry. It is now explicitly provisional:

| field | value |
|---|---|
| `status` | `provisional` |
| `vintage` | `unknown` |
| `licence` | `unknown` |
| `blocks_publication` | `true` |
| `confirmation_required_from` | upstream controller (`kaitiwu/berlin-cci-atlas`) |

`metadata.attribution.publication_blockers` names it. A validation check fails if the
status is ever silently promoted to confirmed.

### 2.3 Public / internal boundary — enforced, not promised

Previously the allowlist was **advisory**: nothing stopped a file being added to
`data/internal/` and published. New `deploy.py` provides two independent guards:

1. **`resolve_deploy_set()`** expands the allowlist and refuses any path that does not
   exist, escapes the repository, lives under `data/internal/`, or matches a forbidden
   filename.
2. **`assert_no_internal_leak(staged)`** inspects a **staged output directory** — the
   output, not the intention. A misconfigured copy step is caught even when the
   allowlist looks correct.

Proven behaviour (test + validation):

| scenario | result |
|---|---|
| stage `data/public/` | passes |
| stage all of `data/` | **refused** |
| copy one `review_queue.json` into staging | **caught** |
| allowlist containing `../etc/passwd` | **refused** |
| allowlist naming a nonexistent file | **refused** |

### 2.4 Tests that detect invented or unverified official websites

31 new tests in `pipelines/tests/test_websites_and_boundary.py`:

- no published record has `verification: verified_official`
- no record carries an `official` / `is_official` / `official_website` field
- **every published URL is byte-identical to the inherited value** — catches a
  plausible-looking invented URL that would pass a syntax check
- every published URL exists in the inherited data
- a URL shared by more than one venue is never labelled `venue_site_unverified`
- `shared_by_venue_count` rejoins the source data exactly
- berlin.de / bbk / visitberlin URLs are always `directory_reference`
- the 19 shared studio-house records are all `directory_reference`

---

## 3. What the merge does and does not do

**Does:** add the classification model, the website audit, the deploy guards, the
generated data products and 80 tests.

**Does not:** modify `index.html`, deploy, scrape, create workflows, touch `main`
directly, or modify the central event-scraper repository.

**Consequence for the product:** nothing is user-visible yet. `data/public/` is not
consumed by the frontend in this PR.

---

## 4. Open decisions — these do NOT block the merge

| # | decision | where |
|---|---|---|
| 1 | Artist studio houses (16): include as cultural venues, or require evidence of public programmes? | `data/internal/review_queue.json` |
| 2 | Advice centres (12): professional advice is out of scope by policy — confirm the whole group is excluded rather than reviewed? | same |
| 3 | Associations (11): confirm excluded unless they host public events | same |
| 4 | Coworking (2) + hire-only rehearsal (2): exclude? | same |

They block **Phase 1 sign-off**, not the merge: the 43 records sit in
`pending_review`, which is a valid, published state that excludes them from output.
Nothing downstream is wrong while they wait.

---

## 5. Two conditions on publishing later (not on merging)

1. **LOR licence + vintage** must be confirmed by the upstream controller before the
   geography is republished anywhere. Tracked in `metadata.attribution`.
2. **The upstream licence question (Q2)** is unresolved — no `LICENSE` file exists in
   either repo. This gates *publication of derived data outside this fork*, not the
   merge.

---

## 6. Honest caveats

- The 251 included venues were included on venue **type**, not on evidence of actual
  programming. 249 of them were decided by R2 ("a library is public infrastructure").
  That is a defensible default, and it is not evidence.
- No venue was visited. `venue_site_unverified` is precisely that admission.
- One Atlas URL was already 404 during the feasibility phase (`kiekin.org`), so link
  rot exists in the source data.
- Community kitchens and urban gardens are named in the scope decision but have no
  venue whose primary function is either, so no such type exists yet — the vocabulary
  is built to add them without a data-model change, and a test proves it.

---

## 7. Recommendation

**Merge.** The change is additive, the inherited application is untouched and
hash-verified, the internal/public boundary is now genuinely enforced rather than
documented, no output claims to be more verified than it is, and 80 tests + 41
validation checks pass.

Then resolve decisions 1–4 to close Phase 1, and confirm the LOR licence before any
publication step.
