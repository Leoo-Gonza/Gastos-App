"""Pruebas de app/logica/pagos.py: tilde "pagado", pagos parciales, pendiente y totales
del mes (RF-13 a RF-15, RN-20 a RN-23; CA-13.x, CA-14.x, CA-15.x, CA-09.1 completo,
CA-43.5, CA-07.2, CA-45.4, CA-45.6). Base en memoria, datos inventados y fechas fijas."""

from datetime import date

import pytest

from app.logica import catalogos, gastos, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT, formatear_ars, formatear_fecha
from tests.ayudantes import cantidad_filas, id_por_nombre, insertar_mes

HOY = date(2026, 10, 4)  # fecha fija: las pruebas no dependen del día en que se corren


@pytest.fixture
def otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


@pytest.fixture
def seguro(con, mes_id, otros):
    """Gasto de 180.000 (el de CA-14.x y CA-15.1)."""
    return gastos.agregar_gasto(con, mes_id, "Seguro de moto", otros, 18000000, "fijo")


def _pagado(con, gasto_id):
    return gastos.total_pagado(con, gasto_id)


# ---------------------------------------------------------------------------
# Pendiente (RN-20)
# ---------------------------------------------------------------------------


def test_pendiente_sin_pagos_es_el_monto(con, seguro):
    assert pagos.pendiente(con, seguro) == 18000000


def test_pendiente_de_gasto_inexistente(con, mes_id):
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.pendiente(con, 999)
    assert str(error.value) == "El gasto ya no existe."
    assert error.value.campo is None


# ---------------------------------------------------------------------------
# Pago parcial (RF-14, RN-21)
# ---------------------------------------------------------------------------


def test_ca_14_1_pagos_parciales_hasta_cero(con, seguro):
    # CA-14.1: 60.000 → pagado 60.000, pendiente 120.000; 120.000 más → pendiente 0.
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    assert (_pagado(con, seguro), pagos.pendiente(con, seguro)) == (6000000, 12000000)
    pagos.registrar_pago(con, seguro, 12000000, HOY)
    assert pagos.pendiente(con, seguro) == 0
    # "El tilde aparece marcado": pendiente 0, y marcar_pagado no registra nada más.
    assert pagos.marcar_pagado(con, seguro, HOY) is None
    assert len(pagos.listar_pagos(con, seguro)) == 2


def test_registrar_pago_devuelve_el_id_y_guarda_la_fecha_iso(con, seguro):
    pid = pagos.registrar_pago(con, seguro, 6000000, date(2026, 10, 15))
    [fila] = pagos.listar_pagos(con, seguro)
    assert (fila["id"], fila["monto_cent"], fila["fecha"]) == (
        pid,
        6000000,
        "2026-10-15",
    )


def test_ca_14_2_pago_mayor_al_pendiente_se_rechaza(con, seguro):
    # CA-14.2: con pendiente 120.000, un pago de 130.000 se rechaza con el pendiente.
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.registrar_pago(con, seguro, 13000000, HOY)
    assert str(error.value) == "El pago no puede superar lo pendiente ($ 120.000)."
    assert error.value.campo == "monto"
    assert _pagado(con, seguro) == 6000000


def test_pago_igual_al_pendiente_se_acepta_y_uno_de_un_centavo_mas_no(con, seguro):
    # Borde de RN-21: ≤ pendiente.
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    with pytest.raises(ErrorDeValidacion, match="no puede superar"):
        pagos.registrar_pago(con, seguro, 12000001, HOY)
    pagos.registrar_pago(con, seguro, 12000000, HOY)
    assert pagos.pendiente(con, seguro) == 0


def test_pendiente_con_centavos_en_el_mensaje(con, mes_id, otros):
    # El mensaje muestra el pendiente redondeado a pesos (RN-04): 0,50 → "$ 1".
    gid = gastos.agregar_gasto(con, mes_id, "Chicle", otros, 150, "unico")
    pagos.registrar_pago(con, gid, 100, HOY)
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.registrar_pago(con, gid, 51, HOY)
    assert str(error.value) == "El pago no puede superar lo pendiente ($ 1)."
    pagos.registrar_pago(con, gid, 50, HOY)  # el pendiente exacto (0,50) sí entra
    assert pagos.pendiente(con, gid) == 0


