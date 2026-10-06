"""Previsión de los próximos 12 meses (RF-38, RF-39, RN-41 a RN-45).

Mira hacia adelante solo con lo que se repite: el sueldo, los gastos fijos del
mes actual y las cuotas de los planes. No incluye pagos únicos, ingresos extra
ni cambios, y no estima inflación.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date

from app.logica import cuotas, meses
from app.logica.formato import clave_orden, convertir_ars_a_usd, convertir_usd_a_ars

OK = "ok"
SIN_MES_ACTUAL = "sin_mes_actual"
SIN_COTIZACION = "sin_cotizacion"


@dataclass(frozen=True)
class MesPrevisto:
    anio: int
    mes: int
    gastos: int  # G(M) en centavos de pesos (RN-42)
    usd_a_cambiar: int | None  # U(M); None si no hay cotización (RN-45)
    ahorro: int | None  # S − U(M); None si no hay cotización
    liberados: tuple[
        tuple[str, int], ...
    ]  # (plan, monto de la cuota) que se libera (RN-44)


@dataclass(frozen=True)
class Prevision:
    estado: str  # OK, SIN_MES_ACTUAL o SIN_COTIZACION
    anio_actual: int
    mes_actual: int
    sueldo_usd: int | None  # S_actual
    cotizacion: int | None  # K_actual
    meses: tuple[MesPrevisto, ...]  # vacío si no existe el mes actual


def _gastos_fijos(con: sqlite3.Connection, mes_id: int, cotizacion: int | None) -> int:
    """Σ fijos del mes actual, completos aunque sean compartidos (RN-42).

    Los fijos en dólares se pasan a pesos con la cotización actual, como al crear
    un mes nuevo (RN-57); si no hay cotización, con la que se guardó en el gasto.
    """
    total = 0
    for g in con.execute(
        "SELECT * FROM gastos WHERE mes_id = ? AND tipo = 'fijo'", (mes_id,)
    ).fetchall():
        if g["moneda"] == "USD":
            total += convertir_usd_a_ars(
                g["monto_usd_cent"], cotizacion or g["cotizacion_cent"]
            )
        else:
            total += g["monto_cent"]
    return total


def calcular_prevision(con: sqlite3.Connection, hoy: date | None = None) -> Prevision:
    """RN-41: los 12 meses siguientes al mes del calendario, sin incluirlo.

    No depende del mes que se está viendo en la app.
    """
    anio, mes = meses.mes_actual_calendario(hoy)
    actual = meses.obtener_mes_por_fecha(con, anio, mes)
    if actual is None:
        # RN-45: sin el mes actual no hay de dónde sacar sueldo, fijos ni cotización.
        return Prevision(SIN_MES_ACTUAL, anio, mes, None, None, ())

    sueldo = actual["sueldo_usd_cent"]
    cotizacion = actual["cotizacion_cent"]
    fijos = _gastos_fijos(con, actual["id"], cotizacion)
    planes = con.execute("SELECT * FROM planes_cuotas").fetchall()

    previstos = []
    m_anio, m_mes = anio, mes
    for _ in range(12):
        m_anio, m_mes = meses.siguiente(m_anio, m_mes)
        cuotas_del_mes = sum(
            p["monto_cuota_cent"]
            for p in planes
            if cuotas.activo_en(con, p, m_anio, m_mes)
        )
        gastos = fijos + cuotas_del_mes
        # RN-44 / RN-27: se libera la cuota de los planes cuya última fue el mes anterior.
        anterior = meses.anterior(m_anio, m_mes)
        liberados = tuple(
            (p["nombre"], p["monto_cuota_cent"])
            for p in sorted(planes, key=lambda p: clave_orden(p["nombre"]))
            if cuotas.ultima_cuota(p) == anterior
        )
        if cotizacion is None:
            usd = ahorro = None
        else:
            usd = convertir_ars_a_usd(gastos, cotizacion)  # RN-43
            ahorro = sueldo - usd
        previstos.append(MesPrevisto(m_anio, m_mes, gastos, usd, ahorro, liberados))

    estado = OK if cotizacion is not None else SIN_COTIZACION
    return Prevision(estado, anio, mes, sueldo, cotizacion, tuple(previstos))
