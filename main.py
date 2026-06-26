"""
VoiceMorph Desktop — Punto de entrada.

Uso:
    python main.py
"""
import sys
import os

# Asegura que el directorio raíz esté en el path antes de cualquier import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from utils.logger import setup_logger

logger = setup_logger("main")


def main():
    logger.info("VoiceMorph Desktop iniciando")

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    try:
        from ui.main_window import MainWindow
        app = MainWindow()
        app.mainloop()
    except Exception as exc:
        logger.critical("Error fatal al iniciar: %s", exc, exc_info=True)
        # Mostrar error visual aunque falle CustomTkinter
        try:
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "Error Fatal",
                f"VoiceMorph Desktop no pudo iniciarse:\n\n{exc}\n\n"
                "Revisa logs/ para más detalles.",
            )
        except Exception:
            print(f"ERROR FATAL: {exc}")
        sys.exit(1)

    logger.info("VoiceMorph Desktop cerrado")


if __name__ == "__main__":
    main()
