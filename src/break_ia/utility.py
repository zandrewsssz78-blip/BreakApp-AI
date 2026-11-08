"""Utility function implementation for BreakApp-AI Agent."""

from datetime import datetime
from typing import Dict, List, Optional

from break_ia.models import FoodCategory, OrderItem, Product, UserProfile

DEFAULT_WEIGHTS = {
    "content": 0.36,
    "temporal": 0.26,
    "budget": 0.16,
    "rating": 0.10,
    "cluster": 0.12,  # afinidad de usuarios parecidos (clustering no supervisado)
}
NEUTRAL_RATING = 0.8  # calificacion asumida para productos que el usuario nunca ha pedido
SAME_DAY_WEIGHT = 2.0  # peso extra de los pedidos hechos el mismo dia de la semana
SAME_SLOT_WEIGHT = 2.5  # refuerzo para pedidos realizados en la misma franja horaria
MIN_SLOT_ORDERS = 2  # minimo de pedidos en la franja para priorizar esa franja


def parse_time_slot(hour: int, minute: int) -> str:
    """Classifies a time into university campus meal periods."""
    minutes = hour * 60 + minute
    if 420 <= minutes < 660:  # 07:00 to 11:00
        return "BREAK_MANANA"
    elif 660 <= minutes < 870:  # 11:00 to 14:30
        return "ALMUERZO"
    elif 870 <= minutes < 1140:  # 14:30 to 19:00
        return "BREAK_TARDE"
    return "NOCHE"


def _order_slot(order: OrderItem) -> Optional[str]:
    """Franja horaria en la que se hizo un pedido historico (extraccion directa YYYY-MM-DD HH:MM:SS)."""
    ts = order.timestamp
    if len(ts) >= 16 and ts[13] == ":":
        try:
            return parse_time_slot(int(ts[11:13]), int(ts[14:16]))
        except ValueError:
            pass
    try:
        dt = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return parse_time_slot(dt.hour, dt.minute)
    except ValueError:
        return None


def calculate_temporal_affinity(product: Product, time_slot: str, day_of_week: str) -> float:
    """Returns probability score in [0.0, 1.0] for product relevance in time slot."""
    cat = product.category
    tags = set(product.tags)
    is_friday = day_of_week.lower() == "viernes"
    score = 0.5

    if time_slot == "BREAK_MANANA":
        if cat == FoodCategory.BEBIDAS and ({"cafe", "caliente"} & tags):
            score = 1.0
        elif cat == FoodCategory.SNACKS:
            score = 0.85
        elif cat == FoodCategory.POSTRES:
            score = 0.4
        elif cat == FoodCategory.ALMUERZOS:
            score = 0.05
        if "manana" in tags:
            score = min(1.0, score + 0.1)
    elif time_slot == "ALMUERZO":
        if cat == FoodCategory.ALMUERZOS:
            # Viernes de gusto: refuerzo para platos de antojo
            score = 1.0 if (is_friday and "viernes_gusto" in tags) else 0.95
        elif cat == FoodCategory.BEBIDAS and ({"fria", "jugo"} & tags):
            score = 0.8
        elif cat == FoodCategory.POSTRES:
            score = 0.7 if is_friday else 0.4
            if is_friday and "viernes_gusto" in tags:
                score = 0.85
        elif cat == FoodCategory.SNACKS:
            score = 0.3
    elif time_slot == "BREAK_TARDE":
        if cat == FoodCategory.SNACKS:
            score = 0.95
        elif cat == FoodCategory.BEBIDAS:
            score = 0.9
        elif cat == FoodCategory.POSTRES:
            score = 0.8
        elif cat == FoodCategory.ALMUERZOS:
            score = 0.1
        if "tarde" in tags:
            score = min(1.0, score + 0.05)
    return score


def calculate_budget_affinity(product_price: int, min_b: int, max_b: int) -> float:
    """Calculates how well product price fits within user customary budget."""
    if min_b <= product_price <= max_b:
        return 1.0
    elif product_price < min_b:
        ratio = product_price / max(1, min_b)
        return max(0.4, ratio)
    else:
        overshoot = product_price - max_b
        return max(0.0, 1.0 - (overshoot / max(1, max_b)))


