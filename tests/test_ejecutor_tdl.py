import json
import os
import tempfile
import unittest

from app.motor import ejecutor_tdl
from app.motor.perfiles_descarga import extensiones_del_perfil


class PruebasComandos(unittest.TestCase):
    def test_descargar_sin_filtro_no_lleva_include(self):
        comando = ejecutor_tdl.comando_descargar("a.json", "D:\\x")
        self.assertNotIn("-i", comando)
        self.assertIn("--continue", comando)

    def test_descargar_con_perfil_de_comics(self):
        comando = ejecutor_tdl.comando_descargar("a.json", "D:\\x", extensiones_del_perfil("Cómics"))
        self.assertEqual(comando[comando.index("-i") + 1], "cbz,cbr,pdf,zip,rar,7z")


class PruebasOpcionesDeVelocidad(unittest.TestCase):
    def test_por_defecto_ajusta_el_pool_y_oculta_el_progreso(self):
        comando = ejecutor_tdl.comando_descargar("a.json", "D:\\x")
        self.assertEqual(comando[comando.index("--pool") + 1], "8")
        self.assertIn("--disable-progress-ps", comando)
        self.assertNotIn("--takeout", comando)

    def test_el_pool_crece_con_hilos_y_archivos_simultaneos(self):
        comando = ejecutor_tdl.comando_descargar("a.json", "D:\\x", hilos=8, simultaneas=4, takeout=True)
        self.assertEqual(comando[comando.index("--pool") + 1], "32")
        self.assertEqual(comando[comando.index("-t") + 1], "8")
        self.assertEqual(comando[comando.index("-l") + 1], "4")
        self.assertIn("--takeout", comando)

    def test_el_pool_tiene_techo(self):
        comando = ejecutor_tdl.comando_descargar("a.json", "D:\\x", hilos=16, simultaneas=8)
        self.assertEqual(comando[comando.index("--pool") + 1], "64")


