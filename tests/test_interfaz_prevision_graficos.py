"""Pruebas de las pantallas Previsión (paso 6, diseno.md §3.7), Gráficos (paso 7, §3.8)
y la pestaña Apariencia de Ajustes (§3.10). CA-38.1, 38.2, 38.5, 38.7, 38.8, 39.1, 40.1,
41.1 a 41.3, 42.1 y los estados de cada pantalla, sobre la página falsa.

"Hoy" se fija en octubre 2026 reemplazando meses.mes_actual_calendario. Datos inventados.
"""

from datetime import date
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz import estilos
from app.interfaz.aplicacion import Aplicacion
from app.logica import catalogos, configuracion, cuotas, gastos, meses
from app.logica.formato import formatear_mes_corto
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    boton,
    clic,
    de_tipo,
    dialogo_arriba,
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
POSITIVO = "#1E7B34"
POSITIVO_SUAVE = "#E3F2E6"
POSITIVO_SUAVE_OSCURO = "#1D3324"
NEGATIVO = "#B3261E"

SUBTITULO = (
    "Desde Noviembre 2026. Con la cotización ($ 1.600 por US$) y el sueldo "
    "(US$ 1.200,00) de Octubre 2026 (mes actual). Solo gastos fijos y cuotas; "
    "sin inflación ni ingresos extra."
)


@pytest.fixture(autouse=True)
def hoy_octubre(monkeypatch):
    original = meses.mes_actual_calendario

    def falso(hoy=None):
        return (2026, 10) if hoy is None else original(hoy)

    monkeypatch.setattr(meses, "mes_actual_calendario", falso)


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


def _cat(con, nombre):
    try:
        return id_por_nombre(con, catalogos.CATEGORIAS, nombre)
    except AssertionError:
        return catalogos.crear(con, catalogos.CATEGORIAS, nombre)


def _base(con, sueldo=120000):
    """Base del módulo H (§7): 2026-09 y 2026-10 (mes actual, K 1.600), fijos que suman
    800.000 (Internet 38.700 compartido entre 3), un único de 15.000, Avant 41.117 que
    termina en 2026-10 y plan B 10.000 que termina en 2027-02."""
    sep = meses.crear_primer_mes(con, 2026, 9, sueldo, 155000)
    oct_ = meses.crear_mes_siguiente(con, sueldo, 160000)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    otros = _cat(con, "Otros")
    gastos.agregar_gasto(con, oct_, "Alquiler", _cat(con, "Vivienda"), 26000000, "fijo")
    gastos.agregar_gasto(
        con,
        oct_,
        "Internet",
        _cat(con, "Servicios"),
        3870000,
        "fijo",
        partes=[(sofia, None), (marsu, None)],
    )
    gastos.agregar_gasto(
        con, oct_, "Resto de fijos", otros, 80000000 - 26000000 - 3870000, "fijo"
    )
    gastos.agregar_gasto(con, oct_, "Regalo", otros, 1500000, "unico")
    cuotas.crear_plan(con, "Avant", otros, None, 4111700, 3, 2026, 8, hoy=HOY)
    cuotas.crear_plan(con, "Plan B", otros, None, 1000000, 12, 2026, 3, hoy=HOY)
    return SimpleNamespace(sep=sep, oct=oct_, otros=otros)


def _app(con, pantalla, mes_id=None):
    """App sobre una página falsa, en la pantalla pedida (y el mes pedido)."""
    app = Aplicacion(PaginaFalsa(), con)
    app.iniciar()
    if mes_id is None:
        ir(app, pantalla)
    else:
        app.seleccionar_mes(mes_id, pantalla=pantalla)
    return app


def _texto(control):
    """Los textos de un control unidos con " | " ("" si no tiene)."""
    return " | ".join(
        t.value for t in recorrer(control) if isinstance(t, ft.Text) and t.value
    )


def _tabla(app):
    [tabla] = de_tipo(app.pantalla("Previsión").cuerpo, ft.DataTable)
    return tabla


def _filas(app):
    """Filas de la tabla de previsión como tuplas de textos (una por columna)."""
    return [tuple(_texto(c.content) for c in fila.cells) for fila in _tabla(app).rows]


def _meses_de_la_tabla():
    """Las etiquetas "nov 2026" … "oct 2027" (2026-11 a 2027-10)."""
    etiquetas, actual = [], (2026, 10)
    for _ in range(12):
        actual = meses.siguiente(*actual)
        etiquetas.append(formatear_mes_corto(*actual))
    return etiquetas


def _filas_esperadas_base():
    """CA-38.2 + CA-39.1 sobre la base del módulo H."""
    filas = []
    for i, etiqueta in enumerate(_meses_de_la_tabla()):
        if i < 4:
            fila = (etiqueta, "$ 810.000", "US$ 506,25", "US$ 693,75", "")
        else:
            fila = (etiqueta, "$ 800.000", "US$ 500,00", "US$ 700,00", "")
        filas.append(fila)
    filas[0] = (*filas[0][:4], "Avant +$ 41.117")
    filas[4] = (*filas[4][:4], "Plan B +$ 10.000")
    return filas


def _quitar_cotizacion(con, mes_id):
    # Un mes sin cotización (como uno creado sin cargarla), armado por SQL.
    with con:
        con.execute("UPDATE meses SET cotizacion_cent = NULL WHERE id = ?", (mes_id,))


def _claude(con, mes_id, cotizacion):
    """Fijo "Claude" US$ 20,00 guardado con la cotización indicada (CA-38.8 a 38.10)."""
    gastos.agregar_gasto(
        con,
        mes_id,
        "Claude",
        _cat(con, "Otros"),
        None,
        "fijo",
        None,
        "USD",
        2000,
        cotizacion,
    )


def _guardar_cotizacion(app, texto):
    """Escribe la cotización en el diálogo abierto y lo guarda."""
    dialogo = dialogo_arriba(app)
    de_tipo(dialogo, ft.TextField)[0].value = texto
    clic(dialogo, "Guardar")


# ===========================================================================
# Previsión (§3.7)
# ===========================================================================


