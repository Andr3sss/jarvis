"""
generar_graficas.py
-------------------
Genera todas las gráficas necesarias para el informe de las Partes A y B.

Gráficas que produce:
  1. grafica_tamanio_vs_velocidad.png  — Parte A
  2. grafica_tamanio_vs_calidad.png    — Parte A
  3. grafica_contexto_vs_velocidad.png — Parte B
  4. grafica_contexto_vs_tiempo.png    — Parte B

Cómo ejecutarlo:
  python benchmarks/generar_graficas.py

Resultado:
  Todas las gráficas se guardan en: report/capturas/
"""

import csv
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ─────────────────────────────────────────────
# DATOS — editados con tus números reales
# ─────────────────────────────────────────────

# Datos Parte A — cuantización
# Actualiza calidad_promedio con tus puntuaciones del archivo respuestas_calidad.txt
DATOS_CUANTIZACION = [
    {
        "modelo":     "Q8_0",
        "tamanio_gb": 3.19,
        "ram_gb":     0.047,
        "tps":        4.95,
        "calidad":    2.2,
    },
    {
        "modelo":     "Q4_K_M",
        "tamanio_gb": 1.88,
        "ram_gb":     0.052,
        "tps":        27.87,
        "calidad":    2.6,
    },
    {
        "modelo":     "Q3_K_M",
        "tamanio_gb": 1.57,
        "ram_gb":     0.057,
        "tps":        6.73,
        "calidad":    2.0,
    },
]

# Datos Parte B — KV cache (tus resultados reales)
DATOS_KVCACHE = [
    {"contexto": 512,   "tps": 3.81, "tiempo_s": 29.4,  "ram_gb": 0.087},
    {"contexto": 2048,  "tps": 2.59, "tiempo_s": 38.7,  "ram_gb": 0.087},
    {"contexto": 8192,  "tps": 5.60, "tiempo_s": 18.4,  "ram_gb": 0.090},
    {"contexto": 16384, "tps": 0.30, "tiempo_s": 358.2, "ram_gb": 0.090},
]

# ─────────────────────────────────────────────
# CONFIGURACIÓN VISUAL
# ─────────────────────────────────────────────

COLOR_Q8   = "#E24B4A"   # rojo
COLOR_Q4   = "#534AB7"   # morado
COLOR_Q3   = "#0F6E56"   # verde

COLORES_CUANT = [COLOR_Q8, COLOR_Q4, COLOR_Q3]

os.makedirs("report/capturas", exist_ok=True)
plt.rcParams.update({
    "font.family":  "DejaVu Sans",
    "font.size":    11,
    "axes.grid":    True,
    "grid.alpha":   0.3,
    "figure.dpi":   150,
})

# ─────────────────────────────────────────────
# GRÁFICA 1 — Tamaño vs Velocidad (Parte A)
# ─────────────────────────────────────────────

def grafica_tamanio_vs_velocidad():
    fig, ax = plt.subplots(figsize=(7, 5))

    modelos   = [d["modelo"]     for d in DATOS_CUANTIZACION]
    tamanios  = [d["tamanio_gb"] for d in DATOS_CUANTIZACION]
    tps_vals  = [d["tps"]        for d in DATOS_CUANTIZACION]

    bars = ax.bar(modelos, tps_vals, color=COLORES_CUANT, width=0.5, edgecolor="white")

    # Etiquetas encima de cada barra
    for bar, tam, tps in zip(bars, tamanios, tps_vals):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.1,
            f"{tps} tok/s\n({tam} GB)",
            ha="center", va="bottom", fontsize=9, color="#333333"
        )

    ax.set_title("Parte A — Cuantización: Tamaño vs Velocidad de Inferencia", fontsize=12, pad=12)
    ax.set_xlabel("Nivel de Cuantización")
    ax.set_ylabel("Tokens por segundo (tok/s)")
    ax.set_ylim(0, max(tps_vals) * 1.35)

    plt.tight_layout()
    ruta = "report/capturas/grafica_tamanio_vs_velocidad.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardada: {ruta}")


# ─────────────────────────────────────────────
# GRÁFICA 2 — Tamaño vs Calidad (Parte A)
# ─────────────────────────────────────────────

