"""Pruebas de la lógica del historial de meses (paso 4a): mes siguiente/anterior,
listar, mes inicial, sugerencias, crear el mes siguiente copiando los fijos y borrar
el último mes (RF-01 a RF-05, RF-47, RN-07 a RN-11, RN-57; CA-01.1, CA-02.1/02.2,
CA-03.1 sin cuotas, CA-03.2, 03.3, 03.5, 03.6 sin cuotas, CA-05.1, 05.3, CA-27.6,
CA-36.3, CA-47.1 a 47.5). Base en memoria, datos inventados y fechas fijas."""

from datetime import date

import pytest

from app.logica import (
    cambios,
    catalogos,
    configuracion,
    gastos,
    ingresos,
    meses,
    pagos,
)
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT, formatear_ars, formatear_usd
from app.logica.resumen import calcular_resumen
from tests.ayudantes import cantidad_filas, id_por_nombre, insertar_plan

HOY = date(2026, 10, 4)


@pytest.fixture
def otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _agregar(
    con, mes_id, nombre, monto=100000, tipo="fijo", categoria=None, medio=None
):
    categoria = categoria or id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    return gastos.agregar_gasto(con, mes_id, nombre, categoria, monto, tipo, medio)


def _usd(con, mes_id, nombre, usd, cot, tipo="fijo", medio=None):
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    return gastos.agregar_gasto(
        con, mes_id, nombre, otros, None, tipo, medio, "USD", usd, cot
    )


def _por_nombre(con, mes_id):
    return {g["nombre"]: g for g in gastos.listar_gastos(con, mes_id)}


# ---------------------------------------------------------------------------
# siguiente / anterior
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("actual", "sig"),
    [
        ((2026, 10), (2026, 11)),
        ((2026, 11), (2026, 12)),
        ((2026, 12), (2027, 1)),
        ((2027, 1), (2027, 2)),
    ],
)
def test_siguiente_y_anterior(actual, sig):
    assert meses.siguiente(*actual) == sig
    assert meses.anterior(*sig) == actual


def test_anterior_de_enero_es_diciembre_del_anio_anterior():
    assert meses.anterior(2027, 1) == (2026, 12)


# ---------------------------------------------------------------------------
# Listar, buscar y mes inicial
# ---------------------------------------------------------------------------


@pytest.fixture
def tres_meses(con, mes_id):
    """2026-10 (fixture), 2026-11 y 2026-12, creados con crear_mes_siguiente."""
    nov = meses.crear_mes_siguiente(con, 120000, 165000)
    dic = meses.crear_mes_siguiente(con, 130000, 170000)
    return mes_id, nov, dic


def test_listar_meses_del_mas_nuevo_al_mas_viejo(con, tres_meses):
    assert [(m["anio"], m["mes"]) for m in meses.listar_meses(con)] == [
        (2026, 12),
        (2026, 11),
        (2026, 10),
    ]


def test_listar_meses_sin_meses(con):
    assert meses.listar_meses(con) == []


def test_obtener_mes_por_fecha(con, tres_meses):
    oct_, nov, _ = tres_meses
    assert meses.obtener_mes_por_fecha(con, 2026, 11)["id"] == nov
    assert meses.obtener_mes_por_fecha(con, 2026, 10)["id"] == oct_
    assert meses.obtener_mes_por_fecha(con, 2027, 1) is None


@pytest.mark.parametrize(
    ("hoy", "esperado"),
    [
        (date(2026, 11, 15), (2026, 11)),  # el del calendario existe
        (date(2026, 10, 1), (2026, 10)),
        (date(2027, 3, 1), (2026, 12)),  # no existe: el último
        (date(2025, 1, 1), (2026, 12)),  # antes del primero: el último
    ],
)
def test_mes_inicial(con, tres_meses, hoy, esperado):
    mes = meses.mes_inicial(con, hoy)
    assert (mes["anio"], mes["mes"]) == esperado


def test_mes_inicial_sin_meses(con):
    assert meses.mes_inicial(con, HOY) is None


def test_mes_inicial_sin_fecha_usa_hoy(con, mes_id):
    # Sin "hoy" usa el reloj: si octubre 2026 no es hoy, igual devuelve el último.
    assert meses.mes_inicial(con)["id"] == mes_id


# ---------------------------------------------------------------------------
# Sugerencias (CA-03.2)
# ---------------------------------------------------------------------------


