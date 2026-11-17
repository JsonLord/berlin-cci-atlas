"""Verify the frozen Divan fixture reproduces the audited results, record for record.

WHY THIS IS A SEPARATE MODULE AND A SEPARATE COMMAND
`kiez_atlas.divan_audit` regenerates the *summary* from the results file. It
trusts `DIVAN_ATTRIBUTION_RESULTS.json` completely: it recomputes counts from
it, but never asks whether the file's 221 records are the ones the fixture
actually contains. Its `verify_fixture()` only checks the gzip digest, which
proves the archive is intact — not that anyone ever counted what was inside it.

That leaves the audit's central claim unguarded. `DIVAN_ATTRIBUTION_AUDIT.md`
§2 asserts an "independent recount from fixture: 221" and "fixture vs results
JSON, record-for-record: identical". Before this module, nothing executable
computed either number; both were prose. A results file with a wrong title, a
shifted hour, or a dropped record would have passed every existing check.

So this module re-derives the population from the fixture and compares. It is
read-only by construction: it has no code path that writes the results file,
because a verifier that can repair the thing it verifies verifies nothing.

DOCUMENTED EXTRACTION RULES
---------------------------
The fixture is a `simcal` (Simple Events Calendar) month grid. Rules, each one
learned from a real disagreement found while writing this module:

1. Record boundary — each `<li class="simcal-event …">` element is one record.
   There are 221. Other classes share the `simcal-event` prefix without being
   records (`simcal-events` on the 27 list containers, `simcal-events-dots` on
   the 30 dot separators), so the split anchors on the exact class-attribute
   prefix `<li class="simcal-event` followed by a space or quote, not on a bare
   substring search.
2. Title — the first `<span class="simcal-event-title">` in the block. The
   class appears twice per record (visible title and tooltip copy); the first
   is authoritative.
3. Start / end — the `content` attribute of `simcal-event-start-date` and
   `simcal-event-end-time`. **Not** `data-event-start`: that is a Unix epoch in
   UTC, so using it shifts every timestamp by one hour against the audited
   values. `content` carries the source's own offset (+01:00) and is what the
   audit recorded. This was the largest single source of disagreement when the
   rules were first derived (442 field mismatches).
4. Location — inside `simcal-event-address`, prefer
   `<meta itemprop="address" content="…">`, falling back to the span's text.
   One record ("SAAL - Konzertbühne", the single non-recurring,
   non-`has-location` record) carries its location only in the meta element and
   has an empty span body. Reading text alone loses it.
5. All three text fields — strip tags, unescape HTML entities, collapse
   whitespace. Entities are load-bearing: 31 fields differ until
   `&amp;`/`&quot;` are decoded, because the audit stored decoded text.

Run:  python -m kiez_atlas.divan_fixture --repo .
Exit code is non-zero if fixture and results disagree in any way.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import html as html_mod
import json
import re
import sys
from collections import Counter
from pathlib import Path

RESULTS_REL = Path("docs/phase2/divan/DIVAN_ATTRIBUTION_RESULTS.json")
FIXTURE_REL = Path("docs/phase2/divan/fixtures/divan_kalender_snapshot.html.gz")
SHA_REL = Path("docs/phase2/divan/fixtures/divan_kalender_snapshot.html.sha256")

# The four fields the audit's reproducibility claim rests on. Comparison is
# deliberately limited to what the fixture can independently supply; the
# attribution fields are outputs of `attribution.py`, not inputs from the page,
# and re-deriving them here would test the classifier rather than the fixture.
COMPARE_FIELDS: tuple[str, ...] = ("title", "start", "end", "location")

# Results-file key for each compared field.
RESULT_KEYS = {
    "title": "title",
    "start": "start_datetime",
    "end": "end_datetime",
    "location": "location",
}

_LI_SPLIT = re.compile(r'(?=<li class="simcal-event[ "])')
_LI_START = re.compile(r'<li class="simcal-event[ "]')
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def _text(fragment: str) -> str:
    """Strip markup, decode entities, collapse whitespace."""
    return _WS.sub(" ", _TAG.sub(" ", html_mod.unescape(fragment))).strip()


def _attr(block: str, pattern: str) -> str | None:
    m = re.search(pattern, block, re.S)
    return html_mod.unescape(m.group(1)).strip() if m else None


def load_fixture_html(repo: Path) -> tuple[str, dict]:
    """Decompress the fixture and check it against the recorded digest.

    Returns the HTML plus digest metadata. Raises on any integrity failure:
    comparing records extracted from a corrupted page would produce a
    misleading field-by-field diff instead of the single clear error.
    """
    gz_path = repo / FIXTURE_REL
    sha_path = repo / SHA_REL
    if not gz_path.exists():
        raise FileNotFoundError(f"fixture missing at {gz_path}")
    if not sha_path.exists():
        raise FileNotFoundError(f"fixture digest missing at {sha_path}")

    expected = sha_path.read_text(encoding="utf-8").split()[0].strip()
    raw = gzip.decompress(gz_path.read_bytes())
    actual = hashlib.sha256(raw).hexdigest()
    info = {
        "path": str(FIXTURE_REL),
        "sha256": actual,
        "sha256_expected": expected,
        "sha256_matches_recorded": actual == expected,
        "raw_bytes": len(raw),
        "gz_bytes": gz_path.stat().st_size,
    }
    if actual != expected:
        raise ValueError(
            f"fixture digest mismatch: recorded {expected}, "
            f"decompressed to {actual}"
        )
    return raw.decode("utf-8"), info


def extract_records(html: str) -> list[dict]:
    """Apply the documented extraction rules to the fixture HTML."""
    records: list[dict] = []
    for chunk in _LI_SPLIT.split(html):
        # The same boundary as _LI_SPLIT, applied as a full condition rather
        # than a bare startswith: `simcal-events-dots` and `simcal-events` also
        # begin with `<li class="simcal-event`, so a loose prefix test would
        # admit container and separator elements as empty records.
        if not _LI_START.match(chunk):
            continue
        block = chunk.split("</li>")[0]

        title = _attr(block, r'<span class="simcal-event-title">(.*?)</span>')
        start = _attr(
            block,
            r'<span class="simcal-event-start simcal-event-start-date"'
            r'[^>]*content="([^"]*)"',
        )
        end = _attr(
            block,
            r'<span class="simcal-event-end simcal-event-end-time"'
            r'[^>]*content="([^"]*)"',
        )

        loc: str | None = None
        addr = re.search(
            r'<span class="simcal-event-address[^>]*>(.*?)</span>', block, re.S
        )
        if addr:
            body = addr.group(1)
            meta = re.search(
                r'<meta itemprop="address" content="([^"]*)"', body
            )
            loc = (
                html_mod.unescape(meta.group(1)).strip()
                if meta
                else _text(body)
            )

        records.append(
            {
                "title": title or "",
                "start": start or "",
                "end": end or "",
                "location": loc or "",
            }
        )
    return records


def _key(rec: dict) -> tuple:
    return tuple(rec[f] for f in COMPARE_FIELDS)


def compare(fixture_records: list[dict], results: dict) -> dict:
    """Compare fixture-extracted records with the committed results file.

    Identity is the (title, start, end, location) tuple. Comparison is by
    *multiset*, not set: 221 records contain 220 distinct tuples, so one
    duplicate legitimately exists on both sides. Set logic would either flag a
    correct file or mask a real one; a duplicate present on only one side is a
    genuine discrepancy and multiset comparison catches it.
    """
    events = results["events"]
    audited = [{f: e[RESULT_KEYS[f]] for f in COMPARE_FIELDS} for e in events]

    fx_keys = Counter(_key(r) for r in fixture_records)
    au_keys = Counter(_key(r) for r in audited)

    # Multiset difference: multiplicity is respected, so a tuple present twice
    # in the fixture and once in the results surfaces as one additional.
    missing = fx_keys - au_keys   # in fixture, absent from results
    extra = au_keys - fx_keys     # in results, absent from fixture

    # Duplicates are reported, not failed: they are a property of the source
    # (one listing appears twice in the month grid) and are faithfully carried
    # by both sides. Asymmetry is already covered by missing/extra above.
    dup_fixture = {k: c for k, c in fx_keys.items() if c > 1}
    dup_audited = {k: c for k, c in au_keys.items() if c > 1}

    # Positional field diffs, for records that are present on both sides in the
    # same slot. A pure reordering shows up here as `positional_order_differs`
    # while missing/extra stay empty, which distinguishes "someone re-sorted
    # the file" from "the data disagrees".
    mismatches: list[dict] = []
    for i, (f, a) in enumerate(zip(fixture_records, audited)):
        if _key(f) == _key(a):
            continue
        for fld in COMPARE_FIELDS:
            if f[fld] != a[fld]:
                mismatches.append(
                    {
                        "event_index": i,
                        "field": fld,
                        "fixture": f[fld],
                        "results": a[fld],
                    }
                )

    same_order = [_key(r) for r in fixture_records] == [
        _key(r) for r in audited
    ]

    return {
        "compared_fields": list(COMPARE_FIELDS),
        "fixture_record_count": len(fixture_records),
        "results_record_count": len(audited),
        "results_declared_event_count": results.get("event_count"),
        "fixture_distinct_tuples": len(fx_keys),
        "results_distinct_tuples": len(au_keys),
        "duplicates_in_fixture": [
            {f: k[j] for j, f in enumerate(COMPARE_FIELDS)} | {"count": c}
            for k, c in sorted(dup_fixture.items())
        ],
        "duplicates_in_results": [
            {f: k[j] for j, f in enumerate(COMPARE_FIELDS)} | {"count": c}
            for k, c in sorted(dup_audited.items())
        ],
        "missing_from_results": [
            {f: k[j] for j, f in enumerate(COMPARE_FIELDS)} | {"count": c}
            for k, c in sorted(missing.items())
        ],
        "additional_in_results": [
            {f: k[j] for j, f in enumerate(COMPARE_FIELDS)} | {"count": c}
            for k, c in sorted(extra.items())
        ],
        "field_mismatches": mismatches,
        "field_mismatch_count": len(mismatches),
        "positional_order_matches": same_order,
    }


def verify(repo: Path) -> dict:
    """Full verification. Never writes anything."""
    html, fixture_info = load_fixture_html(repo)
    results_path = repo / RESULTS_REL
    if not results_path.exists():
        # A failure, never a skip: the results file is committed, so its
        # absence is a broken checkout, not an environment difference.
        raise FileNotFoundError(
            f"audited results missing at {results_path}; verification cannot "
            "be skipped or it protects nothing"
        )
    results = json.loads(results_path.read_text(encoding="utf-8"))
    records = extract_records(html)
    report = {"fixture": fixture_info, **compare(records, results)}

    report["agrees"] = (
        fixture_info["sha256_matches_recorded"]
        and report["fixture_record_count"] == report["results_record_count"]
        and report["results_record_count"] == report["results_declared_event_count"]
        and not report["missing_from_results"]
        and not report["additional_in_results"]
        and report["field_mismatch_count"] == 0
        and report["positional_order_matches"]
    )
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="kiez_atlas.divan_fixture",
        description=(
            "Independently re-extract the Divan calendar fixture and compare "
            "it with the committed audit results. Read-only: this command "
            "never writes the results file."
        ),
    )
    ap.add_argument("--repo", default=".")
    ap.add_argument(
        "--json", action="store_true", help="print the full report as JSON"
    )
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()

    try:
        r = verify(repo)
    except (FileNotFoundError, ValueError) as exc:
        print(f"FIXTURE VERIFICATION ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
    else:
        f = r["fixture"]
        print(f"fixture          {f['path']}")
        print(
            f"  sha256         {f['sha256']} "
            f"({'matches recorded' if f['sha256_matches_recorded'] else 'MISMATCH'})"
        )
        print(f"  decompressed   {f['raw_bytes']} bytes from {f['gz_bytes']} gzipped")
        print(
            f"records          fixture={r['fixture_record_count']} "
            f"results={r['results_record_count']} "
            f"declared={r['results_declared_event_count']}"
        )
        print(
            f"distinct tuples  fixture={r['fixture_distinct_tuples']} "
            f"results={r['results_distinct_tuples']}"
        )
        print(
            f"duplicates       fixture={len(r['duplicates_in_fixture'])} "
            f"results={len(r['duplicates_in_results'])} (symmetric, expected)"
        )
        print(f"missing from results   {len(r['missing_from_results'])}")
        print(f"additional in results  {len(r['additional_in_results'])}")
        print(f"field mismatches       {r['field_mismatch_count']}")
        print(f"record order matches   {r['positional_order_matches']}")
        for m in r["field_mismatches"][:10]:
            print(
                f"  index {m['event_index']} {m['field']}: "
                f"fixture={m['fixture']!r} results={m['results']!r}"
            )
        print(
            "\nFIXTURE AND RESULTS AGREE"
            if r["agrees"]
            else "\nFIXTURE AND RESULTS DISAGREE"
        )
    return 0 if r["agrees"] else 1


if __name__ == "__main__":
    sys.exit(main())