def test_previsión_titulo_subtitulo_y_columnas(con):
    # §3.7: título, subtítulo con cotización y sueldo del mes actual, y las 5 columnas.
    _base(con)
    app = _app(con, "Previsión")
    p = app.pantalla("Previsión")
    assert "Previsión de los próximos 12 meses" in textos(p.control)
    assert p.subtitulo.value == SUBTITULO
    assert [c.label.value for c in _tabla(app).columns] == [
        "Mes",
        "Gastos estimados",
        "Dólares a cambiar",
        "Ahorro estimado",
        "Se libera",
    ]
    # Las columnas de montos van alineadas a la derecha (numeric).
    assert [c.numeric for c in _tabla(app).columns] == [
        False,
        True,
        True,
        True,
        False,
    ]


def test_ca_38_2_y_39_1_filas_de_la_tabla(con):
    # CA-38.1: 12 filas, nov 2026 a oct 2027 (sin oct 2026). CA-38.2: 810.000 / 506,25 /
    # 693,75 hasta feb 2027 y 800.000 / 500,00 / 700,00 desde mar 2027. CA-39.1: solo
    # nov 2026 (Avant) y mar 2027 (Plan B) indican liberación.
    _base(con)
    app = _app(con, "Previsión")
    assert _filas(app) == _filas_esperadas_base()
    assert "oct 2026" not in [f[0] for f in _filas(app)]


def test_ca_38_1_misma_tabla_con_otro_mes_seleccionado(con):
    # CA-38.1: con 2026-09 seleccionado la tabla (y el subtítulo) son los mismos.
    b = _base(con)
    app = _app(con, "Previsión", b.sep)
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert _filas(app) == _filas_esperadas_base()
    assert app.pantalla("Previsión").subtitulo.value == SUBTITULO


def test_ca_38_1_cambiar_de_mes_con_el_selector_no_cambia_la_tabla(con):
    # Pasar de Octubre a Septiembre con la flecha estando en Previsión no cambia nada.
    _base(con)
    app = _app(con, "Previsión")
    antes = _filas(app)
    app._al_presionar_tecla(tecla("Arrow Left", alt=True))
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert nombre_visible(app) == "Previsión"
    assert _filas(app) == antes


def test_ca_39_1_fila_con_liberacion_resaltada(con):
    # §3.7: las filas con liberaciones tienen fondo positivo suave, flecha hacia abajo y
    # texto en positivo; las demás no tienen fondo.
    _base(con)
    app = _app(con, "Previsión")
    filas = _tabla(app).rows
    colores = [f.color for f in filas]
    assert colores[0] == POSITIVO_SUAVE
    assert colores[4] == POSITIVO_SUAVE
    assert [c for i, c in enumerate(colores) if i not in (0, 4)] == [None] * 10
    celda = filas[0].cells[4].content
    [icono] = de_tipo(celda, ft.Icon)
    assert icono.icon == ft.Icons.ARROW_DOWNWARD
    assert icono.color == POSITIVO
    [texto] = [t for t in de_tipo(celda, ft.Text) if t.value]
    assert texto.color == POSITIVO
    # Las filas sin liberación no tienen íconos.
    assert de_tipo(filas[1].cells[4].content, ft.Icon) == []


def test_ca_39_1_varios_planes_en_el_mismo_mes(con):
    # §3.7: si se liberan varios planes, van uno debajo del otro (ordenados sin acentos).
    b = _base(con)
    cuotas.crear_plan(con, "Zeta", b.otros, None, 200000, 4, 2026, 9, hoy=HOY)
    cuotas.crear_plan(con, "Ágil", b.otros, None, 100000, 3, 2026, 10, hoy=HOY)
    app = _app(con, "Previsión")
    # Ambos terminan en 2026-12: se liberan en la fila de enero 2027.
    fila = _tabla(app).rows[2]
    assert _texto(fila.cells[0].content) == "ene 2027"
    assert _texto(fila.cells[4].content) == "Ágil +$ 1.000 | Zeta +$ 2.000"
    assert len(de_tipo(fila.cells[4].content, ft.Icon)) == 2
    assert fila.color == POSITIVO_SUAVE


