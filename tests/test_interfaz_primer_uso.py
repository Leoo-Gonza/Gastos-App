"""Pruebas de la pantalla de primer uso (RF-04, CA-04.1, CA-04.2, diseno.md §3.1).

Se usa una página falsa: no se abre ninguna ventana.
"""

import flet as ft
import pytest

from app.interfaz.pantalla_primer_uso import PantallaPrimerUso
from app.logica import meses
from tests.ayudantes_interfaz import de_tipo, mes_seleccionado, textos


@pytest.fixture
def pantalla(app_vacia):
    """Pantalla de primer uso con mes y año fijos (Octubre 2026), sin depender del día."""
    p = PantallaPrimerUso(app_vacia)
    p.mes.value = "10"
    p.anio.value = "2026"
    return p


def _completar(p, anio="2026", sueldo="1.200", cotizacion="1.600"):
    p.anio.value = anio
    p.sueldo.value = sueldo
    p.cotizacion.value = cotizacion


def test_sin_meses_arranca_en_primer_uso(app_vacia, pagina):
    # CA-04.1: con la base vacía se muestra la bienvenida, sin menú lateral.
    assert pagina.title == "Gastos – Bienvenido"
    contenido = pagina.controls[0]
    assert "Bienvenido a tu app de gastos" in textos(contenido)
    assert "Crear mes" in textos(contenido)
    assert de_tipo(contenido, ft.NavigationRail) == []


def test_con_meses_arranca_en_gastos(app, pagina):
    # Si ya hay un mes, se va directo a la estructura principal (menú + Gastos).
    assert pagina.title == "Gastos – Octubre 2026"
    assert len(de_tipo(pagina.controls[0], ft.NavigationRail)) == 1


def test_valores_iniciales_del_formulario(app_vacia):
    # §3.1: mes y año del calendario; 12 meses en español; sueldo y cotización vacíos.
    p = PantallaPrimerUso(app_vacia)
    anio, mes = meses.mes_actual_calendario()
    assert p.mes.value == str(mes)
    assert p.anio.value == str(anio)
    assert p.anio.max_length == 4
    assert [o.text for o in p.mes.options][:2] == ["Enero", "Febrero"]
    assert len(p.mes.options) == 12
    assert p.cotizacion.helper == "Podés dejarla vacía y cargarla después."


@pytest.mark.parametrize("anio", ["", "26", "202"])
def test_anio_vacio_o_corto_se_rechaza(pantalla, con, anio):
    # CA-04.2: año vacío o que no tiene 4 dígitos muestra el error y no crea el mes.
    _completar(pantalla, anio=anio)
    pantalla._crear()
    assert pantalla.anio.error == "El año tiene que tener 4 dígitos. Ej.: 2026"
    assert meses.hay_meses(con) is False


def test_anio_0026_lo_rechaza_la_logica_en_el_campo_anio(pantalla, con):
    # "0026" tiene 4 caracteres pero es el año 26: la lógica lo rechaza (campo "anio").
    _completar(pantalla, anio="0026")
    pantalla._crear()
    assert pantalla.anio.error == "El año tiene que tener 4 dígitos."
    assert meses.hay_meses(con) is False


def test_sueldo_vacio_se_rechaza_con_su_mensaje(pantalla, con):
    # §3.1: sueldo vacío.
    _completar(pantalla, sueldo="")
    pantalla._crear()
    assert pantalla.sueldo.error == "Ingresá el sueldo. Si este mes no cobrás, poné 0."
    assert meses.hay_meses(con) is False


def test_errores_se_muestran_todos_juntos(pantalla, con):
    # §2.5: año, sueldo y cotización mal a la vez: los tres errores aparecen juntos.
    _completar(pantalla, anio="", sueldo="", cotizacion="0")
    pantalla._crear()
    assert pantalla.anio.error
    assert pantalla.sueldo.error
    assert pantalla.cotizacion.error
    assert meses.hay_meses(con) is False