@pytest.mark.parametrize(
    ("monto", "mensaje"),
    [
        (0, "El monto tiene que ser mayor a 0."),
        (-500000, "El monto tiene que ser mayor a 0."),
        (100.5, "El monto tiene que ser un número entero de centavos."),
        ("6000000", "El monto tiene que ser un número entero de centavos."),
        (None, "El monto tiene que ser un número entero de centavos."),
        (True, "El monto tiene que ser un número entero de centavos."),
        (MONTO_MAXIMO_CENT + 1, "El monto es demasiado grande."),
    ],
)
def test_ca_14_2_montos_invalidos(con, seguro, monto, mensaje):
    # CA-14.2 / RN-21: 0, negativos, no enteros, bool y demasiado grande se rechazan.
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.registrar_pago(con, seguro, monto, HOY)
    assert str(error.value) == mensaje
    assert error.value.campo == "monto"
    assert cantidad_filas(con, "pagos") == 0


def test_pagar_un_gasto_ya_pagado(con, seguro):
    pagos.marcar_pagado(con, seguro, HOY)
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.registrar_pago(con, seguro, 100, HOY)
    assert str(error.value) == "Este gasto ya está pagado."
    assert error.value.campo == "monto"


def test_pagar_un_gasto_inexistente(con, mes_id):
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.registrar_pago(con, 999, 100, HOY)
    assert str(error.value) == "El gasto ya no existe."
    assert error.value.campo is None
    assert cantidad_filas(con, "pagos") == 0


def test_fecha_por_defecto_es_hoy(con, seguro):
    # Sin fecha se usa la fecha de hoy de la computadora.
    pagos.registrar_pago(con, seguro, 100)
    assert pagos.listar_pagos(con, seguro)[0]["fecha"] == date.today().isoformat()  # noqa: DTZ011


def test_fecha_por_defecto_con_reloj_fijo(con, seguro, monkeypatch):
    # Igual que la anterior, pero fijando "hoy" para no depender del reloj.
    class FechaFija(date):
        @classmethod
        def today(cls):
            return cls(2026, 12, 31)

    monkeypatch.setattr(pagos, "date", FechaFija)
    pagos.marcar_pagado(con, seguro)
    assert pagos.listar_pagos(con, seguro)[0]["fecha"] == "2026-12-31"


# ---------------------------------------------------------------------------
# Tilde "pagado" (RF-13, RN-22)
# ---------------------------------------------------------------------------


def test_ca_13_1_marcar_alquiler(con, mes_id, otros):
    # CA-13.1: pagado 260.000, pendiente 0; el pendiente del mes baja 260.000 y el
    # total de gastos no cambia.
    alquiler = gastos.agregar_gasto(con, mes_id, "Alquiler", otros, 26000000, "fijo")
    gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "unico")
    antes = pagos.totales_del_mes(con, mes_id)
    pid = pagos.marcar_pagado(con, alquiler, HOY)
    assert isinstance(pid, int)
    assert (_pagado(con, alquiler), pagos.pendiente(con, alquiler)) == (26000000, 0)
    despues = pagos.totales_del_mes(con, mes_id)
    assert antes["pendiente"] - despues["pendiente"] == 26000000
    assert despues["total"] == antes["total"]


def test_marcar_despues_de_un_parcial_paga_solo_lo_que_falta(con, seguro):
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    pid = pagos.marcar_pagado(con, seguro, HOY)
    montos = {f["id"]: f["monto_cent"] for f in pagos.listar_pagos(con, seguro)}
    assert montos[pid] == 12000000
    assert pagos.pendiente(con, seguro) == 0


def test_marcar_dos_veces_no_registra_otro_pago(con, seguro):
    assert pagos.marcar_pagado(con, seguro, HOY) is not None
    assert pagos.marcar_pagado(con, seguro, HOY) is None
    assert len(pagos.listar_pagos(con, seguro)) == 1


def test_deshacer_marcar_borrando_ese_pago(con, seguro):
    # "Deshacer" del tilde: borrar el pago devuelto deja el pendiente como antes.
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    pid = pagos.marcar_pagado(con, seguro, HOY)
    pagos.borrar_pago(con, pid)
    assert pagos.pendiente(con, seguro) == 12000000
    assert [f["monto_cent"] for f in pagos.listar_pagos(con, seguro)] == [6000000]


def test_marcar_gasto_inexistente(con, mes_id):
    with pytest.raises(ErrorDeValidacion, match="^El gasto ya no existe.$"):
        pagos.marcar_pagado(con, 999, HOY)


