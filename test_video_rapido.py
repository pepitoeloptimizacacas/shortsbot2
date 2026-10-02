"""
Prueba rápida del vídeo completo con un texto corto (unos 10-15 s de audio):
voz clonada -> subtítulos -> montaje (tarjeta de título, fondo, Subscribe).

Uso:
    .\\.venv-voz\\Scripts\\python.exe test_video_rapido.py
    .\\.venv-voz\\Scripts\\python.exe test_video_rapido.py "Tu texto corto aquí"

Resultado: salida/test_rapido/video_final.mp4
Si repites el mismo texto, la voz sale de la caché (fragmentos_voz) y solo
se rehacen subtítulos y vídeo, así que las repeticiones son mucho más rápidas.
"""
import sys
from pathlib import Path

from config import IDIOMA_SALIDA
from tts import Narrator
from subtitles import generate_subtitles
from montar_video import montar_video

TEXTOS = {
    "es": ("Aquella noche escuché ruidos en el piso de arriba. "
           "Mi vecino juraba que vivía solo, pero alguien caminaba de un lado a otro."),
    "en": ("That night I heard noises from the apartment upstairs. "
           "My neighbor swore he lived alone, but someone kept pacing back and forth."),
}
TITULOS = {
    "es": "Los ruidos de mi vecino",
    "en": "My neighbor's strange noises",
}


def main():
    texto = sys.argv[1] if len(sys.argv) > 1 else TEXTOS.get(IDIOMA_SALIDA, TEXTOS["en"])
    titulo = TITULOS.get(IDIOMA_SALIDA, TITULOS["en"])
    carpeta = Path("salida/test_rapido")
    carpeta.mkdir(parents=True, exist_ok=True)

    narrator = Narrator(audio_prompt_path="referencia_voz.wav")
    audio = carpeta / "narracion.wav"
    narrator.generate(texto, str(audio))

    ass = carpeta / "subtitulos.ass"
    generate_subtitles(str(audio), str(carpeta / "subtitulos.srt"), str(ass))

    video = montar_video(str(audio), ass.as_posix(), titulo, str(carpeta / "video_final.mp4"))
    print(f"\nListo: {video}")


if __name__ == "__main__":
    main()
