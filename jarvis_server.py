"""
jarvis_server.py — VERSION CORREGIDA
--------------------------------------
Servidor Flask para la interfaz grafica de Jarvis.

Correcciones respecto a la version anterior:
  1. El indice RAG se carga UNA SOLA VEZ al arrancar el servidor
     en lugar de recargarse en cada peticion (mucho mas rapido)
  2. El modelo RAG se pasa directamente a las funciones en lugar
     de intentar sobreescribir la variable de modulo (que no funcionaba)
  3. Manejo de errores mas robusto con mensajes claros

Endpoints:
  GET  /                        Sirve static/index.html
  POST /api/chat                Orquesta modelo/RAG y devuelve respuesta
  GET  /api/status              Estado de Ollama y modelos disponibles
  POST /api/historial/guardar   Guarda entrada en data/historial.json
  GET  /api/historial           Devuelve ultimas 20 entradas
  POST /api/voice/transcribe    Placeholder para Whisper
  POST /api/voice/speak         Placeholder para Piper TTS

Ejecucion:
  python jarvis_server.py
"""

import os
import sys
import json
import time
import datetime
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "mcp_tools"))
sys.path.insert(0, os.path.join(BASE_DIR, "rag"))

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))
CORS(app)

# ─────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────

OLLAMA_BASE_URL   = "http://localhost:11434"
OLLAMA_API        = f"{OLLAMA_BASE_URL}/api/generate"
HISTORIAL_PATH    = os.path.join(BASE_DIR, "data", "historial.json")
HISTORIAL_MAX     = 50
HISTORIAL_RETORNO = 20

MODEL_FAST      = "llama3.2:3b-instruct-q3_K_M"
MODEL_REASONING = "phi4-mini:3.8b-q4_K_M"
MODEL_TOOLS     = "llama3.2:3b-instruct-q4_K_M"
MODEL_QUALITY   = "llama3.2:3b-instruct-q8_0"

KEYWORDS_RAG = {
    "quijote", "don quijote", "cervantes", "sancho",
    "dulcinea", "rocinante", "aldonza", "manchego",
    "caballero andante", "molinos", "toboso"
}
KEYWORDS_TOOLS = {
    "calendario", "clima", "tiempo", "temperatura", "lluvia",
    "bitcoin", "ethereum", "crypto", "cripto", "precio", "cuesta",
    "github", "repositorio", "repo", "estrellas", "forks",
    "evento", "reunion", "cita", "horario", "hoy", "semana"
}
KEYWORDS_CODE = {
    "codigo", "funcion", "algoritmo", "programa",
    "python", "javascript", "java", "sql", "html", "css",
    "matematicas", "calcula", "integral", "derivada",
    "ecuacion", "formula", "porcentaje", "probabilidad"
}
KEYWORDS_COMPLEX = {
    "explica", "compara", "analiza", "describe detalladamente",
    "diferencias", "paso a paso", "por que", "razona"
}

# ─────────────────────────────────────────────
# CACHE DEL INDICE RAG
# Se carga una sola vez al arrancar el servidor.
# Esto evita recargar ChromaDB en cada peticion.
# ─────────────────────────────────────────────

_rag_coleccion   = None
_rag_modelo_embed = None
_rag_cargado     = False
_rag_error       = None


def cargar_rag_al_inicio():
    """
    Intenta cargar el indice RAG una sola vez.
    Si falla, el servidor sigue funcionando pero el RAG devuelve error.
    """
    global _rag_coleccion, _rag_modelo_embed, _rag_cargado, _rag_error
    try:
        import rag_pipeline as rag
        print("[RAG] Cargando indice ChromaDB...")
        _rag_coleccion, _rag_modelo_embed = rag.cargar_indice()
        _rag_cargado = True
        print(f"[RAG] Indice cargado: {_rag_coleccion.count()} chunks disponibles")
    except Exception as e:
        _rag_error = str(e)
        _rag_cargado = False
        print(f"[RAG] No se pudo cargar el indice: {e}")
        print("[RAG] El servidor funciona pero el RAG no estara disponible")


# ─────────────────────────────────────────────
# LLAMADA DIRECTA A OLLAMA
# Evita el problema de sobreescribir OLLAMA_MODEL
# en modulos importados. Llama directo a la API.
# ─────────────────────────────────────────────

def llamar_ollama_directo(modelo: str, prompt: str, max_tokens: int = 400) -> tuple:
    """
    Llama directamente a la API de Ollama con el modelo especificado.
    Devuelve (respuesta_texto, tiempo_s, tokens)
    """
    payload = {
        "model":  modelo,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.3,
            "seed": 42
        }
    }
    inicio = time.time()
    try:
        r = requests.post(OLLAMA_API, json=payload, timeout=300)
        r.raise_for_status()
        datos   = r.json()
        tiempo  = round(time.time() - inicio, 2)
        tokens  = datos.get("eval_count", 0)
        return datos.get("response", "").strip(), tiempo, tokens
    except requests.exceptions.Timeout:
        return None, round(time.time() - inicio, 2), 0
    except Exception as e:
        raise RuntimeError(f"Error llamando a Ollama: {str(e)}")


