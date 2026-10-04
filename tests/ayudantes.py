"""Funciones auxiliares para preparar datos inventados en las pruebas.

Algunas cosas todavía no tienen función en la lógica (crear el mes siguiente es del
paso 4, los pagos del paso 2), así que se insertan a mano por SQL.
"""

from app.logica import catalogos


def id_por_nombre(con, tabla, nombre):
    """Busca el id de una categoría / medio / persona por su nombre (incluye archivados)."""
    for fila in catalogos.listar(con, tabla, incluir_archivados=True):
        if fila["nombre"] == nombre:
            return fila["id"]
    raise AssertionError(f"No existe {nombre!r} en {tabla}")


def insertar_mes(con, anio, mes, sueldo=120000, cotizacion=160000):
    """Inserta un mes a mano por SQL."""
    with con:
        cursor = con.execute(
            "INSERT INTO meses (anio, mes, sueldo_usd_cent, cotizacion_cent) VALUES (?, ?, ?, ?)",
            (anio, mes, sueldo, cotizacion),
        )
    return cursor.lastrowid


def insertar_pago(con, gasto_id, monto_cent, fecha="2026-10-05"):
    """Inserta un pago a mano por SQL."""
    with con:
        cursor = con.execute(
            "INSERT INTO pagos (gasto_id, monto_cent, fecha) VALUES (?, ?, ?)",
            (gasto_id, monto_cent, fecha),
        )
    return cursor.lastrowid


def insertar_plan(
    con, nombre, categoria_id, medio_pago_id=None, monto=1000000, cuotas=6
):
    """Inserta un plan de cuotas a mano por SQL (los planes son del paso 4)."""
    with con:
        cursor = con.execute(
            """INSERT INTO planes_cuotas (nombre, categoria_id, medio_pago_id,
                   monto_cuota_cent, cantidad_cuotas, primer_anio, primer_mes)
               VALUES (?, ?, ?, ?, ?, 2026, 8)""",
            (nombre, categoria_id, medio_pago_id, monto, cuotas),
        )
    return cursor.lastrowid


def cantidad_filas(con, tabla):
    return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
