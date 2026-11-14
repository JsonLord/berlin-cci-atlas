"""Point-in-polygon LOR assignment, and a guard against a known naming trap.

Verified facts this module encodes:
  * LOR_BZR has 143 features, LOR_PLR has 542 — matching official Berlin LOR.
  * Every 8-digit Planungsräum id begins with a real 6-digit Bezirksregion id.
  * Bezirksregion NAMES are NOT unique: 'Heerstraße' is both 042002
    (Charlottenburg-Wilmersdorf) and 052005 (Spandau). All joins therefore use
    the id; a test asserts this so the trap can never be reintroduced.
"""

from __future__ import annotations

from dataclasses import dataclass

from shapely.geometry import Point, shape
from shapely.strtree import STRtree


@dataclass
class LorIndex:
    plr_features: list[dict]
    bzr_features: list[dict]
    _plr_geoms: list = None  # type: ignore[assignment]
    _bzr_geoms: list = None  # type: ignore[assignment]
    _plr_tree: object = None
    _bzr_tree: object = None
    plr_by_id: dict = None  # type: ignore[assignment]
    bzr_by_id: dict = None  # type: ignore[assignment]

    @classmethod
    def build(cls, lor_plr: dict, lor_bzr: dict) -> "LorIndex":
        obj = cls(
            plr_features=lor_plr["features"],
            bzr_features=lor_bzr["features"],
        )
        obj._plr_geoms = [shape(f["geometry"]) for f in obj.plr_features]
        obj._bzr_geoms = [shape(f["geometry"]) for f in obj.bzr_features]
        obj._plr_tree = STRtree(obj._plr_geoms)
        obj._bzr_tree = STRtree(obj._bzr_geoms)
        obj.plr_by_id = {f["properties"]["id"]: f["properties"] for f in obj.plr_features}
        obj.bzr_by_id = {f["properties"]["id"]: f["properties"] for f in obj.bzr_features}
        return obj

    def locate(self, lon: float, lat: float) -> tuple[str | None, str | None]:
        """Return (plr_id, bzr_id) containing the point, or (None, None)."""
        pt = Point(lon, lat)
        plr_id = bzr_id = None
        for i in self._plr_tree.query(pt):
            if self._plr_geoms[i].contains(pt):
                plr_id = self.plr_features[i]["properties"]["id"]
                break
        for i in self._bzr_tree.query(pt):
            if self._bzr_geoms[i].contains(pt):
                bzr_id = self.bzr_features[i]["properties"]["id"]
                break
        return plr_id, bzr_id

    def bzr_of_plr(self, plr_id: str) -> str | None:
        """Bezirksregion id implied by an 8-digit Planungsräum id."""
        return plr_id[:6] if plr_id and len(plr_id) == 8 else None

    def duplicate_bzr_names(self) -> dict[str, list[str]]:
        """Bezirksregion names shared by more than one id."""
        seen: dict[str, list[str]] = {}
        for f in self.bzr_features:
            seen.setdefault(f["properties"]["name"], []).append(f["properties"]["id"])
        return {k: v for k, v in seen.items() if len(v) > 1}
