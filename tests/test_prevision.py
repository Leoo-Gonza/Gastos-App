"""Pruebas de la lógica de la previsión (paso 6) y de los datos de los gráficos (paso 7):
RF-38 a RF-42, RN-41 a RN-48; CA-38.1 a CA-38.11, CA-39.1, CA-39.2, CA-40.1, CA-41.1 a
CA-41.3 y CA-42.1. Base en memoria, datos inventados y "hoy" fijo (hoy=...)."""

import dataclasses
from datetime import date

import pytest

from app.logica import (
    cambios,
    catalogos,
    compartidos,
    cuotas,
    gastos,
    graficos,
    ingresos,
    me_deben,
    meses,
    pagos,
    prevision,
)
from app.logica.formato import formatear_ars, formatear_usd
from tests.ayudantes import id_por_nombre

HOY = date(2026, 10, 4)  # mes actual: 2026-10


def _cat(con, nombre):
    try:
        return id_por_nombre(con, catalogos.CATEGORIAS, nombre)
    except AssertionError:
        return catalogos.crear(con, catalogos.CATEGORIAS, nombre)


@pytest.fixture
def base(con):
    """Base del módulo H (§7): mes actual 2026-10 (S 1.200, K 1.600) con fijos que suman
    800.000 (uno es Internet 38.700 compartido), Avant 41.117 con última cuota 2026-10,
    plan B 10.000 con última cuota 2027-02 y un pago único de 15.000. También existe
    2026-09 (para ver que el mes seleccionado no importa)."""
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 155000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    otros = _cat(con, "Otros")
    gastos.agregar_gasto(con, oct_, "Alquiler", _cat(con, "Vivienda"), 26000000, "fijo")
    gastos.agregar_gasto(
        con,
        oct_,
        "Internet",
        _cat(con, "Servicios"),
        3870000,
        "fijo",
        partes=[(sofia, None), (marsu, None)],
    )
    gastos.agregar_gasto(
        con, oct_, "Resto de fijos", otros, 80000000 - 26000000 - 3870000, "fijo"
    )
    gastos.agregar_gasto(con, oct_, "Regalo", otros, 1500000, "unico")
    avant = cuotas.crear_plan(con, "Avant", otros, None, 4111700, 3, 2026, 8, hoy=HOY)
    plan_b = cuotas.crear_plan(
        con, "Plan B", otros, None, 1000000, 12, 2026, 3, hoy=HOY
    )
    return {"sep": sep, "oct": oct_, "avant": avant, "plan_b": plan_b, "sofia": sofia}


def _filas(con, hoy=HOY):
    """[(“AAAA-MM”, gastos, usd, ahorro)] de la previsión."""
    p = prevision.calcular_prevision(con, hoy)
    return [
        (f"{m.anio}-{m.mes:02d}", m.gastos, m.usd_a_cambiar, m.ahorro) for m in p.meses
    ]


def _gastos_por_mes(con, hoy=HOY):
    return {
        f"{m.anio}-{m.mes:02d}": m.gastos
        for m in prevision.calcular_prevision(con, hoy).meses
    }


DESDE_NOV_HASTA_FEB = ["2026-11", "2026-12", "2027-01", "2027-02"]
DESDE_MARZO = [
    "2027-03",
    "2027-04",
    "2027-05",
    "2027-06",
    "2027-07",
    "2027-08",
    "2027-09",
    "2027-10",
]


# ---------------------------------------------------------------------------
# Previsión (RF-38, RN-41 a RN-45, CA-38.x)
# ---------------------------------------------------------------------------


def test_ca_38_1_doce_meses_siguientes_sin_el_actual(con, base):
    p = prevision.calcular_prevision(con, HOY)
    assert (p.estado, p.anio_actual, p.mes_actual) == (prevision.OK, 2026, 10)
    assert (p.sueldo_usd, p.cotizacion) == (120000, 160000)
    assert [
        f"{m.anio}-{m.mes:02d}" for m in p.meses
    ] == DESDE_NOV_HASTA_FEB + DESDE_MARZO
    assert len(p.meses) == 12


