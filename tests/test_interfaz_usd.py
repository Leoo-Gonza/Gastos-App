"""Pruebas de la interfaz de los gastos en dólares: bloque en dólares del diálogo,
cambio de moneda, resultado en tiempo real, edición y tabla (RF-43 a RF-46;
diseno.md §3.3, §4.1 y §6 "Paso 1c"). Página falsa: no se abre ninguna ventana."""

import sqlite3

import flet as ft
import pytest

from app.interfaz import estilos
from app.interfaz.aplicacion import Aplicacion, main, mostrar_error_al_abrir
from app.logica import base_datos, catalogos, gastos, meses
from tests.ayudantes import id_por_nombre, insertar_pago
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    celda,
    de_tipo,
    dialogo_gasto_abierto,
    filas_tabla,
    textos,
)

AYUDA_COTIZACION = "Escribí la cotización que te cobran (oficial, tarjeta o MEP). La app no suma impuestos."
SIN_RESULTADO = "Completá el monto y la cotización para ver cuántos pesos vas a pagar."


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _enfocado(pagina):
    assert pagina.tareas, "No se pidió el foco de ningún control"
    return pagina.tareas[-1].__self__


def _nuevo(app):
    app.pantalla("Gastos").nuevo()
    return dialogo_gasto_abierto(app)


def _elegir_moneda(d, moneda):
    """Simula el clic en el selector de moneda."""
    d.moneda.selected = [moneda]
    d.moneda.on_change(None)


def _escribir(campo, texto):
    """Simula escribir en un campo (dispara on_change, como en cada tecla)."""
    campo.value = texto
    if campo.on_change:
        campo.on_change(None)


def _usd(con, mes_id, usd, cot, nombre="Claude", tipo="unico"):
    return gastos.agregar_gasto(
        con, mes_id, nombre, _otros(con), None, tipo, None, "USD", usd, cot
    )


@pytest.fixture
def app_sin_cotizacion(pagina, con):
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, None)
    aplicacion = Aplicacion(pagina, con)
    aplicacion.iniciar()
    assert aplicacion.mes_id == mes
    return aplicacion


# ---------------------------------------------------------------------------
# Alta: bloque en dólares
# ---------------------------------------------------------------------------


def test_moneda_por_defecto_pesos_y_bloques(app):
    d = _nuevo(app)
    assert d.moneda.selected == ["ARS"]
    assert [s.label.value for s in d.moneda.segments] == [
        "Pesos (ARS)",
        "Dólares (USD)",
    ]
    assert d.bloque_pesos.visible is True
    assert d.bloque_dolares.visible is False
    assert d.ayuda_tipo.value == "Los fijos se copian al mes siguiente."


def test_campos_del_bloque_en_dolares(app):
    d = _nuevo(app)
    assert (d.monto_usd.label, d.monto_usd.prefix, d.monto_usd.suffix) == (
        "Monto en dólares",
        "US$ ",
        "USD",
    )
    assert d.monto_usd.hint_text == "Ej.: 20,00"
    assert (d.cotizacion.label, d.cotizacion.prefix, d.cotizacion.suffix) == (
        "Cotización del día",
        "$ ",
        "por US$",
    )
    assert d.monto.hint_text == "Ej.: 66.020,12"  # el de pesos no cambió


def test_ca_44_1_cotizacion_sugerida_con_la_del_mes(app):
    d = _nuevo(app)
    _elegir_moneda(d, "USD")
    assert d.cotizacion.value == "1.600"
    assert d.cotizacion.helper == AYUDA_COTIZACION
    assert d.boton_usar_la_del_mes.visible is False


def test_ca_44_3_mes_sin_cotizacion_campo_vacio_con_ayuda(app_sin_cotizacion):
    d = _nuevo(app_sin_cotizacion)
    _elegir_moneda(d, "USD")
    assert (d.cotizacion.value or "") == ""
    assert d.cotizacion.helper == "Este mes no tiene cotización: escribí la del día."


