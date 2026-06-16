"""
herramientas.py — VERSION CON 6 HERRAMIENTAS
---------------------------------------------
Define las 6 herramientas externas que Jarvis puede usar:
  1. obtener_clima        — Open-Meteo API
  2. precio_cripto        — CoinGecko API
  3. info_github_repo     — GitHub API
  4. eventos_de_hoy       — Google Calendar (eventos hoy)
  5. eventos_proximos     — Google Calendar (proximos N dias)
  6. buscar_eventos       — Google Calendar (busqueda por palabra clave)
"""

import requests

from gestor_notas import (
    crear_nota, leer_nota, listar_notas, eliminar_nota,
    crear_tarea, completar_tarea, listar_tareas_pendientes,
    listar_tareas_completadas, eliminar_tarea
)


import json
import sys
import os
from typing import Optional

# Importar funciones de calendario (estan en el mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calendario_google import (
    eventos_de_hoy, eventos_proximos, buscar_eventos,
    crear_evento, editar_evento, eliminar_evento, listar_eventos_con_ids
)

# ─────────────────────────────────────────────
# HERRAMIENTA 1: CLIMA (Open-Meteo)
# ─────────────────────────────────────────────

CIUDADES_COORDS = {
    "quito":        (-0.18, -78.47),
    "guayaquil":    (-2.20, -79.90),
    "cuenca":       (-2.90, -79.00),
    "bogota":       (4.71,  -74.07),
    "lima":         (-12.05, -77.04),
    "buenos aires": (-34.61, -58.38),
    "madrid":       (40.42, -3.70),
    "barcelona":    (41.39, 2.16),
    "mexico":       (19.43, -99.13),
    "ciudad de mexico": (19.43, -99.13),
    "santiago":     (-33.45, -70.66),
    "caracas":      (10.49, -66.87),
    "la paz":       (-16.50, -68.13),
    "asuncion":     (-25.30, -57.63),
    "montevideo":   (-34.90, -56.16),
    "san jose":     (9.93,  -84.08),
    "panama":       (8.98,  -79.52),
    "habana":       (23.13, -82.38),
    "san juan":     (18.47, -66.11),
    "tegucigalpa":  (14.07, -87.19),
    "managua":      (12.13, -86.25),
    "san salvador": (13.69, -89.22),
    "guatemala":    (14.63, -90.51),
    "new york":     (40.71, -74.01),
    "london":       (51.51, -0.13),
    "paris":        (48.85, 2.35),
    "tokyo":        (35.69, 139.69),
}

def obtener_clima(ciudad: str) -> dict:
    ciudad_norm = ciudad.lower().strip()
    if ciudad_norm not in CIUDADES_COORDS:
        return {
            "error": f"Ciudad no disponible: {ciudad}",
            "ciudades_disponibles": list(CIUDADES_COORDS.keys())[:10]
        }

    lat, lon = CIUDADES_COORDS[ciudad_norm]
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude":  lat,
        "longitude": lon,
        "current":   "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
        "timezone":  "auto"
    }

    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        datos = r.json().get("current", {})

        codigo = datos.get("weather_code", 0)
        weather_map = {
            0: "Despejado", 1: "Mayormente despejado", 2: "Parcialmente nublado",
            3: "Nublado", 45: "Niebla", 51: "Llovizna ligera",
            61: "Lluvia ligera", 63: "Lluvia moderada", 65: "Lluvia intensa",
            71: "Nevada ligera", 80: "Aguaceros", 95: "Tormenta"
        }
        descripcion = weather_map.get(codigo, f"Codigo {codigo}")

        return {
            "ciudad":      ciudad.title(),
            "temperatura": f"{datos.get('temperature_2m', 0)} C",
            "humedad":     f"{datos.get('relative_humidity_2m', 0)}%",
            "viento":      f"{datos.get('wind_speed_10m', 0)} km/h",
            "condicion":   descripcion,
            "hora_local":  datos.get("time", "")
        }
    except Exception as e:
        return {"error": f"Error consultando clima: {str(e)}"}


# ─────────────────────────────────────────────
# HERRAMIENTA 2: PRECIO CRIPTO (CoinGecko)
# ─────────────────────────────────────────────

