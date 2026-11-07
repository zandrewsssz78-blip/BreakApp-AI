"""Genera datos sinteticos adicionales para BreakApp-AI.

Agrega 25 estudiantes nuevos (usr_estudiante_06 .. usr_estudiante_30) con
~450 lineas de pedido repartidas durante todo el dia. Cada orden tiene de 1 a
4 productos distintos (incluye ordenes de un solo alimento) y todo lo que un
usuario pide en la misma hora se une en una sola orden (consolidate_orders).

Uso (desde la raiz del repo):
    python scripts/generate_orders.py

Es reproducible (semilla fija) e idempotente: vuelve a generar siempre los
mismos datos de los usuarios 06-30 sin tocar los 5 arquetipos originales.
"""

import json
import random
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from break_ia.data_loader import (  # noqa: E402
    MAX_PRODUCTS_PER_ORDER,
    consolidate_orders,
    group_orders,
    load_order_history,
    load_products,
    save_order_history,
)
from break_ia.models import OrderItem, Product  # noqa: E402

DATA_DIR = ROOT / "data" / "raw"
SEED = 2026
TARGET_NEW_LINES = 450  # entre 400 y 500 lineas nuevas
MIN_ORDERS_PER_USER = 6
START, END = date(2026, 8, 3), date(2026, 11, 27)
DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
WEEK = DAYS_ES
SPLIT_SAME_HOUR_PROB = 0.12  # compra en dos momentos de la misma hora -> 1 orden

# Cantidad de productos por orden (1 = un solo alimento). Maximo 4.
N_PRODUCTS_WEIGHTS = {
    "light": {1: 0.50, 2: 0.35, 3: 0.12, 4: 0.03},
    "normal": {1: 0.28, 2: 0.37, 3: 0.23, 4: 0.12},
    "big": {1: 0.10, 2: 0.25, 3: 0.35, 4: 0.30},
}

MEAT = {"carne", "pollo", "proteina", "tocineta", "jamon", "pepperoni", "ranchera"}
DAIRY = {"lacteo", "queso", "helado", "yogurt"}
LACTOSE_SAFE = {"deslactosado", "leche_almendras", "vegano"}

# Ventanas horarias: (inicio h, inicio m, fin h, fin m)
M = (7, 0, 10, 59)
M2 = (8, 0, 9, 0)
BRUNCH = (10, 0, 11, 30)
L = (11, 30, 14, 15)
T = (14, 30, 16, 30)
T2 = (16, 30, 18, 45)
N = (18, 45, 19, 40)


def P(uid, name, windows, days, bmin, bmax, notes, fav=(), diet=(), appetite="normal",
      qty="solo", weight=1.0, friday=False, explore=False):
    """Perfil de generacion. `windows` = [(ventana, peso), ...]."""
    return dict(uid=uid, name=name, windows=windows, days=days, bmin=bmin, bmax=bmax,
                notes=notes, fav=set(fav), diet=set(diet), appetite=appetite, qty=qty,
                weight=weight, friday=friday, explore=explore)


