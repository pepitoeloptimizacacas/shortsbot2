"""Libera medios de lotes publicados o de pruebas terminadas tras 48 horas."""
import json
from datetime import datetime, timedelta
from pathlib import Path


RETENCION = timedelta(days=2)
EXTENSIONES_PESADAS = {'.mp4', '.wav', '.srt', '.ass', '.png', '.jpg', '.jpeg', '.webp'}
ESTADOS_PRUEBA_COMPLETOS = {'generado', 'subido', 'publicado'}


def _fecha_lote(estado, archivo):
    try:
        return datetime.fromisoformat(estado.get('completado') or estado['creado'])
    except (KeyError, TypeError, ValueError):
        return datetime.fromtimestamp(archivo.stat().st_mtime)


def _lote_completo(estado):
    piezas = estado.get('shorts', []) + estado.get('largos', [])
    esperado = int(estado.get('cantidad', len(estado.get('shorts', [])))) + int(
        estado.get('cantidad_largos', len(estado.get('largos', []))))
    if not piezas or len(piezas) != esperado or any(pieza.get('error') for pieza in piezas):
        return False
    if estado.get('modo_prueba'):
        return all(pieza.get('estado') in ESTADOS_PRUEBA_COMPLETOS for pieza in piezas)
    # Un vídeo "generado" aún necesita el archivo para subirlo y uno "subido"
    # puede necesitar comprobaciones posteriores. En producción solo se limpia
    # cuando YouTube confirmó todos como públicos y guardó su identificador.
    return all(pieza.get('estado') == 'publicado' and pieza.get('youtube_id') for pieza in piezas)


def limpiar_lotes(raiz=Path('salida/lotes'), excluir=None, ahora=None):
    """Borra medios 48 h después de terminar; conserva estado e identificadores."""
    raiz = Path(raiz)
    ahora = ahora or datetime.now()
    borrados = []
    for archivo in raiz.glob('*/estado.json'):
        lote = archivo.parent
        if lote.name == excluir:
            continue
        try:
            estado = json.loads(archivo.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if ahora - _fecha_lote(estado, archivo) < RETENCION or not _lote_completo(estado):
            continue
        cantidad = 0
        for ruta in lote.rglob('*'):
            if ruta.is_symlink():
                continue
            if (ruta.is_file() and ruta.name != 'estado.json'
                    and ruta.resolve().is_relative_to(raiz.resolve())
                    and ruta.suffix.casefold() in EXTENSIONES_PESADAS):
                ruta.unlink()
                cantidad += 1
        if cantidad:
            borrados.append({'id_lote': estado.get('id_lote', lote.name), 'archivos': cantidad})
    return borrados


if __name__ == '__main__':
    for resultado in limpiar_lotes():
        print(f"{resultado['id_lote']}: {resultado['archivos']} archivo(s) eliminado(s).")
