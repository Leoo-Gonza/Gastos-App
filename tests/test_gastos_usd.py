"""Pruebas de la lógica de los gastos en dólares (RF-43 a RF-46, RN-53 a RN-56;
CA-43.1 a 43.4, CA-44.x, CA-45.1 a 45.6, CA-45.8) y de la conversión y el formato
(RN-53, RN-04 para cotizaciones). Base en memoria y datos inventados."""

import pytest

from app.logica import catalogos, gastos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    MONTO_MAXIMO_CENT,
    convertir_usd_a_ars,
    formatear_ars,
    formatear_cotizacion,
    formatear_cotizacion_corta,
    formatear_detalle_usd,
)
from tests.ayudantes import cantidad_filas, id_por_nombre, insertar_pago, insertar_plan

# ---------------------------------------------------------------------------
# Conversión y formato (RN-53, RN-04)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("usd", "cotizacion", "ars"),
    [
        (2000, 160000, 3200000),  # RN-53: US$ 20,00 × 1.600 = 32.000
        (1999, 143250, 2863568),  # RN-53: 2863567,5 → 2863568 (mitad hacia arriba)
        (1299, 143250, 1860818),  # diseño §4.1: 18.608,175 → 18.608,18
        (2000, 210000, 4200000),  # CA-43.2: dólar tarjeta
        (1500, 160000, 2400000),
        (1, 40, 0),  # CA-44.5: 0,004 ARS → 0
        (1, 50, 1),  # 0,005 → 0,01 (mitad hacia arriba)
        (1, 149, 1),
        (1, 150, 2),
        (
            MONTO_MAXIMO_CENT,
            MONTO_MAXIMO_CENT,
            MONTO_MAXIMO_CENT * MONTO_MAXIMO_CENT // 100,
        ),
    ],
)
def test_convertir_usd_a_ars(usd, cotizacion, ars):
    # RN-53: centavos de USD × centavos de ARS por US$ ÷ 100, redondeo mitad hacia arriba.
    assert convertir_usd_a_ars(usd, cotizacion) == ars


def test_conversion_se_ve_como_en_los_requisitos():
    # RN-53: "US$ 19,99 × $ 1.432,50 = $ 28.636".
    pesos = convertir_usd_a_ars(1999, 143250)
    assert f"{formatear_detalle_usd(1999, 143250)} = {formatear_ars(pesos)}" == (
        "US$ 19,99 × $ 1.432,50 = $ 28.636"
    )


@pytest.mark.parametrize(
    ("centavos", "texto"),
    [
        (160000, "$ 1.600"),
        (143250, "$ 1.432,50"),  # con decimales: no se redondea a "$ 1.433"
        (143205, "$ 1.432,05"),
        (40, "$ 0,40"),
        (100, "$ 1"),
        (-150, "-$ 1,50"),
    ],
)
def test_formatear_cotizacion_corta(centavos, texto):
    assert formatear_cotizacion_corta(centavos) == texto


@pytest.mark.parametrize(
    ("centavos", "texto"),
    [(160000, "$ 1.600 por US$"), (143250, "$ 1.432,50 por US$")],
)
def test_formatear_cotizacion_usa_la_corta(centavos, texto):
    assert formatear_cotizacion(centavos) == texto


@pytest.mark.parametrize(
    ("usd", "cotizacion", "texto"),
    [
        (2000, 160000, "US$ 20,00 × $ 1.600"),  # CA-46.1
        (1999, 143250, "US$ 19,99 × $ 1.432,50"),  # CA-46.2
        (123456, 100, "US$ 1.234,56 × $ 1"),
    ],
)
def test_formatear_detalle_usd(usd, cotizacion, texto):
    assert formatear_detalle_usd(usd, cotizacion) == texto


# ---------------------------------------------------------------------------
# Alta (RF-43, RF-44, RN-54)
# ---------------------------------------------------------------------------


@pytest.fixture
def otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


@pytest.fixture
def base_1434617(con, mes_id, otros):
    """Gastos en pesos que suman 1.434.617 (base de los CA del módulo E)."""
    gastos.agregar_gasto(con, mes_id, "Gastos del mes", otros, 143461700, "fijo")


def _usd(
    con, mes_id, categoria, usd, cotizacion, nombre="Claude", tipo="unico", medio=None
):
    return gastos.agregar_gasto(
        con, mes_id, nombre, categoria, None, tipo, medio, "USD", usd, cotizacion
    )