def test_ca_38_5_cambiar_la_cotizacion_desde_previsión(con):
    # CA-38.5: con Ctrl+K desde Previsión se cambia la cotización a 2.000: nov 2026
    # pasa a 405,00 / 795,00 y los gastos no cambian. La pantalla se redibuja sola.
    _base(con)
    app = _app(con, "Previsión")
    app._al_presionar_tecla(tecla("K", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Cotización de Octubre 2026"
    _guardar_cotizacion(app, "2.000")
    assert app.hay_dialogo_abierto() is False
    filas = _filas(app)
    assert filas[0] == (
        "nov 2026",
        "$ 810.000",
        "US$ 405,00",
        "US$ 795,00",
        "Avant +$ 41.117",
    )
    assert filas[4][:4] == ("mar 2027", "$ 800.000", "US$ 400,00", "US$ 800,00")
    assert "($ 2.000 por US$)" in app.pantalla("Previsión").subtitulo.value


def test_ca_38_8_fijo_en_dolares_con_la_cotizacion_actual(con):
    # CA-38.8: Claude US$ 20 guardado a 1.600 y después la cotización de 2026-10 pasa
    # a 1.700: en la previsión cuenta 34.000.
    b = _base(con)
    _claude(con, b.oct, 160000)
    meses.editar_cotizacion(con, b.oct, 170000)
    app = _app(con, "Previsión")
    filas = _filas(app)
    assert {f[1:4] for f in filas[:4]} == {("$ 844.000", "US$ 496,47", "US$ 703,53")}
    assert {f[1:4] for f in filas[4:]} == {("$ 834.000", "US$ 490,59", "US$ 709,41")}


def test_ahorro_negativo_muestra_deficit(con):
    # §3.7: ahorro estimado negativo = "-US$ …" en negativo con la palabra "Déficit".
    _base(con, sueldo=40000)  # Sueldo US$ 400 < US$ 506,25 de gastos.
    app = _app(con, "Previsión")
    filas = _filas(app)
    assert filas[0][3] == "-US$ 106,25 Déficit"
    assert filas[4][3] == "-US$ 100,00 Déficit"
    celda = _tabla(app).rows[0].cells[3].content
    assert celda.color == NEGATIVO


def test_ahorro_cero_no_es_deficit(con):
    # Borde: si el ahorro estimado da exactamente 0 no se marca como déficit.
    b = _base(con, sueldo=50625)  # US$ 506,25 = lo que se cambia hasta feb 2027.
    assert b
    app = _app(con, "Previsión")
    assert _filas(app)[0][3] == "US$ 0,00"


# ---------------------------------------------------------------------------
# Estados (RN-45, CA-38.7)
# ---------------------------------------------------------------------------


def test_ca_38_7_sin_cotizacion(con):
    # CA-38.7: sin cotización en el mes actual se ven los gastos en pesos, el aviso y
    # "—" en las columnas en dólares. El subtítulo no menciona la cotización.
    b = _base(con)
    _quitar_cotizacion(con, b.oct)
    app = _app(con, "Previsión")
    p = app.pantalla("Previsión")
    assert (
        "Falta la cotización de Octubre 2026: se muestran solo los gastos en pesos."
        in textos(p.cuerpo)
    )
    assert hay_boton(p.cuerpo, "Cargar cotización")
    assert p.subtitulo.value == (
        "Desde Noviembre 2026. Con el sueldo (US$ 1.200,00) de Octubre 2026 (mes "
        "actual). Solo gastos fijos y cuotas; sin inflación ni ingresos extra."
    )
    filas = _filas(app)
    assert filas[0] == ("nov 2026", "$ 810.000", "—", "—", "Avant +$ 41.117")
    assert filas[4] == ("mar 2027", "$ 800.000", "—", "—", "Plan B +$ 10.000")
    assert {(f[2], f[3]) for f in filas} == {("—", "—")}


def test_ca_38_10_sin_cotizacion_fijo_en_dolares_en_pantalla(con):
    # CA-38.10: Claude a 1.600 (la del gasto) y 2026-10 sin cotización: 842.000 y aviso.
    b = _base(con)
    _claude(con, b.oct, 160000)
    _quitar_cotizacion(con, b.oct)
    app = _app(con, "Previsión")
    assert _filas(app)[0][1] == "$ 842.000"
    assert any(
        t.startswith("Falta la cotización")
        for t in textos(app.pantalla("Previsión").cuerpo)
    )


def test_con_cotizacion_no_hay_aviso(con):
    _base(con)
    app = _app(con, "Previsión")
    p = app.pantalla("Previsión")
    assert not any(t.startswith("Falta la cotización") for t in textos(p.cuerpo))
    assert not hay_boton(p.cuerpo, "Cargar cotización")


def test_cargar_cotizacion_abre_la_del_mes_actual_aunque_se_vea_otro(con):
    # §3.7: "Cargar cotización" abre la cotización del mes ACTUAL (la que usa la
    # previsión), aunque esté seleccionado 2026-09. Al guardar, la tabla se completa
    # y se sigue viendo 2026-09 en Previsión.
    b = _base(con)
    _quitar_cotizacion(con, b.oct)
    app = _app(con, "Previsión", b.sep)
    clic(app.pantalla("Previsión").cuerpo, "Cargar cotización")
    assert titulo_dialogo(dialogo_arriba(app)) == "Cotización de Octubre 2026"
    _guardar_cotizacion(app, "1.600")
    assert meses.obtener_mes(con, b.oct)["cotizacion_cent"] == 160000
    assert meses.obtener_mes(con, b.sep)["cotizacion_cent"] == 155000
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert nombre_visible(app) == "Previsión"
    assert _filas(app) == _filas_esperadas_base()
    assert not hay_boton(app.pantalla("Previsión").cuerpo, "Cargar cotización")


def test_cargar_cotizacion_con_el_mes_actual_borrado_por_detras(con):
    # Borde: la pantalla quedó vieja y el mes actual se borró por detrás. El botón no
    # rompe: se redibuja y se ve el estado "Creá el mes …".
    b = _base(con)
    _quitar_cotizacion(con, b.oct)
    app = _app(con, "Previsión", b.sep)
    meses.borrar_ultimo_mes(con, b.oct)
    clic(app.pantalla("Previsión").cuerpo, "Cargar cotización")
    assert app.hay_dialogo_abierto() is False
    assert "Creá el mes Octubre 2026 para ver la previsión." in textos(
        app.pantalla("Previsión").cuerpo
    )


def test_ca_38_7_sin_mes_actual_ofrece_mes_nuevo(con):
    # CA-38.7 / RN-45: último mes 2026-09; el siguiente es justo el actual: texto y
    # botón "Mes nuevo", que abre la creación de Octubre 2026. Sin tabla ni subtítulo.
    meses.crear_primer_mes(con, 2026, 8, 120000, 160000)
    meses.crear_mes_siguiente(con, 120000, 160000)
    app = _app(con, "Previsión")
    p = app.pantalla("Previsión")
    assert "Creá el mes Octubre 2026 para ver la previsión." in textos(p.cuerpo)
    assert de_tipo(p.cuerpo, ft.DataTable) == []
    assert not p.subtitulo.value
    assert not hay_boton(p.cuerpo, "Ver el gráfico de previsión")
    clic(p.cuerpo, "Mes nuevo")
    assert titulo_dialogo(dialogo_arriba(app)) == "Crear Octubre 2026"


@pytest.mark.parametrize(
    "meses_creados",
    [
        [(2026, 7), (2026, 8)],  # El siguiente al último es 2026-09, no el actual.
        [(2026, 11)],  # Solo existe un mes futuro.
    ],
)
def test_sin_mes_actual_sin_boton_si_no_es_el_siguiente(con, meses_creados):
    # §3.7: si el siguiente al último no es el mes actual, solo se ve el texto.
    meses.crear_primer_mes(con, *meses_creados[0], 120000, 160000)
    for _ in meses_creados[1:]:
        meses.crear_mes_siguiente(con, 120000, 160000)
    app = _app(con, "Previsión")
    p = app.pantalla("Previsión")
    assert "Creá el mes Octubre 2026 para ver la previsión." in textos(p.cuerpo)
    assert not hay_boton(p.cuerpo, "Mes nuevo")


def test_previsión_sin_fijos_ni_cuotas(con, mes_id):
    # Borde: el mes actual sin gastos: 12 filas en $ 0 y todo el sueldo como ahorro.
    app = _app(con, "Previsión")
    filas = _filas(app)
    assert len(filas) == 12
    assert set(filas) == {(f[0], "$ 0", "US$ 0,00", "US$ 1.200,00", "") for f in filas}


# ---------------------------------------------------------------------------
# Enlace al gráfico y Ctrl+N
# ---------------------------------------------------------------------------


def test_ver_el_grafico_va_a_la_tercera_pestana(con):
    # §3.7: el enlace lleva a Gráficos, pestaña 3, sin cambiar el mes elegido.
    b = _base(con)
    app = _app(con, "Previsión", b.sep)
    enlace = boton(app.pantalla("Previsión").cuerpo, "Ver el gráfico de previsión")
    assert enlace.icon == ft.Icons.BAR_CHART
    enlace.on_click(None)
    assert nombre_visible(app) == "Gráficos"
    assert app._rail.selected_index == 5
    assert app.pantalla("Gráficos").pestanas.selected_index == 2
    assert mes_seleccionado(app) == "Septiembre 2026"


def test_ver_el_grafico_con_el_mes_visto_borrado(con):
    # Borde (BUG-16): si el mes que se veía se borró por detrás, el enlace no rompe:
    # pasa al último mes que queda y avisa.
    b = _base(con)
    app = _app(con, "Previsión")
    meses.borrar_ultimo_mes(con, b.oct)
    clic(app.pantalla("Previsión").cuerpo, "Ver el gráfico de previsión")
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert "El mes que estabas viendo ya no existe." in app.page.avisos()


@pytest.mark.parametrize("pantalla", ["Previsión", "Gráficos"])
def test_ctrl_n_no_hace_nada(con, pantalla):
    # §1.3: Ctrl+N no tiene acción en Previsión ni en Gráficos.
    _base(con)
    app = _app(con, pantalla)
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert app.hay_dialogo_abierto() is False
    assert nombre_visible(app) == pantalla
    assert app.pantalla(pantalla).nuevo() is None


# ===========================================================================
# Gráficos (§3.8)
# ===========================================================================


def _base_categorias(con):
    """CA-40.1: gastos de 2026-10 con dos compartidos entre 3 en Servicios."""
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    servicios = _cat(con, "Servicios")
    gastos.agregar_gasto(con, oct_, "Alquiler", _cat(con, "Vivienda"), 26000000, "fijo")
    gastos.agregar_gasto(con, oct_, "Nafta", _cat(con, "Transporte"), 3000000, "unico")
    gastos.agregar_gasto(
        con, oct_, "Teléfono", _cat(con, "Comunicaciones"), 2000000, "fijo"
    )
    for nombre, monto in [("Internet", 3870000), ("Edenor", 6628100)]:
        gastos.agregar_gasto(
            con,
            oct_,
            nombre,
            servicios,
            monto,
            "fijo",
            partes=[(sofia, None), (marsu, None)],
        )
    return oct_


def _filas_categorias(app):
    """[(categoría, valor de la barra, monto, porcentaje)] de la pestaña 1."""
    salida = []
    for fila in app.pantalla("Gráficos").categorias.controls:
        if isinstance(fila, ft.Row):
            nombre, barra, monto, porcentaje = fila.controls
            salida.append(
                (nombre.value, round(barra.value, 4), monto.value, porcentaje.value)
            )
    return salida


def _barras(columna):
    """Las barras verticales de una pestaña: [(etiqueta, tooltip, alto, lado, color)].
    lado: "arriba", "abajo" o None (sin barra)."""
    [fila] = [
        r
        for r in de_tipo(columna, ft.Row)
        if r.controls and all(isinstance(c, ft.Column) for c in r.controls)
    ]
    salida = []
    for col in fila.controls:
        arriba, linea, abajo, etiqueta = col.controls
        assert linea.height == 1  # La línea de 0 está en cada columna.
        barra, lado = None, None
        if arriba.content.bgcolor is not None:
            barra, lado = arriba.content, "arriba"
        elif abajo.content.bgcolor is not None:
            barra, lado = abajo.content, "abajo"
        salida.append(
            (
                etiqueta.value,
                barra.tooltip if barra else None,
                barra.height if barra else None,
                lado,
                barra.bgcolor if barra else None,
            )
        )
    return salida


def _alturas_de_zona(columna):
    """(alto sobre la línea de 0, alto debajo) de la primera columna de barras."""
    [fila] = [
        r
        for r in de_tipo(columna, ft.Row)
        if r.controls and all(isinstance(c, ft.Column) for c in r.controls)
    ]
    arriba, _, abajo, _ = fila.controls[0].controls
    return arriba.height, abajo.height


def _tabla_de(columna):
    """Las filas de "Ver como tabla" como tuplas de textos."""
    [desplegable] = de_tipo(columna, ft.ExpansionTile)
    assert desplegable.title.value == "Ver como tabla"
    [tabla] = de_tipo(desplegable, ft.DataTable)
    return [tuple(c.content.value for c in f.cells) for f in tabla.rows]


def test_graficos_titulo_y_pestanas(con, mes_id):
    # §3.8: título "Gráficos" y tres pestañas en este orden.
    app = _app(con, "Gráficos")
    g = app.pantalla("Gráficos")
    assert "Gráficos" in textos(g.control)
    [barra] = de_tipo(g.pestanas, ft.TabBar)
    assert [t.label for t in barra.tabs] == [
        "Gastos por categoría",
        "Ahorro mes a mes",
        "Previsión de gastos",
    ]
    assert g.pestanas.selected_index == 0


def test_mostrar_pestana(con, mes_id):
    app = _app(con, "Gráficos")
    g = app.pantalla("Gráficos")
    for i in (2, 1, 0):
        g.mostrar_pestana(i)
        assert g.pestanas.selected_index == i


# ---------------------------------------------------------------------------
# 1. Por categoría (CA-40.1)
# ---------------------------------------------------------------------------


def test_ca_40_1_por_categoria_en_pantalla(con):
    # CA-40.1: una fila por categoría con barra (relativa a la mayor), monto y
    # porcentaje; Servicios = 34.994 (tu parte); las categorías sin gastos no aparecen.
    _base_categorias(con)
    app = _app(con, "Gráficos")
    g = app.pantalla("Gráficos")
    assert _filas_categorias(app) == [
        ("Vivienda", 1.0, "$ 260.000", "75 %"),
        ("Servicios", round(3499368 / 26000000, 4), "$ 34.994", "10 %"),
        ("Transporte", round(3000000 / 26000000, 4), "$ 30.000", "9 %"),
        ("Comunicaciones", round(2000000 / 26000000, 4), "$ 20.000", "6 %"),
    ]
    contenido = textos(g.categorias)
    assert contenido[0] == "Tu parte de los gastos de Octubre 2026, por categoría"
    assert "En los gastos compartidos se cuenta solo tu parte." in contenido
    assert "Mercado" not in contenido
    # El nombre tiene ancho fijo de 160 (y tooltip, por si es largo).
    fila = g.categorias.controls[1]
    assert fila.controls[0].width == 160
    assert fila.controls[0].tooltip == "Vivienda"


def test_por_categoria_mes_vacio(con, mes_id):
    # §3.8: sin gastos en el mes, un texto y ninguna barra.
    app = _app(con, "Gráficos")
    g = app.pantalla("Gráficos")
    assert textos(g.categorias) == ["No hay gastos en Octubre 2026 para graficar."]
    assert de_tipo(g.categorias, ft.ProgressBar) == []


def test_por_categoria_sigue_al_mes_seleccionado(con):
    # La pestaña 1 sí depende del mes elegido (a diferencia de la previsión).
    b = _base(con)
    app = _app(con, "Gráficos", b.sep)
    assert textos(app.pantalla("Gráficos").categorias) == [
        "No hay gastos en Septiembre 2026 para graficar."
    ]
    app._al_presionar_tecla(tecla("Arrow Right", alt=True))
    assert textos(app.pantalla("Gráficos").categorias)[0] == (
        "Tu parte de los gastos de Octubre 2026, por categoría"
    )


def test_por_categoria_solo_compartido_en_dolares(con, mes_id):
    # Borde: un único gasto en USD compartido: 100 % y barra llena con tu parte.
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    gastos.agregar_gasto(
        con,
        mes_id,
        "Netflix",
        _cat(con, "Otros"),
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, None)],
    )
    app = _app(con, "Gráficos")
    assert _filas_categorias(app) == [("Otros", 1.0, "$ 12.000", "100 %")]


