"""Revisión ligera de una prueba: vídeo, audio y guion, sin cargar un modelo visual."""
import json
import subprocess
from pathlib import Path

import requests
import soundfile as sf

from config import VELOCIDAD_VIDEO

OLLAMA_URL = 'http://127.0.0.1:11434/api/generate'
MODELO_REVISION = 'qwen3:1.7b'


def _probe(video):
    proceso = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)],
        capture_output=True, text=True, check=True, timeout=30)
    return json.loads(proceso.stdout)


def revisar(video, audio, titulo, guion):
    """Devuelve un dict breve. Ollama revisa el guion; FFmpeg/ffprobe el archivo final."""
    video, audio = Path(video), Path(audio)
    datos = _probe(video)
    streams = datos['streams']
    pista_video = next((s for s in streams if s.get('codec_type') == 'video'), None)
    pista_audio = next((s for s in streams if s.get('codec_type') == 'audio'), None)
    duracion = float(datos['format']['duration'])
    esperada = sf.info(str(audio)).duration / VELOCIDAD_VIDEO
    tecnico = {
        'video': bool(pista_video), 'audio': bool(pista_audio),
        'resolucion': f"{pista_video['width']}x{pista_video['height']}" if pista_video else None,
        'duracion_video': round(duracion, 1), 'duracion_esperada': round(esperada, 1),
        'desfase': round(abs(duracion - esperada), 1),
    }
    if not pista_video or not pista_audio or abs(duracion - esperada) > 3:
        return {'apto': False, 'tecnico': tecnico, 'motivo': 'El archivo final no coincide con el audio o le falta una pista.'}
    print('Revisión rápida: comprobando guion con Ollama pequeño...', flush=True)
    prompt = (
        'Evalúa este guion de misterio para un vídeo narrado. Busca gancho, tensión, cierre, '
        'repeticiones, frases cortadas y promesas que no cumple. Devuelve JSON estricto con '
        'apto (boolean), motivo (máximo 180 caracteres) y mejoras (lista de máximo 3 frases).\n'
        f'Título: {titulo}\nGuion:\n{guion[:7000]}'
    )
    respuesta = requests.post(OLLAMA_URL, json={
        'model': MODELO_REVISION, 'prompt': prompt, 'stream': False, 'format': 'json',
        'think': False, 'keep_alive': 0, 'options': {'num_ctx': 8192, 'num_predict': 280, 'num_thread': 2},
    }, timeout=600)
    respuesta.raise_for_status()
    editorial = json.loads(respuesta.json()['response'])
    if not isinstance(editorial.get('apto'), bool):
        raise ValueError('Ollama no devolvió una revisión válida.')
    return {'apto': editorial['apto'], 'tecnico': tecnico,
            'motivo': str(editorial.get('motivo', 'Sin motivo'))[:180],
            'mejoras': [str(x)[:180] for x in editorial.get('mejoras', [])[:3]]}
