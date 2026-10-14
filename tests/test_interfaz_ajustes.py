"""Pruebas de la pantalla Ajustes: categorías y medios de pago
(RF-10, RF-11, CA-10.x, CA-11.2 en pantalla; diseno.md §3.10, §4.7). Sin ventanas."""

import flet as ft
import pytest

from app.logica import catalogos, gastos
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    boton,
    clic,
    dialogo_arriba,
    hay_boton,
    ir,
    textos,
    titulo_dialogo,
)


@pytest.fixture
def ajustes(app):
    ir(app, "Ajustes")
    return app.pantalla("Ajustes")


@pytest.fixture
def categorias(ajustes):
    return ajustes.listas[0]


@pytest.fixture
def medios(ajustes):
    return ajustes.listas[1]


def _tiles(lista):
    return [c for c in lista.lista.controls if isinstance(c, ft.ListTile)]


def _tile(lista, nombre):
    for t in _tiles(lista):
        if t.title.value == nombre:
            return t
    raise AssertionError(f"No hay fila {nombre!r}")


def _nombres(lista):
    return [t.title.value for t in _tiles(lista)]


def _usar_en_gasto(app, con, tabla, nombre):
    """Crea un gasto que usa la categoría o el medio indicado (así queda "en uso")."""
    if tabla == catalogos.CATEGORIAS:
        cat = id_por_nombre(con, tabla, nombre)
        gastos.agregar_gasto(con, app.mes_id, "X", cat, 100, "fijo")
    else:
        otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
        medio = id_por_nombre(con, tabla, nombre)
        gastos.agregar_gasto(con, app.mes_id, "X", otros, 100, "fijo", medio)


def test_pestanas_y_titulo(ajustes):
    assert "Ajustes" in textos(ajustes.control)
    assert [t.label for t in ajustes.pestanas.content.controls[0].tabs] == [
        "Categorías",
        "Medios de pago",
        "Personas",
        "Meta de ahorro",
        "Apariencia",
        "Importar Excel",  # v2 (paso 8b, diseno.md §3.10): sexta pestaña, la última
    ]


def test_lista_de_categorias_ordenada_con_eliminar(categorias):
    # §3.10: lista ordenada por nombre; sin uso → "Renombrar" y "Eliminar".
    assert _nombres(categorias) == [
        "Deudas",
        "Mercado",
        "Otros",
        "Salud",
        "Servicios",
        "Transporte",
        "Vivienda",
    ]
    t = _tile(categorias, "Mercado")
    assert hay_boton(t, "Renombrar") and hay_boton(t, "Eliminar")
    assert not hay_boton(t, "Archivar")


def test_lista_de_medios(medios):
    assert _nombres(medios) == ["Efectivo", "Tarjeta de crédito", "Transferencia"]


@pytest.mark.parametrize("indice", [0, 1])
def test_en_uso_muestra_archivar_con_tooltip(app, con, ajustes, indice):
    # §3.10: si está en uso el botón dice "Archivar" (no "Eliminar").
    lista = ajustes.listas[indice]
    nombre = "Vivienda" if indice == 0 else "Efectivo"
    _usar_en_gasto(app, con, lista.tabla, nombre)
    lista.refrescar()
    t = _tile(lista, nombre)
    archivar = boton(t, "Archivar")
    assert not hay_boton(t, "Eliminar")
    assert archivar.tooltip.startswith("Se usa en gastos: no se puede borrar.")


def test_eliminar_pide_confirmacion_y_cancelar_no_borra(app, con, categorias):
    clic(_tile(categorias, "Mercado"), "Eliminar")
    confirmacion = dialogo_arriba(app)
    assert titulo_dialogo(confirmacion) == "¿Eliminar la categoría Mercado?"
    clic(confirmacion, "Cancelar")
    assert "Mercado" in _nombres(categorias)


def test_eliminar_confirmado_borra_y_avisa(app, con, categorias, pagina):
    clic(_tile(categorias, "Mercado"), "Eliminar")
    clic(dialogo_arriba(app), "Eliminar")
    assert "Mercado" not in _nombres(categorias)
    assert pagina.avisos()[-1] == '"Mercado" eliminado'
    categorias.mostrar_archivados.value = True
    categorias.refrescar()
    assert "Mercado" not in _nombres(categorias)  # se borró de verdad


def test_eliminar_medio_pide_confirmacion_con_su_texto(app, medios):
    clic(_tile(medios, "Efectivo"), "Eliminar")
    assert titulo_dialogo(dialogo_arriba(app)) == "¿Eliminar el medio de pago Efectivo?"


