"""Pruebas de la pantalla Gastos, el diálogo de gasto y la confirmación de borrado
(RF-06 a RF-09; diseno.md §3.3, §4.1, §2.4, §2.5). Sin abrir ventanas."""

import flet as ft
import pytest

from app.interfaz import estilos
from app.logica import catalogos, gastos
from tests.ayudantes import id_por_nombre, insertar_pago, insertar_plan
from tests.ayudantes_interfaz import (
    boton,
    celda,
    clic,
    columna,
    de_tipo,
    dialogo_arriba,
    dialogo_gasto_abierto,
    filas_tabla,
    hay_boton,
    item_menu,
    textos,
    titulo_dialogo,
    titulos,
)


@pytest.fixture
def pantalla(app):
    return app.pantalla("Gastos")


def _cat(con, nombre):
    return id_por_nombre(con, catalogos.CATEGORIAS, nombre)


def _medio(con, nombre):
    return id_por_nombre(con, catalogos.MEDIOS_PAGO, nombre)


def _cargar_por_dialogo(
    app, pantalla, nombre, categoria_id, monto, tipo="fijo", medio=None
):
    """Abre "Agregar gasto", completa el diálogo y toca Guardar."""
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = nombre
    d.categoria.value = str(categoria_id)
    d.monto.value = monto
    d.tipo.selected = [tipo]
    if medio is not None:
        d.medio.value = str(medio)
    d._guardar()
    return d


def _agregar(
    con, mes_id, nombre, categoria="Otros", monto=3000000, tipo="fijo", medio=None
):
    return gastos.agregar_gasto(
        con, mes_id, nombre, _cat(con, categoria), monto, tipo, medio
    )


def _nombres_en_tabla(pantalla):
    return [fila["Nombre"] for fila in filas_tabla(pantalla)[:-1]]


# ---------------------------------------------------------------------------
# Pantalla Gastos (§3.3)
# ---------------------------------------------------------------------------


def test_estado_vacio_con_boton(app, pantalla):
    # §3.3: sin gastos, texto + botón "Agregar gasto (Ctrl+N)"; sin tabla ni totales.
    assert pantalla.titulo.value == "Gastos de Octubre 2026"
    assert "Todavía no cargaste gastos en Octubre 2026." in textos(pantalla.cuerpo)
    assert de_tipo(pantalla.cuerpo, ft.DataTable) == []
    clic(pantalla.cuerpo, "Agregar gasto (Ctrl+N)")
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo gasto – Octubre 2026"


def test_boton_agregar_gasto_del_encabezado(app, pantalla):
    clic(pantalla.control, "Agregar gasto")
    assert titulo_dialogo(dialogo_arriba(app)) == "Nuevo gasto – Octubre 2026"


GASTOS_PLANILLA = [
    ("Alquiler", "Vivienda", "260.000"),
    ("Servicios", "Servicios", "82.000"),
    ("Seguro de moto", "Transporte", "131.000"),
    ("Mercado", "Mercado", "150.000"),
    ("Nafta", "Transporte", "30.000"),
    ("Teléfono", "Servicios", "20.000"),
    ("Internet", "Servicios", "38.700"),
    ("Psicólogo", "Salud", "140.000"),
]


def test_ca_09_1_ocho_gastos_cargados_por_dialogo(app, pantalla, con, pagina):
    # CA-09.1 en pantalla: los 8 gastos de la planilla dan "$ 851.700" y "TOTAL (8 gastos)".
    for nombre, categoria, monto in GASTOS_PLANILLA:
        _cargar_por_dialogo(app, pantalla, nombre, _cat(con, categoria), monto)
    filas = filas_tabla(pantalla)
    assert len(filas) == 9
    total = filas[-1]
    assert total["Nombre"] == "TOTAL (8 gastos)"
    assert total["Monto"] == "$ 851.700"
    assert pagina.avisos()[0] == 'Gasto "Alquiler" agregado'
    assert app.hay_dialogo_abierto() is False


def test_ca_09_2_total_se_redondea_desde_el_exacto(app, pantalla, con):
    # CA-09.2 en pantalla: 0,40 + 0,40 + 0,40 → total "$ 1".
    for _ in range(3):
        _cargar_por_dialogo(
            app, pantalla, "Chicle", _cat(con, "Otros"), "0,40", "unico"
        )
    assert filas_tabla(pantalla)[-1]["Monto"] == "$ 1"


