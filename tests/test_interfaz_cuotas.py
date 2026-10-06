"""Pruebas de la interfaz de cuotas (paso 4b): pantalla Cuotas, diálogo del plan, cuotas
en la pantalla Gastos ("Cuota n/N", editar, borrar), "Por medio de pago" y cuotas en
"Mes nuevo" (diseno.md §3.3, §3.4, §3.9, §4.2; CA-16.1, 17.x, 18.x, 19.x, 20.x, 21.1,
22.1, 08.2; BUG-19 y BUG-20). Página falsa, sin ventanas.

"Hoy" se fija en octubre 2026 reemplazando meses.mes_actual_calendario: de eso dependen
el filtro de planes, el aviso del diálogo y qué meses toca un plan."""

from datetime import date

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.logica import catalogos, cuotas, gastos, meses, pagos
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    boton,
    celda,
    clic,
    de_tipo,
    dialogo_arriba,
    filas_tabla,
    hay_boton,
    ir,
    item_menu,
    mes_seleccionado,
    nombre_visible,
    recorrer,
    tabla_por_medio,
    tecla,
    textos,
    titulo_dialogo,
)

HOY = date(2026, 10, 4)
POSITIVO = "#1E7B34"
SECUNDARIO = "onSurfaceVariant"


@pytest.fixture(autouse=True)
def hoy_octubre(monkeypatch):
    original = meses.mes_actual_calendario

    def falso(hoy=None):
        return (2026, 10) if hoy is None else original(hoy)

    monkeypatch.setattr(meses, "mes_actual_calendario", falso)


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _meses(con, desde, hasta):
    ids = {desde: meses.crear_primer_mes(con, *desde, 120000, 160000)}
    actual = desde
    while actual != hasta:
        actual = meses.siguiente(*actual)
        ids[actual] = meses.crear_mes(con, *actual, 120000, 160000)
    return ids


def _app(con, pantalla="Cuotas"):
    app = Aplicacion(PaginaFalsa(), con)
    app.iniciar()
    ir(app, pantalla)
    return app


def _plan(con, nombre="Plan", monto=1000000, cantidad=6, primera=(2026, 8), medio=None):
    return cuotas.crear_plan(
        con, nombre, _otros(con), medio, monto, cantidad, *primera, hoy=HOY
    )


@pytest.fixture
def oct_nov(con):
    """Meses 2026-09, 2026-10 y 2026-11 (hoy: octubre)."""
    return _meses(con, (2026, 9), (2026, 11))


# --- Lectura de la tabla de planes ---


def _tabla_planes(pantalla):
    tablas = de_tipo(pantalla.cuerpo, ft.DataTable)
    assert len(tablas) == 1, "No hay tabla de planes"
    return tablas[0]


def _texto(control):
    partes = [t.value for t in recorrer(control) if isinstance(t, ft.Text) and t.value]
    return " | ".join(partes) if partes else None


def _filas(pantalla):
    tabla = _tabla_planes(pantalla)
    titulos = [c.label.value for c in tabla.columns]
    return [
        dict(zip(titulos, (_texto(c.content) for c in f.cells), strict=True))
        for f in tabla.rows
    ]


def _fila_plan(pantalla, nombre):
    tabla = _tabla_planes(pantalla)
    for fila in tabla.rows:
        if _texto(fila.cells[0].content) == nombre:
            return fila
    raise AssertionError(nombre)


def _menu_plan(pantalla, nombre):
    return {i.content: i for i in _fila_plan(pantalla, nombre).cells[-1].content.items}


def _dialogo_plan(app):
    return boton(dialogo_arriba(app), "Guardar").on_click.__self__


def _completar(
    d,
    con,
    nombre="Avant Service",
    monto="41.116,66",
    cantidad="3",
    mes="8",
    anio="2026",
):
    d.nombre.value = nombre
    d.categoria.value = str(_otros(con))
    d.monto.value = monto
    d.cantidad.value = cantidad
    d.primer_mes.value = mes
    d.primer_anio.value = anio
    d._actualizar_vista_previa()


def _elegir_filtro(pantalla, valor):
    pantalla.filtro.selected = [valor]
    pantalla.filtro.on_change(None)


def _enfocado(app):
    return app.page.tareas[-1].__self__


# ---------------------------------------------------------------------------
# Navegación y estado vacío
# ---------------------------------------------------------------------------


def test_ctrl_3_va_a_cuotas_y_ctrl_n_abre_nuevo_plan(con, oct_nov):
    app = _app(con, "Resumen")
    app._al_presionar_tecla(tecla("3", ctrl=True))
    assert nombre_visible(app) == "Cuotas"
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo plan de cuotas"


def test_sin_planes_estado_vacio(con, oct_nov):
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    assert "Planes de cuotas" in textos(pantalla.control)
    assert "No tenés planes de cuotas cargados." in textos(pantalla.cuerpo)
    assert pantalla.filtro.visible is False
    clic(pantalla.cuerpo, "Nuevo plan")
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo plan de cuotas"


