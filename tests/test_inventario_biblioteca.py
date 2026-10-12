import os
import tempfile
import unittest

from app.motor import inventario_biblioteca


class PruebasInventario(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.biblioteca = os.path.join(self.temporal.name, "biblioteca")
        self.antigua = os.path.join(self.temporal.name, "antigua")
        for carpeta, nombre, contenido in (
            ("Series", "Episodio 1.mkv", b"a" * 10),
            ("Series", "5847973735897761629.mp4", b"b" * 20),
            ("", "suelto.pdf", b"c" * 5),
        ):
            ruta = os.path.join(self.biblioteca, carpeta)
            os.makedirs(ruta, exist_ok=True)
            with open(os.path.join(ruta, nombre), "wb") as f:
                f.write(contenido)
        os.makedirs(self.antigua)
        with open(os.path.join(self.antigua, "repetido.mkv"), "wb") as f:
            f.write(b"a" * 10)
        with open(os.path.join(self.antigua, "nuevo.mkv"), "wb") as f:
            f.write(b"z" * 99)

    def tearDown(self):
        self.temporal.cleanup()

    def test_reconoce_los_nombres_numericos(self):
        self.assertTrue(inventario_biblioteca.tiene_nombre_numerico("5847973735897761629.mp4"))
        self.assertFalse(inventario_biblioteca.tiene_nombre_numerico("Episodio 1.mkv"))
        self.assertFalse(inventario_biblioteca.tiene_nombre_numerico("5870715025545606180.jpg"))

    def test_el_informe_cuenta_archivos_y_carpetas(self):
        informe = inventario_biblioteca.generar_informe(self.biblioteca)
        self.assertIn("Archivos: 3", informe)
        self.assertIn("Series: 2 archivos", informe)
        self.assertIn("VÍDEOS CON NOMBRE NUMÉRICO: 1", informe)

    def test_la_comparacion_distingue_copias_de_archivos_nuevos(self):
        informe = inventario_biblioteca.generar_informe(self.biblioteca, self.antigua)
        self.assertIn("repetido.mkv (10 bytes): 1 copia(s)", informe)
        self.assertIn("nuevo.mkv (99 bytes): 0 copia(s)", informe)

    def test_no_modifica_nada(self):
        antes = sorted(os.listdir(self.antigua))
        inventario_biblioteca.generar_informe(self.biblioteca, self.antigua)
        self.assertEqual(sorted(os.listdir(self.antigua)), antes)


if __name__ == "__main__":
    unittest.main()
