"""Pruebas de la lógica de gastos compartidos y "me deben" (paso 5a): RF-28 a RF-34,
RN-32 a RN-37, RN-40. Criterios CA-28.x (lógica), CA-29.x a CA-34.x, CA-35.2, CA-05.2,
CA-43.6 (partes), CA-45.7 y CA-47.6 a CA-47.8. Base en memoria, datos inventados y
fechas fijas."""

import dataclasses
from datetime import date, datetime

import pytest

from app.logica import catalogos, compartidos, cuotas, gastos, me_deben, meses, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT, formatear_ars
from app.logica.resumen import calcular_resumen
from tests.ayudantes import cantidad_filas, id_por_nombre

HOY = date(2026, 10, 4)


@pytest.fixture
def otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


@pytest.fixture
def sofia(con):
    return catalogos.crear(con, catalogos.PERSONAS, "Sofía")


@pytest.fixture
def marsu(con):
    return catalogos.crear(con, catalogos.PERSONAS, "Marsu")


def _gasto(con, mes_id, otros, nombre, monto, partes, tipo="fijo"):
    return gastos.agregar_gasto(con, mes_id, nombre, otros, monto, tipo, partes=partes)


def _partes(con, gasto_id):
    """{nombre de la persona: (monto, manual, cobrado, cobrado_cent)}."""
    return {
        p["persona"]: (
            p["monto_cent"],
            bool(p["editada_a_mano"]),
            bool(p["cobrado"]),
            p["cobrado_cent"],
        )
        for p in compartidos.obtener_partes(con, gasto_id)
    }


def _usuario(con, gasto_id):
    return compartidos.parte_del_usuario(
        con, gasto_id, gastos.obtener_gasto(con, gasto_id)["monto_cent"]
    )


def _editar_monto(con, gasto_id, otros, monto, partes=None, tipo="fijo"):
    g = gastos.obtener_gasto(con, gasto_id)
    gastos.editar_gasto(con, gasto_id, g["nombre"], otros, monto, tipo, partes=partes)


def _parte_id(con, gasto_id, persona_id):
    return con.execute(
        "SELECT id FROM partes_gasto WHERE gasto_id = ? AND persona_id = ?",
        (gasto_id, persona_id),
    ).fetchone()["id"]


# ---------------------------------------------------------------------------
# Funciones puras (RN-32, RN-33)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("monto", "personas", "parte"),
    [
        (3870000, 2, 1290000),  # Internet 38.700 entre 3
        (6628100, 2, 2209366),  # Edenor 66.281 entre 3 (trunca)
        (3870000, 1, 1935000),  # solo con Sofía: 19.350
        (100, 2, 33),
        (1, 1, 0),
        (0, 3, 0),
    ],
)
def test_parte_igual(monto, personas, parte):
    assert compartidos.parte_igual(monto, personas) == parte


def test_calcular_partes_automaticas_y_manuales():
    assert compartidos.calcular_partes(3870000, [(1, None), (2, None)]) == {
        1: (1290000, False),
        2: (1290000, False),
    }
    assert compartidos.calcular_partes(3870000, [(1, 1500000), (2, None)]) == {
        1: (1500000, True),
        2: (1290000, False),
    }


def test_calcular_partes_manual_en_cero_se_acepta():
    assert compartidos.calcular_partes(3870000, [(1, 0), (2, None)]) == {
        1: (0, True),
        2: (1290000, False),
    }


def test_calcular_partes_que_suman_justo_el_monto():
    # La parte del usuario puede quedar en 0.
    assert compartidos.calcular_partes(1000, [(1, 600), (2, 400)]) == {
        1: (600, True),
        2: (400, True),
    }


def test_calcular_partes_que_superan_el_monto():
    with pytest.raises(ErrorDeValidacion) as error:
        compartidos.calcular_partes(3870000, [(1, 3000000), (2, None)])
    assert (
        str(error.value) == "Las partes suman $ 42.900 y superan el monto ($ 38.700)."
    )
    assert error.value.campo == "partes"


@pytest.mark.parametrize(
    ("manual", "mensaje"),
    [
        (-1, "La parte no puede ser negativa."),
        (1.5, "La parte tiene que ser un número entero de centavos."),
        (True, "La parte tiene que ser un número entero de centavos."),
        (MONTO_MAXIMO_CENT + 1, "La parte es demasiado grande."),
    ],
)
def test_calcular_partes_manual_invalida(manual, mensaje):
    with pytest.raises(ErrorDeValidacion) as error:
        compartidos.calcular_partes(3870000, [(1, manual)])
    assert (str(error.value), error.value.campo) == (mensaje, "partes")


