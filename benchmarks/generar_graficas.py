"""
generar_graficas.py
-------------------
Genera TODAS las gráficas para el informe — Partes A y B.

Gráficas que produce:
  1. grafica_tamanio_vs_velocidad.png     — Parte A
  2. grafica_calidad_vs_velocidad.png     — Parte A
  3. grafica_tres_variables.png           — Parte A (tamaño + velocidad + calidad juntas)
  4. grafica_contexto_vs_velocidad.png    — Parte B
  5. grafica_contexto_vs_tiempo.png       — Parte B
  6. grafica_contexto_vs_ram.png          — Parte B (faltaba)

Cómo ejecutarlo:
  python benchmarks/generar_graficas.py
"""

import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# ─────────────────────────────────────────────
# DATOS REALES DE TU measurements.csv
# ─────────────────────────────────────────────

DATOS_CUANTIZACION = [
    {"modelo": "Q8_0",   "tamanio_gb": 3.19, "ram_gb": 7.30, "tps": 4.95,  "calidad": 2.2},
    {"modelo": "Q4_K_M", "tamanio_gb": 1.88, "ram_gb": 4.72, "tps": 27.87, "calidad": 2.6},
    {"modelo": "Q3_K_M", "tamanio_gb": 1.57, "ram_gb": 4.10, "tps": 6.73,  "calidad": 2.0},
]

DATOS_KVCACHE = [
    {"contexto": 512,   "tps": 3.81, "tiempo_s": 29.4,  "ram_gb": 7.30},
    {"contexto": 2048,  "tps": 2.59, "tiempo_s": 38.7,  "ram_gb": 7.30},
    {"contexto": 8192,  "tps": 5.60, "tiempo_s": 18.4,  "ram_gb": 7.30},
    {"contexto": 16384, "tps": 0.30, "tiempo_s": 358.2, "ram_gb": 9.10},
]

# ─────────────────────────────────────────────
# CONFIGURACIÓN VISUAL
# ─────────────────────────────────────────────

COLOR_Q8  = "#E24B4A"
COLOR_Q4  = "#534AB7"
COLOR_Q3  = "#0F6E56"
COLORES   = [COLOR_Q8, COLOR_Q4, COLOR_Q3]

os.makedirs("report/capturas", exist_ok=True)
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size":   11,
    "axes.grid":   True,
    "grid.alpha":  0.3,
    "figure.dpi":  150,
})

# ─────────────────────────────────────────────
# GRÁFICA 1 — Tamaño vs Velocidad
# ─────────────────────────────────────────────

def grafica_tamanio_vs_velocidad():
    fig, ax = plt.subplots(figsize=(7, 5))
    modelos  = [d["modelo"]     for d in DATOS_CUANTIZACION]
    tamanios = [d["tamanio_gb"] for d in DATOS_CUANTIZACION]
    tps_vals = [d["tps"]        for d in DATOS_CUANTIZACION]

    bars = ax.bar(modelos, tps_vals, color=COLORES, width=0.5, edgecolor="white")
    for bar, tam, tps in zip(bars, tamanios, tps_vals):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.3,
                f"{tps} tok/s\n({tam} GB)",
                ha="center", va="bottom", fontsize=9)

    ax.set_title("Parte A — Cuantización: Tamaño vs Velocidad", fontsize=12, pad=12)
    ax.set_xlabel("Nivel de Cuantización")
    ax.set_ylabel("Tokens por segundo (tok/s)")
    ax.set_ylim(0, max(tps_vals) * 1.35)
    plt.tight_layout()
    plt.savefig("report/capturas/grafica_tamanio_vs_velocidad.png", bbox_inches="tight")
    plt.close()
    print("[OK] grafica_tamanio_vs_velocidad.png")

# ─────────────────────────────────────────────
# GRÁFICA 2 — Calidad vs Velocidad
# ─────────────────────────────────────────────

