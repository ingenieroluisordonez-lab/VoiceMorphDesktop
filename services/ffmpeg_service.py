import json
import os
import subprocess
from typing import Callable, Optional

from utils.logger import setup_logger
from config import TEMP_DIR, SUPPORTED_VIDEO, SUPPORTED_AUDIO

logger = setup_logger("ffmpeg_service")

ProgressCB = Optional[Callable[[float, str], None]]


class FFmpegService:

    def __init__(self):
        self._verificar_instalacion()

    def _verificar_instalacion(self):
        try:
            r = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
            if r.returncode != 0:
                raise RuntimeError()
            logger.info("FFmpeg disponible")
        except FileNotFoundError:
            raise RuntimeError(
                "FFmpeg no encontrado. Instálalo y agrégalo al PATH.\n"
                "Guía: https://ffmpeg.org/download.html"
            )

    def info(self, ruta: str) -> dict:
        r = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                ruta,
            ],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"ffprobe falló: {r.stderr[:200]}")

        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        dur = float(fmt.get("duration", 0))
        size_b = int(fmt.get("size", 0))

        return {
            "nombre": os.path.basename(ruta),
            "duracion": dur,
            "duracion_fmt": self.fmt_duracion(dur),
            "tamanio_bytes": size_b,
            "tamanio_mb": round(size_b / (1024 ** 2), 2),
            "streams": data.get("streams", []),
        }

    @staticmethod
    def fmt_duracion(seg: float) -> str:
        h = int(seg // 3600)
        m = int((seg % 3600) // 60)
        s = int(seg % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def extraer_audio(
        self,
        ruta_video: str,
        ruta_salida: Optional[str] = None,
        cb: ProgressCB = None,
    ) -> str:
        if ruta_salida is None:
            base = os.path.splitext(os.path.basename(ruta_video))[0]
            ruta_salida = os.path.join(TEMP_DIR, f"{base}_audio.wav")

        if cb:
            cb(0.05, "Extrayendo audio del video…")

        r = subprocess.run(
            [
                "ffmpeg", "-i", ruta_video,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                "-y", ruta_salida,
            ],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Error extrayendo audio: {r.stderr[-300:]}")

        if cb:
            cb(0.2, "Audio extraído")
        logger.debug("Audio extraído → %s", ruta_salida)
        return ruta_salida

    def a_mono_rvc(self, ruta: str, ruta_salida: Optional[str] = None) -> str:
        """Convierte a mono 40000 Hz (formato requerido por RVC)."""
        if ruta_salida is None:
            base = os.path.splitext(ruta)[0]
            ruta_salida = f"{base}_mono40k.wav"

        r = subprocess.run(
            ["ffmpeg", "-i", ruta, "-ac", "1", "-ar", "40000", "-y", ruta_salida],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Error convirtiendo a mono: {r.stderr[-200:]}")
        return ruta_salida

    def pitch_shift(
        self,
        ruta: str,
        ruta_salida: str,
        semitonos: int = 6,
        cb: ProgressCB = None,
    ) -> str:
        if cb:
            cb(0.25, f"Aplicando pitch shift ({semitonos:+d} semitonos)…")

        factor = 2 ** (semitonos / 12)
        # asetrate sube el pitch; atempo corrige la velocidad para que no cambie la duración
        filtro = (
            f"asetrate=44100*{factor:.6f},"
            f"aresample=44100,"
            f"atempo={1/factor:.6f}"
        )

        r = subprocess.run(
            ["ffmpeg", "-i", ruta, "-af", filtro, "-y", ruta_salida],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Pitch shift fallido: {r.stderr[-200:]}")

        if cb:
            cb(0.80, "Pitch shift aplicado")
        return ruta_salida

    def fusionar_audio_video(
        self,
        ruta_video: str,
        ruta_audio: str,
        ruta_salida: str,
        cb: ProgressCB = None,
    ) -> str:
        if cb:
            cb(0.88, "Fusionando audio y video…")

        r = subprocess.run(
            [
                "ffmpeg",
                "-i", ruta_video,
                "-i", ruta_audio,
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-shortest",
                "-y", ruta_salida,
            ],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Error fusionando: {r.stderr[-300:]}")

        if cb:
            cb(0.98, "Video generado")
        logger.debug("Video final → %s", ruta_salida)
        return ruta_salida

    def concatenar_wavs(self, lista_rutas: list, ruta_salida: str) -> str:
        lista_txt = os.path.join(TEMP_DIR, "_concat_list.txt")
        with open(lista_txt, "w", encoding="utf-8") as f:
            for p in lista_rutas:
                # ffmpeg concat necesita slashes, no backslashes
                f.write(f"file '{p.replace(chr(92), '/')}'\n")

        r = subprocess.run(
            [
                "ffmpeg", "-f", "concat", "-safe", "0",
                "-i", lista_txt,
                "-c", "copy",
                "-y", ruta_salida,
            ],
            capture_output=True, text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"Error concatenando: {r.stderr[-200:]}")
        return ruta_salida

    def crear_silencio(self, duracion: float, ruta_salida: str):
        subprocess.run(
            [
                "ffmpeg",
                "-f", "lavfi",
                "-i", "anullsrc=r=22050:cl=mono",
                "-t", str(max(duracion, 0.05)),
                "-y", ruta_salida,
            ],
            capture_output=True,
        )

    @staticmethod
    def es_video(ruta: str) -> bool:
        return os.path.splitext(ruta)[1].lower() in SUPPORTED_VIDEO

    @staticmethod
    def es_audio(ruta: str) -> bool:
        return os.path.splitext(ruta)[1].lower() in SUPPORTED_AUDIO
