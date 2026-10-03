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
│   ├── resumen_carpeta.py          # Recuento y tamaño de una carpeta, estimación de descarga
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
- **Una exportación por canal** (`exportacion_<id>.json`) y una subcarpeta de descarga por canal: nunca un archivo compartido.
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
