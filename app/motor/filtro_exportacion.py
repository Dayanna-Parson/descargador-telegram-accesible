"""Recorta la exportación de un canal a lo que se quiere descargar."""
import logging
import os
import re
from dataclasses import dataclass

from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)


@dataclass
class ResumenFiltro:
    total_con_archivo: int
    coinciden: int
    seleccionados: int
    ya_descargados: int = 0


# ANCLAJE_INICIO: FILTRO_EXPORTACION
def ids_de_mensajes_descargados(carpeta, id_canal):
    """Identificadores de mensaje de los archivos ya terminados en carpeta.

    tdl guarda cada archivo como «<idCanal>_<idMensaje>_nombre»; los .tmp son descargas a medias.
    """
    patron = re.compile(r"^{}_(\d+)_".format(re.escape(str(id_canal))))
    ids = set()
    for _carpeta_actual, _subcarpetas, archivos in os.walk(carpeta):
        for archivo in archivos:
            coincidencia = patron.match(archivo)
            if coincidencia and not archivo.lower().endswith(".tmp"):
                ids.add(int(coincidencia.group(1)))
    return ids


def filtrar_exportacion(ruta_entrada, ruta_salida, extensiones, limite=0, ya_descargados=()):
    """Escribe en ruta_salida solo los mensajes con archivo del tipo pedido que aún faltan.

    extensiones vacío significa cualquier tipo. ya_descargados son identificadores de mensaje que
    no se vuelven a pedir: así tdl no pierde minutos revisando lo que ya está bajado. limite > 0
    se queda con los primeros N pendientes, útil para probar con pocos archivos.
    """
    datos = leer_json(ruta_entrada, None)
    if not isinstance(datos, dict) or not isinstance(datos.get("messages"), list):
        raise ValueError("La exportación del canal no tiene el formato esperado.")
    permitidas = {e.lstrip(".").lower() for e in extensiones or []}
    con_archivo = [m for m in datos["messages"] if isinstance(m, dict) and m.get("file")]
    coincidentes = [
        m for m in con_archivo
        if not permitidas or os.path.splitext(m["file"])[1].lstrip(".").lower() in permitidas
    ]
    hechos = set(ya_descargados)
    pendientes = [m for m in coincidentes if m.get("id") not in hechos]
    seleccionados = pendientes[:limite] if limite and limite > 0 else pendientes
    guardar_json_atomico(ruta_salida, dict(datos, messages=seleccionados))
    return ResumenFiltro(len(con_archivo), len(coincidentes), len(seleccionados),
                         len(coincidentes) - len(pendientes))
# ANCLAJE_FIN: FILTRO_EXPORTACION
