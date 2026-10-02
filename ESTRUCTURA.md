# Carpetas del bot

- `fondos/`: vídeos de fondo usados por shorts y largos.
- `salida/lotes/`: un directorio por lote; dentro se guarda la historia, voz, subtítulos y vídeo de cada resultado.
- `salida/logs/`: registros de ejecución y errores.
- `tests/`: comprobaciones automáticas del bot.
- `monitor-web/`: código del panel web público.

Los archivos de la raíz son los scripts que usa el bot. Usa `crear_video.cmd` para una prueba sin publicación y `iniciar_todo.cmd` para el lote completo.

No borrar `referencia_voz.wav`, `reddit_session.json`, `client_secret.json`, `youtube_token.json`, `youtube_canal.json`, `panel_acceso.json` ni `panel_remoto.json`: contienen la voz configurada, sesiones o la configuración de servicios.
