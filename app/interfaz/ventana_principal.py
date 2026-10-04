"""Ventana principal: pestañas Conexión, Canal, Descarga y Clasificar, con un registro común."""
import collections
import logging
import os
import threading
import time
from datetime import datetime

import wx

from app.config_rutas import (RUTA_BIBLIOTECA, RUTA_CARPETA_REGLAS, RUTA_DESCARGAS, RUTA_EXPORTACIONES,
                              RUTA_REGISTROS)
from app.motor import ajustes, avisos_sonoros, control_espacio, evitar_suspension
from app.motor import anunciador_lector as voz
from app.motor import clasificador
from app.motor import ejecutor_tdl as tdl
from app.motor import exportaciones, filtro_exportacion, instalador_tdl, resumen_carpeta
from app.motor.perfiles_descarga import extensiones_del_perfil, nombres_de_perfiles

logger = logging.getLogger(__name__)

INTERVALO_REGISTRO_MS = 500
INTERVALO_LOG_PROGRESO_SEGUNDOS = 5
INTERVALO_VIGILANCIA_SEGUNDOS = 3
INTERVALO_AVISO_PROGRESO_SEGUNDOS = 20
MAXIMO_REINTENTOS = 3
ESPERA_REINTENTO_SEGUNDOS = 30
UMBRAL_SILENCIO_SEGUNDOS = 120


