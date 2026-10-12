"""Recuento y tamaño de una carpeta, para estimar cuánto ocupará una descarga."""
import logging
import os

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: RESUMEN_CARPETA
def resumir_carpeta(carpeta, extensiones=None):
    """Devuelve (numero_de_archivos, bytes_totales) de lo que hay bajo carpeta.

    Si se indican extensiones, solo cuentan los archivos de esos tipos.
    """
    permitidas = {e.lstrip(".").lower() for e in extensiones or []}
    cantidad = 0
    total = 0
    for carpeta_actual, _subcarpetas, archivos in os.walk(carpeta):
        for archivo in archivos:
            if permitidas and os.path.splitext(archivo)[1].lstrip(".").lower() not in permitidas:
                continue
            try:
                total += os.path.getsize(os.path.join(carpeta_actual, archivo))
                cantidad += 1
            except OSError:
                logger.exception("No se pudo leer el tamaño de %s", archivo)
    return cantidad, total


def resumir_completos(carpeta, extensiones=None):
    """Devuelve (archivos, bytes) de lo ya terminado bajo carpeta; extensiones filtra por tipo.

    Ignora los .tmp con los que tdl escribe mientras descarga: reservan el
    tamaño final por adelantado y harían parecer que ya se ha bajado todo.
    """
    permitidas = {e.lstrip(".").lower() for e in extensiones or []}
    cantidad = 0
    total = 0
    for carpeta_actual, _subcarpetas, archivos in os.walk(carpeta):
        for archivo in archivos:
            if archivo.lower().endswith(".tmp"):
                continue
            if permitidas and os.path.splitext(archivo)[1].lstrip(".").lower() not in permitidas:
                continue
            try:
                total += os.path.getsize(os.path.join(carpeta_actual, archivo))
                cantidad += 1
            except OSError:
                logger.exception("No se pudo leer el tamaño de %s", archivo)
    return cantidad, total


def contar_completos(carpeta):
    """Archivos ya terminados bajo carpeta."""
    return resumir_completos(carpeta)[0]


def formatear_duracion(segundos):
    """«unos 40 minutos», «unas 14 horas», «unos 3 días»."""
    minutos = round(segundos / 60)
    if minutos < 2:
        return "menos de dos minutos"
    if minutos < 90:
        return "unos {} minutos".format(minutos)
    horas = round(segundos / 3600)
    if horas < 36:
        return "unas {} horas".format(horas)
    return "unos {} días".format(round(horas / 24))


def formatear_velocidad(bytes_por_segundo, hablado=False):
    """«4,2 MB/s» para mostrar o «4,2 megabytes por segundo» para decir por voz."""
    unidades = (("bytes por segundo", "B/s"), ("kilobytes por segundo", "KB/s"), ("megabytes por segundo", "MB/s"))
    valor = float(bytes_por_segundo)
    for indice, (largo, corto) in enumerate(unidades):
        if valor < 1024 or indice == len(unidades) - 1:
            texto = "{:.1f}".format(valor) if indice else "{:.0f}".format(valor)
            return "{} {}".format(texto.replace(".", ","), largo if hablado else corto)
        valor /= 1024


def formatear_tamano(bytes_totales):
    """Texto legible: «850 MB», «12,4 GB»."""
    valor = float(bytes_totales)
    for unidad in ("bytes", "KB", "MB", "GB"):
        if valor < 1024 or unidad == "GB":
            texto = "{:.0f}".format(valor) if unidad in ("bytes", "KB", "MB") else "{:.1f}".format(valor)
            return "{} {}".format(texto.replace(".", ","), unidad)
        valor /= 1024
    return "{} bytes".format(bytes_totales)
# ANCLAJE_FIN: RESUMEN_CARPETA
