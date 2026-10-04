"""Pruebas de la ventana principal: configuración, navegación, diálogos, avisos,
error inesperado y atajos de teclado (diseno.md §1, §1.3, §2.5)."""

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.interfaz.pantalla_ajustes import PantallaAjustes
from app.interfaz.pantalla_gastos import PantallaGastos
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    clic,
    dialogo_arriba,
    tecla,
    textos,
    titulo_dialogo,
)


def _pantalla_visible(app):
    return app._pantallas[app._indice]


def test_configuracion_de_la_ventana(app, pagina):
    # §1.1: tamaño inicial y mínimo, tema "como el sistema" y atajos conectados.
    assert (pagina.window.width, pagina.window.height) == (1280, 800)
    assert (pagina.window.min_width, pagina.window.min_height) == (1100, 700)
    assert pagina.theme_mode == ft.ThemeMode.SYSTEM
    assert pagina.on_keyboard_event == app._al_presionar_tecla


def test_menu_lateral_tiene_gastos_y_ajustes(app, pagina):
    # §6 Paso 1: el rail tiene 2 destinos.
    rail = app._rail
    assert [d.label for d in rail.destinations] == ["Gastos", "Ajustes"]
    assert rail.selected_index == 0
    assert isinstance(_pantalla_visible(app), PantallaGastos)


def test_cambiar_de_destino_con_el_rail(app):
    # Elegir "Ajustes" en el rail muestra Ajustes.
    app._rail.selected_index = 1
    app._rail.on_change(type("E", (), {"control": app._rail})())
    assert isinstance(_pantalla_visible(app), PantallaAjustes)
    assert app._contenido.content is _pantalla_visible(app).control


# ---------------------------------------------------------------------------
# Diálogos y avisos
# ---------------------------------------------------------------------------


def test_error_inesperado_muestra_dialogo_con_detalle(app):
    # §2.5: "No se pudo guardar" + "Los datos no se modificaron." + detalle técnico.
    try:
        raise ValueError("falla inventada")
    except ValueError as error:
        app.error_inesperado(error)
    dialogo = dialogo_arriba(app)
    assert titulo_dialogo(dialogo) == "No se pudo guardar"
    contenido = textos(dialogo)
    assert "Los datos no se modificaron." in contenido
    assert any("falla inventada" in t for t in contenido)
    clic(dialogo, "Cerrar")
    assert dialogo.open is False
    assert app.hay_dialogo_abierto() is False


def test_on_dismiss_olvida_el_dialogo(app):
    # Si el diálogo se cierra por otro motivo, la app deja de considerarlo abierto.
    app.error_inesperado(RuntimeError("x"))
    dialogo = dialogo_arriba(app)
    dialogo.on_dismiss(None)
    assert app.hay_dialogo_abierto() is False


def test_avisar_con_deshacer(app, pagina):
    # SnackBar con acción "Deshacer" que llama a la función indicada.
    llamadas = []
    app.avisar("Hecho", al_deshacer=lambda: llamadas.append(1))
    aviso = pagina.ultimo_aviso()
    assert aviso.content.value == "Hecho"
    assert aviso.action == "Deshacer"
    aviso.on_action(None)
    assert llamadas == [1]
    # Los avisos no cuentan como diálogo abierto (no bloquean los atajos).
    assert app.hay_dialogo_abierto() is False


# ---------------------------------------------------------------------------
# Atajos de teclado (§1.3)
# ---------------------------------------------------------------------------


def test_ctrl_2_y_ctrl_1_cambian_de_pantalla(app):
    app._al_presionar_tecla(tecla("2", ctrl=True))
    assert isinstance(_pantalla_visible(app), PantallaAjustes)
    assert app._rail.selected_index == 1
    app._al_presionar_tecla(tecla("1", ctrl=True))
    assert isinstance(_pantalla_visible(app), PantallaGastos)


def test_ctrl_coma_va_a_ajustes(app):
    app._al_presionar_tecla(tecla(",", ctrl=True))
    assert isinstance(_pantalla_visible(app), PantallaAjustes)