PROFILES = [
    P("usr_estudiante_06", "Madrugador del Tinto", [((7, 0, 8, 30), 1)], WEEK, 2500, 9000,
      "Tinto o café sin azúcar, pan de queso, sale rápido a la primera clase",
      fav={"cafe", "panaderia", "sin_azucar"}, appetite="light"),
    P("usr_estudiante_07", "Estudiante Vegano de Mediodía", [((12, 0, 13, 30), 1)], WEEK, 9000, 22000,
      "Prefiere opciones vegano, sin queso, leche de almendras, frutas y comida saludable",
      fav={"vegano", "saludable", "fruta"}, diet={"vegano"}),
    P("usr_estudiante_08", "Intolerante a la Lactosa", [((10, 0, 11, 0), 1), (T, 1)], WEEK, 4000, 16000,
      "Intolerante a la lactosa, pide todo deslactosado y evita helados y quesos",
      fav={"deslactosado", "cafe", "jugo"}, diet={"lactosa"}),
    P("usr_estudiante_09", "Deportista Post-entreno", [(T2, 1)], ["Lunes", "Miércoles", "Jueves"], 10000, 30000,
      "Energizante y agua después de entrenar, compra grande y con proteína",
      fav={"energizante", "proteina", "fitness", "saludable"}, appetite="big", weight=1.1),
    P("usr_estudiante_10", "Estudiante Ahorrador", [((9, 30, 10, 30), 1), ((15, 0, 16, 0), 1)], WEEK, 1800, 8000,
      "Compra lo más económico: galletas, jugos y gaseosas pequeñas",
      fav={"economico", "paquete", "galletas"}, appetite="light"),
    P("usr_estudiante_11", "Arquitectura / Entregas Nocturnas", [(T, 1), ((17, 30, 19, 0), 1)],
      ["Lunes", "Martes", "Miércoles", "Jueves"], 6000, 18000,
      "Café y snacks en época de entregas, bebidas energizantes para trasnochar",
      fav={"energizante", "cafe", "codigo", "salado"}),
    P("usr_estudiante_12", "Almuerzo Tradicional sin Cebolla", [((12, 15, 13, 15), 1)], WEEK, 12000, 24000,
      "Sin cebolla, almuerzo tradicional (ajiaco, mote, bandeja) y jugo natural",
      fav={"tradicional", "sin_cebolla", "sopa", "jugo"}),
    P("usr_estudiante_13", "Fan de la Pizza", [((12, 30, 14, 0), 1)], WEEK, 8000, 25000,
      "Pizza con gaseosa para compartir, le gusta el pan de ajo",
      fav={"pizza", "gaseosa", "compartir", "ajo"}, qty="compartir", friday=True),
    P("usr_estudiante_14", "Dulcero de Postres", [((15, 0, 17, 0), 1)], WEEK, 4500, 20000,
      "Siempre pide algo dulce: helado, chocolate, fresas y postres",
      fav={"postre", "dulce", "helado", "chocolate"}),
    P("usr_estudiante_15", "Cafetero Gourmet", [((8, 30, 10, 0), 1)], WEEK, 4500, 15000,
      "Café gourmet, frappé y croissant, leche deslactosada",
      fav={"cafe", "gourmet", "panaderia", "deslactosado"}),
    P("usr_estudiante_16", "Vegetariano de Pizza y Ensaladas", [((12, 0, 13, 30), 1)], WEEK, 8000, 20000,
      "Vegetariano, pizza margarita o vegetariana, ensaladas, sin cebolla",
      fav={"vegetariano", "pizza", "saludable", "sin_cebolla"}, diet={"vegetariano"}),
    P("usr_estudiante_17", "Gamer de Sala de Cómputo", [((15, 30, 18, 30), 1)], WEEK, 8000, 28000,
      "Salchipapa, energizantes, salsa de ajo extra, pide para compartir",
      fav={"codigo", "energizante", "salsa_ajo", "compartir"}, appetite="big", qty="compartir", weight=1.2),
    P("usr_estudiante_18", "Docente de Mañana", [((7, 30, 9, 0), 2), ((10, 0, 10, 45), 1)],
      ["Martes", "Jueves"], 12000, 30000,
      "Café y pan, baja en azúcar, a veces compra para dos personas",
      fav={"cafe", "panaderia", "bajo_azucar", "sin_azucar", "gourmet"}, qty="compartir", weight=0.9),
    P("usr_estudiante_19", "Posgrado Nocturno", [(N, 2), ((17, 30, 18, 45), 1)],
      ["Lunes", "Martes", "Miércoles", "Jueves"], 6000, 20000,
      "Snack y café antes de la clase nocturna",
      fav={"cafe", "salado", "tarde", "caliente"}),
    P("usr_estudiante_20", "Saludable Cero Azúcar", [((10, 0, 11, 0), 1), ((13, 0, 14, 0), 1)], WEEK, 8000, 24000,
      "Sin azúcar, agua, frutas y opciones fitness, saludable",
      fav={"sin_azucar", "saludable", "fitness", "fruta", "sin_calorias"}),
    P("usr_estudiante_21", "Brunch Tardío", [(BRUNCH, 1)], WEEK, 6000, 20000,
      "Café, arepa y algo dulce a media mañana",
      fav={"cafe", "tradicional", "queso", "dulce", "manana"}),
    P("usr_estudiante_22", "Hamburguesa Rápida", [((11, 30, 12, 30), 1)], WEEK, 9000, 22000,
      "Almuerzos rápidos: hamburguesa, perro caliente y gaseosa, sin cebolla",
      fav={"rapida", "carne", "gaseosa", "sin_cebolla"}),
    P("usr_estudiante_23", "Semillero de Compras Grupales", [(T, 1), ((12, 0, 13, 30), 1)],
      ["Martes", "Miércoles", "Jueves"], 18000, 45000,
      "Compra para todo el semillero: bebidas y snacks para compartir",
      fav={"compartir", "gaseosa", "salado"}, appetite="big", qty="grupal", weight=0.8),
    P("usr_estudiante_24", "Snacker de Empanadas", [((15, 0, 17, 0), 1)], WEEK, 5000, 15000,
      "Empanadas, papas margarita y jugo, antojos salados de la tarde",
      fav={"salado", "tradicional", "paquete", "jugo"}),
    P("usr_estudiante_25", "Mixto Mañana y Tarde", [(M2, 1), ((16, 0, 17, 0), 1)], WEEK, 4000, 16000,
      "Un café por la mañana y un snack por la tarde, sin preferencia fija",
      fav={"cafe", "salado", "dulce"}),
    P("usr_estudiante_26", "Viernes de Gusto", [((12, 30, 14, 0), 1)], WEEK, 10000, 26000,
      "Entre semana almuerzo normal, el viernes se da el gusto con postre y salchipapa",
      fav={"viernes_gusto", "postre", "rapida"}, friday=True, weight=0.9),
    P("usr_estudiante_27", "Deportista de Madrugada", [((7, 0, 8, 0), 1)], WEEK, 6000, 18000,
      "Parfait, aromática y fruta antes de entrenar, vegetariano",
      fav={"saludable", "fruta", "fitness", "manana", "natural"}, diet={"vegetariano"}, appetite="light"),
    P("usr_estudiante_28", "Intercambio Curioso", [((11, 0, 15, 0), 1)], WEEK, 8000, 25000,
      "Le gusta probar productos nuevos cada vez, sin favorito fijo",
      explore=True, weight=1.0),
    P("usr_estudiante_29", "Tarde de Biblioteca", [((14, 30, 17, 0), 1)], WEEK, 3000, 12000,
      "Aromática, café y almojábana mientras estudia en la biblioteca",
      fav={"caliente", "cafe", "panaderia", "natural", "tradicional"}, appetite="light"),
    P("usr_estudiante_30", "Almuerzo Saludable de Pollo", [((12, 0, 13, 15), 1)], WEEK, 12000, 24000,
      "Pollo, ajiaco y ensaladas, poco picante, sin cebolla",
      fav={"pollo", "sopa", "saludable", "sin_cebolla", "sin_picante"}),
]

