"""Pruebas de la interfaz de la cotización automática (paso 9b, Módulo L: RF-59 a RF-62,
RN-84, RN-86, RN-88; CA-25.5, CA-59.x a CA-62.x; docs/diseno.md §3.6 y §3.10).

NUNCA se conectan a internet: se reemplaza cotizacion_online.pedir por una fuente falsa que
anota los pedidos (ver Fuente en test_cotizacion_online.py). Página falsa, sin ventanas.
Hoy = 2026-10-18 (mes actual 2026-10). Los tiempos de la fuente se escalan (3 s -> 0,3 s;
10 s -> 0,2 s) para no esperar de verdad. La búsqueda (page.run_task(self._buscar)) se
ejecuta de verdad con asyncio, o sea con asyncio.to_thread y asyncio.wait_for.

Base de los CA: 2026-09 (cotización 1.600), 2026-10 (sueldo 1.200, cotización 1.600, gastos
1.434.617) y 2026-11 (sin cotización). Datos inventados.
"""

import asyncio
import inspect
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.logica import (
    catalogos,
    configuracion,
    cotizacion_online,
    gastos,
    meses,
)
from app.logica.cotizacion_online import MENSAJE_ERROR
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    boton,
    clic,
    de_tipo,
    dialogo_arriba,
    hay_boton,
    ir,
    recorrer,
    tecla,
    textos,
)
from tests.test_cotizacion_online import BASE, _FALTA, Fuente, cuerpo
from tests.test_interfaz_resumen import _monto, _tarjeta

ORIGEN_BASE = "Dólar blue compra, 18/10/2026 14:05 (DolarApi)"
AYUDA_BOTON = (
    "Trae el precio de compra de hoy desde internet (DolarApi) y completa el campo. "
    "No se guarda hasta que toques Guardar. El dólar se elige en Ajustes."
)


# ---------------------------------------------------------------------------
# Base y ayudantes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """El mes actual es 2026-10 (como en los CA)."""
    original = meses.mes_actual_calendario
    monkeypatch.setattr(
        meses,
        "mes_actual_calendario",
        lambda hoy=None: (2026, 10) if hoy is None else original(hoy),
    )


@pytest.fixture
def fuente(monkeypatch):
    f = Fuente()
    monkeypatch.setattr(cotizacion_online, "pedir", f)
    return f


@pytest.fixture
def mundo(con, fuente):
    """App con 2026-09, 2026-10 y 2026-11 (sin cotización) y gastos 1.434.617 en octubre."""
    sep = meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    octubre = meses.crear_mes(con, 2026, 10, 120000, 160000)
    nov = meses.crear_mes(con, 2026, 11, 120000, None)
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gastos.agregar_gasto(con, octubre, "Gastos del mes", otros, 143461700, "unico")
    pagina = PaginaFalsa()
    app = Aplicacion(pagina, con)
    app.iniciar()
    app.seleccionar_mes(octubre, pantalla="Resumen")
    app.ids = SimpleNamespace(sep=sep, oct=octubre, nov=nov)
    return app


def cot(app, mes_id):
    return meses.obtener_mes(app.con, mes_id)["cotizacion_cent"]


def abrir(app, mes_id):
    """Abre el diálogo de la cotización del mes pedido y lo devuelve."""
    app.seleccionar_mes(mes_id)
    app.editar_cotizacion()
    return dialogo_arriba(app)


def campo(d):
    return d.content.controls[0]


def hay_busqueda(d):
    return any(
        isinstance(b, ft.OutlinedButton) and str(b.content).startswith("Buscar dólar")
        for b in recorrer(d)
    )


def btn_buscar(d):
    [b] = [
        b for b in de_tipo(d, ft.OutlinedButton) if str(b.content).startswith("Buscar")
    ]
    return b


def ruedita(d):
    [r] = de_tipo(d, ft.ProgressRing)
    return r


def fila_origen(d):
    [fila] = [
        r
        for r in de_tipo(d, ft.Row)
        if any(
            isinstance(c, ft.Icon) and c.icon == ft.Icons.INFO_OUTLINE
            for c in r.controls
        )
    ]
    return fila


def origen(d):
    """El texto del origen si se ve; None si está oculto."""
    fila = fila_origen(d)
    return fila.controls[1].value if fila.visible else None


def error(d):
    """True si el aviso de error se ve."""
    [aviso] = [
        c
        for c in de_tipo(d, ft.Container)
        if MENSAJE_ERROR in textos(c) and isinstance(c.content, ft.Row)
    ]
    return aviso.visible


def texto_visible(d, texto):
    return [t for t in de_tipo(d, ft.Text) if t.value == texto]


def buscando(d):
    """Texto de estado y ruedita visibles."""
    [estado] = texto_visible(d, "Buscando la cotización…")
    assert estado.visible == ruedita(d).visible
    return estado.visible


def tareas_de_busqueda(app):
    return [t for t in app.page.tareas if getattr(t, "__name__", "") == "_buscar"]


def tocar_buscar(app):
    """Clic en el botón de buscar. Devuelve la función async pendiente (o None)."""
    antes = len(tareas_de_busqueda(app))
    btn_buscar(dialogo_arriba(app)).on_click(None)
    nuevas = tareas_de_busqueda(app)[antes:]
    return nuevas[0] if nuevas else None


def buscar_y_esperar(app):
    """Clic en buscar y espera la respuesta de verdad (asyncio)."""
    tarea = tocar_buscar(app)
    assert tarea is not None, "el clic no pidió ninguna búsqueda"
    asyncio.run(tarea())


def enfocado(app):
    return app.page.tareas[-1].__self__


def con_demora(app, _demora, escenario):
    """Corre escenario(tarea) con la búsqueda en marcha, en un bucle asyncio real."""

    async def principal():
        tarea = tocar_buscar(app)
        hilo = asyncio.create_task(tarea())
        await asyncio.sleep(0.05)
        await escenario()
        await hilo

    asyncio.run(principal())


# ---------------------------------------------------------------------------
# Ajustes: pestaña Cotización (RF-59, CA-59.1 a CA-59.4, §3.10)
# ---------------------------------------------------------------------------


def ajustes_cotizacion(app):
    ir(app, "Ajustes")
    return app.pantalla("Ajustes").cotizacion


