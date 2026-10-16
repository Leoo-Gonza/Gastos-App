"""Pruebas del paso 8e de la importación de Excel: confirmar, guardar, resultado, error y
cancelar (RF-57, RN-76; CA-57.1 a CA-57.4, CA-57.9 a CA-57.13; docs/diseno.md §3.13 y §3.14).

Sin ventanas: página falsa; los handlers de los controles se llaman a mano y las tareas
que la pantalla pide con page.run_task (el guardado) se ejecutan con ejecutar_tareas().
La base es la de los CA (hoy = 2026-10-14; solo existe 2026-10 con sueldo 1.200, cotización
1.600 y "Alquiler" 260.000; personas Sofía y Marsu; categoría Varios). Datos inventados.
"""

import asyncio

import flet as ft
import pytest

from app.logica import catalogos, confirmar_importacion, me_deben, pagos, resumen
from app.logica.confirmar_importacion import AVISO_SIN_DESHACER, MENSAJE_ERROR
from app.logica.revision_importacion import Nueva
from tests.ayudantes_excel import planilla_prueba, xlsx
from tests.ayudantes_interfaz import (
    boton,
    clic,
    de_tipo,
    dialogo_arriba,
    hay_boton,
    mes_seleccionado,
    nombre_visible,
    tecla,
    textos,
)

# Se reusan las fixtures y los ayudantes de las pruebas de la revisión (8c y 8d).
from tests.test_interfaz_revision import (  # noqa: F401  (las fixtures se usan por nombre)
    abrir,
    abrir_fila,
    abrir_primer_uso,
    aceptar,
    app_primer_uso,
    app_rev,
    base,
    elegir_tipo,
    evento,
    foto,
    fv,
    hoy_fijo,
    sin_nombre,
    tildar,
)

AVANT = "Avant Service cuota 3/ 3 $41.116,66"


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


def ejecutar_tareas(app):
    """Corre las tareas pendientes de page.run_task (el guardado) como lo haría Flet."""
    tareas = app.page.tareas
    while tareas:
        tarea = tareas.pop(0)
        # Las demás tareas son pedidos de foco (control.focus): sin ventana no se pueden correr.
        if getattr(tarea, "__name__", "") == "_guardar":
            asyncio.run(tarea())


def con_sueldo(p):
    """CA-57.1: la fila 19 (1.300) como sueldo, sin otros cambios."""
    elegir_tipo(sin_nombre(p, 19), "sueldo")


def solo_prestamo_y_sueldo(p):
    """CA-57.10: solo "Prestamo MP" y la fila 19 como sueldo."""
    con_sueldo(p)
    for f in p.vista.filas:
        if f.tilde.value and f.fila.nombre != "Prestamo MP" and f.fila.origen.fila_excel != 19:
            tildar(f, False)


def a_noviembre_con_juan(p):
    """CA-57.3: destino 2026-11, tipos cambiados y la persona nueva "Juan" en uso."""
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    elegir_tipo(fv(p, "Gym"), "unico")
    f = fv(p, "Servicios")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    [mas] = [b for b in de_tipo(dlg.persona.control, ft.IconButton) if b.tooltip == "Nueva persona"]
    mas.on_click(None)
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    aceptar(dlg)
    assert p.lista.personas_nuevas == [Nueva("Juan")]


def abrir_resumen(p):
    p.vista.boton_confirmar.on_click(None)
    return dialogo_arriba(p.app)


def importar_de_verdad(p):
    """Confirmar -> Importar -> se ejecuta el guardado. Devuelve el diálogo que queda arriba."""
    abrir_resumen(p)
    clic(dialogo_arriba(p.app), "Importar")
    ejecutar_tareas(p.app)
    return dialogo_arriba(p.app)


def cantidad(con, tabla):
    return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


def nombres(con, tabla):
    return [r[0] for r in con.execute(f"SELECT nombre FROM {tabla}")]


# ---------------------------------------------------------------------------
# CA-57.9: resumen previo
# ---------------------------------------------------------------------------


def test_ca_57_9_resumen_previo_en_pantalla_con_los_textos_y_sin_guardar(app_rev, base):
    # CA-57.9: "Confirmar importación" muestra "Revisá antes de importar" con las líneas
    # exactas, sin "Se crean también", y todavía no se escribe nada en la base.
    antes = foto(base.con)
    p = abrir(app_rev)
    con_sueldo(p)
    d = abrir_resumen(p)
    assert d.title.value == "Revisá antes de importar"
    assert d.modal is True
    assert d.content.width == 520
    assert textos(d.content)[:-1] == [
        "Se va a cargar en Octubre 2026 (ya existe).",
        "•  5 gastos: $ 376.720 (pagado $ 98.700)",
        f"•  1 plan de cuotas: {AVANT} (cuota 3/3, $ 41.117 por mes)",
        '•  3 ítems "me deben": Sofía 2, Marsu 1 ($ 39.685 en total)',
        "•  Sueldo: US$ 1.200,00 -> US$ 1.300,00",
        "No se importan 19 filas (ignoradas o destildadas).",
    ]
    assert AVISO_SIN_DESHACER in textos(d.content)
    assert not any("Se crean también" in t for t in textos(d.content))
    assert foto(base.con) == antes