CRIPTOS_MAP = {
    "bitcoin":  "bitcoin",  "btc": "bitcoin",
    "ethereum": "ethereum", "eth": "ethereum",
    "solana":   "solana",   "sol": "solana",
    "cardano":  "cardano",  "ada": "cardano",
    "dogecoin": "dogecoin", "doge": "dogecoin",
    "ripple":   "ripple",   "xrp": "ripple",
    "binance":  "binancecoin", "bnb": "binancecoin",
    "polkadot": "polkadot", "dot": "polkadot",
    "litecoin": "litecoin", "ltc": "litecoin",
}

def precio_cripto(cripto: str, moneda: str = "usd") -> dict:
    cripto_norm = cripto.lower().strip()
    moneda_norm = moneda.lower().strip()
    cripto_id   = CRIPTOS_MAP.get(cripto_norm, cripto_norm)

    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids":           cripto_id,
        "vs_currencies": moneda_norm,
        "include_24hr_change": "true",
        "include_market_cap":  "true"
    }

    try:
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        datos = r.json()

        if cripto_id not in datos:
            return {"error": f"Criptomoneda no encontrada: {cripto}"}

        info = datos[cripto_id]
        return {
            "criptomoneda": cripto.upper(),
            "moneda":       moneda.upper(),
            "precio":       info.get(moneda_norm, 0),
            "cambio_24h":   f"{info.get(moneda_norm + '_24h_change', 0):.2f}%",
            "market_cap":   info.get(moneda_norm + "_market_cap", 0)
        }
    except Exception as e:
        return {"error": f"Error consultando CoinGecko: {str(e)}"}


# ─────────────────────────────────────────────
# HERRAMIENTA 3: GITHUB REPO INFO
# ─────────────────────────────────────────────

def info_github_repo(owner: str, repo: str) -> dict:
    owner = owner.strip()
    repo  = repo.strip()
    url   = f"https://api.github.com/repos/{owner}/{repo}"

    try:
        r = requests.get(url, timeout=10, headers={"Accept": "application/vnd.github.v3+json"})
        if r.status_code == 404:
            return {"error": f"Repositorio no encontrado: {owner}/{repo}"}
        if r.status_code == 403:
            return {"error": "Limite de API de GitHub alcanzado (60/hora sin auth)"}
        r.raise_for_status()
        datos = r.json()

        return {
            "nombre_completo": datos.get("full_name", ""),
            "descripcion":     datos.get("description", "Sin descripcion"),
            "lenguaje":        datos.get("language", "N/A"),
            "estrellas":       datos.get("stargazers_count", 0),
            "forks":           datos.get("forks_count", 0),
            "issues_abiertos": datos.get("open_issues_count", 0),
            "ultima_actualizacion": datos.get("updated_at", ""),
            "url":             datos.get("html_url", "")
        }
    except Exception as e:
        return {"error": f"Error consultando GitHub: {str(e)}"}


# ─────────────────────────────────────────────
# REGISTRO DE LAS 6 HERRAMIENTAS
# ─────────────────────────────────────────────

