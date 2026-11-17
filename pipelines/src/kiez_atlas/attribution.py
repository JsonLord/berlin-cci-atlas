"""Venue attribution for event records — the shared rules every adapter needs.

WHY THIS IS A MODULE AND NOT ADAPTER-SPECIFIC CODE
The Divan audit (docs/phase2/divan/) found two failure modes that are not
Divan-specific and will recur in every future adapter:

 1. A location string naming SEVERAL physical venues does not tell you which
    one the event is at. Treating "includes our venue" as "is at our venue"
    silently inflates venue-attributable counts. This was a real bug: 9 of 221
    Divan records were classified `divan_hosted` on that basis alone.

 2. A calendar's ownership does not imply every event belongs to that venue.
    Phase 2.1 showed the same shape for berlin.de: a `v_ort`-scoped feed was
    only ~47% venue-precise. Attribution must come from per-event evidence.

So the rules live here, once, are pure functions, and are covered by tests.
No adapter implements its own venue-matching.

EVIDENCE HIERARCHY (from the task specification)
    strong     explicit event location matching the venue's verified address
    supporting organiser/partner reference, or an official programme page
    weak       the venue name appears in the title; same district; same calendar

Weak evidence must never establish `hosted`. That is enforced by the code
structure: only `strong` reaches HOSTED.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

# Classification outcomes. `hosted` is the only value that means "this event
# takes place at the mapped venue". The rest are named so adapters do not
# invent their own vocabulary.
CLASSIFICATIONS: tuple[str, ...] = (
    "hosted",              # strong: takes place at the mapped venue
    "organised_elsewhere", # strong: organiser is the venue, location differs
    "partnered",           # explicitly named as partner/collaborator
    "external_event",      # demonstrably another org, no venue connection
    "ambiguous",           # evidence insufficient or contradictory
    "insufficient_data",   # required information missing
)

# Only these mean "publishable at the venue's map marker".
#
# DO NOT gate publication on `classification` alone. An event at Divan's second
# building is also `hosted` — it is genuinely hosted, just not here — so a
# classification-only gate republishes all 36 sibling-building records at the
# wrong marker, which is the precise failure this module was written to stop.
# Use `is_publishable_at_venue()` instead; it requires the site as well.
PUBLISHABLE_AT_VENUE: frozenset[str] = frozenset({"hosted"})

# The only site value that may appear at this venue's marker.
PUBLISHABLE_SITE = "mapped_venue"


def normalise_address(text: str | None) -> str:
    """Fold case, strip diacritics and punctuation, collapse whitespace."""
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    # German ß does not decompose under NFKD, but sources mix "Nehringstraße"
    # and "Nehringstr." freely. Folding ß -> ss is what makes those match.
    t = t.replace("ß", "ss")
    t = re.sub(r"[^a-z0-9äöüß]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


@dataclass(frozen=True)
class VenueAddress:
    """A venue's address in matchable form."""
    street: str          # e.g. "nehringstr"
    house_number: str    # e.g. "8"
    postcode: str | None

    @classmethod
    def parse(cls, street_number: str, postcode: str | None = None) -> "VenueAddress":
        """Build from 'Nehringstraße 8' style input."""
        n = normalise_address(street_number)
        m = re.match(r"^(.*?)\s+(\d+[a-z]?)$", n)
        if not m:
            return cls(street=n, house_number="", postcode=postcode)
        return cls(street=m.group(1).strip(), house_number=m.group(2), postcode=postcode)

    def _variants(self) -> set[str]:
        """`strasse`/`str` spellings differ across sources; accept both."""
        s = self.street
        out = {s}
        for a, b in (("strasse", "str"), ("str", "strasse")):
            if s.endswith(a):
                out.add(s[: -len(a)] + b)
        return out

    def matches(self, text: str | None) -> bool:
        n = normalise_address(text)
        if not n:
            return False
        for v in self._variants():
            if re.search(rf"\b{re.escape(v)}\s*\.?\s*{re.escape(self.house_number)}\b", n):
                return True
        return False


