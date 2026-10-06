import json
import os
import tempfile
import unittest
from unittest import mock

from app.config_rutas import RUTA_CARPETA_REGLAS
from app.motor import (ajustes, canales, clasificador, control_espacio, descargados, evitar_suspension, exportaciones,
                       filtro_exportacion, resumen_carpeta)


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

    def test_no_vuelve_a_pedir_lo_ya_descargado(self):
        resumen = filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, ["zip", "rar"], ya_descargados={1, 4})
        self.assertEqual((resumen.coinciden, resumen.ya_descargados, resumen.seleccionados), (3, 2, 1))
        self.assertEqual([m["id"] for m in self._leer_salida()["messages"]], [3])

    def test_el_limite_cuenta_sobre_lo_que_falta(self):
        resumen = filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, ["zip", "rar"],
                                                         limite=1, ya_descargados={1})
        self.assertEqual([m["id"] for m in self._leer_salida()["messages"]], [3])
        self.assertEqual((resumen.ya_descargados, resumen.seleccionados), (1, 1))

    def test_ids_de_mensajes_descargados_por_el_nombre_que_pone_tdl(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre in ("2164285849_77_Peli.mkv", "2164285849_78_Otra.mp4", "2164285849_79_Parcial.mkv.tmp",
                           "999_80_DeOtroCanal.mkv", "suelto.mkv"):
                open(os.path.join(carpeta, nombre), "w").close()
            self.assertEqual(filtro_exportacion.ids_de_mensajes_descargados(carpeta, "2164285849"), {77, 78})
            self.assertEqual(filtro_exportacion.ids_de_mensajes_descargados(
                os.path.join(carpeta, "no_existe"), "2164285849"), set())

    def test_formato_invalido_lanza_error(self):
        with open(self.entrada, "w") as f:
            f.write("[]")
        with self.assertRaises(ValueError):
            filtro_exportacion.filtrar_exportacion(self.entrada, self.salida, [])


class PruebasDescargados(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.ruta = os.path.join(self.temporal.name, "descargados.json")

    def tearDown(self):
        self.temporal.cleanup()

    def test_ids_de_nombre_con_rutas_de_windows_y_de_linux(self):
        self.assertEqual(descargados.ids_de_nombre("C:\\Users\\Yo\\descargas\\2164285849_1019_5859.mp4"), ("2164285849", 1019))
        self.assertEqual(descargados.ids_de_nombre("/tmp/x/-1001_77_Peli.mkv"), ("-1001", 77))
        self.assertIsNone(descargados.ids_de_nombre("Peli sin prefijo.mkv"))

    def test_anotar_y_consultar(self):
        self.assertEqual(descargados.anotar_rutas(["/d/111_1_a.mp4", "/d/111_2_b.mp4", "/d/222_9_c.zip", "/d/suelto.mkv"], self.ruta), 3)
        self.assertEqual(descargados.ids_de("111", self.ruta), {1, 2})
        self.assertEqual(descargados.ids_de(222, self.ruta), {9})
        self.assertEqual(descargados.ids_de("999", self.ruta), set())
        self.assertEqual(descargados.anotar_rutas(["/d/111_1_a.mp4"], self.ruta), 0)

    def test_archivo_corrupto_se_ignora(self):
        with open(self.ruta, "w") as f:
            f.write("{no es json")
        self.assertEqual(descargados.ids_de("111", self.ruta), set())

    def test_reconstruir_desde_las_clasificaciones_anteriores(self):
        registros = os.path.join(self.temporal.name, "registros")
        os.makedirs(registros)
        movs = [{"origen": "C:\\d\\2164285849_5_Peli.mkv", "destino": "C:\\b\\Peli.mkv"},
                {"origen": "C:\\d\\2164285849_6_Otra.mkv", "destino": "C:\\b\\Otra.mkv"}]
        with open(os.path.join(registros, "movimientos_20261001_000000.json"), "w") as f:
            json.dump(movs, f)
        with open(os.path.join(registros, "movimientos_20261002_000000.json.deshecho"), "w") as f:
            json.dump([{"origen": "C:\\d\\2164285849_7_Deshecha.mkv", "destino": "x"}], f)
        self.assertEqual(descargados.reconstruir_desde_movimientos(registros, self.ruta), 2)
        self.assertEqual(descargados.ids_de("2164285849", self.ruta), {5, 6})
        self.assertEqual(descargados.reconstruir_desde_movimientos(registros, self.ruta), 0)

    def test_tras_clasificar_no_se_vuelve_a_pedir_lo_ya_bajado(self):
        origen = os.path.join(self.temporal.name, "descargas")
        biblioteca = os.path.join(self.temporal.name, "biblioteca")
        os.makedirs(origen)
        nombres = ["2164285849_10_Peli.mkv", "2164285849_11_Otra.mkv"]
        for nombre in nombres:
            open(os.path.join(origen, nombre), "w").close()
        regla = [{"nombre": "v", "patron": r"\.mkv$", "carpeta": "Vídeos"}]
        movimientos, _sin = clasificador.planificar(origen, biblioteca, regla)
        descargados.anotar_rutas([m.origen for m in movimientos], self.ruta)
        clasificador.aplicar(movimientos, os.path.join(self.temporal.name, "mov.json"))
        self.assertEqual(os.listdir(origen), [])
        self.assertEqual(filtro_exportacion.ids_de_mensajes_descargados(origen, "2164285849"), set())
        entrada = os.path.join(self.temporal.name, "e.json")
        with open(entrada, "w") as f:
            json.dump({"id": 2164285849, "messages": [{"id": 10, "file": "Peli.mkv"}, {"id": 11, "file": "Otra.mkv"},
                                                       {"id": 12, "file": "Nueva.mkv"}]}, f)
        resumen = filtro_exportacion.filtrar_exportacion(entrada, os.path.join(self.temporal.name, "s.json"), ["mkv"],
                                                         ya_descargados=descargados.ids_de("2164285849", self.ruta))
        self.assertEqual((resumen.ya_descargados, resumen.seleccionados), (2, 1))


class PruebasAplicarAvanzado(unittest.TestCase):
    def test_progreso_y_guardado_incremental(self):
        with tempfile.TemporaryDirectory() as carpeta:
            origen = os.path.join(carpeta, "o")
            os.makedirs(origen)
            for i in range(60):
                open(os.path.join(origen, "f%02d.mkv" % i), "w").close()
            regla = [{"nombre": "v", "patron": r"\.mkv$", "carpeta": "V"}]
            movimientos, _sin = clasificador.planificar(origen, os.path.join(carpeta, "b"), regla)
            avances, guardados = [], []
            original = clasificador.guardar_json_atomico
            with mock.patch.object(clasificador, "guardar_json_atomico",
                                   side_effect=lambda r, d: (guardados.append(len(d)), original(r, d))):
                hechos, fallidos = clasificador.aplicar(movimientos, os.path.join(carpeta, "mov.json"),
                                                        lambda h, t: avances.append((h, t)))
            self.assertEqual((len(hechos), len(fallidos)), (60, 0))
            self.assertEqual(avances[0], (1, 60))
            self.assertEqual(avances[-1], (60, 60))
            self.assertEqual(guardados, [25, 50, 60])


class PruebasMismoDisco(unittest.TestCase):
    def test_dos_rutas_de_la_misma_carpeta_estan_en_el_mismo_disco(self):
        with tempfile.TemporaryDirectory() as carpeta:
            self.assertTrue(control_espacio.en_el_mismo_disco(carpeta, os.path.join(carpeta, "no", "existe", "aun")))


class PruebasPrefijoDeTdl(unittest.TestCase):
    def test_quita_el_prefijo_que_pone_tdl(self):
        self.assertEqual(clasificador.quitar_prefijo_de_tdl("1234567890_5877_Hierba.zip"), "Hierba.zip")
        self.assertEqual(clasificador.quitar_prefijo_de_tdl("-100123_5_Thor 1.cbr"), "Thor 1.cbr")

    def test_no_toca_nombres_normales(self):
        for nombre in ("249_Iron_Man_2.cbr", "1_Hola.zip", "Hierba.zip", "12_34.zip"):
            with self.subTest(nombre=nombre):
                self.assertEqual(clasificador.quitar_prefijo_de_tdl(nombre), nombre)

    def test_se_clasifica_igual_con_y_sin_prefijo(self):
        reglas = clasificador.cargar_reglas(os.path.join(RUTA_CARPETA_REGLAS, "Cómics.json"))
        sin = clasificador.clasificar_nombre("Tomodachi Game Tomos 1-14.zip", reglas)
        con = clasificador.clasificar_nombre("1234567890_5877_Tomodachi Game Tomos 1-14.zip", reglas)
        self.assertEqual(sin, con)
        self.assertTrue(con[0].startswith("Cómics/Manga/T"))


class PruebasAjustes(unittest.TestCase):
    def test_valores_de_fabrica_si_no_hay_archivo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            self.assertEqual(ajustes.cargar_ajustes(os.path.join(carpeta, "no.json")),
                             ajustes.VALORES_POR_DEFECTO)

    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "ajustes.json")
            datos = dict(ajustes.VALORES_POR_DEFECTO, hilos=8, simultaneas=4, takeout=True,
                         tamanos_medios={"Cómics": 52428800}, ultimo_canal="2164285849", perfil="Vídeo",
                         carpeta_descarga="D:\\Descargas")
            ajustes.guardar_ajustes(datos, ruta)
            self.assertEqual(ajustes.cargar_ajustes(ruta), datos)

    def test_guardar_sin_todos_los_campos_usa_los_de_fabrica(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "ajustes.json")
            ajustes.guardar_ajustes({"hilos": 6}, ruta)
            self.assertEqual(ajustes.cargar_ajustes(ruta)["simultaneas"], 2)

    def test_tamanos_medios_invalidos_se_descartan(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "ajustes.json")
            with open(ruta, "w") as f:
                json.dump({"tamanos_medios": {"Cómics": 100, "Vídeo": -5, "Audio": "mucho", "Libros": True}}, f)
            self.assertEqual(ajustes.cargar_ajustes(ruta)["tamanos_medios"], {"Cómics": 100})

    def test_valores_fuera_de_rango_o_corruptos_se_corrigen(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "ajustes.json")
            with open(ruta, "w") as f:
                json.dump({"hilos": 999, "simultaneas": 0, "takeout": "si"}, f)
            self.assertEqual(ajustes.cargar_ajustes(ruta), dict(ajustes.VALORES_POR_DEFECTO, hilos=16, simultaneas=1))
            with open(ruta, "w") as f:
                f.write("no es json")
            self.assertEqual(ajustes.cargar_ajustes(ruta)["hilos"], 4)


class PruebasCanalesGuardados(unittest.TestCase):
    def test_guardar_y_cargar(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "canales.json")
            lista = [{"id": "2164285849", "nombre": "Shin Chan [Castellano]", "usuario": ""},
                     {"id": "1380604249", "nombre": "Cómics", "usuario": "comics_es"}]
            canales.guardar_canales(lista, ruta)
            self.assertEqual(canales.cargar_canales(ruta), lista)

    def test_sin_archivo_o_corrupto_devuelve_lista_vacia(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "canales.json")
            self.assertEqual(canales.cargar_canales(ruta), [])
            with open(ruta, "w") as f:
                f.write("no es json")
            self.assertEqual(canales.cargar_canales(ruta), [])

    def test_descarta_elementos_invalidos_y_normaliza_el_id(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "canales.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump([{"id": 5, "nombre": "A"}, {"nombre": "sin id"}, "texto", {"id": 7}], f)
            self.assertEqual(canales.cargar_canales(ruta), [{"id": "5", "nombre": "A", "usuario": ""}])


class PruebasShinChan(unittest.TestCase):
    """Nombres tomados de la lista real del canal; llegan con el prefijo que pone tdl."""
    CASOS = {
        "2164285849_1026_1. SHIN CHAN.- LA INVASIÓN.mkv": ("Películas/Shin Chan", "01. SHIN CHAN.- LA INVASIÓN.mkv"),
        "2164285849_1073_Shin Chan El Superhéroe (2023) [RGodHD10].mkv": ("Películas/Shin Chan", None),
        "2164285849_4_1x001 (By LeCHuSo).mp4": ("Series/Shin Chan/Temporada 01", "Shin Chan - Episodio 001.mp4"),
        "2164285849_228_5x212 (By LeCHuSo).mp4": ("Series/Shin Chan/Temporada 05", "Shin Chan - Episodio 212.mp4"),
        "2164285849_691_17x647ab (By Antonio2587).mp4": ("Series/Shin Chan/Temporada 17", "Shin Chan - Episodio 647ab.mp4"),
        "2164285849_815_20x728_Especial 062 (By Antonio2587).mp4": ("Series/Shin Chan/Especiales", "Especial 062.mp4"),
        "2164285849_378_351 (By LeCHuSo).mp4": ("Series/Shin Chan/Sin temporada/Episodios 351 a 400", "Shin Chan - Episodio 351.mp4"),
        "2164285849_998_936 (Por Antonio2587).mp4": ("Series/Shin Chan/Temporada 26", "Shin Chan - Episodio 936.mp4"),
        "2164285849_960_942 b y c (Por Antonio2587).mp4": ("Series/Shin Chan/Temporada 26", "Shin Chan - Episodio 942b.mp4"),
        "2164285849_930_Shin Chan - 880-converted.mp4": ("Series/Shin Chan/Temporada 24", "Shin Chan - Episodio 880.mp4"),
        "2164285849_950_Shin_Chan_882_Vamos_a_unos_baños_termales_1_y_2_converted.mp4": ("Series/Shin Chan/Temporada 24", None),
        "2164285849_951_S-chan 400 [www.animemf.net] Seba_767.mp4": ("Series/Shin Chan/Sin temporada/Episodios 351 a 400", None),
        "2164285849_952_Sinchan 389.mp4": ("Series/Shin Chan/Sin temporada/Episodios 351 a 400", None),
        "2164285849_953_Shin ChanCap901[Manu767]-converted.mp4 00_00_03-00_17_14.mp4": ("Series/Shin Chan/Temporada 25", None),
        "2164285849_954_capitulo 935 B y C ‐ Hecho con Clipchamp.mp4": ("Series/Shin Chan/Temporada 26", None),
        "2164285849_1022_Ep_860_¡Eh,_que_ayudamos_a_la_señorita_Ageo!_¡Eh,_que_mamá_colecciona.mp4": ("Series/Shin Chan/Temporada 24", None),
        "2164285849_1019_5859677852491846352.mp4": ("Series/Shin Chan/Sin identificar", "5859677852491846352.mp4"),
        "2164285849_1025_5913785064964080760.jpg": ("Imágenes/Shin Chan", None),
    }

    def test_clasificacion_con_nombres_reales(self):
        reglas = clasificador.cargar_reglas(os.path.join(RUTA_CARPETA_REGLAS, "Shin Chan.json"))
        for nombre, (carpeta, final) in self.CASOS.items():
            with self.subTest(nombre=nombre[:60]):
                resultado = clasificador.clasificar_nombre(nombre, reglas)
                self.assertIsNotNone(resultado)
                self.assertEqual(resultado[0], carpeta)
                if final:
                    self.assertEqual(resultado[1], final)

    def test_nombre_muy_largo_conserva_la_extension(self):
        reglas = clasificador.cargar_reglas(os.path.join(RUTA_CARPETA_REGLAS, "Shin Chan.json"))
        largo = "Ep_860_" + "¡Eh,_que_mamá_colecciona_!" * 12 + ".mp4"
        resultado = clasificador.clasificar_nombre(largo, reglas)
        self.assertTrue(resultado[1].endswith(".mp4"))
        self.assertLessEqual(len(resultado[1]), clasificador.LONGITUD_MAXIMA_COMPONENTE)


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

    def test_resumir_completos_ignora_los_tmp_aunque_pesen(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre, tamano in (("a.zip", 100), ("b.cbr", 50), ("c.zip.tmp", 9999)):
                with open(os.path.join(carpeta, nombre), "wb") as f:
                    f.write(b"x" * tamano)
            self.assertEqual(resumen_carpeta.resumir_completos(carpeta), (2, 150))

    def test_resumir_completos_filtra_por_tipo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre in ("a.mp4", "b.MKV", "c.jpg", "d.mp4.tmp"):
                open(os.path.join(carpeta, nombre), "w").close()
            self.assertEqual(resumen_carpeta.resumir_completos(carpeta, ["mp4", "mkv"])[0], 2)
            self.assertEqual(resumen_carpeta.resumir_completos(carpeta)[0], 3)

    def test_resumir_carpeta_filtra_por_tipo(self):
        with tempfile.TemporaryDirectory() as carpeta:
            for nombre, tamano in (("a.zip", 1000), ("b.CBR", 500), ("c.jpg", 10)):
                with open(os.path.join(carpeta, nombre), "wb") as f:
                    f.write(b"x" * tamano)
            self.assertEqual(resumen_carpeta.resumir_carpeta(carpeta), (3, 1510))
            self.assertEqual(resumen_carpeta.resumir_carpeta(carpeta, ["zip", ".cbr"]), (2, 1500))

    def test_formatear_duracion(self):
        casos = {30: "menos de dos minutos", 40 * 60: "unos 40 minutos", 5 * 3600: "unas 5 horas",
                 14 * 3600: "unas 14 horas", 3 * 86400: "unos 3 días"}
        for segundos, esperado in casos.items():
            with self.subTest(segundos=segundos):
                self.assertEqual(resumen_carpeta.formatear_duracion(segundos), esperado)

    def test_formatear_velocidad(self):
        self.assertEqual(resumen_carpeta.formatear_velocidad(500), "500 B/s")
        self.assertEqual(resumen_carpeta.formatear_velocidad(2048), "2,0 KB/s")
        self.assertEqual(resumen_carpeta.formatear_velocidad(int(4.25 * 1024 ** 2)), "4,2 MB/s")
        self.assertEqual(resumen_carpeta.formatear_velocidad(5 * 1024 ** 2, hablado=True), "5,0 megabytes por segundo")

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


class PruebasExportaciones(unittest.TestCase):
    CANAL = {"id": "2164285849", "nombre": "Shin Chan [Castellano]"}

    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.listas = os.path.join(self.temporal.name, "exportaciones")
        self.registros = self.temporal.name

    def tearDown(self):
        self.temporal.cleanup()

    def test_el_nombre_dice_el_canal_y_su_numero(self):
        ruta = exportaciones.ruta_de_exportacion(self.CANAL, self.listas, self.registros)
        self.assertEqual(os.path.basename(ruta), "Shin Chan [Castellano] (2164285849).json")

    def test_se_encuentra_por_el_numero_aunque_cambie_el_nombre(self):
        os.makedirs(self.listas)
        existente = os.path.join(self.listas, "Nombre viejo (2164285849).json")
        open(existente, "w").close()
        ruta = exportaciones.ruta_de_exportacion(self.CANAL, self.listas, self.registros)
        self.assertEqual(ruta, existente)

    def test_migra_la_lista_con_el_formato_antiguo(self):
        antigua = os.path.join(self.registros, "exportacion_2164285849.json")
        with open(antigua, "w") as f:
            f.write("{}")
        ruta = exportaciones.ruta_de_exportacion(self.CANAL, self.listas, self.registros)
        self.assertTrue(os.path.isfile(ruta))
        self.assertFalse(os.path.exists(antigua))
        self.assertEqual(os.path.basename(ruta), "Shin Chan [Castellano] (2164285849).json")

    def test_dos_canales_no_se_mezclan(self):
        otro = {"id": "1380604249", "nombre": "Cómics"}
        self.assertNotEqual(exportaciones.ruta_de_exportacion(self.CANAL, self.listas, self.registros),
                            exportaciones.ruta_de_exportacion(otro, self.listas, self.registros))

    def test_describir_antiguedad(self):
        ruta = os.path.join(self.temporal.name, "x.json")
        open(ruta, "w").close()
        base = os.path.getmtime(ruta)
        casos = {30: "hace unos segundos", 600: "hace 10 minutos", 3600: "hace una hora",
                 3 * 3600: "hace 3 horas", 3 * 86400: "hace 3 días"}
        for segundos, esperado in casos.items():
            with self.subTest(segundos=segundos):
                self.assertEqual(exportaciones.describir_antiguedad(ruta, ahora=base + segundos), esperado)


class PruebasControlEspacio(unittest.TestCase):
    def test_espacio_libre_de_una_carpeta_que_aun_no_existe(self):
        with tempfile.TemporaryDirectory() as carpeta:
            libre = control_espacio.espacio_libre(os.path.join(carpeta, "no", "existe", "todavia"))
            self.assertIsInstance(libre, int)
            self.assertGreater(libre, 0)

    def test_cabe(self):
        gb = 1024 ** 3
        self.assertTrue(control_espacio.cabe(100 * gb, 50 * gb))
        self.assertFalse(control_espacio.cabe(51 * gb, 50 * gb))
        self.assertFalse(control_espacio.cabe(10 * gb, 50 * gb))

    def test_cabe_sin_datos_devuelve_none(self):
        self.assertIsNone(control_espacio.cabe(None, 5))
        self.assertIsNone(control_espacio.cabe(5, None))
        self.assertIsNone(control_espacio.cabe(5, 0))


class PruebasEvitarSuspension(unittest.TestCase):
    def test_bloquear_y_liberar_llaman_a_la_api_con_el_estado_correcto(self):
        with mock.patch.object(evitar_suspension, "_ES_WINDOWS", True), \
                mock.patch.object(evitar_suspension, "_establecer_estado", return_value=1) as api:
            self.assertTrue(evitar_suspension.bloquear())
            self.assertTrue(evitar_suspension.liberar())
        self.assertEqual(api.call_args_list[0][0][0], 0x80000001)
        self.assertEqual(api.call_args_list[1][0][0], 0x80000000)

    def test_si_la_api_falla_no_lanza_excepcion(self):
        with mock.patch.object(evitar_suspension, "_ES_WINDOWS", True), \
                mock.patch.object(evitar_suspension, "_establecer_estado", side_effect=OSError("fallo")):
            self.assertFalse(evitar_suspension.bloquear())

    def test_fuera_de_windows_no_hace_nada(self):
        with mock.patch.object(evitar_suspension, "_ES_WINDOWS", False), \
                mock.patch.object(evitar_suspension, "_establecer_estado") as api:
            self.assertFalse(evitar_suspension.bloquear())
        api.assert_not_called()


if __name__ == "__main__":
    unittest.main()
