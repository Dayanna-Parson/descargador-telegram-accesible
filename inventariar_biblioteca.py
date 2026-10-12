"""Genera registros/inventario_biblioteca.txt con todo lo que contiene una carpeta. Solo lee."""
import os
import sys

from app.config_rutas import RUTA_BIBLIOTECA, RUTA_REGISTROS
from app.motor import inventario_biblioteca

# ANCLAJE_INICIO: INVENTARIO_ENTRADA
CARPETA_ANTIGUA_POR_DEFECTO = os.path.join(RUTA_BIBLIOTECA, "Vídeos sin ordenar")


def pedir_carpeta():
    if len(sys.argv) > 1:
        return sys.argv[1].strip('"')
    return input("Carpeta que quieres revisar (pega la ruta y pulsa Intro): ").strip().strip('"')


def principal():
    carpeta = pedir_carpeta()
    if not os.path.isdir(carpeta):
        print("No existe la carpeta: {}".format(carpeta))
        return 1
    ruta_ffprobe = inventario_biblioteca.localizar_ffprobe()
    print("Leyendo la carpeta. Puede tardar unos minutos si hay muchos vídeos numerados.")
    if not ruta_ffprobe:
        print("No se ha encontrado ffprobe: no se leerá la duración de los vídeos numerados.")

    def avisar(hecho, total):
        if hecho % 25 == 0 or hecho == total:
            print("Vídeos numerados revisados: {} de {}".format(hecho, total))

    informe = inventario_biblioteca.generar_informe(
        carpeta, CARPETA_ANTIGUA_POR_DEFECTO, ruta_ffprobe, avisar)
    os.makedirs(RUTA_REGISTROS, exist_ok=True)
    ruta_informe = os.path.join(RUTA_REGISTROS, "inventario_biblioteca.txt")
    with open(ruta_informe, "w", encoding="utf-8") as archivo:
        archivo.write(informe)
    print("Listo. El informe está en: {}".format(ruta_informe))
    return 0
# ANCLAJE_FIN: INVENTARIO_ENTRADA


if __name__ == "__main__":
    sys.exit(principal())
