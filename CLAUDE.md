# CLAUDE.md — Descargador de Telegram Accesible

Léelo entero antes de tocar nada. Estas reglas no son sugerencias.

## Identidad del proyecto

Aplicación de escritorio para Windows que descarga de forma masiva los archivos de canales de Telegram y los clasifica. Diseñada por y para personas ciegas: la accesibilidad con NVDA es un requisito no negociable. Por debajo ejecuta `tdl` como proceso externo.

- Desarrolladora: Dayanna Parson (TifloTutos · tiflotutos.com)
- Python 3.12+ · wxPython 4.2+ · Windows como plataforma principal

## Reglas absolutas de colaboración

- **Sin rastro de conversaciones:** ninguna referencia en el código ni en los comentarios a conversaciones, sugerencias de IA o sesiones de trabajo.
- **Todo en español:** variables, funciones, clases, comentarios, logs y cadenas de interfaz.
- **Anclajes obligatorios:** todo bloque reemplazable va entre `# ANCLAJE_INICIO: NOMBRE` y `# ANCLAJE_FIN: NOMBRE`. Al entregar código, indica qué bloque reemplaza.
- **Cambios quirúrgicos:** no reescribas un archivo entero si solo cambia un bloque.

## Estructura

```
app/
├── interfaz/ventana_principal.py   # Ventana con pestañas Conexión, Canal, Descarga, Clasificar
├── motor/
│   ├── ejecutor_tdl.py             # Comandos de tdl (bloque TDL_COMANDOS), ejecución en hilo, parseo
│   ├── clasificador.py             # Reglas configurables, series, iniciales: planificar, aplicar, deshacer
│   ├── filtro_exportacion.py       # Recorta la exportación del canal por tipo y límite de archivos
│   ├── descargados.py              # Registro de mensajes ya descargados, que sobrevive a clasificar o mover
│   ├── canales.py                  # Lista de canales recordada entre sesiones
│   ├── exportaciones.py            # Ruta legible de la lista exportada de cada canal y su antigüedad
│   ├── resumen_carpeta.py          # Recuento y tamaño de lo descargado, velocidad media, estimación
│   ├── evitar_suspension.py        # Mantiene el equipo despierto durante la descarga (SetThreadExecutionState)
│   ├── control_espacio.py          # Espacio libre y si una descarga cabe
│   ├── avisos_sonoros.py           # Sonidos del sistema de éxito y error
│   ├── ajustes.py                  # Ajustes recordados (hilos, archivos a la vez, sesión de exportación)
│   ├── instalador_tdl.py           # Descarga, descomprime e instala tdl.exe en bin/ (versión fijada en INSTALADOR_TDL_CONSTANTES)
│   ├── perfiles_descarga.py        # Extensiones por tipo de contenido
│   ├── almacen_json.py             # Lectura y escritura atómica de JSON
│   └── anunciador_lector.py        # accessible_output3: anuncios al lector de pantalla
└── config_rutas.py                 # Rutas absolutas desde RAIZ
configuraciones/reglas/*.json       # Conjuntos de reglas de clasificación (Cómics, Series y películas, ...)
INICIAR_DESCARGADOR.bat             # Lanzador para Windows (comprueba dependencias, abre sin consola)
tests/
```

## Reglas críticas

