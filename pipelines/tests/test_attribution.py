"""Regression tests for venue attribution and the venue publication gate.

These tests protect the Divan v1.1 findings and the reusable attribution rules.
Run from the repository root with:

    python -m unittest pipelines.tests.test_attribution -v

The fixture-backed test is intentionally based on the complete 221-record audit.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE_SRC = REPO_ROOT / "pipelines" / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from kiez_atlas.attribution import (  # noqa: E402
    OtherVenue,
    VenueAddress,
    classify_location,
    normalise_address,
)


DIVAN_8 = VenueAddress.parse("Nehringstraße 8", "14059")
DIVAN_26 = OtherVenue(
    "Mehrgenerationenhaus (Nehringstraße 26)",
    VenueAddress.parse("Nehringstraße 26", "14059"),
)

ADDR_8 = (
    "Interkulturelles Stadtteilzentrum, Nachbarschaftszentrum Divan e.V., "
    "Nehringstr. 8, 14059 Berlin"
)
ADDR_26 = (
    "Mehrgenerationenhaus, Nachbarschaftszentrum Divan e.V., "
    "Nehringstr. 26, 14059 Berlin"
)
ADDR_BOTH = (
    "Interkulturelles Stadtteilzentrum / Mehrgenerationenhaus "
    "Nehringstr. 8 & Nehringstraße 26, 14059 Berlin"
)

RESULTS_PATH = (
    REPO_ROOT / "docs" / "phase2" / "divan" / "DIVAN_ATTRIBUTION_RESULTS.json"
)


def classify(location: str | None, title: str | None = None):
    """Use the production classifier with the two known Divan sites."""
    return classify_location(
        location_text=location,
        venue=DIVAN_8,
        other_venues=[DIVAN_26],
        title=title,
    )


class TestMultiVenueAmbiguity(unittest.TestCase):
    """A multi-site address must never be promoted to the mapped venue."""

    def test_location_naming_both_buildings_is_ambiguous(self):
        result = classify(ADDR_BOTH, "Yoga auf dem Stuhl II")
        self.assertEqual("ambiguous", result.classification)

    def test_multi_venue_location_is_not_the_mapped_site(self):
        result = classify(ADDR_BOTH)
        self.assertNotEqual("mapped_venue", result.site)

    def test_multi_venue_location_requires_human_review(self):
        result = classify(ADDR_BOTH)
        self.assertTrue(result.requires_human_review)

    def test_multi_venue_location_is_not_publishable(self):
        result = classify(ADDR_BOTH)
        self.assertFalse(result.is_publishable_at_venue())

    def test_multi_venue_guard_precedes_positive_address_match(self):
        """Mentioning Nehringstr. 8 alongside 26 is not an exact venue match."""
        result = classify(ADDR_BOTH)
        self.assertNotEqual("hosted", result.classification)
        self.assertFalse(result.is_publishable_at_venue())


class TestSingleVenueAttribution(unittest.TestCase):
    def test_exact_mapped_address_is_hosted_and_publishable(self):
        result = classify(ADDR_8)
        self.assertEqual("hosted", result.classification)
        self.assertEqual("mapped_venue", result.site)
        self.assertFalse(result.requires_human_review)
        self.assertTrue(result.is_publishable_at_venue())

    def test_sibling_building_is_not_publishable_at_mapped_venue(self):
        result = classify(ADDR_26)
        self.assertEqual("other_site", result.site)
        self.assertTrue(result.requires_human_review)
        self.assertFalse(result.is_publishable_at_venue())

    def test_unmatched_named_location_is_not_publishable(self):
        result = classify("SAAL - Konzertbühne")
        self.assertFalse(result.is_publishable_at_venue())

    def test_missing_location_is_not_publishable(self):
        result = classify(None, title="Divan event")
        self.assertFalse(result.is_publishable_at_venue())


class TestAddressNormalisation(unittest.TestCase):
    def test_sharp_s_folds_to_double_s(self):
        self.assertIn("strasse", normalise_address("Nehringstraße 8"))

    def test_strasse_and_str_abbreviations_match(self):
        self.assertTrue(DIVAN_8.matches(ADDR_8))

    def test_diacritics_and_german_spelling_match(self):
        self.assertTrue(DIVAN_8.matches("Nehringstraße 8, 14059 Berlin"))

    def test_house_number_must_match_exactly(self):
        self.assertFalse(DIVAN_8.matches("Nehringstr. 18, 14059 Berlin"))
        self.assertFalse(DIVAN_8.matches("Nehringstr. 26, 14059 Berlin"))


class TestWeakEvidenceNeverEstablishesVenue(unittest.TestCase):
    def test_venue_name_in_title_is_not_hosting_evidence(self):
        result = classify(
            "Irgendwo, 10115 Berlin",
            title="Yoga im Divan",
        )
        self.assertFalse(result.is_publishable_at_venue())

    def test_title_cannot_rescue_missing_location(self):
        result = classify("", title="Divan Divan Divan")
        self.assertFalse(result.is_publishable_at_venue())

    def test_title_and_description_are_currently_inert(self):
        """Pin the real reason the two tests above pass.

        `classify_location` accepts `title` and `description` but does not read
        them, so the tests above pass because the *location* fails to match,
        not because weak evidence was weighed and rejected. Asserting the
        no-op explicitly keeps that from being mistaken for implemented
        weak-evidence logic — see EVENT_ATTRIBUTION_DESIGN.md §3.

        If organiser/programme-page evidence is ever implemented, this test
        must be replaced with one that asserts the new behaviour, not deleted.
        """
        for weak in ("Yoga im Divan", "Divan präsentiert", "MEHRGENERATIONENHAUS"):
            with_text = classify_location(
                location_text="Irgendwo, 10115 Berlin",
                venue=DIVAN_8,
                other_venues=[DIVAN_26],
                title=weak,
                description=weak,
            )
            without_text = classify_location(
                location_text="Irgendwo, 10115 Berlin",
                venue=DIVAN_8,
                other_venues=[DIVAN_26],
            )
            self.assertEqual(without_text, with_text)
            self.assertEqual("ambiguous", with_text.classification)


class TestDivanAuditRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not RESULTS_PATH.exists():
            # Deliberately a failure, not a skip. These four tests are the only
            # thing standing between a regression and a wrong number on a public
            # map. As a skip they were silently inert: if the results file were
            # moved or deleted, the suite stayed green while the audit's core
            # guarantee stopped being checked. The file is committed, so its
            # absence is a defect, not an environment difference.
            raise AssertionError(
                f"Divan audit results missing at {RESULTS_PATH}; the audit "
                "regression cannot be skipped or it protects nothing"
            )
        cls.document = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        cls.events = cls.document["events"]

    def test_audit_population_is_221(self):
        self.assertEqual(221, len(self.events))
        self.assertEqual(221, self.document["event_count"])

    def test_classifier_reproduces_audit_site_counts(self):
        counts = {
            "mapped_venue": 0,
            "other_site": 0,
            "unknown": 0,
        }
        for event in self.events:
            result = classify(event.get("location"), event.get("title"))
            self.assertIn(result.site, counts)
            counts[result.site] += 1

        self.assertEqual(
            {"mapped_venue": 175, "other_site": 36, "unknown": 10},
            counts,
        )

    def test_exactly_175_audited_events_pass_the_publish_gate(self):
        publishable = [
            event
            for event in self.events
            if classify(event.get("location"), event.get("title"))
            .is_publishable_at_venue()
        ]
        self.assertEqual(175, len(publishable))

    def test_no_multi_venue_record_passes_the_publish_gate(self):
        incorrectly_publishable = []
        for event in self.events:
            location = event.get("location") or ""
            if (
                "Nehringstr. 8" in location
                and "Nehringstraße 26" in location
                and classify(location, event.get("title"))
                .is_publishable_at_venue()
            ):
                incorrectly_publishable.append(event)

        self.assertEqual([], incorrectly_publishable)


if __name__ == "__main__":
    unittest.main(verbosity=2)
