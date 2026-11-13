"""Task B — Nearest station matching (Dai backend).

Ranks rail stations by **straight-line (great-circle / Haversine) distance**
from a point. This is NOT walking distance, NOT walking time and NOT distance to
a station exit — station coordinates are single points, and 55 of them are
provisional OSM points (``OSM_PROVISIONAL``).

CLI::

    python station_matching.py 13.7462 100.5347 --top-k 5
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from typing import Any, Optional

from data_loader import Dataset, PathLike, Station, load_dataset

EARTH_RADIUS_M: float = 6_371_008.8
DISTANCE_METHOD = "haversine_straight_line"
FAR_FROM_NETWORK_M: float = 3_000.0
SAME_STATION_MAX_M: float = 300.0
TOP_K_MIN, TOP_K_MAX = 1, 10
TRUSTED_QA = {"WITHIN_100M", "WITHIN_200M"}

STATUS_OK = "OK"
STATUS_FAR = "FAR_FROM_NETWORK"
STATUS_INVALID = "INVALID_COORDINATES"
STATUS_POI_NOT_CONFIRMED = "POI_NOT_CONFIRMED"


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle (straight-line) distance in metres between two WGS84 points.

    Uses the mean Earth radius 6,371,008.8 m. This is *not* a walking distance.
    """
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def validate_coordinates(lat: Any, lon: Any) -> Optional[str]:
    """Return an error message if (lat, lon) is invalid, else ``None``."""
    try:
        lat_f, lon_f = float(lat), float(lon)
    except (TypeError, ValueError):
        return "latitude/longitude must be numbers"
    if isinstance(lat, bool) or isinstance(lon, bool):
        return "latitude/longitude must be numbers"
    if math.isnan(lat_f) or math.isnan(lon_f) or math.isinf(lat_f) or math.isinf(lon_f):
        return "latitude/longitude must be finite (not NaN/inf)"
    if not -90.0 <= lat_f <= 90.0:
        return f"latitude {lat_f} out of range [-90, 90]"
    if not -180.0 <= lon_f <= 180.0:
        return f"longitude {lon_f} out of range [-180, 180]"
    return None


def coordinate_warning(station: Station) -> bool:
    """True if the station coordinate is provisional or outside the trusted QA bands."""
    return station.coordinate_origin == "OSM_PROVISIONAL" or station.coordinate_qa_status not in TRUSTED_QA


def _norm_name(name: str) -> str:
    """Lower-case name without a trailing parenthetical, e.g. 'Bang Wa (Blue)' -> 'bang wa'."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", name).strip().lower()


def build_station_groups(ds: Dataset) -> dict[str, str]:
    """Map every station_line_id to a group id representing one physical station.

    Two records are grouped when either
      * they share a name (``name_th`` equal, or ``name_en`` equal ignoring a
        trailing parenthetical) AND are <= 300 m apart, or
      * they are joined by a TRANSFER whose ``distance_m_from_file`` is 0.
    The group id is the alphabetically smallest member id.
    """
    parent: dict[str, str] = {sid: sid for sid in ds.stations}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    stations = list(ds.stations.values())
    for i, a in enumerate(stations):
        for b in stations[i + 1:]:
            same_name = (a.name_th and a.name_th == b.name_th) or _norm_name(a.name_en) == _norm_name(b.name_en)
            if same_name and haversine_m(a.latitude, a.longitude, b.latitude, b.longitude) <= SAME_STATION_MAX_M:
                union(a.station_line_id, b.station_line_id)
    for c in ds.interchanges:
        if c.connection_category == "TRANSFER" and c.distance_m_from_file == 0:
            union(c.station_line_id_a, c.station_line_id_b)

    return {sid: find(sid) for sid in ds.stations}


_GROUP_CACHE: dict[str, dict[str, str]] = {}


def _groups_for(ds: Dataset) -> dict[str, str]:
    key = str(ds.data_dir)
    if key not in _GROUP_CACHE:
        _GROUP_CACHE[key] = build_station_groups(ds)
    return _GROUP_CACHE[key]


def _station_entry(ds: Dataset, st: Station, distance_m: float, members: list[str]) -> dict[str, Any]:
    member_objs = [ds.stations[m] for m in members]
    return {
        "station_line_id": st.station_line_id,
        "station_line_ids": members,
        "name_en": st.name_en,
        "name_th": st.name_th,
        "line_id": st.line_id,
        "line_ids": sorted({m.line_id for m in member_objs}),
        "line_name_th": ds.line_name_th(st.line_id),
        "latitude": st.latitude,
        "longitude": st.longitude,
        "distance_m": round(distance_m, 1),
        "coordinate_origin": st.coordinate_origin,
        "coordinate_qa_status": st.coordinate_qa_status,
        "coordinate_warning": any(coordinate_warning(m) for m in member_objs),
    }


def find_nearest_stations(
    lat: float,
    lon: float,
    top_k: int = 5,
    group_same_station: bool = True,
    data_dir: Optional[PathLike] = None,
    query: Optional[str] = None,
    poi: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Rank stations by straight-line (Haversine) distance from ``(lat, lon)``.

    ``distance_m`` is a **straight-line distance between coordinate points** —
    not walking distance/time and not distance to the nearest station exit.

    Args:
        lat, lon: WGS84 coordinates of the POI.
        top_k: number of options to return (clamped to 1–10; 3–5 recommended).
        group_same_station: merge station-line records of one physical station
            (e.g. ``BTS-SUK:CEN`` + ``BTS-SIL:CEN``) into one option; the full
            list is kept in ``station_line_ids`` (nearest first).
        data_dir: dataset folder override.
        query, poi: echoed back in the result (Integration Contract #1).

    Returns:
        ``{"query", "poi", "nearest_stations", "distance_method", "status",
        "warnings", "message"}`` with status ``OK``, ``FAR_FROM_NETWORK`` or
        ``INVALID_COORDINATES``.
    """
    poi_out = dict(poi) if poi else {"name": query, "latitude": lat, "longitude": lon, "provider": None}
    result: dict[str, Any] = {
        "query": query,
        "poi": poi_out,
        "nearest_stations": [],
        "distance_method": DISTANCE_METHOD,
        "status": STATUS_OK,
        "warnings": [],
        "message": "",
    }
    err = validate_coordinates(lat, lon)
    if err:
        result.update(status=STATUS_INVALID, message=err)
        return result
    lat, lon = float(lat), float(lon)
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        top_k = 5
    top_k = max(TOP_K_MIN, min(TOP_K_MAX, top_k))

    ds = load_dataset(data_dir)
    dists = sorted(
        ((haversine_m(lat, lon, st.latitude, st.longitude), sid) for sid, st in ds.stations.items()),
        key=lambda t: (t[0], t[1]),
    )

    entries: list[dict[str, Any]] = []
    if group_same_station:
        groups = _groups_for(ds)
        seen: dict[str, list[str]] = {}
        order: list[tuple[float, str]] = []
        for d, sid in dists:
            g = groups[sid]
            if g not in seen:
                seen[g] = []
                order.append((d, sid))
            seen[g].append(sid)
        for d, sid in order[:top_k]:
            entries.append(_station_entry(ds, ds.stations[sid], d, seen[groups[sid]]))
    else:
        for d, sid in dists[:top_k]:
            entries.append(_station_entry(ds, ds.stations[sid], d, [sid]))

    result["nearest_stations"] = entries
    if entries and entries[0]["distance_m"] > FAR_FROM_NETWORK_M:
        result["status"] = STATUS_FAR
        result["warnings"].append(
            f"Nearest station is {entries[0]['distance_m']:.0f} m away (straight line) — beyond {FAR_FROM_NETWORK_M:.0f} m."
        )
    if any(e["coordinate_warning"] for e in entries):
        result["warnings"].append("Some station coordinates are provisional or not within 200 m QA — verify on a map.")
    result["message"] = "Distances are straight-line (Haversine) between coordinate points, not walking distance."
    return result