# ─────────────────────────────────────────────
# ENRUTADOR AUTOMATICO DE MODELOS
# ─────────────────────────────────────────────

def seleccionar_modelo(pregunta: str) -> str:
    texto    = pregunta.lower()
    palabras = texto.split()

    for kw in KEYWORDS_RAG:
        if kw in texto:
            return MODEL_TOOLS

    for kw in KEYWORDS_TOOLS:
        if kw in texto:
            return MODEL_TOOLS

    for kw in KEYWORDS_CODE:
        if kw in texto:
            return MODEL_REASONING

    for kw in KEYWORDS_COMPLEX:
        if kw in texto:
            return MODEL_QUALITY

    if len(palabras) < 8:
        return MODEL_FAST

    return MODEL_TOOLS


def es_pregunta_rag(pregunta: str) -> bool:
    texto = pregunta.lower()
    for kw in KEYWORDS_RAG:
        if kw in texto:
            return True
    return False


# ─────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────

@app.route("/")
def index():
    static_dir = os.path.join(BASE_DIR, "static")
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        return jsonify({
            "error": "static/index.html no encontrado.",
            "tipo":  "error"
        }), 404
    return send_from_directory(static_dir, "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    """
    Recibe:  {"pregunta": "...", "modelo": "...", "modo": "auto|manual"}
    Devuelve: {"respuesta": "...", "herramienta": null|"...",
               "modelo_usado": "...", "tiempo_s": ..., "tipo": "tool|rag|chat"}
    """
    try:
        datos    = request.get_json(force=True, silent=True) or {}
        pregunta = str(datos.get("pregunta", "")).strip()
        modelo   = str(datos.get("modelo",   MODEL_TOOLS)).strip()
        modo     = str(datos.get("modo",     "auto")).strip().lower()

        if not pregunta:
            return jsonify({"error": "Campo 'pregunta' requerido.", "tipo": "error"}), 400

        modelo_usado = seleccionar_modelo(pregunta) if modo == "auto" else (modelo or MODEL_TOOLS)
        inicio       = time.time()

        # ── RAMA RAG ────────────────────────────
        if es_pregunta_rag(pregunta):

            if not _rag_cargado:
                return jsonify({
                    "error": f"El indice RAG no esta disponible: {_rag_error}. "
                             f"Ejecuta primero: python rag/rag_pipeline.py --build",
                    "tipo":  "error"
                }), 503

            try:
                import rag_pipeline as rag

                # Recuperar chunks usando el indice ya cargado en memoria
                chunks = rag.recuperar_chunks(
                    pregunta, _rag_coleccion, _rag_modelo_embed
                )

                if not chunks:
                    return jsonify({
                        "error": "No se encontraron fragmentos relevantes en el corpus.",
                        "tipo":  "error"
                    }), 404

                # Construir el prompt RAG directamente
                contexto = "\n\n---\n\n".join(chunks)
                prompt_rag = (
                    f"Eres un asistente experto en analisis de textos en espanol antiguo.\n"
                    f"Lee CUIDADOSAMENTE el siguiente texto del libro 'Don Quijote de la Mancha'\n"
                    f"y responde la pregunta usando la informacion encontrada en el.\n"
                    f"El texto esta en espanol del siglo XVII. Si encuentras informacion relevante,\n"
                    f"explicala en espanol moderno. Responde siempre con la informacion del texto.\n\n"
                    f"=== TEXTO DEL LIBRO ===\n{contexto}\n=== FIN DEL TEXTO ===\n\n"
                    f"PREGUNTA: {pregunta}\n\n"
                    f"Analiza el texto anterior y responde la pregunta de forma clara y completa:"
                )

                # Llamar directamente a Ollama con el modelo elegido
                respuesta_texto, tiempo_s, _ = llamar_ollama_directo(
                    modelo_usado, prompt_rag, max_tokens=400
                )

                if not respuesta_texto:
                    return jsonify({
                        "error": "El modelo no respondio (timeout). Intenta de nuevo.",
                        "tipo":  "error"
                    }), 504

                return jsonify({
                    "respuesta":    respuesta_texto,
                    "herramienta":  None,
                    "modelo_usado": modelo_usado,
                    "tiempo_s":     round(time.time() - inicio, 2),
                    "tipo":         "rag"
                })

            except Exception as e:
                return jsonify({
                    "error": f"Error en RAG: {str(e)}",
                    "tipo":  "error"
                }), 500

        # ── RAMA AGENTE (tool calling / chat) ────
        try:
            import jarvis_agent as agent

            # Guardamos el modelo original y lo sobreescribimos
            # usando la variable de modulo correcta del agente
            modelo_original      = agent.OLLAMA_MODEL
            agent.OLLAMA_MODEL   = modelo_usado

            resultado = agent.jarvis_responde(pregunta, verbose=False)

            agent.OLLAMA_MODEL = modelo_original

        except Exception as e:
            return jsonify({
                "error": f"Error en jarvis_agent: {str(e)}",
                "tipo":  "error"
            }), 500

        if resultado.get("error"):
            return jsonify({
                "error": resultado["error"],
                "tipo":  "error"
            }), 500

        herramienta = resultado.get("herramienta")
        tipo        = "tool" if resultado.get("uso_herramienta") else "chat"

        return jsonify({
            "respuesta":    resultado.get("respuesta_final", ""),
            "herramienta":  herramienta,
            "modelo_usado": modelo_usado,
            "tiempo_s":     round(time.time() - inicio, 2),
            "tipo":         tipo
        })

    except Exception as e:
        return jsonify({"error": str(e), "tipo": "error"}), 500


@app.route("/api/status", methods=["GET"])
def status():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        datos   = r.json()
        modelos = [m["name"] for m in datos.get("models", [])]
        return jsonify({
            "ollama":              True,
            "modelos_disponibles": modelos,
            "rag_disponible":      _rag_cargado,
            "rag_chunks":          _rag_coleccion.count() if _rag_cargado else 0
        })
    except requests.exceptions.ConnectionError:
        return jsonify({"ollama": False, "modelos_disponibles": [], "rag_disponible": False})
    except requests.exceptions.Timeout:
        return jsonify({"ollama": False, "modelos_disponibles": [], "rag_disponible": False})
    except Exception as e:
        return jsonify({"ollama": False, "modelos_disponibles": [], "error": str(e)})


@app.route("/api/historial/guardar", methods=["POST"])
def historial_guardar():
    try:
        datos       = request.get_json(force=True, silent=True) or {}
        chat_id     = str(datos.get("chat_id", "")).strip()
        pregunta    = str(datos.get("pregunta",  "")).strip()
        respuesta   = str(datos.get("respuesta", "")).strip()
        modelo      = str(datos.get("modelo",    "")).strip()
        herramienta = datos.get("herramienta")
        tiempo_s    = datos.get("tiempo_s", 0.0)

        if not chat_id:
            return jsonify({"error": "Campo 'chat_id' requerido.", "tipo": "error"}), 400

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        mensaje = {
            "pregunta":   pregunta,
            "respuesta":  respuesta,
            "modelo":     modelo,
            "herramienta": herramienta,
            "tiempo_s":   tiempo_s,
            "timestamp":  now_iso
        }

        historial = _leer_historial()

        chat_existente = next((c for c in historial if c.get("chat_id") == chat_id), None)

        if chat_existente:
            chat_existente.setdefault("mensajes", []).append(mensaje)
            chat_existente["timestamp"] = now_iso
            historial.remove(chat_existente)
            historial.insert(0, chat_existente)
        else:
            titulo = (pregunta[:40] + "...") if len(pregunta) > 40 else pregunta
            historial.insert(0, {
                "chat_id":   chat_id,
                "titulo":    titulo,
                "timestamp": now_iso,
                "mensajes":  [mensaje]
            })

        historial = historial[:HISTORIAL_MAX]
        os.makedirs(os.path.dirname(HISTORIAL_PATH), exist_ok=True)
        with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

        return jsonify({"ok": True})

    except Exception as e:
        return jsonify({"error": str(e), "tipo": "error"}), 500


@app.route("/api/historial", methods=["GET"])
def historial_leer():
    try:
        return jsonify(_leer_historial()[:HISTORIAL_RETORNO])
    except Exception as e:
        return jsonify({"error": str(e), "tipo": "error"}), 500


def _leer_historial() -> list:
    if not os.path.exists(HISTORIAL_PATH):
        return []
    try:
        with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, list) else []
    except (json.JSONDecodeError, IOError):
        return []


@app.route("/api/voice/transcribe", methods=["POST"])
def voice_transcribe():
    return jsonify({"transcript": "", "error": "not implemented yet"})


@app.route("/api/voice/speak", methods=["POST"])
def voice_speak():
    return jsonify({"audio_url": "", "error": "not implemented yet"})


# ─────────────────────────────────────────────
# ENTRYPOINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  JARVIS SERVER")
    print("  http://localhost:5000")
    print("=" * 55)
    print(f"  Static dir : {os.path.join(BASE_DIR, 'static')}")
    print(f"  Historial  : {HISTORIAL_PATH}")
    print("=" * 55)

    # Cargar el indice RAG al inicio una sola vez
    cargar_rag_al_inicio()

    print("=" * 55)
    app.run(host="0.0.0.0", port=5000, debug=False)