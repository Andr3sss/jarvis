"""
benchmark_kvcache.py
--------------------
Parte B del proyecto Jarvis — Experimento de KV Cache.

Qué hace:
  Toma el mejor modelo de la Parte A (Q4_K_M) y mide cómo cambian
  la velocidad y el uso de RAM cuando el contexto crece:
    - 512 tokens de contexto
    - 2048 tokens de contexto
    - 8192 tokens de contexto
    - 16384 tokens de contexto (puede fallar por RAM — eso es un resultado válido)

Por qué importa:
  La caché KV guarda las representaciones de cada token del contexto.
  Al crecer el contexto, la caché crece linealmente — más RAM, menos velocidad.
  Este experimento lo demuestra empíricamente con tus propios números.

Cómo ejecutarlo:
  python benchmarks/benchmark_kvcache.py

Resultado:
  - Imprime tabla en pantalla
  - Agrega filas al measurements.csv existente
  - Guarda benchmarks/resultados_kvcache.txt con detalles
"""

import requests
import time
import csv
import os
import psutil

# ─────────────────────────────────────────────
# CONFIGURACIÓN
# ─────────────────────────────────────────────

OLLAMA_URL  = "http://localhost:11434/api/generate"
MODELO      = "llama3.2:3b-instruct-q4_K_M"   # El mejor de la Parte A

# Longitudes de contexto a probar (en tokens aproximados)
CONTEXTOS = [512, 2048, 8192, 16384]

# Timeout por petición en segundos
# 16K tokens puede tardar 15-20 minutos en CPU — le damos 25 min
TIMEOUT = 1500

# ─────────────────────────────────────────────
# GENERAR TEXTO DE RELLENO
# ─────────────────────────────────────────────

