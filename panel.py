"""Panel de solo lectura, accesible únicamente desde este ordenador."""
import json
import threading
import time
import subprocess
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import psutil

BASE = Path(__file__).resolve().parent
temperaturas = []


def sensores():
    global temperaturas
    script = "& { foreach ($ns in @('root/LibreHardwareMonitor','root/OpenHardwareMonitor')) { Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object { $_.SensorType -eq 'Temperature' } | Select-Object Name,Value } } | ConvertTo-Json -Compress"
    while True:
        try:
            r = subprocess.run(['powershell.exe', '-NoProfile', '-Command', script], capture_output=True,
                               text=True, timeout=12, creationflags=0x08000000)
            datos = json.loads(r.stdout) if r.stdout.strip() else []
            if isinstance(datos, dict):
                datos = [datos]
            temperaturas = [{"nombre": d['Name'], "valor": round(float(d['Value']), 1)}
                            for d in datos if d.get('Value') is not None and 0 < float(d['Value']) < 130]
        except (ValueError, OSError, subprocess.TimeoutExpired):
            temperaturas = []
        time.sleep(20)


def estado():
    lotes = sorted((BASE / 'salida/lotes').glob('*/estado.json'), key=lambda p: p.stat().st_mtime, reverse=True)
    lote = {"cantidad": 6, "shorts": []}
    aviso = None
    if lotes:
        try:
            lote = json.loads(lotes[0].read_text(encoding='utf-8'))
        except (OSError, ValueError):
            aviso = 'No se pudo leer el lote; se volverá a intentar.'
    procesos = []
    apagar = False
    for p in psutil.process_iter(['name', 'cmdline', 'memory_info']):
        try:
            args = p.info['cmdline'] or []
            if any(Path(a).name == 'lote_diario.py' for a in args) and 'python' in (p.info['name'] or '').lower():
                procesos.append(p)
                apagar = apagar or '--apagar' in args
        except (psutil.Error, OSError):
            pass
    ram = psutil.virtual_memory()
    disco = psutil.disk_usage(str(BASE))
    shorts = []
    for s in lote.get('shorts', []):
        # Lista explícita: nunca exponer tokens ni URL de sesión de subida.
        shorts.append({"titulo": s.get('historia', {}).get('titulo', 'Preparando historia'),
                       "estado": s.get('estado', 'pendiente'), "error": bool(s.get('error')),
                       "duracion": s.get('duracion'),
                       "video_id": s.get('youtube_id')})
    logs = sorted((BASE / 'salida/logs').glob('bot-*.log'), key=lambda p: p.stat().st_mtime, reverse=True)
    logs = [p for p in logs if '.error.' not in p.name]
    actividad = 'Esperando un lote'
    actualizado = None
    if logs:
        actualizado = logs[0].stat().st_mtime
        with logs[0].open('rb') as f:
            f.seek(max(0, logs[0].stat().st_size - 16000))
            lineas = f.read().decode('utf-8', errors='replace').splitlines()
        for linea in reversed(lineas):
            if 'ERROR' in linea or 'Fallo en' in linea:
                actividad = 'El bot ha registrado un error. Consulta el registro local.'
                break
            if 'Preguntando a Ollama' in linea:
                actividad = 'Eligiendo y adaptando historias con Ollama'
                break
            if 'Cargando modelo' in linea:
                actividad = 'Cargando el modelo de voz'
                break
            if 'Generando narraci' in linea or linea.strip().startswith('['):
                actividad = 'Generando la narración'
                break
            if 'Montando video' in linea:
                actividad = 'Montando vídeo con FFmpeg'
                break
            if 'Publicado:' in linea:
                actividad = 'YouTube ha confirmado una publicación'
                break
            if 'Canal conectado:' in linea:
                actividad = 'Canal conectado; buscando historias'
                break
            if 'Subt' in linea and 'listos' in linea:
                actividad = 'Subtítulos listos'
                break
            if 'Lote:' in linea:
                actividad = linea[:180]
                break
    return {"hora": time.time(), "activo": bool(procesos), "actividad": actividad,
            "ultima_actividad": actualizado, "lote": lotes[0].parent.name if lotes else None,
            "cantidad": lote.get('cantidad', 6), "shorts": shorts, "aviso": aviso,
            "cpu": psutil.cpu_percent(), "ram": {"porcentaje": ram.percent, "usada": ram.used, "total": ram.total},
            "disco": {"libre": disco.free, "total": disco.total}, "temperaturas": temperaturas,
            "apagar": apagar}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.headers.get('Host') not in ('127.0.0.1:8787', 'localhost:8787'):
            self.send_error(403)
            return
        if self.path == '/api/estado':
            try:
                body = json.dumps(estado(), ensure_ascii=False).encode('utf-8')
            except Exception:
                self.send_error(503, 'No se pudo leer el estado')
                return
            tipo = 'application/json; charset=utf-8'
        elif self.path in ('/', '/index.html'):
            body = (BASE / 'panel.html').read_bytes()
            tipo = 'text/html; charset=utf-8'
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data:; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    psutil.cpu_percent()
    threading.Thread(target=sensores, daemon=True).start()
    print('Panel disponible en http://127.0.0.1:8787', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 8787), Handler).serve_forever()
