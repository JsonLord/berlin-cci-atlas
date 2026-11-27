"""Tests for Phase 3 domain models (Organisation, Venue, Role, Series, Occurrence)."""

from __future__ import annotations

import unittest

from kiez_atlas.models import (
    EventOccurrence,
    EventSeries,
    Organisation,
    OrganisationVenueRole,
    Venue,
    slugify,
)


class TestModelSlugify(unittest.TestCase):
    def test_slugify_clean_text(self):
        self.assertEqual("divan_e_v", slugify("Divan e.V."))
        self.assertEqual("lettretage", slugify("Lettrétage"))
        self.assertEqual("str_8a", slugify("Str. 8a"))

    def test_slugify_german_umlauts_and_eszett(self):
        self.assertEqual("schloss_charlottenburg", slugify("Schloß Charlottenburg"))
        self.assertEqual("baerenzwinger", slugify("Bärenzwinger"))


class TestOrganisationModel(unittest.TestCase):
    def test_create_organisation(self):
        org = Organisation.create(
            name="Nachbarschaftszentrum Divan e.V.",
            website_url="https://www.nachbarschaftszentrum-divan.de",
            website_verification="verified_official",
            organisation_type="registered_association",
        )
        self.assertEqual("org_nachbarschaftszentrum_divan_e_v", org.organisation_id)
        self.assertEqual("Nachbarschaftszentrum Divan e.V.", org.canonical_name)
        self.assertEqual("registered_association", org.organisation_type)
        self.assertEqual("verified_official", org.website_verification)

    def test_organisation_is_immutable(self):
        org = Organisation.create("Test Org")
        with self.assertRaises((AttributeError, TypeError)):
            org.canonical_name = "New Name"  # type: ignore

    def test_to_dict_preserves_structure(self):
        org = Organisation.create("Test Org", aliases=["T1", "T2"])
        d = org.to_dict()
        self.assertEqual("org_test_org", d["organisation_id"])
        self.assertEqual(["T1", "T2"], d["aliases"])


class TestVenueModel(unittest.TestCase):
    def test_create_venue(self):
        venue = Venue.create(
            name="Divan Hauptgebäude",
            street="Nehringstraße",
            house_number="8",
            postcode="14059",
            venue_type="community_centre",
            latitude=52.51654,
            longitude=13.29375,
            lor_id="043004",
        )
        self.assertEqual("ven_divan_hauptgebaeude_nehringstrasse_8", venue.venue_id)
        self.assertEqual("Nehringstraße 8", venue.full_address)
        self.assertEqual(52.51654, venue.latitude)
        self.assertEqual("043004", venue.lor_id)
        self.assertTrue(venue.has_map_marker)


class TestOrganisationVenueRole(unittest.TestCase):
    def test_create_role(self):
        role = OrganisationVenueRole.create(
            organisation_id="org_divan_ev",
            venue_id="ven_divan_nehring_8",
            role_type="operates",
            is_primary_headquarters=True,
        )
        self.assertEqual("ovr_org_divan_ev_ven_divan_nehring_8_operates", role.role_id)
        self.assertTrue(role.is_primary_headquarters)


class TestEventSeriesAndOccurrence(unittest.TestCase):
    def test_create_series_and_occurrence(self):
        series = EventSeries.create(
            title="Yoga auf dem Stuhl",
            organiser_id="org_divan_ev",
            series_type="weekly_group",
            recurrence_rule="FREQ=WEEKLY;BYDAY=TU",
        )
        self.assertEqual("srs_org_divan_ev_yoga_auf_dem_stuhl", series.series_id)

        occ = EventOccurrence(
            occurrence_id="occ_divan_yoga_20261117_1000",
            series_id=series.series_id,
            title="Yoga auf dem Stuhl",
            start_datetime="2026-11-17T10:00:00+01:00",
            end_datetime="2026-11-17T11:00:00+01:00",
            organiser_id=series.organiser_id,
            venue_id="ven_divan_nehring_8",
            price_status="free",
            occurrence_status="scheduled",
            classification="hosted",
            site_relationship="mapped_venue",
            is_publishable_at_venue=True,
        )
        self.assertTrue(occ.is_publishable_at_venue)
        self.assertEqual(series.series_id, occ.series_id)
        self.assertEqual("Europe/Berlin", occ.timezone)


if __name__ == "__main__":
    unittest.main()