def test_resumen_previo_botones_foco_y_progreso_oculto(app_rev):
    # §3.13: foco en la opción segura "Volver a la revisión"; "Importar" no tiene foco;
    # la ruedita de progreso está oculta hasta que se guarda.
    p = abrir(app_rev)
    d = abrir_resumen(p)
    assert boton(d, "Volver a la revisión").autofocus is True
    assert not boton(d, "Importar").autofocus
    assert isinstance(boton(d, "Importar"), ft.FilledButton)
    assert isinstance(boton(d, "Volver a la revisión"), ft.TextButton)
    assert p.progreso.visible is False
    assert p.guardando is False


def test_resumen_previo_aviso_de_sin_deshacer_es_info(app_rev):
    # El texto de "sin deshacer" va como aviso aparte (no como línea con viñeta).
    p = abrir(app_rev)
    d = abrir_resumen(p)
    assert not any(t.startswith("•  Esta importación") for t in textos(d.content))
    assert any(isinstance(c, ft.Icon) and c.icon == ft.Icons.INFO_OUTLINE for c in de_tipo(d.content, ft.Icon))


def test_volver_a_la_revision_cierra_el_resumen_sin_cambiar_nada(app_rev, base):
    # CA-57.9: "Volver a la revisión" vuelve a la lista sin cambios y sin nada guardado.
    antes = foto(base.con)
    p = abrir(app_rev)
    con_sueldo(p)
    lista, vista = p.lista, p.vista
    d = abrir_resumen(p)
    clic(d, "Volver a la revisión")
    assert not app_rev.hay_dialogo_abierto()
    assert p.lista is lista and p.vista is vista and app_rev._importacion is p
    assert lista.confirmada is False
    assert foto(base.con) == antes
    # Se puede volver a abrir y sale lo mismo.
    assert abrir_resumen(p).title.value == "Revisá antes de importar"


def test_esc_en_el_resumen_previo_vuelve_a_la_revision(app_rev):
    # §3.13: Esc = volver. La importación sigue y no se pregunta nada.
    p = abrir(app_rev)
    abrir_resumen(p)
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is p


def test_ctrl_enter_con_el_resumen_abierto_no_abre_otro(app_rev):
    p = abrir(app_rev)
    abrir_resumen(p)
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    p.confirmar()
    assert len(app_rev._dialogos) == 1


def test_confirmar_con_errores_no_abre_el_resumen(app_rev):
    # Con dos sueldos el botón queda deshabilitado: ni el clic ni Ctrl+Enter abren nada.
    p = abrir(app_rev)
    elegir_tipo(sin_nombre(p, 19), "sueldo")
    elegir_tipo(fv(p, "Gym"), "sueldo")
    assert p.vista.boton_confirmar.disabled is True
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    p.vista.confirmar()
    assert not app_rev.hay_dialogo_abierto()


def test_resumen_con_todo_en_ignorar_no_se_puede_abrir(app_rev):
    # CA-57.8: sin filas para importar, no se confirma.
    p = abrir(app_rev)
    for f in p.vista.filas:
        if f.tilde.value:
            tildar(f, False)
    assert p.vista.boton_confirmar.disabled is True
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    assert not app_rev.hay_dialogo_abierto()


# ---------------------------------------------------------------------------
# CA-57.1 y CA-57.2: importar de verdad, desde Ajustes
# ---------------------------------------------------------------------------


def test_ca_57_1_importar_guarda_lo_esperado(app_rev, base):
    # CA-57.1 de punta a punta por la pantalla: gastos, pagos, plan, me deben, sueldo.
    p = abrir(app_rev)
    con_sueldo(p)
    importar_de_verdad(p)
    con = base.con
    gs = {
        g["nombre"]: g["monto_cent"]
        for g in con.execute("SELECT * FROM gastos WHERE mes_id = ?", (base.mes_id,))
    }
    assert gs == {
        "Alquiler": 26000000,
        "Servicios": 8200000,
        "Internet": 3870000,
        "psicologo": 14000000,
        "Monotributo 66.020,12": 6602012,
        AVANT: 4111666,
        "Gym": 5000000,
    }
    totales = pagos.totales_del_mes(con, base.mes_id)
    assert totales == {"total": 67783678, "pagado": 9870000, "pendiente": 57913678}
    r = resumen.calcular_resumen(con, base.mes_id)
    assert (r.sueldo_usd, r.usd_a_cambiar, r.ahorro_usd) == (130000, 42365, 87635)
    assert me_deben.total_de(con, base.sofia) == 3290000
    assert me_deben.total_de(con, base.marsu) == 678500
    assert cantidad(con, "planes_cuotas") == 1
    assert cantidad(con, "pagos") == 2
    assert {x["fecha"] for x in con.execute("SELECT fecha FROM pagos")} == {"2026-10-14"}
    assert sorted(nombres(con, "personas")) == ["Marsu", "Sofía"]  # No se crea ninguna.
    assert p.lista.confirmada is True
    assert con.in_transaction is False


