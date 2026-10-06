"""Pruebas de la interfaz del historial de meses (paso 4a): selector de mes, flechas,
Alt+←/→, franja de mes pasado/futuro, "Mes nuevo" (Ctrl/Cmd+Shift+N), "Borrar este mes",
O17 y despues_de_borrar_mes (diseno.md §1.2, §1.3, §3.9). Página falsa, sin ventanas.

"Hoy" se fija en octubre 2026 reemplazando meses.mes_actual_calendario: de eso dependen
el mes con el que arranca la app, el "· mes actual" del selector y la franja."""

from datetime import date
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.logica import (
    base_datos,
    cambios,
    catalogos,
    cuotas,
    gastos,
    ingresos,
    me_deben,
    meses,
    pagos,
)
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    boton,
    clic,
    de_tipo,
    dialogo_arriba,
    dialogo_gasto_abierto,
    hay_boton,
    ir,
    mes_seleccionado,
    nombre_visible,
    recorrer,
    tecla,
    textos,
    titulo_dialogo,
)

HOY = date(2026, 10, 4)
PENDIENTE = "#9A5800"
NEGATIVO = "#B3261E"


def _fijar_hoy(monkeypatch, anio, mes):
    original = meses.mes_actual_calendario

    def falso(hoy=None):
        return (anio, mes) if hoy is None else original(hoy)

    monkeypatch.setattr(meses, "mes_actual_calendario", falso)


@pytest.fixture(autouse=True)
def hoy_octubre(monkeypatch):
    _fijar_hoy(monkeypatch, 2026, 10)


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _crear_meses(con):
    """2026-09, 2026-10 y 2026-11 (S 1.200; K 1.550, 1.600 y 1.650)."""
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 155000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    nov = meses.crear_mes_siguiente(con, 120000, 165000)
    return sep, oct_, nov


def _app(con, plataforma=ft.PagePlatform.WINDOWS):
    pagina = PaginaFalsa(plataforma=plataforma)
    app = Aplicacion(pagina, con)
    app.iniciar()
    return app, pagina


@pytest.fixture
def tres(con):
    """App con septiembre, octubre y noviembre de 2026; arranca en octubre (hoy)."""
    sep, oct_, nov = _crear_meses(con)
    app, pagina = _app(con)
    return SimpleNamespace(app=app, pagina=pagina, sep=sep, oct=oct_, nov=nov)


def _opciones(app):
    return [o.text for o in app._selector_mes.options]


def _elegir_en_el_selector(app, mes_id):
    app._selector_mes.value = str(mes_id)
    app._selector_mes.on_select(SimpleNamespace(control=app._selector_mes))


# ---------------------------------------------------------------------------
# Arranque, selector y franja (§1.2)
# ---------------------------------------------------------------------------


def test_arranca_en_el_mes_del_calendario(tres):
    app = tres.app
    assert app.mes_id == tres.oct
    assert app.page.title == "Gastos – Octubre 2026"
    assert mes_seleccionado(app) == "Octubre 2026"
    assert _opciones(app) == [
        "Noviembre 2026",
        "Octubre 2026 · mes actual",
        "Septiembre 2026",
    ]
    assert [o.key for o in app._selector_mes.options] == [
        str(tres.nov),
        str(tres.oct),
        str(tres.sep),
    ]
    assert app._selector_mes.width == 260
    assert app._franja.visible is False
    assert nombre_visible(app) == "Resumen"


def test_si_el_mes_del_calendario_no_existe_arranca_en_el_ultimo(con, monkeypatch):
    _fijar_hoy(monkeypatch, 2027, 3)
    _crear_meses(con)
    app, _ = _app(con)
    assert mes_seleccionado(app) == "Noviembre 2026"
    assert not any("mes actual" in t for t in _opciones(app))
    assert app._franja.visible is True
    assert app._texto_franja.value == (
        "Estás viendo Noviembre 2026. Los cambios que hagas se guardan en ese mes."
    )


def test_franja_al_ver_un_mes_que_no_es_el_actual(tres):
    app = tres.app
    _elegir_en_el_selector(app, tres.sep)
    assert app.mes_id == tres.sep
    assert app.page.title == "Gastos – Septiembre 2026"
    assert app._franja.visible is True
    assert app._texto_franja.value == (
        "Estás viendo Septiembre 2026. Los cambios que hagas se guardan en ese mes."
    )
    assert app.pantalla("Resumen").titulo.value == "Resumen de Septiembre 2026"
    assert (
        app._texto_cotizacion.value == "Cotización $ 1.550 por US$"
    )  # la de septiembre
    _elegir_en_el_selector(app, tres.oct)
    assert app._franja.visible is False


def test_franja_tiene_el_color_info(tres):
    assert tres.app._franja.bgcolor == "#E3EFF4"  # info suave, tema claro
    assert tres.app._texto_franja.color == "#1F5F7A"


def test_seleccionar_otro_mes_mantiene_la_pantalla(tres):
    app = tres.app
    gastos.agregar_gasto(
        app.con, tres.sep, "Solo de septiembre", _otros(app.con), 100, "fijo"
    )
    pantalla_gastos = ir(app, "Gastos")
    _elegir_en_el_selector(app, tres.sep)
    assert nombre_visible(app) == "Gastos"
    assert pantalla_gastos.titulo.value == "Gastos de Septiembre 2026"
    assert "Solo de septiembre" in textos(pantalla_gastos.cuerpo)


def test_ca_02_1_cada_mes_muestra_sus_datos(tres):
    app = tres.app
    ingresos.agregar_ingreso(app.con, tres.sep, "Bono de septiembre", "ARS", 10000000)
    _elegir_en_el_selector(app, tres.sep)
    resumen = app.pantalla("Resumen")
    assert "Bono de septiembre" in textos(resumen.cuerpo)
    _elegir_en_el_selector(app, tres.oct)
    assert "Bono de septiembre" not in textos(resumen.cuerpo)


def test_seleccionar_mes_con_pantalla(tres):
    app = tres.app
    ir(app, "Ajustes")
    app.seleccionar_mes(tres.nov, pantalla="Gastos")
    assert (nombre_visible(app), mes_seleccionado(app)) == ("Gastos", "Noviembre 2026")


# ---------------------------------------------------------------------------
# Flechas y Alt+←/→ (§1.2, §1.3)
# ---------------------------------------------------------------------------


