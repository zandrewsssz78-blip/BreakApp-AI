"""Auditoría descriptiva: compara el bloque original y el sintético sin mezclarlos."""
import csv, json, statistics
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"raw"
OUT=ROOT/"data"/"reports"/"data_audit.json"

def summarize(rows):
    users={r["user_id"] for r in rows}
    orders={r["order_id"] for r in rows}
    counts=Counter(r["user_id"] for r in rows)
    user_order_sets={}
    for row in rows:
        user_order_sets.setdefault(row["user_id"],set()).add(row["order_id"])
    order_counts=[len(v) for v in user_order_sets.values()]
    frequency_bands=Counter("ocasional" if n<=4 else "regular" if n<=8 else "frecuente" for n in order_counts)
    categories=Counter(r["category"] for r in rows)
    prices=[int(r["unit_price"]) for r in rows]
    return {
        "order_lines":len(rows),"users":len(users),"orders":len(orders),
        "lines_per_user_mean":round(statistics.mean(counts.values()),2) if counts else 0,
        "lines_per_user_median":statistics.median(counts.values()) if counts else 0,
        "orders_per_user_mean":round(statistics.mean(order_counts),2) if order_counts else 0,
        "orders_per_user_min":min(order_counts,default=0),
        "orders_per_user_max":max(order_counts,default=0),
        "orders_per_user_median":statistics.median(order_counts) if order_counts else 0,
        "order_frequency_bands":dict(frequency_bands),
        "categories":dict(categories),
        "unit_price_mean":round(statistics.mean(prices),2) if prices else 0,
        "unit_price_median":statistics.median(prices) if prices else 0,
        "date_min":min((r["timestamp"] for r in rows),default=None),
        "date_max":max((r["timestamp"] for r in rows),default=None),
    }

def main():
    rows=list(csv.DictReader(open(DATA/"order_history.csv",encoding="utf-8")))
    original=[r for r in rows if not r["user_id"].startswith("usr_sintetico_")]
    synthetic=[r for r in rows if r["user_id"].startswith("usr_sintetico_")]
    report={"all":summarize(rows),"original":summarize(original),"synthetic":summarize(synthetic),
            "synthetic_identification":"usr_sintetico_* y order_id SYN_*",
            "interpretation":"Los datos sintéticos amplían diversidad diseñada; no son evidencia de demanda real."}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=="__main__":main()
