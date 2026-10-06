"""Pruebas de la lógica de planes de cuotas (paso 4b): RF-16 a RF-22, RN-24 a RN-31,
RN-52 y la parte de cuotas de RN-09. Criterios CA-16.x a CA-22.x, CA-08.2, CA-08.3,
la parte de cuotas de CA-03.1, CA-03.4, CA-03.6 y CA-37.x con planes creados por la
función. Base en memoria, datos inventados y "hoy" fijo (parámetro hoy=...)."""

from datetime import date

import pytest

from app.logica import catalogos, configuracion, cuotas, gastos, meses, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT, formatear_ars
from app.logica.resumen import calcular_resumen
from tests.ayudantes import cantidad_filas, id_por_nombre

HOY = date(2026, 10, 4)  # mes actual del calendario: 2026-10


def _plan(primer_anio, primer_mes, cantidad, monto=1000000, cancelado=None):
    """Plan "en memoria" para las funciones puras (no hace falta la base)."""
    return {
        "id": 0,
        "primer_anio": primer_anio,
        "primer_mes": primer_mes,
        "cantidad_cuotas": cantidad,
        "monto_cuota_cent": monto,
        "cancelado_anio": cancelado[0] if cancelado else None,
        "cancelado_mes": cancelado[1] if cancelado else None,
    }


@pytest.fixture
def otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _meses(con, desde, hasta):
    """Crea los meses de "desde" a "hasta" (inclusive), en orden. Devuelve {(a, m): id}."""
    ids = {desde: meses.crear_primer_mes(con, *desde, 120000, 160000)}
    actual = desde
    while actual != hasta:
        actual = meses.siguiente(*actual)
        ids[actual] = meses.crear_mes(con, *actual, 120000, 160000)
    return ids


def _crear(
    con,
    otros,
    nombre="Plan",
    monto=1000000,
    cantidad=6,
    primera=(2026, 8),
    medio=None,
    hoy=HOY,
):
    return cuotas.crear_plan(
        con, nombre, otros, medio, monto, cantidad, *primera, hoy=hoy
    )


def _cuota(con, plan_id, mes_id):
    return con.execute(
        "SELECT * FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
        (plan_id, mes_id),
    ).fetchone()


def _texto(con, plan_id, anio, mes):
    return cuotas.detalle(cuotas.obtener_plan(con, plan_id), anio, mes, HOY).cuota_texto


# ---------------------------------------------------------------------------
# Funciones puras: número de cuota, última, restante, estado, detalle
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("primera", "mes", "n"),
    [
        ((2026, 8), (2026, 10), 3),  # CA-16.1
        ((2026, 3), (2026, 10), 8),  # CA-17.2
        ((2026, 3), (2026, 9), 7),
        ((2025, 11), (2026, 10), 12),  # cruce de año
        ((2026, 12), (2026, 10), -1),  # no empezó
        ((2026, 10), (2026, 10), 1),
        ((2026, 11), (2027, 1), 3),
    ],
)
def test_numero_de_cuota(primera, mes, n):
    assert cuotas.numero_de_cuota(_plan(*primera, 12), *mes) == n


@pytest.mark.parametrize(
    ("primera", "cantidad", "ultima"),
    [
        ((2026, 8), 3, (2026, 10)),  # CA-17.1
        ((2026, 3), 12, (2027, 2)),  # CA-17.2
        ((2025, 11), 12, (2026, 10)),  # CA-17.3: cruce de año
        ((2026, 10), 1, (2026, 10)),  # plan de una cuota
        ((2026, 12), 2, (2027, 1)),
        ((2026, 1), 600, (2075, 12)),  # el máximo permitido
    ],
)
def test_ultima_cuota(primera, cantidad, ultima):
    assert cuotas.ultima_cuota(_plan(*primera, cantidad)) == ultima


def test_ultima_cuota_de_un_plan_cancelado():
    # RN-25 / RN-31: el mes anterior al primero sin cuota.
    assert cuotas.ultima_cuota(_plan(2026, 8, 6, cancelado=(2026, 10))) == (2026, 9)
    assert cuotas.ultima_cuota(_plan(2026, 8, 6, cancelado=(2027, 1))) == (2026, 12)


@pytest.mark.parametrize(
    ("primera", "cantidad", "mes", "restante"),
    [
        ((2026, 3), 12, (2026, 10), 4000000),  # CA-17.2: 8/12 → 4 × 10.000
        ((2026, 3), 12, (2026, 9), 5000000),  # CA-17.2: 7/12 → 5 × 10.000
        ((2026, 8), 3, (2026, 10), 0),  # CA-17.1: última cuota
        ((2026, 12), 12, (2026, 10), 12000000),  # CA-17.4: no empezó → 12 × cuota
        ((2026, 1), 3, (2026, 10), 0),  # terminado
    ],
)
def test_restante(primera, cantidad, mes, restante):
    assert cuotas.restante(_plan(*primera, cantidad), *mes) == restante


def test_restante_de_un_plan_cancelado_es_cero():
    assert cuotas.restante(_plan(2026, 8, 6, cancelado=(2026, 10)), 2026, 9) == 0


@pytest.mark.parametrize(
    ("plan", "esperado"),
    [
        (_plan(2026, 8, 6), cuotas.ACTIVO),
        (_plan(2026, 12, 3), cuotas.ACTIVO),  # todavía no empezó: activo
        (_plan(2026, 8, 3), cuotas.ACTIVO),  # última cuota en el mes actual
        (_plan(2026, 7, 3), cuotas.TERMINADO),  # última 2026-09 < 2026-10
        (_plan(2026, 8, 6, cancelado=(2026, 10)), cuotas.CANCELADO),
    ],
)
def test_estado(plan, esperado):
    assert cuotas.estado(plan, HOY) == esperado


