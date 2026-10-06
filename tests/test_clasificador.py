import os
import tempfile
import unittest

from app.motor import clasificador

REGLAS = [
    {
        "nombre": "Serie por temporada y episodio",
        "patron": r"(?i)(?P<temporada>\d{1,2})x(?P<episodio>\d{1,3})",
        "carpeta": "Shin Chan/Temporada {temporada:02}",
        "nombre_nuevo": "S{temporada:02}E{episodio:02}{extension}",
    },
    {
        "nombre": "Cómics",
        "patron": r"(?i)\.(cbz|cbr)$",
        "carpeta": "Cómics",
    },
]


class PruebasClasificarNombre(unittest.TestCase):
    def test_serie_con_temporada_y_episodio(self):
        resultado = clasificador.clasificar_nombre("Shin Chan 3x07 Castellano.mkv", REGLAS)
        self.assertEqual(resultado[0], "Shin Chan/Temporada 03")
        self.assertEqual(resultado[1], "S03E07.mkv")

    def test_regla_por_extension_conserva_el_nombre(self):
        resultado = clasificador.clasificar_nombre("Mortadelo 12.cbz", REGLAS)
        self.assertEqual(resultado, ("Cómics", "Mortadelo 12.cbz", "Cómics"))

    def test_sin_regla_devuelve_none(self):
        self.assertIsNone(clasificador.clasificar_nombre("notas.txt", REGLAS))

    def test_limpia_caracteres_prohibidos_en_windows(self):
        reglas = [{"nombre": "x", "patron": r"(?P<t>.+)\.pdf", "carpeta": "Libros",
                   "nombre_nuevo": "{t}: parte?{extension}"}]
        resultado = clasificador.clasificar_nombre("Cuento.pdf", reglas)
        self.assertEqual(resultado[1], "Cuento parte.pdf")

    def test_plantilla_invalida_se_salta_la_regla(self):
        reglas = [{"nombre": "mala", "patron": r"\.pdf$", "carpeta": "{no_existe}"}]
        self.assertIsNone(clasificador.clasificar_nombre("a.pdf", reglas))


class PruebasPlanYAplicar(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.origen = os.path.join(self.temporal.name, "descargas")
        self.destino = os.path.join(self.temporal.name, "biblioteca")
        os.makedirs(self.origen)
        for nombre in ("Shin Chan 1x01.mkv", "Shin Chan 1x02.mkv", "Mortadelo.cbz", "suelto.txt"):
            with open(os.path.join(self.origen, nombre), "w") as f:
                f.write("x")

    def tearDown(self):
        self.temporal.cleanup()

    def test_planificar_separa_clasificados_y_sin_clasificar(self):
        movimientos, sin_clasificar = clasificador.planificar(self.origen, self.destino, REGLAS)
        self.assertEqual(len(movimientos), 3)
        self.assertEqual(len(sin_clasificar), 1)
        self.assertTrue(all(m.conflicto == "" for m in movimientos))

    def test_aplicar_y_deshacer(self):
        movimientos, _ = clasificador.planificar(self.origen, self.destino, REGLAS)
        registro = os.path.join(self.temporal.name, "registro.json")
        hechos, fallidos = clasificador.aplicar(movimientos, registro)
        self.assertEqual((len(hechos), len(fallidos)), (3, 0))
        self.assertTrue(os.path.isfile(
            os.path.join(self.destino, "Shin Chan", "Temporada 01", "S01E01.mkv")))
        revertidos, omitidos = clasificador.deshacer(registro)
        self.assertEqual((revertidos, omitidos), (3, 0))
        self.assertTrue(os.path.isfile(os.path.join(self.origen, "Shin Chan 1x01.mkv")))

    def test_conflicto_si_dos_archivos_van_al_mismo_destino(self):
        with open(os.path.join(self.origen, "Shin Chan 1x01 copia.mkv"), "w") as f:
            f.write("x")
        movimientos, _ = clasificador.planificar(self.origen, self.destino, REGLAS)
        conflictos = [m for m in movimientos if m.conflicto]
        self.assertEqual(len(conflictos), 1)
        hechos, _ = clasificador.aplicar(movimientos, os.path.join(self.temporal.name, "r.json"))
        self.assertEqual(len(hechos), 3)


if __name__ == "__main__":
    unittest.main()