# ---------------------------------------------------------------------------
# Personas (RF-28, CA-28.x en la lógica)
# ---------------------------------------------------------------------------


def test_la_app_no_carga_personas_iniciales(con):
    assert cantidad_filas(con, "personas") == 0


def test_ca_28_1_persona_sin_uso_se_borra_y_con_uso_se_archiva(
    con, mes_id, otros, sofia, marsu
):
    catalogos.renombrar(con, catalogos.PERSONAS, marsu, "Marsu G.")
    assert catalogos.eliminar(con, catalogos.PERSONAS, marsu) == "borrado"
    _gasto(con, mes_id, otros, "Internet", 3870000, [(sofia, None)])
    assert catalogos.eliminar(con, catalogos.PERSONAS, sofia) == "archivado"
    # Archivada: no se ofrece para compartidos nuevos…
    with pytest.raises(ErrorDeValidacion) as error:
        _gasto(con, mes_id, otros, "Luz", 1000000, [(sofia, None)])
    assert (
        str(error.value)
        == "La persona Sofía está archivada: desarchivala para compartir gastos."
    )
    assert error.value.campo == "compartido"
    # …pero sigue en "me deben".
    assert me_deben.total_de(con, sofia) == 1935000
    assert sofia in [p["id"] for p in me_deben.personas_para_mostrar(con)]


def test_ca_28_1_persona_solo_con_items_tambien_se_archiva(con, sofia):
    item = me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    me_deben.marcar_item_cobrado(con, item, True)  # aunque esté cobrado
    assert catalogos.eliminar(con, catalogos.PERSONAS, sofia) == "archivado"


def test_ca_28_2_desarchivar_vuelve_a_ofrecerse(con, mes_id, otros, sofia):
    _gasto(con, mes_id, otros, "Internet", 3870000, [(sofia, None)])
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    catalogos.desarchivar(con, catalogos.PERSONAS, sofia)
    gid = _gasto(con, mes_id, otros, "Luz", 1000000, [(sofia, None)])
    assert _partes(con, gid)["Sofía"][0] == 500000


def test_editar_un_gasto_que_ya_tenia_a_la_persona_archivada(
    con, mes_id, otros, sofia, marsu
):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    _editar_monto(
        con, gid, otros, 4500000
    )  # partes=None: mantiene a Sofía aunque esté archivada
    assert _partes(con, gid)["Sofía"][0] == 1500000
    gastos.editar_gasto(
        con,
        gid,
        "Internet",
        otros,
        4500000,
        "fijo",
        partes=[(sofia, None), (marsu, None)],
    )
    assert len(_partes(con, gid)) == 2


@pytest.mark.parametrize(
    ("caso", "mensaje"),
    [
        ("repetida", "Una persona aparece dos veces."),
        ("inexistente", "Una de las personas elegidas ya no existe."),
        ("ninguna", "Una de las personas elegidas ya no existe."),
    ],
)
def test_validar_personas(con, mes_id, otros, sofia, caso, mensaje):
    personas = {
        "repetida": [(sofia, None), (sofia, 100)],
        "inexistente": [(sofia, None), (999, None)],
        "ninguna": [(None, None)],
    }[caso]
    with pytest.raises(ErrorDeValidacion) as error:
        _gasto(con, mes_id, otros, "Internet", 3870000, personas)
    assert (str(error.value), error.value.campo) == (mensaje, "compartido")
    assert cantidad_filas(con, "gastos") == 0
    assert cantidad_filas(con, "partes_gasto") == 0


# ---------------------------------------------------------------------------
# Alta compartida (RF-29, RF-30, CA-29.x, CA-30.x)
# ---------------------------------------------------------------------------


def test_ca_29_1_internet_entre_tres(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    assert _partes(con, gid) == {
        "Sofía": (1290000, False, False, 0),
        "Marsu": (1290000, False, False, 0),
    }
    assert _usuario(con, gid) == 1290000


def test_ca_29_2_edenor_con_centavos(con, mes_id, otros, sofia, marsu):
    gid = _gasto(con, mes_id, otros, "Edenor", 6628100, [(sofia, None), (marsu, None)])
    partes = _partes(con, gid)
    assert (partes["Sofía"][0], partes["Marsu"][0], _usuario(con, gid)) == (
        2209366,
        2209366,
        2209368,
    )
    assert partes["Sofía"][0] + partes["Marsu"][0] + _usuario(con, gid) == 6628100
    assert {formatear_ars(m) for m in (2209366, 2209368)} == {"$ 22.094"}


def test_ca_29_3_solo_con_sofia(con, mes_id, otros, sofia):
    gid = _gasto(con, mes_id, otros, "Internet", 3870000, [(sofia, None)])
    assert (_partes(con, gid)["Sofía"][0], _usuario(con, gid)) == (1935000, 1935000)


def test_ca_29_4_el_total_incluye_el_gasto_completo(con, mes_id, otros, sofia, marsu):
    _gasto(con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)])
    assert gastos.total_gastos(con, mes_id) == 3870000
    assert calcular_resumen(con, mes_id).total_gastos == 3870000


