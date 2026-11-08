import csv,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from break_ia.agent import BreakAgent
from break_ia.data_loader import load_order_history,load_products
from datetime import datetime

def test_data_integrity():
 d=ROOT/'data/raw'; rows=list(csv.DictReader(open(d/'order_history.csv',encoding='utf-8'))); products=load_products(d/'products_catalog.csv')
 assert len(rows)>1120 and len({r['user_id'] for r in rows})==130
 assert len(products)==87 and len({p.name for p in products.values()})==87
 assert all(r['product_id'] in products for r in rows)
 assert len({(r['order_id'],r['product_id']) for r in rows})==len(rows)
 assert all(int(r['quantity'])>0 and int(r['total_price'])==int(r['unit_price'])*int(r['quantity']) for r in rows)
 assert all(len({r['user_id'] for r in rows if r['order_id']==oid})==1 for oid in {r['order_id'] for r in rows})
 assert len([r for r in rows if r['user_id'].startswith('usr_sintetico_')])>0
 assert len({r['user_id'] for r in rows if r['user_id'].startswith('usr_sintetico_')})==100
 synthetic_counts={u:sum(1 for r in rows if r['user_id']==u) for u in {r['user_id'] for r in rows if r['user_id'].startswith('usr_sintetico_')}}
 assert len(set(synthetic_counts.values()))>1

def test_agent_inference_and_cold_start():
 a=BreakAgent(ROOT/'data/raw',use_clusters=True)
 x=a.decide('usr_estudiante_01',datetime(2026,11,9,8,20),'Lunes',5)
 y=a.decide('usr_sintetico_040',datetime(2026,11,9,15,20),'Lunes',5)
 z=a.decide('usuario_nuevo_sin_historial',datetime(2026,11,9,12,20),'Lunes',5)
 assert len(x.top_recommendations)==5 and len(y.top_recommendations)==5 and len(z.top_recommendations)==5
 assert [r.product.id for r in x.top_recommendations] != [r.product.id for r in y.top_recommendations]
 assert len({r.product.id for r in z.top_recommendations})==5
 assert a.clusters.k>=2 and 0<=a.clusters.silhouette<=1


def test_hybrid_signals_and_explanations():
    a=BreakAgent(ROOT/'data/raw',use_clusters=True,use_hybrid=True)
    dt=datetime(2026,11,9,8,20)
    x=a.decide('usr_estudiante_01',dt,'Lunes',5)
    y=a.decide('usr_estudiante_02',datetime(2026,11,9,12,20),'Lunes',5)
    assert len(x.top_recommendations)==5
    assert all(item.explanations for item in x.top_recommendations)
    assert [i.product.id for i in x.top_recommendations] != [i.product.id for i in y.top_recommendations]

def test_hybrid_temporal_cutoff_and_cold_start():
    cutoff='2026-10-30 12:03:15'
    a=BreakAgent(ROOT/'data/raw',until=cutoff,use_clusters=True,use_hybrid=True)
    assert all(line.timestamp < cutoff for line in a.orders)
    cold=a.decide('usuario_nuevo_sin_historial',datetime(2026,11,9,12,20),'Lunes',5)
    assert len(cold.top_recommendations)==5
    assert all(item.product.available for item in cold.top_recommendations)


def test_profile_is_derived_for_existing_user_without_archetype():
 a=BreakAgent(ROOT/'data/raw',use_clusters=True,use_hybrid=True)
 profile=a._profile_for_user('usr_estudiante_01',None)
 assert profile.archetype_name=='Perfil aprendido del historial'
 assert profile.min_budget>0 and profile.max_budget>profile.min_budget
 assert profile.frequent_days


def test_new_user_can_be_assigned_after_initial_orders():
 a=BreakAgent(ROOT/'data/raw',use_clusters=True,use_hybrid=True,
              cold_start_users={'usr_estudiante_01'},cold_start_orders=2)
 perception=a.perceive('usr_estudiante_01',datetime(2026,11,9,8,20),'Lunes')
 assert perception['cluster_id'] is not None