@pytest.mark.parametrize(
    ("primera", "cantidad", "mes", "texto"),
    [
        ((2026, 8), 3, (2026, 10), "3/3"),
        ((2026, 3), 12, (2026, 10), "8/12"),
        ((2026, 12), 12, (2026, 10), "no empezó"),
        ((2026, 1), 3, (2026, 10), "terminado"),
    ],
)
def test_detalle_texto_de_la_cuota(primera, cantidad, mes, texto):
    d = cuotas.detalle(_plan(*primera, cantidad), *mes, HOY)
    assert d.cuota_texto == texto
    assert d.total == cantidad * 1000000


def test_detalle_de_un_plan_cancelado():
    plan = _plan(2026, 8, 6, cancelado=(2026, 10))
    assert cuotas.detalle(plan, 2026, 9, HOY).cuota_texto == "2/6"  # antes de cancelar
    assert cuotas.detalle(plan, 2026, 10, HOY).cuota_texto == "terminado"
    d = cuotas.detalle(plan, 2026, 10, HOY)
    assert (d.estado, d.ultima, d.restante) == (cuotas.CANCELADO, (2026, 9), 0)


# ---------------------------------------------------------------------------
# Alta (RF-16, RF-18, RN-29, RN-30, CA-16.x, CA-17.x, CA-18.x)
# ---------------------------------------------------------------------------


def test_ca_16_1_alta_de_avant_service(con, mes_id, otros):
    pid = cuotas.crear_plan(
        con, "Avant Service", otros, None, 4111666, 3, 2026, 8, hoy=HOY
    )
    gasto = _cuota(con, pid, mes_id)
    assert (gasto["nombre"], gasto["tipo"], gasto["monto_cent"]) == (
        "Avant Service",
        "cuota",
        4111666,
    )
    assert (gasto["moneda"], gasto["monto_usd_cent"], gasto["cotizacion_cent"]) == (
        "ARS",
        None,
        None,
    )
    assert formatear_ars(gasto["monto_cent"]) == "$ 41.117"
    assert _texto(con, pid, 2026, 10) == "3/3"
    # CA-17.1
    d = cuotas.detalle(cuotas.obtener_plan(con, pid), 2026, 10, HOY)
    assert (d.ultima, d.restante) == ((2026, 10), 0)


def test_alta_guarda_el_plan(con, mes_id, otros):
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    pid = cuotas.crear_plan(
        con, "  Heladera   nueva ", otros, visa, 1000000, 6, 2026, 8, hoy=HOY
    )
    plan = cuotas.obtener_plan(con, pid)
    assert (plan["nombre"], plan["categoria_id"], plan["medio_pago_id"]) == (
        "Heladera nueva",
        otros,
        visa,
    )
    assert (plan["monto_cuota_cent"], plan["cantidad_cuotas"]) == (1000000, 6)
    assert (plan["primer_anio"], plan["primer_mes"]) == (2026, 8)
    assert (plan["cancelado_anio"], plan["cancelado_mes"]) == (None, None)
    gasto = _cuota(con, pid, mes_id)
    assert (gasto["categoria_id"], gasto["medio_pago_id"]) == (otros, visa)


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"),
    [
        (
            {"cantidad": 0},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": -3},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": 2.5},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": 3.0},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": "3"},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": True},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": None},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        ({"cantidad": 601}, "cantidad", "La cantidad de cuotas es demasiado grande."),
        ({"monto": 0}, "monto", "El monto de la cuota tiene que ser mayor a 0."),
        ({"monto": -100}, "monto", "El monto de la cuota tiene que ser mayor a 0."),
        (
            {"monto": 1.5},
            "monto",
            "El monto de la cuota tiene que ser un número entero de centavos.",
        ),
        (
            {"monto": None},
            "monto",
            "El monto de la cuota tiene que ser un número entero de centavos.",
        ),
        (
            {"monto": MONTO_MAXIMO_CENT + 1},
            "monto",
            "El monto de la cuota es demasiado grande.",
        ),
        ({"nombre": "   "}, "nombre", "Ingresá un nombre."),
        ({"nombre": None}, "nombre", "Ingresá un nombre."),
        ({"categoria": None}, "categoria", "Elegí una categoría."),
        ({"categoria": 999}, "categoria", "La categoría elegida no existe."),
        ({"medio": 999}, "medio_pago", "El medio de pago elegido no existe."),
        ({"primera": (2026, 13)}, "primera", "El mes tiene que estar entre 1 y 12."),
        ({"primera": (2026, 0)}, "primera", "El mes tiene que estar entre 1 y 12."),
        ({"primera": (26, 8)}, "primera", "El año tiene que tener 4 dígitos."),
    ],
)
def test_ca_16_2_validaciones(con, mes_id, otros, cambios, campo, mensaje):
    datos = {
        "nombre": "Plan",
        "categoria": otros,
        "medio": None,
        "monto": 1000000,
        "cantidad": 6,
        "primera": (2026, 8),
    }
    datos.update(cambios)
    with pytest.raises(ErrorDeValidacion) as error:
        cuotas.crear_plan(
            con,
            datos["nombre"],
            datos["categoria"],
            datos["medio"],
            datos["monto"],
            datos["cantidad"],
            *datos["primera"],
            hoy=HOY,
        )
    assert (str(error.value), error.value.campo) == (mensaje, campo)
    assert cantidad_filas(con, "planes_cuotas") == 0
    assert cantidad_filas(con, "gastos") == 0


