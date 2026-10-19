"""Pruebas de los pasos 8c y 8d de la importación de Excel: la lista de revisión en
pantalla y la edición (RF-51 a RF-56, RN-61 a RN-75, RN-78; CA-51.x a CA-56.x;
docs/diseno.md §3.12, §4.9, §4.10 y §4.11).

Sin ventanas: página falsa y los handlers de los controles se llaman a mano, igual que
hace Flet. El archivo se lee con PantallaImportar.leer_archivo (sin selector).

Base de prueba (la de los CA): hoy = 2026-10-14, existe solo 2026-10 con sueldo 1.200,
cotización 1.600 y el gasto fijo "Alquiler" 260.000 (Vivienda); personas Sofía y Marsu;
categoría Varios. Los .xlsx salen de tests/ayudantes_excel.py con datos inventados
(nunca de datos-privados/).
"""

import ast
import asyncio
import pathlib
from datetime import date
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz.aplicacion import Aplicacion
from app.logica import catalogos, cuotas, gastos, me_deben, meses
from app.logica import revision_importacion as rev
from app.logica.revision_importacion import Nueva
from tests.ayudantes import insertar_mes
from tests.ayudantes_excel import (
    a_bytes,
    armar_libro,
    celdas_planilla,
    planilla_con,
    planilla_prueba,
    xlsx,
)
from tests.ayudantes_interfaz import (
    boton,
    clic,
    de_tipo,
    dialogo_arriba,
    hay_boton,
    ir,
    tecla,
    textos,
)

NEGATIVO = "#B3261E"
HOY = date(2026, 10, 14)


class FechaFija(date):
    @classmethod
    def today(cls):
        return cls(2026, 10, 14)


@pytest.fixture(autouse=True)
def hoy_fijo(monkeypatch):
    """Fija "hoy" en 2026-10-14 para la lista (ListaRevision) y para el "mes actual"."""
    original = meses.mes_actual_calendario
    monkeypatch.setattr(
        meses,
        "mes_actual_calendario",
        lambda hoy=None: (2026, 10) if hoy is None else original(hoy),
    )
    monkeypatch.setattr(rev, "date", FechaFija)


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


@pytest.fixture
def base(con, mes_id):
    """La base de los CA: 2026-10 con Alquiler (Vivienda), Sofía, Marsu y Varios."""
    ids = {c["nombre"]: c["id"] for c in catalogos.listar(con, catalogos.CATEGORIAS)}
    varios = catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    gastos.agregar_gasto(con, mes_id, "Alquiler", ids["Vivienda"], 26000000, "fijo")
    return SimpleNamespace(
        con=con,
        mes_id=mes_id,
        varios=varios,
        vivienda=ids["Vivienda"],
        servicios=ids["Servicios"],
        salud=ids["Salud"],
        sofia=sofia,
        marsu=marsu,
    )


@pytest.fixture
def base_sin_varios(con, mes_id):
    """Igual que base pero sin la categoría "Varios" (CA-54.3)."""
    ids = {c["nombre"]: c["id"] for c in catalogos.listar(con, catalogos.CATEGORIAS)}
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    gastos.agregar_gasto(con, mes_id, "Alquiler", ids["Vivienda"], 26000000, "fijo")
    return SimpleNamespace(
        con=con,
        mes_id=mes_id,
        vivienda=ids["Vivienda"],
        servicios=ids["Servicios"],
        sofia=sofia,
        marsu=marsu,
    )


@pytest.fixture
def app_rev(base, pagina, con):
    """Aplicación armada sobre la base de los CA (la base se arma antes)."""
    aplicacion = Aplicacion(pagina, con)
    aplicacion.iniciar()
    return aplicacion


@pytest.fixture
def app_sin_varios(base_sin_varios, pagina, con):
    aplicacion = Aplicacion(pagina, con)
    aplicacion.iniciar()
    return aplicacion


def leer(pantalla, nombre, contenido):
    asyncio.run(pantalla.leer_archivo(nombre, contenido, None))


def abrir(app, contenido=None, nombre="planilla-prueba.xlsx"):
    """Abre la importación desde Ajustes y lee el archivo: devuelve la PantallaImportar."""
    ir(app, "Ajustes")
    ajustes = app.pantalla("Ajustes")
    ajustes.pestanas.selected_index = ajustes.indice_de(ajustes.importar)
    clic(ajustes.importar.control, "Importar Excel")
    p = app._importacion
    leer(p, nombre, contenido or planilla_prueba())
    return p


def evento(control):
    return SimpleNamespace(control=control)


def fv(p, nombre, fila_excel=None):
    """La FilaVista con ese nombre (y, si se indica, en esa fila del Excel)."""
    hallazgos = [
        f
        for f in p.vista.filas
        if f.fila.nombre == nombre
        and (fila_excel is None or f.fila.origen.fila_excel == fila_excel)
    ]
    assert len(hallazgos) == 1, (
        f"{nombre!r} (fila {fila_excel}): {len(hallazgos)} filas"
    )
    return hallazgos[0]


def sin_nombre(p, fila_excel):
    hallazgos = [
        f
        for f in p.vista.filas
        if f.fila.nombre is None and f.fila.origen.fila_excel == fila_excel
    ]
    assert hallazgos
    return hallazgos[0]


def tildar(f, valor):
    f.tilde.value = valor
    f.tilde.on_change(evento(f.tilde))


def elegir_tipo(f, tipo):
    f.tipo.value = tipo
    f.tipo.on_select(evento(f.tipo))


def cobrado(f, valor):
    f.cobrado.value = valor
    f.cobrado.on_change(evento(f.cobrado))


def notas(f):
    return textos(f.notas)


def iconos(f):
    return [i.icon for i in de_tipo(f.notas, ft.Icon)]


def bloque(p, titulo):
    for b in p.vista.bloques + (
        [p.vista.bloque_incompletas] if p.vista.bloque_incompletas else []
    ):
        if b.titulo == titulo:
            return b
    raise AssertionError(f"No hay bloque {titulo!r}")


def subtitulo(b):
    return " ".join(textos(b.subtitulo))


def menu_bloque(b, texto):
    menu = de_tipo(b.control.title, ft.PopupMenuButton)[0]
    [item] = [i for i in menu.items if i.content == texto]
    item.on_click(None)


def filtrar(p, filtro):
    sel = p.vista.selector_filtro
    sel.selected = [filtro]
    sel.on_change(evento(sel))


def etiquetas_filtro(p):
    return {s.value: s.label.value for s in p.vista.selector_filtro.segments}


def visibles(p):
    return [f.fila.nombre for f in p.vista.filas if f.control.visible]


def abrir_fila(p, f):
    """Abre el diálogo §4.9 de esa fila; devuelve (AlertDialog, DialogoFilaImportacion)."""
    f.lapiz.on_click(None)
    d = dialogo_arriba(p.app)
    return d, boton(d, "Aceptar").on_click.__self__


def aceptar(dlg):
    dlg._aceptar()


def abrir_bloque(p, titulo):
    menu_bloque(bloque(p, titulo), "Cambiar tipo o categoría de todas...")
    d = dialogo_arriba(p.app)
    return d, boton(
        d, [t for t in textos(d) if t.startswith("Aplicar")][0]
    ).on_click.__self__


def clave_cat(id_):
    return f"id:{id_}"


def archivar(con, tabla, id_):
    """Archiva una categoría o persona a mano (la lógica no tiene función para esto)."""
    with con:
        con.execute(f"UPDATE {tabla} SET archivado = 1 WHERE id = ?", (id_,))