@pytest.mark.parametrize("key", ["0", "3", "9"])
def test_ctrl_numero_sin_pantalla_no_hace_nada(app, key):
    # Solo hay 2 destinos en el paso 1: Ctrl+0, Ctrl+3... se ignoran sin error.
    app._al_presionar_tecla(tecla(key, ctrl=True))
    assert isinstance(_pantalla_visible(app), PantallaGastos)


def test_tecla_sin_modificador_no_hace_nada(app):
    app._al_presionar_tecla(tecla("2"))
    app._al_presionar_tecla(tecla("N"))
    assert isinstance(_pantalla_visible(app), PantallaGastos)
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize("key", ["N", "n"])
def test_ctrl_n_en_gastos_abre_nuevo_gasto(app, key):
    app._al_presionar_tecla(tecla(key, ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo gasto – Octubre 2026"


def test_ctrl_shift_n_no_abre_nuevo_gasto(app):
    # Ctrl+Shift+N queda reservado para "Mes nuevo" (paso 4).
    app._al_presionar_tecla(tecla("N", ctrl=True, shift=True))
    assert app.hay_dialogo_abierto() is False


def test_ctrl_n_en_ajustes_segun_la_pestana(app):
    # Ctrl+N en Ajustes: nuevo elemento de la pestaña visible.
    app.ir_a(1)
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Nueva categoría"
    app._al_presionar_tecla(tecla("Escape"))

    _pantalla_visible(app).pestanas.selected_index = 1
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo medio de pago"


def test_con_dialogo_abierto_los_atajos_se_ignoran(app):
    # §1.3: mientras hay un diálogo abierto, los atajos globales no hacen nada.
    app._al_presionar_tecla(tecla("N", ctrl=True))
    dialogo = dialogo_arriba(app)
    app._al_presionar_tecla(tecla("2", ctrl=True))
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert isinstance(_pantalla_visible(app), PantallaGastos)
    assert app._dialogos == [dialogo]


def test_escape_cierra_el_dialogo_de_arriba(app):
    # Esc cierra solo el diálogo de más arriba.
    app._al_presionar_tecla(tecla("N", ctrl=True))
    primero = dialogo_arriba(app)
    app.error_inesperado(RuntimeError("x"))
    segundo = dialogo_arriba(app)
    app._al_presionar_tecla(tecla("Escape"))
    assert segundo.open is False
    assert app._dialogos == [primero]
    app._al_presionar_tecla(tecla("Escape"))
    assert primero.open is False
    assert app.hay_dialogo_abierto() is False


def test_escape_sin_dialogo_no_hace_nada(app):
    app._al_presionar_tecla(tecla("Escape"))
    assert isinstance(_pantalla_visible(app), PantallaGastos)


def test_en_macos_se_usa_cmd(con, mes_id):
    # §1.3: en macOS el modificador es Cmd (meta); Ctrl no hace nada.
    pagina = PaginaFalsa(plataforma=ft.PagePlatform.MACOS)
    app = Aplicacion(pagina, con)
    app.iniciar()
    app._al_presionar_tecla(tecla("2", ctrl=True))
    assert isinstance(_pantalla_visible(app), PantallaGastos)
    app._al_presionar_tecla(tecla("2", meta=True))
    assert isinstance(_pantalla_visible(app), PantallaAjustes)


def test_en_windows_cmd_no_hace_nada(app):
    app._al_presionar_tecla(tecla("2", meta=True))
    assert isinstance(_pantalla_visible(app), PantallaGastos)


def test_atajos_en_primer_uso_no_rompen(app_vacia, pagina):
    # En la pantalla de primer uso no hay destinos: los atajos se ignoran sin error.
    app_vacia._al_presionar_tecla(tecla("N", ctrl=True))
    app_vacia._al_presionar_tecla(tecla("2", ctrl=True))
    assert pagina.title == "Gastos – Bienvenido"
    assert app_vacia.hay_dialogo_abierto() is False
