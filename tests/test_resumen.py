"""Pruebas de la lógica del paso 3: sueldo, cotización, ingresos extra, cambios, meta y
resumen del mes (RF-23 a RF-27, RF-35 a RF-37; RN-12 a RN-19, RN-38, RN-39;
CA-23.x a CA-27.x, CA-35.1/35.3/35.4, CA-36.x, CA-37.x y las partes del paso 3 de
CA-43.1, 43.2, 43.7 y 45.1). Base en memoria, datos inventados y fechas fijas.

Los valores esperados se calcularon a mano con las fórmulas de los requisitos, no
copiando lo que da el código."""

import dataclasses
from datetime import date, datetime

import pytest

from app.logica import cambios, catalogos, configuracion, gastos, ingresos, meses, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    MONTO_MAXIMO_CENT,
    convertir_ars_a_usd,
    formatear_ars,
    formatear_cotizacion_corta,
    formatear_usd,
)
from app.logica.resumen import Resumen, calcular_resumen
from tests.ayudantes import id_por_nombre, insertar_mes, insertar_plan

HOY = date(2026, 10, 4)


@pytest.fixture
def otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


@pytest.fixture
def base(con, mes_id, otros):
    """Mes 2026-10 (S = 1.200, K = 1.600) con gastos que suman 1.434.617 (módulo E)."""
    gastos.agregar_gasto(con, mes_id, "Gastos del mes", otros, 143461700, "unico")
    return mes_id


def _r(con, mes_id) -> Resumen:
    return calcular_resumen(con, mes_id)


def _usd(r_valor):
    return formatear_usd(r_valor) if r_valor is not None else None


# ---------------------------------------------------------------------------
# Conversión ARS → USD (RN-15, RN-16, RN-03)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("pesos", "cotizacion", "usd"),
    [
        (143461700, 160000, 89664),  # planilla: 896,6356… → 896,64
        (133461700, 160000, 83414),  # CA-24.1: 834,135… → 834,14 (mitad hacia arriba)
        (143461700, 170000, 84389),  # CA-25.1: 843,892… → 843,89
        (6000000, 160000, 3750),  # CA-27.3: 60.000 / 1.600 = 37,50
        (1, 200, 1),  # 0,005 → 0,01 (mitad hacia arriba)
        (1, 201, 0),  # 0,00497… → 0
        (0, 160000, 0),
        (100, 143250, 0),  # 1 peso a 1.432,50 = 0,0007 → 0
        (143250, 143250, 100),  # cotización con centavos: exacto US$ 1,00
    ],
)
def test_convertir_ars_a_usd(pesos, cotizacion, usd):
    assert convertir_ars_a_usd(pesos, cotizacion) == usd


# ---------------------------------------------------------------------------
# Ejemplo de la planilla y CA-35.1 (RN-12 a RN-17, RN-20)
# ---------------------------------------------------------------------------


def test_ejemplo_de_la_planilla(con, base):
    r = _r(con, base)
    assert (r.sueldo_usd, r.cotizacion, r.total_gastos) == (120000, 160000, 143461700)
    assert (r.pesos_a_cubrir, r.pesos_sobrantes) == (143461700, 0)
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 896,64", "US$ 303,36")
    assert r.sobrantes_usd == 0
    assert (r.extras_ars, r.extras_usd, r.cambiado_usd, r.cambiado_ars) == (0, 0, 0, 0)
    assert r.falta_cotizacion is False
    assert r.total_me_deben == 0  # RN-40 llega en el paso 5


def test_ca_35_1_con_400000_pagados(con, mes_id, otros):
    # CA-35.1: gastos 1.434.617 con 400.000 pagados: pendiente 1.034.617; lo demás igual.
    a = gastos.agregar_gasto(con, mes_id, "Alquiler", otros, 40000000, "fijo")
    gastos.agregar_gasto(con, mes_id, "Resto", otros, 103461700, "unico")
    pagos.marcar_pagado(con, a, HOY)
    r = _r(con, mes_id)
    assert formatear_usd(r.sueldo_usd) == "US$ 1.200,00"
    assert formatear_cotizacion_corta(r.cotizacion) == "$ 1.600"
    assert formatear_ars(r.total_gastos) == "$ 1.434.617"
    assert formatear_ars(r.pesos_a_cubrir) == "$ 1.434.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 896,64", "US$ 303,36")
    assert formatear_ars(r.pendiente_de_pago) == "$ 1.034.617"


