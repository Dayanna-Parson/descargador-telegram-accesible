import json
import os
import tempfile
import unittest

from app.motor import clasificador, pies_de_mensaje

REGLAS = clasificador.cargar_reglas(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "configuraciones", "reglas", "Shin Chan.json"))

PIE_EPISODIO = "#Shinchan2T #Cap33 #Cap33A => Hacemos la comida #Cap33B => Hago volar cometas"
PIE_ESPECIAL = "#Shinchan3T #Especiales #Especial7 => Va a nacer un bebé"


class PruebasPies(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        mensajes = [
            {"id": 38, "file": "5782757084164525222.mp4", "text": PIE_EPISODIO},
            {"id": 37, "file": "5782757084164525221.mp4", "text": PIE_ESPECIAL},
            {"id": 40, "file": "repetido.mp4", "text": "uno"},
            {"id": 41, "file": "repetido.mp4", "text": "otro"},
            {"id": 42, "file": "sin_pie.mp4"},
        ]
        with open(os.path.join(self.temporal.name, "canal (99).json"), "w", encoding="utf-8") as f:
            json.dump({"id": 99, "messages": mensajes}, f)
        self.pies = pies_de_mensaje.cargar_pies(self.temporal.name)

    def tearDown(self):
        self.temporal.cleanup()

    def test_busca_por_nombre_y_por_prefijo_de_tdl(self):
        self.assertEqual(self.pies.buscar("5782757084164525222.mp4"), PIE_EPISODIO)
        self.assertEqual(self.pies.buscar("99_38_5782757084164525222.mp4"), PIE_EPISODIO)

    def test_un_nombre_repetido_con_pies_distintos_no_se_adivina(self):
        self.assertEqual(self.pies.buscar("repetido.mp4"), "")
        self.assertEqual(self.pies.buscar("99_41_repetido.mp4"), "otro")

    def test_sin_pie_o_desconocido_devuelve_vacio(self):
        self.assertEqual(self.pies.buscar("sin_pie.mp4"), "")
        self.assertEqual(self.pies.buscar("no_existe.mp4"), "")

    def test_carpeta_inexistente_no_falla(self):
        self.assertEqual(len(pies_de_mensaje.cargar_pies(os.path.join(self.temporal.name, "no"))), 0)

    def test_regla_de_episodio_usa_la_temporada_del_pie(self):
        resultado = clasificador._clasificar_detallado("5782757084164525222.mp4", REGLAS, PIE_EPISODIO)
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 02")
        self.assertEqual(resultado.nombre_final, "Shin Chan - Episodio 033.mp4")

    def test_regla_de_especial_usa_el_pie(self):
        resultado = clasificador._clasificar_detallado("5782757084164525221.mp4", REGLAS, PIE_ESPECIAL)
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 03")
        self.assertEqual(resultado.nombre_final, "Shin Chan - Especial 007.mp4")

    def test_sin_pie_el_video_numerico_sigue_sin_identificar(self):
        resultado = clasificador._clasificar_detallado("5782757084164525222.mp4", REGLAS, "")
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Sin identificar")

    def test_episodios_ya_nombrados_se_recolocan_por_la_tabla_de_temporadas(self):
        for nombre, carpeta in (("Shin Chan - Episodio 617.mp4", "Temporada 17"),
                                ("Shin Chan - Episodio 882.mp4", "Temporada 25"),
                                ("Shin Chan - Episodio 353.mp4", "Temporada 09")):
            with self.subTest(nombre=nombre):
                resultado = clasificador._clasificar_detallado(nombre, REGLAS)
                self.assertEqual(resultado.carpeta, "Series/Shin Chan/" + carpeta)
                self.assertEqual(resultado.nombre_final, nombre)

    def test_un_episodio_con_titulo_conserva_su_nombre(self):
        nombre = "Shin Chan - Episodio 859 - ¡Eh, que papá tiene un pelazo!.mp4"
        resultado = clasificador._clasificar_detallado(nombre, REGLAS)
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 24")
        self.assertEqual(resultado.nombre_final, nombre)

    def test_un_especial_ya_nombrado_va_a_su_temporada(self):
        resultado = clasificador._clasificar_detallado("Especial 044 (By Antonio2587).mp4", REGLAS)
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 14")
        self.assertEqual(resultado.nombre_final, "Shin Chan - Especial 044.mp4")

    def test_peliculas_sin_numero_en_el_nombre_toman_el_del_canal(self):
        for nombre, final in (("Shin Chan Operacion Espia De Oro (2011).mp4", "19. Shin Chan - Operación Espía de Oro.mp4"),
                              ("2013-Shin Chan - El secreto esta en la salsa.mkv", "21. Shin Chan - El secreto está en la salsa.mkv"),
                              ("Shin.Chan,.Papa.Robot.(Spanish).avi", "22. Shin Chan - Papá Robot.avi")):
            with self.subTest(nombre=nombre):
                resultado = clasificador._clasificar_detallado(nombre, REGLAS)
                self.assertEqual((resultado.carpeta, resultado.nombre_final), ("Películas/Shin Chan", final))

    def test_dos_versiones_del_mismo_episodio_se_conservan_las_dos(self):
        with tempfile.TemporaryDirectory() as raiz:
            origen = os.path.join(raiz, "origen")
            os.makedirs(origen)
            for nombre in ("Sinchan 378.mp4", "5782757084164525222.mp4"):
                open(os.path.join(origen, nombre), "w").close()
            pie = "#Shinchan9T #Cap378 #Cap378A => Titulo"
            pies = pies_de_mensaje.PiesDeMensaje()
            pies.anotar(99, 50, "5782757084164525222.mp4", pie)
            movimientos, sin_clasificar = clasificador.planificar(origen, os.path.join(raiz, "bib"), REGLAS, pies)
            nombres = sorted(os.path.basename(m.destino) for m in movimientos)
            self.assertEqual(sin_clasificar, [])
            self.assertEqual(nombres, ["Shin Chan - Episodio 378 (versión 2).mp4", "Shin Chan - Episodio 378.mp4"])
            self.assertFalse(any(m.conflicto for m in movimientos))

    def test_planificar_con_pies(self):
        with tempfile.TemporaryDirectory() as raiz:
            origen = os.path.join(raiz, "origen")
            os.makedirs(origen)
            open(os.path.join(origen, "5782757084164525222.mp4"), "w").close()
            movimientos, sin_clasificar = clasificador.planificar(origen, os.path.join(raiz, "bib"), REGLAS, self.pies)
            self.assertEqual(sin_clasificar, [])
            self.assertTrue(movimientos[0].destino.endswith(
                os.path.join("Temporada 02", "Shin Chan - Episodio 033.mp4")))


if __name__ == "__main__":
    unittest.main()
