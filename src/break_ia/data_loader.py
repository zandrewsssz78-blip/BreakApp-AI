"""Data loader and parser for BreakApp CSV and JSON datasets."""

import csv
import json
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List

from break_ia.models import FoodCategory, Order, OrderItem, Product, UserProfile

MAX_PRODUCTS_PER_ORDER = 4  # productos distintos permitidos en una sola orden
ORDER_CSV_FIELDS = [
    "order_id", "user_id", "product_id", "product_name", "restaurant_id",
    "category", "quantity", "unit_price", "total_price", "timestamp",
    "day_of_week", "rating",
]


def _parse_list(value: str) -> List[str]:
    """Parsea listas del CSV: 'a|b|c' (formato actual) o '["a", "b"]' (formato JSON)."""
    value = (value or "").strip()
    if not value:
        return []
    if value.startswith("["):
        try:
            return [str(v) for v in json.loads(value)]
        except json.JSONDecodeError:
            value = value.strip("[]")
    return [v.strip().strip('"') for v in value.replace(",", "|").split("|") if v.strip()]


def _parse_prep_time(value: str) -> int:
    """Convierte '10-15 min' en minutos (punto medio). Acepta tambien un entero."""
    digits = [int(n) for n in "".join(c if c.isdigit() else " " for c in value or "").split()]
    if not digits:
        return 0
    return round(sum(digits) / len(digits))


def _parse_rating(value: str):
    """Rating como entero; admite '5' o '5.0'. Devuelve None si esta vacio."""
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def load_products(catalog_path: Path) -> Dict[str, Product]:
    """Loads products catalog into a dictionary indexed by product ID."""
    products: Dict[str, Product] = {}
    with open(catalog_path, mode="r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            p = Product(
                id=row["product_id"],
                name=row["name"],
                price=int(row["price"]),
                prep_time=_parse_prep_time(row.get("prep_time", "")),
                category=FoodCategory(row["category"]),
                restaurant_id=row["restaurant_id"],
                available=row["available"].strip().lower() == "true",
                tags=_parse_list(row.get("tags", "")),
                pairing_ids=_parse_list(row.get("pairing_ids", "")),
            )
            products[p.id] = p
    return products


def _hour_key(item: OrderItem) -> tuple:
    """Clave de agrupacion: usuario + fecha + hora (ej. 2026-08-03 08)."""
    return (item.user_id, item.timestamp[:13])


def consolidate_orders(items: List[OrderItem]) -> List[OrderItem]:
    """Une en UNA sola orden todo lo que un usuario pidio en la misma hora.

    - Lineas del mismo usuario, fecha y hora comparten order_id y timestamp
      (el del primer pedido de esa hora).
    - Si el mismo producto aparece dos veces en la hora, se suma la cantidad.
    - Las ordenes se renumeran en orden cronologico (ORD_0001, ORD_0002, ...),
      asi que aplicarla dos veces da el mismo resultado.
    - Una orden no puede tener mas de MAX_PRODUCTS_PER_ORDER productos distintos.
    """
    groups: "OrderedDict[tuple, List[OrderItem]]" = OrderedDict()
    for it in sorted(items, key=lambda i: (i.timestamp, i.user_id)):
        groups.setdefault(_hour_key(it), []).append(it)

    result: List[OrderItem] = []
    for n, lines in enumerate(groups.values(), start=1):
        order_id = f"ORD_{n:04d}"
        first = lines[0]
        merged: "OrderedDict[str, OrderItem]" = OrderedDict()
        for ln in lines:
            if ln.product_id in merged:
                m = merged[ln.product_id]
                m.quantity += ln.quantity
                m.total_price = m.quantity * m.unit_price
                if m.rating is None:
                    m.rating = ln.rating
                elif ln.rating is not None:
                    m.rating = round((m.rating + ln.rating) / 2)
            else:
                merged[ln.product_id] = OrderItem(
                    user_id=ln.user_id,
                    order_id=order_id,
                    timestamp=first.timestamp,
                    day_of_week=first.day_of_week,
                    restaurant_id=ln.restaurant_id,
                    product_id=ln.product_id,
                    product_name=ln.product_name,
                    category=ln.category,
                    quantity=ln.quantity,
                    unit_price=ln.unit_price,
                    total_price=ln.total_price,
                    rating=ln.rating,
                )
        if len(merged) > MAX_PRODUCTS_PER_ORDER:
            raise ValueError(
                f"{order_id} ({first.user_id}, {first.timestamp[:13]}h) tiene "
                f"{len(merged)} productos; el maximo es {MAX_PRODUCTS_PER_ORDER}."
            )
        result.extend(merged.values())
    return result


def group_orders(items: List[OrderItem]) -> List[Order]:
    """Agrupa las lineas (OrderItem) por order_id en objetos Order."""
    by_id: "OrderedDict[str, Order]" = OrderedDict()
    for it in items:
        order = by_id.get(it.order_id)
        if order is None:
            order = by_id[it.order_id] = Order(
                order_id=it.order_id,
                user_id=it.user_id,
                timestamp=it.timestamp,
                day_of_week=it.day_of_week,
            )
        order.items.append(it)
    return list(by_id.values())


