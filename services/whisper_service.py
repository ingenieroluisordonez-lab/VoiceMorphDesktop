import threading
from typing import Callable, Dict, Optional

from utils.logger import setup_logger
from config import DEVICE, WHISPER_MODEL

logger = setup_logger("whisper_service")

ProgressCB = Optional[Callable[[float, str], None]]


class WhisperService:

    def __init__(self):
        self._model = None
        self._lock = threading.Lock()

    def _cargar(self, cb: ProgressCB = None):
        if self._model is not None:
            return

        with self._lock:
            if self._model is not None:
                return
            try:
                import whisper
                if cb:
                    cb(0.05, f"Cargando Whisper {WHISPER_MODEL}…")
                logger.info("Cargando Whisper %s en %s", WHISPER_MODEL, DEVICE)
                self._model = whisper.load_model(WHISPER_MODEL, device=DEVICE)
                if cb:
                    cb(0.30, "Whisper listo")
                logger.info("Whisper cargado")
            except ImportError:
                raise RuntimeError(
                    "openai-whisper no instalado.\n"
                    "Ejecuta: pip install openai-whisper"
                )

    def transcribir(
        self,
        ruta_audio: str,
        idioma: str = "es",
        cb: ProgressCB = None,
        cancel: Optional[threading.Event] = None,
    ) -> Dict:
        self._cargar(cb)

        if cancel and cancel.is_set():
            raise InterruptedError("Cancelado")

        if cb:
            cb(0.32, "Transcribiendo…")
        logger.info("Transcribiendo: %s", ruta_audio)

        resultado = self._model.transcribe(
            ruta_audio,
            language=idioma if idioma != "auto" else None,
            verbose=False,
            task="transcribe",
        )

        if cb:
            cb(0.70, f"Transcripción lista — {len(resultado['segments'])} segmentos")
        logger.info("Segmentos: %d", len(resultado["segments"]))

        return {
            "text": resultado["text"],
            "segments": resultado["segments"],
            "language": resultado.get("language", idioma),
        }

    def liberar(self):
        if self._model is not None:
            try:
                import torch
                del self._model
                self._model = None
                if DEVICE == "cuda":
                    torch.cuda.empty_cache()
                logger.info("Whisper liberado")
            except Exception as exc:
                logger.warning("Error liberando Whisper: %s", exc)