def test_columnas_de_la_tabla(app, pantalla, con, mes_id):
    # §3.3 (paso 2): Pag., Nombre, Categoría, Tipo, Medio de pago, Monto, Pagado,
    # Pendiente (+ acciones). Los tres montos son numéricos (alineados a la derecha).
    _agregar(con, mes_id, "Nafta", "Transporte", 3000000, "unico")
    app.refrescar()
    tabla = de_tipo(pantalla.cuerpo, ft.DataTable)[0]
    assert titulos(pantalla) == [
        "Pag.",
        "Nombre",
        "Categoría",
        "Tipo",
        "Medio de pago",
        "Monto",
        "Pagado",
        "Pendiente",
        "",
    ]
    for titulo in ("Monto", "Pagado", "Pendiente"):
        assert tabla.columns[columna(pantalla, titulo)].numeric is True
    fila = filas_tabla(pantalla)[0]
    assert {
        k: fila[k] for k in ("Nombre", "Categoría", "Tipo", "Medio de pago", "Monto")
    } == {
        "Nombre": "Nafta",
        "Categoría": "Transporte",
        "Tipo": "Único",
        "Medio de pago": "—",
        "Monto": "$ 30.000",
    }


def test_orden_fijos_cuotas_unicos_y_por_nombre(app, pantalla, con, mes_id):
    # §3.3: primero fijos, luego cuotas, luego únicos; dentro de cada grupo por nombre
    # (sin distinguir mayúsculas).
    _agregar(con, mes_id, "Zapatillas", tipo="unico")
    _agregar(con, mes_id, "Zeta", tipo="fijo")
    _agregar(con, mes_id, "alquiler", tipo="fijo")
    _agregar(con, mes_id, "Bicicleta", tipo="unico")
    plan = insertar_plan(con, "Heladera", _cat(con, "Otros"))
    with con:
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, plan_cuotas_id) "
            "VALUES (?, 'Heladera', ?, 1000000, 'cuota', ?)",
            (mes_id, _cat(con, "Otros"), plan),
        )
    app.refrescar()
    assert _nombres_en_tabla(pantalla) == [
        "alquiler",
        "Zeta",
        "Heladera",
        "Bicicleta",
        "Zapatillas",
    ]
    assert [f["Tipo"] for f in filas_tabla(pantalla)[:-1]] == [
        "Fijo",
        "Fijo",
        "Cuota 3/6",
        "Único",
        "Único",
    ]


def test_orden_por_nombre_ignora_acentos(app, pantalla, con, mes_id):
    # Igual que las listas de Ajustes (O5): "Ómnibus" va entre "Nafta" y "Psicólogo".
    for nombre in ["Psicólogo", "Ómnibus", "Nafta"]:
        _agregar(con, mes_id, nombre)
    app.refrescar()
    assert _nombres_en_tabla(pantalla) == ["Nafta", "Ómnibus", "Psicólogo"]


def test_total_con_un_solo_gasto_en_singular(app, pantalla, con, mes_id):
    # Con un gasto la fila de total debería decir "TOTAL (1 gasto)", no "1 gastos".
    _agregar(con, mes_id, "Nafta")
    app.refrescar()
    assert filas_tabla(pantalla)[-1]["Nombre"] == "TOTAL (1 gasto)"


def test_categoria_y_medio_archivados_en_texto_secundario(app, pantalla, con, mes_id):
    # §3.3: categoría/medio archivados se ven en texto secundario con tooltip.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 2500000, "fijo", visa)
    _agregar(con, mes_id, "Nafta", "Transporte", medio=_medio(con, "Efectivo"))
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    app.refrescar()

    categoria = celda(pantalla, "Cuota gym", "Categoría").content
    medio = celda(pantalla, "Cuota gym", "Medio de pago").content
    assert (categoria.value, categoria.color, categoria.tooltip) == (
        "Gym",
        estilos.TEXTO_SECUNDARIO,
        "Categoría archivada",
    )
    assert (medio.value, medio.color, medio.tooltip) == (
        "Visa Santander",
        estilos.TEXTO_SECUNDARIO,
        "Medio de pago archivado",
    )
    assert celda(pantalla, "Nafta", "Categoría").content.color is None
    assert celda(pantalla, "Nafta", "Medio de pago").content.color is None


