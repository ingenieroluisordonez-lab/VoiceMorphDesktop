# VoiceMorph Desktop

Aplicación de escritorio para conversión de voz y traducción automática de videos, todo de forma **100% offline** después de la instalación inicial.

## Funcionalidades

- **Conversión de voz** — cambia el timbre de una voz usando modelos RVC o pitch shift simple
- **Traducción al Inglés** — transcribe con Whisper, traduce con Argos Translate y sintetiza con Piper TTS
- **Traducción al Portugués** — mismo pipeline, voz diferente
- **Cola de procesamiento** — procesa múltiples archivos en lote sin supervisión
- **Historial** — registro local de todas las conversiones realizadas
- **GPU/CPU automático** — detecta CUDA y lo usa si está disponible

## Tecnologías

| Componente | Librería |
|---|---|
| Transcripción | [OpenAI Whisper](https://github.com/openai/whisper) large-v3 |
| Conversión de voz | [RVC](https://github.com/RVC-Project/Retrieval-based-Voice-Conversion-WebUI) |
| Traducción offline | [Argos Translate](https://github.com/argosopentech/argos-translate) |
| Síntesis de voz | [Piper TTS](https://github.com/rhasspy/piper) |
| Audio/Video | [FFmpeg](https://ffmpeg.org/) |
| Interfaz | [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) |

## Requisitos

- Python 3.10 o 3.11 (recomendado)
- FFmpeg instalado y en el PATH
- GPU NVIDIA con CUDA (opcional, mejora la velocidad significativamente)

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/ingenieroluisordonez-lab/VoiceMorphDesktop.git
cd VoiceMorphDesktop

# Crear entorno virtual e instalar dependencias
install.bat
```

O manualmente:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

O ejecutar `run.bat`.

### Conversión de voz con RVC

1. Descarga un modelo RVC (`.pth` + `.index` opcional) desde [weights.gg](https://weights.gg) o Hugging Face
2. Coloca los archivos en `models/voices/`
3. Selecciona el modelo en el desplegable
4. Ajusta el tono con el slider si es necesario
5. Selecciona tu archivo y haz clic en **Convertir Voz**

Sin modelo RVC, la app aplica pitch shift simple con FFmpeg.

### Traducción de video

1. Selecciona un video o audio en español
2. Clic en **Traducir Inglés** o **Traducir Portugués**
3. La primera vez descarga el paquete de traducción (~100 MB, requiere internet)
4. El resultado se guarda en la carpeta `output/`

## Formatos soportados

**Video:** `.mp4`, `.avi`, `.mkv`  
**Audio:** `.mp3`, `.wav`

## Estructura del proyecto

```
VoiceMorphDesktop/
├── main.py                  # Punto de entrada
├── config.py                # Configuración central
├── services/
│   ├── ffmpeg_service.py    # Extracción y fusión de audio/video
│   ├── whisper_service.py   # Transcripción automática
│   ├── translation_service.py  # Traducción offline
│   └── voice_service.py     # RVC y Piper TTS
├── ui/
│   └── main_window.py       # Interfaz gráfica
├── database/
│   └── sqlite_manager.py    # Historial de conversiones
├── utils/
│   └── logger.py            # Sistema de logs
└── models/
    ├── voices/              # Modelos RVC (.pth, .index)
    └── piper/               # Modelos Piper TTS (.onnx)
```

## Licencia

MIT
