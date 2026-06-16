"""
jarvis_agent.py — VERSION FINAL CON RESOLUCION DE IDs
-------------------------------------------------------
Mejora principal: el ID del evento se resuelve ANTES de
ejecutar la herramienta, no despues de que falla.
"""

import os
import sys
import json
import time
import re
import argparse
import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from herramientas import HERRAMIENTAS_DISPONIBLES, listar_herramientas_para_prompt

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b-instruct-q4_K_M"


def construir_prompt_decision(pregunta_usuario: str) -> str:
    herramientas_desc = listar_herramientas_para_prompt()

    prompt = f"""Eres Jarvis, un asistente que tiene acceso a herramientas externas para obtener datos en tiempo real.

{herramientas_desc}

INSTRUCCIONES IMPORTANTES:
1. Si la pregunta requiere datos en tiempo real o acciones, DEBES usar las herramientas necesarias.
2. Si necesitas UNA herramienta, responde con UN objeto JSON:
   {{"tool": "nombre_herramienta", "parametros": {{"param1": "valor1"}}}}
3. Si necesitas DOS herramientas en secuencia, responde con DOS objetos JSON separados por punto y coma:
   {{"tool": "herramienta1", "parametros": {{...}}}}; {{"tool": "herramienta2", "parametros": {{...}}}}
4. Si NO necesitas ninguna herramienta, responde con:
   {{"tool": "ninguna", "respuesta": "tu respuesta en lenguaje natural"}}
5. NUNCA escribas texto fuera del JSON. Solo el JSON o los JSONs.

EJEMPLOS:

Pregunta: "Que clima hace en Madrid?"
Respuesta: {{"tool": "obtener_clima", "parametros": {{"ciudad": "Madrid"}}}}

Pregunta: "Cuanto vale ethereum en euros?"
Respuesta: {{"tool": "precio_cripto", "parametros": {{"cripto": "ethereum", "moneda": "eur"}}}}

Pregunta: "Cuantas estrellas tiene ollama/ollama?"
Respuesta: {{"tool": "info_github_repo", "parametros": {{"owner": "ollama", "repo": "ollama"}}}}

Pregunta: "Crea una nota llamada Python con el contenido: lenguaje de programacion"
Respuesta: {{"tool": "crear_nota", "parametros": {{"titulo": "Python", "contenido": "lenguaje de programacion"}}}}

Pregunta: "Crea una tarea llamada Estudiar para el lunes"
Respuesta: {{"tool": "crear_tarea", "parametros": {{"titulo": "Estudiar", "fecha_limite": "lunes"}}}}

Pregunta: "Muéstrame mis tareas pendientes"
Respuesta: {{"tool": "listar_tareas_pendientes", "parametros": {{}}}}

Pregunta: "Cuanto cuesta el bitcoin y guarda el precio como una nota llamada Precio BTC"
Respuesta: {{"tool": "precio_cripto", "parametros": {{"cripto": "bitcoin", "moneda": "usd"}}}}; {{"tool": "crear_nota", "parametros": {{"titulo": "Precio BTC", "contenido": "consultar precio obtenido"}}}}

Pregunta: "Hola, como estas?"
Respuesta: {{"tool": "ninguna", "respuesta": "Hola! Soy Jarvis, tu asistente local. Estoy listo para ayudarte."}}

Pregunta: "elimina el evento llamado Defensa Jarvis de mi calendario"
Respuesta: {{"tool": "buscar_eventos", "parametros": {{"palabra_clave": "Defensa Jarvis"}}}}; {{"tool": "eliminar_evento_calendario", "parametros": {{"evento_id": "usar_id_del_resultado_anterior"}}}}

Pregunta: "edita el evento Reunion de equipo y cambia la hora a las 15:00"
Respuesta: {{"tool": "buscar_eventos", "parametros": {{"palabra_clave": "Reunion de equipo"}}}}; {{"tool": "editar_evento_calendario", "parametros": {{"evento_id": "usar_id_del_resultado_anterior", "nueva_hora_inicio": "15:00"}}}}

Pregunta: "cambia el titulo del evento PRUEBA FINAL a Examen Final"
Respuesta: {{"tool": "buscar_eventos", "parametros": {{"palabra_clave": "PRUEBA FINAL"}}}}; {{"tool": "editar_evento_calendario", "parametros": {{"evento_id": "usar_id_del_resultado_anterior", "nuevo_titulo": "Examen Final"}}}}

AHORA RESPONDE A ESTA PREGUNTA (solo JSON):
Pregunta: "{pregunta_usuario}"
Respuesta:"""
    return prompt


