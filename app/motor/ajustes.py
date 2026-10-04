"""Ajustes del usuario que se recuerdan entre sesiones (velocidad de descarga y tamaños medios)."""
import logging

from app.config_rutas import RUTA_AJUSTES
from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)

# ANCLAJE_INICIO: AJUSTES_USUARIO
LIMITES = {"hilos": (1, 16), "simultaneas": (1, 8)}
VALORES_POR_DEFECTO = {"hilos": 4, "simultaneas": 2, "takeout": False, "tamanos_medios": {},
                       "ultimo_canal": "", "perfil": "", "carpeta_descarga": ""}
CLAVES_DE_TEXTO = ("ultimo_canal", "perfil", "carpeta_descarga")


def _es_entero(valor):
    return isinstance(valor, int) and not isinstance(valor, bool)


def cargar_ajustes(ruta=RUTA_AJUSTES):
    """Lee los ajustes; lo que falte, esté corrupto o fuera de rango vuelve al valor de fábrica.

    tamanos_medios guarda, por tipo de contenido, los bytes medios por archivo medidos en
    descargas anteriores; sirve para estimar si una descarga nueva cabe en el disco.
    """
    guardados = leer_json(ruta, {})
    ajustes = {clave: (dict(valor) if isinstance(valor, dict) else valor)
               for clave, valor in VALORES_POR_DEFECTO.items()}
    if not isinstance(guardados, dict):
        return ajustes
    for clave, (minimo, maximo) in LIMITES.items():
        valor = guardados.get(clave)
        if _es_entero(valor):
            ajustes[clave] = min(max(valor, minimo), maximo)
    if isinstance(guardados.get("takeout"), bool):
        ajustes["takeout"] = guardados["takeout"]
    for clave in CLAVES_DE_TEXTO:
        if isinstance(guardados.get(clave), str):
            ajustes[clave] = guardados[clave]
    medios = guardados.get("tamanos_medios")
    if isinstance(medios, dict):
        ajustes["tamanos_medios"] = {
            str(nombre): valor for nombre, valor in medios.items() if _es_entero(valor) and valor > 0
        }
    return ajustes


def guardar_ajustes(ajustes, ruta=RUTA_AJUSTES):
    guardar_json_atomico(
        ruta, {clave: ajustes.get(clave, defecto) for clave, defecto in VALORES_POR_DEFECTO.items()}
    )
# ANCLAJE_FIN: AJUSTES_USUARIO
