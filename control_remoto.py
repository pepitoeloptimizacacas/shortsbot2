"""Recoge órdenes del panel remoto y arranca el lote diario de forma local."""
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import psutil
import requests

BASE = Path(__file__).resolve().parent
ID_VALIDO = re.compile(r"^[0-9a-f-]{16,64}$", re.I)


def _responder(config, orden_id, estado, detalle):
    requests.post(config['url'].rstrip('/') + '/api/orden/resultado',
                  json={'id': orden_id, 'estado': estado, 'detalle': detalle[:180]},
                  headers={'Authorization': 'Bearer ' + config['token']}, timeout=15).raise_for_status()


def _hay_lote_activo():
    for proceso in psutil.process_iter(['name', 'cmdline']):
        try:
            argumentos = proceso.info['cmdline'] or []
            if 'python' in (proceso.info['name'] or '').casefold() and any(Path(a).name == 'lote_diario.py' for a in argumentos):
                return True
        except (psutil.Error, OSError):
            continue
    return False


def procesar_orden(config):
    """No ejecuta texto remoto: solo admite la orden fija de iniciar el lote."""
    respuesta = requests.get(config['url'].rstrip('/') + '/api/orden/siguiente',
                             headers={'Authorization': 'Bearer ' + config['token']}, timeout=15)
    # El panel publicado puede ser una versión anterior sin control remoto.
    # En ese caso el monitor sigue enviando estado sin registrar un fallo cada 10 s.
    if respuesta.status_code == 404:
        return False
    respuesta.raise_for_status()
    orden = respuesta.json()
    if not orden:
        return False
    orden_id = str(orden.get('id', ''))
    if not ID_VALIDO.fullmatch(orden_id):
        return False
    if orden.get('tipo') != 'iniciar':
        _responder(config, orden_id, 'rechazada', 'Orden no admitida.')
        return True
    if _hay_lote_activo():
        _responder(config, orden_id, 'ocupado', 'Ya hay un lote en ejecución.')
        return True
    (BASE / 'salida/logs').mkdir(parents=True, exist_ok=True)
    registro = BASE / 'salida/logs' / f"control-remoto-{datetime.now():%Y%m%d-%H%M%S}.log"
    with registro.open('ab') as log:
        subprocess.Popen(['cmd.exe', '/c', f'call "{BASE / "iniciar_todo.cmd"}"'], cwd=BASE,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS)
    _responder(config, orden_id, 'iniciada', 'El PC ha empezado el lote diario.')
    return True
