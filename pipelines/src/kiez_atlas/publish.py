"""Build the Phase 1 public data products from the embedded Atlas data.

Outputs
    data/public/venues.json               included venues only (product_status=included)
    data/public/neighbourhoods.geojson    143 LOR Bezirksregionen
    data/public/metadata.json             versions, counts, freshness, attribution
    data/internal/venue_inventory.json    ALL 303 records, auditable, never deployed
    data/internal/classification.json     per-record rule + reason
    data/internal/review_queue.json       pending_review records with their reasons

Separation rule: `data/public/` is the only directory the site may read. The
public venue record uses additionalProperties:false in its schema, so an
internal field cannot leak into it by accident.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .classify import classify
from .extract_embedded import load_atlas, sha256_of
from .geo import LorIndex
from .vocab import COMMUNITY_RELEVANCE, EVENT_SOURCE_STATUS, PRODUCT_STATUS, VENUE_TYPES

SCHEMA_VERSION = "0.2.0"
PIPELINE_VERSION = "0.1.0"

# Attribution for the LOR geography. The inherited META.sources register does
# NOT credit it (verified: grepping META for LOR/Bezirksregion/Planungsraum
# returns zero hits). This entry is a PROPOSED correction to inherited
# attribution; it is not a change to the privacy notice, and the vintage is
# recorded as unknown rather than invented.
LOR_ATTRIBUTION = {
    "title": "Senatsverwaltung für Stadtentwicklung, Bauen und Wohnen / Amt für "
             "Statistik Berlin-Brandenburg: Lifelines of Regions (LOR) "
             "Berlin — Planungsräume (542) and Bezirksregionen (143)",
    "url": "https://www.statistik-berlin-brandenburg.de/geodata",
    "note": "Polygons inherited from the CCI Atlas build. The upstream "
            "META.sources register does not credit this layer; vintage is not "
            "recorded in the source data and is therefore stated as unknown "
            "rather than assumed. Confirm licence and vintage with the "
            "upstream controller before republication.",
    "vintage": "unknown",
    "licence": "unknown — see docs/feasibility/REPORT.md §G.4",
}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build(index_html: Path, out_root: Path) -> dict:
    atlas = load_atlas(index_html)
    places = atlas["PLACES"]
    lor = LorIndex.build(atlas["LOR_PLR"], atlas["LOR_BZR"])

    generated = _now()
    inventory: list[dict] = []
    public_venues: list[dict] = []
    classification: list[dict] = []
    review_queue: list[dict] = []

    for p in places:
        d = classify(p)
        pip_plr, pip_bzr = lor.locate(p["c"][0], p["c"][1])
        atlas_bzr = lor.bzr_of_plr(p["lor"])
        lor_agrees = pip_plr == p["lor"]

        # --- internal: full auditable inventory, all 303 ---
        inventory.append({
            "venue_id": p["id"],
            "venue_name": p["name"],
            "inherited": {
                "cat": p["cat"],
                "layer": p["layer"],
                "sectors": p["sectors"],
                "desc": p["desc"],
                "address": p["address"],
                "plz": p["plz"],
                "url": p["url"],
                "flag": p["flag"],
                "district": p["d"],
                "lor_plr": p["lor"],
                "coords": p["c"],
                "coordinate_precision": p["prec"],
                "distance_green_m": p["dg"],
                "distance_water_m": p["dw"],
            },
            "provenance": {"source_reference": p["src"]},
            "classification": {
                "venue_type": d.venue_type,
                "community_relevance": d.community_relevance,
                "product_status": d.product_status,
                "rule": d.rule,
                "reason": d.reason,
            },
            "event_source_status": "not_assessed",
            "geography": {
                "atlas_lor_plr": p["lor"],
                "atlas_lor_bzr": atlas_bzr,
                "atlas_lor_bzr_name": lor.plr_by_id.get(p["lor"], {}).get("bzr"),
                "pip_lor_plr": pip_plr,
                "pip_lor_bzr": pip_bzr,
                "lor_agrees_with_atlas": lor_agrees,
            },
        })

        # --- internal: rule trace ---
        classification.append({
            "venue_id": p["id"],
            "venue_name": p["name"],
            "inherited_cat": p["cat"],
            "venue_type": d.venue_type,
            "product_status": d.product_status,
            "rule": d.rule,
            "reason": d.reason,
        })

        if d.product_status == "pending_review":
            review_queue.append({
                "venue_id": p["id"],
                "venue_name": p["name"],
                "inherited_cat": p["cat"],
                "venue_type": d.venue_type,
                "rule": d.rule,
                "reason": d.reason,
                "website": p["url"],
                "address": p["address"],
            })

        # --- public: included venues only, minimal fields ---
        if d.product_status == "included":
            bzr_id = pip_bzr or atlas_bzr
            public_venues.append({
                "schema_version": SCHEMA_VERSION,
                "venue_id": p["id"],
                "venue_name": p["name"],
                "venue_type": d.venue_type,
                "community_relevance": d.community_relevance,
                "latitude": p["c"][1],
                "longitude": p["c"][0],
                "address": p["address"],
                "plz": p["plz"],
                "district": p["d"],
                "lor_id": bzr_id,
                "lor_name": lor.bzr_by_id.get(bzr_id, {}).get("name") if bzr_id else None,
                "lor_plr_id": pip_plr or p["lor"],
                "coordinate_precision": p["prec"],
                "website": p["url"],
                "atlas_provenance": {
                    "source_reference": p["src"],
                    "atlas_category": p["cat"],
                    "atlas_layer": p["layer"],
                },
            })

    # --- neighbourhoods.geojson ---
    venue_counts: dict[str, int] = {}
    for v in public_venues:
        if v["lor_id"]:
            venue_counts[v["lor_id"]] = venue_counts.get(v["lor_id"], 0) + 1

    features = []
    for f in lor.bzr_features:
        props = f["properties"]
        features.append({
            "type": "Feature",
            "properties": {
                "schema_version": SCHEMA_VERSION,
                "lor_id": props["id"],
                "lor_name": props["name"],
                "district": props["district"],
                "venue_count": venue_counts.get(props["id"], 0),
            },
            "geometry": f["geometry"],
        })
    neighbourhoods = {
        "type": "FeatureCollection",
        "name": "bezirksregionen",
        "crs": {"type": "name",
                "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "features": features,
    }

    # --- metadata ---
    statuses = [c["product_status"] for c in classification]
    types: dict[str, int] = {}
    for c in classification:
        types[c["venue_type"]] = types.get(c["venue_type"], 0) + 1

    metadata = {
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": PIPELINE_VERSION,
        "generated_at": generated,
        "source": {
            "repository": "JsonLord/berlin-cci-atlas",
            "upstream": "kaitiwu/berlin-cci-atlas",
            "extracted_from": "index.html window.ATLAS.PLACES",
            "index_html_sha256": sha256_of(index_html),
            "atlas_data_checked": atlas.get("META", {}).get("checked"),
        },
        "counts": {
            "original_records": len(places),
            "included": statuses.count("included"),
            "excluded": statuses.count("excluded"),
            "pending_review": statuses.count("pending_review"),
            "public_venues": len(public_venues),
            "bezirksregionen": len(features),
            "bezirksregionen_with_venues": len(venue_counts),
            "planning_raeume": len(lor.plr_features),
        },
        "venue_type_distribution": dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        "geography": {
            "model": "Berlin LOR Bezirksregionen (primary) / Planungsräume (detail)",
            "join_key": "lor_id",
            "warning": "Bezirksregion names are not unique (e.g. 'Heerstraße' is "
                       "both 042002 and 052005). Always join on lor_id, never on name.",
            "duplicate_bzr_names": lor.duplicate_bzr_names(),
            "lor_agrees_with_atlas": sum(
                1 for i in inventory if i["geography"]["lor_agrees_with_atlas"]),
            "lor_disagreements": [
                {"venue_id": i["venue_id"],
                 "atlas_lor_plr": i["geography"]["atlas_lor_plr"],
                 "pip_lor_plr": i["geography"]["pip_lor_plr"]}
                for i in inventory if not i["geography"]["lor_agrees_with_atlas"]],
        },
        "attribution": {
            "inherited_register": atlas.get("META", {}).get("sources", []),
            "added_by_this_pipeline": [LOR_ATTRIBUTION],
        },
        "vocabularies": {
            "venue_type": VENUE_TYPES,
            "community_relevance": COMMUNITY_RELEVANCE,
            "product_status": PRODUCT_STATUS,
            "event_source_status": EVENT_SOURCE_STATUS,
        },
        "not_public": ["data/internal/venue_inventory.json",
                       "data/internal/classification.json",
                       "data/internal/review_queue.json"],
    }

    pub = out_root / "public"
    internal = out_root / "internal"
    pub.mkdir(parents=True, exist_ok=True)
    internal.mkdir(parents=True, exist_ok=True)

    def dump(path: Path, obj) -> None:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n",
                        encoding="utf-8")

    dump(pub / "venues.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated,
        "count": len(public_venues),
        "venues": public_venues,
    })
    dump(pub / "neighbourhoods.geojson", neighbourhoods)
    dump(pub / "metadata.json", metadata)
    dump(internal / "venue_inventory.json", {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated,
        "notice": "INTERNAL. Operational and editorial working data. Not deployed.",
        "count": len(inventory),
        "venues": inventory,
    })
    dump(internal / "classification.json", {
        "generated_at": generated,
        "count": len(classification),
        "records": classification,
    })
    dump(internal / "review_queue.json", {
        "generated_at": generated,
        "count": len(review_queue),
        "notice": "Physical venues whose community relevance the rules could not "
                  "settle. A human decides; do not resolve by rule.",
        "venues": review_queue,
    })

    return metadata
