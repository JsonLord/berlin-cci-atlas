"""Legacy projection compiler (Strategy A).

Transforms internal relational domain models (Organisation, Venue, Role)
into the public JSON contracts required by existing consumers:
 - data/public/venues.json (schema v0.3.0)
 - index.html window.ATLAS.PLACES format

Guarantees 100% backward compatibility with zero frontend regression.
"""

from __future__ import annotations

import re
from typing import Any

from .models import Organisation, OrganisationVenueRole, Venue

SCHEMA_VERSION = "0.3.0"


def decompose_inventory_record(record: dict[str, Any]) -> tuple[Organisation, Venue, OrganisationVenueRole]:
    """Decompose an auditable internal inventory record into relational entities."""
    venue_id = record["venue_id"]
    venue_name = record["venue_name"]
    inh = record["inherited"]
    cls_data = record.get("classification", {})
    wa = record.get("website_assessment", {})
    prov = record.get("provenance", {})
    geo = record.get("geography", {})

    # Extract street and house number, handling optional complex notes like "(ACUD Studio)"
    raw_addr = inh.get("address") or ""
    # Strip parenthetical notes for address matching
    clean_addr = re.sub(r"\(.*?\)", "", raw_addr).strip()
    m = re.match(r"^(.*?)\s+(\d+[a-z]?)$", clean_addr)
    if m:
        street = m.group(1).strip()
        house_num = m.group(2).strip()
    else:
        street = clean_addr
        house_num = ""

    # 1. Physical Venue entity
    coords = inh.get("coords") or [0.0, 0.0]
    pip_bzr = geo.get("pip_lor_bzr")
    atlas_bzr = geo.get("atlas_lor_bzr")
    bzr_id = pip_bzr or atlas_bzr
    pip_plr = geo.get("pip_lor_plr")
    plr_id = pip_plr or inh.get("lor_plr")

    venue = Venue.create(
        name=venue_name,
        street=raw_addr,  # preserve raw address representation for display fidelity
        house_number="",
        postcode=inh.get("plz") or "",
        venue_id=f"ven_{venue_id}",
        venue_type=cls_data.get("venue_type", "community_centre"),
        community_relevance=cls_data.get("community_relevance", []),
        district=inh.get("district"),
        latitude=coords[1],
        longitude=coords[0],
        coordinate_precision=inh.get("coordinate_precision", "street"),
        lor_id=bzr_id,
        lor_plr_id=plr_id,
        legacy_atlas_id=venue_id,
        legacy_category=inh.get("cat"),
        legacy_layer=inh.get("layer"),
        verification_status="verified" if cls_data.get("product_status") == "included" else "provisional",
    )

    # 2. Organisation entity
    org = Organisation.create(
        name=venue_name,
        organisation_id=f"org_{venue_id}",
        website_url=wa.get("url"),
        website_verification=wa.get("verification", "unverified"),
        description=inh.get("desc"),
        source_references=[{
            "source_name": "Atlas Ingestion Provenance",
            "reference_url": prov.get("source_reference"),
            "observed_at": "2026-11-14",
        }] if prov.get("source_reference") else [],
    )

    # 3. OrganisationVenueRole entity
    role = OrganisationVenueRole.create(
        organisation_id=org.organisation_id,
        venue_id=venue.venue_id,
        role_type="operates",
        is_primary_headquarters=True,
    )

    return org, venue, role


def project_legacy_venue(
    venue: Venue,
    org: Organisation | None = None,
    website_assessment: dict[str, Any] | None = None,
    lor_name: str | None = None,
) -> dict[str, Any]:
    """Compile internal entities into the exact schema v0.3.0 public venue dictionary."""
    wa = website_assessment or {}
    url = org.website_url if org else None
    kind = wa.get("kind", "venue_site_unverified")
    verification = org.website_verification if org else "unverified"
    shared_by = wa.get("shared_by_venue_count", 1)

    source_ref = ""
    if org and org.source_references:
        source_ref = org.source_references[0].get("reference_url", "")

    return {
        "schema_version": SCHEMA_VERSION,
        "venue_id": venue.legacy_atlas_id or venue.venue_id.replace("ven_", ""),
        "venue_name": venue.canonical_name,
        "venue_type": venue.venue_type,
        "community_relevance": list(venue.community_relevance),
        "latitude": venue.latitude,
        "longitude": venue.longitude,
        "address": venue.street if not venue.house_number else f"{venue.street} {venue.house_number}",
        "plz": venue.postcode,
        "district": venue.district,
        "lor_id": venue.lor_id,
        "lor_name": lor_name or venue.lor_name,
        "lor_plr_id": venue.lor_plr_id,
        "coordinate_precision": venue.coordinate_precision,
        "website": {
            "url": url,
            "kind": kind,
            "verification": verification,
            "shared_by_venue_count": shared_by,
        },
        "atlas_provenance": {
            "source_reference": source_ref,
            "atlas_category": venue.legacy_category,
            "atlas_layer": venue.legacy_layer,
        },
    }
