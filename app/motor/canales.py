"""Lista de canales de Telegram recordada entre sesiones, para no pedirla a tdl cada vez."""
import logging

from app.config_rutas import RUTA_CANALES
from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: CANALES_GUARDADOS
def cargar_canales(ruta=RUTA_CANALES):
    """Devuelve [{'id', 'nombre', 'usuario'}] guardados; lo que no sea válido se descarta."""
    datos = leer_json(ruta, [])
    if not isinstance(datos, list):
        return []
    canales = []
    for elemento in datos:
        if isinstance(elemento, dict) and elemento.get("id") and "nombre" in elemento:
            canales.append({"id": str(elemento["id"]), "nombre": str(elemento["nombre"]),
                            "usuario": str(elemento.get("usuario") or "")})
    return canales


def guardar_canales(canales, ruta=RUTA_CANALES):
    guardar_json_atomico(ruta, canales)
# ANCLAJE_FIN: CANALES_GUARDADOS
