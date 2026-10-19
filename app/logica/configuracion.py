"""Preferencias guardadas en la tabla configuracion (clave → valor de texto).

La meta de ahorro mensual en USD (RF-36, una sola para todos los meses), el
tema (Apariencia) y el dólar para la cotización automática (RN-79).
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


# Apariencia (diseño §3.10): "claro", "oscuro" o "sistema" (como Windows/macOS).
TEMAS = ("claro", "oscuro", "sistema")
_TEMA = "tema"


def obtener_tema(con: sqlite3.Connection) -> str:
    """El tema elegido; "sistema" si nunca se eligió uno."""
    fila = con.execute(
        "SELECT valor FROM configuracion WHERE clave = ?", (_TEMA,)
    ).fetchone()
    return fila["valor"] if fila and fila["valor"] in TEMAS else "sistema"


def guardar_tema(con: sqlite3.Connection, tema: str) -> None:
    if tema not in TEMAS:
        raise ErrorDeValidacion(
            "El tema tiene que ser claro, oscuro o sistema.", "tema"
        )
    with con:
        con.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
            (_TEMA, tema),
        )


# Dólar para la cotización automática (v2, RN-79): qué busca el botón "Buscar
# dólar ..." del diálogo de la cotización. Se guarda un valor propio de la app,
# no el nombre que usa DolarApi (§5.11).
DOLARES = ("blue", "mep", "oficial", "cripto")
_DOLAR = "dolar_cotizacion"


def obtener_dolar(con: sqlite3.Connection) -> str:
    """El dólar elegido; "blue" si nunca se eligió o lo guardado no es válido."""
    fila = con.execute(
        "SELECT valor FROM configuracion WHERE clave = ?", (_DOLAR,)
    ).fetchone()
    return fila["valor"] if fila and fila["valor"] in DOLARES else "blue"


def guardar_dolar(con: sqlite3.Connection, dolar: str) -> None:
    if dolar not in DOLARES:
        raise ErrorDeValidacion(
            "El dólar tiene que ser blue, MEP, oficial o cripto.", "dolar"
        )
    with con:
        con.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)",
            (_DOLAR, dolar),
        )
