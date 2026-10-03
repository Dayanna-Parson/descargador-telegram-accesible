"""Lectura y escritura de JSON. La escritura es siempre atómica."""
import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: ALMACEN_JSON
def leer_json(ruta, valor_por_defecto=None):
    """Lee un JSON. Si no existe o está corrupto, devuelve el valor por defecto."""
    if not os.path.isfile(ruta):
        return valor_por_defecto
    try:
        with open(ruta, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (OSError, ValueError):
        logger.exception("No se pudo leer el JSON %s", ruta)
        return valor_por_defecto


def guardar_json_atomico(ruta, datos):
    """Escribe a un temporal en la misma carpeta y renombra sobre el destino."""
    carpeta = os.path.dirname(os.path.abspath(ruta))
    os.makedirs(carpeta, exist_ok=True)
    descriptor, ruta_temporal = tempfile.mkstemp(dir=carpeta, suffix=".tmp")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as archivo:
            json.dump(datos, archivo, ensure_ascii=False, indent=2)
        os.replace(ruta_temporal, ruta)
    except Exception:
        logger.exception("No se pudo guardar el JSON %s", ruta)
        if os.path.exists(ruta_temporal):
            os.remove(ruta_temporal)
        raise
# ANCLAJE_FIN: ALMACEN_JSON
