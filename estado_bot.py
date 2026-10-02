"""Persistencia atómica y exclusión mutua para los procesos del bot."""
import json
import os
import time
from pathlib import Path
from contextlib import contextmanager


def guardar_json(ruta, datos):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(ruta.suffix + ".tmp")
    with temporal.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
        archivo.flush()
        os.fsync(archivo.fileno())
    temporal.replace(ruta)


@contextmanager
def bloqueo(ruta, intentos=1, espera=1):
    import msvcrt
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("a+b") as archivo:
        archivo.seek(0, 2)
        if archivo.tell() == 0:
            archivo.write(b"0")
            archivo.flush()
        archivo.seek(0)
        ultimo = None
        for intento in range(max(1, intentos)):
            try:
                msvcrt.locking(archivo.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError as exc:
                ultimo = exc
                if intento == intentos - 1:
                    raise RuntimeError("Ya hay otro lote ejecutándose.") from exc
                time.sleep(espera)
        else:
            raise RuntimeError("Ya hay otro lote ejecutándose.") from ultimo
        try:
            yield
        finally:
            archivo.seek(0)
            msvcrt.locking(archivo.fileno(), msvcrt.LK_UNLCK, 1)
