"""Pruebas de app/logica/gastos.py: alta, edición, baja, lista y total
(RF-06 a RF-09, RF-12; CA-06.x, CA-07.x, CA-08.1, CA-09.1, CA-09.2, CA-12.1)."""

import pytest

from app.logica import catalogos, gastos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT, formatear_ars, leer_monto
from tests.ayudantes import (
    cantidad_filas,
    id_por_nombre,
    insertar_mes,
    insertar_pago,
    insertar_plan,
)


@pytest.fixture
def transporte(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Transporte")


# ---------------------------------------------------------------------------
# RF-06: alta
# ---------------------------------------------------------------------------


def test_ca_06_1_alta_nafta_aparece_y_sube_el_total(con, mes_id, transporte):
    # CA-06.1: "Nafta", Transporte, 30.000, pago único: aparece y el total sube 30.000.
    antes = gastos.total_gastos(con, mes_id)
    gastos.agregar_gasto(
        con, mes_id, "Nafta", transporte, leer_monto("30.000"), "unico"
    )
    lista = gastos.listar_gastos(con, mes_id)
    assert [(f["nombre"], f["categoria"], f["tipo"]) for f in lista] == [
        ("Nafta", "Transporte", "unico")
    ]
    assert lista[0]["monto_cent"] == 3000000
    assert lista[0]["medio_pago"] is None  # el medio es opcional
    assert gastos.total_gastos(con, mes_id) - antes == 3000000


def test_alta_con_medio_de_pago(con, mes_id, transporte):
    # RF-06: el medio de pago se guarda si se elige.
    efectivo = id_por_nombre(con, catalogos.MEDIOS_PAGO, "Efectivo")
    gid = gastos.agregar_gasto(
        con, mes_id, "Nafta", transporte, 3000000, "fijo", efectivo
    )
    assert gastos.obtener_gasto(con, gid)["medio_pago_id"] == efectivo


def test_alta_normaliza_espacios_del_nombre(con, mes_id, transporte):
    gid = gastos.agregar_gasto(
        con, mes_id, "  Seguro   de  moto ", transporte, 100, "fijo"
    )
    assert gastos.obtener_gasto(con, gid)["nombre"] == "Seguro de moto"


@pytest.mark.parametrize("texto", ["-5.000", "0", "", "abc"])
def test_ca_06_2_monto_invalido_escrito_se_rechaza(con, mes_id, texto):
    # CA-06.2: −5.000, 0, vacío o "abc" se rechazan al leer el monto (con mensaje)
    # y por lo tanto no se crea ningún gasto.
    with pytest.raises(ErrorDeValidacion) as error:
        leer_monto(texto)
    assert str(error.value)  # tiene un mensaje para mostrar
    assert cantidad_filas(con, "gastos") == 0


@pytest.mark.parametrize("monto", [-500000, 0])
def test_ca_06_2_agregar_gasto_rechaza_monto_no_positivo(
    con, mes_id, transporte, monto
):
    # CA-06.2: aunque llegue un monto inválido ya convertido, la lógica lo rechaza.
    with pytest.raises(ErrorDeValidacion, match="mayor a 0"):
        gastos.agregar_gasto(con, mes_id, "Nafta", transporte, monto, "unico")
    assert cantidad_filas(con, "gastos") == 0


@pytest.mark.parametrize("nombre", ["", "   ", "\t"])
def test_ca_06_3_sin_nombre_se_rechaza(con, mes_id, transporte, nombre):
    # CA-06.3: alta sin nombre se rechaza.
    with pytest.raises(ErrorDeValidacion, match="nombre"):
        gastos.agregar_gasto(con, mes_id, nombre, transporte, 3000000, "unico")
    assert cantidad_filas(con, "gastos") == 0


def test_ca_06_3_sin_categoria_se_rechaza(con, mes_id):
    # CA-06.3: alta sin categoría se rechaza.
    with pytest.raises(ErrorDeValidacion, match="categoría"):
        gastos.agregar_gasto(con, mes_id, "Nafta", None, 3000000, "unico")
    assert cantidad_filas(con, "gastos") == 0


def test_categoria_inexistente_se_rechaza(con, mes_id):
    with pytest.raises(ErrorDeValidacion, match="no existe"):
        gastos.agregar_gasto(con, mes_id, "Nafta", 9999, 3000000, "unico")


def test_medio_de_pago_inexistente_se_rechaza(con, mes_id, transporte):
    with pytest.raises(ErrorDeValidacion, match="no existe"):
        gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "unico", 9999)


