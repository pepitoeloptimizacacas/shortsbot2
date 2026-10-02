# ShortsBot

## Todo automático: seis shorts y tres largos

Haz doble clic en `iniciar_todo.cmd` o ejecuta `.\iniciar_todo.cmd`. Arranca Ollama, inicia el monitor y prepara las historias; después genera y publica los seis shorts, seguidos de los tres largos. Apaga el PC solo cuando las nueve publicaciones estén confirmadas. Si algo falla, conserva el progreso y no apaga el equipo.

El lote se identifica por la fecha. Ejecutar el mismo día reanuda ese lote; para continuar otro día usa `.\iniciar_todo.cmd --lote FECHA_DEL_LOTE`. Necesita conexión a Internet y las sesiones de Reddit y YouTube válidas. `crear_video.cmd` se conserva para generar un único largo de prueba sin publicar ni apagar.

## Crear un vídeo largo con un comando

Ejecuta `.\crear_video.cmd`. Busca una historia, prepara el guion, genera la voz clonada, los subtítulos y el montaje con un vídeo de `fondos`. No publica ni apaga el PC. El resultado queda en `salida/lotes/prueba-FECHA-HORA-IDENTIFICADOR/largo_01/video_final.mp4`. Cada ejecución crea una prueba nueva, para no sobrescribir resultados anteriores. La velocidad se ajusta en `VELOCIDAD_VIDEO` de `config.py`; por defecto, 1.08.

## Historias y estilo

El buscador consulta relatos de nosleep, shortscarystories y creepypasta: misterio, suspense y terror narrativo. Prioriza señales de sucesos inquietantes, secretos, investigación y revelaciones; excluye episodios numerados y publicaciones marcadas para adultos. La IA exige gancho, conflicto, claridad, desenlace, misterio, tensión y revelación con al menos 4/5 en cada criterio. Rechaza anécdotas cotidianas de oficina, recursos humanos y disputas menores. Si no encuentra una historia adecuada, informa del fallo; no vuelve a las fuentes anteriores. Este filtro no garantiza retención ni visitas.

Cada largo desarrolla una sola historia, con pistas y tensión creciente, reservando la revelación para el final. No inventa crímenes para convertir una anécdota corriente en misterio. Los relatos de estas comunidades se etiquetan como ficción en la descripción pública.

Se limpian etiquetas como `r/tifu`, `u/usuario`, `TIFU`, `EDIT` y enlaces antes de narrar. Las fuentes se conservan en los JSON locales; no se incluyen en la descripción pública de las nuevas subidas.

Shorts y largos usan exclusivamente los vídeos MP4 de la carpeta fondos, con un inicio aleatorio. El lote alterna de forma estable `referencia_voz.wav` y `referencia2.wav` (hombre, mujer, hombre, mujer...) y acelera el resultado un 8 % sin cambiar el tono; los subtítulos se aceleran junto con la imagen para mantener la sincronización. La música instrumental se sintetiza localmente, sin grabaciones descargadas, y baja automáticamente bajo la voz. Cada carpeta guarda `musica_original.wav`; el fondo se lee directamente de fondos. Los vídeos largos generan `miniatura.jpg` a 1280×720 con la caja de comentario grande y el publicador la asigna mediante la API de YouTube. Los vídeos ya generados o publicados no se rehacen automáticamente. Reinicia el bot para que un proceso ya abierto cargue los cambios.

## Monitor por Internet

El monitor remoto usa una contraseña y recibe solo CPU, RAM, espacio libre, sensores disponibles y el estado de los shorts. No recibe credenciales de YouTube ni los guiones completos. Al ejecutar `iniciar_bot.cmd` también se inicia el envío del estado. Para iniciarlo por separado, ejecuta `iniciar_monitor.cmd`.

El PC debe permanecer encendido y conectado. Si deja de enviar datos durante 45 segundos, el panel avisa y conserva la última lectura. La temperatura solo aparece si LibreHardwareMonitor u OpenHardwareMonitor están abiertos y exponen sensores compatibles; no es una temperatura estimada.

`panel_remoto.json` y `panel_acceso.json` contienen secretos del monitor; no los compartas.

Genera seis shorts y tres vídeos largos por lote diario, los publica en YouTube y apaga Windows tras confirmar las nueve publicaciones. Si falla uno, guarda el progreso y NO apaga el PC.

Cada largo desarrolla UNA historia extensa, en español y horizontal 1920×1080, con voz y subtítulos. La IA escribe doce tramos de 230–300 palabras, conservando los hechos y el desenlace de una sola fuente, sin relleno ni relatos mezclados. Se validan entre 15 y 30 minutos. Se necesitan nueve historias nuevas para completar el lote: seis para shorts y tres fuentes extensas para largos. Se generan secuencialmente. No se garantiza terminar nueve vídeos en 24 horas: depende del PC y los servicios.