def test_rn_19_pagos_no_cambian_el_resumen(con, base, otros):
    # RN-19: los pagos y los tildes no afectan los cálculos (solo el pendiente).
    antes = _r(con, base)
    gid = gastos.listar_gastos(con, base)[0]["id"]
    pagos.registrar_pago(con, gid, 50000000, HOY)
    pagos.marcar_pagado(con, gid, HOY)
    despues = _r(con, base)
    assert (
        dataclasses.replace(despues, pendiente_de_pago=antes.pendiente_de_pago) == antes
    )
    assert (antes.pendiente_de_pago, despues.pendiente_de_pago) == (143461700, 0)
    pagos.quitar_pagos(con, gid)
    assert _r(con, base) == antes


def test_resumen_es_inmutable(con, base):
    r = _r(con, base)
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.ahorro_usd = 0  # type: ignore[misc]


def test_resumen_de_mes_inexistente(con):
    with pytest.raises(ErrorDeValidacion, match="^El mes no existe.$"):
        calcular_resumen(con, 999)


def test_mes_vacio(con, mes_id):
    r = _r(con, mes_id)
    assert (r.total_gastos, r.pesos_a_cubrir, r.usd_a_cambiar) == (0, 0, 0)
    assert r.ahorro_usd == 120000  # todo el sueldo
    assert r.capacidad == 192000000  # S × K
    assert r.pendiente_de_pago == 0


def test_rn_12_total_cuenta_gastos_pagados_o_no(con, mes_id, otros):
    a = gastos.agregar_gasto(con, mes_id, "A", otros, 1000000, "fijo")
    gastos.agregar_gasto(con, mes_id, "B", otros, 2000000, "unico")
    pagos.marcar_pagado(con, a, HOY)
    assert _r(con, mes_id).total_gastos == 3000000


def test_datos_de_otros_meses_no_cuentan(con, base, otros):
    nov = insertar_mes(con, 2026, 11, sueldo=50000, cotizacion=100000)
    gastos.agregar_gasto(con, nov, "Otro", otros, 99900, "fijo")
    ingresos.agregar_ingreso(con, nov, "Bono", "ARS", 1000000)
    ingresos.agregar_ingreso(con, nov, "Freelance", "USD", 5000)
    cambios.agregar_cambio(con, nov, 10000, 100000, fecha=HOY)
    r = _r(con, base)
    assert (r.total_gastos, r.extras_ars, r.extras_usd, r.cambiado_usd) == (
        143461700,
        0,
        0,
        0,
    )
    assert _usd(r.ahorro_usd) == "US$ 303,36"


# ---------------------------------------------------------------------------
# Sueldo (RF-23, CA-23.x)
# ---------------------------------------------------------------------------


def test_ca_23_1_cambiar_el_sueldo(con, base):
    assert _usd(_r(con, base).ahorro_usd) == "US$ 303,36"
    meses.editar_sueldo(con, base, 130000)
    r = _r(con, base)
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 896,64", "US$ 403,36")


def test_ca_23_2_sueldo_cero_da_deficit(con, base):
    meses.editar_sueldo(con, base, 0)
    assert _r(con, base).ahorro_usd == -89664


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        (-1, "El sueldo no puede ser negativo."),
        (1.5, "El sueldo tiene que ser un número entero de centavos."),
        (True, "El sueldo tiene que ser un número entero de centavos."),
        (None, "El sueldo tiene que ser un número entero de centavos."),
        (MONTO_MAXIMO_CENT + 1, "El sueldo es demasiado grande."),
    ],
)
def test_ca_23_2_sueldo_invalido(con, base, valor, mensaje):
    with pytest.raises(ErrorDeValidacion) as error:
        meses.editar_sueldo(con, base, valor)
    assert (str(error.value), error.value.campo) == (mensaje, "sueldo")
    assert meses.obtener_mes(con, base)["sueldo_usd_cent"] == 120000


def test_editar_sueldo_de_mes_inexistente(con):
    with pytest.raises(ErrorDeValidacion) as error:
        meses.editar_sueldo(con, 999, 100)
    assert (str(error.value), error.value.campo) == ("El mes no existe.", None)


def test_ca_35_3_deficit(con, base):
    meses.editar_sueldo(con, base, 80000)
    r = _r(con, base)
    assert r.ahorro_usd == -9664
    assert formatear_usd(r.ahorro_usd) == "-US$ 96,64"


