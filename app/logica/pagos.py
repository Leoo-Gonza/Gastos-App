"""Pagos de los gastos: tilde "pagado", pagos parciales y pendiente (RF-13 a RF-15).

Lo pagado no se guarda en el gasto: es la suma de sus pagos (RN-20). Así un
gasto puede tener varios pagos parciales y se puede borrar uno por uno.
Todos los pagos son en pesos, también los de un gasto en dólares.
"""

import sqlite3
from datetime import date, datetime

from app.logica import gastos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, validar_centavos


def _gasto_existente(con: sqlite3.Connection, gasto_id: int) -> sqlite3.Row:
    gasto = gastos.obtener_gasto(con, gasto_id)
    if gasto is None:
        raise ErrorDeValidacion("El gasto ya no existe.")
    return gasto


def pendiente(con: sqlite3.Connection, gasto_id: int) -> int:
    """RN-20: lo que falta pagar del gasto, en centavos."""
    gasto = _gasto_existente(con, gasto_id)
    return gasto["monto_cent"] - gastos.total_pagado(con, gasto_id)


def registrar_pago(
    con: sqlite3.Connection, gasto_id: int, monto_cent: int, fecha: date | None = None
) -> int:
    """RF-14: registra un pago (parcial o total) y devuelve su id.

    RN-21: el pago tiene que ser mayor a 0 y no puede superar lo pendiente.
    "fecha" es opcional para que las pruebas puedan fijarla; por defecto, hoy.
    """
    falta = pendiente(con, gasto_id)
    validar_centavos(monto_cent, campo="monto")
    if falta == 0:
        raise ErrorDeValidacion("Este gasto ya está pagado.", "monto")
    if monto_cent > falta:
        raise ErrorDeValidacion(
            f"El pago no puede superar lo pendiente ({formatear_ars(falta)}).", "monto"
        )
    # Fecha local a propósito: es el día que el usuario ve en su calendario.
    fecha = fecha or date.today()  # noqa: DTZ011
    # O22: un datetime (fecha con hora, como el que devuelve el calendario de
    # Flet) también es un date para Python. Se guarda solo la fecha.
    if isinstance(fecha, datetime):
        fecha = fecha.date()
    with con:
        cursor = con.execute(
            "INSERT INTO pagos (gasto_id, monto_cent, fecha) VALUES (?, ?, ?)",
            # isoformat() da "2026-10-04": se guarda así para que se ordene bien.
            (gasto_id, monto_cent, fecha.isoformat()),
        )
    return cursor.lastrowid


def marcar_pagado(
    con: sqlite3.Connection, gasto_id: int, fecha: date | None = None
) -> int | None:
    """RF-13 / RN-22: el tilde. Registra un pago por todo lo pendiente.

    Devuelve el id de ese pago (para "Deshacer"), o None si ya estaba pagado.
    """
    falta = pendiente(con, gasto_id)
    if falta == 0:
        return None
    return registrar_pago(con, gasto_id, falta, fecha)


def quitar_pagos(con: sqlite3.Connection, gasto_id: int) -> int:
    """RN-22: destildar "pagado" borra todos los pagos del gasto.

    Devuelve cuántos pagos se borraron. La confirmación la pide la pantalla.
    """
    _gasto_existente(con, gasto_id)
    with con:
        cursor = con.execute("DELETE FROM pagos WHERE gasto_id = ?", (gasto_id,))
    return cursor.rowcount


def listar_pagos(con: sqlite3.Connection, gasto_id: int) -> list[sqlite3.Row]:
    """RF-15: pagos de un gasto, del más viejo al más nuevo."""
    return con.execute(
        "SELECT id, monto_cent, fecha FROM pagos WHERE gasto_id = ? ORDER BY fecha, id",
        (gasto_id,),
    ).fetchall()


def borrar_pago(con: sqlite3.Connection, pago_id: int) -> None:
    """RF-15: borra un pago puntual (para corregir errores)."""
    with con:
        cursor = con.execute("DELETE FROM pagos WHERE id = ?", (pago_id,))
    if cursor.rowcount == 0:
        raise ErrorDeValidacion("Ese pago ya no existe.")


def totales_del_mes(con: sqlite3.Connection, mes_id: int) -> dict[str, int]:
    """RF-09 / RN-20: total de gastos, pagado y pendiente del mes, en centavos.

    Son las columnas "Gastos", "Pagado" y "Falta por pagar" de la planilla.
    """
    fila = con.execute(
        """SELECT COALESCE(SUM(g.monto_cent), 0) AS total,
                  COALESCE(SUM((SELECT COALESCE(SUM(p.monto_cent), 0)
                                  FROM pagos p WHERE p.gasto_id = g.id)), 0) AS pagado
             FROM gastos g
            WHERE g.mes_id = ?""",
        (mes_id,),
    ).fetchone()
    return {
        "total": fila["total"],
        "pagado": fila["pagado"],
        "pendiente": fila["total"] - fila["pagado"],
    }