def foto(con):
    tablas = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {
        t: [tuple(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY 1")]
        for t in tablas
    }


def cargar_primera_importacion(b):
    """Deja en la base lo que dejaría importar planilla-prueba.xlsx una vez (CA-56.4)."""
    for nombre, monto in [
        ("Servicios", 8200000),
        ("Internet", 3870000),
        ("psicologo", 14000000),
        ("Monotributo 66.020,12", 6602012),
        ("Gym", 5000000),
    ]:
        gastos.agregar_gasto(b.con, b.mes_id, nombre, b.varios, monto, "fijo")
    cuotas.crear_plan(
        b.con,
        "Avant Service cuota 3/ 3 $41.116,66",
        b.varios,
        None,
        4111666,
        3,
        2026,
        8,
        hoy=HOY,
    )
    for persona, descripcion, monto in [
        (b.sofia, "Prestamo MP", 2000000),
        (b.sofia, "Internet", 1290000),
        (b.marsu, "tacones chiqui baby", 678500),
    ]:
        me_deben.agregar_item(b.con, persona, descripcion, monto, HOY)


# ---------------------------------------------------------------------------
# CA-51.1, CA-51.2, CA-51.7, CA-52.1: la lista esperada en pantalla
# ---------------------------------------------------------------------------

# (fila Excel, nombre, tipo, tilde, monto mostrado, categoría o persona, cuota)
ESPERADA = {
    "Gasto del Mes": [
        (3, "Alquiler", "fijo", False, "$ 260.000", "Varios", "-"),
        (4, "Servicios", "fijo", True, "$ 82.000", "Varios", "-"),
        (5, "Internet", "fijo", True, "$ 38.700", "Varios", "-"),
        (6, "Tarjetas de Credito", "ignorar", False, "$ 582.917", "", "-"),
        (7, "psicologo", "fijo", True, "$ 140.000", "Varios", "-"),
    ],
    "Deudas": [
        (12, "Monotributo 66.020,12", "fijo", True, "$ 66.020", "Varios", "-"),
        (
            13,
            "Avant Service cuota 3/ 3 $41.116,66",
            "cuota",
            True,
            "$ 41.117",
            "Varios",
            "3/3",
        ),
        (15, "Gym", "fijo", True, "$ 50.000", "Varios", "-"),
    ],
    "Deudas sofia": [
        (22, "Prestamo MP", "me_deben", True, "$ 20.000", "Sofía", "-"),
        (23, "Internet", "me_deben", True, "$ 12.900", "Sofía", "-"),
        (24, "Total", "ignorar", False, "$ 32.900", "", "-"),
    ],
    "Marsu": [
        (27, "tacones chiqui baby", "me_deben", True, "$ 6.785", "Marsu", "-"),
        (28, "Total", "ignorar", False, "$ 6.785", "", "-"),
    ],
}


def test_los_cuatro_bloques_en_orden_y_las_13_filas_esperadas(app_rev):
    # CA-51.1 + CA-51.7 + CA-52.1: bloques en el orden del Excel, cada fila con su número de
    # fila, tipo, tilde, monto, categoría o persona y cuota. Sin "Otras filas" ni bloques vacíos.
    p = abrir(app_rev)
    assert [b.titulo for b in p.vista.bloques] == list(ESPERADA)
    for b in p.vista.bloques:
        obtenido = [
            (
                f.fila.origen.fila_excel,
                f.nombre.value,
                f.tipo.value,
                f.tilde.value,
                f.monto.value,
                f.categoria.value,
                f.cuota.value,
            )
            for f in b.filas
        ]
        assert obtenido == ESPERADA[b.titulo], b.titulo


def test_los_titulos_de_los_bloques_se_ven_en_mayusculas(app_rev):
    # §3.12: título del Excel "en mayúsculas visuales".
    p = abrir(app_rev)
    visibles_ = [textos(b.control.title)[0] for b in p.vista.bloques]
    assert visibles_ == ["GASTO DEL MES", "DEUDAS", "DEUDAS SOFIA", "MARSU"]


def test_los_bloques_vienen_abiertos(app_rev):
    # §3.12: todos los bloques de la lista principal vienen abiertos.
    p = abrir(app_rev)
    assert all(b.control.expanded for b in p.vista.bloques)


def test_subtitulos_de_los_bloques(app_rev):
    # §3.12: "filas X a Y · se importan N de M". Con Alquiler "ya existe" (destildada),
    # Gasto del Mes importa 3 de 5 (el boceto del diseño dice 4 porque no tiene esa base).
    p = abrir(app_rev)
    assert subtitulo(bloque(p, "Gasto del Mes")) == "filas 3 a 7 · se importan 3 de 5"
    assert subtitulo(bloque(p, "Deudas")) == "filas 12 a 15 · se importan 3 de 3"
    assert subtitulo(bloque(p, "Deudas sofia")) == "filas 22 a 24 · se importan 2 de 3"
    assert subtitulo(bloque(p, "Marsu")) == "filas 27 a 28 · se importan 1 de 2"


def test_cada_fila_muestra_su_numero_de_fila_del_excel_con_tooltip(app_rev):
    # §3.12 columna "Fila": el número y el tooltip "Fila N del Excel".
    p = abrir(app_rev)
    f = fv(p, "Gym")
    numeros = [
        t for t in de_tipo(f.control, ft.Text) if t.tooltip == "Fila 15 del Excel"
    ]
    assert [t.value for t in numeros] == ["15"]


def test_incompletas_16_filas_plegadas_y_en_ignorar(app_rev):
    # CA-51.2: 16 filas, todas "ignorar", en un grupo plegado al final de la lista.
    p = abrir(app_rev)
    inc = p.vista.bloque_incompletas
    assert len(inc.filas) == 16
    assert inc.control.expanded is False
    assert all(f.tipo.value == "ignorar" for f in inc.filas)
    assert not any(f.tilde.value for f in inc.filas)
    assert subtitulo(inc) == "16 filas · todas se ignoran, salvo que las completes"
    assert p.vista.lista_filas.controls[-2] is inc.control  # antes del "sin resultados"


def test_incompletas_nombres_y_notas(app_rev):
    # CA-51.2: las que tienen nombre dicen "Falta el monto. Se ignora."; las que no
    # tienen, "Falta el nombre. Se ignora." (y se ven como "(sin nombre)").
    p = abrir(app_rev)
    con_nombre = [f for f in p.vista.bloque_incompletas.filas if f.fila.nombre]
    sin = [f for f in p.vista.bloque_incompletas.filas if not f.fila.nombre]
    assert [f.nombre.value for f in con_nombre] == [
        "Gasto del Mes",
        "Gastos",
        "Pagado",
        "total",
        "Falta por pagar",
        "Deudas",
        "Monto",
        "Total deudas",
        "Deuda freezer",
        "Obra social",
        "Sueldo",
        "Deudas sofia",
        "Marsu",
    ]
    assert all(notas(f) == ["Falta el monto. Se ignora."] for f in con_nombre)
    assert len(sin) == 3
    assert [f.monto.value for f in sin] == ["$ 1.103.617", "$ 1.004.917", "$ 1.300"]
    assert all(f.nombre.value == "(sin nombre)" and f.nombre.italic for f in sin)
    assert all(notas(f) == ["Falta el nombre. Se ignora."] for f in sin)
    assert all(f.monto.value != "(sin monto)" for f in sin)


def test_incompletas_incluye_texto_de_ayuda(app_rev):
    # §3.12: el grupo abre con el texto que explica qué son.
    p = abrir(app_rev)
    assert (
        "Son textos sin monto (títulos, encabezados) o montos sin texto (totales). "
        "Si alguna es un dato que querés traer, por ejemplo el sueldo, completala y "
        "cambiale el tipo."
    ) in textos(p.vista.bloque_incompletas.control)


def test_el_66021_de_la_fila_12_no_aparece_en_ningun_lado(app_rev):
    # CA-51.1: el 66021 de "Total deudas" no es una fila ni un pagado.
    p = abrir(app_rev)
    todos = textos(p.vista.control)
    assert not any("66.021" in t for t in todos)


def test_sin_filas_incompletas_no_hay_grupo(app_rev):
    # Un Excel completo no muestra "Filas incompletas".
    p = abrir(app_rev, xlsx({"C3": "Luz", "D3": 1000}))
    assert p.vista.bloque_incompletas is None
    assert not any("INCOMPLETAS" in t.upper() for t in textos(p.vista.lista_filas))


def test_excel_sin_titulos_un_solo_bloque_filas_detectadas(app_rev):
    # CA-51.7 (última frase): sin ningún título, un solo bloque "Filas detectadas".
    p = abrir(app_rev, xlsx({"C3": "Luz", "D3": 1000, "C4": "Gas", "D4": 2000}))
    assert [b.titulo for b in p.vista.bloques] == ["Filas detectadas"]
    assert subtitulo(p.vista.bloques[0]) == "filas 3 a 4 · se importan 2 de 2"


def test_filas_sin_titulo_van_a_otras_filas(app_rev):
    # CA-51.8 (variante): una fila totalmente vacía separa el título; las filas quedan en
    # "Otras filas" y vienen como gasto fijo.
    celdas = celdas_planilla()
    from tests.ayudantes_excel import insertar_fila

    p = abrir(app_rev, xlsx(insertar_fila(celdas, 21)))
    assert "Otras filas" in [b.titulo for b in p.vista.bloques]
    otras = bloque(p, "Otras filas")
    assert [f.tipo.value for f in otras.filas[:2]] == ["fijo", "fijo"]


# ---------------------------------------------------------------------------
# Tilde, tipo y nota de cada fila (RF-52, RN-68, CA-52.7)
# ---------------------------------------------------------------------------


def test_filas_ignoradas_tienen_el_tilde_deshabilitado_con_tooltip(app_rev):
    # §3.12: en "ignorar" el tilde está deshabilitado y sin tilde, con el tooltip del diseño.
    p = abrir(app_rev)
    f = fv(p, "Tarjetas de Credito")
    assert f.tilde.disabled is True and f.tilde.value is False
    assert f.tilde.tooltip == "Esta fila se ignora. Cambiá el tipo para importarla."
    g = fv(p, "Servicios")
    assert g.tilde.disabled is False and g.tilde.tooltip == "Importar esta fila"


def test_filas_apagadas_se_ven_en_color_secundario(app_rev):
    # §3.12: lo que no se importa va en texto secundario (no con opacidad).
    p = abrir(app_rev)
    apagada = fv(p, "Alquiler")  # destildada
    normal = fv(p, "Servicios")
    assert (
        apagada.nombre.color == "onSurfaceVariant"
        and apagada.monto.color == "onSurfaceVariant"
    )
    assert normal.nombre.color is None
    assert apagada.control.opacity in (1, None)


def test_tipo_ofrece_los_seis_tipos_con_sus_textos(app_rev):
    # §3.12: opciones y orden exactos.
    p = abrir(app_rev)
    opciones = [(o.key, o.text) for o in fv(p, "Gym").tipo.options]
    assert opciones == [
        ("fijo", "Gasto fijo"),
        ("unico", "Gasto único"),
        ("cuota", "Cuota"),
        ("me_deben", "Me deben"),
        ("sueldo", "Sueldo (USD)"),
        ("ignorar", "Ignorar"),
    ]


@pytest.mark.parametrize(
    "tipo", ["fijo", "unico", "cuota", "me_deben", "sueldo", "ignorar"]
)
def test_se_puede_cambiar_a_cualquiera_de_los_seis_tipos(app_rev, tipo):
    # CA-52.6: cualquier fila a cualquiera de los seis tipos, sin que reviente.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    elegir_tipo(f, tipo)
    assert f.fila.tipo == tipo and f.tipo.value == tipo


def test_ignorada_pasa_a_gasto_fijo_se_tilda_sola_y_vuelve_a_ignorar_sin_tilde(app_rev):
    # CA-52.7: "Tarjetas de Credito" -> fijo queda tildada; -> ignorar queda sin tilde.
    p = abrir(app_rev)
    f = fv(p, "Tarjetas de Credito")
    elegir_tipo(f, "fijo")
    assert f.tilde.value is True and f.tilde.disabled is False
    assert f.categoria.value == "Varios"
    elegir_tipo(f, "ignorar")
    assert f.tilde.value is False and f.tilde.disabled is True


def test_ignorada_no_se_puede_tildar_desde_la_lista(app_rev):
    # RN-68: una fila ignorada no se puede tildar; si el handler llega igual, no rompe
    # y la fila sigue sin tilde.
    p = abrir(app_rev)
    f = fv(p, "Tarjetas de Credito")
    tildar(f, True)
    assert f.fila.tildada is False and f.tilde.value is False


def test_alquiler_ya_existe_pasos_de_tipo_del_ca_52_7(app_rev):
    # CA-52.7: Alquiler (ya existe, destildada): fijo -> único sigue destildada; pasada a
    # ignorar y después a fijo, queda tildada con la nota "Si la importás, queda repetida.".
    p = abrir(app_rev)
    f = fv(p, "Alquiler")
    elegir_tipo(f, "unico")
    assert f.tilde.value is False
    assert notas(f) == ["Ya existe en Octubre 2026. Viene destildada."]
    elegir_tipo(f, "ignorar")
    elegir_tipo(f, "fijo")
    assert f.tilde.value is True
    assert notas(f) == ["Ya existe en Octubre 2026. Si la importás, queda repetida."]


def test_ca_56_1_alquiler_ya_existe_y_al_tildar_cambia_la_nota(app_rev):
    # CA-56.1: destildada con "Viene destildada."; tildada, "queda repetida.".
    p = abrir(app_rev)
    f = fv(p, "Alquiler")
    assert f.tilde.value is False
    assert notas(f) == ["Ya existe en Octubre 2026. Viene destildada."]
    tildar(f, True)
    assert notas(f) == ["Ya existe en Octubre 2026. Si la importás, queda repetida."]
    tildar(f, False)
    assert notas(f) == ["Ya existe en Octubre 2026. Viene destildada."]


def test_iconos_de_las_notas(app_rev):
    # §3.12 tabla de notas: ya existe = WARNING_AMBER; compartido = PEOPLE_OUTLINE;
    # cuota = INFO_OUTLINE; incompleta = INFO_OUTLINE.
    p = abrir(app_rev)
    assert iconos(fv(p, "Alquiler")) == [ft.Icons.WARNING_AMBER]
    assert iconos(fv(p, "Internet", 23)) == [ft.Icons.PEOPLE_OUTLINE]
    assert iconos(fv(p, "Avant Service cuota 3/ 3 $41.116,66")) == [
        ft.Icons.INFO_OUTLINE
    ]
    assert iconos(fv(p, "Obra social")) == [ft.Icons.INFO_OUTLINE]


def test_colores_de_las_notas(app_rev):
    # §3.12: aviso = pendiente (ámbar), compartido/cuota = info; el texto lleva el mismo color.
    p = abrir(app_rev)
    ambar = de_tipo(fv(p, "Alquiler").notas, ft.Text)[0].color
    info = de_tipo(fv(p, "Internet", 23).notas, ft.Text)[0].color
    assert ambar == "#9A5800"
    assert info == "#1F5F7A"


def test_nota_de_cuota_de_avant(app_rev):
    # CA-52.1: texto exacto del plan.
    p = abrir(app_rev)
    f = fv(p, "Avant Service cuota 3/ 3 $41.116,66")
    assert notas(f) == [
        "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. "
        "Se agrega la cuota 3/3 en Octubre 2026."
    ]


def test_pagado_completo_y_parcial(app_rev):
    # §3.12: Internet "✓ Completo"; psicologo "Parcial · falta $ 80.000". Las demás no
    # muestran pagado.
    p = abrir(app_rev)
    internet = fv(p, "Internet", 5)
    assert internet.pagado.visible and internet.pagado.value == "$ 38.700"
    assert internet.estado_pagado.value == "✓ Completo"
    assert internet.estado_pagado.color == "#1E7B34"
    psico = fv(p, "psicologo")
    assert psico.pagado.value == "$ 60.000"
    assert psico.estado_pagado.value == "Parcial · falta $ 80.000"
    assert psico.estado_pagado.color == "#9A5800"
    gym = fv(p, "Gym")
    assert not gym.pagado.visible and not gym.estado_pagado.visible


def test_cobrado_solo_aparece_en_me_deben(app_rev):
    # §3.12: el tilde "Cobrado" solo se ve en filas "me deben".
    p = abrir(app_rev)
    assert fv(p, "Prestamo MP").cobrado.visible is True
    assert fv(p, "Servicios").cobrado.visible is False
    f = fv(p, "Servicios")
    elegir_tipo(f, "me_deben")
    assert f.cobrado.visible is True


def test_cobrado_de_la_columna_f_ca_51_6(app_rev):
    # CA-51.6: Prestamo MP e Internet (Sofía) vienen cobrados; tacones sin cobrar y con la
    # nota del "3.000".
    celdas = celdas_planilla()
    celdas.update(
        {"F21": "Cobrado", "F22": 20000, "F23": "x", "F26": "Cobrado", "F27": 3000}
    )
    p = abrir(app_rev, xlsx(celdas))
    assert fv(p, "Prestamo MP").cobrado.value is True
    assert fv(p, "Internet", 23).cobrado.value is True
    tacones = fv(p, "tacones chiqui baby")
    assert tacones.cobrado.value is False
    assert notas(tacones) == [
        "En la columna Cobrado dice \"3.000\"; los ítems 'me deben' no tienen cobro parcial, "
        "quedó como no cobrado."
    ]
    assert iconos(tacones) == [ft.Icons.WARNING_AMBER]


def test_destildar_cobrado_cambia_la_lista_y_borra_la_nota(app_rev):
    # CA-51.6: si el usuario destilda "cobrado" antes de confirmar, queda no cobrado.
    celdas = celdas_planilla()
    celdas.update({"F21": "Cobrado", "F22": 20000, "F26": "Cobrado", "F27": 3000})
    p = abrir(app_rev, xlsx(celdas))
    f = fv(p, "Prestamo MP")
    cobrado(f, False)
    assert f.fila.cobrado is False
    cobrado(fv(p, "tacones chiqui baby"), True)
    assert fv(p, "tacones chiqui baby").fila.cobrado is True
    assert (
        notas(fv(p, "tacones chiqui baby")) == []
    )  # la nota explicaba lo que leyó la app


def test_cobrado_no_cambia_el_tilde_ni_el_pie(app_rev):
    p = abrir(app_rev)
    antes = p.vista.texto_pie.value
    cobrado(fv(p, "Prestamo MP"), True)
    assert p.vista.texto_pie.value == antes
    assert fv(p, "Prestamo MP").tilde.value is True


def test_persona_vacia_se_ve_elegi_persona_en_negativo(app_rev):
    # §3.12: "Elegí persona" en negativo si falta; "Sofía y Marsu" no identifica una persona.
    p = abrir(app_rev, planilla_con({"D21": "Sofía y Marsu"}))
    f = fv(p, "Prestamo MP")
    assert f.categoria.value == "Elegí persona"
    assert f.categoria.color == NEGATIVO


def test_cuota_sin_datos_dice_falta_en_negativo(app_rev):
    # §3.12: la columna Cuota dice "Falta" en negativo si no hay n/N.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    elegir_tipo(f, "cuota")
    assert f.cuota.value == "Falta" and f.cuota.color == NEGATIVO


def test_sueldo_se_muestra_en_dolares_y_sin_nombre(app_rev):
    # §3.12 / RN-70: el "1.300" suelto pasa a sueldo: monto en US$, "(sin nombre)", sin error
    # y con la nota del sueldo del mes. No tiene categoría ni persona.
    p = abrir(app_rev)
    f = sin_nombre(p, 19)
    elegir_tipo(f, "sueldo")
    assert f.monto.value == "US$ 1.300,00"
    assert f.nombre.value == "(sin nombre)"
    assert f.tilde.value is True
    assert f.categoria.value == "" and f.cuota.value == "-"
    assert notas(f) == ["Sueldo del mes: US$ 1.200,00 -> US$ 1.300,00."]
    assert p.vista.lista.errores(f.fila) == []
    assert p.vista.texto_pie.value == (
        'Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo.'
    )


def test_sueldo_igual_al_actual_no_muestra_flecha(app_rev):
    # §3.12: si no cambia: "Sueldo del mes: US$ 1.200,00."
    p = abrir(app_rev, planilla_con({"B19": 1200}))
    f = sin_nombre(p, 19)
    elegir_tipo(f, "sueldo")
    assert notas(f) == ["Sueldo del mes: US$ 1.200,00."]


def test_dos_sueldos_error_en_ambas_filas_aviso_pie_y_boton(app_rev):
    # RN-70 + §3.12: error en todas las filas de sueldo, aviso del archivo arriba, pie y botón.
    p = abrir(app_rev)
    elegir_tipo(sin_nombre(p, 19), "sueldo")
    elegir_tipo(fv(p, "Gym"), "sueldo")
    texto = "Marcaste 2 filas como sueldo; dejá una sola."
    assert texto in notas(sin_nombre(p, 19))
    assert texto in notas(fv(p, "Gym"))
    assert texto in textos(p.vista.avisos_archivo)
    assert p.vista.texto_pie.value == texto
    assert p.vista.boton_confirmar.disabled is True
    assert p.vista.avisos_archivo.visible


def test_un_sueldo_vuelve_a_ignorar_y_desaparece_el_aviso(app_rev):
    p = abrir(app_rev)
    elegir_tipo(sin_nombre(p, 19), "sueldo")
    elegir_tipo(fv(p, "Gym"), "sueldo")
    elegir_tipo(fv(p, "Gym"), "fijo")
    assert not p.vista.avisos_archivo.visible
    assert p.vista.boton_confirmar.disabled is False


# ---------------------------------------------------------------------------
# Controles generales: mes destino (RF-55, RN-73, CA-55.x)
# ---------------------------------------------------------------------------


def test_ca_55_1_mes_destino_ofrece_2026_10_y_2026_11(app_rev):
    # CA-55.1: viene 2026-10 ("mes actual"); se ofrece el siguiente "se crea al confirmar";
    # no 2026-09 ni 2026-12. Del más nuevo al más viejo.
    p = abrir(app_rev)
    assert p.vista.mes.label == "Mes destino"
    assert p.vista.mes.value == "2026-10"
    assert [(o.key, o.text) for o in p.vista.mes.options] == [
        ("2026-11", "Noviembre 2026 · se crea al confirmar"),
        ("2026-10", "Octubre 2026 · mes actual"),
    ]


def test_ayuda_del_mes_que_existe_y_es_el_ultimo(app_rev):
    p = abrir(app_rev)
    assert textos(p.vista.ayuda_mes) == [
        "Octubre 2026 ya existe: se agregan los datos, sin borrar nada de lo que ya tiene."
    ]


def test_ayuda_del_mes_existente_con_sueldo_suma_segunda_linea(app_rev):
    # §3.12: con una fila de sueldo se suma la línea del reemplazo del sueldo.
    p = abrir(app_rev)
    elegir_tipo(sin_nombre(p, 19), "sueldo")
    assert textos(p.vista.ayuda_mes) == [
        "Octubre 2026 ya existe: se agregan los datos, sin borrar nada de lo que ya tiene.",
        "El sueldo de este mes se reemplaza por el de la fila marcada como sueldo.",
    ]


def test_ayuda_del_mes_siguiente_que_se_crea(app_rev):
    p = abrir(app_rev)
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    assert textos(p.vista.ayuda_mes) == [
        "Noviembre 2026 todavía no existe: se crea al confirmar, con los gastos fijos y las "
        "cuotas de Octubre 2026, y con su sueldo y su cotización."
    ]


def test_ca_55_2_destino_2026_11_el_sueldo_muestra_el_cambio(app_rev):
    # CA-55.2: la fila de sueldo muestra "US$ 1.200,00 -> US$ 1.300,00." con destino 2026-11.
    p = abrir(app_rev)
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    f = sin_nombre(p, 19)
    elegir_tipo(f, "sueldo")
    assert notas(f) == ["Sueldo del mes: US$ 1.200,00 -> US$ 1.300,00."]
    # Y las notas de cuota usan el mes destino nuevo.
    assert notas(fv(p, "Avant Service cuota 3/ 3 $41.116,66")) == [
        "Plan de 3 cuotas: primera Septiembre 2026, última Noviembre 2026. "
        "Se agrega la cuota 3/3 en Noviembre 2026."
    ]


def test_ca_55_3_mes_que_existe_pero_no_es_el_ultimo_avisa(app_rev, base):
    # CA-55.3: destino 2026-09 con 2026-09 y 2026-10 existentes: aviso en ámbar.
    insertar_mes(base.con, 2026, 9)
    p = abrir(app_rev)
    assert (
        "Los gastos fijos que importes no se agregan a los meses siguientes que ya existen."
        not in textos(p.vista.ayuda_mes)
    )
    p.vista.mes.value = "2026-9"
    p.vista.mes.on_select(evento(p.vista.mes))
    assert (
        "Los gastos fijos que importes no se agregan a los meses siguientes que ya existen."
        in textos(p.vista.ayuda_mes)
    )
    avisos = [
        c
        for c in de_tipo(p.vista.ayuda_mes, ft.Icon)
        if c.icon == ft.Icons.WARNING_AMBER
    ]
    assert avisos


def test_ca_55_5_con_ultimo_mes_2026_08_el_destino_propuesto_es_2026_08(con, pagina):
    # CA-55.5: último mes 2026-08 -> destino 2026-08 (no existen 09 ni 10).
    meses.crear_primer_mes(con, 2026, 8, 120000, 160000)
    catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    app = Aplicacion(pagina, con)
    app.iniciar()
    p = abrir(app)
    assert p.vista.mes.value == "2026-8"
    assert [o.key for o in p.vista.mes.options] == ["2026-9", "2026-8"]
    # Es el mes más viejo y el último existente; no es el "mes actual".
    assert p.vista.mes.options[1].text == "Agosto 2026"


def test_ca_56_5_cambiar_de_mes_retilda_y_avisa_6_segundos(app_rev, base):
    # CA-56.5: 2026-09 sin Alquiler y 2026-10 con Alquiler. Al pasar a 2026-09 la marca
    # desaparece, se vuelve a tildar y se avisa (SnackBar de 6 s). Al pasar a 2026-11 vuelve.
    insertar_mes(base.con, 2026, 9)
    p = abrir(app_rev)
    f = fv(p, "Alquiler")
    assert f.tilde.value is False
    p.vista.mes.value = "2026-9"
    p.vista.mes.on_select(evento(p.vista.mes))
    assert f.tilde.value is True
    assert notas(f) == []
    assert p.app.page.avisos()[-1] == "Cambiaste el mes: 1 fila se volvió a tildar."
    assert p.app.page.ultimo_aviso().duration == 6000
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    assert f.tilde.value is False
    assert notas(f) == ["Ya existe en Noviembre 2026. Viene destildada."]
    assert (
        p.app.page.avisos()[-1]
        == 'Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó.'
    )
    assert p.app.page.ultimo_aviso().duration == 6000


def test_cambiar_de_mes_sin_efecto_no_avisa(app_rev):
    # §3.12: "si nada cambió, no hay aviso". 2026-10 -> 2026-11: Alquiler se copiaría, ya estaba
    # destildada: nada cambia.
    p = abrir(app_rev)
    antes = len(p.app.page.avisos())
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    assert len(p.app.page.avisos()) == antes


def test_ca_56_5_la_marca_se_recalcula_tambien_en_la_nota_de_las_otras_filas(
    app_rev, base
):
    # El resumen del pie y el subtítulo del bloque se actualizan con el mes.
    insertar_mes(base.con, 2026, 9)
    p = abrir(app_rev)
    assert subtitulo(bloque(p, "Gasto del Mes")) == "filas 3 a 7 · se importan 3 de 5"
    p.vista.mes.value = "2026-9"
    p.vista.mes.on_select(evento(p.vista.mes))
    assert subtitulo(bloque(p, "Gasto del Mes")) == "filas 3 a 7 · se importan 4 de 5"
    assert p.vista.texto_pie.value.startswith("Se importan 10 filas: 6 gastos")


def test_mes_no_ofrecido_no_rompe(app_rev):
    # Un valor de mes fuera de las opciones (no debería pasar) da el aviso de validación
    # y no cambia el mes ni rompe la pantalla.
    p = abrir(app_rev)
    p.vista._cambiar_mes("2026-12")
    assert (p.lista.anio, p.lista.mes) == (2026, 10)
    assert "Ese mes no se puede elegir." in p.app.page.avisos()


# ---------------------------------------------------------------------------
# Primer uso: mes y año libres (RN-73, CA-55.4)
# ---------------------------------------------------------------------------


@pytest.fixture
def app_primer_uso(pagina, con):
    """Base sin meses ni personas: arranca en el primer uso. Se crea "Varios"."""
    catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    aplicacion = Aplicacion(pagina, con)
    aplicacion.iniciar()
    return aplicacion


def abrir_primer_uso(app, contenido=None):
    clic(app.page.controls[0], "Importar Excel")
    p = app._importacion
    leer(p, "planilla-prueba.xlsx", contenido or planilla_prueba())
    return p


def test_primer_uso_muestra_mes_y_anio_libres_con_valores_del_calendario(
    app_primer_uso,
):
    p = abrir_primer_uso(app_primer_uso)
    v = p.vista
    assert v.mes.label == "Mes" and v.mes.value == "10"
    assert v.anio.label == "Año" and v.anio.value == "2026" and v.anio.max_length == 4
    assert [o.text for o in v.mes.options][:2] == ["Enero", "Febrero"]
    assert len(v.mes.options) == 12
    assert textos(v.ayuda_mes) == [
        "Se crea al confirmar, sin cotización: la cargás después en el Resumen. "
        "Si no marcás una fila como sueldo, el sueldo del mes queda en US$ 0,00."
    ]


def test_primer_uso_anio_de_dos_digitos_da_error_y_bloquea(app_primer_uso):
    # CA-55.4 ("año 26 se rechaza") + §3.12: error en el campo, botón deshabilitado con tooltip.
    p = abrir_primer_uso(app_primer_uso)
    v = p.vista
    v.anio.value = "26"
    v.anio.on_change(evento(v.anio))
    assert v.anio.error == "El año tiene que tener 4 dígitos. Ej.: 2026"
    assert v.boton_confirmar.disabled is True
    assert v.boton_confirmar.tooltip == "Corregí el mes destino."
    assert textos(v.ayuda_mes) == []  # el error ya está en el campo


def test_primer_uso_corregir_el_anio_rehabilita(app_primer_uso):
    p = abrir_primer_uso(app_primer_uso)
    v = p.vista
    v.anio.value = "26"
    v.anio.on_change(evento(v.anio))
    v.anio.value = "2027"
    v.anio.on_change(evento(v.anio))
    assert v.anio.error is None
    assert v.mes_invalido is False
    assert v.boton_confirmar.disabled is False
    assert (p.lista.anio, p.lista.mes) == (2027, 10)


def test_primer_uso_anio_vacio_y_anio_de_cinco_digitos(app_primer_uso):
    p = abrir_primer_uso(app_primer_uso)
    v = p.vista
    for valor in ("", "202", "20266"):
        v.anio.value = valor
        v.anio.on_change(evento(v.anio))
        assert v.anio.error == "El año tiene que tener 4 dígitos. Ej.: 2026", valor
        assert v.boton_confirmar.disabled is True


def test_primer_uso_cambiar_mes_actualiza_las_notas_de_cuota(app_primer_uso):
    p = abrir_primer_uso(app_primer_uso)
    v = p.vista
    v.mes.value = "12"
    v.mes.on_select(evento(v.mes))
    assert notas(fv(p, "Avant Service cuota 3/ 3 $41.116,66")) == [
        "Plan de 3 cuotas: primera Octubre 2026, última Diciembre 2026. "
        "Se agrega la cuota 3/3 en Diciembre 2026."
    ]


def test_primer_uso_alquiler_no_es_ya_existe(app_primer_uso):
    # No hay ningún mes: nada "ya existe" (O78) y las 6 filas de gasto se importan.
    p = abrir_primer_uso(app_primer_uso)
    assert fv(p, "Alquiler").tilde.value is True
    assert notas(fv(p, "Alquiler")) == []


def test_primer_uso_sueldo_dice_que_el_mes_todavia_no_existe_en_el_dialogo(
    app_primer_uso,
):
    # §4.9: si el mes no existe: "Octubre 2026 todavía no existe."
    p = abrir_primer_uso(app_primer_uso)
    f = sin_nombre(p, 19)
    elegir_tipo(f, "sueldo")
    d, dlg = abrir_fila(p, f)
    assert dlg.ayuda_sueldo.value == "Octubre 2026 todavía no existe."


# ---------------------------------------------------------------------------
# Categoría por defecto (RF-54, RN-75, CA-54.x)
# ---------------------------------------------------------------------------


def test_categoria_por_defecto_viene_varios_con_boton_mas(app_rev, base):
    # CA-54.1 / §3.12: dropdown "Categoría por defecto" con Varios elegido y "+" al lado.
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    assert c.dropdown.label == "Categoría por defecto"
    assert c.dropdown.value == clave_cat(base.varios)
    assert c.dropdown.error_text is None
    mas = [
        b for b in de_tipo(c.control, ft.IconButton) if b.tooltip == "Nueva categoría"
    ]
    assert len(mas) == 1 and mas[0].icon == ft.Icons.ADD


def test_ayuda_de_la_categoria_por_defecto(app_rev):
    p = abrir(app_rev)
    assert (
        "Se usa en los gastos y cuotas que no cambies a mano. Los gastos quedan sin medio "
        "de pago: lo completás después en Gastos."
    ) in textos(p.vista.control)


def test_ca_54_2_categoria_a_mano_y_despues_la_por_defecto(app_rev, base):
    # CA-54.2: Internet (fila 5) a Servicios; luego la por defecto a Vivienda: Internet queda
    # en Servicios (con "• " y tooltip), las demás pasan a Vivienda sin marca.
    p = abrir(app_rev)
    internet = fv(p, "Internet", 5)
    d, dlg = abrir_fila(p, internet)
    dlg.categoria.dropdown.value = clave_cat(base.servicios)
    aceptar(dlg)
    assert internet.categoria.value == "• Servicios"
    assert internet.categoria.tooltip == "Elegida a mano"
    c = p.vista.categoria_defecto
    c.dropdown.value = clave_cat(base.vivienda)
    c.dropdown.on_select(evento(c.dropdown))
    assert internet.categoria.value == "• Servicios"
    for nombre in ("Servicios", "psicologo", "Gym", "Monotributo 66.020,12"):
        f = fv(p, nombre)
        assert f.categoria.value == "Vivienda", nombre
        assert f.categoria.tooltip is None
    assert fv(p, "Avant Service cuota 3/ 3 $41.116,66").categoria.value == "Vivienda"


def test_categoria_elegida_en_el_dialogo_igual_a_la_por_defecto_sigue_la_por_defecto(
    app_rev, base
):
    # RN-75: la opción "Categoría por defecto (Varios)" del diálogo deja la fila siguiendo
    # la por defecto: no lleva "•".
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    assert dlg.categoria.dropdown.options[0].key == "defecto"
    assert dlg.categoria.dropdown.options[0].text == "Categoría por defecto (Varios)"
    assert dlg.categoria.dropdown.value == "defecto"
    aceptar(dlg)
    assert f.fila.categoria is None
    assert f.categoria.value == "Varios"


def test_el_dialogo_refleja_una_categoria_propia(app_rev, base):
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.categoria.dropdown.value = clave_cat(base.salud)
    aceptar(dlg)
    d2, dlg2 = abrir_fila(p, f)
    assert dlg2.categoria.dropdown.value == clave_cat(base.salud)
    # La opción por defecto cambia su texto si cambia la por defecto.
    assert dlg2.categoria.dropdown.options[0].text == "Categoría por defecto (Varios)"


def test_ca_54_3_sin_varios_no_hay_por_defecto_y_cada_fila_da_error(app_sin_varios):
    # CA-54.3: sin "Varios": dropdown vacío con error_text; cada fila de gasto y de cuota
    # muestra "Elegí una categoría."; el botón queda deshabilitado.
    p = abrir(app_sin_varios)
    v = p.vista
    assert v.categoria_defecto.dropdown.value is None
    assert (
        v.categoria_defecto.dropdown.error_text
        == "Elegí una categoría para los gastos y cuotas."
    )
    for nombre in (
        "Servicios",
        "Internet",
        "psicologo",
        "Gym",
        "Monotributo 66.020,12",
    ):
        f = fv(p, nombre, 5 if nombre == "Internet" else None)
        assert "Elegí una categoría." in notas(f), nombre
        assert f.control.bgcolor == "#FCE8E6"
    assert "Elegí una categoría." in notas(fv(p, "Avant Service cuota 3/ 3 $41.116,66"))
    assert v.boton_confirmar.disabled is True
    assert v.boton_confirmar.tooltip == "Primero corregí las filas con errores."
    assert v.texto_pie.value.startswith("Hay 6 filas con errores.")
    assert v.ir_al_error.visible is True


def test_ca_54_3_crear_categoria_nueva_la_elige_y_cancelar_no_la_crea(
    app_sin_varios, base_sin_varios
):
    # CA-54.3: crear "Importado" desde el "+" la deja elegida como por defecto, sin errores
    # de categoría; y como no se escribe en la base, al cancelar no existe.
    con = base_sin_varios.con
    antes = foto(con)
    p = abrir(app_sin_varios)
    c = p.vista.categoria_defecto
    c.abrir()
    assert c.fila_nueva.visible
    c.nombre.value = "Importado"
    c.agregar()
    assert c.dropdown.value == "nueva:Importado"
    assert "Importado (nueva)" in [o.text for o in c.dropdown.options]
    assert p.lista.categoria_defecto == Nueva("Importado")
    assert not c.fila_nueva.visible
    assert c.dropdown.error_text is None
    assert p.vista.boton_confirmar.disabled is False
    assert fv(p, "Gym").categoria.value == "Importado (nueva)"
    # Cancelar la importación: como hubo cambios (8e), pide confirmar y hay que tocar "Descartar".
    clic(p.vista.control, "Cancelar")
    assert app_sin_varios._importacion is p
    clic(dialogo_arriba(app_sin_varios), "Descartar")
    assert app_sin_varios._importacion is None
    assert "Importado" not in [
        c_["nombre"] for c_ in catalogos.listar(con, catalogos.CATEGORIAS, True)
    ]
    assert foto(con) == antes


def test_fila_de_nueva_categoria_texto_de_ayuda_y_botones(app_rev):
    # §4.11: Agregar / Cancelar y la ayuda "Se crea al confirmar...".
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    assert c.fila_nueva.visible is False
    [mas] = [
        b for b in de_tipo(c.control, ft.IconButton) if b.tooltip == "Nueva categoría"
    ]
    mas.on_click(None)
    assert c.fila_nueva.visible is True
    ayuda = textos(c.fila_nueva)
    assert "Se crea al confirmar la importación. Si cancelás, no se crea." in ayuda
    assert "Agregar" in ayuda and "Cancelar" in ayuda
    assert c.nombre.label == "Nombre de la categoría"
    clic(c.fila_nueva, "Cancelar")
    assert c.fila_nueva.visible is False


def test_categoria_nueva_validaciones(app_rev, base):
    # §4.11: vacío, ya existe (sin acentos ni mayúsculas), archivada, ya agregada.
    catalogos.crear(base.con, catalogos.CATEGORIAS, "Mascotas")
    id_viejo = catalogos.crear(base.con, catalogos.CATEGORIAS, "Regalos")
    archivar(base.con, catalogos.CATEGORIAS, id_viejo)
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    c.abrir()
    c.nombre.value = "   "
    c.agregar()
    assert c.nombre.error == "Ingresá un nombre."
    c.nombre.value = "salud"
    c.agregar()
    assert c.nombre.error == 'Ya existe una categoría llamada "Salud".'
    c.nombre.value = "regalos"
    c.agregar()
    assert c.nombre.error == (
        'Ya existe una categoría llamada "Regalos" (está archivada). '
        "Podés desarchivarla en Ajustes."
    )
    c.nombre.value = "Hobbies"
    c.agregar()
    assert c.nombre.error is None
    c.abrir()
    c.nombre.value = "HOBBIES"
    c.agregar()
    assert (
        c.nombre.error
        == 'Ya agregaste una categoría llamada "Hobbies" en esta importación.'
    )
    # La fila en línea sigue abierta con el error.
    assert c.fila_nueva.visible


def test_categoria_nueva_se_ve_en_el_dialogo_de_otra_fila(app_rev):
    # §4.11: se puede elegir en las demás filas mientras dure la revisión.
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    c.abrir()
    c.nombre.value = "Mascotas"
    c.agregar()
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    assert "Mascotas (nueva)" in [o.text for o in dlg.categoria.dropdown.options]
    # El valor por defecto del dialogo ahora dice Mascotas.
    assert dlg.categoria.dropdown.options[0].text == "Categoría por defecto (Mascotas)"


# ---------------------------------------------------------------------------
# Filtros y conteos (§3.12)
# ---------------------------------------------------------------------------


def test_etiquetas_del_filtro_con_cantidades(app_rev):
    # §3.12: "Todas (29)" · "Se importan (9)" · "Con avisos (n)" · "Con errores (0)".
    # Avisos con esta base: Alquiler (ya existe) e Internet de Sofía (posible compartido).
    p = abrir(app_rev)
    assert etiquetas_filtro(p) == {
        "todas": "Todas (29)",
        "importan": "Se importan (9)",
        "avisos": "Con avisos (2)",
        "errores": "Con errores (0)",
    }
    assert p.vista.selector_filtro.selected == ["todas"]


def test_filtro_se_importan_oculta_el_resto_y_los_bloques_sin_filas(app_rev):
    p = abrir(app_rev)
    filtrar(p, "importan")
    assert sorted(visibles(p)) == sorted(
        [
            "Servicios",
            "Internet",
            "psicologo",
            "Monotributo 66.020,12",
            "Avant Service cuota 3/ 3 $41.116,66",
            "Gym",
            "Prestamo MP",
            "Internet",
            "tacones chiqui baby",
        ]
    )
    assert p.vista.bloque_incompletas.control.visible is False
    assert all(b.control.visible for b in p.vista.bloques)  # todos tienen alguna


def test_filtro_con_avisos_solo_deja_alquiler_e_internet_de_sofia(app_rev):
    p = abrir(app_rev)
    filtrar(p, "avisos")
    assert visibles(p) == ["Alquiler", "Internet"]
    assert bloque(p, "Deudas").control.visible is False
    assert bloque(p, "Marsu").control.visible is False
    assert bloque(p, "Gasto del Mes").control.visible is True


def test_informacion_de_cuota_no_cuenta_como_aviso(app_rev):
    # §3.12: la nota de cuota es "info": Avant no entra en "Con avisos".
    p = abrir(app_rev)
    filtrar(p, "avisos")
    assert "Avant Service cuota 3/ 3 $41.116,66" not in visibles(p)


def test_filtro_todas_vuelve_a_mostrar_todo(app_rev):
    p = abrir(app_rev)
    filtrar(p, "importan")
    filtrar(p, "todas")
    assert len(visibles(p)) == 29
    assert p.vista.bloque_incompletas.control.visible


def test_filtro_sin_resultados_muestra_texto_y_ver_todas(app_rev):
    # §3.12: "Ninguna fila coincide con este filtro." + "Ver todas".
    p = abrir(app_rev)
    assert p.vista.sin_resultados.visible is False
    filtrar(p, "errores")
    assert p.vista.sin_resultados.visible is True
    assert "Ninguna fila coincide con este filtro." in textos(p.vista.sin_resultados)
    assert visibles(p) == []
    assert not any(b.control.visible for b in p.vista.bloques)
    clic(p.vista.sin_resultados, "Ver todas")
    assert p.vista.sin_resultados.visible is False
    assert p.vista.selector_filtro.selected == ["todas"]
    assert len(visibles(p)) == 29


def test_los_conteos_del_filtro_se_actualizan_con_cada_cambio(app_rev):
    p = abrir(app_rev)
    tildar(fv(p, "Servicios"), False)
    assert etiquetas_filtro(p)["importan"] == "Se importan (8)"
    elegir_tipo(fv(p, "Tarjetas de Credito"), "fijo")
    assert etiquetas_filtro(p)["importan"] == "Se importan (9)"
    elegir_tipo(fv(p, "Gym"), "cuota")  # sin cuota: error
    assert etiquetas_filtro(p)["errores"] == "Con errores (1)"


def test_con_errores_se_marca_con_icono_en_cuanto_hay_uno(app_rev):
    # §3.12: "Con errores" aparece resaltado (ícono) cuando hay alguno.
    p = abrir(app_rev)
    seg = [s for s in p.vista.selector_filtro.segments if s.value == "errores"][0]
    assert seg.icon is None
    elegir_tipo(fv(p, "Gym"), "cuota")
    assert seg.icon is not None and seg.icon.icon == ft.Icons.ERROR_OUTLINE
    elegir_tipo(fv(p, "Gym"), "fijo")
    assert seg.icon is None


def test_filtro_activo_se_reaplica_cuando_cambia_una_fila(app_rev):
    # Con "Se importan" activo, destildar una fila la oculta de inmediato.
    p = abrir(app_rev)
    filtrar(p, "importan")
    assert "Gym" in visibles(p)
    tildar(fv(p, "Gym"), False)
    assert "Gym" not in visibles(p)


def test_filtro_errores_muestra_la_fila_con_error_y_su_bloque_plegado(app_rev):
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "cuota")
    filtrar(p, "errores")
    assert visibles(p) == ["Gym"]
    assert bloque(p, "Deudas").control.visible
    assert not bloque(p, "Marsu").control.visible


# ---------------------------------------------------------------------------
# Acciones de bloque (RN-78, CA-52.8)
# ---------------------------------------------------------------------------


def test_menu_del_bloque_tiene_las_tres_acciones(app_rev):
    p = abrir(app_rev)
    menu = de_tipo(bloque(p, "Marsu").control.title, ft.PopupMenuButton)[0]
    assert menu.tooltip == "Acciones del bloque" and menu.icon == ft.Icons.MORE_VERT
    assert [i.content for i in menu.items] == [
        "Tildar todas las filas",
        "Destildar todas las filas",
        "Cambiar tipo o categoría de todas...",
    ]


def test_filas_incompletas_no_tiene_menu_de_bloque(app_rev):
    p = abrir(app_rev)
    assert not de_tipo(p.vista.bloque_incompletas.control.title, ft.PopupMenuButton)


def test_ca_52_8_destildar_y_tildar_todas_en_deudas_sofia(app_rev):
    # CA-52.8: destilda 22 y 23 (24 sigue sin tilde); tildar vuelve a tildar 22 y 23, 24 sigue
    # ignorada y sin tilde.
    p = abrir(app_rev)
    menu_bloque(bloque(p, "Deudas sofia"), "Destildar todas las filas")
    assert [f.tilde.value for f in bloque(p, "Deudas sofia").filas] == [
        False,
        False,
        False,
    ]
    assert subtitulo(bloque(p, "Deudas sofia")) == "filas 22 a 24 · se importan 0 de 3"
    menu_bloque(bloque(p, "Deudas sofia"), "Tildar todas las filas")
    assert [f.tilde.value for f in bloque(p, "Deudas sofia").filas] == [
        True,
        True,
        False,
    ]
    assert fv(p, "Total", 24).tipo.value == "ignorar"


def test_ca_52_8_tildar_todas_tilda_tambien_las_ya_existe(app_rev, base):
    # CA-52.8 (segunda importación): "Tildar todas las filas" tilda las "ya existe" del bloque.
    cargar_primera_importacion(base)
    p = abrir(app_rev)
    sofia = bloque(p, "Deudas sofia")
    assert [f.tilde.value for f in sofia.filas] == [False, False, False]
    assert (
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
        in notas(sofia.filas[0])
    )
    menu_bloque(sofia, "Tildar todas las filas")
    assert [f.tilde.value for f in sofia.filas] == [True, True, False]
    assert notas(sofia.filas[0])[0] == (
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Si la importás, queda repetida."
    )


def test_ca_56_4_segunda_importacion_todo_ya_existe(app_rev, base):
    # CA-56.4: en la segunda importación, las filas de gasto, Avant y las tres de "me deben"
    # vienen "ya existe" y destildadas; Avant con la nota de gasto (no la de plan).
    cargar_primera_importacion(base)
    p = abrir(app_rev)
    for nombre, excel in [
        ("Servicios", 4),
        ("Internet", 5),
        ("psicologo", 7),
        ("Monotributo 66.020,12", 12),
        ("Gym", 15),
        ("Avant Service cuota 3/ 3 $41.116,66", 13),
        ("Prestamo MP", 22),
        ("Internet", 23),
        ("tacones chiqui baby", 27),
        ("Alquiler", 3),
    ]:
        f = fv(p, nombre, excel)
        assert f.tilde.value is False, nombre
    assert notas(fv(p, "Servicios")) == ["Ya existe en Octubre 2026. Viene destildada."]
    assert notas(fv(p, "Avant Service cuota 3/ 3 $41.116,66")) == [
        "Ya existe en Octubre 2026. Viene destildada.",
        "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. "
        "Se agrega la cuota 3/3 en Octubre 2026.",
    ]
    assert notas(fv(p, "tacones chiqui baby")) == [
        "Marsu ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
    ]
    assert p.vista.texto_pie.value == "No hay filas para importar."
    assert p.vista.boton_confirmar.disabled is True
    assert p.vista.boton_confirmar.tooltip == "Tildá al menos una fila."
    # Tildar "Prestamo MP" y volver a destildar.
    f = fv(p, "Prestamo MP")
    tildar(f, True)
    assert notas(f)[0] == (
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Si la importás, queda repetida."
    )
    tildar(f, False)
    assert notas(f)[0] == (
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
    )


def test_ca_56_3_repetida_en_el_archivo(app_rev):
    # CA-56.3: dos "Nafta | 30000": las dos tildadas con la nota; Internet gasto/me deben no.
    p = abrir(app_rev, xlsx({"C3": "Nafta", "D3": 30000, "C4": "Nafta", "D4": 30000}))
    nafta = [f for f in p.vista.filas if f.fila.nombre == "Nafta"]
    assert len(nafta) == 2
    for f in nafta:
        assert f.tilde.value is True
        assert notas(f) == [
            "Repetida en el archivo. Si no es un error del Excel, podés importarla igual."
        ]
        assert iconos(f) == [ft.Icons.CONTENT_COPY]
    assert p.vista.boton_confirmar.disabled is False
    clic(p.vista.control, "Cancelar")
    p2 = abrir(app_rev)
    assert not any("Repetida" in t for f in p2.vista.filas for t in notas(f))


def test_ca_56_2_nombre_con_espacios_y_sin_acento_ya_existe(app_rev, base):
    # CA-56.2: gasto "Teléfono" en 2026-10, fila " telefono " del Excel viene "ya existe".
    gastos.agregar_gasto(
        base.con, base.mes_id, "Teléfono", base.varios, 1000000, "fijo"
    )
    p = abrir(app_rev, xlsx({"C3": " telefono ", "D3": 5000}))
    f = p.vista.filas[0]
    assert f.tilde.value is False
    assert notas(f) == ["Ya existe en Octubre 2026. Viene destildada."]


def test_ca_56_6_aviso_de_gasto_compartido_aparece_y_desaparece(app_rev):
    # CA-56.6: Internet (fila 23) avisa por Internet (fila 5). Al ignorar la fila 5, se va.
    aviso = (
        "¿Es parte de un gasto compartido? Si es así, ignorala y marcá el gasto como "
        "compartido después."
    )
    p = abrir(app_rev)
    assert notas(fv(p, "Internet", 23)) == [aviso]
    assert notas(fv(p, "Prestamo MP")) == []
    assert notas(fv(p, "tacones chiqui baby")) == []
    elegir_tipo(fv(p, "Internet", 5), "ignorar")
    assert notas(fv(p, "Internet", 23)) == []
    elegir_tipo(fv(p, "Internet", 5), "fijo")
    assert notas(fv(p, "Internet", 23)) == [aviso]
    tildar(fv(p, "Internet", 5), False)
    assert notas(fv(p, "Internet", 23)) == []


def test_ca_56_6_sigue_como_me_deben_y_tildada_y_se_puede_confirmar(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Internet", 23)
    assert f.tipo.value == "me_deben" and f.tilde.value is True
    assert p.vista.boton_confirmar.disabled is False


def test_ca_56_7_plan_terminado_ya_existe(app_rev, base):
    # CA-56.7: plan terminado "Heladera 2/12" y un Excel con la misma fila -> cuota, ya existe.
    cuotas.crear_plan(
        base.con, "Heladera 2/12", base.varios, None, 3000000, 3, 2026, 1, hoy=HOY
    )
    p = abrir(app_rev, xlsx({"C3": "Heladera 2/12", "D3": 30000}))
    f = p.vista.filas[0]
    assert f.tipo.value == "cuota" and f.tilde.value is False
    assert (
        notas(f)[0] == "Ya existe un plan de cuotas con este nombre. Viene destildada."
    )
    tildar(f, True)
    assert (
        notas(f)[0]
        == "Ya existe un plan de cuotas con este nombre. Si la importás, queda repetida."
    )


# ---------------------------------------------------------------------------
# Pie, errores y botón Confirmar (RN-68)
# ---------------------------------------------------------------------------


def test_pie_con_todo_bien(app_rev):
    p = abrir(app_rev)
    v = p.vista
    assert (
        v.texto_pie.value
        == 'Se importan 9 filas: 5 gastos, 1 plan de cuotas y 3 ítems "me deben".'
    )
    assert v.boton_confirmar.disabled is False
    assert v.boton_confirmar.tooltip == "Ctrl+Enter"
    assert v.icono_pie.visible is False and v.ir_al_error.visible is False


def test_tooltip_del_boton_en_macos_usa_cmd(pagina, con, base):
    # El atajo se muestra con la convención de cada sistema.
    import flet as ft_

    pagina.platform = ft_.PagePlatform.MACOS
    app = Aplicacion(pagina, con)
    app.iniciar()
    p = abrir(app)
    assert p.vista.boton_confirmar.tooltip == "⌘Enter"


def test_pie_se_actualiza_con_cada_cambio_de_tilde(app_rev):
    p = abrir(app_rev)
    tildar(fv(p, "Servicios"), False)
    assert (
        p.vista.texto_pie.value
        == 'Se importan 8 filas: 4 gastos, 1 plan de cuotas y 3 ítems "me deben".'
    )
    tildar(fv(p, "Alquiler"), True)
    assert p.vista.texto_pie.value.startswith("Se importan 9 filas: 5 gastos")


def test_pie_sin_filas_para_importar(app_rev):
    # RN-68: "No hay filas para importar." con botón deshabilitado y tooltip "Tildá al menos una fila.".
    p = abrir(app_rev)
    for b in p.vista.bloques:
        menu_bloque(b, "Destildar todas las filas")
    v = p.vista
    assert v.texto_pie.value == "No hay filas para importar."
    assert v.boton_confirmar.disabled is True
    assert v.boton_confirmar.tooltip == "Tildá al menos una fila."
    assert v.icono_pie.visible is False


def test_error_de_fila_bloquea_el_boton_y_muestra_pie_y_ir_al_error(app_rev):
    # RN-68 + §3.12: error -> pie en negativo con ícono, botón deshabilitado con tooltip,
    # "Ir al primer error" visible. Singular en el pie.
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "cuota")
    v = p.vista
    assert v.texto_pie.value == (
        "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar."
    )
    assert v.texto_pie.color == NEGATIVO
    assert v.icono_pie.visible and v.icono_pie.icon == ft.Icons.ERROR_OUTLINE
    assert v.boton_confirmar.disabled is True
    assert v.boton_confirmar.tooltip == "Primero corregí las filas con errores."
    assert v.ir_al_error.visible is True


def test_dos_errores_pie_en_plural(app_rev):
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "cuota")
    elegir_tipo(fv(p, "Servicios"), "me_deben")
    assert p.vista.texto_pie.value == (
        "Hay 2 filas con errores. Corregilas, ignoralas o destildalas para continuar."
    )