def test_ca_38_1_no_depende_del_mes_seleccionado(con, base):
    # La previsión no recibe el mes seleccionado: es la misma "viendo" septiembre u octubre
    # (solo depende del calendario). Llamarla dos veces da exactamente lo mismo.
    assert prevision.calcular_prevision(con, HOY) == prevision.calcular_prevision(
        con, HOY
    )
    assert prevision.calcular_prevision(
        con, date(2026, 10, 31)
    ) == prevision.calcular_prevision(con, HOY)


def test_ca_38_2_gastos_usd_y_ahorro(con, base):
    filas = {f: (g, u, a) for f, g, u, a in _filas(con)}
    for mes in DESDE_NOV_HASTA_FEB:
        g, u, a = filas[mes]
        assert (formatear_ars(g), formatear_usd(u), formatear_usd(a)) == (
            "$ 810.000",
            "US$ 506,25",
            "US$ 693,75",
        ), mes
    for mes in DESDE_MARZO:
        g, u, a = filas[mes]
        assert (formatear_ars(g), formatear_usd(u), formatear_usd(a)) == (
            "$ 800.000",
            "US$ 500,00",
            "US$ 700,00",
        ), mes


def test_ca_38_3_sin_pagos_unicos_y_compartidos_completos(con, base):
    # El único de 15.000 no está; Internet cuenta 38.700 completo (no solo la parte propia).
    assert _gastos_por_mes(con)["2027-03"] == 80000000


def test_ca_38_4_extras_y_cambios_no_cambian_la_tabla(con, base):
    antes = prevision.calcular_prevision(con, HOY)
    ingresos.agregar_ingreso(con, base["oct"], "Freelance", "USD", 10000)
    ingresos.agregar_ingreso(con, base["oct"], "Bono", "ARS", 5000000)
    cambios.agregar_cambio(con, base["oct"], 50000, 150000, fecha=HOY)
    assert prevision.calcular_prevision(con, HOY) == antes


def test_pagos_y_me_deben_no_cambian_la_tabla(con, base):
    antes = prevision.calcular_prevision(con, HOY)
    for g in gastos.listar_gastos(con, base["oct"]):
        pagos.marcar_pagado(con, g["id"], HOY)
    me_deben.agregar_item(con, base["sofia"], "Préstamo", 2000000, HOY)
    for parte in con.execute("SELECT id FROM partes_gasto").fetchall():
        compartidos.marcar_cobrada(con, parte["id"], True)
    assert prevision.calcular_prevision(con, HOY) == antes


def test_ca_38_5_cambiar_la_cotizacion_actual(con, base):
    meses.editar_cotizacion(con, base["oct"], 200000)
    [nov, *_] = prevision.calcular_prevision(con, HOY).meses
    assert (
        nov.gastos,
        formatear_usd(nov.usd_a_cambiar),
        formatear_usd(nov.ahorro),
    ) == (
        81000000,
        "US$ 405,00",
        "US$ 795,00",
    )


def test_ca_38_6_cuota_omitida(con, base):
    dic = meses.crear_mes_siguiente(con, 120000, 160000)  # 2026-11
    dic = meses.crear_mes_siguiente(con, 120000, 160000)  # 2026-12
    cuota = con.execute(
        "SELECT id FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
        (base["plan_b"], dic),
    ).fetchone()["id"]
    gastos.borrar_gasto(con, cuota)
    por_mes = _gastos_por_mes(con)
    assert por_mes["2026-12"] == 80000000
    assert [por_mes[m] for m in ["2026-11", "2027-01", "2027-02"]] == [81000000] * 3


def test_ca_38_7_sin_cotizacion(con, base):
    with con:
        con.execute(
            "UPDATE meses SET cotizacion_cent = NULL WHERE id = ?", (base["oct"],)
        )
    p = prevision.calcular_prevision(con, HOY)
    assert (p.estado, p.cotizacion) == (prevision.SIN_COTIZACION, None)
    assert [m.gastos for m in p.meses][:5] == [81000000] * 4 + [80000000]
    assert all(m.usd_a_cambiar is None and m.ahorro is None for m in p.meses)


def test_ca_38_7_sin_el_mes_actual(con):
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    p = prevision.calcular_prevision(con, HOY)
    assert (p.estado, p.anio_actual, p.mes_actual, p.meses) == (
        prevision.SIN_MES_ACTUAL,
        2026,
        10,
        (),
    )
    assert (p.sueldo_usd, p.cotizacion) == (None, None)