def test_ca_57_2_resultado_en_pantalla_y_ver_el_mes(app_rev, base):
    # CA-57.2: "Importación terminada", texto exacto, "Para completar:" con 2 líneas (sin
    # cotización), sin "Deshacer"; "Ver Octubre 2026" muestra 2026-10 en Gastos con el menú.
    p = abrir(app_rev)
    con_sueldo(p)
    d = importar_de_verdad(p)
    assert d is not None and not any("Revisá antes" in t for t in textos(d.title))
    assert "Importación terminada" in textos(d.title)
    assert d.modal is True
    iconos = [c for c in de_tipo(d.title, ft.Icon)]
    assert iconos and iconos[0].icon == ft.Icons.CHECK_CIRCLE
    contenido = textos(d.content)
    assert contenido == [
        'Se importaron: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo '
        "(US$ 1.300,00) en Octubre 2026.",
        "Para completar:",
        "•  Los gastos quedaron sin medio de pago. Podés ponérselo en Gastos.",
        "•  Si alguno es compartido, marcalo desde el gasto.",
    ]
    assert not any("Deshacer" in t or "deshacer" in t for t in textos(d))
    assert hay_boton(d, "Ver Octubre 2026")
    assert boton(d, "Ver Octubre 2026").autofocus is True
    assert len(d.actions) == 1
    # El resumen previo ya se cerró: solo queda el resultado.
    assert app_rev._dialogos == [d]
    clic(d, "Ver Octubre 2026")
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is None
    assert nombre_visible(app_rev) == "Gastos"
    assert mes_seleccionado(app_rev) == "Octubre 2026"
    assert app_rev.mes_id == base.mes_id
    assert app_rev.page.title == "Gastos – Octubre 2026"
    assert len(de_tipo(app_rev.page.controls[0], ft.NavigationRail)) == 1


def test_esc_en_el_resultado_lleva_al_mes_igual_que_ver(app_rev, base):
    # Lo importado ya está guardado: Esc hace lo mismo que "Ver ...".
    p = abrir(app_rev)
    con_sueldo(p)
    importar_de_verdad(p)
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is None
    assert nombre_visible(app_rev) == "Gastos"
    assert mes_seleccionado(app_rev) == "Octubre 2026"


def test_ca_57_10_solo_me_deben_y_sueldo_va_a_resumen(app_rev, base):
    # CA-57.10: el resultado dice 1 ítem y el sueldo; "Ver Octubre 2026" muestra Resumen.
    p = abrir(app_rev)
    solo_prestamo_y_sueldo(p)
    d = importar_de_verdad(p)
    assert textos(d.content)[0] == (
        'Se importaron: 1 ítem "me deben" y el sueldo (US$ 1.300,00) en Octubre 2026.'
    )
    # Sin gastos: no aparece la línea de "sin medio de pago".
    assert textos(d.content)[1:] == [
        "Para completar:",
        "•  Si alguno es compartido, marcalo desde el gasto.",
    ]
    clic(d, "Ver Octubre 2026")
    assert nombre_visible(app_rev) == "Resumen"
    assert mes_seleccionado(app_rev) == "Octubre 2026"
    assert cantidad(base.con, "items_me_deben") == 1


def test_resultado_solo_sueldo_no_muestra_para_completar(app_rev):
    # RN-76: solo el sueldo: ninguna línea de "Para completar:" (ni el título).
    p = abrir(app_rev)
    con_sueldo(p)
    for f in p.vista.filas:
        if f.tilde.value and f.fila.origen.fila_excel != 19:
            tildar(f, False)
    d = importar_de_verdad(p)
    assert textos(d.content) == ["Se importaron: el sueldo (US$ 1.300,00) en Octubre 2026."]
    clic(d, "Ver Octubre 2026")
    assert nombre_visible(app_rev) == "Resumen"


def test_importar_a_un_mes_nuevo_desde_ajustes_ver_muestra_ese_mes(app_rev, base):
    # Destino 2026-11 (se crea): el botón dice "Ver Noviembre 2026" y la app lo selecciona.
    p = abrir(app_rev)
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    d = abrir_resumen(p)
    assert textos(d.content)[0] == "Se va a crear Noviembre 2026 y cargar ahí los datos."
    clic(d, "Importar")
    ejecutar_tareas(app_rev)
    d = dialogo_arriba(app_rev)
    clic(d, "Ver Noviembre 2026")
    assert mes_seleccionado(app_rev) == "Noviembre 2026"
    assert nombre_visible(app_rev) == "Gastos"
    assert [(m["anio"], m["mes"]) for m in base.con.execute("SELECT * FROM meses ORDER BY 2,3")] == [
        (2026, 10),
        (2026, 11),
    ]


