@echo off
cd /d "%~dp0"
".venv-voz\Scripts\python.exe" -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
  echo El entorno .venv-voz no funciona o falta su instalacion de Python.
  echo Reinstala Python 3.11 y recrea .venv-voz antes de iniciar el bot.
  pause
  exit /b 1
)
".venv-voz\Scripts\python.exe" iniciar_ollama.py
if errorlevel 1 (
  echo No se ha podido preparar Ollama. El bot no se iniciara.
  pause
  exit /b 1
)
".venv-voz\Scripts\python.exe" lanzar_monitor.py
".venv-voz\Scripts\python.exe" lote_diario.py --publicar --apagar %*
if errorlevel 1 (
  echo El bot se ha detenido. El PC NO se apagara. Lee el error anterior.
  pause
  exit /b 1
)