def test_sin_ningun_mes(con):
    p = prevision.calcular_prevision(con, HOY)
    assert (p.estado, p.meses) == (prevision.SIN_MES_ACTUAL, ())


def _claude(con, base, cotizacion):
    return gastos.agregar_gasto(
        con,
        base["oct"],
        "Claude",
        _cat(con, "Otros"),
        None,
        "fijo",
        None,
        "USD",
        2000,
        cotizacion,
    )


def test_ca_38_8_fijo_en_dolares_con_la_cotizacion_actual(con, base):
    _claude(con, base, 160000)
    meses.editar_cotizacion(con, base["oct"], 170000)
    filas = {f: (g, u, a) for f, g, u, a in _filas(con)}
    for mes in DESDE_NOV_HASTA_FEB:
        g, u, a = filas[mes]
        assert (formatear_ars(g), formatear_usd(u), formatear_usd(a)) == (
            "$ 844.000",
            "US$ 496,47",
            "US$ 703,53",
        ), mes
    for mes in DESDE_MARZO:
        g, u, a = filas[mes]
        assert (formatear_ars(g), formatear_usd(u), formatear_usd(a)) == (
            "$ 834.000",
            "US$ 490,59",
            "US$ 709,41",
        ), mes


def test_ca_38_9_dolar_tarjeta_usa_la_cotizacion_actual(con, base):
    _claude(con, base, 210000)
    assert _gastos_por_mes(con)["2026-11"] == 84200000


def test_ca_38_10_sin_cotizacion_usa_la_del_gasto(con, base):
    _claude(con, base, 160000)
    with con:
        con.execute(
            "UPDATE meses SET cotizacion_cent = NULL WHERE id = ?", (base["oct"],)
        )
    p = prevision.calcular_prevision(con, HOY)
    assert p.estado == prevision.SIN_COTIZACION
    assert p.meses[0].gastos == 84200000


def test_ca_38_11_pago_unico_en_dolares_no_aparece(con, base):
    gastos.agregar_gasto(
        con,
        base["oct"],
        "Curso",
        _cat(con, "Otros"),
        None,
        "unico",
        None,
        "USD",
        5000,
        160000,
    )
    assert _gastos_por_mes(con)["2026-11"] == 81000000


