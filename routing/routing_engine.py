"""Task C — Routing engine (Dai backend).

Graph
-----
* node  = ``station_line_id`` (never station_code or name)
* edges = RIDE (``ride_edges_master.csv``) + TRANSFER / BRANCH_JUNCTION
  (``interchanges_master.csv``)

NOTE: every connection is treated as **bidirectional**, as stated in the
dataset README for prototype testing. Operational directionality (one-way
segments, branch service patterns, transfer conditions) MUST be verified before
production use.

Optimisation modes (lexicographic tuple costs, Dijkstra with ``heapq``)
-----------------------------------------------------------------------
* ``shortest_edges``   : minimise (total edges RIDE+TRANSFER+BRANCH_JUNCTION, TRANSFERs)
* ``fewest_transfers`` : minimise (TRANSFERs, RIDEs, BRANCH_JUNCTIONs)

``BRANCH_JUNCTION`` is never counted as a transfer.

This module does not know travel times or fares; it never claims a route is
fastest or cheapest. ``find_alternative_routes`` exists so the Fare Engine can
compare several real alternatives during Integration.

CLI::

    python routing_engine.py ARL:A1 MRT-BLU:BL04 --mode fewest_transfers --json
"""

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import sys
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Optional, Sequence

from data_loader import Dataset, PathLike, load_dataset, resolve_data_dir

RIDE = "RIDE"
TRANSFER = "TRANSFER"
BRANCH_JUNCTION = "BRANCH_JUNCTION"

MODE_SHORTEST_EDGES = "shortest_edges"
MODE_FEWEST_TRANSFERS = "fewest_transfers"
MODES = (MODE_SHORTEST_EDGES, MODE_FEWEST_TRANSFERS)

STATUS_OK = "OK"
STATUS_SAME_STATION = "SAME_STATION"
STATUS_NO_ROUTE = "NO_ROUTE"
STATUS_UNKNOWN_STATION = "UNKNOWN_STATION"
STATUS_INVALID_OPTIMIZATION = "INVALID_OPTIMIZATION"

Cost = tuple[int, ...]


@dataclass(frozen=True)
class Edge:
    """A directed view of one (bidirectional) connection."""

    src: str
    dst: str
    type: str
    line_id: Optional[str]
    edge_id: str
    distance_m_from_file: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "from": self.src,
            "to": self.dst,
            "type": self.type,
            "line_id": self.line_id,
            "edge_id": self.edge_id,
        }
        if self.type != RIDE:
            d["connection_id"] = self.edge_id
        return d


def edge_cost(edge: Edge, mode: str) -> Cost:
    """Per-edge cost vector for ``mode`` (summed component-wise along a path)."""
    is_t = 1 if edge.type == TRANSFER else 0
    is_r = 1 if edge.type == RIDE else 0
    is_b = 1 if edge.type == BRANCH_JUNCTION else 0
    if mode == MODE_SHORTEST_EDGES:
        return (1, is_t, 0)
    return (is_t, is_r, is_b)


def _add(a: Cost, b: Cost) -> Cost:
    return tuple(x + y for x, y in zip(a, b))


def path_cost(edges: Sequence[Edge], mode: str) -> Cost:
    """Total lexicographic cost of a path."""
    total: Cost = (0, 0, 0)
    for e in edges:
        total = _add(total, edge_cost(e, mode))
    return total