def test_cantidad_maxima_600_se_acepta(con, mes_id, otros):
    pid = _crear(con, otros, cantidad=600)
    assert cuotas.obtener_plan(con, pid)["cantidad_cuotas"] == 600


@pytest.mark.parametrize("tabla", [catalogos.CATEGORIAS, catalogos.MEDIOS_PAGO])
def test_alta_no_acepta_categoria_ni_medio_archivados(con, mes_id, otros, tabla):
    gym = catalogos.crear(con, tabla, "Gym")
    if tabla == catalogos.CATEGORIAS:
        gastos.agregar_gasto(con, mes_id, "X", gym, 100, "fijo")
    else:
        gastos.agregar_gasto(con, mes_id, "X", otros, 100, "fijo", gym)
    catalogos.eliminar(con, tabla, gym)
    with pytest.raises(ErrorDeValidacion, match="archivad"):
        if tabla == catalogos.CATEGORIAS:
            cuotas.crear_plan(con, "Plan", gym, None, 100, 3, 2026, 8, hoy=HOY)
        else:
            cuotas.crear_plan(con, "Plan", otros, gym, 100, 3, 2026, 8, hoy=HOY)
    assert cantidad_filas(con, "planes_cuotas") == 0


def test_ca_17_2_cuota_y_restante_segun_el_mes_visto(con, mes_id, otros):
    pid = _crear(con, otros, cantidad=12, primera=(2026, 3))
    plan = cuotas.obtener_plan(con, pid)
    d10 = cuotas.detalle(plan, 2026, 10, HOY)
    d09 = cuotas.detalle(plan, 2026, 9, HOY)
    assert (d10.cuota_texto, d10.ultima, d10.restante) == ("8/12", (2027, 2), 4000000)
    assert (d09.cuota_texto, d09.restante) == ("7/12", 5000000)


def test_ca_17_3_ultima_cuota_cruzando_el_anio(con, mes_id, otros):
    pid = _crear(con, otros, cantidad=12, primera=(2025, 11))
    assert cuotas.ultima_cuota(cuotas.obtener_plan(con, pid)) == (2026, 10)
    assert _texto(con, pid, 2026, 10) == "12/12"
    assert _cuota(con, pid, mes_id) is not None


def test_ca_17_4_plan_que_no_empezo(con, mes_id, otros):
    pid = _crear(con, otros, cantidad=12, primera=(2026, 12))
    assert _cuota(con, pid, mes_id) is None
    d = cuotas.detalle(cuotas.obtener_plan(con, pid), 2026, 10, HOY)
    assert (d.cuota_texto, d.restante) == ("no empezó", 12000000)


def test_ca_18_1_y_18_2_genera_en_el_mes_actual_y_los_futuros(con, otros):
    ids = _meses(con, (2026, 9), (2026, 11))
    pid = _crear(con, otros)  # 6 cuotas desde 2026-08; hoy 2026-10
    assert _cuota(con, pid, ids[(2026, 9)]) is None  # CA-18.1: 2026-09 no se toca
    assert _cuota(con, pid, ids[(2026, 10)])["monto_cent"] == 1000000
    assert _texto(con, pid, 2026, 10) == "3/6"
    assert _cuota(con, pid, ids[(2026, 11)]) is not None  # CA-18.2
    assert _texto(con, pid, 2026, 11) == "4/6"


def test_ca_18_3_si_el_mes_actual_no_existe_no_genera_y_aparece_al_crearlo(con, otros):
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    pid = _crear(con, otros)
    assert cantidad_filas(con, "gastos") == 0
    assert _cuota(con, pid, sep) is None
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, oct_)["tipo"] == "cuota"
    assert _texto(con, pid, 2026, 10) == "3/6"


def test_alta_nunca_toca_meses_anteriores_al_actual(con, otros):
    # Hoy es 2026-11: el plan empieza en 2026-08 pero octubre (pasado) no se toca.
    ids = _meses(con, (2026, 9), (2026, 11))
    pid = _crear(con, otros, hoy=date(2026, 11, 2))
    assert _cuota(con, pid, ids[(2026, 9)]) is None
    assert _cuota(con, pid, ids[(2026, 10)]) is None
    assert _cuota(con, pid, ids[(2026, 11)]) is not None


def test_plan_de_una_sola_cuota(con, otros):
    ids = _meses(con, (2026, 10), (2026, 11))
    pid = _crear(con, otros, cantidad=1, primera=(2026, 10))
    assert _cuota(con, pid, ids[(2026, 10)]) is not None
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    assert _texto(con, pid, 2026, 10) == "1/1"
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, dic) is None


def test_plan_que_cruza_el_anio(con, otros):
    _meses(con, (2026, 10), (2026, 11))
    pid = _crear(con, otros, cantidad=3, primera=(2026, 11))
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    ene = meses.crear_mes_siguiente(con, 120000, 160000)
    feb = meses.crear_mes_siguiente(con, 120000, 160000)
    assert (_texto(con, pid, 2026, 12), _texto(con, pid, 2027, 1)) == ("2/3", "3/3")
    assert _cuota(con, pid, dic) is not None and _cuota(con, pid, ene) is not None
    assert _cuota(con, pid, feb) is None
    assert cuotas.ultima_cuota(cuotas.obtener_plan(con, pid)) == (2027, 1)


