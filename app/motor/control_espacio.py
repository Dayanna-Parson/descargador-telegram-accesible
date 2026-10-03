"""Espacio libre en disco y decisión de si una descarga cabe."""
import logging
import os
import shutil

logger = logging.getLogger(__name__)

RESERVA_MINIMA_BYTES = 2 * 1024 ** 3


# ANCLAJE_INICIO: CONTROL_ESPACIO
def espacio_libre(ruta):
    """Bytes libres en el disco de ruta, aunque la carpeta aún no exista. None si no se puede saber."""
    actual = os.path.abspath(ruta)
    while not os.path.exists(actual):
        padre = os.path.dirname(actual)
        if padre == actual:
            break
        actual = padre
    try:
        return shutil.disk_usage(actual).free
    except OSError:
        logger.exception("No se pudo consultar el espacio libre de %s", actual)
        return None


def cabe(libre, estimado, reserva=RESERVA_MINIMA_BYTES):
    """True si tras descargar quedan al menos reserva bytes libres; None si falta algún dato."""
    if libre is None or not estimado:
        return None
    return libre - estimado >= reserva
# ANCLAJE_FIN: CONTROL_ESPACIO
