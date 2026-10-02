"""Envía únicamente el estado público seleccionado, mediante HTTPS y token propio."""
import json
import time
import threading
import requests
import panel
from control_remoto import procesar_orden

if __name__ == '__main__':
    config = json.loads((panel.BASE / 'panel_remoto.json').read_text(encoding='utf-8'))
    if not config['url'].startswith('https://'):
        raise ValueError('El monitor remoto requiere HTTPS.')
    threading.Thread(target=panel.sensores, daemon=True).start()
    while True:
        try:
            response = requests.post(config['url'].rstrip('/') + '/api/recibir',
                                     json=panel.estado(), headers={'Authorization': 'Bearer ' + config['token']}, timeout=20)
            response.raise_for_status()
            procesar_orden(config)
        except Exception:
            print('No se pudo actualizar el panel remoto o leer una orden; se reintentará.', flush=True)
        time.sleep(10)