# ---------------------------------------------------------------------------
# Ingresos extra (RF-24, CA-24.x)
# ---------------------------------------------------------------------------


def test_ca_24_1_extra_en_pesos(con, base):
    ingresos.agregar_ingreso(con, base, "Venta de bici", "ARS", 10000000)
    r = _r(con, base)
    assert formatear_ars(r.pesos_a_cubrir) == "$ 1.334.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 834,14", "US$ 365,86")
    assert r.extras_ars == 10000000


def test_ca_24_2_extra_en_dolares(con, base):
    ingresos.agregar_ingreso(con, base, "Freelance", "USD", 5000)
    r = _r(con, base)
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 896,64", "US$ 353,36")
    assert r.extras_usd == 5000


@pytest.mark.parametrize(
    ("descripcion", "moneda", "monto", "campo"),
    [
        ("Bono", "ARS", 0, "monto"),  # CA-24.3
        ("Bono", "ARS", -100, "monto"),
        ("Bono", "EUR", 100, "moneda"),  # CA-24.3
        ("Bono", "ars", 100, "moneda"),
        ("Bono", None, 100, "moneda"),
        ("Bono", "USD", 1.5, "monto"),
        ("Bono", "USD", True, "monto"),
        ("Bono", "USD", MONTO_MAXIMO_CENT + 1, "monto"),
        ("", "ARS", 100, "descripcion"),
        ("   ", "ARS", 100, "descripcion"),
    ],
)
def test_ca_24_3_ingreso_invalido(con, base, descripcion, moneda, monto, campo):
    with pytest.raises(ErrorDeValidacion) as error:
        ingresos.agregar_ingreso(con, base, descripcion, moneda, monto)
    assert error.value.campo == campo
    assert ingresos.listar_ingresos(con, base) == []


def test_mensajes_de_ingreso(con, base):
    with pytest.raises(ErrorDeValidacion, match="^Ingresá una descripción.$"):
        ingresos.agregar_ingreso(con, base, " ", "ARS", 100)
    with pytest.raises(ErrorDeValidacion, match="^La moneda tiene que ser ARS o USD.$"):
        ingresos.agregar_ingreso(con, base, "Bono", "EUR", 100)
    with pytest.raises(ErrorDeValidacion, match="^El monto tiene que ser mayor a 0.$"):
        ingresos.agregar_ingreso(con, base, "Bono", "ARS", 0)


def test_abm_de_ingresos(con, base):
    a = ingresos.agregar_ingreso(con, base, "  Venta   de bici ", "ARS", 10000000)
    b = ingresos.agregar_ingreso(con, base, "Freelance", "USD", 5000)
    assert ingresos.obtener_ingreso(con, a)["descripcion"] == "Venta de bici"
    assert [f["id"] for f in ingresos.listar_ingresos(con, base)] == [a, b]
    assert ingresos.totales_por_moneda(con, base) == {"ARS": 10000000, "USD": 5000}

    # Editar, incluso cambiando la moneda.
    ingresos.editar_ingreso(con, a, "Venta de bici", "USD", 2000)
    assert ingresos.totales_por_moneda(con, base) == {"ARS": 0, "USD": 7000}
    with pytest.raises(ErrorDeValidacion):
        ingresos.editar_ingreso(con, a, "", "USD", 2000)
    assert ingresos.obtener_ingreso(con, a)["monto_cent"] == 2000

    ingresos.borrar_ingreso(con, a)
    assert ingresos.obtener_ingreso(con, a) is None
    assert ingresos.totales_por_moneda(con, base) == {"ARS": 0, "USD": 5000}


def test_varios_extras_se_suman(con, base):
    ingresos.agregar_ingreso(con, base, "A", "ARS", 5000000)
    ingresos.agregar_ingreso(con, base, "B", "ARS", 5000000)
    ingresos.agregar_ingreso(con, base, "C", "USD", 2500)
    ingresos.agregar_ingreso(con, base, "D", "USD", 2500)
    r = _r(con, base)
    assert (r.extras_ars, r.extras_usd) == (10000000, 5000)
    assert _usd(r.ahorro_usd) == "US$ 415,86"  # 1.200 + 50 − 834,14


