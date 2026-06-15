"""
benchmark_phi4.py
-----------------
Benchmark de Phi-4-mini para el bonus de comparativa de familias.
Usa exactamente las mismas 5 preguntas y rúbrica que benchmark_quant.py
para que los resultados sean directamente comparables con Llama 3.2 3B.

Como ejecutarlo:
  python benchmarks/benchmark_phi4.py

Resultado:
  Agrega filas al measurements.csv existente
  Guarda respuestas en benchmarks/respuestas_phi4.txt para puntuar
"""

import requests
import time
import csv
import os
import psutil

OLLAMA_URL      = "http://localhost:11434/api/generate"
OLLAMA_API_TAGS = "http://localhost:11434/api/tags"

MODELOS = [
    "phi4-mini:3.8b-q8_0",
    "phi4-mini:3.8b-q4_K_M",
]

PROMPT_VELOCIDAD = (
    "Explain in detail how a computer processor executes instructions. "
    "Describe the fetch-decode-execute cycle, the role of registers, "
    "the ALU, and how modern CPUs use pipelining to improve performance. "
    "Give a concrete example with a simple addition operation."
)

PREGUNTAS_CALIDAD = [
    {
        "id": "Q1_matematicas",
        "tipo": "Matematicas",
        "pregunta": "Si 3x + 7 = 22, cuanto es x al cuadrado? Muestra todos los pasos."
    },
    {
        "id": "Q2_codigo",
        "tipo": "Codigo",
        "pregunta": "Write a Python function that reverses a singly linked list. Include the Node class definition and a brief explanation of how it works."
    },
    {
        "id": "Q3_resumen",
        "tipo": "Resumen",
        "pregunta": (
            "Resume el siguiente texto en maximo 3 oraciones: "
            "La inteligencia artificial es un campo de la informatica que busca crear sistemas capaces de realizar tareas que normalmente requieren inteligencia humana. "
            "Estas tareas incluyen el reconocimiento de voz, la toma de decisiones, la traduccion de idiomas y el reconocimiento visual de patrones. "
            "El aprendizaje automatico, una subdisciplina de la IA, permite a los sistemas aprender de los datos sin ser programados explicitamente para cada tarea. "
            "Las redes neuronales profundas han revolucionado el campo al lograr resultados superiores a los humanos en tareas especificas como el diagnostico medico por imagen."
        )
    },
    {
        "id": "Q4_hecho",
        "tipo": "Hecho historico",
        "pregunta": "En que año se publico el paper Attention is All You Need y quienes fueron sus autores principales? Que arquitectura introdujo?"
    },
    {
        "id": "Q5_razonamiento",
        "tipo": "Razonamiento",
        "pregunta": (
            "Hay 5 cajas. La caja A es mas pesada que la B. "
            "La caja C es mas liviana que la D. "
            "La caja B pesa lo mismo que la C. "
            "La caja E es mas pesada que la A. "
            "Ordena todas las cajas de mas liviana a mas pesada y explica tu razonamiento paso a paso."
        )
    },
]

RUBRICA = """
RUBRICA DE CALIDAD (0-3 puntos por pregunta):
  0 = Respuesta incorrecta, sin sentido, o completamente inventada
  1 = Parcialmente correcta pero con errores importantes o muy incompleta
  2 = Correcta en lo principal pero con detalles faltantes o imprecisos
  3 = Correcta, completa, precisa y bien explicada

Respuestas esperadas:
  Q1: x=5, x^2=25
  Q2: Clase Node con val y next. Funcion que itera invirtiendo punteros.
  Q3: 3 oraciones capturando IA, ML y redes neuronales
  Q4: 2017, Vaswani et al. Google Brain, arquitectura Transformer
  Q5: Orden: C=B < A < E, con D entre B y A o entre A y E segun logica
"""


def verificar_ollama():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            print("[OK] Ollama esta corriendo\n")
            return True
    except Exception:
        pass
    print("[ERROR] Ollama no responde. Ejecuta: ollama serve")
    return False


def obtener_tamanio_modelo(nombre):
    try:
        r = requests.get(OLLAMA_API_TAGS, timeout=10)
        for m in r.json().get("models", []):
            if m["name"] == nombre or m["model"] == nombre:
                return round(m.get("size", 0) / (1024**3), 2)
    except Exception:
        pass
    return 0.0


def obtener_ram_ollama_gb():
    ram_total = 0
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            if 'ollama' in proc.info['name'].lower():
                ram_total += proc.info['memory_info'].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return round(ram_total / (1024**3), 3)


def llamar_modelo(modelo, prompt, max_tokens=220):
    payload = {
        "model":  modelo,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.1,
            "seed": 42
        }
    }
    ram_antes = obtener_ram_ollama_gb()
    inicio    = time.time()
    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=600)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] No se puede conectar a Ollama.")
        return None
    except requests.exceptions.Timeout:
        print(f"\n[TIMEOUT] El modelo tardo demasiado.")
        return None

    tiempo       = time.time() - inicio
    ram_despues  = obtener_ram_ollama_gb()
    datos        = r.json()
    tokens       = datos.get("eval_count", 0)
    tps          = round(tokens / tiempo, 2) if tiempo > 0 else 0

    return {
        "respuesta":      datos.get("response", ""),
        "tiempo_s":       round(tiempo, 2),
        "tokens":         tokens,
        "tokens_por_seg": tps,
        "ram_pico_gb":    max(ram_antes, ram_despues),
    }


