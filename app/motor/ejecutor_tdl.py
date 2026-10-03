"""Envoltorio de tdl: construye los comandos y los ejecuta en un hilo secundario.

Ningún método de esta clase toca la interfaz. Las funciones de retorno
(al_linea, al_terminar) se llaman desde el hilo de trabajo, así que la
interfaz debe pasarlas siempre por wx.CallAfter.
"""
import json
import logging
import os
import re
import subprocess
import threading

from app.config_rutas import RUTA_TDL

logger = logging.getLogger(__name__)

_PATRON_ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


# ANCLAJE_INICIO: TDL_COMANDOS
# Todas las opciones de línea de comandos de tdl viven aquí. Si una versión
# nueva de tdl cambia alguna, es el único bloque que hay que tocar.
def comando_iniciar_sesion_escritorio():
    return ["login", "-T", "desktop"]


def comando_iniciar_sesion_codigo():
    return ["login", "-T", "code"]


def comando_listar_chats():
    return ["chat", "ls", "-o", "json"]


def comando_exportar_chat(chat, ruta_json):
    return ["chat", "export", "-c", str(chat), "-o", ruta_json]


def comando_descargar(ruta_json, carpeta_destino, extensiones=None, hilos=4, limite=2):
    comando = [
        "dl", "-f", ruta_json, "-d", carpeta_destino,
        "--continue", "--skip-same",
        "-t", str(hilos), "-l", str(limite),
    ]
    if extensiones:
        comando += ["-i", ",".join(e.lstrip(".").lower() for e in extensiones)]
    return comando
# ANCLAJE_FIN: TDL_COMANDOS


# ANCLAJE_INICIO: TDL_PARSEO
def parsear_lista_chats(texto):
    """Convierte la salida de «chat ls -o json» en [{'id', 'nombre', 'usuario'}].

    Es tolerante: busca el primer corchete de apertura por si tdl antepone
    líneas de información, y acepta nombres de campo habituales.
    """
    inicio = texto.find("[")
    if inicio < 0:
        return []
    try:
        datos = json.loads(texto[inicio:])
    except ValueError:
        logger.exception("La lista de chats de tdl no es un JSON válido")
        return []
    chats = []
    for elemento in datos:
        if not isinstance(elemento, dict):
            continue
        identificador = elemento.get("id")
        nombre = elemento.get("visible_name") or elemento.get("title") or elemento.get("name") or ""
        if identificador is None:
            continue
        chats.append({
            "id": str(identificador),
            "nombre": str(nombre),
            "usuario": str(elemento.get("username") or ""),
        })
    return chats


def contar_archivos_exportados(ruta_json):
    """Cuenta los mensajes con archivo en un JSON exportado por tdl."""
    try:
        with open(ruta_json, "r", encoding="utf-8") as archivo:
            datos = json.load(archivo)
    except (OSError, ValueError):
        logger.exception("No se pudo leer la exportación %s", ruta_json)
        return 0
    mensajes = datos.get("messages", []) if isinstance(datos, dict) else []
    return sum(1 for m in mensajes if isinstance(m, dict) and m.get("file"))
# ANCLAJE_FIN: TDL_PARSEO


# ANCLAJE_INICIO: TDL_EJECUTOR
class EjecutorTdl:
    """Lanza tdl como proceso hijo y reenvía su salida línea a línea."""

    def __init__(self, ruta_tdl=None):
        self.ruta_tdl = ruta_tdl or RUTA_TDL
        self._proceso = None
        self._hilo = None

    def disponible(self):
        return os.path.isfile(self.ruta_tdl)

    def en_ejecucion(self):
        return self._proceso is not None and self._proceso.poll() is None

    def ejecutar(self, argumentos, al_linea, al_terminar):
        """Arranca tdl en un hilo. al_terminar recibe el código de salida."""
        if self.en_ejecucion():
            raise RuntimeError("Ya hay una operación de tdl en curso.")
        comando = [self.ruta_tdl] + list(argumentos)
        banderas = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self._proceso = subprocess.Popen(
                comando,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=banderas,
            )
        except OSError:
            logger.exception("No se pudo lanzar tdl: %s", comando)
            al_terminar(-1)
            return
        self._hilo = threading.Thread(
            target=self._leer_salida, args=(al_linea, al_terminar), daemon=True
        )
        self._hilo.start()

    def _leer_salida(self, al_linea, al_terminar):
        proceso = self._proceso
        try:
            for linea in proceso.stdout:
                limpia = _PATRON_ANSI.sub("", linea).replace("\r", "\n").strip()
                if limpia:
                    al_linea(limpia)
        except Exception:
            logger.exception("Error leyendo la salida de tdl")
        codigo = proceso.wait()
        for flujo in (proceso.stdin, proceso.stdout):
            try:
                flujo.close()
            except OSError:
                logger.exception("No se pudo cerrar un flujo de tdl")
        al_terminar(codigo)

    def enviar_entrada(self, texto):
        """Escribe una línea en la entrada estándar (p. ej. el código de acceso)."""
        if not self.en_ejecucion():
            return
        try:
            self._proceso.stdin.write(texto + "\n")
            self._proceso.stdin.flush()
        except OSError:
            logger.exception("No se pudo escribir en la entrada de tdl")

    def cancelar(self):
        """Detiene tdl. Al relanzar la descarga, --continue retoma lo pendiente."""
        if self.en_ejecucion():
            self._proceso.terminate()
# ANCLAJE_FIN: TDL_EJECUTOR
