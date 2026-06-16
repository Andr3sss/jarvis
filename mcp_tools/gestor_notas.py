"""
gestor_notas.py — VERSION CON ARCHIVOS TXT
-------------------------------------------
Gestor local de notas y tareas para Jarvis.

Cada nota se guarda en DOS lugares:
  1. data/notas_tareas.json  — para que Jarvis pueda leerlas rapido
  2. data/notas/titulo.txt   — archivo de texto plano legible por cualquiera

Las tareas solo se guardan en el JSON porque son datos estructurados.
"""

import os
import json
import re
import datetime

BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATOS_PATH  = os.path.join(BASE_DIR, "data", "notas_tareas.json")
NOTAS_DIR   = os.path.join(BASE_DIR, "data", "notas")


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────

def _cargar_datos() -> dict:
    if not os.path.exists(DATOS_PATH):
        return {"notas": [], "tareas": []}
    try:
        with open(DATOS_PATH, "r", encoding="utf-8") as f:
            datos = json.load(f)
        if "notas"  not in datos: datos["notas"]  = []
        if "tareas" not in datos: datos["tareas"] = []
        return datos
    except (json.JSONDecodeError, IOError):
        return {"notas": [], "tareas": []}


def _guardar_datos(datos: dict) -> bool:
    try:
        os.makedirs(os.path.dirname(DATOS_PATH), exist_ok=True)
        with open(DATOS_PATH, "w", encoding="utf-8") as f:
            json.dump(datos, f, ensure_ascii=False, indent=2)
        return True
    except IOError:
        return False


def _ahora() -> str:
    return datetime.datetime.now().strftime("%d/%m/%Y %H:%M")


def _titulo_a_nombre_archivo(titulo: str) -> str:
    """
    Convierte el titulo de una nota en un nombre de archivo seguro.
    Ejemplo: "Precio Bitcoin hoy" -> "precio_bitcoin_hoy.txt"
    """
    nombre = titulo.lower().strip()
    nombre = re.sub(r'[^a-z0-9\s]', '', nombre)
    nombre = re.sub(r'\s+', '_', nombre)
    nombre = nombre[:50]
    return nombre + ".txt"


def _guardar_nota_txt(titulo: str, contenido: str,
                      fecha_creacion: str, ultima_edicion: str) -> str:
    """
    Guarda la nota como archivo .txt legible.
    Devuelve la ruta del archivo creado.
    """
    os.makedirs(NOTAS_DIR, exist_ok=True)
    nombre_archivo = _titulo_a_nombre_archivo(titulo)
    ruta           = os.path.join(NOTAS_DIR, nombre_archivo)

    contenido_txt = f"""NOTA: {titulo}
{"=" * (len(titulo) + 6)}
Creada:        {fecha_creacion}
Ultima edicion: {ultima_edicion}
{"=" * (len(titulo) + 6)}

{contenido}
"""
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(contenido_txt)

    return ruta


def _eliminar_nota_txt(titulo: str):
    """Elimina el archivo .txt de la nota si existe."""
    nombre_archivo = _titulo_a_nombre_archivo(titulo)
    ruta           = os.path.join(NOTAS_DIR, nombre_archivo)
    if os.path.exists(ruta):
        os.remove(ruta)


# ─────────────────────────────────────────────
# FUNCIONES DE NOTAS
# ─────────────────────────────────────────────

def crear_nota(titulo: str, contenido: str) -> dict:
    """
    Crea o actualiza una nota.
    Se guarda en JSON (para Jarvis) y en .txt (para el usuario).
    """
    titulo    = titulo.strip()
    contenido = contenido.strip()

    if not titulo:
        return {"error": "El titulo de la nota no puede estar vacio."}
    if not contenido:
        return {"error": "El contenido de la nota no puede estar vacio."}

    datos     = _cargar_datos()
    ahora     = _ahora()
    existente = next((n for n in datos["notas"]
                      if n["titulo"].lower() == titulo.lower()), None)

    if existente:
        existente["contenido"]      = contenido
        existente["ultima_edicion"] = ahora
        accion = "actualizada"
    else:
        datos["notas"].append({
            "titulo":         titulo,
            "contenido":      contenido,
            "fecha_creacion": ahora,
            "ultima_edicion": ahora
        })
        accion = "creada"

    if not _guardar_datos(datos):
        return {"error": "No se pudo guardar la nota en el archivo JSON."}

    # Guardar tambien como .txt
    fecha_creacion = existente["fecha_creacion"] if existente else ahora
    ruta_txt = _guardar_nota_txt(titulo, contenido, fecha_creacion, ahora)

    return {
        "ok":       True,
        "accion":   accion,
        "titulo":   titulo,
        "archivo":  ruta_txt,
        "mensaje":  f"Nota '{titulo}' {accion} correctamente. "
                    f"Puedes leerla en: {ruta_txt}"
    }


