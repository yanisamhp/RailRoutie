"""Offline dataset integrity checks. No third party dependencies."""
import csv
import json
from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError(f'Invalid CSV header: {path.name}')
        rows = list(reader)
        if any(None in row or None in row.values() for row in rows):
            raise ValueError(f'Malformed CSV record: {path.name}')
        return rows


def interval(row):
    start = date.fromisoformat(row['effective_from']) if row['effective_from'] else None
    stop = date.fromisoformat(row['verified_through'])
    end = date.fromisoformat(row['effective_to']) if row.get('effective_to') else None
    if (start and start > stop) or (end and start and end < start) or (end and stop > end):
        raise ValueError('Invalid date interval')


def validate_dataset(root=ROOT):
    root = Path(root)
    tables = {name: read(root/'data'/f'{name}.csv') for name in
              ('stations_coordinates_provisional', 'lines_master', 'ride_edges_master', 'interchanges_master')}
    stations = tables['stations_coordinates_provisional']
    lines = tables['lines_master']
    def unique(rows, key):
        values = [r[key] for r in rows]
        if any(not v for v in values) or len(values) != len(set(values)):
            raise ValueError(f'Duplicate/empty {key}')
        return set(values)
    station_ids = unique(stations, 'station_line_id')
    line_ids = unique(lines, 'line_id')
    by_station = {r['station_line_id']: r for r in stations}
    if any(r['line_id'] not in line_ids for r in stations):
        raise ValueError('Orphan station line_id')
    graph = {}
    for name, ak, bk, tk in (
        ('ride_edges_master', 'source_station_line_id', 'target_station_line_id', 'edge_type'),
        ('interchanges_master', 'station_line_id_a', 'station_line_id_b', 'connection_category')):
        for row in tables[name]:
            a, b, kind = row[ak], row[bk], row[tk]
            if a not in station_ids or b not in station_ids or a == b:
                raise ValueError('Orphan/self graph edge')
            if kind not in ({'RIDE'} if name == 'ride_edges_master' else {'TRANSFER', 'BRANCH_JUNCTION'}):
                raise ValueError('Invalid master edge type')
            if name == 'ride_edges_master' and any(by_station[s]['line_id'] != row['line_id'] for s in (a,b)):
                raise ValueError('RIDE line mismatch')
            key = frozenset((a,b))
            if key in graph:
                raise ValueError('Duplicate graph edge')
            graph[key] = kind
    sources = read(root/'fare_sources.csv')
    unique(sources, 'source_id')
    source_map = {r['source_id']: r for r in sources}
    coverage = read(root/'fare_coverage.csv')
    if unique(coverage, 'line_id') != line_ids:
        raise ValueError('Coverage must list every master line exactly once')
    matrix = read(root/'fare_matrix.csv')
    keys = set()
    for row in matrix:
        key = tuple(row[k] for k in ('from_station_line_id','to_station_line_id','passenger_type','ticket_type'))
        if key in keys:
            raise ValueError('Duplicate fare key')
        keys.add(key)
        if any(s not in station_ids for s in key[:2]) or key[0] == key[1]:
            raise ValueError('Orphan/self fare station')
        try:
            price = Decimal(row['fare_thb'])
        except InvalidOperation as exc:
            raise ValueError('Invalid fare amount') from exc
        if not price.is_finite() or price <= 0:
            raise ValueError('Fare must be finite and positive')
        if row['source_id'] not in source_map or source_map[row['source_id']]['verification_status'] != 'ACTIVE':
            raise ValueError('Fare source not active/known')
        if row['passenger_type'] != 'adult' or row['ticket_type'] != 'single_journey':
            raise ValueError('Unsupported fare row context')
        interval(row)
    context_rows = read(root/'concession_matrix.csv')
    context_keys = set()
    for row in context_rows:
        key = tuple(row[k] for k in ('from_station_line_id','to_station_line_id','passenger_type','ticket_type'))
        if key in context_keys or any(x not in station_ids for x in key[:2]) or key[0]==key[1]:
            raise ValueError('Duplicate/orphan/self concession fare')
        context_keys.add(key)
        try: amount=Decimal(row['fare_thb'])
        except InvalidOperation as exc: raise ValueError('Invalid concession amount') from exc
        if not amount.is_finite() or amount<=0:raise ValueError('Invalid concession amount')
        if row['source_id'] not in source_map or source_map[row['source_id']]['verification_status']!='ACTIVE':
            raise ValueError('Unverified concession source')
        date.fromisoformat(row['verified_through'])
        if row['passenger_type'] not in {'adult','student','senior','child','disabled'}:raise ValueError('Unknown concession context')
    policies = read(root/'transfer_rules.csv')
    policy_keys = set()
    for row in policies:
        key = frozenset((row['from_station_line_id'],row['to_station_line_id']))
        if key in policy_keys or graph.get(key) not in {'TRANSFER','BRANCH_JUNCTION'}:
            raise ValueError('Invalid/duplicate policy graph edge')
        policy_keys.add(key)
        if row['policy'] not in {'CONTINUE','SEPARATE','DISCOUNT'} or row['ticket_type'] != 'single_journey':
            raise ValueError('Invalid transfer policy context')
        source = source_map.get(row['source_id'])
        if not source or source['verification_status'] not in {'ACTIVE','TRANSFER_ONLY'}:
            raise ValueError('Unverified transfer source')
        interval(row)
    products = read(root/'pass_products.csv')
    product_keys = set()
    for row in products:
        key=(row['product_id'],row['passenger_type'])
        if key in product_keys or not key[0] or key[1] not in {'adult','student'}:
            raise ValueError('Duplicate/invalid pass product')
        product_keys.add(key)
        if row['kind'] not in {'LONG','SHORT'} or row['source_id'] not in source_map or source_map[row['source_id']]['verification_status']!='ACTIVE':
            raise ValueError('Invalid pass kind/source')
        try:
            price=Decimal(row['price_thb'])
            values=[int(row[k]) for k in ['trip_count','valid_days','activation_days']]
            if not price.is_finite() or price<=0 or any(x<=0 for x in values):raise ValueError()
            if date.fromisoformat(row['sale_from'])>date.fromisoformat(row['sale_to']):raise ValueError()
        except (InvalidOperation,ValueError) as exc:
            raise ValueError('Invalid pass price/count/date') from exc
    return {'status':'PASS', 'records':{k:len(v) for k,v in tables.items()},
            'edge_types':dict(Counter(graph.values())), 'fare_rows':len(matrix), 'context_rows':len(context_rows),
            'transfer_rules':len(policies), 'pass_product_rows':len(products), 'line_ids':sorted(line_ids),
            'schemas':{k:list(v[0]) for k,v in tables.items()}}


if __name__ == '__main__':
    print(json.dumps(validate_dataset(), ensure_ascii=False, indent=2))
