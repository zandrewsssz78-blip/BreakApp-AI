# Informe técnico – BREAK IA Fase 2

## Resumen ejecutivo

Se trabajó sobre el repositorio Fase 1, conservando la interfaz de inferencia local y los datos existentes. Se añadieron señales colaborativas usuario-usuario y producto-producto, afinidad por contenido y producto por franja, popularidad contextual, explicaciones de recomendación, auditoría de datos, incorporación validada de pedidos y evaluación ampliada con *baselines* estáticos y simulación *cold-start*.

No se implementó API, Firebase ni Android.

## 1. Auditoría de la base

| Indicador | Total | Bloque original/no sintético | Sintético |
|---|---:|---:|---:|
| Líneas | 2.152 | 1.120 | 1.032 |
| Usuarios | 130 | 30 | 100 |
| Pedidos | 1.277 | 563 | 714 |
| Líneas promedio por usuario | 16,55 | 37,33 | 10,32 |
| Mediana de líneas por usuario | 12,0 | 19,0 | 9,0 |
| Pedidos promedio por usuario | 9,82 | 18,77 | 7,14 |
| Rango de pedidos por usuario | 2–76 | 6–76 | 2–13 |
| Precio unitario promedio | $6.265,38 | $6.735,89 | $5.754,75 |
| Precio unitario mediano | $4.500 | $5.000 | $4.200 |

Distribución de categorías:

| Categoría | Total | Original/no sintético | Sintético |
|---|---:|---:|---:|
| Bebidas | 861 | 452 | 409 |
| Snacks | 584 | 283 | 301 |
| Almuerzos | 370 | 223 | 147 |
| Postres | 337 | 162 | 175 |

**Interpretación:** el bloque sintético aumenta la cantidad de perfiles (100 nuevos usuarios `usr_sintetico_*`) con frecuencia variable (34 frecuentes, 44 regulares y 22 ocasionales) y canastas de 1 a 3 productos vinculadas a acompañamientos del catálogo (`pairing_ids`). El script `audit_dataset.py` produce el detalle reproducible en `data/reports/data_audit.json`.

### Control de corte temporal

El bloque original contiene fechas posteriores al 6 de noviembre de 2026. Por ello, `train_agent.py` y `evaluate_agent.py` excluyen cualquier registro posterior al corte `--as-of`. Con el corte reproducible `2026-11-06 20:47:23`, el entrenamiento utiliza **1.960 líneas** y **1.183 pedidos** válidos de los 130 usuarios.

## 2. Arquitectura del recomendador híbrido

El agente combina la función de utilidad multicriterio con una capa colaborativa y de contenido precalculada:

1. **User-user CF (35 %):** similitud coseno entre vectores usuario-producto ponderada por la intensidad de compra del vecino en los 20 vecinos más cercanos.
2. **Item-item CF (20 %):** coocurrencia de productos dentro de una misma orden (`order_id`).
3. **Content-based por franja (30 %):** afinidad histórica hacia el producto en la franja horaria, su categoría y sus etiquetas (`tags`).
4. **Popularidad contextual (15 %):** popularidad en la franja horaria con respaldo global.
5. **Agente de utilidad + clusters:** prioriza el historial del usuario en la misma franja (`MIN_SLOT_ORDERS = 2`, refuerzo de franja `2,5x` y de día `2,0x`) y aplica un peso adaptativo de cluster (`0,015` a `0,24`) según cuántos pedidos previos tenga el usuario en ese horario.

La combinación final pondera de forma adaptativa el puntaje de reglas y el puntaje híbrido (`0,72 / 0,28` para usuarios con 3+ líneas; `0,60 / 0,40` con 1–2 líneas; `0,15 / 0,85` en arranque en frío).

## 3. Clustering

Con el vector optimizado de 10 características (4 proporciones de franja horaria, 4 proporciones de categoría, precio unitario medio y productos por orden) y corte `2026-11-06 20:47:23`:

