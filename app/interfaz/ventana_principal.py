"""Ventana principal: pestañas Conexión, Canal y Descarga, con un registro común."""
import logging
import os

import wx

from app.config_rutas import RAIZ, RUTA_REGISTROS
from app.motor import anunciador_lector as voz
from app.motor import ejecutor_tdl as tdl
from app.motor.perfiles_descarga import extensiones_del_perfil, nombres_de_perfiles

logger = logging.getLogger(__name__)


# ANCLAJE_INICIO: VENTANA_PRINCIPAL
class VentanaPrincipal(wx.Frame):
    def __init__(self):
        super().__init__(None, title="Descargador de Telegram Accesible", size=(820, 640))
        self.ejecutor = tdl.EjecutorTdl()
        self._chats = []
        self._ruta_exportacion = os.path.join(RUTA_REGISTROS, "exportacion.json")
        self._salida_acumulada = []
        self._construir_interfaz()
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
        caja.Add(self.boton_actualizar_chats, 0, wx.ALL, 8)
        caja.Add(etiqueta, 0, wx.LEFT | wx.RIGHT, 8)
        caja.Add(self.lista_chats, 1, wx.EXPAND | wx.ALL, 8)
        pagina.SetSizer(caja)
        return pagina

    def _pagina_descarga(self, padre):
        pagina = wx.Panel(padre)
        caja = wx.BoxSizer(wx.VERTICAL)
        etiqueta_perfil = wx.StaticText(pagina, label="&Tipo de contenido")
        self.selector_perfil = wx.Choice(pagina, choices=nombres_de_perfiles(), name="Tipo de contenido")
        self.selector_perfil.SetSelection(0)
        etiqueta_carpeta = wx.StaticText(pagina, label="Carpeta de &destino")
        self.campo_carpeta = wx.TextCtrl(pagina, value=os.path.join(RAIZ, "descargas"), name="Carpeta de destino")
        self.boton_examinar = wx.Button(pagina, label="&Examinar...")
        self.boton_examinar.Bind(wx.EVT_BUTTON, self._al_examinar)
        self.boton_exportar = wx.Button(pagina, label="E&xportar lista del canal seleccionado")
        self.boton_descargar = wx.Button(pagina, label="&Descargar / reanudar")
        self.boton_pausar = wx.Button(pagina, label="&Pausar")
        self.boton_exportar.Bind(wx.EVT_BUTTON, self._al_exportar)
        self.boton_descargar.Bind(wx.EVT_BUTTON, self._al_descargar)
        self.boton_pausar.Bind(wx.EVT_BUTTON, self._al_pausar)
        fila = wx.BoxSizer(wx.HORIZONTAL)
        fila.Add(self.campo_carpeta, 1, wx.RIGHT, 8)
        fila.Add(self.boton_examinar, 0)
        for control in (etiqueta_perfil, self.selector_perfil, etiqueta_carpeta):
            caja.Add(control, 0, wx.ALL, 6)
        caja.Add(fila, 0, wx.EXPAND | wx.ALL, 6)
        for control in (self.boton_exportar, self.boton_descargar, self.boton_pausar):
            caja.Add(control, 0, wx.ALL, 6)
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
        self._salida_acumulada.append(linea)
        wx.CallAfter(self._escribir, linea)

    def _lanzar(self, argumentos, al_terminar):
        """Ejecuta tdl; al_terminar se recibe en el hilo principal con (codigo, salida)."""
        self._salida_acumulada = []

        def terminado(codigo):
            salida = "\n".join(self._salida_acumulada)
            wx.CallAfter(al_terminar, codigo, salida)

        try:
            self.ejecutor.ejecutar(argumentos, self._linea_desde_hilo, terminado)
        except RuntimeError as error:
            self._escribir(str(error), anunciar=True)
    # ANCLAJE_FIN: VENTANA_REGISTRO

    # ANCLAJE_INICIO: VENTANA_ACCIONES
    def _comprobar_tdl(self):
        if not self.ejecutor.disponible():
            self._escribir(
                "No se encuentra tdl. Copia tdl.exe en la carpeta bin del programa.", anunciar=True
            )

    def _al_sesion_escritorio(self, _evento):
        self._escribir("Importando la sesión de Telegram Desktop...", anunciar=True)
        self._lanzar(tdl.comando_iniciar_sesion_escritorio(), self._tras_sesion)

    def _al_sesion_codigo(self, _evento):
        self._escribir("Iniciando sesión con código. Sigue las indicaciones del registro.", anunciar=True)
        self._lanzar(tdl.comando_iniciar_sesion_codigo(), self._tras_sesion)
        wx.CallLater(1500, self._pedir_entrada)

    def _pedir_entrada(self):
        if not self.ejecutor.en_ejecucion():
            return
        dialogo = wx.TextEntryDialog(
            self, "Escribe lo que pide tdl (teléfono o código recibido) y pulsa Aceptar.", "Datos de acceso"
        )
        if dialogo.ShowModal() == wx.ID_OK:
            self.ejecutor.enviar_entrada(dialogo.GetValue())
            wx.CallLater(3000, self._pedir_entrada)
        dialogo.Destroy()

    def _tras_sesion(self, codigo, _salida):
        if codigo == 0:
            self._escribir("Sesión iniciada correctamente.", anunciar=True)
        else:
            self._escribir("No se pudo iniciar la sesión. Revisa el registro.", anunciar=True)

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
        dialogo = wx.DirDialog(self, "Elige la carpeta de destino", self.campo_carpeta.GetValue())
        if dialogo.ShowModal() == wx.ID_OK:
            self.campo_carpeta.SetValue(dialogo.GetPath())
        dialogo.Destroy()
        self.boton_examinar.SetFocus()

    def _al_exportar(self, _evento):
        indice = self.lista_chats.GetSelection()
        if indice == wx.NOT_FOUND:
            self._escribir("Primero elige un canal en la pestaña Canal.", anunciar=True)
            return
        os.makedirs(RUTA_REGISTROS, exist_ok=True)
        self._escribir("Exportando la lista de archivos del canal...", anunciar=True)
        self._lanzar(tdl.comando_exportar_chat(self._chats[indice]["id"], self._ruta_exportacion),
                     self._tras_exportar)

    def _tras_exportar(self, codigo, _salida):
        if codigo != 0:
            self._escribir("No se pudo exportar el canal.", anunciar=True)
            return
        total = tdl.contar_archivos_exportados(self._ruta_exportacion)
        self._escribir("Exportación lista: {} archivos en el canal.".format(total), anunciar=True)

    def _al_descargar(self, _evento):
        if not os.path.isfile(self._ruta_exportacion):
            self._escribir("Primero exporta la lista del canal.", anunciar=True)
            return
        carpeta = self.campo_carpeta.GetValue().strip()
        if not carpeta:
            self._escribir("Indica una carpeta de destino.", anunciar=True)
            return
        os.makedirs(carpeta, exist_ok=True)
        extensiones = extensiones_del_perfil(self.selector_perfil.GetStringSelection())
        self._escribir("Descargando. Puedes pausar y reanudar cuando quieras.", anunciar=True)
        self._lanzar(tdl.comando_descargar(self._ruta_exportacion, carpeta, extensiones), self._tras_descargar)

    def _tras_descargar(self, codigo, _salida):
        if codigo == 0:
            self._escribir("Descarga terminada.", anunciar=True)
        else:
            self._escribir("La descarga se ha detenido. Pulsa Descargar para reanudarla.", anunciar=True)

    def _al_pausar(self, _evento):
        if self.ejecutor.en_ejecucion():
            self.ejecutor.cancelar()
            self._escribir("Pausando...", anunciar=True)
    # ANCLAJE_FIN: VENTANA_ACCIONES
# ANCLAJE_FIN: VENTANA_PRINCIPAL