def test_subtitulo_y_tooltip_del_filtro(con, oct_nov):
    _plan(con)
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    assert (
        pantalla.subtitulo.value
        == "Cuota y restante calculados para Octubre 2026 (mes seleccionado)."
    )
    assert pantalla.filtro.tooltip == "Según el mes actual (Octubre 2026)"
    assert [s.label.value for s in pantalla.filtro.segments] == [
        "Activos (1)",
        "Terminados (0)",
        "Cancelados (0)",
    ]
    assert boton(pantalla.control, "Nuevo plan").tooltip == "Nuevo plan (Ctrl+N)"


# ---------------------------------------------------------------------------
# Diálogo del plan (§4.2) y alta (CA-16.1, CA-18.x)
# ---------------------------------------------------------------------------


def test_dialogo_nuevo_plan_valores_iniciales(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    contenido = textos(d.dialogo)
    assert (
        "Las cuotas se agregan desde el mes actual (Octubre 2026) y en los meses siguientes "
        "que ya existan. Los meses anteriores no se modifican." in contenido
    )
    assert "Las cuotas se cargan en pesos." in contenido
    assert d.nombre.autofocus is True
    assert (d.primer_mes.value, d.primer_anio.value) == ("10", "2026")
    assert d.medio.value == "ninguno"
    assert d.medio.options[0].text == "Sin medio de pago"
    assert d.monto.prefix == "$ "
    assert d.cantidad.input_filter.regex_string == "[0-9]"
    assert d.vista_previa.value == (
        "Completá el monto, la cantidad de cuotas y la primera cuota para ver el plan."
    )


def test_ca_16_1_alta_desde_el_dialogo(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con)
    assert d.vista_previa.value == (
        "Última cuota: Octubre 2026 · Total del plan: $ 123.350 · "
        "En Octubre 2026 (mes actual) va la cuota 3/3"
    )
    d._guardar()
    assert d.dialogo.open is False
    assert (
        app.page.avisos()[-1] == "Plan creado. Se agregó la cuota 3/3 en Octubre 2026."
    )
    [fila] = _filas(app.pantalla("Cuotas"))[:-1]
    assert fila["Nombre"] == "Avant Service"
    assert fila["Medio"] == "—"
    assert (fila["Cuota"], fila["Cuota del mes"]) == ("$ 41.117", "3/3")
    assert (fila["Primera"], fila["Última"], fila["Restante"]) == (
        "ago 2026",
        "oct 2026",
        "$ 0",
    )
    # En Gastos aparece la cuota con "Cuota 3/3".
    ir(app, "Gastos")
    gasto = next(
        f for f in filas_tabla(app.pantalla("Gastos")) if f["Nombre"] == "Avant Service"
    )
    assert (gasto["Tipo"], gasto["Monto"]) == ("Cuota 3/3", "$ 41.117")


@pytest.mark.parametrize(
    ("mes", "anio", "cantidad", "fin"),
    [
        ("12", "2026", "12", "todavía no empezó"),
        ("1", "2026", "3", "ya terminó"),
        ("3", "2026", "12", "va la cuota 8/12"),
    ],
)
def test_vista_previa(con, oct_nov, mes, anio, cantidad, fin):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con, monto="10.000", cantidad=cantidad, mes=mes, anio=anio)
    assert d.vista_previa.value.endswith(f"En Octubre 2026 (mes actual) {fin}")


def test_vista_previa_se_actualiza_en_cada_cambio(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con)
    d.cantidad.value = "6"
    d.cantidad.on_change(None)
    assert d.vista_previa.value.startswith(
        "Última cuota: Enero 2027 · Total del plan: $ 246.700"
    )
    d.primer_mes.value = "9"
    d.primer_mes.on_select(None)
    assert d.vista_previa.value.startswith("Última cuota: Febrero 2027")
    d.monto.value = ""
    d.monto.on_change(None)
    assert d.vista_previa.value.startswith("Completá")


def test_ca_18_3_alta_sin_el_mes_actual_creado(con):
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con, monto="10.000", cantidad="6")
    d._guardar()
    assert app.page.avisos()[-1] == (
        "Plan creado. No se agregaron cuotas: Octubre 2026 todavía no existe. "
        "La cuota aparecerá al crear ese mes."
    )


def test_alta_de_un_plan_que_no_empezo(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con, monto="10.000", cantidad="12", mes="12")
    d._guardar()
    assert app.page.avisos()[-1] == "Plan creado."
    [fila] = _filas(app.pantalla("Cuotas"))[:-1]
    assert (fila["Cuota del mes"], fila["Restante"]) == (
        "No empezó",
        "$ 120.000",
    )  # CA-17.4
    celda_mes = _fila_plan(app.pantalla("Cuotas"), "Avant Service").cells[4].content
    assert celda_mes.color == SECUNDARIO