def llamar_modelo(prompt: str, max_tokens: int = 300) -> tuple:
    payload = {
        "model":  OLLAMA_MODEL,
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
        response = requests.post(OLLAMA_URL, json=payload, timeout=120)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] Ollama no responde.")
        sys.exit(1)
    except requests.exceptions.Timeout:
        return None, 0, 0

    datos  = response.json()
    tiempo = time.time() - inicio
    tokens = datos.get("eval_count", 0)
    return datos.get("response", ""), tiempo, tokens


def extraer_json(texto: str) -> list:
    if not texto:
        return []

    texto  = texto.replace("```json", "").replace("```", "").strip()
    partes = re.split(r'\}\s*;\s*\{', texto)

    resultados = []

    for i, parte in enumerate(partes):
        if i > 0:
            parte = "{" + parte
        if i < len(partes) - 1:
            parte = parte + "}"

        parte  = parte.strip()
        inicio = parte.find("{")
        fin    = parte.rfind("}")

        if inicio == -1 or fin == -1 or fin < inicio:
            continue

        json_str = parte[inicio:fin + 1]

        try:
            obj = json.loads(json_str)
            if isinstance(obj, dict) and "tool" in obj:
                resultados.append(obj)
        except json.JSONDecodeError:
            try:
                json_str_limpio = re.sub(r'\s+', ' ', json_str)
                obj = json.loads(json_str_limpio)
                if isinstance(obj, dict) and "tool" in obj:
                    resultados.append(obj)
            except json.JSONDecodeError:
                continue

    return resultados


def ejecutar_herramienta(nombre: str, parametros: dict) -> dict:
    if nombre not in HERRAMIENTAS_DISPONIBLES:
        return {"error": f"Herramienta desconocida: {nombre}"}

    funcion = HERRAMIENTAS_DISPONIBLES[nombre]["funcion"]

    try:
        return funcion(**parametros)
    except TypeError as e:
        return {"error": f"Parametros incorrectos: {str(e)}"}
    except Exception as e:
        return {"error": f"Error al ejecutar herramienta: {str(e)}"}


