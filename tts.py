"""
Genera la narración en audio a partir de un texto usando Chatterbox
Multilingual TTS con voz clonada (referencia_voz.wav).

Requiere correrse con el venv que ya tienes montado (.venv-voz), por
ejemplo:
    .\\.venv-voz\\Scripts\\python.exe tts.py "Texto de prueba..."
"""
import os

# Limitar los hilos antes de importar torch evita sobresuscripción.
# Este portátil tiene 2 núcleos físicos / 4 lógicos. Dos es el punto de
# partida; TTS_NUM_THREADS permite comparar otros valores sin editar código.
NUM_HILOS = max(1, min(int(os.environ.get("TTS_NUM_THREADS", "2")), os.cpu_count() or 1))
os.environ["OMP_NUM_THREADS"] = str(NUM_HILOS)
os.environ["MKL_NUM_THREADS"] = str(NUM_HILOS)
os.environ["NUMEXPR_NUM_THREADS"] = str(NUM_HILOS)

import re
import hashlib
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from config import IDIOMA_SALIDA

DEFAULT_VOICE_PROMPT = "referencia_voz.wav"
MAX_CHARS_PER_CHUNK = 220          # Chatterbox degrada calidad con textos muy largos
SILENCE_BETWEEN_CHUNKS_MS = 280    # pausa natural entre fragmentos

# Controla la emoción de la voz. exaggeration alto = más expresiva/dramática
# (pero habla más rápido); cfg_weight bajo compensa bajando el ritmo.
# Valores por defecto de Chatterbox: 0.5 / 0.5 (voz "neutra", la que sonaba seca).
EXAGGERATION = 0.7
CFG_WEIGHT = 0.3


def _split_into_chunks(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Parte el texto en fragmentos cortos, respetando frases primero y comas si hace falta."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    chunks: list[str] = []
    current = ""

    def flush():
        nonlocal current
        if current:
            chunks.append(current)
            current = ""

    for sentence in sentences:
        candidate = f"{current} {sentence}".strip() if current else sentence
        if len(candidate) <= max_chars:
            current = candidate
            continue

        flush()
        if len(sentence) <= max_chars:
            current = sentence
            continue

        # frase demasiado larga: partir por comas
        for part in sentence.split(", "):
            candidate2 = f"{current}, {part}".strip(", ") if current else part
            if len(candidate2) <= max_chars:
                current = candidate2
            else:
                flush()
                current = part
    flush()
    # Una frase sin comas también debe respetar el límite.
    bounded = []
    for chunk in chunks:
        while len(chunk) > max_chars:
            cut = chunk.rfind(" ", 0, max_chars + 1)
            cut = cut if cut > 0 else max_chars
            bounded.append(chunk[:cut])
            chunk = chunk[cut:].strip()
        if chunk:
            bounded.append(chunk)
    return bounded


class Narrator:
    """Envoltorio sobre ChatterboxMultilingualTTS para generar narraciones largas."""

    def __init__(self, audio_prompt_path: str = DEFAULT_VOICE_PROMPT, language_id: str = None, device: str = "cpu"):
        # El guion ya está terminado. No mantener dos modelos grandes en memoria.
        import requests
        from ollama_selector import OLLAMA_URL, MODEL
        try:
            respuesta = requests.post(OLLAMA_URL, json={'model': MODEL, 'keep_alive': 0}, timeout=30)
            respuesta.raise_for_status()
            print('Modelo de guion descargado de memoria para generar la voz.', flush=True)
        except requests.RequestException:
            print('No se pudo liberar Ollama; se intentará generar la voz con la memoria disponible.', flush=True)
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # import diferido: carga pesada

        torch.set_num_threads(NUM_HILOS)
        try:
            torch.set_num_interop_threads(1)
        except RuntimeError:
            pass  # ya se había fijado antes en este proceso; no pasa nada
        print("Cargando modelo de voz...", flush=True)
        self.model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        self.audio_prompt_path = audio_prompt_path
        self.language_id = language_id or IDIOMA_SALIDA
        self.sample_rate = self.model.sr
        self._reference_ready = False

    def usar_voz(self, audio_prompt_path: str):
        """Cambia la voz de referencia activa (para alternar voces entre shorts,
        ej. masculina/femenina) sin recargar el modelo entero — solo recalcula
        la preparación de la referencia si de verdad cambia."""
        if audio_prompt_path != self.audio_prompt_path or not self._reference_ready:
            with torch.inference_mode():
                self.model.prepare_conditionals(audio_prompt_path, exaggeration=EXAGGERATION)
            self.audio_prompt_path = audio_prompt_path
            self._reference_ready = True

    def generate(self, text: str, output_path: str) -> str:
        """Genera un .wav narrado a partir de `text`, devolviendo la ruta final."""
        self.usar_voz(self.audio_prompt_path)
        chunks = _split_into_chunks(text)
        if not chunks:
            raise ValueError("No se puede narrar un guion vacío.")
        print(f"Generando narración en {len(chunks)} fragmento(s)...", flush=True)

        silence = np.zeros(int(self.sample_rate * SILENCE_BETWEEN_CHUNKS_MS / 1000), dtype=np.float32)
        pieces: list[np.ndarray] = []
        referencia = Path(self.audio_prompt_path)
        firma_voz = hashlib.sha256(referencia.read_bytes()).hexdigest()
        cache = Path(output_path).parent / 'fragmentos_voz'
        cache.mkdir(parents=True, exist_ok=True)
        for i, chunk in enumerate(chunks, 1):
            started = time.perf_counter()
            print(f"  [{i}/{len(chunks)}] {chunk[:60]}...", flush=True)
            firma = hashlib.sha256(f'{chunk}|{self.language_id}|{firma_voz}|{EXAGGERATION}|{CFG_WEIGHT}|{self.sample_rate}'.encode()).hexdigest()
            guardado = cache / f'{firma}.wav'
            if guardado.exists():
                muestras, sr = sf.read(guardado, dtype='float32')
                if sr != self.sample_rate or not len(muestras):
                    raise ValueError('Fragmento de voz guardado inválido.')
            else:
                with torch.inference_mode():
                    audio = self.model.generate(
                        chunk, language_id=self.language_id,
                        exaggeration=EXAGGERATION, cfg_weight=CFG_WEIGHT)
                muestras = audio.squeeze(0).detach().cpu().numpy()
                if not len(muestras) or not np.isfinite(muestras).all():
                    raise ValueError('El modelo devolvió audio vacío o inválido.')
                temporal = guardado.with_suffix('.tmp.wav')
                sf.write(temporal, muestras, self.sample_rate)
                temporal.replace(guardado)
            print(f'    Fragmento listo en {time.perf_counter() - started:.1f} s '
                  f'({len(muestras) / self.sample_rate:.1f} s de audio).', flush=True)
            pieces.append(muestras)
            if i < len(chunks):
                pieces.append(silence)

        full_audio = np.concatenate(pieces)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        sf.write(output_path, full_audio, self.sample_rate)
        print(f"Audio listo: {output_path}", flush=True)
        return output_path


if __name__ == "__main__":
    import sys

    texto = sys.argv[1] if len(sys.argv) > 1 else (
        "That afternoon I got home and realized something had changed."
    )
    narrator = Narrator()
    narrator.generate(texto, "salida/narracion.wav")
