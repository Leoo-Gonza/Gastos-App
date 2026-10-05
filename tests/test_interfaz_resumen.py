"""Pruebas de la interfaz del Resumen (paso 3b): barra superior con la cotización,
tarjetas, meta, capacidad, desglose, ingresos extra, cambios, diálogos de sueldo,
cotización y meta, pestaña "Meta de ahorro" de Ajustes y atajos (diseno.md §1.2,
§1.3, §3.2, §3.6, §3.10, §4.5, §4.6). Página falsa, sin ventanas; fechas fijas."""

from datetime import date, datetime

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.interfaz.dialogos import dialogo_cambio
from app.logica import cambios, catalogos, configuracion, gastos, ingresos, meses, pagos
from tests.ayudantes import id_por_nombre, insertar_plan
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
    tecla,
    textos,
    titulo_dialogo,
)

HOY = date(2026, 10, 4)
PENDIENTE = "#9A5800"
PENDIENTE_SUAVE = "#FFF1DC"
POSITIVO = "#1E7B34"
NEGATIVO = "#B3261E"


class FechaFija(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 4)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    monkeypatch.setattr(dialogo_cambio, "date", FechaFija)
    monkeypatch.setattr(cambios, "date", FechaFija)


@pytest.fixture
def app(app_en_inicio):
    """La app tal como arranca: en el Resumen de Octubre 2026 (S 1.200, K 1.600)."""
    return app_en_inicio


@pytest.fixture
def resumen(app):
    return app.pantalla("Resumen")


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _gasto(app, nombre, monto, tipo="unico"):
    gid = gastos.agregar_gasto(
        app.con, app.mes_id, nombre, _otros(app.con), monto, tipo
    )
    app.refrescar()
    return gid


def _base(app):
    """Gastos que suman 1.434.617 (base de los CA del módulo E)."""
    return _gasto(app, "Gastos del mes", 143461700)


# --- Lectura de las tarjetas ---


def _tarjetas(resumen):
    return de_tipo(resumen.cuerpo, ft.Card)


def _etiqueta(card):
    return card.content.content.controls[0].controls[0].value


def _tarjeta(resumen, etiqueta):
    encontradas = [c for c in _tarjetas(resumen) if _etiqueta(c) == etiqueta]
    assert len(encontradas) == 1, (
        f"No hay tarjeta {etiqueta!r}: {[_etiqueta(c) for c in _tarjetas(resumen)]}"
    )
    return encontradas[0]


def _principal(card):
    """El control principal de la tarjeta (monto, o texto si falta la cotización)."""
    return card.content.content.controls[1]


def _monto(card):
    """Texto del monto principal (aunque esté en un Row con ícono)."""
    principal = _principal(card)
    if isinstance(principal, ft.Text):
        return principal
    return [t for t in de_tipo(principal, ft.Text)][-1]


def _abajo(card):
    return card.content.content.controls[2:]


def _textos_abajo(card):
    salida = []
    for control in _abajo(card):
        salida += [t for t in textos(control) if t]
    return salida


def _enfocado(pagina):
    return pagina.tareas[-1].__self__


def _campo(dialogo):
    return dialogo.content.controls[0]


# ---------------------------------------------------------------------------
# Barra superior: cotización (§1.2, Ctrl+K)
# ---------------------------------------------------------------------------


def test_barra_con_cotizacion(app):
    assert mes_seleccionado(app) == "Octubre 2026"
    assert app._texto_cotizacion.value == "Cotización $ 1.600 por US$"
    assert app._icono_cotizacion.icon == ft.Icons.EDIT_OUTLINED
    assert app._cotizacion.bgcolor is None
    assert app._cotizacion.tooltip == "Editar la cotización (Ctrl+K)"


def test_ca_25_4_barra_con_cotizacion_con_centavos(app):
    meses.editar_cotizacion(app.con, app.mes_id, 143250)
    app.refrescar()
    assert app._texto_cotizacion.value == "Cotización $ 1.432,50 por US$"


def test_barra_sin_cotizacion(pagina, con):
    meses.crear_primer_mes(con, 2026, 10, 120000, None)
    app = Aplicacion(pagina, con)
    app.iniciar()
    assert app._texto_cotizacion.value == "Cotización sin cargar – Cargar"
    assert app._icono_cotizacion.icon == ft.Icons.WARNING_AMBER
    assert app._cotizacion.bgcolor == PENDIENTE_SUAVE
    assert app._texto_cotizacion.color == PENDIENTE
    # Al cargarla, la barra vuelve a la normalidad.
    app._cotizacion.on_click(None)
    _campo(dialogo_arriba(app)).value = "1.600"
    clic(dialogo_arriba(app), "Guardar")
    assert app._texto_cotizacion.value == "Cotización $ 1.600 por US$"
    assert (app._cotizacion.bgcolor, app._texto_cotizacion.color) == (None, None)


def test_tooltip_de_la_cotizacion_en_macos(con, mes_id):
    app = Aplicacion(PaginaFalsa(plataforma=ft.PagePlatform.MACOS), con)
    app.iniciar()
    assert app._cotizacion.tooltip == "Editar la cotización (⌘K)"


def test_clic_en_la_barra_abre_la_cotizacion(app):
    app._cotizacion.on_click(None)
    assert titulo_dialogo(dialogo_arriba(app)) == "Cotización de Octubre 2026"


