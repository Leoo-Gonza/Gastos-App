"""Preferencias guardadas en la tabla configuracion (clave → valor de texto).

Por ahora: la meta de ahorro mensual en USD (RF-36). Es una sola para todos
los meses.
"""

import sqlite3

from app.logica.errores import ErrorDeValidacion
from app.logica.formato import validar_centavos

_META = "meta_ahorro_usd_cent"


def obtener_meta(con: sqlite3.Connection) -> int | None:
    """Meta en centavos de USD, o None si no hay meta."""
    fila = con.execute(
        "SELECT valor FROM configuracion WHERE clave = ?", (_META,)
    ).fetchone()
    # La tabla guarda texto: se convierte a número al leer.
    return int(fila["valor"]) if fila else None


def guardar_meta(con: sqlite3.Connection, meta_usd_cent: int) -> None:
    if meta_usd_cent is None:
        raise ErrorDeValidacion("Ingresá la meta.", "meta")
    validar_centavos(meta_usd_cent, que="La meta", campo="meta")
    with con:
        # INSERT OR REPLACE: si ya había una meta, la reemplaza.
        con.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
            (_META, str(meta_usd_cent)),
        )


def quitar_meta(con: sqlite3.Connection) -> None:
    """Sin meta, el resumen no muestra la barra de avance (RN-39)."""
    with con:
        con.execute("DELETE FROM configuracion WHERE clave = ?", (_META,))