def test_alta_es_atomica(con, mes_id, otros, monkeypatch):
    _meses_extra = meses.crear_mes_siguiente(con, 120000, 160000)  # 2026-11
    original = cuotas._insertar_cuota
    llamadas = []

    def falla_en_la_segunda(con_, plan, mes):
        llamadas.append(1)
        if len(llamadas) == 2:
            raise RuntimeError("falla simulada")
        original(con_, plan, mes)

    monkeypatch.setattr(cuotas, "_insertar_cuota", falla_en_la_segunda)
    with pytest.raises(RuntimeError):
        _crear(con, otros)
    assert cantidad_filas(con, "planes_cuotas") == 0
    assert cantidad_filas(con, "gastos") == 0
    assert _meses_extra


# ---------------------------------------------------------------------------
# Mes nuevo con cuotas (RN-09, CA-03.1, CA-03.4, CA-03.6)
# ---------------------------------------------------------------------------


def test_ca_03_1_la_cuota_3_3_aparece_al_crear_noviembre(con, mes_id, otros):
    pid = _crear(con, otros, nombre="Avant", cantidad=3, primera=(2026, 9))
    assert meses.sugerencias_mes_siguiente(con)["cuotas"] == 1
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    cuota = _cuota(con, pid, nov)
    assert (cuota["nombre"], cuota["monto_cent"]) == ("Avant", 1000000)
    assert gastos.total_pagado(con, cuota["id"]) == 0
    assert _texto(con, pid, 2026, 11) == "3/3"


def test_ca_03_4_planes_terminados_y_cancelados_no_generan(con, mes_id, otros):
    termina = _crear(
        con, otros, nombre="Termina en octubre", cantidad=3, primera=(2026, 8)
    )
    cancelado = _crear(con, otros, nombre="Cancelado", cantidad=12, primera=(2026, 8))
    cuotas.cancelar_plan(con, cancelado, hoy=HOY)
    sigue = _crear(con, otros, nombre="Sigue", cantidad=12, primera=(2026, 8))
    assert meses.sugerencias_mes_siguiente(con)["cuotas"] == 1
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, termina, nov) is None
    assert _cuota(con, cancelado, nov) is None
    assert _cuota(con, sigue, nov) is not None


def test_ca_03_6_cuota_con_medio_archivado_se_genera(con, mes_id, otros):
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    pid = _crear(con, otros, medio=visa)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)  # en uso: se archiva
    assert catalogos.obtener(con, catalogos.MEDIOS_PAGO, visa)["archivado"] == 1
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    [fila] = [
        g
        for g in gastos.listar_gastos(con, nov)
        if g["id"] == _cuota(con, pid, nov)["id"]
    ]
    assert (fila["medio_pago"], fila["medio_pago_archivado"]) == ("Visa Santander", 1)


def test_crear_mes_con_falla_al_generar_cuotas_no_deja_nada(
    con, mes_id, otros, monkeypatch
):
    _crear(con, otros)
    gastos.agregar_gasto(con, mes_id, "Alquiler", otros, 100, "fijo")

    def falla(*args, **kwargs):
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(cuotas, "generar_cuotas_del_mes", falla)
    with pytest.raises(RuntimeError):
        meses.crear_mes_siguiente(con, 120000, 160000)
    assert len(meses.listar_meses(con)) == 1
    assert cantidad_filas(con, "gastos") == 2  # la cuota y el fijo de octubre


def test_cuotas_que_se_generarian(con, mes_id, otros):
    _crear(con, otros, nombre="A", cantidad=6)
    _crear(con, otros, nombre="B", cantidad=3)  # última 2026-10
    _crear(con, otros, nombre="C", cantidad=6, primera=(2027, 1))
    assert cuotas.cuotas_que_se_generarian(con, 2026, 11) == 1
    assert cuotas.cuotas_que_se_generarian(con, 2027, 1) == 2


def test_ca_03_2_sugerencias_incluyen_las_cuotas(con, mes_id, otros):
    _crear(con, otros)
    sug = meses.sugerencias_mes_siguiente(con)
    assert (sug["anio"], sug["mes"], sug["cuotas"]) == (2026, 11, 1)


# ---------------------------------------------------------------------------
# Edición (RF-19, RN-30, CA-19.x)
# ---------------------------------------------------------------------------


@pytest.fixture
def caso_18_2(con, otros):
    """2026-09, 2026-10 y 2026-11; plan de 6 cuotas de 10.000 desde 2026-08.

    Como 2026-09 es anterior al mes actual, su cuota (si existía de antes) se
    inserta por SQL para comprobar que la edición no la toca."""
    ids = _meses(con, (2026, 9), (2026, 11))
    pid = _crear(con, otros)
    with con:
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Plan', ?, 1000000, 'cuota', ?)",
            (ids[(2026, 9)], otros, pid),
        )
    return ids, pid


def _editar(
    con,
    pid,
    otros,
    monto=1000000,
    cantidad=6,
    primera=(2026, 8),
    nombre="Plan",
    medio=None,
):
    cuotas.editar_plan(
        con, pid, nombre, otros, medio, monto, cantidad, *primera, hoy=HOY
    )


def test_ca_19_1_cambiar_la_cuota(con, otros, caso_18_2):
    ids, pid = caso_18_2
    _editar(con, pid, otros, monto=1200000)
    assert _cuota(con, pid, ids[(2026, 10)])["monto_cent"] == 1200000
    assert _cuota(con, pid, ids[(2026, 11)])["monto_cent"] == 1200000
    assert _cuota(con, pid, ids[(2026, 9)])["monto_cent"] == 1000000


