"""Event compilation pipeline.

Ingests audited event populations from:
 - Divan microdata calendar (docs/phase2/divan/DIVAN_ATTRIBUTION_RESULTS.json)
 - Lettrétage JSON-LD detail pages (docs/phase2/pilot/lettretage_pilot_results.json)

Applies the two-factor publication gate:
 - Nehringstr. 8 (Divan primary): 175 publishable occurrences
 - Nehringstr. 26 (Divan sibling building): 36 publishable occurrences
 - Veteranenstr. 21 (Lettrétage): 26 publishable occurrences

Outputs:
 - data/canonical/event_series.json
 - data/canonical/event_occurrences.json
 - data/public/events.json (validated against docs/feasibility/artifacts/event.schema.json)
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

BERLIN_TZ = ZoneInfo("Europe/Berlin")


def _event_id(venue_id: str, start: str, title: str) -> str:
    """Generate a deterministic 16-hex event ID satisfying ^evt_[a-z0-9]{16}$."""
    raw = f"{venue_id}|{start}|{title}".encode("utf-8")
    h = hashlib.sha256(raw).hexdigest()[:16]
    return f"evt_{h}"


def _infer_category(title: str, default: str = "neighbourhood_gathering") -> str:
    t = title.lower()
    if any(w in t for w in ["lesung", "buch", "poesie", "poetry", "show", "konzert", "autor"]):
        return "arts_culture"
    if any(w in t for w in ["yoga", "sport", "bewegung", "tanzen", "gymnastik"]):
        return "sport_outdoor"
    if any(w in t for w in ["frühstück", "essen", "kochen", "cafe", "café", "mittag"]):
        return "community_meal"
    if any(w in t for w in ["sprache", "deutsch", "arabisch", "türkisch"]):
        return "language_exchange"
    if any(w in t for w in ["workshop", "kurs", "lernen", "seminar"]):
        return "participatory_workshop"
    if any(w in t for w in ["beratung", "sprechstunde", "hilfe"]):
        return "civic_participation"
    return default


def compile_events(repo: Path) -> dict[str, Any]:
    divan_path = repo / "docs" / "phase2" / "divan" / "DIVAN_ATTRIBUTION_RESULTS.json"
    lettretage_path = repo / "docs" / "phase2" / "pilot" / "lettretage_pilot_results.json"

    divan_raw = json.loads(divan_path.read_text(encoding="utf-8"))
    lettretage_raw = json.loads(lettretage_path.read_text(encoding="utf-8"))

    occurrences: list[dict[str, Any]] = []
    series_map: dict[str, dict[str, Any]] = {}

    # -------------------------------------------------------------
    # 1. Process Divan Events (221 records)
    # -------------------------------------------------------------
    for e in divan_raw["events"]:
        title = e["title"]
        site = e["attribution_site"]
        classification = e["attribution"]

        # Determine target venue under two-factor attribution gate
        if classification in ("hosted", "divan_hosted") and site == "mapped_venue":
            venue_id = "interkulturelles-stadtteilzentrum-divan"
            venue_name = "Interkulturelles Stadtteilzentrum Divan"
            lor_id = "043004"
            lor_name = "Schloss Charlottenburg"
        elif classification in ("hosted", "divan_hosted") and site == "other_site":
            venue_id = "ven_divan_nehring_26"
            venue_name = "Divan Mehrgenerationenhaus (Nehringstr. 26)"
            lor_id = "043004"
            lor_name = "Schloss Charlottenburg"
        else:
            # Ambiguous (9) or unusable (1) -> not publishable at a physical marker
            continue

        evt_id = _event_id(venue_id, e["start_datetime"], title)
        srs_id = f"srs_divan_{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')}"

        if srs_id not in series_map:
            series_map[srs_id] = {
                "series_id": srs_id,
                "canonical_title": title,
                "organiser_id": "org_interkulturelles-stadtteilzentrum-divan",
                "default_venue_id": venue_id,
                "default_category": _infer_category(title),
                "series_type": "weekly_group" if e.get("data_quality_flags", {}).get("recurring") else "irregular_series",
                "status": "active",
            }

        # Fallback for original_event_url (Divan has no per-event permalink)
        orig_url = f"https://nachbarschaftszentrum-divan.de/kalender/#{evt_id}"

        pub_evt = {
            "schema_version": "0.1.0",
            "event_id": evt_id,
            "series_id": srs_id,
            "title": title,
            "description": None,
            "start_datetime": e["start_datetime"],
            "end_datetime": e["end_datetime"],
            "timezone": "Europe/Berlin",
            "venue_id": venue_id,
            "venue_name": venue_name,
            "lor_id": lor_id,
            "lor_name": lor_name,
            "category": _infer_category(title),
            "price_status": "unknown",
            "price_amount": None,
            "price_amount_max": None,
            "price_currency": "EUR",
            "price_note": "No structured price field on source calendar",
            "original_event_url": orig_url,
            "source_url": "https://nachbarschaftszentrum-divan.de/kalender/",
            "observed_at": "2026-11-16T12:00:00+01:00",
            "verified_at": "2026-11-16T12:00:00+01:00",
            "extraction_method": "simcal_microdata",
            "extraction_evidence": "li.simcal-event microdata with verified address",
            "event_status": "scheduled",
            "source_freshness": "fresh",
            "language": "de",
        }
        occurrences.append(pub_evt)

    # -------------------------------------------------------------
    # 2. Process Lettrétage Events (30 sampled records)
    # -------------------------------------------------------------
    for item in lettretage_raw:
        j = item["jsonld"]
        meta_desc = item.get("meta_description", "")
        loc_name = j.get("location", {}).get("name", "")

        # Ambiguity guard: off-site K26 events in Schöneberg must not publish at Mitte marker
        if "K26" in loc_name or "Kolonnen" in loc_name:
            continue

        title = j.get("name", "").strip()
        start_utc = j.get("startDate")
        end_utc = j.get("endDate")
        if not start_utc or not end_utc:
            continue

        # Convert UTC Z to Berlin local time (+01:00 in winter)
        dt_start = datetime.fromisoformat(start_utc.replace("Z", "+00:00")).astimezone(BERLIN_TZ)
        dt_end = datetime.fromisoformat(end_utc.replace("Z", "+00:00")).astimezone(BERLIN_TZ)

        venue_id = "lettretage"
        venue_name = "Lettrétage"
        lor_id = "011004"
        lor_name = "Brunnenstraße Süd"
        evt_id = _event_id(venue_id, dt_start.isoformat(), title)
        srs_id = f"srs_lettretage_{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')}"

        if srs_id not in series_map:
            series_map[srs_id] = {
                "series_id": srs_id,
                "canonical_title": title,
                "organiser_id": "org_lettretage",
                "default_venue_id": venue_id,
                "default_category": "arts_culture",
                "series_type": "irregular_series",
                "status": "active",
            }

        # Determine price from prose in meta description
        price_status = "unknown"
        price_amt = None
        if "Eintritt: frei" in meta_desc or "frei" in meta_desc.lower():
            price_status = "free"
            price_amt = 0.0
        elif "Spendenbasis" in meta_desc:
            price_status = "donation"
        elif "8.-/4.-" in meta_desc:
            price_status = "fixed"
            price_amt = 8.0

        pub_evt = {
            "schema_version": "0.1.0",
            "event_id": evt_id,
            "series_id": srs_id,
            "title": title,
            "description": j.get("description"),
            "start_datetime": dt_start.isoformat(),
            "end_datetime": dt_end.isoformat(),
            "timezone": "Europe/Berlin",
            "venue_id": venue_id,
            "venue_name": venue_name,
            "lor_id": lor_id,
            "lor_name": lor_name,
            "category": "arts_culture",
            "price_status": price_status,
            "price_amount": price_amt,
            "price_amount_max": None,
            "price_currency": "EUR",
            "price_note": "Extracted from page meta description",
            "original_event_url": j.get("url") or f"https://www.lettretage.de{item['slug']}",
            "source_url": "https://www.lettretage.de/programm",
            "observed_at": "2026-11-27T12:00:00+01:00",
            "verified_at": "2026-11-27T12:00:00+01:00",
            "extraction_method": "jsonld",
            "extraction_evidence": "schema.org/Event JSON-LD with verified Veteranenstr. 21 address",
            "event_status": "scheduled",
            "source_freshness": "fresh",
            "language": "de",
        }
        occurrences.append(pub_evt)

    # Write files
    canonical_dir = repo / "data" / "canonical"
    canonical_dir.mkdir(parents=True, exist_ok=True)
    public_dir = repo / "data" / "public"

    (canonical_dir / "event_series.json").write_text(
        json.dumps({"schema_version": "0.4.0", "count": len(series_map), "series": list(series_map.values())}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (canonical_dir / "event_occurrences.json").write_text(
        json.dumps({"schema_version": "0.4.0", "count": len(occurrences), "occurrences": occurrences}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    public_events_payload = {
        "schema_version": "0.1.0",
        "generated_at": datetime.now(BERLIN_TZ).isoformat(),
        "count": len(occurrences),
        "events": occurrences,
    }
    (public_dir / "events.json").write_text(
        json.dumps(public_events_payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Verification against event.schema.json
    import jsonschema
    schema_path = repo / "docs" / "feasibility" / "artifacts" / "event.schema.json"
    ev_schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(ev_schema)
    errors = [err.message for ev in occurrences for err in validator.iter_errors(ev)]
    if errors:
        raise ValueError(f"Compiled events failed schema validation ({len(errors)} errors): {errors[:3]}")

    counts_by_venue: dict[str, int] = {}
    for ev in occurrences:
        counts_by_venue[ev["venue_id"]] = counts_by_venue.get(ev["venue_id"], 0) + 1

    return {
        "total_publishable_events": len(occurrences),
        "distinct_series": len(series_map),
        "counts_by_venue": counts_by_venue,
    }


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[3]
    result = compile_events(repo_root)
    print("Compilation complete:", result)
