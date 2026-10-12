import json
import os
import tempfile
import unittest

from app.motor import clasificador, pies_de_mensaje

REGLAS = clasificador.cargar_reglas(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "configuraciones", "reglas", "Shin Chan.json"))

PIE_EPISODIO = ("#Shinchan2T #Cap33 #Cap33A => Hacemos la comida #Cap33B => Hago volar cometas "
                "#Cap33C => Hacemos un muñeco de nieve")
PIE_ESPECIAL = ("#Shinchan3T #Especiales #Especial7 => Va a nacer un bebé — Soy vendedor de cerillas || "
                "Soy vendedor de fósforos — Hay cena de nochevieja")
PIE_JUNTO = ("#Shinchan27T #Cap959 #Cap959A -> Papá tiene un pelazo #Cap960 #Cap960A -> Vamos a comer dulces "
             "#Cap960B -> Hima se viene conmigo")
PIE_CON_ERRATAS = "#Shinchan6T #Capa243 #Cap243A => Tengo un mapa del tesoro #Cap234B => El ejército es muy agradecido"


def pies_de(*datos):
    pies = pies_de_mensaje.PiesDeMensaje()
    for identificador, nombre, texto in datos:
        pies.anotar(99, identificador, nombre, texto)
    return pies


class PruebasTextoDelPie(unittest.TestCase):
    def test_capitulos_solo_con_etiquetas_principales(self):
        self.assertEqual(pies_de_mensaje.capitulos_del_pie(PIE_EPISODIO), [33])
        self.assertEqual(pies_de_mensaje.capitulos_del_pie(PIE_CON_ERRATAS), [243])
        self.assertEqual(pies_de_mensaje.capitulos_del_pie(PIE_JUNTO), [959, 960])

    def test_episodios_del_pie(self):
        self.assertEqual(pies_de_mensaje.episodios_del_pie(PIE_EPISODIO), "033")
        self.assertEqual(pies_de_mensaje.episodios_del_pie(PIE_JUNTO), "959 a 960")
        self.assertEqual(pies_de_mensaje.episodios_del_pie(PIE_ESPECIAL), "")

    def test_titulos_se_unen_y_no_se_parten(self):
        self.assertEqual(pies_de_mensaje.titulos_del_pie(PIE_EPISODIO),
                         " - Hacemos la comida, Hago volar cometas")
        self.assertEqual(pies_de_mensaje.titulos_del_pie(PIE_CON_ERRATAS),
                         " - Tengo un mapa del tesoro")

    def test_titulos_de_un_especial_usan_la_primera_alternativa(self):
        texto = pies_de_mensaje.titulos_del_pie(PIE_ESPECIAL)
        self.assertEqual(texto, " - Va a nacer un bebé, Soy vendedor de cerillas")

    def test_un_titulo_demasiado_largo_se_recorta_con_puntos_suspensivos(self):
        pie = "#Shinchan2T #Cap40 #Cap40A => " + "palabra " * 20
        texto = pies_de_mensaje.titulos_del_pie(pie)
        self.assertTrue(texto.endswith("…"))
        self.assertLessEqual(len(texto), pies_de_mensaje.MAXIMO_CARACTERES_DE_TITULOS + 4)

    def test_sin_titulos_no_deja_separador(self):
        self.assertEqual(pies_de_mensaje.titulos_del_pie("#Shinchan2T #Cap40"), "")