def test_ca_19_2_cuota_con_pagos_no_se_toca(con, otros, caso_18_2):
    ids, pid = caso_18_2
    cuota_oct = _cuota(con, pid, ids[(2026, 10)])["id"]
    pagos.registrar_pago(con, cuota_oct, 500000, HOY)
    _editar(con, pid, otros, monto=1200000)
    assert gastos.obtener_gasto(con, cuota_oct)["monto_cent"] == 1000000
    assert pagos.pendiente(con, cuota_oct) == 500000
    assert _cuota(con, pid, ids[(2026, 11)])["monto_cent"] == 1200000


def test_ca_19_3_cuota_omitida_no_se_vuelve_a_crear(con, otros, caso_18_2):
    ids, pid = caso_18_2
    gastos.borrar_gasto(con, _cuota(con, pid, ids[(2026, 11)])["id"])
    _editar(con, pid, otros, monto=1200000)
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    assert _cuota(con, pid, ids[(2026, 10)])["monto_cent"] == 1200000


def test_editar_nombre_categoria_y_medio(con, otros, caso_18_2):
    ids, pid = caso_18_2
    vivienda = id_por_nombre(con, catalogos.CATEGORIAS, "Vivienda")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    cuotas.editar_plan(
        con, pid, "Heladera", vivienda, visa, 1000000, 6, 2026, 8, hoy=HOY
    )
    for mes in [(2026, 10), (2026, 11)]:
        c = _cuota(con, pid, ids[mes])
        assert (c["nombre"], c["categoria_id"], c["medio_pago_id"]) == (
            "Heladera",
            vivienda,
            visa,
        )
    viejo = _cuota(con, pid, ids[(2026, 9)])
    assert (viejo["nombre"], viejo["categoria_id"], viejo["medio_pago_id"]) == (
        "Plan",
        otros,
        None,
    )


def test_editar_acortando_el_plan_borra_las_cuotas_que_sobran(con, otros, caso_18_2):
    # 6 → 3 cuotas: la última pasa a 2026-10; la de 2026-11 se borra (sin pagos).
    ids, pid = caso_18_2
    _editar(con, pid, otros, cantidad=3)
    assert _cuota(con, pid, ids[(2026, 10)]) is not None
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    assert cantidad_filas(con, "cuotas_omitidas") == 0  # no la borró el usuario
    assert _cuota(con, pid, ids[(2026, 9)]) is not None


def test_editar_acortando_conserva_las_cuotas_con_pagos(con, otros, caso_18_2):
    ids, pid = caso_18_2
    cuota_nov = _cuota(con, pid, ids[(2026, 11)])["id"]
    pagos.registrar_pago(con, cuota_nov, 100000, HOY)
    _editar(con, pid, otros, cantidad=3)
    assert gastos.obtener_gasto(con, cuota_nov) is not None


def test_editar_alargando_el_plan_crea_cuotas(con, otros):
    ids = _meses(con, (2026, 10), (2026, 12))
    pid = _crear(con, otros, cantidad=3, primera=(2026, 9))  # última 2026-11
    assert _cuota(con, pid, ids[(2026, 12)]) is None
    _editar(con, pid, otros, cantidad=6, primera=(2026, 9))
    assert _cuota(con, pid, ids[(2026, 12)]) is not None
    assert _texto(con, pid, 2026, 12) == "4/6"


def test_editar_cambiando_la_primera_cuota(con, otros, caso_18_2):
    # La primera pasa a 2026-11: en 2026-10 ya no corresponde (se borra); 2026-09 no se toca.
    ids, pid = caso_18_2
    _editar(con, pid, otros, primera=(2026, 11))
    assert _cuota(con, pid, ids[(2026, 10)]) is None
    assert _cuota(con, pid, ids[(2026, 11)]) is not None
    assert _texto(con, pid, 2026, 11) == "1/6"
    assert _cuota(con, pid, ids[(2026, 9)]) is not None


def test_editar_con_errores_no_cambia_nada(con, otros, caso_18_2):
    ids, pid = caso_18_2
    with pytest.raises(ErrorDeValidacion):
        _editar(con, pid, otros, monto=0)
    assert cuotas.obtener_plan(con, pid)["monto_cuota_cent"] == 1000000
    assert _cuota(con, pid, ids[(2026, 10)])["monto_cent"] == 1000000


def test_editar_conserva_categoria_y_medio_archivados_del_plan(con, mes_id, otros):
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    pid = cuotas.crear_plan(con, "Plan", gym, visa, 1000000, 6, 2026, 8, hoy=HOY)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    cuotas.editar_plan(con, pid, "Plan", gym, visa, 1100000, 6, 2026, 8, hoy=HOY)
    assert cuotas.obtener_plan(con, pid)["monto_cuota_cent"] == 1100000


def test_editar_plan_inexistente(con, mes_id, otros):
    with pytest.raises(ErrorDeValidacion) as error:
        _editar(con, 999, otros)
    assert (str(error.value), error.value.campo) == (
        "Ese plan de cuotas ya no existe.",
        None,
    )


def test_editar_nunca_toca_meses_anteriores_aunque_se_vea_otro(con, otros, caso_18_2):
    # Aunque la primera cuota sea anterior y se "esté viendo" 2026-09, solo cambia
    # el mes actual y los futuros.
    ids, pid = caso_18_2
    _editar(con, pid, otros, monto=1500000, primera=(2026, 7))
    assert _cuota(con, pid, ids[(2026, 9)])["monto_cent"] == 1000000


# ---------------------------------------------------------------------------
# Cancelación (RF-20, RN-31, CA-20.x)
# ---------------------------------------------------------------------------


