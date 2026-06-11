"""
benchmark_quant.py
------------------
Parte A del proyecto Jarvis — Estudio de cuantización.

Qué hace:
  Para cada modelo (Q8_0, Q4_K_M, Q3_K_M) mide:
    - Tamaño del archivo en disco (GB)
    - RAM pico usada por Ollama durante inferencia (GB)
    - Tokens por segundo en una respuesta de ~200 tokens
    - Calidad en 5 preguntas estándar (la puntúas tú con la rúbrica)

Cómo ejecutarlo:
  1. Ollama debe estar corriendo: ollama serve (en otra terminal)
  2. Los 3 modelos deben estar descargados: ollama list
  3. Ejecutar: python benchmarks/benchmark_quant.py

Resultado:
  - Imprime tabla en pantalla
  - Guarda measurements.csv en la carpeta raíz del proyecto
  - Guarda respuestas completas en benchmarks/respuestas_calidad.txt para que las puntúes
"""

import requests
import time
import csv
import os
import json
import psutil
import subprocess

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_API_TAGS = "http://localhost:11434/api/tags"

# Los 3 modelos a comparar — nombres exactos de ollama
MODELOS = [
    "llama3.2:3b-instruct-q8_0",
    "llama3.2:3b-instruct-q4_K_M",
    "llama3.2:3b-instruct-q3_K_M",
]

# Prompt fijo para medir tokens/seg (siempre el mismo para comparar justo)
PROMPT_VELOCIDAD = (
    "Explain in detail how a computer processor executes instructions. "
    "Describe the fetch-decode-execute cycle, the role of registers, "
    "the ALU, and how modern CPUs use pipelining to improve performance. "
    "Give a concrete example with a simple addition operation."
)

# Las 5 preguntas estándar de calidad
PREGUNTAS_CALIDAD = [
    {
        "id": "Q1_matematicas",
        "tipo": "Matemáticas",
        "pregunta": "Si 3x + 7 = 22, ¿cuánto es x al cuadrado? Muestra todos los pasos."
    },
    {
        "id": "Q2_codigo",
        "tipo": "Código",
        "pregunta": "Write a Python function that reverses a singly linked list. Include the Node class definition and a brief explanation of how it works."
    },
    {
        "id": "Q3_resumen",
        "tipo": "Resumen",
        "pregunta": (
            "Resume el siguiente texto en máximo 3 oraciones: "
            "La inteligencia artificial es un campo de la informática que busca crear sistemas capaces de realizar tareas que normalmente requieren inteligencia humana. "
            "Estas tareas incluyen el reconocimiento de voz, la toma de decisiones, la traducción de idiomas y el reconocimiento visual de patrones. "
            "El aprendizaje automático, una subdisciplina de la IA, permite a los sistemas aprender de los datos sin ser programados explícitamente para cada tarea. "
            "Las redes neuronales profundas han revolucionado el campo al lograr resultados superiores a los humanos en tareas específicas como el diagnóstico médico por imagen."
        )
    },
    {
        "id": "Q4_hecho",
        "tipo": "Hecho histórico",
        "pregunta": "¿En qué año se publicó el paper 'Attention is All You Need' y quiénes fueron sus autores principales? ¿Qué arquitectura introdujo?"
    },
    {
        "id": "Q5_razonamiento",
        "tipo": "Razonamiento",
        "pregunta": (
            "Hay 5 cajas. La caja A es más pesada que la B. "
            "La caja C es más liviana que la D. "
            "La caja B pesa lo mismo que la C. "
            "La caja E es más pesada que la A. "
            "Ordena todas las cajas de más liviana a más pesada y explica tu razonamiento paso a paso."
        )
    },
]

# ─────────────────────────────────────────────
# RÚBRICA DE CALIDAD (léela antes de puntuar)
# ─────────────────────────────────────────────

RUBRICA = """
RÚBRICA DE CALIDAD (0-3 puntos por pregunta):
  0 = Respuesta incorrecta, sin sentido, o completamente inventada
  1 = Parcialmente correcta pero con errores importantes o muy incompleta
  2 = Correcta en lo principal pero con detalles faltantes o imprecisos
  3 = Correcta, completa, precisa y bien explicada

Respuestas esperadas:
  Q1: x=5, x²=25 (pasos: 3x=15, x=5, 5²=25)
  Q2: Clase Node con val y next. Función que itera invirtiendo punteros. Retorna nuevo head.
  Q3: 3 oraciones que capturen: IA=tareas humanas, ML=aprender de datos, redes neuronales=resultados superiores
  Q4: 2017, Vaswani et al. (Google Brain), arquitectura Transformer basada solo en atención
  Q5: Orden correcto: C=B < A < E, con D en algún lugar. Razonamiento lógico paso a paso.
"""