@pytest.mark.parametrize("pantalla", ["Resumen", "Gastos", "Ajustes"])
@pytest.mark.parametrize("key", ["K", "k"])
def test_ctrl_k_abre_la_cotizacion_desde_cualquier_pantalla(app, pantalla, key):
    ir(app, pantalla)
    app._al_presionar_tecla(tecla(key, ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Cotización de Octubre 2026"


def test_ctrl_k_con_un_dialogo_abierto_se_ignora(app):
    app._al_presionar_tecla(tecla("N", ctrl=True))
    app._al_presionar_tecla(tecla("K", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Registrar cambio de dólares"
    assert len(app._dialogos) == 1


def test_ctrl_k_en_primer_uso_no_hace_nada(app_vacia):
    app_vacia._al_presionar_tecla(tecla("K", ctrl=True))
    assert app_vacia.hay_dialogo_abierto() is False


def test_ctrl_k_sin_modificador_no_hace_nada(app):
    app._al_presionar_tecla(tecla("K"))
    assert app.hay_dialogo_abierto() is False


# ---------------------------------------------------------------------------
# Diálogo de cotización (§3.6, CA-25.x)
# ---------------------------------------------------------------------------


def test_dialogo_de_cotizacion_contenido(app):
    app.editar_cotizacion()
    dialogo = dialogo_arriba(app)
    assert _campo(dialogo).value == "1.600"
    assert _campo(dialogo).suffix == "por US$"
    assert _campo(dialogo).autofocus is True
    assert (
        "Se usa para calcular los dólares a cambiar. No modifica los cambios ya "
        "registrados ni los gastos en dólares ya cargados." in textos(dialogo)
    )
    assert not any("en dólares. Si querés" in t for t in textos(dialogo))


@pytest.mark.parametrize(("cantidad", "texto"), [(1, "1 gasto"), (2, "2 gastos")])
def test_dialogo_de_cotizacion_avisa_gastos_en_dolares(app, cantidad, texto):
    for i in range(cantidad):
        gastos.agregar_gasto(
            app.con,
            app.mes_id,
            f"Sub {i}",
            _otros(app.con),
            None,
            "fijo",
            None,
            "USD",
            2000,
            160000,
        )
    app.editar_cotizacion()
    assert (
        f"Este mes tiene {texto} en dólares. Si querés actualizarlos, editalos uno por uno."
        in textos(dialogo_arriba(app))
    )


def test_ca_25_1_cambiar_la_cotizacion_desde_el_dialogo(app, resumen, pagina):
    _base(app)
    app.editar_cotizacion()
    dialogo = dialogo_arriba(app)
    _campo(dialogo).value = "1.700"
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert pagina.avisos()[-1] == "Cotización actualizada: $ 1.700 por US$"
    assert app._texto_cotizacion.value == "Cotización $ 1.700 por US$"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 843,89"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 356,11"


def test_cotizacion_con_centavos_en_el_aviso(app, pagina):
    app.editar_cotizacion()
    _campo(dialogo_arriba(app)).value = "1.432,50"
    clic(dialogo_arriba(app), "Guardar")
    assert pagina.avisos()[-1] == "Cotización actualizada: $ 1.432,50 por US$"


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("", "Ingresá la cotización."),
        ("0", "La cotización tiene que ser mayor a 0."),  # CA-25.2
        ("1600.5", "Usá coma para los decimales. Ej.: 66.020,12"),
    ],
)
def test_ca_25_2_cotizacion_invalida_en_el_dialogo(app, pagina, texto, mensaje):
    app.editar_cotizacion()
    dialogo = dialogo_arriba(app)
    _campo(dialogo).value = texto
    clic(dialogo, "Guardar")
    assert _campo(dialogo).error == mensaje
    assert dialogo.open is True
    assert _enfocado(pagina) is _campo(dialogo)
    assert meses.obtener_mes(app.con, app.mes_id)["cotizacion_cent"] == 160000


def test_cancelar_la_cotizacion_no_cambia_nada(app):
    app.editar_cotizacion()
    dialogo = dialogo_arriba(app)
    _campo(dialogo).value = "9.999"
    clic(dialogo, "Cancelar")
    assert meses.obtener_mes(app.con, app.mes_id)["cotizacion_cent"] == 160000


def test_enter_guarda_la_cotizacion(app):
    app.editar_cotizacion()
    campo = _campo(dialogo_arriba(app))
    campo.value = "1.650"
    campo.on_submit(None)
    assert meses.obtener_mes(app.con, app.mes_id)["cotizacion_cent"] == 165000


# ---------------------------------------------------------------------------
# Tarjetas del Resumen (§3.2, CA-35.x)
# ---------------------------------------------------------------------------


def test_arranca_en_el_resumen(app, resumen):
    assert nombre_visible(app) == "Resumen"
    assert resumen.titulo.value == "Resumen de Octubre 2026"
    contenido = textos(resumen.cuerpo)
    assert "EN PESOS" in contenido and "EN DÓLARES" in contenido
    assert [_etiqueta(c) for c in _tarjetas(resumen)] == [
        "Total gastos",
        "Falta pagar",
        "Pesos a cubrir",
        "Sueldo",
        "Dólares a cambiar",
        "Ahorro del mes",
        "Capacidad de endeudamiento",
    ]


def test_ca_35_1_tarjetas_con_pagos(app, resumen):
    a = _gasto(app, "Alquiler", 40000000, "fijo")
    _gasto(app, "Resto", 103461700)
    pagos.marcar_pagado(app.con, a, HOY)
    app.refrescar()
    total = _tarjeta(resumen, "Total gastos")
    assert (_monto(total).value, _textos_abajo(total)) == ("$ 1.434.617", ["2 gastos"])
    falta = _tarjeta(resumen, "Falta pagar")
    assert (_monto(falta).value, _monto(falta).color) == ("$ 1.034.617", PENDIENTE)
    assert _textos_abajo(falta) == ["Pagado $ 400.000"]
    cubrir = _tarjeta(resumen, "Pesos a cubrir")
    assert _monto(cubrir).value == "$ 1.434.617"
    assert _textos_abajo(cubrir) == ["Gastos − extras en pesos − pesos de cambios"]
    assert _monto(_tarjeta(resumen, "Sueldo")).value == "US$ 1.200,00"
    cambiar = _tarjeta(resumen, "Dólares a cambiar")
    assert _monto(cambiar).value == "US$ 896,64"
    assert _textos_abajo(cambiar) == ["$ 1.434.617 ÷ $ 1.600"]
    ahorro = _tarjeta(resumen, "Ahorro del mes")
    assert (_monto(ahorro).value, _monto(ahorro).color) == ("US$ 303,36", POSITIVO)


def test_un_gasto_en_singular_y_todo_pagado_en_verde(app, resumen):
    gid = _gasto(app, "Alquiler", 26000000, "fijo")
    pagos.marcar_pagado(app.con, gid, HOY)
    app.refrescar()
    assert _textos_abajo(_tarjeta(resumen, "Total gastos")) == ["1 gasto"]
    falta = _tarjeta(resumen, "Falta pagar")
    assert (_monto(falta).value, _monto(falta).color) == ("$ 0", POSITIVO)


def test_rn_19_el_resumen_se_actualiza_al_volver_de_gastos(app, resumen):
    assert _monto(_tarjeta(resumen, "Total gastos")).value == "$ 0"
    ir(app, "Gastos")
    gastos.agregar_gasto(
        app.con, app.mes_id, "Nafta", _otros(app.con), 3000000, "unico"
    )
    ir(app, "Resumen")
    assert _monto(_tarjeta(resumen, "Total gastos")).value == "$ 30.000"


def test_ca_35_3_deficit(app, resumen):
    _base(app)
    meses.editar_sueldo(app.con, app.mes_id, 80000)
    app.refrescar()
    card = _tarjeta(resumen, "Déficit")
    icono = de_tipo(_principal(card), ft.Icon)[0]
    assert (icono.icon, icono.color) == (ft.Icons.TRENDING_DOWN, NEGATIVO)
    assert (_monto(card).value, _monto(card).color) == ("-US$ 96,64", NEGATIVO)


def test_ca_27_3_y_35_4_pesos_sobrantes(app, resumen):
    _gasto(app, "Gastos", 10000000)
    cambios.agregar_cambio(app.con, app.mes_id, 10000, 160000, fecha=HOY)
    app.refrescar()
    cubrir = _tarjeta(resumen, "Pesos a cubrir")
    assert _monto(cubrir).value == "$ 0"
    [sobrante] = _abajo(cubrir)
    assert sobrante.value == "Pesos sobrantes $ 60.000 = US$ 37,50 (se suman al ahorro)"
    assert sobrante.color == POSITIVO
    cambiar = _tarjeta(resumen, "Dólares a cambiar")
    assert (_monto(cambiar).value, _textos_abajo(cambiar)) == ("US$ 0,00", [])
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 1.137,50"


def _app_sin_cotizacion(con):
    meses.crear_primer_mes(con, 2026, 10, 120000, None)
    app = Aplicacion(PaginaFalsa(), con)
    app.iniciar()
    return app


def _dice_carga_la_cotizacion(card):
    principal = _principal(card)
    return (
        principal.value == "Cargá la cotización"
        and principal.color == PENDIENTE
        and principal.size == 16
        and hay_boton(card, "Cargar cotización")
    )


def test_ca_25_3_sin_cotizacion_y_con_gastos(con):
    app = _app_sin_cotizacion(con)
    _base(app)
    resumen = app.pantalla("Resumen")
    for etiqueta in (
        "Dólares a cambiar",
        "Ahorro del mes",
        "Capacidad de endeudamiento",
    ):
        assert _dice_carga_la_cotizacion(_tarjeta(resumen, etiqueta)), etiqueta
    # Lo que no depende de la cotización se ve normal.
    assert _monto(_tarjeta(resumen, "Total gastos")).value == "$ 1.434.617"
    assert _monto(_tarjeta(resumen, "Pesos a cubrir")).value == "$ 1.434.617"
    # "Cargar cotización" abre el diálogo.
    clic(_tarjeta(resumen, "Ahorro del mes"), "Cargar cotización")
    assert titulo_dialogo(dialogo_arriba(app)) == "Cotización de Octubre 2026"
    assert (_campo(dialogo_arriba(app)).value or "") == ""


def test_sobrantes_sin_cotizacion_no_muestran_dolares(con):
    app = _app_sin_cotizacion(con)
    _gasto(app, "Gastos", 10000000)
    cambios.agregar_cambio(app.con, app.mes_id, 10000, 160000, fecha=HOY)
    app.refrescar()
    [sobrante] = _abajo(_tarjeta(app.pantalla("Resumen"), "Pesos a cubrir"))
    assert sobrante.value == "Pesos sobrantes $ 60.000"


def test_ca_27_5_sin_cotizacion_con_f_cero(con):
    # F = 0: el ahorro se calcula; la capacidad sigue pidiendo la cotización (O26).
    app = _app_sin_cotizacion(con)
    _gasto(app, "Gastos", 16000000)
    cambios.agregar_cambio(app.con, app.mes_id, 10000, 160000, fecha=HOY)
    app.refrescar()
    resumen = app.pantalla("Resumen")
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 1.100,00"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 0,00"
    assert _dice_carga_la_cotizacion(_tarjeta(resumen, "Capacidad de endeudamiento"))


def test_ca_23_2_sueldo_cero(app, resumen):
    _base(app)
    meses.editar_sueldo(app.con, app.mes_id, 0)
    app.refrescar()
    aviso = resumen.cuerpo.controls[0]
    assert "El sueldo de este mes es 0." in textos(aviso)
    assert aviso.bgcolor == PENDIENTE_SUAVE
    sueldo = _tarjeta(resumen, "Sueldo")
    assert de_tipo(_principal(sueldo), ft.Icon)[0].icon == ft.Icons.WARNING_AMBER
    assert _monto(sueldo).value == "US$ 0,00"
    assert _monto(_tarjeta(resumen, "Déficit")).value == "-US$ 896,64"


def test_sin_aviso_de_sueldo_si_no_es_cero(app, resumen):
    assert "El sueldo de este mes es 0." not in textos(resumen.cuerpo)


# ---------------------------------------------------------------------------
# Diálogo de sueldo (§3.6, CA-23.x)
# ---------------------------------------------------------------------------


def _abrir_sueldo(resumen, app):
    [lapiz] = [b for b in de_tipo(_tarjeta(resumen, "Sueldo"), ft.IconButton)]
    assert lapiz.tooltip == "Editar sueldo"
    lapiz.on_click(None)
    return dialogo_arriba(app)


def test_ca_23_1_editar_el_sueldo(app, resumen, pagina):
    _base(app)
    dialogo = _abrir_sueldo(resumen, app)
    assert titulo_dialogo(dialogo) == "Sueldo de Octubre 2026"
    assert _campo(dialogo).value == "1.200"
    assert (_campo(dialogo).prefix, _campo(dialogo).suffix) == ("US$ ", "USD")
    _campo(dialogo).value = "1.300"
    clic(dialogo, "Guardar")
    assert pagina.avisos()[-1] == "Sueldo actualizado: US$ 1.300,00"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 403,36"


def test_sueldo_cero_desde_el_dialogo(app, resumen, pagina):
    dialogo = _abrir_sueldo(resumen, app)
    _campo(dialogo).value = "0"
    clic(dialogo, "Guardar")
    assert pagina.avisos()[-1] == "Sueldo actualizado: US$ 0,00"
    assert "El sueldo de este mes es 0." in textos(resumen.cuerpo)


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("", "Ingresá el sueldo. Si este mes no cobrás, poné 0."),
        ("1.2.3", "Escribí solo números. Ej.: 66.020,12"),
        ("1200.5", "Usá coma para los decimales. Ej.: 66.020,12"),
        ("999.999.999.999,01", "El sueldo es demasiado grande."),
    ],
)
def test_sueldo_invalido_en_el_dialogo(app, resumen, pagina, texto, mensaje):
    dialogo = _abrir_sueldo(resumen, app)
    _campo(dialogo).value = texto
    clic(dialogo, "Guardar")
    assert _campo(dialogo).error == mensaje
    assert _enfocado(pagina) is _campo(dialogo)
    assert meses.obtener_mes(app.con, app.mes_id)["sueldo_usd_cent"] == 120000


