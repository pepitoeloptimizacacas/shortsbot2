"""Retira JSON de pruebas antiguas, conservando una copia recuperable."""
import json
from datetime import datetime
from pathlib import Path
from estado_bot import bloqueo

def main():
    base = Path(__file__).resolve().parent
    raiz = (base / 'salida/lotes').resolve()
    copia = base / 'salida/respaldo_json_pruebas' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    total = 0
    with bloqueo(base / 'salida/bot.lock'):
        for archivo in raiz.glob('*/estado.json'):
            estado = json.loads(archivo.read_text(encoding='utf-8'))
            piezas = estado.get('shorts', []) + estado.get('largos', [])
            prueba = estado.get('modo_prueba') or (estado.get('cantidad') == 0 and archivo.parent.name.startswith(('video-', 'prueba')))
            if not prueba or any(p.get('youtube_id') or p.get('estado') in ('subido', 'publicado') for p in piezas):
                continue
            for ruta in list(archivo.parent.rglob('historia.json')) + [archivo]:
                if ruta.is_symlink() or not ruta.resolve().is_relative_to(raiz):
                    raise RuntimeError('Ruta fuera de la carpeta de lotes.')
                destino = copia / ruta.relative_to(raiz)
                destino.parent.mkdir(parents=True, exist_ok=True)
                ruta.replace(destino)
                total += 1
    print(f'{total} JSON retirados. Copia recuperable: {copia}')

if __name__ == '__main__':
    main()