def test_fila_con_error_fondo_borde_icono_y_texto_en_negativo(app_rev):
    # §3.12: fondo negativo suave, borde izquierdo de 4 px en negativo, ERROR_OUTLINE + texto.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    elegir_tipo(f, "cuota")
    assert f.control.bgcolor == "#FCE8E6"
    assert f.control.border.left.width == 4 and f.control.border.left.color == NEGATIVO
    assert notas(f)[0] == "Indicá la cuota actual y la cantidad de cuotas."
    assert iconos(f)[0] == ft.Icons.ERROR_OUTLINE
    assert de_tipo(f.notas, ft.Text)[0].color == NEGATIVO


def test_el_error_se_quita_al_ignorar_o_destildar_la_fila(app_rev):
    # RN-68: la fila con error se corrige pasándola a ignorar o destildándola.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    elegir_tipo(f, "cuota")
    tildar(f, False)
    assert f.control.bgcolor is None and f.control.border is None
    assert p.vista.boton_confirmar.disabled is False
    tildar(f, True)
    assert p.vista.boton_confirmar.disabled is True
    elegir_tipo(f, "ignorar")
    assert p.vista.boton_confirmar.disabled is False


def test_orden_de_las_notas_errores_primero(app_rev):
    # §3.12: errores, avisos e info, en ese orden. "Internet" (fila 23) como cuota:
    # error de cuota + aviso de ya existe? Se arma con Alquiler a cuota sin datos.
    p = abrir(app_rev)
    f = fv(p, "Alquiler")
    tildar(f, True)
    elegir_tipo(f, "cuota")
    nt = notas(f)
    assert nt[0] == "Indicá la cuota actual y la cantidad de cuotas."
    assert nt[1].startswith("Ya existe en Octubre 2026")


