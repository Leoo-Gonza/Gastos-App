"""Pruebas de los arreglos de la ronda 5 en la interfaz: foco en el primer error (O10),
atajos según el sistema (O11), tooltip de Archivar (O12), gastos que ya no existen (O15),
foco en "Cancelar" (O16), avisos de Ajustes (BUG-08) y total en singular (BUG-06)."""

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.interfaz.pantalla_primer_uso import PantallaPrimerUso
from app.logica import catalogos, gastos, meses
from tests.ayudantes import id_por_nombre, insertar_pago
from tests.ayudantes_interfaz import (
    PaginaFalsa,
    boton,
    clic,
    dialogo_arriba,
    dialogo_gasto_abierto,
    filas_tabla,
    ir,
    textos,
)


def _enfocado(pagina):
    """El control al que se le pidió el foco por última vez (app.enfocar usa run_task)."""
    assert pagina.tareas, "No se pidió el foco de ningún control"
    return pagina.tareas[-1].__self__


def _otros(con):
    return id_por_nombre(con, catalogos.CATEGORIAS, "Otros")


# ---------------------------------------------------------------------------
# O10: foco en el primer campo con error
# ---------------------------------------------------------------------------


@pytest.fixture
def primer_uso(app_vacia):
    p = PantallaPrimerUso(app_vacia)
    p.mes.value = "10"
    p.anio.value = "2026"
    p.sueldo.value = "1.200"
    p.cotizacion.value = "1.600"
    return p


@pytest.mark.parametrize(
    ("anio", "sueldo", "cotizacion", "campo"),
    [
        ("", "", "0", "anio"),
        ("2026", "", "0", "sueldo"),
        ("2026", "1.200", "0", "cotizacion"),
        ("0026", "1.200", "1.600", "anio"),  # error que viene de la lógica
    ],
)
def test_o10_primer_uso_enfoca_el_primer_error(
    primer_uso, pagina, anio, sueldo, cotizacion, campo
):
    primer_uso.anio.value = anio
    primer_uso.sueldo.value = sueldo
    primer_uso.cotizacion.value = cotizacion
    primer_uso._crear()
    assert _enfocado(pagina) is getattr(primer_uso, campo)


def test_o10_primer_uso_sin_errores_no_pide_foco(primer_uso, pagina):
    primer_uso._crear()
    assert pagina.tareas == []


def test_primer_uso_mensajes_con_el_nombre_del_dato(primer_uso):
    # BUG-07: los mensajes del primer uso nombran el sueldo y la cotización.
    primer_uso.sueldo.value = "1.2.3"
    primer_uso.cotizacion.value = "0"
    primer_uso._crear()
    assert primer_uso.sueldo.error == "Escribí solo números. Ej.: 66.020,12"
    assert primer_uso.cotizacion.error == "La cotización tiene que ser mayor a 0."
    primer_uso.sueldo.value = "999.999.999.999,01"
    primer_uso._crear()
    assert primer_uso.sueldo.error == "El sueldo es demasiado grande."


def test_primer_uso_si_ya_existe_un_mes_muestra_el_error_en_mes(primer_uso, con):
    # Error de la lógica sin campo (ya hay un mes): va debajo del desplegable de Mes.
    meses.crear_primer_mes(con, 2026, 9, 120000)
    primer_uso._crear()
    assert (
        primer_uso.mes.error_text
        == "Ya existe un mes. Los siguientes se crean con 'Mes nuevo'."
    )
    assert meses.obtener_ultimo_mes(con)["mes"] == 9


@pytest.mark.parametrize(
    ("nombre", "con_categoria", "monto", "campo"),
    [
        ("", False, "", "nombre"),
        ("Nafta", False, "", "categoria"),
        ("Nafta", True, "", "monto"),
        ("Nafta", True, "66020.12", "monto"),
    ],
)
def test_o10_dialogo_gasto_enfoca_el_primer_error(
    app, con, pagina, nombre, con_categoria, monto, campo
):
    app.pantalla("Gastos").nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = nombre
    d.categoria.value = str(_otros(con)) if con_categoria else None
    d.monto.value = monto
    d._guardar()
    assert _enfocado(pagina) is getattr(d, campo)


def test_o10_error_de_la_logica_en_medio_enfoca_medio(app, con, pagina):
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    app.pantalla("Gastos").nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Seguro"
    d.categoria.value = str(_otros(con))
    d.monto.value = "10.000"
    d.medio.value = str(visa)
    gastos.agregar_gasto(con, app.mes_id, "Otro", _otros(con), 100, "fijo", visa)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    d._guardar()
    assert _enfocado(pagina) is d.medio


