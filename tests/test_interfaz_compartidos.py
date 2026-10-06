"""Pruebas de la interfaz del paso 5: sección "Compartido" del diálogo de gasto, ícono y
texto al borrar en Gastos, pantalla Me deben, diálogo de ítem, pestaña Personas,
tarjeta "Te deben" y textos de crear/borrar mes (diseno.md §3.2, §3.3, §3.5, §3.9,
§3.10, §4.1, §4.8; CA-28.x a CA-35.2, CA-05.2, CA-43.6, CA-45.7, CA-47.8; O40 y O41).
Página falsa, sin ventanas; "hoy" fijo en 04/10/2026."""

from datetime import date, datetime

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.interfaz.dialogos import dialogo_item
from app.logica import catalogos, compartidos, gastos, me_deben, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_mes_corto
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    boton,
    celda,
    clic,
    de_tipo,
    dialogo_arriba,
    dialogo_gasto_abierto,
    hay_boton,
    ir,
    item_menu,
    nombre_visible,
    recorrer,
    tecla,
    textos,
    titulo_dialogo,
)

HOY = date(2026, 10, 4)
PENDIENTE = "#9A5800"
NEGATIVO = "#B3261E"
POSITIVO = "#1E7B34"
SECUNDARIO = "onSurfaceVariant"


class FechaFija(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 4)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    original = meses.mes_actual_calendario
    monkeypatch.setattr(
        meses,
        "mes_actual_calendario",
        lambda hoy=None: (2026, 10) if hoy is None else original(hoy),
    )
    monkeypatch.setattr(dialogo_item, "date", FechaFija)
    monkeypatch.setattr(me_deben, "date", FechaFija)


@pytest.fixture
def oct_(con):
    return meses.crear_primer_mes(con, 2026, 10, 120000, 160000)


@pytest.fixture
def sofia(con):
    return catalogos.crear(con, catalogos.PERSONAS, "Sofía")


@pytest.fixture
def marsu(con):
    return catalogos.crear(con, catalogos.PERSONAS, "Marsu")


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


def _app(con, pantalla="Gastos"):
    app = Aplicacion(PaginaFalsa(), con)
    app.iniciar()
    ir(app, pantalla)
    return app


def _internet(con, mes_id, partes):
    return gastos.agregar_gasto(
        con, mes_id, "Internet", _otros(con), 3870000, "fijo", partes=partes
    )


def _parte_id(con, gasto_id, persona_id):
    return con.execute(
        "SELECT id FROM partes_gasto WHERE gasto_id = ? AND persona_id = ?",
        (gasto_id, persona_id),
    ).fetchone()["id"]


def _seccion(app):
    return dialogo_gasto_abierto(app).compartido


def _nuevo_gasto(app, nombre="Internet", monto="38.700"):
    app.pantalla("Gastos").nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = nombre
    d.categoria.value = str(_otros(app.con))
    d.monto.value = monto
    return d


def _activar(seccion, *personas):
    seccion.interruptor.value = True
    seccion.interruptor.on_change(None)
    for pid in personas:
        seccion.tildes[pid].value = True
        seccion.tildes[pid].on_change(None)


def _valores(seccion):
    return {
        seccion.nombres[pid]: seccion.campos[pid].value for pid in seccion._elegidas()
    }


def _escribir_parte(seccion, persona_id, texto):
    seccion.campos[persona_id].value = texto
    seccion.campos[persona_id].on_change(None)


def _avisos(seccion):
    return [t.value for t in seccion.avisos.controls]


# ---------------------------------------------------------------------------
# O41 en la lógica, formatear_mes_corto y personas_compartido
# ---------------------------------------------------------------------------


def test_o41_marcar_devuelve_el_estado_anterior_y_restaurar_lo_repone(
    con, oct_, sofia, marsu
):
    gid = _internet(con, oct_, [(sofia, None), (marsu, None)])
    pid = _parte_id(con, gid, sofia)
    compartidos.marcar_cobrada(con, pid, True)
    gastos.editar_gasto(
        con, gid, "Internet", _otros(con), 3000000, "fijo"
    )  # a devolver 2.900
    assert me_deben.total_de(con, sofia) == -290000
    previo = compartidos.marcar_cobrada(con, pid, True)
    assert previo == (False, 1290000)
    assert me_deben.total_de(con, sofia) == 0
    compartidos.restaurar_cobro(con, pid, *previo)
    fila = con.execute(
        "SELECT cobrado, cobrado_cent FROM partes_gasto WHERE id = ?", (pid,)
    ).fetchone()
    assert tuple(fila) == (0, 1290000)
    assert me_deben.total_de(con, sofia) == -290000  # "a devolver $ 2.900" de nuevo


def test_o41_desmarcar_a_mano_sigue_dejando_lo_cobrado_en_cero(con, oct_, sofia):
    gid = _internet(con, oct_, [(sofia, None)])
    pid = _parte_id(con, gid, sofia)
    compartidos.marcar_cobrada(con, pid, True)
    assert compartidos.marcar_cobrada(con, pid, False) == (True, 1935000)
    fila = con.execute(
        "SELECT cobrado, cobrado_cent FROM partes_gasto WHERE id = ?", (pid,)
    ).fetchone()
    assert tuple(fila) == (0, 0)


