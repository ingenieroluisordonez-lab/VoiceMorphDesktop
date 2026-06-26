# VoiceMorph Desktop — Manual de Instalación y Uso

## Requisitos del Sistema

| Componente | Mínimo | Recomendado |
|------------|--------|-------------|
| SO | Windows 10 64-bit | Windows 11 |
| Python | 3.12 | 3.12 |
| RAM | 8 GB | 16 GB |
| GPU | Sin GPU (CPU) | NVIDIA RTX con ≥ 6 GB VRAM |
| VRAM | — | 8 GB para Whisper large-v3 |
| Disco | 15 GB libres | 25 GB libres |
| Internet | Solo instalación | Solo instalación |

> **Con GPU NVIDIA**: el procesamiento es 5-10× más rápido.  
> **Sin GPU**: funciona pero puede tardar varios minutos por archivo.

---

## Instalación Paso a Paso

### 1. Instalar Python 3.12

1. Descarga desde [python.org/downloads](https://www.python.org/downloads/)
2. En el instalador, **marca "Add Python to PATH"**
3. Verifica en la terminal:
   ```
   python --version
   ```

### 2. Instalar FFmpeg

Opción A — Script automático (recomendado):
```
setup_ffmpeg.bat
```

Opción B — Manual:
1. Descarga desde [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) → `ffmpeg-release-essentials.zip`
2. Extrae en `C:\ffmpeg\`
3. Agrega `C:\ffmpeg\bin` a la variable de entorno `PATH`
4. Verifica: `ffmpeg -version`

### 3. Instalar Drivers NVIDIA + CUDA (si tienes GPU)

1. Actualiza los drivers NVIDIA desde [nvidia.com/drivers](https://www.nvidia.com/drivers)
2. El soporte CUDA lo incluye PyTorch automáticamente — **no necesitas instalar CUDA Toolkit por separado**

### 4. Instalar VoiceMorph Desktop

```
install.bat
```

Esto instala:
- PyTorch con CUDA 12.1
- Whisper Large-v3
- RVC-Python
- XTTS-v2
- Argos Translate + paquetes es→en y es→pt

> La primera ejecución de `install.bat` puede tardar **15-30 minutos** por las descargas.

### 5. Ejecutar

```
python main.py
```

---

## Agregar Modelos de Voz RVC

La conversión a voz femenina usa modelos RVC (`.pth` + `.index`).

### ¿Dónde obtener modelos?
- [weights.gg](https://weights.gg) — buscá "female voice" o "anime"
- [huggingface.co](https://huggingface.co) — búsqueda: "rvc model female"
- Comunidad RVC en Discord

### Cómo instalar un modelo
1. Descarga el archivo `.pth` (obligatorio) y `.index` (opcional, mejora la calidad)
2. Cópialos en la carpeta:
   ```
   VoiceMorphDesktop\models\voices\
   ```
3. En la aplicación, haz clic en **"↺ Actualizar"** para que aparezca en el selector

### Modelos recomendados por caso de uso

| Uso | Tipo de modelo |
|-----|---------------|
| Voz femenina natural | Modelos entrenados con voces reales |
| Anime/personajes | Modelos de voces de anime |
| Voz masculina → femenina | Cualquier modelo femenino, pitch +5 a +7 |

---

## Uso de la Aplicación

### Flujo básico

1. **Seleccionar Archivo** — MP4, AVI, MKV, MP3 o WAV
2. **Elegir modelo RVC** (o usar pitch shift básico si no tienes uno)
3. **Ajustar semitonos** — +6 es el valor estándar para masculino → femenino
4. Hacer clic en la acción deseada

### Acciones disponibles

#### Voz Femenina
Convierte la voz del audio original usando RVC o pitch shift.  
- **Con modelo RVC**: preserva timbre, emociones y pausas
- **Sin modelo (pitch shift)**: conversión básica, menos natural

Salida: `output/nombre_femenino.mp4` o `output/nombre_femenino.wav`

#### Traducir a Inglés / Portugués
Pipeline completo:
```
Audio original
    ↓ FFmpeg
Audio WAV
    ↓ Whisper Large-v3
Transcripción en español
    ↓ Argos Translate (offline)
Texto traducido
    ↓ XTTS-v2
Audio en el idioma destino
    ↓ FFmpeg
Video final con nueva pista de audio
```

> **Primera traducción**: instala los paquetes de idioma (~100 MB cada uno, requiere internet).  
> **Siguientes veces**: completamente offline.

---

## Solución de Problemas

### `FFmpeg no encontrado`
```
Ejecuta setup_ffmpeg.bat y reinicia la terminal.
```

### `CUDA out of memory`
Opciones:
1. Cierra otras aplicaciones que usen la GPU
2. Usa un modelo Whisper más pequeño editando `config.py`:
   ```python
   WHISPER_MODEL = "medium"  # en lugar de "large-v3"
   ```
3. Si persiste, el sistema usará CPU automáticamente

### `rvc-python no instalado`
```
pip install rvc-python
```
Si falla la instalación de rvc-python, la aplicación usa pitch shift básico como fallback.

### Error al cargar XTTS-v2
La primera carga descarga ~2 GB del modelo. Requiere internet y puede tardar varios minutos.
```
pip install TTS --upgrade
```

### La traducción suena robótica
- XTTS-v2 necesita al menos 6 segundos de audio de referencia de buena calidad
- Usa archivos de audio con voz clara y sin música de fondo

### El historial no se guarda
Verifica que la carpeta `database/` tenga permisos de escritura.

---

## Estructura de Carpetas

```
VoiceMorphDesktop/
├── main.py               ← Punto de entrada
├── config.py             ← Configuración global
├── requirements.txt
├── install.bat           ← Instalador automático
├── setup_ffmpeg.bat      ← Instala FFmpeg
│
├── ui/
│   └── main_window.py    ← Interfaz gráfica
│
├── services/
│   ├── ffmpeg_service.py
│   ├── whisper_service.py
│   ├── translation_service.py
│   └── voice_service.py
│
├── database/
│   ├── sqlite_manager.py
│   └── voicemorph.db     ← Se crea automáticamente
│
├── utils/
│   └── logger.py
│
├── models/
│   └── voices/           ← Coloca aquí tus modelos .pth
│
├── temp/                 ← Archivos temporales (se limpian solos)
├── output/               ← Archivos de salida
└── logs/                 ← Logs diarios
```

---

## Configuración Avanzada (`config.py`)

```python
# Cambiar modelo Whisper
WHISPER_MODEL = "medium"       # small | medium | large-v2 | large-v3

# Semitonos por defecto para voz femenina
RVC_F0_UP_KEY = 6              # +4 a +8 es el rango habitual

# Método de extracción de pitch RVC
RVC_F0_METHOD = "rmvpe"        # rmvpe (más preciso) | pm | harvest | crepe

# Máximo de caracteres por llamada a XTTS
XTTS_MAX_CHARS = 380
```

---

## Licencia y Uso

Aplicación diseñada para uso interno exclusivo.  
Los modelos de terceros (Whisper, XTTS-v2, RVC) tienen sus propias licencias.
