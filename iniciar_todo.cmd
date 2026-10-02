@echo off
setlocal
cd /d "%~dp0"
title ShortsBot - 6 shorts y 3 videos largos
echo Se iniciara Ollama y se prepararan las historias.
echo Se generaran y publicaran primero 6 shorts y despues 3 videos largos.
echo El PC se apagara solo al confirmar las 9 publicaciones.
echo Si hay un fallo, el progreso queda guardado y el PC permanece encendido.
echo.
call "%~dp0iniciar_bot.cmd" %* --cantidad 6 --largos 3
exit /b %errorlevel%