def resolver_parametros(tool: str, parametros: dict,
                         datos_combinados: dict) -> dict:
    """
    Resuelve placeholders en los parametros ANTES de ejecutar la herramienta.

    Casos que maneja:
      1. evento_id = "usar_id_del_resultado_anterior"
         → busca el ID real en el resultado de buscar_eventos
      2. contenido = "consultar precio obtenido"
         → sustituye con el precio real de precio_cripto
    """
    parametros = dict(parametros)  # copia para no mutar el original

    # CASO 1: Editar o eliminar evento necesita el ID real
    if (tool in ("editar_evento_calendario", "eliminar_evento_calendario") and
            "usar_id_del_resultado_anterior" in str(parametros.get("evento_id", ""))):

        eventos = datos_combinados.get("buscar_eventos", {}).get("eventos", [])

        # buscar_eventos devuelve eventos limpios sin ID
        # necesitamos listar_eventos_con_ids que sí devuelve IDs
        # pero si buscar_eventos tiene el campo "id" lo usamos
        id_real = None
        for ev in eventos:
            if ev.get("id"):
                id_real = ev["id"]
                break

        # Si buscar_eventos no tiene IDs (porque limpiar_para_jarvis los quita),
        # hacemos una llamada directa a listar_eventos_con_ids para obtenerlos
        if not id_real:
            from calendario_google import listar_eventos_con_ids
            # Extraer la palabra clave que busco el paso anterior
            palabra = ""
            for decision_anterior in datos_combinados:
                if decision_anterior == "buscar_eventos":
                    # Intentar recuperar la palabra del resultado
                    palabra = datos_combinados["buscar_eventos"].get(
                        "palabra_clave", ""
                    )
                    break

            if palabra:
                from calendario_google import autenticar
                from googleapiclient.discovery import build
                import datetime

                try:
                    servicio  = autenticar()
                    time_min  = datetime.datetime.now(
                        datetime.timezone.utc).isoformat().replace('+00:00', 'Z')
                    time_max  = (datetime.datetime.now(datetime.timezone.utc) +
                                 datetime.timedelta(days=90)).isoformat().replace('+00:00', 'Z')

                    resultado = servicio.events().list(
                        calendarId   = "primary",
                        timeMin      = time_min,
                        timeMax      = time_max,
                        q            = palabra,
                        maxResults   = 5,
                        singleEvents = True,
                        orderBy      = "startTime"
                    ).execute()

                    items = resultado.get("items", [])
                    if items:
                        id_real = items[0].get("id", "")
                except Exception:
                    pass

        if id_real:
            parametros["evento_id"] = id_real
        else:
            return {"__error__": f"No se encontro el ID del evento. "
                                 f"Verifica que el nombre es exactamente correcto."}

    # CASO 2: Crear nota con precio obtenido del paso anterior
    if (tool == "crear_nota" and
            "consultar precio obtenido" in str(parametros.get("contenido", "")) and
            "precio_cripto" in datos_combinados):

        precio_datos   = datos_combinados["precio_cripto"]
        contenido_real = (
            f"{precio_datos.get('criptomoneda', '')} vale "
            f"{precio_datos.get('precio', '')} "
            f"{precio_datos.get('moneda', '')} "
            f"(cambio 24h: {precio_datos.get('cambio_24h', '')})"
        )
        parametros["contenido"] = contenido_real

    return parametros