def test_cambiar_a_dolares_muestra_el_bloque_y_enfoca_el_monto(app, pagina):
    d = _nuevo(app)
    _elegir_moneda(d, "USD")
    assert d.bloque_pesos.visible is False
    assert d.bloque_dolares.visible is True
    assert d.ayuda_tipo.value == (
        "Los fijos se copian al mes siguiente con los mismos dólares y la cotización del mes nuevo."
    )
    assert _enfocado(pagina) is d.monto_usd


def test_cambiar_de_moneda_conserva_lo_escrito_y_no_convierte(app, pagina):
    # §4.1: cada bloque conserva lo escrito; el 20 en pesos no se transforma en dólares.
    d = _nuevo(app)
    d.monto.value = "38.700"
    _elegir_moneda(d, "USD")
    assert (d.monto_usd.value or "") == ""
    _escribir(d.monto_usd, "20")
    tareas_antes = len(pagina.tareas)
    _elegir_moneda(d, "ARS")
    assert d.monto.value == "38.700"
    assert (
        len(pagina.tareas) == tareas_antes
    )  # el campo no está vacío: no se mueve el foco
    _elegir_moneda(d, "USD")
    assert d.monto_usd.value == "20"


def test_cambiar_de_moneda_limpia_los_errores_ocultos(app):
    d = _nuevo(app)
    d._guardar()  # en pesos: error en Monto
    assert d.monto.error
    _elegir_moneda(d, "USD")
    assert d.monto.error is None
    d._guardar()  # en dólares: errores en los dos campos del bloque
    d.cotizacion.value = ""
    d._guardar()
    assert d.monto_usd.error and d.cotizacion.error
    _elegir_moneda(d, "ARS")
    assert d.monto_usd.error is None
    assert d.cotizacion.error is None


@pytest.mark.parametrize(
    ("usd", "cotizacion", "texto"),
    [
        ("20", "1.600", "US$ 20,00 × $ 1.600 = $ 32.000 a pagar"),  # CA-44.1
        ("19,99", "1.432,50", "US$ 19,99 × $ 1.432,50 = $ 28.636 a pagar"),  # CA-44.2
        ("12,99", "1432,5", "US$ 12,99 × $ 1.432,50 = $ 18.608 a pagar"),  # diseño §4.1
    ],
)
def test_resultado_en_tiempo_real(app, usd, cotizacion, texto):
    d = _nuevo(app)
    _elegir_moneda(d, "USD")
    _escribir(d.cotizacion, cotizacion)
    _escribir(d.monto_usd, usd)
    assert d.texto_resultado.value == texto
    assert d.texto_resultado.size == 18
    assert d.nota_resultado.visible is True
    assert d.nota_resultado.value == "Los pesos quedan fijos con esta cotización."
    assert gastos.listar_gastos(app.con, app.mes_id) == []  # todavía no se guardó


@pytest.mark.parametrize(
    ("usd", "cotizacion"),
    [
        ("", "1.600"),
        ("20", ""),
        ("abc", "1.600"),
        ("20.5", "1.600"),
        ("0", "1.600"),
        ("20", "0"),
    ],
)
def test_resultado_con_datos_faltantes_muestra_ayuda_sin_error(app, usd, cotizacion):
    d = _nuevo(app)
    _elegir_moneda(d, "USD")
    _escribir(d.cotizacion, cotizacion)
    _escribir(d.monto_usd, usd)
    assert d.texto_resultado.value == SIN_RESULTADO
    assert d.texto_resultado.color is None  # sin color de error mientras se escribe
    assert d.nota_resultado.visible is False


def test_resultado_se_actualiza_al_cambiar_la_cotizacion(app):
    d = _nuevo(app)
    _elegir_moneda(d, "USD")
    _escribir(d.monto_usd, "20")
    _escribir(d.cotizacion, "2.100")
    assert d.texto_resultado.value == "US$ 20,00 × $ 2.100 = $ 42.000 a pagar"