def generar_contexto(num_tokens_aprox: int) -> str:
    """
    Genera un texto de relleno de aproximadamente num_tokens_aprox tokens.
    Regla aproximada: 1 token ≈ 4 caracteres en inglés.
    Usamos texto técnico real para que el modelo no lo ignore.
    """
    parrafo_base = (
        "In computer science, a cache is a hardware or software component "
        "that stores data so that future requests for that data can be served faster. "
        "The key-value cache in transformer models stores the key and value matrices "
        "computed during the attention mechanism for each token in the context window. "
        "As the context length grows, the KV cache size grows linearly, consuming "
        "more memory and requiring more computation during each generation step. "
        "This is one of the fundamental bottlenecks of large language model inference "
        "on hardware with limited memory bandwidth such as CPU-only systems. "
    )
    # Repetir hasta alcanzar el tamaño aproximado
    chars_necesarios = num_tokens_aprox * 4
    repeticiones = (chars_necesarios // len(parrafo_base)) + 1
    texto = (parrafo_base * repeticiones)[:chars_necesarios]
    return texto


# ─────────────────────────────────────────────
# MEDIR RAM DE OLLAMA
# ─────────────────────────────────────────────

def obtener_ram_ollama_gb() -> float:
    """Mide la RAM que usa el proceso Ollama en este momento."""
    ram_total = 0
    for proc in psutil.process_iter(['name', 'memory_info']):
        try:
            if 'ollama' in proc.info['name'].lower():
                ram_total += proc.info['memory_info'].rss
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return round(ram_total / (1024**3), 3)


# ─────────────────────────────────────────────
# LLAMAR AL MODELO CON CONTEXTO LARGO
# ─────────────────────────────────────────────

def medir_con_contexto(longitud_contexto: int) -> dict:
    """
    Envía un prompt con contexto de la longitud indicada y mide
    tokens/seg y RAM pico.
    """
    # Construir el prompt: contexto largo + pregunta corta al final
    contexto = generar_contexto(longitud_contexto)
    pregunta = (
        "\n\nBased on the context above about caching in computer systems, "
        "explain in one paragraph what a KV cache is and why it matters for LLM inference."
    )
    prompt_completo = contexto + pregunta

    payload = {
        "model": MODELO,
        "prompt": prompt_completo,
        "stream": False,
        "options": {
            "num_predict": 150,    # Respuesta corta — medimos velocidad de generación
            "num_ctx": longitud_contexto + 200,  # Ventana de contexto = longitud + margen
            "temperature": 0.1,
            "seed": 42
        }
    }

    print(f"  Enviando prompt de ~{longitud_contexto} tokens...", end=" ", flush=True)

    ram_antes = obtener_ram_ollama_gb()
    inicio    = time.time()

    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        tiempo = time.time() - inicio
        print(f"TIMEOUT después de {round(tiempo/60, 1)} minutos")
        return {
            "longitud_contexto": longitud_contexto,
            "tokens_por_seg": 0,
            "ram_pico_gb": obtener_ram_ollama_gb(),
            "tiempo_s": round(tiempo, 1),
            "tokens_generados": 0,
            "estado": "TIMEOUT",
            "respuesta": "TIMEOUT - contexto demasiado largo para la RAM disponible"
        }
    except requests.exceptions.ConnectionError:
        print("ERROR DE CONEXIÓN")
        return {
            "longitud_contexto": longitud_contexto,
            "tokens_por_seg": 0,
            "ram_pico_gb": 0,
            "tiempo_s": 0,
            "tokens_generados": 0,
            "estado": "ERROR",
            "respuesta": "Error de conexión con Ollama"
        }

    tiempo_total = time.time() - inicio
    ram_despues  = obtener_ram_ollama_gb()
    ram_pico     = max(ram_antes, ram_despues)

    datos            = response.json()
    tokens_generados = datos.get("eval_count", 0)
    respuesta_texto  = datos.get("response", "")
    tps = round(tokens_generados / tiempo_total, 2) if tiempo_total > 0 else 0

    print(f"OK — {tps} tok/s | RAM: {ram_pico} GB | {round(tiempo_total, 1)}s")

    return {
        "longitud_contexto": longitud_contexto,
        "tokens_por_seg": tps,
        "ram_pico_gb": ram_pico,
        "tiempo_s": round(tiempo_total, 1),
        "tokens_generados": tokens_generados,
        "estado": "OK",
        "respuesta": respuesta_texto
    }


# ─────────────────────────────────────────────
# BENCHMARK PRINCIPAL
# ─────────────────────────────────────────────

def ejecutar_benchmark_kvcache():
    print("=" * 65)
    print("  BENCHMARK KV CACHE — Parte B del Proyecto Jarvis")
    print("=" * 65)
    print(f"  Modelo: {MODELO}")
    print(f"  Contextos a probar: {CONTEXTOS}")
    print(f"\n  ADVERTENCIA: El contexto de 16384 tokens puede tardar")
    print(f"  15-25 minutos o fallar por RAM insuficiente.")
    print(f"  Ambos casos son resultados válidos para el informe.\n")

    # Verificar Ollama
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=5)
        if r.status_code == 200:
            print("[OK] Ollama está corriendo\n")
    except Exception:
        print("[ERROR] Ollama no responde. Verifica que esté corriendo.")
        return

    resultados    = []
    detalles_txt  = []

    for contexto in CONTEXTOS:
        print(f"{'─'*65}")
        print(f"  Contexto: {contexto} tokens")
        print(f"{'─'*65}")

        resultado = medir_con_contexto(contexto)
        resultados.append(resultado)

        detalles_txt.append(
            f"\nContexto {contexto} tokens:\n"
            f"  Estado:          {resultado['estado']}\n"
            f"  Tokens/seg:      {resultado['tokens_por_seg']}\n"
            f"  RAM pico:        {resultado['ram_pico_gb']} GB\n"
            f"  Tiempo total:    {resultado['tiempo_s']} s\n"
            f"  Tokens generados:{resultado['tokens_generados']}\n"
            f"  Respuesta:\n{resultado['respuesta'][:300]}...\n"
        )

    # ── Guardar en measurements.csv ──
    csv_path   = "measurements.csv"
    campos     = ["modelo", "cuantizacion", "tamanio_gb", "ram_pico_gb",
                  "tokens_por_seg", "calidad_promedio", "contexto_tokens",
                  "tipo_experimento"]

    archivo_nuevo = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campos)
        if archivo_nuevo:
            writer.writeheader()
        for r in resultados:
            writer.writerow({
                "modelo":           MODELO,
                "cuantizacion":     "q4_K_M",
                "tamanio_gb":       2.0,
                "ram_pico_gb":      r["ram_pico_gb"],
                "tokens_por_seg":   r["tokens_por_seg"],
                "calidad_promedio": "N/A",
                "contexto_tokens":  r["longitud_contexto"],
                "tipo_experimento": "kvcache"
            })
    print(f"\n[OK] Resultados agregados a: {csv_path}")

    # ── Guardar detalles en txt ──
    os.makedirs("benchmarks", exist_ok=True)
    txt_path = "benchmarks/resultados_kvcache.txt"
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("RESULTADOS EXPERIMENTO KV CACHE — Parte B\n")
        f.write(f"Modelo: {MODELO}\n")
        f.write("=" * 65 + "\n")
        for d in detalles_txt:
            f.write(d)
        f.write("\n" + "=" * 65 + "\n")
        f.write("ANÁLISIS:\n")
        f.write(
            "La caché KV crece linealmente con el contexto. Cada token adicional\n"
            "requiere almacenar vectores Key y Value para todas las capas de atención.\n"
            "Para llama3.2:3b: 28 capas × 8 cabezas × 64 dims × 2 (K+V) × 2 bytes (fp16)\n"
            "= aproximadamente 57,344 bytes por token de contexto = ~56 KB/token.\n"
            "En 8192 tokens: ~448 MB solo de KV cache.\n"
            "En 16384 tokens: ~896 MB solo de KV cache.\n"
        )
    print(f"[OK] Detalles guardados en: {txt_path}")

    # ── Resumen en pantalla ──
    print("\n" + "=" * 65)
    print("  RESUMEN — KV CACHE")
    print("=" * 65)
    print(f"  {'Contexto':>10} {'Tok/s':>8} {'RAM (GB)':>10} {'Tiempo(s)':>10} {'Estado':>8}")
    print(f"  {'─'*10} {'─'*8} {'─'*10} {'─'*10} {'─'*8}")
    for r in resultados:
        print(
            f"  {r['longitud_contexto']:>10} "
            f"{r['tokens_por_seg']:>8} "
            f"{r['ram_pico_gb']:>10} "
            f"{r['tiempo_s']:>10} "
            f"{r['estado']:>8}"
        )

    print("\n  SIGUIENTE PASO:")
    print("  Con estos números genera las gráficas con:")
    print("  python benchmarks/generar_graficas.py")
    print("=" * 65)


if __name__ == "__main__":
    ejecutar_benchmark_kvcache()
