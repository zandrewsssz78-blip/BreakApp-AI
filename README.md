# BreakApp-AI: Agente Racional para la Recomendación Contextual y Optimización de Pedidos en Cafeterías Universitarias

> **Asignatura:** Inteligencia Artificial (2026-2S)  
> **Universidad:** Universidad de Bogotá Jorge Tadeo Lozano (Utadeo)  
> **Conexión Interdisciplinar:** Proyecto articulado con la materia de **Aplicaciones Móviles (BreakApp)**.

---

## 1. Visión General del Proyecto

En el campus universitario, los estudiantes y docentes cuentan con descansos breves (*breaks*) de 15 a 30 minutos entre clases. La adquisición de alimentos en cafeterías como *Catering Gourmet*, *Punto Verde* y *Central Food* enfrenta fricción por menús estáticos, congestión en horas pico y falta de personalización según horarios, presupuestos y restricciones dietéticas (alergias, lactosa, opciones veganas).

**BreakApp-AI** es un agente inteligente desacoplado que actúa como el cerebro predictivo de la aplicación móvil **BreakApp**. En lugar de requerir que el usuario navegue pasivamente decenas de opciones, el agente percibe el contexto temporal (hora del receso, día de la semana), el perfil transaccional del usuario y las restricciones declaradas para sugerir de forma proactiva:
1. **Top-$K$ Productos de Máxima Utilidad:** Ordenados según congruencia horaria y preferencias.
2. **Sugerencias de Maridaje / Combos Óptimos:** Emparejamiento con categorías complementarias (ej. Almuerzo + Bebida natural o Café + Croissant).
3. **Banners Contextuales Proactivos:** Mensajes personalizados en la interfaz móvil (ej. *"¿Listo para tu café matutino? Prueba hoy nuestro Capuchino con Croissant"*).

---

## 2. Formulación y Especificación PEAS del Agente

El agente inteligente está formulado bajo el paradigma formal de agentes racionales (Russell & Norvig), delimitado según sus cuatro dimensiones fundamentales:

| Dimensión PEAS | Descripción en BreakApp-AI |
| :--- | :--- |
| **Rendimiento (Performance)** | Función de utilidad multicriterio $U(u, p, t) = w_1 S_{\mathrm{content}} + w_2 S_{\mathrm{temporal}} + w_3 S_{\mathrm{budget}} + w_4 S_{\mathrm{rating}} - \lambda P_{\mathrm{alergias}}$, que maximiza la afinidad por categoría y tags, la coherencia de horario (mañana vs. almuerzo vs. tarde), la proximidad al presupuesto y penaliza con costo estricto ($\lambda \gg 0$) alérgenos o ingredientes no deseados. |
| **Entorno (Environment)** | Ecosistema de cafeterías de campus (*Catering Gourmet*, *Punto Verde*, *Central Food*), catálogo activo de 23 productos distribuidos en 4 categorías canónicas (`ALMUERZOS`, `SNACKS`, `BEBIDAS`, `POSTRES`), y la comunidad universitaria modelada por perfiles heterogéneos. |
| **Actuadores (Actuators)** | Generador de payload estructurado JSON para consumo en la API móvil de BreakApp: vector de recomendaciones Top-$K$, sugerencia de combo con descuento (`pairing_ids`) y banner generativo contextual. |
| **Sensores (Sensors)** | Ingesta de registros históricos de transacciones (`order_history.csv`), catálogo enriquecido (`products_catalog.csv`), reloj del sistema (hora y día de la semana) y notas de texto libre (`notes`). |

### Ciclo Percepción – Decisión – Acción
El agente opera en 5 etapas secuenciales:
1. **Percibir:** Captura el identificador del usuario, el instante temporal ($t$) y el estado del catálogo.
2. **Filtrar:** Aplica filtros duros de restricciones dietéticas (ej. "Sin cebolla", "Deslactosada") y disponibilidad.
3. **Evaluar Utilidad:** Computa la función $U(u, p, t)$ para todos los productos candidatos.
4. **Decidir:** Ordena y selecciona el Top-$K$ de mayor utilidad junto a su maridaje óptimo.
5. **Actuar:** Retorna la respuesta estructurada para renderizado en la interfaz móvil.

---

## 3. Estructura del Repositorio

