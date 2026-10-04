"""Meses: creación del primer mes y consultas.

En el paso 4 se agregan crear el mes siguiente y borrar el último.
"""

import sqlite3
from datetime import date

from app.logica.errores import ErrorDeValidacion
from app.logica.formato import validar_centavos


def mes_actual_calendario(hoy: date | None = None) -> tuple[int, int]:
    """(año, mes) de hoy según el reloj del sistema.

    Recibe "hoy" opcional para que las pruebas puedan fijar la fecha y no
    dependan del día en que se corren.
    """
    # Se usa la fecha local de la computadora a propósito: el "mes actual" es
    # el que ve el usuario en su calendario, no el de otra zona horaria.
    hoy = hoy or date.today()  # noqa: DTZ011
    return hoy.year, hoy.month


def validar_anio_mes(anio: int, mes: int) -> None:
    """RN-07: año de 4 dígitos y mes de 1 a 12."""
    if not 1000 <= anio <= 9999:
        raise ErrorDeValidacion("El año tiene que tener 4 dígitos.")
    if not 1 <= mes <= 12:
        raise ErrorDeValidacion("El mes tiene que estar entre 1 y 12.")


def hay_meses(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM meses LIMIT 1").fetchone() is not None


def crear_primer_mes(
    con: sqlite3.Connection,
    anio: int,
    mes: int,
    sueldo_usd_cent: int,
    cotizacion_cent: int | None = None,
) -> int:
    """RF-04: crea el primer mes y devuelve su id.

    La cotización es opcional: puede quedar sin cargar (RN-18).
    """
    if hay_meses(con):
        raise ErrorDeValidacion(
            "Ya existe un mes. Los siguientes se crean con 'Mes nuevo'."
        )
    validar_anio_mes(anio, mes)
    validar_centavos(sueldo_usd_cent, permitir_cero=True, que="El sueldo")
    if cotizacion_cent is not None:
        validar_centavos(cotizacion_cent, que="La cotización")

    with con:
        cursor = con.execute(
            "INSERT INTO meses (anio, mes, sueldo_usd_cent, cotizacion_cent) VALUES (?, ?, ?, ?)",
            (anio, mes, sueldo_usd_cent, cotizacion_cent),
        )
    return cursor.lastrowid


def obtener_mes(con: sqlite3.Connection, mes_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM meses WHERE id = ?", (mes_id,)).fetchone()


def obtener_ultimo_mes(con: sqlite3.Connection) -> sqlite3.Row | None:
    """El mes más reciente, o None si todavía no hay ninguno."""
    return con.execute(
        "SELECT * FROM meses ORDER BY anio DESC, mes DESC LIMIT 1"
    ).fetchone()
