"""Dai POI/Matching/Routing + Bambi Fare integration. No web server or UI."""
from __future__ import annotations
import argparse,copy,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
# Dai's delivered modules intentionally use flat imports. Preserve their source bytes.
for directory in (ROOT/'routing',ROOT/'fare'):
    if str(directory) not in sys.path:sys.path.insert(0,str(directory))
from routing_engine import RoutingEngine,Edge
from fare_engine import FareEngine

CONTRACT_STATUSES={'OK','FARE_DATA_UNAVAILABLE','PARTIAL','PENDING_REVIEW','UNKNOWN_STATION','ROUTE_NOT_FAREABLE'}

def contract_fare(quote):
    out=copy.deepcopy(quote);raw=out['status'];out['engine_status']=raw
    if raw in {'OK','PENDING_REVIEW'}:status=raw
    elif raw=='INVALID_ROUTE' and (out.get('route_status')=='UNKNOWN_STATION' or 'UNKNOWN_STATION_ID' in out.get('reasons',[])):status='UNKNOWN_STATION'
    elif raw in {'FARE_DATA_UNAVAILABLE','UNSUPPORTED_FARE_CONTEXT'}:status='FARE_DATA_UNAVAILABLE'
    else:status='ROUTE_NOT_FAREABLE'
    out['status']=status
    if out.get('total_fare_thb') is not None:out['total_fare_thb']=float(out['total_fare_thb'])
    return out

class TransportBackend:
    def __init__(self,root=ROOT):
        self.root=Path(root)
        self.fare=FareEngine(self.root/'fare')
        self.routing=RoutingEngine(data_dir=self.root/'data_original')
        self.overlay=json.loads((self.root/'fare/network_overlay.json').read_text())
        for op in self.overlay['operations']:
            a,b=op['from'],op['to']
            if op['action']=='REMOVE':
                for x,y in [(a,b),(b,a)]:
                    before=len(self.routing.adj[x]);self.routing.adj[x]=[e for e in self.routing.adj[x] if not(e.dst==y and e.type==op['type'])]
                    if len(self.routing.adj[x])!=before-1:raise ValueError('Routing overlay removal mismatch')
            else:
                if any(e.dst==b for e in self.routing.adj[a]):raise ValueError('Routing overlay addition duplicate')
                self.routing.adj[a].append(Edge(a,b,'RIDE',op['line_id'],op['edge_id']))
                self.routing.adj[b].append(Edge(b,a,'RIDE',op['line_id'],op['edge_id']))
        actual={(edge.src,edge.dst):edge.type for edges in self.routing.adj.values() for edge in edges}
        if actual!=self.fare.graph:raise ValueError('Routing and Fare runtime graphs differ')
        for edges in self.routing.adj.values():edges.sort(key=lambda e:(e.dst,e.edge_id))
    def calculate_fare(self,route,**context):
        return contract_fare(self.fare.calculate(route,**context))
    def calculate_fares(self,routes,**context):
        if not isinstance(routes,list):raise ValueError('routes must be a list')
        return [self.calculate_fare(r,**context) for r in routes]
    def plan(self,origin,destination,optimization='fewest_transfers',alternatives=3,**context):
        if isinstance(alternatives,bool) or not isinstance(alternatives,int) or not 1<=alternatives<=5:
            raise ValueError('alternatives must be an integer1..5')
        primary=self.routing.find_route(origin,destination,optimization,route_id='route_main')
        base={'network_revision':self.fare.network_revision,'scope':'SUPPLIED_CANDIDATES_ONLY','network_wide_cheapest_proven':False}
        if primary['status'] not in {'OK','SAME_STATION'}:
            return {**base,'status':'ROUTING_ERROR','route':primary,'fare':self.calculate_fare(primary,**context),'candidates':[],'comparison':None}
        pool=self.routing.find_alternative_routes(origin,destination,k=alternatives)
        paths={tuple(primary['station_line_ids']):primary}
        for r in pool:
            if tuple(r['station_line_ids']) not in paths:paths[tuple(r['station_line_ids'])]=r
        candidates=list(paths.values())
        quotes=self.calculate_fares(candidates,**context)
        comparison=self.fare.compare_routes(candidates,**context)
        comparison['results']=[contract_fare(q) for q in comparison['results']]
        comparison['network_revision']=self.fare.network_revision
        plan_status = ('OK' if quotes[0]['status']=='OK' else
                       'FARE_ESTIMATED' if quotes[0]['status']=='PENDING_REVIEW' and quotes[0].get('is_estimate') is True else
                       'FARE_UNAVAILABLE')
        return {**base,'status':plan_status,'route':primary,'fare':quotes[0],
                'candidates':[{'route':r,'fare':q} for r,q in zip(candidates,quotes)],'comparison':comparison}
    def plan_places(self,origin_query,destination_query,*,origin_choice=None,destination_choice=None,
            origin_station_choice=0,destination_station_choice=0,provider=None,**kwargs):
        from poi_search import search_poi,confirm_poi
        from station_matching import match_poi_to_stations
        origin=search_poi(origin_query,provider=provider);destination=search_poi(destination_query,provider=provider)
        for res,choice in [(origin,origin_choice),(destination,destination_choice)]:
            if choice is not None:
                selected=confirm_poi(res,choice);res.clear();res.update(selected)
        if any(r['status'] not in {'OK','CONFIRMED'} for r in (origin,destination)):
            return {'status':'POI_CONFIRMATION_REQUIRED' if any(r['status']=='AMBIGUOUS' for r in (origin,destination)) else 'POI_UNAVAILABLE','origin_search':origin,'destination_search':destination,'plan':None}
        near_o=match_poi_to_stations(origin,top_k=3,data_dir=self.root/'data_original')
        near_d=match_poi_to_stations(destination,top_k=3,data_dir=self.root/'data_original')
        try:
            for selection in (origin_station_choice,destination_station_choice):
                if isinstance(selection,bool) or not isinstance(selection,int) or selection<0:raise ValueError()
            a=near_o['nearest_stations'][origin_station_choice]['station_line_id'];b=near_d['nearest_stations'][destination_station_choice]['station_line_id']
        except (IndexError,ValueError):return {'status':'INVALID_STATION_SELECTION','origin_matching':near_o,'destination_matching':near_d,'plan':None}
        planned=self.plan(a,b,**kwargs)
        return {'status':planned['status'],'origin_search':origin,'destination_search':destination,'origin_matching':near_o,'destination_matching':near_d,
                'station_selection_basis':'EXPLICIT_CHOICE_OR_DEFAULT_NEAREST','distance_method':'haversine_straight_line','live_geocoding':provider is None,
                'plan':planned}

