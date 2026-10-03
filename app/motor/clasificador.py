"""Clasificación de archivos descargados mediante reglas configurables.

Cada regla es un diccionario con:
  nombre       texto descriptivo de la regla
  patron       expresión regular que se busca en el nombre del archivo
  carpeta      plantilla de la carpeta de destino (admite grupos con nombre)
  nombre_nuevo plantilla opcional del nombre final (por defecto, el mismo)

Las plantillas usan str.format con los grupos con nombre del patrón; los
valores numéricos se convierten a entero, así que sirve «{temporada:02}».
También están disponibles {nombre} (sin extensión) y {extension}.
"""
import logging
import os
import re
import shutil
from dataclasses import dataclass

from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)

_CARACTERES_PROHIBIDOS = re.compile(r'[<>:"|?*\x00-\x1f]')


@dataclass
class Movimiento:
    origen: str
    destino: str
    regla: str
    conflicto: str = ""


# ANCLAJE_INICIO: CLASIFICADOR_REGLAS
def _limpiar_componente(texto):
    limpio = _CARACTERES_PROHIBIDOS.sub("", texto).strip().rstrip(".")
    return limpio or "_"


def _valores_de_plantilla(coincidencia, nombre_archivo):
    nombre, extension = os.path.splitext(nombre_archivo)
    valores = {}
    for clave, valor in coincidencia.groupdict().items():
        if valor is None:
            continue
        valores[clave] = int(valor) if valor.isdigit() else valor.strip()
    valores.setdefault("nombre", nombre)
    valores["extension"] = extension
    return valores


def clasificar_nombre(nombre_archivo, reglas):
    """Devuelve (carpeta_relativa, nombre_final, nombre_regla) o None."""
    for regla in reglas:
        coincidencia = re.search(regla["patron"], nombre_archivo)
        if not coincidencia:
            continue
        valores = _valores_de_plantilla(coincidencia, nombre_archivo)
        try:
            carpeta = regla["carpeta"].format(**valores)
            final = regla.get("nombre_nuevo", "{nombre}{extension}").format(**valores)
        except (KeyError, IndexError, ValueError):
            logger.exception("La regla «%s» tiene una plantilla inválida", regla.get("nombre"))
            continue
        partes = [_limpiar_componente(p) for p in carpeta.replace("\\", "/").split("/") if p]
        return "/".join(partes), _limpiar_componente(final), regla.get("nombre", "")
    return None


def cargar_reglas(ruta_reglas):
    reglas = leer_json(ruta_reglas, [])
    return reglas if isinstance(reglas, list) else []
# ANCLAJE_FIN: CLASIFICADOR_REGLAS


# ANCLAJE_INICIO: CLASIFICADOR_PLAN
def planificar(carpeta_origen, carpeta_destino, reglas):
    """Calcula los movimientos sin tocar nada. Devuelve (movimientos, sin_clasificar)."""
    movimientos = []
    sin_clasificar = []
    destinos_usados = set()
    for carpeta_actual, _carpetas, archivos in os.walk(carpeta_origen):
        for archivo in sorted(archivos):
            ruta_origen = os.path.join(carpeta_actual, archivo)
            resultado = clasificar_nombre(archivo, reglas)
            if resultado is None:
                sin_clasificar.append(ruta_origen)
                continue
            carpeta_relativa, nombre_final, nombre_regla = resultado
            ruta_destino = os.path.join(carpeta_destino, *carpeta_relativa.split("/"), nombre_final)
            conflicto = ""
            if os.path.abspath(ruta_origen) == os.path.abspath(ruta_destino):
                continue
            if os.path.exists(ruta_destino):
                conflicto = "El destino ya existe."
            elif ruta_destino.lower() in destinos_usados:
                conflicto = "Otro archivo tiene el mismo destino."
            destinos_usados.add(ruta_destino.lower())
            movimientos.append(Movimiento(ruta_origen, ruta_destino, nombre_regla, conflicto))
    return movimientos, sin_clasificar
# ANCLAJE_FIN: CLASIFICADOR_PLAN


# ANCLAJE_INICIO: CLASIFICADOR_APLICAR
def aplicar(movimientos, ruta_registro):
    """Mueve los archivos sin conflicto y guarda un registro para poder deshacer.

    Devuelve (hechos, fallidos), listas de Movimiento.
    """
    hechos = []
    fallidos = []
    try:
        for movimiento in movimientos:
            if movimiento.conflicto:
                continue
            try:
                os.makedirs(os.path.dirname(movimiento.destino), exist_ok=True)
                shutil.move(movimiento.origen, movimiento.destino)
                hechos.append(movimiento)
            except OSError:
                logger.exception("No se pudo mover %s", movimiento.origen)
                fallidos.append(movimiento)
    finally:
        guardar_json_atomico(
            ruta_registro,
            [{"origen": m.origen, "destino": m.destino} for m in hechos],
        )
    return hechos, fallidos


def deshacer(ruta_registro):
    """Revierte los movimientos de un registro. Devuelve (revertidos, omitidos)."""
    registro = leer_json(ruta_registro, [])
    revertidos = 0
    omitidos = 0
    for entrada in reversed(registro):
        origen, destino = entrada["origen"], entrada["destino"]
        if not os.path.exists(destino) or os.path.exists(origen):
            omitidos += 1
            continue
        try:
            os.makedirs(os.path.dirname(origen), exist_ok=True)
            shutil.move(destino, origen)
            revertidos += 1
        except OSError:
            logger.exception("No se pudo deshacer el movimiento de %s", destino)
            omitidos += 1
    return revertidos, omitidos
# ANCLAJE_FIN: CLASIFICADOR_APLICAR
