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
    description: str
    price: int
    prep_time: int
    category: FoodCategory
    restaurant_id: str
    available: bool
    calories: int
    tags: List[str] = field(default_factory=list)
    complementary_category: Optional[str] = None
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
    price_cop: int
    notes: str
    rating: Optional[int] = None


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
