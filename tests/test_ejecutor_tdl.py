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


class PruebasConsola(unittest.TestCase):
    def test_lote_entrecomilla_rutas_con_espacios_y_deja_pausa(self):
        texto = ejecutor_tdl._texto_lote("C:\\Mis programas\\bin\\tdl.exe", ["login", "-T", "code"])
        lineas = texto.splitlines()
        self.assertEqual(lineas[1], '"C:\\Mis programas\\bin\\tdl.exe" login -T code')
        self.assertEqual(lineas[-1], "pause >nul")


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