def test_o10_rn_23_enfoca_el_monto(app, con, pagina):
    gid = gastos.agregar_gasto(con, app.mes_id, "Seguro", _otros(con), 18000000, "fijo")
    insertar_pago(con, gid, 6000000)
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    d.monto.value = "50.000"
    d._guardar()
    assert _enfocado(pagina) is d.monto


def test_o10_dialogo_de_nombre_en_ajustes_enfoca_el_campo(app, pagina):
    ir(app, "Ajustes")
    app.pantalla("Ajustes").listas[0].nuevo()
    dialogo = dialogo_arriba(app)
    clic(dialogo, "Guardar")
    campo = dialogo.content.controls[0]
    assert campo.error == "Ingresá un nombre."
    assert _enfocado(pagina) is campo


# ---------------------------------------------------------------------------
# O11: atajos en los textos según el sistema
# ---------------------------------------------------------------------------


def _app_en(plataforma, con):
    aplicacion = Aplicacion(PaginaFalsa(plataforma=plataforma), con)
    aplicacion.iniciar()
    ir(aplicacion, "Gastos")
    return aplicacion


@pytest.mark.parametrize(
    ("plataforma", "atajo"),
    [
        (ft.PagePlatform.MACOS, "⌘N"),
        (ft.PagePlatform.WINDOWS, "Ctrl+N"),
        (ft.PagePlatform.LINUX, "Ctrl+N"),
    ],
)
def test_o11_textos_de_atajos_segun_el_sistema(con, mes_id, plataforma, atajo):
    aplicacion = _app_en(plataforma, con)
    assert aplicacion.atajo("N") == atajo
    gastos_pantalla = aplicacion.pantalla("Gastos")
    assert (
        boton(gastos_pantalla.control, "Agregar gasto").tooltip
        == f"Agregar gasto ({atajo})"
    )
    # Estado vacío: el botón lleva el atajo en el texto.
    assert f"Agregar gasto ({atajo})" in textos(gastos_pantalla.cuerpo)
    ajustes = aplicacion.pantalla("Ajustes")
    assert boton(ajustes.listas[0].control, "Nueva categoría").tooltip == (
        f"Nueva categoría ({atajo})"
    )
    assert boton(ajustes.listas[1].control, "Nuevo medio de pago").tooltip == (
        f"Nuevo medio de pago ({atajo})"
    )


# ---------------------------------------------------------------------------
# O12: tooltip de "Archivar" con el género correcto
# ---------------------------------------------------------------------------


def test_o12_tooltip_de_archivar(app, con):
    gastos.agregar_gasto(
        con,
        app.mes_id,
        "X",
        id_por_nombre(con, catalogos.CATEGORIAS, "Vivienda"),
        100,
        "fijo",
        id_por_nombre(con, catalogos.MEDIOS_PAGO, "Efectivo"),
    )
    # Paso 5: también una persona en uso (con un ítem en "Me deben").
    from app.logica import me_deben

    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    me_deben.agregar_item(con, sofia, "Préstamo", 100)
    ir(app, "Ajustes")
    categorias, medios, personas = app.pantalla("Ajustes").listas
    [vivienda] = [t for t in categorias.lista.controls if t.title.value == "Vivienda"]
    [efectivo] = [t for t in medios.lista.controls if t.title.value == "Efectivo"]
    [persona] = [t for t in personas.lista.controls if t.title.value == "Sofía"]
    assert boton(vivienda, "Archivar").tooltip == (
        "Se usa en gastos: no se puede borrar. Archivada no aparece al cargar datos nuevos."
    )
    assert boton(efectivo, "Archivar").tooltip == (
        "Se usa en gastos: no se puede borrar. Archivado no aparece al cargar datos nuevos."
    )
    assert boton(persona, "Archivar").tooltip == (
        "Tiene gastos compartidos o ítems en Me deben: no se puede borrar. "
        "Archivada no aparece al compartir gastos nuevos."
    )


# ---------------------------------------------------------------------------
# O15: gastos que ya no existen
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("accion", ["editar", "borrar"])
def test_o15_editar_o_borrar_un_gasto_que_ya_no_existe(app, con, pagina, accion):
    gid = gastos.agregar_gasto(con, app.mes_id, "Nafta", _otros(con), 100, "fijo")
    app.refrescar()
    gastos.borrar_gasto(con, gid)  # se borra "por detrás"; la tabla quedó vieja
    getattr(app.pantalla("Gastos"), accion)(gid)
    assert app.hay_dialogo_abierto() is False
    assert pagina.avisos()[-1] == "Ese gasto ya no existe."
    assert "Todavía no cargaste gastos en Octubre 2026." in textos(
        app.pantalla("Gastos").cuerpo
    )


