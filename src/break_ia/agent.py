"""BreakAgent: Rational intelligent recommendation agent for BreakApp."""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from break_ia.data_loader import load_order_history, load_products, load_user_archetypes
from break_ia.models import (
    OrderItem,
    Product,
    RecommendationItem,
    RecommendationResponse,
    UserProfile,
)
from break_ia.utility import compute_utility_score, parse_time_slot


class BreakAgent:
    """Intelligent Recommender Agent for campus cafeterias."""

    def __init__(self, data_dir: Path):
        self.catalog = load_products(data_dir / "products_catalog.csv")
        self.orders = load_order_history(data_dir / "order_history.csv")
        self.archetypes = load_user_archetypes()

        # Group orders by user
        self.user_orders: Dict[str, List[OrderItem]] = {}
        for o in self.orders:
            self.user_orders.setdefault(o.user_id, []).append(o)

    def perceive(self, user_id: str, dt: datetime, day_of_week: str) -> dict:
        """Perceives user identity, current clock, day of week, and active catalog."""
        return {
            "user_id": user_id,
            "datetime": dt,
            "day_of_week": day_of_week,
            "user_orders": self.user_orders.get(user_id, []),
            "profile": self.archetypes.get(
                user_id,
                UserProfile(
                    user_id=user_id,
                    archetype_name="Estudiante General",
                    habitual_time_range="12:00 - 02:00 PM",
                    frequent_days=["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"],
                    min_budget=5000,
                    max_budget=20000,
                    notes_clues="",
                    expected_recommendation="Menú del día recomendado",
                ),
            ),
        }

    def filter_candidates(self, perception: dict) -> List[Product]:
        """Hard restriction filter: availability and mandatory catalog constraints."""
        candidates = [p for p in self.catalog.values() if p.available]
        return candidates

    def decide(self, user_id: str, dt: datetime, day_of_week: str, k: int = 3) -> RecommendationResponse:
        """Complete decision cycle evaluating candidate utilities and pairing combos."""
        perception = self.perceive(user_id, dt, day_of_week)
        candidates = self.filter_candidates(perception)

        scored_items: List[RecommendationItem] = []
        for prod in candidates:
            score = compute_utility_score(
                product=prod,
                user_orders=perception["user_orders"],
                user_profile=perception["profile"],
                target_dt=dt,
                day_of_week=day_of_week,
            )
            # Find best pairing product if defined
            pairing_prod: Optional[Product] = None
            if prod.pairing_ids:
                for pid in prod.pairing_ids:
                    if pid in self.catalog and self.catalog[pid].available:
                        pairing_prod = self.catalog[pid]
                        break

            scored_items.append(
                RecommendationItem(
                    product=prod,
                    utility_score=round(score, 4),
                    matched_tags=prod.tags,
                    pairing_product=pairing_prod,
                )
            )

        # Sort descending by utility
        scored_items.sort(key=lambda x: x.utility_score, reverse=True)
        top_k = scored_items[:k]

        # Generate contextual banner message
        banner = self._generate_banner(perception, top_k)

        # Formulate suggested combo
        suggested_combo = None
        if top_k and top_k[0].pairing_product:
            main_p = top_k[0].product
            side_p = top_k[0].pairing_product
            combo_total = main_p.price + side_p.price
            combo_discount_price = int(combo_total * 0.90)  # 10% combo discount
            suggested_combo = {
                "name": f"Combo Break: {main_p.name} + {side_p.name}",
                "main_item": main_p.name,
                "complementary_item": side_p.name,
                "restaurant": main_p.restaurant_id,
                "regular_price": combo_total,
                "combo_price": combo_discount_price,
                "savings": combo_total - combo_discount_price,
            }

        return RecommendationResponse(
            user_id=user_id,
            timestamp=dt.strftime("%Y-%m-%d %H:%M:%S"),
            day_of_week=day_of_week,
            banner_message=banner,
            top_recommendations=top_k,
            suggested_combo=suggested_combo,
        )

    def _generate_banner(self, perception: dict, top_items: List[RecommendationItem]) -> str:
        """Generates dynamic, human-like recommendation banner for mobile UI."""
        dt = perception["datetime"]
        day = perception["day_of_week"]
        slot = parse_time_slot(dt.hour, dt.minute)

        if not top_items:
            return "¡Bienvenido a BreakApp! Explora nuestras mejores opciones para hoy."

        best = top_items[0].product
        pairing = top_items[0].pairing_product
        pairing_str = f" con {pairing.name}" if pairing else ""

        if slot == "BREAK_MANANA":
            return f"¿Listo para tu descanso matutino? Te sugerimos un {best.name}{pairing_str} en {best.restaurant_id.replace('_', ' ').title()}."
        elif slot == "ALMUERZO":
            if day.lower() == "viernes":
                return f"¡Es viernes de consentirse! Disfruta un {best.name}{pairing_str}."
            return f"¿Hora de almorzar? Te recomendamos el {best.name}{pairing_str} recién preparado."
        elif slot == "BREAK_TARDE":
            return f"Recarga energía para tu tarde: prueba {best.name}{pairing_str}."
        else:
            return f"Termina tu jornada con una pausa deliciosa: {best.name}."


def main():
    """CLI execution for testing BreakAgent."""
    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "raw"
    agent = BreakAgent(data_dir)

    print("=" * 70)
    print("BREAKAPP-AI: AGENTE RACIONAL DE RECOMENDACIÓN CONTEXTUAL")
    print("=" * 70)

    test_cases = [
        ("usr_estudiante_01", datetime(2026, 10, 28, 8, 20), "Miércoles"),
        ("usr_estudiante_02", datetime(2026, 10, 30, 12, 45), "Viernes"),
        ("usr_estudiante_03", datetime(2026, 10, 29, 13, 10), "Jueves"),
        ("usr_estudiante_04", datetime(2026, 10, 29, 15, 30), "Jueves"),
        ("usr_docente_05", datetime(2026, 10, 28, 9, 45), "Miércoles"),
    ]

    for uid, dt, day in test_cases:
        res = agent.decide(uid, dt, day, k=3)
        print(f"\n[Usuario: {uid}] - {day} {dt.strftime('%H:%M')}")
        print(f"Banner: {res.banner_message}")
        print("Top 3 Recomendaciones:")
        for idx, item in enumerate(res.top_recommendations, 1):
            p = item.product
            pair_name = f" (Sugerencia combo: {item.pairing_product.name})" if item.pairing_product else ""
            print(f"  {idx}. {p.name} [{p.category.value}] - ${p.price:,} COP (Utilidad: {item.utility_score}){pair_name}")
        if res.suggested_combo:
            c = res.suggested_combo
            print(f"  * {c['name']} por ${c['combo_price']:,} COP (Ahorro: ${c['savings']:,} COP)")


if __name__ == "__main__":
    main()