SLOT_TEMPLATE = {
    "MANANA": ["BEBIDAS", "SNACKS", "POSTRES", "BEBIDAS"],
    "ALMUERZO": ["ALMUERZOS", "BEBIDAS", "POSTRES", "SNACKS"],
    "TARDE": ["SNACKS", "BEBIDAS", "POSTRES", "SNACKS"],
}
SINGLE_CATEGORY = {  # que pide cuando la orden es de un solo alimento
    "MANANA": {"BEBIDAS": 0.7, "SNACKS": 0.3},
    "ALMUERZO": {"ALMUERZOS": 0.85, "SNACKS": 0.1, "BEBIDAS": 0.05},
    "TARDE": {"SNACKS": 0.5, "BEBIDAS": 0.3, "POSTRES": 0.2},
}
CATEGORY_BIAS = {  # cuanto pesa cada categoria segun la franja
    "MANANA": {"BEBIDAS": 1.0, "SNACKS": 0.85, "POSTRES": 0.4, "ALMUERZOS": 0.05},
    "ALMUERZO": {"ALMUERZOS": 1.0, "BEBIDAS": 0.8, "POSTRES": 0.5, "SNACKS": 0.3},
    "TARDE": {"SNACKS": 0.95, "BEBIDAS": 0.9, "POSTRES": 0.8, "ALMUERZOS": 0.1},
}


def slot_of(h: int, m: int) -> str:
    """Misma clasificacion que utility.parse_time_slot (la noche usa plantilla de tarde)."""
    mins = h * 60 + m
    if 420 <= mins < 660:
        return "MANANA"
    if 660 <= mins < 870:
        return "ALMUERZO"
    return "TARDE"


def pick(rng, weights: dict):
    return rng.choices(list(weights), weights=list(weights.values()), k=1)[0]


# El catalogo no etiqueta todos los ingredientes (ej. la pizza vegetariana no trae
# 'queso' y el perro caliente no trae 'carne'), asi que ademas de los tags se
# revisan palabras clave del nombre del producto.
MEAT_NAME_WORDS = ("perro caliente", "salchipapa", "hamburguesa", "jamón", "pollo", "carne",
                   "tocineta", "pepperoni", "ranchera", "criolla", "bandeja", "ajiaco",
                   "sándwich")
DAIRY_NAME_WORDS = ("queso", "crema", "helado", "leche", "yogurt", "pizza", "brownie",
                    "pan de ajo")


def _has_word(name: str, words: tuple) -> bool:
    n = name.lower()
    return any(w in n for w in words)