@pytest.mark.parametrize("tipo", ["cuota", "mensual", "", "FIJO"])
def test_tipo_invalido_se_rechaza(con, mes_id, transporte, tipo):
    # RF-06: solo "fijo" o "unico"; las cuotas se crean desde un plan (RF-16).
    with pytest.raises(ErrorDeValidacion):
        gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, tipo)
    assert cantidad_filas(con, "gastos") == 0


def test_ca_06_4_monto_con_centavos_se_guarda_exacto(con, mes_id, transporte):
    # CA-06.4: "66.020,12" se guarda 6602012 y en pantalla se ve "66.020".
    gid = gastos.agregar_gasto(
        con, mes_id, "Servicios", transporte, leer_monto("66.020,12"), "fijo"
    )
    guardado = gastos.obtener_gasto(con, gid)["monto_cent"]
    assert guardado == 6602012
    assert formatear_ars(guardado) == "$ 66.020"


def test_ca_06_5_categoria_archivada_no_aparece_para_dar_de_alta(con, mes_id):
    # CA-06.5: una categoría archivada no aparece en la lista para el alta.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 2500000, "fijo")
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    ofrecidas = [f["nombre"] for f in catalogos.listar(con, catalogos.CATEGORIAS)]
    assert "Gym" not in ofrecidas


def test_ca_12_1_deuda_jeho_como_pago_unico(con, mes_id):
    # CA-12.1 (pago único): "Deuda Jeho" se carga como pago único de 159.000.
    deudas = id_por_nombre(con, catalogos.CATEGORIAS, "Deudas")
    gid = gastos.agregar_gasto(
        con, mes_id, "Deuda Jeho", deudas, leer_monto("159.000"), "unico"
    )
    fila = gastos.obtener_gasto(con, gid)
    assert (fila["nombre"], fila["tipo"], fila["monto_cent"]) == (
        "Deuda Jeho",
        "unico",
        15900000,
    )


def test_monto_enorme_se_rechaza_al_leer_y_al_guardar(con, mes_id, transporte):
    # BUG-01 (ronda 1), versión estricta: un monto enorme se rechaza con
    # ErrorDeValidacion tanto al leerlo como al guardarlo (antes: OverflowError).
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        leer_monto("99999999999999999999")
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        gastos.agregar_gasto(
            con, mes_id, "Nafta", transporte, 9999999999999999999900, "unico"
        )
    assert cantidad_filas(con, "gastos") == 0


# ---------------------------------------------------------------------------
# RF-07: edición
# ---------------------------------------------------------------------------


def test_ca_07_1_editar_monto_sube_el_total_y_no_cambia_otros_meses(
    con, mes_id, transporte
):
    # CA-07.1: Nafta 30.000 -> 35.000: el total sube 5.000 y otro mes no cambia (RN-11).
    nafta = gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "fijo")
    noviembre = insertar_mes(con, 2026, 11)
    gastos.agregar_gasto(con, noviembre, "Nafta", transporte, 3000000, "fijo")

    antes = gastos.total_gastos(con, mes_id)
    gastos.editar_gasto(con, nafta, "Nafta", transporte, leer_monto("35.000"), "fijo")
    assert gastos.total_gastos(con, mes_id) - antes == 500000
    assert gastos.total_gastos(con, noviembre) == 3000000
    assert gastos.listar_gastos(con, noviembre)[0]["monto_cent"] == 3000000


def test_editar_todos_los_campos(con, mes_id, transporte):
    # RF-07: se puede editar cualquier campo.
    nafta = gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "unico")
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    efectivo = id_por_nombre(con, catalogos.MEDIOS_PAGO, "Efectivo")
    gastos.editar_gasto(con, nafta, "Combustible", otros, 4000000, "fijo", efectivo)
    fila = gastos.obtener_gasto(con, nafta)
    assert (fila["nombre"], fila["categoria_id"], fila["monto_cent"]) == (
        "Combustible",
        otros,
        4000000,
    )
    assert (fila["tipo"], fila["medio_pago_id"]) == ("fijo", efectivo)


def test_editar_quitar_medio_de_pago(con, mes_id, transporte):
    efectivo = id_por_nombre(con, catalogos.MEDIOS_PAGO, "Efectivo")
    nafta = gastos.agregar_gasto(
        con, mes_id, "Nafta", transporte, 3000000, "fijo", efectivo
    )
    gastos.editar_gasto(con, nafta, "Nafta", transporte, 3000000, "fijo", None)
    assert gastos.obtener_gasto(con, nafta)["medio_pago_id"] is None