# ---------------------------------------------------------------------------
# 2. Ahorro mes a mes (CA-41.x)
# ---------------------------------------------------------------------------


def _tres_meses_de_ahorro(con):
    """CA-41.1: 2026-08 (250,00), 2026-09 (280,00) y 2026-10 (303,36)."""
    otros = _cat(con, "Otros")
    ago = meses.crear_primer_mes(con, 2026, 8, 120000, 160000)
    sep = meses.crear_mes_siguiente(con, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    gastos.agregar_gasto(con, ago, "Gastos", otros, 152000000, "unico")
    gastos.agregar_gasto(con, sep, "Gastos", otros, 147200000, "unico")
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 143461700, "unico")
    return ago, sep, oct_


def test_ca_41_1_ahorro_mes_a_mes(con):
    # CA-41.1: tres barras hacia arriba en orden, alto proporcional a la mayor (200),
    # tooltip "<Mes Año>: US$ X", color positivo y la misma info en "Ver como tabla".
    _tres_meses_de_ahorro(con)
    app = _app(con, "Gráficos")
    ahorro = app.pantalla("Gráficos").ahorro
    assert textos(ahorro)[0] == "Ahorro en dólares, mes a mes"
    assert _barras(ahorro) == [
        (
            "ago 2026",
            "Agosto 2026: US$ 250,00",
            round(200 * 25000 / 30336),
            "arriba",
            POSITIVO,
        ),
        (
            "sep 2026",
            "Septiembre 2026: US$ 280,00",
            round(200 * 28000 / 30336),
            "arriba",
            POSITIVO,
        ),
        ("oct 2026", "Octubre 2026: US$ 303,36", 200, "arriba", POSITIVO),
    ]
    # Sin negativos, toda la altura queda arriba de la línea de 0.
    assert _alturas_de_zona(ahorro) == (200, 0)
    assert _tabla_de(ahorro) == [
        ("ago 2026", "US$ 250,00"),
        ("sep 2026", "US$ 280,00"),
        ("oct 2026", "US$ 303,36"),
    ]
    # Sin meses "s/cot." no aparece la aclaración.
    assert not any("s/cot." in t for t in textos(ahorro))


