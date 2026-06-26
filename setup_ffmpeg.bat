@echo off

echo.
echo  VoiceMorph Desktop - Instalador de FFmpeg
echo  ==========================================
echo.

:: Verificar si FFmpeg ya esta disponible
ffmpeg -version >nul 2>&1
if not errorlevel 1 (
    echo  FFmpeg ya esta instalado.
    echo.
    ffmpeg -version 2>&1 | findstr "ffmpeg version"
    echo.
    echo  Presiona cualquier tecla para salir...
    pause >nul
    exit /b 0
)

echo  Intentando instalar con winget...
winget install --id Gyan.FFmpeg -e --source winget
if not errorlevel 1 (
    echo.
    echo  FFmpeg instalado con winget.
    echo  Reinicia la terminal y ejecuta: python main.py
    echo.
    pause
    exit /b 0
)

echo.
echo  winget no disponible. Instalando manualmente...
echo.

set "FFMPEG_DIR=%USERPROFILE%\ffmpeg"
set "FFMPEG_ZIP=%TEMP%\ffmpeg.zip"

echo  Descargando FFmpeg en %FFMPEG_ZIP%...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%FFMPEG_ZIP%' -UseBasicParsing"

if not exist "%FFMPEG_ZIP%" (
    echo.
    echo  ERROR: No se pudo descargar FFmpeg.
    echo  Descargalo manualmente desde: https://www.gyan.dev/ffmpeg/builds/
    echo  Extrae el zip y agrega la carpeta bin\ al PATH.
    pause
    exit /b 1
)

echo  Descomprimiendo...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Path '%FFMPEG_ZIP%' -DestinationPath '%FFMPEG_DIR%' -Force"

:: Buscar la carpeta bin dentro del directorio extraido
for /d %%d in ("%FFMPEG_DIR%\ffmpeg-*") do (
    set "FFMPEG_BIN=%%d\bin"
)

if not defined FFMPEG_BIN (
    echo  ERROR: No se encontro la carpeta bin dentro del zip.
    pause
    exit /b 1
)

:: Agregar al PATH del usuario de forma permanente
powershell -NoProfile -Command "[System.Environment]::SetEnvironmentVariable('PATH', [System.Environment]::GetEnvironmentVariable('PATH','User') + ';%FFMPEG_BIN%', 'User')"

set "PATH=%PATH%;%FFMPEG_BIN%"

echo.
ffmpeg -version 2>&1 | findstr "ffmpeg version"
echo.
echo  FFmpeg instalado en: %FFMPEG_BIN%
echo  Reinicia la terminal antes de ejecutar python main.py
echo.
pause