def test_ca_07_2_no_se_puede_bajar_el_monto_por_debajo_de_lo_pagado(
    con, mes_id, transporte
):
    # CA-07.2: gasto 180.000 con 60.000 pagados; editar a 50.000 se rechaza con mensaje.
    gid = gastos.agregar_gasto(con, mes_id, "Seguro", transporte, 18000000, "fijo")
    insertar_pago(con, gid, 6000000)
    with pytest.raises(ErrorDeValidacion, match="ya pagaste"):
        gastos.editar_gasto(con, gid, "Seguro", transporte, 5000000, "fijo")
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 18000000


def test_ca_07_2_bajar_a_un_monto_mayor_a_lo_pagado_se_acepta(con, mes_id, transporte):
    # CA-07.2: a 100.000 se acepta y el pendiente queda 40.000.
    gid = gastos.agregar_gasto(con, mes_id, "Seguro", transporte, 18000000, "fijo")
    insertar_pago(con, gid, 6000000)
    gastos.editar_gasto(con, gid, "Seguro", transporte, 10000000, "fijo")
    fila = gastos.listar_gastos(con, mes_id)[0]
    assert fila["pagado_cent"] == 6000000
    assert fila["monto_cent"] - fila["pagado_cent"] == 4000000


def test_editar_monto_igual_a_lo_pagado_se_acepta(con, mes_id, transporte):
    # Borde de RN-23: monto igual a lo pagado (pendiente 0) es válido.
    gid = gastos.agregar_gasto(con, mes_id, "Seguro", transporte, 18000000, "fijo")
    insertar_pago(con, gid, 4000000)
    insertar_pago(con, gid, 2000000)
    gastos.editar_gasto(con, gid, "Seguro", transporte, 6000000, "fijo")
    assert gastos.total_pagado(con, gid) == 6000000


def test_editar_con_datos_invalidos_no_cambia_nada(con, mes_id, transporte):
    gid = gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "fijo")
    for args in [
        ("", transporte, 3000000, "fijo"),
        ("Nafta", None, 3000000, "fijo"),
        ("Nafta", transporte, 0, "fijo"),
        ("Nafta", transporte, -100, "fijo"),
        ("Nafta", transporte, 3000000, "cuota"),
    ]:
        with pytest.raises(ErrorDeValidacion):
            gastos.editar_gasto(con, gid, *args)
    fila = gastos.obtener_gasto(con, gid)
    assert (fila["nombre"], fila["monto_cent"], fila["tipo"]) == (
        "Nafta",
        3000000,
        "fijo",
    )


def test_editar_gasto_inexistente(con, mes_id, transporte):
    with pytest.raises(ErrorDeValidacion, match="ya no existe"):
        gastos.editar_gasto(con, 999, "Nafta", transporte, 3000000, "fijo")


def test_editar_cuota_se_rechaza(con, mes_id, transporte):
    # Las cuotas se editan desde su plan (paso 4).
    plan = insertar_plan(con, "Heladera", transporte)
    with con:
        cursor = con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Heladera', ?, 1000000, 'cuota', ?)",
            (mes_id, transporte, plan),
        )
    with pytest.raises(ErrorDeValidacion, match="plan"):
        gastos.editar_gasto(
            con, cursor.lastrowid, "Heladera", transporte, 2000000, "fijo"
        )


def test_editar_conserva_categoria_y_medio_archivados(con, mes_id):
    # RN-49: un gasto que ya tenía una categoría/medio archivado puede editarse
    # sin tener que cambiarlos.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    gid = gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 2500000, "fijo", visa)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    gastos.editar_gasto(con, gid, "Cuota gym", gym, 2800000, "fijo", visa)
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 2800000


def test_editar_no_permite_cambiar_a_categoria_o_medio_archivado(
    con, mes_id, transporte
):
    # RN-49: no se puede elegir una archivada distinta de la que ya tenía.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    gastos.agregar_gasto(con, mes_id, "Viejo", gym, 100, "fijo", visa)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)

    gid = gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "fijo")
    with pytest.raises(ErrorDeValidacion, match="archivada"):
        gastos.editar_gasto(con, gid, "Nafta", gym, 3000000, "fijo")
    with pytest.raises(ErrorDeValidacion, match="archivado"):
        gastos.editar_gasto(con, gid, "Nafta", transporte, 3000000, "fijo", visa)


# ---------------------------------------------------------------------------
# RF-08: baja
# ---------------------------------------------------------------------------