def test_ca_41_2_cambiar_la_cotizacion_cambia_solo_ese_punto(con):
    # CA-41.2: la cotización de 2026-10 pasa a 1.700 (con Ctrl+K desde Gráficos).
    _tres_meses_de_ahorro(con)
    app = _app(con, "Gráficos")
    app._al_presionar_tecla(tecla("K", ctrl=True))
    _guardar_cotizacion(app, "1.700")
    tabla = _tabla_de(app.pantalla("Gráficos").ahorro)
    assert tabla == [
        ("ago 2026", "US$ 250,00"),
        ("sep 2026", "US$ 280,00"),
        ("oct 2026", "US$ 356,11"),
    ]
    assert _barras(app.pantalla("Gráficos").ahorro)[2][1] == "Octubre 2026: US$ 356,11"


def test_ca_41_3_mes_sin_cotizacion_sin_barra(con):
    # CA-41.3: un mes sin cotización y con gastos: etiqueta "s/cot.", sin barra, sin
    # error; aclaración debajo y "sin cotización" en la tabla.
    otros = _cat(con, "Otros")
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, None)
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 100000, "unico")
    app = _app(con, "Gráficos")
    ahorro = app.pantalla("Gráficos").ahorro
    barras = _barras(ahorro)
    assert barras[0][:4] == ("sep 2026", "Septiembre 2026: US$ 1.200,00", 200, "arriba")
    assert barras[1] == ("oct 2026\ns/cot.", None, None, None, None)
    assert 'Los meses marcados "s/cot." no tienen cotización cargada.' in textos(ahorro)
    assert _tabla_de(ahorro) == [
        ("sep 2026", "US$ 1.200,00"),
        ("oct 2026", "sin cotización"),
    ]


