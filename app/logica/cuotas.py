"""Planes de cuotas (RF-16 a RF-21, RN-24 a RN-31, RN-52).

Un plan es la deuda ("Avant Service, 3 cuotas de $ 41.117 desde agosto"). Vive
fuera de los meses: cada mes tiene su gasto de tipo "cuota" que lo apunta.

Regla central (RN-30): crear, editar o cancelar un plan solo toca el mes actual
del calendario y los meses futuros que ya existen. Nunca los meses anteriores, y
nunca una cuota que ya tiene pagos.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from app.logica import gastos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import clave_orden, validar_centavos

# 50 años: más cuotas que eso es un error de tipeo (RN-29). La usa también la
# revisión de la importación, para avisar antes de guardar.
MAXIMO_CUOTAS = 600

ACTIVO = "activo"
TERMINADO = "terminado"
CANCELADO = "cancelado"


# ----------------------------------------------------------------------
# Cuentas con meses (sin base de datos)
# ----------------------------------------------------------------------


def numero_de_cuota(plan, anio: int, mes: int) -> int:
    """RN-24: qué número de cuota corresponde al mes. Puede ser < 1 (no empezó)
    o > cantidad (ya terminó). Ej.: primera 2026-08, mes 2026-10 -> 3."""
    return (anio - plan["primer_anio"]) * 12 + (mes - plan["primer_mes"]) + 1


def _sumar_meses(anio: int, mes: int, cantidad: int) -> tuple[int, int]:
    """(2026, 8) + 2 -> (2026, 10); cruza el año: (2026, 11) + 2 -> (2027, 1)."""
    indice = anio * 12 + (mes - 1) + cantidad
    return indice // 12, indice % 12 + 1


def ultima_cuota(plan) -> tuple[int, int] | None:
    """RN-25: mes de la última cuota, o None si el plan no llegó a tener ninguna.

    Si se canceló, es la más temprana entre la última cuota real y el mes anterior
    al primero sin cuota (BUG-19). Si eso queda antes de la primera cuota (se
    canceló antes de empezar), el plan no tuvo cuotas: None.
    """
    real = _sumar_meses(
        plan["primer_anio"], plan["primer_mes"], plan["cantidad_cuotas"] - 1
    )
    if plan["cancelado_anio"] is None:
        return real
    ultima = min(real, meses.anterior(plan["cancelado_anio"], plan["cancelado_mes"]))
    if ultima < (plan["primer_anio"], plan["primer_mes"]):
        return None
    return ultima


def _cancelado_en(plan, anio: int, mes: int) -> bool:
    if plan["cancelado_anio"] is None:
        return False
    return (anio, mes) >= (plan["cancelado_anio"], plan["cancelado_mes"])


def restante(plan, anio: int, mes: int) -> int:
    """RN-28: lo que falta pagar después de la cuota de ese mes, en centavos.

    No empezó: todas las cuotas. Terminado o cancelado: 0.
    """
    if plan["cancelado_anio"] is not None:
        return 0
    n = numero_de_cuota(plan, anio, mes)
    cantidad = plan["cantidad_cuotas"]
    if n < 1:
        return cantidad * plan["monto_cuota_cent"]
    if n >= cantidad:
        return 0
    return (cantidad - n) * plan["monto_cuota_cent"]


def estado(plan, hoy: date | None = None) -> str:
    """RF-21: "cancelado", "terminado" (última cuota anterior al mes actual) o "activo".

    Depende del mes del calendario, no del mes que se está viendo (CA-21.1).
    """
    if plan["cancelado_anio"] is not None:
        return CANCELADO
    if ultima_cuota(plan) < meses.mes_actual_calendario(hoy):
        return TERMINADO
    return ACTIVO


# ----------------------------------------------------------------------
# Consultas
# ----------------------------------------------------------------------


def obtener_plan(con: sqlite3.Connection, plan_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM planes_cuotas WHERE id = ?", (plan_id,)
    ).fetchone()


def _exigir_plan(con: sqlite3.Connection, plan_id: int) -> sqlite3.Row:
    plan = obtener_plan(con, plan_id)
    if plan is None:
        raise ErrorDeValidacion("Ese plan de cuotas ya no existe.")
    return plan


def _omitida(con: sqlite3.Connection, plan_id: int, anio: int, mes: int) -> bool:
    fila = con.execute(
        "SELECT 1 FROM cuotas_omitidas WHERE plan_cuotas_id = ? AND anio = ? AND mes = ?",
        (plan_id, anio, mes),
    ).fetchone()
    return fila is not None


def activo_en(con: sqlite3.Connection, plan, anio: int, mes: int) -> bool:
    """RN-24: el plan tiene cuota en ese mes (empezó, no terminó, no está
    cancelado y la cuota de ese mes no se borró a mano)."""
    n = numero_de_cuota(plan, anio, mes)
    return (
        1 <= n <= plan["cantidad_cuotas"]
        and not _cancelado_en(plan, anio, mes)
        and not _omitida(con, plan["id"], anio, mes)
    )


@dataclass(frozen=True)
class DetallePlan:
    """Lo que muestra la pantalla Cuotas para un plan, visto desde un mes."""

    plan: sqlite3.Row
    estado: str
    cuota_texto: str  # "3/6", "no empezó" o "terminado"
    ultima: tuple[int, int] | None  # None: se canceló antes de la primera cuota.
    restante: int
    total: int  # cantidad × monto de la cuota


def detalle(plan, anio: int, mes: int, hoy: date | None = None) -> DetallePlan:
    n = numero_de_cuota(plan, anio, mes)
    if n < 1:
        cuota_texto = "no empezó"
    elif n > plan["cantidad_cuotas"] or _cancelado_en(plan, anio, mes):
        cuota_texto = "terminado"
    else:
        cuota_texto = f"{n}/{plan['cantidad_cuotas']}"
    return DetallePlan(
        plan=plan,
        estado=estado(plan, hoy),
        cuota_texto=cuota_texto,
        ultima=ultima_cuota(plan),
        restante=restante(plan, anio, mes),
        total=plan["cantidad_cuotas"] * plan["monto_cuota_cent"],
    )


def listar_planes(
    con: sqlite3.Connection,
    anio: int,
    mes: int,
    filtro: str | None = None,
    hoy: date | None = None,
) -> list[DetallePlan]:
    """Planes vistos desde (anio, mes). filtro: "activo", "terminado", "cancelado" o None."""
    planes = con.execute("SELECT * FROM planes_cuotas").fetchall()
    # BUG-20: se ordena en Python, sin acentos ni mayúsculas, como todas las listas.
    planes = sorted(planes, key=lambda p: clave_orden(p["nombre"]))
    detalles = [detalle(p, anio, mes, hoy) for p in planes]
    if filtro is not None:
        detalles = [d for d in detalles if d.estado == filtro]
    return detalles


# ----------------------------------------------------------------------
# Alta, edición y cancelación
# ----------------------------------------------------------------------


def _validar(
    con: sqlite3.Connection,
    nombre: str,
    categoria_id: int | None,
    medio_pago_id: int | None,
    monto_cuota_cent: int,
    cantidad_cuotas: int,
    primer_anio: int,
    primer_mes: int,
    actual=None,
) -> str:
    """RN-29. Devuelve el nombre limpio. "actual" es el plan que se edita (o None)."""
    limpio = " ".join((nombre or "").split())
    if not limpio:
        raise ErrorDeValidacion("Ingresá un nombre.", "nombre")
    # Mismas reglas de categoría y medio que un gasto: lo archivado solo se
    # acepta si el plan que se edita ya lo tenía (RN-49).
    gastos.validar_categoria(
        con, categoria_id, actual["categoria_id"] if actual else None
    )
    gastos.validar_medio_pago(
        con, medio_pago_id, actual["medio_pago_id"] if actual else None
    )
    validar_centavos(monto_cuota_cent, que="El monto de la cuota", campo="monto")
    es_entero = isinstance(cantidad_cuotas, int) and not isinstance(
        cantidad_cuotas, bool
    )
    if not es_entero or cantidad_cuotas < 1:
        raise ErrorDeValidacion(
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
            "cantidad",
        )
    if cantidad_cuotas > MAXIMO_CUOTAS:
        raise ErrorDeValidacion(
            "La cantidad de cuotas es demasiado grande.", "cantidad"
        )
    try:
        meses.validar_anio_mes(primer_anio, primer_mes)
    except ErrorDeValidacion as error:
        # El mismo mensaje, pero en el campo de la primera cuota.
        raise ErrorDeValidacion(str(error), "primera") from None
    return limpio


def crear_plan(
    con: sqlite3.Connection,
    nombre: str,
    categoria_id: int | None,
    medio_pago_id: int | None,
    monto_cuota_cent: int,
    cantidad_cuotas: int,
    primer_anio: int,
    primer_mes: int,
    hoy: date | None = None,
) -> int:
    """RF-16 / RF-18: crea el plan y genera sus cuotas en el mes actual y los
    futuros que existan (RN-30). La primera cuota puede ser un mes pasado (RN-29)."""
    nombre = _validar(
        con,
        nombre,
        categoria_id,
        medio_pago_id,
        monto_cuota_cent,
        cantidad_cuotas,
        primer_anio,
        primer_mes,
    )
    with con:
        cursor = con.execute(
            """INSERT INTO planes_cuotas (nombre, categoria_id, medio_pago_id, monto_cuota_cent,
                                          cantidad_cuotas, primer_anio, primer_mes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                nombre,
                categoria_id,
                medio_pago_id,
                monto_cuota_cent,
                cantidad_cuotas,
                primer_anio,
                primer_mes,
            ),
        )
        plan_id = cursor.lastrowid
        _sincronizar(con, plan_id, hoy)
    return plan_id