def load_order_history(orders_path: Path, consolidate: bool = True) -> List[OrderItem]:
    """Carga el historial de pedidos (una fila por producto de cada orden).

    Con consolidate=True (por defecto) los pedidos de un mismo usuario hechos en
    la misma hora quedan como una sola orden, aunque el CSV los traiga separados.
    """
    orders: List[OrderItem] = []
    with open(orders_path, mode="r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("user_id") or not row.get("order_id"):
                continue
            orders.append(
                OrderItem(
                    user_id=row["user_id"],
                    order_id=row["order_id"],
                    timestamp=row["timestamp"],
                    day_of_week=row["day_of_week"],
                    restaurant_id=row["restaurant_id"],
                    product_id=row["product_id"],
                    product_name=row["product_name"],
                    category=FoodCategory(row["category"]),
                    quantity=int(row["quantity"]),
                    unit_price=int(row["unit_price"]),
                    total_price=int(row["total_price"]),
                    rating=_parse_rating(row.get("rating")),
                )
            )
    return consolidate_orders(orders) if consolidate else orders


def save_order_history(items: List[OrderItem], orders_path: Path) -> None:
    """Escribe el historial en CSV con el mismo formato que usa load_order_history."""
    with open(orders_path, mode="w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=ORDER_CSV_FIELDS)
        w.writeheader()
        for i in items:
            w.writerow({
                "order_id": i.order_id, "user_id": i.user_id,
                "product_id": i.product_id, "product_name": i.product_name,
                "restaurant_id": i.restaurant_id, "category": i.category.value,
                "quantity": i.quantity, "unit_price": i.unit_price,
                "total_price": i.total_price, "timestamp": i.timestamp,
                "day_of_week": i.day_of_week,
                "rating": "" if i.rating is None else i.rating,
            })


def load_user_archetypes(dataset_path: Path = None) -> Dict[str, UserProfile]:
    """Carga los arquetipos desde breakapp_synthetic_dataset.json (user_archetypes).

    Si el archivo no existe devuelve el respaldo integrado (los mismos 5 arquetipos).
    """
    if dataset_path is not None and Path(dataset_path).exists():
        with open(dataset_path, mode="r", encoding="utf-8") as f:
            raw = json.load(f).get("user_archetypes", [])
        if raw:
            return {
                a["user_id"]: UserProfile(
                    user_id=a["user_id"],
                    archetype_name=a["archetype_name"],
                    habitual_time_range=a["habitual_time_range"],
                    frequent_days=a["frequent_days"],
                    min_budget=a["min_budget"],
                    max_budget=a["max_budget"],
                    notes_clues=a["notes_clues"],
                    expected_recommendation=a["expected_recommendation"],
                )
                for a in raw
            }
    return _default_archetypes()


def _default_archetypes() -> Dict[str, UserProfile]:
    """Respaldo: arquetipos del benchmark sintetico BreakApp."""
    week = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    return {
        "usr_estudiante_01": UserProfile(
            "usr_estudiante_01", "Estudiante Mañanero / Cafetero", "08:00 - 09:00 AM",
            ["Lunes", "Miércoles", "Viernes"], 4500, 11000,
            "Leche deslactosada, sin azúcar, fan del Capuchino y panadería recién horneada",
            "Capuchino o Café con Croissant de Chocolate / Pandebono / Muffin de arándanos",
        ),
        "usr_estudiante_02": UserProfile(
            "usr_estudiante_02", "Almuerzo Ejecutivo + Viernes de Gusto", "12:15 - 01:15 PM",
            week, 14000, 28500,
            "Sin cebolla, almuerzo tradicional entre semana y viernes de pizza, hamburguesa o postre",
            "Lun-Jue: Bandeja Paisa Break o Ajiaco Santafereño + Jugo; "
            "Viernes: Hamburguesa Sencilla o Pizza Pepperoni + Brownie con Helado",
        ),
        "usr_estudiante_03": UserProfile(
            "usr_estudiante_03", "Fitness / Saludable / Vegetariano", "10:15 - 11:00 AM y 12:45 - 01:30 PM",
            week, 10000, 26000,
            "Leche de almendras o en agua, sin aderezos pesados, opciones vegetarianas y frutas frescas",
            "Almuerzo de Ensalada, Pizza Vegetariana o Ensalada de Frutas Premium + Jugo Natural en Agua / Aromática",
        ),
        "usr_estudiante_04": UserProfile(
            "usr_estudiante_04", "Estudiante Tarde / Tardes de Código", "03:15 - 05:00 PM",
            week, 8000, 22000,
            "Pide para compartir en grupo, salsa de ajo extra, snacks salados y bebidas energizantes o gaseosas",
            "Palitos de Queso, Salchipapa Tradicional o Empanadas + Colombiana / Pepsi Personal / Speed Max",
        ),
        "usr_docente_05": UserProfile(
            "usr_docente_05", "Docente Gourmet / Compras Grupales", "09:30 - 10:15 AM y 12:30 - 01:30 PM",
            ["Martes", "Miércoles", "Jueves"], 18000, 35000,
            "Leche de almendras, baja en azúcar, compras dobles para colegas, gusto por repostería fina y almuerzos típicos",
            "Mañana: Capuchino + Croissant de Chocolate / Fresas con Crema; "
            "Mediodía: Ajiaco Santafereño + Jugo Natural + Postre Tres Leches",
        ),
    }
