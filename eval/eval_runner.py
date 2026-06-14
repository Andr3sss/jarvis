"""
eval_runner.py
--------------
Parte E del proyecto Jarvis — Evaluacion automatizada.

Que hace:
  1. Lee test_set.json con los 20 prompts
  2. Ejecuta cada prompt contra Jarvis (con RAG o herramientas segun categoria)
  3. Evalua automaticamente: exito / parcial / fallo
  4. Guarda resultados en eval/eval_results.json
  5. Genera eval/eval_summary.csv con metricas por categoria

Como ejecutarlo:
  python eval/eval_runner.py

Tiempo estimado: 20-40 minutos en CPU (20 prompts x 1-2 min cada uno)
"""

import json
import time
import os
import sys
import csv
import requests

# Rutas del proyecto
ROOT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT_DIR, 'mcp_tools'))
sys.path.insert(0, os.path.join(ROOT_DIR, 'rag'))

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:3b-instruct-q4_K_M"

TEST_SET_PATH    = os.path.join(ROOT_DIR, "eval", "test_set.json")
RESULTS_PATH     = os.path.join(ROOT_DIR, "eval", "eval_results.json")
SUMMARY_CSV_PATH = os.path.join(ROOT_DIR, "eval", "eval_summary.csv")

os.makedirs(os.path.join(ROOT_DIR, "eval"), exist_ok=True)


# ─────────────────────────────────────────────
# IMPORTAR MODULOS DE JARVIS
# ─────────────────────────────────────────────

def cargar_modulos():
    """Carga los modulos de Jarvis necesarios para la evaluacion."""
    try:
        from jarvis_agent import jarvis_responde
        print("[OK] jarvis_agent cargado")
    except Exception as e:
        print(f"[ERROR] No se pudo cargar jarvis_agent: {e}")
        sys.exit(1)

    try:
        from rag_pipeline import cargar_indice, recuperar_chunks, responder_con_rag, responder_sin_rag
        print("[OK] rag_pipeline cargado")
        coleccion, modelo_embed = cargar_indice()
        print(f"[OK] Indice RAG cargado con {coleccion.count()} chunks")
    except Exception as e:
        print(f"[ERROR] No se pudo cargar rag_pipeline: {e}")
        sys.exit(1)

    return jarvis_responde, cargar_indice, recuperar_chunks, responder_con_rag, responder_sin_rag, coleccion, modelo_embed


# ─────────────────────────────────────────────
# EJECUTAR PROMPT SEGUN CATEGORIA
# ─────────────────────────────────────────────

def ejecutar_prompt(test, jarvis_responde, coleccion, modelo_embed,
                    recuperar_chunks, responder_con_rag, responder_sin_rag):
    """
    Ejecuta un prompt segun su categoria y devuelve la respuesta + metricas.
    """
    categoria = test["categoria"]
    prompt    = test["prompt"]
    inicio    = time.time()
    respuesta = ""
    herramienta_usada = None
    tokens    = 0
    error     = None

    try:
        if categoria == "chat_puro":
            # Solo el modelo, sin RAG ni herramientas
            payload = {
                "model":  OLLAMA_MODEL,
                "prompt": f"Responde de forma clara y directa en espanol:\n\n{prompt}",
                "stream": False,
                "options": {"num_predict": 300, "temperature": 0.3, "seed": 42}
            }
            r = requests.post(OLLAMA_URL, json=payload, timeout=300)
            datos     = r.json()
            respuesta = datos.get("response", "")
            tokens    = datos.get("eval_count", 0)

        elif categoria == "rag_required":
            # RAG: buscar en corpus + responder con contexto
            chunks    = recuperar_chunks(prompt, coleccion, modelo_embed)
            respuesta, _ = responder_con_rag(prompt, chunks)
            tokens    = len(respuesta.split()) * 2  # Aproximacion

        elif categoria in ("tool_required", "multistep"):
            # Jarvis completo con herramientas
            resultado = jarvis_responde(prompt, verbose=False)
            respuesta = resultado.get("respuesta_final", "")
            herramienta_usada = resultado.get("herramienta")
            tokens    = resultado.get("tokens_totales", 0)
            if resultado.get("error"):
                error = resultado["error"]

        elif categoria == "adversarial":
            # Intentar con herramientas primero, luego con modelo solo
            resultado = jarvis_responde(prompt, verbose=False)
            respuesta = resultado.get("respuesta_final", "")
            herramienta_usada = resultado.get("herramienta")
            tokens    = resultado.get("tokens_totales", 0)

    except requests.exceptions.Timeout:
        respuesta = "TIMEOUT"
        error     = "El modelo no respondio en el tiempo limite"
    except Exception as e:
        respuesta = f"ERROR: {str(e)}"
        error     = str(e)

    latencia = round(time.time() - inicio, 2)

    return {
        "respuesta":         respuesta,
        "herramienta_usada": herramienta_usada,
        "latencia_s":        latencia,
        "tokens":            tokens,
        "error":             error
    }


