"""
jarvis_agent.py
---------------
Orquestador principal de Jarvis con tool calling.

Como funciona:
  1. Recibe una pregunta del usuario
  2. Envia un prompt especial al modelo describiendo las herramientas
  3. El modelo decide si necesita usar una herramienta y responde en JSON
  4. Parseamos el JSON y ejecutamos la herramienta correspondiente
  5. Enviamos el resultado de la herramienta al modelo para que genere
     una respuesta natural al usuario

Si el modelo decide que NO necesita herramienta, responde directamente.

Como ejecutarlo:
  python jarvis_agent.py --pregunta "Que clima hace en Quito?"
  python jarvis_agent.py --pregunta "Cuanto cuesta el Bitcoin en pesos mexicanos?"
  python jarvis_agent.py --pregunta "Cuantas estrellas tiene el repo de ollama?"

Tambien funciona en modo interactivo:
  python jarvis_agent.py
"""

import os
import sys
import json
import time
import re
import argparse
import requests

# Importar las herramientas
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herramientas import HERRAMIENTAS_DISPONIBLES, listar_herramientas_para_prompt

# ─────────────────────────────────────────────
# CONFIGURACION
# ─────────────────────────────────────────────

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b-instruct-q4_K_M"


# ─────────────────────────────────────────────
# PROMPT QUE ENSEÑA AL MODELO A USAR HERRAMIENTAS
# ─────────────────────────────────────────────

def construir_prompt_decision(pregunta_usuario: str) -> str:
    """
    Construye el prompt que le dice al modelo:
      - que herramientas existen
      - como debe responder si necesita usar una
      - como debe responder si NO necesita ninguna
    """
    herramientas_desc = listar_herramientas_para_prompt()

    prompt = f"""Eres Jarvis, un asistente que tiene acceso a herramientas externas para obtener datos en tiempo real.

{herramientas_desc}

INSTRUCCIONES IMPORTANTES:
1. Si la pregunta requiere datos en tiempo real (clima, precio cripto, info de GitHub), DEBES usar una herramienta.
2. Responde SOLO con un objeto JSON en este formato exacto:
   {{"tool": "nombre_herramienta", "parametros": {{"param1": "valor1", ...}}}}
3. Si la pregunta NO requiere ninguna herramienta (saludo, pregunta general de conocimiento), responde con:
   {{"tool": "ninguna", "respuesta": "tu respuesta en lenguaje natural"}}
4. NUNCA escribas texto fuera del JSON. Solo el JSON.

EJEMPLOS:

Pregunta: "Que clima hace en Madrid?"
Respuesta: {{"tool": "obtener_clima", "parametros": {{"ciudad": "Madrid"}}}}

Pregunta: "Cuanto vale 1 ethereum en euros?"
Respuesta: {{"tool": "precio_cripto", "parametros": {{"cripto": "ethereum", "moneda": "eur"}}}}

Pregunta: "Cuantas estrellas tiene el repositorio python/cpython?"
Respuesta: {{"tool": "info_github_repo", "parametros": {{"owner": "python", "repo": "cpython"}}}}

Pregunta: "Hola, como estas?"
Respuesta: {{"tool": "ninguna", "respuesta": "Hola! Soy Jarvis, tu asistente local. Estoy listo para ayudarte."}}

AHORA RESPONDE A ESTA PREGUNTA (solo JSON):
Pregunta: "{pregunta_usuario}"
Respuesta:"""
    return prompt


# ─────────────────────────────────────────────
# LLAMADA AL MODELO
# ─────────────────────────────────────────────