def grafica_calidad_vs_velocidad():
    fig, ax1 = plt.subplots(figsize=(7, 5))
    modelos   = [d["modelo"]  for d in DATOS_CUANTIZACION]
    calidades = [d["calidad"] for d in DATOS_CUANTIZACION]
    tps_vals  = [d["tps"]     for d in DATOS_CUANTIZACION]
    x = range(len(modelos))

    bars = ax1.bar(x, calidades, color=COLORES, width=0.4, edgecolor="white")
    ax1.set_ylabel("Calidad promedio (0–3)")
    ax1.set_ylim(0, 3.5)
    ax1.set_xticks(x)
    ax1.set_xticklabels(modelos)

    for bar, cal in zip(bars, calidades):
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                 f"{cal}", ha="center", va="bottom", fontsize=10, fontweight="bold")

    ax2 = ax1.twinx()
    ax2.plot(x, tps_vals, color="#EF9F27", marker="o", linewidth=2, markersize=8)
    ax2.set_ylabel("Tokens por segundo (tok/s)", color="#EF9F27")
    ax2.tick_params(axis="y", labelcolor="#EF9F27")

    ax1.set_title("Parte A — Cuantización: Calidad vs Velocidad", fontsize=12, pad=12)
    ax1.set_xlabel("Nivel de Cuantización")

    p1 = mpatches.Patch(color="#534AB7", label="Calidad promedio (0-3)")
    p2 = plt.Line2D([0],[0], color="#EF9F27", marker="o", label="Tok/s")
    ax1.legend(handles=[p1, p2], loc="upper left", fontsize=9)

    plt.tight_layout()
    plt.savefig("report/capturas/grafica_calidad_vs_velocidad.png", bbox_inches="tight")
    plt.close()
    print("[OK] grafica_calidad_vs_velocidad.png")

# ─────────────────────────────────────────────
# GRÁFICA 3 — Tres variables juntas (FALTABA)
# ─────────────────────────────────────────────

def grafica_tres_variables():
    fig, ax = plt.subplots(figsize=(8, 5))
    modelos   = [d["modelo"]     for d in DATOS_CUANTIZACION]
    tamanios  = [d["tamanio_gb"] for d in DATOS_CUANTIZACION]
    tps_vals  = [d["tps"]        for d in DATOS_CUANTIZACION]
    calidades = [d["calidad"]    for d in DATOS_CUANTIZACION]
    ram_vals  = [d["ram_gb"]     for d in DATOS_CUANTIZACION]

    x = np.array(tamanios)
    y = np.array(tps_vals)
    # Tamaño del círculo proporcional a la calidad
    sizes  = [c * 400 for c in calidades]

    scatter = ax.scatter(x, y, s=sizes, c=COLORES, alpha=0.85, edgecolors="white", linewidth=1.5)

    # Etiquetas de cada punto
    for i, (xi, yi, mod, cal, tam, ram) in enumerate(
            zip(x, y, modelos, calidades, tamanios, ram_vals)):
        ax.annotate(
            f"{mod}\nTam: {tam} GB\nRAM: {ram} GB\nCal: {cal}/3",
            xy=(xi, yi),
            xytext=(12, 8),
            textcoords="offset points",
            fontsize=8,
            color="#333333",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white", alpha=0.7, edgecolor="#cccccc")
        )

    ax.set_title("Parte A — Tamaño · Velocidad · Calidad (tamaño del círculo = calidad)",
                 fontsize=11, pad=12)
    ax.set_xlabel("Tamaño del modelo en disco (GB)")
    ax.set_ylabel("Tokens por segundo (tok/s)")

    # Leyenda de tamaño de círculo
    for cal in [2.0, 2.6]:
        ax.scatter([], [], s=cal*400, c="#888888", alpha=0.6,
                   label=f"Calidad {cal}/3")
    ax.legend(title="Calidad (tamaño círculo)", fontsize=9, loc="upper right")

    plt.tight_layout()
    plt.savefig("report/capturas/grafica_tres_variables.png", bbox_inches="tight")
    plt.close()
    print("[OK] grafica_tres_variables.png")

# ─────────────────────────────────────────────
# GRÁFICA 4 — Contexto vs Velocidad
# ─────────────────────────────────────────────

def grafica_contexto_vs_velocidad():
    fig, ax = plt.subplots(figsize=(8, 5))
    contextos = [d["contexto"] for d in DATOS_KVCACHE]
    tps_vals  = [d["tps"]      for d in DATOS_KVCACHE]

    ax.plot(contextos, tps_vals, color="#534AB7", marker="o",
            linewidth=2.5, markersize=9)

    for ctx, tps in zip(contextos, tps_vals):
        ax.annotate(f"{tps} tok/s", xy=(ctx, tps),
                    xytext=(0, 12), textcoords="offset points",
                    ha="center", fontsize=9)

    ax.axvline(x=16384, color="#E24B4A", linestyle="--", alpha=0.7, linewidth=1.5)
    ax.text(14000, max(tps_vals)*0.75, "Swap\nactivado",
            color="#E24B4A", fontsize=8, ha="center")

    ax.set_title("Parte B — KV Cache: Longitud de Contexto vs Velocidad", fontsize=12, pad=12)
    ax.set_xlabel("Longitud del contexto (tokens)")
    ax.set_ylabel("Tokens por segundo (tok/s)")
    ax.set_xscale("log", base=2)
    ax.set_xticks(contextos)
    ax.set_xticklabels([str(c) for c in contextos])
    ax.set_ylim(0, max(tps_vals) * 1.4)

    plt.tight_layout()
    plt.savefig("report/capturas/grafica_contexto_vs_velocidad.png", bbox_inches="tight")
    plt.close()
    print("[OK] grafica_contexto_vs_velocidad.png")

