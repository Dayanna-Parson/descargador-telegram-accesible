import json
import os
import tempfile
import unittest

from app.config_rutas import RUTA_CARPETA_REGLAS
from app.motor import clasificador, filtro_exportacion, resumen_carpeta


class PruebasSerieEInicial(unittest.TestCase):
    def test_extraer_serie(self):
        casos = {
            "Tomodachi Game Tomos 15-26": "Tomodachi Game",
            "Batman - La secta": "Batman",
            "Ghostbusters Vol1": "Ghostbusters",
            "Asombroso Spiderman Vol 7 USA #1-20": "Asombroso Spiderman",
            "Ben 10 (2026) #1": "Ben 10",
            "Mister Milagro (Vol 4)": "Mister Milagro",
            "Estela Plateada.- Parábola": "Estela Plateada",
            "Pulgarcito (1981-1985) Parte 2": "Pulgarcito",
            "52": "52",
            "300": "300",
            "020. Los 4 Fantasticos - Una vida fantastica": "Los 4 Fantasticos",
            "139.- La Patrulla-X - Equipo Extinción 3 VvX Consecuencias": "La Patrulla-X",
            "Justice League Unlimited (All In) #1-14": "Justice League Unlimited",
        }
        for nombre, esperado in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(clasificador.extraer_serie(nombre), esperado)

    def test_calcular_inicial(self):
        casos = {
            "El Último Atlas": "U",
            "Los 4 Fantásticos": "0-9",
            "The Walking Dead": "W",
            "Aquí hay avería": "A",
            "...": "#",
            "1236 Córdoba": "0-9",
        }
        for serie, esperado in casos.items():
            with self.subTest(serie=serie):
                self.assertEqual(clasificador.calcular_inicial(serie), esperado)


class PruebasAgrupacion(unittest.TestCase):
    REGLAS = [{"nombre": "cbr", "patron": r"\.cbr$", "carpeta": "C/{inicial}/{serie}", "agrupar_series": True}]

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.origen = os.path.join(self.temporal.name, "o")
        self.destino = os.path.join(self.temporal.name, "d")
        os.makedirs(self.origen)

    def tearDown(self):
        self.temporal.cleanup()

    def _planificar(self, nombres, reglas=None):
        for nombre in nombres:
            open(os.path.join(self.origen, nombre), "w").close()
        movimientos, _sin = clasificador.planificar(self.origen, self.destino, reglas or self.REGLAS)
        return [os.path.relpath(m.destino, self.destino).replace(os.sep, "/") for m in movimientos]

    def test_serie_con_dos_archivos_tiene_carpeta(self):
        rutas = self._planificar(["Thor 1.cbr", "Thor 2.cbr"])
        self.assertEqual(rutas, ["C/T/Thor/Thor 1.cbr", "C/T/Thor/Thor 2.cbr"])

    def test_archivo_unico_no_crea_carpeta_de_serie(self):
        self.assertEqual(self._planificar(["Hulk 1.cbr"]), ["C/H/Hulk 1.cbr"])

    def test_variantes_de_tildes_comparten_carpeta(self):
        rutas = self._planificar(["Capitán América 1.cbr", "Capitán América 2.cbr", "Capitan America 3.cbr"])
        self.assertEqual({r.rsplit("/", 1)[0] for r in rutas}, {"C/C/Capitán América"})

    def test_empate_prefiere_la_variante_con_tildes(self):
        rutas = self._planificar(["Capitán América 1.cbr", "Capitan America 2.cbr"])
        self.assertEqual({r.rsplit("/", 1)[0] for r in rutas}, {"C/C/Capitán América"})


class PruebasReglasIncluidas(unittest.TestCase):
    def test_todos_los_conjuntos_son_validos_y_compilan(self):
        conjuntos = clasificador.listar_conjuntos_de_reglas(RUTA_CARPETA_REGLAS)
        self.assertGreaterEqual(len(conjuntos), 3)
        for nombre, ruta in conjuntos:
            reglas = clasificador.cargar_reglas(ruta)
            self.assertTrue(reglas, nombre)
            for regla in reglas:
                self.assertEqual({"nombre", "patron", "carpeta"} <= set(regla), True, regla.get("nombre"))
                clasificador._clasificar_detallado("prueba.zip", [regla])

    def test_comics_reales_van_a_su_categoria(self):
        reglas = clasificador.cargar_reglas(os.path.join(RUTA_CARPETA_REGLAS, "Cómics.json"))
        casos = {
            "Spiderman Coleccionable 1 - Lomo Rojo.zip": "Cómics/Marvel/S/Spiderman Coleccionable",
            "Batman - La secta.zip": "Cómics/DC/B/Batman",
            "Tomodachi Game Tomos 1-14.zip": "Cómics/Manga/T/Tomodachi Game",
            "Hooky.zip": "Cómics/Manga/H",
            "Star Wars - Thrawn.zip": "Cómics/Licencias y videojuegos/S/Star Wars",
            "020. Los 4 Fantasticos - Una vida fantastica.cbr": "Cómics/Marvel/0-9/Los 4 Fantasticos",
            "300.rar": "Cómics/Otros/0-9",
        }
        for nombre, carpeta in casos.items():
            with self.subTest(nombre=nombre):
                resultado = clasificador._clasificar_detallado(nombre, reglas)
                self.assertTrue(resultado.carpeta.startswith(carpeta.rsplit("/", 1)[0]), resultado.carpeta)

    def test_series_con_temporada_y_episodio(self):
        reglas = clasificador.cargar_reglas(os.path.join(RUTA_CARPETA_REGLAS, "Series y películas.json"))
        resultado = clasificador.clasificar_nombre("Shin Chan 2x13 Castellano.mkv", reglas)
        self.assertEqual(resultado[0], "Series/Shin Chan/Temporada 02")
        self.assertEqual(resultado[1], "Shin Chan - S02E13.mkv")
        resultado = clasificador.clasificar_nombre("Shin.Chan.S01E05.1080p.mkv", reglas)
        self.assertEqual(resultado[0], "Series/Shin Chan/Temporada 01")


