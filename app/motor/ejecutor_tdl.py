"""Envoltorio de tdl: construye los comandos y los ejecuta en un hilo secundario.

Ningún método de esta clase toca la interfaz. Las funciones de retorno
(al_linea, al_terminar) se llaman desde el hilo de trabajo, así que la
interfaz debe pasarlas siempre por wx.CallAfter.
"""
import csv
import json
import logging
import os
import re
import subprocess
import threading

from app.config_rutas import RUTA_REGISTROS, RUTA_TDL

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


def comando_exportar_chat(chat, ruta_json, con_texto=True):
    """Exporta la lista de mensajes del canal; con_texto añade el pie de cada mensaje (puede traer el título)."""
    comando = ["chat", "export", "-c", str(chat), "-o", ruta_json]
    if con_texto:
        comando.append("--with-content")
    return comando


def comando_descargar(ruta_json, carpeta_destino, extensiones=None, hilos=4, simultaneas=2,
                      takeout=False, ocultar_estadisticas=True):
    """Comando de descarga. hilos = por archivo; simultaneas = archivos a la vez.

    --pool es el número de conexiones con los servidores de Telegram (8 por
    defecto): hay que subirlo a la par que hilos x simultaneas o no aporta nada.
    """
    comando = [
        "dl", "-f", ruta_json, "-d", carpeta_destino,
        "--continue", "--skip-same",
        "-t", str(hilos), "-l", str(simultaneas),
        "--pool", str(min(max(8, hilos * simultaneas), 64)),
    ]
    if takeout:
        comando.append("--takeout")
    if ocultar_estadisticas:
        # Oculta la línea de uso de CPU y memoria de tdl; la barra de progreso se sigue pintando.
        comando.append("--disable-progress-ps")
    if extensiones:
        comando += ["-i", ",".join(e.lstrip(".").lower() for e in extensiones)]
    return comando
# ANCLAJE_FIN: TDL_COMANDOS


# ANCLAJE_INICIO: TDL_PARSEO
_PATRON_PROGRESO = re.compile(r"\d+(?:[.,]\d+)?\s*%|\d\s*[KMG]i?B/s", re.IGNORECASE)


_PATRON_ARCHIVO = re.compile(
    r"(?P<porcentaje>\d+(?:[.,]\d+)?)%\s*\[[^\]]*\]\s*\[[^\]]*?\bin\s+[^;\]]+;\s*~ETA:\s*(?P<eta>[^;\]]+);"
    r"\s*(?P<velocidad>[\d.,]+\s*[KMG]?B/s)\]", re.IGNORECASE)
_PATRON_TOTAL = re.compile(r"^\[[#.\s]+\]\s*\[(?P<tiempo>[^;\]]+);\s*(?P<velocidad>[\d.,]+\s*[KMG]?B/s)\]", re.IGNORECASE)
_PATRON_VELOCIDAD = re.compile(r"(?P<numero>[\d.,]+)\s*(?P<unidad>[KMG]?)B/s", re.IGNORECASE)


def interpretar_progreso(linea):
    """Extrae datos de las líneas de progreso de tdl.

    Devuelve {"tipo": "archivo", "porcentaje", "velocidad", "eta"} para la línea de un archivo,
    {"tipo": "total", "velocidad", "tiempo"} para la barra general, o None si no es ninguna.
    tdl pinta un bloque (una línea por archivo en curso y la general al final) varias veces por segundo.
    """
    coincidencia = _PATRON_ARCHIVO.search(linea)
    if coincidencia:
        return {"tipo": "archivo", "porcentaje": float(coincidencia["porcentaje"].replace(",", ".")),
                "velocidad": coincidencia["velocidad"], "eta": coincidencia["eta"].strip()}
    coincidencia = _PATRON_TOTAL.search(linea)
    if coincidencia:
        return {"tipo": "total", "velocidad": coincidencia["velocidad"], "tiempo": coincidencia["tiempo"].strip()}
    return None


def velocidad_hablada(texto):
    """«4.12 MB/s» -> «4,12 megabytes por segundo», para decirlo por voz."""
    coincidencia = _PATRON_VELOCIDAD.search(texto)
    if not coincidencia:
        return texto
    unidades = {"": "bytes", "K": "kilobytes", "M": "megabytes", "G": "gigabytes"}
    return "{} {} por segundo".format(coincidencia["numero"].replace(".", ","),
                                       unidades[coincidencia["unidad"].upper()])


