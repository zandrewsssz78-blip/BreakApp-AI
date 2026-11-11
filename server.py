"""Servidor REST API para BreakApp-AI.
Proporciona endpoints /api/chat y /api/recommend para conectar el Agente de IA con la app móvil.
Funciona sin dependencias externas obligatorias usando la biblioteca estándar de Python (http.server).
"""

import json
import pickle
import re
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "src"))

try:
    from break_ia.agent import BreakAgent
except ImportError:
    BreakAgent = None

AGENT_INSTANCE = None


def get_agent():
    """Carga el modelo serializado o inicializa una nueva instancia."""
    global AGENT_INSTANCE
    if AGENT_INSTANCE is not None:
        return AGENT_INSTANCE

    pkl_path = ROOT_DIR / "data" / "models" / "break_agent.pkl"
    if pkl_path.exists():
        try:
            with open(pkl_path, "rb") as f:
                AGENT_INSTANCE = pickle.load(f)
                print(f"[OK] Modelo cargado desde {pkl_path}")
                return AGENT_INSTANCE
        except Exception as e:
            print(f"[WARN] No se pudo cargar break_agent.pkl ({e}), instanciando agente...")

    if BreakAgent is not None:
        data_dir = ROOT_DIR / "data" / "raw"
        if not data_dir.exists():
            data_dir = ROOT_DIR / "data"
        AGENT_INSTANCE = BreakAgent(data_dir=data_dir, use_clusters=True, use_hybrid=True)
        print("[OK] Agente inicializado exitosamente en memoria.")
        return AGENT_INSTANCE

    return None


def parse_prompt_intent(prompt: str):
    """Analiza la intención del usuario a partir del texto ingresado."""
    p_lower = prompt.lower()
    now = datetime.now()

    # Detectar categoría sugerida o intención de horario
    intent = "general"
    simulated_hour = now.hour

    if any(k in p_lower for k in ["desayuno", "mañana", "café", "cafe", "tinto", "capuchino"]):
        intent = "desayuno"
        simulated_hour = 8
    elif any(k in p_lower for k in ["almuerzo", "almorzar", "hambre", "plato fuerte", "ejecutivo", "bandeja", "sopa"]):
        intent = "almuerzo"
        simulated_hour = 13
    elif any(k in p_lower for k in ["snack", "tarde", "onces", "receso", "algo rápido", "rapido"]):
        intent = "snack"
        simulated_hour = 16
    elif any(k in p_lower for k in ["dulce", "postre", "antojo", "helado", "dona"]):
        intent = "postre"
        simulated_hour = 16
    elif any(k in p_lower for k in ["cena", "noche", "salchipapa", "pizza", "hamburguesa"]):
        intent = "cena"
        simulated_hour = 19

    # Detección de presupuesto
    budget_limit = None
    match_price = re.search(r"(\d+)[.\s]*(k|mil|000)?", p_lower)
    if "menos de" in p_lower or "presupuesto" in p_lower or "económico" in p_lower or "barato" in p_lower:
        if match_price:
            val = int(match_price.group(1))
            if val < 100:
                val *= 1000
            budget_limit = val
        else:
            budget_limit = 10000

    target_dt = now.replace(hour=simulated_hour, minute=15, second=0)
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    day_of_week = dias_semana[target_dt.weekday()] if target_dt.weekday() < 5 else "Lunes"

    return {
        "intent": intent,
        "target_dt": target_dt,
        "day_of_week": day_of_week,
        "budget_limit": budget_limit,
    }


def format_currency(price: int) -> str:
    return f"${price:,.0f}".replace(",", ".")