# ANCLAJE_INICIO: VENTANA_PRINCIPAL
class VentanaPrincipal(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Descargador de Telegram Accesible", size=(820, 640))
        self.ejecutor = tdl.EjecutorTdl()
        self._chats = []
        self._ruta_filtrada = os.path.join(RUTA_REGISTROS, "lista_de_descarga_actual.json")
        self._resumen_filtro = None
        self._conjuntos = []
        self._plan = []
        self._sin_clasificar = []
        self._salida_acumulada = []
        self._cola_registro = collections.deque()
        self._filtrar_progreso = False
        self._ultimo_log_progreso = 0.0
        self._parar_vigilancia = None
        self._progreso = (0, 0, 0)
        self._carpeta_descarga = ""
        self._ajustes = ajustes.cargar_ajustes()
        self._perfil_descarga = ""
        self._comando_descarga = []
        self._pausa_pedida = False
        self._reintentos = 0
        self._esperando_reintento = False
        self._temporizador_reintento = None
        self._bloque_tdl = []
        self._estado_tdl = None
        self._ultima_actividad_tdl = 0.0
        self._construir_interfaz()
        self._temporizador_registro = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._vaciar_cola_registro, self._temporizador_registro)
        self._temporizador_registro.Start(INTERVALO_REGISTRO_MS)
        self._registrar_atajos()
        self.Centre()
        wx.CallAfter(self._comprobar_tdl)

    # ANCLAJE_INICIO: VENTANA_CONSTRUCCION
    def _construir_interfaz(self):
        panel = wx.Panel(self)
        raiz = wx.BoxSizer(wx.VERTICAL)
        self.cuaderno = wx.Notebook(panel)
        self.cuaderno.AddPage(self._pagina_conexion(self.cuaderno), "Conexión")
        self.cuaderno.AddPage(self._pagina_canal(self.cuaderno), "Canal")
        self.cuaderno.AddPage(self._pagina_descarga(self.cuaderno), "Descarga")
        self.cuaderno.AddPage(self._pagina_clasificar(self.cuaderno), "Clasificar")
        self.cuaderno.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self._al_cambiar_pestana)
        raiz.Add(self.cuaderno, 3, wx.EXPAND | wx.ALL, 8)

        etiqueta_registro = wx.StaticText(panel, label="&Registro de actividad")
        self.registro = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, name="Registro de actividad"
        )
        raiz.Add(etiqueta_registro, 0, wx.LEFT | wx.RIGHT, 8)
        raiz.Add(self.registro, 2, wx.EXPAND | wx.ALL, 8)
        panel.SetSizer(raiz)
        self.cuaderno.SetFocus()

    def _pagina_conexion(self, padre):
        pagina = wx.Panel(padre)
        caja = wx.BoxSizer(wx.VERTICAL)
        self.boton_instalar_tdl = wx.Button(pagina, label="&Instalar o actualizar tdl")
        self.boton_instalar_tdl.Bind(wx.EVT_BUTTON, self._al_instalar_tdl)
        caja.Add(self.boton_instalar_tdl, 0, wx.ALL, 8)
        self.boton_sesion_escritorio = wx.Button(pagina, label="Importar sesión de Telegram &Desktop")
        self.boton_sesion_codigo = wx.Button(pagina, label="Iniciar sesión con &código")
        self.boton_sesion_escritorio.Bind(wx.EVT_BUTTON, self._al_sesion_escritorio)
        self.boton_sesion_codigo.Bind(wx.EVT_BUTTON, self._al_sesion_codigo)
        caja.Add(self.boton_sesion_escritorio, 0, wx.ALL, 8)
        caja.Add(self.boton_sesion_codigo, 0, wx.ALL, 8)
        pagina.SetSizer(caja)
        return pagina

    def _pagina_canal(self, padre):
        pagina = wx.Panel(padre)
        caja = wx.BoxSizer(wx.VERTICAL)
        self.boton_actualizar_chats = wx.Button(pagina, label="&Actualizar lista de canales")
        self.boton_actualizar_chats.Bind(wx.EVT_BUTTON, self._al_actualizar_chats)
        etiqueta = wx.StaticText(pagina, label="&Canales y chats disponibles")
        self.lista_chats = wx.ListBox(pagina, name="Canales y chats disponibles")
        self.lista_chats.Bind(wx.EVT_LISTBOX, lambda _e: self._actualizar_canal_en_descarga())
        caja.Add(self.boton_actualizar_chats, 0, wx.ALL, 8)
        caja.Add(etiqueta, 0, wx.LEFT | wx.RIGHT, 8)
        caja.Add(self.lista_chats, 1, wx.EXPAND | wx.ALL, 8)
        pagina.SetSizer(caja)
        return pagina

    def _pagina_descarga(self, padre):
        pagina = wx.Panel(padre)
        caja = wx.BoxSizer(wx.VERTICAL)
        etiqueta_canal = wx.StaticText(pagina, label="Ca&nal que se descargará (se elige en la pestaña Canal)")
        self.campo_canal = wx.TextCtrl(pagina, style=wx.TE_READONLY, name="Canal que se descargará")
        self.campo_canal.SetValue("Ninguno")
        etiqueta_perfil = wx.StaticText(pagina, label="&Tipo de contenido")
        self.selector_perfil = wx.Choice(pagina, choices=nombres_de_perfiles(), name="Tipo de contenido")
        self.selector_perfil.SetSelection(0)
        etiqueta_carpeta = wx.StaticText(pagina, label="&Carpeta de destino")
        self.campo_carpeta = wx.TextCtrl(pagina, value=RUTA_DESCARGAS, name="Carpeta de destino")
        self.boton_examinar = wx.Button(pagina, label="&Examinar...")
        self.boton_examinar.Bind(wx.EVT_BUTTON, self._al_examinar)
        etiqueta_limite = wx.StaticText(pagina, label="&Límite de archivos (0 para descargarlos todos; usa un número pequeño para hacer una prueba)")
        self.campo_limite = wx.SpinCtrl(pagina, min=0, max=100000, initial=0, name="Límite de archivos")
        etiqueta_hilos = wx.StaticText(pagina, label="&Hilos por archivo (de 1 a 16; más hilos, más velocidad, hasta el límite de Telegram)")
        self.campo_hilos = wx.SpinCtrl(pagina, min=1, max=16, initial=self._ajustes["hilos"], name="Hilos por archivo")
        etiqueta_simultaneas = wx.StaticText(pagina, label="&Archivos a la vez (de 1 a 8)")
        self.campo_simultaneas = wx.SpinCtrl(pagina, min=1, max=8, initial=self._ajustes["simultaneas"], name="Archivos a la vez")
        self.casilla_takeout = wx.CheckBox(
            pagina, label="&Usar sesión de exportación de Telegram (menos esperas por límites; puede pedirte permiso en tu app)",
            name="Usar sesión de exportación de Telegram")
        self.casilla_takeout.SetValue(self._ajustes["takeout"])
        self.boton_exportar = wx.Button(pagina, label="E&xportar lista del canal seleccionado")
        self.boton_descargar = wx.Button(pagina, label="&Descargar / reanudar")
        self.boton_pausar = wx.Button(pagina, label="&Pausar")
        self.boton_estado = wx.Button(pagina, label="E&stado de la descarga (Control+E)")
        self.boton_estado.Bind(wx.EVT_BUTTON, self._al_estado)
        self.boton_abrir_descarga = wx.Button(pagina, label="A&brir la carpeta de la descarga")
        self.boton_abrir_listas = wx.Button(pagina, label="Abrir carpeta de listas exp&ortadas")
        self.boton_abrir_descarga.Bind(wx.EVT_BUTTON, self._al_abrir_descarga)
        self.boton_abrir_listas.Bind(wx.EVT_BUTTON, self._al_abrir_listas)
        self.indicador = wx.Gauge(pagina, range=100, name="Progreso de la descarga")
        self.boton_exportar.Bind(wx.EVT_BUTTON, self._al_exportar)
        self.boton_descargar.Bind(wx.EVT_BUTTON, self._al_descargar)
        self.boton_pausar.Bind(wx.EVT_BUTTON, self._al_pausar)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.campo_carpeta, 1, wx.RIGHT, 8)
        fila.Add(self.boton_examinar, 0)
        for control in (etiqueta_canal, self.campo_canal, etiqueta_perfil, self.selector_perfil, etiqueta_carpeta):
            caja.Add(control, 0, wx.ALL, 6)
        caja.Add(fila, 0, wx.EXPAND | wx.ALL, 6)
        for control in (etiqueta_limite, self.campo_limite, etiqueta_hilos, self.campo_hilos,
                        etiqueta_simultaneas, self.campo_simultaneas, self.casilla_takeout,
                        self.boton_exportar, self.boton_descargar, self.boton_pausar, self.boton_estado,
                        self.indicador, self.boton_abrir_descarga, self.boton_abrir_listas):
            caja.Add(control, 0, wx.ALL, 6)
        pagina.SetSizer(caja)
        return pagina

    def _pagina_clasificar(self, padre):
        pagina = wx.Panel(padre)
        caja = wx.BoxSizer(wx.VERTICAL)
        self._conjuntos = clasificador.listar_conjuntos_de_reglas(RUTA_CARPETA_REGLAS)
        etiqueta_reglas = wx.StaticText(pagina, label="Con&junto de reglas")
        self.selector_reglas = wx.Choice(pagina, choices=[n for n, _ruta in self._conjuntos], name="Conjunto de reglas")
        if self._conjuntos:
            self.selector_reglas.SetSelection(0)
        etiqueta_origen = wx.StaticText(pagina, label="Carpeta de &origen (lo descargado)")
        self.campo_origen = wx.TextCtrl(pagina, value=RUTA_DESCARGAS, name="Carpeta de origen")
        self.boton_examinar_origen = wx.Button(pagina, label="Examinar o&rigen...")
        etiqueta_biblioteca = wx.StaticText(pagina, label="Carpeta de la &biblioteca (destino)")
        self.campo_biblioteca = wx.TextCtrl(pagina, value=RUTA_BIBLIOTECA, name="Carpeta de la biblioteca")
        self.boton_examinar_biblioteca = wx.Button(pagina, label="Examinar b&iblioteca...")
        self.boton_calcular = wx.Button(pagina, label="&Calcular vista previa")
        etiqueta_plan = wx.StaticText(pagina, label="&Vista previa: archivo y carpeta donde irá")
        self.lista_plan = wx.ListBox(pagina, name="Vista previa de la clasificación")
        etiqueta_sin = wx.StaticText(pagina, label="Archivos &sin clasificar")
        self.lista_sin_clasificar = wx.ListBox(pagina, name="Archivos sin clasificar")
        self.boton_aplicar = wx.Button(pagina, label="&Aplicar clasificación")
        self.boton_deshacer = wx.Button(pagina, label="&Deshacer la última clasificación")
        self.boton_examinar_origen.Bind(wx.EVT_BUTTON, lambda _e: self._elegir_carpeta(
            self.campo_origen, "Elige la carpeta de origen", self.boton_examinar_origen))
        self.boton_examinar_biblioteca.Bind(wx.EVT_BUTTON, lambda _e: self._elegir_carpeta(
            self.campo_biblioteca, "Elige la carpeta de la biblioteca", self.boton_examinar_biblioteca))
        self.boton_calcular.Bind(wx.EVT_BUTTON, self._al_calcular_plan)
        self.boton_aplicar.Bind(wx.EVT_BUTTON, self._al_aplicar_plan)
        self.boton_deshacer.Bind(wx.EVT_BUTTON, self._al_deshacer_clasificacion)
        fila_origen = wx.BoxSizer(wx.HORIZONTAL)
        fila_origen.Add(self.campo_origen, 1, wx.RIGHT, 8)
        fila_origen.Add(self.boton_examinar_origen, 0)
        fila_biblioteca = wx.BoxSizer(wx.HORIZONTAL)
        fila_biblioteca.Add(self.campo_biblioteca, 1, wx.RIGHT, 8)
        fila_biblioteca.Add(self.boton_examinar_biblioteca, 0)
        fila_botones = wx.BoxSizer(wx.HORIZONTAL)
        fila_botones.Add(self.boton_calcular, 0, wx.RIGHT, 8)
        fila_botones.Add(self.boton_aplicar, 0, wx.RIGHT, 8)
        fila_botones.Add(self.boton_deshacer, 0)
        caja.Add(etiqueta_reglas, 0, wx.LEFT | wx.TOP, 6)
        caja.Add(self.selector_reglas, 0, wx.ALL, 6)
        caja.Add(etiqueta_origen, 0, wx.LEFT | wx.TOP, 6)
        caja.Add(fila_origen, 0, wx.EXPAND | wx.ALL, 6)
        caja.Add(etiqueta_biblioteca, 0, wx.LEFT | wx.TOP, 6)
        caja.Add(fila_biblioteca, 0, wx.EXPAND | wx.ALL, 6)
        caja.Add(fila_botones, 0, wx.ALL, 6)
        caja.Add(etiqueta_plan, 0, wx.LEFT | wx.TOP, 6)
        caja.Add(self.lista_plan, 2, wx.EXPAND | wx.ALL, 6)
        caja.Add(etiqueta_sin, 0, wx.LEFT | wx.TOP, 6)
        caja.Add(self.lista_sin_clasificar, 1, wx.EXPAND | wx.ALL, 6)
        pagina.SetSizer(caja)
        return pagina
    # ANCLAJE_FIN: VENTANA_CONSTRUCCION

    # ANCLAJE_INICIO: VENTANA_REGISTRO
    def _escribir(self, texto, anunciar=False):
        """Añade una línea al registro. Solo se llama desde el hilo principal."""
        self.registro.AppendText(texto + "\n")
        if anunciar:
            voz.hablar(texto)

    def _linea_desde_hilo(self, linea):
        """Recibe cada línea de tdl desde el hilo de lectura; no toca la interfaz."""
        self._ultima_actividad_tdl = time.monotonic()
        if self._filtrar_progreso and tdl.es_linea_de_progreso(linea):
            self._registrar_progreso_de_tdl(linea)
            # La barra de progreso se redibuja varias veces por segundo: ni a la
            # ventana ni al log salvo de vez en cuando.
            ahora = time.monotonic()
            if ahora - self._ultimo_log_progreso >= INTERVALO_LOG_PROGRESO_SEGUNDOS:
                self._ultimo_log_progreso = ahora
                logger.info("tdl (progreso): %s", linea)
            return
        if not self._filtrar_progreso:
            self._salida_acumulada.append(linea)
        logger.info("tdl: %s", linea)
        self._cola_registro.append(linea)

    def _registrar_progreso_de_tdl(self, linea):
        """Guarda lo último que dice tdl: un bloque de líneas de archivos y una general al final."""
        dato = tdl.interpretar_progreso(linea)
        if dato is None:
            return
        if dato["tipo"] == "archivo":
            self._bloque_tdl.append(dato)
            if len(self._bloque_tdl) > 32:
                del self._bloque_tdl[:-16]
        else:
            self._estado_tdl = {"archivos": list(self._bloque_tdl), "velocidad": dato["velocidad"],
                                "momento": time.monotonic()}
            self._bloque_tdl = []

    def _vaciar_cola_registro(self, _evento=None):
        """Vuelca al registro, de golpe y desde el hilo principal, lo acumulado por tdl."""
        lineas = []
        while self._cola_registro and len(lineas) < 200:
            lineas.append(self._cola_registro.popleft())
        if lineas:
            self.registro.AppendText("\n".join(lineas) + "\n")

    def _lanzar(self, argumentos, al_terminar, filtrar_progreso=False):
        """Ejecuta tdl; al_terminar se recibe en el hilo principal con (codigo, salida).

        Devuelve False si no se pudo lanzar (por ejemplo, porque ya hay otra operación en curso).
        """
        self._salida_acumulada = []
        self._filtrar_progreso = filtrar_progreso
        self._ultimo_log_progreso = 0.0
        self._bloque_tdl = []
        self._estado_tdl = None
        self._ultima_actividad_tdl = time.monotonic()

        def terminado(codigo):
            salida = "\n".join(self._salida_acumulada)
            wx.CallAfter(al_terminar, codigo, salida)

        try:
            self.ejecutor.ejecutar(argumentos, self._linea_desde_hilo, terminado)
        except RuntimeError as error:
            self._escribir(str(error), anunciar=True)
            return False
        return True
    # ANCLAJE_FIN: VENTANA_REGISTRO

    # ANCLAJE_INICIO: VENTANA_ACCIONES
    def _comprobar_tdl(self):
        if not self.ejecutor.disponible():
            self._escribir(
                "No se encuentra tdl. Ve a la pestaña Conexión y pulsa Instalar o actualizar tdl.",
                anunciar=True,
            )

    def _al_instalar_tdl(self, _evento):
        if self.ejecutor.en_ejecucion():
            self._escribir("Hay una operación en curso. Espera a que termine.", anunciar=True)
            return
        self.boton_instalar_tdl.Disable()
        self._escribir("Descargando tdl {}. Esto puede tardar un poco.".format(instalador_tdl.VERSION_TDL),
                       anunciar=True)
        threading.Thread(target=self._hilo_instalar_tdl, daemon=True).start()

    def _hilo_instalar_tdl(self):
        # Solo se anuncia cada 25 % para no saturar la voz del lector de pantalla.
        ultimo_anunciado = [0]

        def progreso(porcentaje):
            if porcentaje >= ultimo_anunciado[0] + 25 and porcentaje < 100:
                ultimo_anunciado[0] = porcentaje - porcentaje % 25
                wx.CallAfter(self._escribir, "Descargado el {} por ciento.".format(ultimo_anunciado[0]), True)

        try:
            instalador_tdl.instalar_tdl(al_progreso=progreso)
            wx.CallAfter(self._tras_instalar_tdl, "tdl se ha instalado correctamente.")
        except instalador_tdl.ErrorInstalacionTdl as error:
            wx.CallAfter(self._tras_instalar_tdl, str(error))
        except Exception:
            logger.exception("Fallo inesperado al instalar tdl")
            wx.CallAfter(self._tras_instalar_tdl, "Ha ocurrido un error inesperado al instalar tdl.")

    def _tras_instalar_tdl(self, mensaje):
        self._escribir(mensaje, anunciar=True)
        self.boton_instalar_tdl.Enable()
        self.boton_instalar_tdl.SetFocus()

    def _al_sesion_escritorio(self, _evento):
        self._iniciar_sesion_en_consola(
            tdl.comando_iniciar_sesion_escritorio(),
            "Se abre una ventana para importar la sesión de Telegram Desktop.",
        )

    def _al_sesion_codigo(self, _evento):
        self._iniciar_sesion_en_consola(
            tdl.comando_iniciar_sesion_codigo(),
            "Se abre una ventana. Escribe tu teléfono con prefijo, por ejemplo más cuatro cuatro, y después el código que recibas en Telegram.",
        )

    def _iniciar_sesion_en_consola(self, argumentos, aviso):
        """El inicio de sesión es interactivo: se hace en una consola real de Windows."""
        if not self.ejecutor.disponible():
            self._escribir("Primero instala tdl con el botón Instalar o actualizar tdl.", anunciar=True)
            return
        try:
            proceso = tdl.abrir_en_consola(argumentos)
        except OSError:
            logger.exception("No se pudo abrir la consola de tdl")
            self._escribir("No se pudo abrir la ventana de inicio de sesión.", anunciar=True)
            return
        self._escribir(aviso, anunciar=True)
        threading.Thread(target=self._esperar_consola, args=(proceso,), daemon=True).start()

    def _esperar_consola(self, proceso):
        proceso.wait()
        wx.CallAfter(
            self._escribir,
            "La ventana de inicio de sesión se ha cerrado. Pulsa Actualizar lista de canales para comprobar que funciona.",
            True,
        )

    def _al_actualizar_chats(self, _evento):
        self._escribir("Consultando tus canales...", anunciar=True)
        self._lanzar(tdl.comando_listar_chats(), self._tras_listar_chats)

    def _tras_listar_chats(self, codigo, salida):
        if codigo != 0:
            self._escribir("No se pudo obtener la lista de canales.", anunciar=True)
            return
        self._chats = tdl.parsear_lista_chats(salida)
        self.lista_chats.Freeze()
        self.lista_chats.Clear()
        for chat in self._chats:
            usuario = " (@{})".format(chat["usuario"]) if chat["usuario"] else ""
            self.lista_chats.Append(chat["nombre"] + usuario)
        self.lista_chats.Thaw()
        if self._chats:
            self.lista_chats.SetSelection(0)
        self._escribir("Se han encontrado {} canales y chats.".format(len(self._chats)), anunciar=True)

    def _al_examinar(self, _evento):
        self._elegir_carpeta(self.campo_carpeta, "Elige la carpeta de destino", self.boton_examinar)

    def _elegir_carpeta(self, campo, titulo, boton):
        dialogo = wx.DirDialog(self, titulo, campo.GetValue(), style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dialogo.ShowModal() == wx.ID_OK:
            campo.SetValue(dialogo.GetPath())
        dialogo.Destroy()
        boton.SetFocus()

    def _canal_seleccionado(self):
        indice = self.lista_chats.GetSelection()
        if indice == wx.NOT_FOUND or indice >= len(self._chats):
            return None
        return self._chats[indice]

    def _actualizar_canal_en_descarga(self):
        canal = self._canal_seleccionado()
        self.campo_canal.SetValue(canal["nombre"] if canal else "Ninguno")

    def _al_cambiar_pestana(self, evento):
        evento.Skip()
        wx.CallAfter(self._actualizar_canal_en_descarga)

    @staticmethod
    def _ruta_exportacion_de(canal):
        """Cada canal tiene su propia lista, con el nombre del canal, para no mezclarlas."""
        return exportaciones.ruta_de_exportacion(canal, RUTA_EXPORTACIONES, RUTA_REGISTROS)

    def _al_exportar(self, _evento):
        canal = self._canal_seleccionado()
        if canal is None:
            self._escribir("Primero elige un canal en la pestaña Canal.", anunciar=True)
            return
        self._exportar(canal, self._tras_exportar)

    def _exportar(self, canal, al_terminar):
        os.makedirs(RUTA_EXPORTACIONES, exist_ok=True)
        self._escribir("Exportando la lista de archivos del canal {}...".format(canal["nombre"]), anunciar=True)
        self._lanzar(tdl.comando_exportar_chat(canal["id"], self._ruta_exportacion_de(canal)),
                     lambda codigo, _salida: al_terminar(canal, codigo))

    def _tras_exportar(self, canal, codigo):
        if codigo != 0:
            self._escribir("No se pudo exportar el canal {}.".format(canal["nombre"]), anunciar=True)
            return
        total = tdl.contar_archivos_exportados(self._ruta_exportacion_de(canal))
        self._escribir("Exportación lista: el canal {n} tiene {t} archivos. La lista está en la carpeta de listas exportadas."
                       .format(n=canal["nombre"], t=total), anunciar=True)

    def _al_descargar(self, _evento):
        canal = self._canal_seleccionado()
        if canal is None:
            self._escribir("Primero elige un canal en la pestaña Canal.", anunciar=True)
            return
        if self.ejecutor.en_ejecucion():
            self._escribir("Hay una operación en curso. Espera a que termine o pulsa Pausar.", anunciar=True)
            return
        if not os.path.isfile(self._ruta_exportacion_de(canal)):
            self._escribir("El canal {} aún no está exportado. Se exporta ahora y después empieza la descarga."
                           .format(canal["nombre"]), anunciar=True)
            self._exportar(canal, self._tras_exportar_para_descargar)
            return
        self._descargar(canal)

    def _tras_exportar_para_descargar(self, canal, codigo):
        if codigo != 0:
            self._escribir("No se pudo exportar el canal {}.".format(canal["nombre"]), anunciar=True)
            return
        self._descargar(canal)

    def _descargar(self, canal):
        base = self.campo_carpeta.GetValue().strip()
        if not base:
            self._escribir("Indica una carpeta de destino.", anunciar=True)
            return
        carpeta = os.path.join(base, clasificador.nombre_seguro(canal["nombre"]))
        perfil = self.selector_perfil.GetStringSelection()
        extensiones = extensiones_del_perfil(perfil)
        limite = self.campo_limite.GetValue()
        ruta_lista = self._ruta_exportacion_de(canal)
        try:
            resumen = filtro_exportacion.filtrar_exportacion(ruta_lista, self._ruta_filtrada, extensiones, limite)
        except (ValueError, OSError):
            logger.exception("No se pudo preparar la lista de descarga")
            self._escribir("No se pudo preparar la lista de descarga. Vuelve a exportar el canal.", anunciar=True)
            return
        if resumen.seleccionados == 0:
            self._escribir("En el canal {} no hay archivos de ese tipo de contenido.".format(canal["nombre"]),
                           anunciar=True)
            return
        ya = min(resumen.seleccionados, resumen_carpeta.resumir_completos(carpeta, extensiones)[0])
        faltan = resumen.seleccionados - ya
        if faltan == 0:
            self._escribir(
                "En la carpeta ya hay {ya} archivos de ese tipo y el canal tiene {n}: no hay nada que descargar. "
                "Si el canal tiene archivos nuevos, pulsa Exportar para actualizar la lista."
                .format(ya=ya, n=resumen.seleccionados), anunciar=True)
            return
        if not self._espacio_suficiente(carpeta, faltan):
            return
        os.makedirs(carpeta, exist_ok=True)
        self._resumen_filtro = resumen
        self._carpeta_descarga = carpeta
        self._escribir(
            "Canal {canal}. Se usa la lista exportada {antiguedad}. Hay {sel} archivos de ese tipo, de {total} que tiene "
            "el canal. Ya están descargados {ya}; se descargarán los {faltan} que faltan, en la carpeta {carpeta}. "
            "tdl puede tardar unos minutos en empezar a bajar. Pulsa Control E para saber cómo va."
            .format(canal=canal["nombre"], antiguedad=exportaciones.describir_antiguedad(ruta_lista),
                    sel=resumen.seleccionados, total=resumen.total_con_archivo, ya=ya, faltan=faltan, carpeta=carpeta),
            anunciar=True,
        )
        self._ajustes = dict(
            self._ajustes,
            hilos=self.campo_hilos.GetValue(),
            simultaneas=self.campo_simultaneas.GetValue(),
            takeout=self.casilla_takeout.GetValue(),
        )
        try:
            ajustes.guardar_ajustes(self._ajustes)
        except Exception:
            logger.exception("No se pudieron guardar los ajustes de descarga")
        comando = tdl.comando_descargar(
            self._ruta_filtrada, carpeta, hilos=self._ajustes["hilos"],
            simultaneas=self._ajustes["simultaneas"], takeout=self._ajustes["takeout"])
        self._comando_descarga = comando
        self._perfil_descarga = perfil
        self._pausa_pedida = False
        self._reintentos = 0
        self._esperando_reintento = False
        if self._lanzar(comando, self._tras_descargar, filtrar_progreso=True):
            evitar_suspension.bloquear()
            self._iniciar_vigilancia(carpeta, resumen.seleccionados, extensiones, ya)

    # ANCLAJE_INICIO: VENTANA_ESPACIO
    def _espacio_suficiente(self, carpeta, total):
        """Dice cuánto espacio hay y, si se conoce el tamaño medio, avisa de si no cabe."""
        libre = control_espacio.espacio_libre(carpeta)
        if libre is None:
            self._escribir("No se pudo comprobar el espacio libre del disco.", anunciar=True)
            return True
        perfil = self.selector_perfil.GetStringSelection()
        medio = self._ajustes.get("tamanos_medios", {}).get(perfil)
        estimado = medio * total if medio else None
        texto = "Espacio libre en el disco de destino: {}.".format(resumen_carpeta.formatear_tamano(libre))
        if estimado:
            texto += " Como mucho esta descarga ocupará unos {}.".format(resumen_carpeta.formatear_tamano(estimado))
        else:
            texto += (" Aún no sé cuánto ocupará este tipo de contenido: haz antes una descarga de prueba "
                      "con un límite pequeño para calcularlo.")
        self._escribir(texto, anunciar=True)
        if control_espacio.cabe(libre, estimado) is False:
            return self._confirmar(
                "Puede que no quepa: tienes {l} libres y se calcula que ocupará unos {e}. "
                "¿Descargar de todos modos?".format(
                    l=resumen_carpeta.formatear_tamano(libre), e=resumen_carpeta.formatear_tamano(estimado)),
                "Poco espacio en el disco",
            )
        return True

    def _pausar_por_espacio(self, libre):
        """Para la descarga antes de llenar el disco."""
        self._pausa_pedida = True
        avisos_sonoros.sonar_error()
        self._escribir(
            "Queda muy poco espacio en el disco: {}. Se pausa la descarga para no llenarlo. "
            "Libera espacio y pulsa Descargar para reanudarla.".format(resumen_carpeta.formatear_tamano(libre)),
            anunciar=True,
        )
        self._cancelar_reintento()
        if self.ejecutor.en_ejecucion():
            self.ejecutor.cancelar()
        else:
            self._finalizar_descarga()
    # ANCLAJE_FIN: VENTANA_ESPACIO

    # ANCLAJE_INICIO: VENTANA_PROGRESO
    def _iniciar_vigilancia(self, carpeta, total, extensiones, ya):
        """Cuenta cada pocos segundos los archivos terminados y avisa sin saturar la voz.

        El recuento es el total de la carpeta, no solo lo de esta sesión: al reanudar
        después de una pausa sigue por donde iba y no vuelve a cero.
        """
        self._detener_vigilancia()
        parar = threading.Event()
        self._parar_vigilancia = parar
        self._progreso = (ya, total, 0)
        self.indicador.SetRange(max(total, 1))
        self.indicador.SetValue(ya)
        threading.Thread(target=self._hilo_vigilar, args=(carpeta, total, extensiones, parar), daemon=True).start()

    def _detener_vigilancia(self):
        if self._parar_vigilancia is not None:
            self._parar_vigilancia.set()
            self._parar_vigilancia = None

    def _hilo_vigilar(self, carpeta, total, extensiones, parar):
        archivos_base = resumen_carpeta.resumir_completos(carpeta, extensiones)[0]
        ultimo_anunciado = 0
        ultimo_aviso = time.monotonic()
        aviso_de_silencio_dado = False
        while not parar.wait(INTERVALO_VIGILANCIA_SEGUNDOS):
            archivos = resumen_carpeta.resumir_completos(carpeta, extensiones)[0]
            hechos = min(total, archivos)
            nuevos = max(0, archivos - archivos_base)
            ahora = time.monotonic()
            anunciar = nuevos != ultimo_anunciado and ahora - ultimo_aviso >= INTERVALO_AVISO_PROGRESO_SEGUNDOS
            if anunciar:
                ultimo_anunciado = nuevos
                ultimo_aviso = ahora
            wx.CallAfter(self._mostrar_progreso, hechos, total, nuevos, anunciar)
            silencio = ahora - self._ultima_actividad_tdl
            if silencio >= UMBRAL_SILENCIO_SEGUNDOS and not aviso_de_silencio_dado:
                aviso_de_silencio_dado = True
                wx.CallAfter(self._avisar_silencio, silencio)
            elif silencio < UMBRAL_SILENCIO_SEGUNDOS:
                aviso_de_silencio_dado = False
            libre = control_espacio.espacio_libre(carpeta)
            if libre is not None and libre < control_espacio.RESERVA_MINIMA_BYTES:
                wx.CallAfter(self._pausar_por_espacio, libre)
                return

    def _avisar_silencio(self, segundos):
        if not self.ejecutor.en_ejecucion():
            return
        self._escribir(
            "tdl lleva {m} minutos sin dar señales. Puede estar preparando la lista o comprobando los archivos ya "
            "descargados, o haber perdido la conexión. Pulsa Control E para ver su estado. Si sigue igual unos "
            "minutos más, pulsa Pausar y después Descargar.".format(m=int(segundos // 60)),
            anunciar=True,
        )

    @staticmethod
    def _texto_progreso(hechos, total, nuevos):
        texto = "Descargados {h} de {t} archivos.".format(h=hechos, t=total)
        if nuevos and nuevos != hechos:
            texto += " {n} en esta sesión.".format(n=nuevos)
        return texto

    def _texto_actividad_de_tdl(self):
        """Lo que está haciendo tdl ahora mismo, según lo último que ha escrito."""
        ahora = time.monotonic()
        estado = self._estado_tdl
        if estado and estado["archivos"] and ahora - estado["momento"] < 10:
            porcentajes = ", ".join("{:.0f}".format(a["porcentaje"]) for a in estado["archivos"])
            return " tdl está descargando {n} en paralelo, al {p} por ciento, a {v} en total.".format(
                n=len(estado["archivos"]), p=porcentajes, v=tdl.velocidad_hablada(estado["velocidad"]))
        silencio = ahora - self._ultima_actividad_tdl
        if silencio < 10:
            return " tdl está activo."
        return (" tdl no da señales desde hace {} segundos; puede estar preparando la lista o comprobando los "
                "archivos ya descargados.".format(int(silencio)))

    def _mostrar_progreso(self, hechos, total, nuevos, anunciar):
        if hechos > self._progreso[0]:
            self._reintentos = 0
        self._progreso = (hechos, total, nuevos)
        self.indicador.SetValue(hechos)
        if anunciar:
            self._escribir(self._texto_progreso(hechos, total, nuevos) + self._texto_actividad_de_tdl(),
                           anunciar=True)

    def _al_estado(self, _evento=None):
        if self._esperando_reintento:
            self._escribir("La descarga se cortó y está esperando para reintentarlo.", anunciar=True)
            return
        if not self.ejecutor.en_ejecucion() or self._parar_vigilancia is None:
            self._escribir("No hay ninguna descarga en curso.", anunciar=True)
            return
        hechos, total, nuevos = self._progreso
        texto = self._texto_progreso(hechos, total, nuevos) + self._texto_actividad_de_tdl()
        libre = control_espacio.espacio_libre(self._carpeta_descarga)
        if libre is not None:
            texto += " Espacio libre: {}.".format(resumen_carpeta.formatear_tamano(libre))
        self._escribir(texto, anunciar=True)

    def _al_abrir_descarga(self, _evento):
        canal = self._canal_seleccionado()
        base = self.campo_carpeta.GetValue().strip()
        self._abrir_carpeta(os.path.join(base, clasificador.nombre_seguro(canal["nombre"])) if canal else base)

    def _al_abrir_listas(self, _evento):
        self._abrir_carpeta(RUTA_EXPORTACIONES)

    def _abrir_carpeta(self, carpeta):
        """Abre una carpeta en el Explorador de Windows."""
        try:
            os.makedirs(carpeta, exist_ok=True)
            os.startfile(carpeta)
        except (OSError, AttributeError):
            logger.exception("No se pudo abrir la carpeta %s", carpeta)
            self._escribir("No se pudo abrir la carpeta {}.".format(carpeta), anunciar=True)
            return
        self._escribir("Se abre la carpeta {}.".format(carpeta), anunciar=True)

    def _registrar_atajos(self):
        """Atajos globales de la ventana; nunca la tecla Espacio."""
        id_estado = wx.NewIdRef()
        self.Bind(wx.EVT_MENU, self._al_estado, id=id_estado)
        self.SetAcceleratorTable(wx.AcceleratorTable([wx.AcceleratorEntry(wx.ACCEL_CTRL, ord("E"), id_estado)]))
    # ANCLAJE_FIN: VENTANA_PROGRESO

    def _finalizar_descarga(self):
        """Deja todo como antes de empezar: sin vigilancia y con el equipo libre de dormirse."""
        self._detener_vigilancia()
        evitar_suspension.liberar()
        self._esperando_reintento = False

    def _cancelar_reintento(self):
        if self._temporizador_reintento is not None:
            self._temporizador_reintento.Stop()
            self._temporizador_reintento = None
        self._esperando_reintento = False

    def _tras_descargar(self, codigo, _salida):
        self._vaciar_cola_registro()
        if codigo == 0:
            self._finalizar_descarga()
            avisos_sonoros.sonar_exito()
            self._escribir("Descarga terminada. Calculando el tamaño...", anunciar=True)
            threading.Thread(
                target=self._hilo_resumir_descarga, args=(self._carpeta_descarga, self._perfil_descarga), daemon=True
            ).start()
            return
        if self._pausa_pedida:
            self._finalizar_descarga()
            self._escribir("Descarga en pausa. Pulsa Descargar para reanudarla.", anunciar=True)
            return
        if self._reintentos < MAXIMO_REINTENTOS:
            self._reintentos += 1
            self._esperando_reintento = True
            self._escribir(
                "La descarga se ha cortado. Reintento {n} de {m} en {s} segundos."
                .format(n=self._reintentos, m=MAXIMO_REINTENTOS, s=ESPERA_REINTENTO_SEGUNDOS),
                anunciar=True,
            )
            self._temporizador_reintento = wx.CallLater(ESPERA_REINTENTO_SEGUNDOS * 1000, self._reintentar_descarga)
            return
        self._finalizar_descarga()
        avisos_sonoros.sonar_error()
        self._escribir(
            "La descarga se ha detenido tras varios intentos. Revisa la conexión y pulsa Descargar para reanudarla.",
            anunciar=True,
        )

    def _reintentar_descarga(self):
        self._temporizador_reintento = None
        self._esperando_reintento = False
        if self._pausa_pedida or self.ejecutor.en_ejecucion():
            return
        self._escribir("Reintentando la descarga...", anunciar=True)
        if not self._lanzar(self._comando_descarga, self._tras_descargar, filtrar_progreso=True):
            self._finalizar_descarga()

    def _hilo_resumir_descarga(self, carpeta, perfil):
        cantidad, total = resumen_carpeta.resumir_carpeta(carpeta, extensiones_del_perfil(perfil))
        wx.CallAfter(self._tras_resumir_descarga, cantidad, total, perfil)

    def _tras_resumir_descarga(self, cantidad, total, perfil):
        mensaje = "En la carpeta hay {n} archivos de ese tipo, que ocupan {t}.".format(
            n=cantidad, t=resumen_carpeta.formatear_tamano(total))
        if cantidad >= 3:
            # Se recuerda el tamaño medio de este tipo de contenido para estimar futuras descargas.
            self._ajustes["tamanos_medios"] = {
                **self._ajustes.get("tamanos_medios", {}), perfil: int(total / cantidad)}
            try:
                ajustes.guardar_ajustes(self._ajustes)
            except Exception:
                logger.exception("No se pudo guardar el tamaño medio por archivo")
        resumen = self._resumen_filtro
        if resumen and cantidad and resumen.seleccionados < resumen.coinciden:
            estimado = total / cantidad * resumen.coinciden
            mensaje += " Descargar los {c} de ese tipo ocuparía unos {e}, como cálculo orientativo.".format(
                c=resumen.coinciden, e=resumen_carpeta.formatear_tamano(estimado))
        self._escribir(mensaje, anunciar=True)

    def _al_pausar(self, _evento):
        if self._esperando_reintento:
            self._pausa_pedida = True
            self._cancelar_reintento()
            self._finalizar_descarga()
            self._escribir("Reintento cancelado. Pulsa Descargar para reanudar cuando quieras.", anunciar=True)
            return
        if self.ejecutor.en_ejecucion():
            self._pausa_pedida = True
            self.ejecutor.cancelar()
            self._escribir("Pausando...", anunciar=True)
    # ANCLAJE_FIN: VENTANA_ACCIONES

    # ANCLAJE_INICIO: VENTANA_CLASIFICAR
    @staticmethod
    def _texto_movimiento(movimiento, carpeta_biblioteca):
        carpeta = os.path.dirname(os.path.relpath(movimiento.destino, carpeta_biblioteca)).replace(os.sep, "/")
        texto = "{} → {}".format(os.path.basename(movimiento.origen), carpeta)
        if movimiento.conflicto:
            texto += " (conflicto: {})".format(movimiento.conflicto)
        return texto

    def _al_calcular_plan(self, _evento):
        if not self._conjuntos:
            self._escribir("No hay conjuntos de reglas en la carpeta configuraciones, reglas.", anunciar=True)
            return
        origen = self.campo_origen.GetValue().strip()
        biblioteca = self.campo_biblioteca.GetValue().strip()
        if not os.path.isdir(origen):
            self._escribir("La carpeta de origen no existe.", anunciar=True)
            return
        if not biblioteca:
            self._escribir("Indica la carpeta de la biblioteca.", anunciar=True)
            return
        ruta_reglas = self._conjuntos[self.selector_reglas.GetSelection()][1]
        self.boton_calcular.Disable()
        self._escribir("Calculando la vista previa...", anunciar=True)
        threading.Thread(target=self._hilo_calcular_plan, args=(origen, biblioteca, ruta_reglas), daemon=True).start()

    def _hilo_calcular_plan(self, origen, biblioteca, ruta_reglas):
        try:
            reglas = clasificador.cargar_reglas(ruta_reglas)
            movimientos, sin_clasificar = clasificador.planificar(origen, biblioteca, reglas)
        except Exception:
            logger.exception("Fallo al calcular la vista previa de la clasificación")
            wx.CallAfter(self._tras_calcular_plan, None, None, biblioteca)
            return
        wx.CallAfter(self._tras_calcular_plan, movimientos, sin_clasificar, biblioteca)

    def _tras_calcular_plan(self, movimientos, sin_clasificar, biblioteca):
        self.boton_calcular.Enable()
        if movimientos is None:
            self._escribir("No se pudo calcular la vista previa. Revisa el registro.", anunciar=True)
            return
        self._plan = movimientos
        self._sin_clasificar = sin_clasificar
        self.lista_plan.Freeze()
        self.lista_plan.Set([self._texto_movimiento(m, biblioteca) for m in movimientos])
        self.lista_plan.Thaw()
        self.lista_sin_clasificar.Freeze()
        self.lista_sin_clasificar.Set([os.path.basename(r) for r in sin_clasificar])
        self.lista_sin_clasificar.Thaw()
        conflictos = sum(1 for m in movimientos if m.conflicto)
        self._escribir(
            "Vista previa lista: se moverán {n} archivos, {s} quedan sin clasificar y {c} tienen conflicto."
            .format(n=len(movimientos) - conflictos, s=len(sin_clasificar), c=conflictos),
            anunciar=True,
        )
        if movimientos:
            self.lista_plan.SetSelection(0)
            self.lista_plan.SetFocus()

    def _confirmar(self, mensaje, titulo):
        dialogo = wx.MessageDialog(self, mensaje, titulo, wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION)
        dialogo.SetYesNoLabels("&Sí, continuar", "&No, cancelar")
        respuesta = dialogo.ShowModal()
        dialogo.Destroy()
        return respuesta == wx.ID_YES

    def _al_aplicar_plan(self, _evento):
        pendientes = sum(1 for m in self._plan if not m.conflicto)
        if not pendientes:
            self._escribir("No hay nada que aplicar. Calcula primero la vista previa.", anunciar=True)
            return
        confirmado = self._confirmar(
            "Se moverán {} archivos a la biblioteca. Después podrás deshacerlo. ¿Continuar?".format(pendientes),
            "Aplicar clasificación",
        )
        self.boton_aplicar.SetFocus()
        if not confirmado:
            return
        os.makedirs(RUTA_REGISTROS, exist_ok=True)
        ruta_registro = os.path.join(
            RUTA_REGISTROS, "movimientos_{}.json".format(datetime.now().strftime("%Y%m%d_%H%M%S")))
        self.boton_aplicar.Disable()
        self._escribir("Moviendo archivos...", anunciar=True)
        threading.Thread(target=self._hilo_aplicar_plan, args=(list(self._plan), ruta_registro), daemon=True).start()

    def _hilo_aplicar_plan(self, plan, ruta_registro):
        try:
            hechos, fallidos = clasificador.aplicar(plan, ruta_registro)
        except Exception:
            logger.exception("Fallo al aplicar la clasificación")
            wx.CallAfter(self._tras_aplicar_plan, 0, -1)
            return
        wx.CallAfter(self._tras_aplicar_plan, len(hechos), len(fallidos))

    def _tras_aplicar_plan(self, hechos, fallidos):
        self.boton_aplicar.Enable()
        self._plan = []
        self._sin_clasificar = []
        self.lista_plan.Clear()
        self.lista_sin_clasificar.Clear()
        if fallidos < 0:
            self._escribir("Ha ocurrido un error al mover los archivos. Revisa el registro.", anunciar=True)
            return
        mensaje = "Clasificación terminada: se han movido {} archivos.".format(hechos)
        if fallidos:
            mensaje += " {} no se pudieron mover; mira el registro.".format(fallidos)
        self._escribir(mensaje + " Puedes deshacerla desde el botón Deshacer.", anunciar=True)

    def _al_deshacer_clasificacion(self, _evento):
        ruta_registro = clasificador.ultimo_registro(RUTA_REGISTROS)
        if not ruta_registro:
            self._escribir("No hay ninguna clasificación que deshacer.", anunciar=True)
            return
        confirmado = self._confirmar(
            "Se devolverán los archivos de la última clasificación a su sitio de origen. ¿Continuar?",
            "Deshacer clasificación",
        )
        self.boton_deshacer.SetFocus()
        if not confirmado:
            return
        self.boton_deshacer.Disable()
        self._escribir("Deshaciendo la última clasificación...", anunciar=True)
        threading.Thread(target=self._hilo_deshacer, args=(ruta_registro,), daemon=True).start()

    def _hilo_deshacer(self, ruta_registro):
        try:
            revertidos, omitidos = clasificador.deshacer(ruta_registro)
        except Exception:
            logger.exception("Fallo al deshacer la clasificación")
            wx.CallAfter(self._tras_deshacer, 0, -1)
            return
        wx.CallAfter(self._tras_deshacer, revertidos, omitidos)

    def _tras_deshacer(self, revertidos, omitidos):
        self.boton_deshacer.Enable()
        if omitidos < 0:
            self._escribir("Ha ocurrido un error al deshacer. Revisa el registro.", anunciar=True)
            return
        mensaje = "Se han devuelto {} archivos a su sitio.".format(revertidos)
        if omitidos:
            mensaje += " {} se han omitido porque ya no estaban donde se esperaba.".format(omitidos)
        self._escribir(mensaje, anunciar=True)
    # ANCLAJE_FIN: VENTANA_CLASIFICAR
# ANCLAJE_FIN: VENTANA_PRINCIPAL
