"""Pruebas de la interfaz de pagos (paso 2b): columnas Pag./Pagado/Pendiente, fila de
totales, tilde "pagado" con Deshacer, destildar con confirmación, "Registrar pago" y
"Ver pagos" (RF-13 a RF-15; diseno.md §3.3, §4.3, §4.4; CA-09.1, CA-13.x, CA-14.x,
CA-15.1, CA-43.5). Además O22 en la lógica. Página falsa, sin ventanas; fechas fijas."""

from datetime import date, datetime
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz.dialogos import dialogo_pago
from app.logica import catalogos, gastos, pagos
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    boton,
    celda,
    clic,
    de_tipo,
    dialogo_arriba,
    filas_tabla,
    hay_boton,
    item_menu,
    tecla,
    textos,
    titulo_dialogo,
)

HOY = date(2026, 10, 4)
PENDIENTE = "#9A5800"  # color "pendiente", tema claro
POSITIVO = "#1E7B34"  # color "positivo", tema claro


class FechaFija(date):
    """ "Hoy" fijo para el diálogo de pago (no depende del día en que se corren)."""

    @classmethod
    def today(cls):
        return cls(2026, 10, 4)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(dialogo_pago, "date", FechaFija)
    monkeypatch.setattr(pagos, "date", FechaFija)


@pytest.fixture
def pantalla(app):
    return app.pantalla("Gastos")


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _agregar(app, nombre, monto, tipo="fijo"):
    gid = gastos.agregar_gasto(
        app.con, app.mes_id, nombre, _otros(app.con), monto, tipo
    )
    app.refrescar()
    return gid


def _tilde(pantalla, nombre):
    return celda(pantalla, nombre, "Pag.").content


def _clic_tilde(pantalla, nombre):
    """Simula el clic en el tilde: invierte el valor y dispara on_change."""
    tilde = _tilde(pantalla, nombre)
    tilde.value = not tilde.value
    tilde.on_change(SimpleNamespace(control=tilde))
    return tilde


def _fila(pantalla, nombre):
    return next(f for f in filas_tabla(pantalla) if f["Nombre"] == nombre)


def _total(pantalla):
    return filas_tabla(pantalla)[-1]


def _dialogo_pago(app):
    return boton(dialogo_arriba(app), "Guardar").on_click.__self__


def _dialogo_ver(app):
    return boton(dialogo_arriba(app), "Registrar otro pago").on_click.__self__


def _abrir_pago(app, pantalla, nombre):
    item_menu(pantalla, nombre, "Registrar pago").on_click(None)
    return _dialogo_pago(app)


def _pagar(app, pantalla, nombre, monto_texto):
    d = _abrir_pago(app, pantalla, nombre)
    d.monto.value = monto_texto
    d._guardar()
    return d


def _abrir_ver(app, pantalla, nombre):
    item_menu(pantalla, nombre, "Ver pagos").on_click(None)
    return _dialogo_ver(app)


def _enfocado(pagina):
    return pagina.tareas[-1].__self__


# ---------------------------------------------------------------------------
# O22 (lógica): un datetime se guarda como fecha sola
# ---------------------------------------------------------------------------


def test_o22_registrar_pago_con_datetime_guarda_solo_la_fecha(app):
    gid = _agregar(app, "Seguro", 18000000)
    pagos.registrar_pago(app.con, gid, 100, datetime(2026, 10, 4, 23, 59, 59))  # noqa: DTZ001
    assert pagos.listar_pagos(app.con, gid)[0]["fecha"] == "2026-10-04"


def test_o22_marcar_pagado_con_datetime(app):
    gid = _agregar(app, "Seguro", 18000000)
    pagos.marcar_pagado(app.con, gid, datetime(2026, 1, 2, 0, 0, 1))  # noqa: DTZ001
    assert pagos.listar_pagos(app.con, gid)[0]["fecha"] == "2026-01-02"


def test_o22_ordena_bien_mezclando_date_y_datetime(app):
    gid = _agregar(app, "Seguro", 18000000)
    a = pagos.registrar_pago(app.con, gid, 100, datetime(2026, 10, 4, 18, 0))  # noqa: DTZ001
    b = pagos.registrar_pago(app.con, gid, 100, date(2026, 10, 4))
    assert [p["id"] for p in pagos.listar_pagos(app.con, gid)] == [a, b]


