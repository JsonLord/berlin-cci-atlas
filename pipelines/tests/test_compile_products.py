"""Tests for Phase 3 compilation pipelines (relational entities and public events)."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import jsonschema

from kiez_atlas.compile_events import compile_events
from kiez_atlas.compile_relational import compile_relational_entities

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "docs" / "feasibility" / "artifacts" / "event.schema.json"


class TestCompileRelationalEntities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.counts = compile_relational_entities(REPO_ROOT)
        cls.orgs = json.loads((REPO_ROOT / "data" / "canonical" / "organisations.json").read_text(encoding="utf-8"))
        cls.venues = json.loads((REPO_ROOT / "data" / "canonical" / "venues.json").read_text(encoding="utf-8"))
        cls.roles = json.loads((REPO_ROOT / "data" / "canonical" / "organisation_venue_roles.json").read_text(encoding="utf-8"))

    def test_entity_counts(self):
        self.assertEqual(303, self.counts["organisations"])
        self.assertEqual(304, self.counts["venues"])  # 303 original + Divan Nehringstr. 26
        self.assertEqual(304, self.counts["roles"])

    def test_divan_building_2_is_registered(self):
        v2 = next((v for v in self.venues["venues"] if v["venue_id"] == "ven_divan_nehring_26"), None)
        self.assertIsNotNone(v2, "ven_divan_nehring_26 missing from canonical venues.json")
        self.assertEqual("Nehringstraße", v2["street"])
        self.assertEqual("26", v2["house_number"])
        self.assertEqual("14059", v2["postcode"])
        self.assertEqual("043004", v2["lor_id"])
        self.assertEqual("04300413", v2["lor_plr_id"])
        self.assertTrue(v2["has_map_marker"])

    def test_divan_operates_both_buildings(self):
        divan_roles = [
            r for r in self.roles["roles"]
            if r["organisation_id"] == "org_interkulturelles-stadtteilzentrum-divan"
        ]
        self.assertEqual(2, len(divan_roles))
        venues_operated = {r["venue_id"] for r in divan_roles}
        self.assertIn("ven_interkulturelles-stadtteilzentrum-divan", venues_operated)
        self.assertIn("ven_divan_nehring_26", venues_operated)


class TestCompileEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = compile_events(REPO_ROOT)
        cls.pub_events = json.loads((REPO_ROOT / "data" / "public" / "events.json").read_text(encoding="utf-8"))
        cls.series = json.loads((REPO_ROOT / "data" / "canonical" / "event_series.json").read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_total_event_counts_and_breakdown(self):
        self.assertEqual(237, self.result["total_publishable_events"])
        counts = self.result["counts_by_venue"]
        self.assertEqual(175, counts["interkulturelles-stadtteilzentrum-divan"])
        self.assertEqual(36, counts["ven_divan_nehring_26"])
        self.assertEqual(26, counts["lettretage"])

    def test_all_public_events_validate_against_schema(self):
        events = self.pub_events["events"]
        self.assertEqual(237, len(events))
        errors = [err.message for ev in events for err in self.validator.iter_errors(ev)]
        self.assertEqual([], errors, f"Event validation errors: {errors[:3]}")

    def test_timezones_are_strictly_europe_berlin(self):
        for ev in self.pub_events["events"]:
            self.assertEqual("Europe/Berlin", ev["timezone"])

    def test_distinct_series_grouped(self):
        self.assertEqual(82, self.result["distinct_series"])
        self.assertEqual(82, self.series["count"])


if __name__ == "__main__":
    unittest.main()
