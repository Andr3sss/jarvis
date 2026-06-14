"""
calendario_google.py — VERSION FINAL CON VISTA BONITA
------------------------------------------------------
Herramienta de Google Calendar para Jarvis.

Dos modos de uso:
  1. Como modulo (Jarvis lo importa): devuelve JSON estructurado
  2. Ejecucion directa: muestra vista bonita tipo agenda
"""

import os
import sys
import datetime
import re

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("[ERROR] Faltan librerias de Google.")
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
# Zona horaria de Ecuador (UTC-5)
ZONA_LOCAL = datetime.timezone(datetime.timedelta(hours=-5))
DIR_SCRIPT       = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(DIR_SCRIPT, 'credentials.json')
TOKEN_PATH       = os.path.join(DIR_SCRIPT, 'token.json')

# Mapeo de calendarios a categorias para agrupar y mostrar bonito
CATEGORIAS_CALENDARIO = {
    "Calendario (Canvas)": ("UNIVERSIDAD",      "academico"),
    "World Cup":           ("MUNDIAL 2026",     "deportes"),
    "Festivos en Ecuador": ("FESTIVOS",         "festivo"),
}


# ─────────────────────────────────────────────
# AUTENTICACION
# ─────────────────────────────────────────────

def autenticar():
    creds = None
    if os.path.exists(TOKEN_PATH):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            if not os.path.exists(CREDENTIALS_PATH):
                print(f"[ERROR] No se encontro credentials.json")
                sys.exit(1)
            flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────

def ahora_utc_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')

def fecha_utc_futura(dias):
    futura = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=dias)
    return futura.isoformat().replace('+00:00', 'Z')

def obtener_ids_calendarios(servicio):
    try:
        lista = servicio.calendarList().list().execute()
        return [(c['id'], c.get('summary', 'sin nombre')) for c in lista.get('items', [])]
    except Exception:
        return [('primary', 'primary')]


def categorizar_calendario(nombre):
    """Devuelve (etiqueta_corta, categoria) para un nombre de calendario."""
    for clave, (etiqueta, categoria) in CATEGORIAS_CALENDARIO.items():
        if clave in nombre:
            return etiqueta, categoria
    return "PERSONAL", "personal"


def limpiar_titulo(titulo):
    """Quita texto entre corchetes y emojis para una version mas limpia."""
    # Quitar [MACHINE LEARNING 06-SIN-A] y similares
    titulo_limpio = re.sub(r'\[[^\]]+\]', '', titulo).strip()
    return titulo_limpio if titulo_limpio else titulo


def formato_partido_mundial(titulo):
    """Convierte '🇨🇮 Ivory Coast - 🇪🇨 Ecuador' a 'Ivory Coast vs Ecuador'."""
    titulo_sin_emoji = re.sub(r'[\U0001F1E6-\U0001F1FF]+\s*', '', titulo)
    titulo_sin_emoji = titulo_sin_emoji.replace(' - ', ' vs ').strip()
    return titulo_sin_emoji


def formatear_fecha_evento(evento):
    start = evento.get('start', {})
    fecha_str = start.get('dateTime', start.get('date', ''))
    if not fecha_str:
        return "Sin fecha", None
    try:
        if 'T' in fecha_str:
            dt = datetime.datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            # Convertir a hora local de Ecuador (UTC-5)
            dt_local = dt.astimezone(ZONA_LOCAL)
            return dt_local.strftime('%d/%m/%Y a las %H:%M'), dt_local
        else:
            dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
            # Eventos de dia completo: marcar como zona local
            dt = dt.replace(tzinfo=ZONA_LOCAL)
            return dt.strftime('%d/%m/%Y (todo el dia)'), dt
    except Exception:
        return fecha_str, None


def resumir_evento(evento, nombre_calendario):
    """
    Devuelve un dict simple optimizado para que el modelo Llama lo entienda
    """
    fecha_legible, fecha_obj = formatear_fecha_evento(evento)
    etiqueta, categoria      = categorizar_calendario(nombre_calendario)
    titulo_raw               = evento.get('summary', '(sin titulo)')

    # Limpiar titulo segun categoria
    if categoria == "deportes":
        titulo = formato_partido_mundial(titulo_raw)
    elif categoria == "academico":
        titulo = limpiar_titulo(titulo_raw)
    else:
        titulo = titulo_raw

    return {
        "titulo":     titulo,
        "fecha":      fecha_legible,
        "tipo":       etiqueta,
        "categoria":  categoria,
        "_fecha_obj": fecha_obj,
        "_titulo_original": titulo_raw,
    }


