"""Tests for independent fixture-to-results verification of the Divan audit.

Run from the repository root with:

    PYTHONPATH=./pipelines/src python -m pytest pipelines/tests -v

These tests guard a different claim from `test_attribution.py`. That file proves
the classifier reproduces 175 / 36 / 10 from the results file. These prove the
results file itself is what the frozen fixture contains — otherwise the audit's
"221 records" is a number asserted in prose and copied forward.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_SRC = REPO_ROOT / "pipelines" / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from kiez_atlas import divan_fixture as dfx  # noqa: E402

RESULTS_PATH = REPO_ROOT / dfx.RESULTS_REL


def _load_results() -> dict:
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


class TestFixtureIntegrity(unittest.TestCase):
    def test_decompresses_to_the_recorded_digest(self):
        _html, info = dfx.load_fixture_html(REPO_ROOT)
        self.assertTrue(
            info["sha256_matches_recorded"],
            "fixture no longer matches its recorded sha256",
        )
        self.assertEqual(676682, info["raw_bytes"])
        self.assertEqual(85701, info["gz_bytes"])

    def test_digest_is_the_real_sha256_of_the_decompressed_bytes(self):
        """Guards against a self-consistent but meaningless digest file."""
        html, info = dfx.load_fixture_html(REPO_ROOT)
        self.assertEqual(
            hashlib.sha256(html.encode("utf-8")).hexdigest(), info["sha256"]
        )


class TestSummaryCarriesTrueDigest(unittest.TestCase):
    """`divan_audit` also reports the fixture digest, into the summary JSON.

    Two modules compute the same digest. If they ever disagree, the summary
    publishes a hash the fixture does not have — which is worse than saying
    nothing, because it looks verified.
    """

    def test_summary_fixture_block_matches_the_real_digest(self):
        from kiez_atlas import divan_audit

        _html, info = dfx.load_fixture_html(REPO_ROOT)
        results = json.loads(
            (REPO_ROOT / divan_audit.RESULTS_REL).read_text(encoding="utf-8")
        )
        summary = divan_audit.summarise(results, repo=REPO_ROOT)
        self.assertEqual(info["sha256"], summary["fixture"]["sha256"])
        self.assertTrue(summary["fixture"]["sha256_matches_recorded"])
        self.assertEqual(info["raw_bytes"], summary["fixture"]["raw_bytes"])


class TestExtractionRules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, _ = dfx.load_fixture_html(REPO_ROOT)
        cls.records = dfx.extract_records(cls.html)

    def test_fixture_yields_221_records(self):
        self.assertEqual(221, len(self.records))

    def test_every_record_has_all_four_compared_fields(self):
        """A silently empty field would understate the audited population."""
        for i, r in enumerate(self.records):
            for field in dfx.COMPARE_FIELDS:
                self.assertTrue(
                    r[field].strip(),
                    f"record {i} has empty {field!r}; extraction rule is wrong",
                )

    def test_timestamps_keep_the_source_offset_not_utc(self):
        """`data-event-start` is UTC epoch; `content` carries +01:00.

        Reading the wrong attribute shifts all 442 timestamps by an hour and
        still yields 221 records, so a count-only check would pass while every
        time in the audit was wrong.
        """
        for r in self.records:
            for field in ("start", "end"):
                self.assertRegex(
                    r[field], r"T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$",
                    f"{field}={r[field]!r} lost its UTC offset",
                )

    def test_html_entities_are_decoded(self):
        raw = json.dumps(self.records, ensure_ascii=False)
        self.assertNotIn(
            "&amp;", raw,
            "undecoded entities remain; the audit stores decoded text",
        )
        self.assertNotIn("&quot;", raw)

    def test_location_only_record_is_recovered(self):
        """The one record whose location lives solely in a <meta> element."""
        matches = [r for r in self.records if "SAAL - Konzertbühne" == r["title"]]
        self.assertEqual(1, len(matches))
        self.assertEqual("SAAL - Konzertbühne", matches[0]["location"])

    def test_prefix_sharing_classes_exist_in_the_fixture(self):
        """`simcal-events` and `simcal-events-dots` share the record's class
        prefix. They are containers and separators, not records, and the
        extractor's boundary must not count them. The behavioural proof is
        `test_decoy_prefix_li_is_not_extracted` below; this pins the premise.
        """
        self.assertIn('class="simcal-events"', self.html)
        self.assertIn('class="simcal-events-dots"', self.html)
        self.assertEqual(221, len(self.records))

    def test_decoy_prefix_li_is_not_extracted(self):
        """Direct proof of the boundary rule, independent of fixture contents."""
        decoy = (
            '<li class="simcal-events-dots">x</li>'
            '<li class="simcal-events">y</li>'
            '<li class="simcal-event simcal-event-recurring">'
            '<span class="simcal-event-title">Real</span>'
            '<span class="simcal-event-start simcal-event-start-date" '
            'content="2026-11-01T12:00:00+01:00"></span>'
            '<span class="simcal-event-end simcal-event-end-time" '
            'content="2026-11-01T22:00:00+01:00"></span>'
            '<span class="simcal-event-address">'
            '<meta itemprop="address" content="Nehringstr. 8" /></span></li>'
        )
        out = dfx.extract_records(decoy)
        self.assertEqual(1, len(out))
        self.assertEqual("Real", out[0]["title"])
        self.assertEqual("Nehringstr. 8", out[0]["location"])


class TestFixtureMatchesResults(unittest.TestCase):
    """The audit's central reproducibility claim, made executable."""

    @classmethod
    def setUpClass(cls):
        cls.report = dfx.verify(REPO_ROOT)

    def test_fixture_and_results_agree(self):
        self.assertTrue(
            self.report["agrees"],
            f"fixture/results disagree: {self.report['field_mismatches'][:3]}",
        )

    def test_record_counts_match_and_match_the_declared_count(self):
        self.assertEqual(221, self.report["fixture_record_count"])
        self.assertEqual(221, self.report["results_record_count"])
        self.assertEqual(221, self.report["results_declared_event_count"])

    def test_no_missing_additional_or_mismatched_records(self):
        self.assertEqual([], self.report["missing_from_results"])
        self.assertEqual([], self.report["additional_in_results"])
        self.assertEqual(0, self.report["field_mismatch_count"])

    def test_record_order_matches(self):
        """`event_index` is referenced in error messages, so order is load-bearing."""
        self.assertTrue(self.report["positional_order_matches"])

    def test_the_one_source_duplicate_is_symmetric(self):
        """221 records hold 220 distinct tuples; both sides must carry it."""
        self.assertEqual(220, self.report["fixture_distinct_tuples"])
        self.assertEqual(220, self.report["results_distinct_tuples"])
        self.assertEqual(
            len(self.report["duplicates_in_fixture"]),
            len(self.report["duplicates_in_results"]),
        )


