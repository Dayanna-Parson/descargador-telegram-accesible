"""Informe de solo lectura de lo que contiene una carpeta de la biblioteca."""
import json
import logging
import os
import re
import shutil
import subprocess
from collections import Counter

from app.config_rutas import RUTA_BIN
from app.motor.resumen_carpeta import formatear_duracion, formatear_tamano

logger = logging.getLogger(__name__)

# ANCLAJE_INICIO: INVENTARIO_RECORRIDO
EXTENSIONES_DE_VIDEO = {"mp4", "mkv", "avi", "mov", "m4v", "wmv"}
PATRON_NOMBRE_NUMERICO = re.compile(r"^\d{8,}\.[A-Za-z0-9]+$")


def recorrer_carpeta(carpeta):
    """Devuelve una lista de (ruta_relativa_de_carpeta, nombre, bytes) de todos los archivos."""
    encontrados = []
    for carpeta_actual, subcarpetas, archivos in os.walk(carpeta):
        subcarpetas.sort()
        relativa = os.path.relpath(carpeta_actual, carpeta)
        relativa = "" if relativa == "." else relativa
        for nombre in sorted(archivos):
            try:
                tamano = os.path.getsize(os.path.join(carpeta_actual, nombre))
            except OSError:
                logger.exception("No se pudo leer el tamaño de %s", nombre)
                continue
            encontrados.append((relativa, nombre, tamano))
    return encontrados


def tiene_nombre_numerico(nombre):
    """True para los vídeos que Telegram guarda solo con un número largo (las imágenes no cuentan)."""
    return bool(PATRON_NOMBRE_NUMERICO.match(nombre)) and \
        os.path.splitext(nombre)[1].lstrip(".").lower() in EXTENSIONES_DE_VIDEO
# ANCLAJE_FIN: INVENTARIO_RECORRIDO


# ANCLAJE_INICIO: INVENTARIO_METADATOS
def localizar_ffprobe():
    """Ruta de ffprobe si está en bin/ o en el PATH; None si no hay."""
    for candidato in ("ffprobe.exe", "ffprobe"):
        ruta = os.path.join(RUTA_BIN, candidato)
        if os.path.isfile(ruta):
            return ruta
    return shutil.which("ffprobe")


def leer_metadatos_de_video(ruta_ffprobe, ruta_video):
    """Devuelve (duracion_en_segundos, titulo) de un vídeo; None en lo que no se pueda leer."""
    orden = [ruta_ffprobe, "-v", "error", "-show_entries", "format=duration:format_tags=title",
             "-of", "json", ruta_video]
    opciones = {"capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace", "timeout": 60}
    if os.name == "nt":
        opciones["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        resultado = subprocess.run(orden, **opciones)
        formato = json.loads(resultado.stdout or "{}").get("format", {})
    except (OSError, subprocess.SubprocessError, ValueError):
        logger.exception("No se pudieron leer los metadatos de %s", ruta_video)
        return None, None
    try:
        duracion = float(formato.get("duration"))
    except (TypeError, ValueError):
        duracion = None
    titulo = (formato.get("tags") or {}).get("title")
    return duracion, titulo
# ANCLAJE_FIN: INVENTARIO_METADATOS


# ANCLAJE_INICIO: INVENTARIO_INFORME
def _resumen_por_carpeta(archivos):
    por_carpeta = {}
    for relativa, _nombre, tamano in archivos:
        cantidad, total = por_carpeta.get(relativa, (0, 0))
        por_carpeta[relativa] = (cantidad + 1, total + tamano)
    return por_carpeta


def _copias_por_tamano(carpeta_antigua, archivos):
    """Para cada archivo de carpeta_antigua, qué archivos de la biblioteca miden lo mismo."""
    por_tamano = {}
    for relativa, nombre, tamano in archivos:
        por_tamano.setdefault(tamano, []).append(os.path.join(relativa, nombre))
    lineas = []
    for _relativa, nombre, tamano in recorrer_carpeta(carpeta_antigua):
        copias = por_tamano.get(tamano, [])
        lineas.append("{} ({}): {} copia(s) del mismo tamaño".format(nombre, formatear_tamano(tamano), len(copias)))
        lineas.extend("    " + copia for copia in copias)
    return lineas


def generar_informe(carpeta, carpeta_antigua=None, ruta_ffprobe=None, al_progreso=None):
    """Texto del informe: totales, extensiones, carpetas, listado, vídeos sin nombre y comparación."""
    archivos = recorrer_carpeta(carpeta)
    total = sum(tamano for _r, _n, tamano in archivos)
    lineas = ["INFORME DE LA CARPETA", carpeta, "",
              "Archivos: {}  Tamaño total: {}".format(len(archivos), formatear_tamano(total)), ""]

    extensiones = Counter(os.path.splitext(n)[1].lstrip(".").lower() or "(sin extensión)" for _r, n, _t in archivos)
    lineas.append("POR EXTENSIÓN")
    lineas.extend("  {}: {}".format(ext, cantidad) for ext, cantidad in extensiones.most_common())

    lineas += ["", "POR CARPETA"]
    for relativa, (cantidad, tamano) in sorted(_resumen_por_carpeta(archivos).items()):
        lineas.append("  {}: {} archivos, {}".format(relativa or "(raíz)", cantidad, formatear_tamano(tamano)))

    numericos = [(r, n, t) for r, n, t in archivos if tiene_nombre_numerico(n)]
    lineas += ["", "VÍDEOS CON NOMBRE NUMÉRICO: {}".format(len(numericos))]
    for indice, (relativa, nombre, tamano) in enumerate(numericos, 1):
        detalle = ""
        if ruta_ffprobe:
            duracion, titulo = leer_metadatos_de_video(ruta_ffprobe, os.path.join(carpeta, relativa, nombre))
            detalle = ", duración {}".format(formatear_duracion(duracion)) if duracion else ""
            detalle += ", título «{}»".format(titulo) if titulo else ""
            if al_progreso:
                al_progreso(indice, len(numericos))
        lineas.append("  {}\\{} ({}{})".format(relativa, nombre, formatear_tamano(tamano), detalle))
    if numericos and not ruta_ffprobe:
        lineas.append("  (ffprobe no está disponible: no se ha leído la duración ni el título)")

    lineas += ["", "LISTADO COMPLETO"]
    carpeta_anterior = None
    for relativa, nombre, tamano in archivos:
        if relativa != carpeta_anterior:
            lineas.append("[{}]".format(relativa or "raíz"))
            carpeta_anterior = relativa
        lineas.append("  {} ({})".format(nombre, formatear_tamano(tamano)))

    if carpeta_antigua and os.path.isdir(carpeta_antigua):
        lineas += ["", "COMPARACIÓN CON {}".format(carpeta_antigua)]
        lineas.extend(_copias_por_tamano(carpeta_antigua, archivos))
    return "\n".join(lineas) + "\n"
# ANCLAJE_FIN: INVENTARIO_INFORME