# ---------------------------------------------------------------------------
# CA-57.11: categorías y personas nuevas solo si se usan
# ---------------------------------------------------------------------------


def test_ca_57_11_persona_nueva_sin_uso_no_se_menciona_ni_se_crea(app_rev, base):
    # Juan se crea para "Servicios" como me deben y después Servicios vuelve a gasto fijo.
    p = abrir(app_rev)
    f = fv(p, "Servicios")
    d, dlg = abrir_fila(p, f)
    dlg.tipo.value = "me_deben"
    dlg.tipo.on_select(evento(dlg.tipo))
    [mas] = [b for b in de_tipo(dlg.persona.control, ft.IconButton) if b.tooltip == "Nueva persona"]
    mas.on_click(None)
    dlg.persona.nombre.value = "Juan"
    dlg.persona.agregar()
    aceptar(dlg)
    elegir_tipo(f, "fijo")
    d = abrir_resumen(p)
    assert not any("Juan" in t for t in textos(d.content))
    clic(d, "Importar")
    ejecutar_tareas(app_rev)
    assert "Juan" not in nombres(base.con, "personas")


def test_ca_57_11_categoria_por_defecto_nueva_se_menciona_y_se_crea(app_rev, base):
    # "Importado" como categoría por defecto: el resumen la menciona y los gastos y el plan
    # quedan en ella.
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    c.abrir()
    c.nombre.value = "Importado"
    c.agregar()
    d = abrir_resumen(p)
    assert 'Se crean también: la categoría "Importado".' in textos(d.content)
    clic(d, "Importar")
    ejecutar_tareas(app_rev)
    assert "Importado" in nombres(base.con, "categorias")
    filas = base.con.execute(
        "SELECT g.nombre, c.nombre FROM gastos g JOIN categorias c ON c.id = g.categoria_id "
        "WHERE g.nombre IN ('Gym', 'Servicios', ?)",
        (AVANT,),
    ).fetchall()
    assert len(filas) == 3 and {f[1] for f in filas} == {"Importado"}


def test_ca_57_11_categoria_nueva_solo_en_gym_y_gym_destildado_no_se_crea(app_rev, base):
    # "Importado" elegida solo en Gym; si Gym se destilda, no se crea.
    p = abrir(app_rev)
    f = fv(p, "Gym")
    d, dlg = abrir_fila(p, f)
    dlg.categoria.abrir()
    dlg.categoria.nombre.value = "Importado"
    dlg.categoria.agregar()
    aceptar(dlg)
    assert p.lista.categorias_nuevas == [Nueva("Importado")]
    tildar(f, False)
    d = abrir_resumen(p)
    assert not any("Importado" in t for t in textos(d.content))
    clic(d, "Importar")
    ejecutar_tareas(app_rev)
    assert "Importado" not in nombres(base.con, "categorias")


# ---------------------------------------------------------------------------
# CA-57.12: primer uso
# ---------------------------------------------------------------------------


def test_ca_57_12_primer_uso_resumen_resultado_y_ver(app_primer_uso):
    # Base sin meses: destino Octubre 2026 sin fila de sueldo.
    app = app_primer_uso
    con = app.con
    p = abrir_primer_uso(app)
    d = abrir_resumen(p)
    contenido = textos(d.content)
    assert contenido[0] == "Se va a crear Octubre 2026, sin cotización, y cargar ahí los datos."
    assert "•  Sin sueldo: el sueldo de Octubre 2026 queda en US$ 0,00." in contenido or (
        "Sin sueldo: el sueldo de Octubre 2026 queda en US$ 0,00." in contenido
    )
    clic(d, "Importar")
    ejecutar_tareas(app)
    d = dialogo_arriba(app)
    assert "Cargá la cotización de Octubre 2026 en el Resumen." in "\n".join(textos(d.content))
    assert cantidad(con, "meses") == 1
    clic(d, "Ver Octubre 2026")
    assert app._importacion is None
    assert nombre_visible(app) == "Gastos"
    assert mes_seleccionado(app) == "Octubre 2026"
    assert len(de_tipo(app.page.controls[0], ft.NavigationRail)) == 1
    assert app.page.title == "Gastos – Octubre 2026"
    mes = con.execute("SELECT * FROM meses").fetchone()
    assert mes["sueldo_usd_cent"] == 0


def test_primer_uso_solo_sueldo_va_a_resumen_con_el_menu(app_primer_uso):
    # Primer uso + solo sueldo: "Ver ..." arma la ventana principal en Resumen.
    app = app_primer_uso
    p = abrir_primer_uso(app)
    con_sueldo(p)
    for f in p.vista.filas:
        if f.tilde.value and f.fila.origen.fila_excel != 19:
            tildar(f, False)
    d = importar_de_verdad(p)
    clic(d, "Ver Octubre 2026")
    assert nombre_visible(app) == "Resumen"
    assert mes_seleccionado(app) == "Octubre 2026"


