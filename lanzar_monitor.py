"""Arranca el envío del panel en segundo plano, una sola vez."""
import subprocess
from pathlib import Path
import sys
import psutil

BASE = Path(__file__).resolve().parent
if __name__ == '__main__' and (BASE / 'panel_remoto.json').exists():
    target = str(BASE / 'publicar_estado.py')
    running = False
    for p in psutil.process_iter(['cmdline']):
        if target in (p.info.get('cmdline') or []):
            running = True
            break
    if not running:
        (BASE / 'salida/logs').mkdir(parents=True, exist_ok=True)
        with (BASE / 'salida/logs/monitor.log').open('ab') as log:
            subprocess.Popen([sys.executable, '-u', target], cwd=BASE,
                             stdout=log, stderr=log, stdin=subprocess.DEVNULL,
                             creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
        print('Monitor remoto iniciado.')
    else:
        print('El monitor remoto ya está en marcha.')