@pytest.mark.parametrize("accion", ["editar", "borrar"])
def test_ingreso_inexistente(con, base, accion):
    with pytest.raises(ErrorDeValidacion) as error:
        if accion == "editar":
            ingresos.editar_ingreso(con, 999, "Bono", "ARS", 100)
        else:
            ingresos.borrar_ingreso(con, 999)
    assert (str(error.value), error.value.campo) == ("Ese ingreso ya no existe.", None)


def test_ingreso_en_mes_inexistente(con):
    with pytest.raises(ErrorDeValidacion, match="^El mes no existe.$"):
        ingresos.agregar_ingreso(con, 999, "Bono", "ARS", 100)


def test_totales_por_moneda_sin_ingresos(con, base):
    assert ingresos.totales_por_moneda(con, base) == {"ARS": 0, "USD": 0}


# ---------------------------------------------------------------------------
# Cotización del mes (RF-25, CA-25.x)
# ---------------------------------------------------------------------------


def test_ca_25_1_cambiar_la_cotizacion(con, base):
    meses.editar_cotizacion(con, base, 170000)
    r = _r(con, base)
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 843,89", "US$ 356,11")


@pytest.mark.parametrize(
    ("valor", "mensaje"),
    [
        (0, "La cotización tiene que ser mayor a 0."),  # CA-25.2
        (-160000, "La cotización tiene que ser mayor a 0."),  # CA-25.2
        (None, "Ingresá la cotización."),  # no se puede volver a dejar vacía
        (1600.5, "La cotización tiene que ser un número entero de centavos."),
        (True, "La cotización tiene que ser un número entero de centavos."),
        (MONTO_MAXIMO_CENT + 1, "La cotización es demasiado grande."),
    ],
)
def test_ca_25_2_cotizacion_invalida(con, base, valor, mensaje):
    with pytest.raises(ErrorDeValidacion) as error:
        meses.editar_cotizacion(con, base, valor)
    assert (str(error.value), error.value.campo) == (mensaje, "cotizacion")
    assert meses.obtener_mes(con, base)["cotizacion_cent"] == 160000


def test_cargar_la_cotizacion_a_un_mes_que_no_tenia(con, otros):
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, None)
    gastos.agregar_gasto(con, mes, "Gastos", otros, 143461700, "unico")
    assert _r(con, mes).falta_cotizacion is True
    meses.editar_cotizacion(con, mes, 160000)
    assert _usd(_r(con, mes).ahorro_usd) == "US$ 303,36"


def test_editar_cotizacion_de_mes_inexistente(con):
    with pytest.raises(ErrorDeValidacion, match="^El mes no existe.$"):
        meses.editar_cotizacion(con, 999, 160000)


def test_ca_25_3_sin_cotizacion_y_con_gastos(con, otros):
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, None)
    gastos.agregar_gasto(con, mes, "Gastos", otros, 143461700, "fijo")
    configuracion.guardar_meta(con, 30000)
    r = _r(con, mes)
    assert r.cotizacion is None
    assert (r.usd_a_cambiar, r.sobrantes_usd, r.ahorro_usd, r.capacidad) == (
        None,
        None,
        None,
        None,
    )
    assert r.avance_meta is None
    assert r.falta_cotizacion is True
    # Lo que no depende de la cotización se calcula igual.
    assert (r.total_gastos, r.pesos_a_cubrir) == (143461700, 143461700)


def test_ca_25_4_cotizacion_con_centavos(con, base):
    meses.editar_cotizacion(con, base, 143250)
    r = _r(con, base)
    assert formatear_cotizacion_corta(r.cotizacion) == "$ 1.432,50"
    # 1.434.617 / 1.432,50 = 1.001,4778… → US$ 1.001,48
    assert r.usd_a_cambiar == 100148


def test_ca_45_1_la_cotizacion_del_mes_no_cambia_los_gastos_en_dolares(
    con, base, otros
):
    gastos.agregar_gasto(
        con, base, "Claude", otros, None, "unico", None, "USD", 2000, 160000
    )
    meses.editar_cotizacion(con, base, 170000)
    r = _r(con, base)
    assert formatear_ars(r.total_gastos) == "$ 1.466.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 862,72", "US$ 337,28")