- **Algoritmo seleccionado:** K-Means ($k=3$).
- **Silhouette en entrenamiento:** **0,3886** ($k=2$: 0,2887; $k=3$: **0,3886**; $k=4$: 0,3362; $k=5$: 0,2953; $k=6$: 0,2915).
- **Estabilidad ARI:** **1,0000** entre semillas alternativas.
- **Silhouette en partición temporal de evaluación (80/20):** **0,3873** con estabilidad ARI **1,0000** y tamaños balanceados de 54, 48 y 26 usuarios.

Comparación diagnóstica (`compare_clustering.py`):

| Algoritmo | Silhouette | Distribución / observación |
|---|---:|---|
| **K-Means (k=3)** | **0,3886** | 26 / 53 / 51; cobertura total y asignación por centroides |
| K-Medoids (k=3) | 0,3877 | 52 / 25 / 53 |
| Jerárquico promedio (k=3) | 0,3384 | 64 / 21 / 45 |
| DBSCAN | 0,4918* | 6 grupos; excluye 62 de 130 usuarios como ruido |

*La silueta de DBSCAN se calcula solo sobre los 68 usuarios sin ruido; por su baja cobertura no se utiliza en producción.

## 4. Evaluación temporal del recomendador

Con corte `--as-of "2026-11-06 20:47:23"`, se evalúan los 1.183 pedidos previos mediante división temporal estricta 80/20 en `2026-10-19 12:35:50` (946 pedidos de entrenamiento y 237 de prueba):

| Métrica | Baseline global | Baseline franja | Cold-start | Reglas | Reglas + clusters | Híbrido + clusters |
|---|---:|---:|---:|---:|---:|---:|
| Precision@5 | 0,0532 | 0,0751 | 0,0641 | 0,1418 | 0,1443 | **0,1511** |
| Recall@5 | 0,1712 | 0,2264 | 0,1899 | 0,4575 | 0,4648 | **0,4930** |
| NDCG@5 | 0,1041 | 0,1668 | 0,1305 | 0,3420 | 0,3447 | **0,3726** |
| Hit Rate@5 | 0,2658 | 0,3207 | 0,2996 | 0,6076 | 0,6118 | **0,6329** |
| MAP@5 | 0,0678 | 0,1247 | 0,0909 | 0,2715 | 0,2730 | **0,2988** |
| Latencia media (ms) | 0,001 | 0,001 | 2,398 | 10,963 | 15,056 | **19,467** |
| Latencia p95 (ms) | 0,001 | 0,002 | 2,857 | 37,843 | 48,847 | **55,931** |

**Lectura de resultados:**
1. El agente **Híbrido + Clusters** alcanza el mejor desempeño en todas las métricas de calidad (`Hit Rate@5 = 63,29 %`, `Recall@5 = 49,30 %`, `NDCG@5 = 0,3726`, `MAP@5 = 0,2988`), superando en **+31,2 puntos porcentuales** de Hit Rate al baseline por franja horaria (`32,07 %`) y en **+36,7 puntos** al baseline global (`26,58 %`).
2. La incorporación de **Clusters K-Means** sobre las reglas (`rules_clusters`) mejora Precision, Recall, NDCG, Hit Rate (`61,18 %` vs `60,76 %`) y MAP al respaldar a los usuarios cuando compran en una franja horaria con poco historial propio.
3. El pre-cálculo de vecindarios colaborativos y el parseo directo de franjas horarias redujeron la latencia media del modelo híbrido a **19,47 ms**, cumpliendo holgadamente la restricción de tiempo real (< 50 ms).

## 5. Aprendizaje por lotes y pruebas

- `ingest_orders.py` valida esquema, catálogo, precios, cantidades y colisiones antes de respaldar en `data/backups/` y actualizar el historial maestro.
- `pytest -q` ejecuta y aprueba las **6 pruebas automatizadas** de integridad de datos, inferencia, explicaciones híbridas, corte temporal, derivación de perfil y asignación de clusters en arranque en frío.