class TestVerificationFailsOnDisagreement(unittest.TestCase):
    """Negative controls.

    Without these, `test_fixture_and_results_agree` could pass vacuously: a
    comparison that always returns "agree" is indistinguishable from a correct
    one until the day it matters. Each test injects exactly one defect and
    requires the comparison to isolate it.
    """

    @classmethod
    def setUpClass(cls):
        cls.html, _ = dfx.load_fixture_html(REPO_ROOT)
        cls.clean = dfx.extract_records(cls.html)
        cls.results = _load_results()

    def _tampered(self, mutate):
        mutated = copy.deepcopy(self.results)
        mutate(mutated)
        return dfx.compare(self.clean, mutated)

    def test_detects_a_changed_title(self):
        r = self._tampered(lambda d: d["events"][7].__setitem__("title", "X"))
        self.assertGreater(r["field_mismatch_count"], 0)

    def test_detects_a_shifted_hour(self):
        def mutate(d):
            d["events"][3]["end_datetime"] = "2026-11-02T14:00:00+01:00"
        self.assertGreater(self._tampered(mutate)["field_mismatch_count"], 0)

    def test_detects_a_dropped_record(self):
        r = self._tampered(lambda d: d["events"].pop(50))
        self.assertEqual(1, len(r["missing_from_results"]))
        self.assertEqual([], r["additional_in_results"])

    def test_detects_an_extra_record(self):
        def mutate(d):
            d["events"].append(dict(d["events"][0]))
        r = self._tampered(mutate)
        self.assertEqual(1, len(r["additional_in_results"]))

    def test_detects_a_pure_reordering(self):
        """Same multiset, wrong order: missing/extra stay empty, order flag fires."""
        r = self._tampered(lambda d: d["events"].reverse())
        self.assertEqual([], r["missing_from_results"])
        self.assertEqual([], r["additional_in_results"])
        self.assertFalse(r["positional_order_matches"])

    def test_detects_a_location_changed_to_a_sibling_building(self):
        """The exact failure the Divan audit is about: a venue swap."""
        def mutate(d):
            d["events"][0]["location"] = (
                "Mehrgenerationenhaus, Nachbarschaftszentrum Divan e.V., "
                "Nehringstr. 26, 14059 Berlin, 03081700103"
            )
        r = self._tampered(mutate)
        self.assertEqual("location", r["field_mismatches"][0]["field"])

    def test_clean_data_passes_the_same_comparison(self):
        """Proves the checks above fire on the injection, not on the harness."""
        r = dfx.compare(self.clean, self.results)
        self.assertEqual(0, r["field_mismatch_count"])
        self.assertTrue(r["positional_order_matches"])