HERRAMIENTAS_DISPONIBLES = {
    "obtener_clima": {
        "funcion":     obtener_clima,
        "descripcion": "Obtiene el clima actual de una ciudad (temperatura, humedad, viento, condicion).",
        "parametros": {
            "ciudad": "Nombre de la ciudad (ej: 'Quito', 'Madrid', 'Tokyo')"
        },
        "ejemplo": '{"tool": "obtener_clima", "parametros": {"ciudad": "Quito"}}'
    },
    "precio_cripto": {
        "funcion":     precio_cripto,
        "descripcion": "Obtiene el precio actual de una criptomoneda en cualquier moneda fiat.",
        "parametros": {
            "cripto": "Nombre o simbolo de la criptomoneda (ej: 'bitcoin', 'BTC', 'ethereum')",
            "moneda": "Codigo de moneda fiat (ej: 'usd', 'eur', 'mxn'). Default: 'usd'"
        },
        "ejemplo": '{"tool": "precio_cripto", "parametros": {"cripto": "bitcoin", "moneda": "usd"}}'
    },
    "info_github_repo": {
        "funcion":     info_github_repo,
        "descripcion": "Obtiene informacion publica de un repositorio de GitHub (estrellas, lenguaje, issues).",
        "parametros": {
            "owner": "Usuario u organizacion duena del repo (ej: 'ollama')",
            "repo":  "Nombre del repositorio (ej: 'ollama')"
        },
        "ejemplo": '{"tool": "info_github_repo", "parametros": {"owner": "ollama", "repo": "ollama"}}'
    },
    "eventos_de_hoy": {
        "funcion":     eventos_de_hoy,
        "descripcion": "Lista los eventos del calendario del usuario para hoy. Incluye eventos academicos, partidos del mundial, festivos y eventos personales.",
        "parametros": {},
        "ejemplo": '{"tool": "eventos_de_hoy", "parametros": {}}'
    },
    "eventos_proximos": {
        "funcion":     eventos_proximos,
        "descripcion": "Lista los proximos eventos del calendario del usuario en los proximos N dias.",
        "parametros": {
            "dias": "Numero de dias hacia adelante a consultar (1-30). Default: 7"
        },
        "ejemplo": '{"tool": "eventos_proximos", "parametros": {"dias": 7}}'
    },
    "buscar_eventos": {
        "funcion":     buscar_eventos,
        "descripcion": "Busca eventos del calendario que contengan una palabra clave en el titulo (proximos 90 dias).",
        "parametros": {
            "palabra_clave": "Texto a buscar en titulos de eventos (ej: 'Ecuador', 'partido', 'examen', 'reunion')"
        },
        "ejemplo": '{"tool": "buscar_eventos", "parametros": {"palabra_clave": "Ecuador"}}'
    },

    "crear_nota": {
        "funcion":     crear_nota,
        "descripcion": "Crea o actualiza una nota personal con titulo y contenido.",
        "parametros": {
            "titulo":    "Titulo de la nota (ej: 'Apuntes de Python')",
            "contenido": "Contenido completo de la nota"
        },
        "ejemplo": '{"tool": "crear_nota", "parametros": {"titulo": "Mi nota", "contenido": "Contenido aqui"}}'
    },
    "leer_nota": {
        "funcion":     leer_nota,
        "descripcion": "Lee y devuelve el contenido de una nota por su titulo.",
        "parametros": {
            "titulo": "Titulo exacto de la nota a leer"
        },
        "ejemplo": '{"tool": "leer_nota", "parametros": {"titulo": "Mi nota"}}'
    },
    "listar_notas": {
        "funcion":     listar_notas,
        "descripcion": "Lista todas las notas guardadas con sus titulos y una preview.",
        "parametros": {},
        "ejemplo": '{"tool": "listar_notas", "parametros": {}}'
    },
    "eliminar_nota": {
        "funcion":     eliminar_nota,
        "descripcion": "Elimina una nota por su titulo.",
        "parametros": {
            "titulo": "Titulo de la nota a eliminar"
        },
        "ejemplo": '{"tool": "eliminar_nota", "parametros": {"titulo": "Mi nota"}}'
    },
    "crear_tarea": {
        "funcion":     crear_tarea,
        "descripcion": "Crea una nueva tarea pendiente con titulo, descripcion opcional y fecha limite opcional.",
        "parametros": {
            "titulo":       "Titulo de la tarea (ej: 'Estudiar para el examen')",
            "descripcion":  "Descripcion detallada de la tarea (opcional)",
            "fecha_limite": "Fecha limite en formato DD/MM/YYYY (opcional)"
        },
        "ejemplo": '{"tool": "crear_tarea", "parametros": {"titulo": "Estudiar", "descripcion": "Repasar capitulos 1 al 5", "fecha_limite": "20/06/2026"}}'
    },
    "completar_tarea": {
        "funcion":     completar_tarea,
        "descripcion": "Marca una tarea pendiente como completada.",
        "parametros": {
            "titulo": "Titulo exacto de la tarea a completar"
        },
        "ejemplo": '{"tool": "completar_tarea", "parametros": {"titulo": "Estudiar"}}'
    },
    "listar_tareas_pendientes": {
        "funcion":     listar_tareas_pendientes,
        "descripcion": "Lista todas las tareas que estan pendientes de completar.",
        "parametros": {},
        "ejemplo": '{"tool": "listar_tareas_pendientes", "parametros": {}}'
    },
    "listar_tareas_completadas": {
        "funcion":     listar_tareas_completadas,
        "descripcion": "Lista todas las tareas que ya fueron completadas.",
        "parametros": {},
        "ejemplo": '{"tool": "listar_tareas_completadas", "parametros": {}}'
    },
    "eliminar_tarea": {
        "funcion":     eliminar_tarea,
        "descripcion": "Elimina una tarea por su titulo (pendiente o completada).",
        "parametros": {
            "titulo": "Titulo exacto de la tarea a eliminar"
        },
        "ejemplo": '{"tool": "eliminar_tarea", "parametros": {"titulo": "Estudiar"}}'
    },

    "crear_evento_calendario": {
        "funcion":     crear_evento,
        "descripcion": "Crea un nuevo evento en Google Calendar del usuario.",
        "parametros": {
            "titulo":      "Nombre del evento (ej: 'Examen de Machine Learning')",
            "fecha":       "Fecha en formato DD/MM/YYYY (ej: '20/06/2026')",
            "hora_inicio": "Hora de inicio HH:MM (ej: '09:00'). Opcional, si no se pone es todo el dia",
            "hora_fin":    "Hora de fin HH:MM (ej: '11:00'). Opcional",
            "descripcion": "Descripcion adicional del evento. Opcional"
        },
        "ejemplo": '{"tool": "crear_evento_calendario", "parametros": {"titulo": "Examen", "fecha": "20/06/2026", "hora_inicio": "09:00", "hora_fin": "11:00"}}'
    },

    "listar_eventos_con_ids": {
        "funcion":     listar_eventos_con_ids,
        "descripcion": "Lista los proximos eventos del calendario principal con sus IDs para poder editarlos o eliminarlos.",
        "parametros": {
            "dias": "Numero de dias hacia adelante a consultar (default: 7)"
        },
        "ejemplo": '{"tool": "listar_eventos_con_ids", "parametros": {"dias": 7}}'
    },
    "editar_evento_calendario": {
        "funcion":     editar_evento,
        "descripcion": "Edita un evento existente en Google Calendar. Requiere el ID del evento obtenido con listar_eventos_con_ids.",
        "parametros": {
            "evento_id":        "ID unico del evento a editar (obligatorio)",
            "nuevo_titulo":     "Nuevo titulo del evento (opcional)",
            "nueva_fecha":      "Nueva fecha en formato DD/MM/YYYY (opcional)",
            "nueva_hora_inicio": "Nueva hora de inicio HH:MM (opcional)",
            "nueva_hora_fin":   "Nueva hora de fin HH:MM (opcional)",
            "nueva_descripcion": "Nueva descripcion del evento (opcional)"
        },
        "ejemplo": '{"tool": "editar_evento_calendario", "parametros": {"evento_id": "abc123", "nuevo_titulo": "Nuevo nombre"}}'
    },
    "eliminar_evento_calendario": {
        "funcion":     eliminar_evento,
        "descripcion": "Elimina un evento de Google Calendar por su ID. Requiere el ID obtenido con listar_eventos_con_ids.",
        "parametros": {
            "evento_id": "ID unico del evento a eliminar (obligatorio)"
        },
        "ejemplo": '{"tool": "eliminar_evento_calendario", "parametros": {"evento_id": "abc123"}}'
    }

    
}