@pytest.mark.parametrize("cobrado_cent", [-1, 1.5, None])
def test_o41_restaurar_con_valores_invalidos(con, oct_, sofia, cobrado_cent):
    gid = _internet(con, oct_, [(sofia, None)])
    with pytest.raises(ErrorDeValidacion):
        compartidos.restaurar_cobro(con, _parte_id(con, gid, sofia), True, cobrado_cent)


def test_o41_restaurar_una_parte_inexistente(con):
    with pytest.raises(ErrorDeValidacion, match="^Esa parte ya no existe.$"):
        compartidos.restaurar_cobro(con, 999, True, 100)


@pytest.mark.parametrize(
    ("anio", "mes", "texto"),
    [(2026, 10, "oct 2026"), (2027, 1, "ene 2027"), (2026, 12, "dic 2026")],
)
def test_formatear_mes_corto(anio, mes, texto):
    assert formatear_mes_corto(anio, mes) == texto


@pytest.mark.parametrize("mes", [0, 13])
def test_formatear_mes_corto_mes_invalido(mes):
    with pytest.raises(ValueError):
        formatear_mes_corto(2026, mes)


def test_listar_gastos_trae_personas_compartido(con, oct_, sofia, marsu):
    _internet(con, oct_, [(sofia, None), (marsu, None)])
    gastos.agregar_gasto(con, oct_, "Nafta", _otros(con), 100, "unico")
    assert {
        g["nombre"]: g["personas_compartido"] for g in gastos.listar_gastos(con, oct_)
    } == {
        "Internet": 2,
        "Nafta": 0,
    }


# ---------------------------------------------------------------------------
# Pestaña Personas (§3.10, CA-28.x)
# ---------------------------------------------------------------------------


def _personas(app):
    ajustes = ir(app, "Ajustes")
    return ajustes.listas[2]


def test_pestana_personas_vacia(con, oct_):
    app = _app(con)
    lista = _personas(app)
    assert textos(lista.lista) == [
        "No hay personas. Agregá a las personas con las que compartís gastos."
    ]
    assert lista.mostrar_archivados.label == "Mostrar archivadas"
    assert hay_boton(lista.control, "Nueva persona")


def test_ca_28_1_crear_renombrar_y_eliminar_persona(con, oct_):
    app = _app(con)
    lista = _personas(app)
    lista.nuevo()
    dialogo = dialogo_arriba(app)
    assert titulo_dialogo(dialogo) == "Nueva persona"
    dialogo.content.controls[0].value = "Sofía"
    clic(dialogo, "Guardar")
    assert [t.title.value for t in lista.lista.controls] == ["Sofía"]
    [tile] = lista.lista.controls
    clic(tile, "Eliminar")
    assert titulo_dialogo(dialogo_arriba(app)) == "¿Eliminar a la persona Sofía?"
    clic(dialogo_arriba(app), "Eliminar")
    assert catalogos.listar(con, catalogos.PERSONAS, incluir_archivados=True) == []


def test_ca_28_1_persona_en_uso_se_archiva(con, oct_, sofia):
    me_deben.agregar_item(con, sofia, "Préstamo", 100, HOY)
    app = _app(con)
    lista = _personas(app)
    [tile] = lista.lista.controls
    archivar = boton(tile, "Archivar")
    assert archivar.tooltip == (
        "Tiene gastos compartidos o ítems en Me deben: no se puede borrar. "
        "Archivada no aparece al compartir gastos nuevos."
    )
    archivar.on_click(None)
    assert catalogos.obtener(con, catalogos.PERSONAS, sofia)["archivado"] == 1
    lista.mostrar_archivados.value = True
    lista.refrescar()
    assert lista.lista.controls[0].subtitle.value == "Archivada"


def test_ctrl_n_en_la_pestana_personas(con, oct_):
    app = _app(con)
    ajustes = ir(app, "Ajustes")
    ajustes.pestanas.selected_index = 2
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Nueva persona"


# ---------------------------------------------------------------------------
# Sección "Compartido" del diálogo de gasto (§4.1, CA-29.x, CA-30.x, CA-31.x)
# ---------------------------------------------------------------------------


def test_sin_personas_el_interruptor_esta_deshabilitado(con, oct_):
    app = _app(con)
    _nuevo_gasto(app)
    seccion = _seccion(app)
    assert seccion.interruptor.label == "Compartido"
    assert seccion.interruptor.disabled is True
    assert "Agregá personas en Ajustes → Personas para compartir gastos." in textos(
        seccion.control
    )
    assert seccion.leer() == []


