"""Impide que Windows suspenda el equipo mientras dura una descarga larga."""
import ctypes
import logging
import os

logger = logging.getLogger(__name__)

_ES_WINDOWS = os.name == "nt"
_ES_CONTINUO = 0x80000000
_ES_SISTEMA_REQUERIDO = 0x00000001


# ANCLAJE_INICIO: EVITAR_SUSPENSION
def _establecer_estado(estado):
    """Llama a la API de Windows. Devuelve el estado anterior, o 0 si falló."""
    return ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(estado))


def _fijar(estado, descripcion):
    if not _ES_WINDOWS:
        return False
    try:
        if _establecer_estado(estado) == 0:
            logger.warning("Windows no aceptó la petición de %s la suspensión", descripcion)
            return False
        return True
    except Exception:
        logger.exception("No se pudo %s la suspensión del equipo", descripcion)
        return False


def bloquear():
    """Mantiene el equipo despierto. Llamar siempre desde el mismo hilo que liberar()."""
    return _fijar(_ES_CONTINUO | _ES_SISTEMA_REQUERIDO, "bloquear")


def liberar():
    """Devuelve a Windows el control normal de la suspensión."""
    return _fijar(_ES_CONTINUO, "liberar")
# ANCLAJE_FIN: EVITAR_SUSPENSION