def test_ca_59_1_ajustes_muestra_blue_y_cuatro_opciones(mundo):
    pestana = ajustes_cotizacion(mundo)
    assert pestana.opciones.value == "blue"
    radios = de_tipo(pestana.control, ft.Radio)
    assert [(r.value, r.label) for r in radios] == [
        ("blue", "Blue"),
        ("mep", "MEP"),
        ("oficial", "Oficial"),
        ("cripto", "Cripto"),
    ]
    assert "Dólar para la cotización" in textos(pestana.control)
    # No hay ninguna opción de compra o venta.
    assert not any(r.label in ("Compra", "Venta") for r in radios)


def test_ajustes_tiene_siete_pestanas_con_cotizacion_entre_meta_y_apariencia(mundo):
    ir(mundo, "Ajustes")
    ajustes = mundo.pantalla("Ajustes")
    tabs = ajustes.pestanas.content.controls[0]
    assert [t.label for t in tabs.tabs] == [
        "Categorías",
        "Medios de pago",
        "Personas",
        "Meta de ahorro",
        "Cotización",
        "Apariencia",
        "Importar Excel",
    ]
    assert ajustes.pestanas.length == 7
    assert len(ajustes.pestanas.content.controls[1].controls) == 7
    assert tabs.scrollable is True  # a 1100 px no entran 7 pestañas (observación 33)


def test_ca_59_1_el_dialogo_tiene_el_boton_blue_y_el_pedido_va_a_blue(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    assert btn_buscar(d).content == "Buscar dólar blue"
    assert fuente.pedidos == []
    buscar_y_esperar(mundo)
    assert [u for u, _ in fuente.pedidos] == ["https://dolarapi.com/v1/dolares/blue"]


@pytest.mark.parametrize(
    ("dolar", "boton_", "casa", "nombre"),
    [
        ("mep", "Buscar dólar MEP", "bolsa", "MEP"),
        ("oficial", "Buscar dólar oficial", "oficial", "oficial"),
        ("cripto", "Buscar dólar cripto", "cripto", "cripto"),
    ],
)
def test_ca_59_2_elegir_otro_dolar(mundo, fuente, dolar, boton_, casa, nombre):
    pestana = ajustes_cotizacion(mundo)
    pestana.opciones.value = dolar
    pestana.opciones.on_change(SimpleNamespace(control=pestana.opciones))
    assert (
        mundo.page.avisos()[-1]
        == f"Dólar para la cotización: {pestana.OPCIONES[dolar]}"
    )
    fila = mundo.con.execute(
        "SELECT valor FROM configuracion WHERE clave = 'dolar_cotizacion'"
    ).fetchone()
    assert fila["valor"] == dolar
    d = abrir(mundo, mundo.ids.oct)
    assert btn_buscar(d).content == boton_
    buscar_y_esperar(mundo)
    assert [u for u, _ in fuente.pedidos] == [f"https://dolarapi.com/v1/dolares/{casa}"]
    assert origen(d) == f"Dólar {nombre} compra, 18/10/2026 14:05 (DolarApi)"


def test_aviso_dice_mep_con_su_etiqueta(mundo):
    pestana = ajustes_cotizacion(mundo)
    pestana.elegir("mep")
    assert mundo.page.avisos()[-1] == "Dólar para la cotización: MEP"


def test_ca_59_3_el_dolar_elegido_sobrevive_a_cerrar_y_abrir(mundo, pagina):
    ajustes_cotizacion(mundo).elegir("mep")
    nueva = Aplicacion(
        PaginaFalsa(), mundo.con
    )  # "volver a abrir la app" con la misma base
    nueva.iniciar()
    ir(nueva, "Ajustes")
    assert nueva.pantalla("Ajustes").cotizacion.opciones.value == "mep"
    d = abrir(nueva, mundo.ids.oct)
    assert btn_buscar(d).content == "Buscar dólar MEP"


def test_ca_59_3_valor_desconocido_en_la_base_muestra_blue(mundo):
    mundo.con.execute(
        "INSERT INTO configuracion (clave, valor) VALUES ('dolar_cotizacion', 'xyz')"
    )
    pestana = ajustes_cotizacion(mundo)
    assert pestana.opciones.value == "blue"
    assert btn_buscar(abrir(mundo, mundo.ids.oct)).content == "Buscar dólar blue"


def test_ca_59_4_cambiar_el_dolar_no_cambia_cotizaciones_ni_busca(mundo, fuente):
    pestana = ajustes_cotizacion(mundo)
    pestana.elegir("mep")
    assert (
        cot(mundo, mundo.ids.sep),
        cot(mundo, mundo.ids.oct),
        cot(mundo, mundo.ids.nov),
    ) == (
        160000,
        160000,
        None,
    )
    assert fuente.pedidos == []
    assert tareas_de_busqueda(mundo) == []


def test_elegir_con_fallo_vuelve_a_la_opcion_guardada_y_avisa_el_error(
    mundo, monkeypatch
):
    pestana = ajustes_cotizacion(mundo)
    pestana.elegir("oficial")

    def falla(con, dolar):
        raise RuntimeError("disco lleno inventado")

    monkeypatch.setattr(configuracion, "guardar_dolar", falla)
    pestana.opciones.value = "cripto"  # lo que el usuario acaba de tocar
    pestana.elegir("cripto")
    assert pestana.opciones.value == "oficial"  # volvió a lo guardado
    assert configuracion.obtener_dolar(mundo.con) == "oficial"
    assert mundo.hay_dialogo_abierto()  # error_inesperado
    assert "Dólar para la cotización: Cripto" not in mundo.page.avisos()


def test_elegir_la_misma_opcion_de_nuevo_no_rompe(mundo):
    pestana = ajustes_cotizacion(mundo)
    pestana.elegir("mep")
    pestana.elegir("mep")
    assert configuracion.obtener_dolar(mundo.con) == "mep"


def test_ajustes_no_pide_nada_al_cambiar_de_pestana(mundo, fuente):
    ajustes = mundo.pantalla("Ajustes")
    ir(mundo, "Ajustes")
    for i in range(7):
        ajustes.pestanas.selected_index = i
        ajustes.pestanas.on_change(None)
    assert fuente.pedidos == []


def test_ctrl_n_en_cotizacion_no_hace_nada(mundo):
    pestana = ajustes_cotizacion(mundo)
    ajustes = mundo.pantalla("Ajustes")
    ajustes.pestanas.selected_index = ajustes.indice_de(pestana)
    mundo._al_presionar_tecla(tecla("N", ctrl=True))
    assert not mundo.hay_dialogo_abierto()


# ---------------------------------------------------------------------------
# Qué meses tienen botón (RN-80, CA-25.5, CA-60.1, CA-60.2)
# ---------------------------------------------------------------------------


def test_ca_60_1_botones_por_mes(mundo):
    d_oct = abrir(mundo, mundo.ids.oct)
    assert hay_busqueda(d_oct)
    mundo.cerrar_dialogo(d_oct)
    d_nov = abrir(mundo, mundo.ids.nov)
    assert hay_busqueda(d_nov)
    mundo.cerrar_dialogo(d_nov)
    d_sep = abrir(mundo, mundo.ids.sep)
    assert not hay_busqueda(d_sep)
    # Sin botón, ni deshabilitado, ni su ayuda, ni ruedita, ni origen, ni error.
    assert de_tipo(d_sep, ft.OutlinedButton) == []
    assert de_tipo(d_sep, ft.ProgressRing) == []
    assert AYUDA_BOTON not in textos(d_sep)
    assert MENSAJE_ERROR not in textos(d_sep)
    assert "Buscando la cotización…" not in textos(d_sep)


def test_ca_25_5_octubre_tiene_el_boton_y_septiembre_no(mundo):
    assert btn_buscar(abrir(mundo, mundo.ids.oct)).content == "Buscar dólar blue"
    mundo.cerrar_dialogo(dialogo_arriba(mundo))
    assert not hay_busqueda(abrir(mundo, mundo.ids.sep))


def test_ca_60_1_septiembre_se_edita_a_mano_como_siempre(mundo, fuente):
    d = abrir(mundo, mundo.ids.sep)
    campo(d).value = "1.650"
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.sep) == 165000
    assert d.open is False
    assert fuente.pedidos == []