def test_ca_30_1_parte_manual(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, 1500000), (marsu, None)]
    )
    assert _partes(con, gid) == {
        "Sofía": (1500000, True, False, 0),
        "Marsu": (1290000, False, False, 0),
    }
    assert _usuario(con, gid) == 1080000


def test_ca_30_2_parte_manual_que_deja_negativo_al_usuario(
    con, mes_id, otros, sofia, marsu
):
    with pytest.raises(ErrorDeValidacion) as error:
        _gasto(
            con, mes_id, otros, "Internet", 3870000, [(sofia, 3000000), (marsu, None)]
        )
    assert (
        str(error.value) == "Las partes suman $ 42.900 y superan el monto ($ 38.700)."
    )
    assert error.value.campo == "partes"
    assert (
        cantidad_filas(con, "gastos") == 0
    )  # atomicidad: no queda el gasto sin partes


def test_editar_a_un_reparto_invalido_no_cambia_nada(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    with pytest.raises(ErrorDeValidacion):
        gastos.editar_gasto(
            con,
            gid,
            "Internet 2",
            otros,
            3870000,
            "fijo",
            partes=[(sofia, 3000000), (marsu, None)],
        )
    assert gastos.obtener_gasto(con, gid)["nombre"] == "Internet"
    assert _partes(con, gid)["Sofía"] == (1290000, False, False, 0)


def test_gasto_en_dolares_compartido_ca_43_6(con, mes_id, otros, sofia, marsu):
    # CA-43.6: Netflix fijo US$ 15,00 × 1.600 = 24.000 entre 3: 8.000 cada uno.
    gid = gastos.agregar_gasto(
        con,
        mes_id,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, None), (marsu, None)],
    )
    assert (
        _partes(con, gid)["Sofía"][0],
        _partes(con, gid)["Marsu"][0],
        _usuario(con, gid),
    ) == (
        800000,
        800000,
        800000,
    )


def test_las_cuotas_no_se_pueden_compartir(con, mes_id, otros, sofia):
    with pytest.raises(ErrorDeValidacion) as error:
        _gasto(con, mes_id, otros, "Heladera", 1000000, [(sofia, None)], tipo="cuota")
    # El tipo "cuota" ya se rechaza en el alta; y validar_personas también lo rechaza.
    assert error.value.campo in ("tipo", "compartido")
    with pytest.raises(ErrorDeValidacion) as error:
        compartidos.validar_personas(con, [(sofia, None)], None, "cuota")
    assert (str(error.value), error.value.campo) == (
        "Las cuotas no se pueden compartir.",
        "compartido",
    )


def test_una_cuota_existente_no_se_puede_compartir_al_editar(con, mes_id, otros, sofia):
    pid = cuotas.crear_plan(con, "Heladera", otros, None, 1000000, 6, 2026, 8, hoy=HOY)
    cuota = con.execute(
        "SELECT id FROM gastos WHERE plan_cuotas_id = ?", (pid,)
    ).fetchone()["id"]
    with pytest.raises(ErrorDeValidacion):
        gastos.editar_gasto(
            con, cuota, "Heladera", otros, 1000000, "cuota", partes=[(sofia, None)]
        )
    assert cantidad_filas(con, "partes_gasto") == 0


def test_dejar_de_compartir(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    gastos.editar_gasto(con, gid, "Internet", otros, 3870000, "fijo", partes=[])
    assert compartidos.obtener_partes(con, gid) == []
    assert _usuario(con, gid) == 3870000


def test_compartir_un_gasto_que_no_lo_era(con, mes_id, otros, sofia):
    gid = _gasto(con, mes_id, otros, "Internet", 3870000, None)
    assert compartidos.obtener_partes(con, gid) == []
    gastos.editar_gasto(
        con, gid, "Internet", otros, 3870000, "fijo", partes=[(sofia, None)]
    )
    assert _partes(con, gid)["Sofía"][0] == 1935000


def test_borrar_un_gasto_compartido_borra_sus_partes(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    gastos.borrar_gasto(con, gid)
    assert cantidad_filas(con, "partes_gasto") == 0
    assert me_deben.total_de(con, sofia) == 0


# ---------------------------------------------------------------------------
# Cambio de monto (RF-31, RN-34, CA-31.x, CA-45.7)
# ---------------------------------------------------------------------------


@pytest.fixture
def internet(con, mes_id, otros, sofia, marsu):
    return _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )


def test_ca_31_1_monto_nuevo_sin_manuales(con, otros, internet):
    _editar_monto(con, internet, otros, 4500000)
    assert {n: p[0] for n, p in _partes(con, internet).items()} == {
        "Sofía": 1500000,
        "Marsu": 1500000,
    }
    assert _usuario(con, internet) == 1500000


def test_ca_31_2_con_sofia_manual(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, 1500000), (marsu, None)]
    )
    _editar_monto(con, gid, otros, 4500000)
    assert ({n: p[0] for n, p in _partes(con, gid).items()}, _usuario(con, gid)) == (
        {"Sofía": 1500000, "Marsu": 1500000},
        1500000,
    )
    _editar_monto(con, gid, otros, 3000000)
    assert ({n: p[0] for n, p in _partes(con, gid).items()}, _usuario(con, gid)) == (
        {"Sofía": 1500000, "Marsu": 1000000},
        500000,
    )