def editar_plan(
    con: sqlite3.Connection,
    plan_id: int,
    nombre: str,
    categoria_id: int | None,
    medio_pago_id: int | None,
    monto_cuota_cent: int,
    cantidad_cuotas: int,
    primer_anio: int,
    primer_mes: int,
    hoy: date | None = None,
) -> None:
    """RF-19: cambia el plan y sus cuotas del mes actual y los futuros (RN-30)."""
    actual = _exigir_plan(con, plan_id)
    nombre = _validar(
        con,
        nombre,
        categoria_id,
        medio_pago_id,
        monto_cuota_cent,
        cantidad_cuotas,
        primer_anio,
        primer_mes,
        actual,
    )
    with con:
        con.execute(
            """UPDATE planes_cuotas
               SET nombre = ?, categoria_id = ?, medio_pago_id = ?, monto_cuota_cent = ?,
                   cantidad_cuotas = ?, primer_anio = ?, primer_mes = ?
               WHERE id = ?""",
            (
                nombre,
                categoria_id,
                medio_pago_id,
                monto_cuota_cent,
                cantidad_cuotas,
                primer_anio,
                primer_mes,
                plan_id,
            ),
        )
        _sincronizar(con, plan_id, hoy)


def cancelar_plan(
    con: sqlite3.Connection, plan_id: int, hoy: date | None = None
) -> None:
    """RF-20 / RN-31: deja de generar cuotas.

    El primer mes sin cuota es el mes actual; o el siguiente, si la cuota del mes
    actual ya tiene pagos (esa cuota se conserva y pasa a ser la última).
    """
    plan = _exigir_plan(con, plan_id)
    if plan["cancelado_anio"] is not None:
        raise ErrorDeValidacion("Ese plan ya está cancelado.")
    if estado(plan, hoy) == TERMINADO:
        # BUG-19: un plan terminado ya no cobra cuotas: no hay nada que cancelar.
        raise ErrorDeValidacion("Ese plan ya terminó.")
    anio, mes = meses.mes_actual_calendario(hoy)
    cuota_actual = _cuota_del_mes(con, plan_id, anio, mes)
    if cuota_actual is not None and gastos.total_pagado(con, cuota_actual["id"]) > 0:
        anio, mes = meses.siguiente(anio, mes)
    with con:
        con.execute(
            "UPDATE planes_cuotas SET cancelado_anio = ?, cancelado_mes = ? WHERE id = ?",
            (anio, mes, plan_id),
        )
        _sincronizar(con, plan_id, hoy)