def test_errores_juntos_en_dolares_y_foco_al_primero(app, pagina):
    d = _nuevo(app)
    _elegir_moneda(d, "USD")
    d.cotizacion.value = ""
    d._guardar()
    assert d.nombre.error == "Ingresá un nombre."
    assert d.categoria.error_text == "Elegí una categoría."
    assert d.monto_usd.error == "Ingresá el monto en dólares."
    assert d.cotizacion.error == "Ingresá la cotización del día."
    assert d.monto.error is None  # el bloque oculto no se valida
    assert _enfocado(pagina) is d.nombre
    assert gastos.listar_gastos(app.con, app.mes_id) == []


@pytest.mark.parametrize(
    ("usd", "cotizacion", "campo", "mensaje"),
    [
        ("", "1.600", "monto_usd", "Ingresá el monto en dólares."),
        ("0", "1.600", "monto_usd", "El monto tiene que ser mayor a 0."),
        ("20.5", "1.600", "monto_usd", "Usá coma para los decimales. Ej.: 66.020,12"),
        ("20", "", "cotizacion", "Ingresá la cotización del día."),
        ("20", "0", "cotizacion", "La cotización tiene que ser mayor a 0."),
        ("20", "1.600,123", "cotizacion", "Usá como máximo 2 decimales."),
    ],
)
def test_mensajes_del_bloque_en_dolares(
    app, con, pagina, usd, cotizacion, campo, mensaje
):
    d = _nuevo(app)
    d.nombre.value = "Claude"
    d.categoria.value = str(_otros(con))
    _elegir_moneda(d, "USD")
    d.monto_usd.value = usd
    d.cotizacion.value = cotizacion
    d._guardar()
    assert getattr(d, campo).error == mensaje
    assert _enfocado(pagina) is getattr(d, campo)
    assert gastos.listar_gastos(con, app.mes_id) == []


def test_al_guardar_en_pesos_no_se_valida_el_bloque_en_dolares(app, con):
    d = _nuevo(app)
    d.nombre.value = "Nafta"
    d.categoria.value = str(_otros(con))
    _elegir_moneda(d, "USD")
    d.monto_usd.value = "basura"
    _elegir_moneda(d, "ARS")
    d.monto.value = "30.000"
    d._guardar()
    fila = gastos.listar_gastos(con, app.mes_id)[0]
    assert (fila["moneda"], fila["monto_cent"], fila["monto_usd_cent"]) == (
        "ARS",
        3000000,
        None,
    )


def _cargar_claude(app, con, usd="20", cotizacion=None, tipo="unico"):
    d = _nuevo(app)
    d.nombre.value = "Claude"
    d.categoria.value = str(_otros(con))
    _elegir_moneda(d, "USD")
    d.monto_usd.value = usd
    if cotizacion is not None:
        d.cotizacion.value = cotizacion
    d.tipo.selected = [tipo]
    d._guardar()
    return d


def test_ca_43_1_guardar_en_dolares(app, con, pagina):
    d = _cargar_claude(app, con)
    fila = gastos.listar_gastos(con, app.mes_id)[0]
    assert (
        fila["moneda"],
        fila["monto_usd_cent"],
        fila["cotizacion_cent"],
        fila["monto_cent"],
    ) == (
        "USD",
        2000,
        160000,
        3200000,
    )
    assert d.dialogo.open is False
    assert pagina.avisos()[-1].startswith('Gasto "Claude" agregado')


def test_aviso_de_alta_en_dolares_con_pesos_y_dolares(app, con, pagina):
    # §6 Paso 1c: SnackBar "Gasto "Claude" agregado: $ 32.000 (US$ 20,00)".
    _cargar_claude(app, con)
    assert pagina.avisos()[-1] == 'Gasto "Claude" agregado: $ 32.000 (US$ 20,00)'


def test_enter_en_monto_en_dolares_guarda(app, con):
    d = _nuevo(app)
    d.nombre.value = "Claude"
    d.categoria.value = str(_otros(con))
    _elegir_moneda(d, "USD")
    d.monto_usd.value = "20"
    d.monto_usd.on_submit(None)
    assert len(gastos.listar_gastos(con, app.mes_id)) == 1