def test_ca_31_3_monto_que_deja_negativo_al_usuario_se_rechaza(
    con, mes_id, otros, sofia, marsu
):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, 1500000), (marsu, None)]
    )
    with pytest.raises(ErrorDeValidacion) as error:
        _editar_monto(con, gid, otros, 2000000)
    assert error.value.campo == "partes"
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3870000
    assert _partes(con, gid)["Marsu"][0] == 1290000


def test_ca_31_4_parte_cobrada_que_sube(con, otros, sofia, internet):
    compartidos.marcar_cobrada(con, _parte_id(con, internet, sofia), True)
    _editar_monto(con, internet, otros, 4500000)
    assert _partes(con, internet)["Sofía"] == (1500000, False, False, 1290000)
    [linea] = me_deben.lineas_de(con, sofia)
    assert (linea.monto, linea.cobrado, linea.cobrado_cent, linea.pendiente) == (
        1500000,
        False,
        1290000,
        210000,
    )
    assert me_deben.total_de(con, sofia) == 210000  # "cobrado 12.900, falta 2.100"


def test_ca_31_5_parte_cobrada_que_baja(con, otros, sofia, internet):
    compartidos.marcar_cobrada(con, _parte_id(con, internet, sofia), True)
    _editar_monto(con, internet, otros, 3000000)
    [linea] = me_deben.lineas_de(con, sofia)
    assert (linea.monto, linea.cobrado, linea.cobrado_cent, linea.pendiente) == (
        1000000,
        False,
        1290000,
        -290000,
    )
    assert me_deben.total_de(con, sofia) == -290000  # "a devolver 2.900"


def test_ca_31_6_parte_manual_cobrada_no_cambia(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, 1500000), (marsu, None)]
    )
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    _editar_monto(con, gid, otros, 4500000)
    assert _partes(con, gid)["Sofía"] == (1500000, True, True, 1500000)
    assert me_deben.total_de(con, sofia) == 0


def test_ca_31_7_volver_a_marcar_cobra_la_parte_nueva(con, otros, sofia, internet):
    pid = _parte_id(con, internet, sofia)
    compartidos.marcar_cobrada(con, pid, True)
    _editar_monto(con, internet, otros, 4500000)
    compartidos.marcar_cobrada(con, pid, True)
    assert _partes(con, internet)["Sofía"] == (1500000, False, True, 1500000)
    assert me_deben.total_de(con, sofia) == 0


def test_cambiar_otra_cosa_que_no_es_el_monto_no_descobra(con, otros, sofia, internet):
    compartidos.marcar_cobrada(con, _parte_id(con, internet, sofia), True)
    gastos.editar_gasto(con, internet, "Internet Fibra", otros, 3870000, "unico")
    assert _partes(con, internet)["Sofía"][2] is True


def test_ca_45_7_gasto_en_dolares_que_cambia_de_cotizacion(
    con, mes_id, otros, sofia, marsu
):
    # Netflix US$ 15 × 1.600 = 24.000 entre 3, con la parte de Sofía (8.000) cobrada.
    gid = gastos.agregar_gasto(
        con,
        mes_id,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, None), (marsu, None)],
    )
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    gastos.editar_gasto(
        con, gid, "Netflix", otros, None, "fijo", None, "USD", 1500, 170000
    )
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 2550000
    partes = _partes(con, gid)
    assert partes["Marsu"] == (850000, False, False, 0)
    assert partes["Sofía"] == (850000, False, False, 800000)  # cobrado 8.000, falta 500
    assert me_deben.total_de(con, sofia) == 50000