class RoutingEngine:
    """Graph + routing algorithms over one dataset."""

    def __init__(self, data_dir: Optional[PathLike] = None, dataset: Optional[Dataset] = None) -> None:
        self.ds: Dataset = dataset or load_dataset(data_dir)
        self.adj: dict[str, list[Edge]] = {sid: [] for sid in self.ds.stations}
        # Bidirectional — see module docstring: verify real directionality before production.
        for r in self.ds.ride_edges:
            self.adj[r.source].append(Edge(r.source, r.target, RIDE, r.line_id, r.edge_id))
            self.adj[r.target].append(Edge(r.target, r.source, RIDE, r.line_id, r.edge_id))
        for c in self.ds.interchanges:
            a, b = c.station_line_id_a, c.station_line_id_b
            self.adj[a].append(Edge(a, b, c.connection_category, None, c.connection_id, c.distance_m_from_file))
            self.adj[b].append(Edge(b, a, c.connection_category, None, c.connection_id, c.distance_m_from_file))
        for sid in self.adj:
            self.adj[sid].sort(key=lambda e: (e.dst, e.edge_id))

    # ------------------------------------------------------------------ core
    def shortest_path(
        self,
        origin: str,
        dest: str,
        mode: str,
        blocked_edges: frozenset[tuple[str, str, str]] = frozenset(),
        blocked_nodes: frozenset[str] = frozenset(),
    ) -> Optional[list[Edge]]:
        """Dijkstra with tuple costs. Returns a list of edges, ``[]`` if origin == dest, or ``None``."""
        if origin == dest:
            return []
        best: dict[str, Cost] = {origin: (0, 0, 0)}
        prev: dict[str, Edge] = {}
        heap: list[tuple[Cost, str]] = [((0, 0, 0), origin)]
        done: set[str] = set()
        while heap:
            cost, node = heapq.heappop(heap)
            if node in done:
                continue
            done.add(node)
            if node == dest:
                break
            for e in self.adj[node]:
                if e.dst in blocked_nodes or e.dst in done or (e.src, e.dst, e.edge_id) in blocked_edges:
                    continue
                nc = _add(cost, edge_cost(e, mode))
                if e.dst not in best or nc < best[e.dst]:
                    best[e.dst] = nc
                    prev[e.dst] = e
                    heapq.heappush(heap, (nc, e.dst))
        if dest not in done:
            return None
        path: list[Edge] = []
        cur = dest
        while cur != origin:
            e = prev[cur]
            path.append(e)
            cur = e.src
        path.reverse()
        return path

    def k_shortest_paths(self, origin: str, dest: str, k: int, mode: str) -> list[list[Edge]]:
        """Yen's algorithm: up to ``k`` loopless paths in increasing ``mode`` cost."""
        first = self.shortest_path(origin, dest, mode)
        if first is None:
            return []
        found: list[list[Edge]] = [first]
        candidates: list[tuple[Cost, tuple[str, ...], list[Edge]]] = []
        seen_keys: set[tuple[str, ...]] = {_edge_key(first)}
        while len(found) < k:
            last = found[-1]
            last_nodes = _nodes(origin, last)
            for i in range(len(last)):
                spur = last_nodes[i]
                root_edges = last[:i]
                root_nodes = last_nodes[: i + 1]
                blocked_e = set()
                for p in found:
                    if _nodes(origin, p)[: i + 1] == root_nodes and len(p) > i:
                        blocked_e.add((p[i].src, p[i].dst, p[i].edge_id))
                spur_path = self.shortest_path(
                    spur, dest, mode, frozenset(blocked_e), frozenset(root_nodes[:-1])
                )
                if spur_path is None:
                    continue
                total = root_edges + spur_path
                key = _edge_key(total)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                heapq.heappush(candidates, (path_cost(total, mode), key, total))
            if not candidates:
                break
            _, _, nxt = heapq.heappop(candidates)
            found.append(nxt)
        return found

    # ------------------------------------------------------------- results
    def _same_station_link(self, a: str, b: str) -> Optional[Edge]:
        for e in self.adj.get(a, []):
            if e.dst == b and e.type == TRANSFER and e.distance_m_from_file == 0:
                return e
        return None

    def build_route(
        self,
        origin: str,
        dest: str,
        edges: list[Edge],
        optimization: str,
        status: str = STATUS_OK,
        route_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Turn an edge list into the structured route dict (Integration Contract #2)."""
        nodes = _nodes(origin, edges)
        ride = sum(1 for e in edges if e.type == RIDE)
        transfers = [e for e in edges if e.type == TRANSFER]
        branches = [e for e in edges if e.type == BRANCH_JUNCTION]
        legs = self._legs(edges)
        lines_used: list[str] = []
        for leg in legs:
            if leg["line_id"] not in lines_used:
                lines_used.append(leg["line_id"])
        return {
            "route_id": route_id or _route_id(optimization, nodes),
            "status": status,
            "optimization": optimization,
            "origin": origin,
            "destination": dest,
            "station_line_ids": nodes,
            "edges": [e.to_dict() for e in edges],
            "summary": {
                "ride_count": ride,
                "transfer_count": len(transfers),
                "branch_junction_count": len(branches),
                "edge_count": len(edges),
                "lines_used": lines_used,
            },
            "legs": legs,
            "transfers": [
                {"from": e.src, "to": e.dst, "connection_id": e.edge_id, "distance_m_from_file": e.distance_m_from_file}
                for e in transfers
            ],
            "branch_junctions": [{"from": e.src, "to": e.dst, "connection_id": e.edge_id} for e in branches],
            "message": "",
        }

    def _legs(self, edges: list[Edge]) -> list[dict[str, Any]]:
        legs: list[dict[str, Any]] = []
        entered_via = "START"
        cur: Optional[dict[str, Any]] = None
        for e in edges:
            if e.type == RIDE:
                if cur is None or cur["line_id"] != e.line_id:
                    cur = {
                        "line_id": e.line_id,
                        "line_name_th": self.ds.line_name_th(e.line_id or ""),
                        "from": e.src,
                        "to": e.dst,
                        "station_line_ids": [e.src, e.dst],
                        "stations": 2,
                        "rides": 1,
                        "entered_via": entered_via,
                    }
                    legs.append(cur)
                else:
                    cur["to"] = e.dst
                    cur["station_line_ids"].append(e.dst)
                    cur["stations"] += 1
                    cur["rides"] += 1
            else:
                cur = None
                entered_via = e.type
        return legs

    def _error(self, origin: Any, dest: Any, optimization: str, status: str, message: str, **extra: Any) -> dict[str, Any]:
        out = {
            "route_id": None,
            "status": status,
            "optimization": optimization,
            "origin": origin,
            "destination": dest,
            "station_line_ids": [],
            "edges": [],
            "summary": {"ride_count": 0, "transfer_count": 0, "branch_junction_count": 0, "edge_count": 0, "lines_used": []},
            "legs": [],
            "transfers": [],
            "branch_junctions": [],
            "message": message,
        }
        out.update(extra)
        return out

    def find_route(
        self, origin_id: str, dest_id: str, optimization: str = MODE_FEWEST_TRANSFERS, route_id: Optional[str] = None
    ) -> dict[str, Any]:
        """Best route between two ``station_line_id`` values for one optimisation mode.

        Never raises for bad input: returns ``UNKNOWN_STATION``, ``NO_ROUTE``,
        ``INVALID_OPTIMIZATION`` or ``SAME_STATION`` statuses instead.
        """
        if optimization not in MODES:
            return self._error(origin_id, dest_id, optimization, STATUS_INVALID_OPTIMIZATION,
                               f"optimization must be one of {MODES}")
        unknown = [x for x in (origin_id, dest_id) if not isinstance(x, str) or x not in self.ds.stations]
        if unknown:
            return self._error(origin_id, dest_id, optimization, STATUS_UNKNOWN_STATION,
                               f"Unknown station_line_id: {', '.join(map(str, unknown))}", unknown_ids=unknown)
        if origin_id == dest_id:
            r = self.build_route(origin_id, dest_id, [], optimization, STATUS_SAME_STATION, route_id)
            r["message"] = "Origin and destination are the same station-line record."
            return r
        link = self._same_station_link(origin_id, dest_id)
        if link is not None:
            r = self.build_route(origin_id, dest_id, [link], optimization, STATUS_SAME_STATION, route_id)
            r["message"] = "Same physical station on different lines (TRANSFER with distance 0); no ride needed."
            return r
        path = self.shortest_path(origin_id, dest_id, optimization)
        if path is None:
            return self._error(origin_id, dest_id, optimization, STATUS_NO_ROUTE, "No path in the network.")
        return self.build_route(origin_id, dest_id, path, optimization, STATUS_OK, route_id)

    def find_alternative_routes(self, origin_id: str, dest_id: str, k: int = 3) -> list[dict[str, Any]]:
        """Up to ``k`` genuinely different routes (distinct station sequences).

        Combines Yen's k-shortest paths under both modes, de-duplicates by
        station sequence and orders by (transfers, rides). Intended as input
        for fare comparison — this module makes **no claim** about which is
        cheapest. Returns ``[]`` for unknown IDs / no route; a single
        ``SAME_STATION`` route when applicable.
        """
        k = max(1, int(k))
        base = self.find_route(origin_id, dest_id, MODE_FEWEST_TRANSFERS)
        if base["status"] in (STATUS_UNKNOWN_STATION, STATUS_NO_ROUTE):
            return []
        if base["status"] == STATUS_SAME_STATION:
            base["optimization"] = "alternatives"
            base["found_by"] = [MODE_FEWEST_TRANSFERS]
            return [base]
        pool: dict[tuple[str, ...], tuple[list[Edge], set[str]]] = {}
        for mode in MODES:
            for p in self.k_shortest_paths(origin_id, dest_id, k + 2, mode):
                key = tuple(_nodes(origin_id, p))
                if key in pool:
                    pool[key][1].add(mode)
                else:
                    pool[key] = (p, {mode})
        ranked = sorted(pool.values(), key=lambda t: (path_cost(t[0], MODE_FEWEST_TRANSFERS), len(t[0]), _edge_key(t[0])))
        out = []
        for i, (p, modes) in enumerate(ranked[:k], start=1):
            r = self.build_route(origin_id, dest_id, p, "alternatives", STATUS_OK, f"route_{i:03d}")
            r["found_by"] = sorted(modes)
            r["rank"] = i
            out.append(r)
        return out

    def route_between_candidates(
        self, origin_ids: Iterable[str], dest_ids: Iterable[str], optimization: str = MODE_FEWEST_TRANSFERS
    ) -> dict[str, Any]:
        """Try every (origin, destination) pair and return the best route for ``optimization``.

        Adds ``selected_origin``, ``selected_destination``, ``pairs_tried`` and
        ``pairs_failed`` (with their statuses) to the route dict.
        """
        origin_ids, dest_ids = list(dict.fromkeys(origin_ids or [])), list(dict.fromkeys(dest_ids or []))
        if optimization not in MODES:
            return self._error(origin_ids, dest_ids, optimization, STATUS_INVALID_OPTIMIZATION,
                               f"optimization must be one of {MODES}")
        best: Optional[tuple[tuple, dict[str, Any]]] = None
        tried, failed = 0, []
        for o in origin_ids:
            for d in dest_ids:
                tried += 1
                r = self.find_route(o, d, optimization)
                if r["status"] == STATUS_SAME_STATION:
                    rank: tuple = (0, (0, 0, 0), o, d)
                elif r["status"] == STATUS_OK:
                    edges = [Edge(e["from"], e["to"], e["type"], e["line_id"], e["edge_id"]) for e in r["edges"]]
                    rank = (1, path_cost(edges, optimization), o, d)
                else:
                    failed.append({"origin": o, "destination": d, "status": r["status"]})
                    continue
                if best is None or rank < best[0]:
                    best = (rank, r)
        if best is None:
            status = STATUS_UNKNOWN_STATION if failed and all(f["status"] == STATUS_UNKNOWN_STATION for f in failed) else STATUS_NO_ROUTE
            res = self._error(origin_ids, dest_ids, optimization, status, "No valid origin/destination pair produced a route.")
        else:
            res = best[1]
        res.update(
            selected_origin=res["origin"] if best else None,
            selected_destination=res["destination"] if best else None,
            pairs_tried=tried,
            pairs_failed=failed,
        )
        return res


# --------------------------------------------------------------- helpers
def _nodes(origin: str, edges: Sequence[Edge]) -> list[str]:
    return [origin] + [e.dst for e in edges]


def _edge_key(edges: Sequence[Edge]) -> tuple[str, ...]:
    return tuple(f"{e.src}>{e.dst}#{e.edge_id}" for e in edges)


def _route_id(optimization: str, nodes: Sequence[str]) -> str:
    h = hashlib.sha1(("|".join([optimization, *nodes])).encode("utf-8")).hexdigest()[:10]
    return f"route_{h}"


_ENGINES: dict[str, RoutingEngine] = {}


def get_engine(data_dir: Optional[PathLike] = None) -> RoutingEngine:
    """Cached engine per dataset directory."""
    key = str(resolve_data_dir(data_dir))
    if key not in _ENGINES:
        _ENGINES[key] = RoutingEngine(data_dir)
    return _ENGINES[key]


def find_route(origin_id: str, dest_id: str, optimization: str = MODE_FEWEST_TRANSFERS,
               data_dir: Optional[PathLike] = None) -> dict[str, Any]:
    """Module-level wrapper of :meth:`RoutingEngine.find_route`."""
    return get_engine(data_dir).find_route(origin_id, dest_id, optimization)


def find_alternative_routes(origin_id: str, dest_id: str, k: int = 3,
                            data_dir: Optional[PathLike] = None) -> list[dict[str, Any]]:
    """Module-level wrapper of :meth:`RoutingEngine.find_alternative_routes`."""
    return get_engine(data_dir).find_alternative_routes(origin_id, dest_id, k)


def route_between_candidates(origin_ids: list[str], dest_ids: list[str],
                             optimization: str = MODE_FEWEST_TRANSFERS,
                             data_dir: Optional[PathLike] = None) -> dict[str, Any]:
    """Module-level wrapper of :meth:`RoutingEngine.route_between_candidates`."""
    return get_engine(data_dir).route_between_candidates(origin_ids, dest_ids, optimization)


def route_to_text(route: dict[str, Any], data_dir: Optional[PathLike] = None) -> str:
    """Human-readable Thai description of a route dict (presentation only)."""
    ds = get_engine(data_dir).ds

    def nm(sid: str) -> str:
        st = ds.stations.get(sid)
        return f"{st.name_th} ({sid})" if st else str(sid)

    status = route.get("status")
    if status == STATUS_UNKNOWN_STATION:
        return f"ไม่พบรหัสสถานี: {', '.join(map(str, route.get('unknown_ids', [])))}"
    if status == STATUS_NO_ROUTE:
        return "ไม่พบเส้นทางระหว่างสถานีที่เลือก"
    if status == STATUS_INVALID_OPTIMIZATION:
        return f"โหมดไม่ถูกต้อง: {route.get('optimization')}"
    if status == STATUS_SAME_STATION:
        return f"ต้นทางและปลายทางเป็นสถานีเดียวกัน: {nm(route['origin'])} → {nm(route['destination'])}"
    s = route["summary"]
    mode_th = {"fewest_transfers": "เปลี่ยนสายน้อยที่สุด", "shortest_edges": "จำนวนช่วงน้อยที่สุด"}.get(
        route.get("optimization"), route.get("optimization"))
    lines = [
        f"เส้นทาง {nm(route['origin'])} → {nm(route['destination'])} [{mode_th}]",
        f"นั่ง {s['ride_count']} ช่วงสถานี, เปลี่ยนสาย {s['transfer_count']} ครั้ง"
        + (f", ผ่านจุดแยกสาขา {s['branch_junction_count']} ครั้ง (ไม่นับเป็นการเปลี่ยนสาย)" if s["branch_junction_count"] else ""),
    ]
    for i, leg in enumerate(route["legs"], start=1):
        via = {"TRANSFER": "เปลี่ยนสายแล้ว", "BRANCH_JUNCTION": "ผ่านจุดแยกสาขาแล้ว"}.get(leg["entered_via"], "")
        lines.append(f"  {i}. {via + ' ' if via else ''}นั่ง{leg['line_name_th'] or leg['line_id']} "
                     f"จาก {nm(leg['from'])} ถึง {nm(leg['to'])} ({leg['rides']} ช่วง)")
    lines.append("หมายเหตุ: สมมติว่าทุกช่วงเดินรถได้สองทิศทาง; ไม่มีข้อมูลเวลาเดินทางหรือค่าโดยสารในโมดูลนี้")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Rail routing over dai_routing_v2")
    p.add_argument("origin")
    p.add_argument("destination")
    p.add_argument("--mode", choices=MODES, default=MODE_FEWEST_TRANSFERS)
    p.add_argument("--json", action="store_true", help="print structured JSON")
    p.add_argument("--alternatives", type=int, default=0, metavar="K", help="also list K alternative routes")
    p.add_argument("--data-dir", default=None)
    a = p.parse_args(argv)
    r = find_route(a.origin, a.destination, a.mode, a.data_dir)
    alts = find_alternative_routes(a.origin, a.destination, a.alternatives, a.data_dir) if a.alternatives else []
    if a.json:
        print(json.dumps({"route": r, "alternatives": alts} if alts else r, ensure_ascii=False, indent=2))
    else:
        print(route_to_text(r, a.data_dir))
        for alt in alts:
            print(f"\n--- ทางเลือก {alt['rank']} ---")
            print(route_to_text(alt, a.data_dir))
    return 0 if r["status"] in (STATUS_OK, STATUS_SAME_STATION) else 1


if __name__ == "__main__":
    raise SystemExit(main())