def llamar_modelo(prompt: str, max_tokens: int = 250) -> tuple:
    """Llama a Ollama y devuelve (respuesta, tiempo_s, tokens)."""
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.1,
            "seed": 42
        }
    }

    inicio = time.time()
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=120)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("[ERROR] Ollama no responde. Verifica que este corriendo.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        return None, 0, 0

    datos  = r.json()
    tiempo = time.time() - inicio
    tokens = datos.get("eval_count", 0)
    return datos.get("response", ""), tiempo, tokens


# ─────────────────────────────────────────────
# PARSEO ROBUSTO DEL JSON DEL MODELO
# ─────────────────────────────────────────────

def extraer_json(texto: str) -> dict:
    """
    Parseo robusto: a veces el modelo escribe texto antes/despues del JSON.
    Buscamos el primer { y el ultimo } para extraer solo el JSON.
    """
    if not texto:
        return None

    # Quitar bloques markdown si los hay
    texto = texto.replace("```json", "").replace("```", "").strip()

    # Buscar primer { y ultimo }
    inicio = texto.find("{")
    fin    = texto.rfind("}")

    if inicio == -1 or fin == -1 or fin < inicio:
        return None

    json_str = texto[inicio:fin + 1]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # Intento de rescate: buscar JSON anidados
        try:
            # Quitar saltos de linea y espacios extras
            json_str_limpio = re.sub(r'\s+', ' ', json_str)
            return json.loads(json_str_limpio)
        except json.JSONDecodeError:
            return None


# ─────────────────────────────────────────────
# EJECUCION DE LA HERRAMIENTA
# ─────────────────────────────────────────────

def ejecutar_herramienta(nombre: str, parametros: dict) -> dict:
    """Llama la funcion Python correspondiente a la herramienta."""
    if nombre not in HERRAMIENTAS_DISPONIBLES:
        return {"error": f"Herramienta desconocida: {nombre}"}

    funcion = HERRAMIENTAS_DISPONIBLES[nombre]["funcion"]

    try:
        return funcion(**parametros)
    except TypeError as e:
        return {"error": f"Parametros incorrectos: {str(e)}"}
    except Exception as e:
        return {"error": f"Error al ejecutar herramienta: {str(e)}"}


# ─────────────────────────────────────────────
# FLUJO COMPLETO DE JARVIS
# ─────────────────────────────────────────────

def jarvis_responde(pregunta: str, verbose: bool = True) -> dict:
    """
    Flujo completo:
      1. Modelo decide si usa herramienta
      2. Si usa, ejecutamos y le pasamos el resultado
      3. Modelo genera respuesta final natural
    """
    resultado = {
        "pregunta": pregunta,
        "uso_herramienta": False,
        "herramienta": None,
        "datos_herramienta": None,
        "respuesta_final": "",
        "tiempo_total_s": 0,
        "tokens_totales": 0,
        "error": None
    }

    tiempo_inicio = time.time()

    # PASO 1: Pedirle al modelo que decida
    if verbose:
        print("\n[1/3] El modelo esta decidiendo si necesita una herramienta...")

    prompt_decision = construir_prompt_decision(pregunta)
    respuesta_modelo, tiempo1, tokens1 = llamar_modelo(prompt_decision, max_tokens=200)
    resultado["tokens_totales"] += tokens1

    if not respuesta_modelo:
        resultado["error"] = "El modelo no respondio (timeout)"
        return resultado

    if verbose:
        print(f"      Respuesta cruda del modelo: {respuesta_modelo[:200]}")

    # PASO 2: Parsear el JSON
    decision = extraer_json(respuesta_modelo)

    if not decision:
        resultado["error"] = "El modelo no genero JSON valido"
        resultado["respuesta_final"] = (
            "Lo siento, no pude procesar tu pregunta. "
            "Respuesta cruda del modelo: " + respuesta_modelo[:200]
        )
        return resultado

    # PASO 3: Verificar si usar herramienta o no
    tool = decision.get("tool", "ninguna")

    if tool == "ninguna":
        # No usa herramienta, devolver respuesta directa
        resultado["respuesta_final"] = decision.get("respuesta", "Sin respuesta")
        resultado["tiempo_total_s"]  = round(time.time() - tiempo_inicio, 2)
        return resultado

    # SI USA HERRAMIENTA
    parametros = decision.get("parametros", {})
    resultado["uso_herramienta"]   = True
    resultado["herramienta"]       = tool

    if verbose:
        print(f"\n[2/3] Ejecutando herramienta: {tool}")
        print(f"      Parametros: {parametros}")

    # PASO 4: Ejecutar la herramienta
    datos = ejecutar_herramienta(tool, parametros)
    resultado["datos_herramienta"] = datos

    if "error" in datos:
        resultado["respuesta_final"] = f"Error: {datos['error']}"
        resultado["tiempo_total_s"]  = round(time.time() - tiempo_inicio, 2)
        return resultado

    if verbose:
        print(f"      Datos obtenidos: {json.dumps(datos, ensure_ascii=False)[:200]}")

    # PASO 5: Pedirle al modelo que genere respuesta natural con los datos
    if verbose:
        print(f"\n[3/3] Generando respuesta natural con los datos...")

    prompt_respuesta = f"""Eres Jarvis, un asistente amable. El usuario te pregunto:
"{pregunta}"

Acabas de obtener estos datos reales de una API:
{json.dumps(datos, ensure_ascii=False, indent=2)}

Genera una respuesta natural, clara y util en espanol usando esos datos.
No menciones que usaste una API o herramienta, simplemente responde como si supieras la informacion.
Se conciso, maximo 3 oraciones."""

    respuesta_final, tiempo2, tokens2 = llamar_modelo(prompt_respuesta, max_tokens=200)
    resultado["tokens_totales"]   += tokens2
    resultado["respuesta_final"]   = respuesta_final.strip() if respuesta_final else "Sin respuesta"
    resultado["tiempo_total_s"]    = round(time.time() - tiempo_inicio, 2)

    return resultado


# ─────────────────────────────────────────────
# MODO LINEA DE COMANDOS
# ─────────────────────────────────────────────

def modo_pregunta_unica(pregunta: str):
    print("=" * 60)
    print(f"  JARVIS")
    print("=" * 60)
    print(f"\nPregunta del usuario: {pregunta}\n")

    resultado = jarvis_responde(pregunta, verbose=True)

    print("\n" + "=" * 60)
    print("  RESPUESTA FINAL DE JARVIS:")
    print("=" * 60)
    print(resultado["respuesta_final"])
    print("=" * 60)
    print(f"\nTiempo total: {resultado['tiempo_total_s']}s | Tokens: {resultado['tokens_totales']}")
    if resultado["uso_herramienta"]:
        print(f"Herramienta usada: {resultado['herramienta']}")
    if resultado.get("error"):
        print(f"Error: {resultado['error']}")


def modo_interactivo():
    print("=" * 60)
    print("  JARVIS — Modo interactivo")
    print("  Escribe 'salir' para terminar")
    print("=" * 60)

    while True:
        try:
            pregunta = input("\nTu pregunta: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nHasta luego!")
            break

        if pregunta.lower() in ("salir", "exit", "quit"):
            print("Hasta luego!")
            break
        if not pregunta:
            continue

        resultado = jarvis_responde(pregunta, verbose=False)
        print("\n" + "-" * 60)
        print("Jarvis:", resultado["respuesta_final"])
        print("-" * 60)
        if resultado["uso_herramienta"]:
            print(f"(Uso: {resultado['herramienta']} | {resultado['tiempo_total_s']}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis con herramientas externas")
    parser.add_argument("--pregunta", type=str, help="Pregunta unica para Jarvis")
    args = parser.parse_args()

    if args.pregunta:
        modo_pregunta_unica(args.pregunta)
    else:
        modo_interactivo()