def test_ca_43_1_alta_de_claude_en_dolares(con, mes_id, otros, base_1434617):
    gid = _usd(con, mes_id, otros, 2000, 160000)
    fila = gastos.obtener_gasto(con, gid)
    assert (fila["moneda"], fila["monto_usd_cent"], fila["cotizacion_cent"]) == (
        "USD",
        2000,
        160000,
    )
    assert fila["monto_cent"] == 3200000
    assert formatear_ars(gastos.total_gastos(con, mes_id)) == "$ 1.466.617"


def test_ca_43_2_con_cotizacion_del_gasto_distinta_a_la_del_mes(
    con, mes_id, otros, base_1434617
):
    gid = _usd(con, mes_id, otros, 2000, 210000)
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 4200000
    assert formatear_ars(gastos.total_gastos(con, mes_id)) == "$ 1.476.617"


@pytest.mark.parametrize("tipo", ["fijo", "unico"])
def test_fijos_y_unicos_pueden_ser_en_dolares(con, mes_id, otros, tipo):
    gid = _usd(con, mes_id, otros, 2000, 160000, tipo=tipo)
    assert gastos.obtener_gasto(con, gid)["tipo"] == tipo


def test_ca_43_3_cuota_en_dolares_se_rechaza(con, mes_id, otros):
    with pytest.raises(ErrorDeValidacion) as error:
        _usd(con, mes_id, otros, 2000, 160000, tipo="cuota")
    assert error.value.campo == "tipo"
    assert cantidad_filas(con, "gastos") == 0


def test_editar_una_cuota_a_dolares_se_rechaza(con, mes_id, otros):
    plan = insertar_plan(con, "Heladera", otros)
    with con:
        cursor = con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Heladera', ?, 1000000, 'cuota', ?)",
            (mes_id, otros, plan),
        )
    with pytest.raises(ErrorDeValidacion):
        gastos.editar_gasto(
            con,
            cursor.lastrowid,
            "Heladera",
            otros,
            None,
            "cuota",
            None,
            "USD",
            2000,
            160000,
        )
    assert gastos.obtener_gasto(con, cursor.lastrowid)["moneda"] == "ARS"


def test_ca_43_4_se_suma_por_sus_pesos_en_el_medio_de_pago(con, mes_id, otros):
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    _usd(con, mes_id, otros, 2000, 160000, medio=visa)
    gastos.agregar_gasto(con, mes_id, "Gym", otros, 5000000, "fijo", visa)
    total_visa = sum(
        f["monto_cent"]
        for f in gastos.listar_gastos(con, mes_id)
        if f["medio_pago_id"] == visa
    )
    assert formatear_ars(total_visa) == "$ 82.000"


def test_ca_44_2_cotizacion_con_decimales(con, mes_id, otros):
    gid = _usd(con, mes_id, otros, 1999, 143250)
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 2863568


def test_ca_44_3_mes_sin_cotizacion_exige_la_del_gasto(con, otros):
    mes_id = meses.crear_primer_mes(con, 2026, 10, 120000, None)
    with pytest.raises(ErrorDeValidacion) as error:
        _usd(con, mes_id, otros, 2000, None)
    assert error.value.campo == "cotizacion"
    gid = _usd(con, mes_id, otros, 2000, 155000)
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3100000


@pytest.mark.parametrize("usd", [0, -500, None, "abc", 20.5, True])
def test_ca_44_4_monto_en_dolares_invalido(con, mes_id, otros, usd):
    with pytest.raises(ErrorDeValidacion) as error:
        _usd(con, mes_id, otros, usd, 160000)
    assert error.value.campo == "monto_usd"
    assert str(error.value).startswith("El monto en dólares ")
    assert cantidad_filas(con, "gastos") == 0


@pytest.mark.parametrize("cotizacion", [0, -160000, None, "1600", 1600.5])
def test_ca_44_4_cotizacion_del_gasto_invalida(con, mes_id, otros, cotizacion):
    with pytest.raises(ErrorDeValidacion) as error:
        _usd(con, mes_id, otros, 2000, cotizacion)
    assert error.value.campo == "cotizacion"
    assert str(error.value).startswith("La cotización ")
    assert cantidad_filas(con, "gastos") == 0


def test_ca_44_4_mensajes_exactos(con, mes_id, otros):
    with pytest.raises(
        ErrorDeValidacion, match="^El monto en dólares tiene que ser mayor a 0.$"
    ):
        _usd(con, mes_id, otros, 0, 160000)
    with pytest.raises(
        ErrorDeValidacion, match="^La cotización tiene que ser mayor a 0.$"
    ):
        _usd(con, mes_id, otros, 2000, 0)


def test_ca_44_5_resultado_que_redondea_a_cero(con, mes_id, otros):
    with pytest.raises(ErrorDeValidacion) as error:
        _usd(con, mes_id, otros, 1, 40)
    assert error.value.campo == "resultado"
    assert (
        str(error.value)
        == "Con estos valores el gasto da $ 0. Revisá el monto y la cotización."
    )
    assert cantidad_filas(con, "gastos") == 0


