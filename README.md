# Descargador de Telegram Accesible

Aplicación de escritorio para Windows, accesible con lectores de pantalla, que descarga de forma masiva los archivos de un canal de Telegram (vídeo, cómics, libros, complementos...) y los clasifica con reglas configurables. Por debajo usa [tdl](https://github.com/iyear/tdl).

Desarrolladora: Dayanna Parson (TifloTutos · tiflotutos.com)

## Puesta en marcha

1. Instala Python 3.12+ y las dependencias: `pip install -r requisitos.txt`.
2. Abre el programa con doble clic en `INICIAR_DESCARGADOR.bat` (o con `python iniciar_descargador.py`). Si faltan dependencias, el `.bat` te lo dice.
3. En la pestaña Conexión, pulsa «Instalar o actualizar tdl»: descarga la versión fijada en `app/motor/instalador_tdl.py` (bloque `INSTALADOR_TDL_CONSTANTES`), la descomprime y deja `tdl.exe` en `bin/`. También puedes copiarlo a mano desde las *releases* de tdl.
4. En la misma pestaña, inicia sesión: se abre una ventana de consola donde tdl te hace las preguntas (teléfono con prefijo y código de Telegram). Todo lo que diga tdl queda además en `descargador.log`. En Canal, actualiza la lista y elige el canal. En Descarga, exporta la lista, elige tipo de contenido y carpeta, y descarga.

Si la descarga se corta o la pausas, vuelve a pulsar «Descargar / reanudar»: tdl continúa donde se quedó.

## Descargar con prueba previa

En la pestaña Descarga eliges el tipo de contenido (Cómics, Vídeo, Libros...), que filtra por extensión y deja fuera, por ejemplo, las portadas `.jpg`. El campo **Límite de archivos** permite empezar por un número pequeño: al terminar, el programa te dice cuánto ocupa lo descargado y estima, de forma orientativa, cuánto ocuparía todo lo del mismo tipo. Si lo repites sin límite, tdl se salta lo que ya está descargado.

Cada canal tiene su propia lista exportada y su propia subcarpeta dentro de la carpeta de destino (`descargas/<nombre del canal>/`), así que nunca se mezclan. La pestaña Descarga muestra el canal elegido; si aún no está exportado, «Descargar» lo exporta antes de empezar.

**Progreso accesible.** Mientras se descarga, el programa cuenta cada pocos segundos los archivos terminados de la carpeta (no solo los de esta sesión: al pausar y reanudar sigue por donde iba) y los anuncia por voz, como máximo una vez cada 20 segundos. Si tdl lleva 2 minutos sin dar señales, lo avisa. Con **Control+E** (o el botón «Estado de la descarga») lo oyes cuando quieras. También hay un indicador de progreso, y el detalle completo queda en `descargador.log`.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Lo descargado | `descargas/<nombre del canal>/` (los archivos llevan delante `<id del canal>_<id del mensaje>_`, que pone tdl; al clasificar se quitan) |
| Lista exportada de cada canal | `registros/exportaciones/<nombre del canal> (<id>).json`. Es solo la lista de lo que hay en el canal, no los archivos. Se puede borrar sin riesgo; si no existe, «Descargar» la crea |
| Lista de lo que se está descargando ahora | `registros/lista_de_descarga_actual.json` (la lista del canal ya filtrada por tipo y límite) |
| Registro de cada clasificación, para deshacer | `registros/movimientos_<fecha>.json` |
| Lanzador del inicio de sesión | `registros/tdl_consola.bat` (se genera solo) |
| Diario del programa | `descargador.log`, `.log.1` y `.log.2` en la carpeta principal: las tres últimas tandas, de 2 MB cada una |
| Biblioteca clasificada | `biblioteca/` |

En Descarga hay dos botones para abrir la carpeta de la descarga y la de listas exportadas. «Exportar» solo hace falta para actualizar la lista cuando el canal ha subido archivos nuevos; «Descargar» exporta por su cuenta si todavía no hay lista de ese canal.

## Descargas largas

- **El equipo no se suspende** mientras dura la descarga, y se libera al terminar, pausar o fallar.
- **Espacio en disco.** Antes de empezar, el programa dice cuánto espacio libre hay. Tras una descarga de prueba recuerda el tamaño medio por archivo de ese tipo de contenido y, en las siguientes, calcula cuánto ocupará todo; si no parece caber, pregunta antes de empezar. Si durante la descarga quedan menos de 2 GB libres, la **pausa sola** para no llenar el disco.
- **Cerrar el programa.** Si hay una descarga en marcha, pregunta antes de cerrar; si dices que sí, detiene tdl del todo, para que no quede descargando sin ventana. Lo que ya está terminado no se pierde; los archivos que se estaban bajando en ese momento empiezan de nuevo al reanudar. Lo más limpio es pulsar **Pausar**, esperar a que diga «Descarga en pausa» y entonces cerrar.
- **Reanudar.** Basta con volver a pulsar «Descargar». Al preparar la lista se quitan los archivos que ya están en la carpeta (se reconocen por el `<idCanal>_<idMensaje>_` que pone tdl), así que tdl solo recibe lo que falta. Aun así, al reanudar tdl puede tardar hasta unos 12 minutos en empezar a bajar (en un equipo real se midieron 10 y 12 minutos, frente a 2 segundos al arrancar de cero): es normal, no pulses Pausar mientras tanto, porque reinicias la espera. Si encuentra un tdl de una sesión anterior que se quedó funcionando, te ofrece detenerlo antes de empezar, porque dos a la vez se estorban.
- **Reintentos.** Si tdl se corta (por ejemplo, por una caída de red), espera 30 segundos y reintenta hasta 3 veces seguidas; el contador se pone a cero cada vez que hay avance. Si lo pausas tú, no reintenta.
- **Avisos.** Al terminar suena el sonido del sistema de éxito y el programa lo dice por voz; si falla del todo, suena el de error. Control+E también dice el espacio libre.

## Velocidad

Una caché no acelera nada: el límite lo pone Telegram, que reparte la velocidad por conexión y por servidor. Lo que sí ayuda es abrir **más conexiones a la vez**, y la pestaña Descarga lo permite:

- **Hilos por archivo** (`-t` de tdl, 4 por defecto) y **Archivos a la vez** (`-l`, 2 por defecto). Súbelos poco a poco, por ejemplo 8 y 4. El programa sube a la par el número de conexiones con Telegram (`--pool`), porque si no los hilos extra no servirían de nada.
- **Sesión de exportación** (`--takeout`): Telegram aplica límites de espera más laxos a las exportaciones de datos. Puede pedirte permiso desde tu aplicación de Telegram, así que está desmarcada por defecto.
- Con **Control+E** el programa dice cuántos archivos van, cuántos descarga tdl ahora en paralelo, en qué porcentaje y a qué **velocidad total** (la que mide el propio tdl), así que puedes comparar configuraciones. También calcula, de forma orientativa, cuánto falta por bajar y cuánto tardará (con el tamaño medio de lo ya descargado y la velocidad actual), y avisa si no te cabría en el disco. Si empiezas a ver esperas o errores `FLOOD_WAIT` en el registro, baja los valores: Telegram te está frenando. En una prueba real, 8 archivos a la vez dieron 1,5 MB/s en total, peor que los 2 a la vez (de 2 a 4 MB/s): parece que Telegram limita la velocidad por cuenta, y subir el paralelismo solo añade riesgo, porque al pausar o cortarse se pierde lo que cada archivo llevaba a medias. Lo prudente es 2 o 3 archivos a la vez con 4 hilos.

Los valores se recuerdan entre sesiones. Una cuenta Premium de Telegram tiene límites de velocidad más altos, pero eso no se puede cambiar desde aquí.

## Clasificación

La pestaña Clasificar ordena lo descargado en una biblioteca pensada para navegar con lector de pantalla. Siempre enseña una **vista previa** antes de mover nada, lista aparte lo que no sabe clasificar y guarda un registro para **deshacer** la última clasificación.

Con el conjunto «Cómics» el árbol queda así:

```
biblioteca/Cómics/<categoría>/<inicial>/<serie>/<archivo>
biblioteca/Cómics/Marvel/T/Thor/Thor 1.cbr
biblioteca/Cómics/Manga/T/Tomodachi Game/Tomodachi Game Tomos 1-14.zip
```

- Las categorías son Marvel, DC, Manga, Licencias y videojuegos, Europeo y clásico español y Otros.
- La inicial ignora artículos («El último Atlas» va en la U) y agrupa los números en «0-9».
- Una serie solo tiene carpeta propia si hay al menos dos archivos suyos, para no obligar a entrar en carpetas de un solo elemento. Las variantes con tildes o mayúsculas comparten carpeta.
- Con «Series y películas» el árbol es `Series/<serie>/Temporada 01/<serie> - S01E05.mkv` y `Películas/<inicial>/...`.

Los conjuntos de reglas son archivos JSON en `configuraciones/reglas/`; puedes editarlos o añadir los tuyos. Cada regla tiene `patron` (expresión regular, escrita sin tildes), `carpeta` y, opcionalmente, `nombre_nuevo` y `agrupar_series`. Las plantillas admiten los grupos con nombre del patrón y `{serie}`, `{inicial}`, `{nombre}` y `{extension}`. Más detalle en `app/motor/clasificador.py`. Si quieres reclasificar la biblioteca con otras reglas, pon la misma carpeta como origen y como biblioteca.

## Pruebas

```
python -m unittest discover -s tests -t . -v
```

## Estado

La lógica de comandos, el parseo y la clasificación están probados. La ventana y las opciones exactas de línea de comandos de tdl (todas en `app/motor/ejecutor_tdl.py`, bloque `TDL_COMANDOS`) están pendientes de probar en Windows con tdl real.
