"""Classification tests. Each test exists because a real record broke it first.

Run:  python -m pytest pipelines/tests  (or: python pipelines/tests/test_classify.py)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipelines" / "src"))

from kiez_atlas import vocab                                    # noqa: E402
from kiez_atlas.classify import (                               # noqa: E402
    CATEGORY_TO_TYPE, NON_PHYSICAL_IDS, TYPE_OVERRIDES, classify, derive_type)
from kiez_atlas.extract_embedded import load_atlas              # noqa: E402

PLACES = {p["id"]: p for p in load_atlas(REPO / "index.html")["PLACES"]}


def place(**over):
    """A minimal synthetic record; override any inherited field."""
    base = {"id": "synthetic", "name": "Synthetic", "cat": "community",
            "layer": "social", "sectors": ["all"], "desc": "", "address": "Straße 1",
            "plz": "10115", "url": "https://example.invalid", "flag": True,
            "src": "https://example.invalid/src", "d": "Mitte", "lor": "01100310",
            "c": [13.4, 52.52], "prec": "street", "dg": 100, "dw": 100}
    base.update(over)
    return base


class TestKeyIntegrity(unittest.TestCase):
    """The first run had 9 of 37 override keys pointing at ids that did not
    exist — they were silently inert. This test makes that impossible."""

    def test_override_keys_exist(self):
        dead = [k for k in TYPE_OVERRIDES if k not in PLACES]
        self.assertEqual([], dead, "TYPE_OVERRIDES keys must be real venue ids")

    def test_non_physical_keys_exist(self):
        dead = [k for k in NON_PHYSICAL_IDS if k not in PLACES]
        self.assertEqual([], dead)

    def test_override_types_are_known(self):
        for k, (t, _) in TYPE_OVERRIDES.items():
            self.assertIn(t, vocab.VENUE_TYPES, f"{k} -> unknown type {t}")

    def test_source_ids_are_truncated_not_invented(self):
        """ids in the source data max out at 48 chars; note it, don't fix it."""
        self.assertLessEqual(max(len(i) for i in PLACES), 50)


class TestVcFundIsNotACommunityVenue(unittest.TestCase):
    """Regression: 'early-stage' matched \\bstage\\b and 'public venture capital
    arm' matched a public-* construction, so a VC fund was classified as a
    community venue. Ambiguous words are not evidence."""

    def test_ibb_ventures_excluded(self):
        d = classify(PLACES["ibb-ventures-vc-fonds-kreativwirtschaft"])
        self.assertEqual("excluded", d.product_status)
        self.assertEqual("funding_body", d.venue_type)

    def test_stage_word_alone_is_not_public_evidence(self):
        d = classify(place(cat="funding",
                           desc="Public venture arm taking stakes in early-stage startups."))
        self.assertEqual("excluded", d.product_status)

    def test_all_funding_bodies_excluded_without_strong_evidence(self):
        for pid, p in PLACES.items():
            if p["cat"] == "funding":
                d = classify(p)
                self.assertNotEqual("included", d.product_status,
                                    f"{p['name']} must not be included")


class TestAssociationsAreNotVenues(unittest.TestCase):
    """Regression: two theatrical *membership associations* were included
    because their descriptions contain the word 'theatre'. Being about theatre
    is not hosting theatre events."""

    def _by_name(self, prefix):
        """Truncated ids make hardcoding brittle; resolve by name instead."""
        hits = [p for p in PLACES.values() if p["name"].startswith(prefix)]
        self.assertEqual(1, len(hits), prefix)
        return hits[0]

    def test_laft_berlin_not_included(self):
        d = classify(self._by_name("LAFT Berlin"))
        self.assertNotEqual("included", d.product_status)

    def test_bundesverband_not_included(self):
        self.assertNotEqual("included",
                            classify(self._by_name("Bundesverband Freie Darstellende")).product_status)

    def test_association_with_weak_evidence_goes_to_review_not_include(self):
        d = classify(place(cat="network",
                           desc="Association representing the theatre sector; lobbies."))
        self.assertEqual("pending_review", d.product_status)
        self.assertEqual("R3b", d.rule)


class TestStrongEvidenceOverrides(unittest.TestCase):
    """R4: an advice desk or studio house that demonstrably serves the public
    is community-relevant despite its category."""

    def test_free_public_consultations_include_advice_centre(self):
        d = classify(PLACES["music-pool-berlin"])
        self.assertEqual("included", d.product_status)
        self.assertEqual("R4", d.rule)

    def test_open_studio_includes_studio_building(self):
        d = classify(PLACES["atelierhaus-mengerzeile"])
        self.assertEqual("included", d.product_status)
        self.assertEqual("R4", d.rule)

    def test_private_studio_letting_goes_to_review(self):
        d = classify(place(cat="studios", desc="Association-run studios for artists."))
        self.assertEqual("pending_review", d.product_status)
        self.assertEqual("R5", d.rule)


