"""Cambios de dólares a pesos ya realizados en el mes (RF-26, RN-13).

Cada cambio guarda los pesos que realmente se recibieron. La cotización del
mes se aplica solo a lo que todavía falta cambiar (RF-27).
"""

import sqlite3
from datetime import date, datetime

from app.logica.errores import ErrorDeValidacion
from app.logica.formato import convertir_usd_a_ars, validar_centavos
from app.logica.meses import exigir_mes


def ars_sugeridos(usd_cent: int, cotizacion_cent: int) -> int:
    """RN-13: pesos que se reciben por un cambio (USD × cotización).

    Es solo una sugerencia: el usuario puede corregirla (ej. por una comisión).
    """
    return convertir_usd_a_ars(usd_cent, cotizacion_cent)


def _validar(
    usd_cent: int, cotizacion_cent: int, ars_cent: int | None, fecha: date | None
) -> tuple[int, str]:
    validar_centavos(usd_cent, que="El monto en dólares", campo="usd")
    validar_centavos(cotizacion_cent, que="La cotización", campo="cotizacion")
    if ars_cent is None:
        ars_cent = ars_sugeridos(usd_cent, cotizacion_cent)
    validar_centavos(ars_cent, que="El monto en pesos", campo="ars")
    # Fecha local a propósito: el día que el usuario ve en su calendario.
    fecha = fecha or date.today()  # noqa: DTZ011
    if isinstance(
        fecha, datetime
    ):  # Un datetime también es un date: se guarda solo el día.
        fecha = fecha.date()
    return ars_cent, fecha.isoformat()


def agregar_cambio(
    con: sqlite3.Connection,
    mes_id: int,
    usd_cent: int,
    cotizacion_cent: int,
    ars_cent: int | None = None,
    fecha: date | None = None,
) -> int:
    """Registra un cambio. Si ars_cent es None, se usan los pesos sugeridos."""
    exigir_mes(con, mes_id)
    ars_cent, fecha_iso = _validar(usd_cent, cotizacion_cent, ars_cent, fecha)
    with con:
        cursor = con.execute(
            "INSERT INTO cambios (mes_id, fecha, usd_cent, cotizacion_cent, ars_cent) "
            "VALUES (?, ?, ?, ?, ?)",
            (mes_id, fecha_iso, usd_cent, cotizacion_cent, ars_cent),
        )
    return cursor.lastrowid


def editar_cambio(
    con: sqlite3.Connection,
    cambio_id: int,
    usd_cent: int,
    cotizacion_cent: int,
    ars_cent: int | None = None,
    fecha: date | None = None,
) -> None:
    actual = obtener_cambio(con, cambio_id)
    if actual is None:
        raise ErrorDeValidacion("Ese cambio ya no existe.")
    # Si no se indica fecha, se conserva la que tenía.
    fecha = fecha or date.fromisoformat(actual["fecha"])
    ars_cent, fecha_iso = _validar(usd_cent, cotizacion_cent, ars_cent, fecha)
    with con:
        con.execute(
            "UPDATE cambios SET fecha = ?, usd_cent = ?, cotizacion_cent = ?, ars_cent = ? "
            "WHERE id = ?",
            (fecha_iso, usd_cent, cotizacion_cent, ars_cent, cambio_id),
        )


def borrar_cambio(con: sqlite3.Connection, cambio_id: int) -> None:
    with con:
        cursor = con.execute("DELETE FROM cambios WHERE id = ?", (cambio_id,))
    if cursor.rowcount == 0:
        raise ErrorDeValidacion("Ese cambio ya no existe.")


def obtener_cambio(con: sqlite3.Connection, cambio_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM cambios WHERE id = ?", (cambio_id,)).fetchone()


def listar_cambios(con: sqlite3.Connection, mes_id: int) -> list[sqlite3.Row]:
    return con.execute(
        "SELECT * FROM cambios WHERE mes_id = ? ORDER BY fecha, id", (mes_id,)
    ).fetchall()


def totales(con: sqlite3.Connection, mes_id: int) -> dict[str, int]:
    """{"usd": C_usd, "ars": C_ars} en centavos (variables de RN-14 y RN-17)."""
    fila = con.execute(
        "SELECT COALESCE(SUM(usd_cent), 0) AS usd, COALESCE(SUM(ars_cent), 0) AS ars "
        "FROM cambios WHERE mes_id = ?",
        (mes_id,),
    ).fetchone()
    return {"usd": fila["usd"], "ars": fila["ars"]}