def test_o15_gasto_borrado_con_el_dialogo_de_edicion_abierto(app, con, pagina):
    # Error de la lógica sin campo: se cierra el diálogo, se refresca y se avisa.
    gid = gastos.agregar_gasto(con, app.mes_id, "Nafta", _otros(con), 100, "fijo")
    gastos.agregar_gasto(con, app.mes_id, "Alquiler", _otros(con), 100, "fijo")
    app.refrescar()
    app.pantalla("Gastos").editar(gid)
    d = dialogo_gasto_abierto(app)
    gastos.borrar_gasto(con, gid)
    d.monto.value = "200"
    d._guardar()
    assert d.dialogo.open is False
    assert app.hay_dialogo_abierto() is False
    assert pagina.avisos()[-1] == "El gasto ya no existe."
    assert [f["Nombre"] for f in filas_tabla(app.pantalla("Gastos"))[:-1]] == [
        "Alquiler"
    ]
    assert len(gastos.listar_gastos(con, app.mes_id)) == 1  # no se creó otro


# ---------------------------------------------------------------------------
# O16: "Cancelar" con foco por defecto en las confirmaciones
# ---------------------------------------------------------------------------


def test_o16_cancelar_tiene_el_foco_en_la_confirmacion(app, con):
    gid = gastos.agregar_gasto(con, app.mes_id, "Nafta", _otros(con), 100, "fijo")
    app.refrescar()
    app.pantalla("Gastos").borrar(gid)
    confirmacion = dialogo_arriba(app)
    assert boton(confirmacion, "Cancelar").autofocus is True
    assert not boton(confirmacion, "Borrar").autofocus


def test_o16_tambien_en_eliminar_de_ajustes(app):
    ir(app, "Ajustes")
    categorias = app.pantalla("Ajustes").listas[0]
    [mercado] = [t for t in categorias.lista.controls if t.title.value == "Mercado"]
    clic(mercado, "Eliminar")
    assert boton(dialogo_arriba(app), "Cancelar").autofocus is True


# ---------------------------------------------------------------------------
# BUG-06 y BUG-08
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("cantidad", "texto"), [(1, "TOTAL (1 gasto)"), (2, "TOTAL (2 gastos)")]
)
def test_bug06_total_singular_y_plural(app, con, cantidad, texto):
    for i in range(cantidad):
        gastos.agregar_gasto(con, app.mes_id, f"Gasto {i}", _otros(con), 100, "fijo")
    app.refrescar()
    assert filas_tabla(app.pantalla("Gastos"))[-1]["Nombre"] == texto


def test_bug08_eliminar_que_paso_a_estar_en_uso_avisa_archivado(app, con, pagina):
    # La lista mostraba "Eliminar", pero al confirmar ya estaba en uso: la lógica lo
    # archiva y el aviso dice "archivado" (con Deshacer), no "eliminado".
    ir(app, "Ajustes")
    categorias = app.pantalla("Ajustes").listas[0]
    [mercado] = [t for t in categorias.lista.controls if t.title.value == "Mercado"]
    clic(mercado, "Eliminar")
    gastos.agregar_gasto(
        con,
        app.mes_id,
        "X",
        id_por_nombre(con, catalogos.CATEGORIAS, "Mercado"),
        100,
        "fijo",
    )
    clic(dialogo_arriba(app), "Eliminar")
    aviso = pagina.ultimo_aviso()
    assert aviso.content.value == '"Mercado" archivado'
    assert aviso.action == "Deshacer"
    assert '"Mercado" eliminado' not in pagina.avisos()


def test_bug08_desarchivar_algo_que_ya_no_existe_no_avisa_exito(app, con, pagina):
    ir(app, "Ajustes")
    categorias = app.pantalla("Ajustes").listas[0]
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    gastos.agregar_gasto(con, app.mes_id, "X", gym, 100, "fijo")
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    categorias.mostrar_archivados.value = True
    categorias.refrescar()
    [tile] = [t for t in categorias.lista.controls if t.title.value == "Gym"]
    # Se borra de la base "por detrás" (simula una lista vieja).
    with con:
        con.execute("DELETE FROM gastos WHERE categoria_id = ?", (gym,))
        con.execute("DELETE FROM categorias WHERE id = ?", (gym,))
    clic(tile, "Desarchivar")
    assert pagina.avisos()[-1] == "Ese elemento ya no existe."
    assert not any("vuelve a aparecer" in a for a in pagina.avisos())