class PruebasRegistroYConjuntos(unittest.TestCase):
    def test_deshacer_marca_el_registro_y_ultimo_registro_lo_ignora(self):
        with tempfile.TemporaryDirectory() as carpeta:
            origen = os.path.join(carpeta, "a.txt")
            destino = os.path.join(carpeta, "sub", "a.txt")
            open(origen, "w").close()
            registros = os.path.join(carpeta, "registros")
            ruta = os.path.join(registros, "movimientos_20260101_000000.json")
            clasificador.aplicar([clasificador.Movimiento(origen, destino, "r")], ruta)
            self.assertEqual(clasificador.ultimo_registro(registros), ruta)
            self.assertEqual(clasificador.deshacer(ruta), (1, 0))
            self.assertIsNone(clasificador.ultimo_registro(registros))
            self.assertTrue(os.path.isfile(ruta + ".deshecho"))


class PruebasFiltroExportacion(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.entrada = os.path.join(self.temporal.name, "e.json")
        self.salida = os.path.join(self.temporal.name, "s.json")
        mensajes = [{"id": 1, "type": "message", "file": "a.zip"}, {"id": 2, "type": "message", "file": "a.jpg"},
                    {"id": 3, "type": "message", "file": "b.RAR"}, {"id": 4, "type": "message", "file": "c.zip"},
                    {"id": 5, "type": "message"}]
        with open(self.entrada, "w", encoding="utf-8") as f:
            json.dump({"id": 99, "messages": mensajes}, f)

    def tearDown(self):
        self.temporal.cleanup()

    def _leer_salida(self):
        with open(self.salida, encoding="utf-8") as f:
            return json.load(f)

    def test_filtra_por_extension_sin_distinguir_mayusculas(self):
        resumen = filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, ["zip", ".rar"])
        self.assertEqual((resumen.total_con_archivo, resumen.coinciden, resumen.seleccionados), (4, 3, 3))
        self.assertEqual(self._leer_salida()["id"], 99)

    def test_limite_recorta_la_seleccion(self):
        resumen = filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, ["zip", "rar"], limite=2)
        self.assertEqual((resumen.coinciden, resumen.seleccionados), (3, 2))
        self.assertEqual([m["id"] for m in self._leer_salida()["messages"]], [1, 3])

    def test_sin_extensiones_incluye_todo_lo_que_tenga_archivo(self):
        resumen = filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, [])
        self.assertEqual(resumen.seleccionados, 4)

    def test_formato_invalido_lanza_error(self):
        with open(self.entrada, "w") as f:
            f.write("[]")
        with self.assertRaises(ValueError):
            filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, [])


class PruebasNombreSeguro(unittest.TestCase):
    def test_nombre_seguro(self):
        self.assertEqual(clasificador.nombre_seguro("-1001234567"), "-1001234567")
        self.assertEqual(clasificador.nombre_seguro('Canal: "Cómics" ¿Sí?'), "Canal Cómics ¿Sí")
        self.assertEqual(clasificador.nombre_seguro("***"), "_")


class PruebasResumenCarpeta(unittest.TestCase):
    def test_resumir_carpeta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            os.makedirs(os.path.join(carpeta, "sub"))
            for nombre, tamano in (("a", 100), (os.path.join("sub", "b"), 200)):
                with open(os.path.join(carpeta, nombre), "wb") as f:
                    f.write(b"x" * tamano)
            self.assertEqual(resumen_carpeta.resumir_carpeta(carpeta), (2, 300))

    def test_contar_completos_ignora_los_tmp(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre in ("a.zip", "b.cbr", "c.zip.tmp", "D.TMP"):
                open(os.path.join(carpeta, nombre), "w").close()
            self.assertEqual(resumen_carpeta.contar_completos(carpeta), 2)

    def test_formatear_tamano(self):
        self.assertEqual(resumen_carpeta.formatear_tamano(0), "0 bytes")
        self.assertEqual(resumen_carpeta.formatear_tamano(2048), "2 KB")
        self.assertEqual(resumen_carpeta.formatear_tamano(5 * 1024 ** 2), "5 MB")
        self.assertEqual(resumen_carpeta.formatear_tamano(int(1.5 * 1024 ** 3)), "1,5 GB")


if __name__ == "__main__":
    unittest.main()