def test_septiembre_el_dialogo_es_igual_que_antes_de_la_v2(mundo):
    d = abrir(mundo, mundo.ids.sep)
    # Controles del cuerpo: el campo y las ayudas (nada más).
    controles = d.content.controls
    assert isinstance(controles[0], ft.TextField)
    assert all(isinstance(c, ft.Text) for c in controles[1:])


def test_ca_60_2_con_el_mes_actual_en_noviembre(mundo, monkeypatch):
    monkeypatch.setattr(meses, "mes_actual_calendario", lambda hoy=None: (2026, 11))
    d_oct = abrir(mundo, mundo.ids.oct)
    assert not hay_busqueda(d_oct)
    mundo.cerrar_dialogo(d_oct)
    assert hay_busqueda(abrir(mundo, mundo.ids.nov))


def test_cambio_de_anio_diciembre_2026_vs_enero_2027(mundo, monkeypatch):
    # Borde: se compara (año, mes), no solo el mes: 2026-11 < 2027-01.
    monkeypatch.setattr(meses, "mes_actual_calendario", lambda hoy=None: (2027, 1))
    assert not hay_busqueda(abrir(mundo, mundo.ids.nov))


def test_mes_futuro_agrega_la_frase_de_cotizacion_de_hoy(mundo):
    d_nov = abrir(mundo, mundo.ids.nov)
    assert AYUDA_BOTON + " Es la cotización de hoy, no la de Noviembre 2026." in textos(
        d_nov
    )
    mundo.cerrar_dialogo(d_nov)
    d_oct = abrir(mundo, mundo.ids.oct)
    assert AYUDA_BOTON in textos(d_oct)
    assert not any("Es la cotización de hoy" in t for t in textos(d_oct))


def test_orden_vertical_del_dialogo(mundo):
    # §3.6: campo, origen, fila de búsqueda, error, ayuda del botón, ayuda de siempre.
    d = abrir(mundo, mundo.ids.oct)
    c = d.content.controls
    assert isinstance(c[0], ft.TextField)
    assert c[1] is fila_origen(d)
    assert btn_buscar(d) in recorrer(c[2])
    assert ruedita(d) in recorrer(c[2])
    assert c[3].content.controls[1].value == MENSAJE_ERROR
    assert c[4].value == AYUDA_BOTON
    assert c[5].value.startswith("Se usa para calcular")


def test_estado_inicial_del_dialogo(mundo, fuente):
    # Sin buscar: sin origen, sin error, sin ruedita, botón habilitado, Guardar habilitado.
    d = abrir(mundo, mundo.ids.oct)
    assert origen(d) is None
    assert error(d) is False
    assert buscando(d) is False
    assert btn_buscar(d).disabled in (None, False)
    assert boton(d, "Guardar").disabled in (None, False)
    assert campo(d).read_only in (None, False)
    assert campo(d).value == "1.600"
    assert campo(d).autofocus is True
    assert btn_buscar(d).icon == ft.Icons.CLOUD_DOWNLOAD_OUTLINED
    assert (
        btn_buscar(d).tooltip
        == "Busca el precio de compra de hoy en internet. No guarda nada."
    )
    assert fuente.pedidos == []


# ---------------------------------------------------------------------------
# Nunca busca sola (RN-88, CA-60.3)
# ---------------------------------------------------------------------------


def test_ca_60_3_nunca_busca_sola(mundo, fuente):
    # Cambiar de mes, abrir y cerrar el diálogo sin tocar el botón, cambiar el dólar en
    # Ajustes y crear el mes 2026-12: ningún pedido.
    for mes in (mundo.ids.sep, mundo.ids.nov, mundo.ids.oct):
        mundo.seleccionar_mes(mes)
    d = abrir(mundo, mundo.ids.oct)
    clic(d, "Cancelar")
    d = abrir(mundo, mundo.ids.nov)
    clic(d, "Cancelar")
    ajustes_cotizacion(mundo).elegir("mep")
    mundo.seleccionar_mes(mundo.ids.nov)
    mundo.crear_mes_nuevo()
    nuevo = dialogo_arriba(mundo)
    assert not hay_busqueda(nuevo)
    assert not any("Buscar" in t for t in textos(nuevo))
    # RN-09: sugiere la cotización del último mes. 2026-11 no tiene: queda vacío.
    sugerido = [t for t in de_tipo(nuevo, ft.TextField) if t.label == "Cotización"][0]
    assert sugerido.value in (None, "")
    clic(nuevo, "Crear mes")
    assert meses.obtener_ultimo_mes(mundo.con)["mes"] == 12
    assert fuente.pedidos == []
    assert tareas_de_busqueda(mundo) == []


