"""Lotes recuperables: python lote_diario.py [--publicar] [--apagar]."""
import argparse
import gc
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from datetime import datetime
from estado_bot import guardar_json, bloqueo
from config import IDIOMA_SALIDA, LARGO_MIN_SEGUNDOS, LARGO_MAX_SEGUNDOS
from videos_largos import elegir_largo, ids_historia, montar_largo
from limpiar_lotes import limpiar_lotes

BASE = Path(__file__).resolve().parent
VOCES_ALTERNADAS = ("referencia_voz.wav", "referencia2.wav")


def voz_para_indice(indice: int) -> str:
    """Voz estable por posición: reanudar un lote no cambia el narrador."""
    return VOCES_ALTERNADAS[indice % len(VOCES_ALTERNADAS)]


def validar_video(ruta, formato="short"):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_format", "-show_streams",
                             "-of", "json", str(ruta)], capture_output=True, text=True,
                            check=True, timeout=30)
    datos = json.loads(result.stdout)
    video = next((s for s in datos["streams"] if s["codec_type"] == "video"), None)
    audio = any(s["codec_type"] == "audio" for s in datos["streams"])
    duracion = float(datos["format"]["duration"])
    ancho, alto = (1920, 1080) if formato == "largo" else (1080, 1920)
    if not video or not audio or video["width"] != ancho or video["height"] != alto:
        raise ValueError(f"El vídeo debe tener audio y resolución {ancho}x{alto}.")
    if not ((LARGO_MIN_SEGUNDOS <= duracion <= LARGO_MAX_SEGUNDOS) if formato == "largo" else (10 <= duracion <= 180)):
        raise ValueError(f"Duración inesperada para {formato}: {duracion:.1f}s.")
    return duracion


def reintentar(operacion, intentos=3):
    for intento in range(intentos):
        try:
            return operacion()
        except Exception:
            if intento == intentos - 1:
                raise
            time.sleep(2 ** intento)


def listo_para_apagar(estado, cantidad, cantidad_largos):
    shorts = estado.get('shorts', [])
    largos = estado.get('largos', [])
    return (len(shorts) == cantidad and len(largos) == cantidad_largos
            and all(p.get('estado') == 'publicado' and p.get('youtube_id')
                    for p in shorts + largos))


def videos_por_turno(estado, carpeta, guardar, antes_de_buscar):
    """Entrega primero el progreso guardado y después un guion nuevo cada vez."""
    yield from estado['shorts'] + estado['largos']
    from reddit_scraper import buscar_candidatos
    from ollama_selector import elegir_mejor_historia
    reservados = {i for s in estado['shorts'] + estado['largos'] for i in ids_historia(s['historia'])}
    for otro in carpeta.parent.glob('*/estado.json'):
        otros = json.loads(otro.read_text(encoding='utf-8'))
        reservados.update(i for s in otros.get('shorts', []) + otros.get('largos', [])
                          for i in ids_historia(s['historia']))
    for tipo, cantidad in (('shorts', estado['cantidad']), ('largos', estado['cantidad_largos'])):
        candidatos = None
        while len(estado[tipo]) < cantidad:
            antes_de_buscar()
            if candidatos is None:
                opciones = dict(limite_por_sub=100, max_candidatos=100,
                                min_length=12000, max_length=40000) if tipo == 'largos' else dict(max_candidatos=40)
                candidatos = reintentar(lambda: buscar_candidatos(**opciones))
            candidatos = [c for c in candidatos if c['id'] not in reservados]
            if not candidatos:
                raise RuntimeError('No hay suficientes historias nuevas. El progreso está guardado.')
            # elegir_largo ya prueba fuentes distintas. Repetir la operación
            # completa volvía a adaptar las mismas historias durante horas.
            historia = elegir_largo(candidatos) if tipo == 'largos' else elegir_mejor_historia(candidatos)
            prefijo = 'largo' if tipo == 'largos' else 'short'
            destino = carpeta / f'{prefijo}_{len(estado[tipo]) + 1:02d}'
            guardar_json(destino / 'historia.json', historia)
            video = {'historia': historia, 'carpeta': destino.as_posix(), 'estado': 'pendiente'}
            if tipo == 'largos':
                video['formato'] = 'largo'
            estado[tipo].append(video)
            reservados.update(ids_historia(historia))
            guardar()
            yield video


