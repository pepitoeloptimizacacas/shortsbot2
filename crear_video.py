"""Prueba un largo nuevo desde Reddit, sin publicar, apagar ni marcarlo como usado."""
import argparse
from pathlib import Path
from uuid import uuid4
from datetime import datetime
from iniciar_ollama import preparar
from lote_diario import ejecutar


VOCES = {
    '1': ('hombre', 'referencia_voz.wav'),
    '2': ('mujer', 'referencia2.wav'),
}


def elegir_voz():
    while True:
        opcion = input('Elige voz: [1] Hombre  [2] Mujer: ').strip()
        if opcion in VOCES:
            nombre, archivo = VOCES[opcion]
            print(f'Voz seleccionada: {nombre}.', flush=True)
            return archivo
        print('Escribe 1 para hombre o 2 para mujer.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lote', default='prueba',
                        help='Prefijo opcional. Siempre crea una prueba nueva; no reanuda lotes antiguos.')
    args = parser.parse_args()
    if not args.lote or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for c in args.lote):
        parser.error('Nombre de lote inválido.')
    voz = elegir_voz()
    if not (Path(__file__).resolve().parent / voz).is_file():
        parser.error(f'Falta el archivo de referencia: {voz}')
    args.lote = f'{args.lote}-{datetime.now():%Y%m%d-%H%M%S}-{uuid4().hex[:8]}'
    preparar()
    print(f'Lote de prueba: {args.lote}. Buscando una historia nueva en Reddit...', flush=True)
    ejecutar(argparse.Namespace(lote=args.lote, cantidad=0, largos=1, publicar=False,
                               apagar=False, modo_prueba=True, voz_referencia=voz,
                               revisar=True))
    print(f'Vídeo listo en salida/lotes/{args.lote}/largo_01/video_final.mp4', flush=True)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f'No se pudo completar la prueba: {exc}', flush=True)
        raise SystemExit(1)