def test_ca_43_1_y_43_2_resumen_con_gasto_en_dolares(con, base, otros):
    gid = gastos.agregar_gasto(
        con, base, "Claude", otros, None, "unico", None, "USD", 2000, 160000
    )
    r = _r(con, base)
    assert formatear_ars(r.pesos_a_cubrir) == "$ 1.466.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 916,64", "US$ 283,36")
    # CA-43.2: cotización del gasto 2.100 (dólar tarjeta); USD a cambiar con la del mes.
    gastos.editar_gasto(
        con, gid, "Claude", otros, None, "unico", None, "USD", 2000, 210000
    )
    r = _r(con, base)
    assert formatear_ars(r.total_gastos) == "$ 1.476.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 922,89", "US$ 277,11")


# ---------------------------------------------------------------------------
# Cambios realizados (RF-26, RN-13, CA-26.x, CA-27.x)
# ---------------------------------------------------------------------------


def test_ca_26_1_ars_sugeridos(con):
    assert cambios.ars_sugeridos(50000, 150000) == 75000000
    assert cambios.ars_sugeridos(1999, 143250) == 2863568  # mitad hacia arriba


def test_ca_26_1_y_26_2_cambio_sugerido_y_corregido(con, base):
    cid = cambios.agregar_cambio(con, base, 50000, 150000, fecha=HOY)
    assert cambios.obtener_cambio(con, cid)["ars_cent"] == 75000000
    cambios.editar_cambio(con, cid, 50000, 150000, 74500000)
    fila = cambios.obtener_cambio(con, cid)
    assert (fila["ars_cent"], fila["fecha"]) == (74500000, "2026-10-04")


@pytest.mark.parametrize(
    ("usd", "cot", "ars", "campo"),
    [
        (0, 150000, None, "usd"),  # CA-26.3
        (-100, 150000, None, "usd"),
        (50000, 0, None, "cotizacion"),  # CA-26.3
        (50000, -1, None, "cotizacion"),
        (50000, 150000, 0, "ars"),  # CA-26.3
        (50000, 150000, -1, "ars"),
        (1.5, 150000, None, "usd"),
        (50000, True, None, "cotizacion"),
        (50000, 150000, "750000", "ars"),
        (None, 150000, None, "usd"),
        (50000, None, None, "cotizacion"),
        (1, 1, None, "ars"),  # US$ 0,01 × $ 0,01 = 0 pesos sugeridos
        (MONTO_MAXIMO_CENT, 160000, None, "ars"),  # sugeridos sobre el tope
    ],
)
def test_ca_26_3_cambio_invalido(con, base, usd, cot, ars, campo):
    with pytest.raises(ErrorDeValidacion) as error:
        cambios.agregar_cambio(con, base, usd, cot, ars, HOY)
    assert error.value.campo == campo
    assert cambios.listar_cambios(con, base) == []


def test_mensajes_de_cambio(con, base):
    with pytest.raises(
        ErrorDeValidacion, match="^El monto en dólares tiene que ser mayor a 0.$"
    ):
        cambios.agregar_cambio(con, base, 0, 150000, fecha=HOY)
    with pytest.raises(
        ErrorDeValidacion, match="^La cotización tiene que ser mayor a 0.$"
    ):
        cambios.agregar_cambio(con, base, 100, 0, fecha=HOY)
    with pytest.raises(
        ErrorDeValidacion, match="^El monto en pesos tiene que ser mayor a 0.$"
    ):
        cambios.agregar_cambio(con, base, 100, 150000, 0, HOY)


def test_ca_27_1_cambio_de_750000(con, base):
    cambios.agregar_cambio(con, base, 50000, 150000, fecha=HOY)
    r = _r(con, base)
    assert formatear_ars(r.pesos_a_cubrir) == "$ 684.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 427,89", "US$ 272,11")
    assert (r.cambiado_usd, r.cambiado_ars) == (50000, 75000000)
    # Cambiar la cotización del mes a 1.700 no modifica los 750.000 del cambio.
    meses.editar_cotizacion(con, base, 170000)
    assert _r(con, base).cambiado_ars == 75000000
    assert cambios.listar_cambios(con, base)[0]["ars_cent"] == 75000000


def test_ca_27_2_cambio_corregido_a_745000(con, base):
    cambios.agregar_cambio(con, base, 50000, 150000, 74500000, HOY)
    r = _r(con, base)
    assert formatear_ars(r.pesos_a_cubrir) == "$ 689.617"
    assert (_usd(r.usd_a_cambiar), _usd(r.ahorro_usd)) == ("US$ 431,01", "US$ 268,99")