def test_ca_29_1_internet_entre_tres_desde_el_dialogo(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app)
    seccion = d.compartido
    assert (seccion.interruptor.value, seccion.detalle.visible) == (False, False)
    _activar(seccion, sofia, marsu)
    assert seccion.detalle.visible is True
    assert _valores(seccion) == {"Sofía": "12.900", "Marsu": "12.900"}
    assert seccion.tu_parte.value == "Tu parte: $ 12.900"
    campo = seccion.campos[sofia]
    assert (campo.width, campo.dense, campo.prefix) == (180, True, "$ ")
    d._guardar()
    assert app.page.avisos()[-1] == 'Gasto "Internet" agregado'
    gid = gastos.listar_gastos(con, oct_)[0]["id"]
    partes = {
        p["persona"]: p["monto_cent"] for p in compartidos.obtener_partes(con, gid)
    }
    assert partes == {"Sofía": 1290000, "Marsu": 1290000}
    # CA-29.4: el total cuenta los 38.700 completos; la fila muestra el ícono.
    pantalla = app.pantalla("Gastos")
    icono = de_tipo(celda(pantalla, "Internet", "Nombre").content, ft.Icon)[0]
    assert (
        (icono.icon, icono.size, icono.tooltip)
        == (
            ft.Icons.PEOPLE,
            16,
            "Compartido con Marsu y Sofía",  # en orden alfabético (como la lista de personas)
        )
    )


def test_gasto_no_compartido_no_tiene_icono(con, oct_):
    gastos.agregar_gasto(con, oct_, "Nafta", _otros(con), 100, "unico")
    app = _app(con)
    assert isinstance(celda(app.pantalla("Gastos"), "Nafta", "Nombre").content, ft.Text)


def test_ca_29_2_y_29_3(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app, "Edenor", "66.281")
    _activar(d.compartido, sofia, marsu)
    assert _valores(d.compartido) == {"Sofía": "22.093,66", "Marsu": "22.093,66"}
    assert d.compartido.tu_parte.value == "Tu parte: $ 22.094"
    d.compartido.tildes[marsu].value = False
    d.compartido.tildes[marsu].on_change(None)
    d.monto.value = "38.700"
    d.monto.on_change(None)
    assert _valores(d.compartido) == {"Sofía": "19.350"}  # CA-29.3


def test_ca_30_1_parte_manual_y_repartir(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app)
    seccion = d.compartido
    _activar(seccion, sofia, marsu)
    _escribir_parte(seccion, sofia, "15.000")
    assert seccion.tu_parte.value == "Tu parte: $ 10.800"
    etiquetas = {
        fila.controls[0].value: fila.controls[2].visible
        for fila in seccion.filas.controls
    }
    assert etiquetas == {"Sofía": True, "Marsu": False}
    assert seccion.filas.controls[0].controls[2].value == "manual"
    clic(seccion.control, "Repartir en partes iguales")
    assert _valores(seccion) == {"Sofía": "12.900", "Marsu": "12.900"}
    assert not any(f.controls[2].visible for f in seccion.filas.controls)


def test_ca_30_2_partes_que_superan_el_monto(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app)
    seccion = d.compartido
    _activar(seccion, sofia, marsu)
    _escribir_parte(seccion, sofia, "30.000")
    assert seccion.tu_parte.value == "Tu parte: -$ 4.200"
    assert (seccion.error.visible, seccion.error.value) == (
        True,
        "Las partes suman $ 42.900 y superan el monto ($ 38.700).",
    )
    d._guardar()
    assert d.dialogo.open is True
    assert (
        seccion.error.value
        == "Las partes suman $ 42.900 y superan el monto ($ 38.700)."
    )
    assert gastos.listar_gastos(con, oct_) == []


def test_ca_31_1_al_cambiar_el_monto_se_recalculan_las_partes(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app)
    _activar(d.compartido, sofia, marsu)
    d.monto.value = "45.000"
    d.monto.on_change(None)
    assert _valores(d.compartido) == {"Sofía": "15.000", "Marsu": "15.000"}
    d.monto.value = "abc"
    d.monto.on_change(None)
    assert d.compartido.tu_parte.value == "Tu parte: —"


def test_compartido_sin_personas_elegidas_se_rechaza(con, oct_, sofia):
    app = _app(con)
    d = _nuevo_gasto(app)
    _activar(d.compartido)
    d._guardar()
    assert (
        d.compartido.error.value == "Elegí al menos una persona o desactivá Compartido."
    )
    assert d.dialogo.open is True


def test_parte_manual_invalida(con, oct_, sofia):
    app = _app(con)
    d = _nuevo_gasto(app)
    _activar(d.compartido, sofia)
    _escribir_parte(d.compartido, sofia, "abc")
    assert d.compartido.tu_parte.value == "Tu parte: —"
    d._guardar()
    assert d.compartido.campos[sofia].error == "Escribí solo números. Ej.: 66.020,12"
    assert d.compartido.error.value == "Revisá la parte de Sofía."
    assert gastos.listar_gastos(con, oct_) == []


def test_parte_manual_en_cero(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app)
    _activar(d.compartido, sofia, marsu)
    _escribir_parte(d.compartido, sofia, "0")
    d._guardar()
    gid = gastos.listar_gastos(con, oct_)[0]["id"]
    assert {
        p["persona"]: p["monto_cent"] for p in compartidos.obtener_partes(con, gid)
    } == {
        "Sofía": 0,
        "Marsu": 1290000,
    }


