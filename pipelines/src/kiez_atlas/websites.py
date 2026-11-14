"""Classify what an inherited `url` actually points at.

WHY THIS EXISTS
---------------
`PLACES[].url` is NOT "the venue's official website". It is "a page the compiler
used to describe this venue". Auditing all 303 records shows three distinct
shapes, and collapsing them into one `website` field was misleading:

    directory_reference      a listing/index page on someone else's site
                             (berlin.de, bbk-kulturwerk.de, visitberlin.de,
                             kgberlin.net, erih.net). 166/303 records.
    shared_organisation_site one URL reused by several venues because it belongs
                             to their umbrella organisation, not to the venue
                             itself (e.g. one page for 19 studio houses).
    venue_site_unverified    a URL on a domain that looks like the venue's own.
                             137/303 records.

CRITICAL: **not one of these has been verified as the venue's official website.**
The feasibility study never visited them. So no record is ever labelled
`official`; the strongest claim available is `venue_site_unverified`. A separate
`verification` field carries that limitation explicitly, and a test asserts no
record ever claims `official`.

This module invents nothing. It only classifies the URL that was already there.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlparse

# Hosts whose pages are directories/listings about venues, not venues' own sites.
# Verified by inspection: berlin.de serves district/library index pages,
# bbk-kulturwerk.de serves one shared studio-house directory page,
# visitberlin.de is a tourism portal, kgberlin.net is a gallery network portal,
# erih.net is a heritage-directory.
DIRECTORY_HOSTS: frozenset[str] = frozenset({
    "www.berlin.de",
    "berlin.de",
    "www.bbk-kulturwerk.de",
    "bbk-kulturwerk.de",
    "www.visitberlin.de",
    "visitberlin.de",
    "www.kgberlin.net",
    "kgberlin.net",
    "www.erih.net",
    "erih.net",
})

WEBSITE_KINDS: dict[str, str] = {
    "directory_reference":
        "A listing/index page hosted by a third party (city portal, studio-house "
        "directory, tourism site). Not the venue's own website.",
    "shared_organisation_site":
        "One URL reused by several venues because it belongs to their umbrella "
        "organisation rather than to the individual venue.",
    "venue_site_unverified":
        "A URL on a domain that appears to belong to the venue. NOT verified as "
        "official — no record was visited during the feasibility phase.",
}

VERIFICATION_STATUSES: dict[str, str] = {
    "unverified":
        "Carried over from the inherited data. Nobody has confirmed this URL "
        "belongs to the venue, is current, or is the official site.",
    "verified_official":
        "Confirmed by visiting, with the confirmation recorded. No record has "
        "this status yet; the vocabulary exists so it can be earned later.",
}


@dataclass(frozen=True)
class WebsiteAssessment:
    url: str | None
    kind: str
    verification: str
    host: str | None
    shared_by: int          # how many venues in the directory use this exact URL
    note: str


def assess(urls: list[str | None]) -> dict[str, WebsiteAssessment]:
    """Assess every inherited url, given the full list (needed for sharing)."""
    counts = Counter(u for u in urls if u)
    out: dict[str, WebsiteAssessment] = {}

    for url in {u for u in urls if u}:
        host = urlparse(url).netloc
        shared = counts[url]

        if host in DIRECTORY_HOSTS:
            kind = "directory_reference"
            note = (f"Host {host!r} is a third-party directory/portal, so this is a "
                    f"reference to where the venue is described, not the venue's site.")
        elif shared > 1:
            kind = "shared_organisation_site"
            note = (f"This exact URL is used by {shared} venues, so it belongs to a "
                    f"shared umbrella organisation rather than to this venue alone.")
        else:
            kind = "venue_site_unverified"
            note = (f"Domain {host!r} appears to belong to the venue, but it has not "
                    f"been visited or confirmed as the official site.")

        out[url] = WebsiteAssessment(
            url=url, kind=kind, verification="unverified",
            host=host, shared_by=shared, note=note)

    return out


def assess_place(place: dict, index: dict[str, WebsiteAssessment]) -> WebsiteAssessment:
    url = place.get("url")
    if not url:
        return WebsiteAssessment(url=None, kind="venue_site_unverified",
                                 verification="unverified", host=None, shared_by=0,
                                 note="No URL in the inherited record.")
    return index[url]