- **Rutas absolutas** siempre, partiendo de `RAIZ` en `config_rutas.py`.
- **Hilos:** tdl y cualquier trabajo pesado van en hilo secundario; la interfaz se actualiza solo con `wx.CallAfter`.
- **Escritura JSON atómica** con `guardar_json_atomico`.
- **Errores nunca silenciosos:** prohibido `except: pass` sin `logger.exception(...)`.
- **Anuncios por voz** con `app.motor.anunciador_lector.hablar()`. No uses `SetLabel()` de un `StaticText` para algo que NVDA deba decir.
- **Atajos:** nunca la tecla Espacio.
- **Opciones de tdl:** viven todas en el bloque `TDL_COMANDOS` de `ejecutor_tdl.py`. Si una versión de tdl cambia una opción, solo se toca ahí.
- **Pasos interactivos de tdl (inicio de sesión):** van en una consola real con `abrir_en_consola`, nunca por tuberías: tdl pregunta de forma interactiva y necesita un terminal.
- **Nunca vuelques a la interfaz cada línea de tdl:** su barra de progreso se redibuja varias veces por segundo y satura la cola de eventos de wx (la ventana deja de responder). Las líneas de progreso se descartan (`es_linea_de_progreso`) y el resto pasa por una cola que un temporizador vuelca al registro de golpe.
- **tdl guarda los archivos como `<idCanal>_<idMensaje>_nombre`** (plantilla por defecto). El clasificador siempre quita ese prefijo (`quitar_prefijo_de_tdl`) antes de aplicar reglas; no lo olvides en cualquier código nuevo que lea nombres de la carpeta de descargas.
- **Velocidad:** `--pool` de tdl debe crecer con `-t` x `-l` (ver `comando_descargar`); los ajustes del usuario viven en `ajustes.py`. El progreso se mide solo con archivos terminados, nunca con los `.tmp`, que reservan el tamaño final.
- **Descargas largas:** `evitar_suspension.bloquear()`/`liberar()` siempre desde el hilo principal y emparejados (todo final de descarga pasa por `_finalizar_descarga`). Los reintentos y la pausa por poco espacio respetan `_pausa_pedida`: lo que pide el usuario nunca se reintenta.
- **El tamaño medio por archivo se calcula por tipo de contenido y solo con archivos de ese tipo** (`tamanos_medios` en `ajustes.py`); mezclarlos, por ejemplo con las portadas, daría estimaciones optimistas.
- **El progreso es absoluto:** archivos terminados de ese tipo en la carpeta del canal frente al total de la lista, nunca solo los de la sesión (al reanudar se vería «0 de N»). La velocidad que se dice es la que mide tdl (`interpretar_progreso`); calcularla con archivos terminados da cifras absurdas con vídeos grandes.
- **`--disable-progress-ps` solo oculta la línea de CPU y memoria de tdl**, no su barra de progreso: esa se filtra con `es_linea_de_progreso`.
- **Cerrar la ventana nunca deja a tdl huérfano:** `_al_cerrar` pide confirmación y llama a `detener_y_esperar()`. Windows no mata a los procesos hijos al cerrar el padre. Antes de empezar una descarga se detectan y ofrecen detener los tdl ajenos (`procesos_tdl_ajenos`).
- **Al reanudar solo se pasan a tdl los mensajes que faltan** (`ids_de_mensajes_descargados` + `filtrar_exportacion(..., ya_descargados)`), reconocidos por el prefijo `<idCanal>_<idMensaje>_`. Si el prefijo no coincidiera, no se excluye nada y se vuelve al comportamiento anterior, nunca se saltan archivos que no estén.
- **El silencio de tdl al reanudar es normal hasta unos 12 minutos** (medido en un log real); el aviso de silencio salta a los 15.
- **Al abrir, los canales salen de `configuraciones/canales.json`** y se refrescan en segundo plano. Cuando se sustituye `self._chats`, el canal elegido se calcula ANTES (la posición de la lista es de la lista anterior). Se recuerdan `ultimo_canal`, `perfil` y `carpeta_descarga` en `ajustes.json`.
- **Las reglas con episodios numerados** usan `temporadas_desde` y `bloque`; nunca inventes una temporada que los datos no respalden. Los nombres finales conservan siempre la extensión aunque se recorten.
- **Clasificar quita el prefijo de tdl, así que antes de mover se apunta cada mensaje en `descargados.json`** (`descargados.anotar_rutas`); `_descargar` une ese registro con lo que hay en la carpeta. Sin él, «Descargar» tras clasificar volvería a bajar todo el canal. El progreso es `ya + nuevos` de la sesión.
- **`clasificador.aplicar` guarda el registro de movimientos cada 25 archivos** y avisa del progreso: una mudanza entre discos es larga y puede cortarse. Entre discos distintos se comprueba el espacio del destino (`en_el_mismo_disco`).
- **Una exportación por canal** (`<nombre> (<id>).json`) y una subcarpeta de descarga por canal: nunca un archivo compartido.
- **Atajos de la ventana** (`_registrar_atajos`): Control+E anuncia el estado de la descarga. Nunca la tecla Espacio.
- **Toda la salida de tdl se registra** en `descargador.log` (`logger.info`), no solo en la ventana: si algo falla, el log debe bastar para diagnosticarlo.
- **Clasificar es reversible:** `aplicar()` siempre guarda un registro y `deshacer()` lo revierte. Nunca muevas archivos sin vista previa y sin registro.
- No añadas dependencias sin justificación.

## Accesibilidad NVDA: checklist antes de dar un cambio de interfaz por terminado

1. ¿El foco llega a donde debe al cambiar de pestaña y al cerrar diálogos?
2. ¿Todos los controles tienen etiqueta (`StaticText` previo con `&`) y nombre accesible?
3. ¿Los avisos de progreso son puntuales, sin saturar la cola de voz?
4. ¿Los atajos evitan la tecla Espacio?

## Pruebas

`python -m unittest discover -s tests -t . -v`. No añadas pruebas que dependan de wxPython, de tdl real ni de Telegram.

## Pendiente

- Probar la ventana en Windows con tdl real y NVDA (la lógica está probada; los controles no).
- Atajos de teclado centralizados en el frame.
- Reglas de clasificación afinadas con las exportaciones reales de cada canal.
- Descomprimir opcionalmente los .zip y .rar tras clasificar.
- Internacionalización, si se quiere.