def test_menu_de_fila_editar_y_borrar(app, pantalla, con, mes_id):
    # §3.3 (paso 2): menú de acciones Editar · Registrar pago · Ver pagos · Borrar.
    _agregar(con, mes_id, "Nafta")
    app.refrescar()
    menu = celda(pantalla, "Nafta", "").content
    assert isinstance(menu, ft.PopupMenuButton)
    assert menu.tooltip == "Acciones"
    assert [i.content for i in menu.items] == [
        "Editar",
        "Registrar pago",
        "Ver pagos",
        "Borrar",
    ]

    item_menu(pantalla, "Nafta", "Editar").on_click(None)
    assert titulo_dialogo(dialogo_arriba(app)) == "Editar gasto – Octubre 2026"
    app.cerrar_dialogo(dialogo_arriba(app))

    item_menu(pantalla, "Nafta", "Borrar").on_click(None)
    assert titulo_dialogo(dialogo_arriba(app)) == "¿Borrar el gasto Nafta?"


def test_clic_en_el_nombre_abre_editar(app, pantalla, con, mes_id):
    # §2.5: clic en el nombre (DataCell.on_tap) abre "Editar".
    _agregar(con, mes_id, "Nafta")
    app.refrescar()
    celda(pantalla, "Nafta", "Nombre").on_tap(None)
    d = dialogo_gasto_abierto(app)
    assert d.nombre.value == "Nafta"


def test_con_varias_filas_cada_menu_edita_su_gasto(app, pantalla, con, mes_id):
    # Cada fila abre su propio gasto (no el último de la lista).
    _agregar(con, mes_id, "Alquiler")
    _agregar(con, mes_id, "Nafta")
    app.refrescar()
    item_menu(pantalla, "Alquiler", "Editar").on_click(None)
    assert dialogo_gasto_abierto(app).nombre.value == "Alquiler"


# ---------------------------------------------------------------------------
# Confirmación de borrado (CA-08.1 en pantalla)
# ---------------------------------------------------------------------------


def test_ca_08_1_cancelar_no_borra(app, pantalla, con, mes_id):
    gid = _agregar(con, mes_id, "Nafta")
    app.refrescar()
    pantalla.borrar(gid)
    confirmacion = dialogo_arriba(app)
    assert (
        "Se borran también sus pagos ($ 0 pagado). Esta acción no se puede deshacer."
        in (textos(confirmacion))
    )
    clic(confirmacion, "Cancelar")
    assert confirmacion.open is False
    assert gastos.obtener_gasto(con, gid) is not None
    assert _nombres_en_tabla(pantalla) == ["Nafta"]


def test_ca_08_1_borrar_borra_y_recalcula(app, pantalla, con, mes_id, pagina):
    # Al confirmar desaparece con sus pagos, el total se recalcula y hay aviso.
    gid = _agregar(con, mes_id, "Nafta", monto=18000000)
    _agregar(con, mes_id, "Alquiler", monto=26000000)
    insertar_pago(con, gid, 6000000)
    app.refrescar()
    pantalla.borrar(gid)
    confirmacion = dialogo_arriba(app)
    assert any("($ 60.000 pagado)" in t for t in textos(confirmacion))
    boton_borrar = boton(confirmacion, "Borrar")
    assert boton_borrar.style.bgcolor == "#B3261E"  # negativo, tema claro
    boton_borrar.on_click(None)
    assert gastos.obtener_gasto(con, gid) is None
    assert gastos.total_pagado(con, gid) == 0
    assert _nombres_en_tabla(pantalla) == ["Alquiler"]
    assert filas_tabla(pantalla)[-1]["Monto"] == "$ 260.000"
    assert pagina.avisos()[-1] == 'Gasto "Nafta" borrado'
    assert app.hay_dialogo_abierto() is False


def test_borrar_el_ultimo_vuelve_al_estado_vacio(app, pantalla, con, mes_id):
    gid = _agregar(con, mes_id, "Nafta")
    app.refrescar()
    pantalla.borrar(gid)
    clic(dialogo_arriba(app), "Borrar")
    assert "Todavía no cargaste gastos en Octubre 2026." in textos(pantalla.cuerpo)


