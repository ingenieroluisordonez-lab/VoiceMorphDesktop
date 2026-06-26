import os
import shutil
import threading
from typing import Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

from services.ffmpeg_service    import FFmpegService
from services.whisper_service   import WhisperService
from services.translation_service import TranslationService
from services.voice_service     import VoiceService
from database.sqlite_manager    import SQLiteManager
from utils.logger               import setup_logger
from config import (
    SUPPORTED_ALL, OUTPUT_DIR, TEMP_DIR, VOICES_DIR, DEVICE,
)

logger = setup_logger("main_window")


class MainWindow(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("VoiceMorph Desktop")
        self.geometry("820x780")
        self.minsize(720, 650)

        self._ruta_archivo: Optional[str] = None
        self._info_archivo: Optional[dict] = None
        self._proceso_activo = False
        self._cancel = threading.Event()
        self._queue: list[dict] = []

        self._ffmpeg = FFmpegService()
        self._whisper = WhisperService()
        self._translator = TranslationService()
        self._voice = VoiceService()
        self._db = SQLiteManager()

        self._build_ui()
        self._refresh_models()
        self._refresh_history()
        self._show_gpu_info()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        scroll.grid_columnconfigure(0, weight=1)
        self._scroll = scroll

        # Título
        ctk.CTkLabel(
            scroll, text="VoiceMorph Desktop",
            font=ctk.CTkFont(size=26, weight="bold"),
        ).grid(row=0, column=0, pady=(12, 2))

        self._lbl_gpu = ctk.CTkLabel(
            scroll,
            text=f"Dispositivo: {DEVICE.upper()} | Cargando info…",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        self._lbl_gpu.grid(row=1, column=0, pady=(0, 12))

        # Sección Archivo
        self._build_section_archivo(scroll, row=2)

        # Sección Modelo RVC
        self._build_section_modelo(scroll, row=3)

        # Sección Botones
        self._build_section_botones(scroll, row=4)

        # Sección Cola (lote nocturno)
        self._build_section_cola(scroll, row=5)

        # Sección Progreso
        self._build_section_progreso(scroll, row=6)

        # Sección Historial
        self._build_section_historial(scroll, row=7)


    def _build_section_archivo(self, parent, row):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        f.grid_columnconfigure(1, weight=1)

        self._section_label(f, "ARCHIVO", row=0)

        ctk.CTkButton(
            f, text="📂  Seleccionar Archivo",
            command=self._select_file, width=180,
        ).grid(row=1, column=0, padx=14, pady=6, sticky="w")

        self._lbl_nombre = ctk.CTkLabel(
            f, text="Ningún archivo seleccionado", text_color="gray"
        )
        self._lbl_nombre.grid(row=1, column=1, padx=8, sticky="w")

        info_row = ctk.CTkFrame(f, fg_color="transparent")
        info_row.grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 10), sticky="w")

        self._lbl_dur  = ctk.CTkLabel(info_row, text="Duración: —", text_color="gray")
        self._lbl_size = ctk.CTkLabel(info_row, text="Tamaño: —", text_color="gray")
        self._lbl_dur.grid(row=0, column=0, padx=(0, 24))
        self._lbl_size.grid(row=0, column=1)


    def _build_section_modelo(self, parent, row):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        f.grid_columnconfigure(1, weight=1)

        self._section_label(f, "CONVERSION DE VOZ", row=0)

        # Selector de modelo RVC
        sel_row = ctk.CTkFrame(f, fg_color="transparent")
        sel_row.grid(row=1, column=0, columnspan=2, padx=14, pady=(2, 2), sticky="ew")
        sel_row.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(sel_row, text="Modelo RVC:").grid(row=0, column=0, padx=(0, 8))

        self._cmb_modelo = ctk.CTkComboBox(
            sel_row,
            values=["— Sin modelo (pitch shift) —"],
            width=280,
            command=self._on_modelo_change,
        )
        self._cmb_modelo.set("— Sin modelo (pitch shift) —")
        self._cmb_modelo.grid(row=0, column=1, sticky="ew")

        ctk.CTkButton(
            sel_row, text="↻", width=32,
            command=self._refresh_models,
            font=ctk.CTkFont(size=14),
        ).grid(row=0, column=2, padx=(6, 0))

        # Ayuda / ruta
        ctk.CTkLabel(
            f,
            text=f"Coloca archivos .pth (+ .index opcional) en:  {VOICES_DIR}",
            font=ctk.CTkFont(size=10), text_color="gray",
        ).grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 4), sticky="w")

        ctk.CTkLabel(
            f,
            text="Descarga modelos en weights.gg o huggingface.co (busca 'RVC voice model')",
            font=ctk.CTkFont(size=10), text_color="gray",
        ).grid(row=3, column=0, columnspan=2, padx=14, pady=(0, 6), sticky="w")

        # Ajuste de tono (opcional con RVC, principal sin modelo)
        pitch_row = ctk.CTkFrame(f, fg_color="transparent")
        pitch_row.grid(row=4, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")

        self._lbl_pitch_titulo = ctk.CTkLabel(pitch_row, text="Ajuste de tono:")
        self._lbl_pitch_titulo.grid(row=0, column=0, padx=(0, 6))

        self._slider_pitch = ctk.CTkSlider(
            pitch_row, from_=-12, to=12, number_of_steps=24,
            width=200, command=self._on_pitch_change,
        )
        self._slider_pitch.set(6)
        self._slider_pitch.grid(row=0, column=1, padx=4)

        self._lbl_pitch = ctk.CTkLabel(pitch_row, text="+6  (masculino→femenino)")
        self._lbl_pitch.grid(row=0, column=2, padx=6)


    def _build_section_botones(self, parent, row):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        f.grid_columnconfigure((0, 1, 2), weight=1)

        self._section_label(f, "CONVERSIONES", row=0)

        btn_cfg = dict(height=64, font=ctk.CTkFont(size=13, weight="bold"))

        self._btn_fem = ctk.CTkButton(
            f, text="🎙  Convertir\nVoz",
            fg_color="#7C3AED", hover_color="#6D28D9",
            command=self._do_female, **btn_cfg,
        )
        self._btn_fem.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

        self._btn_en = ctk.CTkButton(
            f, text="🇺🇸  Traducir\nInglés",
            fg_color="#0369A1", hover_color="#075985",
            command=self._do_english, **btn_cfg,
        )
        self._btn_en.grid(row=1, column=1, padx=10, pady=10, sticky="ew")

        self._btn_pt = ctk.CTkButton(
            f, text="🇧🇷  Traducir\nPortugués",
            fg_color="#065F46", hover_color="#047857",
            command=self._do_portuguese, **btn_cfg,
        )
        self._btn_pt.grid(row=1, column=2, padx=10, pady=10, sticky="ew")

        self._btn_cancel = ctk.CTkButton(
            f, text="✕  Cancelar proceso",
            fg_color="#B91C1C", hover_color="#991B1B",
            command=self._do_cancel,
            height=34, state="disabled",
        )
        self._btn_cancel.grid(
            row=2, column=0, columnspan=3,
            padx=10, pady=(0, 10), sticky="ew",
        )

        self._action_buttons = [self._btn_fem, self._btn_en, self._btn_pt]


    def _build_section_cola(self, parent, row):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        f.grid_columnconfigure(0, weight=1)

        self._section_label(f, "COLA DE PROCESAMIENTO (lote nocturno)", row=0)

        top = ctk.CTkFrame(f, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew", padx=14, pady=(2, 4))
        top.grid_columnconfigure(2, weight=1)

        ctk.CTkLabel(top, text="Acción:").grid(row=0, column=0, padx=(0, 8))

        self._cmb_accion_cola = ctk.CTkComboBox(
            top,
            values=["Voz Femenina", "Traducir Inglés", "Traducir Portugués"],
            width=200,
            state="readonly",
        )
        self._cmb_accion_cola.set("Traducir Inglés")
        self._cmb_accion_cola.grid(row=0, column=1, padx=(0, 8))

        ctk.CTkButton(
            top, text="➕  Agregar archivos",
            command=self._add_to_queue, width=180,
        ).grid(row=0, column=2, sticky="e")

        self._txt_cola = ctk.CTkTextbox(
            f, height=140, state="disabled",
            font=ctk.CTkFont(family="Consolas", size=11),
        )
        self._txt_cola.grid(row=2, column=0, padx=14, pady=4, sticky="ew")

        bot = ctk.CTkFrame(f, fg_color="transparent")
        bot.grid(row=3, column=0, sticky="ew", padx=14, pady=(0, 10))
        bot.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(
            bot, text="🗑  Limpiar cola",
            command=self._clear_queue, fg_color="gray40", height=36,
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        self._btn_proc_cola = ctk.CTkButton(
            bot, text="▶  Procesar cola",
            command=self._process_queue,
            fg_color="#16A34A", hover_color="#15803D",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=36,
        )
        self._btn_proc_cola.grid(row=0, column=1, padx=(4, 0), sticky="ew")

        self._refresh_queue()


    def _build_section_progreso(self, parent, row):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        f.grid_columnconfigure(0, weight=1)

        self._section_label(f, "ESTADO", row=0)

        self._lbl_status = ctk.CTkLabel(
            f, text="Listo", text_color="#22C55E",
            font=ctk.CTkFont(size=13),
        )
        self._lbl_status.grid(row=1, column=0, padx=14, pady=2, sticky="w")

        self._progressbar = ctk.CTkProgressBar(f, mode="determinate")
        self._progressbar.set(0)
        self._progressbar.grid(row=2, column=0, padx=14, pady=(4, 4), sticky="ew")

        self._lbl_output = ctk.CTkLabel(
            f, text="", text_color="#7DD3FC",
            font=ctk.CTkFont(size=11),
        )
        self._lbl_output.grid(row=3, column=0, padx=14, pady=(0, 10), sticky="w")


    def _build_section_historial(self, parent, row):
        f = ctk.CTkFrame(parent)
        f.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        f.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(f, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 4))
        header.grid_columnconfigure(0, weight=1)

        self._section_label(header, "HISTORIAL", row=0, col=0)

        ctk.CTkButton(
            header, text="🗑  Limpiar",
            command=self._clear_history,
            width=90, height=26, fg_color="gray40",
        ).grid(row=0, column=1)

        self._txt_history = ctk.CTkTextbox(f, height=160, state="disabled")
        self._txt_history.grid(row=1, column=0, padx=14, pady=(0, 12), sticky="ew")

    # Helpers UI
    @staticmethod
    def _section_label(parent, texto: str, row: int, col: int = 0):
        ctk.CTkLabel(
            parent, text=texto,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=row, column=col, columnspan=3, padx=14, pady=(10, 4), sticky="w")
    # GPU info

    def _show_gpu_info(self):
        try:
            import torch
            if torch.cuda.is_available():
                name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
                txt  = f"GPU: {name}  ({vram:.1f} GB VRAM)  |  CUDA habilitado"
                logger.info(txt)
            else:
                txt = "Sin GPU NVIDIA detectada — usando CPU"
                logger.info(txt)
            self._lbl_gpu.configure(text=txt)
        except Exception:
            pass
    # Archivo

    def _select_file(self):
        ext = " ".join(f"*{e}" for e in SUPPORTED_ALL)
        ruta = filedialog.askopenfilename(
            title="Seleccionar archivo multimedia",
            filetypes=[
                ("Multimedia", ext),
                ("Videos",     "*.mp4 *.avi *.mkv"),
                ("Audios",     "*.mp3 *.wav"),
                ("Todos",      "*.*"),
            ],
        )
        if ruta:
            self._load_file(ruta)

    def _load_file(self, ruta: str):
        try:
            info = self._ffmpeg.info(ruta)
            self._ruta_archivo = ruta
            self._info_archivo = info

            self._lbl_nombre.configure(text=info["nombre"], text_color="white")
            self._lbl_dur.configure(
                text=f"Duración: {info['duracion_fmt']}", text_color="white"
            )
            self._lbl_size.configure(
                text=f"Tamaño: {info['tamanio_mb']} MB", text_color="white"
            )
            logger.info("Archivo cargado: %s", ruta)
        except Exception as exc:
            messagebox.showerror("Error al cargar", str(exc))
            logger.error("Error cargando archivo: %s", exc)

    def _refresh_models(self):
        modelos = self._voice.listar_modelos()
        opciones = ["— Sin modelo (pitch shift) —"] + [m["nombre"] for m in modelos]
        self._cmb_modelo.configure(values=opciones)
        if modelos:
            logger.info("Modelos RVC encontrados: %s", [m["nombre"] for m in modelos])
        else:
            self._cmb_modelo.set("— Sin modelo (pitch shift) —")

    def _on_modelo_change(self, valor: str):
        tiene_modelo = valor != "— Sin modelo (pitch shift) —"
        if tiene_modelo:
            # Con RVC el tono es ajuste adicional (0 = sin cambio extra)
            self._slider_pitch.set(0)
            self._lbl_pitch.configure(text="0  (sin ajuste extra de tono)")
            self._lbl_pitch_titulo.configure(text="Ajuste de tono (+/-):")
        else:
            self._slider_pitch.set(6)
            self._lbl_pitch.configure(text="+6  (masculino→femenino)")
            self._lbl_pitch_titulo.configure(text="Ajuste de tono:")

    def _on_pitch_change(self, val: float):
        st = int(val)
        signo = "+" if st >= 0 else ""
        tiene_modelo = (
            hasattr(self, "_cmb_modelo") and
            self._cmb_modelo.get() != "— Sin modelo (pitch shift) —"
        )
        if tiene_modelo:
            nota = "  (ajuste sobre el modelo RVC)" if st != 0 else "  (sin ajuste extra)"
        else:
            nota = "  (masculino→femenino)" if st == 6 else ""
        self._lbl_pitch.configure(text=f"{signo}{st}{nota}")
    # Control de procesos

    def _check_file(self) -> bool:
        if not self._ruta_archivo:
            messagebox.showwarning("Sin archivo", "Selecciona un archivo primero.")
            return False
        return True

    def _begin_process(self, nombre: str):
        self._proceso_activo = True
        self._cancel.clear()
        for b in self._action_buttons:
            b.configure(state="disabled")
        if hasattr(self, "_btn_proc_cola"):
            self._btn_proc_cola.configure(state="disabled")
        self._btn_cancel.configure(state="normal")
        self._lbl_status.configure(text=f"⏳  {nombre}…", text_color="#FCD34D")
        self._progressbar.set(0)
        self._lbl_output.configure(text="")

    def _end_process(self, ok: bool, msg: str, ruta_out: Optional[str] = None):
        self._proceso_activo = False
        for b in self._action_buttons:
            b.configure(state="normal")
        if hasattr(self, "_btn_proc_cola"):
            self._btn_proc_cola.configure(state="normal")
        self._btn_cancel.configure(state="disabled")

        if ok:
            self._lbl_status.configure(text=f"✓  {msg}", text_color="#22C55E")
            self._progressbar.set(1.0)
            if ruta_out:
                self._lbl_output.configure(text=f"Guardado: {ruta_out}")
            self._refresh_history()
        else:
            self._lbl_status.configure(text=f"✗  {msg}", text_color="#F87171")
            self._progressbar.set(0)

    def _cb(self, val: float, msg: str):
        """Callback de progreso — thread-safe."""
        self.after(0, lambda: self._progressbar.set(val))
        self.after(0, lambda: self._lbl_status.configure(
            text=msg, text_color="#FCD34D"
        ))

    def _do_cancel(self):
        if self._proceso_activo:
            self._cancel.set()
            self._lbl_status.configure(text="Cancelando…", text_color="#FB923C")
            logger.info("Cancelación solicitada")
    # Conversión a voz femenina

    def _do_female(self):
        if not self._check_file():
            return
        modelo = self._cmb_modelo.get()
        nombre = f"RVC ({modelo})" if modelo != "— Sin modelo (pitch shift) —" else "Pitch Shift"
        self._begin_process(f"Convirtiendo voz — {nombre}")
        threading.Thread(target=self._run_female, daemon=True).start()

    def _run_female(self):
        try:
            ruta_out = self._pipeline_voz(self._ruta_archivo, self._info_archivo)
            self.after(0, lambda: self._end_process(True, "Conversión completada", ruta_out))
        except InterruptedError:
            self.after(0, lambda: self._end_process(False, "Proceso cancelado"))
        except Exception as exc:
            logger.error("Error conversión de voz: %s", exc, exc_info=True)
            msg = str(exc)
            self.after(0, lambda: self._end_process(False, f"Error: {msg[:80]}"))
            self.after(0, lambda: messagebox.showerror("Error", msg))

    def _pipeline_voz(self, src: str, info: dict) -> str:
        """Conversión de voz (RVC o pitch shift). Reusable en single-file y cola."""
        es_video = self._ffmpeg.es_video(src)
        base     = os.path.splitext(os.path.basename(src))[0]
        ext_out  = ".mp4" if es_video else ".wav"

        modelo_sel = self._cmb_modelo.get()
        usa_rvc    = modelo_sel != "— Sin modelo (pitch shift) —"
        sufijo     = "_rvc" if usa_rvc else "_pitch"
        ruta_out   = os.path.join(OUTPUT_DIR, f"{base}{sufijo}{ext_out}")

        if es_video:
            audio_src = self._ffmpeg.extraer_audio(src, cb=self._cb)
        else:
            audio_src = src

        if self._cancel.is_set():
            raise InterruptedError()

        semitonos        = int(self._slider_pitch.get())
        audio_convertido = os.path.join(TEMP_DIR, f"{base}{sufijo}.wav")

        if usa_rvc:
            modelos     = self._voice.listar_modelos()
            modelo_info = next(
                (m for m in modelos if m["nombre"] == modelo_sel), None
            )
            if modelo_info is None:
                raise RuntimeError(f"Modelo '{modelo_sel}' no encontrado en disco.")

            self._voice.convertir_rvc(
                ruta_audio=audio_src,
                ruta_salida=audio_convertido,
                ruta_modelo=modelo_info["ruta_pth"],
                ruta_index=modelo_info.get("ruta_index"),
                pitch_semitonos=semitonos,
                cb=self._cb,
                cancel=self._cancel,
            )
            tipo_conv = f"RVC ({modelo_sel})"
        else:
            self._voice.convertir_pitch(
                ruta_audio=audio_src,
                ruta_salida=audio_convertido,
                semitonos=semitonos,
                cb=self._cb,
                cancel=self._cancel,
            )
            tipo_conv = f"Pitch Shift ({semitonos:+d} st)"

        if self._cancel.is_set():
            raise InterruptedError()

        if es_video:
            self._ffmpeg.fusionar_audio_video(
                src, audio_convertido, ruta_out, cb=self._cb
            )
        else:
            shutil.copy2(audio_convertido, ruta_out)

        self._db.agregar(
            src, tipo_conv,
            archivo_resultado=ruta_out,
            duracion_seg=info.get("duracion") if info else None,
        )
        return ruta_out
    # Traducción

    def _do_english(self):
        if not self._check_file():
            return
        self._begin_process("Traducción al Inglés")
        threading.Thread(
            target=self._run_translation, args=("en", "inglés"), daemon=True
        ).start()

    def _do_portuguese(self):
        if not self._check_file():
            return
        self._begin_process("Traducción al Portugués")
        threading.Thread(
            target=self._run_translation, args=("pt", "portugues"), daemon=True
        ).start()

    def _run_translation(self, lang_code: str, lang_name: str):
        try:
            ruta_out = self._pipeline_traduccion(
                self._ruta_archivo, self._info_archivo, lang_code, lang_name,
            )
            self.after(0, lambda: self._end_process(
                True, f"Traducción al {lang_name} completada", ruta_out
            ))
        except InterruptedError:
            self.after(0, lambda: self._end_process(False, "Proceso cancelado"))
        except Exception as exc:
            logger.error("Error traducción: %s", exc, exc_info=True)
            msg = str(exc)
            self.after(0, lambda: self._end_process(False, f"Error: {msg[:80]}"))
            self.after(0, lambda: messagebox.showerror("Error", msg))

    def _pipeline_traduccion(
        self, src: str, info: dict, lang_code: str, lang_name: str,
    ) -> str:
        """Pipeline: audio → Whisper → Argos Translate → Piper TTS → video."""
        es_video = self._ffmpeg.es_video(src)
        base     = os.path.splitext(os.path.basename(src))[0]
        ext_out  = ".mp4" if es_video else ".wav"
        ruta_out = os.path.join(OUTPUT_DIR, f"{base}_{lang_name}{ext_out}")

        if es_video:
            audio_src = self._ffmpeg.extraer_audio(src, cb=self._cb)
        else:
            audio_src = src

        if self._cancel.is_set():
            raise InterruptedError()

        self._cb(0.08, "Transcribiendo con Whisper…")
        resultado = self._whisper.transcribir(
            audio_src, idioma="es", cb=self._cb, cancel=self._cancel
        )

        if self._cancel.is_set():
            raise InterruptedError()

        if not self._translator.paquete_instalado("es", lang_code):
            self._cb(0.70, "Instalando paquete de traducción (requiere internet)…")
            self._translator.instalar_paquete("es", lang_code, cb=self._cb)

        self._cb(0.72, f"Traduciendo al {lang_name}…")
        segs_trad = self._translator.traducir_segmentos(
            resultado["segments"],
            from_code="es",
            to_code=lang_code,
            cb=self._cb,
        )

        if self._cancel.is_set():
            raise InterruptedError()

        self._cb(0.80, f"Sintetizando voz en {lang_name} (Piper TTS)…")
        texto_trad = " ".join(s["text"] for s in segs_trad).strip()
        audio_tts  = os.path.join(TEMP_DIR, f"{base}_{lang_name}.wav")

        self._voice.sintetizar(
            texto=texto_trad,
            ruta_salida=audio_tts,
            idioma=lang_code,
            cb=self._cb,
            cancel=self._cancel,
        )

        if self._cancel.is_set():
            raise InterruptedError()

        if es_video:
            self._ffmpeg.fusionar_audio_video(
                src, audio_tts, ruta_out, cb=self._cb
            )
        else:
            shutil.copy2(audio_tts, ruta_out)

        self._db.agregar(
            src, f"Traducción {lang_name.capitalize()}",
            archivo_resultado=ruta_out,
            duracion_seg=info.get("duracion") if info else None,
        )
        return ruta_out
    # Cola de procesamiento (modo lote)

    def _add_to_queue(self):
        accion = self._cmb_accion_cola.get()
        ext = " ".join(f"*{e}" for e in SUPPORTED_ALL)
        rutas = filedialog.askopenfilenames(
            title="Seleccionar archivos para la cola",
            filetypes=[
                ("Multimedia", ext),
                ("Videos",     "*.mp4 *.avi *.mkv"),
                ("Audios",     "*.mp3 *.wav"),
                ("Todos",      "*.*"),
            ],
        )
        if not rutas:
            return
        for ruta in rutas:
            self._queue.append({"ruta": ruta, "accion": accion})
        self._refresh_queue()
        logger.info("Cola: +%d archivos como '%s' (total=%d)",
                    len(rutas), accion, len(self._queue))

    def _refresh_queue(self):
        self._txt_cola.configure(state="normal")
        self._txt_cola.delete("1.0", "end")
        if not self._queue:
            self._txt_cola.insert("end", "Cola vacía. Selecciona acción y agrega archivos.\n")
        else:
            for i, item in enumerate(self._queue, 1):
                nombre = os.path.basename(item["ruta"])
                self._txt_cola.insert(
                    "end", f"{i:>2}. [{item['accion']:<18}]  {nombre}\n"
                )
        self._txt_cola.configure(state="disabled")

    def _clear_queue(self):
        if self._proceso_activo:
            messagebox.showwarning(
                "Procesando", "Espera a que termine la cola o cancélala primero."
            )
            return
        if not self._queue:
            return
        if messagebox.askyesno("Confirmar", "¿Vaciar la cola?"):
            self._queue.clear()
            self._refresh_queue()

    def _process_queue(self):
        if self._proceso_activo:
            return
        if not self._queue:
            messagebox.showinfo(
                "Cola vacía", "Agrega archivos a la cola primero."
            )
            return
        self._begin_process(f"Procesando cola ({len(self._queue)} archivos)")
        threading.Thread(target=self._run_queue, daemon=True).start()

    def _run_queue(self):
        """Procesa todos los items de la cola secuencialmente.
        Errores individuales no detienen el lote — solo cancelación explícita."""
        items       = list(self._queue)   # snapshot
        n_snapshot  = len(items)
        total       = n_snapshot
        ok_count    = 0
        fail_count  = 0
        last_idx    = 0
        errores: list[str] = []

        for idx, item in enumerate(items, 1):
            last_idx = idx
            if self._cancel.is_set():
                last_idx = idx - 1   # este item no se intentó
                break

            ruta   = item["ruta"]
            accion = item["accion"]
            nombre = os.path.basename(ruta)

            self.after(0, lambda i=idx, n=nombre, a=accion: self._lbl_status.configure(
                text=f"⏳  Lote {i}/{total} · {a} · {n}",
                text_color="#FCD34D",
            ))
            self.after(0, lambda i=idx: self._progressbar.set(i / max(total, 1)))
            logger.info("Lote %d/%d — %s — %s", idx, total, accion, nombre)

            try:
                if not os.path.isfile(ruta):
                    raise RuntimeError("Archivo no encontrado")

                info = self._ffmpeg.info(ruta)

                if accion == "Voz Femenina":
                    self._pipeline_voz(ruta, info)
                elif accion == "Traducir Inglés":
                    self._pipeline_traduccion(ruta, info, "en", "ingles")
                elif accion == "Traducir Portugués":
                    self._pipeline_traduccion(ruta, info, "pt", "portugues")
                else:
                    raise RuntimeError(f"Acción desconocida: {accion}")

                ok_count += 1
                logger.info("✓ Lote %d/%d completado", idx, total)

            except InterruptedError:
                logger.info("Cola cancelada en %d/%d", idx, total)
                last_idx = idx - 1   # cancelado a mitad → no contar como intentado
                break
            except Exception as exc:
                fail_count += 1
                errores.append(f"{nombre} ({accion}): {exc}")
                logger.error("✗ Lote %d/%d falló: %s", idx, total, exc, exc_info=True)
                # Continuar con el siguiente — no abortar todo el lote.

        # Reconstrucción de la cola:
        # - todo lo procesado (items[:last_idx]) sale
        # - lo no procesado (items[last_idx:]) se queda
        # - lo que el usuario agregó durante el lote (self._queue[n_snapshot:]) también
        sin_procesar  = items[last_idx:]
        agregados     = list(self._queue[n_snapshot:])
        self._queue[:] = sin_procesar + agregados

        self.after(0, self._refresh_queue)
        self.after(0, self._refresh_history)

        if self._cancel.is_set():
            msg = f"Cola cancelada — {ok_count}/{total} OK, {fail_count} errores"
        else:
            msg = f"Cola terminada — {ok_count}/{total} OK, {fail_count} errores"

        self.after(0, lambda: self._end_process(ok_count > 0, msg))

        if errores:
            resumen = "\n".join(f"• {e}" for e in errores[:10])
            if len(errores) > 10:
                resumen += f"\n… y {len(errores) - 10} más"
            self.after(0, lambda: messagebox.showinfo(
                "Resumen de cola", f"{ok_count} completados, {fail_count} errores.\n\n{resumen}"
            ))
    # Historial

    def _refresh_history(self):
        registros = self._db.listar(25)
        self._txt_history.configure(state="normal")
        self._txt_history.delete("1.0", "end")

        if not registros:
            self._txt_history.insert("end", "Sin conversiones registradas.\n")
        else:
            for r in registros:
                fecha = (r.get("fecha") or "")[:16]
                linea = (
                    f"[{fecha}]  {r['archivo_original']}"
                    f"  →  {r['tipo_conversion']}\n"
                )
                self._txt_history.insert("end", linea)

        self._txt_history.configure(state="disabled")

    def _clear_history(self):
        if messagebox.askyesno("Confirmar", "¿Eliminar todo el historial?"):
            self._db.limpiar()
            self._refresh_history()
    # Cierre

    def _on_close(self):
        if self._proceso_activo:
            if not messagebox.askyesno(
                "Proceso activo",
                "Hay un proceso en curso. ¿Cerrar de todas formas?",
            ):
                return
            self._cancel.set()

        try:
            self._voice.liberar()
            self._whisper.liberar()
        except Exception:
            pass

        self.destroy()
