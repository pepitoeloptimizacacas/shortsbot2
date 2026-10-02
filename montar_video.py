"""
Monta el video final del short:
  - Fondo: si hay videos .mp4 en la carpeta `fondos/`, elige uno al azar.
    Si el clip es más largo que la narración (ej. un parkour de 2 horas),
    arranca desde un punto aleatorio en vez de siempre desde el principio,
    para que no se repita siempre la misma parte. Si el clip es más corto
    que la narración, lo repite en bucle desde el principio. Si no hay
    ningún video en `fondos/`, genera un fondo procedural (degradado
    animado tipo "satisfying") sin depender de ningún video con copyright.
  - Narración: el audio ya generado (narracion.wav).
  - Subtítulos: se queman en el video desde el .ass (karaoke palabra por
    palabra).
  - Título: la tarjeta PNG generada por title_card.py. Se revela con un
    efecto de "wipe" (izquierda a derecha) al aparecer, se queda fija un
    rato, y desaparece con el mismo efecto en vez de cortar de golpe.
  - Suscríbete: la animación de subscribe_animation.mp4 (fondo blanco
    quitado con chroma key) aparece a mitad del video.

Requiere ffmpeg instalado y accesible en el PATH.
"""
import random
import json
import subprocess
from pathlib import Path

import soundfile as sf

from title_card import crear_tarjeta_titulo

CARPETA_FONDOS = Path("fondos")
ANCHO, ALTO = 1080, 1920

# --- Tarjeta de título ---
SEGUNDOS_TITULO_VISIBLE = 4     # tiempo total en pantalla, incluyendo entrada y salida
SEGUNDOS_REVELADO = 0.6         # duración del wipe al aparecer Y al desaparecer

# --- Animación de "Subscribe" ---
RUTA_SUBSCRIBE = Path("subscribe_animation.mp4")
SUBSCRIBE_ANCHO = 750           # ancho al que se escala el botón
SUBSCRIBE_DURACION = 3.5        # cuánto se muestra (el clip original dura ~6s)
SUBSCRIBE_POS_Y_FRAC = 0.62     # posición vertical (fracción de la altura del video)

MARGEN_FINAL_SEGUNDOS = 5  # no arrancar el fondo tan cerca del final que se corte


def _duracion_audio(ruta_audio: str) -> float:
    info = sf.info(ruta_audio)
    return info.frames / info.samplerate


def _duracion_video(ruta_video: Path) -> float:
    resultado = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(ruta_video),
        ],
        capture_output=True, text=True, check=True, timeout=30,
    )
    return float(resultado.stdout.strip())


def _elegir_fondo_local() -> Path | None:
    if not CARPETA_FONDOS.exists():
        return None
    clips = list(CARPETA_FONDOS.glob("*.mp4"))
    return random.choice(clips) if clips else None


def _construir_efecto_titulo() -> str:
    """
    Efecto de wipe en la tarjeta de título: entra revelándose de izquierda
    a derecha, se queda fija, y sale de la misma forma (el lado derecho
    "se cierra" hacia la izquierda) en vez de desaparecer de golpe.
    """
    t_in_fin = SEGUNDOS_REVELADO
    t_out_inicio = SEGUNDOS_TITULO_VISIBLE - SEGUNDOS_REVELADO
    t_out_fin = SEGUNDOS_TITULO_VISIBLE
    duracion_salida = t_out_fin - t_out_inicio

    alpha_expr = (
        f"if(lt(T,{t_in_fin}),"
        f"if(lt(X,(W*T/{t_in_fin})),alpha(X,Y),0),"
        f"if(lt(T,{t_out_inicio}),"
        f"alpha(X,Y),"
        f"if(lt(T,{t_out_fin}),"
        f"if(lt(X,(W*(1-(T-{t_out_inicio})/{duracion_salida}))),alpha(X,Y),0),"
        f"0)))"
    )

    return (
        f"[2:v]format=rgba,geq=r='r(X,Y)':g='g(X,Y)':b='b(X,Y)':a='{alpha_expr}'[titulo_reveal];"
    )


def _construir_efecto_subscribe(duracion_total: float) -> tuple[str, float]:
    """Devuelve el trozo de filtro para el botón de Subscribe y el instante en que empieza."""
    inicio = duracion_total / 2
    fin = inicio + SUBSCRIBE_DURACION
    filtro = (
        f"[3:v]colorkey=0xFFFFFF:0.15:0.05,scale={SUBSCRIBE_ANCHO}:-1[sub_keyed];"
        f"[con_titulo][sub_keyed]overlay=(main_w-overlay_w)/2:main_h*{SUBSCRIBE_POS_Y_FRAC}:"
        f"enable='between(t,{inicio:.2f},{fin:.2f})'[vout];"
    )
    return filtro, inicio