# ─────────────────────────────────────────────
# GRÁFICA 5 — Contexto vs Tiempo
# ─────────────────────────────────────────────

def grafica_contexto_vs_tiempo():
    fig, ax = plt.subplots(figsize=(8, 5))
    contextos = [d["contexto"] for d in DATOS_KVCACHE]
    tiempos   = [d["tiempo_s"] for d in DATOS_KVCACHE]
    colores   = ["#0F6E56", "#0F6E56", "#EF9F27", "#E24B4A"]

    bars = ax.bar([str(c) for c in contextos], tiempos,
                  color=colores, width=0.5, edgecolor="white")

    for bar, t in zip(bars, tiempos):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
                f"{t}s", ha="center", va="bottom", fontsize=9)

    ax.set_title("Parte B — KV Cache: Longitud de Contexto vs Tiempo Total", fontsize=12, pad=12)
    ax.set_xlabel("Longitud del contexto (tokens)")
    ax.set_ylabel("Tiempo total de respuesta (segundos)")
    ax.set_ylim(0, max(tiempos) * 1.15)

    p1 = mpatches.Patch(color="#0F6E56", label="Normal (en RAM)")
    p2 = mpatches.Patch(color="#EF9F27", label="Lento (límite RAM)")
    p3 = mpatches.Patch(color="#E24B4A", label="Crítico (swap activado)")
    ax.legend(handles=[p1, p2, p3], fontsize=9)

    plt.tight_layout()
    plt.savefig("report/capturas/grafica_contexto_vs_tiempo.png", bbox_inches="tight")
    plt.close()
    print("[OK] grafica_contexto_vs_tiempo.png")

# ─────────────────────────────────────────────
# GRÁFICA 6 — Contexto vs RAM (FALTABA)
# ─────────────────────────────────────────────

def grafica_contexto_vs_ram():
    fig, ax = plt.subplots(figsize=(8, 5))
    contextos = [d["contexto"] for d in DATOS_KVCACHE]
    ram_vals  = [d["ram_gb"]   for d in DATOS_KVCACHE]

    ax.fill_between(contextos, ram_vals, alpha=0.15, color="#534AB7")
    ax.plot(contextos, ram_vals, color="#534AB7", marker="o",
            linewidth=2.5, markersize=9)

    for ctx, ram in zip(contextos, ram_vals):
        ax.annotate(f"{ram} GB", xy=(ctx, ram),
                    xytext=(0, 12), textcoords="offset points",
                    ha="center", fontsize=9)

    # Línea de límite de RAM disponible
    ax.axhline(y=7.9, color="#E24B4A", linestyle="--", alpha=0.8, linewidth=1.5)
    ax.text(contextos[0] + 100, 8.0, "RAM disponible máxima (7.9 GB)",
            color="#E24B4A", fontsize=8)

    ax.set_title("Parte B — KV Cache: Longitud de Contexto vs RAM Usada", fontsize=12, pad=12)
    ax.set_xlabel("Longitud del contexto (tokens)")
    ax.set_ylabel("RAM usada por llama-server.exe (GB)")
    ax.set_xscale("log", base=2)
    ax.set_xticks(contextos)
    ax.set_xticklabels([str(c) for c in contextos])
    ax.set_ylim(0, 12)

    plt.tight_layout()
    plt.savefig("report/capturas/grafica_contexto_vs_ram.png", bbox_inches="tight")
    plt.close()
    print("[OK] grafica_contexto_vs_ram.png")

# ─────────────────────────────────────────────
# EJECUTAR TODAS
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  Generando 6 gráficas para el informe...")
    print("=" * 55 + "\n")

    grafica_tamanio_vs_velocidad()
    grafica_calidad_vs_velocidad()
    grafica_tres_variables()
    grafica_contexto_vs_velocidad()
    grafica_contexto_vs_tiempo()
    grafica_contexto_vs_ram()

    print("\n[OK] Las 6 gráficas están en: report/capturas/")
    print("=" * 55)