# ---------------------------------------------------------------------------
# Tabla: Pag., Pagado, Pendiente (§3.3)
# ---------------------------------------------------------------------------


def test_gasto_sin_pagos(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    fila = _fila(pantalla, "Nafta")
    assert (fila["Pagado"], fila["Pendiente"]) == ("$ 0", "$ 30.000")
    assert celda(pantalla, "Nafta", "Pendiente").content.color == PENDIENTE
    tilde = _tilde(pantalla, "Nafta")
    assert isinstance(tilde, ft.Checkbox)
    assert tilde.value is False
    assert tilde.tooltip == "Marcar como pagado"


def test_gasto_con_pago_parcial_muestra_parcial(app, pantalla):
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 6000000, HOY)
    app.refrescar()
    fila = _fila(pantalla, "Seguro de moto")
    assert (fila["Pagado"], fila["Pendiente"]) == ("$ 60.000 | Parcial", "$ 120.000")
    _, parcial = celda(pantalla, "Seguro de moto", "Pagado").content.controls
    assert (parcial.size, parcial.color) == (13, PENDIENTE)
    assert _tilde(pantalla, "Seguro de moto").value is False


def test_gasto_pagado_muestra_tilde_y_pagado_en_verde(app, pantalla):
    gid = _agregar(app, "Alquiler", 26000000)
    pagos.marcar_pagado(app.con, gid, HOY)
    app.refrescar()
    fila = _fila(pantalla, "Alquiler")
    assert (fila["Pagado"], fila["Pendiente"]) == (
        "$ 260.000",
        "Pagado",
    )  # sin "Parcial"
    icono, texto = celda(pantalla, "Alquiler", "Pendiente").content.controls
    assert (icono.icon, icono.color) == (ft.Icons.CHECK, POSITIVO)
    assert texto.color == POSITIVO
    assert _tilde(pantalla, "Alquiler").value is True


def test_pagado_con_parciales_tambien_marca_el_tilde(app, pantalla):
    # RN-22: el tilde aparece marcado aunque se haya pagado con parciales.
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 6000000, HOY)
    pagos.registrar_pago(app.con, gid, 12000000, HOY)
    app.refrescar()
    assert _tilde(pantalla, "Seguro de moto").value is True
    assert _fila(pantalla, "Seguro de moto")["Pagado"] == "$ 180.000"


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


def test_ca_09_1_y_ca_13_1_en_pantalla(app, pantalla, pagina):
    # CA-09.1: total 851.700, pagado 0, pendiente 851.700. CA-13.1: marcar el tilde
    # de Alquiler → pagado 260.000, pendiente 591.700; el total no cambia.
    for nombre, monto in GASTOS_PLANILLA:
        _agregar(app, nombre, monto)
    total = _total(pantalla)
    assert (total["Monto"], total["Pagado"], total["Pendiente"]) == (
        "$ 851.700",
        "$ 0",
        "$ 851.700",
    )
    _clic_tilde(pantalla, "Alquiler")
    total = _total(pantalla)
    assert (total["Monto"], total["Pagado"], total["Pendiente"]) == (
        "$ 851.700",
        "$ 260.000",
        "$ 591.700",
    )
    assert _fila(pantalla, "Alquiler")["Pendiente"] == "Pagado"
    aviso = pagina.ultimo_aviso()
    assert (aviso.content.value, aviso.action) == (
        "Alquiler marcado como pagado",
        "Deshacer",
    )
    assert app.hay_dialogo_abierto() is False  # marcar no pide confirmación


def test_total_pendiente_cero_con_icono(app, pantalla):
    gid = _agregar(app, "Alquiler", 26000000)
    pagos.marcar_pagado(app.con, gid, HOY)
    app.refrescar()
    icono, texto = celda(pantalla, "TOTAL (1 gasto)", "Pendiente").content.controls
    assert (icono.icon, icono.color) == (ft.Icons.CHECK_CIRCLE, POSITIVO)
    assert (texto.value, texto.color, texto.weight) == (
        "$ 0",
        POSITIVO,
        ft.FontWeight.W_700,
    )