def ejecutar_benchmark():
    print("=" * 65)
    print("  BENCHMARK PHI-4-MINI — Comparativa de familias (Bonus)")
    print("=" * 65)
    print(RUBRICA)

    if not verificar_ollama():
        return

    resultados      = []
    respuestas_txt  = []

    for modelo in MODELOS:
        print(f"\n{'─'*65}")
        print(f"  Modelo: {modelo}")
        print(f"{'─'*65}")

        tamanio = obtener_tamanio_modelo(modelo)
        print(f"  Tamano en disco: {tamanio} GB")

        print(f"\n  [1/2] Midiendo velocidad (3 repeticiones)...")
        tps_lista  = []
        ram_lista  = []

        for intento in range(3):
            print(f"    Intento {intento+1}/3...", end=" ", flush=True)
            res = llamar_modelo(modelo, PROMPT_VELOCIDAD, max_tokens=220)
            if res:
                tps_lista.append(res["tokens_por_seg"])
                ram_lista.append(res["ram_pico_gb"])
                print(f"{res['tokens_por_seg']} tok/s | RAM: {res['ram_pico_gb']} GB")
            else:
                print("FALLO")

        if not tps_lista:
            print(f"  [ERROR] No se pudo medir {modelo}. Saltando.")
            continue

        tps_promedio = round(sum(tps_lista) / len(tps_lista), 2)
        ram_promedio = round(sum(ram_lista)  / len(ram_lista),  3)
        print(f"\n  Promedio: {tps_promedio} tok/s | RAM pico: {ram_promedio} GB")

        print(f"\n  [2/2] Ejecutando las 5 preguntas de calidad...")
        respuestas_modelo = []

        for pregunta in PREGUNTAS_CALIDAD:
            print(f"    {pregunta['tipo']}...", end=" ", flush=True)
            res = llamar_modelo(modelo, pregunta["pregunta"], max_tokens=300)
            if res:
                print(f"OK ({res['tiempo_s']}s)")
                respuestas_modelo.append({
                    "id":        pregunta["id"],
                    "tipo":      pregunta["tipo"],
                    "pregunta":  pregunta["pregunta"],
                    "respuesta": res["respuesta"],
                    "tiempo_s":  res["tiempo_s"],
                    "puntuacion": "??"
                })
            else:
                print("FALLO")
                respuestas_modelo.append({
                    "id":        pregunta["id"],
                    "tipo":      pregunta["tipo"],
                    "pregunta":  pregunta["pregunta"],
                    "respuesta": "ERROR",
                    "tiempo_s":  0,
                    "puntuacion": "0"
                })

        respuestas_txt.append({"modelo": modelo, "preguntas": respuestas_modelo})

        resultados.append({
            "modelo":           modelo,
            "cuantizacion":     modelo.split(":")[-1],
            "tamanio_gb":       tamanio,
            "ram_pico_gb":      ram_promedio,
            "tokens_por_seg":   tps_promedio,
            "calidad_promedio": "??",
            "contexto_tokens":  200,
            "tipo_experimento": "bonus_phi4"
        })

        print(f"\n  [OK] {modelo} completado.")

    # Guardar en measurements.csv
    csv_path    = "measurements.csv"
    archivo_nuevo = not os.path.exists(csv_path)
    campos = ["modelo", "cuantizacion", "tamanio_gb", "ram_pico_gb",
              "tokens_por_seg", "calidad_promedio", "contexto_tokens",
              "tipo_experimento"]

    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        if archivo_nuevo:
            writer.writeheader()
        writer.writerows(resultados)
    print(f"\n[OK] Metricas guardadas en: {csv_path}")

    # Guardar respuestas para puntuar
    os.makedirs("benchmarks", exist_ok=True)
    txt_path = "benchmarks/respuestas_phi4.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(RUBRICA + "\n\n")
        f.write("=" * 65 + "\n")
        f.write("RESPUESTAS PHI-4-MINI PARA PUNTUAR\n")
        f.write("Reemplaza ?? con tu puntuacion (0, 1, 2 o 3)\n")
        f.write("=" * 65 + "\n\n")
        for bloque in respuestas_txt:
            f.write(f"\n{'='*65}\n")
            f.write(f"MODELO: {bloque['modelo']}\n")
            f.write(f"{'='*65}\n")
            for p in bloque["preguntas"]:
                f.write(f"\n[{p['id']}] Tipo: {p['tipo']}\n")
                f.write(f"Pregunta: {p['pregunta']}\n")
                f.write(f"Tiempo: {p['tiempo_s']}s\n")
                f.write(f"Respuesta:\n{p['respuesta']}\n")
                f.write(f"TU PUNTUACION (0-3): {p['puntuacion']}\n")
                f.write("-" * 40 + "\n")

    print(f"[OK] Respuestas guardadas en: {txt_path}")

    # Resumen
    print("\n" + "=" * 65)
    print("  RESUMEN PHI-4-MINI")
    print("=" * 65)
    print(f"  {'Modelo':<35} {'Tamano':>8} {'RAM':>8} {'Tok/s':>8}")
    print(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*8}")
    for r in resultados:
        print(f"  {r['modelo']:<35} {r['tamanio_gb']:>7}G "
              f"{r['ram_pico_gb']:>7}G {r['tokens_por_seg']:>8}")

    print(f"\n  SIGUIENTE PASO:")
    print(f"  1. Abre: benchmarks/respuestas_phi4.txt")
    print(f"  2. Puntua cada respuesta con la rubrica (0-3)")
    print(f"  3. Actualiza calidad_promedio en measurements.csv")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_benchmark()
