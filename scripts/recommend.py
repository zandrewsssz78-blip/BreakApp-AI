"""Inferencias locales desde el artefacto entrenado; no levanta servidor."""
import argparse,pickle,sys
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--user',required=True);p.add_argument('--when',default='2026-11-09 12:30:00');p.add_argument('-k',type=int,default=5);a=p.parse_args()
 with (ROOT/'data/models/break_agent.pkl').open('rb') as f: agent=pickle.load(f)
 dt=datetime.strptime(a.when,'%Y-%m-%d %H:%M:%S'); result=agent.decide(a.user,dt,['Lunes','Martes','Miércoles','Jueves','Viernes'][dt.weekday()] if dt.weekday()<5 else 'Lunes',a.k)
 print(result.banner_message)
 for x in result.top_recommendations:
  print(f'{x.product.id}\t{x.product.name}\t${x.product.price:,}\tscore={x.utility_score:.4f}')
  for reason in x.explanations: print(f'  - {reason}')
 print(f'cluster={result.cluster_id} | {result.cluster_label}')
if __name__=='__main__':main()