def allowed(prod: Product, prof: dict) -> bool:
    tags = set(prod.tags)
    diet = prof["diet"]
    if not prod.available:
        return False
    if diet & {"vegetariano", "vegano"}:
        if (MEAT & tags) and not ({"vegetariano", "vegano"} & tags):
            return False
        if _has_word(prod.name, MEAT_NAME_WORDS):
            return False
    if "vegano" in diet:
        # vegano: solo productos marcados 'vegano' o de fruta, sin lacteos
        if not ({"vegano", "fruta"} & tags):
            return False
        if (DAIRY & tags) and "vegano" not in tags:
            return False
        if _has_word(prod.name, ("queso", "crema", "helado", "leche", "yogurt")):
            return False
    if "lactosa" in diet and not (LACTOSE_SAFE & tags):
        if (DAIRY & tags) or _has_word(prod.name, DAIRY_NAME_WORDS):
            return False
    return True


def product_weight(prod: Product, prof: dict, slot: str) -> float:
    w = CATEGORY_BIAS[slot][prod.category.value] * 0.5 + 0.5
    if not prof["explore"]:
        w *= 1 + 2.0 * len(prof["fav"] & set(prod.tags))
    if prod.price > prof["bmax"]:
        w *= 0.1
    elif prod.price < prof["bmin"] * 0.3:
        w *= 0.7
    return w


def choose_quantity(rng, prof: dict, prod: Product) -> int:
    mode = prof["qty"]
    if mode == "grupal":
        return pick(rng, {1: 0.2, 2: 0.45, 3: 0.35})
    if mode == "compartir" and prod.category.value in ("SNACKS", "BEBIDAS", "ALMUERZOS"):
        return pick(rng, {1: 0.45, 2: 0.45, 3: 0.10})
    return pick(rng, {1: 0.9, 2: 0.1})


def build_order(rng, prof: dict, catalog: list, slot: str) -> list:
    """Devuelve [(Product, cantidad)] con 1 a 4 productos distintos."""
    n = pick(rng, N_PRODUCTS_WEIGHTS[prof["appetite"]])
    pool = [p for p in catalog if allowed(p, prof)]
    if n == 1:
        cats = [pick(rng, SINGLE_CATEGORY[slot])]
    else:
        cats = SLOT_TEMPLATE[slot][:n]
        if n >= 3 and rng.random() < 0.25:  # variedad: no siempre el mismo orden
            tail = cats[1:]
            rng.shuffle(tail)
            cats = [cats[0]] + tail
    chosen: list = []
    for cat in cats:
        cands = [p for p in pool if p.category.value == cat and p.id not in {c.id for c in chosen}]
        if not cands:
            continue
        # leve preferencia por el mismo restaurante del primer producto
        ws = [product_weight(p, prof, slot) * (1.4 if chosen and p.restaurant_id == chosen[0].restaurant_id else 1.0)
              for p in cands]
        chosen.append(rng.choices(cands, weights=ws, k=1)[0])
    # recorta si se pasa del presupuesto (siempre queda al menos 1 producto)
    items = [(p, choose_quantity(rng, prof, p)) for p in chosen]
    while len(items) > 1 and sum(p.price * q for p, q in items) > prof["bmax"] * 1.25:
        items.pop()
    return items[:MAX_PRODUCTS_PER_ORDER]


def weekdays_in_range(days: list) -> list:
    out, d = [], START
    while d <= END:
        if d.weekday() < 5 and DAYS_ES[d.weekday()] in days:
            out.append(d)
        d += timedelta(days=1)
    return out


def random_rating(rng) -> int:
    return pick(rng, {5: 0.65, 4: 0.28, 3: 0.07})