# ---------------------------------------------------------------------------
# Meta (RF-36, RN-39, CA-36.x)
# ---------------------------------------------------------------------------


def _bloque_meta(resumen, etiqueta="Ahorro del mes"):
    return _abajo(_tarjeta(resumen, etiqueta))[0]


def test_sin_meta_boton_definir(app, resumen):
    bloque = _bloque_meta(resumen)
    assert isinstance(bloque, ft.TextButton)
    assert bloque.content == "Definir meta de ahorro"
    assert de_tipo(resumen.cuerpo, ft.ProgressBar) == []
    bloque.on_click(None)
    dialogo = dialogo_arriba(app)
    assert titulo_dialogo(dialogo) == "Meta de ahorro"
    assert not hay_boton(dialogo, "Quitar meta")
    assert "Es la misma para todos los meses." in textos(dialogo)


def test_ca_36_1_meta_superada_y_luego_a_la_mitad(app, resumen, pagina):
    _base(app)
    _bloque_meta(resumen).on_click(None)
    _campo(dialogo_arriba(app)).value = "300"
    clic(dialogo_arriba(app), "Guardar")
    assert pagina.avisos()[-1] == "Meta de ahorro: US$ 300,00"
    bloque = _bloque_meta(resumen)
    assert hay_boton(bloque, "Meta US$ 300,00")
    [porcentaje] = [
        t for t in de_tipo(bloque, ft.Text) if t.value and t.value.endswith("%")
    ]
    assert (porcentaje.value, porcentaje.tooltip) == ("101 %", "101,12 %")
    [barra] = de_tipo(bloque, ft.ProgressBar)
    assert (barra.value, barra.color) == (1.0, POSITIVO)  # llena y en verde

    clic(bloque, "Meta US$ 300,00")
    dialogo = dialogo_arriba(app)
    assert _campo(dialogo).value == "300"
    assert hay_boton(dialogo, "Quitar meta")
    _campo(dialogo).value = "600"
    clic(dialogo, "Guardar")
    bloque = _bloque_meta(resumen)
    [porcentaje] = [
        t for t in de_tipo(bloque, ft.Text) if t.value and t.value.endswith("%")
    ]
    assert (porcentaje.value, porcentaje.tooltip) == ("51 %", "50,56 %")
    [barra] = de_tipo(bloque, ft.ProgressBar)
    assert barra.value == pytest.approx(0.5056)
    assert barra.color is None


