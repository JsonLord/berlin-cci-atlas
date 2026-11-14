"""Tests for website meaning and the public/internal deploy boundary.

These exist because two claims were previously unenforced:
  1. that a `website` field is not a verified official site, and
  2. that internal files cannot reach a deployment.
A claim that no test checks is a claim that will quietly become false.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipelines" / "src"))

from kiez_atlas import websites                                        # noqa: E402
from kiez_atlas.deploy import (                                       # noqa: E402
    DeployBoundaryError, assert_no_internal_leak, internal_files,
    read_allowlist, resolve_deploy_set)
from kiez_atlas.extract_embedded import load_atlas                    # noqa: E402

ATLAS = load_atlas(REPO / "index.html")
PUB = REPO / "data" / "public"
INTERNAL = REPO / "data" / "internal"


class TestWebsiteClassification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.places = ATLAS["PLACES"]
        cls.index = websites.assess([p["url"] for p in cls.places])
        cls.pub = json.loads((PUB / "venues.json").read_text(encoding="utf-8"))["venues"]
        cls.inv = json.loads((INTERNAL / "venue_inventory.json")
                             .read_text(encoding="utf-8"))["venues"]

    def test_every_url_is_classified(self):
        for p in self.places:
            self.assertIn(p["url"], self.index, p["id"])

    def test_kind_is_always_a_known_value(self):
        for url, a in self.index.items():
            self.assertIn(a.kind, websites.WEBSITE_KINDS, url)

    def test_verification_is_always_a_known_value(self):
        for url, a in self.index.items():
            self.assertIn(a.verification, websites.VERIFICATION_STATUSES, url)

    # ---- the core guarantee: nothing claims to be official ----

    def test_no_record_claims_an_official_website(self):
        """No URL was visited during feasibility, so no record may claim
        official status. This is the test that stops a future edit from
        silently upgrading 'unverified' to 'official'."""
        for v in self.pub:
            self.assertNotEqual("verified_official", v["website"]["verification"], v["venue_id"])

    def test_no_public_record_has_an_official_boolean(self):
        """A bare `official: true` field would be an invented claim."""
        for v in self.pub:
            self.assertNotIn("official", v)
            self.assertNotIn("is_official", v)
            self.assertNotIn("official_website", v)

    def test_metadata_declares_zero_official_claims(self):
        meta = json.loads((PUB / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(0, meta["websites"]["official_claims"])

    # ---- the distinction itself ----

    def test_berlin_de_urls_are_directory_references(self):
        for v in self.pub:
            url = v["website"]["url"] or ""
            if urlparse(url).netloc in websites.DIRECTORY_HOSTS:
                self.assertEqual("directory_reference", v["website"]["kind"], v["venue_id"])

    def test_shared_urls_are_not_labelled_venue_sites(self):
        for v in self.pub:
            if v["website"]["shared_by_venue_count"] > 1:
                self.assertNotEqual("venue_site_unverified", v["website"]["kind"],
                                    f"{v['venue_id']} shares its URL")

    def test_the_19_studio_houses_are_directory_references(self):
        """The single most misleading case: 19 venues in the inventory share one
        bbk page. Only 3 of them are published (16 are pending_review), so this
        asserts across the inventory, not just the public subset."""
        url = "https://www.bbk-kulturwerk.de/en/art-spaces-berlin/studio-houses"
        in_inventory = [v for v in self.inv if v["inherited"]["url"] == url]
        self.assertEqual(19, len(in_inventory))
        for v in in_inventory:
            self.assertEqual("directory_reference", v["website_assessment"]["kind"], v["venue_id"])
            self.assertEqual(19, v["website_assessment"]["shared_by_venue_count"], v["venue_id"])

    def test_published_studio_house_refs_are_also_directory_references(self):
        url = "https://www.bbk-kulturwerk.de/en/art-spaces-berlin/studio-houses"
        published = [v for v in self.pub if v["website"]["url"] == url]
        self.assertGreaterEqual(len(published), 1)
        for v in published:
            self.assertEqual("directory_reference", v["website"]["kind"], v["venue_id"])

    def test_shared_by_count_matches_reality(self):
        counts: dict[str, int] = {}
        for p in self.places:
            counts[p["url"]] = counts.get(p["url"], 0) + 1
        for v in self.pub:
            url = v["website"]["url"]
            self.assertEqual(counts[url], v["website"]["shared_by_venue_count"], v["venue_id"])

    # ---- no invention ----

    def test_every_published_url_exists_in_the_inherited_data(self):
        """Guards against a hand-typed or guessed URL entering the output."""
        inherited = {p["url"] for p in self.places}
        for v in self.pub:
            if v["website"]["url"] is not None:
                self.assertIn(v["website"]["url"], inherited, v["venue_id"])

    def test_no_url_field_was_synthesised_from_the_venue_name(self):
        """A plausible-looking invented domain would pass a syntax check but
        fail this: the url must be byte-identical to the inherited value."""
        by_id = {p["id"]: p for p in self.places}
        for v in self.pub:
            self.assertEqual(by_id[v["venue_id"]]["url"], v["website"]["url"], v["venue_id"])

    def test_inventory_carries_the_assessment_for_all_303(self):
        self.assertEqual(303, len(self.inv))
        for v in self.inv:
            wa = v["website_assessment"]
            self.assertIn(wa["kind"], websites.WEBSITE_KINDS, v["venue_id"])
            self.assertGreaterEqual(len(wa["note"]), 10, v["venue_id"])

    def test_distribution_sums_to_public_count(self):
        meta = json.loads((PUB / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(len(self.pub), sum(meta["websites"]["distribution"].values()))


class TestLorAttributionIsProvisional(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = json.loads((PUB / "metadata.json").read_text(encoding="utf-8"))

    def test_status_is_explicitly_provisional(self):
        entry = self.meta["attribution"]["added_by_this_pipeline"][0]
        self.assertEqual("provisional", entry["status"])

    def test_vintage_and_licence_are_unknown_not_guessed(self):
        entry = self.meta["attribution"]["added_by_this_pipeline"][0]
        self.assertEqual("unknown", entry["vintage"])
        self.assertIn("unknown", entry["licence"])

    def test_publication_is_marked_blocked(self):
        entry = self.meta["attribution"]["added_by_this_pipeline"][0]
        self.assertTrue(entry["blocks_publication"])

    def test_confirmation_owner_is_named(self):
        entry = self.meta["attribution"]["added_by_this_pipeline"][0]
        self.assertIn("upstream controller", entry["confirmation_required_from"])

    def test_metadata_lists_the_blocker(self):
        blockers = self.meta["attribution"]["publication_blockers"]
        self.assertTrue(any("LOR" in b for b in blockers))

    def test_inherited_register_is_untouched(self):
        """We add attribution; we never rewrite what upstream credited."""
        self.assertEqual(7, len(self.meta["attribution"]["inherited_register"]))


class TestDeployBoundary(unittest.TestCase):
    def test_allowlist_reads(self):
        entries = read_allowlist(REPO)
        self.assertIn("index.html", entries)
        self.assertIn("data/public/venues.json", entries)

    def test_resolve_deploy_set_returns_only_real_files(self):
        files = resolve_deploy_set(REPO)
        self.assertTrue(files)
        for f in files:
            self.assertTrue(f.exists(), f)

    def test_resolve_never_includes_internal(self):
        for f in resolve_deploy_set(REPO):
            rel = f.relative_to(REPO.resolve()).as_posix()
            self.assertFalse(rel.startswith("data/internal/"), rel)

    def test_public_staging_passes(self):
        assert_no_internal_leak(PUB)   # must not raise

    def test_data_root_staging_is_refused(self):
        """The whole data/ tree contains internal files, so it must fail."""
        with self.assertRaises(DeployBoundaryError):
            assert_no_internal_leak(REPO / "data")

    def test_internal_staging_is_refused(self):
        with self.assertRaises(DeployBoundaryError):
            assert_no_internal_leak(INTERNAL)

    def test_a_copied_internal_file_is_caught(self):
        """Simulate the realistic failure: someone copies internal data into
        the public staging directory."""
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as td:
            staged = Path(td)
            shutil.copytree(PUB, staged / "public")
            assert_no_internal_leak(staged)          # clean first
            (staged / "public" / "review_queue.json").write_text("{}")
            with self.assertRaises(DeployBoundaryError):
                assert_no_internal_leak(staged)

    def test_allowlist_rejects_traversal(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "data").mkdir()
            (repo / "data" / "deploy-allowlist.txt").write_text("../etc/passwd\n")
            with self.assertRaises(DeployBoundaryError):
                resolve_deploy_set(repo)

    def test_allowlist_rejects_listed_missing_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            (repo / "data").mkdir()
            (repo / "data" / "deploy-allowlist.txt").write_text("does-not-exist.json\n")
            with self.assertRaises(DeployBoundaryError):
                resolve_deploy_set(repo)

    def test_internal_files_are_present_and_enumerated(self):
        names = {p.name for p in internal_files(REPO)}
        self.assertEqual({"venue_inventory.json", "classification.json",
                          "review_queue.json"}, names)


if __name__ == "__main__":
    unittest.main(verbosity=2)
