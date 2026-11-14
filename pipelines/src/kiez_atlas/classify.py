"""Rule-based venue classification for the Kiez Events Atlas.

Scope decision (Leon Gründling, 2026-11-14)
-------------------------------------------
The Atlas is a broad network of community-relevant *physical* venues. It is NOT
limited to `cat == "hub"`. The defining criterion is the venue's community
function, not its inherited directory category. Four dimensions stay separate:

    venue_type            what kind of place this is
    community_relevance   which community functions it enables
    product_status        included | excluded | pending_review
    event_source_status   whether events can be retrieved (assessed separately)

Rule ordering — first match wins, and every record records the rule that fired
so no decision is silent:

    R1   non-physical resource            -> excluded
    R2   inherently public venue type     -> included
    R4   STRONG public-access evidence    -> included   (overrides R3/R5)
    R3   funding / bank / state office    -> excluded
    R3b  association or advice desk      -> pending_review
    R5   physical, public access unproven -> pending_review
    R6   unmapped                        -> pending_review (never guessed)

R4 outranks R3 and R3b deliberately: an advice centre or association that
demonstrably runs a public programme is community-relevant even though its
inherited category is `advice` or `network`.

Nothing is invented. Where the record cannot settle a question it goes to
pending_review rather than being coerced in either direction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .vocab import (
    ADMINISTRATIVE_TYPES,
    COMMUNITY_RELEVANCE,
    EVIDENCE_REQUIRED_TYPES,
    FINANCIAL_OR_STATE_TYPES,
    INHERENTLY_PUBLIC_TYPES,
    REASONS,
    VENUE_TYPES,
)

# ---------------------------------------------------------------------------
# venue_type derivation
# ---------------------------------------------------------------------------

# Name/description patterns checked before the category map because they are
# more specific than `cat`. First match wins.
NAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"online community portal", re.I), "portal"),
    (re.compile(r"\bVolkshochschule\b", re.I), "adult_education_centre"),
    (re.compile(r"Jugendkunstschule|KUNSTBASTION|Young Arts|YouKunst|\bMiK\b", re.I),
     "youth_arts_school"),
    (re.compile(r"Musikschule", re.I), "music_school"),
    (re.compile(r"Makerspace|FreeLab", re.I), "makerspace"),
    (re.compile(r"Bibliothek|Bücherei|ZLB", re.I), "library"),
    (re.compile(r"Stadtteilzentrum|Stadtteiltreff|Stadtteilladen|Nachbarschaftshaus|"
                r"Nachbarschaftszentrum|Nachbarschaftsetage|Nachbarschaftstreff|"
                r"Mehrgenerationenhaus|Bürgerzentrum|Bürgerhaus|Kiez Zentrum|"
                r"Kiez-Treff|Kieztreff|Kiezstube|Kiezbegegnung|Begegnungsstätte|"
                r"Staakentreff|Wohngebietszentrum|Stadtschloss|KOMPASS-Haus|"
                r"Kiek in|Haus der Begegnung", re.I),
     "community_centre"),
    (re.compile(r"Kulturhaus|Kulturzentrum|KulturMarktHalle|Freizeitforum|"
                r"Gemeinschaftshaus|Socio-cultural", re.I),
     "cultural_centre"),
    (re.compile(r"Galerie|Ausstellungszentrum|Kunst Raum|Kunstraum|projektraum|"
                r"Projektraum|studio im HOCHHAUS|GalerieETAGE|Bärenzwinger|"
                r"Klosterruine|Gotisches Haus", re.I),
     "gallery"),
    (re.compile(r"coworking", re.I), "coworking_space"),
    (re.compile(r"theater|freilichtbühne|bühne", re.I), "event_venue"),
]

CATEGORY_TO_TYPE: dict[str, str] = {
    "community": "community_centre",
    "library": "library",
    "vhs": "adult_education_centre",
    "musicschool": "music_school",
    "artschool": "youth_arts_school",
    "makerspace": "makerspace",
    "hub": "creative_hub",
    "culture": "gallery",
    "studios": "artist_studio_building",
    "rehearsal": "rehearsal_space",
    "coworking": "coworking_space",
    "network": "association_office",
    "advice": "advice_centre",
    "funding": "funding_body",
    "incubator": "university_facility",
}

# Records whose inherited category is misleading enough that an explicit,
# keyed override is more auditable than a fuzzy pattern. Keyed by venue_id.
TYPE_OVERRIDES: dict[str, tuple[str, str]] = {
    # Cultural centres / event venues misfiled as `culture` (elsewhere = gallery)
    "wabe": ("cultural_centre", "desc: 'District-run cultural centre'"),
    "brotfabrik": ("cultural_centre", "desc: 'Cultural centre with stage, cinema and gallery'"),
    "theater-unterm-dach": ("event_venue", "desc: 'District theatre'"),
    "freilichtbuhne-weissensee": ("event_venue", "desc: 'District open-air stage'"),
    "gemeinschaftshaus-gropiusstadt": ("cultural_centre",
                                       "desc: 'Largest cultural centre in southern Neukölln'"),
    "kulturhaus-spandau": ("cultural_centre", "desc: 'District cultural centre'"),
    "kulturhaus-schwartzsche-villa": ("cultural_centre",
                                      "desc: 'District cultural centre and gallery'"),
    "gutshaus-steglitz": ("event_venue", "desc: 'used by the district for exhibitions and events'"),
    "altglienicker-burgerzentrum-im-burgerhaus-altgli": (
        "community_centre",
        "desc: 'Socio-cultural centre ... with music, theatre and courses'"),
    "schloss-biesdorf": ("gallery", "desc: 'housing a municipal gallery'"),
    "freizeitforum-marzahn": ("cultural_centre", "desc: 'Large cultural and leisure centre'"),
    "fontane-haus-im-markischen-viertel": (
        "event_venue",
        "desc: 'District event venue with halls for concerts, theatre and community events'"),
    "kulturhaus-karlshorst": ("cultural_centre",
                              "desc: 'District cultural centre with concerts, theatre and a gallery'"),
    "kulturzentrum-alte-schule-adlershof-galerie-adle": (
        "cultural_centre", "desc: 'District cultural centre with municipal gallery'"),
    "mies-van-der-rohe-haus": ("gallery", "desc: 'showing contemporary art and architecture'"),
    "zitadelle-spandau-zak-zentrum-fur-aktuelle-kunst": (
        "gallery", "desc: 'centre for contemporary art'"),
    "haus-am-kleistpark": ("gallery", "desc: 'municipal gallery with an adjoining project room'"),
    "klosterruine-berlin": ("event_venue", "desc: 'used by the district for art and events'"),

    # Multi-use creative quarters misfiled as plain studio buildings
    "exrotaprint": ("creative_hub",
                    "desc: former factory renting to artists, small businesses and social organisations"),
    "ateliers-uferhallen": ("creative_hub", "desc: studios plus dance and rehearsal rooms"),
    "fahrbereitschaft": ("creative_hub", "desc: 'creative quarter with artist studios and workshops'"),
    "kunstfabrik-hb55": ("creative_hub", "desc: 'Studio and workshop centre for arts and crafts'"),
    "kunst-in-den-gerichtshofen": ("creative_hub", "desc: courtyard complex run by an artists' association"),
    "kunstlerhof-frohnau": ("creative_hub",
                            "desc: 'rents studios and runs residencies, exhibitions, workshops'"),

    # Institutions whose function is clearer than their category
    "lettretage": ("cultural_centre",
                   "desc: 'Anchor institution ... runs a public programme and projects'"),
    "filmnetzwerk-berlin": ("advice_centre",
                            "desc: 'meeting point ... with events, pitches, a coffee club'"),
    "haus-der-statistik-haus-der-materialisierung": (
        "creative_hub",
        "desc: 'material-reuse initiatives, textile and repair workshops and event spaces'"),
    "motionlab-berlin": ("makerspace", "desc: 'Hardware makerspace and coworking hub'"),
    "orwohaus": ("creative_hub", "desc: 'about 100 rehearsal rooms, recording studios' plus "
                                    "a public concert programme"),
    "house-of-music-noisy-rooms": ("event_venue", "desc: 'a stage and seminar rooms'"),
    "funkhaus-berlin": ("creative_hub", "type: large multi-use creative quarter"),
    "holzmarkt-25": ("creative_hub", "type: multi-use creative quarter"),
    "malzfabrik": ("event_venue", "type: converted malting plant used as an event venue"),
    "haus-schwarzenberg": ("creative_hub", "type: studio-house complex with public courtyard"),
    "berlin-career-college-berliner-startup-stipendiu": (
        "university_facility", "desc: 'UdK Berlin's career and transfer unit'"),
}

# Records whose whole purpose is an online resource. Enumerated rather than
# pattern-matched: deciding "is this physical?" from prose alone is exactly the
# silent judgement the decision forbids.
NON_PHYSICAL_IDS: dict[str, str] = {
    "creative-city-berlin":
        "desc: 'Online community portal of Kulturprojekte Berlin'. The address is "
        "'Klosterstraße 68 (c/o Kulturprojekte Berlin GmbH)' — a postal c/o for an "
        "online service, not a public venue.",
}

# ---------------------------------------------------------------------------
# public-activity evidence — two tiers
# ---------------------------------------------------------------------------
# WHY TWO TIERS. A single "does it mention events?" regex produced demonstrably
# wrong results during development: a venture-capital fund was INCLUDED because
# "early-stage" matched \bstage\b and "public venture capital arm" matched a
# public-* construction; and two theatrical *membership associations* were
# INCLUDED because their descriptions contain the word "theatre" — they are
# about theatre, they do not host it. Ambiguous words are not evidence.
#
#   STRONG  an explicit public-access construction. Sufficient to INCLUDE a
#           venue whose type would otherwise be excluded or reviewed.
#   WEAK    a venue-function hint that does not establish public access.
#           Sufficient only to route to pending_review, never to include.

STRONG_PUBLIC = re.compile(
    r"open\s+to\s+the\s+public"
    r"|open\s+(?:studio|day|meeting|workshop)s?\b"
    r"|public\s+(?:programme|program|events?|access|readings?|lectures?)"
    r"|publicly\s+(?:funded\s+)?(?:programme|events?|access|workshop)"
    r"|for\s+the\s+public\b"
    r"|(?:free|open)\s+(?:to|for)\s+(?:all|everyone|residents)\b"
    r"|\bdrop[- ]?in\b"
    r"|\bfor\s+residents\b"
    r"|free\s+(?:one-hour\s+)?consultations?\b"
    r"|\bVeranstaltungen?\b"
    r"|öffentlich(?:en|es)?\s+(?:Veranstaltung|Programm|Zugang|Angebot)"
    r"|\bbegegnung\b"
    r"|neighbourhood\s+(?:centre|events?|activities|cafe|café)"
    r"|community\s+(?:centre|events?|activities|meals?)"
    r"|host(?:s|ing)?\s+(?:concerts?|events?|exhibitions?|readings?|courses?)"
    r"|runs?\s+(?:a\s+)?public\b",
    re.I,
)

WEAK_PUBLIC = re.compile(
    r"\bexhibitions?\b|\bexhibit\b|\bkunstverleih\b|art\s+lending"
    r"|\bconcerts?\b|\bcinema\b|open[- ]air\s+stage"
    r"|\breadings?\b"
    r"|\bcourses?\b|\bKurse?\b"
    r"|\bsubside[dD]?\b"
    r"|\bcounselling\b"
    r"|\bworkshops?\b"
    r"|\btheatre\b|\btheater\b",
    re.I,
)


@dataclass
class Decision:
    venue_type: str
    community_relevance: list[str]
    product_status: str
    rule: str
    reason: str
    notes: list[str] = field(default_factory=list)


def derive_type(place: dict) -> tuple[str, str]:
    """Return (venue_type, how_it_was_derived)."""
    vid = place["id"]
    if vid in TYPE_OVERRIDES:
        t, why = TYPE_OVERRIDES[vid]
        return t, f"type_override ({why})"
    # Match on the NAME only. A description tells you what a venue contains or
    # does, not what it is: 12 libraries mention a makerspace they *host* and
    # were being retyped as makerspaces, which would have silently dropped the
    # library identity of 12 public venues. Where a description really is the
    # only evidence, the record gets an explicit TYPE_OVERRIDES entry instead.
    for pat, t in NAME_PATTERNS:
        if pat.search(place["name"]):
            return t, f"name pattern {pat.pattern[:36]!r}"
    t = CATEGORY_TO_TYPE.get(place["cat"])
    if t:
        return t, f"category map cat={place['cat']!r}"
    return "creative_hub", "unmapped fallback"


def relevance_for(place: dict, vtype: str, public: bool) -> list[str]:
    rel: list[str] = []

    def add(*vals: str) -> None:
        for v in vals:
            assert v in COMMUNITY_RELEVANCE, f"unknown relevance {v}"
            if v not in rel:
                rel.append(v)

    text = (place["name"] + " " + place["desc"]).lower()

    if vtype in INHERENTLY_PUBLIC_TYPES:
        add("open_access")
    if public:
        add("public_events")
    if re.search(r"workshop|kurs|course|tuition|teach|lesson", text):
        add("participatory_workshops")
    if re.search(r"café|garden|lounge|meeting room|begegnung|treff|kitchen|salon", text):
        add("neighbourhood_gathering")
    if re.search(r"course|learn|bildung|education|tuition|qualif", text):
        add("learning")
    if re.search(r"maker|3d print|repair|werkstatt|tools|sewing|laser|cnc|print workshop", text):
        add("making_repair")
    if re.search(r"exhibit|galerie|gallery|concert|theatre|stage|cinema|performance", text):
        add("arts_presentation")
    if re.search(r"rehearsal|probe|proben|studio", text):
        add("rehearsal_production")
    if re.search(r"advice|beratung|counsel|support|help desk|coaching", text):
        add("advice_support")
    if re.search(r"network|verband|association|chamber|branch", text):
        add("sector_networking")
    if re.search(r"fund|grant|loan|finance|förd", text):
        add("funding_access")
    if re.search(r"rents?\s+(?:work\s+)?spaces?|artist studios|studio house|bookable", text):
        add("private_workspace")
    if re.search(r"online|portal|website|information", text):
        add("information_resource")

    return rel or ["information_resource"]


def classify(place: dict) -> Decision:
    """Apply the ordered rule set to one inherited venue record."""
    vid = place["id"]
    desc = place["desc"]

    # R1 — non-physical
    if vid in NON_PHYSICAL_IDS:
        return Decision(
            venue_type="portal",
            community_relevance=["information_resource"],
            product_status="excluded",
            rule="R1",
            reason=f"{REASONS['non_physical']} {NON_PHYSICAL_IDS[vid]}",
        )

    vtype, how = derive_type(place)
    assert vtype in VENUE_TYPES, f"unknown venue_type {vtype}"

    sm = STRONG_PUBLIC.search(desc)
    strong = bool(sm)
    weak_hits = sorted({w.lower() for w in WEAK_PUBLIC.findall(desc) if w})

    # R2 — inherently public infrastructure
    if vtype in INHERENTLY_PUBLIC_TYPES:
        return Decision(
            venue_type=vtype,
            community_relevance=relevance_for(place, vtype, strong or bool(weak_hits)),
            product_status="included",
            rule="R2",
            reason=f"{how}; type {vtype!r} is public community infrastructure by definition",
        )

    # R4 — STRONG public-access evidence overrides the administrative default
    if strong and (vtype in ADMINISTRATIVE_TYPES or vtype in EVIDENCE_REQUIRED_TYPES):
        return Decision(
            venue_type=vtype,
            community_relevance=relevance_for(place, vtype, True),
            product_status="included",
            rule="R4",
            reason=f"{REASONS['public_activity_evidenced']} {how}; STRONG evidence "
                   f"{sm.group(0)!r} in {desc[:150]!r}",
        )

    # R3 — funding body / bank / state office, no public-access evidence
    if vtype in FINANCIAL_OR_STATE_TYPES:
        return Decision(
            venue_type=vtype,
            community_relevance=relevance_for(place, vtype, False),
            product_status="excluded",
            rule="R3",
            reason=f"{REASONS['administrative_not_public']} {how}; desc={desc[:150]!r}",
        )

    # R3b — membership association or advice desk with only WEAK evidence.
    # An association *about* a scene is not a venue hosting that scene's
    # events, but it may still run public sessions -> a human decides.
    if vtype in ADMINISTRATIVE_TYPES:
        return Decision(
            venue_type=vtype,
            community_relevance=relevance_for(place, vtype, False),
            product_status="pending_review",
            rule="R3b",
            reason=f"{REASONS['ambiguous_function']} {how}; only WEAK function hints "
                   f"{weak_hits}, no public-access construction. desc={desc[:150]!r}",
        )

    # R5 — physical but public access unevidenced
    if vtype in EVIDENCE_REQUIRED_TYPES:
        return Decision(
            venue_type=vtype,
            community_relevance=relevance_for(place, vtype, False),
            product_status="pending_review",
            rule="R5",
            reason=f"{REASONS['no_public_activity_evidenced']} {how}; WEAK hints "
                   f"{weak_hits}; desc={desc[:150]!r}",
        )

    # R6 — never guess
    return Decision(
        venue_type=vtype,
        community_relevance=relevance_for(place, vtype, False),
        product_status="pending_review",
        rule="R6",
        reason=f"{REASONS['ambiguous_function']} {how}",
    )
