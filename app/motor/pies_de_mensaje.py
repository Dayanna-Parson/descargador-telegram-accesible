"""Pies (texto) de los mensajes de las exportaciones, para clasificar archivos sin nombre útil."""
import logging
import os
import re

from app.motor.almacen_json import leer_json

logger = logging.getLogger(__name__)

# ANCLAJE_INICIO: PIES_DE_MENSAJE
_PREFIJO_DE_TDL = re.compile(r"^(-?\d+)_(\d+)_(?=.)")
_CAPITULO_PRINCIPAL = re.compile(r"#Capa?(\d+)(?![\dA-Za-z])")
_CAPITULO_DE_SEGMENTO = re.compile(r"#Capa?(\d+)[A-Za-z]")
_ESPECIAL = re.compile(r"#Especial(\d+)(?!\d)")
_TITULO_DE_SEGMENTO = re.compile(r"#(?:Capa?)?\d+[A-Za-z]*\s*(?:=>|->)\s*([^#]+)")
_TITULOS_DE_ESPECIAL = re.compile(r"(?:=>|->)\s*([^#]+)")
_SEPARADOR_DE_ESPECIAL = re.compile(r"\s+[—–]\s+")
_ALTERNATIVA = re.compile(r"\s*\|\|\s*")
MAXIMO_CARACTERES_DE_TITULOS = 46


def capitulos_del_pie(pie):
    """Números de capítulo que contiene el vídeo según su pie, de menor a mayor.

    Se fía de las etiquetas principales («#Cap33»); las de segmento («#Cap33B») traen erratas.
    """
    capitulos = {int(n) for n in _CAPITULO_PRINCIPAL.findall(pie)}
    if not capitulos:
        capitulos = {int(n) for n in _CAPITULO_DE_SEGMENTO.findall(pie)}
    return sorted(capitulos)


def episodios_del_pie(pie):
    """«033» o, si el vídeo junta varios capítulos seguidos, «959 a 960»; cadena vacía si no hay."""
    capitulos = capitulos_del_pie(pie)
    if not capitulos:
        return ""
    if capitulos[-1] - capitulos[0] == 1:
        return "{:03} a {:03}".format(capitulos[0], capitulos[-1])
    return "{:03}".format(capitulos[0])


def _limpiar_titulo(texto):
    primero = _ALTERNATIVA.split(texto.strip())[0]
    return re.sub(r"\s+", " ", primero.replace("/", "-").replace("\\", "-")).strip(" .-–—")


def titulos_del_pie(pie, maximo=MAXIMO_CARACTERES_DE_TITULOS):
    """Títulos de los segmentos del pie, unidos por comas y recortados sin partir un título.

    Devuelve «» o un texto que empieza por « - », listo para colgar de un nombre de archivo.
    """
    titulos = [_limpiar_titulo(t) for t in _TITULO_DE_SEGMENTO.findall(pie)]
    if not titulos:
        coincidencia = _TITULOS_DE_ESPECIAL.search(pie)
        if coincidencia:
            titulos = [_limpiar_titulo(t) for t in _SEPARADOR_DE_ESPECIAL.split(coincidencia.group(1))]
    elegidos = []
    for titulo in titulos:
        if titulo and (not elegidos or titulo != elegidos[-1]):
            elegidos.append(titulo)
    if not elegidos:
        return ""
    texto = ""
    for titulo in elegidos:
        candidato = titulo if not texto else texto + ", " + titulo
        if len(candidato) > maximo:
            break
        texto = candidato
    if not texto:
        corte = elegidos[0][:maximo - 1]
        texto = (corte.rsplit(" ", 1)[0] if " " in corte else corte).rstrip(" ,.-") + "…"
    return " - " + texto


class PiesDeMensaje:
    """Busca el pie de un archivo por su identificador de mensaje o, si ya no lo lleva, por su nombre."""

    def __init__(self):
        self._por_mensaje = {}
        self._por_nombre = {}
        self._ambiguos = set()
        self._por_capitulo = {}
        self._por_especial = {}
        self._renombres = {}

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
        capitulos = capitulos_del_pie(texto)
        if capitulos and not _ESPECIAL.search(texto):
            self._por_capitulo.setdefault(capitulos[0], texto)
        especial = _ESPECIAL.search(texto)
        if especial:
            self._por_especial.setdefault(int(especial.group(1)), texto)

    def anotar_renombre(self, nombre_origen, nombre_destino):
        """Recuerda que un archivo se llamaba nombre_origen antes de que clasificar le pusiera nombre_destino."""
        if nombre_origen and nombre_destino and nombre_origen.lower() != nombre_destino.lower():
            self._renombres[nombre_destino.lower()] = nombre_origen

    def por_numero(self, tipo, numero):
        """Pie de un capítulo («episodio») o de un especial por su número; cadena vacía si no hay."""
        indice = self._por_especial if tipo == "especial" else self._por_capitulo
        return indice.get(numero, "")

    def buscar(self, nombre_archivo):
        """Pie del archivo; si ya se renombró al clasificar, sigue el rastro hasta su nombre original."""
        visto = set()
        actual = nombre_archivo
        while actual and actual.lower() not in visto:
            texto = self._buscar_directo(actual)
            if texto:
                return texto
            visto.add(actual.lower())
            actual = self._renombres.get(actual.lower())
        return ""

    def _buscar_directo(self, nombre_archivo):
        coincidencia = _PREFIJO_DE_TDL.match(nombre_archivo)
        if coincidencia:
            texto = self._por_mensaje.get((coincidencia.group(1), int(coincidencia.group(2))))
            if texto:
                return texto
            nombre_archivo = nombre_archivo[coincidencia.end():]
        if nombre_archivo in self._ambiguos:
            return ""
        return self._por_nombre.get(nombre_archivo, "")


def _nombre_base(ruta):
    return re.split(r"[\\/]", ruta)[-1]


def _leer_renombres(pies, carpeta_registros):
    """Aprende de los registros de clasificar cómo se llamaba cada archivo antes de moverlo."""
    if not carpeta_registros or not os.path.isdir(carpeta_registros):
        return
    for archivo in sorted(os.listdir(carpeta_registros)):
        if not (archivo.startswith("movimientos_") and archivo.endswith(".json")):
            continue
        registro = leer_json(os.path.join(carpeta_registros, archivo), [])
        if not isinstance(registro, list):
            continue
        for entrada in registro:
            if isinstance(entrada, dict) and isinstance(entrada.get("origen"), str) \
                    and isinstance(entrada.get("destino"), str):
                pies.anotar_renombre(_nombre_base(entrada["origen"]), _nombre_base(entrada["destino"]))


def cargar_pies(carpeta_exportaciones, carpeta_registros=None):
    """Lee las exportaciones y recoge el pie de cada mensaje con archivo.

    Con carpeta_registros también aprende los cambios de nombre de clasificaciones anteriores,
    para encontrar el pie de archivos que ya no se llaman como en el canal.
    """
    pies = PiesDeMensaje()
    _leer_renombres(pies, carpeta_registros)
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
