"""Audited product quotes. No payment, identity check, pass purchase or balance mutation."""
import csv
import math
from datetime import date
from decimal import Decimal

GREEN = {'BTS-SUK', 'BTS-SIL'}
RED = {'SRT-DRD', 'SRT-LRD'}
FREE_HEIGHT = {'MRT-BLU': (120, 'SRC_V5_BLUE_LAW'),
               'MRT-PPL': (120, 'SRC_V5_PURPLE_LAW'),
               'MRT-YLW': (90, 'SRC_V5_YELLOW_LAW'),
               'MRT-PNK': (90, 'SRC_V5_PINK_LAW'),
               'MRT-PNK-MT': (90, 'SRC_V5_PINK_LAW')}

def number(x, lo=0):
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x) and x >= lo

def block(q, reason, status='FARE_DATA_UNAVAILABLE'):
    q.update(status=status, total_fare_thb=None, reasons=[reason])
    return q

def attach(q, e, source_ids):
    ids = {s['source_id'] for s in q['sources']} | set(source_ids)
    q['sources'] = [dict(e.sources[s]) for s in sorted(ids)]

def child_or_disability(q, e, route, person, ticket, ec, daily_cap, travel_date):
    if daily_cap or ticket != 'single_journey':
        return block(q, 'Special counter token cannot be combined with this ticket or daily cap')
    if ec.get('counter_issued_token') is not True:
        return block(q, 'Operator counter must confirm/issue the entitlement token')
    lines = {e.stations[s]['line_id'] for s in route['station_line_ids']}
    used = set()
    half_red = False
    for line in lines:
        if line in FREE_HEIGHT:
            threshold, src = FREE_HEIGHT[line]
            if person == 'disabled':
                valid = ec.get('disability_card_verified') is True
            else:
                age=ec.get('age_years')
                if age is not None and (isinstance(age,bool) or not isinstance(age,int) or not 0<=age<=14):
                    return block(q, 'MRTA child definition requires age<=14; counter must confirm eligibility')
                valid = number(ec.get('height_cm'), .01) and ec['height_cm'] <= threshold
            if not valid:
                return block(q, 'Height/entitlement outside verified exemption for ' + line)
            used.add(src)
        elif line in RED:
            if travel_date < '2026-09-13':
                return block(q, 'Red child product only audited under the notice effective2026-09-13')
            if person == 'disabled':
                valid = ec.get('disability_card_verified') is True
            else:
                age=ec.get('age_years')
                valid = isinstance(age,int) and not isinstance(age,bool) and 0<=age<=7
                if not valid and isinstance(age,int) and not isinstance(age,bool) and 7<age<=15:
                    half_red=True; valid=True
            if not valid:
                return block(q, 'Red entitlement not established')
            used.add('SRC_V5_RED_CHILD_NOTICE')
        else:
            return block(q, 'Special counter token not verified for ' + line, 'UNSUPPORTED_FARE_CONTEXT')
    q['regular_fare_before_entitlement_thb'] = q['total_fare_thb']
    estimated = False
    for s in q['fare_segments']:
        line = e.stations[s['from_station_line_id']]['line_id']
        src = 'SRC_V5_RED_CHILD_NOTICE' if line in RED else FREE_HEIGHT[line][1]
        price=Decimal(str(s['fare_thb']))/2 if line in RED and half_red else Decimal(0)
        fractional_red = line in RED and half_red and price != price.to_integral_value()
        if fractional_red:
            # User-approved prototype assumption. DIT general payment guidance
            # preserves exactly 50 satang; it does not confirm SRTET ticket fares.
            estimated = True
            used.add('SRC_DIT_GENERAL_ROUNDING_2015')
        s.update(fare_thb=float(price), source_ids=[src])
        if fractional_red:
            s.update(status='PENDING_REVIEW', is_estimate=True,
                     source_ids=[src, 'SRC_DIT_GENERAL_ROUNDING_2015'])
    total=sum(Decimal(str(s['fare_thb'])) for s in q['fare_segments'])
    q.update(status='PENDING_REVIEW' if estimated else 'OK', total_fare_thb=float(total), gross_fare_thb=float(total),
             fare_adjustments=[], reasons=[], pricing_basis='VERIFIED_EXEMPTION', settlement_mode='ENTITLEMENT')
    if estimated:
        q.update(is_estimate=True, operator_fare_confirmed=False,
                 pricing_basis='PROTOTYPE_RED_CHILD_HALF_FARE_GENERAL_ROUNDING',
                 settlement_mode='ESTIMATE_ONLY',
                 reasons=['RED_CHILD_HALF_FARE_ESTIMATE_NOT_OPERATOR_CONFIRMED'],
                 display_label_th='ราคาประมาณ รอยืนยันจากผู้ให้บริการ',
                 notes_th=['คำนวณค่าโดยสารเด็กสายสีแดงจากราคาปกติลด 50% และคงเศษ 50 สตางค์ตามเกณฑ์ทั่วไปของกรมการค้าภายใน มกราคม 2558 เป็นสมมติฐานของต้นแบบ ยังไม่ใช่ราคาจำหน่ายตั๋วที่ SRTET ยืนยัน'])
    attach(q, e, used)
    return q