def test_subtitulo_del_bloque_muestra_con_error_aunque_este_plegado(app_rev):
    # §3.12: "un bloque plegado nunca esconde un error".
    p = abrir(app_rev)
    bloque(p, "Deudas").control.expanded = False
    elegir_tipo(fv(p, "Gym"), "cuota")
    assert (
        subtitulo(bloque(p, "Deudas"))
        == "filas 12 a 15 · se importan 3 de 3 · 1 con error"
    )
    iconos_ = de_tipo(bloque(p, "Deudas").subtitulo, ft.Icon)
    assert [i.icon for i in iconos_] == [ft.Icons.ERROR_OUTLINE]
    elegir_tipo(fv(p, "Gym"), "fijo")
    assert "error" not in subtitulo(bloque(p, "Deudas"))


def test_ir_al_primer_error_abre_el_bloque_y_desplaza_la_lista(app_rev):
    # §3.12: despliega su bloque si estaba plegado, desplaza hasta esa fila y enfoca el lápiz.
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "cuota")
    elegir_tipo(fv(p, "Servicios"), "me_deben")
    bloque(p, "Deudas").control.expanded = False
    bloque(p, "Gasto del Mes").control.expanded = False
    pagina = p.app.page
    pagina.tareas.clear()
    llamadas = []

    async def scroll_falso(**kw):
        llamadas.append(kw)

    p.vista.lista_filas.scroll_to = scroll_falso
    clic(p.vista.control, "Ir al primer error")
    # El primer error en el orden del Excel es Servicios (fila 4).
    assert bloque(p, "Gasto del Mes").control.expanded is True
    assert bloque(p, "Deudas").control.expanded is False  # no era el primero
    assert len(pagina.tareas) == 2
    for t in pagina.tareas:
        if getattr(t, "__name__", "") == "desplazar":
            asyncio.run(t())
    assert llamadas == [
        {"scroll_key": f"fila-{fv(p, 'Servicios').indice}", "duration": 300}
    ]
    assert pagina.tareas[-1] == fv(p, "Servicios").lapiz.focus


