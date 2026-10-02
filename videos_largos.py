"""Vídeos horizontales que desarrollan una sola historia por vídeo."""
from pathlib import Path
from config import VELOCIDAD_VIDEO, LARGO_MIN_SEGUNDOS, LARGO_MAX_SEGUNDOS


def ids_historia(historia):
    return historia.get("ids", [historia["id"]])


def elegir_largo(candidatos):
    from ollama_selector import elegir_mejor_historia
    disponibles = [c for c in candidatos if len(c.get('text', '').split()) >= 2400]
    if not disponibles:
        raise RuntimeError("No hay una historia suficientemente extensa para desarrollar un vídeo largo.")
    # Revisar fuentes distintas; no volver a sortear la misma historia rechazada.
    disponibles.sort(key=lambda c: abs(len(c['text'].split()) - 3200))
    errores = []
    for candidato in disponibles[:8]:
        print(f"Evaluando historia larga {candidato['id']}...", flush=True)
        try:
            historia = elegir_mejor_historia([candidato], para_largo=True)
            historia['tipo_guion'] = 'historia_unica'
            return historia
        except ValueError as exc:
            errores.append(str(exc))
            print(f"Historia {candidato['id']} descartada: {exc}", flush=True)
    raise ValueError('Ninguna de las fuentes revisadas dio un guion válido. Último motivo: ' + errores[-1])


def montar_largo(audio, subtitulos, titulo, salida):
    from montar_video import _duracion_audio
    duracion = _duracion_audio(audio) / VELOCIDAD_VIDEO
    if not LARGO_MIN_SEGUNDOS <= duracion <= LARGO_MAX_SEGUNDOS:
        raise ValueError(f"El largo acelerado duraría {duracion:.0f}s; debe durar entre 15 y 30 minutos.")
    ass = Path(subtitulos)
    horizontal = ass.with_name("subtitulos_horizontal.ass")
    texto = ass.read_text(encoding="utf-8-sig")
    texto = texto.replace("PlayResX: 1080", "PlayResX: 1920").replace("PlayResY: 1920", "PlayResY: 1080")
    texto = texto.replace("Arial Black,90,", "Arial Black,56,")
    horizontal.write_text(texto, encoding="utf-8")
    from estilo_video import montar_satisfactorio
    return montar_satisfactorio(audio, horizontal, titulo, salida, horizontal=True)