def grafica_tamanio_vs_calidad():
    fig, ax1 = plt.subplots(figsize=(7, 5))

    modelos   = [d["modelo"]     for d in DATOS_CUANTIZACION]
    tamanios  = [d["tamanio_gb"] for d in DATOS_CUANTIZACION]
    calidades = [d["calidad"]    for d in DATOS_CUANTIZACION]
    tps_vals  = [d["tps"]        for d in DATOS_CUANTIZACION]

    x = range(len(modelos))

    # Barras de calidad
    bars = ax1.bar(x, calidades, color=COLORES_CUANT, width=0.4, label="Calidad (0-3)", edgecolor="white")
    ax1.set_ylabel("Calidad promedio (0–3)", color="#333333")
    ax1.set_ylim(0, 3.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(modelos)

    # Línea de tokens/seg en eje secundario
    ax2 = ax1.twinx()
    ax2.plot(x, tps_vals, color="#EF9F27", marker="o",
             linewidth=2, markersize=8, label="Tok/s")
    ax2.set_ylabel("Tokens por segundo (tok/s)", color="#EF9F27")
    ax2.tick_params(axis="y", labelcolor="#EF9F27")

    # Etiquetas de calidad
    for bar, cal in zip(bars, calidades):
        ax1.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.05,
            f"{cal}",
            ha="center", va="bottom", fontsize=10, fontweight="bold"
        )

    ax1.set_title("Parte A — Cuantización: Calidad vs Velocidad por Nivel", fontsize=12, pad=12)
    ax1.set_xlabel("Nivel de Cuantización")

    # Leyenda combinada
    patch1 = mpatches.Patch(color="#534AB7", label="Calidad promedio (0-3)")
    line1  = plt.Line2D([0], [0], color="#EF9F27", marker="o", label="Tok/s")
    ax1.legend(handles=[patch1, line1], loc="upper left", fontsize=9)

    plt.tight_layout()
    ruta = "report/capturas/grafica_tamanio_vs_calidad.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardada: {ruta}")


# ─────────────────────────────────────────────
# GRÁFICA 3 — Contexto vs Velocidad (Parte B)
# ─────────────────────────────────────────────

def grafica_contexto_vs_velocidad():
    fig, ax = plt.subplots(figsize=(8, 5))

    contextos = [d["contexto"] for d in DATOS_KVCACHE]
    tps_vals  = [d["tps"]      for d in DATOS_KVCACHE]

    ax.plot(contextos, tps_vals, color="#534AB7", marker="o",
            linewidth=2.5, markersize=9, label="Tok/s")

    # Etiquetas en cada punto
    for ctx, tps in zip(contextos, tps_vals):
        ax.annotate(
            f"{tps} tok/s",
            xy=(ctx, tps),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center", fontsize=9,
            color="#333333"
        )

    # Línea de referencia en 16384 tokens (swap)
    ax.axvline(x=16384, color="#E24B4A", linestyle="--", alpha=0.7, linewidth=1.5)
    ax.text(16384 + 200, max(tps_vals) * 0.8,
            "Swap activado\n(disco como RAM)",
            color="#E24B4A", fontsize=8)

    ax.set_title("Parte B — KV Cache: Longitud de Contexto vs Velocidad", fontsize=12, pad=12)
    ax.set_xlabel("Longitud del contexto (tokens)")
    ax.set_ylabel("Tokens por segundo (tok/s)")
    ax.set_xscale("log", base=2)
    ax.set_xticks(contextos)
    ax.set_xticklabels([str(c) for c in contextos])
    ax.set_ylim(0, max(tps_vals) * 1.4)

    plt.tight_layout()
    ruta = "report/capturas/grafica_contexto_vs_velocidad.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardada: {ruta}")


# ─────────────────────────────────────────────
# GRÁFICA 4 — Contexto vs Tiempo total (Parte B)
# ─────────────────────────────────────────────

def grafica_contexto_vs_tiempo():
    fig, ax = plt.subplots(figsize=(8, 5))

    contextos = [d["contexto"] for d in DATOS_KVCACHE]
    tiempos   = [d["tiempo_s"] for d in DATOS_KVCACHE]

    colores_barra = ["#0F6E56", "#0F6E56", "#EF9F27", "#E24B4A"]

    bars = ax.bar(
        [str(c) for c in contextos],
        tiempos,
        color=colores_barra,
        width=0.5,
        edgecolor="white"
    )

    for bar, t in zip(bars, tiempos):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 3,
            f"{t}s",
            ha="center", va="bottom", fontsize=9
        )

    ax.set_title("Parte B — KV Cache: Longitud de Contexto vs Tiempo Total", fontsize=12, pad=12)
    ax.set_xlabel("Longitud del contexto (tokens)")
    ax.set_ylabel("Tiempo total de respuesta (segundos)")
    ax.set_ylim(0, max(tiempos) * 1.15)

    # Leyenda de colores
    p1 = mpatches.Patch(color="#0F6E56", label="Normal (en RAM)")
    p2 = mpatches.Patch(color="#EF9F27", label="Lento (límite RAM)")
    p3 = mpatches.Patch(color="#E24B4A", label="Crítico (swap activado)")
    ax.legend(handles=[p1, p2, p3], fontsize=9)

    plt.tight_layout()
    ruta = "report/capturas/grafica_contexto_vs_tiempo.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] Guardada: {ruta}")


# ─────────────────────────────────────────────
# EJECUTAR TODAS
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Generando gráficas para el informe...")
    print("=" * 55)

    grafica_tamanio_vs_velocidad()
    grafica_tamanio_vs_calidad()
    grafica_contexto_vs_velocidad()
    grafica_contexto_vs_tiempo()

    print("\n[OK] Las 4 gráficas están en: report/capturas/")
    print("\nANTES DE CONTINUAR:")
    print("  Abre tu measurements.csv y verifica que los tok/s")
    print("  de Q8_0 y Q3_K_M coincidan con los valores en")
    print("  DATOS_CUANTIZACION al inicio de este script.")
    print("  Si son diferentes, edita el script y vuelve a correrlo.")
    print("=" * 55)
