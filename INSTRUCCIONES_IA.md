# Crear vídeos sin pasos manuales

Desde esta carpeta, en el PC del bot:

```powershell
.\crear_video.cmd
```

Genera un único vídeo largo de prueba de principio a fin: búsqueda, una sola historia desarrollada en español, voz clonada de `referencia_voz.wav`, subtítulos y montaje. Usa exclusivamente un MP4 de `fondos`. Mantiene título y música. La velocidad final es 1.08, conservando el tono y sincronizando imagen, voz y subtítulos.

No cambiar la voz por una de Windows ni el fondo por animaciones o clips descargados para acelerar una prueba. La generación puede tardar en este PC.

Buscar misterio, suspense y terror narrativo: una anomalía inquietante, pistas, tensión creciente y una revelación final. Descartar anécdotas corrientes de oficina, caramelos, recursos humanos y disputas menores. Cada largo desarrolla una sola fuente; no mezclar historias ni inventar crímenes para hacer interesante una fuente aburrida. Mantener la etiqueta de ficción cuando corresponda. La configuración se aplica a selecciones nuevas; no reescribe lotes existentes.

El comando imprime el identificador del lote. Si se interrumpe, reanudar sin duplicar:

```powershell
.\crear_video.cmd --lote IDENTIFICADOR_IMPRESO
```

Salida: `salida/lotes/IDENTIFICADOR/largo_01/video_final.mp4`. Solo anunciarlo como terminado si el comando terminó correctamente y el archivo existe. No publica ni apaga el PC.

El lanzador completo es `iniciar_todo.cmd`: arranca Ollama y el monitor, prepara las historias, genera y publica primero seis shorts y después tres largos, y apaga al confirmar todas las publicaciones. Delega en `iniciar_bot.cmd` fijando seis shorts y tres largos. Para reanudar otro día: `iniciar_todo.cmd --lote IDENTIFICADOR`. No usar ninguno de estos dos comandos para una prueba. Conservar `crear_video.cmd` para pruebas sin publicación ni apagado.
