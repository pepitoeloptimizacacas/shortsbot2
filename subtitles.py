"""
Genera subtítulos (.srt normal y .ass estilo "shorts" con resaltado
palabra por palabra) a partir del audio YA narrado, usando faster-whisper
para sacar los timestamps por palabra.

Se transcribe el audio generado (no el texto original) para que el
timing de los subtítulos coincida exactamente con lo que se oye.
"""
from pathlib import Path

import soundfile as sf
from faster_whisper import WhisperModel

from config import IDIOMA_SALIDA

WORDS_PER_LINE = 4
TRIM_BUFFER_SECONDS = 0.3  # margen tras la última palabra antes de cortar


def _format_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def _format_ass_timestamp(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:01}:{m:02}:{s:02}.{cs:02}"


def transcribe_words(audio_path: str, model_size: str = "small", language: str = None, modelo=None):
    """Devuelve una lista de (palabra, inicio, fin) usando faster-whisper.

    Si se pasa `modelo` (un WhisperModel ya cargado), lo reutiliza en vez
    de cargar uno nuevo — útil para procesar varios audios seguidos sin
    pagar el coste de carga cada vez.
    """
    language = language or IDIOMA_SALIDA
    if modelo is None:
        modelo = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = modelo.transcribe(audio_path, language=language, word_timestamps=True)

    words = []
    for segment in segments:
        for word in segment.words:
            words.append((word.word.strip(), word.start, word.end))
    return words


def write_srt(words, srt_path: str, words_per_line: int = WORDS_PER_LINE):
    lines = []
    idx = 1
    for i in range(0, len(words), words_per_line):
        group = words[i: i + words_per_line]
        start, end = group[0][1], group[-1][2]
        text = " ".join(w for w, _, _ in group)
        lines.append(f"{idx}\n{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}\n{text}\n")
        idx += 1
    Path(srt_path).parent.mkdir(parents=True, exist_ok=True)
    Path(srt_path).write_text("\n".join(lines), encoding="utf-8")


ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Shorts,Arial Black,90,&H00FFFFFF,&H0000D7FF,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,4,2,2,60,60,120,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def write_ass(words, ass_path: str, words_per_line: int = WORDS_PER_LINE):
    """Genera un .ass con karaoke por palabra (\\k) para resaltar según se habla.

    PrimaryColour = blanco (palabra aún no dicha), SecondaryColour = amarillo/dorado
    (palabra activa). Esto lo interpreta libass automáticamente al quemarlo con ffmpeg.
    """
    lines = [ASS_HEADER]
    for i in range(0, len(words), words_per_line):
        group = words[i: i + words_per_line]
        start, end = group[0][1], group[-1][2]
        karaoke_text = ""
        cursor = start
        for word, w_start, w_end in group:
            gap_cs = max(0, round((w_start - cursor) * 100))
            if gap_cs:
                karaoke_text += f"{{\\k{gap_cs}}}"
            duration_cs = max(1, int(round((w_end - w_start) * 100)))
            word = word.replace("\\", "").replace("{", "").replace("}", "")
            karaoke_text += f"{{\\k{duration_cs}}}{word} "
            cursor = w_end
        line = (
            f"Dialogue: 0,{_format_ass_timestamp(start)},{_format_ass_timestamp(end)},"
            f"Shorts,,0,0,0,,{karaoke_text.strip()}"
        )
        lines.append(line)
    Path(ass_path).parent.mkdir(parents=True, exist_ok=True)
    Path(ass_path).write_text("\n".join(lines), encoding="utf-8")


def trim_trailing_audio(audio_path: str, words, buffer_seconds: float = TRIM_BUFFER_SECONDS):
    """Recorta el audio justo después de la última palabra transcrita.

    Chatterbox a veces genera un hueco de silencio + un 'blip' de ruido tras
    terminar la frase; como ya transcribimos el audio para los subtítulos,
    usamos esa misma transcripción como referencia fiable de dónde acaba
    el habla real, y descartamos todo lo que sobra después.
    """
    if not words:
        return audio_path

    last_word_end = words[-1][2]
    data, sample_rate = sf.read(audio_path)
    original_duration = len(data) / sample_rate
    cutoff = last_word_end + buffer_seconds

    if cutoff < original_duration - 0.05:  # solo recortar si hay algo real que quitar
        cutoff_samples = int(cutoff * sample_rate)
        sf.write(audio_path, data[:cutoff_samples], sample_rate)
        print(
            f"Audio recortado: {original_duration:.2f}s -> {cutoff:.2f}s "
            f"(se quitó cola de {original_duration - cutoff:.2f}s)",
            flush=True,
        )
    return audio_path


def generate_subtitles(
    audio_path: str,
    srt_path: str,
    ass_path: str,
    model_size: str = "small",
    trim_audio: bool = True,
    modelo=None,
):
    words = transcribe_words(audio_path, model_size=model_size, modelo=modelo)
    if not words:
        raise ValueError("No se detectó habla en la narración; no se generará el vídeo.")
    write_srt(words, srt_path)
    write_ass(words, ass_path)
    if trim_audio:
        trim_trailing_audio(audio_path, words)
    print(f"Subtítulos listos: {srt_path} / {ass_path}", flush=True)
    return words


if __name__ == "__main__":
    import sys

    audio = sys.argv[1] if len(sys.argv) > 1 else "salida/narracion.wav"
    generate_subtitles(audio, "salida/subtitulos.srt", "salida/subtitulos.ass")