def test_ca_13_2_destildar_borra_todos_los_pagos(con, seguro):
    # CA-13.2: dos parciales (60.000 y 50.000); destildar borra los dos.
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    pagos.registrar_pago(con, seguro, 5000000, HOY)
    assert pagos.quitar_pagos(con, seguro) == 2
    assert pagos.pendiente(con, seguro) == 18000000
    assert pagos.listar_pagos(con, seguro) == []


@pytest.mark.parametrize("cantidad", [0, 1, 3])
def test_quitar_pagos_devuelve_cuantos_borro(con, seguro, cantidad):
    for _ in range(cantidad):
        pagos.registrar_pago(con, seguro, 100000, HOY)
    assert pagos.quitar_pagos(con, seguro) == cantidad
    assert pagos.pendiente(con, seguro) == 18000000


def test_quitar_pagos_no_toca_los_de_otro_gasto(con, mes_id, otros, seguro):
    otro = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "unico")
    pagos.registrar_pago(con, seguro, 100000, HOY)
    pagos.marcar_pagado(con, otro, HOY)
    pagos.quitar_pagos(con, seguro)
    assert pagos.pendiente(con, otro) == 0


def test_quitar_pagos_de_gasto_inexistente(con, mes_id):
    with pytest.raises(ErrorDeValidacion, match="^El gasto ya no existe.$"):
        pagos.quitar_pagos(con, 999)


# ---------------------------------------------------------------------------
# Ver y borrar pagos (RF-15)
# ---------------------------------------------------------------------------


def test_ca_15_1_borrar_un_pago(con, seguro):
    # CA-15.1: pagos de 60.000 y 50.000; borrar el de 60.000 → pagado 50.000, pendiente 130.000.
    p60 = pagos.registrar_pago(con, seguro, 6000000, HOY)
    pagos.registrar_pago(con, seguro, 5000000, HOY)
    pagos.borrar_pago(con, p60)
    assert (_pagado(con, seguro), pagos.pendiente(con, seguro)) == (5000000, 13000000)


def test_listar_pagos_ordenados_por_fecha_y_despues_por_id(con, seguro):
    a = pagos.registrar_pago(con, seguro, 100, date(2026, 10, 20))
    b = pagos.registrar_pago(con, seguro, 200, date(2026, 10, 5))
    c = pagos.registrar_pago(con, seguro, 300, date(2026, 10, 5))
    d = pagos.registrar_pago(con, seguro, 400, date(2025, 12, 31))
    assert [f["id"] for f in pagos.listar_pagos(con, seguro)] == [d, b, c, a]
    assert list(pagos.listar_pagos(con, seguro)[0].keys()) == [
        "id",
        "monto_cent",
        "fecha",
    ]


def test_listar_pagos_de_un_gasto_sin_pagos(con, seguro):
    assert pagos.listar_pagos(con, seguro) == []


def test_borrar_pago_inexistente(con, seguro):
    pid = pagos.registrar_pago(con, seguro, 100, HOY)
    pagos.borrar_pago(con, pid)
    with pytest.raises(ErrorDeValidacion) as error:
        pagos.borrar_pago(con, pid)  # borrarlo dos veces
    assert str(error.value) == "Ese pago ya no existe."
    assert error.value.campo is None


def test_borrar_pago_no_toca_los_demas(con, mes_id, otros, seguro):
    otro = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "unico")
    pid = pagos.registrar_pago(con, seguro, 100, HOY)
    pagos.registrar_pago(con, seguro, 200, HOY)
    pagos.registrar_pago(con, otro, 300, HOY)
    pagos.borrar_pago(con, pid)
    assert _pagado(con, seguro) == 200
    assert _pagado(con, otro) == 300


# ---------------------------------------------------------------------------
# Totales del mes (RF-09, RN-20)
# ---------------------------------------------------------------------------

GASTOS_PLANILLA = [
    ("Alquiler", 26000000),
    ("Servicios", 8200000),
    ("Seguro de moto", 13100000),
    ("Mercado", 15000000),
    ("Nafta", 3000000),
    ("Teléfono", 2000000),
    ("Internet", 3870000),
    ("Psicólogo", 14000000),
]