def test_ahorro_negativo_baja_de_la_linea_de_cero(con):
    # §3.8: el ahorro negativo se dibuja hacia abajo, en color negativo; las zonas de
    # arriba y abajo suman 200 y guardan la proporción.
    otros = _cat(con, "Otros")
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    gastos.agregar_gasto(con, sep, "Gastos", otros, 147200000, "unico")  # +280,00
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 208000000, "unico")  # -100,00
    app = _app(con, "Gráficos")
    ahorro = app.pantalla("Gráficos").ahorro
    barras = _barras(ahorro)
    assert barras[0] == (
        "sep 2026",
        "Septiembre 2026: US$ 280,00",
        147,
        "arriba",
        POSITIVO,
    )
    assert barras[1] == ("oct 2026", "Octubre 2026: -US$ 100,00", 53, "abajo", NEGATIVO)
    assert _alturas_de_zona(ahorro) == (147, 53)


def test_ahorro_todo_negativo(con):
    # Borde: solo negativos: no hay zona de arriba y la barra mayor ocupa los 200.
    otros = _cat(con, "Otros")
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 208000000, "unico")
    app = _app(con, "Gráficos")
    ahorro = app.pantalla("Gráficos").ahorro
    assert _barras(ahorro) == [
        ("oct 2026", "Octubre 2026: -US$ 100,00", 200, "abajo", NEGATIVO)
    ]
    assert _alturas_de_zona(ahorro) == (0, 200)


def test_ahorro_cero_sin_barra_y_sin_error(con):
    # Borde: ahorro exactamente 0 en el único mes: ninguna barra, sin división por 0.
    otros = _cat(con, "Otros")
    oct_ = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 192000000, "unico")
    app = _app(con, "Gráficos")
    ahorro = app.pantalla("Gráficos").ahorro
    assert _barras(ahorro) == [("oct 2026", None, None, None, None)]
    assert _tabla_de(ahorro) == [("oct 2026", "US$ 0,00")]


def test_meta_de_ahorro_en_el_grafico(con, mes_id):
    # §3.8: con meta se ve "Meta: US$ X"; sin meta, no.
    app = _app(con, "Gráficos")
    assert not any(
        t.startswith("Meta:") for t in textos(app.pantalla("Gráficos").ahorro)
    )
    configuracion.guardar_meta(con, 50000)
    app.refrescar()
    assert "Meta: US$ 500,00" in textos(app.pantalla("Gráficos").ahorro)


# ---------------------------------------------------------------------------
# 3. Previsión de gastos (CA-42.1)
# ---------------------------------------------------------------------------


def test_ca_42_1_grafico_de_prevision_igual_a_la_tabla(con):
    # CA-42.1: 12 barras con los mismos valores que la tabla de Previsión (810.000
    # hasta feb 2027 y 800.000 desde mar 2027).
    _base(con)
    app = _app(con, "Previsión")
    tabla = [(f[0], f[1]) for f in _filas(app)]
    ir(app, "Gráficos")
    prev = app.pantalla("Gráficos").prevision
    assert _tabla_de(prev) == tabla
    barras = _barras(prev)
    assert [b[0] for b in barras] == _meses_de_la_tabla()
    assert barras[0][1] == "Noviembre 2026: $ 810.000"
    assert barras[4][1] == "Marzo 2027: $ 800.000"
    assert [b[2] for b in barras] == [200] * 4 + [round(200 * 800000 / 810000)] * 8
    assert {b[3] for b in barras} == {"arriba"}
    assert "Gastos estimados de los próximos 12 meses" in textos(prev)


def test_ca_42_1_caso_38_8_en_el_grafico(con):
    # CA-42.1 en el caso CA-38.8: 844.000 y 834.000.
    b = _base(con)
    _claude(con, b.oct, 160000)
    meses.editar_cotizacion(con, b.oct, 170000)
    app = _app(con, "Gráficos")
    valores = [v for _, v in _tabla_de(app.pantalla("Gráficos").prevision)]
    assert valores == ["$ 844.000"] * 4 + ["$ 834.000"] * 8


def test_grafico_de_prevision_no_depende_del_mes(con):
    # Como la tabla (CA-38.1): con 2026-09 seleccionado, el mismo gráfico.
    b = _base(con)
    app = _app(con, "Gráficos")
    antes = _tabla_de(app.pantalla("Gráficos").prevision)
    app.seleccionar_mes(b.sep)
    assert _tabla_de(app.pantalla("Gráficos").prevision) == antes


def test_grafico_de_prevision_sin_mes_actual(con):
    # §3.8: sin el mes actual, solo el texto "Creá el mes …"; las otras pestañas andan.
    meses.crear_primer_mes(con, 2026, 8, 120000, 160000)
    meses.crear_mes_siguiente(con, 120000, 160000)
    app = _app(con, "Gráficos")
    g = app.pantalla("Gráficos")
    assert textos(g.prevision) == ["Creá el mes Octubre 2026 para ver la previsión."]
    assert textos(g.categorias) == ["No hay gastos en Septiembre 2026 para graficar."]
    assert len(_barras(g.ahorro)) == 2


def test_grafico_de_prevision_todo_en_cero(con, mes_id):
    # Borde: sin fijos ni cuotas, 12 meses en $ 0: sin barras y sin error.
    app = _app(con, "Gráficos")
    barras = _barras(app.pantalla("Gráficos").prevision)
    assert len(barras) == 12
    assert {b[1:] for b in barras} == {(None, None, None, None)}


def test_grafico_de_prevision_sin_cotizacion_igual_se_ve(con):
    # Sin cotización en el mes actual, los gastos en pesos se grafican igual.
    b = _base(con)
    _quitar_cotizacion(con, b.oct)
    app = _app(con, "Gráficos")
    valores = [v for _, v in _tabla_de(app.pantalla("Gráficos").prevision)]
    assert valores == ["$ 810.000"] * 4 + ["$ 800.000"] * 8


# ===========================================================================
# Ajustes → Apariencia (§3.10)
# ===========================================================================


def _apariencia(app):
    ajustes = ir(app, "Ajustes")
    ajustes.pestanas.selected_index = 4
    ajustes.refrescar()
    return ajustes.apariencia


