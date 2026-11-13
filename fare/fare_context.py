"""Explicit fare products and refunds. Pure quotes; no card charging or identity checks."""
from datetime import date
from decimal import Decimal, InvalidOperation
try:
    from .fare_engine import FareEngine, SNAPSHOT_DATE, read_csv
except ImportError:
    from fare_engine import FareEngine, SNAPSHOT_DATE, read_csv

MRT={'MRT-BLU','MRT-PPL','MRT-YLW','MRT-PNK','MRT-PNK-MT'}
RED={'SRT-DRD','SRT-LRD'}
GREEN={'BTS-SUK','BTS-SIL'}
RABBIT=GREEN|{'BTS-GLD','MRT-YLW','MRT-PNK','MRT-PNK-MT'}

def calculate_context_fare(route, *, passenger_type='adult', ticket_type='single_journey',
        travel_date=SNAPSHOT_DATE, eligibility_confirmed=False, same_card=None,
        transfer_minutes=None, card_scheme='bank_emv', card_activated=None,
        apply_daily_cap=False, daily_context=None, eligibility_context=None,
        pass_context=None, _engine=None):
    e=_engine or FareEngine()
    q=e.calculate(route,travel_date=travel_date)
    q.update(passenger_type=passenger_type,ticket_type=ticket_type)
    def blocked(reason,status='FARE_DATA_UNAVAILABLE'):
        q.update(status=status,total_fare_thb=None,reasons=[reason]);return q
    if q['status']!='OK':return q
    if not isinstance(apply_daily_cap,bool):return blocked('apply_daily_cap must be boolean','INVALID_CONTEXT')
    for name,value in [('transfer_minutes',transfer_minutes),('daily_context',daily_context),('eligibility_context',eligibility_context),('pass_context',pass_context)]:
        if value is not None and not isinstance(value,dict):return blocked(name+' must be an object','INVALID_CONTEXT')
    if passenger_type not in {'adult','student','senior','child','disabled'}:
        return blocked('Unverified passenger product','UNSUPPORTED_FARE_CONTEXT')
    if ticket_type=='mrt_concession_card':
        return blocked('Legacy MRT/MRTPlus card retired2026-06-01; use current eligible EMV product or eligible token','UNSUPPORTED_FARE_CONTEXT')
    if ticket_type not in {'single_journey','rabbit','srt_concession_card','emv','srt_pass','bts_pass'}:
        return blocked('Unverified ticket/pass/promotion product','UNSUPPORTED_FARE_CONTEXT')
    if passenger_type!='adult' and eligibility_confirmed is not True:
        return blocked('Caller must confirm concession entitlement; no identity validation is performed','UNSUPPORTED_FARE_CONTEXT')
    lines={e.stations[s]['line_id'] for s in route['station_line_ids']}
    used={s['source_id'] for s in q['sources']}
    def finish_sources():q['sources']=[dict(e.sources[x]) for x in sorted(used)]
    # Product implementations are isolated; quote never mutates a real card.
    if passenger_type in {'child','disabled'}:
        try:
            from .extended_products import child_or_disability
        except ImportError:
            from extended_products import child_or_disability
        return child_or_disability(q,e,route,passenger_type,ticket_type,eligibility_context or {},apply_daily_cap,travel_date)
    if ticket_type=='bts_pass':
        try:
            from .extended_products import bts_pass
        except ImportError:
            from extended_products import bts_pass
        return bts_pass(q,e,route,passenger_type,pass_context or {},travel_date,apply_daily_cap)
    if ticket_type in {'srt_pass','bts_pass'}:
        if apply_daily_cap:return blocked('Pass and daily cap cannot be combined in this product','UNSUPPORTED_FARE_CONTEXT')
        pc=pass_context or {}
        product='SRT_30D_30T' if ticket_type=='srt_pass' else 'BTS_XTREME_LONG_MAINLINE'
        if passenger_type!='adult' or pc.get('product_id')!=product or pc.get('entitlement_confirmed') is not True:
            return blocked('Exact active pass entitlement must be confirmed','UNSUPPORTED_FARE_CONTEXT')
        if not lines<=(RED if ticket_type=='srt_pass' else GREEN):return blocked('Pass does not cover every line','UNSUPPORTED_FARE_CONTEXT')
        if ticket_type=='bts_pass':
            for sid in route['station_line_ids']:
                code=e.stations[sid]['station_code']
                if code in {'CEN','W1'}:continue
                if not (code[0] in 'NES' and code[1:].isdigit() and 1<=int(code[1:])<=dict(N=8,E=9,S=8)[code[0]]):
                    return blocked('BTS extension surcharge not implemented for this pass','UNSUPPORTED_FARE_CONTEXT')
        try:
            start,end=date.fromisoformat(pc['valid_from']),date.fromisoformat(pc['valid_until'])
            if not start<=date.fromisoformat(travel_date)<=end or (end-start).days>29 or end<start:raise ValueError()
            remaining=pc['remaining_trips']
            if isinstance(remaining,bool) or not isinstance(remaining,int) or remaining<1:raise ValueError()
            if ticket_type=='srt_pass' and remaining>30:raise ValueError()
        except (KeyError,ValueError,TypeError):return blocked('Pass expired, exhausted or validity/balance invalid')
        src='SRC_SRT_PRODUCT_CONDITIONS' if ticket_type=='srt_pass' else 'SRC_BTS_PASS_CATALOG'
        used.add(src);q['regular_fare_before_pass_thb']=q['total_fare_thb']
        for seg in q['fare_segments']:seg.update(fare_thb=0.0,source_ids=[src])
        q.update(status='OK',total_fare_thb=0.0,gross_fare_thb=0.0,fare_adjustments=[],reasons=[],pricing_basis='EXISTING_PREPAID_PASS_CASH_DUE',settlement_mode='EXISTING_PASS',pass_trips_required=1,remaining_trips_after_quote=remaining-1,pass_balance_mutated=False)
        if ticket_type=='srt_pass':q.update(pass_purchase_price_thb=800.0,pass_travel_value_thb=750.0,pass_issue_fee_thb=50.0,allocated_travel_value_per_trip_thb=25.0)
        finish_sources();return q
    if ticket_type=='rabbit' and not lines<=RABBIT:return blocked('Rabbit acceptance not verified for every line','UNSUPPORTED_FARE_CONTEXT')
    if ticket_type=='srt_concession_card' and not lines<=RED:return blocked('SRT card restricted to Red','UNSUPPORTED_FARE_CONTEXT')
    if passenger_type=='student' and ticket_type=='single_journey':return blocked('Student concession requires a verified eligible card','UNSUPPORTED_FARE_CONTEXT')
    if not isinstance(card_scheme,str):return blocked('card_scheme must be a string','INVALID_CONTEXT')
    is_mang=ticket_type=='emv' and card_scheme.startswith('mangmoom_')
    is_mrt=ticket_type=='emv' and card_scheme.startswith('mrt_emv_')
    if ticket_type=='emv':
        if 'ARL' in lines:used.add('SRC_ARL_EMV_DRT')
        if not lines<=(MRT|RED|{'ARL'}):return blocked('EMV acceptance not verified for every line','UNSUPPORTED_FARE_CONTEXT')
        allowed={'bank_emv'}|{prefix+person for prefix in ['mangmoom_','mrt_emv_'] for person in ['adult','student','senior']}
        if card_scheme not in allowed:return blocked('Unverified EMV scheme','UNSUPPORTED_FARE_CONTEXT')
        if passenger_type!='adult' and card_scheme not in {f'mangmoom_{passenger_type}',f'mrt_emv_{passenger_type}'}:
            return blocked('Matching eligible concession EMV scheme required','UNSUPPORTED_FARE_CONTEXT')
        if (is_mang or is_mrt) and (passenger_type!='adult' or lines-{'MRT-BLU','MRT-PPL'}) and card_activated is not True:
            return blocked('Confirm card activated and bound/eKYC where required')
        if is_mrt and not lines<={'MRT-BLU','MRT-PPL'}:return blocked('Current MRT EMV concessions outside Blue/Purple not verified in this release','UNSUPPORTED_FARE_CONTEXT')
    table={(r['from_station_line_id'],r['to_station_line_id'],r['passenger_type'],r['ticket_type']):r for r in read_csv(e.root/'concession_matrix.csv')}
    for seg in q['fare_segments']:
        a,b=seg['from_station_line_id'],seg['to_station_line_id'];line=e.stations[a]['line_id']
        person=passenger_type;media=ticket_type
        if ticket_type=='emv':
            media='mangmoom_emv'
            if line=='ARL' and is_mang:
                # Explicit normal-fare rule for every Mangmoom category on ARL, not a fallback.
                person='adult';used.add('SRC_MANGMOOM_CURRENT')
            if passenger_type!='adult':used.add('SRC_MANGMOOM_CURRENT')
        need=person!='adult' or (ticket_type=='rabbit' and line in GREEN)
        if need:
            row=table.get((a,b,person,media))
            if not row:return blocked('No verified exact product price for '+a+'->'+b,'UNSUPPORTED_FARE_CONTEXT')
            if travel_date!=row['verified_through']:return blocked('Requested date outside audited context snapshot')
            seg.update(fare_thb=float(row['fare_thb']),source_ids=[row['source_id']]);used.add(row['source_id'])
    adjustments=[]
    for adjustment in q['fare_adjustments']:
        adjustments.append({**adjustment,'amount_thb':float({'adult':14,'student':13,'senior':7}[passenger_type])})
    gross=sum(Decimal(str(s['fare_thb'])) for s in q['fare_segments'])-sum(Decimal(str(a['amount_thb'])) for a in adjustments)
    refunds=[]
    if ticket_type=='emv':
        conn_map={frozenset((r['station_line_id_a'],r['station_line_id_b'])):r['connection_id'] for r in read_csv(e.root/'data/interchanges_master.csv')}
        for edge in route['edges']:
            if edge['type']!='TRANSFER':continue
            a,b=edge['from'],edge['to'];conn=conn_map[frozenset((a,b))]
            left=next((s for s in q['fare_segments'] if a in s['station_line_ids']),None)
            right=next((s for s in q['fare_segments'] if b in s['station_line_ids']),None)
            if left is None or right is None:continue
            if conn in {'CONN-011','CONN-020'}:
                if same_card is not True:return blocked('Confirm same card for integrated EMV journey')
                continue
            if not isinstance(same_card,bool):return blocked('same_card must be explicit for cross-system EMV')
            if not same_card:continue
            mins=(transfer_minutes or {}).get(conn)
            if isinstance(mins,bool) or not isinstance(mins,(int,float)) or not Decimal(str(mins)).is_finite() or mins<0:return blocked('Missing or invalid transfer_minutes for '+conn)
            if mins>30:continue
            if conn not in {'CONN-012','CONN-013'}:return blocked('Cross-system EMV rebate amount unverified for '+conn)
            if passenger_type!='adult' and not is_mang:return blocked('Concession transfer amount verified for Mangmoom only')
            to_mono=e.stations[b]['line_id'] in {'MRT-PNK','MRT-YLW'}
            amount=({'adult':15,'student':15,'senior':8} if to_mono else {'adult':14,'student':13,'senior':7})[passenger_type]
            src='SRC_MANGMOOM_CURRENT' if is_mang else ('SRC_EMV_BLUE_YELLOW' if conn=='CONN-012' else 'SRC_EMV_PURPLE_PINK')
            used.add(src);refunds.append({'connection_id':conn,'amount_thb':float(amount),'source_id':src,'settlement':'DEFERRED_REFUND'})
    net=gross-sum(Decimal(str(x['amount_thb'])) for x in refunds)
    if net<0:return blocked('Refunds exceed fare')
    q.update(fare_adjustments=adjustments,gross_fare_thb=float(gross),transfer_refund_thb=float(gross-net),transfer_refunds=refunds,settlement_mode='PAY_GROSS_THEN_REFUND' if refunds else 'NORMAL_FARE',pricing_basis='EXPLICIT_MEDIA_AND_PASSENGER_CONTEXT')
    if apply_daily_cap:
        if ticket_type!='emv' or passenger_type not in {'adult','student'} or not lines<=({'MRT-BLU','MRT-PPL'}|RED):return blocked('Daily cap only for eligible Purple/Red share; unrelated systems excluded','UNSUPPORTED_FARE_CONTEXT')
        if not lines&({'MRT-PPL'}|RED):return blocked('No eligible Purple/Red movement in route','UNSUPPORTED_FARE_CONTEXT')
        if not ('2025-12-01'<=travel_date<='2026-11-30'):return blocked('Policy outside verified period')
        if same_card is False and any(x['type']=='TRANSFER' for x in route['edges']):return blocked('Cannot apply one-card daily cap to a multiple-card cross-system journey')
        dc=daily_context or {}
        if dc.get('date')!=travel_date or dc.get('same_card_confirmed') is not True or dc.get('complete_tap_history') is not True or dc.get('payments_settled') is not True:return blocked('Need same-card/date complete-tap and successful-payment history')
        try:
            raw=dc.get('prior_eligible_fare_thb',dc.get('prior_eligible_net_fare_thb'))
            if isinstance(raw,bool):raise ValueError()
            prior=Decimal(str(raw))
            if not prior.is_finite() or prior<0:raise ValueError()
        except (InvalidOperation,ValueError):return blocked('Invalid prior eligible spend')
        cap=Decimal(40 if passenger_type=='adult' else 30)
        eligible=sum(Decimal(str(s['fare_thb'])) for s in q['fare_segments'] if e.stations[s['from_station_line_id']]['line_id'] in ({'MRT-PPL'}|RED))
        # BEM explicitly assigns the Blue/Purple entry deduction to the Purple pool in both directions.
        eligible-=sum(Decimal(str(a['amount_thb'])) for a in adjustments)
        if eligible<0 or eligible>net:return blocked('Unverified daily-cap allocation')
        outside=net-eligible
        payable=min(cap,prior+eligible)-min(cap,prior)
        net=outside+payable
        q.update(daily_cap_thb=float(cap),eligible_fare_before_daily_cap_thb=float(eligible),fare_outside_daily_cap_thb=float(outside),net_fare_before_daily_cap_thb=float(outside+eligible),daily_cap_refund_thb=float(eligible-payable),settlement_mode='PAY_GROSS_THEN_REFUND',daily_cap_accumulator_updated=False)
        used.add('SRC_BEM_DAILY_ALLOCATION')
    q.update(status='OK',total_fare_thb=float(net),reasons=[])
    finish_sources();return q