def velocidad_en_bytes(texto):
    """«4.12 MB/s» -> bytes por segundo; 0 si no se entiende."""
    coincidencia = _PATRON_VELOCIDAD.search(texto)
    if not coincidencia:
        return 0.0
    factor = {"": 1, "K": 1024, "M": 1024 ** 2, "G": 1024 ** 3}[coincidencia.group("unidad").upper()]
    try:
        return float(coincidencia.group("numero").replace(",", ".")) * factor
    except ValueError:
        return 0.0


def es_linea_de_progreso(linea):
    """Indica si una línea es la barra de progreso que tdl redibuja varias veces por segundo."""
    return bool(_PATRON_PROGRESO.search(linea))


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


# ANCLAJE_INICIO: TDL_PROCESOS
def _parsear_tasklist(texto, nombre_imagen):
    """PID de los procesos con ese nombre en la salida CSV de «tasklist»."""
    pids = []
    for fila in csv.reader(texto.splitlines()):
        if len(fila) >= 2 and fila[0].lower() == nombre_imagen.lower() and fila[1].isdigit():
            pids.append(int(fila[1]))
    return pids


def procesos_tdl_ajenos(excluir_pid=None, nombre_imagen="tdl.exe"):
    """PID de otros tdl en marcha, por ejemplo de una sesión anterior cerrada sin detenerlo.

    Solo en Windows; en otros sistemas devuelve una lista vacía.
    """
    if os.name != "nt":
        return []
    try:
        resultado = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq {}".format(nombre_imagen), "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        logger.exception("No se pudo consultar la lista de procesos")
        return []
    return [pid for pid in _parsear_tasklist(resultado.stdout, nombre_imagen) if pid != excluir_pid]


def detener_procesos(pids):
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True, timeout=15,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except (OSError, subprocess.SubprocessError):
            logger.exception("No se pudo detener el proceso %s", pid)
# ANCLAJE_FIN: TDL_PROCESOS


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
        logger.info("Lanzando tdl: %s", comando)
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

    def pid(self):
        return self._proceso.pid if self.en_ejecucion() else None

    def detener_y_esperar(self, segundos=5):
        """Detiene tdl y espera a que el proceso desaparezca; si no lo hace, lo mata."""
        if self._proceso is None or self._proceso.poll() is not None:
            return
        self._proceso.terminate()
        try:
            self._proceso.wait(timeout=segundos)
        except subprocess.TimeoutExpired:
            logger.warning("tdl no se detuvo a tiempo; se fuerza el cierre")
            self._proceso.kill()
            try:
                self._proceso.wait(timeout=segundos)
            except subprocess.TimeoutExpired:
                logger.error("No se pudo cerrar el proceso de tdl")

    def cancelar(self):
        """Detiene tdl. Al relanzar la descarga, --continue retoma lo pendiente."""
        if self.en_ejecucion():
            self._proceso.terminate()
# ANCLAJE_FIN: TDL_EJECUTOR


# ANCLAJE_INICIO: TDL_CONSOLA
def _texto_lote(ruta_tdl, argumentos):
    """Contenido del .bat que ejecuta tdl y deja la ventana abierta al terminar."""
    return "\n".join([
        "@echo off",
        subprocess.list2cmdline([ruta_tdl] + list(argumentos)),
        "echo.",
        "echo Pulsa una tecla para cerrar esta ventana.",
        "pause >nul",
        "",
    ])


def abrir_en_consola(argumentos, ruta_tdl=None, ruta_lote=None):
    """Ejecuta tdl en una ventana de consola propia, para los pasos interactivos.

    Devuelve el proceso de esa ventana. Las preguntas y errores de tdl se ven
    y se leen directamente en ella con el lector de pantalla.
    """
    ruta_tdl = ruta_tdl or RUTA_TDL
    ruta_lote = ruta_lote or os.path.join(RUTA_REGISTROS, "tdl_consola.bat")
    os.makedirs(os.path.dirname(ruta_lote), exist_ok=True)
    codificacion = "oem" if os.name == "nt" else "utf-8"
    with open(ruta_lote, "w", encoding=codificacion, newline="\r\n") as archivo:
        archivo.write(_texto_lote(ruta_tdl, argumentos))
    logger.info("Abriendo tdl en consola: %s", argumentos)
    return subprocess.Popen([ruta_lote], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
# ANCLAJE_FIN: TDL_CONSOLA