class BreakAiHandler(BaseHTTPRequestHandler):
    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def do_OPTIONS(self):
        self.send_response(200)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path in ["/", "/api/health"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            resp = {
                "status": "online",
                "service": "BreakApp-AI Service",
                "version": "2.0",
                "model": "Hybrid Agent (Rules + K-Means + Collaborative Filtering)",
                "timestamp": datetime.now().isoformat(),
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0) or 0)
        post_data = self.rfile.read(content_length)

        try:
            body = json.loads(post_data.decode("utf-8")) if post_data else {}
        except Exception:
            body = {}

        if parsed.path == "/api/chat":
            self.handle_chat(body)
        elif parsed.path == "/api/recommend":
            self.handle_recommend(body)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_chat(self, body):
        prompt = body.get("prompt", "")
        user_id = body.get("userId", "usr_estudiante_01")

        parsed_intent = parse_prompt_intent(prompt)
        agent = get_agent()

        if agent is None:
            self.send_response(500)
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"response": "Error: El agente no se encuentra disponible."}')
            return

        dt = parsed_intent["target_dt"]
        dow = parsed_intent["day_of_week"]

        try:
            result = agent.decide(user_id=user_id, dt=dt, day_of_week=dow, k=5)
            recs = result.top_recommendations

            # Filtrar por presupuesto si el usuario lo especificó
            if parsed_intent["budget_limit"] is not None:
                budget = parsed_intent["budget_limit"]
                filtered = [r for r in recs if r.product.price <= budget]
                if filtered:
                    recs = filtered

            # Construir texto conversacional con formato rico
            frase_saludo = f"¡Hola! Según tus gustos y el horario de las {dt.strftime('%H:%M')}, "
            if parsed_intent["intent"] == "almuerzo":
                frase_saludo += "te tengo las mejores opciones para un almuerzo delicioso y rendidor en el campus:"
            elif parsed_intent["intent"] == "desayuno":
                frase_saludo += "para empezar bien la jornada te recomiendo estas opciones frescas y calientes:"
            elif parsed_intent["intent"] == "snack":
                frase_saludo += "para tu receso o descanso entre clases estas opciones son ideales y rápidas:"
            elif parsed_intent["intent"] == "postre":
                frase_saludo += "aquí tienes las mejores opciones para quitarte el antojo dulce:"
            else:
                frase_saludo += "nuestro recomendador inteligente seleccionó estas opciones para ti:"

            lineas = [frase_saludo, ""]
            structured_recs = []

            for i, r in enumerate(recs[:4], start=1):
                p = r.product
                precio_fmt = format_currency(p.price)
                rest_name = agent.restaurant_names.get(p.restaurant_id, p.restaurant_id.replace("_", " ").title())
                razon = r.explanations[0] if r.explanations else "Recomendado para tu perfil"

                lineas.append(f"{i}. **{p.name}** — {precio_fmt} ({rest_name})")
                lineas.append(f"   ⏱️ {p.prep_time} min • 💡 {razon}")

                pairing_name = None
                pairing_price = None
                if r.pairing_product:
                    pairing_name = r.pairing_product.name
                    pairing_price = r.pairing_product.price
                    lineas.append(f"   🥤 *Acompáñalo con:* {pairing_name} ({format_currency(pairing_price)})")
                lineas.append("")

                structured_recs.append({
                    "product_id": p.id,
                    "name": p.name,
                    "price": p.price,
                    "restaurant_id": p.restaurant_id,
                    "restaurant_name": rest_name,
                    "category": str(p.category.value if hasattr(p.category, "value") else p.category),
                    "prep_time": p.prep_time,
                    "utility_score": round(r.utility_score, 3),
                    "explanations": r.explanations,
                    "pairing_id": r.pairing_product.id if r.pairing_product else None,
                    "pairing_name": pairing_name,
                    "pairing_price": pairing_price,
                })

            combo_data = None
            if recs and recs[0].pairing_product:
                principal = recs[0].product
                acomp = recs[0].pairing_product
                total_combo = principal.price + acomp.price
                lineas.append(f"⭐ **Combo Sugerido:** {principal.name} + {acomp.name} por **{format_currency(total_combo)}**.")
                combo_data = {
                    "main_name": principal.name,
                    "pairing_name": acomp.name,
                    "total_price": total_combo,
                }

            lineas.append("\n¿Deseas agregar alguno directamente al carrito?")
            texto_final = "\n".join(lineas)

            response_data = {
                "response": texto_final,
                "banner": result.banner_message,
                "cluster_label": result.cluster_label or "Perfil Estudiante",
                "recommendations": structured_recs,
                "suggested_combo": combo_data,
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(json.dumps(response_data, ensure_ascii=False).encode("utf-8"))

        except Exception as e:
            self.send_response(500)
            self._send_cors_headers()
            self.end_headers()
            err_resp = {"response": f"Ocurrió un error en el agente: {str(e)}"}
            self.wfile.write(json.dumps(err_resp).encode("utf-8"))

    def handle_recommend(self, body):
        user_id = body.get("user_id", "usr_estudiante_01")
        when_str = body.get("when", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        k = int(body.get("k", 5))

        agent = get_agent()
        if agent is None:
            self.send_response(500)
            self._send_cors_headers()
            self.end_headers()
            self.wfile.write(b'{"error": "Agent not available"}')
            return

        try:
            dt = datetime.strptime(when_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            dt = datetime.now()
        dow = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"][dt.weekday()] if dt.weekday() < 5 else "Lunes"

        result = agent.decide(user_id, dt, dow, k)
        resp = {
            "user_id": result.user_id,
            "banner_message": result.banner_message,
            "cluster_label": result.cluster_label,
            "top_recommendations": [
                {
                    "product_id": r.product.id,
                    "name": r.product.name,
                    "price": r.product.price,
                    "category": str(r.product.category.value if hasattr(r.product.category, "value") else r.product.category),
                    "restaurant_id": r.product.restaurant_id,
                    "utility_score": r.utility_score,
                    "explanations": r.explanations,
                }
                for r in result.top_recommendations
            ],
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))


def run(port=8000):
    server_address = ("0.0.0.0", port)
    httpd = HTTPServer(server_address, BreakAiHandler)
    print("==================================================")
    print("  🤖 Servidor BreakApp-AI iniciado exitosamente")
    print(f"  📡 Escuchando en: http://0.0.0.0:{port}")
    print(f"  🌐 Para emulador Android: http://10.0.2.2:{port}/api/chat")
    print("==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nDeteniendo servidor...")
        httpd.server_close()


if __name__ == "__main__":
    p = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        p = int(sys.argv[1])
    run(p)