def test_edicion_precarga_lo_compartido(con, oct_, sofia, marsu):
    gid = _internet(con, oct_, [(sofia, 1500000), (marsu, None)])
    app = _app(con)
    app.pantalla("Gastos").editar(gid)
    seccion = _seccion(app)
    assert (seccion.interruptor.value, seccion.detalle.visible) == (True, True)
    assert (seccion.tildes[sofia].value, seccion.tildes[marsu].value) == (True, True)
    assert _valores(seccion) == {"Sofía": "15.000", "Marsu": "12.900"}
    assert seccion.manual == {sofia: True, marsu: False}
    assert seccion.tu_parte.value == "Tu parte: $ 10.800"


def test_ca_31_2_editar_el_monto_mantiene_la_manual(con, oct_, sofia, marsu):
    gid = _internet(con, oct_, [(sofia, 1500000), (marsu, None)])
    app = _app(con)
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    d.monto.value = "30.000"
    d.monto.on_change(None)
    assert _valores(d.compartido) == {"Sofía": "15.000", "Marsu": "10.000"}
    assert d.compartido.tu_parte.value == "Tu parte: $ 5.000"
    d._guardar()
    assert {
        p["persona"]: p["monto_cent"] for p in compartidos.obtener_partes(con, gid)
    } == {
        "Sofía": 1500000,
        "Marsu": 1000000,
    }


def test_dejar_de_compartir_desde_el_dialogo(con, oct_, sofia):
    gid = _internet(con, oct_, [(sofia, None)])
    app = _app(con)
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    d.compartido.interruptor.value = False
    d.compartido.interruptor.on_change(None)
    assert d.compartido.detalle.visible is False
    d._guardar()
    assert compartidos.obtener_partes(con, gid) == []


@pytest.mark.parametrize(
    ("monto", "aviso"),
    [
        (
            "45.000",
            "La parte de Sofía ya estaba cobrada ($ 12.900). Va a quedar pendiente: falta $ 2.100.",
        ),
        (
            "30.000",
            "La parte de Sofía ya estaba cobrada ($ 12.900). Va a quedar pendiente: a devolver $ 2.900.",
        ),
    ],
)
def test_ca_31_4_y_31_5_aviso_de_parte_cobrada(con, oct_, sofia, marsu, monto, aviso):
    gid = _internet(con, oct_, [(sofia, None), (marsu, None)])
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    app = _app(con)
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    assert _avisos(d.compartido) == []
    d.monto.value = monto
    d.monto.on_change(None)
    assert _avisos(d.compartido) == [aviso]
    assert d.compartido.avisos.controls[0].color == PENDIENTE
    d._guardar()
    fila = compartidos.obtener_partes(con, gid)[0]
    assert (fila["cobrado"], fila["cobrado_cent"]) == (0, 1290000)


def test_o40_aviso_al_sacar_a_una_persona_que_ya_pago(con, oct_, sofia, marsu):
    gid = _internet(con, oct_, [(sofia, None), (marsu, None)])
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    app = _app(con)
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    d.compartido.tildes[sofia].value = False
    d.compartido.tildes[sofia].on_change(None)
    o40 = (
        "La parte de Sofía ya estaba cobrada ($ 12.900). Si la sacás, ese cobro deja de "
        'figurar en "Me deben".'
    )
    assert _avisos(d.compartido) == [o40]
    # También al apagar "Compartido".
    d.compartido.tildes[sofia].value = True
    d.compartido.tildes[sofia].on_change(None)
    assert _avisos(d.compartido) == []
    d.compartido.interruptor.value = False
    d.compartido.interruptor.on_change(None)
    assert _avisos(d.compartido) == [o40]
    # El aviso no bloquea: se puede guardar.
    d.compartido.interruptor.value = True
    d.compartido.interruptor.on_change(None)
    d.compartido.tildes[sofia].value = False
    d.compartido.tildes[sofia].on_change(None)
    d._guardar()
    assert d.dialogo.open is False
    assert [p["persona"] for p in compartidos.obtener_partes(con, gid)] == ["Marsu"]


def test_persona_archivada_en_el_dialogo(con, oct_, sofia, marsu):
    gid = _internet(con, oct_, [(sofia, None)])
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    app = _app(con)
    app.pantalla("Gastos").editar(gid)
    assert _seccion(app).tildes[sofia].label == "Sofía (archivada)"
    app.cerrar_dialogo(dialogo_arriba(app))
    app.pantalla("Gastos").nuevo()
    assert sofia not in _seccion(app).tildes  # en un alta no se ofrece


def test_error_de_la_logica_va_a_la_seccion(con, oct_, sofia):
    app = _app(con)
    d = _nuevo_gasto(app)
    _activar(d.compartido, sofia)
    me_deben.agregar_item(con, sofia, "X", 100, HOY)
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)  # se archiva por detrás
    d._guardar()
    assert (
        d.compartido.error.value
        == "La persona Sofía está archivada: desarchivala para compartir gastos."
    )
    assert d.dialogo.open is True


