"""Ajustes del usuario que se recuerdan entre sesiones (velocidad de descarga)."""
import logging

from app.config_rutas import RUTA_AJUSTES
from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)

# ANCLAJE_INICIO: AJUSTES_USUARIO
LIMITES = {"hilos": (1, 16), "simultaneas": (1, 8)}
VALORES_POR_DEFECTO = {"hilos": 4, "simultaneas": 2, "takeout": False}


def cargar_ajustes(ruta=RUTA_AJUSTES):
    """Lee los ajustes; lo que falte, esté corrupto o fuera de rango vuelve al valor de fábrica."""
    guardados = leer_json(ruta, {})
    ajustes = dict(VALORES_POR_DEFECTO)
    if not isinstance(guardados, dict):
        return ajustes
    for clave, (minimo, maximo) in LIMITES.items():
        valor = guardados.get(clave)
        if isinstance(valor, int) and not isinstance(valor, bool):
            ajustes[clave] = min(max(valor, minimo), maximo)
    if isinstance(guardados.get("takeout"), bool):
        ajustes["takeout"] = guardados["takeout"]
    return ajustes


def guardar_ajustes(ajustes, ruta=RUTA_AJUSTES):
    guardar_json_atomico(ruta, {clave: ajustes[clave] for clave in VALORES_POR_DEFECTO})
# ANCLAJE_FIN: AJUSTES_USUARIO