def test_archivar_no_pide_confirmacion_y_ofrece_deshacer(app, con, categorias, pagina):
    # §3.10: archivar no pide confirmación (es reversible) y el aviso tiene "Deshacer".
    _usar_en_gasto(app, con, catalogos.CATEGORIAS, "Vivienda")
    categorias.refrescar()
    clic(_tile(categorias, "Vivienda"), "Archivar")
    assert app.hay_dialogo_abierto() is False
    assert "Vivienda" not in _nombres(categorias)
    aviso = pagina.ultimo_aviso()
    assert aviso.content.value == '"Vivienda" archivado'
    assert aviso.action == "Deshacer"
    aviso.on_action(None)
    assert "Vivienda" in _nombres(categorias)
    assert (
        catalogos.obtener(
            con, catalogos.CATEGORIAS, id_por_nombre(con, "categorias", "Vivienda")
        )["archivado"]
        == 0
    )


def test_mostrar_archivadas_y_desarchivar(app, con, categorias, pagina):
    # §3.10: el switch muestra las archivadas con su etiqueta y botón "Desarchivar".
    _usar_en_gasto(app, con, catalogos.CATEGORIAS, "Vivienda")
    categorias.refrescar()
    clic(_tile(categorias, "Vivienda"), "Archivar")
    assert categorias.mostrar_archivados.label == "Mostrar archivadas"
    categorias.mostrar_archivados.value = True
    categorias.mostrar_archivados.on_change(None)
    t = _tile(categorias, "Vivienda")
    assert t.subtitle.value == "Archivada"
    assert hay_boton(t, "Desarchivar")
    assert not hay_boton(t, "Archivar")
    clic(t, "Desarchivar")
    assert _tile(categorias, "Vivienda").subtitle is None
    assert pagina.avisos()[-1] == '"Vivienda" vuelve a aparecer al cargar datos'


def test_medios_archivados_dicen_archivado(app, con, medios):
    _usar_en_gasto(app, con, catalogos.MEDIOS_PAGO, "Efectivo")
    medios.refrescar()
    clic(_tile(medios, "Efectivo"), "Archivar")
    medios.mostrar_archivados.value = True
    medios.refrescar()
    assert medios.mostrar_archivados.label == "Mostrar archivados"
    assert _tile(medios, "Efectivo").subtitle.value == "Archivado"


def test_lista_vacia_muestra_texto(con, categorias):
    for fila in catalogos.listar(con, catalogos.CATEGORIAS):
        catalogos.eliminar(con, catalogos.CATEGORIAS, fila["id"])
    categorias.refrescar()
    assert textos(categorias.lista) == ["No hay categorías."]


# --- Crear y renombrar (§4.7) ---


def _campo_nombre(dialogo):
    return dialogo.content.controls[0]


def test_crear_categoria(app, con, categorias, pagina):
    clic(categorias.control, "Nueva categoría")
    dialogo = dialogo_arriba(app)
    assert titulo_dialogo(dialogo) == "Nueva categoría"
    _campo_nombre(dialogo).value = "  Educación "
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert "Educación" in _nombres(categorias)
    assert pagina.avisos()[-1] == 'Agregado: "Educación"'


def test_crear_con_enter(app, categorias):
    categorias.nuevo()
    campo = _campo_nombre(dialogo_arriba(app))
    campo.value = "Educación"
    campo.on_submit(None)
    assert "Educación" in _nombres(categorias)


@pytest.mark.parametrize("nombre", ["", "   ", "salud", "SALUD"])
def test_crear_vacio_o_repetido_muestra_error_en_el_campo(app, categorias, nombre):
    # CA-10.2 en pantalla: el error queda debajo del campo y el diálogo no se cierra.
    categorias.nuevo()
    dialogo = dialogo_arriba(app)
    _campo_nombre(dialogo).value = nombre
    clic(dialogo, "Guardar")
    assert _campo_nombre(dialogo).error
    assert app._dialogos == [dialogo]
    assert len(_nombres(categorias)) == 7


def test_mensaje_de_nombre_vacio_segun_diseno(app, categorias):
    # §3.10: vacío → "Ingresá un nombre."
    categorias.nuevo()
    dialogo = dialogo_arriba(app)
    clic(dialogo, "Guardar")
    assert _campo_nombre(dialogo).error == "Ingresá un nombre."