# ----------------------------------------------------------------------
# Cuotas en los meses
# ----------------------------------------------------------------------


def _cuota_del_mes(con: sqlite3.Connection, plan_id: int, anio: int, mes: int):
    return con.execute(
        """SELECT g.* FROM gastos g JOIN meses m ON m.id = g.mes_id
            WHERE g.plan_cuotas_id = ? AND m.anio = ? AND m.mes = ?""",
        (plan_id, anio, mes),
    ).fetchone()


def _insertar_cuota(con: sqlite3.Connection, plan, mes_id: int) -> None:
    con.execute(
        """INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo,
                               medio_pago_id, plan_cuotas_id)
           VALUES (?, ?, ?, ?, 'cuota', ?, ?)""",
        (
            mes_id,
            plan["nombre"],
            plan["categoria_id"],
            plan["monto_cuota_cent"],
            plan["medio_pago_id"],
            plan["id"],
        ),
    )


def cuota_en_mes(con: sqlite3.Connection, plan_id: int, mes_id: int) -> int | None:
    """La cuota del plan en ese mes (id del gasto); si falta y el plan está activo
    ahí, la crea. None si el plan no tiene cuota en ese mes.

    La usa la importación de Excel (RN-71): la cuota va en el mes destino aunque
    sea anterior al mes actual, una excepción a RN-30. Sin commit: se llama
    dentro de la transacción de la importación.
    """
    plan = _exigir_plan(con, plan_id)
    mes = meses.exigir_mes(con, mes_id)
    cuota = _cuota_del_mes(con, plan_id, mes["anio"], mes["mes"])
    if cuota is not None:
        return cuota["id"]
    if not activo_en(con, plan, mes["anio"], mes["mes"]):
        return None
    _insertar_cuota(con, plan, mes_id)
    return _cuota_del_mes(con, plan_id, mes["anio"], mes["mes"])["id"]