def listar_herramientas_para_prompt() -> str:
    texto = "HERRAMIENTAS DISPONIBLES:\n\n"
    for nombre, info in HERRAMIENTAS_DISPONIBLES.items():
        texto += f"- {nombre}: {info['descripcion']}\n"
        if info["parametros"]:
            texto += f"  Parametros:\n"
            for param, desc in info["parametros"].items():
                texto += f"    * {param}: {desc}\n"
        else:
            texto += f"  Parametros: ninguno\n"
        texto += f"  Ejemplo: {info['ejemplo']}\n\n"
    return texto


# ─────────────────────────────────────────────
# PRUEBAS RAPIDAS
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 60)
    print("  PROBANDO LAS 6 HERRAMIENTAS")
    print("=" * 60)

    print("\n[1/6] Clima en Quito:")
    print(json.dumps(obtener_clima("Quito"), indent=2, ensure_ascii=False))

    print("\n[2/6] Precio del Bitcoin en USD:")
    print(json.dumps(precio_cripto("bitcoin", "usd"), indent=2, ensure_ascii=False))

    print("\n[3/6] Info de github.com/ollama/ollama:")
    print(json.dumps(info_github_repo("ollama", "ollama"), indent=2, ensure_ascii=False))

    print("\n[4/6] Eventos de hoy:")
    print(json.dumps(eventos_de_hoy(), indent=2, ensure_ascii=False))

    print("\n[5/6] Eventos proximos 3 dias:")
    print(json.dumps(eventos_proximos(3), indent=2, ensure_ascii=False))

    print("\n[6/6] Buscar 'Ecuador':")
    print(json.dumps(buscar_eventos("Ecuador"), indent=2, ensure_ascii=False))

    print("\n" + "=" * 60)
    print("  Si las 6 funcionaron, todo esta listo para Jarvis!")
    print("=" * 60)
