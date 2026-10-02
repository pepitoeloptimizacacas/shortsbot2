"""OAuth de escritorio y subida recuperable mediante la API oficial de YouTube."""
import json
from pathlib import Path
import time
from estado_bot import guardar_json
from config import YOUTUBE_CANAL_ESPERADO, IDIOMA_SALIDA

BASE = Path(__file__).resolve().parent
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
          "https://www.googleapis.com/auth/youtube.readonly"]


def conectar(autorizar=False, abrir_navegador=True):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import AuthorizedSession, Request
    token = BASE / "youtube_token.json"
    cred = Credentials.from_authorized_user_file(str(token), SCOPES) if token.exists() and not autorizar else None
    if cred and cred.expired and cred.refresh_token:
        cred.refresh(Request())
    if not cred or not cred.valid:
        if not autorizar:
            raise RuntimeError("Conecta tu canal primero: ejecuta conectar_youtube.cmd (consulta README.md).")
        from google_auth_oauthlib.flow import InstalledAppFlow
        secret = BASE / "client_secret.json"
        if not secret.exists():
            raise RuntimeError("Falta client_secret.json: descarga tu cliente OAuth de escritorio de Google Cloud. Consulta README.md.")
        cred = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(
            port=0, open_browser=abrir_navegador, timeout_seconds=600,
            prompt="consent select_account")
    session = AuthorizedSession(cred)
    response = session.get("https://www.googleapis.com/youtube/v3/channels",
                           params={"part": "snippet", "mine": "true"}, timeout=60)
    response.raise_for_status()
    canales = response.json().get("items", [])
    if len(canales) != 1:
        raise RuntimeError("La cuenta autorizada debe tener un canal de YouTube identificable.")
    canal = canales[0]
    normalizar = lambda valor: "".join(c for c in valor.casefold() if c.isalnum())
    nombres = [canal["snippet"].get("title", ""), canal["snippet"].get("customUrl", "")]
    if normalizar(YOUTUBE_CANAL_ESPERADO) not in [normalizar(n) for n in nombres]:
        raise RuntimeError(f"Canal incorrecto: {canal['snippet']['title']}. Debes elegir {YOUTUBE_CANAL_ESPERADO}; no se guardó esta autorización.")
    fijado = BASE / "youtube_canal.json"
    if fijado.exists() and json.loads(fijado.read_text(encoding="utf-8"))["id"] != canal["id"]:
        raise RuntimeError("El identificador del canal no coincide con redditplot ya conectado.")
    guardar_json(fijado, {"id": canal["id"], "titulo": canal["snippet"]["title"]})
    guardar_json(token, json.loads(cred.to_json()))
    session.canal_id = canales[0]["id"]
    print(f"Canal conectado: {canales[0]['snippet']['title']}", flush=True)
    return session


def aceptar_respuesta(response, short, guardar):
    if response.status_code in (200, 201):
        video_id = response.json().get("id")
        if not video_id:
            raise RuntimeError("YouTube no devolvió un identificador de vídeo.")
        short["youtube_id"] = video_id
        short["estado"] = "subido"
        guardar()
        return True
    if response.status_code == 308:
        return False
    if response.status_code in (404, 410):
        raise RuntimeError("La sesión de subida caducó. Revisa YouTube Studio antes de resolverla; no se creará otra subida que pueda duplicar el vídeo.")
    response.raise_for_status()
    raise RuntimeError(f"Respuesta inesperada de YouTube: {response.status_code}")


def _bytes_confirmados(response, total):
    """Devuelve el siguiente byte a enviar de una respuesta reanudable."""
    rango = response.headers.get("Range")
    if not rango:
        return 0
    try:
        inicio, fin = rango.removeprefix("bytes=").split("-", 1)
        inicio, fin = int(inicio), int(fin)
    except (AttributeError, ValueError):
        raise RuntimeError(f"YouTube devolvió un rango de subida inválido: {rango!r}.")
    if inicio != 0 or fin < inicio or fin >= total:
        raise RuntimeError(f"YouTube devolvió un rango de subida fuera de límites: {rango!r}.")
    return fin + 1