@pytest.fixture
def gastos_100000(con, mes_id, otros):
    gastos.agregar_gasto(con, mes_id, "Gastos", otros, 10000000, "unico")
    return mes_id


def test_ca_27_3_y_ca_35_4_pesos_sobrantes(con, gastos_100000):
    mes = gastos_100000
    cambios.agregar_cambio(con, mes, 10000, 160000, fecha=HOY)  # 100 USD = 160.000
    r = _r(con, mes)
    assert (r.pesos_a_cubrir, r.usd_a_cambiar) == (0, 0)
    assert formatear_ars(r.pesos_sobrantes) == "$ 60.000"  # CA-35.4
    assert _usd(r.sobrantes_usd) == "US$ 37,50"
    assert _usd(r.ahorro_usd) == "US$ 1.137,50"


def test_ca_27_4_sobrantes_por_extra_en_pesos(con, gastos_100000):
    mes = gastos_100000
    ingresos.agregar_ingreso(con, mes, "Bono", "ARS", 15000000)
    r = _r(con, mes)
    assert formatear_ars(r.pesos_sobrantes) == "$ 50.000"
    assert (_usd(r.sobrantes_usd), _usd(r.ahorro_usd)) == ("US$ 31,25", "US$ 1.231,25")


def test_ca_27_5_sin_cotizacion(con, otros):
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, None)
    gid = gastos.agregar_gasto(con, mes, "Gastos", otros, 10000000, "unico")
    cambios.agregar_cambio(con, mes, 10000, 160000, fecha=HOY)
    r = _r(con, mes)
    assert (r.ahorro_usd, r.falta_cotizacion) == (None, True)
    assert r.pesos_sobrantes == 6000000  # los pesos sí se saben
    # Gastos 160.000 con el mismo cambio y sin cotización (F = 0): ahorro 1.100,00.
    gastos.editar_gasto(con, gid, "Gastos", otros, 16000000, "unico")
    r = _r(con, mes)
    assert _usd(r.ahorro_usd) == "US$ 1.100,00"
    assert (r.usd_a_cambiar, r.sobrantes_usd) == (0, 0)
    assert r.falta_cotizacion is False
    assert r.capacidad is None  # la capacidad sigue necesitando la cotización


def test_varios_cambios_se_suman(con, base):
    cambios.agregar_cambio(con, base, 50000, 150000, fecha=HOY)
    cambios.agregar_cambio(con, base, 10000, 160000, 15900000, HOY)  # con comisión
    assert cambios.totales(con, base) == {"usd": 60000, "ars": 90900000}


def test_cambio_con_cotizacion_con_centavos(con, base):
    cid = cambios.agregar_cambio(con, base, 1999, 143250, fecha=HOY)
    assert cambios.obtener_cambio(con, cid)["ars_cent"] == 2863568
    assert formatear_cotizacion_corta(
        cambios.obtener_cambio(con, cid)["cotizacion_cent"]
    ) == ("$ 1.432,50")


def test_editar_cambio_sin_ars_vuelve_a_sugerir(con, base):
    # RN-13: si cambian los USD o la cotización, se vuelve a sugerir el producto.
    cid = cambios.agregar_cambio(con, base, 50000, 150000, 74500000, HOY)
    cambios.editar_cambio(con, cid, 60000, 150000)
    assert cambios.obtener_cambio(con, cid)["ars_cent"] == 90000000


def test_fechas_de_los_cambios(con, base, monkeypatch):
    a = cambios.agregar_cambio(con, base, 100, 150000, fecha=date(2026, 10, 20))
    b = cambios.agregar_cambio(
        con,
        base,
        100,
        150000,
        fecha=datetime(2026, 10, 5, 22, 0),  # noqa: DTZ001
    )
    c = cambios.agregar_cambio(con, base, 100, 150000, fecha=date(2026, 10, 5))
    assert cambios.obtener_cambio(con, b)["fecha"] == "2026-10-05"  # solo el día
    assert [f["id"] for f in cambios.listar_cambios(con, base)] == [b, c, a]
    # Editar sin fecha conserva la que tenía; con fecha la cambia.
    cambios.editar_cambio(con, a, 200, 150000)
    assert cambios.obtener_cambio(con, a)["fecha"] == "2026-10-20"
    cambios.editar_cambio(con, a, 200, 150000, fecha=datetime(2026, 10, 1, 9, 0))  # noqa: DTZ001
    assert cambios.obtener_cambio(con, a)["fecha"] == "2026-10-01"