def test_ca_03_2_sugerencias(con, mes_id, otros):
    _agregar(con, mes_id, "Alquiler", 26000000)
    _agregar(con, mes_id, "Regalo", 1500000, "unico")
    _usd(con, mes_id, "Claude", 2000, 160000)
    _usd(con, mes_id, "Curso", 5000, 160000, tipo="unico")
    assert meses.sugerencias_mes_siguiente(con) == {
        "anio": 2026,
        "mes": 11,
        "sueldo_usd_cent": 120000,
        "cotizacion_cent": 160000,
        "fijos": 2,
        "fijos_en_dolares": 1,
    }


def test_sugerencias_cruzan_el_anio_y_usan_el_ultimo(con, tres_meses):
    sug = meses.sugerencias_mes_siguiente(con)
    assert (sug["anio"], sug["mes"]) == (2027, 1)
    assert (sug["sueldo_usd_cent"], sug["cotizacion_cent"]) == (130000, 170000)
    assert (sug["fijos"], sug["fijos_en_dolares"]) == (0, 0)


def test_sugerencias_sin_cotizacion(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, None)
    assert meses.sugerencias_mes_siguiente(con)["cotizacion_cent"] is None


def test_sugerencias_sin_meses(con):
    with pytest.raises(
        ErrorDeValidacion, match="^Todavía no hay meses: creá el primero.$"
    ):
        meses.sugerencias_mes_siguiente(con)


# ---------------------------------------------------------------------------
# Crear el mes siguiente (RF-03, RN-08, RN-09)
# ---------------------------------------------------------------------------


def test_ca_03_1_copia_los_fijos_sin_pagos_y_no_los_unicos(con, mes_id, otros):
    alquiler = _agregar(con, mes_id, "Alquiler", 26000000)
    _agregar(con, mes_id, "Regalo", 1500000, "unico")
    pagos.marcar_pagado(con, alquiler, HOY)
    nov = meses.crear_mes(con, 2026, 11, 120000, 160000)
    copiados = _por_nombre(con, nov)
    assert list(copiados) == ["Alquiler"]  # "Regalo" (pago único) no se copia
    assert copiados["Alquiler"]["monto_cent"] == 26000000
    assert copiados["Alquiler"]["pagado_cent"] == 0
    assert pagos.pendiente(con, copiados["Alquiler"]["id"]) == 26000000
    # El de octubre sigue pagado.
    assert pagos.pendiente(con, alquiler) == 0


def test_copia_todos_los_campos_del_fijo(con, mes_id):
    servicios = id_por_nombre(con, catalogos.CATEGORIAS, "Servicios")
    efectivo = id_por_nombre(con, catalogos.MEDIOS_PAGO, "Efectivo")
    _agregar(con, mes_id, "Internet", 3870012, categoria=servicios, medio=efectivo)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    [copia] = gastos.listar_gastos(con, nov)
    assert (copia["nombre"], copia["categoria_id"], copia["medio_pago_id"]) == (
        "Internet",
        servicios,
        efectivo,
    )
    assert (copia["monto_cent"], copia["tipo"], copia["moneda"]) == (
        3870012,
        "fijo",
        "ARS",
    )
    assert (copia["monto_usd_cent"], copia["cotizacion_cent"]) == (None, None)


def test_ca_03_2_sueldo_y_cotizacion_del_mes_nuevo_son_los_que_se_pasan(con, mes_id):
    nov = meses.crear_mes(con, 2026, 11, 130000, 170000)
    mes = meses.obtener_mes(con, nov)
    assert (
        mes["anio"],
        mes["mes"],
        mes["sueldo_usd_cent"],
        mes["cotizacion_cent"],
    ) == (
        2026,
        11,
        130000,
        170000,
    )


def test_crear_mes_con_sueldo_cero_y_sin_cotizacion(con, mes_id):
    nov = meses.crear_mes_siguiente(con, 0)
    mes = meses.obtener_mes(con, nov)
    assert (mes["sueldo_usd_cent"], mes["cotizacion_cent"]) == (0, None)


def test_ca_03_3_no_copia_extras_ni_cambios(con, mes_id):
    ingresos.agregar_ingreso(con, mes_id, "Bono", "ARS", 10000000)
    ingresos.agregar_ingreso(con, mes_id, "Freelance", "USD", 5000)
    cambios.agregar_cambio(con, mes_id, 50000, 150000, fecha=HOY)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    assert ingresos.listar_ingresos(con, nov) == []
    assert cambios.listar_cambios(con, nov) == []
    # Los de octubre siguen.
    assert len(ingresos.listar_ingresos(con, mes_id)) == 2
    assert len(cambios.listar_cambios(con, mes_id)) == 1


