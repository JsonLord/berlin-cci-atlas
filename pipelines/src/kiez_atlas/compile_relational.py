"""Compile internal relational entities from the Phase 1 inventory.

Outputs:
 - data/canonical/organisations.json
 - data/canonical/venues.json
 - data/canonical/organisation_venue_roles.json

Adds Nehringstraße 26 as an explicit physical venue linked to
Nachbarschaftszentrum Divan e.V.
"""

from __future__ import annotations

import json
from pathlib import Path

from .models import Organisation, OrganisationVenueRole, Venue
from .projection import decompose_inventory_record


def compile_relational_entities(repo: Path) -> dict[str, int]:
    inv_path = repo / "data" / "internal" / "venue_inventory.json"
    inventory = json.loads(inv_path.read_text(encoding="utf-8"))

    organisations: dict[str, dict] = {}
    venues: dict[str, dict] = {}
    roles: dict[str, dict] = {}

    for record in inventory["venues"]:
        org, venue, role = decompose_inventory_record(record)
        organisations[org.organisation_id] = org.to_dict()
        venues[venue.venue_id] = venue.to_dict()
        roles[role.role_id] = role.to_dict()

    # --- Add Divan Sibling Building (Nehringstr. 26) ---
    # Divan operates two physical buildings. Adding the second building solves the
    # long-standing audit finding: 36 events take place here, and without a venue
    # entity they can never be placed or shown.
    divan_v2 = Venue.create(
        name="Divan Mehrgenerationenhaus (Nehringstr. 26)",
        street="Nehringstraße",
        house_number="26",
        postcode="14059",
        venue_id="ven_divan_nehring_26",
        venue_type="community_centre",
        community_relevance=["open_access", "public_events", "learning"],
        district="Charlottenburg-Wilmersdorf",
        latitude=52.51821,
        longitude=13.29412,
        coordinate_precision="exact_building",
        lor_id="043004",
        lor_name="Schloss Charlottenburg",
        lor_plr_id="04300413",
        has_map_marker=True,
        legacy_atlas_id=None,
        legacy_category="community",
        legacy_layer="social",
        verification_status="verified",
    )
    venues[divan_v2.venue_id] = divan_v2.to_dict()

    # Link to the Divan organisation
    divan_org_id = "org_interkulturelles-stadtteilzentrum-divan"
    divan_v2_role = OrganisationVenueRole.create(
        organisation_id=divan_org_id,
        venue_id=divan_v2.venue_id,
        role_type="operates",
        is_primary_headquarters=False,
        evidence_description="Second physical site operated by Divan (Mehrgenerationenhaus).",
    )
    roles[divan_v2_role.role_id] = divan_v2_role.to_dict()

    # Write out canonical internal files
    canonical_dir = repo / "data" / "canonical"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    
    org_list = list(organisations.values())
    ven_list = list(venues.values())
    role_list = list(roles.values())

    (canonical_dir / "organisations.json").write_text(
        json.dumps({"schema_version": "0.4.0", "count": len(org_list), "organisations": org_list}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (canonical_dir / "venues.json").write_text(
        json.dumps({"schema_version": "0.4.0", "count": len(ven_list), "venues": ven_list}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (canonical_dir / "organisation_venue_roles.json").write_text(
        json.dumps({"schema_version": "0.4.0", "count": len(role_list), "roles": role_list}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    return {
        "organisations": len(org_list),
        "venues": len(ven_list),
        "roles": len(role_list),
    }


if __name__ == "__main__":
    import sys
    root = Path(__file__).resolve().parents[3]
    counts = compile_relational_entities(root)
    print(f"Compiled relational entities: {counts}")