```text
break-ia/
├── data/
│   ├── raw/
│   │   ├── breakapp_synthetic_dataset.json  # Dataset maestro unificado
│   │   ├── order_history.csv                # 168 pedidos simulados con timestamps, ratings y notes
│   │   └── products_catalog.csv             # 23 productos enriquecidos con tags y pairing_ids
│   └── processed/                           # Features y matrices procesadas
├── docs/
│   ├── 01-entrega_propuesta/                # Entrega 1: Propuesta formal
│   │   ├── main.tex
│   │   ├── referencias.bib
│   │   ├── Makefile
│   │   └── img/LogoUtadeo.svg
│   └── 02-avance_proyecto/                  # Entrega 2: Formulación como Agente Inteligente (PEAS)
│       ├── main.tex
│       ├── referencias.bib
│       ├── Makefile
│       └── img/LogoUtadeo.svg
├── notebooks/
│   ├── 01_exploracion_datos.py              # Análisis exploratorio y resumen de patrones de consumo
│   └── 02_calibracion_agente.py             # Validación de inferencia para los 5 arquetipos
├── src/
│   └── break_ia/
│       ├── __init__.py
│       ├── models.py                        # Entidades del dominio (Product, Order, UserProfile)
│       ├── data_loader.py                   # Ingesta y parseo de catálogo e historial
│       ├── utility.py                       # Formulación matemática de la función de utilidad
│       └── agent.py                         # Implementación del agente racional BreakAgent
├── pyproject.toml                           # Gestión moderna de dependencias con uv
└── README.md
```

---

## 4. Arquetipos de Usuario y Validación de Inferencia

El agente fue evaluado contra los 5 arquetipos representativos de la comunidad universitaria:

1. **`usr_estudiante_01` (Estudiante Mañanero / Cafetero):**
   - *Horario:* 08:10 - 08:30 AM (Lunes, Miércoles, Viernes). Presupuesto: \$4.500 - \$9.500 COP.
   - *Pista en notas:* "Leche deslactosada, sin azúcar, fan del Capuchino".
   - *Acción del Agente a las 8:20 AM:* Capuchino o Mocaccino con Croissant / Galleta de Avena en *Catering Gourmet*.
2. **`usr_estudiante_02` (Almuerzo Ejecutivo + Viernes de Gusto):**
   - *Horario:* 12:30 - 01:00 PM (Lunes a Viernes). Presupuesto: \$15.000 - \$28.500 COP.
   - *Pista en notas:* Rechazo a la cebolla ("Sin cebolla"). Los viernes acostumbra postre.
   - *Acción del Agente:* Lun-Jue sugiere Almuerzo Ejecutivo + Jugo natural; Viernes sugiere Hamburguesa Artesanal + Brownie con Helado en *Central Food*.
3. **`usr_estudiante_03` (Fitness / Saludable / Vegetariano):**
   - *Horario:* 10:30 AM y 01:15 PM. Presupuesto: \$12.500 - \$31.500 COP.
   - *Pista en notas:* Leche de almendras, sin aderezos pesados, extra aguacate.
   - *Acción del Agente a la 1:00 PM:* Bowl Quinoa y Pollo o Bowl Falafel Vegano en *Punto Verde* + Té Matcha Frío o Trufa Vegana.
4. **`usr_estudiante_04` (Estudiante Tarde / Tardes de Código):**
   - *Horario:* 03:15 - 04:50 PM. Presupuesto: \$8.200 - \$23.000 COP.
   - *Pista en notas:* Compra de a 2 unidades para compartir, salsa de ajo.
   - *Acción del Agente a las 3:30 PM:* Combo 2x Empanadas Horneadas o Palitos de Queso + Gaseosa o Mocaccino.
5. **`usr_docente_05` (Docente Gourmet / Compras Grupales):**
   - *Horario:* 09:45 AM y 12:30 PM (Martes, Miércoles, Jueves). Presupuesto: \$23.000 - \$34.000 COP.
   - *Pista en notas:* Leche de almendras, poco picante, baja en azúcar.
   - *Acción del Agente:* Desayuno gourmet (2 Capuchinos + 2 Croissants) o Almuerzo + Limonada de Coco y Cheesecake de Frutos Rojos.

---

## 5. Independencia respecto a la Aplicación Móvil

Para preservar la integridad del proyecto móvil (**BreakApp** en Android Studio):
- No se modificó ningún archivo del proyecto Android original (`break-app-copy`).
- Este proyecto de Inteligencia Artificial opera como un subsistema de toma de decisiones autónomo.
- La futura integración entre ambos componentes se realiza mediante una interfaz de contratos JSON limpia (API REST o exportación local), donde BreakApp envía el identificador y la hora, y el agente responde con el vector de recomendaciones.