def test_ca_08_1_borrar_gasto_borra_sus_pagos_y_recalcula_total(
    con, mes_id, transporte
):
    # CA-08.1 / RN-51: al confirmar desaparece con sus pagos y el total se recalcula.
    nafta = gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "fijo")
    alquiler = gastos.agregar_gasto(
        con, mes_id, "Alquiler", transporte, 26000000, "fijo"
    )
    insertar_pago(con, nafta, 1000000)
    insertar_pago(con, nafta, 500000)
    insertar_pago(con, alquiler, 26000000)

    gastos.borrar_gasto(con, nafta)

    assert gastos.obtener_gasto(con, nafta) is None
    assert [f["nombre"] for f in gastos.listar_gastos(con, mes_id)] == ["Alquiler"]
    assert gastos.total_gastos(con, mes_id) == 26000000
    # Los pagos del gasto borrado desaparecen; los del otro quedan.
    assert cantidad_filas(con, "pagos") == 1
    assert gastos.total_pagado(con, nafta) == 0
    assert gastos.total_pagado(con, alquiler) == 26000000


def test_borrar_gasto_borra_sus_partes_compartidas(con, mes_id, transporte):
    # RN-51: también borra sus partes compartidas (tabla del paso 5, insertada a mano).
    gid = gastos.agregar_gasto(con, mes_id, "Edenor", transporte, 2580000, "fijo")
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    with con:
        con.execute(
            "INSERT INTO partes_gasto (gasto_id, persona_id, monto_cent) VALUES (?, ?, 1290000)",
            (gid, sofia),
        )
    gastos.borrar_gasto(con, gid)
    assert cantidad_filas(con, "partes_gasto") == 0


def test_borrar_gasto_inexistente_no_rompe_nada(con, mes_id, transporte):
    gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "fijo")
    gastos.borrar_gasto(con, 999)
    assert cantidad_filas(con, "gastos") == 1


# ---------------------------------------------------------------------------
# RF-09: lista y total
# ---------------------------------------------------------------------------

GASTOS_PLANILLA = [
    ("Alquiler", "Vivienda", "260.000"),
    ("Servicios", "Servicios", "82.000"),
    ("Seguro de moto", "Transporte", "131.000"),
    ("Mercado", "Mercado", "150.000"),
    ("Nafta", "Transporte", "30.000"),
    ("Teléfono", "Servicios", "20.000"),
    ("Internet", "Servicios", "38.700"),
    ("Psicólogo", "Salud", "140.000"),
]


def test_ca_09_1_total_de_los_8_gastos_de_la_planilla(con, mes_id):
    # CA-09.1 (total): con los 8 gastos de la planilla el total es 851.700.
    for nombre, categoria, monto in GASTOS_PLANILLA:
        cat = id_por_nombre(con, catalogos.CATEGORIAS, categoria)
        gastos.agregar_gasto(con, mes_id, nombre, cat, leer_monto(monto), "fijo")
    total = gastos.total_gastos(con, mes_id)
    assert total == 85170000
    assert formatear_ars(total) == "$ 851.700"
    # La lista respeta el orden de carga.
    assert [f["nombre"] for f in gastos.listar_gastos(con, mes_id)] == [
        g[0] for g in GASTOS_PLANILLA
    ]


def test_ca_09_2_total_redondea_desde_el_valor_exacto(con, mes_id, transporte):
    # CA-09.2: 0,40 + 0,40 + 0,40: el total se ve "1" (1,20), no "0".
    for _ in range(3):
        gastos.agregar_gasto(
            con, mes_id, "Chicle", transporte, leer_monto("0,40"), "unico"
        )
    total = gastos.total_gastos(con, mes_id)
    assert total == 120
    assert formatear_ars(total) == "$ 1"


def test_total_de_mes_sin_gastos_es_cero(con, mes_id):
    # Datos vacíos: un mes sin gastos tiene total 0 y lista vacía.
    assert gastos.total_gastos(con, mes_id) == 0
    assert gastos.listar_gastos(con, mes_id) == []
    assert formatear_ars(gastos.total_gastos(con, mes_id)) == "$ 0"


def test_total_y_lista_solo_del_mes_pedido(con, mes_id, transporte):
    # RF-01: los datos están separados por mes.
    otro = insertar_mes(con, 2026, 9)
    gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "fijo")
    gastos.agregar_gasto(con, otro, "Nafta vieja", transporte, 999900, "fijo")
    assert gastos.total_gastos(con, mes_id) == 3000000
    assert [f["nombre"] for f in gastos.listar_gastos(con, mes_id)] == ["Nafta"]