@pytest.mark.parametrize(
    ("cambios", "campo", "mensaje"),
    [
        ({"nombre": ""}, "nombre", "Ingresá un nombre."),
        ({"monto": ""}, "monto", "Ingresá un monto."),
        ({"monto": "0"}, "monto", "El monto de la cuota tiene que ser mayor a 0."),
        (
            {"cantidad": ""},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        (
            {"cantidad": "0"},
            "cantidad",
            "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1.",
        ),
        ({"cantidad": "601"}, "cantidad", "La cantidad de cuotas es demasiado grande."),
        ({"anio": "26"}, "primer_anio", "El año tiene que tener 4 dígitos."),
        ({"anio": "0026"}, "primer_anio", "El año tiene que tener 4 dígitos."),
    ],
)
def test_ca_16_2_errores_en_el_dialogo(con, oct_nov, cambios, campo, mensaje):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    datos = {
        "nombre": "Plan",
        "monto": "10.000",
        "cantidad": "6",
        "mes": "8",
        "anio": "2026",
    }
    datos.update(cambios)
    _completar(d, con, **datos)
    d._guardar()
    assert getattr(d, campo).error == mensaje
    assert d.dialogo.open is True
    assert _enfocado(app) is getattr(d, campo)
    assert cuotas.listar_planes(con, 2026, 10) == []


def test_errores_juntos_y_foco_al_primero(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    d.primer_anio.value = ""
    d._guardar()
    assert d.nombre.error == "Ingresá un nombre."
    assert d.categoria.error_text == "Elegí una categoría."
    assert d.monto.error == "Ingresá un monto."
    assert d.cantidad.error
    assert d.primer_anio.error == "El año tiene que tener 4 dígitos."
    assert _enfocado(app) is d.nombre


def test_cancelar_el_dialogo_no_crea_nada(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con)
    clic(d.dialogo, "Cancelar")
    assert cuotas.listar_planes(con, 2026, 10) == []


def test_enter_en_la_cantidad_guarda(con, oct_nov):
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con)
    d.cantidad.on_submit(None)
    assert len(cuotas.listar_planes(con, 2026, 10)) == 1


def test_ca_18_1_y_18_2_desde_el_dialogo(con, oct_nov):
    # Viendo 2026-09: la cuota se genera en 2026-10 y 2026-11, no en 2026-09.
    app = _app(con)
    app.seleccionar_mes(oct_nov[(2026, 9)])
    app.pantalla("Cuotas").nuevo()
    d = _dialogo_plan(app)
    _completar(d, con, monto="10.000", cantidad="6")
    d._guardar()
    pid = cuotas.listar_planes(con, 2026, 10)[0].plan["id"]
    for mes, tiene in [((2026, 9), False), ((2026, 10), True), ((2026, 11), True)]:
        existe = con.execute(
            "SELECT 1 FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
            (pid, oct_nov[mes]),
        ).fetchone()
        assert bool(existe) is tiene, mes


# ---------------------------------------------------------------------------
# Tabla, filtros y total (§3.4, CA-17.2, CA-21.1, BUG-20)
# ---------------------------------------------------------------------------


@pytest.fixture
def planes(con, oct_nov):
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    _plan(con, "Avant Service", 4111666, 3, (2026, 8), visa)
    _plan(con, "Plan B", 1000000, 12, (2026, 3))
    _plan(con, "Heladera", 2500000, 12, (2026, 12))
    _plan(con, "Viejo", 500000, 3, (2026, 1))  # terminado
    cancelado = _plan(con, "Cancelado", 700000, 10, (2026, 8))
    cuotas.cancelar_plan(con, cancelado, hoy=HOY)
    return oct_nov


def test_tabla_de_activos_con_total(con, planes):
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    filas = _filas(pantalla)
    assert [f["Nombre"] for f in filas[:-1]] == ["Avant Service", "Heladera", "Plan B"]
    por_nombre = {f["Nombre"]: f for f in filas}
    assert por_nombre["Avant Service"]["Medio"] == "Visa Santander"
    assert (por_nombre["Plan B"]["Cuota del mes"], por_nombre["Plan B"]["Última"]) == (
        "8/12",
        "feb 2027",
    )
    assert por_nombre["Plan B"]["Restante"] == "$ 40.000"  # CA-17.2
    assert por_nombre["Heladera"]["Cuota del mes"] == "No empezó"
    total = filas[-1]
    assert total["Nombre"] == "Total"
    assert total["Cuota"] == "$ 76.117"  # 41.116,66 + 10.000 + 25.000
    assert total["Restante"] == "$ 340.000"  # 0 + 40.000 + 300.000
    assert [s.label.value for s in pantalla.filtro.segments] == [
        "Activos (3)",
        "Terminados (1)",
        "Cancelados (1)",
    ]
    tabla = _tabla_planes(pantalla)
    numericas = {c.label.value for c in tabla.columns if c.numeric}
    assert numericas == {"Cuota", "Restante"}


def test_ca_17_2_viendo_septiembre(con, planes):
    app = _app(con)
    app.seleccionar_mes(planes[(2026, 9)])
    pantalla = app.pantalla("Cuotas")
    assert (
        pantalla.subtitulo.value
        == "Cuota y restante calculados para Septiembre 2026 (mes seleccionado)."
    )
    fila = next(f for f in _filas(pantalla) if f["Nombre"] == "Plan B")
    assert (fila["Cuota del mes"], fila["Restante"]) == ("7/12", "$ 50.000")
    # CA-21.1: el filtro (mes actual) da lo mismo viendo otro mes.
    assert pantalla.filtro.segments[0].label.value == "Activos (3)"


def test_ca_21_1_filtros(con, planes):
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    _elegir_filtro(pantalla, cuotas.TERMINADO)
    [fila] = _filas(pantalla)[:-1]
    assert (fila["Nombre"], fila["Cuota del mes"], fila["Última"]) == (
        "Viejo",
        "Terminado",
        "mar 2026",
    )
    icono = de_tipo(_fila_plan(pantalla, "Viejo").cells[4].content, ft.Icon)[0]
    assert (icono.icon, icono.color) == (ft.Icons.CHECK, POSITIVO)
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    [fila] = _filas(pantalla)[:-1]
    assert (fila["Nombre"], fila["Cuota del mes"], fila["Restante"]) == (
        "Cancelado",
        "Cancelado",
        "$ 0",
    )
    icono = de_tipo(_fila_plan(pantalla, "Cancelado").cells[4].content, ft.Icon)[0]
    assert icono.icon == ft.Icons.BLOCK


def test_filtro_sin_resultados(con, oct_nov):
    _plan(con)
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    _elegir_filtro(pantalla, cuotas.TERMINADO)
    assert textos(pantalla.cuerpo) == ["No hay planes terminados."]
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    assert textos(pantalla.cuerpo) == ["No hay planes cancelados."]


def test_bug20_tabla_ordenada_sin_acentos(con, oct_nov):
    for nombre in ["Zeta", "Ágil", "auto", "Ómnibus"]:
        _plan(con, nombre)
    app = _app(con)
    assert [f["Nombre"] for f in _filas(app.pantalla("Cuotas"))[:-1]] == [
        "Ágil",
        "auto",
        "Ómnibus",
        "Zeta",
    ]


def test_menu_segun_el_estado(con, planes):
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    assert list(_menu_plan(pantalla, "Plan B")) == [
        "Editar plan",
        "Cancelar plan",
        "Ir a la cuota del mes",
    ]
    assert list(_menu_plan(pantalla, "Heladera")) == [
        "Editar plan",
        "Cancelar plan",
    ]  # sin cuota este mes
    _elegir_filtro(pantalla, cuotas.TERMINADO)
    assert list(_menu_plan(pantalla, "Viejo")) == [
        "Editar plan"
    ]  # BUG-19: no se ofrece cancelar
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    assert list(_menu_plan(pantalla, "Cancelado")) == ["Editar plan"]


def test_ir_a_la_cuota_del_mes(con, planes):
    app = _app(con)
    _menu_plan(app.pantalla("Cuotas"), "Plan B")["Ir a la cuota del mes"].on_click(None)
    assert (nombre_visible(app), mes_seleccionado(app)) == ("Gastos", "Octubre 2026")
    assert any(f["Nombre"] == "Plan B" for f in filas_tabla(app.pantalla("Gastos")))


def test_clic_en_el_nombre_edita_el_plan(con, planes):
    app = _app(con)
    _fila_plan(app.pantalla("Cuotas"), "Plan B").cells[0].on_tap(None)
    d = _dialogo_plan(app)
    assert titulo_dialogo(d.dialogo) == "Editar plan de cuotas"
    assert d.nombre.value == "Plan B"


# ---------------------------------------------------------------------------
# Edición (CA-19.x)
# ---------------------------------------------------------------------------


def _editar_desde_la_tabla(app, nombre):
    _menu_plan(app.pantalla("Cuotas"), nombre)["Editar plan"].on_click(None)
    return _dialogo_plan(app)


def test_ca_19_1_editar_la_cuota(con, oct_nov):
    pid = _plan(con)
    app = _app(con)
    d = _editar_desde_la_tabla(app, "Plan")
    assert (
        "Los cambios se aplican desde Octubre 2026. Las cuotas que ya tienen pagos no se "
        "modifican." in textos(d.dialogo)
    )
    assert (d.nombre.value, d.monto.value, d.cantidad.value) == ("Plan", "10.000", "6")
    assert (d.primer_mes.value, d.primer_anio.value, d.medio.value) == (
        "8",
        "2026",
        "ninguno",
    )
    d.monto.value = "12.000"
    d._guardar()
    assert (
        app.page.avisos()[-1]
        == "Plan actualizado. Los cambios se aplican desde Octubre 2026."
    )
    for mes in [(2026, 10), (2026, 11)]:
        cuota = con.execute(
            "SELECT monto_cent FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
            (pid, oct_nov[mes]),
        ).fetchone()
        assert cuota["monto_cent"] == 1200000


def test_ca_19_2_editar_con_pagos(con, oct_nov):
    pid = _plan(con)
    cuota_oct = con.execute(
        "SELECT id FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
        (pid, oct_nov[(2026, 10)]),
    ).fetchone()["id"]
    pagos.registrar_pago(con, cuota_oct, 500000, HOY)
    app = _app(con)
    d = _editar_desde_la_tabla(app, "Plan")
    d.monto.value = "12.000"
    d._guardar()
    assert gastos.obtener_gasto(con, cuota_oct)["monto_cent"] == 1000000
    assert pagos.pendiente(con, cuota_oct) == 500000


def test_editar_plan_con_categoria_y_medio_archivados(con, oct_nov):
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    cuotas.crear_plan(con, "Plan", gym, visa, 1000000, 6, 2026, 8, hoy=HOY)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    app = _app(con)
    d = _editar_desde_la_tabla(app, "Plan")
    assert "Gym (archivada)" in [o.text for o in d.categoria.options]
    assert "Visa Santander (archivado)" in [o.text for o in d.medio.options]
    d.monto.value = "11.000"
    d._guardar()
    assert app.page.avisos()[-1].startswith("Plan actualizado.")


def test_alta_no_ofrece_archivados(con, oct_nov):
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    gastos.agregar_gasto(con, oct_nov[(2026, 10)], "X", gym, 100, "fijo")
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    app = _app(con)
    app.pantalla("Cuotas").nuevo()
    assert not any("Gym" in o.text for o in _dialogo_plan(app).categoria.options)


def test_editar_un_plan_borrado_por_detras(con, oct_nov):
    pid = _plan(con)
    app = _app(con)
    item = _menu_plan(app.pantalla("Cuotas"), "Plan")["Editar plan"]
    with con:
        con.execute("DELETE FROM gastos WHERE plan_cuotas_id = ?", (pid,))
        con.execute("DELETE FROM planes_cuotas WHERE id = ?", (pid,))
    item.on_click(None)
    assert app.hay_dialogo_abierto() is False
    assert app.page.avisos()[-1] == "Ese plan de cuotas ya no existe."


# ---------------------------------------------------------------------------
# Cancelación (CA-20.x, BUG-19)
# ---------------------------------------------------------------------------


def test_ca_20_1_cancelar_desde_la_tabla(con, oct_nov):
    pid = _plan(con)
    app = _app(con)
    _menu_plan(app.pantalla("Cuotas"), "Plan")["Cancelar plan"].on_click(None)
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Cancelar el plan Plan?"
    assert confirmacion.content.value == (
        "Se borran sus cuotas de Octubre 2026 y Noviembre 2026. "
        "No se generan más cuotas. Las cuotas de meses anteriores se conservan."
    )
    assert boton(confirmacion, "Volver").autofocus is True
    assert hay_boton(confirmacion, "Cancelar plan")
    clic(confirmacion, "Volver")
    assert cuotas.obtener_plan(con, pid)["cancelado_anio"] is None

    _menu_plan(app.pantalla("Cuotas"), "Plan")["Cancelar plan"].on_click(None)
    clic(dialogo_arriba(app), "Cancelar plan")
    assert app.page.avisos()[-1] == 'Plan "Plan" cancelado'
    pantalla = app.pantalla("Cuotas")
    assert textos(pantalla.cuerpo) == ["No hay planes activos."]
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    [fila] = _filas(pantalla)[:-1]
    assert (fila["Cuota del mes"], fila["Última"], fila["Restante"]) == (
        "Cancelado",
        "sep 2026",
        "$ 0",
    )


def test_ca_20_2_cancelar_con_pagos_en_el_mes_actual(con, oct_nov):
    pid = _plan(con)
    cuota_oct = con.execute(
        "SELECT id FROM gastos WHERE plan_cuotas_id = ? AND mes_id = ?",
        (pid, oct_nov[(2026, 10)]),
    ).fetchone()["id"]
    pagos.registrar_pago(con, cuota_oct, 500000, HOY)
    app = _app(con)
    _menu_plan(app.pantalla("Cuotas"), "Plan")["Cancelar plan"].on_click(None)
    assert dialogo_arriba(app).content.value == (
        "La cuota de Octubre 2026 ya tiene pagos: se conserva y pasa a ser la última. "
        "Se borra su cuota de Noviembre 2026. "
        "No se generan más cuotas. Las cuotas de meses anteriores se conservan."
    )
    clic(dialogo_arriba(app), "Cancelar plan")
    pantalla = app.pantalla("Cuotas")
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    assert _filas(pantalla)[0]["Última"] == "oct 2026"


def test_cancelar_con_una_sola_cuota_por_borrar(con):
    _meses(con, (2026, 10), (2026, 10))
    _plan(con)
    app = _app(con)
    _menu_plan(app.pantalla("Cuotas"), "Plan")["Cancelar plan"].on_click(None)
    assert dialogo_arriba(app).content.value == (
        "Se borra su cuota de Octubre 2026. "
        "No se generan más cuotas. Las cuotas de meses anteriores se conservan."
    )


def test_bug19_cancelar_un_plan_que_no_empezo_muestra_guion(con, oct_nov):
    _plan(con, cantidad=3, primera=(2026, 12))
    app = _app(con)
    _menu_plan(app.pantalla("Cuotas"), "Plan")["Cancelar plan"].on_click(None)
    assert dialogo_arriba(app).content.value == (
        "No se generan más cuotas. Las cuotas de meses anteriores se conservan."
    )
    clic(dialogo_arriba(app), "Cancelar plan")
    pantalla = app.pantalla("Cuotas")
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    [fila] = _filas(pantalla)[:-1]
    assert (fila["Primera"], fila["Última"]) == ("dic 2026", "—")


def test_bug19_cancelar_algo_que_termino_por_detras_avisa(con, oct_nov, monkeypatch):
    # Si al confirmar el plan ya terminó (la lógica lo rechaza), se avisa sin romper.
    _plan(con)
    app = _app(con)
    _menu_plan(app.pantalla("Cuotas"), "Plan")["Cancelar plan"].on_click(None)

    def ya_termino(*args, **kwargs):
        from app.logica.errores import ErrorDeValidacion

        raise ErrorDeValidacion("Ese plan ya terminó.")

    monkeypatch.setattr(cuotas, "cancelar_plan", ya_termino)
    clic(dialogo_arriba(app), "Cancelar plan")
    assert app.page.avisos()[-1] == "Ese plan ya terminó."
    assert app.hay_dialogo_abierto() is False


# ---------------------------------------------------------------------------
# Cuotas en la pantalla Gastos (§3.3, CA-08.2, CA-22.1)
# ---------------------------------------------------------------------------


def test_boton_plan_de_cuotas_en_gastos(con, oct_nov):
    app = _app(con, "Gastos")
    clic(app.pantalla("Gastos").control, "Plan de cuotas")
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo plan de cuotas"


def test_editar_una_cuota_abre_su_plan(con, oct_nov):
    _plan(con, "Heladera")
    app = _app(con, "Gastos")
    pantalla = app.pantalla("Gastos")
    assert (
        next(f for f in filas_tabla(pantalla) if f["Nombre"] == "Heladera")["Tipo"]
        == "Cuota 3/6"
    )
    item_menu(pantalla, "Heladera", "Editar").on_click(None)
    d = _dialogo_plan(app)
    assert (titulo_dialogo(d.dialogo), d.nombre.value) == (
        "Editar plan de cuotas",
        "Heladera",
    )
    app.cerrar_dialogo(d.dialogo)
    celda(pantalla, "Heladera", "Nombre").on_tap(None)  # clic en el nombre
    assert _dialogo_plan(app).nombre.value == "Heladera"


def test_ca_08_2_borrar_la_cuota_de_un_mes_en_pantalla(con, oct_nov):
    pid = _plan(con)
    app = _app(con, "Gastos")
    app.seleccionar_mes(oct_nov[(2026, 11)])
    pantalla = app.pantalla("Gastos")
    item_menu(pantalla, "Plan", "Borrar").on_click(None)
    confirmacion = dialogo_arriba(app)
    assert (
        titulo_dialogo(confirmacion)
        == "¿Borrar la cuota 4/6 de Plan en Noviembre 2026?"
    )
    assert confirmacion.content.value == (
        "Se borra solo la cuota de este mes. El plan sigue en los demás meses y esta cuota "
        "no se vuelve a generar en Noviembre 2026. Si querés terminar la deuda antes, usá "
        '"Cancelar plan" en la pantalla Cuotas.'
    )
    clic(confirmacion, "Borrar cuota")
    assert app.page.avisos()[-1] == 'Cuota de "Plan" borrada'
    # Noviembre se queda sin gastos: se ve el estado vacío (sin la cuota).
    assert gastos.listar_gastos(con, oct_nov[(2026, 11)]) == []
    assert "Todavía no cargaste gastos en Noviembre 2026." in textos(pantalla.cuerpo)
    omitida = con.execute(
        "SELECT anio, mes FROM cuotas_omitidas WHERE plan_cuotas_id = ?", (pid,)
    ).fetchall()
    assert [tuple(f) for f in omitida] == [(2026, 11)]
    # Octubre conserva la cuota 3/6.
    app.seleccionar_mes(oct_nov[(2026, 10)])
    assert (
        next(f for f in filas_tabla(pantalla) if f["Nombre"] == "Plan")["Tipo"]
        == "Cuota 3/6"
    )


def test_borrar_un_gasto_comun_sigue_igual(con, oct_nov):
    gastos.agregar_gasto(
        con, oct_nov[(2026, 10)], "Nafta", _otros(con), 3000000, "unico"
    )
    app = _app(con, "Gastos")
    item_menu(app.pantalla("Gastos"), "Nafta", "Borrar").on_click(None)
    assert titulo_dialogo(dialogo_arriba(app)) == "¿Borrar el gasto Nafta?"
    clic(dialogo_arriba(app), "Borrar")
    assert app.page.avisos()[-1] == 'Gasto "Nafta" borrado'
    assert gastos.listar_gastos(con, oct_nov[(2026, 10)]) == []


def test_ca_22_1_por_medio_de_pago_en_pantalla(con, oct_nov):
    oct_ = oct_nov[(2026, 10)]
    otros = _otros(con)
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    master = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Mastercard Nación")
    transferencia = id_por_nombre(con, catalogos.MEDIOS_PAGO, "Transferencia")
    gastos.agregar_gasto(con, oct_, "Gym", otros, 5000000, "fijo", visa)
    _plan(con, "Avant", 4111666, 3, (2026, 8), visa)
    gastos.agregar_gasto(con, oct_, "Seguro", otros, 13100000, "fijo", master)
    gastos.agregar_gasto(con, oct_, "Alquiler", otros, 26000000, "fijo", transferencia)
    gastos.agregar_gasto(con, oct_, "Nafta", otros, 3000000, "unico")
    app = _app(con, "Gastos")
    pantalla = app.pantalla("Gastos")
    assert tabla_por_medio(pantalla) == [
        ("Mastercard Nación", "$ 131.000"),
        ("Transferencia", "$ 260.000"),
        ("Visa Santander", "$ 91.117"),
        ("Sin medio de pago", "$ 30.000"),
    ]
    assert "POR MEDIO DE PAGO" in textos(pantalla.cuerpo)


def test_por_medio_de_pago_texto_de_ayuda_del_diseno(con, oct_nov):
    # §3.3 (paso 1c): "Incluye todos los gastos del mes (fijos, cuotas y únicos, en
    # pesos y en dólares) agrupados por cómo se pagan. Los gastos en dólares se suman
    # por sus pesos."
    gastos.agregar_gasto(con, oct_nov[(2026, 10)], "Nafta", _otros(con), 100, "unico")
    app = _app(con, "Gastos")
    assert (
        "Incluye todos los gastos del mes (fijos, cuotas y únicos, en pesos y en dólares) "
        "agrupados por cómo se pagan. Los gastos en dólares se suman por sus pesos."
        in textos(app.pantalla("Gastos").cuerpo)
    )


def test_sin_gastos_no_hay_tabla_por_medio(con, oct_nov):
    app = _app(con, "Gastos")
    assert not any(
        "POR MEDIO DE PAGO" == t for t in textos(app.pantalla("Gastos").cuerpo)
    )


# ---------------------------------------------------------------------------
# "Mes nuevo" con cuotas (§3.9)
# ---------------------------------------------------------------------------


def test_mes_nuevo_cuenta_las_cuotas(con, oct_nov):
    gastos.agregar_gasto(con, oct_nov[(2026, 11)], "Alquiler", _otros(con), 100, "fijo")
    _plan(con)  # 6 cuotas desde 2026-08: en diciembre va la 5/6
    app = _app(con, "Resumen")
    app.crear_mes_nuevo()
    d = boton(dialogo_arriba(app), "Crear mes").on_click.__self__
    contenido = textos(d.dialogo)
    assert "• 1 gasto fijo, sin pagos" in contenido
    assert "• 1 cuota de planes activos" in contenido
    clic(d.dialogo, "Crear mes")
    assert app.page.avisos()[-1] == "Diciembre 2026 creado: 1 gasto fijo y 1 cuota."


def test_mes_nuevo_sin_cuotas_no_las_menciona(con, oct_nov):
    gastos.agregar_gasto(con, oct_nov[(2026, 11)], "Alquiler", _otros(con), 100, "fijo")
    app = _app(con, "Resumen")
    app.crear_mes_nuevo()
    d = boton(dialogo_arriba(app), "Crear mes").on_click.__self__
    assert not any("cuota" in t for t in textos(d.dialogo))
    clic(d.dialogo, "Crear mes")
    assert app.page.avisos()[-1] == "Diciembre 2026 creado: 1 gasto fijo."


def test_mes_nuevo_con_varias_cuotas(con, oct_nov):
    _plan(con, "A")
    _plan(con, "B")
    app = _app(con, "Resumen")
    app.crear_mes_nuevo()
    d = boton(dialogo_arriba(app), "Crear mes").on_click.__self__
    assert "• 2 cuotas de planes activos" in textos(d.dialogo)
    clic(d.dialogo, "Crear mes")
    assert app.page.avisos()[-1] == "Diciembre 2026 creado: 0 gastos fijos y 2 cuotas."


def test_inventario_de_la_pantalla_cuotas_ve_el_menu():
    # El inventario de acciones (test_interfaz_historial) también recorre Cuotas.
    from tests import test_interfaz_historial as h

    assert "Cuotas" in h.MINIMO_DE_ACCIONES


# ---------------------------------------------------------------------------
# Ronda 21: O37 ("Nuevo plan" verifica el mes) y BUG-22 (filtro con el mes borrado)
# ---------------------------------------------------------------------------


def _nuevo_plan_boton(app):
    clic(app.pantalla("Cuotas").control, "Nuevo plan")


def _nuevo_plan_ctrl_n(app):
    app._al_presionar_tecla(tecla("N", ctrl=True))


def _nuevo_plan_estado_vacio(app):
    clic(app.pantalla("Cuotas").cuerpo, "Nuevo plan")


@pytest.mark.parametrize(
    "accion", [_nuevo_plan_boton, _nuevo_plan_ctrl_n], ids=["boton", "ctrl_n"]
)
def test_o37_nuevo_plan_con_el_mes_borrado_por_detras(con, oct_nov, accion):
    _plan(con)  # así la pantalla tiene tabla y el botón del encabezado
    app = _app(con)
    app.seleccionar_mes(oct_nov[(2026, 11)])
    meses.borrar_ultimo_mes(con, oct_nov[(2026, 11)])
    accion(app)
    assert app.hay_dialogo_abierto() is False
    assert app.mes_id == oct_nov[(2026, 10)]
    assert mes_seleccionado(app) == "Octubre 2026"
    assert app.page.avisos()[-1] == "El mes que estabas viendo ya no existe."


def test_o37_nuevo_plan_del_estado_vacio_con_el_mes_borrado(con, oct_nov):
    app = _app(con)  # sin planes: el botón está en el estado vacío
    app.seleccionar_mes(oct_nov[(2026, 11)])
    meses.borrar_ultimo_mes(con, oct_nov[(2026, 11)])
    _nuevo_plan_estado_vacio(app)
    assert app.hay_dialogo_abierto() is False
    assert app.page.avisos()[-1] == "El mes que estabas viendo ya no existe."


def test_o37_sin_meses_va_al_primer_uso(con):
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    app = _app(con)
    meses.borrar_ultimo_mes(con, mes)
    _nuevo_plan_ctrl_n(app)
    assert app.page.title == "Gastos – Bienvenido"
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize(
    "accion",
    [_nuevo_plan_boton, _nuevo_plan_ctrl_n, _nuevo_plan_estado_vacio],
    ids=["boton", "ctrl_n", "estado_vacio"],
)
def test_o37_con_el_mes_existente_abre_el_dialogo(con, oct_nov, accion):
    if accion is not _nuevo_plan_estado_vacio:
        _plan(con)
    app = _app(con)
    avisos_antes = list(app.page.avisos())
    accion(app)
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo plan de cuotas"
    assert app.page.avisos() == avisos_antes


def test_bug22_filtro_con_el_mes_borrado_por_detras(con, oct_nov):
    _plan(con, "Activo")
    cancelado = _plan(con, "Cancelado")
    cuotas.cancelar_plan(con, cancelado, hoy=HOY)
    app = _app(con)
    app.seleccionar_mes(oct_nov[(2026, 11)])
    pantalla = app.pantalla("Cuotas")
    meses.borrar_ultimo_mes(con, oct_nov[(2026, 11)])
    _elegir_filtro(pantalla, cuotas.CANCELADO)  # no tiene que lanzar excepción
    assert app.page.avisos()[-1] == "El mes que estabas viendo ya no existe."
    assert app.mes_id == oct_nov[(2026, 10)]
    # El filtro elegido se respeta en el mes al que se pasó (se ve "Cancelado").
    assert pantalla.filtro_elegido == cuotas.CANCELADO
    assert pantalla.filtro.selected == [cuotas.CANCELADO]
    assert [f["Nombre"] for f in _filas(pantalla)[:-1]] == ["Cancelado"]


def test_bug22_el_filtro_se_respeta_al_volver_a_cuotas(con, oct_nov):
    _plan(con, "Activo")
    cancelado = _plan(con, "Cancelado")
    cuotas.cancelar_plan(con, cancelado, hoy=HOY)
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    _elegir_filtro(pantalla, cuotas.CANCELADO)
    ir(app, "Gastos")
    app.seleccionar_mes(oct_nov[(2026, 9)])
    ir(app, "Cuotas")
    assert pantalla.filtro.selected == [cuotas.CANCELADO]
    assert [f["Nombre"] for f in _filas(pantalla)[:-1]] == ["Cancelado"]


def test_bug22_filtro_con_el_mes_existente_sigue_igual(con, oct_nov):
    _plan(con, "Activo")
    app = _app(con)
    pantalla = app.pantalla("Cuotas")
    avisos_antes = list(app.page.avisos())
    _elegir_filtro(pantalla, cuotas.TERMINADO)
    assert textos(pantalla.cuerpo) == ["No hay planes terminados."]
    assert app.page.avisos() == avisos_antes


def test_bug21_ayuda_exacta_en_un_mes_con_gastos_en_dolares(con, oct_nov):
    oct_ = oct_nov[(2026, 10)]
    gastos.agregar_gasto(
        con, oct_, "Claude", _otros(con), None, "unico", None, "USD", 2000, 160000
    )
    app = _app(con, "Gastos")
    pantalla = app.pantalla("Gastos")
    assert (
        "Incluye todos los gastos del mes (fijos, cuotas y únicos, en pesos y en dólares) "
        "agrupados por cómo se pagan. Los gastos en dólares se suman por sus pesos."
        in textos(pantalla.cuerpo)
    )
    assert tabla_por_medio(pantalla) == [("Sin medio de pago", "$ 32.000")]
