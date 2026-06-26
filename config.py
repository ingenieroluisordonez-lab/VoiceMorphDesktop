import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Rutas principales
MODELS_DIR   = os.path.join(BASE_DIR, "models")
VOICES_DIR   = os.path.join(MODELS_DIR, "voices")
TEMP_DIR     = os.path.join(BASE_DIR, "temp")
OUTPUT_DIR   = os.path.join(BASE_DIR, "output")
LOGS_DIR     = os.path.join(BASE_DIR, "logs")
DATABASE_DIR = os.path.join(BASE_DIR, "database")


def _detectar_dispositivo() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


DEVICE   = _detectar_dispositivo()
USE_CUDA = DEVICE == "cuda"

# Whisper
WHISPER_MODEL    = "large-v3"
WHISPER_LANGUAGE = "es"

# Formatos de archivo soportados
SUPPORTED_VIDEO = [".mp4", ".avi", ".mkv"]
SUPPORTED_AUDIO = [".mp3", ".wav"]
SUPPORTED_ALL   = SUPPORTED_VIDEO + SUPPORTED_AUDIO

DATABASE_PATH = os.path.join(DATABASE_DIR, "voicemorph.db")

# RVC
RVC_F0_METHOD  = "rmvpe"   # rmvpe es el más preciso
RVC_F0_UP_KEY  = 6         # +6 semitonos = masculino → femenino
RVC_INDEX_RATE = 0.75
RVC_PROTECT    = 0.5

# Piper TTS — modelos offline (~60-130 MB)
# Cambia estas variables para usar otra voz del catálogo de abajo
PIPER_DIR = os.path.join(MODELS_DIR, "piper")

PIPER_VOZ_EN = "en_US-lessac-medium"  # medium es 5x más rápido en CPU
PIPER_VOZ_PT = "pt_BR-faber-medium"
PIPER_VOZ_ES = "es_MX-ald-medium"     # para acento España: es_ES-davefx-medium

# Catálogo de voces Piper disponibles
# Para agregar más: busca en https://huggingface.co/rhasspy/piper-voices
_HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
PIPER_CATALOGO_VOCES = {
    # Inglés femeninas
    "en_US-amy-medium": {
        "genero": "F", "calidad": "media",
        "descripcion": "Amy — voz femenina americana, natural",
        "url_base": f"{_HF}/en/en_US/amy/medium/en_US-amy-medium",
    },
    "en_US-lessac-medium": {
        "genero": "F", "calidad": "media",
        "descripcion": "Lessac — femenina americana, muy natural",
        "url_base": f"{_HF}/en/en_US/lessac/medium/en_US-lessac-medium",
    },
    "en_US-lessac-high": {
        "genero": "F", "calidad": "alta",
        "descripcion": "Lessac HIGH — femenina americana, mejor calidad (~130 MB)",
        "url_base": f"{_HF}/en/en_US/lessac/high/en_US-lessac-high",
    },
    "en_US-ljspeech-high": {
        "genero": "F", "calidad": "alta",
        "descripcion": "LJSpeech — narradora femenina, muy clara",
        "url_base": f"{_HF}/en/en_US/ljspeech/high/en_US-ljspeech-high",
    },
    "en_US-kathleen-low": {
        "genero": "F", "calidad": "baja",
        "descripcion": "Kathleen — femenina, modelo ligero",
        "url_base": f"{_HF}/en/en_US/kathleen/low/en_US-kathleen-low",
    },
    # Inglés masculinas
    "en_US-ryan-medium": {
        "genero": "M", "calidad": "media",
        "descripcion": "Ryan — masculino americano",
        "url_base": f"{_HF}/en/en_US/ryan/medium/en_US-ryan-medium",
    },
    # Inglés británico
    "en_GB-cori-medium": {
        "genero": "F", "calidad": "media",
        "descripcion": "Cori — femenina britanica",
        "url_base": f"{_HF}/en/en_GB/cori/medium/en_GB-cori-medium",
    },
    "en_GB-jenny_dioco-medium": {
        "genero": "F", "calidad": "media",
        "descripcion": "Jenny — femenina britanica, muy natural",
        "url_base": f"{_HF}/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium",
    },
    # Español
    "es_MX-ald-medium": {
        "genero": "M", "calidad": "media",
        "descripcion": "Ald — masculino mexicano, la más natural en español",
        "url_base": f"{_HF}/es/es_MX/ald/medium/es_MX-ald-medium",
    },
    "es_ES-davefx-medium": {
        "genero": "M", "calidad": "media",
        "descripcion": "Davefx — masculino español de España",
        "url_base": f"{_HF}/es/es_ES/davefx/medium/es_ES-davefx-medium",
    },
    # Portugués
    "pt_BR-faber-medium": {
        "genero": "M", "calidad": "media",
        "descripcion": "Faber — masculino brasilero",
        "url_base": f"{_HF}/pt/pt_BR/faber/medium/pt_BR-faber-medium",
    },
    "pt_PT-tugao-medium": {
        "genero": "M", "calidad": "media",
        "descripcion": "Tugao — masculino portugues de Portugal",
        "url_base": f"{_HF}/pt/pt_PT/tugao/medium/pt_PT-tugao-medium",
    },
}


def _cfg_voz(nombre: str) -> dict:
    entrada = PIPER_CATALOGO_VOCES[nombre]
    base = entrada["url_base"]
    return {
        "onnx": os.path.join(PIPER_DIR, f"{nombre}.onnx"),
        "json": os.path.join(PIPER_DIR, f"{nombre}.onnx.json"),
        "url_onnx": f"{base}.onnx",
        "url_json": f"{base}.onnx.json",
        "descripcion": entrada["descripcion"],
    }


PIPER_VOICES = {
    "en": _cfg_voz(PIPER_VOZ_EN),
    "pt": _cfg_voz(PIPER_VOZ_PT),
    "es": _cfg_voz(PIPER_VOZ_ES),
}

PIPER_MAX_CHARS = 200

IDIOMAS_TRADUCCION = {
    "Inglés":    "en",
    "Portugués": "pt",
    "Español":   "es",
    "Francés":   "fr",
}

for _d in [MODELS_DIR, VOICES_DIR, PIPER_DIR, TEMP_DIR, OUTPUT_DIR, LOGS_DIR, DATABASE_DIR]:
    os.makedirs(_d, exist_ok=True)