def test_ca_43_6_y_45_7_gasto_en_dolares_compartido(con, oct_, sofia, marsu):
    app = _app(con)
    d = _nuevo_gasto(app, "Netflix", "")
    d.moneda.selected = ["USD"]
    d.moneda.on_change(None)
    d.monto_usd.value = "15"
    d.monto_usd.on_change(None)
    _activar(d.compartido, sofia, marsu)
    assert _valores(d.compartido) == {"Sofía": "8.000", "Marsu": "8.000"}  # CA-43.6
    d._guardar()
    gid = gastos.listar_gastos(con, oct_)[0]["id"]
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    # CA-45.7: cotización del gasto a 1.700 → partes 8.500; Sofía cobrada → aviso.
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    d.cotizacion.value = "1.700"
    d.cotizacion.on_change(None)
    assert _valores(d.compartido) == {"Sofía": "8.500", "Marsu": "8.500"}
    assert _avisos(d.compartido) == [
        "La parte de Sofía ya estaba cobrada ($ 8.000). Va a quedar pendiente: falta $ 500."
    ]
    d._guardar()
    assert me_deben.total_de(con, sofia) == 50000


def test_borrar_un_gasto_compartido_avisa_las_partes(con, oct_, sofia, marsu):
    _internet(con, oct_, [(sofia, None), (marsu, None)])
    app = _app(con)
    item_menu(app.pantalla("Gastos"), "Internet", "Borrar").on_click(None)
    assert dialogo_arriba(app).content.value == (
        "Se borran también sus pagos ($ 0 pagado). También desaparecen las partes de Sofía "
        'y Marsu de "Me deben". Esta acción no se puede deshacer.'
    )


# ---------------------------------------------------------------------------
# Pantalla Me deben (§3.5, CA-32.x a CA-34.x)
# ---------------------------------------------------------------------------


def _tarjeta(app, nombre):
    pantalla = app.pantalla("Me deben")
    for card in de_tipo(pantalla.cuerpo, ft.Card):
        if nombre in textos(card):
            return card
    raise AssertionError(nombre)


def _lineas(card):
    return [t for t in recorrer(card) if isinstance(t, ft.ListTile)]


def _linea(card, descripcion):
    for tile in _lineas(card):
        if tile.title.value == descripcion:
            return tile
    raise AssertionError(descripcion)


def _tildar(tile, valor):
    tile.leading.value = valor
    tile.leading.on_change(type("E", (), {"control": tile.leading})())


@pytest.fixture
def caso_33(con, oct_, sofia, marsu):
    """Sofía con Internet 12.900 (oct 2026) y Préstamo MP 20.000 (CA-33.1)."""
    gid = _internet(con, oct_, [(sofia, None), (marsu, None)])
    item = me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    return gid, item


def test_me_deben_sin_personas(con, oct_):
    app = _app(con, "Me deben")
    pantalla = app.pantalla("Me deben")
    assert "Agregá a las personas con las que compartís gastos." in textos(
        pantalla.cuerpo
    )
    assert pantalla.total.value == "Total: $ 0"
    clic(pantalla.cuerpo, "Ir a Personas")
    assert nombre_visible(app) == "Ajustes"
    assert app.pantalla("Ajustes").pestanas.selected_index == 2


def test_ca_33_1_tarjeta_de_sofia(con, caso_33):
    app = _app(con, "Me deben")
    pantalla = app.pantalla("Me deben")
    assert pantalla.total.value == "Total: $ 45.800"  # Sofía 32.900 + Marsu 12.900
    assert "Acumulado de todos los meses." in textos(pantalla.control)
    card = _tarjeta(app, "Sofía")
    assert card.col == {"md": 6, "xl": 4}
    assert de_tipo(card, ft.CircleAvatar)[0].content.value == "S"
    assert "$ 32.900" in textos(card)
    internet = _linea(card, "Internet")
    assert textos(internet.subtitle) == ["Gasto de oct 2026"]
    assert textos(internet.trailing) == ["$ 12.900"]
    assert (
        de_tipo(internet.trailing, ft.PopupMenuButton) == []
    )  # las partes no tienen menú
    prestamo = _linea(card, "Préstamo MP")
    assert textos(prestamo.subtitle) == ["A mano · 04/10/2026"]
    menu = de_tipo(prestamo.trailing, ft.PopupMenuButton)[0]
    assert [i.content for i in menu.items] == ["Editar", "Borrar"]
    assert internet.leading.tooltip == "Marcar como cobrado"


