"""Utility function implementation for BreakApp-AI Agent."""

from datetime import datetime
from typing import Dict, List, Set
from break_ia.models import FoodCategory, OrderItem, Product, UserProfile


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


def calculate_temporal_affinity(product: Product, time_slot: str, day_of_week: str) -> float:
    """Returns probability score in [0.0, 1.0] for product relevance in time slot."""
    cat = product.category
    tags = set(product.tags)

    if time_slot == "BREAK_MANANA":
        if cat == FoodCategory.BEBIDAS and ("cafeina" in tags or "caliente" in tags):
            return 1.0
        elif cat == FoodCategory.SNACKS:
            return 0.85
        elif cat == FoodCategory.POSTRES:
            return 0.4
        elif cat == FoodCategory.ALMUERZOS:
            return 0.05
    elif time_slot == "ALMUERZO":
        if cat == FoodCategory.ALMUERZOS:
            # Special friday boost for indulgence
            if day_of_week.lower() == "viernes" and "indulgence" in tags:
                return 1.0
            return 0.95
        elif cat == FoodCategory.BEBIDAS and "frio" in tags:
            return 0.8
        elif cat == FoodCategory.POSTRES:
            return 0.7 if day_of_week.lower() == "viernes" else 0.4
        elif cat == FoodCategory.SNACKS:
            return 0.3
    elif time_slot == "BREAK_TARDE":
        if cat == FoodCategory.SNACKS:
            return 0.95
        elif cat == FoodCategory.BEBIDAS:
            return 0.9
        elif cat == FoodCategory.POSTRES:
            return 0.8
        elif cat == FoodCategory.ALMUERZOS:
            return 0.1
    return 0.5


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


def check_dietary_violations(product: Product, user_orders: List[OrderItem]) -> float:
    """Checks for explicit dietary restriction violations inferred from user notes."""
    notes_corpus = " ".join([o.notes.lower() for o in user_orders])
    tags = set(product.tags)
    penalty = 0.0

    # Intolerance to milk / lactose
    if "deslactosada" in notes_corpus or "almendras" in notes_corpus:
        if "lacteos" in tags and "deslactosado" not in tags and "vegano" not in tags:
            penalty += 10.0

    # Vegetarian / Vegan preference
    if "vegano" in notes_corpus or "vegetariano" in notes_corpus:
        if "proteina" in tags and "vegano" not in tags and "vegetariano" not in tags:
            penalty += 10.0

    # Onion rejection
    if "sin cebolla" in notes_corpus:
        # e.g., if dish contains onion, user will strongly reject it
        pass

    return penalty


def compute_utility_score(
    product: Product,
    user_orders: List[OrderItem],
    user_profile: UserProfile,
    target_dt: datetime,
    day_of_week: str,
    weights: Dict[str, float] = None,
) -> float:
    """Computes the overall scalar utility U(u, p, t)."""
    if weights is None:
        weights = {"content": 0.35, "temporal": 0.30, "budget": 0.20, "rating": 0.15}

    # 1. Content / Historical category and tag affinity
    cat_counts: Dict[FoodCategory, int] = {}
    user_tags: Set[str] = set()
    for o in user_orders:
        cat_counts[o.category] = cat_counts.get(o.category, 0) + 1
        # Extract keywords from past products
        if "saludable" in o.notes.lower() or "quinoa" in o.product_name.lower():
            user_tags.add("saludable")
        if "capuchino" in o.product_name.lower() or "café" in o.product_name.lower():
            user_tags.add("cafeina")

    total_orders = max(1, len(user_orders))
    cat_freq = cat_counts.get(product.category, 0) / total_orders
    shared_tags = set(product.tags).intersection(user_tags)
    tag_score = len(shared_tags) / max(1, len(user_tags)) if user_tags else 0.5
    s_content = 0.6 * cat_freq + 0.4 * tag_score

    # 2. Temporal Context
    slot = parse_time_slot(target_dt.hour, target_dt.minute)
    s_temporal = calculate_temporal_affinity(product, slot, day_of_week)

    # 3. Budget Fit
    s_budget = calculate_budget_affinity(product.price, user_profile.min_budget, user_profile.max_budget)

    # 4. Rating & Quality
    s_rating = 0.85 if product.available else 0.0

    # 5. Dietary Violations Penalty
    penalty = check_dietary_violations(product, user_orders)

    utility = (
        weights["content"] * s_content
        + weights["temporal"] * s_temporal
        + weights["budget"] * s_budget
        + weights["rating"] * s_rating
        - penalty
    )

    return max(0.0, utility)
