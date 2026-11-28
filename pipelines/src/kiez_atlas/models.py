"""Core domain models for the Berlin Kiez Events Atlas (Phase 3).

Decouples:
 - Organisation: legal / community entity organizing or curating activities
 - Venue: physical space, street address, and geographic coordinates
 - OrganisationVenueRole: relational link between an organisation and a venue
 - EventSeries: ongoing programme or recurring event concept
 - EventOccurrence: specific dated instance of an event or series

All models are immutable dataclasses with deterministic ID derivation
and clean dictionary serialization.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass, field
from typing import Any


def slugify(text: str) -> str:
    """Normalize text into a clean alphanumeric slug with German transliteration."""
    if not text:
        return ""
    t = text.lower()
    t = t.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]+", "_", t)
    return t.strip("_")


@dataclass(frozen=True)
class Organisation:
    """A cultural, civic, or public entity that organizes or curates events."""
    organisation_id: str
    canonical_name: str
    legal_name: str | None = None
    aliases: tuple[str, ...] = field(default_factory=tuple)
    organisation_type: str = "unknown"
    description: str | None = None
    website_url: str | None = None
    website_verification: str = "unverified"
    verification_status: str = "provisional"
    source_references: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @classmethod
    def create(
        cls,
        name: str,
        *,
        organisation_id: str | None = None,
        legal_name: str | None = None,
        aliases: list[str] | tuple[str, ...] = (),
        organisation_type: str = "unknown",
        description: str | None = None,
        website_url: str | None = None,
        website_verification: str = "unverified",
        verification_status: str = "provisional",
        source_references: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    ) -> Organisation:
        oid = organisation_id or f"org_{slugify(name)}"
        return cls(
            organisation_id=oid,
            canonical_name=name,
            legal_name=legal_name,
            aliases=tuple(aliases),
            organisation_type=organisation_type,
            description=description,
            website_url=website_url,
            website_verification=website_verification,
            verification_status=verification_status,
            source_references=tuple(source_references),
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["aliases"] = list(self.aliases)
        d["source_references"] = list(self.source_references)
        return d


@dataclass(frozen=True)
class Venue:
    """A physical building, space, or geographic coordinate."""
    venue_id: str
    canonical_name: str
    venue_type: str
    community_relevance: tuple[str, ...]
    street: str
    house_number: str
    postcode: str
    city: str = "Berlin"
    district: str | None = None
    latitude: float = 0.0
    longitude: float = 0.0
    coordinate_precision: str = "street"
    lor_id: str | None = None
    lor_name: str | None = None
    lor_plr_id: str | None = None
    has_map_marker: bool = True
    parent_venue_id: str | None = None
    legacy_atlas_id: str | None = None
    legacy_category: str | None = None
    legacy_layer: str | None = None
    verification_status: str = "verified"

    @property
    def full_address(self) -> str:
        return f"{self.street} {self.house_number}".strip()

    @classmethod
    def create(
        cls,
        name: str,
        street: str,
        house_number: str,
        postcode: str,
        *,
        venue_id: str | None = None,
        venue_type: str = "community_centre",
        community_relevance: list[str] | tuple[str, ...] = (),
        city: str = "Berlin",
        district: str | None = None,
        latitude: float = 0.0,
        longitude: float = 0.0,
        coordinate_precision: str = "street",
        lor_id: str | None = None,
        lor_name: str | None = None,
        lor_plr_id: str | None = None,
        has_map_marker: bool = True,
        parent_venue_id: str | None = None,
        legacy_atlas_id: str | None = None,
        legacy_category: str | None = None,
        legacy_layer: str | None = None,
        verification_status: str = "verified",
    ) -> Venue:
        vid = venue_id or f"ven_{slugify(name)}_{slugify(street)}_{slugify(house_number)}"
        return cls(
            venue_id=vid,
            canonical_name=name,
            venue_type=venue_type,
            community_relevance=tuple(community_relevance),
            street=street,
            house_number=house_number,
            postcode=postcode,
            city=city,
            district=district,
            latitude=latitude,
            longitude=longitude,
            coordinate_precision=coordinate_precision,
            lor_id=lor_id,
            lor_name=lor_name,
            lor_plr_id=lor_plr_id,
            has_map_marker=has_map_marker,
            parent_venue_id=parent_venue_id,
            legacy_atlas_id=legacy_atlas_id,
            legacy_category=legacy_category,
            legacy_layer=legacy_layer,
            verification_status=verification_status,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["community_relevance"] = list(self.community_relevance)
        return d


@dataclass(frozen=True)
class OrganisationVenueRole:
    """The relational link defining an organisation's role at a physical venue."""
    role_id: str
    organisation_id: str
    venue_id: str
    role_type: str = "operates"  # operates, owns, manages, resident_tenant, regular_host, partner
    is_primary_headquarters: bool = True
    valid_from: str | None = None
    valid_until: str | None = None
    verification_status: str = "verified"
    evidence_description: str | None = None

    @classmethod
    def create(
        cls,
        organisation_id: str,
        venue_id: str,
        *,
        role_type: str = "operates",
        is_primary_headquarters: bool = True,
        valid_from: str | None = None,
        valid_until: str | None = None,
        verification_status: str = "verified",
        evidence_description: str | None = None,
    ) -> OrganisationVenueRole:
        rid = f"ovr_{organisation_id}_{venue_id}_{role_type}"
        return cls(
            role_id=rid,
            organisation_id=organisation_id,
            venue_id=venue_id,
            role_type=role_type,
            is_primary_headquarters=is_primary_headquarters,
            valid_from=valid_from,
            valid_until=valid_until,
            verification_status=verification_status,
            evidence_description=evidence_description,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EventSeries:
    """A recurring programme or identifiable event format."""
    series_id: str
    canonical_title: str
    organiser_id: str
    title_variants: tuple[str, ...] = field(default_factory=tuple)
    description_template: str | None = None
    default_venue_id: str | None = None
    series_type: str = "weekly_group"
    recurrence_rule: str | None = None
    default_category: str | None = None
    status: str = "active"

    @classmethod
    def create(
        cls,
        title: str,
        organiser_id: str,
        *,
        series_id: str | None = None,
        title_variants: list[str] | tuple[str, ...] = (),
        description_template: str | None = None,
        default_venue_id: str | None = None,
        series_type: str = "weekly_group",
        recurrence_rule: str | None = None,
        default_category: str | None = None,
        status: str = "active",
    ) -> EventSeries:
        sid = series_id or f"srs_{organiser_id}_{slugify(title)}"
        return cls(
            series_id=sid,
            canonical_title=title,
            organiser_id=organiser_id,
            title_variants=tuple(title_variants),
            description_template=description_template,
            default_venue_id=default_venue_id,
            series_type=series_type,
            recurrence_rule=recurrence_rule,
            default_category=default_category,
            status=status,
        )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["title_variants"] = list(self.title_variants)
        return d


@dataclass(frozen=True)
class EventOccurrence:
    """A specific dated instance of an event or series."""
    occurrence_id: str
    title: str
    start_datetime: str
    end_datetime: str
    organiser_id: str
    timezone: str = "Europe/Berlin"
    series_id: str | None = None
    description: str | None = None
    venue_id: str | None = None
    room_note: str | None = None
    access_mode: str = "physical_in_person"
    category: str | None = None
    price_status: str = "unknown"
    price_amount_min: float | None = None
    price_amount_max: float | None = None
    price_currency: str = "EUR"
    booking_url: str | None = None
    occurrence_status: str = "scheduled"
    classification: str = "hosted"
    site_relationship: str = "mapped_venue"
    is_publishable_at_venue: bool = True
    source_id: str | None = None
    source_url: str | None = None
    source_event_id: str | None = None
    fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
