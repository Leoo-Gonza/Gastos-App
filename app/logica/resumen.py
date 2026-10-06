"""Resumen del mes: pesos a cubrir, dólares a cambiar, ahorro, capacidad y meta.

Implementa RN-12 a RN-18, RN-38 y RN-39 (docs/requisitos.md §4.3 y §4.7).
Nada de esto se guarda: se calcula cada vez, así nunca queda desactualizado
si cambia un gasto o la cotización.

Nombres de las variables, igual que en los requisitos:
    S      sueldo en USD                 G      total de gastos en ARS
    E_ars  ingresos extra en ARS         E_usd  ingresos extra en USD
    C_ars  pesos recibidos en cambios    C_usd  dólares ya cambiados
    K      cotización del mes            F      G − E_ars − C_ars
"""

import sqlite3
from dataclasses import dataclass

from app.logica import cambios, configuracion, ingresos, me_deben, pagos
from app.logica.formato import convertir_ars_a_usd, convertir_usd_a_ars
from app.logica.meses import exigir_mes


@dataclass(frozen=True)
class Resumen:
    """Todos los valores del resumen del mes, en centavos.

    frozen=True: una vez calculado no se puede modificar por error.
    Los que dependen de la cotización son None si el mes no tiene (RN-18).
    """

    sueldo_usd: int  # S
    cotizacion: int | None  # K
    total_gastos: int  # G
    extras_ars: int  # E_ars
    extras_usd: int  # E_usd
    cambiado_usd: int  # C_usd
    cambiado_ars: int  # C_ars
    pesos_a_cubrir: int  # máx(F, 0)
    pesos_sobrantes: int  # P = −F si F < 0, si no 0
    usd_a_cambiar: int | None  # U
    sobrantes_usd: int | None  # P_usd
    ahorro_usd: int | None  # puede ser negativo (déficit)
    gastos_fijos_y_cuotas: int  # para la capacidad (RN-38)
    capacidad: int | None  # puede ser negativa
    meta_usd: int | None  # None = sin meta
    avance_meta: float | None  # ahorro / meta (1.0 = 100 %); None sin meta o sin ahorro
    pendiente_de_pago: int  # RN-20
    total_me_deben: int  # RN-40: acumulado de todas las personas (no depende del mes)

    @property
    def falta_cotizacion(self) -> bool:
        """True si hay que cargar la cotización para ver los dólares (RN-18)."""
        return self.ahorro_usd is None


def calcular_resumen(con: sqlite3.Connection, mes_id: int) -> Resumen:
    mes = exigir_mes(con, mes_id)
    s = mes["sueldo_usd_cent"]
    k = mes["cotizacion_cent"]

    totales_pago = pagos.totales_del_mes(con, mes_id)
    g = totales_pago["total"]  # RN-12: monto completo, pagado o no.
    extras = ingresos.totales_por_moneda(con, mes_id)
    e_ars, e_usd = extras["ARS"], extras["USD"]
    hechos = cambios.totales(con, mes_id)
    c_usd, c_ars = hechos["usd"], hechos["ars"]

    # RN-14 y RN-16: F positivo = pesos que faltan; negativo = pesos que sobran.
    f = g - e_ars - c_ars
    pesos_a_cubrir = max(f, 0)
    pesos_sobrantes = max(-f, 0)

    if k is not None:
        u = convertir_ars_a_usd(pesos_a_cubrir, k)  # RN-15
        p_usd = convertir_ars_a_usd(pesos_sobrantes, k)  # RN-16
        ahorro = s + e_usd - c_usd - u + p_usd  # RN-17
    elif f == 0:
        # RN-18: sin cotización pero no falta ni sobra nada: el ahorro se puede calcular.
        u = p_usd = 0
        ahorro = s + e_usd - c_usd
    else:
        u = p_usd = ahorro = None

    # RN-38: lo que sobra por mes después de pagar fijos y cuotas y ahorrar la meta.
    fijos_y_cuotas = con.execute(
        "SELECT COALESCE(SUM(monto_cent), 0) AS total FROM gastos "
        "WHERE mes_id = ? AND tipo IN ('fijo', 'cuota')",
        (mes_id,),
    ).fetchone()["total"]
    meta = configuracion.obtener_meta(con)
    capacidad = None
    if k is not None:
        meta_en_pesos = convertir_usd_a_ars(meta, k) if meta else 0
        capacidad = convertir_usd_a_ars(s, k) - fijos_y_cuotas - meta_en_pesos

    # RN-39: avance de la meta. La pantalla limita la barra entre 0 % y 100 %.
    avance = ahorro / meta if meta and ahorro is not None else None

    return Resumen(
        sueldo_usd=s,
        cotizacion=k,
        total_gastos=g,
        extras_ars=e_ars,
        extras_usd=e_usd,
        cambiado_usd=c_usd,
        cambiado_ars=c_ars,
        pesos_a_cubrir=pesos_a_cubrir,
        pesos_sobrantes=pesos_sobrantes,
        usd_a_cambiar=u,
        sobrantes_usd=p_usd,
        ahorro_usd=ahorro,
        gastos_fijos_y_cuotas=fijos_y_cuotas,
        capacidad=capacidad,
        meta_usd=meta,
        avance_meta=avance,
        pendiente_de_pago=totales_pago["pendiente"],
        total_me_deben=me_deben.total_general(con),
    )