def test_ca_09_1_completo_total_pagado_y_pendiente(con, mes_id, otros):
    # CA-09.1: total 851.700 y pendiente 851.700; tras marcar el Alquiler,
    # pagado 260.000 y pendiente 591.700.
    ids = {
        nombre: gastos.agregar_gasto(con, mes_id, nombre, otros, monto, "fijo")
        for nombre, monto in GASTOS_PLANILLA
    }
    assert pagos.totales_del_mes(con, mes_id) == {
        "total": 85170000,
        "pagado": 0,
        "pendiente": 85170000,
    }
    pagos.marcar_pagado(con, ids["Alquiler"], HOY)
    totales = pagos.totales_del_mes(con, mes_id)
    assert [formatear_ars(totales[k]) for k in ("total", "pagado", "pendiente")] == [
        "$ 851.700",
        "$ 260.000",
        "$ 591.700",
    ]


def test_totales_de_un_mes_sin_gastos(con, mes_id):
    assert pagos.totales_del_mes(con, mes_id) == {
        "total": 0,
        "pagado": 0,
        "pendiente": 0,
    }


def test_totales_de_un_mes_inexistente(con):
    assert pagos.totales_del_mes(con, 999) == {"total": 0, "pagado": 0, "pendiente": 0}


def test_totales_con_varios_gastos_y_pagos(con, mes_id, otros):
    a = gastos.agregar_gasto(con, mes_id, "A", otros, 1000000, "fijo")
    b = gastos.agregar_gasto(con, mes_id, "B", otros, 2000000, "fijo")
    gastos.agregar_gasto(con, mes_id, "C", otros, 40, "unico")
    pagos.registrar_pago(con, a, 300000, HOY)
    pagos.registrar_pago(con, a, 200000, HOY)
    pagos.marcar_pagado(con, b, HOY)
    assert pagos.totales_del_mes(con, mes_id) == {
        "total": 3000040,
        "pagado": 2500000,
        "pendiente": 500040,
    }


def test_totales_separados_por_mes(con, mes_id, otros):
    noviembre = insertar_mes(con, 2026, 11)
    oct_ = gastos.agregar_gasto(con, mes_id, "Alquiler", otros, 26000000, "fijo")
    nov = gastos.agregar_gasto(con, noviembre, "Alquiler", otros, 27000000, "fijo")
    pagos.marcar_pagado(con, oct_, HOY)
    pagos.registrar_pago(con, nov, 1000000, HOY)
    assert pagos.totales_del_mes(con, mes_id) == {
        "total": 26000000,
        "pagado": 26000000,
        "pendiente": 0,
    }
    assert pagos.totales_del_mes(con, noviembre) == {
        "total": 27000000,
        "pagado": 1000000,
        "pendiente": 26000000,
    }


def test_totales_coinciden_con_la_suma_por_gasto(con, mes_id, otros):
    # Total pendiente del mes = Σ pendiente de cada gasto (RN-20).
    ids = [
        gastos.agregar_gasto(con, mes_id, f"G{i}", otros, 1000 * (i + 1), "fijo")
        for i in range(5)
    ]
    pagos.registrar_pago(con, ids[1], 500, HOY)
    pagos.marcar_pagado(con, ids[3], HOY)
    totales = pagos.totales_del_mes(con, mes_id)
    assert totales["pendiente"] == sum(pagos.pendiente(con, g) for g in ids)
    assert totales["total"] == gastos.total_gastos(con, mes_id)


# ---------------------------------------------------------------------------
# Gastos en dólares (CA-43.5, RN-20) y RN-23 con pagos registrados (CA-07.2, 45.4, 45.6)
# ---------------------------------------------------------------------------


@pytest.fixture
def claude(con, mes_id, otros):
    return gastos.agregar_gasto(
        con, mes_id, "Claude", otros, None, "unico", None, "USD", 2000, 160000
    )


def test_ca_43_5_marcar_pagado_un_gasto_en_dolares(con, claude):
    # CA-43.5: marcar pagado Claude registra un pago de 32.000 ARS y el pendiente queda 0.
    pid = pagos.marcar_pagado(con, claude, HOY)
    [fila] = pagos.listar_pagos(con, claude)
    assert (fila["id"], fila["monto_cent"]) == (pid, 3200000)
    assert pagos.pendiente(con, claude) == 0


