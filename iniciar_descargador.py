"""Punto de entrada del Descargador de Telegram Accesible."""
import logging
import logging.handlers
import os

RAIZ_INICIO = os.path.dirname(os.path.abspath(__file__))


# ANCLAJE_INICIO: CONFIGURAR_LOGGING
def configurar_logging():
    manejador = logging.handlers.RotatingFileHandler(
        os.path.join(RAIZ_INICIO, "descargador.log"),
        maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[manejador],
    )
# ANCLAJE_FIN: CONFIGURAR_LOGGING


def principal():
    configurar_logging()
    import wx
    from app.interfaz.ventana_principal import VentanaPrincipal
    aplicacion = wx.App(False)
    ventana = VentanaPrincipal()
    ventana.Show()
    aplicacion.MainLoop()


if __name__ == "__main__":
    principal()
