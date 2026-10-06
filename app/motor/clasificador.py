"""Clasificación de archivos descargados mediante reglas configurables.

Cada regla es un diccionario con:
  nombre          texto descriptivo de la regla
  patron          expresión regular que se busca en el nombre del archivo; si no
                  coincide tal cual, se prueba sobre el nombre en minúsculas y
                  sin tildes, así que basta escribir los patrones sin tildes
  carpeta         plantilla de la carpeta de destino
  nombre_nuevo    plantilla opcional del nombre final (por defecto, el mismo)
  agrupar_series  opcional; si es verdadero, {serie} solo crea carpeta cuando
                  hay al menos dos archivos de la misma serie
  temporadas_desde opcional; lista [[episodio_inicial, temporada], ...] para deducir la
                  temporada de los archivos que solo traen número de episodio
  bloque          opcional; tamaño de los bloques de episodios para los que no se
                  conoce la temporada (por ejemplo 50: «Episodios 351 a 400»)

Las plantillas usan str.format con los grupos con nombre del patrón; los
valores numéricos se convierten a entero, así que sirve «{temporada:02}».
Además están disponibles:
  {nombre}     el nombre sin extensión
  {extension}  la extensión, con el punto
  {serie}      el grupo «serie» del patrón o, si no hay, la serie deducida del nombre
  {inicial}    letra por la que se ordena la serie (sin artículos), o «0-9» o «#»
  {ubicacion}  para reglas con grupo «episodio»: «Temporada 05» si se conoce o se deduce, y si
               no «Sin temporada/Episodios 351 a 400» (necesita la opción «bloque»)
"""
import logging
import os
import re
import shutil
import unicodedata
from collections import Counter
from dataclasses import dataclass

from app.motor.almacen_json import guardar_json_atomico, leer_json

logger = logging.getLogger(__name__)

_CARACTERES_PROHIBIDOS = re.compile(r'[<>:"|?*\x00-\x1f]')
LONGITUD_MAXIMA_COMPONENTE = 100
_ARTICULOS_INICIALES = {"el", "la", "los", "las", "un", "una", "unos", "unas", "the", "a", "an"}


@dataclass
class Movimiento:
    origen: str
    destino: str
    regla: str
    conflicto: str = ""


@dataclass
class Clasificacion:
    carpeta: str
    carpeta_sin_serie: str
    nombre_final: str
    regla: str
    clave_serie: str
    plantilla_carpeta: str = ""
    valores: dict = None
    serie: str = ""


# ANCLAJE_INICIO: CLASIFICADOR_TEXTO
_PREFIJO_NUMERICO = re.compile(r"^\s*\d{3}(?:\.-|\.|-)?[\s_]+(?=[^\d\s])")
_SEPARADOR_TITULO = re.compile(r"\s+[-–—·:]\s+|\.\s*[-–—]\s*")
_AGRUPADORES = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]")
_PALABRA_NUMERACION = (
    r"(?:vol|volumen|tomos?|parte|cap[ií]tulos?|temporada|no|num|n[uú]mero|integrales?|episodio)"
)
_NUMERACION_FINAL = re.compile(
    r"[\s\-–]*(?:\b" + _PALABRA_NUMERACION + r"\.?\s*)?#?\s*\d[\d\s,\-–+y]*$", re.IGNORECASE
)
_NUMERACION_CON_PALABRA = re.compile(
    r"[\s\-–]*\b" + _PALABRA_NUMERACION + r"\.?\s*#?\s*\d[\d\s,\-–+y]*$", re.IGNORECASE
)
_PALABRAS_FINALES = re.compile(r"\s+(?:usa|completo|completa|integral|integrales|especiales?)\s*$", re.IGNORECASE)


_PREFIJO_DE_TDL = re.compile(r"^-?\d+_\d+_(?=.)")


def quitar_prefijo_de_tdl(nombre_archivo):
    """tdl guarda los archivos como «<idCanal>_<idMensaje>_nombre»; devuelve el nombre original."""
    return _PREFIJO_DE_TDL.sub("", nombre_archivo, count=1)


def normalizar_texto(texto):
    """Minúsculas, sin tildes y con los guiones bajos convertidos en espacios."""
    descompuesto = unicodedata.normalize("NFKD", texto)
    sin_marcas = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_marcas.lower().replace("_", " ")