def test_ca_27_6_los_pesos_sobrantes_no_pasan_al_mes_siguiente(con, mes_id):
    # CA-27.3 en octubre: gastos 100.000 y cambio de 100 USD (160.000) → sobran 60.000.
    _agregar(con, mes_id, "Gastos", 10000000, "unico")
    cambios.agregar_cambio(con, mes_id, 10000, 160000, fecha=HOY)
    assert calcular_resumen(con, mes_id).pesos_sobrantes == 6000000
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    r = calcular_resumen(con, nov)
    assert (r.pesos_sobrantes, r.sobrantes_usd, r.total_gastos) == (0, 0, 0)
    assert r.ahorro_usd == 120000


@pytest.mark.parametrize(
    ("anio", "mes"),
    [(2026, 12), (2026, 9), (2026, 10), (2027, 11), (2025, 11)],
)
def test_ca_03_5_solo_se_puede_crear_el_siguiente(con, mes_id, anio, mes):
    with pytest.raises(ErrorDeValidacion) as error:
        meses.crear_mes(con, anio, mes, 120000, 160000)
    assert (
        str(error.value) == "Solo se puede crear el mes siguiente al último (11/2026)."
    )
    assert error.value.campo == "mes"
    assert len(meses.listar_meses(con)) == 1


def test_crear_mes_que_cruza_el_anio(con, tres_meses):
    ene = meses.crear_mes(con, 2027, 1, 130000, 170000)
    mes = meses.obtener_mes(con, ene)
    assert (mes["anio"], mes["mes"]) == (2027, 1)
    with pytest.raises(ErrorDeValidacion) as error:
        meses.crear_mes(con, 2026, 13, 130000)
    assert error.value.campo == "mes"  # mes imposible
    with pytest.raises(ErrorDeValidacion, match=r"\(02/2027\)"):
        meses.crear_mes(con, 2027, 3, 130000)


@pytest.mark.parametrize(
    ("anio", "mes", "campo"), [(26, 11, "anio"), (2026, 0, "mes"), (2026, 13, "mes")]
)
def test_crear_mes_con_fecha_imposible(con, mes_id, anio, mes, campo):
    with pytest.raises(ErrorDeValidacion) as error:
        meses.crear_mes(con, anio, mes, 120000)
    assert error.value.campo == campo


@pytest.mark.parametrize(
    ("sueldo", "cot", "campo", "mensaje"),
    [
        (-1, 160000, "sueldo", "El sueldo no puede ser negativo."),
        (
            1.5,
            160000,
            "sueldo",
            "El sueldo tiene que ser un número entero de centavos.",
        ),
        (
            None,
            160000,
            "sueldo",
            "El sueldo tiene que ser un número entero de centavos.",
        ),
        (MONTO_MAXIMO_CENT + 1, 160000, "sueldo", "El sueldo es demasiado grande."),
        (120000, 0, "cotizacion", "La cotización tiene que ser mayor a 0."),
        (120000, -1, "cotizacion", "La cotización tiene que ser mayor a 0."),
        (
            120000,
            1600.5,
            "cotizacion",
            "La cotización tiene que ser un número entero de centavos.",
        ),
    ],
)
def test_crear_mes_con_valores_invalidos(con, mes_id, sueldo, cot, campo, mensaje):
    _agregar(con, mes_id, "Alquiler")
    with pytest.raises(ErrorDeValidacion) as error:
        meses.crear_mes(con, 2026, 11, sueldo, cot)
    assert (str(error.value), error.value.campo) == (mensaje, campo)
    assert len(meses.listar_meses(con)) == 1
    assert cantidad_filas(con, "gastos") == 1  # no se copió nada


def test_crear_mes_sin_meses(con):
    with pytest.raises(
        ErrorDeValidacion, match="^Todavía no hay meses: creá el primero.$"
    ):
        meses.crear_mes(con, 2026, 10, 120000)
    with pytest.raises(
        ErrorDeValidacion, match="^Todavía no hay meses: creá el primero.$"
    ):
        meses.crear_mes_siguiente(con, 120000)


