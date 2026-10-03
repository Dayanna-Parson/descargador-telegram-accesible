"""Recuento y tamaño de una carpeta, para estimar cuánto ocupará una descarga."""
import logging
import os

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: RESUMEN_CARPETA
def resumir_carpeta(carpeta):
    """Devuelve (numero_de_archivos, bytes_totales) de todo lo que hay bajo carpeta."""
    cantidad = 0
    total = 0
    for carpeta_actual, _subcarpetas, archivos in os.walk(carpeta):
        for archivo in archivos:
            try:
                total += os.path.getsize(os.path.join(carpeta_actual, archivo))
                cantidad += 1
            except OSError:
                logger.exception("No se pudo leer el tamaño de %s", archivo)
    return cantidad, total


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