def test_lista_incluye_pagado_por_gasto(con, mes_id, transporte):
    # RF-09: la lista trae pagado_cent (suma de pagos) de cada gasto; sin pagos es 0.
    a = gastos.agregar_gasto(con, mes_id, "A", transporte, 1000000, "fijo")
    gastos.agregar_gasto(con, mes_id, "B", transporte, 2000000, "fijo")
    insertar_pago(con, a, 300000)
    insertar_pago(con, a, 200000)
    pagado = {f["nombre"]: f["pagado_cent"] for f in gastos.listar_gastos(con, mes_id)}
    assert pagado == {"A": 500000, "B": 0}


# ---------------------------------------------------------------------------
# Ronda 2: tope de montos (BUG-01), tipo de monto (O2), mes inexistente (O3)
# ---------------------------------------------------------------------------


def test_tope_exacto_se_acepta_en_agregar_gasto(con, mes_id, transporte):
    # El tope MONTO_MAXIMO_CENT es válido y se guarda exacto.
    gid = gastos.agregar_gasto(
        con, mes_id, "Casa", transporte, MONTO_MAXIMO_CENT, "unico"
    )
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == MONTO_MAXIMO_CENT
    assert formatear_ars(gastos.total_gastos(con, mes_id)) == "$ 999.999.999.999"


def test_tope_mas_un_centavo_se_rechaza_en_agregar_gasto(con, mes_id, transporte):
    # Un centavo más que el tope se rechaza y no se guarda nada.
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        gastos.agregar_gasto(
            con, mes_id, "Casa", transporte, MONTO_MAXIMO_CENT + 1, "unico"
        )
    assert cantidad_filas(con, "gastos") == 0


def test_tope_en_editar_gasto(con, mes_id, transporte):
    # editar_gasto acepta el tope exacto y rechaza un centavo más, sin cambiar el gasto.
    gid = gastos.agregar_gasto(con, mes_id, "Casa", transporte, 100, "unico")
    gastos.editar_gasto(con, gid, "Casa", transporte, MONTO_MAXIMO_CENT, "unico")
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == MONTO_MAXIMO_CENT
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        gastos.editar_gasto(
            con, gid, "Casa", transporte, MONTO_MAXIMO_CENT + 1, "unico"
        )
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == MONTO_MAXIMO_CENT


def test_varios_gastos_en_el_tope_suman_exacto(con, mes_id, transporte):
    # Sumar varios montos en el tope no pierde precisión (enteros, RN-01).
    for _ in range(3):
        gastos.agregar_gasto(
            con, mes_id, "Casa", transporte, MONTO_MAXIMO_CENT, "unico"
        )
    assert gastos.total_gastos(con, mes_id) == 3 * MONTO_MAXIMO_CENT


@pytest.mark.parametrize("monto", [100.5, 3000000.0, "3000000", True, False, None])
def test_o2_monto_que_no_es_entero_se_rechaza_al_agregar(
    con, mes_id, transporte, monto
):
    # O2 / RN-01: el monto tiene que ser int de centavos; float (aunque sea "redondo"),
    # texto, bool o None se rechazan con ErrorDeValidacion y no se guarda nada.
    with pytest.raises(ErrorDeValidacion):
        gastos.agregar_gasto(con, mes_id, "Nafta", transporte, monto, "unico")
    assert cantidad_filas(con, "gastos") == 0


@pytest.mark.parametrize("monto", [100.5, True, "3000000", None])
def test_o2_monto_que_no_es_entero_se_rechaza_al_editar(con, mes_id, transporte, monto):
    # O2: lo mismo al editar; el gasto queda como estaba y sigue siendo int.
    gid = gastos.agregar_gasto(con, mes_id, "Nafta", transporte, 3000000, "unico")
    with pytest.raises(ErrorDeValidacion):
        gastos.editar_gasto(con, gid, "Nafta", transporte, monto, "unico")
    fila = gastos.obtener_gasto(con, gid)
    assert fila["monto_cent"] == 3000000
    assert isinstance(fila["monto_cent"], int)


def test_o3_agregar_gasto_en_mes_inexistente(con, mes_id, transporte):
    # O3: un mes que no existe da ErrorDeValidacion con mensaje, no IntegrityError.
    with pytest.raises(ErrorDeValidacion, match="El mes no existe"):
        gastos.agregar_gasto(con, 999, "Nafta", transporte, 3000000, "unico")
    assert cantidad_filas(con, "gastos") == 0


def test_o3_agregar_gasto_sin_ningun_mes(con, transporte):
    # O3 con la base vacía (primer uso, todavía sin mes creado).
    with pytest.raises(ErrorDeValidacion, match="El mes no existe"):
        gastos.agregar_gasto(con, 1, "Nafta", transporte, 3000000, "unico")
