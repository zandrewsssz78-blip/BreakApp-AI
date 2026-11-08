"""Amplía el dataset con 100 perfiles sintéticos de frecuencia y canasta variables."""
import csv, json, random
from datetime import datetime, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/"data"/"raw"
SEED=314159
DAYS=["Lunes","Martes","Miércoles","Jueves","Viernes"]

def main():
    rng=random.Random(SEED)
    catalog=list(csv.DictReader(open(DATA/"products_catalog.csv",encoding="utf-8")))
    by_id={p["product_id"]:p for p in catalog}
    rows=list(csv.DictReader(open(DATA/"order_history.csv",encoding="utf-8")))
    data=json.load(open(DATA/"breakapp_synthetic_dataset.json",encoding="utf-8"))
    # Idempotencia: reconstruye solo los perfiles/pedidos creados por este generador.
    rows=[r for r in rows if not r["user_id"].startswith("usr_sintetico_")]
    data["user_archetypes"]=[a for a in data["user_archetypes"] if not a["user_id"].startswith("usr_sintetico_")]
    if len(rows)<1120 or len({r["user_id"] for r in rows})<30:
        raise ValueError("La base no sintética no conserva la cantidad mínima esperada.")
    segments=[
      ("Cafetero matutino","cafe","BEBIDAS",(7,10),3500,13000),
      ("Almuerzo tradicional","tradicional","ALMUERZOS",(11,14),11000,29000),
      ("Snack de tarde","salado","SNACKS",(14,18),3000,16000),
      ("Dulce y repostería","dulce","POSTRES",(13,17),4000,18000),
      ("Explorador equilibrado","saludable","SNACKS",(9,16),5000,24000),
    ]
    profiles=[]
    additions=[]
    for n in range(100):
        uid=f"usr_sintetico_{n+1:03d}"
        label,tag,cat,hrs,bmin,bmax=segments[n%5]
        shift=(n%7)-3
        lo=max(7,min(17,hrs[0]+(n%3)-1))
        hi=min(19,max(lo+1,hrs[1]+(n%3)-1))
        budget_min=max(2000,bmin+shift*350)
        budget_max=max(budget_min+2500,bmax+shift*600)
        preferred=[p for p in catalog if tag in (p.get("tags") or "").lower() and budget_min*.25<=int(p["price"])<=budget_max]
        category_pool=[p for p in catalog if p["category"]==cat and budget_min*.25<=int(p["price"])<=budget_max]
        pool=preferred or category_pool or [p for p in catalog if int(p["price"])<=budget_max] or catalog
        # Cada usuario tiene de 2 a 3 productos habituales dentro de su segmento y explora ocasionalmente
        fav_count=min(len(pool), rng.randint(2,3))
        favorites=rng.sample(pool, fav_count)
        # Frecuencia variable: 30% frecuente, 45% regular y 25% ocasional.
        band=rng.choices(["frecuente","regular","ocasional"],weights=[.30,.45,.25])[0]
        n_orders={"frecuente":rng.randint(9,13),"regular":rng.randint(5,8),"ocasional":rng.randint(2,4)}[band]
        frequent_days=rng.sample(DAYS,rng.randint(3,5))
        profiles.append({
          "user_id":uid,"archetype_name":f"{label} {n+1:03d}",
          "habitual_time_range":f"{lo:02d}:00 - {hi:02d}:00",
          "frequent_days":frequent_days,"min_budget":budget_min,"max_budget":budget_max,
          "notes_clues":f"Perfil sintético {band}; segmento {label}; afinidad temática {tag}; variación individual {n%7}.",
          "expected_recommendation":f"Productos afines a {tag} y compras en franja {lo}-{hi}."
        })
        used_days=set()
        for j in range(n_orders):
            # Espaciado variable y días coherentes con el perfil, sin órdenes idénticas.
            offset=(n*3+j*8+rng.randint(0,4))%95
            day=datetime(2026,8,3)+timedelta(days=offset)
            attempts=0
            while (day.weekday()>4 or DAYS[day.weekday()] not in frequent_days or day.date() in used_days) and attempts<20:
                day+=timedelta(days=1); attempts+=1
            used_days.add(day.date())
            hour=rng.randint(lo,min(hi,19))
            ts=day.replace(hour=hour,minute=rng.randrange(60),second=rng.randrange(60))
            # Preferencia estable (hábito personal + exploración dentro y fuera del segmento).
            roll=rng.random()
            if roll < 0.72:
                chosen=rng.choice(favorites)
            elif roll < 0.92:
                chosen=rng.choice(pool)
            else:
                affordable_cat=[p for p in category_pool if int(p["price"])<=budget_max] or pool
                chosen=rng.choice(affordable_cat)
            basket_size=rng.choices([1,2,3],[.65,.28,.07])[0]
            basket=[chosen]
            # Priorizar acompañamientos naturales (pairing_ids) si existen y se ajustan al presupuesto
            pair_tokens=[x.strip() for x in (chosen.get("pairing_ids") or "").replace(",","|").split("|") if x.strip()]
            pair_items=[by_id[pid] for pid in pair_tokens if pid in by_id and int(by_id[pid]["price"])<=budget_max]
            complementary=[p for p in catalog if p["product_id"]!=chosen["product_id"]
                and int(p["price"])<=budget_max]
            if basket_size>=2:
                if pair_items and rng.random()<0.80:
                    basket.append(rng.choice(pair_items))
                else:
                    cross=[p for p in complementary if p["category"]!=chosen["category"]]
                    basket.append(rng.choice(cross or complementary))
            if basket_size>=3:
                used_pids={x["product_id"] for x in basket}
                rem_pairs=[p for p in pair_items if p["product_id"] not in used_pids]
                remaining=[p for p in complementary if p["product_id"] not in used_pids]
                if rem_pairs:
                    basket.append(rng.choice(rem_pairs))
                elif remaining:
                    basket.append(rng.choice(remaining))
            for item in basket:
                additions.append({
                  "order_id":f"PENDING_{uid}_{j:02d}","user_id":uid,
                  "product_id":item["product_id"],"product_name":item["name"],
                  "restaurant_id":item["restaurant_id"],"category":item["category"],
                  "quantity":"1","unit_price":item["price"],"total_price":item["price"],
                  "timestamp":ts.strftime("%Y-%m-%d %H:%M:%S"),
                  "day_of_week":DAYS[ts.weekday()],
                  "rating":str(rng.choices([3,4,5],[.08,.27,.65])[0])
                })
    all_rows=rows+additions
    all_rows.sort(key=lambda r:(r["timestamp"],r["user_id"],r["product_id"]))
    new_ids={}
    for row in all_rows:
        if row["order_id"].startswith("PENDING_"):
            token=row["order_id"]
            if token not in new_ids:
                new_ids[token]=f"SYN_{len(new_ids)+1:05d}"
            row["order_id"]=new_ids[token]
    fields=list(rows[0])
    with open(DATA/"order_history.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(all_rows)
    data["user_archetypes"]=data["user_archetypes"]+profiles
    data["order_history"]=all_rows
    md=data["metadata"]
    md.update(total_order_lines=len(all_rows),total_orders=len({r["order_id"] for r in all_rows}),
      total_archetypes=len(data["user_archetypes"]),total_users=len({r["user_id"] for r in all_rows}),
      synthetic_added_lines=len(additions),synthetic_added_users=100,synthetic_seed=SEED,
      synthetic_frequency_bands="frecuente 9-13; regular 5-8; ocasional 2-4 pedidos por usuario")
    prior_note=md.get("schema_note","").split(" Nuevos registros identificados")[0].split(" Perfiles y pedidos sintéticos")[0].split(" Bloque sintético")[0]
    md["schema_note"]=(prior_note+" Bloque sintético identificable por usuarios usr_sintetico_* y pedidos SYN_*; frecuencia y canastas variables.")
    with open(DATA/"breakapp_synthetic_dataset.json","w",encoding="utf-8") as f:
        json.dump(data,f,ensure_ascii=False,indent=2)
    print(f"OK: {len(all_rows)} líneas; {md['total_orders']} pedidos; {md['total_users']} usuarios; {len(catalog)} productos; {len(additions)} líneas sintéticas")
if __name__=="__main__":
    main()