def leer_nota(titulo: str) -> dict:
    """Lee una nota por su titulo desde el JSON."""
    titulo = titulo.strip()
    datos  = _cargar_datos()

    nota = next((n for n in datos["notas"]
                 if n["titulo"].lower() == titulo.lower()), None)

    if not nota:
        titulos = [n["titulo"] for n in datos["notas"]]
        return {
            "error":            f"No encontre ninguna nota llamada '{titulo}'.",
            "notas_existentes": titulos if titulos else ["No hay notas guardadas."]
        }

    nombre_archivo = _titulo_a_nombre_archivo(titulo)
    ruta_txt       = os.path.join(NOTAS_DIR, nombre_archivo)

    return {
        "titulo":         nota["titulo"],
        "contenido":      nota["contenido"],
        "fecha_creacion": nota.get("fecha_creacion", ""),
        "ultima_edicion": nota.get("ultima_edicion", ""),
        "archivo_txt":    ruta_txt if os.path.exists(ruta_txt) else "No disponible"
    }


def listar_notas() -> dict:
    """Lista todas las notas guardadas."""
    datos = _cargar_datos()

    if not datos["notas"]:
        return {
            "total":   0,
            "notas":   [],
            "mensaje": "No tienes notas guardadas todavia."
        }

    resumen = []
    for n in datos["notas"]:
        nombre_archivo = _titulo_a_nombre_archivo(n["titulo"])
        ruta_txt       = os.path.join(NOTAS_DIR, nombre_archivo)
        resumen.append({
            "titulo":         n["titulo"],
            "fecha_creacion": n.get("fecha_creacion", ""),
            "archivo_txt":    ruta_txt if os.path.exists(ruta_txt) else "No disponible",
            "preview":        n["contenido"][:80] + "..."
                              if len(n["contenido"]) > 80
                              else n["contenido"]
        })

    return {
        "total":        len(resumen),
        "carpeta_notas": NOTAS_DIR,
        "notas":        resumen
    }


def eliminar_nota(titulo: str) -> dict:
    """Elimina una nota del JSON y su archivo .txt."""
    titulo = titulo.strip()
    datos  = _cargar_datos()

    original = len(datos["notas"])
    datos["notas"] = [n for n in datos["notas"]
                      if n["titulo"].lower() != titulo.lower()]

    if len(datos["notas"]) == original:
        return {"error": f"No encontre ninguna nota llamada '{titulo}'."}

    if not _guardar_datos(datos):
        return {"error": "No se pudo guardar el cambio en el archivo."}

    _eliminar_nota_txt(titulo)

    return {
        "ok":      True,
        "titulo":  titulo,
        "mensaje": f"Nota '{titulo}' eliminada correctamente (JSON y archivo .txt)."
    }


# ─────────────────────────────────────────────
# FUNCIONES DE TAREAS
# ─────────────────────────────────────────────

def crear_tarea(titulo: str,
                descripcion: str = "",
                fecha_limite: str = "") -> dict:
    titulo = titulo.strip()

    if not titulo:
        return {"error": "El titulo de la tarea no puede estar vacio."}

    datos     = _cargar_datos()
    existente = next((t for t in datos["tareas"]
                      if t["titulo"].lower() == titulo.lower()), None)

    if existente:
        return {
            "error":  f"Ya existe una tarea llamada '{titulo}'.",
            "estado": existente["estado"],
            "tip":    "Si quieres actualizarla, elimina la anterior primero."
        }

    datos["tareas"].append({
        "titulo":           titulo,
        "descripcion":      descripcion.strip(),
        "fecha_limite":     fecha_limite.strip(),
        "estado":           "pendiente",
        "fecha_creacion":   _ahora(),
        "fecha_completado": None
    })

    if not _guardar_datos(datos):
        return {"error": "No se pudo guardar la tarea."}

    msg = f"Tarea '{titulo}' creada correctamente."
    if fecha_limite:
        msg += f" Fecha limite: {fecha_limite}."

    return {
        "ok":      True,
        "titulo":  titulo,
        "estado":  "pendiente",
        "mensaje": msg
    }