# ---------------------------------------------------------------------------
# Diálogo de gasto (§4.1)
# ---------------------------------------------------------------------------


def test_dialogo_nuevo_valores_iniciales(app, pantalla, con, mes_id):
    # §4.1: tipo "Fijo mensual" por defecto; medio "Sin medio de pago" primero;
    # categoría sin elegir; sin botón Borrar; Nombre con autofocus.
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    assert d.tipo.selected == ["fijo"]
    assert d.categoria.value is None
    assert d.medio.value == "ninguno"
    assert d.medio.options[0].text == "Sin medio de pago"
    assert d.nombre.autofocus is True
    assert d.nombre.max_length == 60
    assert not hay_boton(d.dialogo, "Borrar")
    assert [o.text for o in d.categoria.options] == [
        r["nombre"] for r in catalogos.listar(con, catalogos.CATEGORIAS)
    ]


def test_dialogo_errores_todos_juntos(app, pantalla, con):
    # §2.5: sin nombre, sin categoría y sin monto: los tres errores a la vez; no se cierra.
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d._guardar()
    assert d.nombre.error == "Ingresá un nombre."
    assert d.categoria.error_text == "Elegí una categoría."
    assert d.monto.error == "Ingresá un monto."
    assert app._dialogos == [d.dialogo]
    assert gastos.listar_gastos(con, app.mes_id) == []


@pytest.mark.parametrize(
    ("monto", "mensaje"),
    [
        ("66020.12", "Usá coma para los decimales. Ej.: 66.020,12"),
        ("0", "El monto tiene que ser mayor a 0."),
        ("66020,123", "Usá como máximo 2 decimales."),
        ("1.000.000.000.000", "El monto es demasiado grande."),
    ],
)
def test_dialogo_monto_invalido_muestra_mensaje(app, pantalla, con, monto, mensaje):
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Nafta"
    d.categoria.value = str(_cat(con, "Transporte"))
    d.monto.value = monto
    d._guardar()
    assert d.monto.error == mensaje
    assert app.hay_dialogo_abierto() is True
    assert gastos.listar_gastos(con, app.mes_id) == []


def test_corregir_y_volver_a_guardar_limpia_los_errores(app, pantalla, con):
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d._guardar()
    d.nombre.value = "Nafta"
    d.categoria.value = str(_cat(con, "Transporte"))
    d.monto.value = "30.000"
    d._guardar()
    assert (d.nombre.error, d.categoria.error_text, d.monto.error) == (None, None, None)
    assert app.hay_dialogo_abierto() is False


@pytest.mark.parametrize(
    ("escrito", "queda"),
    [
        ("66020,5", "66.020,50"),
        ("66020", "66.020"),
        ("1434617,1", "1.434.617,10"),
        ("66020.12", "66020.12"),  # inválido: se deja como está
        ("", ""),
    ],
)
def test_campo_monto_se_reescribe_al_salir(app, pantalla, escrito, queda):
    # §2.4: al salir del campo, un valor válido se reescribe prolijo.
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d.monto.value = escrito
    d.monto.on_blur(None)
    assert d.monto.value == queda


def test_campo_monto_configuracion(app, pantalla):
    # §2.4: prefijo "$ ", sufijo ARS, alineado a la derecha, filtro de 0-9 . ,
    pantalla.nuevo()
    m = dialogo_gasto_abierto(app).monto
    assert (m.prefix, m.suffix, m.text_align) == ("$ ", "ARS", ft.TextAlign.RIGHT)
    assert m.input_filter.regex_string == r"[0-9.,]"
    assert m.hint_text == "Ej.: 66.020,12"


def test_alta_completa_con_medio_y_pago_unico(app, pantalla, con, pagina):
    # RF-06 en pantalla: se guarda, se cierra, aparece en la tabla y avisa.
    d = _cargar_por_dialogo(
        app,
        pantalla,
        "  Nafta  ",
        _cat(con, "Transporte"),
        "30.000",
        "unico",
        _medio(con, "Efectivo"),
    )
    fila = gastos.listar_gastos(con, app.mes_id)[0]
    assert (fila["nombre"], fila["monto_cent"], fila["tipo"], fila["medio_pago"]) == (
        "Nafta",
        3000000,
        "unico",
        "Efectivo",
    )
    assert d.dialogo.open is False
    assert pagina.avisos()[-1] == 'Gasto "Nafta" agregado'
    assert _nombres_en_tabla(pantalla) == ["Nafta"]


