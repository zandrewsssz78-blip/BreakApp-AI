"""Evaluación temporal holdout: Baselines, Reglas, Clusters, Híbrido y Cold-Start."""
import argparse,json,sys,time
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from break_ia.agent import BreakAgent
from break_ia.data_loader import group_orders,load_order_history
from break_ia.utility import parse_time_slot
DATA=ROOT/'data/raw'; REPORT=ROOT/'data/reports/evaluation.json'
def metrics(ranked,relevant,k):
 top=ranked[:k]; hits=[1 if p in relevant else 0 for p in top]
 precision=sum(hits)/k; recall=sum(hits)/max(1,len(relevant)); dcg=sum(v/__import__('math').log2(i+2) for i,v in enumerate(hits))
 ideal=sum(1/__import__('math').log2(i+2) for i in range(min(k,len(relevant))))
 ap=sum((sum(hits[:i+1])/(i+1))*hit for i,hit in enumerate(hits))/max(1,min(k,len(relevant)))
 return {'precision':precision,'recall':recall,'ndcg':dcg/ideal if ideal else 0.0,'hit':float(any(hits)),'map':ap}
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument('--as-of',default=None,help='Corte exclusivo YYYY-MM-DD HH:MM:SS; por defecto ahora (Bogota).')
 args=parser.parse_args()
 as_of=args.as_of or datetime.now(ZoneInfo('America/Bogota')).strftime('%Y-%m-%d %H:%M:%S')
 lines=load_order_history(DATA/'order_history.csv'); orders=sorted((o for o in group_orders(lines) if o.timestamp<as_of),key=lambda x:x.timestamp)
 cut=orders[int(.8*len(orders))].timestamp
 train_lines=[l for l in lines if l.timestamp<cut]
 test=[o for o in orders if o.timestamp>=cut]
 global_top=[pid for pid,_ in Counter(l.product_id for l in train_lines).most_common(10)]
 slot_counts={}
 for l in train_lines:
  dt_l=datetime.strptime(l.timestamp,'%Y-%m-%d %H:%M:%S')
  s=parse_time_slot(dt_l.hour,dt_l.minute)
  slot_counts.setdefault(s,Counter())[l.product_id]+=1
 slot_top={s:[pid for pid,_ in c.most_common(10)] for s,c in slot_counts.items()}
 agent=BreakAgent(DATA,until=cut,use_clusters=True,use_hybrid=True)
 base_clusters=BreakAgent(DATA,until=cut,use_clusters=True,use_hybrid=False)
 rules_only=BreakAgent(DATA,until=cut,use_clusters=False,use_hybrid=False)
 cold_users={o.user_id for o in test}
 cold_agent=BreakAgent(DATA,until=cut,use_clusters=True,use_hybrid=True,cold_start_users=cold_users,cold_start_orders=0)
 models=[('baseline_global',None),('baseline_slot',None),('cold_start',cold_agent),('rules_only',rules_only),('rules_clusters',base_clusters),('hybrid_clusters',agent)]
 agg={name:{m:0.0 for m in ('precision','recall','ndcg','hit','map')} for name,_ in models}; latency={k:[] for k in agg}; count=0
 for o in test:
  dt=datetime.strptime(o.timestamp,'%Y-%m-%d %H:%M:%S'); day=o.day_of_week; rel={i.product_id for i in o.items}
  slot=parse_time_slot(dt.hour,dt.minute)
  for name,model in models:
   t=time.perf_counter()
   if name=='baseline_global':
    rec=global_top
   elif name=='baseline_slot':
    rec=slot_top.get(slot,global_top)
   else:
    rec=[x.product.id for x in model.decide(o.user_id,dt,day,k=10).top_recommendations]
   latency[name].append((time.perf_counter()-t)*1000)
   mm=metrics(rec,rel,5)
   for key,val in mm.items(): agg[name][key]+=val
  count+=1
 results={'as_of':as_of,'total_orders_used':len(orders),'split':'temporal 80/20; train strictly before cutoff','cutoff':cut,'train_orders':sum(o.timestamp<cut for o in orders),'test_orders':count,'k':5,'models':{}}
 for name in agg:
  results['models'][name]={k:round(v/max(1,count),4) for k,v in agg[name].items()}
  results['models'][name]['latency_ms_mean']=round(sum(latency[name])/max(1,len(latency[name])),3)
  results['models'][name]['latency_ms_p95']=round(sorted(latency[name])[int(.95*(len(latency[name])-1))],3) if latency[name] else 0
 results['clustering']={'algorithm':'K-Means','k':agent.clusters.k,'silhouette':agent.clusters.silhouette,'silhouette_by_k':agent.clusters.silhouette_by_k,'stability_ari':agent.clusters.stability_ari,'cluster_sizes':{str(cid):len(info.users) for cid,info in agent.clusters.info.items()}}
 results['evaluation_note']='Includes static popularity baselines (global and time-slot) and cold-start simulation excluding every test user from clustering and collaborative training.'
 REPORT.parent.mkdir(parents=True,exist_ok=True);REPORT.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
