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
import json
import sys
import os
from typing import Optional

# Importar funciones de calendario (estan en el mismo directorio)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from calendario_google import eventos_de_hoy, eventos_proximos, buscar_eventos


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