def test_el_primer_mes_sigue_sin_poder_crearse_dos_veces(con, mes_id):
    with pytest.raises(ErrorDeValidacion):
        meses.crear_primer_mes(con, 2026, 11, 120000)


def test_solo_copia_del_ultimo_mes(con, mes_id):
    # Septiembre no existe; se crean noviembre y diciembre. Diciembre copia de
    # noviembre: lo que se borró en noviembre ya no vuelve (RN-09).
    _agregar(con, mes_id, "Alquiler", 26000000)
    _agregar(con, mes_id, "Gym", 2500000)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    gym_nov = _por_nombre(con, nov)["Gym"]["id"]
    gastos.borrar_gasto(con, gym_nov)
    _agregar(con, nov, "Netflix", 600000)
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    assert list(_por_nombre(con, dic)) == ["Alquiler", "Netflix"]
    # Octubre no se toca.
    assert list(_por_nombre(con, mes_id)) == ["Alquiler", "Gym"]


def test_las_cuotas_no_se_copian_como_fijos(con, mes_id, otros):
    # Las cuotas las genera el plan (paso 4b): crear_mes no las copia como gasto fijo.
    plan = insertar_plan(con, "Heladera", otros, monto=1000000, cuotas=6)
    with con:
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Heladera', ?, 1000000, 'cuota', ?)",
            (mes_id, otros, plan),
        )
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    assert not any(
        g["nombre"] == "Heladera" and g["tipo"] == "fijo"
        for g in gastos.listar_gastos(con, nov)
    )


def test_ca_03_6_fijo_con_categoria_y_medio_archivados_se_copia(con, mes_id):
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    _agregar(con, mes_id, "Gym", 2500000, categoria=gym, medio=visa)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    [copia] = gastos.listar_gastos(con, nov)
    assert (copia["categoria"], copia["categoria_archivada"]) == ("Gym", 1)
    assert (copia["medio_pago"], copia["medio_pago_archivado"]) == ("Visa Santander", 1)


def test_crear_mes_es_atomico(con, mes_id, monkeypatch):
    # Si falla a mitad de la copia, no queda un mes a medias.
    _agregar(con, mes_id, "Alquiler")
    _usd(con, mes_id, "Claude", 2000, 160000)
    _usd(con, mes_id, "Netflix", 1500, 160000)
    original = meses.convertir_usd_a_ars
    llamadas = []

    def falla_en_la_segunda(usd, cot):
        llamadas.append(1)
        if len(llamadas) == 2:
            raise RuntimeError("falla simulada a mitad de la copia")
        return original(usd, cot)

    monkeypatch.setattr(meses, "convertir_usd_a_ars", falla_en_la_segunda)
    with pytest.raises(RuntimeError):
        meses.crear_mes_siguiente(con, 120000, 170000)
    assert len(meses.listar_meses(con)) == 1
    assert cantidad_filas(con, "gastos") == 3
    monkeypatch.undo()
    nov = meses.crear_mes_siguiente(con, 120000, 170000)  # después funciona
    assert len(gastos.listar_gastos(con, nov)) == 3


# ---------------------------------------------------------------------------
# Fijos en dólares al mes nuevo (RF-47, RN-57, CA-47.x)
# ---------------------------------------------------------------------------


def test_ca_47_1_con_la_cotizacion_del_mes_nuevo(con, mes_id):
    claude = _usd(con, mes_id, "Claude", 2000, 160000)
    pagos.marcar_pagado(con, claude, HOY)
    nov = meses.crear_mes_siguiente(con, 120000, 170000)
    copia = _por_nombre(con, nov)["Claude"]
    assert (copia["monto_usd_cent"], copia["cotizacion_cent"], copia["monto_cent"]) == (
        2000,
        170000,
        3400000,
    )
    assert copia["pagado_cent"] == 0  # sin pagos
    assert gastos.obtener_gasto(con, claude)["monto_cent"] == 3200000  # octubre sigue


def test_ca_47_2_sin_cotizacion_conserva_la_del_gasto(con, mes_id):
    _usd(con, mes_id, "Claude", 2000, 160000)
    nov = meses.crear_mes_siguiente(con, 120000, None)
    copia = _por_nombre(con, nov)["Claude"]
    assert (copia["cotizacion_cent"], copia["monto_cent"]) == (160000, 3200000)


