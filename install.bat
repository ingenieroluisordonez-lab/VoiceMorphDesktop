@echo off

echo.
echo  VoiceMorph Desktop - Instalador
echo  ================================
echo.

:: Verificar Python
echo [1/7] Verificando Python...
python --version 2>nul
if errorlevel 1 (
    echo.
    echo  ERROR: Python no encontrado.
    echo  Descarga Python 3.12 o 3.13 desde: https://www.python.org/downloads/
    echo  Marca "Add to PATH" durante la instalacion.
    pause
    exit /b 1
)

:: Crear venv si no existe
if not exist "venv\Scripts\python.exe" (
    echo.
    echo [2/7] Creando entorno virtual...
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR creando venv.
        pause
        exit /b 1
    )
) else (
    echo.
    echo [2/7] venv existente detectado, se reutiliza.
)

:: Usar python del venv a partir de aqui
set "PY=venv\Scripts\python.exe"

:: Actualizar pip
echo.
echo [3/7] Actualizando pip...
"%PY%" -m pip install --upgrade pip

:: PyTorch con CUDA
echo.
echo [4/7] Instalando PyTorch con CUDA 12.1...
echo  (Si tienes otra version de CUDA visita pytorch.org/get-started/locally)
echo.
"%PY%" -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (
    echo  CUDA fallo, instalando version CPU...
    "%PY%" -m pip install torch torchaudio
)

:: Dependencias generales
echo.
echo [5/7] Instalando dependencias...
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo  ERROR en pip install. Verifica conexion a internet.
    pause
    exit /b 1
)

:: rvc-python con --no-deps (sus pins fairseq y faiss-cpu==1.7.3 rompen
:: en Python 3.13; las deps reales las puso requirements.txt arriba).
echo.
echo [6/7] Instalando rvc-python (sin sus deps por incompatibilidad de pins)...
"%PY%" -m pip install --no-deps rvc-python==0.1.5
if errorlevel 1 (
    echo  ERROR instalando rvc-python.
    pause
    exit /b 1
)

:: Paquetes de traduccion offline
echo.
echo [7/7] Descargando paquetes de traduccion offline (es-en, es-pt)...
echo  Requiere internet esta primera vez (~100 MB por par de idiomas).
"%PY%" -c "import argostranslate.package as p; p.update_package_index(); pkgs=p.get_available_packages(); [p.install_from_path(x.download()) for par in [('es','en'),('es','pt')] for x in pkgs if x.from_code==par[0] and x.to_code==par[1]]"

:: Carpetas
echo.
echo  Creando carpetas...
if not exist "models\voices"  mkdir "models\voices"
if not exist "models\piper"   mkdir "models\piper"
if not exist "temp"           mkdir "temp"
if not exist "output"         mkdir "output"
if not exist "logs"           mkdir "logs"
if not exist "database"       mkdir "database"

:: Verificacion final
echo.
echo  Verificando instalacion...
"%PY%" -c "import customtkinter, whisper, piper, argostranslate, librosa, transformers; import torch; print('  torch=' + torch.__version__ + '  cuda=' + str(torch.cuda.is_available()))"
"%PY%" -c "from rvc_python.infer import RVCInference" 2>nul && echo   rvc-python OK || echo   rvc-python aun no importable (se cargara con el parche fairseq en runtime)

echo.
echo  ================================
echo   Instalacion completada!
echo.
echo   Para ejecutar:  run.bat   (o:  venv\Scripts\python.exe main.py)
echo.
echo   Para voz femenina con calidad:
echo   Coloca archivos .pth en models\voices\
echo  ================================
echo.
pause