def test_resultado_en_pesos_demasiado_grande(con, mes_id, otros):
    # Dólares y cotización válidos, pero el producto supera el tope de pesos.
    with pytest.raises(ErrorDeValidacion) as error:
        _usd(con, mes_id, otros, MONTO_MAXIMO_CENT, 160000)
    assert error.value.campo == "resultado"
    assert str(error.value) == "El monto en pesos es demasiado grande."


def test_en_dolares_monto_cent_se_ignora_y_se_calcula(con, mes_id, otros):
    gid = gastos.agregar_gasto(
        con, mes_id, "Claude", otros, 1, "unico", None, "USD", 2000, 160000
    )
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3200000


def test_en_pesos_los_dolares_se_descartan(con, mes_id, otros):
    gid = gastos.agregar_gasto(
        con, mes_id, "Nafta", otros, 3000000, "fijo", None, "ARS", 2000, 160000
    )
    fila = gastos.obtener_gasto(con, gid)
    assert (fila["moneda"], fila["monto_usd_cent"], fila["cotizacion_cent"]) == (
        "ARS",
        None,
        None,
    )


@pytest.mark.parametrize("moneda", ["EUR", "usd", "", None])
def test_moneda_invalida(con, mes_id, otros, moneda):
    with pytest.raises(ErrorDeValidacion) as error:
        gastos.agregar_gasto(
            con, mes_id, "X", otros, 100, "fijo", None, moneda, 2000, 160000
        )
    assert error.value.campo == "moneda"


def test_pesos_por_defecto(con, mes_id, otros):
    gid = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "fijo")
    assert gastos.obtener_gasto(con, gid)["moneda"] == "ARS"


def test_listar_gastos_trae_moneda_dolares_y_cotizacion(con, mes_id, otros):
    _usd(con, mes_id, otros, 2000, 160000)
    gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "fijo")
    filas = {f["nombre"]: f for f in gastos.listar_gastos(con, mes_id)}
    assert (filas["Claude"]["moneda"], filas["Claude"]["monto_usd_cent"]) == (
        "USD",
        2000,
    )
    assert filas["Claude"]["cotizacion_cent"] == 160000
    assert (filas["Nafta"]["moneda"], filas["Nafta"]["cotizacion_cent"]) == (
        "ARS",
        None,
    )


# ---------------------------------------------------------------------------
# Edición (RF-45, RN-55, RN-56, RN-23)
# ---------------------------------------------------------------------------


@pytest.fixture
def claude(con, mes_id, otros, base_1434617):
    return _usd(con, mes_id, otros, 2000, 160000)


def _editar_usd(con, gid, otros, usd, cotizacion, tipo="unico"):
    gastos.editar_gasto(
        con, gid, "Claude", otros, None, tipo, None, "USD", usd, cotizacion
    )


def test_ca_45_1_cambiar_la_cotizacion_del_mes_no_cambia_el_gasto(con, mes_id, claude):
    with con:
        con.execute("UPDATE meses SET cotizacion_cent = 170000 WHERE id = ?", (mes_id,))
    assert gastos.obtener_gasto(con, claude)["monto_cent"] == 3200000
    assert formatear_ars(gastos.total_gastos(con, mes_id)) == "$ 1.466.617"


def test_rn_55_editar_otro_campo_no_cambia_los_pesos(con, mes_id, otros, claude):
    # Cambia la cotización del mes y después se edita solo el nombre: los pesos siguen.
    with con:
        con.execute("UPDATE meses SET cotizacion_cent = 170000 WHERE id = ?", (mes_id,))
    gastos.editar_gasto(
        con, claude, "Claude Pro", otros, None, "unico", None, "USD", 2000, 160000
    )
    assert gastos.obtener_gasto(con, claude)["monto_cent"] == 3200000


def test_ca_45_2_editar_la_cotizacion_del_gasto(con, mes_id, otros, claude):
    _editar_usd(con, claude, otros, 2000, 170000)
    assert gastos.obtener_gasto(con, claude)["monto_cent"] == 3400000
    assert formatear_ars(gastos.total_gastos(con, mes_id)) == "$ 1.468.617"


def test_ca_45_3_editar_el_monto_en_dolares(con, otros, claude):
    _editar_usd(con, claude, otros, 2500, 160000)
    fila = gastos.obtener_gasto(con, claude)
    assert (fila["monto_usd_cent"], fila["monto_cent"]) == (2500, 4000000)