class PruebasParseo(unittest.TestCase):
    def test_lista_de_chats_con_lineas_previas(self):
        texto = "info: cargando\n" + json.dumps([
            {"id": 123, "visible_name": "Canal Shin Chan", "username": "shin"},
            {"id": 456, "title": "Otro"},
            {"sin_id": True},
        ])
        chats = ejecutor_tdl.parsear_lista_chats(texto)
        self.assertEqual([c["id"] for c in chats], ["123", "456"])
        self.assertEqual(chats[0]["nombre"], "Canal Shin Chan")

    def test_salida_invalida_devuelve_lista_vacia(self):
        self.assertEqual(ejecutor_tdl.parsear_lista_chats("sin json"), [])
        self.assertEqual(ejecutor_tdl.parsear_lista_chats("[roto"), [])

    def test_contar_archivos_exportados(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = os.path.join(carpeta, "e.json")
            with open(ruta, "w", encoding="utf-8") as f:
                json.dump({"messages": [{"file": "a.mkv"}, {"text": "hola"}, {"file": "b.mkv"}]}, f)
            self.assertEqual(ejecutor_tdl.contar_archivos_exportados(ruta), 2)


class PruebasInterpretarProgreso(unittest.TestCase):
    # Líneas reales de tdl 0.20.3 copiadas de un descargador.log
    LINEA_ARCHIVO = "Shin Chan [Castellano](216428~ ... 40.3% [###.....] [741.00 MB in 5m27.374s; ~ETA: 8m11s; 2.26 MB/s]"
    LINEA_TOTAL = "[#############################....................] [5m28s; 4.12 MB/s]"

    def test_linea_de_archivo(self):
        dato = ejecutor_tdl.interpretar_progreso(self.LINEA_ARCHIVO)
        self.assertEqual(dato, {"tipo": "archivo", "porcentaje": 40.3, "velocidad": "2.26 MB/s", "eta": "8m11s"})

    def test_linea_general(self):
        dato = ejecutor_tdl.interpretar_progreso(self.LINEA_TOTAL)
        self.assertEqual(dato, {"tipo": "total", "velocidad": "4.12 MB/s", "tiempo": "5m28s"})

    def test_otras_lineas_no_se_interpretan(self):
        for linea in ("CPU: 1.56% Memory: 42.11 MB Goroutines: 78", "Todo listo", ""):
            with self.subTest(linea=linea):
                self.assertIsNone(ejecutor_tdl.interpretar_progreso(linea))

    def test_las_lineas_reales_cuentan_como_progreso(self):
        for linea in (self.LINEA_ARCHIVO, self.LINEA_TOTAL, "CPU: 1.56% Memory: 42.11 MB Goroutines: 78"):
            self.assertTrue(ejecutor_tdl.es_linea_de_progreso(linea))

    def test_velocidad_en_bytes(self):
        self.assertEqual(ejecutor_tdl.velocidad_en_bytes("1 KB/s"), 1024)
        self.assertAlmostEqual(ejecutor_tdl.velocidad_en_bytes("1.54 MB/s"), 1.54 * 1024 ** 2)
        self.assertEqual(ejecutor_tdl.velocidad_en_bytes("nada"), 0)

    def test_velocidad_hablada(self):
        self.assertEqual(ejecutor_tdl.velocidad_hablada("4.12 MB/s"), "4,12 megabytes por segundo")
        self.assertEqual(ejecutor_tdl.velocidad_hablada("850 KB/s"), "850 kilobytes por segundo")
        self.assertEqual(ejecutor_tdl.velocidad_hablada("sin dato"), "sin dato")


class PruebasProgreso(unittest.TestCase):
    def test_reconoce_la_barra_de_progreso(self):
        for linea in ("Hierba.zip 45.3% [12.5 MB/s]", "descargando 7%", "algo 850 KB/s"):
            with self.subTest(linea=linea):
                self.assertTrue(ejecutor_tdl.es_linea_de_progreso(linea))

    def test_no_confunde_otras_lineas(self):
        for linea in ("Todo listo", "error: sin conexión", "canal sin porcentajes"):
            with self.subTest(linea=linea):
                self.assertFalse(ejecutor_tdl.es_linea_de_progreso(linea))


class PruebasProcesos(unittest.TestCase):
    SALIDA = ('"tdl.exe","4321","Console","1","45.120 KB"\n"TDL.EXE","987","Console","1","40.000 KB"\n'
              '"otro.exe","55","Console","1","1.000 KB"\n')

    def test_extrae_los_pid_de_tdl(self):
        self.assertEqual(ejecutor_tdl._parsear_tasklist(self.SALIDA, "tdl.exe"), [4321, 987])

    def test_sin_procesos_no_hay_pid(self):
        texto = "INFO: No hay tareas en ejecución que coincidan con los criterios especificados."
        self.assertEqual(ejecutor_tdl._parsear_tasklist(texto, "tdl.exe"), [])
        self.assertEqual(ejecutor_tdl._parsear_tasklist("", "tdl.exe"), [])

    def test_fuera_de_windows_no_busca_procesos(self):
        if os.name != "nt":
            self.assertEqual(ejecutor_tdl.procesos_tdl_ajenos(), [])


class PruebasConsola(unittest.TestCase):
    def test_lote_entrecomilla_rutas_con_espacios_y_deja_pausa(self):
        texto = ejecutor_tdl._texto_lote("C:\\Mis programas\\bin\\tdl.exe", ["login", "-T", "code"])
        lineas = texto.splitlines()
        self.assertEqual(lineas[1], '"C:\\Mis programas\\bin\\tdl.exe" login -T code')
        self.assertEqual(lineas[-1], "pause >nul")


class PruebasDetener(unittest.TestCase):
    def test_detener_y_esperar_termina_el_proceso(self):
        import sys
        import threading
        fin = threading.Event()
        ejecutor = ejecutor_tdl.EjecutorTdl(ruta_tdl=sys.executable)
        ejecutor.ejecutar(["-c", "import time; time.sleep(60)"], lambda _l: None, lambda _c: fin.set())
        self.assertTrue(ejecutor.en_ejecucion())
        ejecutor.detener_y_esperar(segundos=10)
        self.assertFalse(ejecutor.en_ejecucion())
        self.assertTrue(fin.wait(10))

    def test_detener_sin_proceso_no_falla(self):
        ejecutor_tdl.EjecutorTdl(ruta_tdl="no-existe").detener_y_esperar()


class PruebasEjecutor(unittest.TestCase):
    def test_recoge_salida_y_codigo(self):
        import sys
        import threading
        lineas, codigos, fin = [], [], threading.Event()
        ejecutor = ejecutor_tdl.EjecutorTdl(ruta_tdl=sys.executable)
        ejecutor.ejecutar(["-c", "print('hola'); print('mundo')"], lineas.append,
                          lambda c: (codigos.append(c), fin.set()))
        self.assertTrue(fin.wait(10))
        self.assertEqual(lineas, ["hola", "mundo"])
        self.assertEqual(codigos, [0])


if __name__ == "__main__":
    unittest.main()