# ---------------------------------------------------------------------------
# Mientras guarda: doble clic, Esc, cancelar
# ---------------------------------------------------------------------------


def test_importar_deshabilita_los_botones_y_muestra_la_ruedita(app_rev):
    p = abrir(app_rev)
    d = abrir_resumen(p)
    clic(d, "Importar")
    assert p.guardando is True
    assert p.progreso.visible is True
    assert p.boton_importar.disabled is True and p.boton_volver.disabled is True
    ejecutar_tareas(app_rev)
    assert p.guardando is False


def test_doble_clic_en_importar_guarda_una_sola_vez(app_rev, base):
    # Dos clics seguidos antes de que arranque el guardado: se encola una sola tarea.
    p = abrir(app_rev)
    con_sueldo(p)
    d = abrir_resumen(p)
    clic(d, "Importar")
    clic(d, "Importar")
    p.importar()
    assert [t.__name__ for t in app_rev.page.tareas].count("_guardar") == 1
    ejecutar_tareas(app_rev)
    assert cantidad(base.con, "gastos") == 7  # Alquiler + 5 + la cuota
    assert cantidad(base.con, "items_me_deben") == 3
    assert cantidad(base.con, "planes_cuotas") == 1
    # Un solo diálogo de resultado y ningún error.
    assert len(app_rev._dialogos) == 1
    assert "Importación terminada" in textos(dialogo_arriba(app_rev).title)


def test_volver_a_la_revision_no_funciona_mientras_guarda(app_rev):
    p = abrir(app_rev)
    d = abrir_resumen(p)
    clic(d, "Importar")
    clic(d, "Volver a la revisión")  # El botón está deshabilitado en la pantalla real.
    assert dialogo_arriba(app_rev) is d
    ejecutar_tareas(app_rev)


def test_esc_mientras_guarda_no_cierra_el_resumen(app_rev):
    p = abrir(app_rev)
    d = abrir_resumen(p)
    clic(d, "Importar")
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert dialogo_arriba(app_rev) is d
    ejecutar_tareas(app_rev)
    assert "Importación terminada" in textos(dialogo_arriba(app_rev).title)


def test_cancelar_y_cambiar_archivo_no_hacen_nada_mientras_guarda(app_rev):
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "ignorar")
    d = abrir_resumen(p)
    clic(d, "Importar")
    p.cancelar()
    assert len(app_rev._dialogos) == 1 and dialogo_arriba(app_rev) is d
    assert app_rev._importacion is p
    ejecutar_tareas(app_rev)


# ---------------------------------------------------------------------------
# CA-57.4: error al guardar
# ---------------------------------------------------------------------------


def falla_en_el_segundo_item(monkeypatch):
    """Hace fallar el guardado a mitad: los gastos y el mes ya se escribieron."""
    original = me_deben.agregar_item
    llamadas = []

    def agregar(*args, **kwargs):
        llamadas.append(args)
        if len(llamadas) == 2:
            raise RuntimeError("falla inventada a mitad del guardado")
        return original(*args, **kwargs)

    monkeypatch.setattr(me_deben, "agregar_item", agregar)
    return llamadas


def test_ca_57_4_error_al_guardar_no_deja_nada_y_muestra_el_dialogo(app_rev, base, monkeypatch):
    # CA-57.4: destino 2026-11 + Juan; el guardado falla a mitad. La base queda idéntica
    # (no existe 2026-11, ni Juan, ni gastos nuevos) y se ve "No se pudo importar".
    p = abrir(app_rev)
    a_noviembre_con_juan(p)
    antes = foto(base.con)
    falla_en_el_segundo_item(monkeypatch)
    abrir_resumen(p)
    clic(dialogo_arriba(app_rev), "Importar")
    ejecutar_tareas(app_rev)
    assert foto(base.con) == antes
    assert base.con.in_transaction is False
    assert cantidad(base.con, "meses") == 1
    assert "Juan" not in nombres(base.con, "personas")
    d = dialogo_arriba(app_rev)
    assert app_rev._dialogos == [d]  # El resumen previo se cerró.
    assert d.title.value == "No se pudo importar"
    contenido = textos(d.content)
    assert contenido[0] == MENSAJE_ERROR == "No se pudo importar. No se guardó ningún dato."
    # El detalle técnico es el de la causa real, no el mensaje genérico.
    assert any("falla inventada a mitad del guardado" in t for t in contenido[1:])
    assert hay_boton(d, "Volver a la revisión")
    assert boton(d, "Volver a la revisión").autofocus is True
    assert p.guardando is False
    assert p.lista.confirmada is False


