"""
Herramienta para descargar y cambiar voces de Piper TTS.

Uso:
    venv\Scripts\python.exe descargar_voz.py
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import PIPER_DIR, PIPER_CATALOGO_VOCES, PIPER_VOZ_EN, PIPER_VOZ_PT

BASE_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.py")


def listar_voces():
    print("\n  Voces disponibles en el catálogo:")
    print(f"  {'#':<4} {'Nombre':<30} {'G':<2} {'Cal':<5} Descripción")
    print("  " + "-" * 80)
    for i, (nombre, cfg) in enumerate(PIPER_CATALOGO_VOCES.items(), 1):
        instalada = " [OK]" if os.path.isfile(os.path.join(PIPER_DIR, f"{nombre}.onnx")) else ""
        print(
            f"  {i:<4} {nombre:<30} {cfg['genero']:<2} "
            f"{cfg['calidad']:<5} {cfg['descripcion']}{instalada}"
        )


def descargar_voz(nombre: str):
    if nombre not in PIPER_CATALOGO_VOCES:
        print(f"  ERROR: '{nombre}' no está en el catálogo.")
        return False

    cfg  = PIPER_CATALOGO_VOCES[nombre]
    base = cfg["url_base"]

    archivos = [
        (f"{base}.onnx",      os.path.join(PIPER_DIR, f"{nombre}.onnx")),
        (f"{base}.onnx.json", os.path.join(PIPER_DIR, f"{nombre}.onnx.json")),
    ]

    for url, ruta in archivos:
        if os.path.isfile(ruta):
            print(f"  Ya existe: {os.path.basename(ruta)}")
            continue
        print(f"  Descargando {os.path.basename(ruta)}...")
        try:
            def progreso(bloque, tam_bloque, tam_total):
                if tam_total > 0:
                    pct = min(100, bloque * tam_bloque * 100 // tam_total)
                    print(f"\r  {pct}%", end="", flush=True)

            urllib.request.urlretrieve(url, ruta, reporthook=progreso)
            print(f"\r  Descargado: {os.path.basename(ruta)}")
        except Exception as exc:
            if os.path.isfile(ruta):
                os.remove(ruta)
            print(f"\n  ERROR descargando {url}: {exc}")
            return False

    print(f"  Voz '{nombre}' lista.")
    return True


def cambiar_voz_activa(idioma: str, nombre: str):
    """Edita config.py para cambiar la voz activa."""
    if nombre not in PIPER_CATALOGO_VOCES:
        print(f"  ERROR: '{nombre}' no está en el catálogo.")
        return

    if idioma == "en":
        var = "PIPER_VOZ_EN"
        actual = PIPER_VOZ_EN
    elif idioma == "pt":
        var = "PIPER_VOZ_PT"
        actual = PIPER_VOZ_PT
    else:
        print(f"  Idioma '{idioma}' no soportado (usa 'en' o 'pt').")
        return

    with open(BASE_CONFIG, "r", encoding="utf-8") as f:
        contenido = f.read()

    nuevo = contenido.replace(
        f'{var} = "{actual}"',
        f'{var} = "{nombre}"',
    )

    if nuevo == contenido:
        print(f"  No se encontró '{var} = \"{actual}\"' en config.py")
        return

    with open(BASE_CONFIG, "w", encoding="utf-8") as f:
        f.write(nuevo)

    print(f"  config.py actualizado: {var} = \"{nombre}\"")
    print(f"  Reinicia la app para usar la nueva voz.")


def menu():
    print("\n" + "=" * 60)
    print("   VoiceMorph — Gestión de Voces Piper TTS")
    print("=" * 60)
    print(f"  Voz inglés activa:    {PIPER_VOZ_EN}")
    print(f"  Voz portugués activa: {PIPER_VOZ_PT}")

    while True:
        print("\n  Opciones:")
        print("  [1] Ver catálogo de voces")
        print("  [2] Descargar una voz")
        print("  [3] Cambiar voz de inglés")
        print("  [4] Cambiar voz de portugués")
        print("  [5] Salir")
        print()

        opcion = input("  Selecciona opción (1-5): ").strip()

        if opcion == "1":
            listar_voces()

        elif opcion == "2":
            listar_voces()
            nombre = input("\n  Nombre de la voz a descargar: ").strip()
            descargar_voz(nombre)

        elif opcion == "3":
            listar_voces()
            nombre = input("\n  Nombre de la voz inglés a activar: ").strip()
            if descargar_voz(nombre):
                cambiar_voz_activa("en", nombre)

        elif opcion == "4":
            listar_voces()
            nombre = input("\n  Nombre de la voz portugués a activar: ").strip()
            if descargar_voz(nombre):
                cambiar_voz_activa("pt", nombre)

        elif opcion == "5":
            break
        else:
            print("  Opción no válida.")


if __name__ == "__main__":
    menu()
