"""Aprendizaje no supervisado: agrupa usuarios por comportamiento de consumo.

Solo usa lo que realmente tiene la base de datos: horas de los pedidos,
categorias, precios y tamano de las ordenes (nada de ingredientes).

Pasos:
1. Cada usuario se resume en un vector de 10 numeros (``user_features``).
2. Se normalizan (min-max) y se agrupan con K-Means (k-means++ y varios
   reinicios). El numero de clusters k se escoge con el coeficiente de silueta.
3. Para cada cluster se cuenta que productos se piden y a que hora. Esa
   popularidad "de gente parecida" alimenta la funcion de utilidad del agente
   y sirve de respaldo cuando un usuario tiene poco historial.

K-Means y silueta estan implementados desde cero (sin numpy ni scikit-learn).
"""

import math
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from break_ia.models import FoodCategory, Order, OrderItem, Product
from break_ia.utility import parse_time_slot

SLOTS = ["BREAK_MANANA", "ALMUERZO", "BREAK_TARDE", "NOCHE"]
SLOT_LABEL = {
    "BREAK_MANANA": "Mañana",
    "ALMUERZO": "Mediodía",
    "BREAK_TARDE": "Tarde",
    "NOCHE": "Noche",
}
CATEGORIES = [c.value for c in FoodCategory]
FEATURE_NAMES = (
    [f"franja_{s}" for s in SLOTS]
    + [f"cat_{c}" for c in CATEGORIES]
    + ["precio_unitario_prom", "productos_por_orden"]
)
MIN_LINES_FOR_KEY = 8  # minimo de lineas para confiar en la popularidad de un cluster/franja