def test_apariencia_opciones_y_valor_por_defecto(con, mes_id):
    # §3.10: tres opciones; sin elegir nada, queda marcado "Como el sistema".
    app = _app(con, "Gastos")
    ap = _apariencia(app)
    radios = de_tipo(ap.opciones, ft.Radio)
    assert [(r.value, r.label) for r in radios] == [
        ("claro", "Claro"),
        ("oscuro", "Oscuro"),
        ("sistema", "Como el sistema"),
    ]
    assert ap.opciones.value == "sistema"
    assert (
        "Atajos: Ctrl+N nuevo, Ctrl+K cotización, Ctrl+Shift+N mes nuevo, "
        "Alt+← / Alt+→ cambiar de mes." in textos(ap.control)
    )


def test_apariencia_muestra_el_tema_guardado(con, mes_id):
    configuracion.guardar_tema(con, "oscuro")
    app = _app(con, "Gastos")
    assert _apariencia(app).opciones.value == "oscuro"


@pytest.mark.parametrize(
    ("tema", "modo"),
    [
        ("claro", ft.ThemeMode.LIGHT),
        ("oscuro", ft.ThemeMode.DARK),
        ("sistema", ft.ThemeMode.SYSTEM),
    ],
)
def test_elegir_tema_guarda_aplica_y_avisa(con, tema, modo):
    # §3.10: elegir un tema (con el RadioGroup) lo guarda, cambia theme_mode, vuelve a
    # armar la ventana sin perder el mes ni la pantalla y avisa "Tema actualizado".
    b = _base(con)
    app = _app(con, "Ajustes", b.sep)
    ap = _apariencia(app)
    ap.opciones.value = tema
    ap.opciones.on_change(SimpleNamespace(control=ap.opciones))
    assert configuracion.obtener_tema(con) == tema
    assert app.page.theme_mode == modo
    assert app.page.avisos()[-1] == "Tema actualizado"
    assert nombre_visible(app) == "Ajustes"
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert app.mes_id == b.sep


def test_elegir_tema_mantiene_la_pestana_apariencia(con, mes_id):
    # §3.10: el usuario elige el tema en la pestaña Apariencia; al rearmarse la
    # ventana tiene que seguir viendo esa pestaña (y su opción marcada), no volver a
    # "Categorías".
    app = _app(con, "Gastos")
    _apariencia(app).elegir("oscuro")
    ajustes = app.pantalla("Ajustes")
    assert ajustes.pestanas.selected_index == 4
    assert ajustes.apariencia.opciones.value == "oscuro"


def test_elegir_oscuro_cambia_los_colores_de_estado(con):
    # Los colores semánticos se eligen al dibujar: después de pasar a oscuro, la fila
    # con liberación de la previsión usa el positivo suave del tema oscuro.
    _base(con)
    app = _app(con, "Gastos")
    _apariencia(app).elegir("oscuro")
    ir(app, "Previsión")
    assert _tabla(app).rows[0].color == POSITIVO_SUAVE_OSCURO
    _apariencia(app).elegir("claro")
    ir(app, "Previsión")
    assert _tabla(app).rows[0].color == POSITIVO_SUAVE


def test_elegir_tema_con_el_mes_borrado_por_detras(con):
    # Borde: el mes visto se borró por detrás; elegir el tema no rompe y pasa al
    # último mes que queda.
    b = _base(con)
    app = _app(con, "Gastos")
    ap = _apariencia(app)
    meses.borrar_ultimo_mes(con, b.oct)
    ap.elegir("oscuro")
    assert configuracion.obtener_tema(con) == "oscuro"
    assert mes_seleccionado(app) == "Septiembre 2026"


@pytest.mark.parametrize(
    ("tema", "modo"),
    [
        (None, ft.ThemeMode.SYSTEM),
        ("claro", ft.ThemeMode.LIGHT),
        ("oscuro", ft.ThemeMode.DARK),
        ("sistema", ft.ThemeMode.SYSTEM),
    ],
)
@pytest.mark.parametrize("con_meses", [True, False])
def test_al_abrir_se_aplica_el_tema_guardado(con, tema, modo, con_meses):
    # §3.10: el tema guardado se aplica al abrir la app (también en el primer uso).
    if tema is not None:
        configuracion.guardar_tema(con, tema)
    if con_meses:
        meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    pagina = PaginaFalsa()
    Aplicacion(pagina, con).iniciar()
    assert pagina.theme_mode == modo


def test_al_abrir_con_un_tema_invalido_guardado_usa_el_sistema(con):
    # Borde: un valor raro en la base (editado a mano) no rompe: como el sistema.
    with con:
        con.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('tema', 'rosa')"
        )
    pagina = PaginaFalsa()
    Aplicacion(pagina, con).iniciar()
    assert pagina.theme_mode == ft.ThemeMode.SYSTEM


@pytest.mark.parametrize(
    ("tema", "modo"),
    [
        ("claro", ft.ThemeMode.LIGHT),
        ("oscuro", ft.ThemeMode.DARK),
        ("sistema", ft.ThemeMode.SYSTEM),
        ("cualquiera", ft.ThemeMode.SYSTEM),
    ],
)
def test_aplicar_tema(tema, modo):
    # estilos.aplicar_tema: cada tema con su modo de Flet; uno desconocido = sistema.
    pagina = PaginaFalsa()
    estilos.aplicar_tema(pagina, tema)
    assert pagina.theme_mode == modo
    assert pagina.theme is not None
    assert pagina.dark_theme is not None


# ===========================================================================
# Ronda 25: verificación de BUG-23 y O47
# ===========================================================================


@pytest.mark.parametrize("tema", ["claro", "oscuro", "sistema"])
def test_bug23_la_opcion_elegida_queda_marcada_en_apariencia(con, tema):
    # BUG-23: después de elegir, se sigue en Ajustes → Apariencia, con la opción
    # elegida marcada, el mes de antes y el aviso.
    b = _base(con)
    app = _app(con, "Ajustes", b.sep)
    ap = _apariencia(app)
    ap.opciones.value = tema
    ap.opciones.on_change(SimpleNamespace(control=ap.opciones))
    ajustes = app.pantalla("Ajustes")
    assert nombre_visible(app) == "Ajustes"
    assert ajustes.pestanas.selected_index == ajustes.indice_de(ajustes.apariencia)
    assert ajustes.pestanas.selected_index == 4
    assert ajustes.apariencia.opciones.value == tema
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert app.page.avisos()[-1] == "Tema actualizado"