def test_ca_36_2_ahorro_negativo_barra_en_cero(app, resumen):
    _base(app)
    configuracion.guardar_meta(app.con, 30000)
    meses.editar_sueldo(app.con, app.mes_id, 80000)
    app.refrescar()
    [barra] = de_tipo(_bloque_meta(resumen, "Déficit"), ft.ProgressBar)
    assert barra.value == 0.0


def test_rn_39_con_deficit_el_numero_muestra_el_valor_real(app, resumen):
    # RN-39: "La barra se limita entre 0 % y 100 %; el número muestra el valor real".
    # Ahorro −96,64 con meta 300 → −32,21 %: la barra en 0 %, el número "-32 %".
    _base(app)
    configuracion.guardar_meta(app.con, 30000)
    meses.editar_sueldo(app.con, app.mes_id, 80000)
    app.refrescar()
    bloque = _bloque_meta(resumen, "Déficit")
    [porcentaje] = [
        t for t in de_tipo(bloque, ft.Text) if t.value and t.value.endswith("%")
    ]
    assert porcentaje.tooltip == "-32,21 %"
    assert porcentaje.value == "-32 %"


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [("", "Ingresá la meta."), ("0", "La meta tiene que ser mayor a 0.")],  # CA-36.2
)
def test_meta_invalida_en_el_dialogo(app, resumen, texto, mensaje):
    _bloque_meta(resumen).on_click(None)
    dialogo = dialogo_arriba(app)
    _campo(dialogo).value = texto
    clic(dialogo, "Guardar")
    assert _campo(dialogo).error == mensaje
    assert configuracion.obtener_meta(app.con) is None


def test_quitar_la_meta_desde_el_dialogo(app, resumen, pagina):
    configuracion.guardar_meta(app.con, 30000)
    app.refrescar()
    clic(_bloque_meta(resumen), "Meta US$ 300,00")
    clic(dialogo_arriba(app), "Quitar meta")
    assert configuracion.obtener_meta(app.con) is None
    assert pagina.avisos()[-1] == "Meta de ahorro quitada"
    assert app.hay_dialogo_abierto() is False
    assert _bloque_meta(resumen).content == "Definir meta de ahorro"


# ---------------------------------------------------------------------------
# Capacidad de endeudamiento (RN-38, CA-37.x)
# ---------------------------------------------------------------------------


@pytest.fixture
def caso_37(app):
    """CA-37.1: fijos 785.300, cuota 41.117 (plan por SQL), único 15.000, meta 300."""
    con = app.con
    gastos.agregar_gasto(con, app.mes_id, "Fijos", _otros(con), 78530000, "fijo")
    plan = insertar_plan(con, "Avant Service", _otros(con), monto=4111700, cuotas=3)
    with con:
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Avant Service', ?, 4111700, 'cuota', ?)",
            (app.mes_id, _otros(con), plan),
        )
    gastos.agregar_gasto(con, app.mes_id, "Regalo", _otros(con), 1500000, "unico")
    configuracion.guardar_meta(con, 30000)
    app.refrescar()
    return app


def _calculo(card):
    [tile] = [c for c in _abajo(card) if isinstance(c, ft.ExpansionTile)]
    assert tile.title.value == "Ver cálculo"
    return [[t for t in textos(fila) if t] for fila in tile.controls]


def test_ca_37_1_capacidad_y_su_calculo(caso_37, resumen):
    card = _tarjeta(resumen, "Capacidad de endeudamiento")
    assert (_monto(card).value, _monto(card).color) == ("$ 613.583 por mes", None)
    assert card.content.border is None
    assert _calculo(card) == [
        ["Sueldo en pesos (US$ 1.200,00 × $ 1.600)", "$ 1.920.000"],
        ["− Gastos fijos y cuotas del mes", "$ 826.417"],
        ["− Meta de ahorro (US$ 300,00 × $ 1.600)", "$ 480.000"],
        ["= Capacidad de endeudamiento", "$ 613.583"],
        ["Los pagos únicos y los ingresos extra no se cuentan."],
    ]


def test_ca_37_2_sin_meta(caso_37, resumen):
    configuracion.quitar_meta(caso_37.con)
    caso_37.refrescar()
    card = _tarjeta(resumen, "Capacidad de endeudamiento")
    assert _monto(card).value == "$ 1.093.583 por mes"
    assert ["− Meta de ahorro (US$ 0,00 × $ 1.600)", "$ 0"] in _calculo(card)


def test_ca_37_3_capacidad_negativa(caso_37, resumen):
    configuracion.guardar_meta(caso_37.con, 100000)
    caso_37.refrescar()
    card = _tarjeta(resumen, "Capacidad de endeudamiento")
    assert (_monto(card).value, _monto(card).color) == ("-$ 506.417 por mes", NEGATIVO)
    assert "Sin capacidad de endeudamiento" in _textos_abajo(card)
    icono = de_tipo(card, ft.Icon)[0]
    assert (icono.icon, icono.color) == (ft.Icons.ERROR_OUTLINE, NEGATIVO)
    assert card.content.border is not None  # borde en color negativo


def test_ca_37_4_con_cotizacion_1700_desde_ctrl_k(caso_37, resumen):
    caso_37._al_presionar_tecla(tecla("K", ctrl=True))
    _campo(dialogo_arriba(caso_37)).value = "1.700"
    clic(dialogo_arriba(caso_37), "Guardar")
    assert (
        _monto(_tarjeta(resumen, "Capacidad de endeudamiento")).value
        == "$ 703.583 por mes"
    )


# ---------------------------------------------------------------------------
# "Cómo se calcula el ahorro" (§3.2)
# ---------------------------------------------------------------------------


def test_desglose_del_ahorro_con_el_ejemplo_del_diseno(app, resumen):
    # Ejemplo de §3.2: extra ARS 100.000, extra USD 50, cambio de 500 USD por 745.000.
    _base(app)
    ingresos.agregar_ingreso(app.con, app.mes_id, "Venta bici", "ARS", 10000000)
    ingresos.agregar_ingreso(app.con, app.mes_id, "Freelance", "USD", 5000)
    cambios.agregar_cambio(app.con, app.mes_id, 50000, 150000, 74500000, HOY)
    app.refrescar()
    [tile] = [c for c in resumen.cuerpo.controls if isinstance(c, ft.ExpansionTile)]
    assert tile.title.value == "Cómo se calcula el ahorro"
    filas = [
        [t for t in textos(f) if t]
        for f in tile.controls
        if not isinstance(f, ft.Divider)
    ]
    assert filas == [
        ["Total gastos", "$ 1.434.617"],
        ["− Ingresos extra en pesos", "$ 100.000"],
        ["− Pesos de cambios realizados", "$ 745.000"],
        ["= Pesos a cubrir", "$ 589.617"],
        ["÷ Cotización", "$ 1.600 por US$"],
        ["= Dólares a cambiar", "US$ 368,51"],
        ["Sueldo", "US$ 1.200,00"],
        ["+ Ingresos extra en dólares", "US$ 50,00"],
        ["− Dólares ya cambiados", "US$ 500,00"],
        ["− Dólares a cambiar", "US$ 368,51"],
        ["+ Pesos sobrantes en dólares", "US$ 0,00"],
        ["= Ahorro del mes", "US$ 381,49"],
    ]