def test_ca_44_3_en_pantalla(app_sin_cotizacion, con):
    app = app_sin_cotizacion
    d = _cargar_claude(app, con)
    assert d.cotizacion.error == "Ingresá la cotización del día."
    assert gastos.listar_gastos(con, app.mes_id) == []
    d.cotizacion.value = "1.550"
    d._guardar()
    assert gastos.listar_gastos(con, app.mes_id)[0]["monto_cent"] == 3100000


def test_ca_44_5_resultado_cero_se_muestra_en_el_recuadro(app, con, pagina):
    d = _cargar_claude(app, con, usd="0,01", cotizacion="0,40")
    assert d.texto_resultado.value == (
        "Con estos valores el gasto da $ 0. Revisá el monto y la cotización."
    )
    assert d.texto_resultado.color == estilos.color(app.page, "negativo")
    assert d.nota_resultado.visible is False
    assert _enfocado(pagina) is d.monto_usd
    assert d.dialogo.open is True
    assert gastos.listar_gastos(con, app.mes_id) == []


def test_corregir_despues_de_un_error_en_el_resultado(app, con):
    d = _cargar_claude(app, con, usd="0,01", cotizacion="0,40")
    _escribir(d.monto_usd, "20")
    _escribir(d.cotizacion, "1.600")
    assert d.texto_resultado.color is None
    assert d.texto_resultado.value == "US$ 20,00 × $ 1.600 = $ 32.000 a pagar"
    d._guardar()
    assert len(gastos.listar_gastos(con, app.mes_id)) == 1


# ---------------------------------------------------------------------------
# Edición
# ---------------------------------------------------------------------------


def _editar(app, gid):
    app.pantalla("Gastos").editar(gid)
    return dialogo_gasto_abierto(app)


def test_ca_45_8_edicion_precarga_la_cotizacion_del_gasto(app, con):
    gid = _usd(con, app.mes_id, 1999, 143250)
    d = _editar(app, gid)
    assert d.moneda.selected == ["USD"]
    assert d.bloque_dolares.visible is True and d.bloque_pesos.visible is False
    assert d.monto_usd.value == "19,99"
    assert d.cotizacion.value == "1.432,50"  # la del gasto, no la del mes (1.600)
    assert d.texto_resultado.value == "US$ 19,99 × $ 1.432,50 = $ 28.636 a pagar"


def test_boton_usar_la_del_mes_solo_si_difiere(app, con):
    distinta = _usd(con, app.mes_id, 2000, 210000, nombre="Tarjeta")
    igual = _usd(con, app.mes_id, 2000, 160000, nombre="Oficial")
    d = _editar(app, distinta)
    assert d.boton_usar_la_del_mes.visible is True
    assert d.boton_usar_la_del_mes.content == "Usar la del mes ($ 1.600)"
    d.boton_usar_la_del_mes.on_click(None)
    assert d.cotizacion.value == "1.600"
    assert d.boton_usar_la_del_mes.visible is False
    assert d.texto_resultado.value == "US$ 20,00 × $ 1.600 = $ 32.000 a pagar"
    app.cerrar_dialogo(d.dialogo)
    assert _editar(app, igual).boton_usar_la_del_mes.visible is False


def test_boton_usar_la_del_mes_no_aparece_si_el_mes_no_tiene(app_sin_cotizacion, con):
    gid = _usd(con, app_sin_cotizacion.mes_id, 2000, 160000)
    d = _editar(app_sin_cotizacion, gid)
    assert d.boton_usar_la_del_mes.visible is False
    assert d.cotizacion.value == "1.600"


def test_ca_45_2_editar_la_cotizacion_desde_el_dialogo(app, con, pagina):
    gid = _usd(con, app.mes_id, 2000, 160000)
    d = _editar(app, gid)
    _escribir(d.cotizacion, "1.700")
    assert d.texto_resultado.value == "US$ 20,00 × $ 1.700 = $ 34.000 a pagar"
    d._guardar()
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3400000
    assert pagina.avisos()[-1].startswith('Gasto "Claude" actualizado')


