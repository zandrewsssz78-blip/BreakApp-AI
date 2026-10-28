import marimo

__generated_with = "0.17.6"
app = marimo.App(width="medium")


@app.cell(hide_code=True)
def _():
    from datetime import datetime
    from pathlib import Path
    import sys
    sys.path.append(str(Path("../src").resolve()))
    from break_ia.agent import BreakAgent
    return BreakAgent, Path, datetime, sys


@app.cell
def _(BreakAgent, Path):
    # Inicialización del agente racional
    data_dir = Path("../data/raw")
    agent = BreakAgent(data_dir)
    print("Agente Break-Recommender inicializado con catálogo de", len(agent.catalog), "productos.")
    return agent, data_dir


@app.cell
def _(agent, datetime):
    # Simulación de inferencia para Usuario 1: Estudiante Mañanero a las 8:20 AM
    res_u1 = agent.decide(
        user_id="usr_estudiante_01",
        dt=datetime(2026, 10, 28, 8, 20),
        day_of_week="Lunes",
        k=3
    )
    print("Banner:", res_u1.banner_message)
    print("Combo:", res_u1.suggested_combo)
    for i, rec in enumerate(res_u1.top_recommendations, 1):
        print(f"Top {i}: {rec.product.name} (Utilidad: {rec.utility_score})")
    return (res_u1,)


@app.cell
def _(agent, datetime):
    # Simulación de inferencia para Usuario 2: Viernes de gusto (Almuerzo + Postre) a las 12:45 PM
    res_u2 = agent.decide(
        user_id="usr_estudiante_02",
        dt=datetime(2026, 10, 30, 12, 45),
        day_of_week="Viernes",
        k=3
    )
    print("Banner:", res_u2.banner_message)
    print("Combo:", res_u2.suggested_combo)
    for i, rec in enumerate(res_u2.top_recommendations, 1):
        print(f"Top {i}: {rec.product.name} (Utilidad: {rec.utility_score})")
    return (res_u2,)


if __name__ == "__main__":
    app.run()