def test_desglose_sin_cotizacion(con):
    app = _app_sin_cotizacion(con)
    _base(app)
    resumen = app.pantalla("Resumen")
    [tile] = [c for c in resumen.cuerpo.controls if isinstance(c, ft.ExpansionTile)]
    contenido = textos(tile)
    assert "Sin cotización no se pueden calcular los dólares." in contenido
    assert "= Ahorro del mes" not in contenido


# ---------------------------------------------------------------------------
# Ingresos extra (RF-24, §4.5, CA-24.x)
# ---------------------------------------------------------------------------


def _tabla_en(resumen, seccion):
    """La tabla (o el texto de vacío) que va debajo del título de sección."""
    for columna in resumen.cuerpo.controls:
        if isinstance(columna, ft.Column) and seccion in textos(columna.controls[0]):
            return columna
    raise AssertionError(seccion)


def _filas(tabla_col):
    [tabla] = de_tipo(tabla_col, ft.DataTable)
    return [
        [c.content.value if isinstance(c.content, ft.Text) else None for c in f.cells]
        for f in tabla.rows
    ]


def test_ingresos_vacio(app, resumen):
    col = _tabla_en(resumen, "INGRESOS EXTRA")
    assert "Sin ingresos extra este mes." in textos(col)
    assert hay_boton(col, "Agregar ingreso")


def test_ca_24_1_agregar_ingreso_en_pesos(app, resumen, pagina):
    _base(app)
    clic(_tabla_en(resumen, "INGRESOS EXTRA"), "Agregar ingreso")
    d = boton(dialogo_arriba(app), "Guardar").on_click.__self__
    assert titulo_dialogo(d.dialogo) == "Nuevo ingreso extra"
    assert d.moneda.selected == ["ARS"]
    assert (d.monto.prefix, d.monto.suffix) == ("$ ", "ARS")
    assert d.descripcion.autofocus is True
    d.descripcion.value = "Venta bici"
    d.monto.value = "100.000"
    d._guardar()
    assert pagina.avisos()[-1] == "Ingreso agregado"
    assert _filas(_tabla_en(resumen, "INGRESOS EXTRA"))[0][:3] == [
        "Venta bici",
        "ARS",
        "$ 100.000",
    ]
    assert _monto(_tarjeta(resumen, "Pesos a cubrir")).value == "$ 1.334.617"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 834,14"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 365,86"


def test_ca_24_2_ingreso_en_dolares(app, resumen):
    _base(app)
    resumen.nuevo_ingreso()
    d = boton(dialogo_arriba(app), "Guardar").on_click.__self__
    d.moneda.selected = ["USD"]
    d.moneda.on_change(None)
    assert (d.monto.prefix, d.monto.suffix) == ("US$ ", "USD")
    d.descripcion.value = "Freelance"
    d.monto.value = "50"
    d._guardar()
    assert _filas(_tabla_en(resumen, "INGRESOS EXTRA"))[0][:3] == [
        "Freelance",
        "USD",
        "US$ 50,00",
    ]
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 353,36"


def test_ingreso_errores_juntos_y_foco(app, resumen, pagina):
    resumen.nuevo_ingreso()
    d = boton(dialogo_arriba(app), "Guardar").on_click.__self__
    d.monto.value = "0"
    d._guardar()
    assert d.descripcion.error == "Ingresá una descripción."
    assert d.monto.error == "El monto tiene que ser mayor a 0."
    assert _enfocado(pagina) is d.descripcion
    assert ingresos.listar_ingresos(app.con, app.mes_id) == []


def test_editar_y_borrar_ingreso(app, resumen, pagina):
    iid = ingresos.agregar_ingreso(app.con, app.mes_id, "Freelance", "USD", 5000)
    app.refrescar()
    [tabla] = de_tipo(_tabla_en(resumen, "INGRESOS EXTRA"), ft.DataTable)
    menu = tabla.rows[0].cells[3].content
    assert [i.content for i in menu.items] == ["Editar", "Borrar"]
    menu.items[0].on_click(None)
    d = boton(dialogo_arriba(app), "Guardar").on_click.__self__
    assert titulo_dialogo(d.dialogo) == "Editar ingreso extra"
    assert (d.descripcion.value, d.moneda.selected, d.monto.value) == (
        "Freelance",
        ["USD"],
        "50",
    )
    assert d.monto.prefix == "US$ "
    d.monto.value = "60"
    d._guardar()
    assert pagina.avisos()[-1] == "Ingreso actualizado"
    assert ingresos.obtener_ingreso(app.con, iid)["monto_cent"] == 6000

    [tabla] = de_tipo(_tabla_en(resumen, "INGRESOS EXTRA"), ft.DataTable)
    tabla.rows[0].cells[3].content.items[1].on_click(None)
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Borrar el ingreso Freelance?"
    clic(confirmacion, "Cancelar")
    assert ingresos.obtener_ingreso(app.con, iid) is not None
    [tabla] = de_tipo(_tabla_en(resumen, "INGRESOS EXTRA"), ft.DataTable)
    tabla.rows[0].cells[3].content.items[1].on_click(None)
    clic(dialogo_arriba(app), "Borrar")
    assert ingresos.obtener_ingreso(app.con, iid) is None
    assert pagina.avisos()[-1] == 'Ingreso "Freelance" borrado'
    assert "Sin ingresos extra este mes." in textos(
        _tabla_en(resumen, "INGRESOS EXTRA")
    )


def test_borrar_ingreso_que_ya_no_existe(app, resumen, pagina):
    iid = ingresos.agregar_ingreso(app.con, app.mes_id, "Bono", "ARS", 100)
    app.refrescar()
    [tabla] = de_tipo(_tabla_en(resumen, "INGRESOS EXTRA"), ft.DataTable)
    tabla.rows[0].cells[3].content.items[1].on_click(None)
    ingresos.borrar_ingreso(app.con, iid)
    clic(dialogo_arriba(app), "Borrar")
    assert pagina.avisos()[-1] == "Ese ingreso ya no existe."
    assert 'Ingreso "Bono" borrado' not in pagina.avisos()


# ---------------------------------------------------------------------------
# Cambios realizados (RF-26, §4.6, CA-26.x, CA-27.x)
# ---------------------------------------------------------------------------


def _dialogo_cambio(app):
    return boton(dialogo_arriba(app), "Guardar").on_click.__self__


def _escribir(campo, texto):
    campo.value = texto
    campo.on_change(None)


def test_cambios_vacio(app, resumen):
    col = _tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS")
    assert "Todavía no registraste cambios este mes." in textos(col)
    assert hay_boton(col, "Registrar cambio")


def test_ctrl_n_en_resumen_abre_registrar_cambio(app):
    app._al_presionar_tecla(tecla("N", ctrl=True))
    d = _dialogo_cambio(app)
    assert titulo_dialogo(d.dialogo) == "Registrar cambio de dólares"
    assert d.texto_fecha.value == "04/10/2026"
    assert d.cotizacion.value == "1.600"  # precargada con la del mes
    assert d.usd.autofocus is True
    assert (d.ars.value or "") == ""