# ─────────────────────────────────────────────
# FUNCIONES AUXILIARES
# ─────────────────────────────────────────────

def verificar_ollama():
    """Verifica que Ollama esté corriendo antes de empezar."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            print("[OK] Ollama está corriendo correctamente\n")
            return True
    except Exception:
        pass
    print("[ERROR] Ollama no está corriendo.")
    print("        Abre una terminal nueva y ejecuta: ollama serve")
    print("        Luego vuelve a correr este script.")
    return False


def obtener_tamanio_modelo(nombre_modelo: str) -> float:
    """
    Obtiene el tamaño del modelo en GB desde la API de Ollama.
    """
    try:
        r = requests.get(OLLAMA_API_TAGS, timeout=10)
        modelos = r.json().get("models", [])
        for m in modelos:
            if m["name"] == nombre_modelo or m["model"] == nombre_modelo:
                size_bytes = m.get("size", 0)
                return round(size_bytes / (1024**3), 2)
    except Exception:
        pass
    return 0.0


def obtener_ram_ollama_gb() -> float:
    """
    Mide la RAM que está usando el proceso de Ollama en este momento.
    Devuelve el valor en GB.
    """
    ram_total = 0
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            nombre = proc.info['name'].lower()
            if 'ollama' in nombre:
                ram_bytes = proc.info['memory_info'].rss
                ram_total += ram_bytes
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return round(ram_total / (1024**3), 3)


def llamar_modelo(modelo: str, prompt: str, max_tokens: int = 220) -> dict:
    """
    Llama al modelo y devuelve métricas de rendimiento.
    """
    payload = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.1,  # Bajo para resultados reproducibles
            "seed": 42           # Semilla fija para reproducibilidad
        }
    }

    # RAM antes
    ram_antes = obtener_ram_ollama_gb()

    inicio = time.time()
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=600)
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print("\n[ERROR] No se puede conectar a Ollama. ¿Está corriendo 'ollama serve'?")
        return None
    except requests.exceptions.Timeout:
        print(f"\n[TIMEOUT] El modelo tardó más de 10 minutos. Documentar como timeout.")
        return None

    tiempo_total = time.time() - inicio

    # RAM después (pico aproximado)
    ram_despues = obtener_ram_ollama_gb()
    ram_pico = max(ram_antes, ram_despues)

    datos = response.json()
    tokens_generados = datos.get("eval_count", 0)
    tokens_prompt = datos.get("prompt_eval_count", 0)
    respuesta_texto = datos.get("response", "")

    tps = round(tokens_generados / tiempo_total, 2) if tiempo_total > 0 else 0

    return {
        "respuesta": respuesta_texto,
        "tiempo_s": round(tiempo_total, 2),
        "tokens_generados": tokens_generados,
        "tokens_prompt": tokens_prompt,
        "tokens_por_seg": tps,
        "ram_pico_gb": ram_pico,
    }


# ─────────────────────────────────────────────
# BENCHMARK PRINCIPAL
# ─────────────────────────────────────────────

def ejecutar_benchmark():
    print("=" * 65)
    print("  BENCHMARK DE CUANTIZACIÓN — Parte A del Proyecto Jarvis")
    print("=" * 65)
    print(RUBRICA)

    if not verificar_ollama():
        return

    resultados = []           # Para el CSV
    respuestas_archivo = []   # Para que puntúes manualmente

    for modelo in MODELOS:
        print(f"\n{'─'*65}")
        print(f"  Modelo: {modelo}")
        print(f"{'─'*65}")

        # Tamaño en disco
        tamanio_gb = obtener_tamanio_modelo(modelo)
        print(f"  Tamaño en disco: {tamanio_gb} GB")

        # ── Medición de velocidad (3 repeticiones, promediamos) ──
        print(f"\n  [1/2] Midiendo velocidad (3 repeticiones)...")
        tps_lista = []
        ram_lista = []

        for intento in range(3):
            print(f"    Intento {intento+1}/3...", end=" ", flush=True)
            resultado = llamar_modelo(modelo, PROMPT_VELOCIDAD, max_tokens=220)
            if resultado:
                tps_lista.append(resultado["tokens_por_seg"])
                ram_lista.append(resultado["ram_pico_gb"])
                print(f"{resultado['tokens_por_seg']} tok/s | RAM: {resultado['ram_pico_gb']} GB")
            else:
                print("FALLO")

        if not tps_lista:
            print(f"  [ERROR] No se pudo medir el modelo {modelo}. Saltando.")
            continue

        tps_promedio = round(sum(tps_lista) / len(tps_lista), 2)
        ram_promedio = round(sum(ram_lista) / len(ram_lista), 3)
        print(f"\n  Promedio: {tps_promedio} tok/s | RAM pico: {ram_promedio} GB")

        # ── Medición de calidad (5 preguntas) ──
        print(f"\n  [2/2] Ejecutando las 5 preguntas de calidad...")
        respuestas_modelo = []

        for pregunta in PREGUNTAS_CALIDAD:
            print(f"    {pregunta['tipo']}...", end=" ", flush=True)
            resultado = llamar_modelo(modelo, pregunta["pregunta"], max_tokens=300)
            if resultado:
                print(f"OK ({resultado['tiempo_s']}s)")
                respuestas_modelo.append({
                    "id": pregunta["id"],
                    "tipo": pregunta["tipo"],
                    "pregunta": pregunta["pregunta"],
                    "respuesta": resultado["respuesta"],
                    "tiempo_s": resultado["tiempo_s"],
                    "puntuacion": "??"  # Tú la llenas después
                })
            else:
                print("FALLO")
                respuestas_modelo.append({
                    "id": pregunta["id"],
                    "tipo": pregunta["tipo"],
                    "pregunta": pregunta["pregunta"],
                    "respuesta": "ERROR - timeout o fallo de conexión",
                    "tiempo_s": 0,
                    "puntuacion": "0"
                })

        respuestas_archivo.append({
            "modelo": modelo,
            "preguntas": respuestas_modelo
        })

        # Guardar fila en resultados (calidad_promedio se llena después manualmente)
        resultados.append({
            "modelo": modelo,
            "cuantizacion": modelo.split(":")[-1],
            "tamanio_gb": tamanio_gb,
            "ram_pico_gb": ram_promedio,
            "tokens_por_seg": tps_promedio,
            "calidad_promedio": "??",  # Tú la llenas después con la rúbrica
            "contexto_tokens": 200,
            "tipo_experimento": "cuantizacion"
        })

        print(f"\n  [OK] {modelo} completado.")

    # ── Guardar resultados ──

    # 1. measurements.csv
    csv_path = "measurements.csv"
    archivo_nuevo = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        campos = ["modelo", "cuantizacion", "tamanio_gb", "ram_pico_gb",
                  "tokens_por_seg", "calidad_promedio", "contexto_tokens", "tipo_experimento"]
        writer = csv.DictWriter(f, fieldnames=campos)
        if archivo_nuevo:
            writer.writeheader()
        writer.writerows(resultados)
    print(f"\n[OK] Métricas guardadas en: {csv_path}")

    # 2. Respuestas de calidad para puntuar manualmente
    respuestas_path = "benchmarks/respuestas_calidad.txt"
    os.makedirs("benchmarks", exist_ok=True)
    with open(respuestas_path, "w", encoding="utf-8") as f:
        f.write(RUBRICA + "\n\n")
        f.write("=" * 65 + "\n")
        f.write("RESPUESTAS PARA PUNTUAR MANUALMENTE\n")
        f.write("Edita este archivo y reemplaza ?? con tu puntuación (0, 1, 2 o 3)\n")
        f.write("Luego actualiza measurements.csv con el promedio de calidad\n")
        f.write("=" * 65 + "\n\n")

        for bloque in respuestas_archivo:
            f.write(f"\n{'='*65}\n")
            f.write(f"MODELO: {bloque['modelo']}\n")
            f.write(f"{'='*65}\n")
            for p in bloque["preguntas"]:
                f.write(f"\n[{p['id']}] Tipo: {p['tipo']}\n")
                f.write(f"Pregunta: {p['pregunta']}\n")
                f.write(f"Tiempo: {p['tiempo_s']}s\n")
                f.write(f"Respuesta del modelo:\n{p['respuesta']}\n")
                f.write(f"TU PUNTUACIÓN (0-3): {p['puntuacion']}\n")
                f.write("-" * 40 + "\n")

    print(f"[OK] Respuestas guardadas en: {respuestas_path}")

    # ── Resumen en pantalla ──
    print("\n" + "=" * 65)
    print("  RESUMEN DE RESULTADOS")
    print("=" * 65)
    print(f"  {'Modelo':<35} {'Tamaño':>8} {'RAM':>8} {'Tok/s':>8}")
    print(f"  {'─'*35} {'─'*8} {'─'*8} {'─'*8}")
    for r in resultados:
        print(f"  {r['modelo']:<35} {r['tamanio_gb']:>7}G {r['ram_pico_gb']:>7}G {r['tokens_por_seg']:>8}")

    print(f"\n  SIGUIENTE PASO:")
    print(f"  1. Abre: benchmarks/respuestas_calidad.txt")
    print(f"  2. Lee cada respuesta y puntúala con la rúbrica (0, 1, 2 o 3)")
    print(f"  3. Calcula el promedio de calidad por modelo")
    print(f"  4. Actualiza la columna 'calidad_promedio' en measurements.csv")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_benchmark()
