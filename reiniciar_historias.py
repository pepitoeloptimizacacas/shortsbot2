"""Reinicia un lote y retira JSON de pruebas con copia recuperable."""
import argparse
import json
from datetime import datetime
from pathlib import Path

from estado_bot import bloqueo, guardar_json

BASE = Path(__file__).resolve().parent


def reiniciar(lote):
    raiz = (BASE / 'salida/lotes').resolve()
    actual = (raiz / lote).resolve()
    if actual.parent != raiz or actual.is_symlink() or not actual.is_dir():
        raise ValueError('El lote debe ser una carpeta existente dentro de salida/lotes.')
    respaldo = BASE / 'salida/respaldo_reinicio' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    with bloqueo(BASE / 'salida/bot.lock'):
        # Preservar la prevención de duplicados antes de retirar el estado.
        usados_path = BASE / 'historias_usadas.json'
        usados = set(json.loads(usados_path.read_text(encoding='utf-8'))) if usados_path.exists() else set()
        datos = json.loads((actual / 'estado.json').read_text(encoding='utf-8'))
        for pieza in datos.get('shorts', []) + datos.get('largos', []):
            if pieza.get('youtube_id') or pieza.get('estado') in ('subido', 'publicado'):
                historia = pieza['historia']
                usados.update(historia.get('ids', [historia['id']]))
        guardar_json(usados_path, sorted(usados))
        respaldo.mkdir(parents=True)
        # También apartar los medios evita mezclar el nuevo lote con vídeos viejos.
        actual.rename(respaldo / actual.name)
        retirados = 0
        for estado in raiz.glob('*/estado.json'):
            datos = json.loads(estado.read_text(encoding='utf-8'))
            piezas = datos.get('shorts', []) + datos.get('largos', [])
            if not datos.get('modo_prueba') or any(p.get('youtube_id') for p in piezas):
                continue
            for ruta in list(estado.parent.rglob('historia.json')) + [estado]:
                if ruta.is_symlink() or not ruta.resolve().is_relative_to(raiz):
                    raise ValueError('Ruta de prueba fuera de salida/lotes.')
                destino = respaldo / ruta.relative_to(raiz)
                destino.parent.mkdir(parents=True, exist_ok=True)
                ruta.rename(destino)
                retirados += 1
    print(f'Lote {lote} reiniciado; {retirados} JSON de pruebas retirados.')
    print(f'Copia recuperable: {respaldo}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lote', required=True)
    reiniciar(parser.parse_args().lote)
