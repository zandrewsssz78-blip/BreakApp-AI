# BREAK – Agente híbrido de recomendaciones (Fase 2)

Proyecto Python local para analizar hábitos de compra y generar recomendaciones personalizadas para cafeterías universitarias. Se conserva la arquitectura y la CLI de la Fase 1, e **incorpora un servidor REST API HTTP (`server.py`) con biblioteca estándar para su integración directa con la aplicación móvil Android ([break-app-copy](https://github.com/pepitaemy3535/break-app-copy))**.

## Estado de los datos

| Recurso | Total | Base original | Bloque sintético |
|---|---:|---:|---:|
| Líneas de pedidos | 2.152 | 1.120 | 1.032 |
| Usuarios | 130 | 30 | 100 |
| Pedidos (`order_id`) | 1.277 | 563 | 714 |
| Productos | 87 | 87 | — |

El generador crea 100 perfiles con entre 2 y 13 pedidos por usuario, frecuencias ocasionales/regulares/frecuentes, preferencias habituales por segmento y canastas variables de 1 a 3 productos con maridajes coherentes (`pairing_ids`). Los registros sintéticos se identifican por `usr_sintetico_*` y `SYN_*`. La base original se conserva adicionalmente en `data/original/`. No se afirma que los datos originales representen transacciones reales: el repositorio no acredita su procedencia externa. Los datos sintéticos sirven para desarrollo y pruebas, no para probar demanda real.

### Auditoría inicial

Ejecuta:

```bash
python scripts/audit_dataset.py
```

Genera `data/reports/data_audit.json` con comparación de líneas, usuarios, pedidos, categorías, precios y fechas. En esta versión, la media de líneas por usuario es 37,33 en el bloque original y 10,32 en el sintético. El promedio de pedidos por usuario es 18,77 en el original y 7,14 en el sintético; los usuarios sintéticos varían entre 2 y 13 pedidos. La auditoría también muestra que la base original llega a 76 pedidos para un usuario, por lo que la frecuencia original está muy concentrada en algunos perfiles.

**Advertencia temporal:** el bloque original contiene marcas de tiempo posteriores al 6 de noviembre de 2026. El entrenamiento normal excluye automáticamente las filas posteriores a la fecha/hora de ejecución. Para reproducir un corte se puede indicar `--as-of`. La evaluación temporal utiliza su propio corte histórico.

## Arquitectura incorporada

- `agent.py`: conserva el ciclo percibir-filtrar-evaluar-decidir con ponderación adaptativa entre reglas y señales colaborativas según la longitud del historial del usuario.
- `hybrid.py`: señales user-user (con vecindarios precalculados e intensidad de compra), item-item (coocurrencia en una misma orden), contenido (categoría, etiquetas y afinidad de producto por franja) y popularidad contextual.
- `clustering.py`: K-Means con selección de k por silueta, estabilidad ARI y 10 características de horario, categoría, precio y tamaño de canasta. La frecuencia semanal y diversidad se conservan como descriptores para análisis, pero no ponderan distancias.
- `compare_clustering.py`: benchmark diagnóstico de K-Means, K-Medoids, jerárquico y DBSCAN con las mismas variables.
- `utility.py`: reglas de contexto, presupuesto, historial priorizado por franja horaria (`MIN_SLOT_ORDERS = 2`) y respaldo adaptativo de cluster.
- `data_loader.py`: carga de catálogo e historial.
- `models.py`: entidades y explicaciones de recomendaciones.

### Mezcla híbrida

Con historial disponible, el componente colaborativo combina:
- 35 % similitud usuario-usuario ponderada por frecuencia de compra.
- 20 % relación producto-producto por coocurrencia en una misma orden.
- 30 % afinidad de contenido (producto en franja, categoría y etiquetas).
- 15 % popularidad de la franja horaria.

La puntuación final combina de forma adaptativa el agente base y la señal híbrida (`72 % / 28 %` con 3 o más compras previas; `60 % / 40 %` con 1–2 compras; `15 % / 85 %` en arranque en frío sin historial). Los usuarios sin arquetipo registrado reciben un perfil derivado de su historial. Las señales colaborativas usan decaimiento temporal exponencial de 120 días y estructuras precalculadas al crear el agente.

### Clustering

K-Means se conserva por su equilibrio entre silueta (`0,3886` en entrenamiento y `0,3873` en el corte de evaluación, con `k=3`), cobertura completa de los 130 usuarios, estabilidad `ARI = 1,0000` y asignación inmediata de nuevos usuarios por centroides. Ejecuta `python scripts/compare_clustering.py --as-of "2026-11-06 20:47:23"` para comparar métodos sobre las mismas 10 variables de producción.

## Instalación en Windows / Visual Studio Code

Requiere Python 3.11 o superior.

```powershell
# Abrir terminal en la carpeta del proyecto
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Si PowerShell bloquea la activación, ejecutar en esa terminal:
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

## Flujo de uso

### 1. Auditar datos

```powershell
python scripts/audit_dataset.py
```

### 2. Entrenar el agente

```powershell
python scripts/train_agent.py --as-of "2026-11-06 20:47:23"
```

Genera `data/models/break_agent.pkl` y `data/models/break_agent.json`.

### 3. Generar recomendaciones

```powershell
python scripts/recommend.py --user usr_estudiante_01 --when "2026-11-09 08:20:00" -k 5
python scripts/recommend.py --user usr_sintetico_040 --when "2026-11-09 15:20:00" -k 5
python scripts/recommend.py --user usuario_nuevo_sin_historial --when "2026-11-09 12:20:00" -k 5
```

### 4. Evaluar

```powershell
python scripts/evaluate_agent.py --as-of "2026-11-06 20:47:23"
```

La evaluación descarta pedidos posteriores al corte `--as-of`, usa división temporal 80/20 (946 pedidos de entrenamiento y 237 de prueba antes del corte `2026-10-19 12:35:50`) y compara dos *baselines* de popularidad estática (`baseline_global` y `baseline_slot`), el escenario `cold_start`, `rules_only`, `rules_clusters` y `hybrid_clusters`.

### 5. Ejecutar pruebas

```powershell
pytest -q
```

La ejecución validada de esta entrega finalizó con **6 pruebas aprobadas**.

### 6. Incorporar pedidos nuevos

```powershell
python scripts/ingest_orders.py --input "C:\ruta\pedidos_nuevos.csv" --retrain
```

## Evaluación observada

La ejecución reproducible con corte `--as-of "2026-11-06 20:47:23"` (1.183 pedidos anteriores a esa fecha; split temporal 80/20 con 946 de entrenamiento y 237 de prueba) obtuvo:

| Métrica | Baseline global | Baseline por franja | Cold-start | Solo reglas | Reglas + clusters | Híbrido + clusters |
|---|---:|---:|---:|---:|---:|---:|
| Precision@5 | 0,0532 | 0,0751 | 0,0641 | 0,1418 | 0,1443 | **0,1511** |
| Recall@5 | 0,1712 | 0,2264 | 0,1899 | 0,4575 | 0,4648 | **0,4930** |
| NDCG@5 | 0,1041 | 0,1668 | 0,1305 | 0,3420 | 0,3447 | **0,3726** |
| Hit Rate@5 | 0,2658 | 0,3207 | 0,2996 | 0,6076 | 0,6118 | **0,6329** |
| MAP@5 | 0,0678 | 0,1247 | 0,0909 | 0,2715 | 0,2730 | **0,2988** |
| Latencia media | 0,001 ms | 0,001 ms | 2,398 ms | 10,963 ms | 15,056 ms | **19,467 ms** |
| Latencia p95 | 0,001 ms | 0,002 ms | 2,857 ms | 37,843 ms | 48,847 ms | **55,931 ms** |

Se observa una progresión consistente en todas las métricas de ranking desde los *baselines* estáticos (`Hit Rate@5 = 26,58 %` global y `32,07 %` por franja), pasando por el modelo basado solo en reglas (`60,76 %`), reglas con respaldo de clustering K-Means (`61,18 %`) hasta el recomendador **Híbrido + Clusters (`63,29 %` en Hit Rate@5 y `49,30 %` en Recall@5)**, manteniendo una latencia media de inferencia de **19,5 ms** (< 50 ms).

## Servidor REST API e Integración Móvil (Break-app)

El repositorio incluye un microservicio HTTP nativo (`server.py`) sin dependencias externas adicionales que expone el modelo entrenado (`data/models/break_agent.pkl`) para ser consumido desde la aplicación móvil Android en Kotlin/Jetpack Compose (`https://github.com/pepitaemy3535/break-app-copy`).

### Arranque rápido del servidor

- **Doble clic en Windows:** ejecuta `run_server.bat` o `run_server.ps1`.
- **Por consola:**
  ```powershell
  python server.py 8000
  ```

El servidor escucha en `http://0.0.0.0:8000` (y desde el emulador de Android Studio en `http://10.0.2.2:8000`).

### Endpoints disponibles

1. **`GET /api/health`**: verifica el estado en línea del servicio y la versión del modelo híbrido.
2. **`POST /api/chat`**: procesa consultas en lenguaje natural desde el chat de la app (`prompt`, `userId`), detecta intención horaria y presupuesto, y responde con texto formateado, productos estructurados y combo sugerido.
   ```json
   {
     "prompt": "¿Qué me recomiendas para el almuerzo con menos de 15000?",
     "userId": "usr_estudiante_01"
   }
   ```
3. **`POST /api/recommend`**: devuelve directamente el top-k de recomendaciones estructuradas para un `user_id` y marca temporal `when`.

## Alcance y limitaciones

- Se conserva el proyecto y sus scripts; no se inicia un repositorio desde cero.
- Los eventos sintéticos se identifican explícitamente (`usr_sintetico_*`, `SYN_*`) y no se presentan como compras reales.
- No hay campos normalizados de ingredientes/alérgenos; no se pueden garantizar restricciones dietarias.
- La actualización de modelos es por lotes; no es aprendizaje incremental online.
- La exposición del modelo hacia el cliente móvil se realiza mediante el servidor REST API (`server.py`); la persistencia en Firebase y la experiencia offline/online (*Dual-Engine*) residen en la app móvil (`break-app-copy`).

## Informe técnico

Consulta `docs/INFORME_FASE2.md` y `docs/DIAGNOSTICO_SILHOUETTE.md` para el diagnóstico completo, metodología, resultados y conclusiones de la Fase 2.