def test_rn_55_editar_sin_tocar_dolares_conserva_los_pesos(app, con):
    gid = _usd(con, app.mes_id, 2000, 160000)
    with con:
        con.execute(
            "UPDATE meses SET cotizacion_cent = 170000 WHERE id = ?", (app.mes_id,)
        )
    d = _editar(app, gid)
    assert d.cotizacion.value == "1.600"
    d.nombre.value = "Claude Pro"
    d._guardar()
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3200000


def test_ca_45_4_rn_23_en_el_recuadro_de_resultado(app, con, pagina):
    gid = _usd(con, app.mes_id, 2000, 160000)
    insertar_pago(con, gid, 3000000)
    d = _editar(app, gid)
    d.cotizacion.value = "1.400"
    d._guardar()
    assert d.texto_resultado.value == (
        "Con estos valores el gasto queda en $ 28.000, menos de lo que ya pagaste "
        "($ 30.000). Subí el monto o la cotización."
    )
    assert d.texto_resultado.color == estilos.color(app.page, "negativo")
    assert d.dialogo.open is True
    assert _enfocado(pagina) is d.monto_usd
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3200000
    d.cotizacion.value = "1.550"
    d._guardar()
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 3100000


def test_usd_a_pesos_precarga_los_pesos_y_avisa(app, con):
    gid = _usd(con, app.mes_id, 2000, 160000)
    d = _editar(app, gid)
    assert d.aviso_paso_a_pesos.visible is False
    _elegir_moneda(d, "ARS")
    assert d.monto.value == "32.000"
    assert d.aviso_paso_a_pesos.visible is True
    assert d.aviso_paso_a_pesos.value == (
        "Al guardar en pesos, el gasto deja de guardar los dólares y la cotización."
    )
    d.monto.value = "35.000"
    d._guardar()
    fila = gastos.obtener_gasto(con, gid)
    assert (
        fila["moneda"],
        fila["monto_cent"],
        fila["monto_usd_cent"],
        fila["cotizacion_cent"],
    ) == (
        "ARS",
        3500000,
        None,
        None,
    )


def test_ca_45_6_usd_a_pesos_por_debajo_de_lo_pagado(app, con):
    gid = _usd(con, app.mes_id, 2000, 160000)
    insertar_pago(con, gid, 3200000)
    d = _editar(app, gid)
    _elegir_moneda(d, "ARS")
    d.monto.value = "30.000"
    d._guardar()
    assert (
        d.monto.error
        == "No podés bajar el monto a menos de lo que ya pagaste ($ 32.000)."
    )
    assert gastos.obtener_gasto(con, gid)["moneda"] == "USD"


def test_ca_45_5_pesos_a_dolares_en_edicion(app, con, pagina):
    gid = gastos.agregar_gasto(con, app.mes_id, "Nafta", _otros(con), 3000000, "fijo")
    d = _editar(app, gid)
    assert d.moneda.selected == ["ARS"]
    _elegir_moneda(d, "USD")
    assert (d.monto_usd.value or "") == ""
    assert d.cotizacion.value == "1.600"  # la del mes, como en un alta
    assert d.aviso_paso_a_pesos.visible is False
    assert _enfocado(pagina) is d.monto_usd
    _escribir(d.monto_usd, "25")
    d._guardar()
    fila = gastos.obtener_gasto(con, gid)
    assert (fila["moneda"], fila["monto_cent"]) == ("USD", 4000000)


# ---------------------------------------------------------------------------
# Tabla de gastos (§3.3, RF-46)
# ---------------------------------------------------------------------------


def _celda_monto(app, nombre):
    return celda(app.pantalla("Gastos"), nombre, "Monto").content