def test_cambiar_de_moneda_tambien_recalcula(con, mes_id, otros, sofia, marsu):
    gid = _gasto(con, mes_id, otros, "Netflix", 2400000, [(sofia, None), (marsu, None)])
    gastos.editar_gasto(
        con, gid, "Netflix", otros, None, "fijo", None, "USD", 1500, 170000
    )
    assert _partes(con, gid)["Sofía"][0] == 850000


def test_quitar_y_agregar_personas_con_partes_cobradas(
    con, mes_id, otros, sofia, marsu
):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    pepe = catalogos.crear(con, catalogos.PERSONAS, "Pepe")
    # Se agrega Pepe: las automáticas pasan a 9.675; la de Sofía cambió → pendiente.
    gastos.editar_gasto(
        con,
        gid,
        "Internet",
        otros,
        3870000,
        "fijo",
        partes=[(sofia, None), (marsu, None), (pepe, None)],
    )
    partes = _partes(con, gid)
    assert partes["Sofía"] == (967500, False, False, 1290000)
    assert partes["Pepe"] == (967500, False, False, 0)
    assert me_deben.total_de(con, sofia) == -322500  # a devolver 3.225
    # Se quita a Sofía: su parte (y lo que tenía cobrado) desaparece de "me deben".
    gastos.editar_gasto(
        con,
        gid,
        "Internet",
        otros,
        3870000,
        "fijo",
        partes=[(marsu, None), (pepe, None)],
    )
    assert set(_partes(con, gid)) == {"Marsu", "Pepe"}
    assert me_deben.lineas_de(con, sofia, incluir_cobradas=True) == []


def test_marcar_y_desmarcar_una_parte(con, sofia, internet):
    pid = _parte_id(con, internet, sofia)
    compartidos.marcar_cobrada(con, pid, True)
    assert _partes(con, internet)["Sofía"] == (1290000, False, True, 1290000)
    compartidos.marcar_cobrada(con, pid, False)
    assert _partes(con, internet)["Sofía"] == (1290000, False, False, 0)
    with pytest.raises(ErrorDeValidacion, match="^Esa parte ya no existe.$"):
        compartidos.marcar_cobrada(con, 999, True)


def test_personas_actuales_y_obtener_partes(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, 1500000), (marsu, None)]
    )
    assert compartidos.personas_actuales(con, gid) == [(sofia, 1500000), (marsu, None)]
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    fila = compartidos.obtener_partes(con, gid)[0]
    assert (fila["persona"], fila["persona_archivada"]) == ("Sofía", 1)


# ---------------------------------------------------------------------------
# Ítems a mano (RF-32, CA-32.x)
# ---------------------------------------------------------------------------


def test_ca_32_1_cargar_un_item(con, sofia):
    iid = me_deben.agregar_item(con, sofia, "  Préstamo   MP ", 2000000, HOY)
    item = me_deben.obtener_item(con, iid)
    assert (
        item["descripcion"],
        item["monto_cent"],
        item["fecha"],
        item["cobrado"],
    ) == (
        "Préstamo MP",
        2000000,
        "2026-10-04",
        0,
    )
    [linea] = me_deben.lineas_de(con, sofia)
    assert (
        linea.tipo,
        linea.descripcion,
        linea.cobrado,
        linea.pendiente,
        linea.fecha,
    ) == (
        "item",
        "Préstamo MP",
        False,
        2000000,
        "2026-10-04",
    )


@pytest.mark.parametrize(
    ("persona", "descripcion", "monto", "campo", "mensaje"),
    [
        (
            "sofia",
            "Préstamo",
            0,
            "monto",
            "El monto tiene que ser mayor a 0.",
        ),  # CA-32.2
        ("sofia", "Préstamo", -100, "monto", "El monto tiene que ser mayor a 0."),
        ("sofia", "   ", 100, "descripcion", "Ingresá una descripción."),  # CA-32.2
        ("sofia", None, 100, "descripcion", "Ingresá una descripción."),
        (
            "sofia",
            "Préstamo",
            1.5,
            "monto",
            "El monto tiene que ser un número entero de centavos.",
        ),
        (None, "Préstamo", 100, "persona", "Elegí una persona."),
        (999, "Préstamo", 100, "persona", "Esa persona ya no existe."),
    ],
)
def test_ca_32_2_item_invalido(con, sofia, persona, descripcion, monto, campo, mensaje):
    persona_id = sofia if persona == "sofia" else persona
    with pytest.raises(ErrorDeValidacion) as error:
        me_deben.agregar_item(con, persona_id, descripcion, monto, HOY)
    assert (str(error.value), error.value.campo) == (mensaje, campo)
    assert cantidad_filas(con, "items_me_deben") == 0