def test_ca_57_4_la_revision_se_conserva_y_se_puede_reintentar(app_rev, base, monkeypatch):
    # CA-57.4: con "Volver a la revisión" la lista está igual (tipos, tildes, Juan y destino)
    # y, arreglado el problema, se puede volver a confirmar y se guarda todo una vez.
    p = abrir(app_rev)
    a_noviembre_con_juan(p)
    lista, vista = p.lista, p.vista
    filas_antes = [(f.tipo, f.se_importa, f.nombre, f.monto_cent) for f in lista.filas]
    destino = (lista.anio, lista.mes)
    falla_en_el_segundo_item(monkeypatch)
    abrir_resumen(p)
    clic(dialogo_arriba(app_rev), "Importar")
    ejecutar_tareas(app_rev)
    clic(dialogo_arriba(app_rev), "Volver a la revisión")
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is p and p.lista is lista and p.vista is vista
    assert [(f.tipo, f.se_importa, f.nombre, f.monto_cent) for f in lista.filas] == filas_antes
    assert (lista.anio, lista.mes) == destino == (2026, 11)
    assert lista.personas_nuevas == [Nueva("Juan")]
    assert p.vista.mes.value == "2026-11"
    assert fv(p, "Gym").tipo.value == "unico"
    assert p.vista.boton_confirmar.disabled is False
    assert p.control.content is p.vista.control
    # Reintento: el problema "se arregla" y la segunda vez se guarda completo.
    monkeypatch.undo()
    d = importar_de_verdad(p)
    assert "Importación terminada" in textos(d.title)
    assert "Juan" in nombres(base.con, "personas")
    assert cantidad(base.con, "meses") == 2
    assert cantidad(base.con, "items_me_deben") == 4  # Servicios (Juan) + los 3 de siempre.
    assert cantidad(base.con, "planes_cuotas") == 1


def test_error_al_guardar_esc_cierra_el_error_y_queda_la_revision(app_rev, monkeypatch):
    p = abrir(app_rev)
    falla_en_el_segundo_item(monkeypatch)
    abrir_resumen(p)
    clic(dialogo_arriba(app_rev), "Importar")
    ejecutar_tareas(app_rev)
    assert dialogo_arriba(app_rev).title.value == "No se pudo importar"
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is p and p.vista is not None
    # Y Cancelar sin cambios del usuario sigue saliendo directo.
    p.cancelar()
    assert app_rev._importacion is None


def test_error_en_la_base_real_hace_rollback_de_todo_incluido_el_mes_nuevo(app_rev, base, monkeypatch):
    # Falla al crear el plan de cuotas (después de los gastos y el mes): rollback completo.
    from app.logica import cuotas

    def mal(*a, **kw):
        raise RuntimeError("plan roto inventado")

    p = abrir(app_rev)
    p.vista.mes.value = "2026-11"
    p.vista.mes.on_select(evento(p.vista.mes))
    antes = foto(base.con)
    monkeypatch.setattr(cuotas, "crear_plan", mal)
    abrir_resumen(p)
    clic(dialogo_arriba(app_rev), "Importar")
    ejecutar_tareas(app_rev)
    assert foto(base.con) == antes
    assert dialogo_arriba(app_rev).title.value == "No se pudo importar"


def test_lista_ya_confirmada_no_se_guarda_dos_veces(app_rev, base):
    # Tras importar no se puede volver a confirmar la misma lista: ni desde la pantalla (hay
    # un diálogo modal abierto) ni llamando a la lógica de nuevo.
    p = abrir(app_rev)
    con_sueldo(p)
    importar_de_verdad(p)
    despues = foto(base.con)
    app_rev._al_presionar_tecla(tecla("Enter", ctrl=True))
    p.confirmar()
    p.vista.confirmar()
    assert len(app_rev._dialogos) == 1  # Solo el resultado.
    from app.logica.errores import ErrorDeValidacion

    with pytest.raises(ErrorDeValidacion, match="ya se guardó"):
        confirmar_importacion.confirmar(p.lista)
    assert foto(base.con) == despues


def test_despues_de_importar_cancelar_no_vuelve_a_la_revision(app_rev):
    # El resultado está abierto (modal): Esc no cancela la importación sino que lleva al mes.
    p = abrir(app_rev)
    importar_de_verdad(p)
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert app_rev._importacion is None
    assert not app_rev.hay_dialogo_abierto()


def test_importar_dos_veces_seguidas_desde_ajustes(app_rev, base):
    # Después de "Ver ...", otra importación arma una lista nueva (con "ya existe" donde
    # corresponde, CA-56.4) y no reusa la anterior.
    p = abrir(app_rev)
    importar_de_verdad(p)
    clic(dialogo_arriba(app_rev), "Ver Octubre 2026")
    p2 = abrir(app_rev)
    assert p2 is not p and p2.lista is not p.lista and p2.lista.confirmada is False
    fv(p2, "Servicios")
    # Todo lo ya importado viene destildado ("ya existe"): el cambio de tipos del usuario se
    # puede volver a confirmar sin duplicar si se deja así. Se verifica que no hay error de
    # "ya se guardó" en la lista nueva.
    assert not p2.lista.confirmada


# ---------------------------------------------------------------------------
# CA-57.3: cancelar y cambiar de archivo
# ---------------------------------------------------------------------------


