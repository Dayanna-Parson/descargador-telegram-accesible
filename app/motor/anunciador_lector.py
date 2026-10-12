"""Anuncios al lector de pantalla activo con accessible_output3.

Es perezoso y a prueba de fallos: si la librería no está instalada o no hay
lector de pantalla en ejecución, hablar() no hace nada.
"""
import logging

logger = logging.getLogger(__name__)

_salida = None
_intentado = False


# ANCLAJE_INICIO: ANUNCIADOR_LECTOR
def _obtener_salida():
    global _salida, _intentado
    if _intentado:
        return _salida
    _intentado = True
    try:
        import accessible_output3.outputs.auto as auto
        _salida = auto.Auto()
    except Exception:
        logger.warning("accessible_output3 no está disponible; no habrá anuncios por voz")
        _salida = None
    return _salida


def hablar(texto, interrumpir=True):
    salida = _obtener_salida()
    if salida is None:
        return
    try:
        salida.speak(texto, interrupt=interrumpir)
    except Exception:
        logger.exception("No se pudo anunciar «%s»", texto)
# ANCLAJE_FIN: ANUNCIADOR_LECTOR
