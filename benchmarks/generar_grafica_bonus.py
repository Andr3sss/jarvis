"""
generar_grafica_bonus.py
------------------------
Genera las graficas comparativas entre Llama 3.2 3B y Phi-4-mini
para la seccion de bonus del proyecto Jarvis.

Graficas que produce:
  1. grafica_comparativa_familias.png  — velocidad y calidad lado a lado
  2. grafica_comparativa_tamano.png    — tamaño vs velocidad ambas familias

Como ejecutarlo:
  python benchmarks/generar_grafica_bonus.py
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

os.makedirs("report/capturas", exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size":   11,
    "axes.grid":   True,
    "grid.alpha":  0.3,
    "figure.dpi":  150,
})

# ─────────────────────────────────────────────
# DATOS REALES
# ─────────────────────────────────────────────

DATOS = [
    # Llama 3.2 3B
    {"familia": "Llama 3.2 3B", "cuant": "Q8_0",   "tamanio": 3.19, "ram": 7.30, "tps": 4.95,  "calidad": 2.2, "color": "#534AB7"},
    {"familia": "Llama 3.2 3B", "cuant": "Q4_K_M", "tamanio": 1.88, "ram": 4.72, "tps": 27.87, "calidad": 2.6, "color": "#534AB7"},
    {"familia": "Llama 3.2 3B", "cuant": "Q3_K_M", "tamanio": 1.57, "ram": 4.10, "tps": 6.73,  "calidad": 2.0, "color": "#534AB7"},
    # Phi-4-mini
    {"familia": "Phi-4-mini",   "cuant": "Q8_0",   "tamanio": 3.80, "ram": 7.20, "tps": 4.95,  "calidad": 2.2, "color": "#0F6E56"},
    {"familia": "Phi-4-mini",   "cuant": "Q4_K_M", "tamanio": 2.32, "ram": 4.50, "tps": 22.77, "calidad": 2.6, "color": "#0F6E56"},
]

# ─────────────────────────────────────────────
# GRAFICA 1 — Comparativa velocidad y calidad
# ─────────────────────────────────────────────

def grafica_comparativa_familias():
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    fig.suptitle("Comparativa de familias: Llama 3.2 3B vs Phi-4-mini",
                 fontsize=13, fontweight="bold", y=1.02)

    etiquetas = [f"{d['familia']}\n{d['cuant']}" for d in DATOS]
    tps_vals  = [d["tps"]     for d in DATOS]
    cal_vals  = [d["calidad"] for d in DATOS]
    colores   = [d["color"]   for d in DATOS]
    x         = np.arange(len(etiquetas))
    ancho     = 0.6

    # Panel izquierdo: velocidad
    bars1 = ax1.bar(x, tps_vals, width=ancho, color=colores,
                    edgecolor="white", linewidth=0.8)
    ax1.set_title("Velocidad de inferencia (tok/s)", fontsize=11, pad=10)
    ax1.set_ylabel("Tokens por segundo")
    ax1.set_xticks(x)
    ax1.set_xticklabels(etiquetas, fontsize=8)
    ax1.set_ylim(0, max(tps_vals) * 1.25)

    for bar, val in zip(bars1, tps_vals):
        ax1.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.3,
                 f"{val}", ha="center", va="bottom", fontsize=9)

    # Linea separadora entre familias
    ax1.axvline(x=2.5, color="#888780", linestyle="--",
                alpha=0.5, linewidth=1)
    ax1.text(1.0,  max(tps_vals)*1.18, "Llama 3.2 3B",
             ha="center", fontsize=9, color="#534AB7", fontweight="bold")
    ax1.text(3.5, max(tps_vals)*1.18, "Phi-4-mini",
             ha="center", fontsize=9, color="#0F6E56", fontweight="bold")

    # Panel derecho: calidad
    bars2 = ax2.bar(x, cal_vals, width=ancho, color=colores,
                    edgecolor="white", linewidth=0.8)
    ax2.set_title("Calidad promedio (rubrica 0-3)", fontsize=11, pad=10)
    ax2.set_ylabel("Puntuacion promedio")
    ax2.set_xticks(x)
    ax2.set_xticklabels(etiquetas, fontsize=8)
    ax2.set_ylim(0, 3.5)

    for bar, val in zip(bars2, cal_vals):
        ax2.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 0.05,
                 f"{val}", ha="center", va="bottom",
                 fontsize=10, fontweight="bold")

    ax2.axvline(x=2.5, color="#888780", linestyle="--",
                alpha=0.5, linewidth=1)
    ax2.text(1.0,  3.35, "Llama 3.2 3B",
             ha="center", fontsize=9, color="#534AB7", fontweight="bold")
    ax2.text(3.5, 3.35, "Phi-4-mini",
             ha="center", fontsize=9, color="#0F6E56", fontweight="bold")

    plt.tight_layout()
    ruta = "report/capturas/grafica_comparativa_familias.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] {ruta}")


# ─────────────────────────────────────────────
# GRAFICA 2 — Tamaño vs Velocidad ambas familias
# ─────────────────────────────────────────────

def grafica_comparativa_tamano():
    fig, ax = plt.subplots(figsize=(9, 6))

    llama = [d for d in DATOS if d["familia"] == "Llama 3.2 3B"]
    phi   = [d for d in DATOS if d["familia"] == "Phi-4-mini"]

    # Scatter Llama
    for d in llama:
        size = d["calidad"] * 350
        ax.scatter(d["tamanio"], d["tps"], s=size,
                   color="#534AB7", alpha=0.85,
                   edgecolors="white", linewidth=1.5, zorder=3)
        ax.annotate(
            f"Llama {d['cuant']}\n{d['tps']} tok/s",
            xy=(d["tamanio"], d["tps"]),
            xytext=(10, 8), textcoords="offset points",
            fontsize=8, color="#333333",
            bbox=dict(boxstyle="round,pad=0.3",
                      facecolor="white", alpha=0.8,
                      edgecolor="#CCCAC4")
        )

    # Scatter Phi-4-mini
    for d in phi:
        size = d["calidad"] * 350
        ax.scatter(d["tamanio"], d["tps"], s=size,
                   color="#0F6E56", alpha=0.85,
                   edgecolors="white", linewidth=1.5, zorder=3)
        ax.annotate(
            f"Phi {d['cuant']}\n{d['tps']} tok/s",
            xy=(d["tamanio"], d["tps"]),
            xytext=(10, 8), textcoords="offset points",
            fontsize=8, color="#333333",
            bbox=dict(boxstyle="round,pad=0.3",
                      facecolor="white", alpha=0.8,
                      edgecolor="#CCCAC4")
        )

    ax.set_title("Tamaño en disco vs Velocidad de inferencia\n"
                 "(tamaño del punto proporcional a la calidad)",
                 fontsize=12, pad=12)
    ax.set_xlabel("Tamaño en disco (GB)")
    ax.set_ylabel("Tokens por segundo (tok/s)")

    p1 = mpatches.Patch(color="#534AB7", label="Llama 3.2 3B (Meta)")
    p2 = mpatches.Patch(color="#0F6E56", label="Phi-4-mini (Microsoft)")
    ax.legend(handles=[p1, p2], fontsize=10, loc="upper right")

    plt.tight_layout()
    ruta = "report/capturas/grafica_comparativa_tamano.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] {ruta}")


# ─────────────────────────────────────────────
# GRAFICA 3 — Tabla resumen visual
# ─────────────────────────────────────────────

def grafica_tabla_resumen():
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.axis("off")

    columnas = ["Familia", "Modelo", "Cuant.",
                "Tamaño", "RAM", "Tok/s", "Calidad"]

    filas = [
        ["Llama 3.2 3B\n(Meta)", "llama3.2:3b-instruct",
         "Q8_0",   "3.19 GB", "7.30 GB", "4.95",  "2.2/3.0"],
        ["Llama 3.2 3B\n(Meta)", "llama3.2:3b-instruct",
         "Q4_K_M", "1.88 GB", "4.72 GB", "27.87", "2.6/3.0"],
        ["Llama 3.2 3B\n(Meta)", "llama3.2:3b-instruct",
         "Q3_K_M", "1.57 GB", "4.10 GB", "6.73",  "2.0/3.0"],
        ["Phi-4-mini\n(Microsoft)", "phi4-mini:3.8b",
         "Q8_0",   "3.80 GB", "7.20 GB", "4.95",  "2.2/3.0"],
        ["Phi-4-mini\n(Microsoft)", "phi4-mini:3.8b",
         "Q4_K_M", "2.32 GB", "4.50 GB", "22.77", "2.6/3.0"],
    ]

    tabla = ax.table(
        cellText=filas,
        colLabels=columnas,
        loc="center",
        cellLoc="center"
    )
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(9)
    tabla.scale(1, 2.2)

    # Color cabecera
    for j in range(len(columnas)):
        tabla[0, j].set_facecolor("#534AB7")
        tabla[0, j].set_text_props(color="white", fontweight="bold")

    # Color filas Llama
    for i in range(1, 4):
        for j in range(len(columnas)):
            tabla[i, j].set_facecolor("#EEEDFE")

    # Color filas Phi
    for i in range(4, 6):
        for j in range(len(columnas)):
            tabla[i, j].set_facecolor("#E1F5EE")

    ax.set_title("Tabla comparativa completa: Llama 3.2 3B vs Phi-4-mini",
                 fontsize=12, pad=16, fontweight="bold")

    plt.tight_layout()
    ruta = "report/capturas/grafica_tabla_comparativa.png"
    plt.savefig(ruta, bbox_inches="tight")
    plt.close()
    print(f"[OK] {ruta}")


if __name__ == "__main__":
    print("=" * 55)
    print("  Generando graficas comparativas de familias...")
    print("=" * 55 + "\n")

    grafica_comparativa_familias()
    grafica_comparativa_tamano()
    grafica_tabla_resumen()

    print("\n[OK] Las 3 graficas estan en: report/capturas/")
    print("=" * 55)