class PruebasBusqueda(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        mensajes = [
            {"id": 38, "file": "5782757084164525222.mp4", "text": PIE_EPISODIO},
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

    def test_sigue_el_rastro_de_los_cambios_de_nombre(self):
        carpeta_registros = os.path.join(self.temporal.name, "registros")
        os.makedirs(carpeta_registros)
        with open(os.path.join(carpeta_registros, "movimientos_1.json"), "w", encoding="utf-8") as f:
            json.dump([{"origen": "C:\\d\\99_38_5782757084164525222.mp4", "destino": "C:\\b\\Otro nombre.mp4"},
                       {"origen": "C:\\b\\Otro nombre.mp4", "destino": "D:\\x\\Nombre final.mp4"}], f)
        pies = pies_de_mensaje.cargar_pies(self.temporal.name, carpeta_registros)
        self.assertEqual(pies.buscar("Nombre final.mp4"), PIE_EPISODIO)

    def test_un_rastro_circular_no_se_queda_colgado(self):
        pies = pies_de_mensaje.PiesDeMensaje()
        pies.anotar_renombre("a.mp4", "b.mp4")
        pies.anotar_renombre("b.mp4", "a.mp4")
        self.assertEqual(pies.buscar("a.mp4"), "")

    def test_pie_por_numero_de_capitulo_y_de_especial(self):
        pies = pies_de(("1", "a.mp4", PIE_EPISODIO), (2, "b.mp4", PIE_ESPECIAL))
        self.assertEqual(pies.por_numero("episodio", 33), PIE_EPISODIO)
        self.assertEqual(pies.por_numero("especial", 7), PIE_ESPECIAL)
        self.assertEqual(pies.por_numero("episodio", 7), "")


class PruebasReglasConPie(unittest.TestCase):
    def clasificar(self, nombre, pies=None):
        return clasificador._clasificar_detallado(nombre, REGLAS, pies)

    def test_episodio_con_temporada_numero_y_titulos(self):
        resultado = self.clasificar("5782757084164525222.mp4", pies_de((1, "5782757084164525222.mp4", PIE_EPISODIO)))
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 02")
        self.assertEqual(resultado.nombre_final,
                         "Shin Chan - Temporada 02 - Episodio 033 - Hacemos la comida, Hago volar cometas.mp4")

    def test_especial_dentro_de_su_temporada(self):
        resultado = self.clasificar("a.mp4", pies_de((1, "a.mp4", PIE_ESPECIAL)))
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 03")
        self.assertTrue(resultado.nombre_final.startswith("Shin Chan - Temporada 03 - Especial 007 - Va a nacer un bebé"))

    def test_un_video_que_junta_dos_capitulos_lo_dice(self):
        resultado = self.clasificar("a.mp4", pies_de((1, "a.mp4", PIE_JUNTO)))
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 27")
        self.assertTrue(resultado.nombre_final.startswith("Shin Chan - Temporada 27 - Episodio 959 a 960 - "))

    def test_sin_pie_el_video_numerico_sigue_sin_identificar(self):
        resultado = self.clasificar("5782757084164525222.mp4")
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Sin identificar")

    def test_un_episodio_ya_nombrado_se_recoloca_y_recibe_titulos_por_su_numero(self):
        pies = pies_de((1, "a.mp4", PIE_EPISODIO))
        resultado = self.clasificar("Shin Chan - Episodio 033.mp4", pies)
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 02")
        self.assertEqual(resultado.nombre_final,
                         "Shin Chan - Temporada 02 - Episodio 033 - Hacemos la comida, Hago volar cometas.mp4")

    def test_episodios_ya_nombrados_usan_la_tabla_de_temporadas(self):
        for nombre, carpeta, final in (
                ("Shin Chan - Episodio 617.mp4", "Temporada 17", "Shin Chan - Temporada 17 - Episodio 617.mp4"),
                ("Shin Chan - Episodio 882.mp4", "Temporada 25", "Shin Chan - Temporada 25 - Episodio 882.mp4"),
                ("Shin Chan - Episodio 353.mp4", "Temporada 09", "Shin Chan - Temporada 09 - Episodio 353.mp4")):
            with self.subTest(nombre=nombre):
                resultado = self.clasificar(nombre)
                self.assertEqual(resultado.carpeta, "Series/Shin Chan/" + carpeta)
                self.assertEqual(resultado.nombre_final, final)

    def test_un_especial_ya_nombrado_va_a_su_temporada(self):
        resultado = self.clasificar("Especial 044 (By Antonio2587).mp4")
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 14")
        self.assertEqual(resultado.nombre_final, "Shin Chan - Temporada 14 - Especial 044.mp4")

    def test_un_nombre_con_el_formato_nuevo_no_se_toca(self):
        nombre = "Shin Chan - Temporada 02 - Episodio 033 - Hacemos la comida de año nuevo.mp4"
        resultado = self.clasificar(nombre)
        self.assertEqual((resultado.carpeta, resultado.nombre_final), ("Series/Shin Chan/Temporada 02", nombre))

    def test_un_episodio_mal_nombrado_se_corrige_con_el_rastro_de_su_nombre_original(self):
        pies = pies_de((1021, "Ep_859_titulo.mp4", PIE_JUNTO))
        pies.anotar_renombre("99_1021_Ep_859_titulo.mp4", "Shin Chan - Episodio 859 - Papá tiene un pelazo.mp4")
        resultado = self.clasificar("Shin Chan - Episodio 859 - Papá tiene un pelazo.mp4", pies)
        self.assertEqual(resultado.carpeta, "Series/Shin Chan/Temporada 27")
        self.assertTrue(resultado.nombre_final.startswith("Shin Chan - Temporada 27 - Episodio 959 a 960"))

    def test_peliculas_sin_numero_en_el_nombre_toman_el_del_canal(self):
        for nombre, final in (("Shin Chan Operacion Espia De Oro (2011).mp4", "19. Shin Chan - Operación Espía de Oro.mp4"),
                              ("2013-Shin Chan - El secreto esta en la salsa.mkv", "21. Shin Chan - El secreto está en la salsa.mkv"),
                              ("Shin.Chan,.Papa.Robot.(Spanish).avi", "22. Shin Chan - Papá Robot.avi")):
            with self.subTest(nombre=nombre):
                resultado = self.clasificar(nombre)
                self.assertEqual((resultado.carpeta, resultado.nombre_final), ("Películas/Shin Chan", final))


class PruebasPlanConPie(unittest.TestCase):
    def test_dos_versiones_del_mismo_episodio_se_conservan_las_dos(self):
        with tempfile.TemporaryDirectory() as raiz:
            origen = os.path.join(raiz, "origen")
            os.makedirs(origen)
            for nombre in ("Sinchan 378.mp4", "5782757084164525222.mp4"):
                open(os.path.join(origen, nombre), "w").close()
            pie = "#Shinchan9T #Cap378 #Cap378A => Titulo"
            pies = pies_de((50, "5782757084164525222.mp4", pie), (51, "Sinchan 378.mp4", pie))
            movimientos, sin_clasificar = clasificador.planificar(origen, os.path.join(raiz, "bib"), REGLAS, pies)
            nombres = sorted(os.path.basename(m.destino) for m in movimientos)
            self.assertEqual(sin_clasificar, [])
            self.assertEqual(nombres, ["Shin Chan - Temporada 09 - Episodio 378 - Titulo (versión 2).mp4",
                                       "Shin Chan - Temporada 09 - Episodio 378 - Titulo.mp4"])
            self.assertFalse(any(m.conflicto for m in movimientos))

    def test_la_version_se_conserva_aunque_el_nombre_sea_largo_y_no_se_vuelve_a_mover(self):
        titulo = "Un título larguísimo " * 6
        pies = pies_de((1, "a.mp4", "#Shinchan9T #Cap378 #Cap378A => " + titulo))
        nombre = clasificador._clasificar_detallado("a.mp4", REGLAS, pies).nombre_final
        con_version = clasificador._con_sufijo(nombre, " (versión 2)")
        self.assertLessEqual(len(con_version), clasificador.LONGITUD_MAXIMA_COMPONENTE)
        with tempfile.TemporaryDirectory() as raiz:
            carpeta = os.path.join(raiz, "Series", "Shin Chan", "Temporada 09")
            os.makedirs(carpeta)
            open(os.path.join(carpeta, con_version), "w").close()
            movimientos, _sin = clasificador.planificar(os.path.join(raiz, "Series"), raiz, REGLAS, pies)
            self.assertEqual(movimientos, [])

    def test_planificar_con_pies(self):
        with tempfile.TemporaryDirectory() as raiz:
            origen = os.path.join(raiz, "origen")
            os.makedirs(origen)
            open(os.path.join(origen, "5782757084164525222.mp4"), "w").close()
            pies = pies_de((1, "5782757084164525222.mp4", PIE_EPISODIO))
            movimientos, sin_clasificar = clasificador.planificar(origen, os.path.join(raiz, "bib"), REGLAS, pies)
            self.assertEqual(sin_clasificar, [])
            self.assertTrue(movimientos[0].destino.endswith(os.path.join("Temporada 02", "Shin Chan - Temporada 02 - Episodio 033 - Hacemos la comida, Hago volar cometas.mp4")))


if __name__ == "__main__":
    unittest.main()