def test_ca_43_5_pago_parcial_de_un_gasto_en_dolares(con, claude):
    # Un pago parcial de 10.000 deja pendiente 22.000 (en pesos).
    pagos.registrar_pago(con, claude, 1000000, HOY)
    assert pagos.pendiente(con, claude) == 2200000
    with pytest.raises(
        ErrorDeValidacion,
        match=r"^El pago no puede superar lo pendiente \(\$ 22.000\).$",
    ):
        pagos.registrar_pago(con, claude, 2200001, HOY)


def test_ca_07_2_con_pagos_registrados(con, mes_id, otros, seguro):
    # CA-07.2: 180.000 con 60.000 pagados: 50.000 se rechaza; 100.000 se acepta,
    # pendiente 40.000.
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    with pytest.raises(ErrorDeValidacion) as error:
        gastos.editar_gasto(con, seguro, "Seguro de moto", otros, 5000000, "fijo")
    assert (
        str(error.value)
        == "No podés bajar el monto a menos de lo que ya pagaste ($ 60.000)."
    )
    gastos.editar_gasto(con, seguro, "Seguro de moto", otros, 10000000, "fijo")
    assert pagos.pendiente(con, seguro) == 4000000


def test_ca_45_4_con_pagos_registrados(con, otros, claude):
    # CA-45.4: Claude con un pago de 30.000: cotización 1.400 (28.000) se rechaza;
    # 1.550 (31.000) se acepta y el pendiente queda 1.000; US$ 18 (28.800) se rechaza.
    pagos.registrar_pago(con, claude, 3000000, HOY)

    def editar(usd, cot):
        gastos.editar_gasto(
            con, claude, "Claude", otros, None, "unico", None, "USD", usd, cot
        )

    with pytest.raises(ErrorDeValidacion, match=r"ya pagaste \(\$ 30.000\)"):
        editar(2000, 140000)
    editar(2000, 155000)
    assert pagos.pendiente(con, claude) == 100000
    with pytest.raises(ErrorDeValidacion, match="menos de lo que ya pagaste"):
        editar(1800, 160000)


def test_ca_45_6_con_pagos_registrados(con, otros, claude):
    # CA-45.6: Claude con 32.000 pagados: pasarlo a ARS con 30.000 se rechaza.
    pagos.marcar_pagado(con, claude, HOY)
    with pytest.raises(ErrorDeValidacion, match=r"ya pagaste \(\$ 32.000\)"):
        gastos.editar_gasto(con, claude, "Claude", otros, 3000000, "unico", None, "ARS")
    assert gastos.obtener_gasto(con, claude)["moneda"] == "USD"


def test_subir_el_monto_de_un_gasto_pagado_deja_pendiente(con, otros, seguro):
    # Después de pagar todo, subir el monto deja pendiente la diferencia (el tilde se va).
    pagos.marcar_pagado(con, seguro, HOY)
    gastos.editar_gasto(con, seguro, "Seguro de moto", otros, 20000000, "fijo")
    assert pagos.pendiente(con, seguro) == 2000000
    assert pagos.marcar_pagado(con, seguro, HOY) is not None


def test_borrar_un_gasto_borra_sus_pagos(con, mes_id, otros, seguro):
    # CA-08.1 / RN-51 con pagos registrados por la función.
    otro = gastos.agregar_gasto(con, mes_id, "Nafta", otros, 3000000, "unico")
    pagos.registrar_pago(con, seguro, 6000000, HOY)
    pagos.registrar_pago(con, seguro, 5000000, HOY)
    pagos.marcar_pagado(con, otro, HOY)
    gastos.borrar_gasto(con, seguro)
    assert cantidad_filas(con, "pagos") == 1
    assert pagos.listar_pagos(con, seguro) == []
    assert pagos.totales_del_mes(con, mes_id) == {
        "total": 3000000,
        "pagado": 3000000,
        "pendiente": 0,
    }


# ---------------------------------------------------------------------------
# formatear_fecha
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("iso", "texto"),
    [
        ("2026-10-04", "04/10/2026"),
        ("2026-12-31", "31/12/2026"),
        ("2027-01-01", "01/01/2027"),
        ("2028-02-29", "29/02/2028"),
    ],
)
def test_formatear_fecha(iso, texto):
    assert formatear_fecha(iso) == texto


def test_formatear_fecha_de_un_pago_guardado(con, seguro):
    pagos.registrar_pago(con, seguro, 100, date(2026, 3, 9))
    assert formatear_fecha(pagos.listar_pagos(con, seguro)[0]["fecha"]) == "09/03/2026"
