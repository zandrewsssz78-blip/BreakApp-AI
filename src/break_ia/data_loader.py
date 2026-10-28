"""Data loader and parser for BreakApp CSV and JSON datasets."""

import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

from break_ia.models import FoodCategory, OrderItem, Product, UserProfile


def load_products(catalog_path: Path) -> Dict[str, Product]:
    """Loads products catalog into a dictionary indexed by product ID."""
    products: Dict[str, Product] = {}
    with open(catalog_path, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                tags = json.loads(row["tags"]) if row.get("tags") else []
            except Exception:
                tags = [t.strip().strip('"') for t in row.get("tags", "").strip("[]").split(",") if t.strip()]

            try:
                pairings = json.loads(row["pairing_ids"]) if row.get("pairing_ids") else []
            except Exception:
                pairings = [p.strip().strip('"') for p in row.get("pairing_ids", "").strip("[]").split(",") if p.strip()]

            p = Product(
                id=row["id"],
                name=row["name"],
                description=row["description"],
                price=int(row["price"]),
                prep_time=int(row["prepTime"]),
                category=FoodCategory(row["category"]),
                restaurant_id=row["restaurantId"],
                available=row["available"].strip().lower() == "true",
                calories=int(row["calories"]) if row.get("calories") else 0,
                tags=tags,
                complementary_category=row.get("complementary_category"),
                pairing_ids=pairings,
            )
            products[p.id] = p
    return products


def load_order_history(orders_path: Path) -> List[OrderItem]:
    """Loads simulated order history transactions."""
    orders: List[OrderItem] = []
    with open(orders_path, mode="r", encoding="utf-8") as f:
        # Check if file has preamble metadata rows or starts directly with header
        lines = f.readlines()
        header_idx = -1
        for i, line in enumerate(lines):
            if "user_id,order_id,timestamp" in line:
                header_idx = i
                break

        if header_idx != -1:
            reader = csv.DictReader(lines[header_idx:])
        else:
            reader = csv.DictReader(lines)

        for row in reader:
            if not row.get("user_id") or not row.get("order_id"):
                continue
            rating = int(row["rating"]) if row.get("rating") and row["rating"].strip().isdigit() else None
            item = OrderItem(
                user_id=row["user_id"],
                order_id=row["order_id"],
                timestamp=row["timestamp"],
                day_of_week=row["day_of_week"],
                restaurant_id=row["restaurant_id"],
                product_id=row["product_id"],
                product_name=row["product_name"],
                category=FoodCategory(row["category"]),
                quantity=int(row["quantity"]),
                price_cop=int(row["price_cop"]),
                notes=row.get("notes", "").strip(),
                rating=rating,
            )
            orders.append(item)
    return orders


def load_user_archetypes() -> Dict[str, UserProfile]:
    """Pre-loaded ground truth archetypes defined in BreakApp synthetic benchmark."""
    return {
        "usr_estudiante_01": UserProfile(
            user_id="usr_estudiante_01",
            archetype_name="Estudiante Mañanero (Cafetero)",
            habitual_time_range="08:10 - 08:30 AM",
            frequent_days=["Lunes", "Miércoles", "Viernes"],
            min_budget=4500,
            max_budget=9500,
            notes_clues="Leche deslactosada, sin azúcar, fan del Capuchino",
            expected_recommendation="8:20 AM: Ofrecer Capuchino/Mocaccino deslactosado + Croissant o Galleta de Avena",
        ),
        "usr_estudiante_02": UserProfile(
            user_id="usr_estudiante_02",
            archetype_name="Almuerzo Ejecutivo + Viernes de Gusto",
            habitual_time_range="12:30 - 01:00 PM",
            frequent_days=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
            min_budget=15000,
            max_budget=28500,
            notes_clues="Alergia/rechazo a la cebolla ('Sin cebolla'), viernes pide postre",
            expected_recommendation="12:15 PM: Almuerzo Ejecutivo sin cebolla; los Viernes sugerir Hamburguesa + Brownie con Helado",
        ),
        "usr_estudiante_03": UserProfile(
            user_id="usr_estudiante_03",
            archetype_name="Fitness / Saludable / Vegetariano",
            habitual_time_range="10:30 AM y 01:15 PM",
            frequent_days=["Lunes", "Martes", "Jueves", "Viernes"],
            min_budget=12500,
            max_budget=31500,
            notes_clues="Leche de almendras, sin aderezos pesados, extra aguacate",
            expected_recommendation="1:00 PM: Bowl Quinoa o Falafel en Punto Verde + Té Matcha Frío o Trufa Vegana",
        ),
        "usr_estudiante_04": UserProfile(
            user_id="usr_estudiante_04",
            archetype_name="Estudiante Tarde / Tardes de Código",
            habitual_time_range="03:15 - 04:50 PM",
            frequent_days=["Lunes", "Martes", "Jueves", "Viernes"],
            min_budget=8200,
            max_budget=23000,
            notes_clues="Suele pedir de a 2 unidades (quantity=2) para compartir, salsa de ajo",
            expected_recommendation="3:30 PM: Combo 2x Empanadas Horneadas o Palitos de Queso + Mocaccino o Gaseosa",
        ),
        "usr_docente_05": UserProfile(
            user_id="usr_docente_05",
            archetype_name="Docente Gourmet / Compras Grupales",
            habitual_time_range="09:45 AM y 12:30 PM",
            frequent_days=["Martes", "Miércoles", "Jueves"],
            min_budget=23000,
            max_budget=34000,
            notes_clues="Leche de almendras, poco picante, baja en azúcar",
            expected_recommendation="9:35 AM (Mar/Jue): 2 Capuchinos + 2 Croissants; Miércoles 12:15 PM: Almuerzo + Cheesecake",
        ),
    }