def test_ca_47_3_dolar_tarjeta_toma_la_del_mes_nuevo(con, mes_id):
    _usd(con, mes_id, "Claude", 2000, 210000)
    nov = meses.crear_mes_siguiente(con, 120000, 170000)
    copia = _por_nombre(con, nov)["Claude"]
    assert (copia["cotizacion_cent"], copia["monto_cent"]) == (170000, 3400000)


def test_ca_47_4_cambiar_la_cotizacion_del_mes_nuevo_no_cambia_el_gasto(con, mes_id):
    _usd(con, mes_id, "Claude", 2000, 160000)
    nov = meses.crear_mes_siguiente(con, 120000, 170000)
    meses.editar_cotizacion(con, nov, 180000)
    assert _por_nombre(con, nov)["Claude"]["monto_cent"] == 3400000


def test_ca_47_5_pago_unico_en_dolares_no_se_copia(con, mes_id):
    _usd(con, mes_id, "Curso", 5000, 160000, tipo="unico")
    nov = meses.crear_mes_siguiente(con, 120000, 170000)
    assert gastos.listar_gastos(con, nov) == []


def test_fijo_en_dolares_con_cotizacion_con_centavos(con, mes_id):
    _usd(con, mes_id, "Claude", 1999, 160000)
    nov = meses.crear_mes_siguiente(con, 120000, 143250)
    assert _por_nombre(con, nov)["Claude"]["monto_cent"] == 2863568  # RN-53


def test_mes_nuevo_sin_cotizacion_y_el_ultimo_tampoco(con):
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, None)
    _usd(con, mes, "Claude", 2000, 155000)
    nov = meses.crear_mes_siguiente(con, 120000)
    assert _por_nombre(con, nov)["Claude"]["cotizacion_cent"] == 155000


def test_bug15_fijo_en_dolares_que_al_recalcular_da_cero(con, mes_id):
    # RN-54: el monto en pesos tiene que ser > 0. US$ 0,01 a $ 1,00 = $ 0,01; con la
    # cotización nueva $ 0,40 da $ 0,004 → 0: se avisa y no se crea el mes.
    _usd(con, mes_id, "Prueba", 1, 100)
    with pytest.raises(ErrorDeValidacion) as error:
        meses.crear_mes_siguiente(con, 120000, 40)
    assert str(error.value) == (
        'Con esta cotización, el gasto "Prueba" en dólares da $ 0. Revisá la cotización.'
    )
    assert error.value.campo == "cotizacion"
    assert len(meses.listar_meses(con)) == 1
    assert cantidad_filas(con, "gastos") == 1


@pytest.mark.parametrize(
    "cotizacion_nueva",
    [MONTO_MAXIMO_CENT, 200],  # enorme (no entra en SQLite) y apenas sobre el tope
    ids=["no_entra_en_la_base", "apenas_sobre_el_tope"],
)
def test_bug15_fijo_en_dolares_que_al_recalcular_supera_el_tope(
    con, mes_id, cotizacion_nueva
):
    # US$ 999.999.999.999 a $ 1: con $ 2 da $ 1.999.999.999.998, más que el tope.
    _usd(con, mes_id, "Enorme", MONTO_MAXIMO_CENT, 100)
    with pytest.raises(ErrorDeValidacion) as error:
        meses.crear_mes_siguiente(con, 120000, cotizacion_nueva)
    assert str(error.value) == (
        'Con esta cotización, el gasto "Enorme" en dólares da un monto demasiado grande. '
        "Revisá la cotización."
    )
    assert error.value.campo == "cotizacion"
    assert len(meses.listar_meses(con)) == 1


def test_bug15_valida_todos_antes_de_crear_nada(con, mes_id):
    # El primer fijo se copia bien y el segundo da 0: no queda ni el mes ni el primero.
    _agregar(con, mes_id, "Alquiler", 26000000)
    _usd(con, mes_id, "Bien", 2000, 160000)
    _usd(con, mes_id, "Mal", 1, 100)
    with pytest.raises(ErrorDeValidacion, match='"Mal"'):
        meses.crear_mes_siguiente(con, 120000, 40)
    assert len(meses.listar_meses(con)) == 1
    assert cantidad_filas(con, "gastos") == 3


def test_bug15_sin_cotizacion_nueva_usa_la_del_gasto_y_no_falla(con, mes_id):
    # Sin cotización del mes nuevo, el fijo conserva la suya (US$ 0,01 a $ 1 = $ 0,01).
    _usd(con, mes_id, "Prueba", 1, 100)
    nov = meses.crear_mes_siguiente(con, 120000, None)
    assert _por_nombre(con, nov)["Prueba"]["monto_cent"] == 1


