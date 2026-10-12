"""Pies (texto) de los mensajes de las exportaciones, para clasificar archivos sin nombre útil."""
import logging
import os
import re

from app.motor.almacen_json import leer_json

logger = logging.getLogger(__name__)

# ANCLAJE_INICIO: PIES_DE_MENSAJE
_PREFIJO_DE_TDL = re.compile(r"^(-?\d+)_(\d+)_(?=.)")


class PiesDeMensaje:
    """Busca el pie de un archivo por su identificador de mensaje o, si ya no lo lleva, por su nombre."""

    def __init__(self):
        self._por_mensaje = {}
        self._por_nombre = {}
        self._ambiguos = set()

    def __len__(self):
        return len(self._por_mensaje)

    def anotar(self, id_canal, id_mensaje, nombre_archivo, texto):
        if not texto or not texto.strip():
            return
        self._por_mensaje[(str(id_canal), int(id_mensaje))] = texto
        previo = self._por_nombre.get(nombre_archivo)
        if previo is not None and previo != texto:
            self._ambiguos.add(nombre_archivo)
        self._por_nombre[nombre_archivo] = texto

    def buscar(self, nombre_archivo):
        """Pie del archivo, o cadena vacía si no se conoce o si dos mensajes distintos comparten nombre."""
        coincidencia = _PREFIJO_DE_TDL.match(nombre_archivo)
        if coincidencia:
            texto = self._por_mensaje.get((coincidencia.group(1), int(coincidencia.group(2))))
            if texto:
                return texto
            nombre_archivo = nombre_archivo[coincidencia.end():]
        if nombre_archivo in self._ambiguos:
            return ""
        return self._por_nombre.get(nombre_archivo, "")


def cargar_pies(carpeta_exportaciones):
    """Lee todas las exportaciones de la carpeta y recoge el pie de cada mensaje con archivo."""
    pies = PiesDeMensaje()
    if not os.path.isdir(carpeta_exportaciones):
        return pies
    for archivo in sorted(os.listdir(carpeta_exportaciones)):
        if not archivo.lower().endswith(".json"):
            continue
        datos = leer_json(os.path.join(carpeta_exportaciones, archivo), None)
        if not isinstance(datos, dict) or not isinstance(datos.get("messages"), list):
            continue
        for mensaje in datos["messages"]:
            if not isinstance(mensaje, dict) or not mensaje.get("file") or not isinstance(mensaje.get("id"), int):
                continue
            texto = mensaje.get("text")
            if isinstance(texto, str):
                pies.anotar(datos.get("id", ""), mensaje["id"], mensaje["file"], texto)
    return pies
# ANCLAJE_FIN: PIES_DE_MENSAJE