def test_ca_20_1_cancelar_sin_pagos(con, otros, caso_18_2):
    ids, pid = caso_18_2
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert _cuota(con, pid, ids[(2026, 10)]) is None
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    assert _cuota(con, pid, ids[(2026, 9)]) is not None  # meses anteriores siguen
    plan = cuotas.obtener_plan(con, pid)
    assert (plan["cancelado_anio"], plan["cancelado_mes"]) == (2026, 10)
    assert cuotas.ultima_cuota(plan) == (2026, 9)
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, dic) is None


def test_ca_20_2_cancelar_con_pagos_en_el_mes_actual(con, otros, caso_18_2):
    ids, pid = caso_18_2
    cuota_oct = _cuota(con, pid, ids[(2026, 10)])["id"]
    pagos.registrar_pago(con, cuota_oct, 500000, HOY)
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert gastos.obtener_gasto(con, cuota_oct)["monto_cent"] == 1000000
    assert pagos.pendiente(con, cuota_oct) == 500000
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    plan = cuotas.obtener_plan(con, pid)
    assert (plan["cancelado_anio"], plan["cancelado_mes"]) == (2026, 11)
    assert cuotas.ultima_cuota(plan) == (2026, 10)
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, dic) is None


def test_cancelar_conserva_cuotas_futuras_con_pagos(con, otros, caso_18_2):
    ids, pid = caso_18_2
    cuota_nov = _cuota(con, pid, ids[(2026, 11)])["id"]
    pagos.registrar_pago(con, cuota_nov, 100000, HOY)
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert gastos.obtener_gasto(con, cuota_nov) is not None


def test_ca_20_3_cancelado_restante_cero_y_filtro(con, otros, caso_18_2):
    _, pid = caso_18_2
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    d = cuotas.detalle(cuotas.obtener_plan(con, pid), 2026, 10, HOY)
    assert (d.restante, d.estado) == (0, cuotas.CANCELADO)
    nombres = [
        x.plan["nombre"]
        for x in cuotas.listar_planes(con, 2026, 10, cuotas.CANCELADO, HOY)
    ]
    assert nombres == ["Plan"]


def test_cancelar_dos_veces_o_inexistente(con, otros, caso_18_2):
    _, pid = caso_18_2
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    with pytest.raises(ErrorDeValidacion) as error:
        cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert str(error.value) == "Ese plan ya está cancelado."
    with pytest.raises(ErrorDeValidacion, match="^Ese plan de cuotas ya no existe.$"):
        cuotas.cancelar_plan(con, 999, hoy=HOY)


def test_cancelar_en_distintos_meses(con, otros):
    # Cancelado con "hoy" en noviembre: octubre (pasado) conserva su cuota.
    ids = _meses(con, (2026, 10), (2026, 12))
    pid = _crear(con, otros)
    cuotas.cancelar_plan(con, pid, hoy=date(2026, 11, 20))
    assert _cuota(con, pid, ids[(2026, 10)]) is not None
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    assert _cuota(con, pid, ids[(2026, 12)]) is None
    assert cuotas.ultima_cuota(cuotas.obtener_plan(con, pid)) == (2026, 10)


def test_cancelar_cuando_el_mes_actual_no_existe(con, otros):
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    pid = _crear(con, otros)
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    plan = cuotas.obtener_plan(con, pid)
    assert (plan["cancelado_anio"], plan["cancelado_mes"]) == (2026, 10)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, oct_) is None
    assert sep


def test_editar_un_plan_cancelado_no_lo_reactiva(con, otros, caso_18_2):
    ids, pid = caso_18_2
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    _editar(con, pid, otros, monto=1200000)
    assert _cuota(con, pid, ids[(2026, 10)]) is None
    assert cuotas.obtener_plan(con, pid)["cancelado_anio"] == 2026


def test_bug19_cancelar_un_plan_ya_terminado_se_rechaza(con, mes_id, otros):
    # Un plan que terminó en 2026-03 no se puede cancelar: no cambia nada.
    pid = _crear(con, otros, cantidad=3, primera=(2026, 1))
    with pytest.raises(ErrorDeValidacion) as error:
        cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert (str(error.value), error.value.campo) == ("Ese plan ya terminó.", None)
    plan = cuotas.obtener_plan(con, pid)
    assert (plan["cancelado_anio"], plan["cancelado_mes"]) == (None, None)
    assert cuotas.ultima_cuota(plan) == (2026, 3)
    assert cuotas.estado(plan, HOY) == cuotas.TERMINADO


def test_bug19_cancelar_antes_de_empezar_no_tiene_ultima_cuota(con, mes_id, otros):
    pid = _crear(con, otros, cantidad=3, primera=(2026, 12))
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    plan = cuotas.obtener_plan(con, pid)
    assert cuotas.ultima_cuota(plan) is None
    d = cuotas.detalle(plan, 2026, 10, HOY)
    assert (d.ultima, d.estado, d.restante) == (None, cuotas.CANCELADO, 0)


@pytest.mark.parametrize(
    ("primera", "cantidad", "cancelado", "ultima"),
    [
        ((2026, 8), 6, (2026, 10), (2026, 9)),  # a mitad: el mes anterior a cancelar
        ((2026, 8), 6, (2026, 11), (2026, 10)),  # con pagos en el mes actual
        ((2026, 9), 2, (2026, 11), (2026, 10)),  # cancelado justo después de la última
        ((2026, 9), 2, (2027, 3), (2026, 10)),  # min(última real, anterior a cancelar)
        ((2026, 10), 3, (2026, 10), None),  # cancelado en la primera: no hubo cuotas
        ((2026, 12), 3, (2026, 10), None),  # cancelado antes de empezar
    ],
)
def test_bug19_ultima_cuota_de_un_cancelado(primera, cantidad, cancelado, ultima):
    assert cuotas.ultima_cuota(_plan(*primera, cantidad, cancelado=cancelado)) == ultima