def test_flechas_en_el_mes_del_medio(tres):
    app = tres.app
    assert app._boton_anterior.icon == ft.Icons.CHEVRON_LEFT
    assert app._boton_siguiente.icon == ft.Icons.CHEVRON_RIGHT
    assert app._boton_anterior.tooltip == "Mes anterior (Alt+←)"
    assert app._boton_siguiente.tooltip == "Mes siguiente (Alt+→)"
    assert (app._boton_anterior.disabled, app._boton_siguiente.disabled) == (
        False,
        False,
    )


def test_flechas_en_los_extremos(tres):
    app = tres.app
    app._boton_anterior.on_click(None)
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert (app._boton_anterior.disabled, app._boton_siguiente.disabled) == (
        True,
        False,
    )
    app._boton_siguiente.on_click(None)
    app._boton_siguiente.on_click(None)
    assert mes_seleccionado(app) == "Noviembre 2026"
    assert (app._boton_anterior.disabled, app._boton_siguiente.disabled) == (
        False,
        True,
    )


def test_con_un_solo_mes_las_dos_flechas_estan_deshabilitadas(app):
    assert (app._boton_anterior.disabled, app._boton_siguiente.disabled) == (True, True)


@pytest.mark.parametrize("izquierda", ["Arrow Left", "ArrowLeft"])
@pytest.mark.parametrize("derecha", ["Arrow Right", "ArrowRight"])
def test_alt_flechas_cambian_de_mes(tres, izquierda, derecha):
    app = tres.app
    app._al_presionar_tecla(tecla(izquierda, alt=True))
    assert mes_seleccionado(app) == "Septiembre 2026"
    app._al_presionar_tecla(
        tecla(izquierda, alt=True)
    )  # ya es el primero: no pasa nada
    assert mes_seleccionado(app) == "Septiembre 2026"
    app._al_presionar_tecla(tecla(derecha, alt=True))
    app._al_presionar_tecla(tecla(derecha, alt=True))
    app._al_presionar_tecla(tecla(derecha, alt=True))  # ya es el último
    assert mes_seleccionado(app) == "Noviembre 2026"


def test_flechas_sin_alt_o_con_ctrl_no_cambian_de_mes(tres):
    app = tres.app
    app._al_presionar_tecla(tecla("Arrow Left"))
    app._al_presionar_tecla(tecla("Arrow Left", ctrl=True))
    assert mes_seleccionado(app) == "Octubre 2026"


def test_alt_flecha_con_un_dialogo_abierto_se_ignora(tres):
    app = tres.app
    app.editar_cotizacion()
    app._al_presionar_tecla(tecla("Arrow Left", alt=True))
    assert mes_seleccionado(app) == "Octubre 2026"


def test_alt_flecha_en_macos(con):
    _crear_meses(con)
    app, _ = _app(con, ft.PagePlatform.MACOS)
    app._al_presionar_tecla(tecla("Arrow Right", alt=True))
    assert mes_seleccionado(app) == "Noviembre 2026"


def test_alt_flecha_cruzando_el_anio(con, monkeypatch):
    _fijar_hoy(monkeypatch, 2027, 1)
    meses.crear_primer_mes(con, 2026, 12, 120000, 160000)
    meses.crear_mes_siguiente(con, 120000, 160000)
    app, _ = _app(con)
    assert mes_seleccionado(app) == "Enero 2027"
    app._al_presionar_tecla(tecla("Arrow Left", alt=True))
    assert mes_seleccionado(app) == "Diciembre 2026"


# ---------------------------------------------------------------------------
# Botón "Mes nuevo" y menú "Borrar este mes" (§1.2)
# ---------------------------------------------------------------------------


def test_boton_mes_nuevo(tres):
    assert tres.app._boton_mes_nuevo.content == "Mes nuevo"
    assert tres.app._boton_mes_nuevo.tooltip == "Crear Diciembre 2026 (Ctrl+Shift+N)"


def test_tooltip_mes_nuevo_en_macos(con):
    _crear_meses(con)
    app, _ = _app(con, ft.PagePlatform.MACOS)
    assert app._boton_mes_nuevo.tooltip == "Crear Diciembre 2026 (⇧⌘N)"  # O34


def test_borrar_este_mes_solo_en_el_ultimo(tres):
    app = tres.app
    item = app._item_borrar_mes
    assert app._menu_mes.tooltip == "Más opciones"
    assert (item.disabled, item.content) == (
        True,
        "Solo se puede borrar el último mes (Noviembre 2026)",
    )
    _elegir_en_el_selector(app, tres.nov)
    assert (item.disabled, item.content) == (False, "Borrar este mes")


# ---------------------------------------------------------------------------
# Diálogo "Mes nuevo" (§3.9, CA-03.x)
# ---------------------------------------------------------------------------


def _dialogo_mes_nuevo(app):
    return boton(dialogo_arriba(app), "Crear mes").on_click.__self__


def _con_fijos(app, mes_id, en_dolares=1):
    con = app.con
    gastos.agregar_gasto(con, mes_id, "Alquiler", _otros(con), 26000000, "fijo")
    gastos.agregar_gasto(con, mes_id, "Regalo", _otros(con), 1500000, "unico")
    for i in range(en_dolares):
        gastos.agregar_gasto(
            con,
            mes_id,
            f"Sub {i}",
            _otros(con),
            None,
            "fijo",
            None,
            "USD",
            2000,
            160000,
        )


def test_dialogo_mes_nuevo_contenido(tres):
    app = tres.app
    _con_fijos(app, tres.nov)
    app._boton_mes_nuevo.on_click(None)
    d = _dialogo_mes_nuevo(app)
    assert titulo_dialogo(d.dialogo) == "Crear Diciembre 2026"
    assert (d.sueldo.value, d.cotizacion.value) == ("1.200", "1.650")
    assert d.sueldo.autofocus is True
    assert d.cotizacion.suffix == "por US$"
    contenido = textos(d.dialogo)
    for texto in [
        "Solo se puede crear el mes siguiente al último.",
        "Sugeridos del mes anterior. Podés cambiarlos.",
        "Se va a copiar de Noviembre 2026:",
        "• 2 gastos fijos, sin pagos",
        "  (1 en dólares: se pasan a pesos con la cotización de arriba)",
        "No se copian pagos únicos, ingresos extra ni cambios.",
    ]:
        assert texto in contenido, texto
    assert hay_boton(d.dialogo, "Cancelar")