def _crear_sesion_subida(session, short, total):
    """Crea la sesión reanudable y tolera cortes breves de red o DNS."""
    import requests
    for _ in range(60):
        try:
            response = session.post("https://www.googleapis.com/upload/youtube/v3/videos",
                params={"uploadType": "resumable", "part": "snippet,status"},
                headers={"X-Upload-Content-Length": str(total), "X-Upload-Content-Type": "video/mp4"},
                json={"snippet": {"title": short["historia"]["titulo"],
                                  "description": ("Relato de ficción de misterio y suspense, narrado en español." if short['historia'].get('ficcion') else "Relato de misterio y suspense narrado en español.") + ("\n#Shorts" if short.get('formato', 'short') == 'short' else ''),
                                  "categoryId": "24"},
                      "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}}, timeout=60)
            if response.status_code in (429, 500, 502, 503, 504):
                response.raise_for_status()
            return response
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            transitorio = not isinstance(exc, requests.HTTPError) or exc.response.status_code in (429, 500, 502, 503, 504)
            if not transitorio or intento == 4:
                raise
            time.sleep(2 ** intento)


def _subir_miniatura(session, short, video, guardar):
    """Sube la caja de comentario 16:9 de los vídeos largos."""
    if short.get("formato", "short") != "largo" or short.get("miniatura_subida"):
        return
    miniatura = Path(video).with_name("miniatura.jpg")
    if not miniatura.is_file():
        raise FileNotFoundError(f"Falta la miniatura del vídeo largo: {miniatura}")
    import requests
    datos = miniatura.read_bytes()
    for intento in range(5):
        try:
            response = session.post(
                "https://www.googleapis.com/upload/youtube/v3/thumbnails/set",
                params={"videoId": short["youtube_id"], "uploadType": "media"},
                headers={"Content-Type": "image/jpeg", "Content-Length": str(len(datos))},
                data=datos,
                timeout=120,
            )
            if response.status_code in (429, 500, 502, 503, 504):
                response.raise_for_status()
            response.raise_for_status()
            short["miniatura_subida"] = True
            guardar()
            print(f"Miniatura publicada para {short['youtube_id']}", flush=True)
            return
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as exc:
            transitorio = not isinstance(exc, requests.HTTPError) or exc.response.status_code in (429, 500, 502, 503, 504)
            if not transitorio or intento == 4:
                raise
            time.sleep(2 ** intento)


def publicar(session, short, video, guardar):
    if short.get("youtube_canal") not in (None, session.canal_id):
        raise RuntimeError("Este lote pertenece a otro canal de YouTube.")
    short["youtube_canal"] = session.canal_id
    guardar()
    if not short.get("youtube_id"):
        total = Path(video).stat().st_size
        if not short.get("youtube_session"):
            if short.get("inicio_subida_pendiente"):
                raise RuntimeError("La creación de la sesión quedó interrumpida. Revisa el registro antes de reiniciarla.")
            short["inicio_subida_pendiente"] = True
            guardar()
            response = _crear_sesion_subida(session, short, total)
            if 400 <= response.status_code < 500:
                short.pop("inicio_subida_pendiente", None)
                guardar()
            response.raise_for_status()
            short["youtube_session"] = response.headers["Location"]
            short.pop("inicio_subida_pendiente", None)
            guardar()
        for intento in range(5):
            try:
                response = session.put(short["youtube_session"],
                    headers={"Content-Length": "0", "Content-Range": f"bytes */{total}"}, timeout=60)
                if aceptar_respuesta(response, short, guardar):
                    break
                offset = _bytes_confirmados(response, total)
                with Path(video).open("rb") as archivo:
                    archivo.seek(offset)
                    while offset < total:
                        chunk = archivo.read(8 * 1024 * 1024)
                        end = offset + len(chunk) - 1
                        response = session.put(short["youtube_session"], data=chunk,
                            headers={"Content-Type": "video/mp4", "Content-Length": str(len(chunk)),
                                     "Content-Range": f"bytes {offset}-{end}/{total}"}, timeout=180)
                        if aceptar_respuesta(response, short, guardar):
                            break
                        confirmado = _bytes_confirmados(response, total)
                        if confirmado <= offset:
                            raise RuntimeError("YouTube no confirmó progreso en la subida.")
                        offset = confirmado
                        archivo.seek(offset)
                if short.get("youtube_id"):
                    break
                raise RuntimeError("Subida sin confirmación final.")
            except Exception as exc:
                import requests
                transitorio = isinstance(exc, (requests.Timeout, requests.ConnectionError)) or (
                    isinstance(exc, requests.HTTPError) and exc.response.status_code in (429, 500, 502, 503, 504))
                if not transitorio or intento == 4:
                    raise
                time.sleep(2 ** intento)
    for _ in range(60):
        response = session.get("https://www.googleapis.com/youtube/v3/videos",
            params={"part": "status,processingDetails", "id": short["youtube_id"]}, timeout=60)
        response.raise_for_status()
        items = response.json().get("items", [])
        if items:
            status = items[0]["status"]
            if status.get("uploadStatus") in ("failed", "rejected", "deleted"):
                raise RuntimeError(f"YouTube no aceptó el vídeo: {status.get('uploadStatus')}")
            if status.get("uploadStatus") == "processed":
                if status.get("privacyStatus") != "public":
                    raise RuntimeError("YouTube mantiene el vídeo privado. Revisa las restricciones del proyecto API en Google Cloud y YouTube Studio.")
                _subir_miniatura(session, short, video, guardar)
                short["estado"] = "publicado"
                short["youtube_url"] = f"https://www.youtube.com/watch?v={short['youtube_id']}"
                guardar()
                print(f"Publicado: {short['youtube_url']}", flush=True)
                return
        time.sleep(15)
        raise RuntimeError("YouTube sigue procesando. Repite el comando más tarde; no se volverá a subir.")


if __name__ == "__main__":
    try:
        conectar(autorizar=True)
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
