"""Descarga, descomprime e instala tdl.exe en la carpeta bin del programa."""
import logging
import os
import tempfile
import urllib.request
import zipfile

from app.config_rutas import RUTA_BIN

logger = logging.getLogger(__name__)

# ANCLAJE_INICIO: INSTALADOR_TDL_CONSTANTES
VERSION_TDL = "v0.20.3"
URL_TDL = (
    "https://github.com/iyear/tdl/releases/download/"
    + VERSION_TDL + "/tdl_Windows_64bit.zip"
)
NOMBRE_EJECUTABLE = "tdl.exe"
TAMANO_BLOQUE = 64 * 1024
TIEMPO_ESPERA_SEGUNDOS = 30
# ANCLAJE_FIN: INSTALADOR_TDL_CONSTANTES


class ErrorInstalacionTdl(Exception):
    """Error de instalación con un mensaje ya redactado para el usuario."""


# ANCLAJE_INICIO: INSTALADOR_TDL_DESCARGA
def _descargar(url, ruta_zip, al_progreso):
    """Descarga el zip. al_progreso recibe un entero de 0 a 100 cada vez que cambia."""
    peticion = urllib.request.Request(url, headers={"User-Agent": "DescargadorTelegramAccesible"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIEMPO_ESPERA_SEGUNDOS) as respuesta, \
                open(ruta_zip, "wb") as destino:
            total = int(respuesta.headers.get("Content-Length") or 0)
            recibido = 0
            ultimo_porcentaje = -1
            while True:
                bloque = respuesta.read(TAMANO_BLOQUE)
                if not bloque:
                    break
                destino.write(bloque)
                recibido += len(bloque)
                if total and al_progreso:
                    porcentaje = int(recibido * 100 / total)
                    if porcentaje != ultimo_porcentaje:
                        ultimo_porcentaje = porcentaje
                        al_progreso(porcentaje)
    except OSError as error:
        logger.exception("No se pudo descargar tdl desde %s", url)
        raise ErrorInstalacionTdl(
            "No se pudo descargar tdl. Comprueba tu conexión a internet."
        ) from error
# ANCLAJE_FIN: INSTALADOR_TDL_DESCARGA


# ANCLAJE_INICIO: INSTALADOR_TDL_EXTRACCION
def _extraer_ejecutable(ruta_zip, carpeta_temporal, nombre_ejecutable):
    """Saca solo el ejecutable del zip, leyéndolo en memoria para no usar rutas del zip."""
    try:
        with zipfile.ZipFile(ruta_zip) as archivo_zip:
            miembro = next(
                (n for n in archivo_zip.namelist()
                 if os.path.basename(n).lower() == nombre_ejecutable.lower()),
                None,
            )
            if miembro is None:
                raise ErrorInstalacionTdl(
                    "El archivo descargado no contiene {}.".format(nombre_ejecutable)
                )
            ruta_extraida = os.path.join(carpeta_temporal, nombre_ejecutable)
            with archivo_zip.open(miembro) as origen, open(ruta_extraida, "wb") as destino:
                while True:
                    bloque = origen.read(TAMANO_BLOQUE)
                    if not bloque:
                        break
                    destino.write(bloque)
            return ruta_extraida
    except zipfile.BadZipFile as error:
        logger.exception("El archivo descargado no es un zip válido")
        raise ErrorInstalacionTdl("El archivo descargado está dañado. Inténtalo de nuevo.") from error
# ANCLAJE_FIN: INSTALADOR_TDL_EXTRACCION


# ANCLAJE_INICIO: INSTALADOR_TDL_INSTALAR
def instalar_tdl(carpeta_bin=None, url=URL_TDL, al_progreso=None, nombre_ejecutable=NOMBRE_EJECUTABLE):
    """Descarga el zip, extrae el ejecutable y lo coloca en carpeta_bin.

    Devuelve la ruta del ejecutable instalado. Lanza ErrorInstalacionTdl con un
    mensaje apto para mostrar o decir por voz. Debe llamarse desde un hilo
    secundario: bloquea mientras descarga.
    """
    carpeta_bin = carpeta_bin or RUTA_BIN
    os.makedirs(carpeta_bin, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=carpeta_bin) as carpeta_temporal:
        ruta_zip = os.path.join(carpeta_temporal, "tdl.zip")
        _descargar(url, ruta_zip, al_progreso)
        ruta_extraida = _extraer_ejecutable(ruta_zip, carpeta_temporal, nombre_ejecutable)
        destino = os.path.join(carpeta_bin, nombre_ejecutable)
        try:
            os.replace(ruta_extraida, destino)
        except OSError as error:
            logger.exception("No se pudo colocar %s en %s", nombre_ejecutable, carpeta_bin)
            raise ErrorInstalacionTdl(
                "No se pudo guardar tdl. Si se está usando, espera a que termine y vuelve a probar."
            ) from error
    return destino
# ANCLAJE_FIN: INSTALADOR_TDL_INSTALAR
