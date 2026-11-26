"""Metrics exporter for the Kiez Events Atlas.

Collects and exports structured metrics from the built data products.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from .vocab import PRODUCT_STATUS
from .websites import DIRECTORY_HOSTS
from .geo import LorIndex
from .extract_embedded import load_atlas

# The two Divan buildings, matched on the location text rather than on the
# audit's own `location_site` label: the label is not produced by any code in
# this repository, so counting it would only restate the audit. Matching the
# addresses instead is an independent read of the same evidence.
_NEHRINGSTR_8 = re.compile(r"Nehringstr(?:aße|\.)\s*8\b")
_NEHRINGSTR_26 = re.compile(r"Nehringstr(?:aße|\.)\s*26\b")


@dataclass
class ClassificationMetrics:
    """Metrics derived from venue classification."""
    total_venues: int
    product_status: dict[str, int]
    venue_type: dict[str, int]
    rule_fired: dict[str, int]
    community_relevance: dict[str, int]
    venue_type_by_status: dict[str, dict[str, int]]


@dataclass
class LorMetrics:
    """Metrics derived from LOR geography."""
    total_bzr: int
    total_plr: int
    venues_with_lor: int
    venues_without_lor: int
    bzr_venue_counts: dict[str, int]
    plr_venue_counts: dict[str, int]
    atlas_lor_agree: int
    atlas_lor_disagree: int
    atlas_lor_outside: int


@dataclass
class WebsiteMetrics:
    """Metrics derived from website classification."""
    total_venues: int
    website_kind: dict[str, int]
    verification_status: dict[str, int]
    shared_url_counts: dict[int, int]
    official_claims: int
    directory_hosts: list[str]


@dataclass
class SourceRegistryMetrics:
    """Metrics derived from the Phase 2 source registry."""
    total_sources: int
    source_status: dict[str, int]
    csv_json_agree: bool


@dataclass
class DivanAuditMetrics:
    """Metrics derived from the Divan audit."""
    total_events: int
    attribution_site: dict[str, int]
    attribution: dict[str, int]
    evidence_type: dict[str, int]
    publishable_events: int
    multi_venue_events: int
    fixture_sha256: str
    fixture_raw_bytes: int
    fixture_gz_bytes: int


@dataclass
class AllMetrics:
    """Complete metrics collection."""
    classification: ClassificationMetrics
    lor: LorMetrics
    websites: WebsiteMetrics
    source_registry: SourceRegistryMetrics
    divan_audit: DivanAuditMetrics

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def collect_classification_metrics(repo: Path) -> ClassificationMetrics:
    """Collect metrics from venue_inventory.json and classification.json."""
    inv_path = repo / "data" / "internal" / "venue_inventory.json"
    inv = json.loads(inv_path.read_text(encoding="utf-8"))
    venues = inv["venues"]

    product_status = Counter(v["classification"]["product_status"] for v in venues)
    venue_type = Counter(v["classification"]["venue_type"] for v in venues)
    rule_fired = Counter(v["classification"]["rule"] for v in venues)

    relevance_counter: Counter[str] = Counter()
    for v in venues:
        for r in v["classification"]["community_relevance"]:
            relevance_counter[r] += 1

    # venue_type by product_status
    venue_type_by_status: dict[str, dict[str, int]] = {}
    for status in PRODUCT_STATUS:
        subset = [v for v in venues if v["classification"]["product_status"] == status]
        venue_type_by_status[status] = dict(Counter(v["classification"]["venue_type"] for v in subset))

    return ClassificationMetrics(
        total_venues=len(venues),
        product_status=dict(product_status),
        venue_type=dict(venue_type),
        rule_fired=dict(rule_fired),
        community_relevance=dict(relevance_counter),
        venue_type_by_status=venue_type_by_status,
    )


def collect_lor_metrics(repo: Path) -> LorMetrics:
    """Collect metrics from LOR geography and atlas."""
    atlas = load_atlas(repo / "index.html")
    lor = LorIndex.build(atlas["LOR_PLR"], atlas["LOR_BZR"])

    inv_path = repo / "data" / "internal" / "venue_inventory.json"
    inv = json.loads(inv_path.read_text(encoding="utf-8"))
    venues = inv["venues"]

    # Count venues with/without LOR match
    with_lor = 0
    without_lor = 0
    bzr_counts: Counter[str] = Counter()
    plr_counts: Counter[str] = Counter()
    agree = disagree = outside = 0

    for v in venues:
        inherited = v.get("inherited", {})
        lor_id = inherited.get("lor_plr")
        coords = inherited.get("coords")

        # `lor_plr` is an 8-digit Planungsraum id, so it is looked up in
        # `plr_by_id`; the 6-digit Bezirksregion id is derived from its prefix.
        # Looking an 8-digit id up in `bzr_by_id` never matches and silently
        # reported every venue as unlocated.
        if lor_id and lor_id in lor.plr_by_id:
            with_lor += 1
            bzr_id = lor.bzr_of_plr(lor_id)
            if bzr_id:
                bzr_counts[bzr_id] += 1
            plr_counts[lor_id] += 1
        else:
            without_lor += 1

        # Atlas vs LOR agreement (from test_geo_and_products.py)
        if coords and len(coords) == 2:
            plr, _ = lor.locate(coords[0], coords[1])
            if plr is None:
                outside += 1
            elif plr == lor_id:
                agree += 1
            else:
                disagree += 1
        else:
            outside += 1

    return LorMetrics(
        total_bzr=len(lor.bzr_features),
        total_plr=len(lor.plr_features),
        venues_with_lor=with_lor,
        venues_without_lor=without_lor,
        bzr_venue_counts=dict(bzr_counts),
        plr_venue_counts=dict(plr_counts),
        atlas_lor_agree=agree,
        atlas_lor_disagree=disagree,
        atlas_lor_outside=outside,
    )


def collect_website_metrics(repo: Path) -> WebsiteMetrics:
    """Collect metrics from website classification."""
    pub_path = repo / "data" / "public" / "venues.json"
    pub = json.loads(pub_path.read_text(encoding="utf-8"))
    venues = pub["venues"]

    kind_counter = Counter(v["website"]["kind"] for v in venues if v["website"]["url"])
    verification_counter = Counter(v["website"]["verification"] for v in venues if v["website"]["url"])

    shared_counts: Counter[int] = Counter()
    for v in venues:
        if v["website"]["url"]:
            shared_counts[v["website"]["shared_by_venue_count"]] += 1

    # Check for official claims (should be 0)
    official_claims = sum(1 for v in venues if v["website"]["verification"] == "verified_official")

    # Sorted, not `list(DIRECTORY_HOSTS)`: the source is a frozenset, so its
    # iteration order varies between processes and the JSON output changed
    # bytes on every run. An exporter whose output cannot be diffed cannot be
    # committed, compared or reviewed.
    directory_hosts = sorted(DIRECTORY_HOSTS)

    return WebsiteMetrics(
        total_venues=len(venues),
        website_kind=dict(kind_counter),
        verification_status=dict(verification_counter),
        shared_url_counts=dict(shared_counts),
        official_claims=official_claims,
        directory_hosts=directory_hosts,
    )


def collect_source_registry_metrics(repo: Path) -> SourceRegistryMetrics:
    """Collect metrics from the Phase 2 source registry."""
    registry_path = repo / "docs" / "phase2" / "PHASE2_SOURCE_REGISTRY.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))

    status_counter = Counter(r["source_status"] for r in registry)

    # Check CSV/JSON agreement
    import csv
    csv_path = repo / "docs" / "phase2" / "PHASE2_SOURCE_REGISTRY.csv"
    with csv_path.open(newline="", encoding="utf-8") as fh:
        csv_status = {r["source_id"]: r["source_status"] for r in csv.DictReader(fh)}
    json_status = {r["source_id"]: r["source_status"] for r in registry}
    csv_json_agree = csv_status == json_status

    return SourceRegistryMetrics(
        total_sources=len(registry),
        source_status=dict(status_counter),
        csv_json_agree=csv_json_agree,
    )


def collect_divan_audit_metrics(repo: Path) -> DivanAuditMetrics:
    """Collect metrics from the Divan audit."""
    results_path = repo / "docs" / "phase2" / "divan" / "DIVAN_ATTRIBUTION_RESULTS.json"
    results = json.loads(results_path.read_text(encoding="utf-8"))
    events = results["events"]

    attribution_site_counter = Counter(e["attribution_site"] for e in events)
    attribution_counter = Counter(e["attribution"] for e in events)
    evidence_type_counter = Counter(e["evidence_type"] for e in events)
    publishable = sum(1 for e in events if e["attribution_site"] == "mapped_venue" and not e["requires_human_review"])
    multi_venue = sum(
        1
        for e in events
        if e.get("location")
        and _NEHRINGSTR_8.search(e["location"])
        and _NEHRINGSTR_26.search(e["location"])
    )

    # Fixture info
    from . import divan_fixture as dfx
    _html, info = dfx.load_fixture_html(repo)

    return DivanAuditMetrics(
        total_events=len(events),
        attribution_site=dict(attribution_site_counter),
        attribution=dict(attribution_counter),
        evidence_type=dict(evidence_type_counter),
        publishable_events=publishable,
        multi_venue_events=multi_venue,
        fixture_sha256=info["sha256"],
        fixture_raw_bytes=info["raw_bytes"],
        fixture_gz_bytes=info["gz_bytes"],
    )


def collect_all_metrics(repo: Path) -> AllMetrics:
    """Collect all metrics from the repository."""
    return AllMetrics(
        classification=collect_classification_metrics(repo),
        lor=collect_lor_metrics(repo),
        websites=collect_website_metrics(repo),
        source_registry=collect_source_registry_metrics(repo),
        divan_audit=collect_divan_audit_metrics(repo),
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for metrics collection.

    Takes `argv` explicitly so `kiez_atlas.cli metrics` can forward its own
    arguments without rewriting `sys.argv`, and returns a process exit code.
    """
    import argparse

    ap = argparse.ArgumentParser(prog="kiez_atlas.metrics")
    ap.add_argument("--repo", default=".", help="Repository root")
    ap.add_argument("--output", help="Output file (default: stdout)")
    ap.add_argument("--format", choices=["json", "summary"], default="json")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    metrics = collect_all_metrics(repo)

    if args.format == "summary":
        # Human-readable summary
        out_lines = [
            f"=== Kiez Events Atlas Metrics ===",
            f"Repository: {repo}",
            f"",
            f"--- Classification ---",
            f"  Total venues: {metrics.classification.total_venues}",
            f"  Product status: {metrics.classification.product_status}",
            f"  Venue types: {metrics.classification.venue_type}",
            f"  Rules fired: {metrics.classification.rule_fired}",
            f"  Community relevance: {metrics.classification.community_relevance}",
            f"",
            f"--- LOR Geography ---",
            f"  BZR regions: {metrics.lor.total_bzr}",
            f"  PLR areas: {metrics.lor.total_plr}",
            f"  Venues with LOR: {metrics.lor.venues_with_lor}",
            f"  Venues without LOR: {metrics.lor.venues_without_lor}",
            f"  Atlas/LOR agree: {metrics.lor.atlas_lor_agree}",
            f"  Atlas/LOR disagree: {metrics.lor.atlas_lor_disagree}",
            f"  Atlas/LOR outside: {metrics.lor.atlas_lor_outside}",
            f"",
            f"--- Websites ---",
            f"  Total published venues: {metrics.websites.total_venues}",
            f"  Website kinds: {metrics.websites.website_kind}",
            f"  Verification: {metrics.websites.verification_status}",
            f"  Official claims: {metrics.websites.official_claims}",
            f"",
            f"--- Source Registry ---",
            f"  Total sources: {metrics.source_registry.total_sources}",
            f"  Source status: {metrics.source_registry.source_status}",
            f"  CSV/JSON agree: {metrics.source_registry.csv_json_agree}",
            f"",
            f"--- Divan Audit ---",
            f"  Total events: {metrics.divan_audit.total_events}",
            f"  Attribution site: {metrics.divan_audit.attribution_site}",
            f"  Attribution: {metrics.divan_audit.attribution}",
            f"  Evidence type: {metrics.divan_audit.evidence_type}",
            f"  Publishable: {metrics.divan_audit.publishable_events}",
            f"  Multi-venue: {metrics.divan_audit.multi_venue_events}",
            f"  Fixture SHA256: {metrics.divan_audit.fixture_sha256[:16]}...",
        ]
        output = "\n".join(out_lines)
    else:
        output = metrics.to_json()

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