def _extract_candidate(poi_input: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """Accept a Task-A candidate or a whole ``search_poi`` result; return (candidate, error)."""
    if "candidates" in poi_input and "latitude" not in poi_input:
        if poi_input.get("selected") is not None:
            return poi_input["selected"], None
        if poi_input.get("needs_confirmation"):
            return None, "POI search result is ambiguous — call confirm_poi(result, index) first."
        cands = poi_input.get("candidates") or []
        if poi_input.get("status") == "OK" and cands:
            return cands[0], None
        return None, f"POI search result has status {poi_input.get('status')} and no usable candidate."
    return poi_input, None


def match_poi_to_stations(
    poi_dict: dict[str, Any],
    top_k: int = 5,
    group_same_station: bool = True,
    data_dir: Optional[PathLike] = None,
) -> dict[str, Any]:
    """Match a POI from Task A (``poi_search``) to its nearest stations.

    ``poi_dict`` may be a single candidate (``name``, ``latitude``, ``longitude``,
    ``provider`` …) or a full ``search_poi``/``confirm_poi`` result. An
    unconfirmed AMBIGUOUS result is rejected with ``POI_NOT_CONFIRMED`` rather
    than silently picking a candidate.
    """
    cand, err = _extract_candidate(poi_dict or {})
    query = (poi_dict or {}).get("query")
    if err or cand is None:
        return {
            "query": query,
            "poi": None,
            "nearest_stations": [],
            "distance_method": DISTANCE_METHOD,
            "status": STATUS_POI_NOT_CONFIRMED,
            "warnings": [],
            "message": err or "No POI candidate supplied.",
        }
    poi = {
        "name": cand.get("name") or cand.get("display_name"),
        "latitude": cand.get("latitude"),
        "longitude": cand.get("longitude"),
        "provider": cand.get("provider"),
        "source_id": cand.get("source_id"),
        "source_url": cand.get("source_url"),
    }
    return find_nearest_stations(
        cand.get("latitude"),
        cand.get("longitude"),
        top_k=top_k,
        group_same_station=group_same_station,
        data_dir=data_dir,
        query=query or poi["name"],
        poi=poi,
    )


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Nearest stations by straight-line distance")
    p.add_argument("lat", type=float)
    p.add_argument("lon", type=float)
    p.add_argument("--top-k", type=int, default=5)
    p.add_argument("--no-group", action="store_true", help="do not merge same-station records")
    p.add_argument("--data-dir", default=None)
    a = p.parse_args(argv)
    res = find_nearest_stations(a.lat, a.lon, a.top_k, not a.no_group, a.data_dir)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0 if res["status"] != STATUS_INVALID else 2


if __name__ == "__main__":
    raise SystemExit(main())