# ─────────────────────────────────────────────
# EVALUAR RESULTADO
# ─────────────────────────────────────────────

def evaluar(test, resultado_ejecucion):
    """
    Evalua automaticamente si la respuesta es exito / parcial / fallo.
    Devuelve: "exito", "parcial", "fallo"
    """
    respuesta         = resultado_ejecucion["respuesta"].lower()
    herramienta_usada = resultado_ejecucion["herramienta_usada"]
    criterio          = test["criterio_exito"]
    keywords_exito    = [k.lower() for k in test.get("keywords_exito", [])]
    keywords_fallo    = [k.lower() for k in test.get("keywords_fallo", [])]
    min_palabras      = test.get("min_palabras", 10)
    herramienta_esp   = test.get("herramienta_esperada")

    # Si hubo error grave
    if "TIMEOUT" in resultado_ejecucion["respuesta"] or resultado_ejecucion.get("error"):
        return "fallo"

    # Verificar palabras de fallo primero
    for kf in keywords_fallo:
        if kf in respuesta:
            # En adversarial, encontrar palabras de fallo ES un fallo del sistema
            if test["categoria"] == "adversarial":
                return "fallo"

    num_palabras = len(respuesta.split())

    if criterio == "keywords":
        keywords_encontradas = sum(1 for k in keywords_exito if k in respuesta)
        porcentaje           = keywords_encontradas / len(keywords_exito) if keywords_exito else 0

        if porcentaje >= 0.6 and num_palabras >= min_palabras:
            return "exito"
        elif porcentaje >= 0.3 or num_palabras >= min_palabras:
            return "parcial"
        else:
            return "fallo"

    elif criterio == "herramienta_y_keywords":
        herramienta_ok       = (herramienta_usada == herramienta_esp)
        keywords_encontradas = sum(1 for k in keywords_exito if k in respuesta)
        porcentaje           = keywords_encontradas / len(keywords_exito) if keywords_exito else 0

        if herramienta_ok and porcentaje >= 0.4 and num_palabras >= min_palabras:
            return "exito"
        elif herramienta_ok or porcentaje >= 0.3:
            return "parcial"
        else:
            return "fallo"

    elif criterio == "manejo_gracioso":
        # En adversarial: exito = manejo el error correctamente sin inventar
        keywords_manejo = sum(1 for k in keywords_exito if k in respuesta)

        # Verificar que NO invento datos falsos
        palabras_fallo_encontradas = sum(1 for k in keywords_fallo if k in respuesta)

        if keywords_manejo >= 1 and palabras_fallo_encontradas == 0:
            return "exito"
        elif keywords_manejo >= 1:
            return "parcial"
        else:
            return "fallo"

    return "parcial"


# ─────────────────────────────────────────────
# CALCULAR METRICAS
# ─────────────────────────────────────────────

