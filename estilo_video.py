"""Montaje con los MP4 de fondos, voz clonada, subtítulos y música suave."""
from pathlib import Path
import colorsys
import math
import random
import subprocess
import numpy as np
import soundfile as sf
from PIL import Image, ImageDraw
from config import VELOCIDAD_VIDEO


def crear_fondo(destino, horizontal=False, variante=0):
    destino = Path(destino)
    w, h = (1280, 720) if horizontal else (720, 1280)
    comando = ['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
        '-s', f'{w}x{h}', '-r', '24', '-i', '-', '-an', '-c:v', 'libx264',
        '-preset', 'fast', '-pix_fmt', 'yuv420p', str(destino)]
    with subprocess.Popen(comando, stdin=subprocess.PIPE, stderr=subprocess.PIPE) as proceso:
        try:
            for frame in range(288):
                t = frame / 288 * 2 * math.pi
                img = Image.new('RGB', (w, h), (12, 15, 28))
                draw = ImageDraw.Draw(img)
                # Ondas de péndulos: cada esfera completa ciclos enteros para un bucle continuo.
                for i in range(28):
                    color = tuple(int(c * 255) for c in colorsys.hsv_to_rgb((i / 38 + variante / 7) % 1, .68, .95))
                    for cola in range(7, -1, -1):
                        fase = t - cola * .012
                        x = w / 2 + math.sin(fase * (2 + i % 7) + i * .22) * w * .36
                        y = h * .08 + i / 27 * h * .84
                        if variante % 2:
                            x = w / 2 + math.cos(fase * 2 + i * .32) * w * (.12 + i / 100)
                            y = h / 2 + math.sin(fase * 2 + i * .32) * h * (.12 + i / 100)
                        r = min(w, h) * .022
                        tono = tuple(int(c * (1 - cola / 9)) for c in color)
                        draw.ellipse((x-r, y-r, x+r, y+r), fill=tono)
                proceso.stdin.write(img.tobytes())
            proceso.stdin.close()
            error = proceso.stderr.read().decode(errors='replace')
            if proceso.wait(timeout=120):
                raise RuntimeError(error[-1500:])
        except Exception:
            proceso.kill()
            raise
    return destino


def crear_musica(destino, semilla=0):
    rng = random.Random(semilla)
    sr = 24000
    duracion = 24
    audio = np.zeros(sr * duracion, dtype=np.float32)
    notas = [48, 55, 60, 62, 64, 67, 69]
    for paso in range(48):
        nota = rng.choice(notas)
        t = np.arange(int(sr * 1.5)) / sr
        frecuencia = 440 * 2 ** ((nota - 69) / 12)
        sonido = (np.sin(2*np.pi*frecuencia*t) + .2*np.sin(4*np.pi*frecuencia*t))
        sonido *= (1 - np.exp(-t * 35)) * np.exp(-t * 3) * .12
        inicio = int(paso * .5 * sr)
        n = min(len(sonido), len(audio) - inicio)
        audio[inicio:inicio+n] += sonido[:n]
    fade = np.linspace(0, 1, sr // 4)
    audio[:len(fade)] *= fade
    audio[-len(fade):] *= fade[::-1]
    sf.write(str(destino), audio, sr)
    return Path(destino)


def montar_satisfactorio(audio, ass, titulo, salida, horizontal=False):
    print('Montando video con fondo original y música...', flush=True)
    from title_card import crear_tarjeta_titulo, crear_miniatura_video
    carpeta = Path(salida).parent
    carpeta.mkdir(parents=True, exist_ok=True)
    semilla = random.randrange(1000000)
    clips = list((Path(__file__).resolve().parent / 'fondos').glob('*.mp4'))
    if not clips:
        raise FileNotFoundError('Pon un vídeo MP4 en la carpeta fondos antes de generar.')
    fondo = random.choice(clips)
    print(f'Usando vídeo de fondos: {fondo.name}', flush=True)
    musica = crear_musica(carpeta / 'musica_original.wav', semilla)
    if not 0.5 <= VELOCIDAD_VIDEO <= 2:
        raise ValueError('VELOCIDAD_VIDEO debe estar entre 0.5 y 2.')
    duracion_original = sf.info(str(audio)).duration
    duracion = duracion_original / VELOCIDAD_VIDEO
    probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(fondo)], capture_output=True,
        text=True, check=True, timeout=30)
    inicio = random.uniform(0, max(0, float(probe.stdout.strip()) - duracion_original - 5))
    w, h = (1920, 1080) if horizontal else (1080, 1920)
    ruta = Path(ass).as_posix().replace(':', r'\:').replace("'", r"'\''")
    entradas = ['-stream_loop', '-1', '-ss', str(inicio), '-i', str(fondo), '-i', str(audio),
                '-stream_loop', '-1', '-i', str(musica)]
    filtro = f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,ass='{ruta}'[sub];"
    if horizontal:
        tarjeta = crear_tarjeta_titulo(
            titulo, str(carpeta / 'titulo.png'), ancho=w, alto=h,
        )
        crear_miniatura_video(titulo, str(carpeta / 'miniatura.jpg'))
    else:
        tarjeta = crear_tarjeta_titulo(titulo, str(carpeta / 'titulo.png'))
    entradas += ['-loop', '1', '-i', str(tarjeta)]
    filtro += "[sub][3:v]overlay=0:0:enable='lt(t,3)'[vnormal];"
    filtro += f'[vnormal]setpts=PTS/{VELOCIDAD_VIDEO}[v];'
    filtro += ('[1:a]asplit=2[voz][control];[2:a]volume=0.22[musica];'
               '[musica][control]sidechaincompress=threshold=0.02:ratio=8:attack=20:release=500[duck];'
               '[voz][duck]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[anormal];')
    filtro += f'[anormal]atempo={VELOCIDAD_VIDEO}[a]'
    resultado = subprocess.run(['ffmpeg', '-v', 'error', '-y', *entradas, '-filter_complex', filtro,
        '-map', '[v]', '-map', '[a]', '-t', str(duracion), '-c:v', 'libx264', '-preset', 'fast',
        '-crf', '21', '-threads', '2', '-c:a', 'aac', '-r', '30', '-pix_fmt', 'yuv420p',
        '-movflags', '+faststart', str(salida)], capture_output=True, text=True, timeout=14400)
    if resultado.returncode:
        raise RuntimeError(resultado.stderr[-2000:])
    return str(salida)
