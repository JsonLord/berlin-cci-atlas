"""Tests for the legacy projection compiler (Strategy A)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from kiez_atlas.projection import decompose_inventory_record, project_legacy_venue

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "data" / "internal" / "venue_inventory.json"
PUBLIC_VENUES_PATH = REPO_ROOT / "data" / "public" / "venues.json"
SCHEMA_PATH = REPO_ROOT / "docs" / "feasibility" / "artifacts" / "venue.schema.json"


class TestProjectionCompiler(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        cls.public_data = json.loads(PUBLIC_VENUES_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_decompose_and_project_single_venue(self):
        divan_inv = next(
            v for v in self.inventory["venues"]
            if v["venue_id"] == "interkulturelles-stadtteilzentrum-divan"
        )
        org, venue, role = decompose_inventory_record(divan_inv)

        self.assertEqual("org_interkulturelles-stadtteilzentrum-divan", org.organisation_id)
        self.assertEqual("ven_interkulturelles-stadtteilzentrum-divan", venue.venue_id)
        self.assertEqual("interkulturelles-stadtteilzentrum-divan", venue.legacy_atlas_id)
        self.assertEqual("ovr_org_interkulturelles-stadtteilzentrum-divan_ven_interkulturelles-stadtteilzentrum-divan_operates", role.role_id)

        divan_pub = next(
            v for v in self.public_data["venues"]
            if v["venue_id"] == "interkulturelles-stadtteilzentrum-divan"
        )
        projected = project_legacy_venue(
            venue,
            org,
            website_assessment=divan_inv.get("website_assessment"),
            lor_name=divan_pub.get("lor_name"),
        )

        self.assertFalse(list(self.validator.iter_errors(projected)))
        self.assertEqual(divan_pub["venue_id"], projected["venue_id"])
        self.assertEqual(divan_pub["venue_name"], projected["venue_name"])
        self.assertEqual(divan_pub["latitude"], projected["latitude"])
        self.assertEqual(divan_pub["longitude"], projected["longitude"])
        self.assertEqual(divan_pub["address"], projected["address"])
        self.assertEqual(divan_pub["lor_id"], projected["lor_id"])

    def test_all_251_included_venues_project_to_valid_v030_schema(self):
        pub_by_id = {v["venue_id"]: v for v in self.public_data["venues"]}
        included_inv = [
            v for v in self.inventory["venues"]
            if v["venue_id"] in pub_by_id
        ]
        self.assertEqual(251, len(included_inv))

        for inv in included_inv:
            org, venue, role = decompose_inventory_record(inv)
            pub = pub_by_id[inv["venue_id"]]
            projected = project_legacy_venue(
                venue,
                org,
                website_assessment=inv.get("website_assessment"),
                lor_name=pub.get("lor_name"),
            )
            errors = list(self.validator.iter_errors(projected))
            self.assertEqual([], errors, f"Validation failed for {inv['venue_id']}: {errors}")
            self.assertEqual(pub["venue_id"], projected["venue_id"])
            self.assertEqual(pub["address"], projected["address"])
            self.assertEqual(pub["lor_id"], projected["lor_id"])


if __name__ == "__main__":
    unittest.main()