def montar_video_legacy(
    ruta_narracion: str,
    ruta_subtitulos_ass: str,
    titulo: str,
    ruta_salida: str = "salida/video_final.mp4",
) -> str:
    # Punto de compatibilidad para llamadas antiguas: el montador actual usa
    # exclusivamente fondos/, voz clonada, subtítulos y música local.
    return montar_video(ruta_narracion, ruta_subtitulos_ass, titulo, ruta_salida)

    duracion = _duracion_audio(ruta_narracion)
    ruta_titulo_png = crear_tarjeta_titulo(titulo, str(Path(ruta_salida).parent / "titulo.png"))
    # FFmpeg necesita escapar los separadores de las rutas Windows dentro del filtro.
    ruta_subtitulos_ass = "'" + Path(ruta_subtitulos_ass).as_posix().replace(":", r"\:").replace("'", r"'\''") + "'"
    fondo_local = _elegir_fondo_local()

    Path(ruta_salida).parent.mkdir(parents=True, exist_ok=True)

    efecto_titulo = _construir_efecto_titulo()
    overlay_titulo = (
        f"overlay=0:0:enable='between(t,0,{SEGUNDOS_TITULO_VISIBLE})'[con_titulo];"
    )
    efecto_subscribe, inicio_subscribe = _construir_efecto_subscribe(duracion)
    print(f"Botón de Subscribe a partir del segundo {inicio_subscribe:.1f}", flush=True)

    if fondo_local:
        probe = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(fondo_local)],
                               capture_output=True, text=True, check=True, timeout=30)
        tiene_audio = any(s["codec_type"] == "audio" for s in json.loads(probe.stdout)["streams"])
        duracion_fondo = _duracion_video(fondo_local)
        cabe_sin_loop = duracion_fondo > (duracion + MARGEN_FINAL_SEGUNDOS)

        if cabe_sin_loop:
            inicio_max = duracion_fondo - duracion - MARGEN_FINAL_SEGUNDOS
            inicio = random.uniform(0, inicio_max)
            print(f"Usando fondo local: {fondo_local} (desde el segundo {inicio:.1f})", flush=True)
        else:
            inicio = 0
            print(f"Usando fondo local: {fondo_local} (en bucle, es más corto que la narración)", flush=True)

        filtro = (
            f"[0:v]scale={ANCHO}:{ALTO}:force_original_aspect_ratio=increase,"
            f"crop={ANCHO}:{ALTO},setsar=1[bg];"
            f"[bg]ass={ruta_subtitulos_ass}[subbed];"
            f"{efecto_titulo}"
            f"[subbed][titulo_reveal]{overlay_titulo}"
            f"{efecto_subscribe}"
        )
        if tiene_audio:
            filtro += "[0:a]volume=0.12[bgaudio];[1:a][bgaudio]amix=inputs=2:duration=first:dropout_transition=1:normalize=0[aout]"
        else:
            filtro = filtro.rstrip(";")

        if cabe_sin_loop:
            entrada_fondo = ["-ss", str(inicio), "-i", str(fondo_local)]
        else:
            entrada_fondo = ["-stream_loop", "-1", "-i", str(fondo_local)]

        comando = [
            "ffmpeg", "-y",
            *entrada_fondo,
            "-i", ruta_narracion,
            "-loop", "1", "-framerate", "30", "-i", ruta_titulo_png,
            "-itsoffset", f"{inicio_subscribe:.2f}", "-i", str(RUTA_SUBSCRIBE),
            "-filter_complex", filtro,
            "-map", "[vout]", "-map", "[aout]" if tiene_audio else "1:a",
            "-t", str(duracion),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac",
            ruta_salida,
        ]
    else:
        print("No hay fondos en fondos/, generando fondo procedural...", flush=True)
        filtro = (
            f"[0:v]ass={ruta_subtitulos_ass}[subbed];"
            f"{efecto_titulo}"
            f"[subbed][titulo_reveal]{overlay_titulo}"
            f"{efecto_subscribe}"
        )
        comando = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i",
            f"gradients=size={ANCHO}x{ALTO}:rate=30:speed=0.02:nb_colors=4",
            "-i", ruta_narracion,
            "-loop", "1", "-framerate", "30", "-i", ruta_titulo_png,
            "-itsoffset", f"{inicio_subscribe:.2f}", "-i", str(RUTA_SUBSCRIBE),
            "-filter_complex", filtro.rstrip(";"),
            "-map", "[vout]", "-map", "1:a",
            "-t", str(duracion),
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac",
            ruta_salida,
        ]

    print("Montando video con ffmpeg...", flush=True)
    comando[-1:-1] = ["-r", "30", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    resultado = subprocess.run(comando, capture_output=True, text=True, timeout=7200)
    if resultado.returncode != 0:
        print("ERROR de ffmpeg:\n", resultado.stderr[-3000:], flush=True)
        raise RuntimeError("ffmpeg falló al montar el video")

    print(f"Video listo: {ruta_salida}", flush=True)
    return ruta_salida


def montar_video(ruta_narracion, ruta_subtitulos_ass, titulo, ruta_salida="salida/video_final.mp4"):
    from estilo_video import montar_satisfactorio
    return montar_satisfactorio(ruta_narracion, ruta_subtitulos_ass, titulo, ruta_salida)


if __name__ == "__main__":
    montar_video(
        ruta_narracion="salida/narracion.wav",
        ruta_subtitulos_ass="salida/subtitulos.ass",
        titulo="No sabía que mi vecino guardaba esto en el sótano",
    )