def test_total_pendiente_mayor_a_cero_en_color_pendiente(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    texto = celda(pantalla, "TOTAL (1 gasto)", "Pendiente").content
    assert (texto.value, texto.color, texto.weight) == (
        "$ 30.000",
        PENDIENTE,
        ft.FontWeight.W_700,
    )


# ---------------------------------------------------------------------------
# Tilde: marcar con Deshacer, destildar con confirmación
# ---------------------------------------------------------------------------


def test_deshacer_borra_solo_el_pago_del_tilde(app, pantalla, pagina):
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 6000000, HOY)
    app.refrescar()
    _clic_tilde(pantalla, "Seguro de moto")
    assert pagos.pendiente(app.con, gid) == 0
    pagina.ultimo_aviso().on_action(None)
    assert pagos.pendiente(app.con, gid) == 12000000
    assert [p["monto_cent"] for p in pagos.listar_pagos(app.con, gid)] == [6000000]
    assert _fila(pantalla, "Seguro de moto")["Pagado"] == "$ 60.000 | Parcial"
    pagina.ultimo_aviso().on_action(None)  # Deshacer dos veces no rompe nada
    assert pagos.pendiente(app.con, gid) == 12000000


def test_marcar_un_gasto_que_ya_estaba_pagado_por_detras(app, pantalla, pagina):
    # La tabla quedó vieja: el tilde se marca pero ya estaba pagado. No duplica el pago.
    gid = _agregar(app, "Nafta", 3000000)
    pagos.marcar_pagado(app.con, gid, HOY)  # sin refrescar la tabla
    _clic_tilde(pantalla, "Nafta")
    assert len(pagos.listar_pagos(app.con, gid)) == 1
    assert _tilde(pantalla, "Nafta").value is True
    assert not any("marcado como pagado" in a for a in pagina.avisos())


def _dos_parciales(app):
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 6000000, HOY)
    pagos.registrar_pago(app.con, gid, 12000000, HOY)
    app.refrescar()
    return gid


def test_ca_13_2_destildar_pide_confirmacion(app, pantalla):
    gid = _dos_parciales(app)
    tilde = _clic_tilde(pantalla, "Seguro de moto")
    assert tilde.value is True  # hasta confirmar sigue marcado
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Quitar los pagos de Seguro de moto?"
    assert (
        "Se van a borrar los 2 pagos registrados ($ 180.000). El gasto vuelve a "
        "quedar pendiente por $ 180.000." in textos(confirmacion)
    )
    assert boton(confirmacion, "Cancelar").autofocus is True
    assert hay_boton(confirmacion, "Quitar pagos")
    assert len(pagos.listar_pagos(app.con, gid)) == 2


def test_ca_13_2_cancelar_no_quita_nada(app, pantalla):
    gid = _dos_parciales(app)
    _clic_tilde(pantalla, "Seguro de moto")
    clic(dialogo_arriba(app), "Cancelar")
    assert len(pagos.listar_pagos(app.con, gid)) == 2
    assert _tilde(pantalla, "Seguro de moto").value is True


def test_ca_13_2_confirmar_quita_los_pagos(app, pantalla, pagina):
    gid = _dos_parciales(app)
    _clic_tilde(pantalla, "Seguro de moto")
    clic(dialogo_arriba(app), "Quitar pagos")
    assert pagos.listar_pagos(app.con, gid) == []
    assert pagos.pendiente(app.con, gid) == 18000000
    fila = _fila(pantalla, "Seguro de moto")
    assert (fila["Pagado"], fila["Pendiente"]) == ("$ 0", "$ 180.000")
    assert _tilde(pantalla, "Seguro de moto").value is False
    assert pagina.avisos()[-1] == "Se quitaron los pagos de Seguro de moto"


def test_destildar_con_un_solo_pago_usa_singular(app, pantalla):
    gid = _agregar(app, "Alquiler", 26000000)
    pagos.marcar_pagado(app.con, gid, HOY)
    app.refrescar()
    _clic_tilde(pantalla, "Alquiler")
    assert (
        "Se va a borrar el pago registrado ($ 260.000). El gasto vuelve a quedar "
        "pendiente por $ 260.000." in textos(dialogo_arriba(app))
    )