def calcular_metricas(resultados):
    """Calcula tasas de exito y latencias por categoria."""
    categorias = ["chat_puro", "rag_required", "tool_required", "multistep", "adversarial"]
    metricas   = {}

    # Global
    total   = len(resultados)
    exitos  = sum(1 for r in resultados if r["evaluacion"] == "exito")
    parcial = sum(1 for r in resultados if r["evaluacion"] == "parcial")
    fallos  = sum(1 for r in resultados if r["evaluacion"] == "fallo")

    metricas["global"] = {
        "total":          total,
        "exitos":         exitos,
        "parciales":      parcial,
        "fallos":         fallos,
        "tasa_exito":     round(exitos / total * 100, 1),
        "tasa_parcial":   round(parcial / total * 100, 1),
        "tasa_fallo":     round(fallos / total * 100, 1),
        "latencia_avg_s": round(sum(r["latencia_s"] for r in resultados) / total, 2),
        "tokens_total":   sum(r["tokens"] for r in resultados)
    }

    # Por categoria
    for cat in categorias:
        cat_resultados = [r for r in resultados if r["categoria"] == cat]
        if not cat_resultados:
            continue

        cat_total   = len(cat_resultados)
        cat_exitos  = sum(1 for r in cat_resultados if r["evaluacion"] == "exito")
        cat_parcial = sum(1 for r in cat_resultados if r["evaluacion"] == "parcial")
        cat_fallos  = sum(1 for r in cat_resultados if r["evaluacion"] == "fallo")
        cat_latencia = sum(r["latencia_s"] for r in cat_resultados) / cat_total

        metricas[cat] = {
            "total":          cat_total,
            "exitos":         cat_exitos,
            "parciales":      cat_parcial,
            "fallos":         cat_fallos,
            "tasa_exito":     round(cat_exitos / cat_total * 100, 1),
            "latencia_avg_s": round(cat_latencia, 2)
        }

    return metricas


# ─────────────────────────────────────────────
# GUARDAR RESULTADOS
# ─────────────────────────────────────────────

