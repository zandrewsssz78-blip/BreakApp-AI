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
    data_dir = Path("data/raw") if Path("data/raw").exists() else Path("../data/raw")
    catalog_path = data_dir / "products_catalog.csv"
    df_catalog = pl.read_csv(catalog_path)
    print("Dimensiones del catálogo:", df_catalog.shape)
    df_catalog.head(10)
    return catalog_path, df_catalog


@app.cell
def _(Path, pl):
    # Carga de historial de pedidos sintéticos
    orders_path = data_dir / "order_history.csv"
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
            pl.col("total_price").sum().alias("ingresos_totales_cop"),
        ])
        .sort("ingresos_totales_cop", descending=True)
    )
    summary
    return (summary,)


@app.cell
def _(df_orders, pl):
    # Una orden = todo lo que un usuario pidió en la misma hora (1 a 4 productos)
    df_ordenes = (
        df_orders.group_by("order_id")
        .agg([
            pl.col("user_id").first(),
            pl.col("timestamp").first(),
            pl.col("day_of_week").first(),
            pl.len().alias("n_productos"),
            pl.col("total_price").sum().alias("total_orden_cop"),
        ])
    )
    productos_por_orden = (
        df_ordenes.group_by("n_productos")
        .agg(pl.len().alias("ordenes"))
        .sort("n_productos")
    )
    print("Órdenes:", df_ordenes.height, "| Líneas de producto:", df_orders.height)
    productos_por_orden
    return df_ordenes, productos_por_orden


@app.cell
def _(df_ordenes, pl):
    # Órdenes a lo largo del día
    ordenes_por_hora = (
        df_ordenes.with_columns(
            pl.col("timestamp").str.slice(11, 2).cast(pl.Int32).alias("hora")
        )
        .group_by("hora")
        .agg(pl.len().alias("ordenes"))
        .sort("hora")
    )
    ordenes_por_hora
    return (ordenes_por_hora,)


@app.cell
def _(df_ordenes, pl):
    # Análisis de consumo por usuario y días (ahora por orden, no por línea)
    user_summary = (
        df_ordenes.group_by(["user_id", "day_of_week"])
        .agg([
            pl.len().alias("total_ordenes"),
            pl.col("total_orden_cop").mean().round(0).alias("gasto_promedio_orden_cop"),
        ])
        .sort(["user_id", "day_of_week"])
    )
    user_summary
    return (user_summary,)


if __name__ == "__main__":
    app.run()
