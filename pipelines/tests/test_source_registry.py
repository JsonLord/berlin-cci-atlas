"""The Phase 2 source registry's status vocabulary is enforced, not customary.

Run from the repository root with:

    PYTHONPATH=./pipelines/src python -m pytest pipelines/tests -v

`kiez_atlas.cli validate` carries the same rules, but until now nothing read the
registry back at all: `source_status` is the field a later pipeline would trust
to decide what it may do with a source, and an unrecognised value in it was
indistinguishable from a valid one. The Divan audit is what exposed this — it
downgrades `p2-006` to a status value that did not exist yet, and a vocabulary
nothing validates would have let that downgrade be asserted in prose while the
machine-readable field still said `qualified`.
"""

from __future__ import annotations

import csv
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_SRC = REPO_ROOT / "pipelines" / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from kiez_atlas.vocab import EVENT_SOURCE_STATUS  # noqa: E402

REGISTRY_JSON = REPO_ROOT / "docs" / "phase2" / "PHASE2_SOURCE_REGISTRY.json"
REGISTRY_CSV = REPO_ROOT / "docs" / "phase2" / "PHASE2_SOURCE_REGISTRY.csv"


def _registry():
    return json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))


class TestRegistryExists(unittest.TestCase):
    def test_both_registry_copies_are_committed(self):
        # A failure, never a skip: both files are committed, so a missing copy is
        # a broken checkout, and skipping would silence the only guard on the
        # field that decides what may be done with a source.
        self.assertTrue(REGISTRY_JSON.exists(), f"missing {REGISTRY_JSON}")
        self.assertTrue(REGISTRY_CSV.exists(), f"missing {REGISTRY_CSV}")


class TestStatusVocabulary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = _registry()

    def test_source_ids_are_unique(self):
        ids = [r["source_id"] for r in self.registry]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_status_exists_in_the_vocabulary(self):
        unknown = sorted({r["source_status"] for r in self.registry}
                         - set(EVENT_SOURCE_STATUS))
        self.assertEqual([], unknown,
                         "statuses not defined in vocab.EVENT_SOURCE_STATUS")

    def test_json_and_csv_agree_on_every_status(self):
        """Two hand-maintained copies; a reader of the stale one gets the
        opposite answer, so agreement is asserted rather than assumed."""
        with REGISTRY_CSV.open(newline="", encoding="utf-8") as fh:
            csv_status = {r["source_id"]: r["source_status"]
                          for r in csv.DictReader(fh)}
        json_status = {r["source_id"]: r["source_status"] for r in self.registry}
        self.assertEqual(json_status, csv_status)

    def test_json_and_csv_cover_the_same_sources(self):
        with REGISTRY_CSV.open(newline="", encoding="utf-8") as fh:
            csv_ids = {r["source_id"] for r in csv.DictReader(fh)}
        self.assertEqual({r["source_id"] for r in self.registry}, csv_ids)


class TestDivanRegistryCorrection(unittest.TestCase):
    """The audit's verdict must live in the field code reads, not only in prose."""

    @classmethod
    def setUpClass(cls):
        cls.registry = _registry()
        cls.entry = next(r for r in cls.registry
                         if r["source_id"] == "p2-006")

    def test_status_is_the_audited_value(self):
        self.assertEqual("qualified_with_filter", self.entry["source_status"])

    def test_new_status_is_documented_in_the_vocabulary(self):
        self.assertIn("qualified_with_filter", EVENT_SOURCE_STATUS)
        self.assertTrue(len(EVENT_SOURCE_STATUS["qualified_with_filter"]) > 20,
                        "a status value needs a definition, not just a key")

    def test_evidence_leads_with_the_audited_count(self):
        self.assertIn("221", self.entry["evidence"])
        self.assertNotIn(
            "225 schema.org/Event items", self.entry["evidence"],
            "the superseded figure must not still be advertised as the yield",
        )

    def test_evidence_still_records_that_225_was_refuted(self):
        """The audit trail survives: the number is kept, the claim is not."""
        self.assertIn("225", self.entry["evidence"])
        self.assertRegex(self.entry["evidence"], r"225[^\n]*not reproduce")

    def test_last_checked_matches_the_audit_date(self):
        self.assertEqual("2026-11-16", self.entry["last_checked"])

    def test_status_distribution_matches_the_discovery_writeup(self):
        """PHASE2_SOURCE_DISCOVERY.md publishes a status table; it must not
        contradict the registry it describes."""
        counts = {}
        for r in self.registry:
            counts[r["source_status"]] = counts.get(r["source_status"], 0) + 1
        doc = (REPO_ROOT / "docs" / "phase2" / "PHASE2_SOURCE_DISCOVERY.md"
               ).read_text(encoding="utf-8")
        for status, n in counts.items():
            self.assertRegex(
                doc, rf"\|\s*`{status}`\s*\|\s*\*{{0,2}}{n}\*{{0,2}}\s*\|",
                f"discovery table does not record {status}={n}",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