def jarvis_responde(pregunta: str, verbose: bool = True) -> dict:
    """
    Flujo completo con soporte para tool calling secuencial.
    Los parametros dependientes del resultado anterior se resuelven
    ANTES de ejecutar la herramienta.
    """
    resultado = {
        "pregunta":          pregunta,
        "uso_herramienta":   False,
        "herramienta":       None,
        "herramientas":      [],
        "datos_herramienta": None,
        "respuesta_final":   "",
        "tiempo_total_s":    0,
        "tokens_totales":    0,
        "error":             None
    }

    tiempo_inicio = time.time()

    # PASO 1: Pedirle al modelo que decida
    if verbose:
        print("\n[1/3] El modelo esta decidiendo si necesita una herramienta...")

    prompt_decision = construir_prompt_decision(pregunta)
    respuesta_modelo, tiempo1, tokens1 = llamar_modelo(
        prompt_decision, max_tokens=300
    )
    resultado["tokens_totales"] += tokens1

    if not respuesta_modelo:
        resultado["error"] = "El modelo no respondio (timeout)"
        return resultado

    if verbose:
        print(f"      Respuesta cruda del modelo: {respuesta_modelo[:250]}")

    # PASO 2: Parsear uno o multiples JSONs
    decisiones = extraer_json(respuesta_modelo)

    if not decisiones:
        resultado["error"] = "El modelo no genero JSON valido"
        resultado["respuesta_final"] = (
            "Lo siento, no pude procesar tu pregunta. "
            "Respuesta cruda del modelo: " + respuesta_modelo[:200]
        )
        return resultado

    # PASO 3: Respuesta directa sin herramienta
    if decisiones[0].get("tool") == "ninguna":
        resultado["respuesta_final"] = decisiones[0].get(
            "respuesta", "Sin respuesta"
        )
        resultado["tiempo_total_s"] = round(time.time() - tiempo_inicio, 2)
        return resultado

    # PASO 4: Ejecutar herramientas en secuencia
    datos_combinados     = {}
    herramientas_usadas  = []
    errores_herramientas = []

    for idx, decision in enumerate(decisiones):
        tool       = decision.get("tool", "ninguna")
        parametros = decision.get("parametros", {})

        if tool == "ninguna":
            continue

        # RESOLUCION DE PARAMETROS DEPENDIENTES — antes de ejecutar
        parametros_resueltos = resolver_parametros(tool, parametros, datos_combinados)

        # Si la resolucion devuelve un error interno lo registramos
        if "__error__" in parametros_resueltos:
            errores_herramientas.append(f"{tool}: {parametros_resueltos['__error__']}")
            continue

        if verbose:
            num = f"{idx+1}/{len(decisiones)}"
            print(f"\n[2/3] Ejecutando herramienta {num}: {tool}")
            print(f"      Parametros: {parametros_resueltos}")

        datos = ejecutar_herramienta(tool, parametros_resueltos)

        if "error" in datos:
            errores_herramientas.append(f"{tool}: {datos['error']}")
        else:
            datos_combinados[tool] = datos
            herramientas_usadas.append(tool)

            if verbose:
                datos_str = json.dumps(datos, ensure_ascii=False)
                print(f"      Datos: {datos_str[:150]}")

    resultado["uso_herramienta"]   = len(herramientas_usadas) > 0
    resultado["herramientas"]      = herramientas_usadas
    resultado["herramienta"]       = herramientas_usadas[0] if herramientas_usadas else None
    resultado["datos_herramienta"] = datos_combinados

    if not herramientas_usadas:
        resultado["respuesta_final"] = (
            "Error en las herramientas: " + "; ".join(errores_herramientas)
        )
        resultado["tiempo_total_s"] = round(time.time() - tiempo_inicio, 2)
        return resultado

    # PASO 5: Generar respuesta natural
    if verbose:
        n = len(herramientas_usadas)
        print(f"\n[3/3] Generando respuesta con {n} herramienta(s)...")

    contexto_datos = ""
    for tool_name, datos in datos_combinados.items():
        contexto_datos += f"\nDatos de {tool_name}:\n"
        contexto_datos += json.dumps(datos, ensure_ascii=False, indent=2)
        contexto_datos += "\n"

    if errores_herramientas:
        contexto_datos += (
            f"\nNota: algunas herramientas fallaron: "
            f"{', '.join(errores_herramientas)}"
        )

    prompt_respuesta = f"""Eres Jarvis, un asistente util y amable. El usuario te pregunto:
"{pregunta}"

Obtuviste los siguientes datos reales de las herramientas:
{contexto_datos}
Genera una respuesta natural, clara y util en espanol usando todos los datos.
Si ejecutaste multiples acciones, menciona cada resultado de forma organizada.
Se conciso pero completo, maximo 4 oraciones."""

    respuesta_final, tiempo2, tokens2 = llamar_modelo(
        prompt_respuesta, max_tokens=300
    )
    resultado["tokens_totales"]  += tokens2
    resultado["respuesta_final"]  = (
        respuesta_final.strip() if respuesta_final else "Sin respuesta"
    )
    resultado["tiempo_total_s"]   = round(time.time() - tiempo_inicio, 2)

    return resultado


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

    if resultado.get("herramientas"):
        print(f"Herramientas usadas: {', '.join(resultado['herramientas'])}")
    elif resultado.get("herramienta"):
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
        if resultado.get("herramientas"):
            print(f"(Herramientas: {', '.join(resultado['herramientas'])} | {resultado['tiempo_total_s']}s)")
        elif resultado.get("herramienta"):
            print(f"(Herramienta: {resultado['herramienta']} | {resultado['tiempo_total_s']}s)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Jarvis con herramientas externas")
    parser.add_argument("--pregunta", type=str, help="Pregunta unica para Jarvis")
    args = parser.parse_args()

    if args.pregunta:
        modo_pregunta_unica(args.pregunta)
    else:
        modo_interactivo()