def test_ca_57_3_cancelar_con_cambios_pregunta_y_seguir_revisando_no_pierde_nada(app_rev, base):
    p = abrir(app_rev)
    a_noviembre_con_juan(p)
    clic(p.vista.control, "Cancelar")
    d = dialogo_arriba(app_rev)
    assert d.title.value == "¿Descartar la importación?"
    assert textos(d.content) == [
        "Se pierden los cambios que hiciste en la revisión. No se guarda nada."
        "\nTambién se descartan las categorías y personas nuevas: Juan."
    ]
    assert boton(d, "Seguir revisando").autofocus is True
    clic(d, "Seguir revisando")
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is p and p.vista.mes.value == "2026-11"
    assert p.lista.personas_nuevas == [Nueva("Juan")]


def test_ca_57_3_descartar_vuelve_a_la_pestana_importar_de_ajustes_sin_guardar(app_rev, base):
    antes = foto(base.con)
    p = abrir(app_rev)
    a_noviembre_con_juan(p)
    clic(p.vista.control, "Cancelar")
    clic(dialogo_arriba(app_rev), "Descartar")
    assert app_rev._importacion is None
    ajustes = app_rev.pantalla("Ajustes")
    assert ajustes.pestanas.selected_index == ajustes.indice_de(ajustes.importar)
    assert foto(base.con) == antes
    assert "Juan" not in nombres(base.con, "personas")
    assert base.con.execute("SELECT sueldo_usd_cent FROM meses").fetchone()[0] == 120000


def test_ca_57_3_esc_hace_lo_mismo_que_cancelar(app_rev, base):
    antes = foto(base.con)
    p = abrir(app_rev)
    a_noviembre_con_juan(p)
    app_rev._al_presionar_tecla(tecla("Escape"))
    d = dialogo_arriba(app_rev)
    assert d.title.value == "¿Descartar la importación?"
    # Esc dentro de esa confirmación la cierra y se sigue en la revisión.
    app_rev._al_presionar_tecla(tecla("Escape"))
    assert not app_rev.hay_dialogo_abierto() and app_rev._importacion is p
    # Esc otra vez vuelve a preguntar; se descarta.
    app_rev._al_presionar_tecla(tecla("Escape"))
    clic(dialogo_arriba(app_rev), "Descartar")
    assert app_rev._importacion is None
    assert foto(base.con) == antes


def test_cancelar_con_categoria_nueva_la_nombra(app_rev):
    p = abrir(app_rev)
    c = p.vista.categoria_defecto
    c.abrir()
    c.nombre.value = "Importado"
    c.agregar()
    p.cancelar()
    assert textos(dialogo_arriba(app_rev).content) == [
        "Se pierden los cambios que hiciste en la revisión. No se guarda nada."
        "\nTambién se descartan las categorías y personas nuevas: Importado."
    ]


def test_cancelar_sin_cambios_sale_directo_aunque_se_haya_abierto_y_cerrado_el_resumen(app_rev):
    # Abrir el resumen y volver no cuenta como un cambio del usuario.
    p = abrir(app_rev)
    clic(abrir_resumen(p), "Volver a la revisión")
    assert p.lista.hubo_cambios is False
    p.cancelar()
    assert not app_rev.hay_dialogo_abierto()
    assert app_rev._importacion is None


def test_cancelar_sin_cambios_en_primer_uso_vuelve_al_formulario(app_primer_uso):
    app = app_primer_uso
    p = abrir_primer_uso(app)
    p.cancelar()
    assert app._importacion is None
    assert app.page.title == "Gastos – Bienvenido"


def test_cancelar_con_cambios_en_primer_uso_descarta_y_vuelve_al_formulario(app_primer_uso):
    app = app_primer_uso
    antes = foto(app.con)
    p = abrir_primer_uso(app)
    elegir_tipo(fv(p, "Gym"), "ignorar")
    p.cancelar()
    assert app._importacion is p
    clic(dialogo_arriba(app), "Descartar")
    assert app._importacion is None
    assert app.page.title == "Gastos – Bienvenido"
    assert foto(app.con) == antes


def test_cambiar_archivo_con_cambios_pregunta_y_seguir_revisando_conserva(app_rev):
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "ignorar")
    lista = p.lista
    clic(p.vista.control, "Cambiar archivo u hoja")
    d = dialogo_arriba(app_rev)
    assert d.title.value == "¿Volver a elegir el archivo?"
    assert textos(d.content) == ["Se pierden los cambios que hiciste en la revisión."]
    assert boton(d, "Seguir revisando").autofocus is True
    clic(d, "Seguir revisando")
    assert p.lista is lista and p.vista is not None
    assert fv(p, "Gym").tipo.value == "ignorar"