def test_ca_34_1_tildar_y_deshacer_un_item(con, caso_33, sofia):
    app = _app(con, "Me deben")
    _tildar(_linea(_tarjeta(app, "Sofía"), "Préstamo MP"), True)
    aviso = app.page.ultimo_aviso()
    assert (aviso.content.value, aviso.action) == ("Marcado como cobrado", "Deshacer")
    assert me_deben.total_de(con, sofia) == 1290000
    assert [t.title.value for t in _lineas(_tarjeta(app, "Sofía"))] == ["Internet"]
    pantalla = app.pantalla("Me deben")
    pantalla.mostrar_cobrados.value = True
    pantalla.mostrar_cobrados.on_change(None)
    prestamo = _linea(_tarjeta(app, "Sofía"), "Préstamo MP")
    assert prestamo.leading.value is True
    assert prestamo.title.color == SECUNDARIO
    cobrado = [t for t in de_tipo(prestamo.subtitle, ft.Text) if t.value == "Cobrado"]
    assert cobrado[0].color == POSITIVO
    aviso.on_action(None)  # Deshacer
    assert me_deben.total_de(con, sofia) == 3290000


def test_ca_34_2_marcar_no_cambia_el_resumen(con, caso_33, oct_):
    from app.logica.resumen import calcular_resumen

    antes = calcular_resumen(con, oct_)
    app = _app(con, "Me deben")
    _tildar(_linea(_tarjeta(app, "Sofía"), "Internet"), True)
    despues = calcular_resumen(con, oct_)
    assert (
        despues.total_gastos,
        despues.pesos_a_cubrir,
        despues.usd_a_cambiar,
        despues.ahorro_usd,
    ) == (
        antes.total_gastos,
        antes.pesos_a_cubrir,
        antes.usd_a_cambiar,
        antes.ahorro_usd,
    )


@pytest.mark.parametrize(
    ("monto", "texto", "color", "total"),
    [
        (4500000, "Cobrado $ 12.900 · falta $ 2.100", PENDIENTE, "$ 22.100"),
        (3000000, "Cobrado $ 12.900 · a devolver $ 2.900", NEGATIVO, "$ 17.100"),
    ],
)
def test_ca_31_4_y_31_5_diferencia_en_la_linea(
    con, caso_33, sofia, monto, texto, color, total
):
    gid, _ = caso_33
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    gastos.editar_gasto(con, gid, "Internet", _otros(con), monto, "fijo")
    app = _app(con, "Me deben")
    card = _tarjeta(app, "Sofía")
    linea = _linea(card, "Internet")
    [diferencia] = [
        t for t in de_tipo(linea.subtitle, ft.Text) if t.value.startswith("Cobrado ")
    ]
    assert (diferencia.value, diferencia.color) == (texto, color)
    assert total in textos(card)


def test_o41_deshacer_vuelve_a_a_devolver(con, caso_33, sofia):
    gid, item = caso_33
    me_deben.borrar_item(con, item)
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    gastos.editar_gasto(
        con, gid, "Internet", _otros(con), 3000000, "fijo"
    )  # a devolver 2.900
    app = _app(con, "Me deben")
    _tildar(_linea(_tarjeta(app, "Sofía"), "Internet"), True)
    assert me_deben.total_de(con, sofia) == 0
    app.page.ultimo_aviso().on_action(None)  # Deshacer
    assert me_deben.total_de(con, sofia) == -290000
    card = _tarjeta(app, "Sofía")
    assert "Cobrado $ 12.900 · a devolver $ 2.900" in textos(card)
    total = next(t for t in de_tipo(card, ft.Text) if t.value == "-$ 2.900")
    assert total.color == NEGATIVO
    assert "Le tenés que devolver" in textos(card)


def test_o41_deshacer_un_desmarcado(con, caso_33, sofia):
    gid, _ = caso_33
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    app = _app(con, "Me deben")
    pantalla = app.pantalla("Me deben")
    pantalla.mostrar_cobrados.value = True
    pantalla.mostrar_cobrados.on_change(None)
    _tildar(_linea(_tarjeta(app, "Sofía"), "Internet"), False)
    assert app.page.avisos()[-1] == "Marcado como pendiente"
    fila = con.execute(
        "SELECT cobrado, cobrado_cent FROM partes_gasto WHERE id = ?",
        (_parte_id(con, gid, sofia),),
    ).fetchone()
    assert tuple(fila) == (0, 0)  # desmarcar a mano deja lo cobrado en 0
    app.page.ultimo_aviso().on_action(None)
    fila = con.execute(
        "SELECT cobrado, cobrado_cent FROM partes_gasto WHERE id = ?",
        (_parte_id(con, gid, sofia),),
    ).fetchone()
    assert tuple(fila) == (1, 1290000)


def test_persona_sin_deudas(con, oct_, sofia):
    app = _app(con, "Me deben")
    card = _tarjeta(app, "Sofía")
    assert "Sofía no te debe nada." in textos(card)
    icono = de_tipo(card, ft.Icon)[0]
    assert (icono.icon, icono.color) == (ft.Icons.CHECK_CIRCLE, POSITIVO)
    assert "$ 0" in textos(card)


def test_persona_archivada_con_pendientes(con, caso_33, sofia):
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    app = _app(con, "Me deben")
    assert "Archivada" in textos(_tarjeta(app, "Sofía"))


