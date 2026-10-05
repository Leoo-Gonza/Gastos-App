"""Casos borde de la interfaz: datos que cambian con un diálogo abierto, errores
técnicos y tema oscuro. Sin abrir ventanas."""

import flet as ft
import pytest

from app.interfaz import estilos
from app.logica import catalogos, gastos
from tests.ayudantes import id_por_nombre
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    clic,
    dialogo_arriba,
    dialogo_gasto_abierto,
    ir,
    titulo_dialogo,
)


def _falla(*args, **kwargs):
    raise RuntimeError("falla inventada")


@pytest.mark.parametrize(
    ("modo", "brillo", "esperado"),
    [
        (ft.ThemeMode.LIGHT, ft.Brightness.DARK, "#B3261E"),
        (ft.ThemeMode.DARK, ft.Brightness.LIGHT, "#FF8A80"),
        (ft.ThemeMode.SYSTEM, ft.Brightness.DARK, "#FF8A80"),
        (ft.ThemeMode.SYSTEM, ft.Brightness.LIGHT, "#B3261E"),
    ],
)
def test_color_semantico_segun_el_tema(modo, brillo, esperado):
    # §2.1: el color "negativo" cambia entre tema claro y oscuro (y "como el sistema").
    pagina = PaginaFalsa()
    pagina.theme_mode = modo
    pagina.platform_brightness = brillo
    assert estilos.color(pagina, "negativo") == esperado


def test_medio_archivado_con_el_dialogo_abierto_marca_el_campo_medio(app, con):
    # Si el medio elegido se archiva mientras el diálogo está abierto, el error va
    # debajo de "Medio de pago".
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    app.pantalla("Gastos").nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Seguro"
    d.categoria.value = str(otros)
    d.monto.value = "10.000"
    d.medio.value = str(visa)
    gastos.agregar_gasto(con, app.mes_id, "Otro", otros, 100, "fijo", visa)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    d._guardar()
    assert d.medio.error_text == "El medio de pago elegido está archivado."


def test_error_inesperado_al_crear_categoria_en_linea(app, monkeypatch):
    app.pantalla("Gastos").nuevo()
    d = dialogo_gasto_abierto(app)
    monkeypatch.setattr(catalogos, "crear", _falla)
    d.nueva_categoria.value = "Educación"
    d._agregar_categoria(None)
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


def test_error_inesperado_al_borrar_gasto(app, con, monkeypatch):
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gid = gastos.agregar_gasto(con, app.mes_id, "Nafta", otros, 100, "fijo")
    app.refrescar()
    app.pantalla("Gastos").borrar(gid)
    monkeypatch.setattr(gastos, "borrar_gasto", _falla)
    clic(dialogo_arriba(app), "Borrar")
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"
    assert gastos.obtener_gasto(con, gid) is not None


def test_error_inesperado_al_guardar_un_nombre_en_ajustes(app, monkeypatch):
    ir(app, "Ajustes")
    lista = app.pantalla("Ajustes").listas[0]
    lista.nuevo()
    dialogo = dialogo_arriba(app)
    monkeypatch.setattr(catalogos, "crear", _falla)
    dialogo.content.controls[0].value = "Educación"
    clic(dialogo, "Guardar")
    assert dialogo.open is False
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"


def test_eliminar_algo_que_ya_no_existe_no_dice_eliminado(app, con, pagina):
    # Si al confirmar el elemento ya no existe, el aviso tiene que ser solo el error
    # ("Ese elemento ya no existe."), sin un segundo aviso de "eliminado".
    ir(app, "Ajustes")
    lista = app.pantalla("Ajustes").listas[0]
    [tile] = [t for t in lista.lista.controls if t.title.value == "Mercado"]
    clic(tile, "Eliminar")
    # Se borra "por otro lado" antes de confirmar.
    catalogos.eliminar(
        con, catalogos.CATEGORIAS, id_por_nombre(con, "categorias", "Mercado")
    )
    clic(dialogo_arriba(app), "Eliminar")
    assert "Ese elemento ya no existe." in pagina.avisos()
    assert '"Mercado" eliminado' not in pagina.avisos()


def test_error_inesperado_en_una_accion_de_ajustes(app, con, monkeypatch):
    ir(app, "Ajustes")
    lista = app.pantalla("Ajustes").listas[0]
    [tile] = [t for t in lista.lista.controls if t.title.value == "Mercado"]
    clic(tile, "Eliminar")
    monkeypatch.setattr(catalogos, "eliminar", _falla)
    clic(dialogo_arriba(app), "Eliminar")
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"
