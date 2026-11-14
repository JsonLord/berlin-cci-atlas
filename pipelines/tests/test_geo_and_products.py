"""Geography and built-product tests."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipelines" / "src"))

from kiez_atlas.extract_embedded import load_atlas   # noqa: E402
from kiez_atlas.geo import LorIndex                  # noqa: E402

ATLAS = load_atlas(REPO / "index.html")
LOR = LorIndex.build(ATLAS["LOR_PLR"], ATLAS["LOR_BZR"])
PUB = REPO / "data" / "public"
INTERNAL = REPO / "data" / "internal"


class TestLorGeography(unittest.TestCase):
    def test_counts_match_official_lor(self):
        self.assertEqual(143, len(LOR.bzr_features))
        self.assertEqual(542, len(LOR.plr_features))

    def test_all_geometries_valid(self):
        self.assertTrue(all(g.is_valid for g in LOR._plr_geoms))
        self.assertTrue(all(g.is_valid for g in LOR._bzr_geoms))

    def test_plr_prefix_is_always_a_real_bzr_id(self):
        for f in LOR.plr_features:
            self.assertIn(f["properties"]["id"][:6], LOR.bzr_by_id)

    def test_bzr_names_are_not_unique(self):
        """The join-on-id guard. If someone later joins on name, this breaks."""
        dupes = LOR.duplicate_bzr_names()
        self.assertIn("Heerstraße", dupes)
        self.assertEqual({"042002", "052005"}, set(dupes["Heerstraße"]))

    def test_locate_returns_plr_and_bzr(self):
        plr, bzr = LOR.locate(13.41245, 52.51708)   # Kreativ Kultur Berlin
        self.assertEqual("01100310", plr)
        self.assertEqual("011003", bzr)

    def test_locate_outside_returns_none(self):
        plr, bzr = LOR.locate(13.9, 52.9)
        self.assertIsNone(plr)
        self.assertIsNone(bzr)

    def test_known_atlas_disagreements_are_stable(self):
        """7 mismatch + 1 outside was measured, not assumed. Pin it so a future
        change to the polygons or the classifier is noticed."""
        agree = disagree = outside = 0
        for p in ATLAS["PLACES"]:
            plr, _ = LOR.locate(p["c"][0], p["c"][1])
            if plr is None:
                outside += 1
            elif plr == p["lor"]:
                agree += 1
            else:
                disagree += 1
        self.assertEqual(295, agree)
        self.assertEqual(7, disagree)
        self.assertEqual(1, outside)


class TestBuiltProducts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.venues = json.loads((PUB / "venues.json").read_text(encoding="utf-8"))
        cls.meta = json.loads((PUB / "metadata.json").read_text(encoding="utf-8"))
        cls.neigh = json.loads((PUB / "neighbourhoods.geojson").read_text(encoding="utf-8"))
        cls.inv = json.loads((INTERNAL / "venue_inventory.json").read_text(encoding="utf-8"))
        cls.review = json.loads((INTERNAL / "review_queue.json").read_text(encoding="utf-8"))

    def test_public_files_exist(self):
        for f in ("venues.json", "neighbourhoods.geojson", "metadata.json"):
            self.assertTrue((PUB / f).exists(), f)

    def test_internal_files_exist_and_are_declared_not_public(self):
        for f in ("venue_inventory.json", "classification.json", "review_queue.json"):
            self.assertTrue((INTERNAL / f).exists(), f)
        self.assertEqual(3, len(self.meta["not_public"]))

    def test_original_record_count_is_preserved(self):
        self.assertEqual(303, self.inv["count"])
        self.assertEqual(303, self.meta["counts"]["original_records"])

    def test_public_output_is_the_included_subset(self):
        included = {v["venue_id"] for v in self.inv["venues"]
                    if v["classification"]["product_status"] == "included"}
        self.assertEqual(included, {v["venue_id"] for v in self.venues["venues"]})

    def test_excluded_and_review_records_are_still_in_the_inventory(self):
        """Decision: preserve all 303 in an auditable inventory."""
        st = {v["classification"]["product_status"] for v in self.inv["venues"]}
        self.assertEqual({"included", "excluded", "pending_review"}, st)

    def test_review_queue_matches_inventory(self):
        q = {v["venue_id"] for v in self.review["venues"]}
        inv = {v["venue_id"] for v in self.inv["venues"]
               if v["classification"]["product_status"] == "pending_review"}
        self.assertEqual(inv, q)

    def test_no_venue_is_included_because_of_its_event_source(self):
        """Decision: directory membership is independent of source status."""
        self.assertEqual({"not_assessed"},
                         {v["event_source_status"] for v in self.inv["venues"]})

    def test_lor_attribution_is_recorded(self):
        added = self.meta["attribution"]["added_by_this_pipeline"]
        self.assertEqual(1, len(added))
        self.assertIn("LOR", added[0]["title"])
        self.assertEqual("unknown", added[0]["vintage"])

    def test_inherited_attribution_register_is_carried_through(self):
        self.assertEqual(7, len(self.meta["attribution"]["inherited_register"]))

    def test_metadata_records_source_integrity(self):
        self.assertEqual(64, len(self.meta["source"]["index_html_sha256"]))

    def test_geojson_crs_is_wgs84(self):
        self.assertIn("CRS84", json.dumps(self.neigh["crs"]))

    def test_venue_counts_present_per_bezirksregion(self):
        total = sum(f["properties"]["venue_count"] for f in self.neigh["features"])
        self.assertEqual(self.meta["counts"]["included"], total)


if __name__ == "__main__":
    unittest.main(verbosity=2)
