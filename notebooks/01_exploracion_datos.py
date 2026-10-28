import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    import polars as pl
    import json
    from pathlib import Path
    return pl, json, Path


@app.cell
def _(Path, pl):
    # Carga de catálogo de productos
    catalog_path = Path("../data/raw/products_catalog.csv")
    df_catalog = pl.read_csv(catalog_path)
    print("Dimensiones del catálogo:", df_catalog.shape)
    df_catalog.head(10)
    return catalog_path, df_catalog


@app.cell
def _(Path, pl):
    # Carga de historial de pedidos sintéticos
    orders_path = Path("../data/raw/order_history.csv")
    df_orders = pl.read_csv(orders_path)
    print("Dimensiones de pedidos:", df_orders.shape)
    df_orders.head(10)
    return orders_path, df_orders


@app.cell
def _(df_orders, pl):
    # Resumen de consumo por categoría
    summary = (
        df_orders.group_by("category")
        .agg([
            pl.col("quantity").sum().alias("unidades_vendidas"),
            pl.len().alias("frecuencia_lineas"),
            pl.col("price_cop").sum().alias("ingresos_totales_cop"),
        ])
        .sort("ingresos_totales_cop", descending=True)
    )
    summary
    return (summary,)


@app.cell
def _(df_orders, pl):
    # Análisis de consumo por usuario y días
    user_summary = (
        df_orders.group_by(["user_id", "day_of_week"])
        .agg([
            pl.len().alias("total_pedidos"),
            pl.col("price_cop").mean().round(0).alias("gasto_promedio_cop")
        ])
        .sort(["user_id", "day_of_week"])
    )
    user_summary
    return (user_summary,)


if __name__ == "__main__":
    app.run()
