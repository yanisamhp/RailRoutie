"""Offline fare engine for the DSI463 route contract; Python 3.10+."""
from __future__ import annotations
import argparse
import hashlib
import csv
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
try:
    from .validate_data import validate_dataset
except ImportError:
    from validate_data import validate_dataset

ROOT = Path(__file__).resolve().parent
SNAPSHOT_DATE = '2026-11-10'
SYSTEMS = {'BTS-SUK': 'BTS_GREEN', 'BTS-SIL': 'BTS_GREEN',
           'BTS-GLD': 'BTS_GOLD', 'SRT-DRD': 'SRT_RED', 'SRT-LRD': 'SRT_RED',
           'ARL':'ARL','MRT-BLU':'MRT-BLU','MRT-PPL':'MRT-PPL','MRT-YLW':'MRT-YLW',
           'MRT-PNK':'MRT_PINK','MRT-PNK-MT':'MRT_PINK'}


def read_csv(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


class FareEngine:
    def __init__(self, base_dir=ROOT):
        self.root = Path(base_dir)
        self.validation = validate_dataset(self.root)
        stations = read_csv(self.root / 'data/stations_coordinates_provisional.csv')
        self.stations = {r['station_line_id']: r for r in stations}
        if len(self.stations) != len(stations):
            raise ValueError('Duplicate station_line_id')
        self.sources = {r['source_id']: r for r in read_csv(self.root / 'fare_sources.csv')}
        self.graph = {}
        for r in read_csv(self.root / 'data/ride_edges_master.csv'):
            self._edge(r['source_station_line_id'], r['target_station_line_id'], 'RIDE')
        for r in read_csv(self.root / 'data/interchanges_master.csv'):
            self._edge(r['station_line_id_a'], r['station_line_id_b'], r['connection_category'])
        self.network_revision = 'original-master'
        overlay_path=self.root/'network_overlay.json'
        if overlay_path.exists():
            overlay=json.loads(overlay_path.read_text())
            if hashlib.sha256((self.root/'data/ride_edges_master.csv').read_bytes()).hexdigest()!=overlay['original_ride_csv_sha256']:
                raise ValueError('Network overlay source hash mismatch')
            if overlay['source_id'] not in self.sources:raise ValueError('Unknown network source')
            for op in overlay['operations']:
                a,b=op['from'],op['to']
                if any(x not in self.stations or self.stations[x]['line_id']!=op['line_id'] for x in (a,b)) or op['type']!='RIDE':
                    raise ValueError('Invalid network overlay endpoints')
                if op['action']=='REMOVE':
                    for pair in [(a,b),(b,a)]:
                        if self.graph.pop(pair,None)!='RIDE':raise ValueError('Overlay removal mismatch')
                elif op['action']=='ADD':
                    if (a,b) in self.graph:raise ValueError('Overlay addition already exists')
                    self._edge(a,b,'RIDE')
                else:raise ValueError('Unknown overlay action')
            self.network_revision=overlay['revision']
        self.policies = {}
        for r in read_csv(self.root / 'transfer_rules.csv'):
            key = frozenset((r['from_station_line_id'], r['to_station_line_id']))
            if key in self.policies or any(s not in self.stations for s in key):
                raise ValueError('Invalid or duplicate transfer policy')
            if r['source_id'] not in self.sources or r['policy'] not in {'CONTINUE', 'SEPARATE', 'DISCOUNT'}:
                raise ValueError('Invalid transfer policy source or policy')
            self.policies[key] = r
        self.matrix = {}
        for r in read_csv(self.root / 'fare_matrix.csv'):
            a, b = r['from_station_line_id'], r['to_station_line_id']
            try:
                amount = Decimal(r['fare_thb'])
            except InvalidOperation as exc:
                raise ValueError('Invalid fare amount') from exc
            if not amount.is_finite() or amount < 0:
                raise ValueError('Fare must be finite and nonnegative')
            if a not in self.stations or b not in self.stations or r['source_id'] not in self.sources:
                raise ValueError('Orphan station/source reference')
            if any(SYSTEMS.get(self.stations[s]['line_id']) != r['fare_system'] for s in (a, b)):
                raise ValueError('Fare system mismatch')
            start = date.fromisoformat(r['effective_from']) if r['effective_from'] else None
            end = date.fromisoformat(r['verified_through'])
            if start and start > end:
                raise ValueError('Invalid fare date interval')
            key = (a, b, r['passenger_type'], r['ticket_type'])
            if key in self.matrix:
                raise ValueError('Duplicate fare key')
            self.matrix[key] = r

    def _edge(self, a, b, kind):
        if a not in self.stations or b not in self.stations:
            raise ValueError('Orphan graph edge')
        for key in ((a, b), (b, a)):
            if key in self.graph and self.graph[key] != kind:
                raise ValueError('Conflicting edge types')
            self.graph[key] = kind

    def _validate(self, route):
        if not isinstance(route, dict):
            return 'Route must be an object'
        if not isinstance(route.get('route_id'), str) or not route['route_id'].strip():
            return 'route_id must be a nonempty string'
        ids, edges = route.get('station_line_ids'), route.get('edges')
        if not isinstance(ids, list) or not ids or any(not isinstance(s, str) for s in ids):
            return 'station_line_ids must be a nonempty list of strings'
        if any(s not in self.stations for s in ids):
            return 'UNKNOWN_STATION_ID'
        if len(set(ids)) != len(ids):
            return 'Cyclic routes are not supported'
        if not isinstance(edges, list) or len(edges) != len(ids) - 1:
            return 'Edges must align one-to-one with adjacent stations'
        for a, b, edge in zip(ids, ids[1:], edges):
            if not isinstance(edge, dict) or edge.get('from') != a or edge.get('to') != b:
                return 'Edge order does not match station_line_ids'
            if 'line_id' in edge:
                line = self.stations[a]['line_id'] if edge.get('type') == 'RIDE' else None
                if edge['line_id'] != line:
                    return 'line_id does not match edge context'
            expected = self.graph.get((a, b))
            if expected is None or edge.get('type') != expected:
                return 'Unknown graph edge or incorrect edge type'
        return None

    def calculate(self, route, *, passenger_type='adult', ticket_type='single_journey', travel_date=SNAPSHOT_DATE, **payment_context):
        if passenger_type!='adult' or ticket_type!='single_journey' or payment_context:
            try:
                from .fare_context import calculate_context_fare
            except ImportError:
                from fare_context import calculate_context_fare
            return calculate_context_fare(route, passenger_type=passenger_type, ticket_type=ticket_type, travel_date=travel_date, _engine=self, **payment_context)
        """Return JSON-safe result. No guessed fares or implicit transfer discounts."""
        result = {'route_id': route.get('route_id') if isinstance(route, dict) else None,
                  'total_fare_thb': None, 'fare_segments': [], 'status': 'INVALID_ROUTE',
                  'sources': [], 'reasons': [], 'currency': 'THB', 'travel_date': travel_date,
                  'passenger_type': passenger_type, 'ticket_type': ticket_type,
                  'data_snapshot_date': SNAPSHOT_DATE, 'network_revision':self.network_revision}
        result['pricing_basis'] = 'adult_single_journey_separate_tickets_except_verified_integrated_connections'
        result['fare_adjustments'] = []
        if isinstance(route, dict) and route.get('status') in {'UNKNOWN_STATION','NO_ROUTE','INVALID_INPUT','INVALID_OPTIMIZATION'}:
            result.update(status='INVALID_ROUTE', reasons=[route.get('message') or str(route['status'])], route_status=route['status'])
            return result
        error = self._validate(route)
        if error:
            result['reasons'] = [error]
            return result
        try:
            if not isinstance(travel_date, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', travel_date):
                raise ValueError('Invalid ISO date')
            day = date.fromisoformat(travel_date)
        except (ValueError, TypeError):
            result.update(status='INVALID_CONTEXT', reasons=['travel_date must be YYYY-MM-DD'])
            return result
        if passenger_type != 'adult' or ticket_type != 'single_journey':
            result.update(status='UNSUPPORTED_FARE_CONTEXT', reasons=['Only adult single_journey is supported'])
            return result
        ids, edges = route['station_line_ids'], route['edges']
        if not edges:
            result.update(status='NO_TRAVEL', total_fare_thb=0,
                          reasons=['No ride requested; 0 is not an entry/exit gate fare'])
            return result
        # Build continuous fare-system segments, retaining the exact route and junction edges.
        segments, current, source_ids, unresolved = [], [ids[0]], set(), []
        deductions = []
        for edge_index, edge in enumerate(edges):
            if edge['type'] == 'RIDE':
                current.append(edge['to'])
                continue
            policy = self.policies.get(frozenset((edge['from'], edge['to'])))
            active = policy and policy['ticket_type'] == ticket_type and (
                date.fromisoformat(policy['effective_from'] or policy['verified_through']) <= day
                <= date.fromisoformat(policy['verified_through']))
            if active:
                source_ids.add(policy['source_id'])
            has_left_ride = any(self.graph.get((x,y)) == 'RIDE' for x,y in zip(current,current[1:]))
            future = edges[edge_index+1:]
            has_right_ride = bool(future) and future[0]['type'] == 'RIDE'
            if active and policy['policy'] == 'DISCOUNT' and has_left_ride and has_right_ride:
                deductions.append({'from':edge['from'],'to':edge['to'],'amount_thb':14.0,'source_id':policy['source_id'],'condition':'same through single-journey ticket at Tao Poon'})
            if active and policy['policy'] == 'CONTINUE':
                current.append(edge['to'])
            else:
                segments.append(current)
                current = [edge['to']]
                if not active:
                    unresolved.append('TRANSFER_POLICY_UNVERIFIED:' + edge['from'] + '->' + edge['to'])
        segments.append(current)
        for index, segment in enumerate(segments):
            a, b = segment[0], segment[-1]
            has_ride = any(self.graph.get((x, y)) in {'RIDE','BRANCH_JUNCTION'} for x, y in zip(segment, segment[1:]))
            # A transfer without riding has no fare of its own, but is never advertised as a free journey.
            if not has_ride:
                continue
            key = (a, b, passenger_type, ticket_type)
            row = self.matrix.get(key)
            status, amount, refs = 'FARE_DATA_UNAVAILABLE', None, []
            if row:
                start = date.fromisoformat(row['effective_from']) if row['effective_from'] else date.fromisoformat(row['verified_through'])
                if start <= day <= date.fromisoformat(row['verified_through']):
                    amount = float(Decimal(row['fare_thb']))
                    status, refs = 'OK', [row['source_id']]
                    source_ids.update(refs)
                else:
                    unresolved.append('FARE_DATE_NOT_VERIFIED:' + a + '->' + b)
            else:
                unresolved.append('MISSING_STATION_PAIR:' + a + '->' + b)
            result['fare_segments'].append({'segment_id': index + 1, 'station_line_ids': segment,
                'from_station_line_id': a, 'to_station_line_id': b,
                'fare_system': SYSTEMS.get(self.stations[a]['line_id'], self.stations[a]['line_id']),
                'fare_thb': amount, 'status': status, 'source_ids': refs})
        if not result['fare_segments']:
            unresolved.append('NO_PRICED_RIDE: transfer-only path is not a fare quote')
        complete = not unresolved and all(s['status'] == 'OK' for s in result['fare_segments'])
        result['status'] = 'OK' if complete else 'FARE_DATA_UNAVAILABLE'
        if complete:
            result['fare_adjustments'] = deductions
            result['total_fare_thb'] = float(sum(Decimal(str(s['fare_thb'])) for s in result['fare_segments']) - sum(Decimal(str(d['amount_thb'])) for d in deductions))
        result['sources'] = [dict(self.sources[s]) for s in sorted(source_ids)]
        result['reasons'] = unresolved
        return result

    def compare_routes(self, routes, **context):
        """Rank supplied candidates only. An unpriced candidate prevents a cheapest conclusion."""
        if not isinstance(routes, list) or not routes:
            raise ValueError('Provide at least one candidate route')
        ids = [r.get('route_id') if isinstance(r, dict) else None for r in routes]
        if any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise ValueError('Candidate route_id values must be unique strings')
        if any(self._validate(r) for r in routes):
            raise ValueError('All candidates must be valid routes')
        endpoints = {(r['station_line_ids'][0], r['station_line_ids'][-1]) for r in routes}
        if len(endpoints) != 1:
            raise ValueError('Compare routes for the same origin and destination only')
        results = [self.calculate(r, **context) for r in routes]
        priced = sorted((r for r in results if r['status'] == 'OK'), key=lambda r: (r['total_fare_thb'], r['route_id']))
        complete = len(priced) == len(results)
        best = priced[0]['total_fare_thb'] if priced else None
        return {'status': 'COMPLETE' if complete else 'INCOMPLETE_FARE_COVERAGE',
                'scope': 'SUPPLIED_CANDIDATES_ONLY', 'results': results,
                'priced_ranking': [r['route_id'] for r in priced],
                'cheapest_route_ids': [r['route_id'] for r in priced if r['total_fare_thb'] == best] if complete else [],
                'network_wide_cheapest_proven': False}


def calculate_fare(route, **context):
    if context.get('passenger_type','adult')!='adult' or context.get('ticket_type','single_journey')!='single_journey' or any(k in context for k in ['same_card','transfer_minutes','apply_daily_cap','eligibility_confirmed','daily_context','card_scheme']):
        try:
            from .fare_context import calculate_context_fare
        except ImportError:
            from fare_context import calculate_context_fare
        return calculate_context_fare(route,**context)
    return FareEngine().calculate(route, **context)


def calculate_fares(routes, **context):
    """Batch pricing, preserving input order; routes may have different endpoints."""
    if not isinstance(routes,list):
        raise ValueError('routes must be a list')
    engine=FareEngine()
    return [calculate_fare(route,**context) for route in routes]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='Route JSON file (or list with --compare)')
    parser.add_argument('--compare', action='store_true')
    parser.add_argument('--travel-date', default=SNAPSHOT_DATE)
    parser.add_argument('--passenger-type', default='adult')
    parser.add_argument('--ticket-type', default='single_journey')
    parser.add_argument('--payment-context', type=Path, help='JSON object of optional card/time/eligibility/day context')
    args = parser.parse_args()
    try:
        engine = FareEngine()
        route = json.loads(args.input.read_text(encoding='utf-8-sig'))
        fn = engine.compare_routes if args.compare else engine.calculate
        context = json.loads(args.payment_context.read_text(encoding='utf-8-sig')) if args.payment_context else {}
        allowed={'same_card','transfer_minutes','card_scheme','card_activated','eligibility_confirmed','apply_daily_cap','daily_context','pass_context','eligibility_context'}
        if not isinstance(context,dict) or set(context)-allowed:raise ValueError('Invalid payment context keys')
        result = fn(route, travel_date=args.travel_date, passenger_type=args.passenger_type, ticket_type=args.ticket_type, **context)
    except (ValueError, OSError) as exc:
        result = {'route_id': None, 'total_fare_thb': None, 'fare_segments': [],
                  'sources': [], 'status': 'INVALID_INPUT', 'reasons': [str(exc)]}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['status'] in {'OK', 'NO_TRAVEL', 'COMPLETE'} else 2


if __name__ == '__main__':
    raise SystemExit(main())