def test_mes_actual_sin_fijos(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    p = prevision.calcular_prevision(con, HOY)
    assert all(
        m.gastos == 0 and m.usd_a_cambiar == 0 and m.ahorro == 120000 for m in p.meses
    )


def test_solo_cuentan_los_fijos_del_mes_actual(con, base):
    # Un fijo de septiembre que no está en octubre no cuenta.
    gastos.agregar_gasto(
        con, base["sep"], "Gym viejo", _cat(con, "Otros"), 5000000, "fijo"
    )
    assert _gastos_por_mes(con)["2027-03"] == 80000000


def test_cruce_de_anio_con_hoy_en_diciembre(con):
    meses.crear_primer_mes(con, 2026, 12, 100000, 100000)
    p = prevision.calcular_prevision(con, date(2026, 12, 15))
    assert [f"{m.anio}-{m.mes:02d}" for m in p.meses][:2] == ["2027-01", "2027-02"]
    assert f"{p.meses[-1].anio}-{p.meses[-1].mes:02d}" == "2027-12"


def test_plan_que_todavia_no_empezo_cuenta_desde_su_primer_mes(con):
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    cuotas.crear_plan(
        con, "Heladera", _cat(con, "Otros"), None, 2500000, 3, 2027, 1, hoy=HOY
    )
    por_mes = _gastos_por_mes(con)
    assert [
        por_mes[m] for m in ["2026-11", "2026-12", "2027-01", "2027-03", "2027-04"]
    ] == [
        0,
        0,
        2500000,
        2500000,
        0,
    ]
    assert oct_


def test_plan_cancelado_no_cuenta_despues(con, base):
    cuotas.cancelar_plan(con, base["plan_b"], hoy=HOY)
    assert _gastos_por_mes(con)["2026-11"] == 80000000


# ---------------------------------------------------------------------------
# Liberaciones (RF-39, RN-44, CA-39.x)
# ---------------------------------------------------------------------------


def _liberados(con, hoy=HOY):
    return {
        f"{m.anio}-{m.mes:02d}": m.liberados
        for m in prevision.calcular_prevision(con, hoy).meses
        if m.liberados
    }


def test_ca_39_1_liberaciones(con, base):
    assert _liberados(con) == {
        "2026-11": (("Avant", 4111700),),
        "2027-03": (("Plan B", 1000000),),
    }
    assert formatear_ars(4111700) == "$ 41.117"


def test_ca_39_2_plan_que_termina_en_el_ultimo_mes_no_se_libera_en_la_tabla(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    cuotas.crear_plan(
        con, "Largo", _cat(con, "Otros"), None, 100000, 13, 2026, 10, hoy=HOY
    )  # última 2027-10
    assert _liberados(con) == {}


def test_varios_planes_liberados_el_mismo_mes_ordenados_sin_acentos(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    otros = _cat(con, "Otros")
    for nombre in ["Zeta", "Ágil", "moto"]:
        cuotas.crear_plan(
            con, nombre, otros, None, 100000, 2, 2026, 11, hoy=HOY
        )  # última 2026-12
    assert _liberados(con) == {
        "2027-01": (("Ágil", 100000), ("moto", 100000), ("Zeta", 100000))
    }


def test_liberacion_de_un_plan_cancelado(con, base):
    # Cancelado con pagos en la cuota de octubre: la última pasa a ser 2026-10 →
    # se libera en 2026-11 (y ya no en 2027-03).
    cuota_oct = con.execute(
        "SELECT id FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
        (base["plan_b"], base["oct"]),
    ).fetchone()["id"]
    pagos.registrar_pago(con, cuota_oct, 100000, HOY)
    cuotas.cancelar_plan(con, base["plan_b"], hoy=HOY)
    assert _liberados(con) == {"2026-11": (("Avant", 4111700), ("Plan B", 1000000))}


def test_plan_cancelado_sin_pagos_se_libera_antes_de_la_tabla(con, base):
    # Cancelado en 2026-10 sin pagos: su última cuota es 2026-09 → la liberación
    # cae en 2026-10, fuera de la tabla.
    cuotas.cancelar_plan(con, base["plan_b"], hoy=HOY)
    assert _liberados(con) == {"2026-11": (("Avant", 4111700),)}


def test_plan_cancelado_antes_de_empezar_no_libera_nada(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    pid = cuotas.crear_plan(
        con, "Futuro", _cat(con, "Otros"), None, 100000, 3, 2027, 1, hoy=HOY
    )
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert cuotas.ultima_cuota(cuotas.obtener_plan(con, pid)) is None
    assert _liberados(con) == {}
    assert all(g == 0 for g in _gastos_por_mes(con).values())


def test_prevision_es_inmutable(con, base):
    p = prevision.calcular_prevision(con, HOY)
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.estado = "x"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        p.meses[0].gastos = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Gráficos (RF-40 a RF-42, RN-46 a RN-48)
# ---------------------------------------------------------------------------


def test_ca_40_1_gastos_por_categoria_con_la_parte_propia(con):
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    servicios = _cat(con, "Servicios")
    gastos.agregar_gasto(con, oct_, "Alquiler", _cat(con, "Vivienda"), 26000000, "fijo")
    gastos.agregar_gasto(con, oct_, "Nafta", _cat(con, "Transporte"), 3000000, "unico")
    gastos.agregar_gasto(
        con, oct_, "Teléfono", _cat(con, "Comunicaciones"), 2000000, "fijo"
    )
    gastos.agregar_gasto(
        con,
        oct_,
        "Internet",
        servicios,
        3870000,
        "fijo",
        partes=[(sofia, None), (marsu, None)],
    )
    gastos.agregar_gasto(
        con,
        oct_,
        "Edenor",
        servicios,
        6628100,
        "fijo",
        partes=[(sofia, None), (marsu, None)],
    )
    datos = graficos.gastos_por_categoria(con, oct_)
    assert datos == [
        ("Vivienda", 26000000),
        ("Servicios", 3499368),  # 12.900 + 22.093,68
        ("Transporte", 3000000),
        ("Comunicaciones", 2000000),
    ]
    assert formatear_ars(3499368) == "$ 34.994"
    # Categorías sin gastos (Mercado, Salud, …) no aparecen.
    assert "Mercado" not in [c for c, _ in datos]


def test_por_categoria_con_partes_manuales_y_gasto_en_dolares(con):
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    otros = _cat(con, "Otros")
    gastos.agregar_gasto(
        con, oct_, "Internet", otros, 3870000, "fijo", partes=[(sofia, 3000000)]
    )
    gastos.agregar_gasto(
        con,
        oct_,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, None)],
    )
    # Internet: 38.700 − 30.000 = 8.700. Netflix: 24.000 − 12.000 = 12.000.
    assert graficos.gastos_por_categoria(con, oct_) == [("Otros", 870000 + 1200000)]


def test_por_categoria_parte_propia_en_cero_no_aparece(con):
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    gastos.agregar_gasto(
        con,
        oct_,
        "Regalo de Sofía",
        _cat(con, "Otros"),
        1000000,
        "unico",
        partes=[(sofia, 1000000)],
    )
    gastos.agregar_gasto(con, oct_, "Nafta", _cat(con, "Transporte"), 3000000, "unico")
    assert graficos.gastos_por_categoria(con, oct_) == [("Transporte", 3000000)]


def test_por_categoria_empates_ordenados_sin_acentos_y_mes_vacio(con):
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    assert graficos.gastos_por_categoria(con, oct_) == []
    for nombre in ["Zeta", "Ágil", "medio"]:
        gastos.agregar_gasto(con, oct_, "X", _cat(con, nombre), 100000, "fijo")
    assert [c for c, _ in graficos.gastos_por_categoria(con, oct_)] == [
        "Ágil",
        "medio",
        "Zeta",
    ]


def test_por_categoria_incluye_cuotas_y_pagos_no_importan(con, base):
    datos = dict(graficos.gastos_por_categoria(con, base["oct"]))
    # Otros: resto de fijos + regalo + cuota de Avant + cuota del plan B.
    assert datos["Otros"] == 80000000 - 26000000 - 3870000 + 1500000 + 4111700 + 1000000
    assert datos["Servicios"] == 1290000  # parte propia de Internet
    for g in gastos.listar_gastos(con, base["oct"]):
        pagos.marcar_pagado(con, g["id"], HOY)
    assert dict(graficos.gastos_por_categoria(con, base["oct"])) == datos


def test_ca_41_1_y_41_2_ahorro_por_mes(con):
    otros = _cat(con, "Otros")
    ago = meses.crear_primer_mes(con, 2026, 8, 120000, 160000)
    sep = meses.crear_mes_siguiente(con, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    gastos.agregar_gasto(
        con, ago, "Gastos", otros, 152000000, "unico"
    )  # U = 950,00 → ahorro 250,00
    gastos.agregar_gasto(
        con, sep, "Gastos", otros, 147200000, "unico"
    )  # U = 920,00 → ahorro 280,00
    gastos.agregar_gasto(
        con, oct_, "Gastos", otros, 143461700, "unico"
    )  # ahorro 303,36
    assert graficos.ahorro_por_mes(con) == [
        (2026, 8, 25000),
        (2026, 9, 28000),
        (2026, 10, 30336),
    ]
    meses.editar_cotizacion(con, oct_, 170000)
    assert graficos.ahorro_por_mes(con) == [
        (2026, 8, 25000),
        (2026, 9, 28000),
        (2026, 10, 35611),
    ]


def test_ca_41_3_mes_sin_cotizacion_queda_vacio(con):
    otros = _cat(con, "Otros")
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, None)
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 100000, "unico")
    assert graficos.ahorro_por_mes(con) == [(2026, 9, 120000), (2026, 10, None)]
    assert sep


def test_ahorro_por_mes_sin_meses(con):
    assert graficos.ahorro_por_mes(con) == []


def test_ca_42_1_prevision_de_gastos_igual_a_la_tabla(con, base):
    datos = graficos.prevision_de_gastos(con, HOY)
    assert [g for _, _, g in datos] == [81000000] * 4 + [80000000] * 8
    assert datos[0][:2] == (2026, 11)
    _claude(con, base, 160000)
    meses.editar_cotizacion(con, base["oct"], 170000)
    assert [g for _, _, g in graficos.prevision_de_gastos(con, HOY)] == [
        84400000
    ] * 4 + [83400000] * 8


def test_prevision_de_gastos_sin_mes_actual(con):
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    assert graficos.prevision_de_gastos(con, HOY) == []