def test_ca_45_4_rn_23_en_dolares(con, otros, claude):
    insertar_pago(con, claude, 3000000)
    with pytest.raises(ErrorDeValidacion) as error:
        _editar_usd(con, claude, otros, 2000, 140000)  # 28.000 < 30.000
    assert str(error.value) == (
        "Con estos valores el gasto queda en $ 28.000, menos de lo que ya pagaste "
        "($ 30.000). Subí el monto o la cotización."
    )
    assert error.value.campo == "resultado"
    assert gastos.obtener_gasto(con, claude)["cotizacion_cent"] == 160000

    _editar_usd(con, claude, otros, 2000, 155000)  # 31.000: se acepta
    fila = gastos.obtener_gasto(con, claude)
    assert (
        fila["monto_cent"] - gastos.total_pagado(con, claude) == 100000
    )  # pendiente 1.000

    with pytest.raises(ErrorDeValidacion, match="menos de lo que ya pagaste"):
        _editar_usd(con, claude, otros, 1800, 160000)  # 28.800 < 30.000


def test_rn_23_en_dolares_igual_a_lo_pagado_se_acepta(con, otros, claude):
    insertar_pago(con, claude, 3100000)
    _editar_usd(con, claude, otros, 2000, 155000)  # 31.000 = pagado
    assert gastos.obtener_gasto(con, claude)["monto_cent"] == 3100000


def test_ca_45_5_cambiar_de_moneda_ida_y_vuelta(con, mes_id, otros):
    nafta = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "fijo")
    gastos.editar_gasto(
        con, nafta, "Nafta", otros, None, "fijo", None, "USD", 2500, 160000
    )
    fila = gastos.obtener_gasto(con, nafta)
    assert (fila["moneda"], fila["monto_usd_cent"], fila["monto_cent"]) == (
        "USD",
        2500,
        4000000,
    )
    assert formatear_detalle_usd(fila["monto_usd_cent"], fila["cotizacion_cent"]) == (
        "US$ 25,00 × $ 1.600"
    )
    gastos.editar_gasto(con, nafta, "Nafta", otros, 3500000, "fijo", None, "ARS")
    fila = gastos.obtener_gasto(con, nafta)
    assert (fila["moneda"], fila["monto_usd_cent"], fila["cotizacion_cent"]) == (
        "ARS",
        None,
        None,
    )
    assert fila["monto_cent"] == 3500000


def test_ca_45_6_pasar_a_pesos_por_debajo_de_lo_pagado(con, otros, claude):
    insertar_pago(con, claude, 3200000)
    with pytest.raises(ErrorDeValidacion) as error:
        gastos.editar_gasto(con, claude, "Claude", otros, 3000000, "unico", None, "ARS")
    assert (
        str(error.value)
        == "No podés bajar el monto a menos de lo que ya pagaste ($ 32.000)."
    )
    assert error.value.campo == "monto"
    assert gastos.obtener_gasto(con, claude)["moneda"] == "USD"


def test_pasar_de_pesos_a_dolares_por_debajo_de_lo_pagado(con, mes_id, otros):
    nafta = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "fijo")
    insertar_pago(con, nafta, 3000000)
    with pytest.raises(ErrorDeValidacion) as error:
        gastos.editar_gasto(
            con, nafta, "Nafta", otros, None, "fijo", None, "USD", 1000, 160000
        )
    assert error.value.campo == "resultado"
    assert gastos.obtener_gasto(con, nafta)["moneda"] == "ARS"


def test_editar_en_dolares_con_datos_invalidos_no_cambia_nada(con, otros, claude):
    for usd, cot in [(0, 160000), (2000, 0), (None, 160000), (2000, None), (1, 40)]:
        with pytest.raises(ErrorDeValidacion):
            _editar_usd(con, claude, otros, usd, cot)
    fila = gastos.obtener_gasto(con, claude)
    assert (fila["monto_usd_cent"], fila["cotizacion_cent"], fila["monto_cent"]) == (
        2000,
        160000,
        3200000,
    )


def test_editar_un_mes_no_cambia_otro(con, mes_id, otros):
    # RN-11 también en dólares: el mismo gasto en otro mes no cambia.
    with con:
        otro_mes = con.execute(
            "INSERT INTO meses (anio, mes, sueldo_usd_cent, cotizacion_cent) "
            "VALUES (2026, 11, 120000, 170000)"
        ).lastrowid
    oct_ = _usd(con, mes_id, otros, 2000, 160000, tipo="fijo")
    nov = _usd(con, otro_mes, otros, 2000, 170000, tipo="fijo")
    _editar_usd(con, oct_, otros, 2500, 160000, tipo="fijo")
    assert gastos.obtener_gasto(con, nov)["monto_cent"] == 3400000
