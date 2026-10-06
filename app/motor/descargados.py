"""Registro de lo ya descargado de cada canal, que sobrevive a clasificar o mover los archivos.

tdl nombra cada archivo «<idCanal>_<idMensaje>_nombre». Al clasificar se quita ese prefijo, y sin
él no habría forma de saber qué mensajes ya se bajaron: pulsar Descargar volvería a bajar todo.
"""
import logging
import os
import re

from app.config_rutas import RUTA_DESCARGADOS
from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)

_PREFIJO = re.compile(r"^(-?\d+)_(\d+)_")


# ANCLAJE_INICIO: DESCARGADOS
def ids_de_nombre(nombre_o_ruta):
    """(id_canal, id_mensaje) leído del prefijo de tdl, o None si el nombre no lo lleva."""
    nombre = re.split(r"[\\/]", nombre_o_ruta)[-1]
    coincidencia = _PREFIJO.match(nombre)
    return (coincidencia.group(1), int(coincidencia.group(2))) if coincidencia else None


def cargar_descargados(ruta=RUTA_DESCARGADOS):
    """{id_canal: {ids de mensaje}}; lo que no sea válido se descarta."""
    datos = leer_json(ruta, {})
    resultado = {}
    if isinstance(datos, dict):
        for canal, ids in datos.items():
            if isinstance(ids, list):
                resultado[str(canal)] = {i for i in ids if isinstance(i, int) and not isinstance(i, bool)}
    return resultado


def anotar_rutas(rutas, ruta=RUTA_DESCARGADOS):
    """Apunta como descargados los mensajes de estos archivos. Devuelve cuántos son nuevos."""
    registro = cargar_descargados(ruta)
    nuevos = 0
    for archivo in rutas:
        par = ids_de_nombre(archivo)
        if par and par[1] not in registro.setdefault(par[0], set()):
            registro[par[0]].add(par[1])
            nuevos += 1
    if nuevos:
        guardar_json_atomico(ruta, {canal: sorted(ids) for canal, ids in registro.items()})
    return nuevos


def ids_de(id_canal, ruta=RUTA_DESCARGADOS):
    return set(cargar_descargados(ruta).get(str(id_canal), set()))


def reconstruir_desde_movimientos(carpeta_registros, ruta=RUTA_DESCARGADOS):
    """Rehace el registro con las clasificaciones ya hechas (los movimientos_*.json guardan el origen).

    Los .deshecho no cuentan: sus archivos volvieron a su sitio con el prefijo puesto.
    """
    if not os.path.isdir(carpeta_registros):
        return 0
    rutas = []
    for archivo in sorted(os.listdir(carpeta_registros)):
        if archivo.startswith("movimientos_") and archivo.endswith(".json"):
            for entrada in leer_json(os.path.join(carpeta_registros, archivo), []):
                if isinstance(entrada, dict) and isinstance(entrada.get("origen"), str):
                    rutas.append(entrada["origen"])
    return anotar_rutas(rutas, ruta)
# ANCLAJE_FIN: DESCARGADOS