def test_bug15_justo_en_el_tope_se_acepta(con, mes_id):
    # US$ 999.999.999.999 a $ 1 = exactamente el tope: se copia.
    _usd(con, mes_id, "Tope", MONTO_MAXIMO_CENT, 100)
    nov = meses.crear_mes_siguiente(con, 120000, 100)
    assert _por_nombre(con, nov)["Tope"]["monto_cent"] == MONTO_MAXIMO_CENT


# ---------------------------------------------------------------------------
# Independencia de meses (CA-01.1, CA-02.x, RN-11) y meta (CA-36.3)
# ---------------------------------------------------------------------------


def test_ca_01_1_crear_noviembre_no_cambia_octubre(con, mes_id):
    nafta = _agregar(con, mes_id, "Nafta", 3000000)
    meses.crear_mes_siguiente(con, 120000, 160000)
    assert gastos.obtener_gasto(con, nafta)["monto_cent"] == 3000000


def test_ca_02_1_cada_mes_tiene_sus_datos(con, mes_id):
    _agregar(con, mes_id, "Alquiler", 26000000)
    ingresos.agregar_ingreso(con, mes_id, "Bono", "ARS", 10000000)
    nov = meses.crear_mes_siguiente(con, 130000, 170000)
    _agregar(con, nov, "Regalo", 1500000, "unico")
    r_oct, r_nov = calcular_resumen(con, mes_id), calcular_resumen(con, nov)
    assert (r_oct.cotizacion, r_nov.cotizacion) == (160000, 170000)
    assert (formatear_ars(r_oct.total_gastos), formatear_ars(r_nov.total_gastos)) == (
        "$ 260.000",
        "$ 275.000",
    )
    assert (r_oct.extras_ars, r_nov.extras_ars) == (10000000, 0)
    assert formatear_usd(r_oct.ahorro_usd) == "US$ 1.100,00"  # 1.200 − 160.000/1.600
    assert formatear_usd(r_nov.ahorro_usd) == "US$ 1.138,24"  # 1.300 − 275.000/1.700


def test_ca_02_2_editar_un_mes_pasado_no_cambia_el_otro(con, mes_id):
    alquiler_oct = _agregar(con, mes_id, "Alquiler", 26000000)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    alquiler_nov = _por_nombre(con, nov)["Alquiler"]["id"]
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gastos.editar_gasto(con, alquiler_oct, "Alquiler", otros, 25000000, "fijo")
    assert gastos.obtener_gasto(con, alquiler_nov)["monto_cent"] == 26000000
    gastos.editar_gasto(con, alquiler_nov, "Alquiler", otros, 28000000, "fijo")
    assert gastos.obtener_gasto(con, alquiler_oct)["monto_cent"] == 25000000


def test_ca_36_3_la_meta_es_la_misma_en_todos_los_meses(con, mes_id):
    _agregar(con, mes_id, "Gastos", 143461700, "unico")
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    _agregar(con, nov, "Gastos", 143461700, "unico")
    configuracion.guardar_meta(con, 30000)
    assert (
        calcular_resumen(con, mes_id).avance_meta
        == calcular_resumen(con, nov).avance_meta
    )
    configuracion.guardar_meta(con, 60000)
    assert calcular_resumen(con, mes_id).avance_meta == pytest.approx(0.5056)
    assert calcular_resumen(con, nov).avance_meta == pytest.approx(0.5056)


# ---------------------------------------------------------------------------
# Borrar el último mes (RF-05, RN-10, CA-05.x)
# ---------------------------------------------------------------------------


def test_ca_05_1_solo_se_puede_borrar_el_ultimo(con, mes_id):
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    with pytest.raises(ErrorDeValidacion) as error:
        meses.borrar_ultimo_mes(con, mes_id)
    assert (str(error.value), error.value.campo) == (
        "Solo se puede borrar el último mes.",
        None,
    )
    assert len(meses.listar_meses(con)) == 2
    meses.borrar_ultimo_mes(con, nov)
    assert [m["id"] for m in meses.listar_meses(con)] == [mes_id]


