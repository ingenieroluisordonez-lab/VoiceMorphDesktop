import sqlite3
import os
from typing import List, Dict, Optional

from utils.logger import setup_logger
from config import DATABASE_PATH

logger = setup_logger("sqlite_manager")


class SQLiteManager:

    def __init__(self):
        self._inicializar()

    def _inicializar(self):
        try:
            with sqlite3.connect(DATABASE_PATH) as con:
                con.execute("""
                    CREATE TABLE IF NOT EXISTS historial (
                        id                INTEGER PRIMARY KEY AUTOINCREMENT,
                        archivo_original  TEXT NOT NULL,
                        tipo_conversion   TEXT NOT NULL,
                        archivo_resultado TEXT,
                        fecha             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        duracion_seg      REAL,
                        estado            TEXT DEFAULT 'completado',
                        notas             TEXT
                    )
                """)
                con.commit()
            logger.info("Base de datos lista: %s", DATABASE_PATH)
        except Exception as exc:
            logger.error("Error iniciando BD: %s", exc)
            raise

    def agregar(
        self,
        archivo_original: str,
        tipo_conversion: str,
        archivo_resultado: Optional[str] = None,
        duracion_seg: Optional[float] = None,
        estado: str = "completado",
        notas: Optional[str] = None,
    ) -> int:
        try:
            with sqlite3.connect(DATABASE_PATH) as con:
                cur = con.execute(
                    """
                    INSERT INTO historial
                        (archivo_original, tipo_conversion, archivo_resultado,
                         duracion_seg, estado, notas)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        os.path.basename(archivo_original),
                        tipo_conversion,
                        archivo_resultado,
                        duracion_seg,
                        estado,
                        notas,
                    ),
                )
                con.commit()
                logger.debug("Registro guardado id=%d", cur.lastrowid)
                return cur.lastrowid
        except Exception as exc:
            logger.error("Error guardando registro: %s", exc)
            raise

    def listar(self, limite: int = 50) -> List[Dict]:
        try:
            with sqlite3.connect(DATABASE_PATH) as con:
                con.row_factory = sqlite3.Row
                rows = con.execute(
                    "SELECT * FROM historial ORDER BY fecha DESC LIMIT ?", (limite,)
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.error("Error leyendo historial: %s", exc)
            return []

    def eliminar(self, record_id: int):
        with sqlite3.connect(DATABASE_PATH) as con:
            con.execute("DELETE FROM historial WHERE id = ?", (record_id,))
            con.commit()

    def limpiar(self):
        with sqlite3.connect(DATABASE_PATH) as con:
            con.execute("DELETE FROM historial")
            con.commit()
        logger.info("Historial limpiado")
