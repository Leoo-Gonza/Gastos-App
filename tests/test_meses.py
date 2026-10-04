"""Pruebas de app/logica/meses.py: primer mes (RF-04, CA-04.1, CA-04.2) y RN-06, RN-07."""

from datetime import date

import pytest

from app.logica import meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT
from tests.ayudantes import cantidad_filas, insertar_mes


def test_base_vacia_no_tiene_meses(con):
    # CA-04.1 (lógica): con la base vacía, hay_meses es False y no hay último mes,
    # que es lo que usa la pantalla para pedir crear el primer mes.
    assert meses.hay_meses(con) is False
    assert meses.obtener_ultimo_mes(con) is None


def test_crear_primer_mes_con_cotizacion(con):
    # CA-04.1: crear el primer mes con año, mes, sueldo y cotización; se guarda en centavos.
    mes_id = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    fila = meses.obtener_mes(con, mes_id)
    assert (fila["anio"], fila["mes"]) == (2026, 10)
    assert fila["sueldo_usd_cent"] == 120000
    assert fila["cotizacion_cent"] == 160000
    assert meses.hay_meses(con) is True


def test_crear_primer_mes_sin_cotizacion(con):
    # Decisión aprobada / RN-06: la cotización del primer mes es opcional (queda NULL).
    mes_id = meses.crear_primer_mes(con, 2026, 10, 120000)
    assert meses.obtener_mes(con, mes_id)["cotizacion_cent"] is None


def test_crear_primer_mes_con_cotizacion_con_centavos(con):
    # RN-02: cotización 1.432,50 se guarda como 143250.
    mes_id = meses.crear_primer_mes(con, 2026, 10, 120000, 143250)
    assert meses.obtener_mes(con, mes_id)["cotizacion_cent"] == 143250


def test_crear_primer_mes_con_sueldo_cero(con):
    # RN-05: el sueldo puede ser 0.
    mes_id = meses.crear_primer_mes(con, 2026, 10, 0, 160000)
    assert meses.obtener_mes(con, mes_id)["sueldo_usd_cent"] == 0


def test_no_se_puede_crear_un_segundo_primer_mes(con):
    # RF-04: el primer mes se crea una sola vez; los siguientes son del paso 4.
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    with pytest.raises(ErrorDeValidacion):
        meses.crear_primer_mes(con, 2026, 11, 120000, 160000)
    assert cantidad_filas(con, "meses") == 1


@pytest.mark.parametrize("anio", [26, 99, 0, 999, 10000, -2026])
def test_ca_04_2_rechaza_anio_que_no_tiene_4_digitos(con, anio):
    # CA-04.2 / RN-07: año de 2 dígitos (u otro largo) se rechaza y no se crea nada.
    with pytest.raises(ErrorDeValidacion, match="4 dígitos"):
        meses.crear_primer_mes(con, anio, 10, 120000, 160000)
    assert meses.hay_meses(con) is False


@pytest.mark.parametrize("mes", [0, 13, -1])
def test_ca_04_2_rechaza_mes_fuera_de_rango(con, mes):
    # CA-04.2 / RN-07: mes 0 o 13 se rechaza y no se crea nada.
    with pytest.raises(ErrorDeValidacion, match="entre 1 y 12"):
        meses.crear_primer_mes(con, 2026, mes, 120000, 160000)
    assert meses.hay_meses(con) is False


@pytest.mark.parametrize(("anio", "mes"), [(1000, 1), (9999, 12)])
def test_acepta_limites_validos_de_anio_y_mes(con, anio, mes):
    # Bordes válidos de RN-07.
    meses.crear_primer_mes(con, anio, mes, 120000)
    assert meses.hay_meses(con) is True


def test_rechaza_sueldo_negativo(con):
    # RN-05: el sueldo debe ser >= 0.
    with pytest.raises(ErrorDeValidacion, match="negativo"):
        meses.crear_primer_mes(con, 2026, 10, -1, 160000)
    assert meses.hay_meses(con) is False


@pytest.mark.parametrize("cotizacion", [0, -160000])
def test_rechaza_cotizacion_cero_o_negativa(con, cotizacion):
    # RN-06: la cotización no puede ser 0 ni negativa.
    with pytest.raises(ErrorDeValidacion, match="mayor a 0"):
        meses.crear_primer_mes(con, 2026, 10, 120000, cotizacion)
    assert meses.hay_meses(con) is False