def test_ca_60_3_mes_nuevo_sugiere_la_cotizacion_del_ultimo_mes_sin_boton(
    mundo, fuente
):
    meses.editar_cotizacion(mundo.con, mundo.ids.nov, 170000)
    mundo.crear_mes_nuevo()
    nuevo = dialogo_arriba(mundo)
    campo_cot = [t for t in de_tipo(nuevo, ft.TextField) if t.label == "Cotización"][0]
    assert campo_cot.value == "1.700"
    assert not hay_busqueda(nuevo)
    assert de_tipo(nuevo, ft.ProgressRing) == []
    assert fuente.pedidos == []


def test_ca_60_3_primer_uso_sin_boton(con, fuente):
    app = Aplicacion(PaginaFalsa(), con)
    app.iniciar()
    assert app.mes_id is None
    controles = recorrer(app.page.controls[-1])
    assert not any(
        isinstance(c, ft.OutlinedButton) and str(c.content).startswith("Buscar")
        for c in controles
    )
    assert not any(isinstance(c, ft.ProgressRing) for c in controles)
    assert fuente.pedidos == []


def test_ca_60_3_gasto_en_dolares_sin_boton(mundo, fuente):
    ir(mundo, "Gastos")
    mundo.pantalla("Gastos").nuevo()
    d = dialogo_arriba(mundo)
    asiento = boton(d, "Guardar").on_click.__self__
    asiento.moneda.selected = ["USD"]
    asiento.moneda.on_change(None)
    assert not hay_busqueda(d)
    assert de_tipo(d, ft.ProgressRing) == []
    assert fuente.pedidos == []


def test_ca_60_3_cambio_realizado_sin_boton(mundo, fuente):
    ir(mundo, "Resumen")
    clic(mundo.pantalla("Resumen").cuerpo, "Registrar cambio")
    d = dialogo_arriba(mundo)
    assert not hay_busqueda(d)
    assert de_tipo(d, ft.ProgressRing) == []
    assert fuente.pedidos == []


def test_ca_60_3_la_cotizacion_desde_cualquier_entrada_tiene_el_mismo_boton(mundo):
    # §3.6: Ctrl+K, el lápiz de la barra y "Cargar cotización" abren el mismo diálogo.
    mundo.seleccionar_mes(mundo.ids.oct)
    mundo._al_presionar_tecla(tecla("K", ctrl=True))
    assert hay_busqueda(dialogo_arriba(mundo))
    mundo.cerrar_dialogo(dialogo_arriba(mundo))
    mundo._cotizacion.on_click(None)
    assert hay_busqueda(dialogo_arriba(mundo))
    mundo.cerrar_dialogo(dialogo_arriba(mundo))
    mundo.seleccionar_mes(mundo.ids.nov)
    clic(mundo.pantalla("Resumen").cuerpo, "Cargar cotización")
    assert hay_busqueda(dialogo_arriba(mundo))


# ---------------------------------------------------------------------------
# Búsqueda válida (RN-83 a RN-85, CA-59.5, CA-61.1 a CA-61.6, CA-61.9)
# ---------------------------------------------------------------------------


def test_ca_59_5_y_61_1_el_campo_se_completa_con_la_compra_sin_guardar(mundo):
    resumen = mundo.pantalla("Resumen")
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.630,50"  # compra, no la venta 1.660
    assert origen(d) == ORIGEN_BASE
    assert error(d) is False
    assert buscando(d) is False
    # Mientras el diálogo sigue abierto, todo sigue con la cotización guardada.
    assert cot(mundo, mundo.ids.oct) == 160000
    assert mundo._texto_cotizacion.value == "Cotización $ 1.600 por US$"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 896,64"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 303,36"
    assert mundo.page.avisos() == []


def test_ca_61_1_al_guardar_se_guarda_lo_que_dice_el_campo(mundo):
    resumen = mundo.pantalla("Resumen")
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 163050
    assert d.open is False
    assert mundo._texto_cotizacion.value == "Cotización $ 1.630,50 por US$"
    assert mundo.page.avisos()[-1] == "Cotización actualizada: $ 1.630,50 por US$"
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 879,86"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 320,14"


def test_el_foco_va_al_campo_tras_acertar(mundo):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert enfocado(mundo) is campo(d)


def test_ca_61_2_cancelar_despues_de_buscar(mundo):
    resumen = mundo.pantalla("Resumen")
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    clic(d, "Cancelar")
    assert cot(mundo, mundo.ids.oct) == 160000
    assert _monto(_tarjeta(resumen, "Dólares a cambiar")).value == "US$ 896,64"
    assert _monto(_tarjeta(resumen, "Ahorro del mes")).value == "US$ 303,36"
    d2 = abrir(mundo, mundo.ids.oct)
    assert campo(d2).value == "1.600"
    assert origen(d2) is None


def test_ca_61_2_esc_despues_de_buscar(mundo):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    mundo._al_presionar_tecla(tecla("Escape"))
    assert d.open is False
    assert cot(mundo, mundo.ids.oct) == 160000
    d2 = abrir(mundo, mundo.ids.oct)
    assert campo(d2).value == "1.600"
    assert origen(d2) is None


def test_el_origen_no_se_guarda_tampoco_tras_guardar(mundo):
    # §3.6: al reabrir después de Guardar no se ve el origen, aunque el valor sea el de DolarApi.
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    clic(d, "Guardar")
    d2 = abrir(mundo, mundo.ids.oct)
    assert campo(d2).value == "1.630,50"
    assert origen(d2) is None
    assert error(d2) is False


def test_ca_61_3_mes_sin_cotizacion(mundo):
    d = abrir(mundo, mundo.ids.nov)
    assert not campo(d).value
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.630,50"
    assert origen(d) == ORIGEN_BASE
    assert cot(mundo, mundo.ids.nov) is None
    assert "Cargá la cotización" in textos(
        mundo.pantalla("Resumen").cuerpo
    )  # antes de guardar
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.nov) == 163050
    resumen = mundo.pantalla("Resumen")
    assert "Cargá la cotización" not in textos(resumen.cuerpo)


def test_ca_61_3_cancelar_deja_el_mes_sin_cotizacion(mundo):
    d = abrir(mundo, mundo.ids.nov)
    buscar_y_esperar(mundo)
    clic(d, "Cancelar")
    assert cot(mundo, mundo.ids.nov) is None
    assert not campo(abrir(mundo, mundo.ids.nov)).value
    resumen = mundo.pantalla("Resumen")
    assert "Cargá la cotización" in textos(resumen.cuerpo)


