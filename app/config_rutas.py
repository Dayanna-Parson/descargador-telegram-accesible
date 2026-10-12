"""Rutas absolutas de la aplicación. Todo parte de RAIZ."""
import os
import sys

# ANCLAJE_INICIO: RUTAS_BASE
if getattr(sys, "frozen", False):
    RAIZ = os.path.dirname(sys.executable)
else:
    RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUTA_CONFIGURACIONES = os.path.join(RAIZ, "configuraciones")
RUTA_AJUSTES = os.path.join(RUTA_CONFIGURACIONES, "ajustes.json")
RUTA_CANALES = os.path.join(RUTA_CONFIGURACIONES, "canales.json")
RUTA_DESCARGADOS = os.path.join(RUTA_CONFIGURACIONES, "descargados.json")
RUTA_CARPETA_REGLAS = os.path.join(RUTA_CONFIGURACIONES, "reglas")
RUTA_REGISTROS = os.path.join(RAIZ, "registros")
RUTA_EXPORTACIONES = os.path.join(RUTA_REGISTROS, "exportaciones")
RUTA_BIBLIOTECA = os.path.join(RAIZ, "biblioteca")
RUTA_DESCARGAS = os.path.join(RAIZ, "descargas")
RUTA_BIN = os.path.join(RAIZ, "bin")
RUTA_TDL = os.path.join(RUTA_BIN, "tdl.exe" if os.name == "nt" else "tdl")
# ANCLAJE_FIN: RUTAS_BASE