class RecordedFixtureProvider:
    """Replay Dai's recorded candidates through the real POI search logic; never live evidence."""
    name='recorded_nominatim_fixture'
    from_cache=True
    def __init__(self,path=ROOT/'routing/fixtures/poi_fixtures.json'):
        self.data=json.loads(Path(path).read_text())
    def search(self,query,limit):
        entry=self.data.get(query)
        if not entry:return []
        res=entry['result']
        if res.get('fallback_query'):return []
        return copy.deepcopy(res.get('candidates',[]))[:limit]

_default=None
def get_backend():
    global _default
    if _default is None:_default=TransportBackend()
    return _default

def calculate_fare(route,**context):return get_backend().calculate_fare(route,**context)
def calculate_fares(routes,**context):return get_backend().calculate_fares(routes,**context)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path,help='Plan request JSON')
    args=parser.parse_args()
    try:
        req=json.loads(args.input.read_text(encoding='utf-8-sig'))
        if not isinstance(req,dict):raise ValueError('request must be an object')
        allowed={'origin','destination','optimization','alternatives','fare_context','origin_query','destination_query','origin_choice','destination_choice','origin_station_choice','destination_station_choice','recorded_fixture'}
        if set(req)-allowed:raise ValueError('Unknown request keys')
        backend=get_backend();context=req.get('fare_context',{})
        if not isinstance(context,dict):raise ValueError('fare_context must be an object')
        if 'origin_query' in req:
            provider=RecordedFixtureProvider() if req.get('recorded_fixture') is True else None
            result=backend.plan_places(req['origin_query'],req['destination_query'],provider=provider,origin_choice=req.get('origin_choice'),destination_choice=req.get('destination_choice'),origin_station_choice=req.get('origin_station_choice',0),destination_station_choice=req.get('destination_station_choice',0),optimization=req.get('optimization','fewest_transfers'),alternatives=req.get('alternatives',3),**context)
        else:result=backend.plan(req['origin'],req['destination'],req.get('optimization','fewest_transfers'),req.get('alternatives',3),**context)
    except (KeyError,ValueError,TypeError,OSError) as exc:result={'status':'INVALID_INPUT','reasons':[str(exc)]}
    print(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False))
    return 0 if result['status']=='OK' else 2

if __name__=='__main__':raise SystemExit(main())
