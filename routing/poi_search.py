"""Task A — POI search / geocoding (Dai backend).

Default provider: **Nominatim** (OpenStreetMap), used under the Nominatim
Usage Policy (https://operations.osmfoundation.org/policies/nominatim/):

* identifying ``User-Agent`` (env ``NOMINATIM_USER_AGENT``)
* at most 1 request per second (process-wide throttle)
* 10 s timeout
* results are cached on disk (``.cache/nominatim/``) so the same query is not
  sent twice

Search area: ``viewbox`` = bounding box of all 195 stations in the dataset
(via ``data_loader``) expanded by ``VIEWBOX_MARGIN_DEG`` on every side, with
``bounded=1`` so results outside Bangkok & vicinity are not returned. No
further filtering (by station distance or province) is applied.

``search_poi`` never raises: every failure becomes a status code. It also never
silently picks a candidate when results are ambiguous — use ``confirm_poi``.

CLI::

    python poi_search.py "ตลาดนัดเซฟวัน"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import threading
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Callable, Optional

import requests

STATUS_OK = "OK"
STATUS_AMBIGUOUS = "AMBIGUOUS"
STATUS_NOT_FOUND = "NOT_FOUND"
STATUS_NETWORK_ERROR = "NETWORK_ERROR"
STATUS_RATE_LIMITED = "RATE_LIMITED"
STATUS_INVALID_QUERY = "INVALID_QUERY"
STATUS_CONFIRMED = "CONFIRMED"
STATUS_INVALID_SELECTION = "INVALID_SELECTION"

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
DEFAULT_USER_AGENT = "DSI463-ThaiTransportPlanner/0.1 (student project)"
USER_AGENT_ENV = "NOMINATIM_USER_AGENT"
# Margin (degrees, ≈5.5 km) added around the station bounding box to form the Nominatim viewbox.
VIEWBOX_MARGIN_DEG = 0.05
REQUEST_TIMEOUT_S = 10.0
MIN_INTERVAL_S = 1.0
MAX_QUERY_LEN = 200
MAX_LIMIT = 10
DEFAULT_CACHE_DIR = Path(__file__).resolve().parent / ".cache" / "nominatim"

# Candidates with the same name within this straight-line distance are the same place (e.g. node + way).
DUPLICATE_RADIUS_M = 150.0


def compute_viewbox(margin_deg: float = VIEWBOX_MARGIN_DEG, data_dir: Optional[Any] = None) -> str:
    """Nominatim ``viewbox`` ("left,top,right,bottom" = lon_min,lat_max,lon_max,lat_min) covering every
    station in the dataset, expanded by ``margin_deg`` degrees on each side."""
    from data_loader import load_dataset  # local import keeps provider usable without the dataset in tests

    stations = load_dataset(data_dir).stations.values()
    lats = [s.latitude for s in stations]
    lons = [s.longitude for s in stations]
    left, right = min(lons) - margin_deg, max(lons) + margin_deg
    bottom, top = min(lats) - margin_deg, max(lats) + margin_deg
    return f"{left:.6f},{top:.6f},{right:.6f},{bottom:.6f}"


class ProviderError(Exception):
    """Base class for geocoder failures."""


class RateLimitedError(ProviderError):
    """Provider answered HTTP 429."""


class ProviderNetworkError(ProviderError):
    """Connection error, timeout, bad HTTP status or unparsable response."""


class GeocodingProvider(ABC):
    """Minimal geocoder interface — implement ``search`` to plug in another provider."""

    name: str = "provider"

    @abstractmethod
    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Return normalised candidates (see ``search_poi``). Raise ``ProviderError`` on failure."""