def test_item_a_una_persona_archivada_se_rechaza(con, sofia):
    me_deben.agregar_item(con, sofia, "Préstamo", 100, HOY)
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    with pytest.raises(ErrorDeValidacion) as error:
        me_deben.agregar_item(con, sofia, "Otro", 100, HOY)
    assert (str(error.value), error.value.campo) == (
        "La persona Sofía está archivada.",
        "persona",
    )


def test_editar_y_borrar_items(con, sofia, marsu):
    iid = me_deben.agregar_item(con, sofia, "Préstamo", 2000000, HOY)
    me_deben.editar_item(con, iid, sofia, "Préstamo MP", 2500000)  # sin fecha: conserva
    item = me_deben.obtener_item(con, iid)
    assert (item["descripcion"], item["monto_cent"], item["fecha"]) == (
        "Préstamo MP",
        2500000,
        "2026-10-04",
    )
    me_deben.editar_item(
        con,
        iid,
        marsu,
        "Préstamo MP",
        2500000,
        datetime(2026, 9, 1, 18, 0),  # noqa: DTZ001
    )
    item = me_deben.obtener_item(con, iid)
    assert (item["persona_id"], item["fecha"]) == (
        marsu,
        "2026-09-01",
    )  # datetime → solo el día
    with pytest.raises(ErrorDeValidacion):
        me_deben.editar_item(con, iid, marsu, "", 2500000)
    me_deben.borrar_item(con, iid)
    assert me_deben.obtener_item(con, iid) is None
    for accion in (
        lambda: me_deben.borrar_item(con, iid),
        lambda: me_deben.editar_item(con, iid, sofia, "X", 100),
        lambda: me_deben.marcar_item_cobrado(con, iid, True),
    ):
        with pytest.raises(ErrorDeValidacion, match="^Ese ítem ya no existe.$"):
            accion()


def test_editar_item_de_una_persona_archivada_que_ya_tenia(con, sofia):
    iid = me_deben.agregar_item(con, sofia, "Préstamo", 100, HOY)
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    me_deben.editar_item(con, iid, sofia, "Préstamo MP", 200)
    assert me_deben.obtener_item(con, iid)["monto_cent"] == 200


def test_fecha_del_item_con_datetime_y_por_defecto(con, sofia, monkeypatch):
    iid = me_deben.agregar_item(con, sofia, "A", 100, datetime(2026, 10, 4, 23, 59))  # noqa: DTZ001
    assert me_deben.obtener_item(con, iid)["fecha"] == "2026-10-04"

    class FechaFija(date):
        @classmethod
        def today(cls):
            return cls(2026, 12, 31)

    monkeypatch.setattr(me_deben, "date", FechaFija)
    iid = me_deben.agregar_item(con, sofia, "B", 100)
    assert me_deben.obtener_item(con, iid)["fecha"] == "2026-12-31"


# ---------------------------------------------------------------------------
# Lista y totales (RF-33, RF-34, RN-35, RN-40, CA-33.x, CA-34.x, CA-35.2)
# ---------------------------------------------------------------------------


def test_ca_33_1_total_de_sofia(con, sofia, internet):
    me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    assert me_deben.total_de(con, sofia) == 3290000
    lineas = me_deben.lineas_de(con, sofia)
    assert [
        (linea.tipo, linea.descripcion, linea.anio, linea.mes) for linea in lineas
    ] == [
        ("parte", "Internet", 2026, 10),
        ("item", "Préstamo MP", None, None),
    ]


def test_ca_33_2_y_34_3_internet_en_dos_meses(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, 1500000)]
    )
    me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    compartidos.marcar_cobrada(con, _parte_id(con, gid, marsu), True)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    copia = gastos.listar_gastos(con, nov)[0]["id"]
    # CA-34.3: copiadas como no cobradas; la manual con su valor.
    assert _partes(con, copia) == {
        "Sofía": (1290000, False, False, 0),
        "Marsu": (1500000, True, False, 0),
    }
    # CA-33.2: la lista de Sofía muestra los dos meses y su total pasa a 45.800.
    lineas = me_deben.lineas_de(con, sofia)
    assert [(linea.descripcion, linea.anio, linea.mes) for linea in lineas] == [
        ("Internet", 2026, 10),
        ("Internet", 2026, 11),
        ("Préstamo MP", None, None),
    ]
    assert me_deben.total_de(con, sofia) == 4580000


def test_ca_34_1_marcar_y_desmarcar_un_item(con, sofia, internet):
    iid = me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    me_deben.marcar_item_cobrado(con, iid, True)
    assert me_deben.total_de(con, sofia) == 1290000
    assert [linea.tipo for linea in me_deben.lineas_de(con, sofia)] == ["parte"]
    assert len(me_deben.lineas_de(con, sofia, incluir_cobradas=True)) == 2
    me_deben.marcar_item_cobrado(con, iid, False)
    assert me_deben.total_de(con, sofia) == 3290000