def test_quitar_pagos_de_un_gasto_borrado_por_detras_no_dice_que_se_quitaron(
    app, pantalla, pagina
):
    # Si el gasto se borró entre la confirmación y el clic en "Quitar pagos",
    # el aviso tiene que ser solo el error, sin el de éxito.
    gid = _dos_parciales(app)
    _clic_tilde(pantalla, "Seguro de moto")
    gastos.borrar_gasto(app.con, gid)
    clic(dialogo_arriba(app), "Quitar pagos")
    assert "El gasto ya no existe." in pagina.avisos()
    assert "Se quitaron los pagos de Seguro de moto" not in pagina.avisos()


def test_tilde_de_un_gasto_borrado_por_detras(app, pantalla, pagina):
    gid = _agregar(app, "Nafta", 3000000)
    gastos.borrar_gasto(app.con, gid)
    _clic_tilde(pantalla, "Nafta")
    assert pagina.avisos()[-1] == "Ese gasto ya no existe."
    assert app.hay_dialogo_abierto() is False
    assert "Todavía no cargaste gastos en Octubre 2026." in textos(pantalla.cuerpo)


# ---------------------------------------------------------------------------
# Registrar pago (§4.3, CA-14.x)
# ---------------------------------------------------------------------------


def test_dialogo_registrar_pago_contenido(app, pantalla):
    _agregar(app, "Seguro de moto", 18000000)
    d = _abrir_pago(app, pantalla, "Seguro de moto")
    assert titulo_dialogo(d.dialogo) == "Registrar pago"
    assert (
        "Seguro de moto · Monto $ 180.000 · Pagado $ 0 · Pendiente $ 180.000"
        in textos(d.dialogo)
    )
    assert d.monto.autofocus is True
    assert d.monto.label == "Monto del pago"
    assert (d.texto_fecha.value, d.texto_fecha.read_only) == ("04/10/2026", True)
    assert hay_boton(d.dialogo, "Pagar todo lo pendiente")
    [calendario] = [
        b
        for b in de_tipo(d.dialogo, ft.IconButton)
        if b.icon == ft.Icons.CALENDAR_MONTH
    ]
    assert calendario.tooltip == "Elegir la fecha"


def test_ca_14_1_dos_pagos_hasta_quedar_pagado(app, pantalla, pagina):
    gid = _agregar(app, "Seguro de moto", 18000000)
    d = _pagar(app, pantalla, "Seguro de moto", "60.000")
    assert d.dialogo.open is False
    assert pagina.avisos()[-1] == "Pago de $ 60.000 registrado"
    fila = _fila(pantalla, "Seguro de moto")
    assert (fila["Pagado"], fila["Pendiente"]) == ("$ 60.000 | Parcial", "$ 120.000")

    d = _abrir_pago(app, pantalla, "Seguro de moto")
    assert (
        "Seguro de moto · Monto $ 180.000 · Pagado $ 60.000 · Pendiente $ 120.000"
        in (textos(d.dialogo))
    )
    clic(d.dialogo, "Pagar todo lo pendiente")
    assert d.monto.value == "120.000"
    d._guardar()
    assert pagos.pendiente(app.con, gid) == 0
    assert (
        pagina.avisos()[-1]
        == "Pago de $ 120.000 registrado: Seguro de moto quedó pagado"
    )
    assert _tilde(pantalla, "Seguro de moto").value is True
    assert [p["fecha"] for p in pagos.listar_pagos(app.con, gid)] == ["2026-10-04"] * 2


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("130.000", "El pago no puede superar lo pendiente ($ 120.000)."),  # CA-14.2
        ("0", "El monto tiene que ser mayor a 0."),  # CA-14.2
        ("", "Ingresá un monto."),
        ("abc", "Escribí solo números. Ej.: 66.020,12"),
        ("60000.5", "Usá coma para los decimales. Ej.: 66.020,12"),
    ],
)
def test_ca_14_2_pagos_invalidos(app, pantalla, pagina, texto, mensaje):
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 6000000, HOY)
    app.refrescar()
    d = _pagar(app, pantalla, "Seguro de moto", texto)
    assert d.monto.error == mensaje
    assert d.dialogo.open is True
    assert _enfocado(pagina) is d.monto
    assert len(pagos.listar_pagos(app.con, gid)) == 1