def consultar_todos_calendarios(servicio, time_min, time_max, query=None, max_per_cal=10):
    todos_eventos = []
    calendarios   = obtener_ids_calendarios(servicio)

    for cal_id, cal_nombre in calendarios:
        try:
            params = {
                'calendarId':   cal_id,
                'timeMin':      time_min,
                'timeMax':      time_max,
                'maxResults':   max_per_cal,
                'singleEvents': True,
                'orderBy':      'startTime'
            }
            if query:
                params['q'] = query
            resultado = servicio.events().list(**params).execute()
            for ev in resultado.get('items', []):
                todos_eventos.append(resumir_evento(ev, cal_nombre))
        except Exception:
            continue

    todos_eventos.sort(key=lambda ev: ev.get('_fecha_obj') or datetime.datetime.max.replace(tzinfo=datetime.timezone.utc))
    return todos_eventos


# ─────────────────────────────────────────────
# VISTA BONITA TIPO AGENDA
# ─────────────────────────────────────────────

ICONOS_TIPO = {
    "UNIVERSIDAD": "🎓",
    "MUNDIAL 2026": "⚽",
    "FESTIVOS":   "🎉",
    "PERSONAL":   "📌",
}

def imprimir_agenda(titulo, eventos):
    """Imprime los eventos en formato agenda visualmente atractivo."""
    print("\n" + "═" * 60)
    print(f"  📅 {titulo}")
    print("═" * 60)

    if not eventos:
        print("\n   No hay eventos en este rango.\n")
        return

    # Agrupar por tipo
    grupos = {}
    for ev in eventos:
        tipo = ev["tipo"]
        if tipo not in grupos:
            grupos[tipo] = []
        grupos[tipo].append(ev)

    # Orden de presentacion
    orden = ["UNIVERSIDAD", "MUNDIAL 2026", "FESTIVOS", "PERSONAL"]
    for tipo in orden:
        if tipo not in grupos:
            continue
        icono = ICONOS_TIPO.get(tipo, "•")
        print(f"\n  {icono} {tipo}")
        print("  " + "─" * 56)

        for ev in grupos[tipo]:
            # Hora visible si hay
            fecha = ev["fecha"]
            if "a las" in fecha:
                hora = fecha.split("a las")[1].strip()
                dia  = fecha.split("a las")[0].strip()
                etiqueta = f"  • [{hora}] {dia}  →  {ev['titulo']}"
            else:
                etiqueta = f"  • {fecha}  →  {ev['titulo']}"
            # Truncar si es muy largo
            if len(etiqueta) > 95:
                etiqueta = etiqueta[:92] + "..."
            print(etiqueta)

    print("\n" + "─" * 60)
    print(f"  Total: {len(eventos)} eventos")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────
# LIMPIAR DATOS PARA RETORNAR (sin campos privados)
# ─────────────────────────────────────────────

def limpiar_para_jarvis(eventos):
    """Quita campos internos antes de devolver a Jarvis."""
    limpios = []
    for ev in eventos:
        limpios.append({
            "titulo":     ev["titulo"],
            "fecha":      ev["fecha"],
            "tipo":       ev["tipo"],
        })
    return limpios


# ─────────────────────────────────────────────
# FUNCIONES PUBLICAS PARA JARVIS
# ─────────────────────────────────────────────

def eventos_proximos(dias=7):
    try:
        servicio = autenticar()
        try:
            dias = int(dias)
        except (ValueError, TypeError):
            dias = 7
        dias = max(1, min(dias, 30))

        time_min = ahora_utc_iso()
        time_max = fecha_utc_futura(dias)
        eventos  = consultar_todos_calendarios(servicio, time_min, time_max)

        if not eventos:
            return {
                "total":   0,
                "rango":   f"proximos {dias} dias",
                "eventos": [],
                "mensaje": f"No tienes eventos en los proximos {dias} dias."
            }

        return {
            "total":   len(eventos),
            "rango":   f"proximos {dias} dias",
            "eventos": limpiar_para_jarvis(eventos[:15])
        }
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