# ---------------------------------------------------------------- vectores de usuario
def user_features(lines: Sequence[OrderItem], groups: Sequence[Order]) -> List[float]:
    """Vector crudo del usuario: % de ordenes por franja, % de lineas por categoria,
    precio unitario promedio y productos por orden."""
    slot_counts: Counter = Counter()
    for g in groups:
        try:
            dt = datetime.strptime(g.timestamp, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        slot_counts[parse_time_slot(dt.hour, dt.minute)] += 1
    n_orders = sum(slot_counts.values()) or 1
    cat_counts = Counter(i.category.value for i in lines)
    n_lines = sum(cat_counts.values()) or 1
    avg_price = sum(i.unit_price for i in lines) / (len(lines) or 1)
    basket = sum(g.n_products for g in groups) / (len(groups) or 1)
    dates = []
    for group in groups:
        try:
            dates.append(datetime.strptime(group.timestamp, "%Y-%m-%d %H:%M:%S"))
        except ValueError:
            pass
    span_weeks = max(1.0, ((max(dates) - min(dates)).days / 7.0) if len(dates) > 1 else 1.0)
    frequency = len(groups) / span_weeks
    diversity = len(cat_counts) / max(1, len(CATEGORIES))
    return (
        [slot_counts[s] / n_orders for s in SLOTS]
        + [cat_counts[c] / n_lines for c in CATEGORIES]
        # Frecuencia y diversidad se conservan como métricas descriptivas,
        # pero se excluyen del espacio de distancias: en las pruebas controladas
        # redujeron la silueta sin mejorar las métricas del recomendador.
        + [avg_price, basket]
    )


def _dist2(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((x - y) ** 2 for x, y in zip(a, b))


# ---------------------------------------------------------------- K-Means y silueta
def kmeans(
    points: List[List[float]], k: int, seed: int = 7, n_init: int = 10, max_iter: int = 100
) -> Tuple[List[List[float]], List[int], float]:
    """K-Means con inicializacion k-means++. Devuelve (centroides, etiquetas, inercia)."""
    best: Optional[Tuple[List[List[float]], List[int], float]] = None
    for init in range(n_init):
        rng = random.Random(seed * 1000 + init)
        centroids = [list(rng.choice(points))]
        while len(centroids) < k:
            d2 = [min(_dist2(p, c) for c in centroids) for p in points]
            total = sum(d2)
            if total == 0:
                centroids.append(list(rng.choice(points)))
                continue
            r, acc = rng.random() * total, 0.0
            for p, d in zip(points, d2):
                acc += d
                if acc >= r:
                    centroids.append(list(p))
                    break
        labels = [-1] * len(points)
        for it in range(max_iter):
            new = [min(range(k), key=lambda c: _dist2(p, centroids[c])) for p in points]
            if new == labels:
                break
            labels = new
            for c in range(k):
                members = [p for p, lab in zip(points, labels) if lab == c]
                if members:
                    centroids[c] = [sum(col) / len(members) for col in zip(*members)]
        inertia = sum(_dist2(p, centroids[lab]) for p, lab in zip(points, labels))
        if best is None or inertia < best[2]:
            best = ([list(c) for c in centroids], labels, inertia)
    assert best is not None
    return best


def silhouette(points: List[List[float]], labels: List[int]) -> float:
    """Coeficiente de silueta promedio en [-1, 1] (mas alto = clusters mas separados)."""
    clusters = sorted(set(labels))
    if len(clusters) < 2:
        return 0.0
    total = 0.0
    valid_points = 0
    for i, p in enumerate(points):
        own = [math.sqrt(_dist2(p, q)) for j, q in enumerate(points) if labels[j] == labels[i] and j != i]
        if not own:  # cluster de un solo usuario
            continue
        a = sum(own) / len(own)
        b = min(
            sum(math.sqrt(_dist2(p, q)) for j, q in enumerate(points) if labels[j] == c)
            / sum(1 for lab in labels if lab == c)
            for c in clusters
            if c != labels[i]
        )
        total += (b - a) / max(a, b) if max(a, b) > 0 else 0.0
        valid_points += 1
    return total / max(1, valid_points)




def adjusted_rand_index(labels_a: Sequence[int], labels_b: Sequence[int]) -> float:
    """Adjusted Rand Index entre dos particiones, invariante a IDs de cluster."""
    if len(labels_a) != len(labels_b) or len(labels_a) < 2:
        return 1.0
    from math import comb
    table: Counter = Counter(zip(labels_a, labels_b))
    rows: Counter = Counter(labels_a)
    cols: Counter = Counter(labels_b)
    choose2 = lambda n: n * (n - 1) / 2
    n_pairs = choose2(len(labels_a))
    if n_pairs == 0:
        return 1.0
    index = sum(choose2(v) for v in table.values())
    sum_rows = sum(choose2(v) for v in rows.values())
    sum_cols = sum(choose2(v) for v in cols.values())
    expected = (sum_rows * sum_cols) / n_pairs
    maximum = 0.5 * (sum_rows + sum_cols)
    return (index - expected) / (maximum - expected) if maximum != expected else 1.0


# ---------------------------------------------------------------- modelo de clusters
@dataclass
class ClusterInfo:
    cluster_id: int
    label: str
    users: List[str]
    top_products: List[str]
    mean_features: Dict[str, float] = field(default_factory=dict)


class UserClusterModel:
    """Clusters de usuarios + popularidad de productos por cluster y franja."""

    def __init__(self) -> None:
        self.k: int = 1
        self.silhouette: float = 0.0
        self.silhouette_by_k: Dict[int, float] = {}
        self.stability_ari: float = 1.0
        self.user_cluster: Dict[str, int] = {}
        self.centroids: List[List[float]] = []
        self.mins: List[float] = []
        self.maxs: List[float] = []
        self.info: Dict[int, ClusterInfo] = {}
        # (cluster|None, franja|None) -> conteo de productos / categorias
        self._prod: Dict[tuple, Counter] = {}
        self._cat: Dict[tuple, Counter] = {}
        self._catalog: Dict[str, Product] = {}

    # --------------------------------------------------------------- entrenamiento
    @classmethod
    def fit(
        cls,
        user_lines: Dict[str, List[OrderItem]],
        user_groups: Dict[str, List[Order]],
        catalog: Dict[str, Product],
        k: Optional[int] = None,
        k_range: Tuple[int, int] = (2, 6),
        seed: int = 7,
    ) -> "UserClusterModel":
        m = cls()
        m._catalog = catalog
        users = sorted(u for u, ls in user_lines.items() if ls)
        raw = [user_features(user_lines[u], user_groups.get(u, [])) for u in users]
        if not users:
            m._count(user_lines, user_groups)
            return m
        m.mins = [min(col) for col in zip(*raw)]
        m.maxs = [max(col) for col in zip(*raw)]
        pts = [m.normalize(v) for v in raw]

        if len(users) < 3:
            k = 1
        if k is None:
            hi = min(k_range[1], len(users) - 1)
            for kk in range(k_range[0], hi + 1):
                _, labs, _ = kmeans(pts, kk, seed)
                m.silhouette_by_k[kk] = round(silhouette(pts, labs), 4)
            k = max(m.silhouette_by_k, key=lambda x: (m.silhouette_by_k[x], -x), default=1)
        m.k = k
        centroids, labels, _ = kmeans(pts, k, seed) if k > 1 else ([[sum(c) / len(c) for c in zip(*pts)]], [0] * len(pts), 0.0)
        m.centroids = centroids
        m.silhouette = round(silhouette(pts, labels), 4) if k > 1 else 0.0
        if k > 1 and len(pts) >= k + 1:
            stability = []
            for alt_seed in (17, 29, 43):
                _, alt_labels, _ = kmeans(pts, k, alt_seed)
                stability.append(adjusted_rand_index(labels, alt_labels))
            m.stability_ari = round(sum(stability) / len(stability), 4)
        m.user_cluster = dict(zip(users, labels))
        m._count(user_lines, user_groups)
        m._describe(users, raw, labels)
        return m

    def normalize(self, vec: Sequence[float]) -> List[float]:
        return [
            (v - lo) / (hi - lo) if hi > lo else 0.0
            for v, lo, hi in zip(vec, self.mins, self.maxs)
        ]

    def _count(self, user_lines: Dict[str, List[OrderItem]], user_groups: Dict[str, List[Order]]) -> None:
        for uid, lines in user_lines.items():
            cid = self.user_cluster.get(uid)
            for ln in lines:
                try:
                    dt = datetime.strptime(ln.timestamp, "%Y-%m-%d %H:%M:%S")
                    slot = parse_time_slot(dt.hour, dt.minute)
                except ValueError:
                    continue
                for c in ({cid, None} if cid is not None else {None}):
                    for s in {slot, None}:
                        self._prod.setdefault((c, s), Counter())[ln.product_id] += 1
                        self._cat.setdefault((c, s), Counter())[ln.category.value] += 1

    def _describe(self, users: List[str], raw: List[List[float]], labels: List[int]) -> None:
        for cid in sorted(set(labels)):
            member_idx = [i for i, lab in enumerate(labels) if lab == cid]
            mean = [sum(raw[i][j] for i in member_idx) / len(member_idx) for j in range(len(FEATURE_NAMES))]
            feats = dict(zip(FEATURE_NAMES, mean))
            slot = max(SLOTS, key=lambda s: feats[f"franja_{s}"])
            cat = max(CATEGORIES, key=lambda c: feats[f"cat_{c}"])
            top = [
                self._catalog[pid].name if pid in self._catalog else pid
                for pid, _ in self._prod.get((cid, None), Counter()).most_common(3)
            ]
            self.info[cid] = ClusterInfo(
                cluster_id=cid,
                label=f"{SLOT_LABEL[slot]} · {cat.title()}",
                users=[users[i] for i in member_idx],
                top_products=top,
                mean_features=feats,
            )

    # --------------------------------------------------------------- uso
    def cluster_of(self, user_id: str) -> Optional[int]:
        return self.user_cluster.get(user_id)

    def assign(self, lines: Sequence[OrderItem], groups: Sequence[Order]) -> Optional[int]:
        """Cluster mas cercano para un usuario que no estaba en el entrenamiento."""
        if not self.centroids or not lines:
            return None
        v = self.normalize(user_features(lines, groups))
        return min(range(len(self.centroids)), key=lambda c: _dist2(v, self.centroids[c]))

    def _key(self, cluster_id: Optional[int], slot: Optional[str]) -> tuple:
        """Mejor nivel de detalle con datos suficientes: cluster+franja -> cluster ->
        todos los usuarios+franja -> todos."""
        options = []
        if cluster_id is not None:
            options += [(cluster_id, slot), (cluster_id, None)]
        options += [(None, slot), (None, None)]
        for key in options:
            if sum(self._prod.get(key, Counter()).values()) >= MIN_LINES_FOR_KEY:
                return key
        return (None, None)

    def affinity(self, cluster_id: Optional[int], slot: str, product: Product) -> float:
        """Afinidad en [0, 1] de un producto para gente parecida, a esa hora."""
        key = self._key(cluster_id, slot)
        prods, cats = self._prod.get(key, Counter()), self._cat.get(key, Counter())
        if not prods:
            return 0.5
        p = prods.get(product.id, 0) / max(prods.values())
        c = cats.get(product.category.value, 0) / max(cats.values())
        return 0.7 * p + 0.3 * c

    def summary(self) -> str:
        lines = [f"k = {self.k} clusters (silueta = {self.silhouette})"]
        for cid, info in self.info.items():
            lines.append(
                f"  Cluster {cid} [{info.label}] {len(info.users)} usuarios | "
                f"top: {', '.join(info.top_products)}"
            )
        return "\n".join(lines)