def test_registrar_pago_de_un_gasto_ya_pagado_avisa_sin_dialogo(app, pantalla, pagina):
    gid = _agregar(app, "Alquiler", 26000000)
    pagos.marcar_pagado(app.con, gid, HOY)
    app.refrescar()
    item_menu(pantalla, "Alquiler", "Registrar pago").on_click(None)
    assert app.hay_dialogo_abierto() is False
    assert pagina.avisos()[-1] == "Este gasto ya está pagado."


def test_registrar_pago_de_un_gasto_borrado_por_detras(app, pantalla, pagina):
    gid = _agregar(app, "Nafta", 3000000)
    gastos.borrar_gasto(app.con, gid)
    item_menu(pantalla, "Nafta", "Registrar pago").on_click(None)
    assert app.hay_dialogo_abierto() is False
    assert pagina.avisos()[-1] == "Ese gasto ya no existe."


def test_gasto_borrado_con_el_dialogo_de_pago_abierto(app, pantalla, pagina):
    gid = _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    gastos.borrar_gasto(app.con, gid)
    d.monto.value = "1.000"
    d._guardar()
    assert d.dialogo.open is False
    assert pagina.avisos()[-1] == "El gasto ya no existe."
    assert "Todavía no cargaste gastos en Octubre 2026." in textos(pantalla.cuerpo)


def test_cancelar_y_enter_en_el_dialogo_de_pago(app, pantalla, pagina):
    gid = _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    d.monto.value = "1.000"
    clic(d.dialogo, "Cancelar")
    assert pagos.listar_pagos(app.con, gid) == []
    d = _abrir_pago(app, pantalla, "Nafta")
    d.monto.value = "1.000"
    d.monto.on_submit(None)  # Enter guarda
    assert [p["monto_cent"] for p in pagos.listar_pagos(app.con, gid)] == [100000]


def test_elegir_otra_fecha_con_el_calendario(app, pantalla):
    # O22 en pantalla: el calendario devuelve un datetime y se guarda solo la fecha.
    gid = _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    [boton_cal] = [
        b
        for b in de_tipo(d.dialogo, ft.IconButton)
        if b.icon == ft.Icons.CALENDAR_MONTH
    ]
    boton_cal.on_click(None)
    assert dialogo_arriba(app) is d.calendario
    d.calendario.value = datetime(2026, 10, 1, 15, 30)  # noqa: DTZ001
    d.calendario.on_change(None)
    assert d.texto_fecha.value == "01/10/2026"
    d.monto.value = "1.000"
    d._guardar()
    assert pagos.listar_pagos(app.con, gid)[0]["fecha"] == "2026-10-01"