def test_dialogo_mes_nuevo_sin_fijos_en_dolares_ni_singular(tres):
    app = tres.app
    gastos.agregar_gasto(app.con, tres.nov, "Alquiler", _otros(app.con), 100, "fijo")
    app.crear_mes_nuevo()
    contenido = textos(_dialogo_mes_nuevo(app).dialogo)
    assert "• 1 gasto fijo, sin pagos" in contenido
    assert not any("en dólares" in t for t in contenido)


@pytest.mark.parametrize(
    ("cantidad", "texto"),
    [
        (
            1,
            "  Sin cotización, el gasto en dólares conserva la cotización con la que se cargó.",
        ),
        (
            2,
            (
                "  Sin cotización, los 2 gastos en dólares conservan la cotización "
                "con la que se cargaron."
            ),
        ),
    ],
)
def test_dialogo_mes_nuevo_sin_cotizacion_avisa_rn_57(tres, cantidad, texto):
    app = tres.app
    _con_fijos(app, tres.nov, en_dolares=cantidad)
    app.crear_mes_nuevo()
    d = _dialogo_mes_nuevo(app)
    d.cotizacion.value = ""
    d.cotizacion.on_change(None)
    assert (d.aviso_dolares.value, d.aviso_dolares.color) == (texto, PENDIENTE)
    d.cotizacion.value = "1.700"
    d.cotizacion.on_change(None)
    assert d.aviso_dolares.value == (
        f"  ({cantidad} en dólares: se pasan a pesos con la cotización de arriba)"
    )


def test_crear_mes_desde_el_dialogo(tres):
    app, pagina = tres.app, tres.pagina
    _con_fijos(app, tres.nov)
    ir(app, "Gastos")
    app._al_presionar_tecla(tecla("N", ctrl=True, shift=True))
    d = _dialogo_mes_nuevo(app)
    d.sueldo.value = "1.300"  # CA-03.2: se pueden cambiar antes de confirmar
    d.cotizacion.value = "1.700"
    clic(d.dialogo, "Crear mes")
    assert d.dialogo.open is False
    nuevo = meses.obtener_ultimo_mes(app.con)
    assert (nuevo["anio"], nuevo["mes"]) == (2026, 12)
    assert (nuevo["sueldo_usd_cent"], nuevo["cotizacion_cent"]) == (130000, 170000)
    # Se selecciona el mes nuevo y se muestra el Resumen.
    assert app.mes_id == nuevo["id"]
    assert (nombre_visible(app), mes_seleccionado(app)) == ("Resumen", "Diciembre 2026")
    assert _opciones(app)[0] == "Diciembre 2026"
    assert pagina.avisos()[-1] == "Diciembre 2026 creado: 2 gastos fijos."
    copiados = {g["nombre"]: g for g in gastos.listar_gastos(app.con, nuevo["id"])}
    assert list(copiados) == ["Alquiler", "Sub 0"]
    assert copiados["Sub 0"]["monto_cent"] == 3400000  # US$ 20 × 1.700
    assert app._franja.visible is True  # diciembre no es el mes actual (octubre)
    assert app._boton_mes_nuevo.tooltip == "Crear Enero 2027 (Ctrl+Shift+N)"


def test_crear_mes_estando_en_un_mes_viejo_crea_el_siguiente_al_ultimo(tres):
    app = tres.app
    _elegir_en_el_selector(app, tres.sep)
    app.crear_mes_nuevo()
    assert titulo_dialogo(dialogo_arriba(app)) == "Crear Diciembre 2026"


