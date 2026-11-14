"""Post-build validation. Every check is a hard assertion, not a warning.

The most important check is the last one: index.html must be byte-identical to
the committed blob. This pipeline is read-only with respect to the inherited
application, and that claim must be machine-enforced rather than promised.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import jsonschema

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "docs" / "feasibility" / "artifacts"


class Check:
    def __init__(self) -> None:
        self.results: list[tuple[str, bool, str]] = []

    def add(self, name: str, ok: bool, detail: str = "") -> None:
        self.results.append((name, bool(ok), detail))

    @property
    def failed(self) -> list[tuple[str, bool, str]]:
        return [r for r in self.results if not r[1]]


def _load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def run(repo: Path) -> Check:
    c = Check()
    pub = repo / "data" / "public"
    internal = repo / "data" / "internal"

    venues = _load(pub / "venues.json")
    neighbourhoods = _load(pub / "neighbourhoods.geojson")
    metadata = _load(pub / "metadata.json")
    inventory = _load(internal / "venue_inventory.json")
    classification = _load(internal / "classification.json")
    review = _load(internal / "review_queue.json")

    # ---- schemas ----
    vschema = _load(SCHEMA_DIR / "venue.schema.json")
    ischema = _load(SCHEMA_DIR / "venue_inventory.schema.json")
    VV = jsonschema.Draft202012Validator(vschema)
    IV = jsonschema.Draft202012Validator(ischema)

    vbad = [e for v in venues["venues"] for e in VV.iter_errors(v)]
    c.add("public venues validate against venue.schema.json",
          not vbad, f"{len(venues['venues'])} records, {len(vbad)} errors"
          + (f"; first: {vbad[0].message}" if vbad else ""))

    ibad = [v for v in inventory["venues"] for e in IV.iter_errors(v)]
    c.add("internal inventory validates against venue_inventory.schema.json",
          not ibad, f"{len(inventory['venues'])} records, {len(ibad)} errors"
          + (f"; first: {ibad[0].message}" if ibad else ""))

    # ---- completeness ----
    c.add("all 303 original records preserved in the internal inventory",
          inventory["count"] == 303, f"count={inventory['count']}")
    c.add("classification trace covers every record",
          classification["count"] == 303, f"count={classification['count']}")
    c.add("statuses partition exactly",
          metadata["counts"]["included"] + metadata["counts"]["excluded"]
          + metadata["counts"]["pending_review"] == 303,
          str(metadata["counts"]))
    c.add("public venue count equals included count",
          venues["count"] == metadata["counts"]["included"] == len(venues["venues"]),
          f"{venues['count']} vs {metadata['counts']['included']}")
    c.add("review queue length equals pending_review count",
          review["count"] == metadata["counts"]["pending_review"],
          f"{review['count']} vs {metadata['counts']['pending_review']}")

    # ---- provenance ----
    prov_missing = [v["venue_id"] for v in inventory["venues"]
                    if not v["provenance"]["source_reference"]]
    c.add("every inventory record keeps atlas provenance",
          not prov_missing, f"{len(prov_missing)} missing")

    # inherited fields must be byte-equal to what index.html ships
    import sys
    sys.path.insert(0, str(repo / "pipelines" / "src"))
    from kiez_atlas.extract_embedded import load_atlas
    orig = {p["id"]: p for p in load_atlas(repo / "index.html")["PLACES"]}
    drift = []
    for v in inventory["venues"]:
        o = orig[v["venue_id"]]
        inh = v["inherited"]
        if (inh["cat"] != o["cat"] or inh["layer"] != o["layer"]
                or inh["desc"] != o["desc"] or inh["address"] != o["address"]
                or inh["url"] != o["url"] or inh["flag"] != o["flag"]
                or inh["lor_plr"] != o["lor"] or inh["coords"] != o["c"]
                or inh["sectors"] != o["sectors"] or inh["plz"] != o["plz"]
                or inh["district"] != o["d"]
                or v["provenance"]["source_reference"] != o["src"]):
            drift.append(v["venue_id"])
    c.add("inherited fields are unmodified copies of the source records",
          not drift, f"{len(drift)} drifted" + (f"; e.g. {drift[:3]}" if drift else ""))

    # ---- geography ----
    bzr_ids = {f["properties"]["lor_id"] for f in neighbourhoods["features"]}
    c.add("neighbourhoods.geojson has 143 unique Bezirksregionen",
          len(neighbourhoods["features"]) == 143 and len(bzr_ids) == 143,
          f"{len(neighbourhoods['features'])} features, {len(bzr_ids)} unique ids")
    orphans = [v["venue_id"] for v in venues["venues"]
               if v["lor_id"] and v["lor_id"] not in bzr_ids]
    c.add("every public venue lor_id resolves in neighbourhoods.geojson",
          not orphans, f"{len(orphans)} unresolved")
    badfmt = [v["venue_id"] for v in venues["venues"]
              if v["lor_id"] and (len(v["lor_id"]) != 6 or not v["lor_id"].isdigit())]
    c.add("every public venue lor_id is a 6-digit Bezirksregion id",
          not badfmt, f"{len(badfmt)} malformed")

    # the Heerstraße trap must be visible in metadata
    dupes = metadata["geography"]["duplicate_bzr_names"]
    c.add("metadata exposes non-unique Bezirksregion names (join-on-id guard)",
          "Heerstraße" in dupes and len(dupes["Heerstraße"]) == 2, str(dupes))

    # ---- classification integrity ----
    statuses = {v["venue_id"]: v["classification"]["product_status"]
                for v in inventory["venues"]}
    c.add("no record is included and excluded at once (unique status per id)",
          len(statuses) == 303, f"{len(statuses)} unique ids")

    # event_source_status must NOT be derived from product_status
    ess = {v["event_source_status"] for v in inventory["venues"]}
    c.add("event_source_status is independent (all records not_assessed at Phase 1)",
          ess == {"not_assessed"}, str(ess))

    # every decision names a rule and a substantive reason
    norule = [v["venue_id"] for v in inventory["venues"]
              if not v["classification"]["rule"]
              or len(v["classification"]["reason"]) < 20]
    c.add("every classification names its rule and gives a reason",
          not norule, f"{len(norule)} without")

    # vocab integrity: types/relevance must exist in the registries
    from kiez_atlas import vocab
    unknown_type = [v["venue_id"] for v in inventory["venues"]
                    if v["classification"]["venue_type"] not in vocab.VENUE_TYPES]
    unknown_rel = [v["venue_id"] for v in inventory["venues"]
                   for r in v["classification"]["community_relevance"]
                   if r not in vocab.COMMUNITY_RELEVANCE]
    c.add("all venue_type values exist in the vocabulary",
          not unknown_type, f"{len(unknown_type)} unknown")
    c.add("all community_relevance values exist in the vocabulary",
          not unknown_rel, f"{len(unknown_rel)} unknown")

    # public output must carry no internal keys
    leaked = []
    internal_keys = {"rule", "reason", "product_status", "event_source_status",
                     "classification", "inherited", "geography", "flag", "sectors",
                     "distance_green_m", "distance_water_m", "coordinate_quality"}
    for v in venues["venues"]:
        leaked += [k for k in v if k in internal_keys]
    c.add("public venues.json contains no internal classification fields",
          not leaked, f"{len(set(leaked))} leaked keys: {sorted(set(leaked))}")

    # ---- website honesty ----
    official = [v["venue_id"] for v in venues["venues"]
                if v["website"]["verification"] == "verified_official"]
    c.add("no public venue claims a verified official website",
          not official, f"{len(official)} claims")

    bad_kind = [v["venue_id"] for v in venues["venues"]
                if v["website"]["kind"] not in ("directory_reference",
                                                "shared_organisation_site",
                                                "venue_site_unverified")]
    c.add("every public website kind is a known value", not bad_kind,
          f"{len(bad_kind)} unknown")

    shared_mislabelled = [v["venue_id"] for v in venues["venues"]
                          if v["website"]["shared_by_venue_count"] > 1
                          and v["website"]["kind"] == "venue_site_unverified"]
    c.add("no shared URL is labelled as a venue's own site",
          not shared_mislabelled, f"{len(shared_mislabelled)} mislabelled")

    inherited_urls = {p["url"] for p in load_atlas(repo / "index.html")["PLACES"]}
    invented = [v["venue_id"] for v in venues["venues"]
                if v["website"]["url"] is not None
                and v["website"]["url"] not in inherited_urls]
    c.add("every published website URL exists in the inherited data",
          not invented, f"{len(invented)} invented")

    c.add("metadata declares zero official-website claims",
          metadata.get("websites", {}).get("official_claims") == 0,
          str(metadata.get("websites", {}).get("official_claims")))

    # ---- LOR attribution must stay provisional ----
    lor_entries = [a for a in metadata["attribution"]["added_by_this_pipeline"]
                   if "LOR" in a["title"]]
    c.add("exactly one provisional LOR attribution entry", len(lor_entries) == 1,
          f"{len(lor_entries)} entries")
    if lor_entries:
        e = lor_entries[0]
        c.add("LOR attribution is marked provisional",
              e.get("status") == "provisional", str(e.get("status")))
        c.add("LOR vintage and licence are recorded as unknown",
              e.get("vintage") == "unknown" and "unknown" in e.get("licence", ""),
              f"vintage={e.get('vintage')}")
        c.add("LOR attribution blocks publication until confirmed",
              e.get("blocks_publication") is True, str(e.get("blocks_publication")))
    c.add("metadata lists the LOR publication blocker",
          any("LOR" in b for b in metadata["attribution"].get("publication_blockers", [])),
          "")

    # ---- deploy boundary is executable, not advisory ----
    from kiez_atlas.deploy import (DeployBoundaryError, assert_no_internal_leak,
                                   resolve_deploy_set)
    try:
        files = resolve_deploy_set(repo)
        rels = [f.relative_to(repo.resolve()).as_posix() for f in files]
        c.add("deploy set resolves to real files", bool(files), f"{len(files)} files")
        c.add("deploy set contains no internal path",
              not [r for r in rels if r.startswith("data/internal/")], str(rels))
    except DeployBoundaryError as e:
        c.add("deploy set resolves to real files", False, str(e)[:150])
    try:
        assert_no_internal_leak(repo / "data" / "public")
        c.add("staging data/public passes the leak check", True, "")
    except DeployBoundaryError as e:
        c.add("staging data/public passes the leak check", False, str(e)[:150])
    try:
        assert_no_internal_leak(repo / "data")
        c.add("staging all of data/ is refused (leak check works)", False,
              "no error raised — the guard is not firing")
    except DeployBoundaryError:
        c.add("staging all of data/ is refused (leak check works)", True, "")

    # ---- deploy allowlist ----
    allow = repo / "data" / "deploy-allowlist.txt"
    if allow.exists():
        paths = [ln.strip() for ln in allow.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
        internal_leaks = [p for p in paths if "internal" in p]
        c.add("deploy allowlist contains no internal paths",
              not internal_leaks, f"{len(paths)} entries; leaks={internal_leaks}")
        listed = set(paths)
        for f in ("venues.json", "neighbourhoods.geojson", "metadata.json"):
            c.add(f"deploy allowlist publishes data/public/{f}",
                  f"data/public/{f}" in listed, f"listed={f'data/public/{f}' in listed}")
        # every internal artefact must be absent from the allowlist
        for f in ("venue_inventory.json", "classification.json", "review_queue.json"):
            c.add(f"deploy allowlist excludes data/internal/{f}",
                  f"data/internal/{f}" not in listed, "")
    else:
        c.add("deploy allowlist exists", False, "data/deploy-allowlist.txt missing")

    # ---- the read-only guarantee ----
    try:
        committed = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD:index.html"],
            capture_output=True, text=True, check=True).stdout.strip()
        actual = subprocess.run(
            ["git", "-C", str(repo), "hash-object", "index.html"],
            capture_output=True, text=True, check=True).stdout.strip()
        c.add("index.html is byte-identical to the committed blob (read-only pipeline)",
              committed == actual, f"committed={committed[:12]} actual={actual[:12]}")
    except subprocess.CalledProcessError as e:
        c.add("index.html integrity check ran", False, str(e)[:120])

    return c