def extraer_serie(nombre_sin_extension):
    """Deduce el nombre de la serie quitando numeración, volúmenes y subtítulos.

    «Tomodachi Game Tomos 15-26» -> «Tomodachi Game»
    «Batman - La secta»          -> «Batman»
    «249 Iron Man de X 2 - Y»    -> «Iron Man de X»
    """
    original = re.sub(r"\s+", " ", nombre_sin_extension.replace("_", " ")).strip()
    texto = _PREFIJO_NUMERICO.sub("", original)
    texto = _SEPARADOR_TITULO.split(texto, maxsplit=1)[0]
    texto = _AGRUPADORES.sub("", texto)
    texto = _NUMERACION_FINAL.sub("", texto, count=1)
    anterior = None
    while anterior != texto:
        anterior = texto
        texto = _PALABRAS_FINALES.sub("", texto)
        texto = _NUMERACION_CON_PALABRA.sub("", texto, count=1)
    texto = re.sub(r"\s+", " ", texto).strip(" .-–—:,")
    return texto or original


def calcular_inicial(serie):
    """Letra de ordenación: ignora artículos; dígitos -> «0-9»; otro -> «#»."""
    palabras = normalizar_texto(serie).split()
    while len(palabras) > 1 and palabras[0] in _ARTICULOS_INICIALES:
        palabras.pop(0)
    for caracter in "".join(palabras):
        if caracter.isdigit():
            return "0-9"
        if caracter.isalpha():
            return caracter.upper()
    return "#"
# ANCLAJE_FIN: CLASIFICADOR_TEXTO


# ANCLAJE_INICIO: CLASIFICADOR_REGLAS
def _limpiar_componente(texto):
    limpio = _CARACTERES_PROHIBIDOS.sub("", texto).strip().rstrip(".")
    return limpio[:LONGITUD_MAXIMA_COMPONENTE].strip() or "_"


def _limpiar_nombre_de_archivo(nombre):
    """Como _limpiar_componente, pero sin recortar la extensión cuando el nombre es muy largo."""
    base, extension = os.path.splitext(nombre)
    if len(extension) > 10:
        base, extension = nombre, ""
    base = _CARACTERES_PROHIBIDOS.sub("", base).strip().rstrip(".")[:max(10, LONGITUD_MAXIMA_COMPONENTE - len(extension))]
    return (base.strip() + _CARACTERES_PROHIBIDOS.sub("", extension)) or "_"


def nombre_seguro(texto):
    """Convierte un texto cualquiera en un nombre válido de archivo o carpeta de Windows."""
    return _limpiar_componente(str(texto))


def _unir_carpeta(carpeta):
    partes = [_limpiar_componente(p) for p in carpeta.replace("\\", "/").split("/") if p.strip()]
    return "/".join(partes)


def _valores_de_plantilla(coincidencia, nombre_archivo):
    nombre, extension = os.path.splitext(nombre_archivo)
    valores = {}
    for clave, valor in coincidencia.groupdict().items():
        if valor is None:
            continue
        if valor.isdigit():
            valores[clave] = int(valor)
            continue
        texto = valor.replace("_", " ")
        if " " not in texto.strip():
            texto = texto.replace(".", " ")
        valores[clave] = re.sub(r"\s+", " ", texto).strip(" ._-–—")
    valores.setdefault("nombre", nombre)
    valores["extension"] = extension
    return valores


def _completar_episodio(valores, regla):
    """Deduce la temporada y la ubicación de los archivos con número de episodio."""
    episodio = valores.get("episodio")
    if not isinstance(episodio, int):
        return
    if "temporada" not in valores:
        for desde, temporada in sorted(regla.get("temporadas_desde", []), reverse=True):
            if episodio >= desde:
                valores["temporada"] = temporada
                break
    if "temporada" in valores:
        valores["ubicacion"] = "Temporada {:02}".format(int(valores["temporada"]))
    elif regla.get("bloque"):
        tamano = int(regla["bloque"])
        inicio = (episodio - 1) // tamano * tamano + 1
        valores["ubicacion"] = "Sin temporada/Episodios {:03} a {:03}".format(inicio, inicio + tamano - 1)