@dataclass(frozen=True)
class OtherVenue:
    """Another physical venue that may share an address string."""
    label: str
    address: VenueAddress


@dataclass(frozen=True)
class Attribution:
    classification: str
    evidence_type: str          # "strong" | "supporting" | "weak" | "none"
    evidence: str
    rationale: str
    conflicting_evidence: str | None
    requires_human_review: bool
    # Which physical site the event is at. "mapped_venue" is the only value
    # that may be published at this venue's map marker.
    site: str = "unknown"       # mapped_venue | other_site | unknown

    def is_publishable_at_venue(self) -> bool:
        """True only if the event is hosted AND at the mapped building.

        Both halves are required. `classification == "hosted"` alone is true
        for events at a sibling building of the same organisation, so it must
        never be used on its own as a publication gate.
        """
        return (
            self.classification in PUBLISHABLE_AT_VENUE
            and self.site == PUBLISHABLE_SITE
        )

def classify_location(
    *,
    location_text: str | None,
    venue: VenueAddress,
    other_venues: Iterable[OtherVenue] = (),
    title: str | None = None,
    description: str | None = None,
) -> Attribution:
    """Classify an event's venue relationship from its location string.

    THE MULTI-VENUE RULE
    --------------------
    If the location string names MORE THAN ONE known physical venue, the
    result is `ambiguous` — regardless of whether the target venue is among
    them. Membership of the target venue among several named locations is
    insufficient evidence: the event happens at one place, and the source has
    not said which.

    This guard runs BEFORE the positive match, which is the whole point. A
    version that matched first and then noted ambiguity would still emit
    `hosted` counts inflated by shared-address records.
    """
    text = location_text or ""
    if not normalise_address(text):
        return Attribution(
            classification="insufficient_data",
            evidence_type="none",
            evidence="location field is empty or unparseable",
            rationale="No location information at all; the event cannot be placed.",
            conflicting_evidence=None,
            requires_human_review=True,
            site="unknown",
        )

    venue_hit = venue.matches(text)
    other_hits = [o for o in other_venues if o.address.matches(text)]

    # --- rule 1: multiple physical venues named -> ambiguous ---
    if venue_hit and other_hits:
        names = ", ".join(o.label for o in other_hits)
        return Attribution(
            classification="ambiguous",
            evidence_type="weak",
            evidence=f"location names both target venue and {names}: {text!r}",
            rationale=(
                "The location string identifies more than one physical venue. "
                "Naming the target venue among several locations does not "
                "establish that the event takes place there."
            ),
            conflicting_evidence=(
                f"Contacts the target address and {names}; the source does not "
                "say which one hosts this occurrence."
            ),
            requires_human_review=True,
            site="unknown",
        )

    # --- rule 2: only the target venue -> hosted ---
    if venue_hit:
        return Attribution(
            classification="hosted",
            evidence_type="strong",
            evidence=f"location explicitly matches the venue address: {text!r}",
            rationale="Explicit event location matches the venue's verified address.",
            conflicting_evidence=None,
            requires_human_review=False,
            site="mapped_venue",
        )

    # --- rule 3: only another venue -> hosted elsewhere, not at our marker ---
    if other_hits:
        names = ", ".join(o.label for o in other_hits)
        return Attribution(
            classification="hosted",
            evidence_type="strong",
            evidence=f"location matches {names}: {text!r}",
            rationale=(
                f"The event demonstrably takes place at {names}, a different "
                "physical venue from the one being mapped."
            ),
            conflicting_evidence=(
                "Belongs to the same organisation but a different building; "
                "must not be published at this venue's map marker."
            ),
            requires_human_review=True,
            site="other_site",
        )

    # --- rule 4: no address match at all ---
    return Attribution(
        classification="ambiguous",
        evidence_type="none",
        evidence=f"location {text!r} matches no known venue address",
        rationale="Neither the target venue nor any known sibling venue is named.",
        conflicting_evidence=None,
        requires_human_review=True,
        site="unknown",
    )