def _history_context(
    user_orders: List[OrderItem], slot: str, day_of_week: str
) -> List[tuple]:
    """Pedidos pasados con su peso segun el contexto actual.

    - Si el usuario tiene al menos MIN_SLOT_ORDERS en la franja, prioriza esa franja.
    - Los pedidos de la misma franja y del mismo dia de la semana reciben mayor peso.
    """
    in_slot = [o for o in user_orders if _order_slot(o) == slot]
    relevant = in_slot if len(in_slot) >= MIN_SLOT_ORDERS else user_orders
    day_low = day_of_week.lower()
    weighted = []
    for o in relevant:
        w = SAME_DAY_WEIGHT if o.day_of_week.lower() == day_low else 1.0
        if _order_slot(o) == slot:
            w *= SAME_SLOT_WEIGHT
        weighted.append((o, w))
    return weighted


def compute_utility_score(
    product: Product,
    user_orders: List[OrderItem],
    user_profile: UserProfile,
    target_dt: datetime,
    day_of_week: str,
    weights: Dict[str, float] = None,
    catalog: Dict[str, Product] = None,
    cluster_affinity: Optional[float] = None,
) -> float:
    """Computes the overall scalar utility U(u, p, t).

    cluster_affinity: afinidad [0, 1] del producto para los usuarios de su mismo
    cluster (ver clustering.py). Si es None se ignora ese termino y el peso se
    reparte entre los demas.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    slot = parse_time_slot(target_dt.hour, target_dt.minute)
    weighted_orders = _history_context(user_orders, slot, day_of_week)
    total_w = sum(w for _, w in weighted_orders) or 1.0

    # 1. Content: afinidad historica por categoria, etiquetas y producto concreto
    cat_w: Dict[FoodCategory, float] = {}
    prod_w: Dict[str, float] = {}
    tag_w: Dict[str, float] = {}
    for o, w in weighted_orders:
        cat_w[o.category] = cat_w.get(o.category, 0.0) + w
        prod_w[o.product_id] = prod_w.get(o.product_id, 0.0) + w
        if catalog and o.product_id in catalog:
            for t in catalog[o.product_id].tags:
                tag_w[t] = tag_w.get(t, 0.0) + w

    cat_freq = cat_w.get(product.category, 0.0) / total_w
    prod_affinity = prod_w.get(product.id, 0.0) / max(prod_w.values(), default=1.0)
    if tag_w and product.tags:
        max_tag = max(tag_w.values())
        tag_score = sum(tag_w.get(t, 0.0) / max_tag for t in product.tags) / len(product.tags)
    else:
        tag_score = 0.5
    s_content = 0.25 * cat_freq + 0.25 * tag_score + 0.50 * prod_affinity

    # 2. Temporal Context
    s_temporal = calculate_temporal_affinity(product, slot, day_of_week)

    # 3. Budget Fit
    s_budget = calculate_budget_affinity(product.price, user_profile.min_budget, user_profile.max_budget)

    # 4. Rating: calificacion media que el usuario le dio a este producto
    ratings = [o.rating for o in user_orders if o.product_id == product.id and o.rating]
    s_rating = (sum(ratings) / len(ratings) / 5.0) if ratings else NEUTRAL_RATING
    if not product.available:
        s_rating = 0.0

    # 5. Afinidad de cluster adaptativa: mayor respaldo cuando el historial propio es corto
    w_cluster = weights.get("cluster", 0.0)
    base_scale = max(1e-9, 1.0 - w_cluster)
    base_norm = (
        weights["content"] * s_content
        + weights["temporal"] * s_temporal
        + weights["budget"] * s_budget
        + weights["rating"] * s_rating
    ) / base_scale
    if cluster_affinity is None:
        utility = base_norm
    else:
        slot_count = sum(1 for o in user_orders if _order_slot(o) == slot)
        eff_w = 0.015 if slot_count >= 3 else (0.04 if slot_count == 2 else (0.14 if slot_count == 1 else 0.24))
        utility = (1.0 - eff_w) * base_norm + eff_w * cluster_affinity

    return max(0.0, utility)