def test_bug19_cancelar_en_la_ultima_cuota_se_permite(con, mes_id, otros):
    # La última cuota es el mes actual: el plan todavía está activo y se puede cancelar.
    pid = _crear(con, otros, cantidad=3, primera=(2026, 8))
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    assert cuotas.ultima_cuota(cuotas.obtener_plan(con, pid)) == (2026, 9)


# ---------------------------------------------------------------------------
# Lista y filtros (RF-21, CA-21.1)
# ---------------------------------------------------------------------------


@pytest.fixture
def tres_planes(con, mes_id, otros):
    activo = _crear(con, otros, nombre="Activo", cantidad=6)
    terminado = _crear(con, otros, nombre="Terminado", cantidad=3, primera=(2026, 1))
    cancelado = _crear(con, otros, nombre="Cancelado", cantidad=12)
    cuotas.cancelar_plan(con, cancelado, hoy=HOY)
    futuro = _crear(con, otros, nombre="Futuro", cantidad=3, primera=(2027, 1))
    return activo, terminado, cancelado, futuro


@pytest.mark.parametrize("visto", [(2026, 10), (2026, 9), (2027, 5), (2025, 1)])
def test_ca_21_1_filtros_no_dependen_del_mes_visto(con, tres_planes, visto):
    def nombres(filtro):
        return [
            d.plan["nombre"] for d in cuotas.listar_planes(con, *visto, filtro, HOY)
        ]

    assert nombres(cuotas.ACTIVO) == ["Activo", "Futuro"]
    assert nombres(cuotas.TERMINADO) == ["Terminado"]
    assert nombres(cuotas.CANCELADO) == ["Cancelado"]
    assert nombres(None) == ["Activo", "Cancelado", "Futuro", "Terminado"]


def test_terminado_depende_del_mes_del_calendario(con, mes_id, otros):
    pid = _crear(con, otros, cantidad=3, primera=(2026, 8))  # última 2026-10
    plan = cuotas.obtener_plan(con, pid)
    assert cuotas.estado(plan, date(2026, 10, 31)) == cuotas.ACTIVO
    assert cuotas.estado(plan, date(2026, 11, 1)) == cuotas.TERMINADO


def test_listar_planes_ordena_ignorando_acentos(con, mes_id, otros):
    # Igual que las demás listas de la app (BUG-05, O5): "Ágil" va con la A.
    for nombre in ["Zeta", "Ágil", "auto", "Ómnibus"]:
        _crear(con, otros, nombre=nombre)
    nombres = [d.plan["nombre"] for d in cuotas.listar_planes(con, 2026, 10, hoy=HOY)]
    assert nombres == ["Ágil", "auto", "Ómnibus", "Zeta"]


def test_listar_planes_sin_planes(con, mes_id):
    assert cuotas.listar_planes(con, 2026, 10, hoy=HOY) == []


# ---------------------------------------------------------------------------
# Total por medio de pago (RF-22, CA-22.1)
# ---------------------------------------------------------------------------


def test_ca_22_1_total_por_medio_de_pago(con, mes_id, otros):
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    master = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Mastercard Nación")
    transferencia = id_por_nombre(con, catalogos.MEDIOS_PAGO, "Transferencia")
    gastos.agregar_gasto(con, mes_id, "Gym", otros, 5000000, "fijo", visa)
    cuotas.crear_plan(con, "Avant", otros, visa, 4111666, 3, 2026, 8, hoy=HOY)
    gastos.agregar_gasto(con, mes_id, "Seguro", otros, 13100000, "fijo", master)
    gastos.agregar_gasto(
        con, mes_id, "Alquiler", otros, 26000000, "fijo", transferencia
    )
    gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "unico")
    totales = gastos.totales_por_medio(con, mes_id)
    assert [(n, formatear_ars(t)) for n, t in totales] == [
        ("Mastercard Nación", "$ 131.000"),
        ("Transferencia", "$ 260.000"),
        ("Visa Santander", "$ 91.117"),
        ("Sin medio de pago", "$ 30.000"),
    ]


def test_total_por_medio_incluye_dolares_archivados_y_ordena_sin_acentos(
    con, mes_id, otros
):
    agil = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Ágil Pagos")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa")
    gastos.agregar_gasto(
        con, mes_id, "Claude", otros, None, "unico", visa, "USD", 2000, 160000
    )
    gastos.agregar_gasto(con, mes_id, "X", otros, 100, "fijo", agil)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, agil)  # archivado: igual se suma
    assert gastos.totales_por_medio(con, mes_id) == [
        ("Ágil Pagos", 100),
        ("Visa", 3200000),
    ]


def test_total_por_medio_mes_vacio_y_solo_sin_medio(con, mes_id, otros):
    assert gastos.totales_por_medio(con, mes_id) == []
    gastos.agregar_gasto(con, mes_id, "Nafta", otros, 100, "unico")
    assert gastos.totales_por_medio(con, mes_id) == [("Sin medio de pago", 100)]


# ---------------------------------------------------------------------------
# Borrar la cuota de un mes (RN-52, CA-08.2, CA-08.3)
# ---------------------------------------------------------------------------