def test_ir_al_primer_error_con_el_filtro_puesto_lo_vuelve_a_todas(app_rev):
    # Si la fila con error no pasa el filtro activo, el botón vuelve a "Todas".
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "cuota")
    filtrar(p, "avisos")
    assert "Gym" not in visibles(p)
    p.vista.lista_filas.scroll_to = lambda **kw: asyncio.sleep(0)
    clic(p.vista.control, "Ir al primer error")
    assert p.vista.selector_filtro.selected == ["todas"]
    assert "Gym" in visibles(p)


def test_error_en_filas_incompletas_abre_el_grupo_con_ir_al_primer_error(app_rev):
    # §3.12: el grupo plegado muestra "1 con error" y el botón lo despliega.
    p = abrir(app_rev)
    f = fv(p, "Obra social")
    elegir_tipo(f, "fijo")  # sin monto: error
    inc = p.vista.bloque_incompletas
    assert inc.control.expanded is False
    assert "1 con error" in subtitulo(inc)
    assert notas(f)[0] == "Falta el monto."
    p.vista.lista_filas.scroll_to = lambda **kw: asyncio.sleep(0)
    clic(p.vista.control, "Ir al primer error")
    assert inc.control.expanded is True


def test_ca_53_2_cambiar_tipo_sin_completar_el_monto_da_falta_el_monto(app_rev):
    # CA-53.2: "Obra social" a gasto fijo sin monto -> "Falta el monto." y no se confirma.
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Obra social"), "fijo")
    assert notas(fv(p, "Obra social"))[0] == "Falta el monto."
    assert fv(p, "Obra social").monto.value == "(sin monto)"
    assert p.vista.boton_confirmar.disabled is True


def test_pagado_mayor_que_el_monto_viene_del_excel_ca_51_5(app_rev):
    # CA-51.5: con "Pagado" en E11, Monotributo trae pagado 66.021 y el error del pagado.
    p = abrir(app_rev, planilla_con({"E11": "Pagado"}))
    f = fv(p, "Monotributo 66.020,12")
    assert notas(f)[0] == "El pagado ($ 66.021) es mayor que el monto ($ 66.020)."
    assert p.vista.boton_confirmar.disabled is True
    assert subtitulo(bloque(p, "Deudas")).endswith("1 con error")


def test_hoja_sin_filas_completas_abre_el_grupo_y_avisa(app_rev):
    # §3.12: sin filas con texto y monto: aviso, sin bloques, "Filas incompletas" abierto.
    p = abrir(app_rev, xlsx({"C3": "Luz", "C4": "Gas"}))
    v = p.vista
    assert "No se encontraron filas con un texto y un monto." in textos(
        v.avisos_archivo
    )
    assert v.bloques == []
    assert v.bloque_incompletas.control.expanded is True
    assert v.texto_pie.value == "No hay filas para importar."
    assert v.boton_confirmar.disabled is True


def test_aviso_de_formulas_sin_valor(app_rev):
    # §3.12: "Hay N fórmulas sin valor calculado (ej. D9)..." arriba de la lista.
    p = abrir(app_rev, xlsx({"C3": "Luz", "D3": "=SUM(1,2)", "C4": "Gas", "D4": 500}))
    assert (
        "Hay 1 fórmulas sin valor calculado (ej. D3). Abrí el archivo en Excel, guardalo y "
        "volvé a importarlo para ver esos montos."
    ) in textos(p.vista.avisos_archivo)


def test_sin_avisos_del_archivo_el_bloque_de_avisos_esta_oculto(app_rev):
    p = abrir(app_rev)
    assert p.vista.avisos_archivo.visible is False


# ---------------------------------------------------------------------------
# Diálogo de edición de fila (§4.9, RF-53, CA-53.x)
# ---------------------------------------------------------------------------


def test_dialogo_titulo_botones_y_volver(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "psicologo"))
    assert d.title.value == "Editar fila 7 del Excel"
    assert hay_boton(d, "Aceptar") and hay_boton(d, "Cancelar")
    assert hay_boton(d, "Volver a lo detectado")
    assert not hay_boton(d, "Guardar")
    assert d.modal is True


def test_clic_en_la_fila_tambien_abre_el_dialogo(app_rev):
    # §3.12: clic en el nombre abre §4.9.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    contenedores = [
        c
        for c in de_tipo(f.control, ft.Container)
        if c.on_click is not None and c.expand
    ]
    assert contenedores
    contenedores[0].on_click(None)
    assert dialogo_arriba(p.app).title.value == "Editar fila 15 del Excel"


def test_lapiz_tiene_tooltip_con_el_numero_de_fila(app_rev):
    p = abrir(app_rev)
    assert fv(p, "Gym").lapiz.tooltip == "Editar fila 15"
    assert fv(p, "Gym").lapiz.icon == ft.Icons.EDIT


def test_dialogo_carga_los_valores_de_la_fila(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "psicologo"))
    assert dlg.tipo.value == "fijo"
    assert dlg.nombre.value == "psicologo"
    assert dlg.monto.value == "140.000"
    assert dlg.pagado.value == "60.000"
    assert dlg.cobrado.value is False


def test_dialogo_campos_visibles_segun_el_tipo(app_rev):
    # §4.9: cada tipo muestra solo sus campos.
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    esperado = {
        "fijo": dict(
            pagado=True,
            cat=True,
            cuota=False,
            persona=False,
            cobrado=False,
            sueldo=False,
        ),
        "unico": dict(
            pagado=True,
            cat=True,
            cuota=False,
            persona=False,
            cobrado=False,
            sueldo=False,
        ),
        "cuota": dict(
            pagado=True,
            cat=True,
            cuota=True,
            persona=False,
            cobrado=False,
            sueldo=False,
        ),
        "me_deben": dict(
            pagado=False,
            cat=False,
            cuota=False,
            persona=True,
            cobrado=True,
            sueldo=False,
        ),
        "sueldo": dict(
            pagado=False,
            cat=False,
            cuota=False,
            persona=False,
            cobrado=False,
            sueldo=True,
        ),
        "ignorar": dict(
            pagado=False,
            cat=False,
            cuota=False,
            persona=False,
            cobrado=False,
            sueldo=False,
        ),
    }
    for tipo, e in esperado.items():
        dlg.tipo.value = tipo
        dlg.tipo.on_select(evento(dlg.tipo))
        obtenido = dict(
            pagado=dlg.bloque_pagado.visible,
            cat=dlg.categoria.control.visible,
            cuota=dlg.bloque_cuota.visible,
            persona=dlg.persona.control.visible,
            cobrado=dlg.cobrado.visible,
            sueldo=dlg.ayuda_sueldo.visible,
        )
        assert obtenido == e, tipo


def test_dialogo_conserva_lo_escrito_al_cambiar_de_tipo(app_rev):
    # §4.9: ocultar un bloque no borra lo escrito.
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    dlg.tipo.value = "cuota"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.cuota_actual.value, dlg.cuota_total.value = "2", "6"
    dlg.pagado.value = "10.000"
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.tipo.value = "cuota"
    dlg.tipo.on_select(evento(dlg.tipo))
    assert (dlg.cuota_actual.value, dlg.cuota_total.value, dlg.pagado.value) == (
        "2",
        "6",
        "10.000",
    )


def test_dialogo_sueldo_cambia_etiqueta_a_dolares_y_muestra_ayuda(app_rev):
    # §4.9: "Sueldo" en USD y debajo "Hoy el sueldo de Octubre 2026 es US$ 1.200,00."
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, sin_nombre(p, 19))
    dlg.tipo.value = "sueldo"
    dlg.tipo.on_select(evento(dlg.tipo))
    assert (
        dlg.monto.label == "Sueldo"
        and dlg.monto.prefix == "US$ "
        and dlg.monto.suffix == "USD"
    )
    assert dlg.ayuda_sueldo.value == "Hoy el sueldo de Octubre 2026 es US$ 1.200,00."
    dlg.tipo.value = "fijo"
    dlg.tipo.on_select(evento(dlg.tipo))
    assert dlg.monto.label == "Monto" and dlg.monto.prefix == "$ "


def test_dialogo_sueldo_con_mes_que_se_crea(app_rev):
    p = abrir(app_rev)
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    d, dlg = abrir_fila(p, sin_nombre(p, 19))
    assert dlg.ayuda_sueldo.value == "Noviembre 2026 todavía no existe."


def test_dialogo_aceptar_sueldo_sin_nombre_pasa(app_rev):
    # RN-70: el sueldo no necesita nombre. Se completa en el diálogo y se acepta.
    p = abrir(app_rev)
    f = sin_nombre(p, 19)
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "sueldo"
    dlg.tipo.on_select(evento(dlg.tipo))
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert f.tipo.value == "sueldo" and f.tilde.value is True


def test_ca_53_1_cambiar_nombre_y_monto(app_rev):
    # CA-53.1: "psicologo" -> "Psicólogo" y monto de "Servicios" -> 85.000.
    p = abrir(app_rev)
    f = fv(p, "psicologo")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = "Psicólogo"
    aceptar(dlg)
    assert f.nombre.value == "Psicólogo"
    assert dialogo_arriba(p.app) is None
    s = fv(p, "Servicios")
    d, dlg = abrir_fila(p, s)
    dlg.monto.value = "85.000"
    aceptar(dlg)
    assert s.monto.value == "$ 85.000"
    assert s.fila.monto_cent == 8500000
    assert p.app.page.actualizaciones > 0


def test_dialogo_nombre_con_espacios_se_limpia(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = "   Gym    Sur  "
    aceptar(dlg)
    assert f.nombre.value == "Gym Sur"


def test_dialogo_nombre_vacio_da_error_y_no_cierra(app_rev):
    # §4.9 / RN-68: con tipo que se importa, "Falta el nombre." y el diálogo sigue abierto.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = "  "
    aceptar(dlg)
    assert dlg.nombre.error == "Falta el nombre."
    assert dialogo_arriba(p.app) is d
    assert f.nombre.value == "Gym"  # la fila no cambió
    # Corregir y volver a aceptar limpia el error.
    dlg.nombre.value = "Gym2"
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert f.nombre.value == "Gym2"


def test_dialogo_monto_cero_negativo_y_texto_invalido(app_rev):
    # Montos inválidos: no se puede aceptar y se ve el error bajo el campo.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    for valor, error in [
        ("0", "El monto tiene que ser mayor a 0."),
        ("", "Falta el monto."),
    ]:
        d, dlg = abrir_fila(p, f)
        dlg.monto.value = valor
        aceptar(dlg)
        assert dlg.monto.error == error, valor
        assert dialogo_arriba(p.app) is d
        p.app.cerrar_dialogo(d)
    for valor in ("abc", "-5", "1.2.3,4,5", "99999999999999999999"):
        d, dlg = abrir_fila(p, f)
        dlg.monto.value = valor
        aceptar(dlg)
        assert dlg.monto.error, valor
        assert dialogo_arriba(p.app) is d, valor
        assert f.fila.monto_cent == 5000000
        p.app.cerrar_dialogo(d)