def test_ca_46_1_tabla_con_segunda_linea_y_tooltip(app, con):
    gastos.agregar_gasto(
        con, app.mes_id, "Gastos del mes", _otros(con), 143461700, "fijo"
    )
    _usd(con, app.mes_id, 2000, 160000)
    app.refrescar()
    celda = _celda_monto(app, "Claude")
    assert isinstance(celda, ft.Column)
    pesos, detalle = celda.controls
    assert pesos.value == "$ 32.000"
    assert detalle.value == "US$ 20,00 × $ 1.600"
    assert (detalle.size, detalle.color) == (13, estilos.TEXTO_SECUNDARIO)
    assert celda.tooltip == (
        "Gasto en dólares: US$ 20,00 a $ 1.600 por US$ = $ 32.000. "
        "Los pesos quedan fijos con esa cotización."
    )
    # Los gastos en pesos no muestran detalle en dólares.
    ars = _celda_monto(app, "Gastos del mes")
    assert isinstance(ars, ft.Text) and ars.value == "$ 1.434.617"
    # El total sigue en pesos y suma los pesos del gasto en dólares.
    total = filas_tabla(app.pantalla("Gastos"))[-1]
    assert (total["Nombre"], total["Monto"]) == ("TOTAL (2 gastos)", "$ 1.466.617")
    assert not any("US$" in t for t in total.values() if t)
    assert (
        de_tipo(app.pantalla("Gastos").cuerpo, ft.DataTable)[0].data_row_max_height
        == 64
    )


def test_ca_46_2_cotizacion_con_decimales_en_la_tabla(app, con):
    _usd(con, app.mes_id, 1999, 143250)
    app.refrescar()
    pesos, detalle = _celda_monto(app, "Claude").controls
    assert pesos.value == "$ 28.636"
    assert detalle.value == "US$ 19,99 × $ 1.432,50"


def test_la_moneda_no_cambia_el_orden(app, con):
    _usd(con, app.mes_id, 2000, 160000, nombre="Zeta", tipo="fijo")
    gastos.agregar_gasto(con, app.mes_id, "Alquiler", _otros(con), 100, "fijo")
    _usd(con, app.mes_id, 2000, 160000, nombre="Beta", tipo="unico")
    app.refrescar()
    assert [f["Nombre"] for f in filas_tabla(app.pantalla("Gastos"))[:-1]] == [
        "Alquiler",
        "Zeta",
        "Beta",
    ]


# ---------------------------------------------------------------------------
# Error al abrir la base (RN-59: la app avisa)
# ---------------------------------------------------------------------------


def test_mostrar_error_al_abrir_con_error_inesperado():
    # O18: un error que no es ErrorDeBase no promete ningún respaldo.
    pagina = PaginaFalsa()
    mostrar_error_al_abrir(pagina, RuntimeError("falla rara (simulada)"))
    assert pagina.title == "Gastos – No se pudo abrir"
    contenido = textos(pagina.controls[0])
    assert contenido[0] == "No se pudo abrir la base de datos"
    assert "Ocurrió un error inesperado al abrir la base." in contenido
    assert not any("respaldo" in t for t in contenido[:2])
    assert any("falla rara (simulada)" in t for t in contenido)  # detalle técnico


@pytest.mark.parametrize(
    "mensaje",
    [
        (
            "No se pudo hacer la copia de respaldo, así que la base no se actualizó. "
            "Tus datos no se modificaron."
        ),
        (
            "No se pudo actualizar la base. Tus datos no se modificaron. "
            "Hay una copia de respaldo en C:/tmp/respaldos/gastos-20261004-120000.db."
        ),
        (
            "Esta base es de una versión más nueva de la app. "
            "Actualizá la app antes de abrirla. Tus datos no se modificaron."
        ),
    ],
)
def test_mostrar_error_al_abrir_con_error_de_base(mensaje):
    # O18: un ErrorDeBase se muestra tal cual, con el detalle técnico debajo.
    pagina = PaginaFalsa()
    try:
        try:
            raise sqlite3.OperationalError("causa original (simulada)")
        except sqlite3.OperationalError as causa:
            raise base_datos.ErrorDeBase(mensaje) from causa
    except base_datos.ErrorDeBase as error:
        mostrar_error_al_abrir(pagina, error)
    contenido = textos(pagina.controls[0])
    assert contenido[:2] == ["No se pudo abrir la base de datos", mensaje]
    assert "Ocurrió un error inesperado al abrir la base." not in contenido
    # El detalle técnico incluye la causa original (__cause__).
    assert any("causa original (simulada)" in t for t in contenido)