def test_ca_05_1_borrar_se_lleva_todo_lo_del_mes(con, mes_id, otros):
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    a = _agregar(con, nov, "Alquiler", 26000000)
    pagos.registrar_pago(con, a, 1000000, HOY)
    ingresos.agregar_ingreso(con, nov, "Bono", "ARS", 100)
    cambios.agregar_cambio(con, nov, 100, 150000, fecha=HOY)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    with con:
        con.execute(
            "INSERT INTO partes_gasto (gasto_id, persona_id, monto_cent) VALUES (?, ?, 100)",
            (a, sofia),
        )
    # Datos de octubre, para comprobar que no se tocan.
    b = _agregar(con, mes_id, "Nafta", 3000000)
    pagos.registrar_pago(con, b, 100, HOY)
    ingresos.agregar_ingreso(con, mes_id, "Bono oct", "ARS", 100)

    meses.borrar_ultimo_mes(con, nov)
    assert meses.obtener_mes(con, nov) is None
    for tabla, quedan in [
        ("gastos", 1),
        ("pagos", 1),
        ("partes_gasto", 0),
        ("ingresos_extra", 1),
        ("cambios", 0),
    ]:
        assert cantidad_filas(con, tabla) == quedan, tabla


def test_borrar_no_toca_planes_omitidas_me_deben_categorias_ni_configuracion(
    con, mes_id, otros
):
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    plan = insertar_plan(con, "Heladera", otros)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    with con:
        con.execute(
            "INSERT INTO cuotas_omitidas (plan_cuotas_id, anio, mes) VALUES (?, 2026, 11)",
            (plan,),
        )
        con.execute(
            "INSERT INTO items_me_deben (persona_id, descripcion, monto_cent, fecha) "
            "VALUES (?, 'Préstamo', 500000, '2026-11-02')",
            (sofia,),
        )
    configuracion.guardar_meta(con, 30000)
    antes = {
        t: cantidad_filas(con, t)
        for t in (
            "planes_cuotas",
            "cuotas_omitidas",
            "items_me_deben",
            "categorias",
            "medios_pago",
            "personas",
            "configuracion",
        )
    }
    meses.borrar_ultimo_mes(con, nov)
    assert {t: cantidad_filas(con, t) for t in antes} == antes
    assert configuracion.obtener_meta(con) == 30000


def test_borrar_mes_inexistente(con, mes_id):
    with pytest.raises(ErrorDeValidacion, match="^El mes no existe.$"):
        meses.borrar_ultimo_mes(con, 999)


def test_ca_05_3_volver_a_crear_despues_de_borrar(con, mes_id):
    # CA-05.3: borrar 2026-11 y volver a crearlo copia los fijos de 2026-10.
    _agregar(con, mes_id, "Alquiler", 26000000)
    _usd(con, mes_id, "Claude", 2000, 160000)
    nov = meses.crear_mes_siguiente(con, 120000, 170000)
    _agregar(con, nov, "Solo de noviembre", 100)
    meses.borrar_ultimo_mes(con, nov)
    nov2 = meses.crear_mes(con, 2026, 11, 125000, 180000)
    copiados = _por_nombre(con, nov2)
    assert list(copiados) == ["Alquiler", "Claude"]
    assert copiados["Claude"]["monto_cent"] == 3600000  # con la cotización nueva
    assert meses.obtener_mes(con, nov2)["sueldo_usd_cent"] == 125000


def test_borrar_el_unico_mes_vuelve_al_primer_uso(con, mes_id):
    meses.borrar_ultimo_mes(con, mes_id)
    assert meses.hay_meses(con) is False
    assert meses.mes_inicial(con, HOY) is None
    nuevo = meses.crear_primer_mes(con, 2026, 9, 120000)  # se puede elegir otro mes
    assert meses.obtener_ultimo_mes(con)["id"] == nuevo


def test_borrar_y_crear_varias_veces_cruzando_el_anio(con, tres_meses):
    _, _, dic = tres_meses
    ene = meses.crear_mes_siguiente(con, 130000)
    meses.borrar_ultimo_mes(con, ene)
    meses.borrar_ultimo_mes(con, dic)
    assert meses.sugerencias_mes_siguiente(con)["mes"] == 12
    nuevo_dic = meses.crear_mes_siguiente(con, 130000)
    nuevo_ene = meses.crear_mes_siguiente(con, 130000)
    assert [(m["anio"], m["mes"]) for m in meses.listar_meses(con)][:2] == [
        (2027, 1),
        (2026, 12),
    ]
    assert meses.obtener_ultimo_mes(con)["id"] == nuevo_ene != nuevo_dic