class TestVerificationIsReadOnly(unittest.TestCase):
    def test_verify_does_not_write_the_results_file(self):
        """A verifier that can repair what it verifies verifies nothing."""
        before = hashlib.sha256(RESULTS_PATH.read_bytes()).hexdigest()
        dfx.verify(REPO_ROOT)
        after = hashlib.sha256(RESULTS_PATH.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_module_exposes_no_write_path(self):
        source = (Path(dfx.__file__)).read_text(encoding="utf-8")
        for forbidden in ("write_text", "open(", "dump("):
            self.assertNotIn(
                forbidden, source,
                f"verifier must not contain a write path ({forbidden!r})",
            )


class TestResultsFileIsMandatory(unittest.TestCase):
    def test_missing_results_file_raises_not_skips(self):
        """Silence here would make the whole audit unchecked."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / dfx.FIXTURE_REL.parent).mkdir(parents=True)
            for name in (dfx.FIXTURE_REL.name, dfx.SHA_REL.name):
                shutil.copy2(REPO_ROOT / dfx.FIXTURE_REL.parent / name,
                             root / dfx.FIXTURE_REL.parent / name)
            # Fixture is valid; only the results file is absent, so the raised
            # error must come from the results check and not from the fixture.
            with self.assertRaises(FileNotFoundError) as ctx:
                dfx.verify(root)
        self.assertIn("audited results missing", str(ctx.exception))

    def test_digest_mismatch_raises_rather_than_comparing_garbage(self):
        """A corrupted fixture must stop the run, not produce a field diff.

        Uses a throwaway tree so the committed fixture and digest are untouched.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / dfx.FIXTURE_REL.parent).mkdir(parents=True)
            for name in (dfx.FIXTURE_REL.name, dfx.SHA_REL.name):
                shutil.copy2(REPO_ROOT / dfx.FIXTURE_REL.parent / name,
                             root / dfx.FIXTURE_REL.parent / name)
            (root / dfx.SHA_REL).write_text(
                "0" * 64 + "  divan_kalender_snapshot.html\n", encoding="utf-8"
            )
            with self.assertRaises(ValueError) as ctx:
                dfx.load_fixture_html(root)
        self.assertIn("digest mismatch", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