Para generar solo shorts, usa `iniciar_bot.cmd --largos 0` con un lote nuevo. Al reanudar conserva la cantidad de largos elegida. Los lotes antiguos sin configuración de largos pueden ampliarse a tres. El panel web actual sigue mostrando los shorts; el progreso de los largos queda en `salida/lotes/FECHA/estado.json` y en la consola.

## Conectar YouTube (una vez)

1. Abre https://console.cloud.google.com/ y crea o elige un proyecto.
2. Habilita **YouTube Data API v3** en la biblioteca de APIs.
3. Configura Google Auth Platform / pantalla de consentimiento. Si está en pruebas, añade tu cuenta de Google como usuario de prueba.
4. Crea un cliente OAuth de tipo **Aplicación de escritorio**. Descarga su JSON y guárdalo en esta carpeta como `client_secret.json`.
5. Ejecuta `conectar_youtube.cmd`. En el navegador inicia sesión y autoriza el canal donde quieres publicar. Comprueba el nombre que aparece en la consola.

Las dependencias de YouTube se instalan con `.\.venv-voz\Scripts\python.exe -m pip install -r requirements-youtube.txt` (ya instaladas durante la preparación).

Google puede restringir las subidas de proyectos API sin auditar a **privadas**, aunque se soliciten públicas. En ese caso el bot conserva el ID, informa del problema y no apaga el PC; repetir el comando no duplica el vídeo. Consulta https://developers.google.com/youtube/v3/docs/videos/insert . La autorización de una aplicación en modo de pruebas también puede caducar y requerir reconexión.

## Uso diario

El lanzador comprueba Ollama y lo inicia si no está disponible. Si falla la selección de nuevas historias, el lote procesa igualmente los vídeos ya preparados y conserva el error para reanudar. No apaga el PC hasta completar todo el lote. La narración guarda fragmentos de audio reutilizables para no empezar desde cero después de una interrupción.

Haz doble clic en `iniciar_bot.cmd`, o ejecuta desde esta carpeta:

```powershell
.\iniciar_bot.cmd
```

Se publican en cuanto se termina cada vídeo, sin horarios programados. Debes iniciar el bot cada día con el PC encendido; no se programa el encendido automático. Por defecto se usa un lote por fecha. Ejecutar otra vez el mismo día reanuda ese lote sin duplicar publicaciones. El apagado tiene una cuenta atrás de 60 segundos; se cancela con `shutdown /a`.

Para reanudar un lote anterior, especifica su nombre:

```powershell
.\iniciar_bot.cmd --lote 2026-09-20
```

Para generar sin publicar ni apagar:

```powershell
.\.venv-voz\Scripts\python.exe lote_diario.py
```

Para publicar sin apagar:

```powershell
.\.venv-voz\Scripts\python.exe lote_diario.py --publicar
```

## Archivos y recuperación

- `salida/lotes/FECHA/estado.json`: progreso, errores e identificadores de YouTube.
- Cada `short_XX` guarda historia, fuente, narración, subtítulos, tarjeta y vídeo.
- Un fallo de red durante la subida se reintenta desde los bytes confirmados por YouTube.
- Si la sesión de subida caduca o queda incierto el inicio, se detiene ese short para evitar duplicados. Revisa YouTube Studio y el estado antes de intervenir; no borres el registro para intentar solucionarlo.
- No ejecutes a la vez los scripts individuales y el lote: los individuales son el flujo antiguo y no utilizan el bloqueo del lote.

Requisitos: entorno `.venv-voz` existente con Python 3.11, Chatterbox y Whisper; FFmpeg y FFprobe en PATH; Ollama disponible con `qwen3:4b`; sesión de Reddit creada con `playwright_setup.py`; Chrome instalado; `referencia_voz.wav` y al menos un MP4 en `fondos`. El idioma actual de `config.py` es español. Los shorts se validan entre 10 y 180 segundos; el objetivo de su guion sigue siendo 60–90.

No compartas `reddit_session.json`, `youtube_token.json`, `client_secret.json` ni los registros de subida: contienen acceso o datos de sesión. `.gitignore` los excluye.

## Verificación

```powershell
.\.venv-voz\Scripts\python.exe -m unittest discover -s tests -v
```

Las pruebas simulan YouTube y el apagado; no publican ni apagan el PC. La conexión y publicación reales requieren autorizar tu cuenta.
