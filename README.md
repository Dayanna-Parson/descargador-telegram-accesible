# Descargador de Telegram Accesible

Aplicación de escritorio para Windows, accesible con lectores de pantalla, que descarga de forma masiva los archivos de un canal de Telegram (vídeo, cómics, libros, complementos...) y los clasifica con reglas configurables. Por debajo usa [tdl](https://github.com/iyear/tdl).

Desarrolladora: Dayanna Parson (TifloTutos · tiflotutos.com)

## Puesta en marcha

1. Instala Python 3.12+ y las dependencias: `pip install -r requisitos.txt`.
2. Abre el programa con doble clic en `INICIAR_DESCARGADOR.bat` (o con `python iniciar_descargador.py`). Si faltan dependencias, el `.bat` te lo dice.
3. En la pestaña Conexión, pulsa «Instalar o actualizar tdl»: consulta cuál es la última versión publicada, la descarga y, **antes de sustituir la que tienes, comprueba que entiende todas las órdenes que usa este programa** (pasa cada una con `--help`). Si la nueva no es compatible, conserva la actual y te lo dice. Si no hay internet o no se puede consultar, usa la última versión conocida como buena (`INSTALADOR_TDL_CONSTANTES` en `app/motor/instalador_tdl.py`), y deja `tdl.exe` en `bin/`. También puedes copiarlo a mano desde las *releases* de tdl.
4. En la misma pestaña, inicia sesión: se abre una ventana de consola donde tdl te hace las preguntas (teléfono con prefijo y código de Telegram). Todo lo que diga tdl queda además en `descargador.log`. En Canal, actualiza la lista y elige el canal. En Descarga, exporta la lista, elige tipo de contenido y carpeta, y descarga.

Si la descarga se corta o la pausas, vuelve a pulsar «Descargar / reanudar»: tdl continúa donde se quedó.

## Al abrir el programa

Si la sesión de Telegram ha caducado (`not authorized. please login first`), el programa lo dice con claridad: ve a Conexión y pulsa «Iniciar sesión con código». Para clasificar o mover archivos no hace falta sesión.

La lista de canales se guarda y aparece al instante, y se actualiza sola en segundo plano (si falla, por ejemplo porque hay otro tdl en marcha, se mantiene la última guardada). El programa recuerda también el último canal elegido, el tipo de contenido y la carpeta de destino. «Actualizar lista de canales» solo hace falta cuando te unes a un canal nuevo y quieres verlo ya.

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

**Adónde van los archivos.** Al clasificar se *mueven* a la «Carpeta de la biblioteca», que por defecto es la carpeta `biblioteca` dentro del propio programa, en el mismo disco que él. La confirmación y el aviso final dicen siempre la carpeta de destino, y el botón «Abrir la carpeta de la biblioteca» la abre en el Explorador. Si quieres que se guarde en otro disco, cámbiala antes de aplicar.

Los conjuntos de reglas son archivos JSON en `configuraciones/reglas/`; puedes editarlos o añadir los tuyos. Cada regla tiene `patron` (expresión regular, escrita sin tildes), `carpeta` y, opcionalmente, `nombre_nuevo` y `agrupar_series`. Las plantillas admiten los grupos con nombre del patrón y `{serie}`, `{inicial}`, `{nombre}` y `{extension}`. Más detalle en `app/motor/clasificador.py`. Si quieres reclasificar la biblioteca con otras reglas, pon la misma carpeta como origen y como biblioteca.

### Reglas de Shin Chan

El conjunto «Shin Chan» (`configuraciones/reglas/Shin Chan.json`) está hecho con los datos reales de un canal concreto. Los **pies de los mensajes** del canal (`#Shinchan2T #Cap33 #Cap33A => título ...`) dicen la temporada, el número y los títulos de cada vídeo; se leen de la exportación del canal (`registros/exportaciones`, hay que exportar con la versión actual de tdl) y de los registros de clasificaciones anteriores, para encontrar el pie aunque el archivo ya se haya renombrado.

- Episodios: `Series/Shin Chan/Temporada 02/Shin Chan - Temporada 02 - Episodio 033 - Hacemos la comida, Hago volar cometas.mp4`. Los títulos son los de cada segmento, recortados a unos 46 caracteres sin partir ninguno. Si un vídeo junta dos capítulos seguidos, dice `Episodio 959 a 960`.
- Especiales: dentro de la temporada a la que pertenecen, como en el canal, donde cierran cada temporada: `Shin Chan - Temporada 03 - Especial 007 - Va a nacer un bebé, ....mp4`. Salen después de los episodios.
- Películas: `Películas/Shin Chan/` con el número que les da el canal (`01.` a `22.`; la 20 no está en el canal). Las dos últimas, sin número en el canal, quedan al final.
- Si dos archivos acaban con el mismo nombre, se conservan los dos: el segundo como `... (versión 2).mp4`.
- Un vídeo cuyo nombre es solo un número de Telegram y que no tiene pie va a `Series/Shin Chan/Sin identificar/`; deducirlo por su posición en el canal no es fiable.
- La tabla de temporadas (1 a 27) sale de los pies, no de suposiciones. Una temporada que no esté en la tabla va a `Sin temporada/Episodios N a M`.
- `Imágenes/Shin Chan/` para las portadas.
- Para ordenar de una vez lo ya clasificado: origen = `Series` (y luego `Películas`), biblioteca = la raíz de la biblioteca. Se puede repetir sin miedo: lo que ya está bien no se mueve.

Opciones de regla que lo hacen posible: `patron_pie` (busca en el pie del mensaje en vez de en el nombre), `pie_por` (usa el pie del capítulo o especial con ese número) y `si_se_repite`, además de `temporadas_desde` (lista `[episodio_inicial, temporada]`) y `bloque` (tamaño de los bloques de episodios sin temporada); ambas dan la variable `{ubicacion}`.

### Mover la biblioteca a otro disco

- **Lo más cómodo:** en Clasificar, pon como «Carpeta de la biblioteca» una carpeta del disco externo y aplica. Cada archivo se copia al destino y se borra del origen, uno a uno, así que el espacio se va liberando. El programa comprueba antes que en el destino hay sitio, avisa de que será lento, mantiene el equipo despierto, dice cómo va y guarda el registro cada 25 archivos, por si se corta la luz a mitad.
- **Cada copia se verifica.** Entre discos, un archivo solo se borra del origen después de comprobar que la copia tiene el mismo tamaño; si no coincide, se borra la copia y el original queda intacto. Que sea rápido no es mala señal si el disco externo es un SSD o va por USB 3. Para comprobarlo al terminar, compara el número de archivos y los GB de la carpeta de destino con los del origen antes de mover.
- **Si ya está clasificada** y la mueves tú con el Explorador (mejor copiar, comprobar que está todo y después borrar el original), después indica la nueva carpeta como biblioteca.
- **Mover la carpeta entera sin clasificar.** También vale cortar la carpeta del canal y pegarla en el disco externo tal cual. Al abrir el programa (y al terminar cada descarga) se apunta lo que hay en la carpeta de descargas, así que después «Descargar» no vuelve a pedirlo. Abre el programa una vez antes de moverla. Para ordenarla después, en Clasificar pon como origen la carpeta del disco externo y como biblioteca otra carpeta del mismo disco: dentro de un mismo disco mover es instantáneo y no hace falta espacio extra.
- **Lo ya descargado no se vuelve a bajar.** Al clasificar se quita el prefijo `<idCanal>_<idMensaje>_` que tdl pone a los archivos, y sin él no habría forma de saber qué mensajes están bajados. Por eso el programa apunta cada mensaje en `configuraciones/descargados.json` antes de mover, y al arrancar lo rehace a partir de las clasificaciones anteriores (`registros/movimientos_*.json`). Gracias a eso se puede vaciar o mover `descargas` sin que «Descargar» vuelva a pedir todo.

## Pruebas

```
python -m unittest discover -s tests -t . -v
```

## Estado

La lógica de comandos, el parseo y la clasificación están probados. La ventana y las opciones exactas de línea de comandos de tdl (todas en `app/motor/ejecutor_tdl.py`, bloque `TDL_COMANDOS`) están pendientes de probar en Windows con tdl real.