def guardar_resultados(resultados, metricas):
    """Guarda resultados en JSON y metricas en CSV."""

    # JSON completo
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump({
            "metricas":   metricas,
            "resultados": resultados
        }, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Resultados completos en: {RESULTS_PATH}")

    # CSV de resumen
    campos = ["categoria", "total", "exitos", "parciales", "fallos",
              "tasa_exito", "latencia_avg_s"]

    with open(SUMMARY_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        writer.writeheader()

        for cat, m in metricas.items():
            writer.writerow({
                "categoria":      cat,
                "total":          m["total"],
                "exitos":         m["exitos"],
                "parciales":      m.get("parciales", 0),
                "fallos":         m["fallos"],
                "tasa_exito":     m["tasa_exito"],
                "latencia_avg_s": m["latencia_avg_s"]
            })

    print(f"[OK] Resumen en CSV: {SUMMARY_CSV_PATH}")


# ─────────────────────────────────────────────
# IMPRIMIR RESUMEN FINAL
# ─────────────────────────────────────────────

def imprimir_resumen(metricas):
    """Muestra el resumen de resultados en pantalla."""
    print("\n" + "=" * 65)
    print("  RESULTADOS DE EVALUACION — Parte E del Proyecto Jarvis")
    print("=" * 65)

    g = metricas["global"]
    print(f"\n  GLOBAL: {g['exitos']}/{g['total']} exitos "
          f"({g['tasa_exito']}%) | "
          f"Latencia prom: {g['latencia_avg_s']}s | "
          f"Tokens totales: {g['tokens_total']}")

    print(f"\n  {'Categoria':<20} {'Total':>6} {'Exito%':>8} {'Latencia':>10}")
    print(f"  {'─'*20} {'─'*6} {'─'*8} {'─'*10}")

    categorias_orden = ["chat_puro", "rag_required", "tool_required",
                        "multistep", "adversarial"]
    iconos = {
        "chat_puro":     "💬",
        "rag_required":  "📚",
        "tool_required": "🔧",
        "multistep":     "🔀",
        "adversarial":   "⚠️ "
    }

    for cat in categorias_orden:
        if cat not in metricas:
            continue
        m     = metricas[cat]
        icono = iconos.get(cat, "  ")
        print(f"  {icono} {cat:<18} {m['total']:>6} "
              f"{m['tasa_exito']:>7}% "
              f"{m['latencia_avg_s']:>9}s")

    print("\n" + "=" * 65)
    print("  DETALLE POR RESULTADO:")
    print("=" * 65)


def imprimir_detalle(resultados):
    iconos_eval = {"exito": "✅", "parcial": "⚠️ ", "fallo": "❌"}
    for r in resultados:
        icono = iconos_eval.get(r["evaluacion"], "?")
        print(f"\n  {icono} [{r['id']}] {r['categoria']}")
        print(f"     Prompt:    {r['prompt'][:70]}...")
        print(f"     Respuesta: {r['respuesta'][:100]}...")
        print(f"     Latencia:  {r['latencia_s']}s | Tokens: {r['tokens']}")
        if r.get("herramienta_usada"):
            print(f"     Herram:    {r['herramienta_usada']}")
        if r.get("error"):
            print(f"     Error:     {r['error']}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 65)
    print("  EVALUACION AUTOMATICA — Proyecto Jarvis")
    print("=" * 65)
    print(f"\n  Modelo:    {OLLAMA_MODEL}")
    print(f"  Test set:  {TEST_SET_PATH}")
    print(f"  Tiempo est: 20-40 minutos en CPU\n")

    # Verificar que Ollama responde
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        print("[OK] Ollama respondiendo\n")
    except Exception:
        print("[ERROR] Ollama no responde. Verifica que este corriendo.")
        sys.exit(1)

    # Cargar test set
    if not os.path.exists(TEST_SET_PATH):
        print(f"[ERROR] No se encontro test_set.json en: {TEST_SET_PATH}")
        print("Copia el archivo test_set.json a la carpeta eval/")
        sys.exit(1)

    with open(TEST_SET_PATH, "r", encoding="utf-8") as f:
        test_set = json.load(f)
    print(f"[OK] {len(test_set)} prompts cargados\n")

    # Cargar modulos
    (jarvis_responde, cargar_indice, recuperar_chunks,
     responder_con_rag, responder_sin_rag,
     coleccion, modelo_embed) = cargar_modulos()

    # Ejecutar evaluacion
    resultados = []
    total      = len(test_set)

    print(f"\n{'─'*65}")
    print(f"  Iniciando evaluacion de {total} prompts...")
    print(f"{'─'*65}\n")

    for i, test in enumerate(test_set):
        print(f"  [{i+1:02d}/{total}] {test['id']} ({test['categoria']})")
        print(f"         Prompt: {test['prompt'][:60]}...")

        resultado_ejec = ejecutar_prompt(
            test, jarvis_responde, coleccion, modelo_embed,
            recuperar_chunks, responder_con_rag, responder_sin_rag
        )

        evaluacion = evaluar(test, resultado_ejec)

        iconos = {"exito": "✅", "parcial": "⚠️ ", "fallo": "❌"}
        print(f"         Resultado: {iconos[evaluacion]} {evaluacion.upper()} "
              f"| {resultado_ejec['latencia_s']}s "
              f"| {resultado_ejec['tokens']} tokens")
        if resultado_ejec.get("herramienta_usada"):
            print(f"         Herramienta: {resultado_ejec['herramienta_usada']}")

        resultados.append({
            "id":               test["id"],
            "categoria":        test["categoria"],
            "prompt":           test["prompt"],
            "respuesta":        resultado_ejec["respuesta"],
            "herramienta_usada": resultado_ejec["herramienta_usada"],
            "herramienta_esp":  test.get("herramienta_esperada"),
            "evaluacion":       evaluacion,
            "latencia_s":       resultado_ejec["latencia_s"],
            "tokens":           resultado_ejec["tokens"],
            "error":            resultado_ejec.get("error")
        })

        print()

    # Calcular y mostrar metricas
    metricas = calcular_metricas(resultados)
    imprimir_resumen(metricas)
    imprimir_detalle(resultados)

    # Guardar todo
    guardar_resultados(resultados, metricas)

    print("\n  SIGUIENTE PASO:")
    print("  Revisa eval/eval_results.json para el detalle completo")
    print("  Revisa eval/eval_summary.csv para las metricas del informe")
    print("=" * 65)