def test_elegir_fecha_con_un_date(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    d.calendario.value = date(2025, 12, 31)
    d._elegir_fecha()
    assert d.texto_fecha.value == "31/12/2025"


def test_escape_con_el_calendario_abierto_cierra_solo_el_calendario(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    app.abrir_dialogo(d.calendario)
    app._al_presionar_tecla(tecla("Escape"))
    assert app._dialogos == [d.dialogo]
    assert d.dialogo.open is True


def test_error_inesperado_al_registrar_pago(app, pantalla, monkeypatch):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")

    def falla(*args, **kwargs):
        raise RuntimeError("falla inventada")

    monkeypatch.setattr(pagos, "registrar_pago", falla)
    d.monto.value = "1.000"
    d._guardar()
    assert d.dialogo.open is False
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


def test_ca_43_5_pagos_de_un_gasto_en_dolares(app, pantalla, pagina):
    # CA-43.5: los pagos son en pesos; el diálogo muestra de dónde salen.
    gid = gastos.agregar_gasto(
        app.con,
        app.mes_id,
        "Claude",
        _otros(app.con),
        None,
        "unico",
        None,
        "USD",
        2000,
        160000,
    )
    app.refrescar()
    d = _abrir_pago(app, pantalla, "Claude")
    contenido = textos(d.dialogo)
    assert "Claude · Monto $ 32.000 · Pagado $ 0 · Pendiente $ 32.000" in contenido
    assert "Gasto en dólares: US$ 20,00 × $ 1.600. Se paga en pesos." in contenido
    d.monto.value = "10.000"
    d._guardar()
    assert _fila(pantalla, "Claude")["Pendiente"] == "$ 22.000"
    _clic_tilde(pantalla, "Claude")
    assert pagos.pendiente(app.con, gid) == 0
    assert [p["monto_cent"] for p in pagos.listar_pagos(app.con, gid)] == [
        1000000,
        2200000,
    ]


# ---------------------------------------------------------------------------
# Ver pagos (§4.4, CA-15.1)
# ---------------------------------------------------------------------------


def _filas_ver(d):
    return [[t for t in textos(fila) if t] for fila in d.lista.controls]


def test_ver_pagos_sin_pagos(app, pantalla):
    _agregar(app, "Seguro de moto", 18000000)
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    assert titulo_dialogo(d.dialogo) == "Pagos de Seguro de moto"
    assert _filas_ver(d) == [["Todavía no hay pagos registrados."]]
    assert d.pie.value == "Pagado $ 0 · Pendiente $ 180.000"
    assert d.boton_otro.visible is True


def test_ca_15_1_ver_y_borrar_un_pago(app, pantalla, pagina):
    gid = _agregar(app, "Seguro de moto", 18000000)
    p60 = pagos.registrar_pago(app.con, gid, 6000000, date(2026, 10, 1))
    pagos.registrar_pago(app.con, gid, 5000000, date(2026, 10, 3))
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    assert _filas_ver(d) == [["01/10/2026", "$ 60.000"], ["03/10/2026", "$ 50.000"]]
    assert d.pie.value == "Pagado $ 110.000 · Pendiente $ 70.000"

    # Clic en el tacho de la primera fila: confirmación en la misma fila.
    [tacho] = [b for b in de_tipo(d.lista.controls[0], ft.IconButton)]
    assert tacho.tooltip == "Borrar este pago"
    tacho.on_click(None)
    fila = d.lista.controls[0]
    assert "¿Borrar este pago?" in textos(fila)
    assert boton(fila, "No").autofocus is True
    assert app._dialogos == [d.dialogo]  # no abre otro diálogo

    clic(fila, "Sí, borrar")
    assert [p["id"] for p in pagos.listar_pagos(app.con, gid)] != [p60]
    assert _filas_ver(d) == [["03/10/2026", "$ 50.000"]]
    assert d.pie.value == "Pagado $ 50.000 · Pendiente $ 130.000"
    assert d.dialogo.open is True
    # La tabla de atrás también se actualizó.
    fila_tabla = _fila(pantalla, "Seguro de moto")
    assert (fila_tabla["Pagado"], fila_tabla["Pendiente"]) == (
        "$ 50.000 | Parcial",
        "$ 130.000",
    )


def test_ver_pagos_no_en_la_confirmacion_no_borra(app, pantalla):
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 6000000, HOY)
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    de_tipo(d.lista.controls[0], ft.IconButton)[0].on_click(None)
    clic(d.lista.controls[0], "No")
    assert len(pagos.listar_pagos(app.con, gid)) == 1
    assert "¿Borrar este pago?" not in textos(d.lista)


def test_ver_pagos_ordenados_por_fecha(app, pantalla):
    gid = _agregar(app, "Seguro de moto", 18000000)
    pagos.registrar_pago(app.con, gid, 100000, date(2026, 10, 20))
    pagos.registrar_pago(app.con, gid, 200000, date(2026, 9, 30))
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    assert [f[0] for f in _filas_ver(d)] == ["30/09/2026", "20/10/2026"]


def test_ver_pagos_de_un_gasto_pagado_oculta_registrar_otro(app, pantalla):
    gid = _agregar(app, "Alquiler", 26000000)
    pagos.marcar_pagado(app.con, gid, HOY)
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Alquiler")
    assert d.boton_otro.visible is False
    assert d.pie.value == "Pagado $ 260.000 · Pendiente $ 0"


def test_registrar_otro_pago_desde_ver_pagos(app, pantalla):
    _agregar(app, "Seguro de moto", 18000000)
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    clic(d.dialogo, "Registrar otro pago")
    assert d.dialogo.open is False
    assert titulo_dialogo(dialogo_arriba(app)) == "Registrar pago"
    assert len(app._dialogos) == 1


def test_pago_borrado_por_detras_antes_de_tocar_el_tacho(app, pantalla):
    # Al tocar el tacho el diálogo se redibuja: si el pago ya no está, desaparece.
    gid = _agregar(app, "Seguro de moto", 18000000)
    pid = pagos.registrar_pago(app.con, gid, 6000000, HOY)
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    pagos.borrar_pago(app.con, pid)
    de_tipo(d.lista.controls[0], ft.IconButton)[0].on_click(None)
    assert _filas_ver(d) == [["Todavía no hay pagos registrados."]]


def test_pago_borrado_por_detras_durante_la_confirmacion(app, pantalla, pagina):
    # Si se borra entre "¿Borrar este pago?" y "Sí, borrar": avisa y redibuja.
    gid = _agregar(app, "Seguro de moto", 18000000)
    pid = pagos.registrar_pago(app.con, gid, 6000000, HOY)
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Seguro de moto")
    de_tipo(d.lista.controls[0], ft.IconButton)[0].on_click(None)
    pagos.borrar_pago(app.con, pid)
    clic(d.lista.controls[0], "Sí, borrar")
    assert pagina.avisos()[-1] == "Ese pago ya no existe."
    assert _filas_ver(d) == [["Todavía no hay pagos registrados."]]
    assert d.dialogo.open is True


def test_ver_pagos_de_un_gasto_borrado_por_detras(app, pantalla, pagina):
    gid = _agregar(app, "Nafta", 3000000)
    gastos.borrar_gasto(app.con, gid)
    item_menu(pantalla, "Nafta", "Ver pagos").on_click(None)
    assert app.hay_dialogo_abierto() is False
    assert pagina.avisos()[-1] == "Ese gasto ya no existe."


def test_cerrar_ver_pagos(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_ver(app, pantalla, "Nafta")
    clic(d.dialogo, "Cerrar")
    assert d.dialogo.open is False
    assert app.hay_dialogo_abierto() is False


def test_error_inesperado_al_borrar_un_pago(app, pantalla, monkeypatch):
    gid = _agregar(app, "Nafta", 3000000)
    pagos.registrar_pago(app.con, gid, 100000, HOY)
    app.refrescar()
    d = _abrir_ver(app, pantalla, "Nafta")

    def falla(*args, **kwargs):
        raise RuntimeError("falla inventada")

    monkeypatch.setattr(pagos, "borrar_pago", falla)
    de_tipo(d.lista.controls[0], ft.IconButton)[0].on_click(None)
    clic(d.lista.controls[0], "Sí, borrar")
    assert d.dialogo.open is False
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


def test_borrar_gasto_con_pagos_dice_cuanto_se_pago(app, pantalla):
    # Confirmación de borrado (CA-08.1) con pagos registrados por la pantalla.
    _agregar(app, "Seguro de moto", 18000000)
    _pagar(app, pantalla, "Seguro de moto", "60.000")
    item_menu(pantalla, "Seguro de moto", "Borrar").on_click(None)
    assert any("($ 60.000 pagado)" in t for t in textos(dialogo_arriba(app)))


def _falla(*args, **kwargs):
    raise RuntimeError("falla inventada")


def test_error_inesperado_al_marcar_el_tilde(app, pantalla, monkeypatch):
    _agregar(app, "Nafta", 3000000)
    monkeypatch.setattr(pagos, "marcar_pagado", _falla)
    _clic_tilde(pantalla, "Nafta")
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


def test_error_inesperado_al_quitar_pagos(app, pantalla, monkeypatch, pagina):
    _dos_parciales(app)
    _clic_tilde(pantalla, "Seguro de moto")
    monkeypatch.setattr(pagos, "quitar_pagos", _falla)
    clic(dialogo_arriba(app), "Quitar pagos")
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"
    assert "Se quitaron los pagos de Seguro de moto" not in pagina.avisos()


# ---------------------------------------------------------------------------
# Ronda 10: BUG-10 (tabla refrescada) y O24 (el calendario se cierra al elegir)
# ---------------------------------------------------------------------------


def test_bug10_quitar_pagos_de_un_gasto_borrado_refresca_la_tabla(
    app, pantalla, pagina
):
    gid = _dos_parciales(app)
    _agregar(app, "Nafta", 3000000)
    _clic_tilde(pantalla, "Seguro de moto")
    gastos.borrar_gasto(app.con, gid)
    clic(dialogo_arriba(app), "Quitar pagos")
    assert pagina.avisos()[-1] == "El gasto ya no existe."
    assert [f["Nombre"] for f in filas_tabla(pantalla)[:-1]] == ["Nafta"]
    assert app.hay_dialogo_abierto() is False


def _abrir_calendario(app, d):
    [boton_cal] = [
        b
        for b in de_tipo(d.dialogo, ft.IconButton)
        if b.icon == ft.Icons.CALENDAR_MONTH
    ]
    boton_cal.on_click(None)
    assert app._dialogos == [d.dialogo, d.calendario]


@pytest.mark.parametrize(
    "valor",
    [datetime(2026, 10, 1, 15, 30), date(2026, 10, 1)],  # noqa: DTZ001
    ids=["datetime", "date"],
)
def test_o24_elegir_fecha_cierra_el_calendario(app, pantalla, valor):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    _abrir_calendario(app, d)
    d.calendario.value = valor
    d.calendario.on_change(None)
    assert d.texto_fecha.value == "01/10/2026"
    assert d.calendario.open is False
    assert app._dialogos == [d.dialogo]  # solo queda "Registrar pago"


def test_o24_despues_de_elegir_el_primer_esc_cierra_el_pago(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    _abrir_calendario(app, d)
    d.calendario.value = datetime(2026, 10, 1, 9, 0)  # noqa: DTZ001
    d.calendario.on_change(None)
    app._al_presionar_tecla(tecla("Escape"))
    assert d.dialogo.open is False
    assert app.hay_dialogo_abierto() is False


def test_o24_sin_dialogos_ctrl_n_vuelve_a_andar(app, pantalla):
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    _abrir_calendario(app, d)
    d.calendario.value = date(2026, 10, 2)
    d.calendario.on_change(None)
    app._al_presionar_tecla(tecla("Escape"))
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo gasto – Octubre 2026"


def test_o24_si_despues_llega_on_dismiss_no_rompe_nada(app, pantalla):
    # Si Flet igual avisa el cierre, no saca a "Registrar pago" de la lista.
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    _abrir_calendario(app, d)
    d.calendario.value = date(2026, 10, 2)
    d.calendario.on_change(None)
    d.calendario.on_dismiss(None)
    d.calendario.on_dismiss(None)
    assert app._dialogos == [d.dialogo]
    assert d.dialogo.open is True


def test_o24_elegir_fecha_dos_veces_seguidas(app, pantalla):
    gid = _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    for valor, texto in [
        (datetime(2026, 10, 1, 8, 0), "01/10/2026"),  # noqa: DTZ001
        (date(2026, 9, 15), "15/09/2026"),
    ]:
        _abrir_calendario(app, d)
        d.calendario.value = valor
        d.calendario.on_change(None)
        assert d.texto_fecha.value == texto
        assert app._dialogos == [d.dialogo]
    d.monto.value = "1.000"
    d._guardar()
    assert pagos.listar_pagos(app.con, gid)[0]["fecha"] == "2026-09-15"
    assert app.hay_dialogo_abierto() is False


def test_o24_cancelar_el_calendario_por_on_dismiss(app, pantalla):
    # Si se cierra el calendario sin elegir (Flet avisa con on_dismiss), la fecha
    # no cambia y queda solo "Registrar pago".
    _agregar(app, "Nafta", 3000000)
    d = _abrir_pago(app, pantalla, "Nafta")
    _abrir_calendario(app, d)
    d.calendario.on_dismiss(None)
    assert d.texto_fecha.value == "04/10/2026"
    assert app._dialogos == [d.dialogo]