class TestPatternOrdering(unittest.TestCase):
    """Two ordering bugs found in review: 'Makerspace …-Bibliothek' typed as a
    library, and 'MiK ' matching inside 'Namik Kemal'."""

    def test_library_makerspace_is_makerspace(self):
        for vid in ("makerspace-anna-seghers-bibliothek",
                    "freelab-makerspace-schiller-bibliothek"):
            self.assertEqual("makerspace", derive_type(PLACES[vid])[0], vid)

    def test_namik_kemal_stays_a_library(self):
        pid = "mittelpunktbibliothek-wilhelm-liebknecht-namik-k"
        self.assertEqual("library", derive_type(PLACES[pid])[0])

    def test_real_youth_arts_school_still_matches(self):
        pid = "mik-jugendkunstschule-berlin-mitte"
        self.assertEqual("youth_arts_school", derive_type(PLACES[pid])[0])


class TestNonPhysical(unittest.TestCase):
    def test_online_portal_excluded(self):
        d = classify(PLACES["creative-city-berlin"])
        self.assertEqual("excluded", d.product_status)
        self.assertEqual("portal", d.venue_type)
        self.assertEqual("R1", d.rule)


class TestSeparationOfDimensions(unittest.TestCase):
    """event_source_status must never be inferred from community relevance."""

    def test_inherently_public_types_are_included_regardless_of_source(self):
        for t in vocab.INHERENTLY_PUBLIC_TYPES:
            cat = {v: k for k, v in CATEGORY_TO_TYPE.items()}.get(t, "community")
            d = classify(place(cat=cat, name="X", desc=""))
            self.assertEqual("included", d.product_status, t)

    def test_every_decision_records_a_rule_and_reason(self):
        for pid, p in PLACES.items():
            d = classify(p)
            self.assertIn(d.rule, {"R1", "R2", "R3", "R3b", "R4", "R5", "R6"}, pid)
            self.assertGreaterEqual(len(d.reason), 20, pid)

    def test_statuses_partition_the_directory(self):
        from collections import Counter
        c = Counter(classify(p).product_status for p in PLACES.values())
        self.assertEqual(303, sum(c.values()))
        self.assertEqual({"included", "excluded", "pending_review"}, set(c))

    def test_relevance_values_are_known(self):
        for pid, p in PLACES.items():
            for r in classify(p).community_relevance:
                self.assertIn(r, vocab.COMMUNITY_RELEVANCE, pid)

    def test_types_are_known(self):
        for pid, p in PLACES.items():
            self.assertIn(classify(p).venue_type, vocab.VENUE_TYPES, pid)


class TestExtensibility(unittest.TestCase):
    """The decision requires new venue types without a data-model change."""

    def test_adding_a_type_does_not_break_classification(self):
        vocab.VENUE_TYPES["urban_garden"] = "Allotment/community garden."
        try:
            d = classify(place(cat="community", name="Nachbarschaftsgarten",
                               desc="Community garden with open days."))
            self.assertEqual("included", d.product_status)
        finally:
            del vocab.VENUE_TYPES["urban_garden"]

    def test_public_schema_has_no_closed_venue_type_enum(self):
        import json
        s = json.loads((REPO / "docs/feasibility/artifacts/venue.schema.json")
                       .read_text(encoding="utf-8"))
        self.assertNotIn("enum", s["properties"]["venue_type"])
        self.assertNotIn("enum", s["properties"]["community_relevance"]["items"])


class TestTypeNameNotDescription(unittest.TestCase):
    """Regression: patterns were matching the *description*, so 12 public
    libraries that merely mention a makerspace they host were retyped as
    makerspaces. A description says what a venue contains or does; it does not
    say what the venue IS."""

    def test_library_mentioning_makerspace_stays_a_library(self):
        d = classify(place(cat="library", name="Stadtteilbibliothek Beispiel",
                           desc="Public library with a makerspace, 3D printer and events."))
        self.assertEqual("library", d.venue_type)

    def test_makerspace_named_as_such_is_a_makerspace(self):
        d = classify(place(cat="makerspace", name="Makerspace Beispiel-Bibliothek",
                           desc="Free public library makerspace with sewing machines."))
        self.assertEqual("makerspace", d.venue_type)

    def test_library_and_makerspace_totals_match_inherited_categories(self):
        lib = [p for p in PLACES.values() if p["cat"] == "library"]
        mk = [p for p in PLACES.values() if p["cat"] == "makerspace"]
        # 3 library-hosted makerspaces legitimately carry cat=makerspace already,
        # so the totals must stay at the inherited counts.
        self.assertEqual(66, sum(1 for p in PLACES.values()
                                 if classify(p).venue_type == "library"))
        self.assertEqual(7, sum(1 for p in PLACES.values()
                                if classify(p).venue_type == "makerspace"))
        self.assertEqual(66, len(lib))
        self.assertEqual(7, len(mk))

    def test_no_record_falls_through_to_the_unmapped_fallback(self):
        for pid, p in PLACES.items():
            t, how = derive_type(p)
            self.assertNotEqual("unmapped fallback", how, f"{pid} -> {t}")

class TestInheritedPreserved(unittest.TestCase):
    def test_all_303_present(self):
        self.assertEqual(303, len(PLACES))

    def test_community_and_library_never_excluded(self):
        for pid, p in PLACES.items():
            if p["cat"] in ("community", "library", "vhs", "musicschool", "artschool"):
                self.assertEqual("included", classify(p).product_status,
                                 f"{p['name']} ({p['cat']})")


if __name__ == "__main__":
    unittest.main(verbosity=2)