@pytest.fixture
def caso_08(con, otros):
    """Plan de 6 cuotas de 10.000 desde 2026-08, con 2026-10 y 2026-11 creados."""
    ids = _meses(con, (2026, 10), (2026, 11))
    pid = _crear(con, otros)
    return ids, pid


def test_ca_08_2_borrar_la_cuota_de_un_mes(con, caso_08):
    ids, pid = caso_08
    gastos.borrar_gasto(con, _cuota(con, pid, ids[(2026, 11)])["id"])
    assert _cuota(con, pid, ids[(2026, 11)]) is None
    assert _cuota(con, pid, ids[(2026, 10)]) is not None
    assert _texto(con, pid, 2026, 10) == "3/6"
    assert cuotas.estado(cuotas.obtener_plan(con, pid), HOY) == cuotas.ACTIVO
    omitidas = con.execute(
        "SELECT plan_cuotas_id, anio, mes FROM cuotas_omitidas"
    ).fetchall()
    assert [tuple(f) for f in omitidas] == [(pid, 2026, 11)]
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, dic) is not None
    assert _texto(con, pid, 2026, 12) == "5/6"


def test_ca_08_3_la_omision_sobrevive_a_borrar_y_recrear_los_meses(con, caso_08):
    ids, pid = caso_08
    gastos.borrar_gasto(con, _cuota(con, pid, ids[(2026, 11)])["id"])
    dic = meses.crear_mes_siguiente(con, 120000, 160000)
    meses.borrar_ultimo_mes(con, dic)
    meses.borrar_ultimo_mes(con, ids[(2026, 11)])
    assert cantidad_filas(con, "cuotas_omitidas") == 1  # borrar meses no la borra
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    dic2 = meses.crear_mes_siguiente(con, 120000, 160000)
    assert _cuota(con, pid, nov) is None  # sigue omitida
    assert _cuota(con, pid, dic2) is not None
    assert _texto(con, pid, 2026, 12) == "5/6"


def test_borrar_un_gasto_que_no_es_cuota_no_registra_omision(con, mes_id, otros):
    gid = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 100, "unico")
    gastos.borrar_gasto(con, gid)
    assert cantidad_filas(con, "cuotas_omitidas") == 0


def test_borrar_una_cuota_con_pagos_borra_los_pagos_y_la_omite(con, caso_08):
    ids, pid = caso_08
    cuota = _cuota(con, pid, ids[(2026, 10)])["id"]
    pagos.marcar_pagado(con, cuota, HOY)
    gastos.borrar_gasto(con, cuota)
    assert cantidad_filas(con, "pagos") == 0
    assert cantidad_filas(con, "cuotas_omitidas") == 1


def test_borrar_dos_veces_la_misma_omision_no_falla(con, caso_08, otros):
    ids, pid = caso_08
    gastos.borrar_gasto(con, _cuota(con, pid, ids[(2026, 11)])["id"])
    # Si alguien la recreara a mano y la volviera a borrar, la omisión no se duplica.
    with con:
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Plan', ?, 1000000, 'cuota', ?)",
            (ids[(2026, 11)], otros, pid),
        )
    gastos.borrar_gasto(con, _cuota(con, pid, ids[(2026, 11)])["id"])
    assert cantidad_filas(con, "cuotas_omitidas") == 1


def test_activo_en_respeta_la_omision(con, caso_08):
    ids, pid = caso_08
    plan = cuotas.obtener_plan(con, pid)
    assert cuotas.activo_en(con, plan, 2026, 11) is True
    gastos.borrar_gasto(con, _cuota(con, pid, ids[(2026, 11)])["id"])
    assert cuotas.activo_en(con, plan, 2026, 11) is False
    assert cuotas.activo_en(con, plan, 2026, 12) is True
    assert cuotas.activo_en(con, plan, 2027, 2) is False  # después de la última


# ---------------------------------------------------------------------------
# Capacidad con planes creados por la función (CA-37.x)
# ---------------------------------------------------------------------------


@pytest.fixture
def caso_37(con, mes_id, otros):
    gastos.agregar_gasto(con, mes_id, "Fijos", otros, 78530000, "fijo")
    cuotas.crear_plan(con, "Avant Service", otros, None, 4111700, 3, 2026, 8, hoy=HOY)
    gastos.agregar_gasto(con, mes_id, "Regalo", otros, 1500000, "unico")
    configuracion.guardar_meta(con, 30000)
    return mes_id


def test_ca_37_1_capacidad_con_cuota_creada_por_el_plan(con, caso_37):
    r = calcular_resumen(con, caso_37)
    assert r.gastos_fijos_y_cuotas == 78530000 + 4111700
    assert formatear_ars(r.capacidad) == "$ 613.583"


def test_ca_37_2_a_37_4(con, caso_37):
    configuracion.quitar_meta(con)
    assert formatear_ars(calcular_resumen(con, caso_37).capacidad) == "$ 1.093.583"
    configuracion.guardar_meta(con, 100000)
    assert formatear_ars(calcular_resumen(con, caso_37).capacidad) == "-$ 506.417"
    configuracion.guardar_meta(con, 30000)
    meses.editar_cotizacion(con, caso_37, 170000)
    assert formatear_ars(calcular_resumen(con, caso_37).capacidad) == "$ 703.583"


def test_capacidad_sin_la_cuota_si_se_cancela_el_plan(con, caso_37):
    pid = con.execute("SELECT id FROM planes_cuotas").fetchone()["id"]
    cuotas.cancelar_plan(con, pid, hoy=HOY)
    r = calcular_resumen(con, caso_37)
    assert r.gastos_fijos_y_cuotas == 78530000
