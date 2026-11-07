"""Evalua el agente sin trampa: entrena con el pasado y prueba con el futuro.

Se corta el historial por fecha (80 % mas antiguo = entrenamiento, 20 % mas
reciente = prueba). Para cada orden de prueba el agente recomienda a la hora
exacta del pedido, usando SOLO pedidos anteriores al corte, y se mide si alguno
de sus Top-K productos estaba en la orden real (hit@K).

Se compara contra:
  - "Mas vendidos":   los 3 productos mas pedidos en el entrenamiento (politica estatica).
  - "Mas vendidos en la franja": igual, pero filtrando por la franja horaria.
  - "Solo reglas":    el agente sin clusters (utilidad con contenido, hora, presupuesto, rating).
  - "Reglas + clusters": el agente completo.

Segunda tabla (arranque en frio): un tercio de los usuarios se tratan como
NUEVOS. No participan en el entrenamiento de los clusters y el agente solo
conoce sus primeras N ordenes (N = 0, 1, 2, 3, 5).

Uso (desde la raiz del repo):  python scripts/evaluate_agent.py
"""

import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from break_ia.agent import BreakAgent  # noqa: E402
from break_ia.data_loader import group_orders, load_order_history  # noqa: E402
from break_ia.utility import parse_time_slot  # noqa: E402

DATA_DIR = ROOT / "data" / "raw"
TRAIN_FRACTION = 0.80
MIN_TRAIN_ORDERS = 3  # usuarios con al menos este historial de entrenamiento


def hit_at(recommended: list, bought: set, k: int) -> bool:
    return bool(set(recommended[:k]) & bought)


def main() -> None:
    all_lines = load_order_history(DATA_DIR / "order_history.csv")
    orders = sorted(group_orders(all_lines), key=lambda o: o.timestamp)
    cut = orders[int(len(orders) * TRAIN_FRACTION)].timestamp
    train = [o for o in orders if o.timestamp < cut]
    test = [o for o in orders if o.timestamp >= cut]
    train_count = Counter(o.user_id for o in train)
    test = [o for o in test if train_count[o.user_id] >= MIN_TRAIN_ORDERS]
    print(f"Corte: {cut[:10]} | entrenamiento: {len(train)} ordenes | prueba: {len(test)} ordenes")

    train_lines = [i for o in train for i in o.items]
    pop_global = [pid for pid, _ in Counter(i.product_id for i in train_lines).most_common(5)]
    slot_lines: dict = {}
    for o in train:
        dt = datetime.strptime(o.timestamp, "%Y-%m-%d %H:%M:%S")
        for i in o.items:
            slot_lines.setdefault(parse_time_slot(dt.hour, dt.minute), Counter())[i.product_id] += 1

    rules = BreakAgent(DATA_DIR, until=cut, use_clusters=False)
    full = BreakAgent(DATA_DIR, until=cut, use_clusters=True)
    print("\n" + full.clusters.summary())
    print("Silueta por k:", full.clusters.silhouette_by_k)

    methods = ["Mas vendidos", "Mas vendidos en la franja", "Solo reglas", "Reglas + clusters"]
    hits = {m: {3: 0, 5: 0} for m in methods}
    for o in test:
        dt = datetime.strptime(o.timestamp, "%Y-%m-%d %H:%M:%S")
        bought = {i.product_id for i in o.items}
        slot = parse_time_slot(dt.hour, dt.minute)
        recs = {
            "Mas vendidos": pop_global,
            "Mas vendidos en la franja": [p for p, _ in slot_lines.get(slot, Counter()).most_common(5)],
            "Solo reglas": [r.product.id for r in rules.decide(o.user_id, dt, o.day_of_week, k=5).top_recommendations],
            "Reglas + clusters": [r.product.id for r in full.decide(o.user_id, dt, o.day_of_week, k=5).top_recommendations],
        }
        for m in methods:
            for k in (3, 5):
                hits[m][k] += hit_at(recs[m], bought, k)

    print(f"\n{'Metodo':<28}{'hit@3':>8}{'hit@5':>8}")
    for m in methods:
        print(f"{m:<28}{hits[m][3] / len(test):>8.0%}{hits[m][5] / len(test):>8.0%}")
    cold_start_table(test, cut)


def cold_start_table(test_orders: list, cut: str) -> None:
    users = sorted({o.user_id for o in group_orders(load_order_history(DATA_DIR / "order_history.csv"))})
    cold_users = set(users[::3])  # un tercio de los usuarios, siempre los mismos
    test = [o for o in test_orders if o.user_id in cold_users]
    print(f"\nARRANQUE EN FRIO: {len(cold_users)} usuarios nuevos, {len(test)} ordenes de prueba")
    print(f"{'Historial conocido':<22}{'Solo reglas hit@3':>20}{'Reglas+clusters hit@3':>24}{'hit@5 (reglas / +clusters)':>30}")
    for n in (0, 1, 2, 3, 5):
        row = {}
        for name, use in (("rules", False), ("full", True)):
            ag = BreakAgent(DATA_DIR, until=cut, use_clusters=use, cold_start_users=cold_users, cold_start_orders=n)
            h3 = h5 = 0
            for o in test:
                dt = datetime.strptime(o.timestamp, "%Y-%m-%d %H:%M:%S")
                bought = {i.product_id for i in o.items}
                ids = [r.product.id for r in ag.decide(o.user_id, dt, o.day_of_week, k=5).top_recommendations]
                h3 += hit_at(ids, bought, 3)
                h5 += hit_at(ids, bought, 5)
            row[name] = (h3 / len(test), h5 / len(test))
        print(f"{n:>2} ordenes{'':<12}{row['rules'][0]:>20.0%}{row['full'][0]:>24.0%}"
              f"{row['rules'][1]:>16.0%} / {row['full'][1]:.0%}")


if __name__ == "__main__":
    main()
