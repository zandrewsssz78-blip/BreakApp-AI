"""Data models for BreakApp-AI, aligning with BreakApp domain models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class FoodCategory(str, Enum):
    ALMUERZOS = "ALMUERZOS"
    SNACKS = "SNACKS"
    BEBIDAS = "BEBIDAS"
    POSTRES = "POSTRES"


@dataclass
class Product:
    id: str
    name: str
    price: int
    prep_time: int  # minutos (punto medio del rango del catalogo, ej. "10-15 min" -> 12)
    category: FoodCategory
    restaurant_id: str
    available: bool
    tags: List[str] = field(default_factory=list)
    pairing_ids: List[str] = field(default_factory=list)


@dataclass
class OrderItem:
    user_id: str
    order_id: str
    timestamp: str
    day_of_week: str
    restaurant_id: str
    product_id: str
    product_name: str
    category: FoodCategory
    quantity: int
    unit_price: int
    total_price: int
    rating: Optional[int] = None


@dataclass
class Order:
    """Una orden = todo lo que un usuario pidio en una misma hora (1 a 4 productos)."""

    order_id: str
    user_id: str
    timestamp: str  # momento del primer pedido de esa hora
    day_of_week: str
    items: List[OrderItem] = field(default_factory=list)

    @property
    def n_products(self) -> int:
        """Cantidad de productos distintos en la orden."""
        return len(self.items)

    @property
    def total_price(self) -> int:
        return sum(i.total_price for i in self.items)


@dataclass
class UserProfile:
    user_id: str
    archetype_name: str
    habitual_time_range: str
    frequent_days: List[str]
    min_budget: int
    max_budget: int
    notes_clues: str
    expected_recommendation: str


@dataclass
class RecommendationItem:
    product: Product
    utility_score: float
    matched_tags: List[str] = field(default_factory=list)
    pairing_product: Optional[Product] = None


@dataclass
class RecommendationResponse:
    user_id: str
    timestamp: str
    day_of_week: str
    banner_message: str
    top_recommendations: List[RecommendationItem]
    suggested_combo: Optional[dict] = None
    cluster_id: Optional[int] = None
    cluster_label: Optional[str] = None