def test_ca_34_2_rn_36_me_deben_no_cambia_el_resumen(con, mes_id, otros, sofia, marsu):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    antes = calcular_resumen(con, mes_id)
    iid = me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    me_deben.marcar_item_cobrado(con, iid, True)
    despues = calcular_resumen(con, mes_id)
    sin_me_deben = dataclasses.replace(despues, total_me_deben=antes.total_me_deben)
    assert (
        sin_me_deben == antes
    )  # G, pesos a cubrir, dólares a cambiar y ahorro iguales
    assert (antes.total_gastos, antes.pesos_a_cubrir) == (3870000, 3870000)


def test_ca_35_2_total_general_igual_en_todos_los_meses(con, otros, sofia, marsu):
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    _gasto(con, sep, otros, "Internet", 3870000, [(sofia, None), (marsu, None)])
    me_deben.agregar_item(con, marsu, "Tacones", 678500, HOY)
    total = me_deben.total_de(con, sofia) + me_deben.total_de(con, marsu)
    assert me_deben.total_general(con) == total == 1290000 + 1290000 + 678500
    assert (
        calcular_resumen(con, sep).total_me_deben
        == calcular_resumen(con, oct_).total_me_deben
        == total
    )


def test_total_general_incluye_personas_archivadas_y_negativos(
    con, mes_id, otros, sofia, marsu
):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    _editar_monto(con, gid, otros, 3000000)  # Sofía: a devolver 2.900; Marsu: 10.000
    catalogos.eliminar(con, catalogos.PERSONAS, marsu)  # archivada, igual cuenta
    assert me_deben.total_general(con) == -290000 + 1000000


def test_lineas_ordenadas_partes_por_mes_e_items_por_fecha(con, otros, sofia):
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    _gasto(con, oct_, otros, "B octubre", 100, [(sofia, None)], tipo="unico")
    _gasto(con, sep, otros, "A septiembre", 100, [(sofia, None)], tipo="unico")
    me_deben.agregar_item(con, sofia, "Item nuevo", 100, date(2026, 10, 20))
    me_deben.agregar_item(con, sofia, "Item viejo", 100, date(2026, 1, 2))
    assert [linea.descripcion for linea in me_deben.lineas_de(con, sofia)] == [
        "A septiembre",
        "B octubre",
        "Item viejo",
        "Item nuevo",
    ]


def test_persona_sin_nada_tiene_total_cero(con, sofia):
    assert me_deben.lineas_de(con, sofia) == []
    assert me_deben.total_de(con, sofia) == 0
    assert me_deben.total_general(con) == 0


def test_personas_para_mostrar(con, mes_id, otros, sofia, marsu):
    pepe = catalogos.crear(con, catalogos.PERSONAS, "Pepe")
    agus = catalogos.crear(con, catalogos.PERSONAS, "Ágata")
    # Marsu archivada con algo pendiente: se muestra. Pepe archivado sin nada pendiente: no.
    _gasto(con, mes_id, otros, "Internet", 3870000, [(marsu, None)])
    iid = me_deben.agregar_item(con, pepe, "Ya cobrado", 100, HOY)
    me_deben.marcar_item_cobrado(con, iid, True)
    catalogos.eliminar(con, catalogos.PERSONAS, marsu)
    catalogos.eliminar(con, catalogos.PERSONAS, pepe)
    nombres = [p["nombre"] for p in me_deben.personas_para_mostrar(con)]
    assert nombres == ["Ágata", "Marsu", "Sofía"]
    assert agus


def test_linea_es_inmutable(con, sofia):
    me_deben.agregar_item(con, sofia, "Préstamo", 100, HOY)
    [linea] = me_deben.lineas_de(con, sofia)
    with pytest.raises(dataclasses.FrozenInstanceError):
        linea.monto = 0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Meses: copia (RN-37, CA-47.6 a 47.8) y borrar (CA-05.2)
# ---------------------------------------------------------------------------


@pytest.fixture
def netflix(con, mes_id, otros, sofia, marsu):
    """Netflix fijo US$ 15,00 × 1.600 = 24.000 entre Sofía, Marsu y el usuario."""
    return gastos.agregar_gasto(
        con,
        mes_id,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, None), (marsu, None)],
    )


def _copia_de_netflix(con, mes_id):
    return next(
        g for g in gastos.listar_gastos(con, mes_id) if g["nombre"] == "Netflix"
    )["id"]


