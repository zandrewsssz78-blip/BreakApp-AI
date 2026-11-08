"""Componentes colaborativos y de contenido para el recomendador híbrido BREAK.

Solo aprende con las líneas que recibe en el constructor. Si BreakAgent se crea
con `until`, este módulo nunca ve pedidos posteriores al corte temporal.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from datetime import datetime
from typing import Dict, List, Sequence, Tuple

from break_ia.models import OrderItem, Product
from break_ia.utility import parse_time_slot


def _cosine(a: Dict[str, float], b: Dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(v * b.get(k, 0.0) for k, v in a.items())
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


class HybridSignals:
    """Señales user-user, item-item, contenido y popularidad contextual."""

    def __init__(self, lines: Sequence[OrderItem], catalog: Dict[str, Product]):
        self.catalog = catalog
        self.user_items: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.user_slot_items: Dict[Tuple[str, str], Dict[str, float]] = defaultdict(dict)
        self.item_users: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.item_co: Dict[str, Counter] = defaultdict(Counter)
        self.slot_pop: Dict[str, Counter] = defaultdict(Counter)
        self.category_pop: Counter = Counter()
        self.user_last: Dict[str, datetime] = {}

        parsed = []
        for line in lines:
            try:
                dt = datetime.strptime(line.timestamp, "%Y-%m-%d %H:%M:%S")
            except (TypeError, ValueError):
                continue
            parsed.append((line, dt))
        reference = max((dt for _, dt in parsed), default=None)

        for line, dt in parsed:
            # Decaimiento temporal suave: los hábitos recientes pesan más.
            age_days = max(0, (reference - dt).days) if reference else 0
            weight = math.exp(-age_days / 120.0)
            slot = parse_time_slot(dt.hour, dt.minute)
            qty_w = weight * max(1, line.quantity)
            self.user_items[line.user_id][line.product_id] = (
                self.user_items[line.user_id].get(line.product_id, 0.0) + qty_w
            )
            self.user_slot_items[(line.user_id, slot)][line.product_id] = (
                self.user_slot_items[(line.user_id, slot)].get(line.product_id, 0.0) + qty_w
            )
            self.item_users[line.product_id][line.user_id] = (
                self.item_users[line.product_id].get(line.user_id, 0.0) + qty_w
            )
            self.slot_pop[slot][line.product_id] += weight
            self.category_pop[line.category.value] += weight
            self.user_last[line.user_id] = max(dt, self.user_last.get(line.user_id, dt))

        # Co-ocurrencia por orden, sin contar dos veces el mismo producto.
        baskets: Dict[str, set] = defaultdict(set)
        for line, _ in parsed:
            baskets[line.order_id].add(line.product_id)
        for basket in baskets.values():
            for pid in basket:
                for other in basket:
                    if pid != other:
                        self.item_co[pid][other] += 1

        # Pre-calcular vecindarios user-user y perfiles de contenido para inferencia rápida.
        self._neighbors: Dict[str, List[Tuple[float, Dict[str, float], float]]] = {}
        for uid, target in self.user_items.items():
            neigh = []
            for other_id, vector in self.user_items.items():
                if other_id == uid:
                    continue
                sim = _cosine(target, vector)
                if sim > 0:
                    neigh.append((sim, vector, max(vector.values(), default=1.0)))
            neigh.sort(key=lambda x: x[0], reverse=True)
            self._neighbors[uid] = neigh[:20]

        self._user_cat: Dict[str, Counter] = {}
        self._user_tags: Dict[str, Counter] = {}
        for uid, history in self.user_items.items():
            cat = Counter()
            tags = Counter()
            for pid, w in history.items():
                old = self.catalog.get(pid)
                if old is None:
                    continue
                cat[old.category.value] += w
                for tag in old.tags:
                    tags[tag.lower()] += w
            self._user_cat[uid] = cat
            self._user_tags[uid] = tags

    def user_score(self, user_id: str, product_id: str) -> float:
        """Puntuación user-user ponderada por similitud coseno e intensidad de compra."""
        neighbors = self._neighbors.get(user_id)
        if not neighbors:
            return 0.0
        denom = sum(sim for sim, _, _ in neighbors)
        if denom <= 0:
            return 0.0
        numerator = sum(
            sim * (vec.get(product_id, 0.0) / max_v)
            for sim, vec, max_v in neighbors
            if product_id in vec
        )
        return numerator / denom

    def item_score(self, user_id: str, product_id: str) -> float:
        """Puntuación item-item a partir de productos del historial del usuario."""
        history = self.user_items.get(user_id, {})
        if not history:
            return 0.0
        candidates = self.item_co
        weights = []
        for seen, strength in history.items():
            related = candidates.get(seen, Counter())
            total = sum(related.values())
            if total:
                weights.append((strength, related.get(product_id, 0) / total))
        denom = sum(w for w, _ in weights)
        return sum(w * score for w, score in weights) / denom if denom else 0.0

    def content_score(self, user_id: str, product: Product, slot: str = "") -> float:
        """Afinidad por producto histórico, categoría y etiquetas aprendidas."""
        history = self.user_items.get(user_id, {})
        if not history:
            return 0.0
        cat = self._user_cat.get(user_id, Counter())
        tags = self._user_tags.get(user_id, Counter())
        cat_score = cat.get(product.category.value, 0.0) / max(cat.values(), default=1.0)
        tag_score = (
            sum(tags.get(t.lower(), 0.0) for t in product.tags)
            / (len(product.tags) * max(tags.values()))
            if product.tags and tags else 0.0
        )
        slot_hist = self.user_slot_items.get((user_id, slot), {}) if slot else {}
        if slot_hist:
            prod_aff = slot_hist.get(product.id, 0.0) / max(slot_hist.values(), default=1.0)
        else:
            prod_aff = history.get(product.id, 0.0) / max(history.values(), default=1.0)
        return 0.35 * cat_score + 0.25 * tag_score + 0.40 * prod_aff

    def popularity_score(self, product_id: str, slot: str) -> float:
        """Fallback para cold start: popularidad de la franja con respaldo global."""
        counts = self.slot_pop.get(slot, Counter())
        if not counts:
            counts = Counter()
            for counter in self.slot_pop.values():
                counts.update(counter)
        return counts.get(product_id, 0.0) / max(counts.values(), default=1.0)

    def score(self, user_id: str, product: Product, slot: str) -> Tuple[float, dict]:
        user = self.user_score(user_id, product.id)
        item = self.item_score(user_id, product.id)
        content = self.content_score(user_id, product, slot)
        popularity = self.popularity_score(product.id, slot)
        has_history = bool(self.user_items.get(user_id))
        # Con historial: combina señales colaborativas, afinidad de contenido y contexto.
        if has_history:
            total = 0.35 * user + 0.20 * item + 0.30 * content + 0.15 * popularity
        else:
            total = 0.80 * popularity + 0.20 * content
        return total, {
            "user_cf": user, "item_cf": item, "content": content,
            "popularity": popularity, "has_history": has_history,
        }