def test_main_con_una_base_real_que_falla_muestra_el_mensaje(tmp_path, monkeypatch):
    # De punta a punta, con un archivo temporal: base de una versión más nueva.
    ruta = tmp_path / "gastos.db"
    crudo = sqlite3.connect(ruta)
    crudo.execute("PRAGMA user_version = 2")
    crudo.commit()
    crudo.close()
    original = base_datos.conectar
    monkeypatch.setattr(base_datos, "conectar", lambda: original(ruta))
    pagina = PaginaFalsa()
    main(pagina)
    contenido = textos(pagina.controls[0])
    assert pagina.title == "Gastos – No se pudo abrir"
    assert contenido[1].startswith("Esta base es de una versión más nueva de la app.")


def test_main_muestra_el_error_si_la_base_no_abre(monkeypatch):
    # main() con conectar reemplazado: nunca toca datos-privados/.
    def falla():
        raise OSError("no se pudo crear el respaldo (simulado)")

    monkeypatch.setattr(base_datos, "conectar", falla)
    pagina = PaginaFalsa()
    main(pagina)
    assert pagina.title == "Gastos – No se pudo abrir"


def test_main_arranca_normal_si_la_base_abre(monkeypatch):
    # conectar reemplazado por una base en memoria: arranca en primer uso.
    original = base_datos.conectar
    abiertas = []

    def conectar_en_memoria():
        abiertas.append(original(":memory:"))
        return abiertas[-1]

    monkeypatch.setattr(base_datos, "conectar", conectar_en_memoria)
    pagina = PaginaFalsa()
    main(pagina)
    assert pagina.title == "Gastos – Bienvenido"
    for con in abiertas:  # la prueba cierra lo que abrió
        con.close()


# ---------------------------------------------------------------------------
# BUG-09: avisos al guardar
# ---------------------------------------------------------------------------


def test_bug09_alta_en_dolares_con_decimales(app, con, pagina):
    # El aviso usa los pesos guardados (redondeados para mostrar) y los dólares.
    _cargar_claude(app, con, usd="19,99", cotizacion="1.432,50")
    assert pagina.avisos()[-1] == 'Gasto "Claude" agregado: $ 28.636 (US$ 19,99)'


def test_bug09_alta_en_pesos_sin_montos(app, con, pagina):
    d = _nuevo(app)
    d.nombre.value = "  Nafta  "
    d.categoria.value = str(_otros(con))
    d.monto.value = "30.000"
    d._guardar()
    assert pagina.avisos()[-1] == 'Gasto "Nafta" agregado'


def test_bug09_edicion_en_dolares_sin_montos(app, con, pagina):
    gid = _usd(con, app.mes_id, 2000, 160000)
    d = _editar(app, gid)
    _escribir(d.cotizacion, "1.700")
    d._guardar()
    assert pagina.avisos()[-1] == 'Gasto "Claude" actualizado'


def test_bug09_edicion_de_pesos_a_dolares_sin_montos(app, con, pagina):
    gid = gastos.agregar_gasto(con, app.mes_id, "Nafta", _otros(con), 3000000, "fijo")
    d = _editar(app, gid)
    _elegir_moneda(d, "USD")
    _escribir(d.monto_usd, "25")
    d._guardar()
    assert pagina.avisos()[-1] == 'Gasto "Nafta" actualizado'


def test_bug09_el_aviso_usa_el_nombre_guardado(app, con, pagina):
    # El nombre del aviso sale del gasto guardado (sin espacios de más).
    gid = _usd(con, app.mes_id, 2000, 160000)
    d = _editar(app, gid)
    d.nombre.value = "  Claude   Pro "
    d._guardar()
    assert pagina.avisos()[-1] == 'Gasto "Claude Pro" actualizado'