def test_ca_26_1_y_26_2_pesos_sugeridos_y_corregidos(app, resumen, pagina):
    _base(app)
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    _escribir(d.cotizacion, "1.500")
    _escribir(d.usd, "500")
    assert d.ars.value == "750.000"  # CA-26.1
    assert d.ayuda_ars.value == "Calculado: US$ 500,00 × $ 1.500"
    assert d.boton_recalcular.visible is False

    _escribir(d.ars, "745.000")  # CA-26.2: comisión
    assert d.ayuda_ars.value == "Corregido a mano"
    assert d.boton_recalcular.visible is True
    d._guardar()
    assert pagina.avisos()[-1] == "Cambio registrado"
    filas = _filas(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"))
    assert filas[0][:5] == [
        "04/10/2026",
        "US$ 500,00",
        "$ 1.500",
        "$ 745.000",
        "corregido a mano",
    ]
    assert filas[-1][:4] == ["Total", "US$ 500,00", "", "$ 745.000"]
    [tabla] = de_tipo(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"), ft.DataTable)
    assert "corregido a mano" in textos(tabla.rows[0].cells[4].content)
    # CA-27.2 en pantalla.
    assert _monto(_tarjeta(resumen, "Pesos a cubrir")).value == "$ 689.617"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 431,01"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 268,99"


def test_ca_27_1_cambio_sin_corregir(app, resumen):
    _base(app)
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    _escribir(d.cotizacion, "1.500")
    _escribir(d.usd, "500")
    d._guardar()
    [tabla] = de_tipo(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"), ft.DataTable)
    assert "corregido a mano" not in textos(tabla.rows[0])
    assert _monto(_tarjeta(resumen, "Pesos a cubrir")).value == "$ 684.617"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 427,89"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 272,11"


def test_volver_a_calcular(app, resumen):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    _escribir(d.cotizacion, "1.500")
    _escribir(d.usd, "500")
    _escribir(d.ars, "745.000")
    clic(d.dialogo, "Volver a calcular")
    assert d.ars.value == "750.000"
    assert d.boton_recalcular.visible is False
    assert d.aviso_recalculo.visible is False


def test_corregido_y_despues_cambian_los_dolares_se_recalcula_con_aviso(app, resumen):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    _escribir(d.cotizacion, "1.500")
    _escribir(d.usd, "500")
    _escribir(d.ars, "745.000")
    _escribir(d.usd, "600")  # RN-13: vuelve a sugerir
    assert d.ars.value == "900.000"
    assert d.aviso_recalculo.visible is True
    assert d.aviso_recalculo.value == (
        "Se recalculó con los valores nuevos. Si hubo comisión, corregilo."
    )
    _escribir(d.cotizacion, "1.550")  # sin corrección manual: recalcula sin aviso
    assert d.ars.value == "930.000"
    assert d.aviso_recalculo.visible is False


def test_ca_26_4_cotizacion_con_centavos_en_la_tabla(app, resumen):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    _escribir(d.cotizacion, "1.432,50")
    _escribir(d.usd, "19,99")
    assert d.ayuda_ars.value == "Calculado: US$ 19,99 × $ 1.432,50"
    assert d.ars.value == "28.635,68"
    d._guardar()
    filas = _filas(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"))
    assert filas[0][2:4] == ["$ 1.432,50", "$ 28.636"]


@pytest.mark.parametrize(
    ("usd", "cot", "ars", "campo", "mensaje"),
    [
        ("", "1.500", "1", "usd", "Ingresá un monto."),
        ("0", "1.500", "1", "usd", "El monto en dólares tiene que ser mayor a 0."),
        ("500", "", "1", "cotizacion", "Ingresá la cotización del cambio."),
        (
            "500",
            "0",
            "1",
            "cotizacion",
            "La cotización tiene que ser mayor a 0.",
        ),  # CA-26.3
        (
            "500",
            "1.500",
            "0",
            "ars",
            "El monto en pesos tiene que ser mayor a 0.",
        ),  # CA-26.3
        ("500", "1.500", "", "ars", "Ingresá un monto."),
    ],
)
def test_ca_26_3_cambio_invalido(app, resumen, pagina, usd, cot, ars, campo, mensaje):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    d.usd.value, d.cotizacion.value, d.ars.value = usd, cot, ars
    d._guardar()
    assert getattr(d, campo).error == mensaje
    assert d.dialogo.open is True
    assert cambios.listar_cambios(app.con, app.mes_id) == []


def test_errores_de_cambio_juntos_y_foco_al_primero(app, resumen, pagina):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    d.usd.value, d.cotizacion.value, d.ars.value = "", "", ""
    d._guardar()
    assert d.usd.error and d.cotizacion.error and d.ars.error
    assert _enfocado(pagina) is d.usd


def test_cambio_en_mes_sin_cotizacion(con):
    app = _app_sin_cotizacion(con)
    app._al_presionar_tecla(tecla("N", ctrl=True))
    d = _dialogo_cambio(app)
    assert (d.cotizacion.value or "") == ""
    _escribir(d.usd, "500")
    assert (d.ars.value or "") == "" and d.ayuda_ars.value == ""


def test_fecha_del_cambio_con_el_calendario(app, resumen):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    [boton_cal] = [
        b
        for b in de_tipo(d.dialogo, ft.IconButton)
        if b.icon == ft.Icons.CALENDAR_MONTH
    ]
    boton_cal.on_click(None)
    assert app._dialogos == [d.dialogo, d.calendario]
    d.calendario.value = datetime(2026, 10, 2, 18, 0)  # noqa: DTZ001
    d.calendario.on_change(None)
    assert d.texto_fecha.value == "02/10/2026"
    assert app._dialogos == [d.dialogo]  # el calendario se cerró (como O24)
    _escribir(d.usd, "100")
    d._guardar()
    assert cambios.listar_cambios(app.con, app.mes_id)[0]["fecha"] == "2026-10-02"


def test_editar_cambio_corregido(app, resumen, pagina):
    cid = cambios.agregar_cambio(
        app.con, app.mes_id, 50000, 150000, 74500000, date(2026, 10, 5)
    )
    app.refrescar()
    [tabla] = de_tipo(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"), ft.DataTable)
    tabla.rows[0].cells[5].content.items[0].on_click(None)
    d = _dialogo_cambio(app)
    assert titulo_dialogo(d.dialogo) == "Editar cambio de dólares"
    assert (d.texto_fecha.value, d.usd.value, d.cotizacion.value, d.ars.value) == (
        "05/10/2026",
        "500",
        "1.500",
        "745.000",
    )
    assert d.ayuda_ars.value == "Corregido a mano"
    assert d.boton_recalcular.visible is True
    _escribir(d.ars, "740.000")
    d._guardar()
    assert pagina.avisos()[-1] == "Cambio actualizado"
    fila = cambios.obtener_cambio(app.con, cid)
    assert (fila["ars_cent"], fila["fecha"]) == (74000000, "2026-10-05")


def test_borrar_cambio_con_confirmacion(app, resumen, pagina):
    cid = cambios.agregar_cambio(app.con, app.mes_id, 50000, 150000, 74500000, HOY)
    app.refrescar()
    [tabla] = de_tipo(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"), ft.DataTable)
    tabla.rows[0].cells[5].content.items[1].on_click(None)
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Borrar el cambio del 04/10/2026?"
    assert "US$ 500,00 por $ 745.000. Esta acción no se puede deshacer." in textos(
        confirmacion
    )
    clic(confirmacion, "Borrar")
    assert cambios.obtener_cambio(app.con, cid) is None
    assert pagina.avisos()[-1] == "Cambio borrado"


def test_editar_un_cambio_borrado_por_detras(app, resumen, pagina):
    cid = cambios.agregar_cambio(app.con, app.mes_id, 50000, 150000, fecha=HOY)
    app.refrescar()
    [tabla] = de_tipo(_tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS"), ft.DataTable)
    tabla.rows[0].cells[5].content.items[0].on_click(None)
    d = _dialogo_cambio(app)
    cambios.borrar_cambio(app.con, cid)
    d._guardar()
    assert d.dialogo.open is False
    assert pagina.avisos()[-1] == "Ese cambio ya no existe."
    assert "Todavía no registraste cambios este mes." in textos(
        _tabla_en(resumen, "CAMBIOS DE DÓLARES REALIZADOS")
    )


def test_error_inesperado_al_guardar_un_cambio(app, resumen, monkeypatch):
    def falla(*args, **kwargs):
        raise RuntimeError("falla inventada")

    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    _escribir(d.usd, "100")
    monkeypatch.setattr(cambios, "agregar_cambio", falla)
    d._guardar()
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


# ---------------------------------------------------------------------------
# Ajustes: pestaña "Meta de ahorro" (§3.10)
# ---------------------------------------------------------------------------


@pytest.fixture
def pestana_meta(app):
    ajustes = ir(app, "Ajustes")
    return ajustes.meta


def test_pestana_meta_sin_meta(pestana_meta):
    assert (pestana_meta.campo.value or "") == ""
    assert pestana_meta.boton_quitar.visible is False
    assert "Es la misma meta para todos los meses." in textos(pestana_meta.control)


def test_pestana_meta_guardar_y_quitar(app, pestana_meta, pagina):
    pestana_meta.campo.value = "300"
    clic(pestana_meta.control, "Guardar meta")
    assert configuracion.obtener_meta(app.con) == 30000
    assert pagina.avisos()[-1] == "Meta de ahorro: US$ 300,00"
    assert pestana_meta.boton_quitar.visible is True
    assert pestana_meta.campo.value == "300"
    # La misma meta se ve en el Resumen.
    resumen = ir(app, "Resumen")
    assert hay_boton(_bloque_meta(resumen), "Meta US$ 300,00")
    ir(app, "Ajustes")
    clic(pestana_meta.control, "Quitar meta")
    assert configuracion.obtener_meta(app.con) is None
    assert pagina.avisos()[-1] == "Meta de ahorro quitada"
    assert pestana_meta.boton_quitar.visible is False


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("", "Ingresá la meta."),
        ("0", "La meta tiene que ser mayor a 0."),
        ("abc", "Escribí solo números. Ej.: 66.020,12"),
    ],
)
def test_pestana_meta_errores(app, pestana_meta, pagina, texto, mensaje):
    pestana_meta.campo.value = texto
    pestana_meta.guardar()
    assert pestana_meta.campo.error == mensaje
    assert _enfocado(pagina) is pestana_meta.campo
    assert configuracion.obtener_meta(app.con) is None


def test_enter_en_la_pestana_meta_guarda(app, pestana_meta):
    pestana_meta.campo.value = "450"
    pestana_meta.campo.on_submit(None)
    assert configuracion.obtener_meta(app.con) == 45000


def test_ctrl_n_en_la_pestana_meta_enfoca_el_campo(app, pestana_meta, pagina):
    app.pantalla("Ajustes").pestanas.selected_index = 2
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert _enfocado(pagina) is pestana_meta.campo
    assert app.hay_dialogo_abierto() is False


def test_la_pestana_meta_muestra_la_meta_cargada_en_el_resumen(app):
    configuracion.guardar_meta(app.con, 60000)
    ajustes = ir(app, "Ajustes")
    assert ajustes.meta.campo.value == "600"
    assert ajustes.meta.boton_quitar.visible is True


# ---------------------------------------------------------------------------
# Ronda 13: BUG-11 (los diálogos de un monto no se cierran con un dato inválido)
# ---------------------------------------------------------------------------


def _abrir(app, cual):
    if cual == "sueldo":
        _abrir_sueldo(app.pantalla("Resumen"), app)
    elif cual == "cotizacion":
        app.editar_cotizacion()
    else:
        app.pantalla("Resumen").editar_meta()
    return dialogo_arriba(app)


def _valor_guardado(app, cual):
    if cual == "meta":
        return configuracion.obtener_meta(app.con)
    columna = "sueldo_usd_cent" if cual == "sueldo" else "cotizacion_cent"
    return meses.obtener_mes(app.con, app.mes_id)[columna]


INVALIDOS = [
    ("sueldo", "1.2.3", "Escribí solo números. Ej.: 66.020,12"),
    ("sueldo", "1200.5", "Usá coma para los decimales. Ej.: 66.020,12"),
    ("sueldo", "1200,123", "Usá como máximo 2 decimales."),
    ("sueldo", "-5", "El sueldo no puede ser negativo."),
    ("sueldo", "999.999.999.999,01", "El sueldo es demasiado grande."),
    ("sueldo", "0" * 21, "El sueldo es demasiado grande."),
    ("cotizacion", "0", "La cotización tiene que ser mayor a 0."),
    ("cotizacion", "0,00", "La cotización tiene que ser mayor a 0."),
    ("cotizacion", "-1", "La cotización no puede ser negativa."),
    ("cotizacion", "1600.5", "Usá coma para los decimales. Ej.: 66.020,12"),
    ("cotizacion", "abc", "Escribí solo números. Ej.: 66.020,12"),
    ("cotizacion", "999.999.999.999,01", "La cotización es demasiado grande."),
    ("meta", "0", "La meta tiene que ser mayor a 0."),
    ("meta", "-5", "La meta no puede ser negativa."),
    ("meta", "300.5", "Usá coma para los decimales. Ej.: 66.020,12"),
    ("meta", "abc", "Escribí solo números. Ej.: 66.020,12"),
    ("meta", "999.999.999.999,01", "La meta es demasiado grande."),
]


@pytest.mark.parametrize(("cual", "texto", "mensaje"), INVALIDOS)
def test_bug11_dato_invalido_deja_el_dialogo_abierto(app, pagina, cual, texto, mensaje):
    antes = _valor_guardado(app, cual)
    dialogo = _abrir(app, cual)
    campo = _campo(dialogo)
    campo.value = texto
    avisos_antes = list(pagina.avisos())
    clic(dialogo, "Guardar")
    assert dialogo.open is True
    assert app._dialogos == [dialogo]
    assert campo.value == texto  # lo escrito se conserva
    assert campo.error == mensaje
    assert _enfocado(pagina) is campo
    assert pagina.avisos() == avisos_antes  # sin aviso
    assert _valor_guardado(app, cual) == antes  # nada se guardó


@pytest.mark.parametrize("cual", ["sueldo", "cotizacion", "meta"])
def test_bug11_corregir_despues_del_error_guarda(app, pagina, cual):
    dialogo = _abrir(app, cual)
    campo = _campo(dialogo)
    campo.value = "abc"
    clic(dialogo, "Guardar")
    assert campo.error
    campo.value = "1.234"
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert campo.error is None
    assert _valor_guardado(app, cual) == 123400


@pytest.mark.parametrize("cual", ["sueldo", "cotizacion"])
def test_bug11_mes_borrado_por_detras_cierra_y_avisa(app, pagina, cual):
    dialogo = _abrir(app, cual)
    _campo(dialogo).value = "1.500"
    with app.con:
        app.con.execute("DELETE FROM meses WHERE id = ?", (app.mes_id,))
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert app.hay_dialogo_abierto() is False
    assert pagina.avisos()[-1] == "El mes no existe."


def test_bug11_error_sin_campo_al_guardar_la_meta_cierra_y_avisa(
    app, pagina, monkeypatch
):
    from app.logica.errores import ErrorDeValidacion

    def cambio_por_detras(con, valor):
        raise ErrorDeValidacion("Algo cambió por detrás (simulado).")

    monkeypatch.setattr(configuracion, "guardar_meta", cambio_por_detras)
    dialogo = _abrir(app, "meta")
    _campo(dialogo).value = "300"
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert pagina.avisos()[-1] == "Algo cambió por detrás (simulado)."


def test_bug11_error_inesperado_al_guardar(app, monkeypatch):
    def falla(*args, **kwargs):
        raise RuntimeError("falla inventada")

    monkeypatch.setattr(meses, "editar_cotizacion", falla)
    dialogo = _abrir(app, "cotizacion")
    _campo(dialogo).value = "1.700"
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


def test_bug11_enter_con_dato_invalido_tampoco_cierra(app, pagina):
    dialogo = _abrir(app, "cotizacion")
    campo = _campo(dialogo)
    campo.value = "0"
    campo.on_submit(None)
    assert dialogo.open is True
    assert campo.error == "La cotización tiene que ser mayor a 0."


# ---------------------------------------------------------------------------
# Ronda 13: BUG-12 y O28 en pantalla
# ---------------------------------------------------------------------------


def _porcentaje(resumen, etiqueta):
    bloque = _bloque_meta(resumen, etiqueta)
    [texto] = [t for t in de_tipo(bloque, ft.Text) if t.value and t.value.endswith("%")]
    return texto


def test_bug12_deficit_muestra_el_porcentaje_real_y_barra_en_cero(app, resumen):
    _base(app)
    configuracion.guardar_meta(app.con, 30000)
    meses.editar_sueldo(app.con, app.mes_id, 80000)
    app.refrescar()
    texto = _porcentaje(resumen, "Déficit")
    assert (texto.value, texto.tooltip) == ("-32 %", "-32,21 %")
    [barra] = de_tipo(_bloque_meta(resumen, "Déficit"), ft.ProgressBar)
    assert barra.value == 0.0


def test_o28_mitad_se_redondea_hacia_arriba_en_pantalla(app, resumen):
    # Ahorro US$ 25,00 con meta US$ 200: 12,5 % → "13 %" (round() daba 12).
    meses.editar_sueldo(app.con, app.mes_id, 2500)
    configuracion.guardar_meta(app.con, 20000)
    app.refrescar()
    texto = _porcentaje(resumen, "Ahorro del mes")
    assert (texto.value, texto.tooltip) == ("13 %", "12,50 %")


def test_deficit_chico_no_muestra_menos_cero(app, resumen):
    # Ahorro −US$ 0,01 con meta 300: −0,003 % se ve como 0; no debería decir "-0 %".
    _base(app)
    configuracion.guardar_meta(app.con, 30000)
    meses.editar_sueldo(app.con, app.mes_id, 89663)
    app.refrescar()
    texto = _porcentaje(resumen, "Déficit")
    assert texto.value == "0 %"


# ---------------------------------------------------------------------------
# Ronda 14: BUG-13 y BUG-14 en pantalla
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sueldo", "valor", "tooltip"),
    [
        (89663, "0 %", "0,00 %"),  # ahorro −US$ 0,01: −0,003 %
        (89651, "0 %", "-0,04 %"),  # ahorro −US$ 0,13: −0,043 %
        (
            89514,
            "-1 %",
            "-0,50 %",
        ),  # ahorro −US$ 1,50: −0,5 % → la mitad se aleja del 0
    ],
)
def test_bug13_deficit_chico_en_pantalla(app, resumen, sueldo, valor, tooltip):
    _base(app)
    configuracion.guardar_meta(app.con, 30000)
    meses.editar_sueldo(app.con, app.mes_id, sueldo)
    app.refrescar()
    texto = _porcentaje(resumen, "Déficit")
    assert (texto.value, texto.tooltip) == (valor, tooltip)
    [barra] = de_tipo(_bloque_meta(resumen, "Déficit"), ft.ProgressBar)
    assert barra.value == 0.0


def test_bug13_ahorro_cero_con_meta(app, resumen):
    _base(app)
    configuracion.guardar_meta(app.con, 30000)
    meses.editar_sueldo(app.con, app.mes_id, 89664)  # ahorro exactamente 0
    app.refrescar()
    texto = _porcentaje(resumen, "Ahorro del mes")
    assert (texto.value, texto.tooltip) == ("0 %", "0,00 %")


@pytest.mark.parametrize(
    ("cual", "pegado", "mensaje"),
    [
        ("cotizacion", "-1", "La cotización no puede ser negativa."),
        ("cotizacion", "-1.600", "La cotización no puede ser negativa."),
        ("meta", "-5", "La meta no puede ser negativa."),
        ("sueldo", "-5", "El sueldo no puede ser negativo."),
    ],
)
def test_bug14_pegar_un_negativo_en_los_dialogos(app, pagina, cual, pegado, mensaje):
    antes = _valor_guardado(app, cual)
    dialogo = _abrir(app, cual)
    _campo(dialogo).value = pegado
    clic(dialogo, "Guardar")
    assert _campo(dialogo).error == mensaje
    assert dialogo.open is True
    assert _valor_guardado(app, cual) == antes


def test_bug14_pegar_un_negativo_en_la_pestana_meta(app, pestana_meta, pagina):
    pestana_meta.campo.value = "-5"
    pestana_meta.guardar()
    assert pestana_meta.campo.error == "La meta no puede ser negativa."
    assert _enfocado(pagina) is pestana_meta.campo
    assert configuracion.obtener_meta(app.con) is None


@pytest.mark.parametrize(
    ("campo", "mensaje"),
    [
        ("usd", "El monto en dólares no puede ser negativo."),
        ("cotizacion", "La cotización no puede ser negativa."),
        ("ars", "El monto en pesos no puede ser negativo."),
    ],
)
def test_bug14_pegar_un_negativo_en_el_dialogo_de_cambio(app, resumen, campo, mensaje):
    resumen.nuevo_cambio()
    d = _dialogo_cambio(app)
    d.usd.value, d.cotizacion.value, d.ars.value = "500", "1.500", "750.000"
    getattr(d, campo).value = "-1"
    d._guardar()
    assert getattr(d, campo).error == mensaje
    assert cambios.listar_cambios(app.con, app.mes_id) == []