class _Throttle:
    """Process-wide minimum interval between requests (thread-safe)."""

    def __init__(self, interval_s: float, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        self.interval_s = interval_s
        self.clock = clock
        self.sleep = sleep
        self._last: Optional[float] = None
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = self.clock()
            if self._last is not None:
                remaining = self.interval_s - (now - self._last)
                if remaining > 0:
                    self.sleep(remaining)
            self._last = self.clock()


_NOMINATIM_THROTTLE = _Throttle(MIN_INTERVAL_S)


class NominatimProvider(GeocodingProvider):
    """Nominatim ``/search`` geocoder with on-disk JSON cache and 1 req/s throttle."""

    name = "nominatim"

    def __init__(
        self,
        user_agent: Optional[str] = None,
        cache_dir: Optional[Path] = DEFAULT_CACHE_DIR,
        session: Optional[requests.Session] = None,
        throttle: Optional[_Throttle] = None,
        url: str = NOMINATIM_URL,
        viewbox: Optional[str] = None,
        data_dir: Optional[Any] = None,
    ) -> None:
        self.user_agent = user_agent or os.environ.get(USER_AGENT_ENV) or DEFAULT_USER_AGENT
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.session = session or requests.Session()
        self.throttle = throttle or _NOMINATIM_THROTTLE
        self.url = url
        self.viewbox = viewbox or compute_viewbox(data_dir=data_dir)
        self.last_from_cache = False

    def _params(self, query: str, limit: int) -> dict[str, Any]:
        return {
            "q": query,
            "format": "jsonv2",
            "countrycodes": "th",
            "accept-language": "th,en",
            "viewbox": self.viewbox,
            "bounded": 1,
            "limit": limit,
            "addressdetails": 0,
        }

    def _cache_path(self, params: dict[str, Any]) -> Optional[Path]:
        if not self.cache_dir:
            return None
        key = json.dumps(params, sort_keys=True, ensure_ascii=False)
        return self.cache_dir / (hashlib.sha256(key.encode("utf-8")).hexdigest()[:32] + ".json")

    def fetch_raw(self, query: str, limit: int) -> list[dict[str, Any]]:
        """Raw Nominatim JSON list (from cache if available)."""
        params = self._params(query, limit)
        cpath = self._cache_path(params)
        if cpath and cpath.is_file():
            try:
                cached = json.loads(cpath.read_text(encoding="utf-8"))
                self.last_from_cache = True
                return cached["response"]
            except (OSError, ValueError, KeyError):
                pass  # corrupt cache entry → refetch
        self.last_from_cache = False
        self.throttle.wait()
        try:
            resp = self.session.get(
                self.url,
                params=params,
                headers={"User-Agent": self.user_agent, "Accept-Language": "th,en"},
                timeout=REQUEST_TIMEOUT_S,
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            raise ProviderNetworkError(f"{type(exc).__name__}: {exc}") from exc
        except requests.RequestException as exc:
            raise ProviderNetworkError(f"Request failed: {exc}") from exc
        if resp.status_code == 429:
            raise RateLimitedError("HTTP 429 Too Many Requests from Nominatim")
        if resp.status_code != 200:
            raise ProviderNetworkError(f"HTTP {resp.status_code} from Nominatim")
        try:
            data = resp.json()
        except ValueError as exc:
            raise ProviderNetworkError("Nominatim returned non-JSON content") from exc
        if not isinstance(data, list):
            raise ProviderNetworkError("Unexpected Nominatim response shape")
        if cpath:
            try:
                cpath.parent.mkdir(parents=True, exist_ok=True)
                cpath.write_text(
                    json.dumps({"params": params, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                "response": data}, ensure_ascii=False, indent=1),
                    encoding="utf-8",
                )
            except OSError:
                pass  # cache is best-effort
        return data

    def search(self, query: str, limit: int) -> list[dict[str, Any]]:
        return [c for c in (normalize_nominatim(item) for item in self.fetch_raw(query, limit)) if c]


def normalize_nominatim(item: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convert one Nominatim jsonv2 item to the candidate schema (``None`` if unusable)."""
    try:
        lat, lon = float(item["lat"]), float(item["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    osm_type, osm_id = item.get("osm_type"), item.get("osm_id")
    display = item.get("display_name") or ""
    name = item.get("name") or display.split(",")[0].strip()
    try:
        importance = float(item.get("importance")) if item.get("importance") is not None else None
    except (TypeError, ValueError):
        importance = None
    return {
        "name": name,
        "display_name": display,
        "latitude": lat,
        "longitude": lon,
        "provider": "nominatim",
        "source_id": f"osm:{osm_type}/{osm_id}" if osm_type and osm_id is not None else None,
        "source_url": f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id is not None else None,
        "category": item.get("category") or item.get("class"),
        "type": item.get("type"),
        "importance": importance,
    }


def _dist_m(a: dict[str, Any], b: dict[str, Any]) -> float:
    p1, p2 = math.radians(a["latitude"]), math.radians(b["latitude"])
    dl = math.radians(b["longitude"] - a["longitude"])
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_008.8 * math.asin(min(1.0, math.sqrt(h)))


def dedupe_candidates(cands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop candidates that repeat an earlier one's name within ``DUPLICATE_RADIUS_M``."""
    out: list[dict[str, Any]] = []
    for c in cands:
        if any(c["name"] == o["name"] and _dist_m(c, o) <= DUPLICATE_RADIUS_M for o in out):
            continue
        out.append(c)
    return out


_DEFAULT_PROVIDER: Optional[GeocodingProvider] = None


def get_default_provider() -> GeocodingProvider:
    """Lazily created module-level Nominatim provider."""
    global _DEFAULT_PROVIDER
    if _DEFAULT_PROVIDER is None:
        _DEFAULT_PROVIDER = NominatimProvider()
    return _DEFAULT_PROVIDER


def _result(query: Any, status: str, candidates: list[dict[str, Any]], message: str,
            needs_confirmation: bool = False, selected: Optional[dict[str, Any]] = None,
            provider: Optional[str] = None, from_cache: bool = False) -> dict[str, Any]:
    return {
        "query": query,
        "status": status,
        "candidates": candidates,
        "needs_confirmation": needs_confirmation,
        "selected": selected,
        "provider": provider,
        "from_cache": from_cache,
        "fallback_query": None,
        "message": message,
    }


# Generic Thai prefixes tried (longest first) when the full query is NOT_FOUND.
FALLBACK_PREFIXES: tuple[str, ...] = ("ตลาดนัด", "ตลาด")


def fallback_query_for(query: str) -> Optional[str]:
    """Return ``query`` with a leading generic prefix (``ตลาดนัด``/``ตลาด``) removed, or ``None``."""
    for prefix in FALLBACK_PREFIXES:
        if query.startswith(prefix):
            rest = query[len(prefix):].strip()
            return rest or None
    return None


def search_poi(query: str, limit: int = 5, provider: Optional[GeocodingProvider] = None) -> dict[str, Any]:
    """Geocode a place name (Thai or English) to POI candidates.

    Status rules:
      * ``INVALID_QUERY`` — empty / non-string / longer than 200 characters
      * ``NOT_FOUND``      — provider returned no usable result (also after fallback)
      * ``OK``             — exactly one result (after merging duplicates);
        ``selected`` = that candidate
      * ``AMBIGUOUS``      — more than one result → ``needs_confirmation`` is
        true and ``selected`` is ``None``; the user picks via ``confirm_poi``.
        Nothing is ever auto-selected from several results.
      * ``RATE_LIMITED``   — HTTP 429
      * ``NETWORK_ERROR``  — timeout, connection error, other HTTP/parse error

    Fallback: if the full query is ``NOT_FOUND`` and starts with ``ตลาดนัด`` or
    ``ตลาด``, the prefix is removed and the search is repeated (same provider,
    so the 1 req/s throttle and the cache still apply). Results found this way
    are **always** ``AMBIGUOUS`` with ``needs_confirmation=true`` and
    ``selected=None`` — even a single hit — because they answer a different
    query; ``fallback_query`` records the query actually used.

    Never raises.
    """
    if not isinstance(query, str) or not query.strip():
        return _result(query, STATUS_INVALID_QUERY, [], "Query must be a non-empty string.")
    q = " ".join(query.split())
    if len(q) > MAX_QUERY_LEN:
        return _result(query, STATUS_INVALID_QUERY, [], f"Query longer than {MAX_QUERY_LEN} characters.")
    try:
        limit = max(1, min(MAX_LIMIT, int(limit)))
    except (TypeError, ValueError):
        limit = 5
    try:
        prov = provider or get_default_provider()
    except Exception as exc:  # noqa: BLE001 — e.g. dataset missing when computing the viewbox
        return _result(q, STATUS_NETWORK_ERROR, [], f"Geocoder could not be initialised: {type(exc).__name__}: {exc}")
    res = _search_once(q, limit, prov)
    if res["status"] != STATUS_NOT_FOUND:
        return res
    fq = fallback_query_for(q)
    if not fq:
        return res
    fb = _search_once(fq, limit, prov)
    fb["query"] = q
    fb["fallback_query"] = fq
    if fb["status"] in (STATUS_OK, STATUS_AMBIGUOUS):
        fb.update(
            status=STATUS_AMBIGUOUS,
            needs_confirmation=True,
            selected=None,
            message=(f"'{q}' not found; fallback query '{fq}' returned {len(fb['candidates'])} candidate(s) — "
                     "these may be a different place. Please confirm one with confirm_poi(result, index)."),
        )
    elif fb["status"] == STATUS_NOT_FOUND:
        fb["message"] = f"No place found for '{q}' nor for fallback query '{fq}'."
    else:
        fb["message"] = f"'{q}' not found; fallback query '{fq}' failed: {fb['message']}"
    return fb


def _search_once(q: str, limit: int, prov: GeocodingProvider) -> dict[str, Any]:
    """One provider call → result dict (no fallback). Never raises."""
    pname = getattr(prov, "name", "provider")
    try:
        cands = prov.search(q, limit)
    except RateLimitedError as exc:
        return _result(q, STATUS_RATE_LIMITED, [], f"Geocoder rate limit: {exc}. Try again later.", provider=pname)
    except ProviderError as exc:
        return _result(q, STATUS_NETWORK_ERROR, [], f"Geocoder unavailable: {exc}", provider=pname)
    except Exception as exc:  # noqa: BLE001 — contract: never leak exceptions
        return _result(q, STATUS_NETWORK_ERROR, [], f"Unexpected geocoder error: {type(exc).__name__}: {exc}",
                       provider=pname)
    from_cache = bool(getattr(prov, "last_from_cache", False))
    cands = dedupe_candidates(cands)
    if not cands:
        return _result(q, STATUS_NOT_FOUND, [], "No place found for this query.", provider=pname, from_cache=from_cache)
    if len(cands) == 1:
        return _result(q, STATUS_OK, cands, "One result found.", False, cands[0], pname, from_cache)
    return _result(q, STATUS_AMBIGUOUS, cands,
                   f"{len(cands)} possible places — please confirm one with confirm_poi(result, index).",
                   True, None, pname, from_cache)


def confirm_poi(result: dict[str, Any], index: int) -> dict[str, Any]:
    """Return a copy of ``result`` with candidate ``index`` chosen by the user.

    Status becomes ``CONFIRMED`` with ``selected`` set and
    ``needs_confirmation`` false; an out-of-range index or a result without
    candidates gives ``INVALID_SELECTION`` (no exception).
    """
    out = dict(result or {})
    cands = out.get("candidates") or []
    if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(cands):
        out.update(status=STATUS_INVALID_SELECTION,
                   message=f"Index {index!r} is not a valid candidate (0..{len(cands) - 1}).")
        return out
    out.update(status=STATUS_CONFIRMED, selected=cands[index], needs_confirmation=False,
               message=f"User confirmed candidate {index}: {cands[index]['name']}")
    return out


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Geocode a POI with Nominatim")
    p.add_argument("query")
    p.add_argument("--limit", type=int, default=5)
    p.add_argument("--stations", type=int, default=0, metavar="K",
                   help="also list K nearest stations (straight-line) for the selected/top candidate")
    a = p.parse_args(argv)
    res = search_poi(a.query, a.limit)
    out: dict[str, Any] = {"poi_search": res}
    if a.stations and res["candidates"]:
        from station_matching import match_poi_to_stations
        cand = res["selected"] or res["candidates"][0]
        out["stations_for_candidate"] = match_poi_to_stations(cand, a.stations)
        if res["selected"] is None:
            out["note"] = "AMBIGUOUS: stations shown for candidate 0 only as a preview; user must confirm."
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if res["status"] in (STATUS_OK, STATUS_AMBIGUOUS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