def test_mensaje_de_nombre_repetido_segun_diseno(app, categorias):
    # §3.10: repetido → 'Ya existe una categoría llamada "Salud".'
    categorias.nuevo()
    dialogo = dialogo_arriba(app)
    _campo_nombre(dialogo).value = "salud"
    clic(dialogo, "Guardar")
    assert _campo_nombre(dialogo).error == 'Ya existe una categoría llamada "Salud".'


def test_repetido_de_archivada_avisa_que_esta_archivada(app, con, categorias):
    _usar_en_gasto(app, con, catalogos.CATEGORIAS, "Vivienda")
    catalogos.eliminar(
        con, catalogos.CATEGORIAS, id_por_nombre(con, "categorias", "Vivienda")
    )
    categorias.nuevo()
    dialogo = dialogo_arriba(app)
    _campo_nombre(dialogo).value = "vivienda"
    clic(dialogo, "Guardar")
    assert "archivad" in _campo_nombre(dialogo).error


def test_renombrar_precarga_y_guarda(app, con, categorias, pagina):
    # CA-10.1 en pantalla: renombrar "Salud" a "Salud y bienestar".
    clic(_tile(categorias, "Salud"), "Renombrar")
    dialogo = dialogo_arriba(app)
    assert titulo_dialogo(dialogo) == "Renombrar categoría"
    assert _campo_nombre(dialogo).value == "Salud"
    _campo_nombre(dialogo).value = "Salud y bienestar"
    clic(dialogo, "Guardar")
    assert "Salud y bienestar" in _nombres(categorias)
    assert "Salud" not in _nombres(categorias)
    assert pagina.avisos()[-1] == 'Renombrado: "Salud y bienestar"'


def test_renombrar_a_repetido_muestra_error(app, categorias):
    clic(_tile(categorias, "Salud"), "Renombrar")
    dialogo = dialogo_arriba(app)
    _campo_nombre(dialogo).value = "otros"
    clic(dialogo, "Guardar")
    assert _campo_nombre(dialogo).error
    assert "Salud" in _nombres(categorias)


def test_renombrar_medio(app, medios):
    clic(_tile(medios, "Efectivo"), "Renombrar")
    dialogo = dialogo_arriba(app)
    assert titulo_dialogo(dialogo) == "Renombrar medio de pago"
    _campo_nombre(dialogo).value = "Billetera"
    clic(dialogo, "Guardar")
    assert "Billetera" in _nombres(medios)


def test_cancelar_en_el_dialogo_de_nombre(app, categorias):
    categorias.nuevo()
    dialogo = dialogo_arriba(app)
    _campo_nombre(dialogo).value = "Educación"
    clic(dialogo, "Cancelar")
    assert "Educación" not in _nombres(categorias)
    assert app.hay_dialogo_abierto() is False


def test_categoria_renombrada_se_ve_en_gastos_y_en_el_dialogo(app, con, categorias):
    # CA-10.1: el nombre nuevo se ve en la tabla de gastos y en el desplegable.
    _usar_en_gasto(app, con, catalogos.CATEGORIAS, "Salud")
    catalogos.renombrar(
        con,
        catalogos.CATEGORIAS,
        id_por_nombre(con, "categorias", "Salud"),
        "Salud y bienestar",
    )
    ir(app, "Gastos")
    pantalla = app.pantalla("Gastos")
    assert "Salud y bienestar" in textos(pantalla.cuerpo)


def test_ca_10_4_desarchivada_vuelve_al_dialogo_de_gasto(app, con, categorias):
    # CA-10.4: después de desarchivar, la categoría vuelve a ofrecerse en el alta.
    _usar_en_gasto(app, con, catalogos.CATEGORIAS, "Vivienda")
    categorias.refrescar()
    clic(_tile(categorias, "Vivienda"), "Archivar")
    ir(app, "Gastos")
    app.pantalla("Gastos").nuevo()
    dialogo = dialogo_arriba(app)
    opciones = [
        o.text for o in boton(dialogo, "Guardar").on_click.__self__.categoria.options
    ]
    assert "Vivienda" not in opciones
    app.cerrar_dialogo(dialogo)
    pagina_aviso = app.page.ultimo_aviso()
    pagina_aviso.on_action(None)  # Deshacer = desarchivar
    app.pantalla("Gastos").nuevo()
    dialogo = dialogo_arriba(app)
    opciones = [
        o.text for o in boton(dialogo, "Guardar").on_click.__self__.categoria.options
    ]
    assert "Vivienda" in opciones