def eventos_de_hoy():
    try:
        servicio = autenticar()
        # "Hoy" segun la hora local de Ecuador, no UTC
        ahora_local = datetime.datetime.now(ZONA_LOCAL)
        inicio_dia  = ahora_local.replace(hour=0,  minute=0,  second=0, microsecond=0)
        fin_dia     = ahora_local.replace(hour=23, minute=59, second=59)

        # Convertir a UTC para enviarlo a la API de Google
        inicio_utc = inicio_dia.astimezone(datetime.timezone.utc)
        fin_utc    = fin_dia.astimezone(datetime.timezone.utc)

        time_min = inicio_utc.isoformat().replace('+00:00', 'Z')
        time_max = fin_utc.isoformat().replace('+00:00', 'Z')

        eventos   = consultar_todos_calendarios(servicio, time_min, time_max)
        fecha_hoy = ahora_local.strftime('%d/%m/%Y')

        if not eventos:
            return {
                "fecha":   fecha_hoy,
                "total":   0,
                "eventos": [],
                "mensaje": f"No tienes eventos hoy ({fecha_hoy})."
            }

        return {
            "fecha":   fecha_hoy,
            "total":   len(eventos),
            "eventos": limpiar_para_jarvis(eventos)
        }
    except Exception as e:
        return {"error": f"Error: {str(e)}"}



def buscar_eventos(palabra_clave):
    try:
        if not palabra_clave or len(palabra_clave) < 2:
            return {"error": "Palabra clave muy corta."}

        servicio = autenticar()
        time_min = ahora_utc_iso()
        time_max = fecha_utc_futura(90)
        eventos  = consultar_todos_calendarios(servicio, time_min, time_max, query=palabra_clave)

        if not eventos:
            return {
                "palabra_clave": palabra_clave,
                "total":   0,
                "eventos": [],
                "mensaje": f"No encontre eventos con '{palabra_clave}' en los proximos 90 dias."
            }

        return {
            "palabra_clave": palabra_clave,
            "total":   len(eventos),
            "eventos": limpiar_para_jarvis(eventos[:15])
        }
    except Exception as e:
        return {"error": f"Error: {str(e)}"}


# ─────────────────────────────────────────────
# WRAPPERS CON VISTA BONITA (solo ejecucion directa)
# ─────────────────────────────────────────────

def _consultar_proximos_para_vista(dias=7):
    """Igual que eventos_proximos pero devuelve eventos completos para imprimir."""
    servicio = autenticar()
    time_min = ahora_utc_iso()
    time_max = fecha_utc_futura(dias)
    return consultar_todos_calendarios(servicio, time_min, time_max)

def _consultar_hoy_para_vista():
    servicio   = autenticar()
    ahora      = datetime.datetime.now(datetime.timezone.utc)
    inicio_dia = ahora.replace(hour=0,  minute=0,  second=0, microsecond=0)
    fin_dia    = ahora.replace(hour=23, minute=59, second=59)
    return consultar_todos_calendarios(
        servicio,
        inicio_dia.isoformat().replace('+00:00', 'Z'),
        fin_dia.isoformat().replace('+00:00', 'Z')
    )

def _consultar_buscar_para_vista(palabra_clave):
    servicio = autenticar()
    time_min = ahora_utc_iso()
    time_max = fecha_utc_futura(90)
    return consultar_todos_calendarios(servicio, time_min, time_max, query=palabra_clave)


# ─────────────────────────────────────────────
# EJECUCION DIRECTA: VISTA BONITA
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("           JARVIS — AGENDA DE GOOGLE CALENDAR")
    print("═" * 60)

    eventos_hoy = _consultar_hoy_para_vista()
    fecha_hoy   = datetime.datetime.now().strftime('%A %d de %B, %Y')
    imprimir_agenda(f"EVENTOS DE HOY — {fecha_hoy}", eventos_hoy)

    eventos_sem = _consultar_proximos_para_vista(7)
    imprimir_agenda("PROXIMOS 7 DIAS", eventos_sem)

    eventos_busq = _consultar_buscar_para_vista("Ecuador")
    imprimir_agenda("BUSQUEDA: 'Ecuador' (proximos 90 dias)", eventos_busq)

    print("\n  Listo. Estas funciones ya estan disponibles para Jarvis.\n")