def _clasificar_detallado(nombre_archivo, reglas):
    """Aplica la primera regla que coincida. Devuelve Clasificacion o None."""
    nombre_archivo = quitar_prefijo_de_tdl(nombre_archivo)
    normalizado = normalizar_texto(nombre_archivo)
    base = os.path.splitext(nombre_archivo)[0]
    for regla in reglas:
        try:
            coincidencia = (re.search(regla["patron"], nombre_archivo)
                            or re.search(regla["patron"], normalizado))
        except re.error:
            logger.exception("La regla «%s» tiene un patrón inválido", regla.get("nombre"))
            continue
        if not coincidencia:
            continue
        valores = _valores_de_plantilla(coincidencia, nombre_archivo)
        valores.setdefault("serie", extraer_serie(base))
        valores["inicial"] = calcular_inicial(str(valores["serie"]))
        _completar_episodio(valores, regla)
        agrupa = bool(regla.get("agrupar_series"))
        try:
            carpeta = regla["carpeta"].format(**valores)
            carpeta_sin_serie = (
                regla["carpeta"].format(**dict(valores, serie="")) if agrupa else carpeta
            )
            final = regla.get("nombre_nuevo", "{nombre}{extension}").format(**valores)
        except (KeyError, IndexError, ValueError):
            logger.exception("La regla «%s» tiene una plantilla inválida", regla.get("nombre"))
            continue
        return Clasificacion(
            carpeta=_unir_carpeta(carpeta),
            carpeta_sin_serie=_unir_carpeta(carpeta_sin_serie),
            nombre_final=_limpiar_nombre_de_archivo(final),
            regla=regla.get("nombre", ""),
            clave_serie=normalizar_texto(str(valores["serie"])) if agrupa else "",
            plantilla_carpeta=regla["carpeta"],
            valores=valores,
            serie=str(valores["serie"]),
        )
    return None


def clasificar_nombre(nombre_archivo, reglas):
    """Devuelve (carpeta_relativa, nombre_final, nombre_regla) o None."""
    resultado = _clasificar_detallado(nombre_archivo, reglas)
    if resultado is None:
        return None
    return resultado.carpeta, resultado.nombre_final, resultado.regla


def cargar_reglas(ruta_reglas):
    reglas = leer_json(ruta_reglas, [])
    return reglas if isinstance(reglas, list) else []


def listar_conjuntos_de_reglas(carpeta_reglas):
    """Devuelve [(nombre_para_mostrar, ruta)] de los .json de la carpeta, ordenados."""
    if not os.path.isdir(carpeta_reglas):
        return []
    conjuntos = []
    for archivo in sorted(os.listdir(carpeta_reglas)):
        if archivo.lower().endswith(".json"):
            nombre = os.path.splitext(archivo)[0].replace("_", " ").strip()
            conjuntos.append((nombre[:1].upper() + nombre[1:], os.path.join(carpeta_reglas, archivo)))
    return conjuntos
# ANCLAJE_FIN: CLASIFICADOR_REGLAS


# ANCLAJE_INICIO: CLASIFICADOR_PLAN
def _elegir_nombres_de_serie(candidatos):
    """Un único nombre de carpeta por serie, aunque los archivos varíen en tildes o mayúsculas.

    Gana el escrito más veces; en caso de empate, el que lleva tildes y después el orden alfabético.
    """
    variantes = {}
    for _ruta, c in candidatos:
        if c.clave_serie:
            variantes.setdefault((c.carpeta_sin_serie, c.clave_serie), Counter())[c.serie] += 1
    elegidos = {}
    for clave, conteo in variantes.items():
        elegidos[clave] = sorted(
            conteo, key=lambda s: (-conteo[s], normalizar_texto(s) == s.lower().replace("_", " "), s)
        )[0]
    return elegidos


