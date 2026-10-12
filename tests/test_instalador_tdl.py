import os
import pathlib
import tempfile
import unittest
import zipfile
from unittest import mock

from app.motor import instalador_tdl
from app.motor.instalador_tdl import ErrorInstalacionTdl


class PruebasInstaladorTdl(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.carpeta_bin = os.path.join(self.temporal.name, "bin")

    def tearDown(self):
        self.temporal.cleanup()

    def _crear_zip(self, miembros, nombre="tdl.zip"):
        ruta = os.path.join(self.temporal.name, nombre)
        with zipfile.ZipFile(ruta, "w") as archivo:
            for miembro, contenido in miembros.items():
                archivo.writestr(miembro, contenido)
        return pathlib.Path(ruta).as_uri()

    def test_instala_el_ejecutable_y_no_deja_basura(self):
        url = self._crear_zip({"LICENSE": "x", "tdl.exe": "binario"})
        progreso = []
        ruta = instalador_tdl.instalar_tdl(self.carpeta_bin, url, progreso.append)
        self.assertEqual(ruta, os.path.join(self.carpeta_bin, "tdl.exe"))
        with open(ruta) as f:
            self.assertEqual(f.read(), "binario")
        self.assertEqual(os.listdir(self.carpeta_bin), ["tdl.exe"])
        self.assertEqual(progreso[-1], 100)

    def test_encuentra_el_ejecutable_dentro_de_una_subcarpeta(self):
        url = self._crear_zip({"dentro/TDL.EXE": "binario"})
        ruta = instalador_tdl.instalar_tdl(self.carpeta_bin, url)
        self.assertTrue(os.path.isfile(ruta))

    def test_sustituye_una_version_anterior(self):
        os.makedirs(self.carpeta_bin)
        with open(os.path.join(self.carpeta_bin, "tdl.exe"), "w") as f:
            f.write("viejo")
        url = self._crear_zip({"tdl.exe": "nuevo"})
        ruta = instalador_tdl.instalar_tdl(self.carpeta_bin, url)
        with open(ruta) as f:
            self.assertEqual(f.read(), "nuevo")

    def test_zip_sin_ejecutable_da_error_claro(self):
        url = self._crear_zip({"LICENSE": "x"})
        with self.assertRaises(ErrorInstalacionTdl):
            instalador_tdl.instalar_tdl(self.carpeta_bin, url)
        self.assertFalse(os.path.exists(os.path.join(self.carpeta_bin, "tdl.exe")))

    def test_archivo_que_no_es_zip_da_error_claro(self):
        ruta = os.path.join(self.temporal.name, "falso.zip")
        with open(ruta, "w") as f:
            f.write("esto no es un zip")
        with self.assertRaises(ErrorInstalacionTdl):
            instalador_tdl.instalar_tdl(self.carpeta_bin, pathlib.Path(ruta).as_uri())

    def test_descarga_imposible_da_error_claro(self):
        url = pathlib.Path(os.path.join(self.temporal.name, "no_existe.zip")).as_uri()
        with self.assertRaises(ErrorInstalacionTdl):
            instalador_tdl.instalar_tdl(self.carpeta_bin, url)


    def test_url_de_version_acepta_la_v_o_no(self):
        esperado = "https://github.com/iyear/tdl/releases/download/v0.21.0/tdl_Windows_64bit.zip"
        self.assertEqual(instalador_tdl.url_de_version("v0.21.0"), esperado)
        self.assertEqual(instalador_tdl.url_de_version("0.21.0"), esperado)

    def test_version_mas_reciente_lee_la_etiqueta_de_la_redireccion(self):
        class Respuesta:
            def __init__(self, destino): self.destino = destino
            def geturl(self): return self.destino
            def __enter__(self): return self
            def __exit__(self, *a): return False
        with mock.patch.object(instalador_tdl.urllib.request, "urlopen",
                               return_value=Respuesta("https://github.com/iyear/tdl/releases/tag/v0.21.3")):
            self.assertEqual(instalador_tdl.version_mas_reciente(), "0.21.3")
        with mock.patch.object(instalador_tdl.urllib.request, "urlopen", return_value=Respuesta("https://github.com/otra")):
            self.assertIsNone(instalador_tdl.version_mas_reciente())
        with mock.patch.object(instalador_tdl.urllib.request, "urlopen", side_effect=OSError("sin red")):
            self.assertIsNone(instalador_tdl.version_mas_reciente())

    def test_una_version_incompatible_no_sustituye_a_la_actual(self):
        url = self._crear_zip({"tdl.exe": "nuevo"})
        os.makedirs(self.carpeta_bin)
        with open(os.path.join(self.carpeta_bin, "tdl.exe"), "w") as f:
            f.write("viejo")
        with self.assertRaises(ErrorInstalacionTdl):
            instalador_tdl.instalar_tdl(self.carpeta_bin, url, verificar=lambda ruta: (False, "no entiende «dl»"))
        with open(os.path.join(self.carpeta_bin, "tdl.exe")) as f:
            self.assertEqual(f.read(), "viejo")
        self.assertEqual(os.listdir(self.carpeta_bin), ["tdl.exe"])

    def test_una_version_compatible_se_instala(self):
        url = self._crear_zip({"tdl.exe": "nuevo"})
        ruta = instalador_tdl.instalar_tdl(self.carpeta_bin, url, verificar=lambda r: (os.path.isfile(r), ""))
        with open(ruta) as f:
            self.assertEqual(f.read(), "nuevo")


if __name__ == "__main__":
    unittest.main()
