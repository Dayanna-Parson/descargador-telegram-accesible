"""Recorta la exportación de un canal a lo que se quiere descargar."""
import logging
import os
from dataclasses import dataclass

from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)


@dataclass
class ResumenFiltro:
    total_con_archivo: int
    coinciden: int
    seleccionados: int


# ANCLAJE_INICIO: FILTRO_EXPORTACION
def filtrar_exportacion(ruta_entrada, ruta_salida, extensiones, limite=0):
    """Escribe en ruta_salida solo los mensajes con archivo del tipo pedido.

    extensiones vacío significa cualquier tipo. limite > 0 se queda con los
    primeros N, útil para probar con pocos archivos antes de bajarlo todo.
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
    seleccionados = coincidentes[:limite] if limite and limite > 0 else coincidentes
    guardar_json_atomico(ruta_salida, dict(datos, messages=seleccionados))
    return ResumenFiltro(len(con_archivo), len(coincidentes), len(seleccionados))
# ANCLAJE_FIN: FILTRO_EXPORTACION
