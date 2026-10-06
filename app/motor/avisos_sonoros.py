"""Sonidos del sistema para avisar de que una tarea larga ha terminado o ha fallado.

Se llaman siempre desde el hilo principal.
"""
import logging
import os

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: AVISOS_SONOROS
def _reproducir(alias):
    if os.name != "nt":
        return
    try:
        import winsound
        winsound.PlaySound(alias, winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        logger.exception("No se pudo reproducir el sonido del sistema %s", alias)


def sonar_exito():
    _reproducir("SystemAsterisk")


def sonar_error():
    _reproducir("SystemHand")
# ANCLAJE_FIN: AVISOS_SONOROS
