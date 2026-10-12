"""Dónde se guarda la lista exportada de cada canal y cómo de antigua es."""
import logging
import os
import shutil
import time

from app.motor.clasificador import nombre_seguro

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: EXPORTACIONES
def ruta_de_exportacion(canal, carpeta_exportaciones, carpeta_antigua):
    """Ruta de la lista exportada del canal: «<Nombre del canal> (<id>).json».

    Se localiza por el identificador, así que sigue valiendo si el canal cambia de nombre.
    Las listas con el formato antiguo («exportacion_<id>.json», sueltas en la carpeta de
    registros) se mueven y se renombran la primera vez que se piden.
    """
    sufijo = " ({}).json".format(nombre_seguro(canal["id"]))
    if os.path.isdir(carpeta_exportaciones):
        for archivo in sorted(os.listdir(carpeta_exportaciones)):
            if archivo.endswith(sufijo):
                return os.path.join(carpeta_exportaciones, archivo)
    nueva = os.path.join(carpeta_exportaciones, nombre_seguro(canal["nombre"]) + sufijo)
    antigua = os.path.join(carpeta_antigua, "exportacion_{}.json".format(canal["id"]))
    if os.path.isfile(antigua):
        try:
            os.makedirs(carpeta_exportaciones, exist_ok=True)
            shutil.move(antigua, nueva)
            return nueva
        except OSError:
            logger.exception("No se pudo mover la lista antigua %s", antigua)
            return antigua
    return nueva


def describir_antiguedad(ruta, ahora=None):
    """«hace 3 horas», «hace 2 días»... según la fecha de modificación del archivo."""
    segundos = max(0, (ahora if ahora is not None else time.time()) - os.path.getmtime(ruta))
    if segundos < 90:
        return "hace unos segundos"
    minutos = round(segundos / 60)
    if minutos < 60:
        return "hace {} minutos".format(minutos)
    horas = round(minutos / 60)
    if horas < 36:
        return "hace {} horas".format(horas) if horas != 1 else "hace una hora"
    return "hace {} días".format(round(horas / 24))
# ANCLAJE_FIN: EXPORTACIONES