def test_ca_47_6_partes_automaticas_al_mes_nuevo(con, mes_id, sofia, netflix):
    compartidos.marcar_cobrada(con, _parte_id(con, netflix, sofia), True)
    avisos = []
    nov = meses.crear_mes(con, 2026, 11, 120000, 170000, avisos=avisos)
    copia = _copia_de_netflix(con, nov)
    assert gastos.obtener_gasto(con, copia)["monto_cent"] == 2550000
    assert _partes(con, copia) == {
        "Sofía": (850000, False, False, 0),
        "Marsu": (850000, False, False, 0),
    }
    assert avisos == []


def test_ca_47_7_partes_manuales_que_entran(con, mes_id, otros, sofia, marsu, netflix):
    gastos.editar_gasto(
        con,
        netflix,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, 1200000), (marsu, 1000000)],
    )
    avisos = []
    nov = meses.crear_mes(con, 2026, 11, 120000, 150000, avisos=avisos)
    copia = _copia_de_netflix(con, nov)
    assert gastos.obtener_gasto(con, copia)["monto_cent"] == 2250000
    assert _partes(con, copia) == {
        "Sofía": (1200000, True, False, 0),
        "Marsu": (1000000, True, False, 0),
    }
    assert _usuario(con, copia) == 50000
    assert avisos == []


def test_ca_47_8_partes_manuales_que_no_entran(
    con, mes_id, otros, sofia, marsu, netflix
):
    gastos.editar_gasto(
        con,
        netflix,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, 1200000), (marsu, 1000000)],
    )
    avisos = []
    nov = meses.crear_mes(con, 2026, 11, 120000, 140000, avisos=avisos)
    copia = _copia_de_netflix(con, nov)
    assert gastos.obtener_gasto(con, copia)["monto_cent"] == 2100000
    assert _partes(con, copia) == {
        "Sofía": (700000, False, False, 0),
        "Marsu": (700000, False, False, 0),
    }
    assert _usuario(con, copia) == 700000
    assert avisos == [
        "Las partes de Netflix se repartieron en partes iguales porque cambió el monto."
    ]
    # Las partes de octubre siguen siendo 12.000 / 10.000 / 2.000.
    assert {n: p[0] for n, p in _partes(con, netflix).items()} == {
        "Sofía": 1200000,
        "Marsu": 1000000,
    }
    assert _usuario(con, netflix) == 200000


def test_ca_47_8_sin_lista_de_avisos_igual_crea_el_mes(
    con, mes_id, otros, sofia, marsu, netflix
):
    gastos.editar_gasto(
        con,
        netflix,
        "Netflix",
        otros,
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, 1200000), (marsu, 1000000)],
    )
    nov = meses.crear_mes(con, 2026, 11, 120000, 140000)  # sin avisos
    assert _partes(con, _copia_de_netflix(con, nov))["Sofía"][0] == 700000


def test_copia_de_un_fijo_en_pesos_con_persona_archivada(
    con, mes_id, otros, sofia, marsu
):
    gid = _gasto(
        con, mes_id, otros, "Internet", 3870000, [(sofia, None), (marsu, None)]
    )
    catalogos.eliminar(
        con, catalogos.PERSONAS, sofia
    )  # archivada: igual se copia (RN-09)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    copia = gastos.listar_gastos(con, nov)[0]["id"]
    assert set(_partes(con, copia)) == {"Sofía", "Marsu"}
    assert gid


def test_unicos_compartidos_no_se_copian(con, mes_id, otros, sofia):
    _gasto(con, mes_id, otros, "Regalo", 1000000, [(sofia, None)], tipo="unico")
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    assert gastos.listar_gastos(con, nov) == []
    assert me_deben.total_de(con, sofia) == 500000


def test_ca_05_2_borrar_el_mes_borra_sus_partes_pero_no_los_items(con, otros, sofia):
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    _gasto(
        con,
        oct_,
        otros,
        "Internet",
        3870000,
        [(sofia, None), (catalogos.crear(con, catalogos.PERSONAS, "Marsu"), None)],
    )
    me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    assert me_deben.total_de(con, sofia) == 3290000
    meses.borrar_ultimo_mes(con, oct_)
    lineas = me_deben.lineas_de(con, sofia, incluir_cobradas=True)
    assert [(linea.tipo, linea.descripcion) for linea in lineas] == [
        ("item", "Préstamo MP")
    ]
    assert me_deben.total_de(con, sofia) == 2000000


def test_pagos_de_un_gasto_compartido_no_cambian_las_partes(
    con, mes_id, otros, sofia, internet
):
    # Pagar el gasto (lo paga el usuario) no tiene que ver con lo que le deben.
    pagos.marcar_pagado(con, internet, HOY)
    assert me_deben.total_de(con, sofia) == 1290000