def test_ca_61_4_cotizacion_entera(mundo, fuente):
    fuente.contenido = cuerpo(compra=1630)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.630"
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 163000
    assert mundo._texto_cotizacion.value == "Cotización $ 1.630 por US$"


@pytest.mark.parametrize(
    ("compra", "texto", "centavos"),
    [(1630.555, "1.630,56", 163056), (1630.554, "1.630,55", 163055)],
)
def test_ca_61_9_mas_de_dos_decimales(mundo, fuente, compra, texto, centavos):
    fuente.contenido = cuerpo(compra=compra)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert campo(d).value == texto
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == centavos


def test_cotizacion_con_miles_en_el_campo(mundo, fuente):
    fuente.contenido = cuerpo(compra=1234567.8)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.234.567,80"
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 123456780


def test_ca_61_5_editar_a_mano_despues_de_buscar(mundo):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    campo(d).value = "1.640"
    campo(d).on_change(None)
    assert origen(d) is None
    campo(d).value = "1.630,50"  # volver a escribir lo mismo no lo trae de vuelta
    campo(d).on_change(None)
    assert origen(d) is None
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 163050


def test_ca_61_5_tocar_de_nuevo_vuelve_a_completar_y_mostrar_el_origen(mundo):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    campo(d).value = "1.640"
    campo(d).on_change(None)
    assert origen(d) is None
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.630,50"
    assert origen(d) == ORIGEN_BASE


def test_salir_del_campo_no_borra_el_origen(mundo):
    # §3.6: on_blur reescribe el formato pero no es un cambio del usuario.
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    campo(d).on_blur(None)
    assert origen(d) == ORIGEN_BASE
    assert campo(d).value == "1.630,50"


def test_la_busqueda_no_dispara_el_on_change_del_campo(mundo):
    # Si el código lo disparara, la búsqueda borraría su propio origen.
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert origen(d) == ORIGEN_BASE


def test_la_busqueda_borra_el_error_de_validacion_del_campo(mundo):
    # Borde: un error de "Ingresá la cotización." queda en el campo; la búsqueda lo limpia.
    d = abrir(mundo, mundo.ids.nov)
    clic(d, "Guardar")  # campo vacío -> error en el campo
    assert campo(d).error == "Ingresá la cotización."
    buscar_y_esperar(mundo)
    assert campo(d).error is None
    assert campo(d).value == "1.630,50"


def test_buscar_reemplaza_lo_que_el_usuario_habia_escrito(mundo):
    # RN-84: una búsqueda válida reemplaza el contenido del campo, sea cual sea.
    d = abrir(mundo, mundo.ids.oct)
    campo(d).value = "999"
    campo(d).on_change(None)
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.630,50"


def test_se_puede_buscar_varias_veces_y_cada_una_reemplaza(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    fuente.contenido = cuerpo(compra=1700.25, fechaActualizacion="2026-10-18T18:00:00Z")
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.700,25"
    assert origen(d) == "Dólar blue compra, 18/10/2026 15:00 (DolarApi)"
    assert len(fuente.pedidos) == 2


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        ("2026-10-18T02:30:00Z", "17/10/2026 23:30"),
        ("2026-10-18T14:05:00-03:00", "18/10/2026 14:05"),
        ("2026-10-18T17:05:59Z", "18/10/2026 14:05"),
    ],
)
def test_ca_61_6_hora_de_argentina_en_pantalla(mundo, fuente, fecha, esperado):
    # Aunque la computadora diga 20:00, se muestra la hora de la fuente.
    fuente.contenido = cuerpo(fechaActualizacion=fecha)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert origen(d) == f"Dólar blue compra, {esperado} (DolarApi)"


def test_origen_largo_baja_de_linea_con_expand(mundo):
    d = abrir(mundo, mundo.ids.oct)
    assert fila_origen(d).controls[1].expand is True


# ---------------------------------------------------------------------------
# Errores (RN-87, CA-62.1 a CA-62.6)
# ---------------------------------------------------------------------------


def comprobar_error(mundo, d, campo_esperado="1.600"):
    assert error(d) is True
    assert MENSAJE_ERROR in textos(d)
    assert campo(d).value == campo_esperado
    assert origen(d) is None or campo_esperado == "1.630,50"
    assert buscando(d) is False
    assert btn_buscar(d).disabled in (None, False)
    assert boton(d, "Guardar").disabled in (None, False)
    assert campo(d).read_only in (None, False)
    assert enfocado(mundo) is btn_buscar(d)  # foco al botón para reintentar
    assert mundo.page.avisos() == []  # el error va en el diálogo, no en un SnackBar
    assert mundo.hay_dialogo_abierto() and dialogo_arriba(mundo) is d


def test_ca_62_1_sin_conexion(mundo, monkeypatch):
    import urllib.error

    monkeypatch.setattr(
        cotizacion_online, "pedir", Fuente(error=urllib.error.URLError("sin internet"))
    )
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    comprobar_error(mundo, d)
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 160000
    assert mundo._texto_cotizacion.value == "Cotización $ 1.600 por US$"


def test_ca_62_1_el_mensaje_no_tiene_detalles_tecnicos(mundo, monkeypatch):
    monkeypatch.setattr(
        cotizacion_online, "pedir", Fuente(error=OSError("getaddrinfo failed 10.0.0.1"))
    )
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert not any("getaddrinfo" in t or "10.0.0.1" in t for t in textos(d))


def test_ca_62_2_sin_respuesta_a_los_10_segundos(mundo, monkeypatch, fuente):
    # Escala: límite 0,2 s (en lugar de 10 s) y la fuente tarda 0,6 s. Respuesta base
    # tardía (el "12 s"): se descarta.
    fuente.demora = 0.6
    real = cotizacion_online.buscar_con_limite
    monkeypatch.setattr(
        cotizacion_online, "buscar_con_limite", lambda con: real(con, tiempo_maximo=0.2)
    )
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    comprobar_error(mundo, d)
    assert origen(d) is None
    assert cot(mundo, mundo.ids.oct) == 160000


