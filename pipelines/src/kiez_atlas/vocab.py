"""Controlled vocabularies for the Kiez Events Atlas venue model.

DESIGN NOTE — extensibility
----------------------------
The decision requires that "new community-relevant venue types must be addable
without changing the fundamental data model." That is satisfied structurally:
`venue_type` and each `community_relevance` value are plain strings validated
against the registries below, not against a closed JSON-Schema enum. Adding a
type means adding one entry here plus, if it should be auto-included, one line
in `INHERENTLY_PUBLIC_TYPES`. No schema migration, no data rewrite.

Every value carries a human description so the classification report can
explain itself without a separate glossary.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# venue_type — what kind of physical place is this?
# --------------------------------------------------------------------------
VENUE_TYPES: dict[str, str] = {
    # --- public community infrastructure ---
    "community_centre": "Neighbourhood/community centre: Stadtteilzentrum, Nachbarschaftshaus, "
                        "Mehrgenerationenhaus, Bürgerzentrum, Kiez-Treff, Begegnungsstätte.",
    "cultural_centre": "Cultural centre with a public programme: Kulturhaus, Kulturzentrum, "
                       "sozio-cultural centre, Freizeitforum, Gemeinschaftshaus.",
    "library": "Public or community library, including district and central libraries.",
    "adult_education_centre": "Public adult education centre (Volkshochschule).",
    "music_school": "Public music school (Musikschule).",
    "youth_arts_school": "Youth arts school (Jugendkunstschule).",
    "gallery": "Exhibition space, typically municipally run: Kommunale Galerie, project space.",
    "event_venue": "Venue whose primary function is hosting events: halls, stages, converted "
                   "industrial event spaces.",
    "creative_hub": "Multi-use creative quarter or hub combining studios, workshops and public "
                    "programme space.",
    # --- making / producing ---
    "makerspace": "Shared making space with public access: 3D printing, textiles, electronics.",
    "workshop_space": "Subsidised craft/art workshop with public or subsidised access.",
    "rehearsal_space": "Rehearsal or production space for performing arts and music.",
    "artist_studio_building": "Building let primarily as artist studios.",
    "coworking_space": "Commercial coworking space, sometimes with public event space.",
    # --- service / administrative ---
    "advice_centre": "Advice and counselling service for creatives or residents.",
    "association_office": "Office of a membership association, chamber or professional body.",
    "funding_body": "Grant-making or funding institution.",
    "bank": "Public development bank.",
    "government_office": "Public administration office.",
    "university_facility": "University unit or facility.",
    # --- non-physical ---
    "portal": "Online-only resource: portal, directory or information service with no "
              "public physical venue of its own.",
}

# Types that are public-facing by construction: if a record has one of these
# types it is included without needing extra evidence in its description.
INHERENTLY_PUBLIC_TYPES: frozenset[str] = frozenset({
    "community_centre", "cultural_centre", "library", "adult_education_centre",
    "music_school", "youth_arts_school", "gallery", "event_venue", "creative_hub",
    "makerspace", "workshop_space",
})

# Types that are administrative/service in nature. Included only if the record
# itself evidences a public programme; otherwise excluded.
ADMINISTRATIVE_TYPES: frozenset[str] = frozenset({
    "association_office", "funding_body", "bank", "government_office",
    "university_facility",
})

# Types whose financial or state-administrative purpose dominates: only STRONG
# public-access evidence can overcome the exclusion. A funding round is not a
# funding *event*, and a chamber is not a venue.
FINANCIAL_OR_STATE_TYPES: frozenset[str] = frozenset({
    "funding_body", "bank", "government_office", "university_facility",
})

# Types that are physical but whose public accessibility must be evidenced
# per record (private workspace, hire-only, or service desk).
EVIDENCE_REQUIRED_TYPES: frozenset[str] = frozenset({
    "artist_studio_building", "rehearsal_space", "coworking_space", "advice_centre",
})

# --------------------------------------------------------------------------
# community_relevance — which community functions does the venue enable?
# --------------------------------------------------------------------------
COMMUNITY_RELEVANCE: dict[str, str] = {
    "public_events": "Hosts events open to the general public.",
    "open_access": "Drop-in access without membership or appointment.",
    "participatory_workshops": "Runs courses, workshops or making sessions open to participation.",
    "neighbourhood_gathering": "Provides social space: café, lounge, meeting rooms, garden.",
    "learning": "Offers structured learning (courses, tuition, qualifications).",
    "making_repair": "Provides tools, materials or repair facilities.",
    "arts_presentation": "Presents art, performance or exhibitions to the public.",
    "rehearsal_production": "Provides space for producing or rehearsing work.",
    "advice_support": "Offers counselling, advice or support services.",
    "sector_networking": "Professional/B2B networking for a sector.",
    "funding_access": "Provides access to grants, loans or finance.",
    "private_workspace": "Rents workspace privately; not public by default.",
    "information_resource": "Provides information online or by remote enquiry.",
}

# --------------------------------------------------------------------------
# product_status
# --------------------------------------------------------------------------
PRODUCT_STATUS: dict[str, str] = {
    "included": "Part of the Kiez Events Atlas venue directory.",
    "excluded": "Not part of the directory; reason recorded.",
    "pending_review": "Physical venue whose community relevance is ambiguous; "
                      "needs a human decision.",
}

# Machine-readable exclusion / review reasons.
REASONS: dict[str, str] = {
    "non_physical": "No public physical venue of its own (portal or online resource).",
    "administrative_not_public": "Administrative or funding body with no public "
                                 "community programme evidenced.",
    "no_public_activity_evidenced": "Physical, but the record evidences only private "
                                    "workspace or commercial hire; no public activity.",
    "public_activity_evidenced": "Record evidences a public programme, so treated as "
                                 "community-relevant despite its category.",
    "ambiguous_function": "Function could support community activity but the record "
                          "does not settle it.",
}

# --------------------------------------------------------------------------
# event_source_status — deliberately independent of product_status
# --------------------------------------------------------------------------
EVENT_SOURCE_STATUS: dict[str, str] = {
    "not_assessed": "No source discovery attempted yet.",
    "candidate": "A plausible source exists but extraction is unproven or incomplete.",
    "qualified": "A source was fetched and yielded usable, dated events.",
    "temporarily_unavailable": "Source unreachable at last check (DNS, 404, outage).",
    "not_suitable": "The known URL publishes no usable event data.",
    # Added by the Divan audit. `qualified` means extraction works, and that is
    # true of Divan; what it does not say is that only 79.2% of the extracted
    # records belong to the building the Atlas marker represents. Recording that
    # as `qualified` with a caveat in free text is how the 225-event yield
    # survived review — the status field is what downstream code reads, and it
    # said "usable" without saying "not raw-publishable".
    "qualified_with_filter": (
        "Extraction works and records are usable, but they must be filtered "
        "before publication. Not eligible for raw publication. The filter is "
        "specified, not necessarily implemented."
    ),
}