def test_obtener_mes_inexistente_devuelve_none(con):
    assert meses.obtener_mes(con, 999) is None


def test_obtener_ultimo_mes_es_el_mas_reciente(con):
    # El último mes se ordena por año y mes, no por orden de carga.
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    insertar_mes(con, 2027, 1)
    insertar_mes(con, 2026, 12)
    ultimo = meses.obtener_ultimo_mes(con)
    assert (ultimo["anio"], ultimo["mes"]) == (2027, 1)


@pytest.mark.parametrize(
    ("hoy", "esperado"),
    [
        (date(2026, 10, 4), (2026, 10)),
        (date(2026, 12, 31), (2026, 12)),
        (date(2027, 1, 1), (2027, 1)),
    ],
)
def test_mes_actual_calendario_con_fecha_fija(hoy, esperado):
    # §7: el mes actual debe poder fijarse en las pruebas.
    assert meses.mes_actual_calendario(hoy) == esperado


def test_mes_actual_calendario_sin_fecha_usa_hoy():
    # Sin parámetro usa el reloj del sistema.
    # Fecha local a propósito, igual que la app (ver meses.py).
    hoy = date.today()  # noqa: DTZ011
    assert meses.mes_actual_calendario() == (hoy.year, hoy.month)


# ---------------------------------------------------------------------------
# Ronda 3: O8 – sueldo y cotización validados con validar_centavos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sueldo", [1.5, 120000.0, "120000", True, False, None])
def test_o8_sueldo_que_no_es_entero_se_rechaza(con, sueldo):
    # O8 / RN-01: el sueldo tiene que ser int de centavos; no se crea el mes.
    with pytest.raises(
        ErrorDeValidacion, match="^El sueldo tiene que ser un número entero"
    ):
        meses.crear_primer_mes(con, 2026, 10, sueldo, 160000)
    assert meses.hay_meses(con) is False


@pytest.mark.parametrize("cotizacion", [1600.5, 160000.0, "160000", True])
def test_o8_cotizacion_que_no_es_entera_se_rechaza(con, cotizacion):
    # O8 / RN-02: la cotización tiene que ser int de centavos.
    with pytest.raises(
        ErrorDeValidacion, match="^La cotización tiene que ser un número entero"
    ):
        meses.crear_primer_mes(con, 2026, 10, 120000, cotizacion)
    assert meses.hay_meses(con) is False


@pytest.mark.parametrize("sueldo", [MONTO_MAXIMO_CENT + 1, 10**20])
def test_o8_sueldo_enorme_se_rechaza_con_mensaje(con, sueldo):
    # O8: antes 10**20 daba OverflowError de SQLite.
    with pytest.raises(ErrorDeValidacion, match="^El sueldo es demasiado grande.$"):
        meses.crear_primer_mes(con, 2026, 10, sueldo, 160000)
    assert meses.hay_meses(con) is False


@pytest.mark.parametrize("cotizacion", [MONTO_MAXIMO_CENT + 1, 10**20])
def test_o8_cotizacion_enorme_se_rechaza_con_mensaje(con, cotizacion):
    with pytest.raises(ErrorDeValidacion, match="^La cotización es demasiado grande.$"):
        meses.crear_primer_mes(con, 2026, 10, 120000, cotizacion)
    assert meses.hay_meses(con) is False


def test_o8_sueldo_y_cotizacion_en_el_tope_exacto_se_aceptan(con):
    # El tope exacto vale para sueldo y cotización y se guarda sin perder precisión.
    mes_id = meses.crear_primer_mes(con, 2026, 10, MONTO_MAXIMO_CENT, MONTO_MAXIMO_CENT)
    fila = meses.obtener_mes(con, mes_id)
    assert fila["sueldo_usd_cent"] == MONTO_MAXIMO_CENT
    assert fila["cotizacion_cent"] == MONTO_MAXIMO_CENT


def test_o8_mensajes_de_sueldo_y_cotizacion_negativos(con):
    # Los mensajes nombran el dato correcto.
    with pytest.raises(ErrorDeValidacion, match="^El sueldo no puede ser negativo.$"):
        meses.crear_primer_mes(con, 2026, 10, -1, 160000)
    with pytest.raises(
        ErrorDeValidacion, match="^La cotización tiene que ser mayor a 0.$"
    ):
        meses.crear_primer_mes(con, 2026, 10, 120000, -1)