def test_ca_33_2_internet_de_dos_meses(con, caso_33, sofia):
    meses.crear_mes_siguiente(con, 120000, 160000)
    app = _app(con, "Me deben")
    card = _tarjeta(app, "Sofía")
    origenes = [textos(t.subtitle)[0] for t in _lineas(card)]
    assert origenes == ["Gasto de oct 2026", "Gasto de nov 2026", "A mano · 04/10/2026"]
    assert "$ 45.800" in textos(card)


# ---------------------------------------------------------------------------
# Diálogo de ítem (§4.8, CA-32.x)
# ---------------------------------------------------------------------------


def _dialogo_item(app):
    return boton(dialogo_arriba(app), "Guardar").on_click.__self__


def test_ca_32_1_agregar_item_desde_la_tarjeta(con, oct_, sofia):
    app = _app(con, "Me deben")
    clic(_tarjeta(app, "Sofía"), "Agregar ítem")
    d = _dialogo_item(app)
    assert titulo_dialogo(d.dialogo) == "Nuevo ítem de Me deben"
    assert (d.persona.value, d.texto_fecha.value, d.descripcion.autofocus) == (
        str(sofia),
        "04/10/2026",
        True,
    )
    d.descripcion.value = "Préstamo MP"
    d.monto.value = "20.000"
    d._guardar()
    assert app.page.avisos()[-1] == "Ítem agregado"
    trailing = _linea(_tarjeta(app, "Sofía"), "Préstamo MP").trailing
    assert [t.value for t in de_tipo(trailing, ft.Text)] == ["$ 20.000"]


@pytest.mark.parametrize(
    ("descripcion", "monto", "campo", "mensaje"),
    [
        ("", "20.000", "descripcion", "Ingresá una descripción."),  # CA-32.2
        ("Préstamo", "0", "monto", "El monto tiene que ser mayor a 0."),  # CA-32.2
        ("Préstamo", "", "monto", "Ingresá un monto."),
    ],
)
def test_ca_32_2_errores_del_item(con, oct_, sofia, descripcion, monto, campo, mensaje):
    app = _app(con, "Me deben")
    app.pantalla("Me deben").nuevo_item(sofia)
    d = _dialogo_item(app)
    d.descripcion.value, d.monto.value = descripcion, monto
    d._guardar()
    assert getattr(d, campo).error == mensaje
    assert app.page.tareas[-1].__self__ is getattr(d, campo)
    assert me_deben.lineas_de(con, sofia) == []


def test_ctrl_n_en_me_deben_pide_la_persona(con, oct_, sofia):
    app = _app(con, "Me deben")
    app._al_presionar_tecla(tecla("N", ctrl=True))
    d = _dialogo_item(app)
    assert d.persona.value is None
    assert d.descripcion.autofocus is False
    d.descripcion.value, d.monto.value = "Préstamo", "100"
    d._guardar()
    assert d.persona.error_text == "Elegí una persona."
    assert app.page.tareas[-1].__self__ is d.persona


def test_editar_y_borrar_un_item(con, caso_33, sofia):
    _, item = caso_33
    app = _app(con, "Me deben")
    menu = de_tipo(
        _linea(_tarjeta(app, "Sofía"), "Préstamo MP").trailing, ft.PopupMenuButton
    )[0]
    menu.items[0].on_click(None)
    d = _dialogo_item(app)
    assert titulo_dialogo(d.dialogo) == "Editar ítem"
    assert (d.descripcion.value, d.monto.value, d.texto_fecha.value) == (
        "Préstamo MP",
        "20.000",
        "04/10/2026",
    )
    d.monto.value = "25.000"
    d._guardar()
    assert app.page.avisos()[-1] == "Ítem actualizado"
    assert me_deben.obtener_item(con, item)["monto_cent"] == 2500000
    menu = de_tipo(
        _linea(_tarjeta(app, "Sofía"), "Préstamo MP").trailing, ft.PopupMenuButton
    )[0]
    menu.items[1].on_click(None)
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Borrar el ítem Préstamo MP?"
    assert confirmacion.content.value == "$ 25.000. Esta acción no se puede deshacer."
    clic(confirmacion, "Borrar")
    assert app.page.avisos()[-1] == 'Ítem "Préstamo MP" borrado'
    assert me_deben.obtener_item(con, item) is None


def test_editar_item_de_persona_archivada(con, caso_33, sofia):
    _, item = caso_33
    catalogos.eliminar(con, catalogos.PERSONAS, sofia)
    app = _app(con, "Me deben")
    app.pantalla("Me deben").editar_item(item)
    d = _dialogo_item(app)
    assert "Sofía (archivada)" in [o.text for o in d.persona.options]
    d._guardar()
    assert app.page.avisos()[-1] == "Ítem actualizado"