def ejecutar(args):
    os.chdir(BASE)
    cantidad_largos = getattr(args, "largos", 0)
    modo_prueba = getattr(args, "modo_prueba", False)
    voz_referencia = getattr(args, "voz_referencia", "referencia_voz.wav")
    if args.apagar and not args.publicar:
        raise ValueError("--apagar requiere --publicar.")
    for programa in ("ffmpeg", "ffprobe"):
        if not shutil.which(programa):
            raise RuntimeError(f"Falta {programa} en PATH.")
    carpeta = Path("salida/lotes") / args.lote
    archivo = carpeta / "estado.json"
    with bloqueo(Path("salida/bot.lock")):
        if archivo.exists():
            estado = json.loads(archivo.read_text(encoding="utf-8"))
            if estado.get("idioma", "en") != IDIOMA_SALIDA:
                raise ValueError("El lote guardado tiene otro idioma. Usa otro --lote para crear historias nuevas.")
            if estado["cantidad"] != args.cantidad:
                raise ValueError("El lote existente tiene otra cantidad. Usa otro --lote.")
            if bool(estado.get("modo_prueba", False)) != modo_prueba:
                raise ValueError("El lote existente pertenece a otro modo. Usa otro --lote.")
        else:
            estado = {"cantidad": args.cantidad, "idioma": IDIOMA_SALIDA, "shorts": [],
                      "creado": datetime.now().isoformat(), "id_lote": args.lote,
                      "modo_prueba": modo_prueba}
            guardar_json(archivo, estado)
        guardar = lambda: guardar_json(archivo, estado)
        if "cantidad_largos" in estado and estado["cantidad_largos"] != cantidad_largos:
            raise ValueError("El lote existente tiene otra cantidad de largos. Usa otro --lote.")
        estado["cantidad_largos"] = cantidad_largos
        estado.setdefault("largos", [])
        guardar()
        borrados = limpiar_lotes(Path("salida/lotes"), excluir=args.lote)
        if borrados:
            print(f'Limpieza: liberado espacio de {len(borrados)} lote(s) antiguo(s).', flush=True)
        youtube = None
        if args.publicar:
            from youtube_publicar import conectar
            youtube = conectar()
        errores = []
        narrator = whisper = None

        def liberar_modelos():
            nonlocal narrator, whisper
            narrator = whisper = None
            gc.collect()

        def preparar_videos():
            try:
                yield from videos_por_turno(estado, carpeta, guardar, liberar_modelos)
            except Exception as exc:
                estado['error_seleccion'] = f'{type(exc).__name__}: {exc}'
                guardar()
                errores.append(estado['error_seleccion'])
                print(f"Selección detenida: {estado['error_seleccion']}. Progreso guardado.", flush=True)
                if modo_prueba and not estado['shorts'] and not estado['largos']:
                    raise RuntimeError(f"Falló la búsqueda o adaptación de la historia: {estado['error_seleccion']}") from exc
            else:
                estado.pop('error_seleccion', None)
                guardar()

        for indice_video, short in enumerate(preparar_videos()):
            try:
                formato = short.get("formato", "short")
                voz_predeterminada = voz_referencia if modo_prueba else voz_para_indice(indice_video)
                voz_actual = short.setdefault("voz_referencia", voz_predeterminada)
                if not (BASE / voz_actual).is_file():
                    raise FileNotFoundError(f"Falta la referencia de voz {voz_actual}.")
                guardar()
                if formato == 'largo' and len(ids_historia(short['historia'])) > 1 and not short.get('youtube_id'):
                    raise ValueError('Este largo antiguo reúne varias historias. Usa un lote nuevo para generar una sola historia.')
                destino = Path(short["carpeta"])
                final = destino / "video_final.mp4"
                if short["estado"] == "pendiente":
                    from ollama_selector import limpiar_texto, validar_repeticiones
                    for campo in ("titulo", "guion"):
                        short["historia"][campo] = limpiar_texto(short["historia"][campo])
                    validar_repeticiones(short['historia']['guion'])
                    guardar()
                    from tts import Narrator
                    from faster_whisper import WhisperModel
                    from subtitles import generate_subtitles
                    from montar_video import montar_video
                    if narrator is None:
                        narrator = Narrator(audio_prompt_path=voz_actual)
                    else:
                        narrator.usar_voz(voz_actual)
                    audio = destino / "narracion.wav"
                    ass = destino / "subtitulos.ass"
                    narrator.generate(short["historia"]["guion"], str(audio))
                    if whisper is None:
                        whisper = WhisperModel("small", device="cpu", compute_type="int8")
                    generate_subtitles(str(audio), str(destino / "subtitulos.srt"), str(ass), modelo=whisper)
                    temporal = destino / "video_temporal.mp4"
                    montar = montar_largo if formato == "largo" else montar_video
                    montar(str(audio), ass.as_posix(), short["historia"]["titulo"], str(temporal))
                    short["duracion"] = validar_video(temporal, formato)
                    temporal.replace(final)
                    short["estado"] = "generado"
                    guardar()
                if not modo_prueba:
                    from reddit_scraper import _guardar_usado
                    for post_id in ids_historia(short["historia"]):
                        _guardar_usado(post_id)
                if args.publicar:
                    from youtube_publicar import publicar
                    if not short.get("youtube_id"):
                        validar_video(final, formato)
                    publicar(youtube, short, final, guardar)
                short.pop("error", None)
                guardar()
            except Exception as exc:
                short["error"] = f"{type(exc).__name__}: {exc}"
                guardar()
                errores.append(short["error"])
                print(f"Fallo en {short['carpeta']}: {short['error']}", flush=True)
        if getattr(args, 'revisar', False):
            # La voz y Whisper ocupan memoria. Se liberan antes de cargar Ollama
            # para que la revisión no compita con ellos en equipos modestos.
            narrator = whisper = None
            gc.collect()
            from revisar_video import revisar
            for short in estado['shorts'] + estado['largos']:
                if short.get('estado') not in ('generado', 'subido', 'publicado'):
                    continue
                destino = Path(short['carpeta'])
                try:
                    short['revision'] = revisar(
                        destino / 'video_final.mp4', destino / 'narracion.wav',
                        short['historia']['titulo'], short['historia']['guion'])
                    guardar()
                except Exception as exc:
                    short['revision'] = {'apto': False, 'error': f'{type(exc).__name__}: {exc}'}
                    guardar()
        esperado = "publicado" if args.publicar else "generado"
        completos = sum(s["estado"] == esperado or (not args.publicar and s["estado"] in ("subido", "publicado"))
                        for s in estado["shorts"] + estado["largos"])
        total = args.cantidad + cantidad_largos
        print(f"Lote: {completos}/{total} completados. Registro: {archivo}", flush=True)
        if errores or completos != total:
            raise RuntimeError("Quedan vídeos pendientes. No se apagará el PC. Repite el mismo comando para reanudar.")
        if not estado.get('completado'):
            estado['completado'] = datetime.now().isoformat()
            guardar()
        if args.apagar:
            if not listo_para_apagar(estado, args.cantidad, cantidad_largos):
                raise RuntimeError('Comprobación final incompleta. No se apagará el PC.')
            print("Publicaciones confirmadas. Apagado en 60 segundos; cancelar: shutdown /a", flush=True)
            subprocess.run(["shutdown", "/s", "/t", "60"], check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cantidad", type=int, default=6)
    parser.add_argument("--largos", type=int, default=3, help="Vídeos largos por lote (0 a 3).")
    parser.add_argument("--lote", default=datetime.now().strftime("%Y-%m-%d"),
                        help="Usa el mismo identificador para reanudar, incluso otro día.")
    parser.add_argument("--publicar", action="store_true")
    parser.add_argument("--apagar", action="store_true")
    args = parser.parse_args()
    if not 0 <= args.largos <= 3:
        parser.error("La cantidad de largos debe estar entre 0 y 3.")
    if not 0 <= args.cantidad <= 6:
        parser.error("La cantidad de shorts debe estar entre 0 y 6.")
    if args.cantidad + args.largos == 0:
        parser.error("El lote debe contener al menos un vídeo.")
    if not args.lote or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in args.lote):
        parser.error("--lote solo admite letras, números, guiones y guiones bajos.")
    try:
        ejecutar(args)
    except Exception as exc:
        print(f"ERROR: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