def test_cotizacion_cero_se_rechaza(pantalla, con):
    # RN-06: cotización "0" no se acepta y no se crea el mes.
    _completar(pantalla, cotizacion="0")
    pantalla._crear()
    assert pantalla.cotizacion.error
    assert meses.hay_meses(con) is False


def test_cotizacion_cero_muestra_el_mensaje_del_diseno(pantalla):
    # §3.1: el mensaje debajo de "Cotización" tiene que nombrar la cotización.
    _completar(pantalla, cotizacion="0")
    pantalla._crear()
    assert pantalla.cotizacion.error == "La cotización tiene que ser mayor a 0."


def test_cotizacion_vacia_se_acepta(pantalla, con):
    # RN-06 / decisión aprobada: la cotización puede quedar vacía (NULL).
    _completar(pantalla, cotizacion="")
    pantalla._crear()
    assert meses.obtener_ultimo_mes(con)["cotizacion_cent"] is None


def test_sueldo_cero_se_acepta(pantalla, con):
    # RN-05: sueldo 0 se acepta.
    _completar(pantalla, sueldo="0")
    pantalla._crear()
    assert meses.obtener_ultimo_mes(con)["sueldo_usd_cent"] == 0


def test_sueldo_cero_muestra_aviso_al_salir_del_campo(pantalla):
    # §3.1: con sueldo 0, debajo del campo y en color "pendiente": "El sueldo de este mes es 0".
    pantalla.sueldo.value = "0"
    pantalla.sueldo.on_blur(None)
    assert pantalla.sueldo.helper == "El sueldo de este mes es 0"
    assert pantalla.sueldo.helper_style.color == "#9A5800"  # pendiente, tema claro
    assert pantalla.sueldo.error is None


def test_sueldo_distinto_de_cero_no_muestra_aviso_y_se_formatea(pantalla):
    # Al salir del campo el monto se reescribe prolijo y el aviso desaparece.
    pantalla.sueldo.value = "0"
    pantalla.sueldo.on_blur(None)
    pantalla.sueldo.value = "1200,5"
    pantalla.sueldo.on_blur(None)
    assert pantalla.sueldo.helper is None
    assert pantalla.sueldo.value == "1.200,50"


def test_crear_guarda_en_centavos_y_pasa_al_resumen(pantalla, app_vacia, pagina, con):
    # CA-04.1 y §3.1: al crear, pasa a la estructura principal con la pantalla
    # Resumen (paso 3 en adelante).
    _completar(pantalla, sueldo="1.200", cotizacion="1.432,50")
    pantalla._crear()
    mes = meses.obtener_ultimo_mes(con)
    assert (mes["anio"], mes["mes"]) == (2026, 10)
    assert (mes["sueldo_usd_cent"], mes["cotizacion_cent"]) == (120000, 143250)
    assert pagina.title == "Gastos – Octubre 2026"
    assert mes_seleccionado(app_vacia) == "Octubre 2026"
    assert "Resumen de Octubre 2026" in textos(pagina.controls[0])
    assert app_vacia._rail.selected_index == 0


def test_enter_en_el_sueldo_crea_el_mes(pantalla, con):
    # §2.5: Enter guarda (on_submit).
    _completar(pantalla)
    pantalla.sueldo.on_submit(None)
    assert meses.hay_meses(con) is True


def test_error_inesperado_al_crear_muestra_dialogo(pantalla, app_vacia, monkeypatch):
    # §2.5: si falla algo que no es un dato mal cargado, aparece "No se pudo guardar".
    def falla(*args, **kwargs):
        raise RuntimeError("disco lleno (inventado)")

    monkeypatch.setattr(meses, "crear_primer_mes", falla)
    _completar(pantalla)
    pantalla._crear()
    dialogo = app_vacia._dialogos[-1]
    assert dialogo.title.value == "No se pudo guardar"
    assert any("RuntimeError" in t for t in textos(dialogo))