def test_cambiar_archivo_con_cambios_y_volver_a_elegir_descarta_la_lista(app_rev, base):
    antes = foto(base.con)
    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "ignorar")
    clic(p.vista.control, "Cambiar archivo u hoja")
    clic(dialogo_arriba(app_rev), "Volver a elegir")
    assert p.lista is None and p.vista is None
    assert p.control.content is p._elegir
    assert hay_boton(p.tarjeta, "Elegir archivo...")
    assert app_rev._importacion is p
    assert foto(base.con) == antes


def test_cambiar_archivo_sin_cambios_no_pregunta(app_rev):
    p = abrir(app_rev)
    clic(p.vista.control, "Cambiar archivo u hoja")
    assert not app_rev.hay_dialogo_abierto()
    assert p.lista is None


def test_cambiar_archivo_luego_nueva_lista_no_arrastra_la_confirmacion(app_rev, base):
    # Elegir de nuevo el archivo arma una lista nueva que se puede importar normalmente.
    from tests.test_interfaz_revision import leer

    p = abrir(app_rev)
    elegir_tipo(fv(p, "Gym"), "ignorar")
    clic(p.vista.control, "Cambiar archivo u hoja")
    clic(dialogo_arriba(app_rev), "Volver a elegir")
    leer(p, "otra.xlsx", xlsx({"C1": "Luz", "D1": 10000}))
    d = importar_de_verdad(p)
    assert textos(d.content)[0] == "Se importaron: 1 gasto en Octubre 2026."
    assert "Luz" in nombres(base.con, "gastos")
    assert "Gym" not in nombres(base.con, "gastos")


# ---------------------------------------------------------------------------
# CA-57.13 y otros
# ---------------------------------------------------------------------------


def test_ca_57_13_la_app_no_intercepta_el_cierre_de_la_ventana():
    # Cerrar la ventana durante la revisión no pregunta: no hay ningún manejador de cierre.
    import pathlib

    raiz = pathlib.Path(__file__).resolve().parents[1] / "app"
    codigo = "\n".join(p.read_text(encoding="utf-8") for p in raiz.rglob("*.py"))
    assert "prevent_close" not in codigo
    assert "on_window_event" not in codigo
    assert "on_close" not in codigo


def test_el_error_inesperado_de_siempre_conserva_sus_textos(app_rev):
    # error_inesperado sin parámetros sigue diciendo lo de antes (otras pantallas lo usan).
    app_rev.error_inesperado(RuntimeError("x inventado"))
    d = dialogo_arriba(app_rev)
    assert d.title.value == "No se pudo guardar"
    assert "Los datos no se modificaron." in textos(d.content)
    assert hay_boton(d, "Cerrar")
    assert boton(d, "Cerrar").autofocus is True


def test_mostrar_importado_con_pantalla_desconocida_falla_claro(app_rev):
    # mostrar_importado solo acepta nombres del menú; otro nombre es un error de programación.
    with pytest.raises(ValueError):
        app_rev.mostrar_importado(app_rev.mes_id, "Inexistente")


def test_importar_un_excel_con_unico_gasto_y_pagado_parcial_de_punta_a_punta(app_rev, base):
    # CA-57.5: "Luz | 10000 | 4000" bajo un encabezado "Pagado": queda pendiente 6.000.
    from tests.test_interfaz_revision import leer

    p = abrir(app_rev)
    clic(p.vista.control, "Cambiar archivo u hoja")
    leer(p, "luz.xlsx", xlsx({"C1": "Gasto", "D1": "Monto", "E1": "Pagado",
                              "C2": "Luz", "D2": 10000, "E2": 4000}))
    d = importar_de_verdad(p)
    assert textos(d.content)[0] == "Se importaron: 1 gasto en Octubre 2026."
    luz = base.con.execute("SELECT id FROM gastos WHERE nombre = 'Luz'").fetchone()[0]
    assert pagos.pendiente(base.con, luz) == 600000


def test_primer_uso_error_al_guardar_no_crea_el_mes_y_se_puede_cancelar(app_primer_uso, monkeypatch):
    # Primer uso + fallo a mitad: no queda ni el mes ni nada; la revisión sigue y, sin
    # cambios del usuario, Cancelar vuelve a la bienvenida.
    app = app_primer_uso
    antes = foto(app.con)
    p = abrir_primer_uso(app)
    # Sin personas en la base no hay ítems "me deben": se hace fallar la creación del plan,
    # que ocurre después de crear el mes y los gastos.
    from app.logica import cuotas

    def mal(*a, **kw):
        raise RuntimeError("plan roto inventado")

    monkeypatch.setattr(cuotas, "crear_plan", mal)
    abrir_resumen(p)
    clic(dialogo_arriba(app), "Importar")
    ejecutar_tareas(app)
    assert foto(app.con) == antes
    assert cantidad(app.con, "meses") == 0
    assert dialogo_arriba(app).title.value == "No se pudo importar"
    clic(dialogo_arriba(app), "Volver a la revisión")
    assert app._importacion is p and p.vista is not None
    p.cancelar()
    assert app.page.title == "Gastos – Bienvenido"
    assert app.mes_id is None or not app.con.execute("SELECT 1 FROM meses").fetchone()