def test_fecha_del_item_con_el_calendario(con, oct_, sofia):
    app = _app(con, "Me deben")
    app.pantalla("Me deben").nuevo_item(sofia)
    d = _dialogo_item(app)
    [boton_cal] = [
        b
        for b in de_tipo(d.dialogo, ft.IconButton)
        if b.icon == ft.Icons.CALENDAR_MONTH
    ]
    boton_cal.on_click(None)
    assert app._dialogos == [d.dialogo, d.calendario]
    d.calendario.value = datetime(2026, 9, 15, 20, 0)  # noqa: DTZ001
    d.calendario.on_change(None)
    assert d.texto_fecha.value == "15/09/2026"
    assert app._dialogos == [d.dialogo]  # el calendario se cerró (como O24)
    d.descripcion.value, d.monto.value = "Tacones", "6.785"
    d._guardar()
    assert me_deben.lineas_de(con, sofia)[0].fecha == "2026-09-15"


def test_editar_un_item_borrado_por_detras(con, caso_33):
    _, item = caso_33
    app = _app(con, "Me deben")
    me_deben.borrar_item(con, item)
    app.pantalla("Me deben").editar_item(item)
    assert app.hay_dialogo_abierto() is False
    assert app.page.avisos()[-1] == "Ese ítem ya no existe."


# ---------------------------------------------------------------------------
# Tarjeta "Te deben" del Resumen (§3.2, CA-35.2)
# ---------------------------------------------------------------------------


def _tarjeta_te_deben(app):
    resumen = app.pantalla("Resumen")
    for card in de_tipo(resumen.cuerpo, ft.Card):
        if "Te deben (todas las personas)" in textos(card):
            return card
    raise AssertionError("No hay tarjeta Te deben")


def test_te_deben_en_cero(con, oct_):
    app = _app(con, "Resumen")
    card = _tarjeta_te_deben(app)
    assert "$ 0" in textos(card)
    assert "Nadie te debe nada." in textos(card)


def test_ca_35_2_te_deben_es_el_mismo_en_todos_los_meses(con, oct_, sofia, marsu):
    _internet(con, oct_, [(sofia, None), (marsu, None)])
    me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    nov = meses.crear_mes_siguiente(con, 120000, 160000)
    app = _app(con, "Resumen")
    # 12.900 × 2 (octubre) + 12.900 × 2 (noviembre, copiado) + 20.000 = 71.600
    total = "$ 71.600"
    card = _tarjeta_te_deben(app)
    assert total in textos(card)
    assert "Acumulado de todos los meses." in textos(card)
    app.seleccionar_mes(nov)
    assert total in textos(_tarjeta_te_deben(app))
    clic(_tarjeta_te_deben(app), "Ver")
    assert nombre_visible(app) == "Me deben"
    assert app.pantalla("Me deben").total.value == f"Total: {total}"


def test_te_deben_negativo_en_rojo(con, oct_, sofia):
    gid = _internet(con, oct_, [(sofia, None)])
    compartidos.marcar_cobrada(con, _parte_id(con, gid, sofia), True)
    gastos.editar_gasto(
        con, gid, "Internet", _otros(con), 3000000, "fijo"
    )  # a devolver 4.350
    app = _app(con, "Resumen")
    monto = next(
        t for t in de_tipo(_tarjeta_te_deben(app), ft.Text) if t.value == "-$ 4.350"
    )
    assert monto.color == NEGATIVO


# ---------------------------------------------------------------------------
# Meses: borrar (CA-05.2) y crear con partes repartidas (CA-47.8)
# ---------------------------------------------------------------------------


def test_ca_05_2_borrar_el_mes_avisa_y_saca_las_partes(con, sofia, marsu):
    meses.crear_primer_mes(con, 2026, 9, 120000, 160000)
    oct_ = meses.crear_mes_siguiente(con, 120000, 160000)
    _internet(con, oct_, [(sofia, None), (marsu, None)])
    me_deben.agregar_item(con, sofia, "Préstamo MP", 2000000, HOY)
    app = _app(con, "Resumen")
    app._item_borrar_mes.on_click(None)
    texto = dialogo_arriba(app).content.value
    assert 'Las partes compartidas de este mes desaparecen de "Me deben". ' in texto
    clic(dialogo_arriba(app), "Borrar mes")
    ir(app, "Me deben")
    card = _tarjeta(app, "Sofía")
    assert [t.title.value for t in _lineas(card)] == ["Préstamo MP"]


def test_borrar_un_mes_sin_partes_no_lo_menciona(con, oct_):
    app = _app(con, "Resumen")
    app._item_borrar_mes.on_click(None)
    assert "Las partes compartidas" not in dialogo_arriba(app).content.value


def test_ca_47_8_aviso_al_crear_el_mes(con, oct_, sofia, marsu):
    gastos.agregar_gasto(
        con,
        oct_,
        "Netflix",
        _otros(con),
        None,
        "fijo",
        None,
        "USD",
        1500,
        160000,
        partes=[(sofia, 1200000), (marsu, 1000000)],
    )
    app = _app(con, "Resumen")
    app.crear_mes_nuevo()
    d = boton(dialogo_arriba(app), "Crear mes").on_click.__self__
    d.cotizacion.value = "1.400"
    clic(d.dialogo, "Crear mes")
    assert app.page.avisos()[-1] == (
        "Noviembre 2026 creado: 1 gasto fijo. "
        "Las partes de Netflix se repartieron en partes iguales porque cambió el monto."
    )
