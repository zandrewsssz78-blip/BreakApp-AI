# Diagnóstico técnico de Silhouette y Calibración — BREAK AI

Fecha de ejecución: 2026-11-07  
Corte temporal reproducible: `2026-11-06 20:47:23`

## 1. Resumen ejecutivo

Con el conjunto de 130 usuarios (30 originales y 100 sintéticos con frecuencias variables entre 2 y 13 pedidos) y 1.960 líneas previas al corte `2026-11-06 20:47:23`:

- El vector de **10 características** (horarios, categorías, precio unitario promedio y tamaño de canasta) alcanza un coeficiente de Silhouette de **0.3886** ($K=3$, estabilidad $\text{ARI} = 1.0000$).
- En la partición temporal 80/20 de evaluación (`cutoff = 2026-10-19 12:35:50`), K-Means mantiene $K=3$ con Silhouette **0.3873** y estabilidad $\text{ARI} = 1.0000$.
- Las variables `frecuencia_pedidos_semana` y `diversidad_categorias` se conservan como descriptores analíticos fuera de la distancia euclidiana para evitar degradar la separación geométrica de los grupos.

## 2. Resultados por número de clusters ($K$)

| $K$ | Silhouette (Entrenamiento) | Silhouette (Split 80/20 Evaluación) |
|---:|---:|---:|
| 2 | 0.2887 | 0.2847 |
| **3** | **0.3886** | **0.3873** |
| 4 | 0.3362 | 0.3392 |
| 5 | 0.2953 | 0.2985 |
| 6 | 0.2915 | 0.3008 |

## 3. Desempeño escalonado del recomendador (Split temporal 80/20)

| Modelo | Precision@5 | Recall@5 | NDCG@5 | Hit Rate@5 | MAP@5 | Latencia media (ms) |
|---|---:|---:|---:|---:|---:|---:|
| `baseline_global` | 0.0532 | 0.1712 | 0.1041 | 0.2658 | 0.0678 | 0.001 |
| `baseline_slot` | 0.0751 | 0.2264 | 0.1668 | 0.3207 | 0.1247 | 0.001 |
| `cold_start` | 0.0641 | 0.1899 | 0.1305 | 0.2996 | 0.0909 | 2.398 |
| `rules_only` | 0.1418 | 0.4575 | 0.3420 | 0.6076 | 0.2715 | 10.963 |
| `rules_clusters` | 0.1443 | 0.4648 | 0.3447 | 0.6118 | 0.2730 | 15.056 |
| `hybrid_clusters` | **0.1511** | **0.4930** | **0.3726** | **0.6329** | **0.2988** | **19.467** |
