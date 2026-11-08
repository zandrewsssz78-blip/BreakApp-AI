"""Entrena y persiste el agente; nunca incorpora filas posteriores al corte as-of."""
import argparse, json, pickle, sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"src"))
from break_ia.agent import BreakAgent

DATA=ROOT/"data"/"raw"
OUT=ROOT/"data"/"models"/"break_agent.pkl"

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--as-of",default=None,help="Corte exclusivo YYYY-MM-DD HH:MM:SS; por defecto ahora.")
    args=parser.parse_args()
    cutoff=args.as_of or datetime.now(ZoneInfo("America/Bogota")).strftime("%Y-%m-%d %H:%M:%S")
    agent=BreakAgent(DATA,until=cutoff,use_clusters=True,use_hybrid=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open("wb") as f:
        pickle.dump(agent,f,pickle.HIGHEST_PROTOCOL)
    meta={
        "created_at_utc":datetime.now(timezone.utc).isoformat(),
        "training_cutoff_exclusive":cutoff,
        "users":len(agent.user_orders),
        "order_lines":len(agent.orders),
        "products":len(agent.catalog),
        "clusters":agent.clusters.k if agent.clusters else 0,
        "silhouette":agent.clusters.silhouette if agent.clusters else None,
        "silhouette_by_k":agent.clusters.silhouette_by_k if agent.clusters else {},
        "stability_ari":agent.clusters.stability_ari if agent.clusters else None,
        "recommender":"rules + user-user CF + item-item CF + content + contextual popularity",
        "online_learning":False,
    }
    OUT.with_suffix(".json").write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
