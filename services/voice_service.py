"""
Servicio de conversión y síntesis de voz.

Módulo A – Librosa STFT pitch shift: fallback cuando no hay modelo RVC.
Módulo B – RVC (Retrieval-based Voice Conversion): reemplaza completamente
           el timbre de la voz usando un modelo .pth descargado.
           Usa transformers en lugar de fairseq (incompatible con Python 3.13).
Módulo C – Piper TTS: sintetiza texto en inglés o portugués (para traducción).
               Offline después de descargar el modelo (~60-130 MB por idioma).
"""
import os
import subprocess
import threading
import time
import urllib.request
from typing import Callable, Dict, List, Optional

from utils.logger import setup_logger
from config import (
    TEMP_DIR, VOICES_DIR,
    PIPER_VOICES, PIPER_MAX_CHARS,
    RVC_INDEX_RATE, RVC_PROTECT, DEVICE,
)

logger = setup_logger("voice_service")

ProgressCB = Optional[Callable[[float, str], None]]


class VoiceService:

    def __init__(self):
        self._piper_voices: Dict[str, object] = {}
        self._rvc_cache:    Dict[str, object] = {}
        self._lock = threading.Lock()

    # =========================================================================
    # A ─ Pitch Shift con Librosa (conversión masculino → femenino)
    # =========================================================================

    def convertir_pitch(
        self,
        ruta_audio: str,
        ruta_salida: str,
        semitonos: int = 6,
        cb: ProgressCB = None,
        cancel: Optional[threading.Event] = None,
    ) -> str:
        """
        Desplaza el tono usando librosa (algoritmo STFT phase vocoder).
        Mucho más natural que el método básico de FFmpeg porque preserva
        los formantes de la voz — no suena a marciano.
        +6 semitonos: voz masculina → femenina.
        +4 a +5: resultado más sutil y natural para algunas voces.
        """
        if cancel and cancel.is_set():
            raise InterruptedError("Cancelado")

        if cb:
            cb(0.20, "Cargando audio…")

        try:
            import librosa
            import soundfile as sf
            import numpy as np
        except ImportError:
            logger.warning("librosa no disponible, usando FFmpeg como fallback")
            return self._convertir_pitch_ffmpeg(ruta_audio, ruta_salida, semitonos, cb)

        if cb:
            cb(0.30, f"Convirtiendo voz ({semitonos:+d} semitonos) con librosa…")

        # Cargar audio (mono, sample rate original)
        y, sr = librosa.load(ruta_audio, sr=None, mono=True)

        if cancel and cancel.is_set():
            raise InterruptedError("Cancelado")

        if cb:
            cb(0.50, "Procesando pitch shift (puede tardar 1-2 min en CPU)…")

        # STFT phase vocoder — preserva formantes mucho mejor que asetrate
        y_shifted = librosa.effects.pitch_shift(
            y, sr=sr,
            n_steps=float(semitonos),
            bins_per_octave=24,   # más resolución = más natural
            res_type="soxr_hq",   # soxr: rápido y sin dependencias extra
        )

        if cancel and cancel.is_set():
            raise InterruptedError("Cancelado")

        if cb:
            cb(0.82, "Guardando audio convertido…")

        sf.write(ruta_salida, y_shifted, sr, subtype="PCM_16")

        if cb:
            cb(0.88, "Conversión de voz completada")
        logger.info("Pitch shift librosa %+d st → %s", semitonos, ruta_salida)
        return ruta_salida

    def _convertir_pitch_ffmpeg(
        self,
        ruta_audio: str,
        ruta_salida: str,
        semitonos: int,
        cb: ProgressCB = None,
    ) -> str:
        """Fallback: pitch shift básico con FFmpeg."""
        if cb:
            cb(0.25, f"Pitch shift FFmpeg ({semitonos:+d} st)…")
        factor = 2 ** (semitonos / 12)
        filtro = (
            f"asetrate=44100*{factor:.6f},"
            "aresample=44100,"
            f"atempo={1/factor:.6f}"
        )
        r = subprocess.run(
            ["ffmpeg", "-i", ruta_audio, "-af", filtro, "-y", ruta_salida],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Error en pitch shift: {r.stderr[-300:]}")
        if cb:
            cb(0.85, "Conversión completada")
        return ruta_salida

    # =========================================================================
    # B ─ RVC (Retrieval-based Voice Conversion)
    # =========================================================================

    @staticmethod
    def _parchar_fairseq():
        """
        Inyecta un módulo 'fairseq' falso en sys.modules antes de que
        rvc-python intente importarlo.

        Carga el hubert_base.pt LOCAL (descargado por rvc-python) y mapea
        sus weights al modelo HuggingFace HubertModel.  Esto es necesario
        porque el hubert_base.pt de RVC es un modelo distinto al estándar
        facebook/hubert-base-ls960 de HuggingFace — usar el incorrecto
        produce audio lleno de ruido.
        """
        import sys
        if "fairseq" in sys.modules:
            return

        import re
        import types
        import torch
        import torch.nn as nn

        _cache: Dict[str, object] = {}

        class _HubertWrapper:
            """Adapta la API HuggingFace HuBERT a la que espera rvc-python."""
            def __init__(self, hf_model):
                self._m = hf_model
                self.final_proj = nn.Linear(768, 256)  # solo v1; v2 no lo usa

            def extract_features(self, source, padding_mask=None, output_layer=12):
                out = self._m(
                    input_values=source.squeeze(1),
                    output_hidden_states=True,
                )
                return (out.hidden_states[output_layer],)

            def to(self, dev):
                self._m = self._m.to(dev)
                self.final_proj = self.final_proj.to(dev)
                return self

            def half(self):
                self._m = self._m.half()
                self.final_proj = self.final_proj.half()
                return self

            def float(self):
                self._m = self._m.float()
                self.final_proj = self.final_proj.float()
                return self

            def eval(self):
                self._m.eval()
                return self

        def _remap_fairseq_a_hf(fs: dict) -> dict:
            """Remapea keys de fairseq al formato HuggingFace HuBERT."""
            # Keys que no se usan en inferencia
            SKIP = {
                "mask_emb", "final_proj.weight", "final_proj.bias",
                "label_embs_concat",
            }
            mapped = {}
            for k, v in fs.items():
                if k in SKIP:
                    continue
                # pos_conv: fairseq weight_norm → HuggingFace parametrizations
                if k == "encoder.pos_conv.0.bias":
                    mapped["encoder.pos_conv_embed.conv.bias"] = v
                    continue
                if k == "encoder.pos_conv.0.weight_g":
                    mapped["encoder.pos_conv_embed.conv.parametrizations.weight.original0"] = v
                    continue
                if k == "encoder.pos_conv.0.weight_v":
                    mapped["encoder.pos_conv_embed.conv.parametrizations.weight.original1"] = v
                    continue
                # CNN feature extractor: .N.0.weight → .N.conv.weight
                m = re.match(r"feature_extractor\.conv_layers\.(\d+)\.0\.weight", k)
                if m:
                    mapped[f"feature_extractor.conv_layers.{m.group(1)}.conv.weight"] = v
                    continue
                # Solo capa 0 tiene layer norm en la CNN
                m = re.match(r"feature_extractor\.conv_layers\.0\.2\.(weight|bias)", k)
                if m:
                    mapped[f"feature_extractor.conv_layers.0.layer_norm.{m.group(1)}"] = v
                    continue
                # layer_norm (feature) → feature_projection.layer_norm
                if k in ("layer_norm.weight", "layer_norm.bias"):
                    mapped[f"feature_projection.{k}"] = v
                    continue
                # post_extract_proj → feature_projection.projection
                if k.startswith("post_extract_proj."):
                    mapped[f"feature_projection.projection.{k[len('post_extract_proj.'):]}"] = v
                    continue
                # Capas transformer
                m = re.match(r"(encoder\.layers\.\d+)\.self_attn\.(.+)", k)
                if m:
                    mapped[f"{m.group(1)}.attention.{m.group(2)}"] = v
                    continue
                m = re.match(r"(encoder\.layers\.\d+)\.self_attn_layer_norm\.(.+)", k)
                if m:
                    mapped[f"{m.group(1)}.layer_norm.{m.group(2)}"] = v
                    continue
                m = re.match(r"(encoder\.layers\.\d+)\.fc1\.(.+)", k)
                if m:
                    mapped[f"{m.group(1)}.feed_forward.intermediate_dense.{m.group(2)}"] = v
                    continue
                m = re.match(r"(encoder\.layers\.\d+)\.fc2\.(.+)", k)
                if m:
                    mapped[f"{m.group(1)}.feed_forward.output_dense.{m.group(2)}"] = v
                    continue
                # Resto sin cambio (encoder.layer_norm, final_layer_norm, etc.)
                mapped[k] = v
            return mapped

        def _cargar_ensemble(paths, suffix=""):
            key = paths[0] if paths else "default"
            if key not in _cache:
                # Asegurarse de que fairseq.data.dictionary.Dictionary existe
                # para que torch.load pueda deserializar el checkpoint
                for _mod in ["fairseq", "fairseq.data", "fairseq.data.dictionary"]:
                    if _mod not in sys.modules:
                        sys.modules[_mod] = types.ModuleType(_mod)
                if not hasattr(sys.modules["fairseq.data.dictionary"], "Dictionary"):
                    class _Dict: pass
                    sys.modules["fairseq.data.dictionary"].Dictionary = _Dict

                pt_path = key  # = lib_dir/base_model/hubert_base.pt
                logger.info("Cargando HuBERT desde checkpoint local: %s", pt_path)
                cpt = torch.load(pt_path, map_location="cpu", weights_only=False)
                mapped = _remap_fairseq_a_hf(cpt["model"])

                from transformers import HubertModel
                hf_cache = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    "..", "models", "hubert_hf_cache",
                )
                # Cargamos la arquitectura HF (pesos se sobreescribirán)
                hf = HubertModel.from_pretrained(
                    "facebook/hubert-base-ls960",
                    cache_dir=hf_cache,
                )
                missing, unexpected = hf.load_state_dict(mapped, strict=False)
                faltantes = [k for k in missing if "pos_conv" not in k]
                if faltantes:
                    logger.warning("HuBERT: weights no cargados: %s", faltantes[:5])
                hf.eval()
                logger.info("HuBERT cargado con weights locales de rvc-python")
                _cache[key] = _HubertWrapper(hf)
            return [_cache[key]], None, None

        class _CheckpointUtils:
            load_model_ensemble_and_task = staticmethod(_cargar_ensemble)

        fairseq_mod = types.ModuleType("fairseq")
        fairseq_mod.checkpoint_utils = _CheckpointUtils()

        cu_mod = types.ModuleType("fairseq.checkpoint_utils")
        cu_mod.load_model_ensemble_and_task = _cargar_ensemble

        sys.modules["fairseq"]                  = fairseq_mod
        sys.modules["fairseq.checkpoint_utils"] = cu_mod
        logger.info("Parche fairseq activo — usará hubert_base.pt local")

    def convertir_rvc(
        self,
        ruta_audio: str,
        ruta_salida: str,
        ruta_modelo: str,
        ruta_index: Optional[str] = None,
        pitch_semitonos: int = 0,
        cb: ProgressCB = None,
        cancel: Optional[threading.Event] = None,
    ) -> str:
        """
        Convierte la voz usando un modelo RVC (.pth) descargado.
        Primera vez: descarga hubert_base.pt (~350 MB), rmvpe.pt (~100 MB)
        y el modelo HuBERT de HuggingFace (~360 MB).
        Las siguientes ejecuciones son inmediatas (todo cacheado).
        """
        if cancel and cancel.is_set():
            raise InterruptedError()

        if cb:
            cb(0.04, "Preparando RVC…")

        self._parchar_fairseq()

        try:
            from rvc_python.infer import RVCInference
        except ImportError as exc:
            raise RuntimeError(f"rvc-python no disponible: {exc}") from exc

        device = "cuda:0" if DEVICE == "cuda" else "cpu:0"

        with self._lock:
            if ruta_modelo not in self._rvc_cache:
                if cb:
                    cb(0.10, "Primera vez: descargando modelos base RVC (~450 MB)…")
                inst = RVCInference(device=device)

                if cb:
                    cb(0.28, "Cargando modelo de voz…")
                inst.load_model(ruta_modelo, index_path=ruta_index or "")
                self._rvc_cache[ruta_modelo] = inst

            rvc = self._rvc_cache[ruta_modelo]
            rvc.set_params(
                f0up_key=pitch_semitonos,
                f0method="rmvpe",
                # El índice FAISS fue construido con features de fairseq HuBERT original.
                # Nuestro parche usa HuggingFace HuBERT (espacio incompatible) → silencio.
                # Sin índice, el sintetizador RVC funciona correctamente.
                index_rate=0.0,
                protect=RVC_PROTECT,
            )

        if cancel and cancel.is_set():
            raise InterruptedError()

        # RVC requiere mono 16 kHz
        ruta_16k = os.path.join(TEMP_DIR, "_rvc_in16k.wav")
        r = subprocess.run(
            ["ffmpeg", "-i", ruta_audio,
             "-ar", "16000", "-ac", "1", "-y", ruta_16k],
            capture_output=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Error re-muestreando a 16 kHz: {r.stderr[-200:]}")

        if cb:
            cb(0.40, "Convirtiendo voz con RVC… (puede tardar minutos en CPU)")

        rvc.infer_file(ruta_16k, ruta_salida)

        if cancel and cancel.is_set():
            raise InterruptedError()

        if cb:
            cb(0.92, "Conversión RVC completada")
        logger.info("RVC → %s", ruta_salida)
        return ruta_salida

    def listar_modelos(self) -> List[Dict]:
        """Lista archivos .pth de RVC disponibles (para futura compatibilidad)."""
        modelos = []
        if not os.path.isdir(VOICES_DIR):
            return modelos
        for nombre in os.listdir(VOICES_DIR):
            if nombre.endswith(".pth"):
                base = os.path.splitext(nombre)[0]
                pth  = os.path.join(VOICES_DIR, nombre)
                idx  = os.path.join(VOICES_DIR, f"{base}.index")
                modelos.append({
                    "nombre":     base,
                    "ruta_pth":   pth,
                    "ruta_index": idx if os.path.isfile(idx) else None,
                    "tiene_index": os.path.isfile(idx),
                })
        return modelos

    # =========================================================================
    # B ─ Piper TTS (síntesis para traducción)
    # =========================================================================

    def _descargar_modelo_piper(self, lang_code: str, cb: ProgressCB = None):
        """Descarga el modelo Piper para el idioma dado si no existe."""
        cfg = PIPER_VOICES.get(lang_code)
        if cfg is None:
            raise RuntimeError(f"Idioma '{lang_code}' no configurado en Piper.")

        for url_key, ruta_key in [("url_onnx", "onnx"), ("url_json", "json")]:
            ruta = cfg[ruta_key]
            if os.path.isfile(ruta):
                continue

            url = cfg[url_key]
            nombre_archivo = os.path.basename(ruta)

            if cb:
                cb(0.12, f"Descargando modelo Piper: {nombre_archivo}…")
            logger.info("Descargando %s → %s", url, ruta)

            try:
                urllib.request.urlretrieve(url, ruta)
            except Exception as exc:
                # Limpiar archivo incompleto
                if os.path.isfile(ruta):
                    os.remove(ruta)
                raise RuntimeError(
                    f"No se pudo descargar el modelo Piper para '{lang_code}'.\n"
                    f"Verifica la conexión a internet.\nError: {exc}"
                )

            logger.info("Descargado: %s", ruta)

    def _cargar_piper(self, lang_code: str, cb: ProgressCB = None):
        """Carga (o reutiliza) el modelo Piper para un idioma."""
        if lang_code in self._piper_voices:
            return self._piper_voices[lang_code]

        self._descargar_modelo_piper(lang_code, cb)

        try:
            from piper.voice import PiperVoice
        except ImportError:
            raise RuntimeError(
                "piper-tts no instalado.\n"
                "Ejecuta: pip install piper-tts"
            )

        cfg  = PIPER_VOICES[lang_code]
        if cb:
            cb(0.35, f"Cargando Piper TTS ({lang_code})…")

        voz  = PiperVoice.load(cfg["onnx"], config_path=cfg["json"])
        self._piper_voices[lang_code] = voz
        logger.info("Piper TTS cargado: %s", lang_code)
        return voz

    @staticmethod
    def _dividir_texto(texto: str, max_chars: int = PIPER_MAX_CHARS) -> List[str]:
        """
        Divide texto largo en fragmentos respetando oraciones.
        Cascada: 1) por oraciones (.!?), 2) por comas/punto-y-coma,
        3) forzado por palabras si queda algo demasiado largo.
        Sin esto, un párrafo sin puntuación cuelga al fonemizador.
        """
        if len(texto) <= max_chars:
            return [texto]

        # Nivel 1: oraciones
        fragmentos, actual = [], ""
        for oracion in texto.replace("!", ".").replace("?", ".").split("."):
            oracion = oracion.strip()
            if not oracion:
                continue
            candidato = f"{actual} {oracion}." if actual else f"{oracion}."
            if len(candidato) > max_chars and actual:
                fragmentos.append(actual)
                actual = f"{oracion}."
            else:
                actual = candidato
        if actual:
            fragmentos.append(actual)

        # Nivel 2: si una oración sigue muy larga → por comas/punto-y-coma
        nivel2 = []
        for frag in fragmentos:
            if len(frag) <= max_chars:
                nivel2.append(frag)
                continue
            sub_actual = ""
            partes = frag.replace(";", ",").split(",")
            for parte in partes:
                parte = parte.strip()
                if not parte:
                    continue
                candidato = f"{sub_actual}, {parte}" if sub_actual else parte
                if len(candidato) > max_chars and sub_actual:
                    nivel2.append(sub_actual)
                    sub_actual = parte
                else:
                    sub_actual = candidato
            if sub_actual:
                nivel2.append(sub_actual)

        # Nivel 3: corte forzado por palabras (último recurso)
        final = []
        for frag in nivel2:
            if len(frag) <= max_chars:
                final.append(frag)
                continue
            sub_actual = ""
            for palabra in frag.split():
                cand = f"{sub_actual} {palabra}" if sub_actual else palabra
                if len(cand) > max_chars and sub_actual:
                    final.append(sub_actual)
                    sub_actual = palabra
                else:
                    sub_actual = cand
            if sub_actual:
                final.append(sub_actual)

        return final or [texto[:max_chars]]

    @staticmethod
    def _limpiar_texto(texto: str) -> str:
        """
        Limpia el texto antes de enviarlo a Piper.
        Elimina caracteres que pueden hacer fallar la síntesis.
        """
        import unicodedata
        # Normalizar unicode (ej: tildes compuestas → precompuestas)
        texto = unicodedata.normalize("NFC", texto)
        # Eliminar caracteres de control excepto espacios y saltos de línea
        texto = "".join(
            c for c in texto
            if unicodedata.category(c) not in ("Cc", "Cf") or c in ("\n", "\t")
        )
        # Reemplazar saltos de línea y tabs por espacio
        texto = " ".join(texto.split())
        return texto.strip()

    @staticmethod
    def _silencio_wav(ruta: str, sample_rate: int, duracion: float = 0.3):
        """Crea un WAV de silencio sin necesitar FFmpeg."""
        import wave
        n = int(sample_rate * duracion)
        with wave.open(ruta, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b"\x00\x00" * n)

    def sintetizar(
        self,
        texto: str,
        ruta_salida: str,
        idioma: str = "en",
        cb: ProgressCB = None,
        cancel: Optional[threading.Event] = None,
    ) -> str:
        """
        Sintetiza texto con Piper TTS.
        Usa synthesize_stream_raw para evitar problemas con el header WAV.
        El modelo se descarga automáticamente la primera vez (~60-130 MB).
        """
        import wave
        import shutil

        with self._lock:
            voz = self._cargar_piper(idioma, cb)

        if cancel and cancel.is_set():
            raise InterruptedError("Cancelado")

        sample_rate = voz.config.sample_rate
        fragmentos  = self._dividir_texto(texto)
        total       = len(fragmentos)
        tmp_wavs    = []

        logger.info("Piper: %d fragmento(s) a sintetizar", total)

        for i, frag in enumerate(fragmentos):
            if cancel and cancel.is_set():
                raise InterruptedError("Cancelado")

            tmp = os.path.join(TEMP_DIR, f"_piper_{i:04d}.wav")
            tmp_wavs.append(tmp)

            if cb:
                cb(0.42 + (i / total) * 0.40, f"Sintetizando fragmento {i+1}/{total}…")

            frag_limpio = self._limpiar_texto(frag)

            if not frag_limpio:
                # Fragmento vacío → silencio corto para no romper la concatenación
                self._silencio_wav(tmp, sample_rate, duracion=0.3)
                continue

            preview = frag_limpio[:60] + ("…" if len(frag_limpio) > 60 else "")
            logger.info("[%d/%d] (%d chars) %s", i + 1, total, len(frag_limpio), preview)
            t0 = time.time()

            try:
                # synthesize_wav con set_wav_format=True configura los parámetros
                # del archivo WAV automáticamente (canales, sample rate, bits)
                with wave.open(tmp, "wb") as wf:
                    voz.synthesize_wav(
                        frag_limpio,
                        wf,
                        set_wav_format=True,
                    )
                logger.info("[%d/%d] OK en %.1fs", i + 1, total, time.time() - t0)

            except Exception as exc:
                logger.warning("[%d/%d] falló (%s) — usando silencio", i + 1, total, exc)
                self._silencio_wav(tmp, sample_rate, duracion=0.5)

        # Ensamblar fragmentos en un solo WAV
        if len(tmp_wavs) == 1:
            shutil.move(tmp_wavs[0], ruta_salida)
        else:
            if cb:
                cb(0.85, "Ensamblando audio final…")
            lista = os.path.join(TEMP_DIR, "_piper_list.txt")
            with open(lista, "w", encoding="utf-8") as f:
                for p in tmp_wavs:
                    f.write(f"file '{p.replace(chr(92), '/')}'\n")

            r = subprocess.run(
                ["ffmpeg", "-f", "concat", "-safe", "0",
                 "-i", lista, "-c", "copy", "-y", ruta_salida],
                capture_output=True, text=True,
            )
            if r.returncode != 0:
                raise RuntimeError(f"FFmpeg concat falló: {r.stderr[-200:]}")

            for t in tmp_wavs:
                if os.path.isfile(t):
                    os.remove(t)

        if cb:
            cb(0.88, "Síntesis completada")
        logger.info("Piper TTS → %s (%d fragmentos)", ruta_salida, total)
        return ruta_salida

    # =========================================================================
    # Liberar memoria
    # =========================================================================

    def liberar(self):
        """Descarga los modelos de la memoria."""
        self._piper_voices.clear()
        logger.info("Modelos de voz liberados")
