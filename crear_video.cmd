@echo off
setlocal
cd /d "%~dp0"
".venv-voz\Scripts\python.exe" -c "import sys; print(sys.version)" >nul 2>nul
if errorlevel 1 (
  echo El entorno .venv-voz no funciona o falta su instalacion de Python.
  echo Reinstala Python 3.11 y recrea .venv-voz antes de generar el video.
  pause
  exit /b 1
)
".venv-voz\Scripts\python.exe" -u crear_video.py %*
exit /b %errorlevel%
