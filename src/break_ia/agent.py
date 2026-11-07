"""BreakAgent: Rational intelligent recommendation agent for BreakApp."""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

from break_ia.clustering import UserClusterModel
from break_ia.data_loader import (
    group_orders,
    load_order_history,
    load_products,
    load_user_archetypes,
)
from break_ia.models import (
    Order,
    OrderItem,
    Product,
    RecommendationItem,
    RecommendationResponse,
    UserProfile,
)
from break_ia.utility import DEFAULT_WEIGHTS, compute_utility_score, parse_time_slot


class BreakAgent:
    """Intelligent Recommender Agent for campus cafeterias."""

    def __init__(
        self,
        data_dir: Path,
        until: Optional[str] = None,
        use_clusters: bool = True,
        n_clusters: Optional[int] = None,
        cold_start_users: Optional[Set[str]] = None,
        cold_start_orders: int = 0,
    ):
        """until: solo usa pedidos con timestamp < until (para evaluar sin trampa).
        use_clusters: False = solo reglas/utilidad, sin aprendizaje no supervisado.
        n_clusters: fija k; con None se escoge por coeficiente de silueta.
        cold_start_users / cold_start_orders: simulan usuarios nuevos. Esos usuarios
        NO participan en el entrenamiento de los clusters y solo conservan sus
        primeras `cold_start_orders` ordenes como historial (se usa para evaluar)."""
        data_dir = Path(data_dir)
        dataset_path = data_dir / "breakapp_synthetic_dataset.json"

        self.catalog = load_products(data_dir / "products_catalog.csv")
        self.orders = load_order_history(data_dir / "order_history.csv")
        if until is not None:
            self.orders = [o for o in self.orders if o.timestamp < until]
        self.archetypes = load_user_archetypes(dataset_path)
        self.restaurant_names = self._load_restaurant_names(dataset_path)

        # Una orden = todo lo que el usuario pidio en la misma hora (1 a 4 productos)
        self.order_groups: List[Order] = group_orders(self.orders)

        # Group orders by user (lineas de pedido y ordenes completas)
        self.user_orders: Dict[str, List[OrderItem]] = {}
        for o in self.orders:
            self.user_orders.setdefault(o.user_id, []).append(o)
        self.user_order_groups: Dict[str, List[Order]] = {}
        for og in self.order_groups:
            self.user_order_groups.setdefault(og.user_id, []).append(og)

        # Aprendizaje no supervisado: clusters de usuarios por comportamiento
        cold = set(cold_start_users or ())
        self.clusters: Optional[UserClusterModel] = None
        if use_clusters:
            self.clusters = UserClusterModel.fit(
                {u: ls for u, ls in self.user_orders.items() if u not in cold},
                {u: gs for u, gs in self.user_order_groups.items() if u not in cold},
                self.catalog,
                k=n_clusters,
            )
        for u in cold:  # arranque en frio simulado: solo las primeras N ordenes
            groups = self.user_order_groups.get(u, [])[:cold_start_orders]
            keep = {g.order_id for g in groups}
            self.user_order_groups[u] = groups
            self.user_orders[u] = [i for i in self.user_orders.get(u, []) if i.order_id in keep]

    @staticmethod
    def _load_restaurant_names(dataset_path: Path) -> Dict[str, str]:
        """Nombres legibles de restaurantes (ej. 'peoples_pizza' -> "People's Pizza")."""
        if not dataset_path.exists():
            return {}
        with open(dataset_path, mode="r", encoding="utf-8") as f:
            restaurants = json.load(f).get("restaurants", [])
        return {r["restaurant_id"]: r["name"] for r in restaurants}

    def _restaurant_name(self, restaurant_id: str) -> str:
        return self.restaurant_names.get(restaurant_id, restaurant_id.replace("_", " ").title())

    def perceive(self, user_id: str, dt: datetime, day_of_week: str) -> dict:
        """Perceives user identity, current clock, day of week, and active catalog."""
        cluster_id = None
        if self.clusters is not None:
            cluster_id = self.clusters.cluster_of(user_id)
            if cluster_id is None:  # usuario que no estaba en el entrenamiento
                cluster_id = self.clusters.assign(
                    self.user_orders.get(user_id, []), self.user_order_groups.get(user_id, [])
                )
        return {
            "user_id": user_id,
            "datetime": dt,
            "day_of_week": day_of_week,
            "cluster_id": cluster_id,
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

    def _score(self, prod: Product, perception: dict, dt: datetime, day_of_week: str) -> float:
        cluster_aff = None
        if self.clusters is not None:
            slot = parse_time_slot(dt.hour, dt.minute)
            cluster_aff = self.clusters.affinity(perception["cluster_id"], slot, prod)
        return compute_utility_score(
            product=prod,
            user_orders=perception["user_orders"],
            user_profile=perception["profile"],
            target_dt=dt,
            day_of_week=day_of_week,
            catalog=self.catalog,
            cluster_affinity=cluster_aff,
        )

    def _best_pairing(
        self, prod: Product, perception: dict, dt: datetime, day_of_week: str
    ) -> Optional[Product]:
        """Elige el complemento (pairing_ids) con mayor utilidad para este usuario."""
        best: Optional[Product] = None
        best_score = 0.0
        for pid in prod.pairing_ids:
            cand = self.catalog.get(pid)
            if cand is None or not cand.available:
                continue
            s = self._score(cand, perception, dt, day_of_week)
            if s > best_score:
                best, best_score = cand, s
        return best

    def decide(self, user_id: str, dt: datetime, day_of_week: str, k: int = 3) -> RecommendationResponse:
        """Complete decision cycle evaluating candidate utilities and pairing combos."""
        perception = self.perceive(user_id, dt, day_of_week)
        candidates = self.filter_candidates(perception)

        scored = [(self._score(p, perception, dt, day_of_week), p) for p in candidates]
        scored.sort(key=lambda x: x[0], reverse=True)

        top_k: List[RecommendationItem] = [
            RecommendationItem(
                product=prod,
                utility_score=round(score, 4),
                matched_tags=prod.tags,
                pairing_product=self._best_pairing(prod, perception, dt, day_of_week),
            )
            for score, prod in scored[:k]
        ]

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
            cluster_id=perception["cluster_id"],
            cluster_label=self._cluster_label(perception["cluster_id"]),
        )

    def _cluster_label(self, cluster_id: Optional[int]) -> Optional[str]:
        if self.clusters is None or cluster_id is None or cluster_id not in self.clusters.info:
            return None
        return self.clusters.info[cluster_id].label

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
            return (
                f"¿Listo para tu descanso matutino? Te sugerimos {best.name}{pairing_str} "
                f"en {self._restaurant_name(best.restaurant_id)}."
            )
        elif slot == "ALMUERZO":
            if day.lower() == "viernes":
                return f"¡Es viernes de consentirse! Disfruta {best.name}{pairing_str}."
            return f"¿Hora de almorzar? Te recomendamos {best.name}{pairing_str} recién preparado."
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
    if agent.clusters is not None:
        print("Clusters de usuarios (K-Means):")
        print(agent.clusters.summary())

    test_cases = [
        ("usr_estudiante_01", datetime(2026, 10, 28, 8, 20), "Miércoles"),
        ("usr_estudiante_02", datetime(2026, 10, 30, 12, 45), "Viernes"),
        ("usr_estudiante_03", datetime(2026, 10, 29, 13, 10), "Jueves"),
        ("usr_estudiante_04", datetime(2026, 10, 29, 15, 30), "Jueves"),
        ("usr_docente_05", datetime(2026, 10, 28, 9, 45), "Miércoles"),
    ]

    for uid, dt, day in test_cases:
        res = agent.decide(uid, dt, day, k=3)
        cl = f" | Cluster {res.cluster_id}: {res.cluster_label}" if res.cluster_label else ""
        print(f"\n[Usuario: {uid}] - {day} {dt.strftime('%H:%M')}{cl}")
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