def test_ca_62_2_el_limite_es_de_10_segundos_en_la_interfaz():
    # La interfaz no pasa otro límite: usa el predeterminado (10 s).
    from app.interfaz.dialogos import dialogos_valores

    fuente_buscar = inspect.getsource(dialogos_valores._BusquedaCotizacion._buscar)
    assert "buscar_con_limite(self.app.con)" in fuente_buscar
    param = inspect.signature(cotizacion_online.buscar_con_limite).parameters[
        "tiempo_maximo"
    ]
    assert param.default == 10


@pytest.mark.parametrize(
    "compra",
    [0, -5, _FALTA, None, "abc", "1630.5", True, 0.004],
)
def test_ca_62_3_compra_invalida(mundo, fuente, compra):
    fuente.contenido = cuerpo(compra=compra)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    comprobar_error(mundo, d)
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 160000


@pytest.mark.parametrize(
    ("contenido", "estado"),
    [
        (b"<html>Error</html>", 200),
        (b"[]", 200),
        (cuerpo(), 500),
        (cuerpo(), 404),
        (b"", 200),
    ],
)
def test_ca_62_3_contenido_y_estados_invalidos(mundo, fuente, contenido, estado):
    fuente.contenido, fuente.estado = contenido, estado
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    comprobar_error(mundo, d)
    assert cot(mundo, mundo.ids.oct) == 160000


@pytest.mark.parametrize("fecha", [_FALTA, "ayer", "2026-10-18T14:05:00"])
def test_ca_62_4_fecha_no_valida(mundo, fuente, fecha):
    fuente.contenido = cuerpo(fechaActualizacion=fecha)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    comprobar_error(mundo, d)


@pytest.mark.parametrize("venta", [_FALTA, "abc"])
def test_ca_62_5_la_venta_no_se_usa(mundo, fuente, venta):
    fuente.contenido = cuerpo(venta=venta)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert campo(d).value == "1.630,50"
    assert error(d) is False
    assert origen(d) == ORIGEN_BASE


