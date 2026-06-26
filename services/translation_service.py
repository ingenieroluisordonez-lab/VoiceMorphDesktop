import threading
from typing import Callable, Dict, List, Optional

from utils.logger import setup_logger

logger = setup_logger("translation_service")

ProgressCB = Optional[Callable[[float, str], None]]


class TranslationService:

    def __init__(self):
        self._lock = threading.Lock()

    def paquete_instalado(self, from_code: str, to_code: str) -> bool:
        try:
            import argostranslate.translate as at
            langs = at.get_installed_languages()
            src = next((l for l in langs if l.code == from_code), None)
            if src is None:
                return False
            dst = next((l for l in langs if l.code == to_code), None)
            if dst is None:
                return False
            return src.get_translation(dst) is not None
        except Exception:
            return False

    def instalar_paquete(self, from_code: str, to_code: str, cb: ProgressCB = None):
        """Descarga e instala el paquete de traducción (solo necesita internet la primera vez)."""
        try:
            import argostranslate.package as ap

            if cb:
                cb(0.10, f"Buscando paquete {from_code}→{to_code}…")

            ap.update_package_index()
            disponibles = ap.get_available_packages()

            pkg = next(
                (p for p in disponibles if p.from_code == from_code and p.to_code == to_code),
                None,
            )
            if pkg is None:
                raise RuntimeError(f"No existe paquete Argos para {from_code}→{to_code}.")

            if cb:
                cb(0.40, "Descargando paquete…")
            ruta = pkg.download()

            if cb:
                cb(0.80, "Instalando paquete…")
            ap.install_from_path(ruta)

            if cb:
                cb(1.00, "Paquete instalado")
            logger.info("Paquete instalado: %s→%s", from_code, to_code)

        except Exception as exc:
            logger.error("Error instalando paquete: %s", exc)
            raise

    def paquetes_instalados(self) -> List[str]:
        try:
            import argostranslate.translate as at
            resultado = []
            for lang in at.get_installed_languages():
                for tr in lang.translations_from:
                    resultado.append(f"{lang.code}→{tr.to_lang.code}")
            return resultado
        except Exception:
            return []

    def traducir(self, texto: str, from_code: str, to_code: str) -> str:
        try:
            import argostranslate.translate as at
            langs = at.get_installed_languages()
            src = next(l for l in langs if l.code == from_code)
            dst = next(l for l in langs if l.code == to_code)
            return src.get_translation(dst).translate(texto)
        except StopIteration:
            raise RuntimeError(
                f"Paquete {from_code}→{to_code} no instalado. "
                "Usa instalar_paquete() primero."
            )

    def traducir_segmentos(
        self,
        segmentos: List[Dict],
        from_code: str,
        to_code: str,
        cb: ProgressCB = None,
    ) -> List[Dict]:
        """Traduce segmentos de Whisper manteniendo los timestamps."""
        import argostranslate.translate as at

        langs = at.get_installed_languages()
        src = next((l for l in langs if l.code == from_code), None)
        dst = next((l for l in langs if l.code == to_code), None)

        if src is None or dst is None or src.get_translation(dst) is None:
            raise RuntimeError(f"Paquete {from_code}→{to_code} no instalado.")

        traduccion = src.get_translation(dst)
        total = len(segmentos)
        resultado = []

        for i, seg in enumerate(segmentos):
            texto_orig = seg["text"].strip()
            texto_trad = traduccion.translate(texto_orig) if texto_orig else ""

            resultado.append({
                "start": seg["start"],
                "end": seg["end"],
                "text": texto_trad,
            })

            if cb and total:
                cb(0.30 + (i / total) * 0.38, f"Traduciendo {i+1}/{total}…")

        return resultado