def test_enter_en_nombre_o_monto_guarda(app, pantalla, con):
    # §2.5: Enter guarda (on_submit en los campos de texto).
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Nafta"
    d.categoria.value = str(_cat(con, "Transporte"))
    d.monto.value = "30.000"
    d.monto.on_submit(None)
    assert len(gastos.listar_gastos(con, app.mes_id)) == 1


def test_cancelar_no_cambia_nada(app, pantalla, con, pagina):
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Nafta"
    d.categoria.value = str(_cat(con, "Transporte"))
    d.monto.value = "30.000"
    clic(d.dialogo, "Cancelar")
    assert d.dialogo.open is False
    assert app.hay_dialogo_abierto() is False
    assert gastos.listar_gastos(con, app.mes_id) == []
    assert pagina.avisos() == []


def test_ca_06_5_alta_no_ofrece_categoria_ni_medio_archivados(
    app, pantalla, con, mes_id
):
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 100, "fijo", visa)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    assert not any("Gym" in o.text for o in d.categoria.options)
    assert not any("Visa" in o.text for o in d.medio.options)


def test_categoria_nueva_en_linea(app, pantalla, con):
    # §4.1: "+" muestra la fila dentro del diálogo; al agregar queda seleccionada.
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    assert d.fila_nueva_categoria.visible is False
    [mas] = [
        b for b in de_tipo(d.dialogo, ft.IconButton) if b.tooltip == "Nueva categoría"
    ]
    mas.on_click(None)
    assert d.fila_nueva_categoria.visible is True
    d.nueva_categoria.value = "Educación"
    clic(d.fila_nueva_categoria, "Agregar")
    nueva = _cat(con, "Educación")
    assert d.categoria.value == str(nueva)
    assert "Educación" in [o.text for o in d.categoria.options]
    assert d.fila_nueva_categoria.visible is False
    assert d.nueva_categoria.value == ""
    assert app._dialogos == [d.dialogo]  # no abre otro diálogo


@pytest.mark.parametrize(
    ("nombre", "mensaje"),
    [
        ("salud", 'Ya existe una categoría llamada "Salud".'),
        ("  ", "Ingresá un nombre."),
    ],
)
def test_categoria_nueva_repetida_o_vacia_da_error(app, pantalla, con, nombre, mensaje):
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d._mostrar_nueva_categoria(None)
    d.nueva_categoria.value = nombre
    d._agregar_categoria(None)
    assert d.nueva_categoria.error
    if mensaje:
        assert d.nueva_categoria.error == mensaje
    assert d.fila_nueva_categoria.visible is True
    assert len(catalogos.listar(con, catalogos.CATEGORIAS)) == 7


def test_sin_categorias_la_fila_aparece_abierta(app, pantalla, con):
    # §4.1: sin categorías, la fila de nueva categoría aparece abierta con el aviso.
    for fila in catalogos.listar(con, catalogos.CATEGORIAS):
        catalogos.eliminar(con, catalogos.CATEGORIAS, fila["id"])
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    assert d.aviso_sin_categorias.visible is True
    assert (
        d.aviso_sin_categorias.value == "Todavía no tenés categorías. Creá la primera."
    )
    assert d.fila_nueva_categoria.visible is True


def test_edicion_precarga_los_datos(app, pantalla, con, mes_id):
    efectivo = _medio(con, "Efectivo")
    gid = _agregar(con, mes_id, "Servicios", "Servicios", 6602012, "unico", efectivo)
    pantalla.editar(gid)
    d = dialogo_gasto_abierto(app)
    assert titulo_dialogo(d.dialogo) == "Editar gasto – Octubre 2026"
    assert d.nombre.value == "Servicios"
    assert d.categoria.value == str(_cat(con, "Servicios"))
    assert d.monto.value == "66.020,12"
    assert d.tipo.selected == ["unico"]
    assert d.medio.value == str(efectivo)
    assert hay_boton(d.dialogo, "Borrar")


def test_edicion_sin_medio_precarga_sin_medio(app, pantalla, con, mes_id):
    gid = _agregar(con, mes_id, "Nafta")
    pantalla.editar(gid)
    assert dialogo_gasto_abierto(app).medio.value == "ninguno"