def generate(catalog: dict) -> list:
    rng = random.Random(SEED)
    prods = list(catalog.values())
    day_pool = {pr["uid"]: weekdays_in_range(pr["days"]) for pr in PROFILES}
    used = {pr["uid"]: set() for pr in PROFILES}  # (fecha, hora) ya usadas por usuario
    raw: list = []
    new_lines = 0

    def one_order(prof: dict) -> int:
        for _ in range(60):
            d = rng.choice(day_pool[prof["uid"]])
            if prof["friday"] and d.weekday() != 4 and rng.random() < 0.5:
                fridays = [x for x in day_pool[prof["uid"]] if x.weekday() == 4]
                d = rng.choice(fridays) if fridays else d
            h0, m0, h1, m1 = pick(rng, dict(prof["windows"]))
            minutes = rng.randint(h0 * 60 + m0, h1 * 60 + m1)
            hh, mm = divmod(minutes, 60)
            if (d, hh) in used[prof["uid"]]:
                continue
            used[prof["uid"]].add((d, hh))
            items = build_order(rng, prof, prods, slot_of(hh, mm))
            ts = datetime(d.year, d.month, d.day, hh, mm, rng.randint(0, 59))
            events = [(ts, items)]
            # a veces compra en dos momentos de la MISMA hora -> se unifica en 1 orden
            if len(items) >= 2 and rng.random() < SPLIT_SAME_HOUR_PROB:
                ts2 = ts + timedelta(minutes=rng.randint(8, 35))
                if ts2.hour == ts.hour:
                    k = rng.randint(1, len(items) - 1)
                    events = [(ts, items[:k]), (ts2, items[k:])]
            for when, evt in events:
                for prod, qty in evt:
                    raw.append(OrderItem(
                        user_id=prof["uid"], order_id="TMP",
                        timestamp=when.strftime("%Y-%m-%d %H:%M:%S"),
                        day_of_week=DAYS_ES[when.weekday()],
                        restaurant_id=prod.restaurant_id, product_id=prod.id,
                        product_name=prod.name, category=prod.category, quantity=qty,
                        unit_price=prod.price, total_price=prod.price * qty,
                        rating=random_rating(rng),
                    ))
            return len(items)
        return 0

    for prof in PROFILES:  # minimo de ordenes por usuario
        for _ in range(MIN_ORDERS_PER_USER):
            new_lines += one_order(prof)
    weights = [pr["weight"] for pr in PROFILES]
    while new_lines < TARGET_NEW_LINES:  # el resto, repartido segun el peso del perfil
        new_lines += one_order(rng.choices(PROFILES, weights=weights, k=1)[0])
    return raw


def fmt12(h0, m0, h1, m1) -> str:
    def f(h, m):
        return f"{(h % 12) or 12:02d}:{m:02d}"
    return f"{f(h0, m0)} - {f(h1, m1)} {'AM' if h1 < 12 else 'PM'}"


def build_archetypes(prof_list: list, orders: list) -> list:
    out = []
    for pr in prof_list:
        mine = [o for o in orders if o.user_id == pr["uid"]]
        top = Counter(o.product_name for o in mine).most_common(3)
        out.append({
            "user_id": pr["uid"],
            "archetype_name": pr["name"],
            "habitual_time_range": " y ".join(fmt12(*w) for w, _ in pr["windows"]),
            "frequent_days": pr["days"],
            "min_budget": pr["bmin"],
            "max_budget": pr["bmax"],
            "notes_clues": pr["notes"],
            "expected_recommendation": "Más pedidos: " + ", ".join(n for n, _ in top),
        })
    return out


def main() -> None:
    catalog = load_products(DATA_DIR / "products_catalog.csv")
    new_uids = {p["uid"] for p in PROFILES}

    base = [o for o in load_order_history(DATA_DIR / "order_history.csv", consolidate=False)
            if o.user_id not in new_uids]  # idempotente: se regeneran los usuarios 06-30
    generated = generate(catalog)
    all_lines = consolidate_orders(base + generated)
    save_order_history(all_lines, DATA_DIR / "order_history.csv")

    # ---- JSON maestro ----
    path = DATA_DIR / "breakapp_synthetic_dataset.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    kept = [a for a in data["user_archetypes"] if a["user_id"] not in new_uids]
    data["user_archetypes"] = kept + build_archetypes(PROFILES, all_lines)
    data["order_history"] = [{
        "order_id": o.order_id, "user_id": o.user_id, "product_id": o.product_id,
        "product_name": o.product_name, "restaurant_id": o.restaurant_id,
        "category": o.category.value, "quantity": o.quantity, "unit_price": o.unit_price,
        "total_price": o.total_price, "timestamp": o.timestamp,
        "day_of_week": o.day_of_week, "rating": o.rating,
    } for o in all_lines]
    orders = group_orders(all_lines)
    md = data["metadata"]
    md["total_orders"] = len(orders)
    md["total_order_lines"] = len(all_lines)
    md["total_archetypes"] = len(data["user_archetypes"])
    md["order_rule"] = (
        "Una orden agrupa todo lo que un usuario pide en la misma hora "
        f"(1 a {MAX_PRODUCTS_PER_ORDER} productos distintos); una fila por producto."
    )
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sizes = Counter(o.n_products for o in orders)
    print(f"Lineas nuevas: {len(generated)} | usuarios nuevos: {len(PROFILES)}")
    print(f"Total: {len(all_lines)} lineas en {len(orders)} ordenes")
    print("Productos por orden:", dict(sorted(sizes.items())))


if __name__ == "__main__":
    main()