def test_dialogo_pagado_mayor_que_el_monto(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.monto.value = "10.000"
    dlg.pagado.value = "12.000"
    aceptar(dlg)
    assert dlg.pagado.error == "El pagado ($ 12.000) es mayor que el monto ($ 10.000)."
    assert dialogo_arriba(p.app) is d


def test_dialogo_pagado_negativo_o_invalido_no_se_acepta(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    dlg.pagado.value = "-5"
    aceptar(dlg)
    assert dlg.pagado.error
    assert dialogo_arriba(p.app) is d


def test_dialogo_pagado_igual_al_monto_queda_completo(app_rev):
    # §4.9: "Si es igual al monto, queda pagado completo."
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.pagado.value = "50.000"
    aceptar(dlg)
    assert f.estado_pagado.value == "✓ Completo"
    d, dlg = abrir_fila(p, f)
    dlg.pagado.value = "20.000"
    aceptar(dlg)
    assert f.estado_pagado.value == "Parcial · falta $ 30.000"
    d, dlg = abrir_fila(p, f)
    dlg.pagado.value = ""
    aceptar(dlg)
    assert not f.pagado.visible and not f.estado_pagado.visible


def test_dialogo_pagado_cero_no_muestra_pagado(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Internet", 5)
    d, dlg = abrir_fila(p, f)
    dlg.pagado.value = "0"
    aceptar(dlg)
    assert not f.pagado.visible


def test_dialogo_ayuda_del_pagado(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    assert "Lo que ya pagaste. Si es igual al monto, queda pagado completo." in textos(
        dlg.bloque_pagado
    )
    assert dlg.pagado.label == "Pagado (opcional)"


def test_dialogo_cancelar_no_cambia_nada(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = "Otro"
    dlg.monto.value = "1"
    dlg.tipo.value = "ignorar"
    clic(d, "Cancelar")
    assert dialogo_arriba(p.app) is None
    assert (f.fila.nombre, f.fila.monto_cent, f.fila.tipo) == ("Gym", 5000000, "fijo")


def test_volver_a_lo_detectado_restaura_la_fila(app_rev):
    # §4.9: restaura nombre, monto, pagado, tipo y tilde a lo que leyó la app.
    p = abrir(app_rev)
    f = fv(p, "psicologo")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = "Otro nombre"
    dlg.monto.value = "1"
    dlg.pagado.value = ""
    dlg.tipo.value = "unico"
    aceptar(dlg)
    assert f.nombre.value == "Otro nombre"
    d, dlg = abrir_fila(p, f)
    clic(d, "Volver a lo detectado")
    assert dialogo_arriba(p.app) is None
    assert f.nombre.value == "psicologo"
    assert f.monto.value == "$ 140.000"
    assert f.tipo.value == "fijo" and f.tilde.value is True
    assert f.pagado.value == "$ 60.000"
    assert f.estado_pagado.value == "Parcial · falta $ 80.000"


def test_volver_a_lo_detectado_en_fila_ya_existe_la_deja_destildada(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Alquiler")
    tildar(f, True)
    d, dlg = abrir_fila(p, f)
    clic(d, "Volver a lo detectado")
    assert f.tilde.value is False
    assert notas(f) == ["Ya existe en Octubre 2026. Viene destildada."]


def test_volver_a_lo_detectado_con_errores_en_la_fila_los_limpia(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Obra social")
    elegir_tipo(f, "fijo")
    assert p.vista.boton_confirmar.disabled
    d, dlg = abrir_fila(p, f)
    assert dlg.monto.error == "Falta el monto."
    clic(d, "Volver a lo detectado")
    assert f.tipo.value == "ignorar"
    assert p.vista.boton_confirmar.disabled is False


def test_dialogo_foco_inicial_en_el_primer_campo_con_error(app_rev):
    # §4.9: foco inicial en el primer campo con error; si no hay, en Nombre.
    p = abrir(app_rev)
    pagina = p.app.page
    pagina.tareas.clear()
    f = fv(p, "Obra social")
    elegir_tipo(f, "fijo")
    pagina.tareas.clear()
    d, dlg = abrir_fila(p, f)
    assert pagina.tareas[-1] == dlg.monto.focus
    p.app.cerrar_dialogo(d)
    g = fv(p, "Gym")
    pagina.tareas.clear()
    d, dlg = abrir_fila(p, g)
    assert pagina.tareas[-1] == dlg.nombre.focus


def test_ca_53_2_completar_obra_social_con_monto_y_tipo(app_rev):
    # CA-53.2: monto 45.000 + gasto fijo: queda tildada, con categoría, y sigue en "Filas
    # incompletas" (no se mueve de grupo).
    p = abrir(app_rev)
    f = fv(p, "Obra social")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "fijo"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.monto.value = "45.000"
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert f.tipo.value == "fijo" and f.tilde.value is True
    assert f.monto.value == "$ 45.000" and f.categoria.value == "Varios"
    assert f in p.vista.bloque_incompletas.filas
    assert subtitulo(p.vista.bloque_incompletas) == "16 filas · se importan 1"
    assert p.vista.texto_pie.value.startswith("Se importan 10 filas: 6 gastos")
    # La nota "Falta el monto. Se ignora." ya no corresponde (el tipo no es ignorar).
    assert "Falta el monto. Se ignora." not in notas(f)


def test_completar_nombre_de_numero_suelto_en_filas_incompletas(app_rev):
    # §3.12 / RF-53: un número sin nombre se completa en el diálogo.
    p = abrir(app_rev)
    f = sin_nombre(p, 9)
    d, dlg = abrir_fila(p, f)
    assert dlg.tipo.value == "ignorar"
    dlg.nombre.value = "Varios del mes"
    dlg.tipo.value = "unico"
    aceptar(dlg)
    assert f.nombre.value == "Varios del mes" and f.tilde.value is True


def test_ignorar_con_errores_en_el_dialogo_se_puede_aceptar(app_rev):
    # RN-68: con tipo "ignorar" el diálogo se acepta aunque falten datos.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = ""
    dlg.monto.value = ""
    dlg.tipo.value = "ignorar"
    dlg.tipo.on_select(evento(dlg.tipo))
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert f.tipo.value == "ignorar" and f.tilde.value is False
    assert f.nombre.value == "(sin nombre)" and f.monto.value == "(sin monto)"


def test_ignorar_con_monto_ilegible_no_se_acepta(app_rev):
    # Un monto con letras no se puede leer ni siquiera para "ignorar": se muestra el error.
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    dlg.tipo.value = "ignorar"
    dlg.monto.value = "abc"
    aceptar(dlg)
    assert dlg.monto.error
    assert dialogo_arriba(p.app) is d


def test_ca_53_3_gym_a_cuota(app_rev):
    # CA-53.3: sin cuota actual ni cantidad -> error; 2 de 6 -> plan; 7 de 6 -> error; cantidad 0.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "cuota"
    dlg.tipo.on_select(evento(dlg.tipo))
    aceptar(dlg)
    assert dlg.cuota_total.error == "Indicá la cuota actual y la cantidad de cuotas."
    assert dialogo_arriba(p.app) is d
    dlg.cuota_actual.value, dlg.cuota_total.value = "7", "6"
    aceptar(dlg)
    assert (
        dlg.cuota_actual.error
        == "La cuota actual tiene que estar entre 1 y la cantidad de cuotas."
    )
    dlg.cuota_actual.value, dlg.cuota_total.value = "1", "0"
    aceptar(dlg)
    assert (
        dlg.cuota_total.error
        == "La cantidad de cuotas tiene que ser un número entero de 1 o más."
    )
    dlg.cuota_actual.value, dlg.cuota_total.value = "2", "6"
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert (f.cuota.value, f.fila.cuota_actual, f.fila.cuota_total) == ("2/6", 2, 6)
    assert notas(f) == [
        "Plan de 6 cuotas: primera Septiembre 2026, última Febrero 2027. "
        "Se agrega la cuota 2/6 en Octubre 2026."
    ]


def test_dialogo_cuota_vista_previa_se_actualiza_en_cada_tecla(app_rev):
    # §4.9: vista previa del plan en recuadro info, solo con datos válidos, con el mes destino.
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    dlg.tipo.value = "cuota"
    dlg.tipo.on_select(evento(dlg.tipo))
    assert dlg.vista_plan.visible is False
    dlg.cuota_actual.value, dlg.cuota_total.value = "3", "3"
    dlg.cuota_actual.on_change(evento(dlg.cuota_actual))
    assert dlg.vista_plan.visible is True
    assert dlg.texto_plan.value == (
        "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. "
        "Se agrega la cuota 3/3 en Octubre 2026."
    )
    dlg.cuota_actual.value = "9"
    dlg.cuota_actual.on_change(evento(dlg.cuota_actual))
    assert dlg.vista_plan.visible is False
    dlg.cuota_total.value = "1"
    dlg.cuota_actual.value = "1"
    dlg.cuota_total.on_change(evento(dlg.cuota_total))
    assert dlg.texto_plan.value.startswith(
        "Plan de 1 cuota: primera Octubre 2026, última Octubre 2026."
    )
    assert "Ej.: cuota 3 de 12" in textos(dlg.bloque_cuota)


def test_dialogo_cuota_campos_solo_numeros(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    assert dlg.cuota_actual.input_filter is not None
    assert dlg.cuota_actual.input_filter.regex_string == r"[0-9]"
    assert dlg.cuota_total.input_filter.regex_string == r"[0-9]"
    assert (
        dlg.cuota_actual.label == "Cuota actual"
        and dlg.cuota_total.label == "Cantidad de cuotas"
    )


def test_dialogo_cuota_con_texto_no_numerico_pegado(app_rev):
    # El filtro de Flet impide escribir "2,5"; si llegara igual, la pantalla no tiene que
    # romperse ni dejar aceptar el diálogo.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "cuota"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.cuota_actual.value, dlg.cuota_total.value = "1", "2,5"
    aceptar(dlg)
    assert dlg.cuota_total.error
    assert dialogo_arriba(p.app) is d
    assert f.fila.tipo == "fijo"


def test_ca_53_7_tope_de_600_cuotas(app_rev):
    # CA-53.7: 1 de 601 -> "La cantidad de cuotas es demasiado grande." y no se acepta;
    # 1 de 600 -> nota "Plan de 600 cuotas: primera Octubre 2026, última Septiembre 2076...".
    p = abrir(app_rev)
    f = fv(p, "Avant Service cuota 3/ 3 $41.116,66")
    d, dlg = abrir_fila(p, f)
    dlg.cuota_actual.value, dlg.cuota_total.value = "1", "601"
    dlg.cuota_total.on_change(evento(dlg.cuota_total))
    assert dlg.vista_plan.visible is False  # sin vista previa con 601 cuotas
    aceptar(dlg)
    assert dlg.cuota_total.error == "La cantidad de cuotas es demasiado grande."
    assert dialogo_arriba(p.app) is d
    dlg.cuota_total.value = "600"
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert notas(f) == [
        "Plan de 600 cuotas: primera Octubre 2026, última Septiembre 2076. "
        "Se agrega la cuota 1/600 en Octubre 2026."
    ]


def test_ca_53_4_servicios_a_me_deben_sin_persona(app_rev):
    # CA-53.4: la persona viene vacía, "Elegí persona" en la fila y "Elegí una persona." de error.
    p = abrir(app_rev)
    f = fv(p, "Servicios")
    elegir_tipo(f, "me_deben")
    assert f.categoria.value == "Elegí persona"
    assert "Elegí una persona." in notas(f)
    assert p.vista.boton_confirmar.disabled is True


def test_ca_53_4_dialogo_sin_persona_no_se_acepta(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Servicios")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    aceptar(dlg)
    assert dlg.persona.dropdown.error_text == "Elegí una persona."
    assert dialogo_arriba(p.app) is d


def test_ca_53_4_crear_juan_y_elegirlo(app_rev, base):
    # CA-53.4: crear la persona nueva "Juan" desde el "+" y elegirla: la fila queda
    # "me deben" Juan (nueva), sin error. En la base NO se crea nada.
    antes = foto(base.con)
    p = abrir(app_rev)
    f = fv(p, "Servicios")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    [mas] = [
        b
        for b in de_tipo(dlg.persona.control, ft.IconButton)
        if b.tooltip == "Nueva persona"
    ]
    mas.on_click(None)
    assert dlg.persona.nombre.label == "Nombre de la persona"
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    assert dlg.persona.dropdown.value == "nueva:Juan"
    assert "Juan (nueva)" in [o.text for o in dlg.persona.dropdown.options]
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert f.categoria.value == "Juan (nueva)"
    assert f.fila.persona == Nueva("Juan") and f.fila.cobrado is False
    assert p.lista.personas_nuevas == [Nueva("Juan")]
    assert p.vista.boton_confirmar.disabled is False
    assert foto(base.con) == antes
    assert "Juan" not in [
        x["nombre"] for x in catalogos.listar(base.con, catalogos.PERSONAS, True)
    ]


def test_ca_53_4_persona_nueva_se_elige_en_otras_filas(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    aceptar(dlg)
    d2, dlg2 = abrir_fila(p, fv(p, "Gym"))
    dlg2.tipo.value = "me_deben"
    dlg2.tipo.on_select(evento(dlg2.tipo))
    assert "Juan (nueva)" in [o.text for o in dlg2.persona.dropdown.options]


def test_ca_53_4_persona_sofia_con_acento_y_mayuscula_se_rechaza(app_rev):
    # CA-53.4: "sofía" -> 'Ya existe una persona llamada "Sofía".' (comparación sin mayúsculas
    # ni acentos: también "SOFIA").
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    for escrito in ("sofía", "SOFIA", "  Sofia  "):
        dlg.persona.nombre.value = escrito
        dlg.persona.agregar()
        assert dlg.persona.nombre.error == 'Ya existe una persona llamada "Sofía".', (
            escrito
        )
    assert p.lista.personas_nuevas == []
    assert dlg.persona.fila_nueva.visible


def test_persona_nueva_vacia_o_repetida_en_la_revision(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = ""
    dlg.persona.agregar()
    assert dlg.persona.nombre.error == "Ingresá un nombre."
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    dlg.persona.abrir()
    dlg.persona.nombre.value = "juan"
    dlg.persona.agregar()
    assert (
        dlg.persona.nombre.error
        == 'Ya agregaste una persona llamada "Juan" en esta importación.'
    )


def test_persona_archivada_se_rechaza_con_el_mensaje_de_archivada(app_rev, base):
    id_ = catalogos.crear(base.con, catalogos.PERSONAS, "Lucho")
    archivar(base.con, catalogos.PERSONAS, id_)
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "lucho"
    dlg.persona.agregar()
    assert dlg.persona.nombre.error == (
        'Ya existe una persona llamada "Lucho" (está archivada). Podés desarchivarla en Ajustes.'
    )


def test_cancelar_la_fila_en_linea_la_cierra_y_limpia(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "Ju"
    clic(dlg.persona.fila_nueva, "Cancelar")
    assert dlg.persona.fila_nueva.visible is False
    assert dlg.persona.nombre.value == ""
    assert dialogo_arriba(p.app) is d  # el diálogo sigue abierto


def test_enter_en_la_fila_en_linea_agrega(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "Juan"
    dlg.persona.nombre.on_submit(None)
    assert p.lista.personas_nuevas == [Nueva("Juan")]


def test_persona_nueva_no_usada_no_aparece_para_crear(app_rev):
    # RN-72: la persona nueva solo se crea si queda en uso; mientras tanto vive en la lista.
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    aceptar(dlg)
    elegir_tipo(fv(p, "Servicios"), "ignorar")
    assert p.lista.nuevas_en_uso() == ([], [])


def test_dialogo_me_deben_cobrado_con_switch(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Prestamo MP")
    d, dlg = abrir_fila(p, f)
    assert dlg.cobrado.label == "Ya me lo pagaron (cobrado)"
    assert dlg.persona.dropdown.value == f"id:{p.lista.filas[f.indice].persona}"
    dlg.cobrado.value = True
    aceptar(dlg)
    assert f.cobrado.value is True and f.fila.cobrado is True


def test_dialogo_me_deben_elegir_otra_persona(app_rev, base):
    p = abrir(app_rev)
    f = fv(p, "Prestamo MP")
    d, dlg = abrir_fila(p, f)
    dlg.persona.dropdown.value = f"id:{base.marsu}"
    aceptar(dlg)
    assert f.categoria.value == "Marsu"


def test_dialogo_pagado_de_me_deben_se_descarta(app_rev):
    # Un "pagado" escrito antes de pasar a "me deben" no se guarda en la fila.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.pagado.value = "10.000"
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.dropdown.value = (
        f"id:{p.lista.filas[0].persona or 0}"
        if False
        else dlg.persona.dropdown.options[0].key
    )
    aceptar(dlg)
    assert f.fila.pagado_cent is None
    assert not f.pagado.visible


def test_esc_en_el_dialogo_lo_cierra_sin_aplicar_cambios(app_rev):
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.nombre.value = "Otro"
    p.app._al_presionar_tecla(tecla("Escape"))
    assert dialogo_arriba(p.app) is None
    assert f.fila.nombre == "Gym"
    assert p.app._importacion is p  # Esc cerró el diálogo, no canceló la importación


# O86 (corregido).
def test_esc_con_la_fila_en_linea_del_dialogo_cierra_solo_esa_fila(app_rev):
    # §4.11: "Esc cierra solo esa fila (no el diálogo)".
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    p.app._al_presionar_tecla(tecla("Escape"))
    assert dialogo_arriba(p.app) is d
    assert dlg.persona.fila_nueva.visible is False


# ---------------------------------------------------------------------------
# Diálogo del bloque (§4.10, RN-78, CA-53.5, CA-53.6)
# ---------------------------------------------------------------------------


def test_dialogo_bloque_titulo_ayuda_y_botones(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas sofia")
    assert d.title.value == "Cambiar las filas de Deudas sofia"
    assert hay_boton(d, "Cancelar") and hay_boton(d, "Aplicar a las 3 filas")
    assert (
        "Se cambian las 3 filas de este bloque, incluidas las que están ignoradas. "
        "Después podés ajustar cada una."
    ) in textos(d)
    assert dlg.tipo.value == ""
    assert dlg.tipo.options[0].text == "No cambiar el tipo"


def test_dialogo_bloque_sin_ignoradas_no_dice_incluidas(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    assert (
        "Se cambian las 3 filas de este bloque. Después podés ajustar cada una."
        in textos(d)
    )


def test_dialogo_bloque_una_sola_fila_en_singular(app_rev):
    p = abrir(app_rev, xlsx({"C1": "Titulo", "C2": "Luz", "D2": 1000}))
    d, dlg = abrir_bloque(p, "Titulo")
    assert hay_boton(d, "Aplicar a la fila")
    assert (
        "Se cambian la fila de este bloque. Después podés ajustar cada una."
        in textos(d)
    )


def test_dialogo_bloque_cuota_y_sueldo_deshabilitados_con_tooltip(app_rev):
    # CA-53.5: "Cuota" y "Sueldo (USD)" no se pueden elegir como tipo.
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas sofia")
    por_clave = {o.key: o for o in dlg.tipo.options}
    assert por_clave["cuota"].disabled is True
    assert por_clave["cuota"].tooltip == "La cuota se elige fila por fila."
    assert por_clave["sueldo"].disabled is True
    assert por_clave["sueldo"].tooltip == "Solo una fila puede ser el sueldo."
    assert not por_clave["fijo"].disabled and not por_clave["ignorar"].disabled


def test_dialogo_bloque_campos_segun_el_tipo(app_rev):
    # §4.10: sin tipo, persona y categoría; "me deben", solo persona; gasto, solo categoría;
    # ignorar, ninguno.
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas sofia")
    esperado = {
        "": (True, True),
        "me_deben": (True, False),
        "fijo": (False, True),
        "unico": (False, True),
        "ignorar": (False, False),
    }
    for tipo, (persona, categoria) in esperado.items():
        dlg.tipo.value = tipo
        dlg.tipo.on_select(evento(dlg.tipo))
        assert (dlg.persona.control.visible, dlg.categoria.control.visible) == (
            persona,
            categoria,
        ), tipo


def test_ca_53_5_sofia_y_marsu_con_persona_marsu(app_rev, base):
    # CA-53.5: título "Sofía y Marsu": filas 22 y 23 "me deben" sin persona; con "No cambiar
    # el tipo" y persona Marsu quedan "me deben" Marsu; la 24 ("Total") sigue ignorada y sin tilde.
    p = abrir(app_rev, planilla_con({"D21": "Sofía y Marsu"}))
    d, dlg = abrir_bloque(p, "Sofía y Marsu")
    dlg.persona.dropdown.value = f"id:{base.marsu}"
    clic(d, "Aplicar a las 3 filas")
    assert dialogo_arriba(p.app) is None
    b = bloque(p, "Sofía y Marsu")
    assert [f.categoria.value for f in b.filas[:2]] == ["Marsu", "Marsu"]
    assert [f.tipo.value for f in b.filas] == ["me_deben", "me_deben", "ignorar"]
    assert b.filas[2].tilde.value is False
    assert p.vista.boton_confirmar.disabled is False


def test_ca_53_6_deudas_sofia_a_gasto_unico_en_servicios(app_rev, base):
    # CA-53.6: 22, 23 y 24 quedan gasto único en Servicios y tildadas (la 24 se tilda sola).
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas sofia")
    dlg.tipo.value = "unico"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.categoria.dropdown.value = f"id:{base.servicios}"
    clic(d, "Aplicar a las 3 filas")
    for f in bloque(p, "Deudas sofia").filas:
        assert f.tipo.value == "unico" and f.tilde.value is True, f.nombre.value
        assert f.categoria.value == "• Servicios"


def test_ca_53_6_deudas_no_cambia_tipo_y_pone_vivienda_sin_tocar_incompletas(
    app_rev, base
):
    # CA-53.6: en "Deudas", "No cambiar el tipo" + Vivienda: Monotributo, Avant y Gym quedan
    # en Vivienda y siguen así si la por defecto pasa a Servicios; "Deuda freezer" y "Obra
    # social" no cambian.
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.categoria.dropdown.value = f"id:{base.vivienda}"
    clic(d, "Aplicar a las 3 filas")
    nombres = ["Monotributo 66.020,12", "Avant Service cuota 3/ 3 $41.116,66", "Gym"]
    assert [fv(p, n).categoria.value for n in nombres] == ["• Vivienda"] * 3
    c = p.vista.categoria_defecto
    c.dropdown.value = f"id:{base.servicios}"
    c.dropdown.on_select(evento(c.dropdown))
    assert [fv(p, n).categoria.value for n in nombres] == ["• Vivienda"] * 3
    assert fv(p, "Servicios").categoria.value == "Servicios"
    for n in ("Deuda freezer", "Obra social"):
        assert fv(p, n).tipo.value == "ignorar" and fv(p, n).categoria.value == ""
        assert fv(p, n).fila.categoria is None


def test_dialogo_bloque_me_deben_sin_persona_da_error_y_no_cierra(app_rev):
    # §4.10: con tipo "Me deben" la persona es obligatoria.
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    clic(d, "Aplicar a las 3 filas")
    assert dlg.persona.dropdown.error_text == "Elegí una persona."
    assert dialogo_arriba(p.app) is d
    assert fv(p, "Gym").tipo.value == "fijo"


def test_dialogo_bloque_a_me_deben_con_persona_nueva(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    clic(d, "Aplicar a las 3 filas")
    assert [fv(p, n).categoria.value for n in ("Gym", "Monotributo 66.020,12")] == [
        "Juan (nueva)",
        "Juan (nueva)",
    ]
    assert p.vista.boton_confirmar.disabled is False


def test_dialogo_bloque_a_ignorar_deja_todo_sin_tilde(app_rev):
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.tipo.value = "ignorar"
    dlg.tipo.on_select(evento(dlg.tipo))
    clic(d, "Aplicar a las 3 filas")
    assert [f.tilde.value for f in bloque(p, "Deudas").filas] == [False] * 3
    assert subtitulo(bloque(p, "Deudas")) == "filas 12 a 15 · se importan 0 de 3"


def test_dialogo_bloque_sin_cambios_no_hace_nada(app_rev):
    # "Un campo que se deja sin elegir no cambia nada".
    p = abrir(app_rev)
    antes = [
        (f.fila.tipo, f.fila.categoria, f.fila.persona, f.fila.tildada)
        for f in p.vista.filas
    ]
    d, dlg = abrir_bloque(p, "Deudas sofia")
    clic(d, "Aplicar a las 3 filas")
    assert antes == [
        (f.fila.tipo, f.fila.categoria, f.fila.persona, f.fila.tildada)
        for f in p.vista.filas
    ]


def test_dialogo_bloque_cancelar_no_cambia_nada(app_rev, base):
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.categoria.dropdown.value = f"id:{base.vivienda}"
    clic(d, "Cancelar")
    assert fv(p, "Gym").categoria.value == "Varios"


def test_dialogo_bloque_categoria_por_defecto_vuelve_a_seguir_la_por_defecto(
    app_rev, base
):
    # La primera opción "Categoría por defecto" quita la categoría propia de las filas.
    p = abrir(app_rev)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.categoria.dropdown.value = f"id:{base.vivienda}"
    clic(d, "Aplicar a las 3 filas")
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.categoria.dropdown.value = "defecto"
    clic(d, "Aplicar a las 3 filas")
    assert fv(p, "Gym").categoria.value == "Varios"
    assert fv(p, "Gym").categoria.tooltip is None


# ---------------------------------------------------------------------------
# Teclado, cambiar de archivo, cancelar (aplicacion.py y pantalla_importar.py)
# ---------------------------------------------------------------------------


def test_ctrl_enter_abre_el_resumen_previo_y_no_guarda_nada(app_rev):
    # 8e: Ctrl+Enter abre "Revisá antes de importar"; todavía no se escribe nada en la base.
    antes = foto(app_rev.con)
    p = abrir(app_rev)
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    d = dialogo_arriba(app_rev)
    assert d is not None and d.title.value == "Revisá antes de importar"
    assert foto(app_rev.con) == antes


def test_clic_en_confirmar_hace_lo_mismo_que_ctrl_enter(app_rev):
    # Tocar "Confirmar importación" abre el mismo resumen previo que Ctrl+Enter.
    p = abrir(app_rev)
    clic(p.vista.control, "Confirmar importación")
    assert dialogo_arriba(app_rev).title.value == "Revisá antes de importar"


def test_ctrl_enter_con_el_boton_deshabilitado_no_hace_nada(app_rev):
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "cuota")
    n = len(p.app.page.avisos())
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    assert len(p.app.page.avisos()) == n


def test_enter_solo_sin_ctrl_no_confirma(app_rev):
    p = abrir(app_rev)
    n = len(p.app.page.avisos())
    app_rev._al_presionar_tecla(tecla("Enter"))
    assert len(p.app.page.avisos()) == n


def test_cmd_enter_en_macos_confirma_y_ctrl_enter_no(pagina, con, base):
    # En macOS confirma Cmd+Enter; Ctrl+Enter no hace nada.
    import flet as ft_

    pagina.platform = ft_.PagePlatform.MACOS
    app = Aplicacion(pagina, con)
    app.iniciar()
    abrir(app)
    app._al_presionar_tecla(tecla("Enter", ctrl=True))
    assert not app.hay_dialogo_abierto()
    app._al_presionar_tecla(tecla("Enter", meta=True))
    assert dialogo_arriba(app).title.value == "Revisá antes de importar"


def test_ctrl_enter_con_un_dialogo_abierto_no_confirma(app_rev):
    p = abrir(app_rev)
    abrir_fila(p, fv(p, "Gym"))
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    assert not p.app.page.avisos()


def test_ctrl_enter_en_la_pantalla_de_elegir_archivo_no_hace_nada(app_rev):
    ir(app_rev, "Ajustes")
    ajustes = app_rev.pantalla("Ajustes")
    ajustes.pestanas.selected_index = ajustes.indice_de(ajustes.importar)
    clic(ajustes.importar.control, "Importar Excel")
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    assert not app_rev.page.avisos()


def test_esc_cancela_la_importacion_sin_cambios(app_rev):
    p = abrir(app_rev)
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert app_rev._importacion is None


def test_esc_con_la_fila_de_nueva_categoria_abierta_cierra_solo_esa_fila(app_rev):
    # El pedido: Esc cierra la fila en línea y no cancela la importación; el segundo Esc cancela.
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    c.abrir()
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert c.fila_nueva.visible is False
    assert app_rev._importacion is p
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert app_rev._importacion is None


def test_los_atajos_de_la_app_no_actuan_durante_la_revision(app_rev):
    p = abrir(app_rev)
    for t in (tecla("1", ctrl=True), tecla("N", ctrl=True), tecla("K", ctrl=True)):
        app_rev._al_presionar_tecla(t)
    assert app_rev._importacion is p
    assert not app_rev.hay_dialogo_abierto()


def test_cambiar_archivo_u_hoja_vuelve_a_la_tarjeta_de_inicio(app_rev):
    p = abrir(app_rev)
    clic(p.vista.control, "Cambiar archivo u hoja")
    assert p.vista is None and p.lista is None
    assert p.control.content is p._elegir
    assert hay_boton(p.tarjeta, "Elegir archivo...")


def test_cambiar_archivo_y_elegir_otro_arma_una_lista_nueva(app_rev):
    # La lista vieja (con sus cambios) no se reutiliza.
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "ignorar")
    vieja = p.lista
    clic(p.vista.control, "Cambiar archivo u hoja")
    leer(p, "planilla-prueba.xlsx", planilla_prueba())
    assert p.lista is not vieja
    assert fv(p, "Gym").tipo.value == "fijo"


def test_dos_hojas_cada_una_arma_su_lista(app_rev):
    libro = armar_libro(
        {
            "Octubre": {"C3": "Luz", "D3": 1000},
            "Septiembre": {"C3": "Agua", "D3": 300, "C4": "Gas", "D4": 400},
        }
    )
    p = abrir(app_rev, a_bytes(libro))
    p.selector_hojas.value = "Septiembre"
    pagina = p.app.page
    tareas = []
    pagina.run_task = lambda f, *a: tareas.append((f, a))
    clic(p.tarjeta, "Revisar filas")
    f, a = tareas[-1]
    asyncio.run(f(*a))
    assert p.lista.hoja.nombre == "Septiembre"
    assert [x.fila.nombre for x in p.vista.filas] == ["Agua", "Gas"]
    assert p.control.content is p.vista.control


def test_cancelar_desde_la_lista_vuelve_a_ajustes(app_rev):
    p = abrir(app_rev)
    clic(p.vista.control, "Cancelar")
    assert app_rev._importacion is None
    assert p.vista is not None or True  # la pantalla se descarta


# ---------------------------------------------------------------------------
# Nada se escribe en la base durante la revisión (RF-57, §3.12)
# ---------------------------------------------------------------------------


def test_nada_se_escribe_en_la_base_durante_toda_la_revision(app_rev, base):
    # Una sesión larga: cambios de tipo, tilde, mes, categoría por defecto, categoría y persona
    # nuevas, edición de filas y acciones de bloque. La base queda idéntica (todas las tablas).
    antes = foto(base.con)
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "unico")
    tildar(fv(p, "Servicios"), False)
    cobrado(fv(p, "Prestamo MP"), True)
    c = p.vista.categoria_defecto
    c.abrir()
    c.nombre.value = "Importado"
    c.agregar()
    d, dlg = abrir_fila(p, fv(p, "Servicios"))
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.persona.abrir()
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    aceptar(dlg)
    d, dlg = abrir_bloque(p, "Deudas")
    dlg.categoria.dropdown.value = f"id:{base.vivienda}"
    clic(d, "Aplicar a las 3 filas")
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    menu_bloque(bloque(p, "Marsu"), "Destildar todas las filas")
    elegir_tipo(sin_nombre(p, 19), "sueldo")
    d, dlg = abrir_fila(p, fv(p, "Obra social"))
    dlg.monto.value = "45.000"
    dlg.tipo.value = "fijo"
    aceptar(dlg)
    filtrar(p, "importan")
    clic(p.vista.control, "Cambiar archivo u hoja")
    assert foto(base.con) == antes


def test_importar_el_archivo_no_cambia_la_base_ni_crea_personas_ni_categorias(
    app_rev, base
):
    antes = foto(base.con)
    abrir(app_rev, planilla_con({"D21": "Deudas Juan"}))
    assert foto(base.con) == antes


def test_la_logica_no_importa_nada_de_la_interfaz():
    # La lógica (app/logica/) nunca importa app.interfaz ni flet, tampoco con los cambios de 8c/8d.
    raiz = pathlib.Path(__file__).resolve().parents[1] / "app" / "logica"
    for archivo in raiz.glob("*.py"):
        arbol = ast.parse(archivo.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                modulos = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                modulos = [nodo.module or ""]
            else:
                continue
            for m in modulos:
                assert not (m.startswith("app.interfaz") or m.startswith("flet")), (
                    f"{archivo.name} importa {m}"
                )


# ---------------------------------------------------------------------------
# Lógica nueva del 8c/8d: notas_con_clase, errores_por_campo, texto_plan
# ---------------------------------------------------------------------------


def lista_de(app, contenido=None):
    return abrir(app, contenido).lista


def test_notas_usa_los_mismos_textos_que_notas_con_clase(app_rev):
    lista = lista_de(app_rev)
    for f in lista.filas:
        assert lista.notas(f) == [t for _, t in lista.notas_con_clase(f)]


def test_las_clases_de_nota_son_las_cinco_documentadas(app_rev):
    lista = lista_de(app_rev)
    clases = {c for f in lista.filas for c, _ in lista.notas_con_clase(f)}
    assert clases <= {"ignorada", "aviso", "repetida", "compartido", "info"}
    assert {"ignorada", "aviso", "compartido", "info"} <= clases


def test_monto_negativo_del_excel_es_aviso_de_monto_no_valido(app_rev):
    # RN-68: una fila con descuento viene "ignorar" con la nota; la clase es "aviso" y se ve
    # con WARNING_AMBER en la lista.
    p = abrir(app_rev, xlsx({"C3": "Descuento", "D3": -5000, "C4": "Luz", "D4": 1000}))
    f = fv(p, "Descuento")
    assert f.tipo.value == "ignorar" and f.tilde.value is False
    assert notas(f) == ["Monto no válido. Si querés importarla, corregí el monto."]
    assert iconos(f) == [ft.Icons.WARNING_AMBER]
    assert f.monto.value != "(sin monto)"
    # Al pasarla a gasto fijo sin corregir el monto, error.
    elegir_tipo(f, "fijo")
    assert "El monto tiene que ser mayor a 0." in notas(f)


def test_errores_por_campo_publico(app_rev):
    lista = lista_de(app_rev)
    gym = next(f for f in lista.filas if f.nombre == "Gym")
    assert lista.errores_por_campo(gym) == {}
    lista.cambiar_tipo(gym.indice, "cuota")
    assert list(lista.errores_por_campo(gym)) == ["cuota"]
    lista.cambiar_tipo(gym.indice, "me_deben")
    assert lista.errores_por_campo(gym) == {"persona": "Elegí una persona."}
    lista.cambiar_tilde(gym.indice, False)
    assert lista.errores_por_campo(gym) == {}


@pytest.mark.parametrize(
    "n,total,esperado",
    [
        (
            3,
            3,
            "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. "
            "Se agrega la cuota 3/3 en Octubre 2026.",
        ),
        (
            1,
            1,
            "Plan de 1 cuota: primera Octubre 2026, última Octubre 2026. "
            "Se agrega la cuota 1/1 en Octubre 2026.",
        ),
        (
            1,
            600,
            "Plan de 600 cuotas: primera Octubre 2026, última Septiembre 2076. "
            "Se agrega la cuota 1/600 en Octubre 2026.",
        ),
        (601, 601, None),
        (1, 601, None),
        (0, 5, None),
        (7, 6, None),
        (None, 6, None),
        (2, None, None),
        (-1, 3, None),
        ("2", 6, None),
        (2.5, 6, None),
        (True, 3, None),
    ],
)
def test_texto_plan(app_rev, n, total, esperado):
    # texto_plan: None si la cuota no es válida o el año queda fuera de rango.
    lista = lista_de(app_rev)
    assert lista.texto_plan(n, total) == esperado


def test_texto_plan_con_anio_fuera_de_rango(con, mes_id):
    # Destino con el año al límite: 1000-01 con cuota 2/3 deja la primera en 999-12 (no válido).
    from tests.ayudantes_excel import planilla_prueba as pp
    from app.logica.importar_excel import abrir_libro
    from app.logica.revision_importacion import ListaRevision

    meses.borrar_ultimo_mes(con, mes_id)
    meses.crear_primer_mes(con, 1000, 1, 120000, 160000)
    lista = ListaRevision(
        con, abrir_libro(pp()).leer_hoja("Octubre"), hoy=date(1000, 1, 1)
    )
    assert lista.texto_plan(2, 3) is None
    assert lista.texto_plan(1, 3).startswith("Plan de 3 cuotas: primera Enero 1000")


# ---------------------------------------------------------------------------
# Más casos de tipos propuestos y bordes vistos desde la pantalla
# ---------------------------------------------------------------------------


def test_ca_52_3_titulo_con_persona_inexistente_viene_como_gasto_fijo(app_rev):
    # CA-52.3: "Deudas Juan" (Juan no existe): las filas 22 y 23 vienen como gasto fijo.
    p = abrir(app_rev, planilla_con({"D21": "Deudas Juan"}))
    assert fv(p, "Prestamo MP").tipo.value == "fijo"
    assert fv(p, "Internet", 23).tipo.value == "fijo"
    assert fv(p, "Prestamo MP").categoria.value == "Varios"


def test_ca_52_3_marsu_archivada_tacones_viene_como_gasto_fijo(app_rev, base):
    archivar(base.con, "personas", base.marsu)
    p = abrir(app_rev)
    assert fv(p, "tacones chiqui baby").tipo.value == "fijo"


def test_ca_52_4_titulo_combinado_da_el_mismo_resultado(app_rev):
    # CA-52.4: título "Deudas sofia" como celda combinada D21:E21.
    celdas = celdas_planilla()
    p = abrir(app_rev, xlsx(celdas, combinadas={"Octubre": ["D21:E21"]}))
    assert [b.titulo for b in p.vista.bloques] == list(ESPERADA)
    assert [f.tipo.value for f in bloque(p, "Deudas sofia").filas] == [
        "me_deben",
        "me_deben",
        "ignorar",
    ]


def test_ca_52_2_cuotas_y_falsas_cuotas_en_la_lista(app_rev):
    # CA-52.2: "Heladera 2/12" cuota 2/12; "Cumple 15/10" y "Algo 601/601" gasto fijo;
    # "Heladera 1/1" cuota 1/1 con nota en singular.
    p = abrir(
        app_rev,
        xlsx(
            {
                "C1": "Heladera 2/12",
                "D1": 30000,
                "C2": "Cumple 15/10",
                "D2": 5000,
                "C3": "Algo 601/601",
                "D3": 1000,
                "C4": "Algo 1/600",
                "D4": 1000,
                "C5": "Heladera 1/1",
                "D5": 30000,
            }
        ),
    )
    por_nombre = {f.fila.nombre: f for f in p.vista.filas}
    assert (
        por_nombre["Heladera 2/12"].tipo.value,
        por_nombre["Heladera 2/12"].cuota.value,
    ) == ("cuota", "2/12")
    assert por_nombre["Cumple 15/10"].tipo.value == "fijo"
    assert por_nombre["Algo 601/601"].tipo.value == "fijo"
    assert por_nombre["Algo 1/600"].cuota.value == "1/600"
    assert notas(por_nombre["Heladera 1/1"]) == [
        "Plan de 1 cuota: primera Octubre 2026, última Octubre 2026. Se agrega la cuota 1/1 en Octubre 2026."
    ]


def test_categoria_elegida_a_mano_se_conserva_al_cambiar_de_tipo_en_la_lista(
    app_rev, base
):
    # RN-75: cambiar el tipo con el selector no pierde la categoría propia.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.categoria.dropdown.value = clave_cat(base.salud)
    aceptar(dlg)
    elegir_tipo(f, "unico")
    assert f.categoria.value == "• Salud"
    elegir_tipo(f, "ignorar")
    elegir_tipo(f, "fijo")
    assert f.categoria.value == "• Salud"


def test_categoria_por_defecto_nueva_se_muestra_con_nueva(app_rev):
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    c.abrir()
    c.nombre.value = "Mascotas"
    c.agregar()
    assert fv(p, "Gym").categoria.value == "Mascotas (nueva)"
    assert p.lista.nuevas_en_uso()[0] == [Nueva("Mascotas")]
    # Si ninguna fila la usa, no se crearía: cambiar la por defecto a otra y a mano en todas.
    c.dropdown.value = clave_cat(1)
    c.dropdown.on_select(evento(c.dropdown))
    assert p.lista.nuevas_en_uso()[0] == []


def test_el_dialogo_permite_crear_un_segundo_sueldo_y_la_lista_lo_marca(app_rev):
    # Observación: el diálogo no valida la cantidad de sueldos (la lógica quita ese error en
    # editar_fila); la lista sí lo marca en las dos filas y bloquea la confirmación.
    p = abrir(app_rev)
    elegir_tipo(sin_nombre(p, 19), "sueldo")
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    dlg.tipo.value = "sueldo"
    dlg.tipo.on_select(evento(dlg.tipo))
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert "Marcaste 2 filas como sueldo; dejá una sola." in notas(fv(p, "Gym"))
    assert p.vista.boton_confirmar.disabled is True


def test_sueldo_cero_o_vacio_en_el_dialogo(app_rev):
    p = abrir(app_rev)
    f = sin_nombre(p, 19)
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "sueldo"
    dlg.tipo.on_select(evento(dlg.tipo))
    for valor, error in (
        ("0", "El monto tiene que ser mayor a 0."),
        ("", "Falta el monto."),
    ):
        dlg.monto.value = valor
        aceptar(dlg)
        assert dlg.monto.error == error
        assert dialogo_arriba(p.app) is d


def test_bloque_unico_filas_detectadas_acepta_acciones(app_rev):
    p = abrir(app_rev, xlsx({"C3": "Luz", "D3": 1000, "C4": "Gas", "D4": 2000}))
    d, dlg = abrir_bloque(p, "Filas detectadas")
    assert d.title.value == "Cambiar las filas de Filas detectadas"
    dlg.tipo.value = "ignorar"
    dlg.tipo.on_select(evento(dlg.tipo))
    clic(d, "Aplicar a las 2 filas")
    assert p.vista.texto_pie.value == "No hay filas para importar."


def test_categoria_por_defecto_archivada_durante_la_revision_marca_error(app_rev, base):
    # O80: si "Varios" se archiva mientras dura la revisión, las filas piden "Elegí una categoría."
    # y el dropdown muestra el error; no se rompe nada.
    p = abrir(app_rev)
    archivar(base.con, "categorias", base.varios)
    elegir_tipo(fv(p, "Gym"), "fijo")
    assert p.vista.categoria_defecto.dropdown.value is None
    assert (
        p.vista.categoria_defecto.dropdown.error_text
        == "Elegí una categoría para los gastos y cuotas."
    )
    assert "Elegí una categoría." in notas(fv(p, "Gym"))
    assert p.vista.boton_confirmar.disabled is True


def test_sueldo_unico_sin_otras_filas_pie_en_singular(app_rev):
    p = abrir(app_rev, xlsx({"B2": 1300}))
    elegir_tipo(p.vista.filas[0], "sueldo")
    assert p.vista.texto_pie.value == "Se importa 1 fila: el sueldo."
    assert p.vista.boton_confirmar.disabled is False


def test_fila_incompleta_completada_aparece_con_el_filtro_se_importan(app_rev):
    # §3.12: una fila completada no se mueve del grupo "Filas incompletas"; con el filtro
    # "Se importan" el grupo se ve solo con esa fila.
    p = abrir(app_rev)
    f = fv(p, "Obra social")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "fijo"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.monto.value = "45.000"
    aceptar(dlg)
    filtrar(p, "importan")
    assert p.vista.bloque_incompletas.control.visible is True
    assert [
        x.fila.nombre for x in p.vista.bloque_incompletas.filas if x.control.visible
    ] == ["Obra social"]


# BUG-37 (corregido).
def test_cuotas_con_miles_de_digitos_no_rompen_el_dialogo(app_rev):
    # Un texto de 5000 dígitos pegado en "Cantidad de cuotas" tiene que dar el error de
    # "demasiado grande" (o ignorarse), no una excepción.
    p = abrir(app_rev)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    dlg.tipo.value = "cuota"
    dlg.tipo.on_select(evento(dlg.tipo))
    dlg.cuota_actual.value, dlg.cuota_total.value = "1", "9" * 5000
    dlg.cuota_total.on_change(evento(dlg.cuota_total))
    aceptar(dlg)
    assert dlg.cuota_total.error
    assert dialogo_arriba(p.app) is d


def test_primer_uso_anio_de_cuatro_digitos_pero_invalido(app_primer_uso):
    # RN-07: "0999" tiene 4 caracteres pero no es un año válido: error y botón bloqueado.
    p = abrir_primer_uso(app_primer_uso)
    v = p.vista
    for valor in ("0000", "0999"):
        v.anio.value = valor
        v.anio.on_change(evento(v.anio))
        assert v.anio.error == "El año tiene que tener 4 dígitos."
        assert v.boton_confirmar.disabled is True
        assert v.boton_confirmar.tooltip == "Corregí el mes destino."
    assert (p.lista.anio, p.lista.mes) == (
        2026,
        10,
    )  # la lista conserva el último mes válido


def test_ir_al_primer_error_sin_errores_no_hace_nada(app_rev):
    p = abrir(app_rev)
    p.app.page.tareas.clear()
    p.vista.ir_al_primer_error()
    assert p.app.page.tareas == []


def test_dialogo_en_base_sin_varios_marca_la_categoria_y_no_deja_aceptar(
    app_sin_varios,
):
    # §4.9: sin categoría por defecto, la fila de gasto ya viene con "Elegí una categoría."
    # y el diálogo lo muestra bajo el selector; tampoco se acepta sin elegir una.
    p = abrir(app_sin_varios)
    d, dlg = abrir_fila(p, fv(p, "Gym"))
    assert dlg.categoria.dropdown.error_text == "Elegí una categoría."
    aceptar(dlg)
    assert dialogo_arriba(p.app) is d
    dlg.categoria.dropdown.value = clave_cat(
        p.vista.categoria_defecto.dropdown.options[0].key.split(":")[1]
    )
    aceptar(dlg)
    assert dialogo_arriba(p.app) is None
    assert fv(p, "Gym").categoria.value.startswith("• ")


def test_un_error_inesperado_en_un_cambio_se_muestra_y_la_pantalla_sigue(
    app_rev, monkeypatch
):
    # Si la lista falla por algo que no es un dato mal cargado, se muestra el diálogo de error
    # de la app y la pantalla se vuelve a dibujar.
    p = abrir(app_rev)

    def falla(*a, **kw):
        raise RuntimeError("falla inventada")

    monkeypatch.setattr(p.lista, "cambiar_tilde", falla)
    tildar(fv(p, "Gym"), False)
    d = dialogo_arriba(p.app)
    assert d is not None and any("falla inventada" in t for t in textos(d))
    assert (
        fv(p, "Gym").tilde.value is True
    )  # la pantalla sigue mostrando lo que dice la lista


def test_confirmar_sin_lista_no_hace_nada(app_rev):
    p = abrir(app_rev)
    clic(p.vista.control, "Cambiar archivo u hoja")
    n = len(p.app.page.avisos())
    p.confirmar()
    assert len(p.app.page.avisos()) == n