def planificar(carpeta_origen, carpeta_destino, reglas):
    """Calcula los movimientos sin tocar nada. Devuelve (movimientos, sin_clasificar).

    Una serie solo tiene carpeta propia si en esta pasada hay al menos dos
    archivos de ella; así no se obliga a entrar en carpetas de un único archivo.
    """
    candidatos = []
    sin_clasificar = []
    for carpeta_actual, _subcarpetas, archivos in os.walk(carpeta_origen):
        for archivo in sorted(archivos):
            ruta_origen = os.path.join(carpeta_actual, archivo)
            clasificacion = _clasificar_detallado(archivo, reglas)
            if clasificacion is None:
                sin_clasificar.append(ruta_origen)
            else:
                candidatos.append((ruta_origen, clasificacion))

    tamano_de_serie = Counter(
        (c.carpeta_sin_serie, c.clave_serie) for _ruta, c in candidatos if c.clave_serie
    )
    nombre_de_serie = _elegir_nombres_de_serie(candidatos)
    movimientos = []
    destinos_usados = set()
    for ruta_origen, c in candidatos:
        agrupa = not c.clave_serie or tamano_de_serie[(c.carpeta_sin_serie, c.clave_serie)] >= 2
        if not agrupa:
            carpeta = c.carpeta_sin_serie
        elif c.clave_serie:
            serie = nombre_de_serie[(c.carpeta_sin_serie, c.clave_serie)]
            carpeta = _unir_carpeta(c.plantilla_carpeta.format(**dict(c.valores, serie=serie)))
        else:
            carpeta = c.carpeta
        ruta_destino = os.path.join(carpeta_destino, *carpeta.split("/"), c.nombre_final)
        if os.path.abspath(ruta_origen) == os.path.abspath(ruta_destino):
            continue
        conflicto = ""
        if os.path.exists(ruta_destino):
            conflicto = "El destino ya existe."
        elif ruta_destino.lower() in destinos_usados:
            conflicto = "Otro archivo tiene el mismo destino."
        destinos_usados.add(ruta_destino.lower())
        movimientos.append(Movimiento(ruta_origen, ruta_destino, c.regla, conflicto))
    movimientos.sort(key=lambda m: m.destino.lower())
    return movimientos, sin_clasificar
# ANCLAJE_FIN: CLASIFICADOR_PLAN


# ANCLAJE_INICIO: CLASIFICADOR_APLICAR
MOVIMIENTOS_ENTRE_GUARDADOS = 25


def _guardar_registro(ruta_registro, hechos):
    guardar_json_atomico(ruta_registro, [{"origen": m.origen, "destino": m.destino} for m in hechos])


def aplicar(movimientos, ruta_registro, al_progreso=None):
    """Mueve los archivos sin conflicto y guarda un registro para poder deshacer.

    El registro se guarda cada pocos archivos, no solo al final, para que un corte de luz a
    mitad de una mudanza larga no deje archivos movidos sin registrar. al_progreso(hechos, total)
    se llama tras cada archivo. Devuelve (hechos, fallidos), listas de Movimiento.
    """
    pendientes = [m for m in movimientos if not m.conflicto]
    hechos = []
    fallidos = []
    try:
        for indice, movimiento in enumerate(pendientes, 1):
            try:
                os.makedirs(os.path.dirname(movimiento.destino), exist_ok=True)
                shutil.move(movimiento.origen, movimiento.destino)
                hechos.append(movimiento)
                if len(hechos) % MOVIMIENTOS_ENTRE_GUARDADOS == 0:
                    _guardar_registro(ruta_registro, hechos)
            except OSError:
                logger.exception("No se pudo mover %s", movimiento.origen)
                fallidos.append(movimiento)
            if al_progreso:
                al_progreso(indice, len(pendientes))
    finally:
        _guardar_registro(ruta_registro, hechos)
    return hechos, fallidos


def ultimo_registro(carpeta_registros):
    """Ruta del registro de movimientos más reciente que aún no se ha deshecho, o None."""
    if not os.path.isdir(carpeta_registros):
        return None
    registros = sorted(
        f for f in os.listdir(carpeta_registros)
        if f.startswith("movimientos_") and f.endswith(".json")
    )
    return os.path.join(carpeta_registros, registros[-1]) if registros else None


def deshacer(ruta_registro):
    """Revierte los movimientos de un registro y lo marca como deshecho.

    Devuelve (revertidos, omitidos).
    """
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
    try:
        os.replace(ruta_registro, ruta_registro + ".deshecho")
    except OSError:
        logger.exception("No se pudo marcar como deshecho el registro %s", ruta_registro)
    return revertidos, omitidos
# ANCLAJE_FIN: CLASIFICADOR_APLICAR
