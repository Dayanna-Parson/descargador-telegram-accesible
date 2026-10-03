# Descargador de Telegram Accesible

Aplicación de escritorio para Windows, accesible con lectores de pantalla, que descarga de forma masiva los archivos de un canal de Telegram (vídeo, cómics, libros, complementos...) y los clasifica con reglas configurables. Por debajo usa [tdl](https://github.com/iyear/tdl).

Desarrolladora: Dayanna Parson (TifloTutos · tiflotutos.com)

## Puesta en marcha

1. Instala Python 3.12+ y las dependencias: `pip install -r requisitos.txt`.
2. Abre el programa con doble clic en `INICIAR_DESCARGADOR.bat` (o con `python iniciar_descargador.py`). Si faltan dependencias, el `.bat` te lo dice.
3. En la pestaña Conexión, pulsa «Instalar o actualizar tdl»: descarga la versión fijada en `app/motor/instalador_tdl.py` (bloque `INSTALADOR_TDL_CONSTANTES`), la descomprime y deja `tdl.exe` en `bin/`. También puedes copiarlo a mano desde las *releases* de tdl.
4. En la misma pestaña, inicia sesión: se abre una ventana de consola donde tdl te hace las preguntas (teléfono con prefijo y código de Telegram). Todo lo que diga tdl queda además en `descargador.log`. En Canal, actualiza la lista y elige el canal. En Descarga, exporta la lista, elige tipo de contenido y carpeta, y descarga.

Si la descarga se corta o la pausas, vuelve a pulsar «Descargar / reanudar»: tdl continúa donde se quedó.

## Clasificación

Las reglas están en `configuraciones/reglas_clasificacion.json`. Cada una tiene `patron` (expresión regular), `carpeta` y, opcionalmente, `nombre_nuevo`; ambas plantillas admiten los grupos con nombre del patrón. Más detalle en `app/motor/clasificador.py`.

## Pruebas

```
python -m unittest discover -s tests -t . -v
```

## Estado

La lógica de comandos, el parseo y la clasificación están probados. La ventana y las opciones exactas de línea de comandos de tdl (todas en `app/motor/ejecutor_tdl.py`, bloque `TDL_COMANDOS`) están pendientes de probar en Windows con tdl real. La pestaña Clasificar de la interfaz aún no está hecha.
