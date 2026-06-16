"""
jarvis_server.py — VERSION FINAL CON PANEL DE GESTION
-------------------------------------------------------
Agrega endpoints REST para el panel visual de gestion de:
  - Notas y tareas (CRUD completo)
  - Eventos de Google Calendar (CRUD completo)

Endpoints nuevos:
  GET    /api/notas                     Lista todas las notas
  GET    /api/notas/<titulo>            Lee una nota especifica
  PUT    /api/notas/<titulo>            Edita el contenido de una nota
  DELETE /api/notas/<titulo>            Elimina una nota

  GET    /api/tareas                    Lista tareas pendientes
  POST   /api/tareas/<titulo>/completar Marca tarea como completada
  DELETE /api/tareas/<titulo>           Elimina una tarea

  GET    /api/calendario/proximos       Proximos eventos con IDs
  POST   /api/calendario/crear         Crear evento
  PUT    /api/calendario/<evento_id>   Editar evento
  DELETE /api/calendario/<evento_id>   Eliminar evento
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
    "evento", "reunion", "cita", "horario", "hoy", "semana",
    "nota", "notas", "anota", "apunta", "guarda esto", "recuerda",
    "tarea", "tareas", "pendiente", "pendientes", "completar",
    "marca como", "lista de tareas", "tengo que hacer",
    "crea una nota", "crea una tarea", "elimina la nota",
    "elimina la tarea", "tareas completadas", "crea un evento",
    "agrega al calendario", "programa", "elimina el evento"
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

# Cache RAG
_rag_coleccion    = None
_rag_modelo_embed = None
_rag_cargado      = False
_rag_error        = None


def cargar_rag_al_inicio():
    global _rag_coleccion, _rag_modelo_embed, _rag_cargado, _rag_error
    try:
        import rag_pipeline as rag
        print("[RAG] Cargando indice ChromaDB...")
        _rag_coleccion, _rag_modelo_embed = rag.cargar_indice()
        _rag_cargado = True
        print(f"[RAG] Indice cargado: {_rag_coleccion.count()} chunks")
    except Exception as e:
        _rag_error   = str(e)
        _rag_cargado = False
        print(f"[RAG] No disponible: {e}")


def llamar_ollama_directo(modelo, prompt, max_tokens=400):
    payload = {
        "model":  modelo,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": max_tokens, "temperature": 0.3, "seed": 42}
    }
    inicio = time.time()
    try:
        r = requests.post(OLLAMA_API, json=payload, timeout=300)
        r.raise_for_status()
        datos  = r.json()
        tiempo = round(time.time() - inicio, 2)
        return datos.get("response", "").strip(), tiempo, datos.get("eval_count", 0)
    except Exception as e:
        raise RuntimeError(f"Error llamando a Ollama: {str(e)}")


def seleccionar_modelo(pregunta):
    texto = pregunta.lower()
    for kw in KEYWORDS_RAG:
        if kw in texto: return MODEL_TOOLS
    for kw in KEYWORDS_TOOLS:
        if kw in texto: return MODEL_TOOLS
    for kw in KEYWORDS_CODE:
        if kw in texto: return MODEL_REASONING
    for kw in KEYWORDS_COMPLEX:
        if kw in texto: return MODEL_QUALITY
    if len(texto.split()) < 8:
        return MODEL_FAST
    return MODEL_TOOLS


def es_pregunta_rag(pregunta):
    texto = pregunta.lower()
    return any(kw in texto for kw in KEYWORDS_RAG)


def _leer_historial():
    if not os.path.exists(HISTORIAL_PATH):
        return []
    try:
        with open(HISTORIAL_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
        return datos if isinstance(datos, list) else []
    except Exception:
        return []


# ─────────────────────────────────────────────
# RUTAS PRINCIPALES
# ─────────────────────────────────────────────

@app.route("/")
def index():
    static_dir = os.path.join(BASE_DIR, "static")
    index_path = os.path.join(static_dir, "index.html")
    if not os.path.exists(index_path):
        return jsonify({"error": "static/index.html no encontrado."}), 404
    return send_from_directory(static_dir, "index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    try:
        datos    = request.get_json(force=True, silent=True) or {}
        pregunta = str(datos.get("pregunta", "")).strip()
        modelo   = str(datos.get("modelo",   MODEL_TOOLS)).strip()
        modo     = str(datos.get("modo",     "auto")).strip().lower()

        if not pregunta:
            return jsonify({"error": "Campo 'pregunta' requerido."}), 400

        modelo_usado = seleccionar_modelo(pregunta) if modo == "auto" else (modelo or MODEL_TOOLS)
        inicio       = time.time()

        if es_pregunta_rag(pregunta):
            if not _rag_cargado:
                return jsonify({"error": f"RAG no disponible: {_rag_error}"}), 503
            try:
                import rag_pipeline as rag
                chunks = rag.recuperar_chunks(pregunta, _rag_coleccion, _rag_modelo_embed)
                if not chunks:
                    return jsonify({"error": "No se encontraron fragmentos relevantes."}), 404

                contexto   = "\n\n---\n\n".join(chunks)
                prompt_rag = (
                    f"Eres un asistente experto en textos en espanol antiguo.\n"
                    f"Lee el siguiente texto del Quijote y responde la pregunta.\n\n"
                    f"=== TEXTO ===\n{contexto}\n=== FIN ===\n\n"
                    f"PREGUNTA: {pregunta}\nRESPUESTA:"
                )
                respuesta_texto, tiempo_s, _ = llamar_ollama_directo(
                    modelo_usado, prompt_rag, max_tokens=400
                )
                if not respuesta_texto:
                    return jsonify({"error": "El modelo no respondio (timeout)."}), 504

                return jsonify({
                    "respuesta":    respuesta_texto,
                    "herramienta":  None,
                    "modelo_usado": modelo_usado,
                    "tiempo_s":     round(time.time() - inicio, 2),
                    "tipo":         "rag"
                })
            except Exception as e:
                return jsonify({"error": f"Error en RAG: {str(e)}"}), 500

        try:
            import jarvis_agent as agent
            modelo_original    = agent.OLLAMA_MODEL
            agent.OLLAMA_MODEL = modelo_usado
            resultado          = agent.jarvis_responde(pregunta, verbose=False)
            agent.OLLAMA_MODEL = modelo_original
        except Exception as e:
            return jsonify({"error": f"Error en jarvis_agent: {str(e)}"}), 500

        if resultado.get("error"):
            return jsonify({"error": resultado["error"]}), 500

        herramientas = resultado.get("herramientas", [])
        herramienta  = ", ".join(herramientas) if herramientas else resultado.get("herramienta")
        tipo         = "tool" if resultado.get("uso_herramienta") else "chat"

        return jsonify({
            "respuesta":    resultado.get("respuesta_final", ""),
            "herramienta":  herramienta,
            "modelo_usado": modelo_usado,
            "tiempo_s":     round(time.time() - inicio, 2),
            "tipo":         tipo
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/status", methods=["GET"])
def status():
    try:
        r = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        r.raise_for_status()
        modelos = [m["name"] for m in r.json().get("models", [])]
        return jsonify({
            "ollama":              True,
            "modelos_disponibles": modelos,
            "rag_disponible":      _rag_cargado,
            "rag_chunks":          _rag_coleccion.count() if _rag_cargado else 0
        })
    except Exception:
        return jsonify({"ollama": False, "modelos_disponibles": [], "rag_disponible": False})


@app.route("/api/historial/guardar", methods=["POST"])
def historial_guardar():
    try:
        datos       = request.get_json(force=True, silent=True) or {}
        chat_id     = str(datos.get("chat_id",    "")).strip()
        pregunta    = str(datos.get("pregunta",   "")).strip()
        respuesta   = str(datos.get("respuesta",  "")).strip()
        modelo      = str(datos.get("modelo",     "")).strip()
        herramienta = datos.get("herramienta")
        tiempo_s    = datos.get("tiempo_s", 0.0)

        if not chat_id:
            return jsonify({"error": "Campo 'chat_id' requerido."}), 400

        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        mensaje = {
            "pregunta": pregunta, "respuesta": respuesta,
            "modelo": modelo, "herramienta": herramienta,
            "tiempo_s": tiempo_s, "timestamp": now_iso
        }

        historial      = _leer_historial()
        chat_existente = next((c for c in historial if c.get("chat_id") == chat_id), None)

        if chat_existente:
            chat_existente.setdefault("mensajes", []).append(mensaje)
            chat_existente["timestamp"] = now_iso
            historial.remove(chat_existente)
            historial.insert(0, chat_existente)
        else:
            titulo = (pregunta[:40] + "...") if len(pregunta) > 40 else pregunta
            historial.insert(0, {
                "chat_id": chat_id, "titulo": titulo,
                "timestamp": now_iso, "mensajes": [mensaje]
            })

        historial = historial[:HISTORIAL_MAX]
        os.makedirs(os.path.dirname(HISTORIAL_PATH), exist_ok=True)
        with open(HISTORIAL_PATH, "w", encoding="utf-8") as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/historial", methods=["GET"])
def historial_leer():
    try:
        return jsonify(_leer_historial()[:HISTORIAL_RETORNO])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# ENDPOINTS DE NOTAS
# ─────────────────────────────────────────────

@app.route("/api/notas", methods=["GET"])
def api_listar_notas():
    try:
        from gestor_notas import listar_notas
        return jsonify(listar_notas())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notas/<path:titulo>", methods=["GET"])
def api_leer_nota(titulo):
    try:
        from gestor_notas import leer_nota
        return jsonify(leer_nota(titulo))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notas/<path:titulo>", methods=["PUT"])
def api_editar_nota(titulo):
    try:
        from gestor_notas import crear_nota
        datos    = request.get_json(force=True, silent=True) or {}
        contenido = datos.get("contenido", "").strip()
        if not contenido:
            return jsonify({"error": "Campo 'contenido' requerido."}), 400
        return jsonify(crear_nota(titulo, contenido))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/notas/<path:titulo>", methods=["DELETE"])
def api_eliminar_nota(titulo):
    try:
        from gestor_notas import eliminar_nota
        return jsonify(eliminar_nota(titulo))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# ENDPOINTS DE TAREAS
# ─────────────────────────────────────────────

@app.route("/api/tareas", methods=["GET"])
def api_listar_tareas():
    try:
        from gestor_notas import listar_tareas_pendientes, listar_tareas_completadas
        pendientes  = listar_tareas_pendientes()
        completadas = listar_tareas_completadas()
        return jsonify({
            "pendientes":  pendientes.get("tareas", []),
            "completadas": completadas.get("tareas", [])
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tareas/<path:titulo>/completar", methods=["POST"])
def api_completar_tarea(titulo):
    try:
        from gestor_notas import completar_tarea
        return jsonify(completar_tarea(titulo))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tareas/<path:titulo>", methods=["DELETE"])
def api_eliminar_tarea(titulo):
    try:
        from gestor_notas import eliminar_tarea
        return jsonify(eliminar_tarea(titulo))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# ENDPOINTS DE CALENDARIO
# ─────────────────────────────────────────────

@app.route("/api/calendario/proximos", methods=["GET"])
def api_calendario_proximos():
    try:
        from calendario_google import listar_eventos_con_ids
        dias = int(request.args.get("dias", 7))
        return jsonify(listar_eventos_con_ids(dias))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/calendario/crear", methods=["POST"])
def api_calendario_crear():
    try:
        from calendario_google import crear_evento
        datos = request.get_json(force=True, silent=True) or {}
        titulo      = datos.get("titulo",      "").strip()
        fecha       = datos.get("fecha",       "").strip()
        hora_inicio = datos.get("hora_inicio", "").strip()
        hora_fin    = datos.get("hora_fin",    "").strip()
        descripcion = datos.get("descripcion", "").strip()

        if not titulo or not fecha:
            return jsonify({"error": "titulo y fecha son obligatorios."}), 400

        return jsonify(crear_evento(titulo, fecha, hora_inicio, hora_fin, descripcion))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/calendario/<evento_id>", methods=["PUT"])
def api_calendario_editar(evento_id):
    try:
        from calendario_google import editar_evento
        datos = request.get_json(force=True, silent=True) or {}
        return jsonify(editar_evento(
            evento_id,
            nuevo_titulo      = datos.get("titulo",      ""),
            nueva_fecha       = datos.get("fecha",       ""),
            nueva_hora_inicio = datos.get("hora_inicio", ""),
            nueva_hora_fin    = datos.get("hora_fin",    ""),
            nueva_descripcion = datos.get("descripcion", "")
        ))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/calendario/<evento_id>", methods=["DELETE"])
def api_calendario_eliminar(evento_id):
    try:
        from calendario_google import eliminar_evento
        return jsonify(eliminar_evento(evento_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
# VOZ (placeholders)
# ─────────────────────────────────────────────

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
    print("  JARVIS SERVER — VERSION FINAL")
    print("  http://localhost:5000")
    print("=" * 55)
    cargar_rag_al_inicio()
    print("=" * 55)
    app.run(host="0.0.0.0", port=5000, debug=False)