def test_edicion_ofrece_archivados_con_sufijo_y_permite_guardar(
    app, pantalla, con, mes_id, pagina
):
    # §4.1: la categoría y el medio archivados ya asignados aparecen con sufijo.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    gid = gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 2500000, "fijo", visa)
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    catalogos.eliminar(con, catalogos.MEDIOS_PAGO, visa)
    pantalla.editar(gid)
    d = dialogo_gasto_abierto(app)
    assert "Gym (archivada)" in [o.text for o in d.categoria.options]
    assert "Visa Santander (archivado)" in [o.text for o in d.medio.options]
    assert (d.categoria.value, d.medio.value) == (str(gym), str(visa))
    d.monto.value = "28.000"
    d._guardar()
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 2800000
    assert pagina.avisos()[-1] == 'Gasto "Cuota gym" actualizado'


def test_categoria_nueva_en_edicion_conserva_el_archivado_ofrecido(
    app, pantalla, con, mes_id
):
    # Crear una categoría en línea al editar no hace perder la opción archivada del gasto.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    gid = gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 2500000, "fijo")
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    pantalla.editar(gid)
    d = dialogo_gasto_abierto(app)
    d.nueva_categoria.value = "Deportes"
    d._agregar_categoria(None)
    assert "Gym (archivada)" in [o.text for o in d.categoria.options]


def test_rn_23_mensaje_nuevo_y_luego_acepta(app, pantalla, con, mes_id, pagina):
    # CA-07.2 en pantalla: 180.000 con 60.000 pagados; 50.000 se rechaza con el mensaje
    # nuevo en el campo Monto; 100.000 se acepta.
    gid = _agregar(con, mes_id, "Seguro", monto=18000000)
    insertar_pago(con, gid, 6000000)
    pantalla.editar(gid)
    d = dialogo_gasto_abierto(app)
    d.monto.value = "50.000"
    d._guardar()
    assert (
        d.monto.error
        == "No podés bajar el monto a menos de lo que ya pagaste ($ 60.000)."
    )
    assert app.hay_dialogo_abierto() is True
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 18000000
    d.monto.value = "100.000"
    d._guardar()
    assert gastos.obtener_gasto(con, gid)["monto_cent"] == 10000000
    assert pagina.avisos()[-1] == 'Gasto "Seguro" actualizado'


def test_error_de_la_logica_va_al_campo_indicado(app, pantalla, con):
    # Si la categoría se archiva con el diálogo abierto, el error va debajo de Categoría.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    pantalla.nuevo()
    d = dialogo_gasto_abierto(app)
    d.nombre.value = "Cuota gym"
    d.categoria.value = str(gym)
    d.monto.value = "25.000"
    # Se archiva "por otro lado": se usa en un gasto y se elimina.
    gastos.agregar_gasto(con, app.mes_id, "Otro", gym, 100, "fijo")
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    d._guardar()
    assert d.categoria.error_text == "La categoría elegida está archivada."
    assert d.monto.error is None


def test_borrar_desde_edicion_abre_la_confirmacion(app, pantalla, con, mes_id):
    # §4.1: "Borrar" cierra el diálogo de edición y abre la confirmación.
    gid = _agregar(con, mes_id, "Nafta")
    pantalla.editar(gid)
    d = dialogo_gasto_abierto(app)
    clic(d.dialogo, "Borrar")
    assert d.dialogo.open is False
    assert len(app._dialogos) == 1
    assert titulo_dialogo(dialogo_arriba(app)) == "¿Borrar el gasto Nafta?"
    clic(dialogo_arriba(app), "Borrar")
    assert gastos.obtener_gasto(con, gid) is None


def test_error_inesperado_al_guardar(app, pantalla, con, monkeypatch):
    # §2.5: falla técnica → se cierra el diálogo y aparece "No se pudo guardar".
    def falla(*args, **kwargs):
        raise RuntimeError("base bloqueada (inventado)")

    monkeypatch.setattr(gastos, "agregar_gasto", falla)
    d = _cargar_por_dialogo(app, pantalla, "Nafta", _cat(con, "Transporte"), "30.000")
    assert d.dialogo.open is False
    assert titulo_dialogo(dialogo_arriba(app)) == "No se pudo guardar"
