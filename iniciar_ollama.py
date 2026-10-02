"""Comprueba el modelo local y arranca Ollama si no está disponible."""
from pathlib import Path
import shutil
import subprocess
import time
import requests
from ollama_selector import MODEL


def preparar():
    def modelos():
        r = requests.get('http://127.0.0.1:11434/api/tags', timeout=5)
        r.raise_for_status()
        return [m['name'] for m in r.json().get('models', [])]
    try:
        disponibles = modelos()
    except requests.ConnectionError:
        exe = shutil.which('ollama')
        if not exe:
            raise RuntimeError('No se encuentra Ollama instalado.')
        carpeta = Path(__file__).resolve().parent / 'salida/logs'
        carpeta.mkdir(parents=True, exist_ok=True)
        with (carpeta / 'ollama-arranque.log').open('ab') as log:
            subprocess.Popen([exe, 'serve'], stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
        for _ in range(15):
            time.sleep(1)
            try:
                disponibles = modelos()
                break
            except requests.ConnectionError:
                continue
        else:
            raise RuntimeError('Ollama no ha arrancado; consulta salida/logs/ollama-arranque.log.')
    if MODEL not in disponibles:
        raise RuntimeError(f'Falta el modelo {MODEL}. Instálalo con ollama pull {MODEL}.')
    print('Ollama listo.', flush=True)


if __name__ == '__main__':
    try:
        preparar()
    except Exception as exc:
        print(f'ERROR: {exc}', flush=True)
        raise SystemExit(1)
