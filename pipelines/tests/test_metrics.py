"""The metrics exporter's numbers are pinned, because one of them was wrong.

Run from the repository root with:

    PYTHONPATH=./pipelines/src python -m pytest pipelines/tests -v

`collect_lor_metrics` originally looked an 8-digit Planungsraum id up in
`LorIndex.bzr_by_id`, whose keys are 6-digit Bezirksregion ids. The lookup never
matched, so the exporter reported `venues_with_lor=0 / venues_without_lor=303`
and exited 0. A metric that is wrong but plausible is worse than no metric: it
is quoted. These tests assert the join against counts that were measured
independently (`test_geo_and_products.py` pins the same 295/7/1 on the atlas
points), so the same defect cannot come back quietly.

The Divan numbers are the ones `docs/phase2/divan/` already treats as
invariants: 221 records, 175 publishable, 36 at the second building.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PIPELINE_SRC = REPO / "pipelines" / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from kiez_atlas import metrics  # noqa: E402
from kiez_atlas.vocab import PRODUCT_STATUS  # noqa: E402


class TestClassificationMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = metrics.collect_classification_metrics(REPO)

    def test_every_inventory_record_is_counted(self):
        self.assertEqual(303, self.m.total_venues)

    def test_status_counts_sum_to_the_total(self):
        self.assertEqual(303, sum(self.m.product_status.values()))

    def test_every_status_is_in_the_vocabulary(self):
        self.assertEqual(set(), set(self.m.product_status) - set(PRODUCT_STATUS))

    def test_venue_type_by_status_covers_every_status(self):
        self.assertEqual(set(PRODUCT_STATUS), set(self.m.venue_type_by_status))


class TestLorMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = metrics.collect_lor_metrics(REPO)

    def test_official_region_counts(self):
        self.assertEqual(143, self.m.total_bzr)
        self.assertEqual(542, self.m.total_plr)

    def test_every_venue_resolves_to_a_planungsraum(self):
        """The regression: this was 0 located / 303 unlocated."""
        self.assertEqual(303, self.m.venues_with_lor)
        self.assertEqual(0, self.m.venues_without_lor)

    def test_bezirksregion_counts_are_derived_from_the_plr_prefix(self):
        self.assertEqual(self.m.venues_with_lor, sum(self.m.bzr_venue_counts.values()))
        self.assertEqual(self.m.venues_with_lor, sum(self.m.plr_venue_counts.values()))
        self.assertTrue(all(len(bzr) == 6 for bzr in self.m.bzr_venue_counts))
        self.assertTrue(all(len(plr) == 8 for plr in self.m.plr_venue_counts))

    def test_atlas_agreement_matches_the_geo_tests(self):
        self.assertEqual(295, self.m.atlas_lor_agree)
        self.assertEqual(7, self.m.atlas_lor_disagree)
        self.assertEqual(1, self.m.atlas_lor_outside)


class TestWebsiteMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = metrics.collect_website_metrics(REPO)

    def test_published_venue_count(self):
        self.assertEqual(251, self.m.total_venues)

    def test_no_url_is_claimed_as_official(self):
        """Nothing was visited, so nothing may be called verified."""
        self.assertEqual(0, self.m.official_claims)
        self.assertEqual({"unverified"}, set(self.m.verification_status))


class TestSourceRegistryMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = metrics.collect_source_registry_metrics(REPO)

    def test_registry_size(self):
        self.assertEqual(27, self.m.total_sources)

    def test_csv_and_json_agree(self):
        self.assertTrue(self.m.csv_json_agree)


class TestDivanAuditMetrics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = metrics.collect_divan_audit_metrics(REPO)

    def test_record_count(self):
        self.assertEqual(221, self.m.total_events)

    def test_attribution_site_split(self):
        self.assertEqual(
            {"mapped_venue": 175, "other_site": 36, "unknown": 10},
            self.m.attribution_site,
        )

    def test_exactly_175_are_publishable(self):
        self.assertEqual(175, self.m.publishable_events)

    def test_multi_venue_events_are_the_nehringstrasse_26_set(self):
        self.assertEqual(9, self.m.multi_venue_events)

    def test_fixture_digest_is_reported(self):
        self.assertEqual(64, len(self.m.fixture_sha256))
        self.assertGreater(self.m.fixture_raw_bytes, 0)
        self.assertGreater(self.m.fixture_gz_bytes, 0)


class TestCli(unittest.TestCase):
    """`kiez_atlas.cli metrics` forwards its arguments without touching argv."""

    def test_summary_goes_to_a_file(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "metrics.txt"
            code = metrics.main(
                ["--repo", str(REPO), "--format", "summary", "--output", str(out)]
            )
            self.assertEqual(0, code)
            text = out.read_text(encoding="utf-8")
        self.assertIn("=== Kiez Events Atlas Metrics ===", text)
        self.assertIn("Total events: 221", text)
        # The line the LOR defect made wrong.
        self.assertIn("Venues with LOR: 303", text)

    def test_json_format_is_valid_json(self):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "metrics.json"
            with contextlib.redirect_stdout(io.StringIO()):
                metrics.main(["--repo", str(REPO), "--output", str(out)])
            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(221, payload["divan_audit"]["total_events"])
        self.assertEqual(303, payload["lor"]["venues_with_lor"])

    def test_output_is_byte_identical_across_processes(self):
        """A frozenset leaked into the JSON and reordered it on every run."""
        import os
        import subprocess

        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            [str(PIPELINE_SRC), env.get("PYTHONPATH", "")]
        ).strip(os.pathsep)
        # Two different hash seeds force two different frozenset orders.
        runs = []
        for seed in ("0", "12345"):
            env["PYTHONHASHSEED"] = seed
            proc = subprocess.run(
                [sys.executable, "-m", "kiez_atlas.cli", "metrics", "--repo", str(REPO)],
                capture_output=True,
                env=env,
                check=True,
            )
            runs.append(proc.stdout)
        self.assertEqual(runs[0], runs[1])

    def test_argv_is_not_mutated(self):
        import contextlib
        import io
        import tempfile

        before = list(sys.argv)
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                metrics.main(["--repo", str(REPO), "--output", str(Path(tmp) / "m.json")])
        self.assertEqual(before, list(sys.argv))


if __name__ == "__main__":
    unittest.main()