def test_ca_62_6_error_despues_de_un_acierto(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    fuente.error = OSError("sin internet")
    buscar_y_esperar(mundo)
    assert error(d) is True
    assert campo(d).value == "1.630,50"
    assert origen(d) == ORIGEN_BASE  # el mismo origen
    campo(d).value = "1.640"
    campo(d).on_change(None)
    assert error(d) is False
    assert origen(d) is None


def test_el_error_desaparece_al_buscar_de_nuevo(mundo, fuente):
    fuente.error = OSError("x")
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert error(d) is True
    fuente.error = None
    buscar_y_esperar(mundo)
    assert error(d) is False
    assert campo(d).value == "1.630,50"


def test_el_error_se_oculta_al_instante_de_empezar_otra_busqueda(mundo, fuente):
    fuente.error = OSError("x")
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert error(d) is True
    tocar_buscar(mundo)  # sin esperar la respuesta
    assert error(d) is False
    assert buscando(d) is True


def test_el_error_no_aparece_al_reabrir_el_dialogo(mundo, fuente):
    fuente.error = OSError("x")
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    clic(d, "Cancelar")
    assert error(abrir(mundo, mundo.ids.oct)) is False


def test_error_inesperado_cierra_el_dialogo_y_avisa(mundo, monkeypatch):
    # Una excepción que no es de validación (bug del código) no se disfraza de "sin conexión".
    async def rota(con):
        raise RuntimeError("falla inventada")

    monkeypatch.setattr(cotizacion_online, "buscar_con_limite", rota)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert d.open is False
    assert dialogo_arriba(mundo) is not d
    assert cot(mundo, mundo.ids.oct) == 160000


# ---------------------------------------------------------------------------
# Mientras busca (RN-86, CA-61.7, CA-61.8)
# ---------------------------------------------------------------------------


def test_ca_61_7_el_clic_marca_todo_antes_de_lanzar_el_pedido(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    tarea = tocar_buscar(mundo)
    assert tarea is not None
    assert fuente.pedidos == []  # todavía no salió ningún pedido
    assert buscando(d) is True
    assert btn_buscar(d).disabled is True
    assert btn_buscar(d).content == "Buscar dólar blue"  # mismo texto
    assert boton(d, "Guardar").disabled is True
    assert campo(d).read_only is True
    assert campo(d).disabled in (None, False)  # solo lectura, no deshabilitado
    assert boton(d, "Cancelar").disabled in (None, False)
    assert error(d) is False


def test_ca_61_7_durante_la_espera(mundo, fuente):
    fuente.demora = 0.3
    d = abrir(mundo, mundo.ids.oct)
    estados = {}

    async def durante():
        estados["buscando"] = buscando(d)
        estados["boton"] = btn_buscar(d).disabled
        estados["guardar"] = boton(d, "Guardar").disabled
        estados["solo_lectura"] = campo(d).read_only
        estados["cancelar"] = boton(d, "Cancelar").disabled
        # Enter en el campo no guarda; Guardar tampoco guarda aunque se llame al handler.
        campo(d).value = "1.700"
        campo(d).on_submit(None)
        boton(d, "Guardar").on_click(None)
        estados["abierto"] = d.open
        estados["en_base"] = cot(mundo, mundo.ids.oct)

    con_demora(mundo, 0.3, durante)
    assert estados.pop("cancelar") in (None, False)  # Cancelar sigue disponible
    estados["cancelar"] = None
    estados = {k: v for k, v in estados.items() if k != "cancelar"}
    assert estados == {
        "buscando": True,
        "boton": True,
        "guardar": True,
        "solo_lectura": True,
        "abierto": True,
        "en_base": 160000,
    }


def test_ca_61_7_dos_clics_hacen_un_solo_pedido(mundo, fuente):
    fuente.demora = 0.3
    d = abrir(mundo, mundo.ids.oct)

    async def durante():
        antes = len(tareas_de_busqueda(mundo))
        btn_buscar(d).on_click(None)  # segundo clic
        btn_buscar(d).on_click(None)  # tercero
        assert len(tareas_de_busqueda(mundo)) == antes

    con_demora(mundo, 0.3, durante)
    assert len(fuente.pedidos) == 1
    assert len(tareas_de_busqueda(mundo)) == 1


def test_ca_61_7_al_llegar_la_respuesta_todo_vuelve(mundo, fuente):
    fuente.demora = 0.2
    d = abrir(mundo, mundo.ids.oct)
    con_demora(mundo, 0.2, _nada)
    assert buscando(d) is False
    assert btn_buscar(d).disabled is False
    assert boton(d, "Guardar").disabled is False
    assert campo(d).read_only is False
    assert campo(d).value == "1.630,50"


async def _nada():
    return None


def test_despues_de_un_error_tambien_vuelve_a_habilitarse_todo(mundo, fuente):
    fuente.demora = 0.1
    fuente.error = OSError("x")
    d = abrir(mundo, mundo.ids.oct)
    con_demora(mundo, 0.1, _nada)
    assert btn_buscar(d).disabled is False
    assert boton(d, "Guardar").disabled is False
    assert campo(d).read_only is False


def test_se_puede_buscar_de_nuevo_despues_de_terminar(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    buscar_y_esperar(mundo)
    assert len(fuente.pedidos) == 2


def test_durante_la_busqueda_se_conserva_el_origen_anterior(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    fuente.demora = 0.3
    visto = {}

    async def durante():
        visto["origen"] = origen(d)
        visto["valor"] = campo(d).value

    con_demora(mundo, 0.3, durante)
    assert visto == {"origen": ORIGEN_BASE, "valor": "1.630,50"}


def test_ca_61_8_cancelar_mientras_busca(mundo, fuente):
    fuente.demora = 0.3
    d = abrir(mundo, mundo.ids.oct)
    avisos = len(mundo.page.mostrados)
    tareas_antes = len(mundo.page.tareas)

    async def durante():
        clic(d, "Cancelar")
        assert d.open is False
        assert not mundo.hay_dialogo_abierto()

    con_demora(mundo, 0.3, durante)
    assert len(fuente.pedidos) == 1
    # No cambió nada: ni base, ni mensajes, ni foco, ni diálogos nuevos.
    assert cot(mundo, mundo.ids.oct) == 160000
    assert len(mundo.page.mostrados) == avisos
    assert not mundo.hay_dialogo_abierto()
    assert len(mundo.page.tareas) == tareas_antes + 1  # solo la propia _buscar
    assert campo(d).value == "1.600"
    assert origen(d) is None
    d2 = abrir(mundo, mundo.ids.oct)
    assert campo(d2).value == "1.600"
    assert origen(d2) is None
    assert buscando(d2) is False
    assert error(d2) is False


def test_ca_61_8_esc_mientras_busca(mundo, fuente):
    fuente.demora = 0.3
    d = abrir(mundo, mundo.ids.oct)

    async def durante():
        mundo._al_presionar_tecla(tecla("Escape"))
        assert d.open is False

    con_demora(mundo, 0.3, durante)
    assert cot(mundo, mundo.ids.oct) == 160000
    assert mundo.page.avisos() == []
    assert not mundo.hay_dialogo_abierto()
    d2 = abrir(mundo, mundo.ids.oct)
    assert campo(d2).value == "1.600" and origen(d2) is None


def test_cerrar_mientras_busca_descarta_tambien_un_error(mundo, fuente):
    fuente.demora = 0.2
    fuente.error = OSError("x")
    d = abrir(mundo, mundo.ids.oct)

    async def durante():
        clic(d, "Cancelar")

    con_demora(mundo, 0.2, durante)
    assert error(d) is False  # nunca se mostró
    assert mundo.page.avisos() == []
    assert not mundo.hay_dialogo_abierto()


def test_cerrar_mientras_busca_descarta_un_fallo_inesperado(mundo, monkeypatch):
    async def rota(con):
        await asyncio.sleep(0.2)
        raise RuntimeError("falla inventada")

    monkeypatch.setattr(cotizacion_online, "buscar_con_limite", rota)
    d = abrir(mundo, mundo.ids.oct)

    async def durante():
        clic(d, "Cancelar")

    con_demora(mundo, 0.2, durante)
    assert not mundo.hay_dialogo_abierto()  # no se abrió el diálogo de error inesperado


def test_la_respuesta_de_un_dialogo_cerrado_no_toca_al_dialogo_nuevo(mundo, fuente):
    # RN-86: cerrar y reabrir mientras la primera busca. Cuando llega la respuesta de la
    # primera, el diálogo nuevo no debe cambiar ni mostrar la respuesta vieja.
    fuente.demora = 0.3
    a = abrir(mundo, mundo.ids.oct)
    visto = {}

    async def principal():
        hilo_a = asyncio.create_task(tocar_buscar(mundo)())
        await asyncio.sleep(0.05)
        clic(a, "Cancelar")
        b = abrir(mundo, mundo.ids.oct)
        await hilo_a
        visto["valor"] = campo(b).value
        visto["origen"] = origen(b)
        visto["buscando"] = buscando(b)
        visto["boton"] = btn_buscar(b).disabled
        visto["a_abierto"] = a.open

    asyncio.run(principal())
    assert visto["valor"] == "1.600"
    assert visto["origen"] is None
    assert visto["buscando"] is False
    assert visto["boton"] in (None, False)
    assert visto["a_abierto"] is False


def test_la_respuesta_vieja_no_apaga_la_busqueda_del_dialogo_nuevo(mundo, fuente):
    # A busca (0,3 s), se cierra; B se abre a los 0,1 s y busca. A termina a los 0,3 s: B
    # tiene que seguir "buscando" (ruedita, botón y Guardar deshabilitados) hasta las 0,4 s.
    fuente.demora = 0.3
    a = abrir(mundo, mundo.ids.oct)
    visto = {}

    async def principal():
        hilo_a = asyncio.create_task(tocar_buscar(mundo)())
        await asyncio.sleep(0.1)
        clic(a, "Cancelar")
        b = abrir(mundo, mundo.ids.oct)
        hilo_b = asyncio.create_task(tocar_buscar(mundo)())
        await hilo_a  # llega la de A (a los ~0,3 s)
        visto["b_buscando"] = buscando(b)
        visto["b_guardar"] = boton(b, "Guardar").disabled
        visto["b_valor"] = campo(b).value
        await hilo_b
        visto["b_final"] = campo(b).value
        visto["b_origen"] = origen(b)

    asyncio.run(principal())
    assert visto["b_buscando"] is True
    assert visto["b_guardar"] is True
    assert visto["b_valor"] == "1.600"
    assert visto["b_final"] == "1.630,50"
    assert visto["b_origen"] == ORIGEN_BASE
    assert len(fuente.pedidos) == 2


def test_respuesta_tardia_de_un_mes_ya_cambiado(mundo, fuente):
    # Borde: se cierra el diálogo de octubre mientras busca, se pasa a noviembre y se abre
    # su diálogo: la respuesta de octubre no puede completar el campo de noviembre.
    fuente.demora = 0.3
    a = abrir(mundo, mundo.ids.oct)
    visto = {}

    async def principal():
        hilo = asyncio.create_task(tocar_buscar(mundo)())
        await asyncio.sleep(0.05)
        clic(a, "Cancelar")
        n = abrir(mundo, mundo.ids.nov)
        await hilo
        visto["n"] = (campo(n).value, origen(n))

    asyncio.run(principal())
    assert visto["n"] in ((None, None), ("", None))
    assert cot(mundo, mundo.ids.nov) is None


def test_guardar_se_puede_tocar_otra_vez_tras_terminar(mundo, fuente):
    fuente.demora = 0.1
    d = abrir(mundo, mundo.ids.oct)
    con_demora(mundo, 0.1, _nada)
    clic(d, "Guardar")
    assert cot(mundo, mundo.ids.oct) == 163050
    assert d.open is False


def test_dialogo_cerrado_con_guardar_no_deja_busquedas_pendientes_que_escriban(
    mundo, fuente
):
    # Guardar está deshabilitado buscando, pero si el handler se llamara igual no guarda:
    # nada que descartar. Se verifica que no haya diálogo abierto tras Cancelar y espera.
    fuente.demora = 0.1
    d = abrir(mundo, mundo.ids.nov)

    async def durante():
        clic(d, "Cancelar")

    con_demora(mundo, 0.1, durante)
    assert cot(mundo, mundo.ids.nov) is None


# ---------------------------------------------------------------------------
# Privacidad (RN-81, CA-62.7)
# ---------------------------------------------------------------------------


def test_ca_62_7_un_solo_pedido_a_la_url_correcta(mundo, fuente):
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert fuente.pedidos == [("https://dolarapi.com/v1/dolares/blue", 10)]
    assert "?" not in fuente.pedidos[0][0]
    assert d.open is True


def test_ca_62_7_el_pedido_es_igual_con_mas_datos_cargados(mundo, fuente):
    sin_datos = None
    abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    sin_datos = list(fuente.pedidos)
    mundo.cerrar_dialogo(dialogo_arriba(mundo))
    catalogos.crear(mundo.con, catalogos.PERSONAS, "Sofía")
    otros = id_por_nombre(mundo.con, catalogos.CATEGORIAS, "Otros")
    gastos.agregar_gasto(
        mundo.con, mundo.ids.oct, "Nada secreto inventado", otros, 12345, "fijo"
    )
    fuente.pedidos.clear()
    abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert fuente.pedidos == sin_datos


def test_el_pedido_real_de_la_interfaz_es_un_get_sin_datos(mundo, monkeypatch):
    # Sin fuente falsa de pedir(): se reemplaza urlopen y se inspecciona el Request real.
    import urllib.request

    monkeypatch.undo()  # saca fuente y hoy_fijo (se vuelve a fijar el mes actual abajo)
    monkeypatch.setattr(meses, "mes_actual_calendario", lambda hoy=None: (2026, 10))
    vistos = []

    class Resp:
        status = 200

        def read(self):
            return cuerpo()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(pedido, *args, **kwargs):
        vistos.append(pedido)
        return Resp()

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    d = abrir(mundo, mundo.ids.oct)
    buscar_y_esperar(mundo)
    assert len(vistos) == 1
    assert vistos[0].full_url == "https://dolarapi.com/v1/dolares/blue"
    assert vistos[0].get_method() == "GET"
    assert vistos[0].data is None
    assert campo(d).value == "1.630,50"


# ---------------------------------------------------------------------------
# Compatibilidad: el diálogo de la cotización de siempre (CA-25.x)
# ---------------------------------------------------------------------------


def test_los_cuatro_dialogos_de_valores_siguen_igual(mundo):
    # Sueldo y meta usan el mismo armado: no tienen botón ni ruedita.
    mundo.editar_cotizacion()  # abre cotización
    mundo.cerrar_dialogo(dialogo_arriba(mundo))
    from app.interfaz.dialogos import dialogos_valores

    dialogos_valores.abrir_sueldo(mundo, mundo.ids.oct)
    d = dialogo_arriba(mundo)
    assert not hay_busqueda(d)
    assert de_tipo(d, ft.ProgressRing) == []
    campo(d).value = "1.300"
    clic(d, "Guardar")
    assert meses.obtener_mes(mundo.con, mundo.ids.oct)["sueldo_usd_cent"] == 130000


def test_guardar_invalido_con_boton_presente_sigue_mostrando_el_error(mundo):
    d = abrir(mundo, mundo.ids.oct)
    campo(d).value = "0"
    clic(d, "Guardar")
    assert campo(d).error == "La cotización tiene que ser mayor a 0."
    assert d.open is True


def test_enter_guarda_en_reposo_con_el_boton_presente(mundo):
    d = abrir(mundo, mundo.ids.oct)
    campo(d).value = "1.650"
    campo(d).on_submit(None)
    assert cot(mundo, mundo.ids.oct) == 165000


def test_aviso_de_gastos_en_dolares_se_mantiene_con_el_boton(mundo):
    otros = id_por_nombre(mundo.con, catalogos.CATEGORIAS, "Otros")
    gastos.agregar_gasto(
        mundo.con, mundo.ids.oct, "Sub", otros, None, "fijo", None, "USD", 2000, 160000
    )
    d = abrir(mundo, mundo.ids.oct)
    assert (
        "Este mes tiene 1 gasto en dólares. Si querés actualizarlos, editalos uno por uno."
        in textos(d)
    )
    assert hay_busqueda(d)


def test_hay_boton_guardar_y_cancelar_donde_se_espera(mundo):
    # La interfaz toma el botón Guardar de actions[1].controls[1] (dialogo_formulario).
    d = abrir(mundo, mundo.ids.oct)
    assert d.actions[1].controls[1] is boton(d, "Guardar")
    assert hay_boton(d, "Cancelar")


def test_la_ruedita_tiene_etiqueta_de_accesibilidad(mundo):
    # §3.6: ProgressRing(..., semantics_label="Buscando la cotización") para lectores de pantalla.
    assert (
        ruedita(abrir(mundo, mundo.ids.oct)).semantics_label == "Buscando la cotización"
    )