def _sincronizar(con: sqlite3.Connection, plan_id: int, hoy: date | None) -> None:
    """Deja las cuotas del plan en el mes actual y los futuros como dice el plan (RN-30).

    Sin commit: la llaman crear/editar/cancelar dentro de su transacción.
    - Cuota con pagos: no se toca (ni el monto ni si existe).
    - Mes donde el plan está activo: se crea o se actualiza la cuota.
    - Mes donde no está activo: se borra la cuota (sin registrarla como omitida:
      no la borró el usuario).
    """
    plan = obtener_plan(con, plan_id)
    desde = meses.mes_actual_calendario(hoy)
    for mes in con.execute("SELECT * FROM meses ORDER BY anio, mes").fetchall():
        if (mes["anio"], mes["mes"]) < desde:
            continue  # Los meses anteriores al actual nunca se modifican.
        cuota = _cuota_del_mes(con, plan_id, mes["anio"], mes["mes"])
        if cuota is not None and gastos.total_pagado(con, cuota["id"]) > 0:
            continue
        if activo_en(con, plan, mes["anio"], mes["mes"]):
            if cuota is None:
                _insertar_cuota(con, plan, mes["id"])
            else:
                con.execute(
                    """UPDATE gastos SET nombre = ?, categoria_id = ?, medio_pago_id = ?,
                                         monto_cent = ?
                       WHERE id = ?""",
                    (
                        plan["nombre"],
                        plan["categoria_id"],
                        plan["medio_pago_id"],
                        plan["monto_cuota_cent"],
                        cuota["id"],
                    ),
                )
        elif cuota is not None:
            con.execute("DELETE FROM gastos WHERE id = ?", (cuota["id"],))


def generar_cuotas_del_mes(con: sqlite3.Connection, mes_id: int) -> int:
    """RN-09: al crear un mes, una cuota por cada plan activo en ese mes.

    Sin commit: la llama meses.crear_mes dentro de su transacción. Se generan
    aunque la categoría o el medio estén archivados. Devuelve cuántas generó.
    """
    mes = con.execute("SELECT * FROM meses WHERE id = ?", (mes_id,)).fetchone()
    generadas = 0
    for plan in con.execute("SELECT * FROM planes_cuotas ORDER BY id").fetchall():
        ya_tiene = _cuota_del_mes(con, plan["id"], mes["anio"], mes["mes"]) is not None
        if activo_en(con, plan, mes["anio"], mes["mes"]) and not ya_tiene:
            _insertar_cuota(con, plan, mes_id)
            generadas += 1
    return generadas


def cuotas_que_se_generarian(con: sqlite3.Connection, anio: int, mes: int) -> int:
    """Cuántas cuotas tendría un mes nuevo (para el diálogo "Mes nuevo", §3.9)."""
    planes = con.execute("SELECT * FROM planes_cuotas").fetchall()
    return sum(1 for plan in planes if activo_en(con, plan, anio, mes))