def test_crear_mes_en_macos_con_cmd_shift_n(con):
    _crear_meses(con)
    app, _ = _app(con, ft.PagePlatform.MACOS)
    app._al_presionar_tecla(tecla("N", ctrl=True, shift=True))
    assert app.hay_dialogo_abierto() is False
    app._al_presionar_tecla(tecla("N", meta=True, shift=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Crear Diciembre 2026"


def test_ctrl_n_sin_shift_sigue_siendo_nuevo_de_la_pantalla(tres):
    app = tres.app
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Registrar cambio de dólares"


def test_ctrl_shift_n_con_un_dialogo_abierto_se_ignora(tres):
    app = tres.app
    app.editar_cotizacion()
    app._al_presionar_tecla(tecla("N", ctrl=True, shift=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Cotización de Octubre 2026"
    assert len(app._dialogos) == 1


def test_cancelar_el_mes_nuevo(tres):
    app = tres.app
    app.crear_mes_nuevo()
    clic(dialogo_arriba(app), "Cancelar")
    assert len(meses.listar_meses(app.con)) == 3
    assert app.hay_dialogo_abierto() is False


def test_enter_en_el_sueldo_crea_el_mes(tres):
    app = tres.app
    app.crear_mes_nuevo()
    _dialogo_mes_nuevo(app).sueldo.on_submit(None)
    assert len(meses.listar_meses(app.con)) == 4


def test_crear_mes_sin_cotizacion_y_sueldo_cero(tres):
    app = tres.app
    app.crear_mes_nuevo()
    d = _dialogo_mes_nuevo(app)
    d.sueldo.value = "0"
    d.cotizacion.value = ""
    clic(d.dialogo, "Crear mes")
    nuevo = meses.obtener_ultimo_mes(app.con)
    assert (nuevo["sueldo_usd_cent"], nuevo["cotizacion_cent"]) == (0, None)
    assert app._texto_cotizacion.value == "Cotización sin cargar – Cargar"
    assert "El sueldo de este mes es 0." in textos(app.pantalla("Resumen").cuerpo)


@pytest.mark.parametrize(
    ("sueldo", "cotizacion", "campo", "mensaje"),
    [
        ("", "1.600", "sueldo", "Ingresá el sueldo. Si este mes no cobrás, poné 0."),
        ("abc", "1.600", "sueldo", "Escribí solo números. Ej.: 66.020,12"),
        ("-5", "1.600", "sueldo", "El sueldo no puede ser negativo."),
        ("1.200", "0", "cotizacion", "La cotización tiene que ser mayor a 0."),
        (
            "1.200",
            "1600.5",
            "cotizacion",
            "Usá coma para los decimales. Ej.: 66.020,12",
        ),
    ],
)
def test_errores_del_mes_nuevo(tres, sueldo, cotizacion, campo, mensaje):
    app, pagina = tres.app, tres.pagina
    app.crear_mes_nuevo()
    d = _dialogo_mes_nuevo(app)
    d.sueldo.value, d.cotizacion.value = sueldo, cotizacion
    clic(d.dialogo, "Crear mes")
    assert getattr(d, campo).error == mensaje
    assert d.dialogo.open is True
    assert pagina.tareas[-1].__self__ is getattr(d, campo)
    assert len(meses.listar_meses(app.con)) == 3


def test_bug15_desde_el_dialogo(tres):
    # Un fijo de US$ 0,01 a $ 1,00 con la cotización nueva $ 0,40 da $ 0: el error
    # queda en el campo cotización, el diálogo sigue abierto y no se crea el mes.
    app, pagina = tres.app, tres.pagina
    gastos.agregar_gasto(
        app.con, tres.nov, "Prueba", _otros(app.con), None, "fijo", None, "USD", 1, 100
    )
    app.crear_mes_nuevo()
    d = _dialogo_mes_nuevo(app)
    d.cotizacion.value = "0,40"
    clic(d.dialogo, "Crear mes")
    assert d.cotizacion.error == (
        'Con esta cotización, el gasto "Prueba" en dólares da $ 0. Revisá la cotización.'
    )
    assert d.dialogo.open is True
    assert pagina.tareas[-1].__self__ is d.cotizacion
    assert len(meses.listar_meses(app.con)) == 3
    d.cotizacion.value = "1.000"  # $ 0,10: ya da más que 0
    clic(d.dialogo, "Crear mes")
    assert len(meses.listar_meses(app.con)) == 4


def test_mes_creado_por_detras_cierra_y_avisa(tres):
    app, pagina = tres.app, tres.pagina
    app.crear_mes_nuevo()
    d = _dialogo_mes_nuevo(app)
    meses.crear_mes_siguiente(app.con, 120000)  # alguien creó diciembre por otro lado
    clic(d.dialogo, "Crear mes")
    assert d.dialogo.open is False
    assert (
        pagina.avisos()[-1]
        == "Solo se puede crear el mes siguiente al último (01/2027)."
    )
    assert len(meses.listar_meses(app.con)) == 4


def test_error_inesperado_al_crear_el_mes(tres, monkeypatch):
    app = tres.app

    def falla(*args, **kwargs):
        raise RuntimeError("falla inventada")

    app.crear_mes_nuevo()
    monkeypatch.setattr(meses, "crear_mes", falla)
    clic(dialogo_arriba(app), "Crear mes")
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


# ---------------------------------------------------------------------------
# Borrar el último mes (§3.9, CA-05.1, CA-05.3)
# ---------------------------------------------------------------------------


def _con_datos(app, mes_id):
    con = app.con
    a = gastos.agregar_gasto(con, mes_id, "Alquiler", _otros(con), 26000000, "fijo")
    b = gastos.agregar_gasto(con, mes_id, "Nafta", _otros(con), 3000000, "unico")
    gastos.agregar_gasto(con, mes_id, "Internet", _otros(con), 3870000, "fijo")
    pagos.marcar_pagado(con, a, HOY)
    pagos.registrar_pago(con, b, 100000, HOY)
    ingresos.agregar_ingreso(con, mes_id, "Bono", "ARS", 100)
    cambios.agregar_cambio(con, mes_id, 100, 150000, fecha=HOY)


def test_confirmacion_de_borrar_mes(tres):
    app = tres.app
    _con_datos(app, tres.nov)
    _elegir_en_el_selector(app, tres.nov)
    app._item_borrar_mes.on_click(None)
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Borrar Noviembre 2026?"
    explicacion = confirmacion.content.value
    assert "Se borran 3 gastos, 2 pagos, 1 ingreso extra" in explicacion
    assert (
        'No se borran los planes de cuotas ni los ítems cargados a mano en "Me deben". '
        "Esta acción no se puede deshacer." in explicacion
    )
    assert boton(confirmacion, "Cancelar").autofocus is True
    assert boton(confirmacion, "Borrar mes").style.bgcolor == NEGATIVO


def test_confirmacion_de_borrar_mes_como_en_el_diseno(tres):
    # §3.9: "Se borran 23 gastos, 15 pagos, 2 ingresos extra y 1 cambio de este mes."
    app = tres.app
    _con_datos(app, tres.nov)
    _elegir_en_el_selector(app, tres.nov)
    app._item_borrar_mes.on_click(None)
    assert dialogo_arriba(app).content.value.startswith(
        "Se borran 3 gastos, 2 pagos, 1 ingreso extra y 1 cambio de este mes."
    )


def test_cancelar_no_borra_el_mes(tres):
    app = tres.app
    _elegir_en_el_selector(app, tres.nov)
    app._item_borrar_mes.on_click(None)
    clic(dialogo_arriba(app), "Cancelar")
    assert meses.obtener_mes(app.con, tres.nov) is not None


def test_ca_05_1_borrar_el_ultimo_selecciona_el_nuevo_ultimo(tres):
    app, pagina = tres.app, tres.pagina
    _con_datos(app, tres.nov)
    ir(app, "Gastos")
    _elegir_en_el_selector(app, tres.nov)
    app._item_borrar_mes.on_click(None)
    clic(dialogo_arriba(app), "Borrar mes")
    assert meses.obtener_mes(app.con, tres.nov) is None
    assert app.mes_id == tres.oct
    assert (nombre_visible(app), mes_seleccionado(app)) == ("Gastos", "Octubre 2026")
    assert _opciones(app) == ["Octubre 2026 · mes actual", "Septiembre 2026"]
    assert pagina.avisos()[-1] == "Noviembre 2026 borrado"
    assert (app._item_borrar_mes.disabled, app._boton_siguiente.disabled) == (
        False,
        True,
    )
    assert app._boton_mes_nuevo.tooltip == "Crear Noviembre 2026 (Ctrl+Shift+N)"


def test_borrar_un_mes_que_no_es_el_ultimo_no_borra(tres):
    # El ítem está deshabilitado; si igual llegara el clic, la lógica lo impide.
    app, pagina = tres.app, tres.pagina
    app._item_borrar_mes.on_click(None)
    clic(dialogo_arriba(app), "Borrar mes")
    assert meses.obtener_mes(app.con, tres.oct) is not None
    assert pagina.avisos()[-1] == "Solo se puede borrar el último mes."


def test_ca_05_3_borrar_y_volver_a_crear(tres):
    app = tres.app
    gastos.agregar_gasto(
        app.con, tres.oct, "Alquiler", _otros(app.con), 26000000, "fijo"
    )
    _elegir_en_el_selector(app, tres.nov)
    app._item_borrar_mes.on_click(None)
    clic(dialogo_arriba(app), "Borrar mes")
    app.crear_mes_nuevo()
    d = _dialogo_mes_nuevo(app)
    assert titulo_dialogo(d.dialogo) == "Crear Noviembre 2026"
    assert "Se va a copiar de Octubre 2026:" in textos(d.dialogo)
    clic(d.dialogo, "Crear mes")
    nov2 = meses.obtener_ultimo_mes(app.con)["id"]
    assert [g["nombre"] for g in gastos.listar_gastos(app.con, nov2)] == ["Alquiler"]


def test_borrar_todos_los_meses_vuelve_al_primer_uso(tres):
    app = tres.app
    for _ in range(3):
        ultimo = meses.obtener_ultimo_mes(app.con)["id"]
        _elegir_en_el_selector(app, ultimo)
        app._item_borrar_mes.on_click(None)
        clic(dialogo_arriba(app), "Borrar mes")
    assert meses.hay_meses(app.con) is False
    assert app.page.title == "Gastos – Bienvenido"
    assert app.mes_id is None
    assert app._pantallas == []
    # En el primer uso los atajos no hacen nada.
    for t in [
        tecla("N", ctrl=True, shift=True),
        tecla("K", ctrl=True),
        tecla("Arrow Left", alt=True),
    ]:
        app._al_presionar_tecla(t)
    assert app.hay_dialogo_abierto() is False


# ---------------------------------------------------------------------------
# O17: el mes que se veía se borró por detrás
# ---------------------------------------------------------------------------


def test_o17_gasto_con_el_mes_borrado_por_detras(tres):
    app, pagina = tres.app, tres.pagina
    _elegir_en_el_selector(app, tres.nov)
    ir(app, "Gastos")
    app.pantalla("Gastos").nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Nafta"
    d.categoria.value = str(_otros(app.con))
    d.monto.value = "30.000"
    meses.borrar_ultimo_mes(app.con, tres.nov)  # se borra por detrás
    d._guardar()
    assert d.dialogo.open is False
    assert pagina.avisos()[-1] == "El mes no existe."
    assert app.mes_id == tres.oct  # pasó al último que queda
    assert mes_seleccionado(app) == "Octubre 2026"
    assert gastos.listar_gastos(app.con, tres.oct) == []  # no se guardó en otro mes


def test_o17_refrescar_con_el_mes_borrado_va_al_ultimo(tres):
    app = tres.app
    _elegir_en_el_selector(app, tres.nov)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    app.refrescar()
    assert (app.mes_id, mes_seleccionado(app)) == (tres.oct, "Octubre 2026")


def test_o17_refrescar_sin_meses_va_al_primer_uso(app):
    meses.borrar_ultimo_mes(app.con, app.mes_id)
    app.refrescar()
    assert app.page.title == "Gastos – Bienvenido"
    assert app._pantallas == []


def test_o17_flecha_con_el_mes_borrado_por_detras(tres):
    # Alt+← con el mes que se veía ya borrado: no debería romper; pasa al último.
    app = tres.app
    _elegir_en_el_selector(app, tres.nov)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    app._al_presionar_tecla(tecla("Arrow Left", alt=True))
    assert app.mes_id in (tres.oct, tres.sep)


# ---------------------------------------------------------------------------
# Ronda 17: BUG-16 en cada punto de entrada, BUG-17 y O34
# ---------------------------------------------------------------------------


def _clic_cotizacion(app):
    app._cotizacion.on_click(None)


def _ctrl_k(app):
    app._al_presionar_tecla(tecla("K", ctrl=True))


def _alt_izquierda(app):
    app._al_presionar_tecla(tecla("Arrow Left", alt=True))


def _alt_derecha(app):
    app._al_presionar_tecla(tecla("ArrowRight", alt=True))


def _flecha_anterior(app):
    app._boton_anterior.on_click(None)


def _flecha_siguiente(app):
    app._boton_siguiente.on_click(None)


def _ctrl_n_en_gastos(app):
    app._al_presionar_tecla(tecla("N", ctrl=True))


def _boton_agregar_gasto(app):
    clic(app.pantalla("Gastos").control, "Agregar gasto")


def _ctrl_n_en_resumen(app):
    app._al_presionar_tecla(tecla("N", ctrl=True))


def _boton_registrar_cambio(app):
    clic(app.pantalla("Resumen").cuerpo, "Registrar cambio")


def _boton_agregar_ingreso(app):
    clic(app.pantalla("Resumen").cuerpo, "Agregar ingreso")


def _lapiz_del_sueldo(app):
    [lapiz] = [
        b
        for b in de_tipo(app.pantalla("Resumen").cuerpo, ft.IconButton)
        if b.tooltip == "Editar sueldo"
    ]
    lapiz.on_click(None)


def _cargar_cotizacion_de_la_tarjeta(app):
    # Botón "Cargar cotización" de las tarjetas (mes sin cotización).
    clic(app.pantalla("Resumen").cuerpo, "Cargar cotización")


ENTRADAS = {
    "flecha_anterior": _flecha_anterior,
    "flecha_siguiente": _flecha_siguiente,
    "alt_izquierda": _alt_izquierda,
    "alt_derecha": _alt_derecha,
    "clic_cotizacion": _clic_cotizacion,
    "ctrl_k": _ctrl_k,
    "ctrl_n_en_gastos": _ctrl_n_en_gastos,
    "boton_agregar_gasto": _boton_agregar_gasto,
    "ctrl_n_en_resumen": _ctrl_n_en_resumen,
    "boton_registrar_cambio": _boton_registrar_cambio,
    "boton_agregar_ingreso": _boton_agregar_ingreso,
    "lapiz_del_sueldo": _lapiz_del_sueldo,
}


# En qué pantalla está cada punto de entrada.
PANTALLA = {"ctrl_n_en_gastos": "Gastos", "boton_agregar_gasto": "Gastos"}


def _preparar(app, entrada):
    """Va a la pantalla de la entrada ANTES de borrar el mes (como en la vida real:
    la pantalla ya está a la vista cuando el mes se borra por detrás)."""
    ir(app, PANTALLA.get(entrada, "Resumen"))


@pytest.mark.parametrize("entrada", list(ENTRADAS))
def test_bug16_mes_borrado_por_detras_en_cada_entrada(tres, entrada):
    app, pagina = tres.app, tres.pagina
    _elegir_en_el_selector(app, tres.nov)
    _preparar(app, entrada)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    ENTRADAS[entrada](app)  # no tiene que lanzar excepción
    assert app.mes_id == tres.oct  # pasó al último que queda
    assert mes_seleccionado(app) == "Octubre 2026"
    assert pagina.avisos()[-1] == "El mes que estabas viendo ya no existe."
    assert app.hay_dialogo_abierto() is False


def test_bug16_cargar_cotizacion_de_la_tarjeta_con_el_mes_borrado(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    nov = meses.crear_mes_siguiente(con, 120000, None)
    app, pagina = _app(con)
    _elegir_en_el_selector(app, nov)
    _preparar(app, "cargar_cotizacion")
    meses.borrar_ultimo_mes(con, nov)
    _cargar_cotizacion_de_la_tarjeta(app)
    assert pagina.avisos()[-1] == "El mes que estabas viendo ya no existe."
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize(
    "entrada", ["flecha_anterior", "ctrl_k", "ctrl_n_en_resumen", "lapiz_del_sueldo"]
)
def test_bug16_sin_meses_va_al_primer_uso(app, entrada):
    # Con el único mes borrado por detrás: no rompe y vuelve al primer uso.
    pagina = app.page
    _preparar(app, entrada)
    meses.borrar_ultimo_mes(app.con, app.mes_id)
    ENTRADAS[entrada](app)
    assert app.page.title == "Gastos – Bienvenido"
    assert app._pantallas == []
    assert pagina.avisos()[-1] == "El mes que estabas viendo ya no existe."
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize(
    ("entrada", "titulo"),
    [
        ("clic_cotizacion", "Cotización de Noviembre 2026"),
        ("ctrl_k", "Cotización de Noviembre 2026"),
        ("ctrl_n_en_gastos", "Nuevo gasto – Noviembre 2026"),
        ("boton_agregar_gasto", "Nuevo gasto – Noviembre 2026"),
        ("ctrl_n_en_resumen", "Registrar cambio de dólares"),
        ("boton_registrar_cambio", "Registrar cambio de dólares"),
        ("boton_agregar_ingreso", "Nuevo ingreso extra"),
        ("lapiz_del_sueldo", "Sueldo de Noviembre 2026"),
    ],
)
def test_bug16_con_el_mes_existente_todo_sigue_igual(tres, entrada, titulo):
    app, pagina = tres.app, tres.pagina
    _elegir_en_el_selector(app, tres.nov)
    _preparar(app, entrada)
    avisos_antes = list(pagina.avisos())
    ENTRADAS[entrada](app)
    assert titulo_dialogo(dialogo_arriba(app)) == titulo
    assert app.mes_id == tres.nov
    assert pagina.avisos() == avisos_antes


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("flecha_anterior", "Octubre 2026"),
        ("alt_izquierda", "Octubre 2026"),
    ],
)
def test_bug16_flechas_con_el_mes_existente(tres, entrada, esperado):
    app, pagina = tres.app, tres.pagina
    _elegir_en_el_selector(app, tres.nov)
    ENTRADAS[entrada](app)
    assert mes_seleccionado(app) == esperado
    assert "El mes que estabas viendo ya no existe." not in pagina.avisos()


def test_bug16_verificar_mes(tres):
    app = tres.app
    assert app.verificar_mes() is True
    _elegir_en_el_selector(app, tres.nov)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    assert app.verificar_mes() is False
    assert app.mes_id == tres.oct
    assert app.verificar_mes() is True


# Otras entradas que dependen del mes (no estaban en la lista del arreglo).


def test_borrar_este_mes_con_el_mes_ya_borrado_por_detras(tres):
    app = tres.app
    _elegir_en_el_selector(app, tres.nov)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    app._item_borrar_mes.on_click(None)  # no tiene que lanzar excepción
    assert app.mes_id == tres.oct
    assert app.hay_dialogo_abierto() is False


def test_editar_un_cambio_con_el_mes_borrado_por_detras(tres):
    app = tres.app
    cambios.agregar_cambio(app.con, tres.nov, 100, 150000, fecha=HOY)
    _elegir_en_el_selector(app, tres.nov)
    tablas = de_tipo(app.pantalla("Resumen").cuerpo, ft.DataTable)
    editar = tablas[-1].rows[0].cells[5].content.items[0]
    meses.borrar_ultimo_mes(app.con, tres.nov)
    editar.on_click(None)  # no tiene que lanzar excepción
    assert app.mes_id == tres.oct
    assert app.hay_dialogo_abierto() is False


# --- BUG-17: confirmación con "y" ---


@pytest.mark.parametrize(
    ("datos", "texto"),
    [
        (
            "muchos",
            "Se borran 3 gastos, 2 pagos, 1 ingreso extra y 1 cambio de este mes.",
        ),
        (
            "vacio",
            "Se borran 0 gastos, 0 pagos, 0 ingresos extra y 0 cambios de este mes.",
        ),
    ],
)
def test_bug17_confirmacion_de_borrar_mes_texto_exacto(tres, datos, texto):
    app = tres.app
    if datos == "muchos":
        _con_datos(app, tres.nov)
    _elegir_en_el_selector(app, tres.nov)
    app._item_borrar_mes.on_click(None)
    assert dialogo_arriba(app).content.value == (
        f"{texto} No se borran los planes de cuotas ni los ítems cargados a mano en "
        '"Me deben". Esta acción no se puede deshacer.'
    )


# --- O34: atajos en los tooltips ---


@pytest.mark.parametrize(
    ("plataforma", "n", "k", "shift_n"),
    [
        (ft.PagePlatform.WINDOWS, "Ctrl+N", "Ctrl+K", "Ctrl+Shift+N"),
        (ft.PagePlatform.LINUX, "Ctrl+N", "Ctrl+K", "Ctrl+Shift+N"),
        (ft.PagePlatform.MACOS, "⌘N", "⌘K", "⇧⌘N"),
    ],
)
def test_o34_tooltips_segun_el_sistema(con, plataforma, n, k, shift_n):
    _crear_meses(con)
    app, _ = _app(con, plataforma)
    assert (app.atajo("N"), app.atajo("K"), app.atajo("N", shift=True)) == (
        n,
        k,
        shift_n,
    )
    assert app._cotizacion.tooltip == f"Editar la cotización ({k})"
    assert app._boton_mes_nuevo.tooltip == f"Crear Diciembre 2026 ({shift_n})"
    gastos_pantalla = ir(app, "Gastos")
    assert (
        boton(gastos_pantalla.control, "Agregar gasto").tooltip
        == f"Agregar gasto ({n})"
    )
    ajustes = ir(app, "Ajustes")
    assert (
        boton(ajustes.listas[0].control, "Nueva categoría").tooltip
        == f"Nueva categoría ({n})"
    )


# ---------------------------------------------------------------------------
# Ronda 18: BUG-18 (los 5 puntos de entrada que faltaban) e inventario
# ---------------------------------------------------------------------------


def _items_de_tabla(app, seccion):
    """Ítems del menú de la primera fila de la tabla de ingresos o de cambios."""
    resumen = app.pantalla("Resumen")
    for columna in resumen.cuerpo.controls:
        if isinstance(columna, ft.Column) and seccion in textos(columna.controls[0]):
            [tabla] = de_tipo(columna, ft.DataTable)
            return {i.content: i for i in de_tipo(tabla.rows[0], ft.PopupMenuItem)}
    raise AssertionError(seccion)


def _con_ingreso_y_cambio(app, mes_id):
    ingresos.agregar_ingreso(app.con, mes_id, "Bono", "ARS", 10000000)
    cambios.agregar_cambio(app.con, mes_id, 10000, 150000, fecha=HOY)


ENTRADAS_BUG18 = {
    "borrar_este_mes": lambda app: app._item_borrar_mes.on_click(None),
    "editar_ingreso": lambda app: _items_de_tabla(app, "INGRESOS EXTRA")[
        "Editar"
    ].on_click(None),
    "borrar_ingreso": lambda app: _items_de_tabla(app, "INGRESOS EXTRA")[
        "Borrar"
    ].on_click(None),
    "editar_cambio": lambda app: _items_de_tabla(app, "CAMBIOS DE DÓLARES REALIZADOS")[
        "Editar"
    ].on_click(None),
    "borrar_cambio": lambda app: _items_de_tabla(app, "CAMBIOS DE DÓLARES REALIZADOS")[
        "Borrar"
    ].on_click(None),
}

TITULOS_BUG18 = {
    "borrar_este_mes": "¿Borrar Noviembre 2026?",
    "editar_ingreso": "Editar ingreso extra",
    "borrar_ingreso": "¿Borrar el ingreso Bono?",
    "editar_cambio": "Editar cambio de dólares",
    "borrar_cambio": "¿Borrar el cambio del 04/10/2026?",
}


def _accion_preparada(app, entrada):
    """Devuelve la acción ya "agarrada" de la pantalla visible (como un clic en un
    control que está en pantalla), para dispararla después de borrar el mes."""
    if entrada == "borrar_este_mes":
        return app._item_borrar_mes.on_click
    seccion = (
        "INGRESOS EXTRA" if "ingreso" in entrada else "CAMBIOS DE DÓLARES REALIZADOS"
    )
    texto = "Editar" if entrada.startswith("editar") else "Borrar"
    return _items_de_tabla(app, seccion)[texto].on_click


@pytest.mark.parametrize("entrada", list(ENTRADAS_BUG18))
def test_bug18_mes_borrado_por_detras(tres, entrada):
    app, pagina = tres.app, tres.pagina
    _con_ingreso_y_cambio(app, tres.nov)
    _elegir_en_el_selector(app, tres.nov)
    accion = _accion_preparada(app, entrada)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    accion(None)  # no tiene que lanzar excepción
    assert app.mes_id == tres.oct
    assert mes_seleccionado(app) == "Octubre 2026"
    assert pagina.avisos()[-1] == "El mes que estabas viendo ya no existe."
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize("entrada", list(ENTRADAS_BUG18))
def test_bug18_sin_meses_va_al_primer_uso(app, entrada):
    pagina = app.page
    _con_ingreso_y_cambio(app, app.mes_id)
    ir(app, "Resumen")
    accion = _accion_preparada(app, entrada)
    meses.borrar_ultimo_mes(app.con, app.mes_id)
    accion(None)
    assert app.page.title == "Gastos – Bienvenido"
    assert app._pantallas == []
    assert pagina.avisos()[-1] == "El mes que estabas viendo ya no existe."
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize("entrada", list(ENTRADAS_BUG18))
def test_bug18_con_el_mes_existente_abre_lo_de_siempre(tres, entrada):
    app, pagina = tres.app, tres.pagina
    _con_ingreso_y_cambio(app, tres.nov)
    _elegir_en_el_selector(app, tres.nov)
    avisos_antes = list(pagina.avisos())
    ENTRADAS_BUG18[entrada](app)
    assert titulo_dialogo(dialogo_arriba(app)) == TITULOS_BUG18[entrada]
    assert app.mes_id == tres.nov
    assert pagina.avisos() == avisos_antes


# --- Inventario: ninguna acción visible rompe con el mes borrado por detrás ---


def _app_con_de_todo(pantalla):
    """App nueva (base en memoria) con tres meses; en Noviembre hay gastos (uno
    pagado, uno en dólares), un ingreso, un cambio, y sin meta; además, planes de
    cuotas activo (con cuota en Noviembre), que no empezó y cancelado (paso 4b).
    Muestra Noviembre."""
    con = base_datos.conectar(":memory:")
    _, oct_, nov = _crear_meses(con)
    otros = _otros(con)
    a = gastos.agregar_gasto(con, nov, "Alquiler", otros, 26000000, "fijo")
    gastos.agregar_gasto(con, nov, "Nafta", otros, 3000000, "unico")
    gastos.agregar_gasto(
        con, nov, "Claude", otros, None, "unico", None, "USD", 2000, 160000
    )
    pagos.marcar_pagado(con, a, HOY)
    _con_ingreso_y_cambio(SimpleNamespace(con=con), nov)
    cuotas.crear_plan(con, "Heladera", otros, None, 1000000, 6, 2026, 8, hoy=HOY)
    cuotas.crear_plan(con, "Futuro", otros, None, 1000000, 3, 2027, 3, hoy=HOY)
    cancelado = cuotas.crear_plan(
        con, "Moto", otros, None, 500000, 12, 2026, 8, hoy=HOY
    )
    cuotas.cancelar_plan(con, cancelado, hoy=HOY)
    # Paso 5: un gasto compartido en Noviembre y un ítem a mano en "Me deben".
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    gastos.agregar_gasto(
        con, nov, "Internet", otros, 3870000, "fijo", partes=[(sofia, None)]
    )
    me_deben.agregar_item(con, sofia, "Préstamo", 2000000, HOY)
    app, pagina = _app(con)
    app.seleccionar_mes(nov, pantalla=pantalla)
    return con, app, pagina, nov, oct_


_EVENTOS = ("on_click", "on_change", "on_select", "on_tap")


def _acciones_visibles(app):
    """Todos los handlers de clic/cambio/selección de lo que está en pantalla
    (barra superior, menú lateral, franja y la pantalla visible)."""
    acciones = []
    for control in recorrer(app.page.controls[0]):
        for evento in _EVENTOS:
            handler = getattr(control, evento, None)
            if callable(handler):
                acciones.append(
                    (type(control).__name__, _etiqueta_de(control), evento, control)
                )
    return acciones


def _etiqueta_de(control):
    for atributo in ("content", "tooltip", "label"):
        valor = getattr(control, atributo, None)
        if isinstance(valor, str):
            return valor
    return ""


def _disparar(control, evento):
    handler = getattr(control, evento)
    handler(SimpleNamespace(control=control, data=None))


MINIMO_DE_ACCIONES = {
    "Resumen": 15,
    "Gastos": 39,
    "Cuotas": 16,
    "Me deben": 13,
    "Previsión": 8,
    "Gráficos": 7,
    "Ajustes": 39,
}


def _fallas_del_inventario(pantalla):
    """Para cada acción visible: app nueva, mes borrado por detrás, disparar la acción.
    Devuelve la lista de fallas (vacía si todo anduvo) y cuántas acciones probó."""
    con, app, _, _, _ = _app_con_de_todo(pantalla)
    cantidad = len(_acciones_visibles(app))
    con.close()
    fallas = []
    for indice in range(cantidad):
        con, app, _, nov, _ = _app_con_de_todo(pantalla)
        tipo, etiqueta, evento, control = _acciones_visibles(app)[indice]
        meses.borrar_ultimo_mes(con, nov)
        try:
            _disparar(control, evento)
            # Después de la acción: o la app ya pasó a un mes que existe (o al primer
            # uso), o el usuario está en un diálogo que no depende del mes borrado
            # (ej. "Mes nuevo", que crea el siguiente al último que queda).
            # Ajustes y Me deben (acumulado) no dependen del mes: ahí alcanza con
            # que no haya excepción.
            if pantalla not in ("Ajustes", "Me deben"):
                existe = app.mes_id is None or meses.obtener_mes(con, app.mes_id)
                assert existe or app.hay_dialogo_abierto()
        except Exception as error:  # noqa: BLE001 (a propósito: se juntan todas las fallas)
            fallas.append(
                f"{tipo} {etiqueta!r} {evento}: {type(error).__name__}: {error}"
            )
        finally:
            con.close()
    return fallas, cantidad


@pytest.mark.parametrize(
    "pantalla",
    ["Resumen", "Gastos", "Cuotas", "Me deben", "Previsión", "Gráficos", "Ajustes"],
)
def test_inventario_ninguna_accion_rompe_con_el_mes_borrado(pantalla):
    fallas, cantidad = _fallas_del_inventario(pantalla)
    # Si alguien saca acciones de la pantalla, el inventario lo nota (y se revisa).
    assert cantidad >= MINIMO_DE_ACCIONES[pantalla]
    assert fallas == []


def test_el_inventario_detecta_una_accion_sin_proteccion(monkeypatch):
    # Prueba de la prueba: si verificar_mes no protegiera nada (como antes de BUG-16
    # y BUG-18), el inventario tiene que encontrar fallas en el Resumen.
    monkeypatch.setattr(Aplicacion, "verificar_mes", lambda self: True)
    fallas, _ = _fallas_del_inventario("Resumen")
    assert fallas, "El inventario no detectó acciones sin protección"
    assert any("Borrar este mes" in f for f in fallas)


def test_inventario_cubre_las_acciones_de_bug16_y_bug18():
    # El inventario realmente incluye las acciones protegidas (si no, no probaría nada).
    con, app, _, _, _ = _app_con_de_todo("Resumen")
    etiquetas = {etiqueta for _, etiqueta, _, _ in _acciones_visibles(app)}
    con.close()
    for esperada in [
        "Mes nuevo",
        "Borrar este mes",
        "Mes anterior (Alt+←)",
        "Mes siguiente (Alt+→)",
        "Editar la cotización (Ctrl+K)",
        "Registrar cambio",
        "Agregar ingreso",
        "Editar sueldo",
        "Editar",
        "Borrar",
    ]:
        assert esperada in etiquetas, esperada


def test_mes_nuevo_con_el_mes_visto_borrado_por_detras(tres):
    # "Mes nuevo" no depende del mes que se ve: ofrece el siguiente al último que
    # queda (Noviembre, porque se borró Noviembre) y al crearlo todo queda al día.
    app = tres.app
    _elegir_en_el_selector(app, tres.nov)
    meses.borrar_ultimo_mes(app.con, tres.nov)
    app._boton_mes_nuevo.on_click(None)
    d = _dialogo_mes_nuevo(app)
    assert titulo_dialogo(d.dialogo) == "Crear Noviembre 2026"
    assert "Se va a copiar de Octubre 2026:" in textos(d.dialogo)
    clic(d.dialogo, "Crear mes")
    nuevo = meses.obtener_ultimo_mes(app.con)
    assert (nuevo["anio"], nuevo["mes"]) == (2026, 11)
    assert app.mes_id == nuevo["id"]
    assert mes_seleccionado(app) == "Noviembre 2026"