def test_bug23_elegir_dos_veces_seguidas(con, mes_id):
    # Elegir otro tema sobre la pestaña ya rearmada sigue funcionando.
    app = _app(con, "Ajustes")
    _apariencia(app).elegir("oscuro")
    app.pantalla("Ajustes").apariencia.elegir("claro")
    ajustes = app.pantalla("Ajustes")
    assert ajustes.pestanas.selected_index == 4
    assert ajustes.apariencia.opciones.value == "claro"
    assert app.page.theme_mode == ft.ThemeMode.LIGHT
    assert app.page.avisos()[-2:] == ["Tema actualizado", "Tema actualizado"]


def test_indice_de_cada_pestana(con, mes_id):
    # indice_de devuelve la posición de cada pestaña en el orden en que se ven.
    ajustes = _app(con, "Ajustes").pantalla("Ajustes")
    pestanas = [*ajustes.listas, ajustes.meta, ajustes.apariencia]
    assert [ajustes.indice_de(p) for p in pestanas] == [0, 1, 2, 3, 4]


def test_bug23_con_el_mes_borrado_por_detras_queda_otro_mes(con):
    # Borde: el mes visto se borró por detrás y quedan otros: no rompe, guarda el
    # tema, pasa al último mes que queda y avisa.
    b = _base(con)
    app = _app(con, "Ajustes")
    ap = _apariencia(app)
    meses.borrar_ultimo_mes(con, b.oct)
    ap.elegir("oscuro")
    assert configuracion.obtener_tema(con) == "oscuro"
    assert app.page.theme_mode == ft.ThemeMode.DARK
    assert app.mes_id == b.sep
    assert mes_seleccionado(app) == "Septiembre 2026"
    assert "Tema actualizado" in app.page.avisos()


def test_bug23_con_el_unico_mes_borrado_por_detras(con, mes_id):
    # Borde: se borró el único mes: elegir el tema no rompe y va al primer uso.
    app = _app(con, "Ajustes")
    ap = _apariencia(app)
    meses.borrar_ultimo_mes(con, mes_id)
    ap.elegir("oscuro")
    assert configuracion.obtener_tema(con) == "oscuro"
    assert app.mes_id is None
    assert app.page.title == "Gastos – Bienvenido"
    assert app.page.theme_mode == ft.ThemeMode.DARK


# --- O47: ninguna barra supera la altura de su zona -------------------------


def _columnas_de(control):
    """[(alto zona arriba, alto zona abajo, alto barra arriba, alto barra abajo)]."""
    salida = []
    for col in control.controls:
        arriba, _, abajo, _ = col.controls
        salida.append(
            (
                arriba.height,
                abajo.height,
                arriba.content.height if arriba.content.bgcolor else None,
                abajo.content.height if abajo.content.bgcolor else None,
            )
        )
    return salida


def _revisar_zonas(control, valores):
    """Invariantes de O47 sobre lo que dibujó _barras con esos valores."""
    columnas = _columnas_de(control)
    hay_negativos = any(v is not None and v < 0 for v in valores)
    for (zona_arriba, zona_abajo, barra_arriba, barra_abajo), v in zip(
        columnas, valores, strict=True
    ):
        # Las zonas suman 200 si hay negativos; si no, todo es zona de arriba.
        assert zona_arriba + zona_abajo == (200 if hay_negativos else zona_arriba)
        if barra_arriba is not None:
            assert v > 0
            assert barra_arriba <= zona_arriba
        if barra_abajo is not None:
            assert v < 0
            assert barra_abajo <= zona_abajo
        # Una barra nunca va del lado equivocado de la línea de 0.
        if v is None or v == 0:
            assert (barra_arriba, barra_abajo) == (None, None)


@pytest.mark.parametrize(
    "valores",
    [
        [100000000, -1],  # positivo enorme, negativo mínimo (antes: 1 px en zona 0)
        [-100000000, 1],  # negativo enorme, positivo mínimo
        [1, -1],
        [1, -3],
        [3, -1],
        [199, -1],
        [1, -199],
        [397, -3],  # 200·397/400 = 198,5: redondeo en el medio
        [3, -397],
        [1, 1, -100000000, None, 0],
        [25000, -12345, 7, -3, None],
    ],
)
def test_o47_barras_dentro_de_su_zona(con, mes_id, valores):
    # O47: con valores que fuerzan el redondeo, ninguna barra pasa del alto de su
    # zona (positivas ≤ zona de arriba, negativas ≤ zona de abajo).
    g = _app(con, "Gráficos").pantalla("Gráficos")
    puntos = [(f"m{i}", v, f"t{i}", "") for i, v in enumerate(valores)]
    _revisar_zonas(g._barras(puntos), valores)


def test_o47_barrido_de_combinaciones(con, mes_id):
    # O47: barrido de pares (positivo, negativo) chicos y grandes; ninguna barra
    # se sale de su zona en ninguno.
    g = _app(con, "Gráficos").pantalla("Gráficos")
    montos = [1, 2, 3, 5, 7, 99, 100, 101, 397, 1000, 12345, 99999, 1000000]
    for positivo in montos:
        for negativo in montos:
            valores = [positivo, -negativo, positivo // 2 or None, -(negativo // 3)]
            puntos = [(f"m{i}", v, "", "") for i, v in enumerate(valores)]
            _revisar_zonas(g._barras(puntos), valores)


def test_o47_en_pantalla_ahorro_grande_y_deficit_minimo(con):
    # O47 en la pantalla: Septiembre ahorra US$ 1.200,00 y Octubre tiene un déficit
    # de US$ 0,01. La barra de Octubre queda dentro de su zona (que es de 0 px).
    otros = _cat(con, "Otros")
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    gastos.agregar_gasto(con, oct_, "Gastos", otros, 192001600, "unico")  # -0,01
    app = _app(con, "Gráficos")
    ahorro = app.pantalla("Gráficos").ahorro
    assert _tabla_de(ahorro) == [
        ("sep 2026", "US$ 1.200,00"),
        ("oct 2026", "-US$ 0,01"),
    ]
    [fila] = [
        r
        for r in de_tipo(ahorro, ft.Row)
        if r.controls and all(isinstance(c, ft.Column) for c in r.controls)
    ]
    _revisar_zonas(fila, [120000, -1])