def test_fecha_por_defecto_de_un_cambio_es_hoy(con, base, monkeypatch):
    class FechaFija(date):
        @classmethod
        def today(cls):
            return cls(2026, 12, 31)

    monkeypatch.setattr(cambios, "date", FechaFija)
    cid = cambios.agregar_cambio(con, base, 100, 150000)
    assert cambios.obtener_cambio(con, cid)["fecha"] == "2026-12-31"


@pytest.mark.parametrize("accion", ["editar", "borrar"])
def test_cambio_inexistente(con, base, accion):
    with pytest.raises(ErrorDeValidacion) as error:
        if accion == "editar":
            cambios.editar_cambio(con, 999, 100, 150000)
        else:
            cambios.borrar_cambio(con, 999)
    assert (str(error.value), error.value.campo) == ("Ese cambio ya no existe.", None)


def test_borrar_cambio(con, base):
    cid = cambios.agregar_cambio(con, base, 50000, 150000, fecha=HOY)
    cambios.borrar_cambio(con, cid)
    assert cambios.listar_cambios(con, base) == []
    assert _usd(_r(con, base).ahorro_usd) == "US$ 303,36"


def test_editar_cambio_invalido_no_cambia_nada(con, base):
    cid = cambios.agregar_cambio(con, base, 50000, 150000, fecha=HOY)
    with pytest.raises(ErrorDeValidacion):
        cambios.editar_cambio(con, cid, 0, 150000)
    fila = cambios.obtener_cambio(con, cid)
    assert (fila["usd_cent"], fila["ars_cent"]) == (50000, 75000000)


def test_cambio_en_mes_inexistente(con):
    with pytest.raises(ErrorDeValidacion, match="^El mes no existe.$"):
        cambios.agregar_cambio(con, 999, 100, 150000, fecha=HOY)


# ---------------------------------------------------------------------------
# Meta de ahorro (RF-36, RN-39, CA-36.x)
# ---------------------------------------------------------------------------


def test_sin_meta(con, base):
    assert configuracion.obtener_meta(con) is None
    r = _r(con, base)
    assert (r.meta_usd, r.avance_meta) == (None, None)


def test_ca_36_1_avance_de_la_meta(con, base):
    configuracion.guardar_meta(con, 30000)
    r = _r(con, base)
    assert r.meta_usd == 30000
    assert r.avance_meta == pytest.approx(1.0112)  # 101,12 %: la barra queda llena
    configuracion.guardar_meta(con, 60000)
    assert _r(con, base).avance_meta == pytest.approx(0.5056)


def test_ca_36_2_ahorro_negativo_y_meta_invalida(con, base):
    configuracion.guardar_meta(con, 30000)
    meses.editar_sueldo(con, base, 80000)
    assert _r(con, base).avance_meta < 0  # la pantalla deja la barra en 0 %
    for valor, mensaje in [
        (0, "La meta tiene que ser mayor a 0."),
        (-100, "La meta tiene que ser mayor a 0."),
        (None, "Ingresá la meta."),
        (1.5, "La meta tiene que ser un número entero de centavos."),
        (True, "La meta tiene que ser un número entero de centavos."),
        (MONTO_MAXIMO_CENT + 1, "La meta es demasiado grande."),
    ]:
        with pytest.raises(ErrorDeValidacion) as error:
            configuracion.guardar_meta(con, valor)
        assert (str(error.value), error.value.campo) == (mensaje, "meta")
    assert configuracion.obtener_meta(con) == 30000


def test_ahorro_cero_con_meta(con, base):
    configuracion.guardar_meta(con, 30000)
    meses.editar_sueldo(con, base, 89664)  # exactamente lo que hay que cambiar
    r = _r(con, base)
    assert (r.ahorro_usd, r.avance_meta) == (0, 0.0)


def test_ca_36_3_la_meta_es_la_misma_en_todos_los_meses(con, base, otros):
    sep = insertar_mes(con, 2026, 9)
    gastos.agregar_gasto(con, sep, "Gastos", otros, 143461700, "unico")
    configuracion.guardar_meta(con, 30000)
    assert (
        _r(con, sep).avance_meta == _r(con, base).avance_meta == pytest.approx(1.0112)
    )
    configuracion.guardar_meta(con, 60000)
    assert _r(con, sep).avance_meta == pytest.approx(0.5056)


