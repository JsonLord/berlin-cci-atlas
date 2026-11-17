"""Regenerate the Divan attribution summary from the audited results.

WHY THIS IS GENERATED AND NOT HAND-WRITTEN
The first version of `DIVAN_ATTRIBUTION_SUMMARY.json` was written by hand and
drifted from `DIVAN_ATTRIBUTION_RESULTS.json` in two ways:

 1. `distinct_titles_current_mapped` said 41 while the same file's
    `distinct_titles_current_mapped_venue` said 40, and the results file
    supports 40. Two fields describing one quantity disagreed.

 2. The single `venue_precision` field conflated two different measurements.
    Events at Divan's *second* building are Divan-organised but are not at the
    mapped venue, so "precision" meant 95.5% or 79.2% depending on which
    question was being asked. Both numbers are correct; one field could not
    hold both, and the ambiguity is what let a 225-event claim survive.

So the summary is derived from the results file, and every count is computed
rather than recalled. If the results change, the summary changes with them.

Run:  python -m kiez_atlas.divan_audit --repo .
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

RESULTS_REL = Path("docs/phase2/divan/DIVAN_ATTRIBUTION_RESULTS.json")
SUMMARY_REL = Path("docs/phase2/divan/DIVAN_ATTRIBUTION_SUMMARY.json")
FIXTURE_REL = Path("docs/phase2/divan/fixtures/divan_kalender_snapshot.html.gz")
SHA_REL = Path("docs/phase2/divan/fixtures/divan_kalender_snapshot.html.sha256")


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def verify_fixture(repo: Path) -> dict:
    """Check the frozen snapshot still decompresses to the recorded digest.

    The audit's central claim is that 221 records were reconstructed from a
    page that no longer needs to be fetched. That claim is only worth anything
    if the fixture is intact, so the digest is verified on every regeneration.
    """
    gz = repo / FIXTURE_REL
    expected = (repo / SHA_REL).read_text(encoding="utf-8").split()[0].strip()
    raw = gzip.decompress(gz.read_bytes())
    actual = hashlib.sha256(raw).hexdigest()
    return {
        "path": str(FIXTURE_REL),
        "sha256": actual,
        "sha256_matches_recorded": actual == expected,
        "raw_bytes": len(raw),
        "gz_bytes": gz.stat().st_size,
    }


def summarise(results: dict, *, repo: Path | None = None) -> dict:
    """Compute the summary. Every number here is derived, never asserted."""
    events = results["events"]

    # The expiry cutoff must be explicit and recorded. The results file carries
    # only a date, so the cutoff is that date at 00:00 UTC. This is not a
    # cosmetic choice: 10 records end during 2026-11-16 itself, so a cutoff
    # late in that day would flip them to expired and move every "current"
    # count. The chosen cutoff reproduces the stored flags exactly, and the
    # loop below fails loudly if that ever stops being true.
    if results.get("audit_timestamp"):
        cutoff = datetime.fromisoformat(
            results["audit_timestamp"].replace("Z", "+00:00")
        )
    else:
        cutoff = datetime.fromisoformat(results["audit_date"]).replace(
            tzinfo=timezone.utc
        )

    total = len(events)
    if total != results.get("event_count", total):
        raise ValueError(
            f"results file is internally inconsistent: event_count="
            f"{results.get('event_count')} but {total} records present"
        )

    mapped = [e for e in events if e["attribution_site"] == "mapped_venue"]
    other = [e for e in events if e["attribution_site"] == "other_site"]
    ambiguous = [e for e in events if e["attribution"] == "ambiguous"]
    insufficient = [e for e in events if e["attribution"] == "insufficient_data"]

    # Expiry is recomputed from the timestamps and then cross-checked against
    # the stored flag. A silent disagreement between the two would make the
    # "current" counts meaningless, so it is an error, not a warning.
    for e in events:
        derived = datetime.fromisoformat(e["end_datetime"]) < cutoff
        if derived != e["data_quality_flags"]["expired"]:
            raise ValueError(
                f"record {e['event_index']} expiry flag disagrees with its "
                f"end_datetime {e['end_datetime']} relative to cutoff {cutoff}"
            )

    current = [e for e in mapped if not e["data_quality_flags"]["expired"]]
    expired = [e for e in mapped if e["data_quality_flags"]["expired"]]

    def pct(n: int) -> float:
        return round(100.0 * n / total, 1) if total else 0.0

    summary = {
        "audit_timestamp": results.get("audit_timestamp"),
        "methodology_version": results.get("methodology_version"),
        "source_url": results.get("source"),
        "venue_id": "interkulturelles-stadtteilzentrum-divan",
        "generated_by": "kiez_atlas.divan_audit",
        "generated_from": str(RESULTS_REL),
        "original_claim": {
            "records": 225,
            "status": "qualified",
            "note": "Phase 2 registry claim. Live page yields 221 items, not 225.",
        },
        "audited_population": {
            "records_reconstructed": total,
            "reconstruction_method": (
                "live page fetch 2026-11-16, full HTML archived; the original "
                "225-record extraction artefact was NOT preserved in the repo"
            ),
            "complete_population": True,
        },
        "classification": {
            "divan_hosted_total": len(mapped) + len(other),
            "divan_hosted_mapped_venue": len(mapped),
            "divan_hosted_other_building": len(other),
            # Kept explicit at zero rather than omitted: a reader must be able
            # to tell "no events of this kind" from "this kind was not audited".
            "divan_organised_elsewhere": sum(
                1 for e in events if e["attribution"] == "organised_elsewhere"
            ),
            "divan_partnered": sum(
                1 for e in events if e["attribution"] == "partnered"
            ),
            "external_event": sum(
                1 for e in events if e["attribution"] == "external_event"
            ),
            "ambiguous": len(ambiguous),
            "insufficient_data": len(insufficient),
        },
        "metrics": {
            # Two different questions, two different numbers. Keeping them in
            # one field is how the source's yield got overstated.
            "map_precision": round(len(mapped) / total, 4),
            "map_precision_pct": pct(len(mapped)),
            "map_precision_definition": (
                "events attributable to the specific building the Atlas marker "
                "represents / all audited records"
            ),
            "organisation_precision": round((len(mapped) + len(other)) / total, 4),
            "organisation_precision_pct": pct(len(mapped) + len(other)),
            "organisation_precision_definition": (
                "events associated with any Divan building / all audited records"
            ),
            "venue_precision": round(len(mapped) / total, 4),
            "venue_precision_deprecated": (
                "alias of map_precision, kept for older readers; use "
                "map_precision or organisation_precision explicitly"
            ),
            "uncertainty_ambiguous_pct": pct(len(ambiguous)),
            "uncertainty_insufficient_pct": pct(len(insufficient)),
        },
        "data_quality": {
            "expiry_cutoff": cutoff.isoformat(),
            "usable_dates": sum(1 for e in events if e["start_datetime"] and e["end_datetime"]),
            "explicit_locations": sum(1 for e in events if (e.get("location") or "").strip()),
            "individual_event_urls": sum(1 for e in events if e.get("event_url")),
            "recurring_records": sum(1 for e in events if e["data_quality_flags"]["recurring"]),
            "distinct_titles_all": len({e["title"] for e in events}),
            "distinct_titles_mapped_venue": len({e["title"] for e in mapped}),
            "current_mapped": len(current),
            "expired_mapped": len(expired),
            # One quantity, one field. The previous file carried two names for
            # it and they disagreed (41 vs 40).
            "distinct_titles_current_mapped": len({e["title"] for e in current}),
            "records_requiring_human_review": sum(
                1 for e in events if e["requires_human_review"]
            ),
            "date_range": {
                "earliest": min(e["start_datetime"] for e in events),
                "latest": max(e["start_datetime"] for e in events),
            },
        },
        "source_qualification": {
            "previous": "qualified",
            "revised": "qualified_with_filter",
            "distinction": (
                "Technically qualified: extraction works and per-event location "
                f"is present. NOT eligible for raw publication: {len(other)} "
                "records belong to a second building with no Atlas marker, and "
                f"{sum(1 for e in events if e['data_quality_flags']['recurring'])}"
                f"/{total} are recurring instances."
            ),
            "raw_instance_count_is_misleading": True,
        },
    }

    if repo is not None:
        summary["fixture"] = verify_fixture(repo)
    return summary


def write(repo: Path) -> dict:
    results = _load(repo / RESULTS_REL)
    summary = summarise(results, repo=repo)
    (repo / SUMMARY_REL).write_text(
        json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kiez_atlas.divan_audit")
    ap.add_argument("--repo", default=".")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    s = write(repo)
    m = s["metrics"]
    print(
        f"wrote {SUMMARY_REL}: {s['audited_population']['records_reconstructed']} records, "
        f"map_precision={m['map_precision_pct']}%, "
        f"organisation_precision={m['organisation_precision_pct']}%"
    )
    if not s.get("fixture", {}).get("sha256_matches_recorded", True):
        print("FIXTURE DIGEST MISMATCH", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
