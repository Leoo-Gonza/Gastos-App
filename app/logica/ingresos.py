"""Ingresos extra del mes, en pesos o en dólares (RF-24).

Los extras en pesos reducen los pesos a cubrir; los extras en dólares suman al
ahorro (RN-14, RN-17).
"""

import sqlite3

from app.logica.errores import ErrorDeValidacion
from app.logica.formato import validar_centavos
from app.logica.meses import exigir_mes


def _validar(descripcion: str, moneda: str, monto_cent: int) -> str:
    limpia = " ".join(descripcion.split())
    if not limpia:
        raise ErrorDeValidacion("Ingresá una descripción.", "descripcion")
    if moneda not in ("ARS", "USD"):
        raise ErrorDeValidacion("La moneda tiene que ser ARS o USD.", "moneda")
    validar_centavos(monto_cent, campo="monto")
    return limpia


def agregar_ingreso(
    con: sqlite3.Connection, mes_id: int, descripcion: str, moneda: str, monto_cent: int
) -> int:
    exigir_mes(con, mes_id)
    descripcion = _validar(descripcion, moneda, monto_cent)
    with con:
        cursor = con.execute(
            "INSERT INTO ingresos_extra (mes_id, descripcion, moneda, monto_cent) "
            "VALUES (?, ?, ?, ?)",
            (mes_id, descripcion, moneda, monto_cent),
        )
    return cursor.lastrowid


def editar_ingreso(
    con: sqlite3.Connection,
    ingreso_id: int,
    descripcion: str,
    moneda: str,
    monto_cent: int,
) -> None:
    if obtener_ingreso(con, ingreso_id) is None:
        raise ErrorDeValidacion("Ese ingreso ya no existe.")
    descripcion = _validar(descripcion, moneda, monto_cent)
    with con:
        con.execute(
            "UPDATE ingresos_extra SET descripcion = ?, moneda = ?, monto_cent = ? WHERE id = ?",
            (descripcion, moneda, monto_cent, ingreso_id),
        )


def borrar_ingreso(con: sqlite3.Connection, ingreso_id: int) -> None:
    with con:
        cursor = con.execute("DELETE FROM ingresos_extra WHERE id = ?", (ingreso_id,))
    if cursor.rowcount == 0:
        raise ErrorDeValidacion("Ese ingreso ya no existe.")


def obtener_ingreso(con: sqlite3.Connection, ingreso_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM ingresos_extra WHERE id = ?", (ingreso_id,)
    ).fetchone()


def listar_ingresos(con: sqlite3.Connection, mes_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM ingresos_extra WHERE mes_id = ? ORDER BY id", (mes_id,)
    ).fetchall()


def totales_por_moneda(con: sqlite3.Connection, mes_id: int) -> dict[str, int]:
    """{"ARS": E_ars, "USD": E_usd} en centavos (variables de RN-14 y RN-17)."""
    totales = {"ARS": 0, "USD": 0}
    for fila in con.execute(
        "SELECT moneda, SUM(monto_cent) AS total FROM ingresos_extra "
        "WHERE mes_id = ? GROUP BY moneda",
        (mes_id,),
    ):
        totales[fila["moneda"]] = fila["total"]
    return totales