def core(e, sid):
    c = e.stations[sid]['station_code']
    if c in {'CEN', 'W1'}:
        return True
    return c[0] in 'NES' and c[1:].isdigit() and 1 <= int(c[1:]) <= {'N':8, 'E':9, 'S':8}[c[0]]

def bts_pass(q, e, route, person, pc, travel_date, daily_cap):
    if daily_cap or person not in {'adult','student'}:
        return block(q, 'BTS pass only audited for adult/student without daily cap', 'UNSUPPORTED_FARE_CONTEXT')
    pid = pc.get('product_id')
    with (e.root/'pass_products.csv').open(encoding='utf-8-sig', newline='') as f:
        product = next((r for r in csv.DictReader(f) if r['product_id']==pid and r['passenger_type']==person), None)
    if pid=='BTS_XTREME_LONG_MAINLINE':
        # Backward compatible active30day long entitlement; actual package purchase price is unknown.
        product=dict(kind='LONG',valid_days='30',trip_count='35',activation_days='30',
                     price_thb='',sale_from='2026-04-01',sale_to='2027-03-31',source_id='SRC_V5_BTS_PASSES')
    if not product or pc.get('entitlement_confirmed') is not True:
        return block(q, 'Exact purchased, loaded and active pass entitlement required')
    if pc.get('other_promotion_applied') is True or pc.get('multiple_passes_loaded') is True:
        return block(q, 'Stacked promotions prohibited; multiple loaded passes require verified FIFO context')
    try:
        start,end,day = map(date.fromisoformat, (pc['valid_from'],pc['valid_until'],travel_date))
        remaining = pc['remaining_trips']; duration = int(product['valid_days'])
        if not start<=day<=end or (end-start).days > duration-1 or end<start:
            raise ValueError()
        if isinstance(remaining,bool) or not isinstance(remaining,int) or not 0<=remaining<=int(product['trip_count']):
            raise ValueError()
        # Caller already confirms activated entitlement; future-dated/redeemable vouchers are not active passes.
        if pc.get('purchased_on') is not None:
            purchase = date.fromisoformat(pc['purchased_on'])
            if not product['sale_from']<=pc['purchased_on']<=product['sale_to'] or not 0<=(start-purchase).days<int(product['activation_days']):
                raise ValueError()
    except (KeyError,ValueError,TypeError):
        return block(q, 'Pass validity, activation window or balance invalid')
    src = product['source_id']
    lines = {e.stations[s]['line_id'] for s in route['station_line_ids']}
    if not lines <= GREEN|{'BTS-GLD'}:
        return block(q, 'BTS pass context does not price every system in route')
    if product['kind']=='SHORT' and pc.get('wallet_link_confirmed') is not True:
        return block(q, 'Short pass requires linked Rabbit Wallet/LINE Pay and Rewards account')
    table = {(r['from_station_line_id'],r['to_station_line_id']):Decimal(r['fare_thb'])
             for r in e_context_rows(e, person)}
    consumed = 0
    regular = Decimal(0)
    for seg in q['fare_segments']:
        a,b=seg['station_line_ids'][0],seg['station_line_ids'][-1]
        if e.stations[a]['line_id']=='BTS-GLD':regular+=Decimal(17)
        elif (a,b) in table:regular+=table[a,b]
        else:return block(q, 'Missing exact regular Rabbit product price')
    for seg in q['fare_segments']:
        ids=seg['station_line_ids']; a,b=ids[0],ids[-1]
        line=e.stations[a]['line_id']
        if line=='BTS-GLD':
            seg.update(fare_thb=17.0, source_ids=[src]); continue
        edges=[x for x in route['edges'] if x['from'] in ids and x['to'] in ids and x['type']=='RIDE']
        core_rides=[x for x in edges if core(e,x['from']) and core(e,x['to'])]
        extension=[x for x in edges if x not in core_rides]
        if product['kind']=='SHORT' and extension and core_rides:
            return block(q, 'BTS_SHORT_MIXED_EXTENSION_ALLOCATION_UNVERIFIED')
        eligible=bool(core_rides) and (product['kind']=='LONG' or len(edges)<=4)
        if not eligible:
            if (a,b) not in table:return block(q, 'Missing exact Rabbit fallback fare')
            seg.update(fare_thb=float(table[a,b]), source_ids=['SRC_BTS_RABBIT_FULL'], pass_trip_used=False)
            continue
        if remaining<=consumed:return block(q, 'Pass exhausted for this journey')
        if extension:
            # Mixed core + one extension zone is explicit in the published diagram.
            # A two-extension-zone allocation has not been independently confirmed.
            if not core(e,a) and not core(e,b):
                return block(q, 'BTS_TWO_EXTENSION_ALLOCATION_UNVERIFIED')
            if len(extension)>=5:
                surcharge=Decimal(25 if person=='adult' else 17)
            else:
                ext=extension if core(e,a) else list(reversed(extension))
                boundary=ext[0]['from'] if core(e,a) else ext[0]['to']
                endpoint=b if core(e,a) else a
                if (boundary,endpoint) not in table:return block(q, 'Missing exact extension price')
                surcharge=table[boundary,endpoint]
        else:surcharge=Decimal(0)
        consumed+=1
        seg.update(fare_thb=float(surcharge), source_ids=[src,'SRC_BTS_RABBIT_FULL'] if extension else [src],
                   pass_trip_used=True, extension_ride_count=len(extension), core_ride_count=len(core_rides))
    total=sum(Decimal(str(s['fare_thb'])) for s in q['fare_segments'])
    q.update(status='OK', total_fare_thb=float(total), gross_fare_thb=float(total),
             regular_fare_before_pass_thb=float(regular), fare_adjustments=[], reasons=[],
             pricing_basis='EXISTING_PREPAID_PASS_CASH_DUE', settlement_mode='EXISTING_PASS',
             pass_product_id=pid, pass_trips_required=consumed, remaining_trips_after_quote=remaining-consumed,
             pass_balance_mutated=False, pass_purchase_price_thb=float(product['price_thb']) if product['price_thb'] else None,
             allocated_pass_cost_per_trip_thb=float(Decimal(product['price_thb'])/Decimal(product['trip_count'])) if product['price_thb'] else None)
    attach(q,e,{src,'SRC_BTS_RABBIT_FULL'}); return q

def e_context_rows(e, person):
    with (e.root/'concession_matrix.csv').open(encoding='utf-8-sig', newline='') as f:
        return [r for r in csv.DictReader(f) if r['ticket_type']=='rabbit' and r['passenger_type']==person]
