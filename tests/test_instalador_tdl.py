import os
import pathlib
import tempfile
import unittest
import zipfile

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


if __name__ == "__main__":
    unittest.main()
