"""
calendario_google.py — VERSION FINAL CON CRUD COMPLETO
-------------------------------------------------------
Herramienta de Google Calendar para Jarvis.

Funciones disponibles:
  LECTURA:
    eventos_de_hoy()
    eventos_proximos(dias)
    buscar_eventos(palabra_clave)
    listar_eventos_con_ids(dias)    <- NUEVO

  ESCRITURA:
    crear_evento(titulo, fecha, hora_inicio, hora_fin, descripcion)
    editar_evento(evento_id, ...)   <- NUEVO
    eliminar_evento(evento_id)      <- NUEVO
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

SCOPES = ['https://www.googleapis.com/auth/calendar']

ZONA_LOCAL       = datetime.timezone(datetime.timedelta(hours=-5))
DIR_SCRIPT       = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(DIR_SCRIPT, 'credentials.json')
TOKEN_PATH       = os.path.join(DIR_SCRIPT, 'token.json')

CATEGORIAS_CALENDARIO = {
    "Calendario (Canvas)": ("UNIVERSIDAD",  "academico"),
    "World Cup":           ("MUNDIAL 2026", "deportes"),
    "Festivos en Ecuador": ("FESTIVOS",     "festivo"),
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
    for clave, (etiqueta, categoria) in CATEGORIAS_CALENDARIO.items():
        if clave in nombre:
            return etiqueta, categoria
    return "PERSONAL", "personal"

def limpiar_titulo(titulo):
    titulo_limpio = re.sub(r'\[[^\]]+\]', '', titulo).strip()
    return titulo_limpio if titulo_limpio else titulo

def formato_partido_mundial(titulo):
    titulo_sin_emoji = re.sub(r'[\U0001F1E6-\U0001F1FF]+\s*', '', titulo)
    titulo_sin_emoji = titulo_sin_emoji.replace(' - ', ' vs ').strip()
    return titulo_sin_emoji

def formatear_fecha_evento(evento):
    start     = evento.get('start', {})
    fecha_str = start.get('dateTime', start.get('date', ''))
    if not fecha_str:
        return "Sin fecha", None
    try:
        if 'T' in fecha_str:
            dt       = datetime.datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            dt_local = dt.astimezone(ZONA_LOCAL)
            return dt_local.strftime('%d/%m/%Y a las %H:%M'), dt_local
        else:
            dt = datetime.datetime.strptime(fecha_str, '%Y-%m-%d')
            dt = dt.replace(tzinfo=ZONA_LOCAL)
            return dt.strftime('%d/%m/%Y (todo el dia)'), dt
    except Exception:
        return fecha_str, None

def resumir_evento(evento, nombre_calendario):
    fecha_legible, fecha_obj = formatear_fecha_evento(evento)
    etiqueta, categoria      = categorizar_calendario(nombre_calendario)
    titulo_raw               = evento.get('summary', '(sin titulo)')

    if categoria == "deportes":
        titulo = formato_partido_mundial(titulo_raw)
    elif categoria == "academico":
        titulo = limpiar_titulo(titulo_raw)
    else:
        titulo = titulo_raw

    return {
        "titulo":           titulo,
        "fecha":            fecha_legible,
        "tipo":             etiqueta,
        "categoria":        categoria,
        "_fecha_obj":       fecha_obj,
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

    todos_eventos.sort(key=lambda ev: ev.get('_fecha_obj') or
                       datetime.datetime.max.replace(tzinfo=datetime.timezone.utc))
    return todos_eventos

def limpiar_para_jarvis(eventos):
    return [{
        "titulo": ev["titulo"],
        "fecha":  ev["fecha"],
        "tipo":   ev["tipo"],
    } for ev in eventos]


# ─────────────────────────────────────────────
# VISTA BONITA
# ─────────────────────────────────────────────

ICONOS_TIPO = {
    "UNIVERSIDAD":  "🎓",
    "MUNDIAL 2026": "⚽",
    "FESTIVOS":     "🎉",
    "PERSONAL":     "📌",
}

def imprimir_agenda(titulo, eventos):
    print("\n" + "═" * 60)
    print(f"  📅 {titulo}")
    print("═" * 60)

    if not eventos:
        print("\n   No hay eventos en este rango.\n")
        return

    grupos = {}
    for ev in eventos:
        tipo = ev["tipo"]
        if tipo not in grupos:
            grupos[tipo] = []
        grupos[tipo].append(ev)

    orden = ["UNIVERSIDAD", "MUNDIAL 2026", "FESTIVOS", "PERSONAL"]
    for tipo in orden:
        if tipo not in grupos:
            continue
        icono = ICONOS_TIPO.get(tipo, "•")
        print(f"\n  {icono} {tipo}")
        print("  " + "─" * 56)
        for ev in grupos[tipo]:
            fecha = ev["fecha"]
            if "a las" in fecha:
                hora     = fecha.split("a las")[1].strip()
                dia      = fecha.split("a las")[0].strip()
                etiqueta = f"  • [{hora}] {dia}  →  {ev['titulo']}"
            else:
                etiqueta = f"  • {fecha}  →  {ev['titulo']}"
            if len(etiqueta) > 95:
                etiqueta = etiqueta[:92] + "..."
            print(etiqueta)

    print("\n" + "─" * 60)
    print(f"  Total: {len(eventos)} eventos")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────
# FUNCIONES PUBLICAS — LECTURA
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
        servicio    = autenticar()
        ahora_local = datetime.datetime.now(ZONA_LOCAL)
        inicio_dia  = ahora_local.replace(hour=0,  minute=0,  second=0, microsecond=0)
        fin_dia     = ahora_local.replace(hour=23, minute=59, second=59)
        inicio_utc  = inicio_dia.astimezone(datetime.timezone.utc)
        fin_utc     = fin_dia.astimezone(datetime.timezone.utc)
        time_min    = inicio_utc.isoformat().replace('+00:00', 'Z')
        time_max    = fin_utc.isoformat().replace('+00:00', 'Z')
        eventos     = consultar_todos_calendarios(servicio, time_min, time_max)
        fecha_hoy   = ahora_local.strftime('%d/%m/%Y')

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
        eventos  = consultar_todos_calendarios(servicio, time_min, time_max,
                                                query=palabra_clave)
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


def listar_eventos_con_ids(dias: int = 7,
                            calendario_id: str = "primary") -> dict:
    """
    Lista proximos eventos del calendario principal con sus IDs.
    Solo consulta el calendario primario para que los eventos
    sean editables (los calendarios de terceros son solo lectura).
    """
    try:
        servicio  = autenticar()
        time_min  = ahora_utc_iso()
        time_max  = fecha_utc_futura(dias)

        resultado = servicio.events().list(
            calendarId   = calendario_id,
            timeMin      = time_min,
            timeMax      = time_max,
            maxResults   = 20,
            singleEvents = True,
            orderBy      = "startTime"
        ).execute()

        eventos = resultado.get("items", [])

        if not eventos:
            return {
                "total":   0,
                "eventos": [],
                "mensaje": f"No tienes eventos editables en los proximos {dias} dias."
            }

        return {
            "total":   len(eventos),
            "rango":   f"Proximos {dias} dias",
            "eventos": [{
                "id":          ev.get("id", ""),
                "titulo":      ev.get("summary", "(sin titulo)"),
                "fecha":       formatear_fecha_evento(ev)[0],
                "descripcion": ev.get("description", ""),
                "link":        ev.get("htmlLink", "")
            } for ev in eventos]
        }

    except HttpError as e:
        return {"error": f"Error de Google Calendar API: {str(e)}"}
    except Exception as e:
        return {"error": f"Error al listar eventos: {str(e)}"}


# ─────────────────────────────────────────────
# FUNCIONES PUBLICAS — ESCRITURA
# ─────────────────────────────────────────────

def crear_evento(titulo: str,
                 fecha: str,
                 hora_inicio: str = "",
                 hora_fin: str = "",
                 descripcion: str = "",
                 calendario_id: str = "primary") -> dict:
    """Crea un evento en Google Calendar."""
    try:
        servicio = autenticar()

        try:
            partes    = fecha.strip().split("/")
            fecha_iso = f"{partes[2]}-{partes[1].zfill(2)}-{partes[0].zfill(2)}"
        except (IndexError, ValueError):
            return {"error": f"Formato de fecha incorrecto: '{fecha}'. Usa DD/MM/YYYY"}

        if not hora_inicio:
            evento = {
                "summary":     titulo,
                "description": descripcion,
                "start": {"date": fecha_iso},
                "end":   {"date": fecha_iso},
            }
        else:
            if not hora_fin:
                hora_parts = hora_inicio.split(":")
                hora_fin   = f"{int(hora_parts[0]) + 1:02d}:{hora_parts[1]}"

            zona_horaria = "America/Guayaquil"
            evento = {
                "summary":     titulo,
                "description": descripcion,
                "start": {
                    "dateTime": f"{fecha_iso}T{hora_inicio}:00",
                    "timeZone": zona_horaria
                },
                "end": {
                    "dateTime": f"{fecha_iso}T{hora_fin}:00",
                    "timeZone": zona_horaria
                },
            }

        resultado = servicio.events().insert(
            calendarId=calendario_id,
            body=evento
        ).execute()

        return {
            "ok":        True,
            "titulo":    titulo,
            "fecha":     fecha,
            "hora":      f"{hora_inicio} a {hora_fin}" if hora_inicio else "Todo el dia",
            "evento_id": resultado.get("id", ""),
            "link":      resultado.get("htmlLink", ""),
            "mensaje":   f"Evento '{titulo}' creado en Google Calendar para el {fecha}."
        }

    except HttpError as e:
        if "insufficientPermissions" in str(e):
            return {"error": "Sin permisos de escritura. Elimina token.json y vuelve a autorizar."}
        return {"error": f"Error de Google Calendar API: {str(e)}"}
    except Exception as e:
        return {"error": f"Error al crear evento: {str(e)}"}


def editar_evento(evento_id: str,
                  nuevo_titulo: str = "",
                  nueva_fecha: str = "",
                  nueva_hora_inicio: str = "",
                  nueva_hora_fin: str = "",
                  nueva_descripcion: str = "",
                  calendario_id: str = "primary") -> dict:
    """
    Edita un evento existente en Google Calendar por su ID.
    Solo modifica los campos que se proporcionen.
    """
    try:
        servicio = autenticar()

        try:
            evento_actual = servicio.events().get(
                calendarId=calendario_id,
                eventId=evento_id
            ).execute()
        except HttpError:
            return {"error": f"No se encontro el evento con ID: {evento_id}"}

        if nuevo_titulo:
            evento_actual["summary"] = nuevo_titulo

        if nueva_descripcion:
            evento_actual["description"] = nueva_descripcion

        if nueva_fecha:
            try:
                partes    = nueva_fecha.strip().split("/")
                fecha_iso = f"{partes[2]}-{partes[1].zfill(2)}-{partes[0].zfill(2)}"
            except (IndexError, ValueError):
                return {"error": f"Formato de fecha incorrecto: '{nueva_fecha}'. Usa DD/MM/YYYY"}

            if "date" in evento_actual.get("start", {}):
                evento_actual["start"]["date"] = fecha_iso
                evento_actual["end"]["date"]   = fecha_iso
            else:
                zona  = evento_actual["start"].get("timeZone", "America/Guayaquil")
                hora_i = nueva_hora_inicio or evento_actual["start"]["dateTime"].split("T")[1][:5]
                hora_f = nueva_hora_fin    or evento_actual["end"]["dateTime"].split("T")[1][:5]
                evento_actual["start"] = {"dateTime": f"{fecha_iso}T{hora_i}:00", "timeZone": zona}
                evento_actual["end"]   = {"dateTime": f"{fecha_iso}T{hora_f}:00", "timeZone": zona}

        elif nueva_hora_inicio:
            if "dateTime" in evento_actual.get("start", {}):
                fecha_actual = evento_actual["start"]["dateTime"].split("T")[0]
                zona         = evento_actual["start"].get("timeZone", "America/Guayaquil")
                hora_f       = nueva_hora_fin or evento_actual["end"]["dateTime"].split("T")[1][:5]
                evento_actual["start"] = {"dateTime": f"{fecha_actual}T{nueva_hora_inicio}:00", "timeZone": zona}
                evento_actual["end"]   = {"dateTime": f"{fecha_actual}T{hora_f}:00",            "timeZone": zona}

        resultado = servicio.events().update(
            calendarId=calendario_id,
            eventId=evento_id,
            body=evento_actual
        ).execute()

        return {
            "ok":        True,
            "titulo":    resultado.get("summary", ""),
            "evento_id": resultado.get("id", ""),
            "link":      resultado.get("htmlLink", ""),
            "mensaje":   f"Evento actualizado correctamente en Google Calendar."
        }

    except HttpError as e:
        if "insufficientPermissions" in str(e):
            return {"error": "Sin permisos de escritura. Elimina token.json y vuelve a autorizar."}
        return {"error": f"Error de Google Calendar API: {str(e)}"}
    except Exception as e:
        return {"error": f"Error al editar evento: {str(e)}"}


def eliminar_evento(evento_id: str,
                    calendario_id: str = "primary") -> dict:
    """Elimina un evento de Google Calendar por su ID."""
    try:
        servicio = autenticar()

        try:
            evento = servicio.events().get(
                calendarId=calendario_id,
                eventId=evento_id
            ).execute()
            titulo = evento.get("summary", "sin titulo")
        except HttpError:
            return {"error": f"No se encontro el evento con ID: {evento_id}"}

        servicio.events().delete(
            calendarId=calendario_id,
            eventId=evento_id
        ).execute()

        return {
            "ok":      True,
            "titulo":  titulo,
            "mensaje": f"Evento '{titulo}' eliminado correctamente de Google Calendar."
        }

    except HttpError as e:
        if "insufficientPermissions" in str(e):
            return {"error": "Sin permisos de escritura. Elimina token.json y vuelve a autorizar."}
        return {"error": f"Error de Google Calendar API: {str(e)}"}
    except Exception as e:
        return {"error": f"Error al eliminar evento: {str(e)}"}


# ─────────────────────────────────────────────
# WRAPPERS VISTA BONITA (ejecucion directa)
# ─────────────────────────────────────────────

def _consultar_proximos_para_vista(dias=7):
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

    print("\n  Listo. Funciones disponibles para Jarvis.\n")