def test_quitar_la_meta(con, base):
    configuracion.guardar_meta(con, 30000)
    configuracion.quitar_meta(con)
    assert configuracion.obtener_meta(con) is None
    assert _r(con, base).avance_meta is None
    configuracion.quitar_meta(con)  # quitar sin meta no da error
    configuracion.guardar_meta(con, 45000)  # se puede volver a cargar
    assert configuracion.obtener_meta(con) == 45000


def test_la_meta_no_toca_otras_configuraciones(con):
    configuracion.guardar_meta(con, 30000)
    configuracion.quitar_meta(con)
    fila = con.execute(
        "SELECT valor FROM configuracion WHERE clave = 'datos_iniciales_cargados'"
    ).fetchone()
    assert fila is not None


# ---------------------------------------------------------------------------
# Capacidad de endeudamiento (RN-38, CA-37.x, CA-43.7)
# ---------------------------------------------------------------------------


@pytest.fixture
def caso_37(con, mes_id, otros):
    """CA-37.1: fijos 785.300, cuota del mes 41.117 (plan insertado por SQL, paso 4),
    pago único 15.000, meta 300 USD; S = 1.200, K = 1.600."""
    gastos.agregar_gasto(con, mes_id, "Fijos", otros, 78530000, "fijo")
    plan = insertar_plan(con, "Avant Service", otros, monto=4111700, cuotas=3)
    with con:
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Avant Service', ?, 4111700, 'cuota', ?)",
            (mes_id, otros, plan),
        )
    gastos.agregar_gasto(con, mes_id, "Regalo", otros, 1500000, "unico")
    configuracion.guardar_meta(con, 30000)
    return mes_id


def test_ca_37_1_capacidad(con, caso_37):
    r = _r(con, caso_37)
    assert r.gastos_fijos_y_cuotas == 78530000 + 4111700  # el pago único no cuenta
    assert formatear_ars(r.capacidad) == "$ 613.583"


def test_ca_37_2_sin_meta(con, caso_37):
    configuracion.quitar_meta(con)
    assert formatear_ars(_r(con, caso_37).capacidad) == "$ 1.093.583"


def test_ca_37_3_capacidad_negativa(con, caso_37):
    configuracion.guardar_meta(con, 100000)
    r = _r(con, caso_37)
    assert r.capacidad == -50641700
    assert formatear_ars(r.capacidad) == "-$ 506.417"


def test_ca_37_4_con_cotizacion_1700(con, caso_37):
    meses.editar_cotizacion(con, caso_37, 170000)
    assert formatear_ars(_r(con, caso_37).capacidad) == "$ 703.583"


def test_capacidad_no_cuenta_ingresos_extra(con, caso_37):
    ingresos.agregar_ingreso(con, caso_37, "Bono", "ARS", 10000000)
    ingresos.agregar_ingreso(con, caso_37, "Freelance", "USD", 10000)
    assert formatear_ars(_r(con, caso_37).capacidad) == "$ 613.583"


def test_capacidad_no_cambia_con_pagos(con, caso_37):
    for g in gastos.listar_gastos(con, caso_37):
        pagos.marcar_pagado(con, g["id"], HOY)
    assert formatear_ars(_r(con, caso_37).capacidad) == "$ 613.583"


@pytest.mark.parametrize(
    ("tipo", "capacidad"), [("fijo", "$ 581.583"), ("unico", "$ 613.583")]
)
def test_ca_43_7_capacidad_con_claude(con, caso_37, otros, tipo, capacidad):
    gastos.agregar_gasto(
        con, caso_37, "Claude", otros, None, tipo, None, "USD", 2000, 160000
    )
    assert formatear_ars(_r(con, caso_37).capacidad) == capacidad


def test_capacidad_con_meta_y_cotizacion_con_centavos(con, mes_id):
    # Meta × K con redondeo: 300,01 × 1.432,50 = 429.764,325 → 429.764,33.
    meses.editar_cotizacion(con, mes_id, 143250)
    configuracion.guardar_meta(con, 30001)
    r = _r(con, mes_id)
    sueldo_en_pesos = 120000 * 143250 // 100  # 1.719.000 exacto
    assert r.capacidad == sueldo_en_pesos - 42976433