def completar_tarea(titulo: str) -> dict:
    titulo = titulo.strip()
    datos  = _cargar_datos()

    tarea = next((t for t in datos["tareas"]
                  if t["titulo"].lower() == titulo.lower()), None)

    if not tarea:
        pendientes = [t["titulo"] for t in datos["tareas"]
                      if t["estado"] == "pendiente"]
        return {
            "error":      f"No encontre ninguna tarea llamada '{titulo}'.",
            "pendientes": pendientes if pendientes else ["No hay tareas pendientes."]
        }

    if tarea["estado"] == "completada":
        return {
            "error":   f"La tarea '{titulo}' ya estaba completada.",
            "cuando":  tarea.get("fecha_completado", "")
        }

    tarea["estado"]           = "completada"
    tarea["fecha_completado"] = _ahora()

    if not _guardar_datos(datos):
        return {"error": "No se pudo guardar el cambio."}

    return {
        "ok":      True,
        "titulo":  titulo,
        "estado":  "completada",
        "mensaje": f"Tarea '{titulo}' marcada como completada el {_ahora()}."
    }


def listar_tareas_pendientes() -> dict:
    datos      = _cargar_datos()
    pendientes = [t for t in datos["tareas"] if t["estado"] == "pendiente"]

    if not pendientes:
        return {
            "total":   0,
            "tareas":  [],
            "mensaje": "No tienes tareas pendientes. Todo al dia."
        }

    return {
        "total":  len(pendientes),
        "tareas": [{
            "titulo":       t["titulo"],
            "descripcion":  t["descripcion"],
            "fecha_limite": t["fecha_limite"] or "Sin fecha limite",
            "creada":       t.get("fecha_creacion", "")
        } for t in pendientes]
    }


def listar_tareas_completadas() -> dict:
    datos       = _cargar_datos()
    completadas = [t for t in datos["tareas"] if t["estado"] == "completada"]

    if not completadas:
        return {
            "total":   0,
            "tareas":  [],
            "mensaje": "No has completado ninguna tarea todavia."
        }

    return {
        "total":  len(completadas),
        "tareas": [{
            "titulo":           t["titulo"],
            "descripcion":      t["descripcion"],
            "fecha_completado": t.get("fecha_completado", "")
        } for t in completadas]
    }


def eliminar_tarea(titulo: str) -> dict:
    titulo = titulo.strip()
    datos  = _cargar_datos()

    original = len(datos["tareas"])
    datos["tareas"] = [t for t in datos["tareas"]
                       if t["titulo"].lower() != titulo.lower()]

    if len(datos["tareas"]) == original:
        return {"error": f"No encontre ninguna tarea llamada '{titulo}'."}

    if not _guardar_datos(datos):
        return {"error": "No se pudo guardar el cambio."}

    return {
        "ok":      True,
        "titulo":  titulo,
        "mensaje": f"Tarea '{titulo}' eliminada correctamente."
    }


# ─────────────────────────────────────────────
# PRUEBA RAPIDA
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 55)
    print("  PROBANDO GESTOR CON ARCHIVOS TXT")
    print("=" * 55)

    print("\n[1] Crear nota (genera .txt):")
    r = crear_nota("Apuntes Python",
                   "Python es un lenguaje de alto nivel muy usado en IA y ciencia de datos.")
    print(json.dumps(r, indent=2, ensure_ascii=False))

    print("\n[2] Crear nota de precio:")
    r = crear_nota("Precio Bitcoin",
                   "Bitcoin vale 64,500 USD al 15/06/2026 con cambio +1.3% en 24h.")
    print(json.dumps(r, indent=2, ensure_ascii=False))

    print("\n[3] Listar notas (muestra ruta del .txt):")
    print(json.dumps(listar_notas(), indent=2, ensure_ascii=False))

    print("\n[4] Crear tarea:")
    r = crear_tarea("Entregar proyecto Jarvis",
                    "Subir repo final a GitHub", "16/06/2026")
    print(json.dumps(r, indent=2, ensure_ascii=False))

    print("\n[5] Listar tareas pendientes:")
    print(json.dumps(listar_tareas_pendientes(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 55)
    print(f"  Revisa la carpeta: {NOTAS_DIR}")
    print("  Deberias ver los archivos .txt creados")
    print("=" * 55)