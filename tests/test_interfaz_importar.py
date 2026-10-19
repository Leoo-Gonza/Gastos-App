"""Pruebas de la importación de Excel, paso 8b: entradas y elegir archivo
(RF-49, RF-50, RF-58, RN-60, CA-49.1, CA-49.2, CA-50.1, CA-58.1, CA-58.2;
diseno.md §3.1, §3.10, §3.11, §1.3). Sin ventanas ni selector real: el selector
de archivos se reemplaza por uno falso y las tareas de run_task se ejecutan a mano.
"""

import ast
import asyncio
import dataclasses
import datetime
import io
import pathlib
import zipfile
from functools import partial
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz.pantalla_importar import PantallaImportar
from app.logica import meses
from tests.ayudantes_excel import (
    a_bytes,
    armar_libro,
    planilla_prueba,
    reemplazar_en_zip,
    xlsx,
)
from tests.ayudantes_interfaz import (
    boton,
    clic,
    de_tipo,
    hay_boton,
    ir,
    tecla,
    textos,
)

INVALIDO = "No se pudo leer el archivo. Solo se aceptan archivos .xlsx de Excel."


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def tareas_con_argumentos(pagina):
    """PaginaFalsa.run_task descarta los argumentos; acá se guardan para poder correrlos."""
    pagina.tareas_listas = []

    def run_task(funcion, *args):
        pagina.tareas_listas.append(partial(funcion, *args))

    pagina.run_task = run_task


def correr_ultima_tarea(pagina):
    """Ejecuta la última tarea guardada por run_task (lo que haría Flet)."""
    asyncio.run(pagina.tareas_listas[-1]())


def leer(pantalla, nombre, contenido, ruta=None):
    asyncio.run(pantalla.leer_archivo(nombre, contenido, ruta))


def abrir_desde_ajustes(app):
    ir(app, "Ajustes")
    ajustes = app.pantalla("Ajustes")
    ajustes.pestanas.selected_index = ajustes.indice_de(ajustes.importar)
    clic(ajustes.importar.control, "Importar Excel")
    return app._importacion


def abrir_desde_primer_uso(app_vacia, pagina):
    clic(pagina.controls[0], "Importar Excel")
    return app_vacia._importacion


def varias_hojas(n=2, vacias=()):
    hojas = {}
    for i in range(1, n + 1):
        hojas[f"Hoja{i}"] = {} if i in vacias else {"C3": f"Gasto{i}", "D3": 1000 * i}
    return a_bytes(armar_libro(hojas))


def libro_con_hoja_de_fecha():
    """Dos hojas: una con datos y otra con solo una fecha (sin texto y monto)."""
    return a_bytes(
        armar_libro(
            {
                "Octubre": {"C3": "Luz", "D3": 1000},
                "Fechas": {"A1": datetime.date(2026, 10, 1)},
            }
        )
    )


class SelectorFalso:
    """Imita a ft.FilePicker: guarda cómo lo llamaron y devuelve lo que se le indique."""

    def __init__(self, archivos):
        self.archivos = archivos
        self.llamadas = []

    async def pick_files(self, **kw):
        self.llamadas.append(kw)
        return self.archivos


def archivo(name, bytes_=None, path=None):
    return SimpleNamespace(name=name, bytes=bytes_, path=path)


def con_selector(app, archivos):
    selector = SelectorFalso(archivos)
    app.selector_de_archivos = lambda: selector
    return selector


def tarjeta(pantalla):
    return textos(pantalla.tarjeta)


def contar_mensajes(pantalla, texto):
    return sum(1 for t in tarjeta(pantalla) if t == texto)


def estado_base(con):
    """Foto de todas las tablas para verificar que no se guardó nada."""
    tablas = [
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {t: con.execute(f"SELECT * FROM {t}").fetchall() for t in tablas}


# ---------------------------------------------------------------------------
# Entradas (CA-49.1, CA-49.2)
# ---------------------------------------------------------------------------


def test_primer_uso_tiene_linea_de_planilla(app_vacia, pagina):
    # CA-49.1: debajo del formulario hay "¿Tenés una planilla?" y el botón de texto.
    contenido = pagina.controls[0]
    assert "¿Tenés una planilla?" in textos(contenido)
    assert isinstance(boton(contenido, "Importar Excel"), ft.TextButton)
    assert hay_boton(contenido, "Crear mes")  # el formulario sigue igual


def _en_profundidad(control):
    """Controles en el orden del árbol (el de Tab), no por niveles como `recorrer`."""
    salida = [control]
    for campo in dataclasses.fields(control):
        if campo.name.startswith("_") or campo.name == "parent":
            continue
        valor = getattr(control, campo.name, None)
        hijos = (
            [valor]
            if isinstance(valor, ft.BaseControl)
            else (
                [v for v in valor if isinstance(v, ft.BaseControl)]
                if isinstance(valor, list)
                else []
            )
        )
        for hijo in hijos:
            salida.extend(_en_profundidad(hijo))
    return salida


def test_primer_uso_orden_crear_mes_antes_que_importar(app_vacia, pagina):
    # §3.1: el orden de Tab es el del árbol: "Crear mes" va antes que "Importar Excel".
    raiz = pagina.controls[0]
    controles = _en_profundidad(raiz)
    assert controles.index(boton(raiz, "Crear mes")) < controles.index(
        boton(raiz, "Importar Excel")
    )


def test_primer_uso_abre_importacion_sin_menu(app_vacia, pagina):
    # CA-49.1: abre la importación a pantalla completa, sin rail ni barra superior.
    pantalla = abrir_desde_primer_uso(app_vacia, pagina)
    assert isinstance(pantalla, PantallaImportar)
    assert pantalla.origen == "primer_uso"
    assert pagina.title == "Gastos – Importar Excel"
    assert de_tipo(pagina.controls[0], ft.NavigationRail) == []
    assert len(pagina.controls) == 1
    assert "Importar desde Excel" in textos(pagina.controls[0])
    assert app_vacia._pantallas == []


def test_primer_uso_cancelar_vuelve_al_formulario_sin_guardar(app_vacia, pagina, con):
    # CA-49.1: Cancelar vuelve al formulario de primer uso y la base sigue sin meses.
    antes = estado_base(con)
    abrir_desde_primer_uso(app_vacia, pagina)
    clic(pagina.controls[0], "Cancelar")
    assert pagina.title == "Gastos – Bienvenido"
    assert "Crear mes" in textos(pagina.controls[0])
    assert app_vacia._importacion is None
    assert meses.mes_inicial(con) is None
    assert estado_base(con) == antes


def test_primer_uso_esc_vuelve_al_formulario(app_vacia, pagina):
    # §1.3: Esc = Cancelar.
    abrir_desde_primer_uso(app_vacia, pagina)
    app_vacia._al_presionar_tecla(tecla("Escape"))
    assert pagina.title == "Gastos – Bienvenido"
    assert app_vacia._importacion is None


def test_ajustes_tiene_pestana_importar_ultima(app):
    # CA-49.2 / §3.10: última pestaña (la séptima desde el paso 9b), con el texto y el botón.
    ir(app, "Ajustes")
    ajustes = app.pantalla("Ajustes")
    etiquetas = [t.label for t in ajustes.pestanas.content.controls[0].tabs]
    assert len(etiquetas) == 7
    assert etiquetas[-1] == "Importar Excel"
    assert ajustes.indice_de(ajustes.importar) == 6
    assert (
        "Traé gastos, cuotas, lo que te deben y el sueldo desde una planilla .xlsx."
        in textos(ajustes.importar.control)
    )
    assert hay_boton(ajustes.importar.control, "Importar Excel")


def test_ajustes_ctrl_n_no_hace_nada_en_importar(app):
    # §3.10: Ctrl+N no tiene acción en la pestaña Importar Excel.
    ir(app, "Ajustes")
    ajustes = app.pantalla("Ajustes")
    ajustes.pestanas.selected_index = ajustes.indice_de(ajustes.importar)
    app._al_presionar_tecla(tecla("N", ctrl=True))
    assert app._dialogos == []
    assert app._importacion is None


def test_ajustes_abre_importacion_sin_menu(app, pagina):
    # CA-49.2: pantalla completa, sin rail.
    pantalla = abrir_desde_ajustes(app)
    assert pantalla.origen == "ajustes"
    assert pagina.title == "Gastos – Importar Excel"
    assert de_tipo(pagina.controls[0], ft.NavigationRail) == []
    assert app._pantallas == []


def test_ajustes_cancelar_vuelve_a_pestana_importar(app, pagina, con):
    # CA-49.2 / §3.10: Cancelar vuelve a Ajustes, pestaña Importar Excel, sin cambios.
    antes = estado_base(con)
    abrir_desde_ajustes(app)
    clic(pagina.controls[0], "Cancelar")
    assert app._importacion is None
    assert len(de_tipo(pagina.controls[0], ft.NavigationRail)) == 1
    ajustes = app.pantalla("Ajustes")
    assert ajustes.pestanas.selected_index == ajustes.indice_de(ajustes.importar)
    assert estado_base(con) == antes
    assert "Importar" not in pagina.title


def test_ajustes_esc_vuelve_a_pestana_importar(app, pagina):
    # §1.3: Esc igual que Cancelar, mismo destino.
    abrir_desde_ajustes(app)
    app._al_presionar_tecla(tecla("Escape"))
    ajustes = app.pantalla("Ajustes")
    assert ajustes.pestanas.selected_index == ajustes.indice_de(ajustes.importar)
    assert app._importacion is None


def test_ajustes_cancelar_vuelve_al_mismo_mes(app, pagina):
    # El mes seleccionado no cambia con la ida y vuelta.
    mes = app.mes_id
    abrir_desde_ajustes(app)
    app._al_presionar_tecla(tecla("Escape"))
    assert app.mes_id == mes


def test_pantalla_inicial_textos(app_vacia, pagina):
    # §3.11: textos del paso 1, tarjeta de 520 y botón "Elegir archivo..." con foco.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    t = textos(pagina.controls[0])
    assert (
        "Elegí un archivo .xlsx. Antes de guardar nada vas a poder revisar todo." in t
    )
    assert (
        "El archivo solo se lee: no se modifica, no se copia y no se guarda en la app."
        in t
    )
    assert boton(p.tarjeta, "Elegir archivo...").autofocus
    assert hay_boton(p.tarjeta, "Cancelar")
    assert de_tipo(pagina.controls[0], ft.Card)[0].width == 520


# ---------------------------------------------------------------------------
# Atajos desactivados durante la importación (§1.3)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "evento",
    [
        tecla("1", ctrl=True),
        tecla("3", ctrl=True),
        tecla("7", ctrl=True),
        tecla("N", ctrl=True),
        tecla("N", ctrl=True, shift=True),
        tecla("K", ctrl=True),
        tecla(",", ctrl=True),
        tecla("Arrow Left", alt=True),
        tecla("Arrow Right", alt=True),
    ],
)
def test_atajos_no_hacen_nada_durante_importacion(app, pagina, evento):
    # §1.3: durante la importación los atajos globales no hacen nada.
    abrir_desde_ajustes(app)
    mes = app.mes_id
    contenido = pagina.controls[0]
    app._al_presionar_tecla(evento)
    assert app._importacion is not None
    assert app.mes_id == mes
    assert app._dialogos == []
    assert pagina.controls[0] is contenido
    assert pagina.title == "Gastos – Importar Excel"


def test_atajos_macos_tampoco(con, mes_id):
    # En macOS (Cmd) tampoco hacen nada.
    from app.interfaz.aplicacion import Aplicacion
    from tests.ayudantes_interfaz import PaginaFalsa

    p = PaginaFalsa(ft.PagePlatform.MACOS)
    a = Aplicacion(p, con)
    a.iniciar()
    ir(a, "Ajustes")
    clic(a.pantalla("Ajustes").importar.control, "Importar Excel")
    a._al_presionar_tecla(tecla("2", meta=True))
    a._al_presionar_tecla(tecla("K", meta=True))
    assert a._importacion is not None and a._dialogos == []


def test_atajos_no_hacen_nada_en_primer_uso_importando(app_vacia, pagina):
    abrir_desde_primer_uso(app_vacia, pagina)
    app_vacia._al_presionar_tecla(tecla("K", ctrl=True))
    app_vacia._al_presionar_tecla(tecla("1", ctrl=True))
    assert app_vacia._importacion is not None
    assert app_vacia._dialogos == []


def test_otra_tecla_no_cancela(app, pagina):
    # Solo Esc cancela; Enter u otras letras no.
    abrir_desde_ajustes(app)
    app._al_presionar_tecla(tecla("Enter"))
    app._al_presionar_tecla(tecla("A"))
    assert app._importacion is not None


def test_esc_ocupada_no_cancela(app, pagina):
    # Mientras lee, Esc y Cancelar no actúan.
    p = abrir_desde_ajustes(app)
    p.ocupada = True
    app._al_presionar_tecla(tecla("Escape"))
    assert app._importacion is p
    p.cancelar()
    assert app._importacion is p


def test_atajos_vuelven_a_funcionar_tras_cancelar(app, pagina):
    # Al salir, los atajos se reactivan (Ctrl+3 va a la tercera pantalla).
    abrir_desde_ajustes(app)
    app._al_presionar_tecla(tecla("Escape"))
    app._al_presionar_tecla(tecla("3", ctrl=True))
    assert app._indice == 2


# ---------------------------------------------------------------------------
# Selector de archivos
# ---------------------------------------------------------------------------


def test_elegir_archivo_lanza_tarea_y_llama_selector_con_parametros(app_vacia, pagina):
    # El botón no abre el selector directo: usa run_task. Y lo llama con los parámetros del diseño.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    selector = con_selector(app_vacia, [])
    clic(p.tarjeta, "Elegir archivo...")
    assert len(pagina.tareas_listas) == 1
    assert selector.llamadas == []  # todavía no corrió
    correr_ultima_tarea(pagina)
    [kw] = selector.llamadas
    assert kw["dialog_title"] == "Elegir una planilla de Excel"
    assert kw["file_type"] == ft.FilePickerFileType.CUSTOM
    assert kw["allowed_extensions"] == ["xlsx"]
    assert kw["with_data"] is True


def test_selector_cerrado_sin_elegir_deja_todo_igual(app_vacia, pagina):
    # Cerrar el selector sin elegir: la tarjeta queda como estaba y no hay aviso.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    antes = tarjeta(p)
    con_selector(app_vacia, [])
    clic(p.tarjeta, "Elegir archivo...")
    correr_ultima_tarea(pagina)
    assert tarjeta(p) == antes
    assert p.ocupada is False
    assert p.libro is None


def test_selector_none_tambien_es_cancelar(app_vacia, pagina):
    # pick_files podría devolver None: no debe romper.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    con_selector(app_vacia, None)
    clic(p.tarjeta, "Elegir archivo...")
    correr_ultima_tarea(pagina)
    assert p.ocupada is False
    assert app_vacia._dialogos == []


def test_selector_con_bytes_lee_el_archivo(app_vacia, pagina):
    # Camino completo: selector -> bytes -> una sola hoja -> lista de revisión (8c).
    p = abrir_desde_primer_uso(app_vacia, pagina)
    con_selector(app_vacia, [archivo("planilla-prueba.xlsx", planilla_prueba())])
    clic(p.tarjeta, "Elegir archivo...")
    correr_ultima_tarea(pagina)
    assert p.vista is not None
    assert p.lista.hoja.nombre == "Octubre"
    assert len(p.vista.bloques) == 4  # Gasto del Mes, Deudas, Deudas sofia, Marsu
    assert p.ocupada is False


def test_selector_sin_bytes_lee_del_disco(app_vacia, pagina, tmp_path):
    # Si bytes es None y hay ruta, se lee del disco.
    ruta = tmp_path / "mi-planilla.xlsx"
    ruta.write_bytes(planilla_prueba())
    p = abrir_desde_primer_uso(app_vacia, pagina)
    con_selector(app_vacia, [archivo("mi-planilla.xlsx", None, str(ruta))])
    clic(p.tarjeta, "Elegir archivo...")
    correr_ultima_tarea(pagina)
    assert p.vista is not None
    assert sum(len(b.filas) for b in p.vista.bloques) == 13


def test_ruta_inexistente_da_aviso_de_archivo_invalido(app_vacia, pagina, tmp_path):
    # El archivo se borró entre elegirlo y leerlo: aviso de error, no un crash.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "borrado.xlsx", None, str(tmp_path / "borrado.xlsx"))
    assert INVALIDO in tarjeta(p)
    assert app_vacia._dialogos == []


def test_sin_bytes_ni_ruta_da_aviso_de_archivo_invalido(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "algo.xlsx", None, None)
    assert INVALIDO in tarjeta(p)


def test_el_archivo_original_no_se_modifica(app_vacia, pagina, tmp_path):
    # RN-60 / CA-50.2: el archivo solo se lee y no se crean copias a su lado.
    ruta = tmp_path / "p.xlsx"
    ruta.write_bytes(planilla_prueba())
    antes = ruta.read_bytes()
    mtime = ruta.stat().st_mtime_ns
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "p.xlsx", None, str(ruta))
    assert ruta.read_bytes() == antes
    assert ruta.stat().st_mtime_ns == mtime
    assert sorted(x.name for x in tmp_path.iterdir()) == ["p.xlsx"]


def test_selector_unico_en_la_app(app_vacia):
    # Se crea al usarlo y es siempre el mismo (Flet pierde los servicios no guardados).
    assert app_vacia._selector_de_archivos is None
    a = app_vacia.selector_de_archivos()
    assert isinstance(a, ft.FilePicker)
    assert app_vacia.selector_de_archivos() is a


def test_excepcion_inesperada_en_la_tarea_muestra_error_y_libera(app_vacia, pagina):
    # Si el selector falla, se muestra el diálogo de error inesperado y se libera "ocupada".
    class Roto:
        async def pick_files(self, **kw):
            raise RuntimeError("falla inventada")

    p = abrir_desde_primer_uso(app_vacia, pagina)
    app_vacia.selector_de_archivos = lambda: Roto()
    clic(p.tarjeta, "Elegir archivo...")
    correr_ultima_tarea(pagina)
    assert p.ocupada is False
    assert len(app_vacia._dialogos) == 1


# ---------------------------------------------------------------------------
# Doble clic / ocupada
# ---------------------------------------------------------------------------


def test_clic_en_elegir_ocupada_no_lanza_tarea(app_vacia, pagina):
    # Con ocupada=True (selector abierto o leyendo) un segundo clic no hace nada.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    p.ocupada = True
    p.elegir_archivo()
    assert pagina.tareas_listas == []


# O82 (corregida): ocupada se marca al hacer clic, antes de run_task.
def test_dos_clics_antes_de_que_corra_la_tarea(app_vacia, pagina):
    # Doble clic real: ocupada recién se pone en True cuando la tarea ARRANCA, no al
    # hacer clic. Dos clics seguidos antes de que Flet corra la tarea encolan dos
    # tareas (dos selectores abiertos). Se espera que solo se encole una.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    clic(p.tarjeta, "Elegir archivo...")
    clic(p.tarjeta, "Elegir archivo...")
    assert len(pagina.tareas_listas) == 1


def test_ocupada_se_libera_tras_leer(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.txt", b"hola")
    assert p.ocupada is False


def test_leyendo_muestra_progreso_y_deshabilita(app_vacia, pagina):
    # §3.11: mientras lee, "Leyendo el archivo..." y los botones deshabilitados.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    p._mostrar_leyendo()
    assert "Leyendo el archivo..." in tarjeta(p)
    assert de_tipo(p.tarjeta, ft.ProgressRing)
    botones = de_tipo(p.tarjeta, ft.TextButton) + de_tipo(p.tarjeta, ft.FilledButton)
    assert botones and all(b.disabled for b in botones)


def test_se_ve_leyendo_durante_la_lectura(app_vacia, pagina, monkeypatch):
    # Durante la lectura la tarjeta muestra "Leyendo el archivo...".
    import app.interfaz.pantalla_importar as modulo

    p = abrir_desde_primer_uso(app_vacia, pagina)
    vistos = []
    original = modulo.abrir_libro

    def espiar(contenido):
        vistos.append(list(tarjeta(p)))
        return original(contenido)

    monkeypatch.setattr(modulo, "abrir_libro", espiar)
    leer(p, "p.xlsx", planilla_prueba())
    assert "Leyendo el archivo..." in vistos[0]


def test_esc_durante_la_lectura_no_cancela(app_vacia, pagina, monkeypatch):
    # Esc a mitad de la lectura no cancela (ocupada).
    import app.interfaz.pantalla_importar as modulo

    p = abrir_desde_primer_uso(app_vacia, pagina)
    original = modulo.abrir_libro

    def espiar(contenido):
        app_vacia._al_presionar_tecla(tecla("Escape"))
        return original(contenido)

    monkeypatch.setattr(modulo, "abrir_libro", espiar)
    leer(p, "p.xlsx", planilla_prueba())
    assert app_vacia._importacion is p


# ---------------------------------------------------------------------------
# CA-58.1: archivos no válidos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nombre",
    [
        "notas.txt",
        "datos.csv",
        "viejo.xls",
        "macro.xlsm",
        "hoja.ods",
        "sin_extension",
        "xlsx",
    ],
)
def test_extension_no_xlsx_da_aviso(app_vacia, pagina, nombre):
    # CA-58.1: .txt, .csv, .xls, etc. por nombre -> texto exacto y "Elegir otro archivo".
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(
        p, nombre, planilla_prueba()
    )  # aunque el contenido fuera válido, el nombre manda
    assert INVALIDO in tarjeta(p)
    assert hay_boton(p.tarjeta, "Elegir otro archivo")
    assert not hay_boton(p.tarjeta, "Revisar filas")
    assert not hay_boton(p.tarjeta, "Elegir archivo...")
    assert hay_boton(p.tarjeta, "Cancelar")


def test_extension_mayuscula_xlsx_se_acepta(app_vacia, pagina):
    # RN-60: la extensión se compara sin distinguir mayúsculas.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "PLANILLA.XLSX", planilla_prueba())
    assert INVALIDO not in tarjeta(p)


def test_txt_renombrado_a_xlsx(app_vacia, pagina):
    # CA-58.1: un texto renombrado pasa el filtro y se rechaza al abrir.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "notas.xlsx", "esto es texto, no un excel".encode())
    assert INVALIDO in tarjeta(p)
    assert hay_boton(p.tarjeta, "Elegir otro archivo")


def test_csv_renombrado_a_xlsx(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "datos.xlsx", b"Luz,1000\nGas,2000\n")
    assert INVALIDO in tarjeta(p)


def test_xlsx_cortado(app_vacia, pagina):
    # CA-58.1: un .xlsx cortado (dañado).
    p = abrir_desde_primer_uso(app_vacia, pagina)
    contenido = planilla_prueba()
    leer(p, "cortado.xlsx", contenido[: len(contenido) // 2])
    assert INVALIDO in tarjeta(p)


def test_xlsx_vacio_0_bytes(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "vacio.xlsx", b"")
    assert INVALIDO in tarjeta(p)


def test_xlsx_con_hoja_interna_danada(app_vacia, pagina):
    # Zip válido pero con la hoja rota por dentro: aviso, no diálogo de error técnico.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    roto = reemplazar_en_zip(
        planilla_prueba(), "xl/worksheets/sheet1.xml", b"<no es xml"
    )
    leer(p, "roto.xlsx", roto)
    assert INVALIDO in tarjeta(p)
    assert app_vacia._dialogos == []


def test_zip_sin_estructura_de_excel(app_vacia, pagina):
    sal = io.BytesIO()
    with zipfile.ZipFile(sal, "w") as z:
        z.writestr("hola.txt", "hola")
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "zip.xlsx", sal.getvalue())
    assert INVALIDO in tarjeta(p)


def test_aviso_de_error_se_reemplaza_no_se_acumula(app_vacia, pagina):
    # §3.11: el mensaje de error se reemplaza cada vez que se elige otro archivo.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "a.txt", b"x")
    leer(p, "b.csv", b"x")
    leer(p, "c.xlsx", b"no")
    assert contar_mensajes(p, INVALIDO) == 1


def test_error_y_luego_archivo_bueno_borra_el_aviso(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "a.txt", b"x")
    leer(p, "ok.xlsx", planilla_prueba())
    assert INVALIDO not in tarjeta(p)
    assert p.vista is not None
    assert sum(len(b.filas) for b in p.vista.bloques) == 13


def test_aviso_invalido_estilo_negativo(app_vacia, pagina):
    # §3.11: aviso negativo con ícono ERROR_OUTLINE.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "a.txt", b"x")
    assert ft.Icons.ERROR_OUTLINE in [i.icon for i in de_tipo(p.tarjeta, ft.Icon)]


def test_error_no_cambia_la_base(app_vacia, pagina, con):
    antes = estado_base(con)
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "a.txt", b"x")
    leer(p, "b.xlsx", b"x")
    assert estado_base(con) == antes


def test_elegir_otro_archivo_tras_error_vuelve_a_lanzar_selector(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "a.txt", b"x")
    con_selector(app_vacia, [])
    clic(p.tarjeta, "Elegir otro archivo")
    assert len(pagina.tareas_listas) == 1


def test_cancelar_tras_error_vuelve_al_origen(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "a.txt", b"x")
    clic(p.tarjeta, "Cancelar")
    assert pagina.title == "Gastos – Bienvenido"


# ---------------------------------------------------------------------------
# CA-58.2: hoja vacía
# ---------------------------------------------------------------------------


def test_archivo_de_una_hoja_vacia(app_vacia, pagina):
    # CA-58.2: una sola hoja vacía -> "No se encontraron datos en la hoja Sheet."
    libro = armar_libro({})
    libro.create_sheet("Sheet")
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "vacio.xlsx", a_bytes(libro))
    assert "No se encontraron datos en la hoja Sheet." in tarjeta(p)
    assert hay_boton(p.tarjeta, "Elegir otro archivo")
    assert hay_boton(p.tarjeta, "Cancelar")
    assert not hay_boton(p.tarjeta, "Revisar filas")
    assert ft.Icons.WARNING_AMBER in [i.icon for i in de_tipo(p.tarjeta, ft.Icon)]


def test_hoja_vacia_con_nombre_propio(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "v.xlsx", a_bytes(armar_libro({"Hoja1": {}})))
    assert "No se encontraron datos en la hoja Hoja1." in tarjeta(p)


def test_varias_hojas_todas_vacias_avisa_de_la_primera(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "v.xlsx", a_bytes(armar_libro({"Enero": {}, "Febrero": {}})))
    assert "No se encontraron datos en la hoja Enero." in tarjeta(p)


def test_una_sola_hoja_con_solo_una_fecha(app_vacia, pagina):
    # Hay una celda pero ninguna fila con texto y monto: hoja sin datos (una sola hoja).
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "f.xlsx", xlsx({"A1": datetime.date(2026, 10, 1)}, nombre_hoja="Fechas"))
    assert "No se encontraron datos en la hoja Fechas." in tarjeta(p)
    assert hay_boton(p.tarjeta, "Elegir otro archivo")


def test_sin_datos_se_reemplaza_con_otro_archivo(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "v.xlsx", a_bytes(armar_libro({"Hoja1": {}})))
    leer(p, "a.txt", b"x")
    assert "No se encontraron datos en la hoja Hoja1." not in tarjeta(p)
    assert INVALIDO in tarjeta(p)


def test_nombre_de_hoja_con_caracteres_raros_en_el_aviso(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "v.xlsx", a_bytes(armar_libro({"Año 2026 (Ñandú)": {}})))
    assert "No se encontraron datos en la hoja Año 2026 (Ñandú)." in tarjeta(p)


def test_hoja_con_solo_textos_no_es_error_en_8b(app_vacia, pagina):
    # CA-58.2 (parte 2): una hoja con solo textos NO es "sin datos" en esta pantalla.
    # Desde 8c muestra la lista con el aviso "No se encontraron filas con un texto y un monto."
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "t.xlsx", xlsx({"C3": "Luz", "C4": "Gas"}))
    assert p.vista is not None
    t = textos(p.vista.control)
    assert not any("No se encontraron datos" in x for x in t)
    assert "No se encontraron filas con un texto y un monto." in t


# ---------------------------------------------------------------------------
# Elegir hoja (CA-50.1, RF-50)
# ---------------------------------------------------------------------------


def test_una_sola_hoja_no_pregunta(app_vacia, pagina):
    # CA-50.1: una sola hoja con datos -> no se pregunta.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "planilla-prueba.xlsx", planilla_prueba())
    assert not hay_boton(p.tarjeta, "Revisar filas")
    assert not de_tipo(p.tarjeta, ft.RadioGroup)
    # Va directo a la lista, que muestra el nombre del archivo y la hoja.
    assert p.vista is not None
    assert 'planilla-prueba.xlsx  ·  Hoja "Octubre"' in textos(p.vista.control)


def test_una_hoja_con_datos_y_otras_vacias_no_pregunta(app_vacia, pagina):
    # Las hojas vacías no se ofrecen: queda una sola, sin preguntar.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", varias_hojas(3, vacias=(1, 3)))
    assert not de_tipo(p.tarjeta, ft.RadioGroup)
    assert p.vista is not None
    assert p.lista.hoja.nombre == "Hoja2"


def test_varias_hojas_preguntan_cual(app_vacia, pagina):
    # RF-50: varias hojas con datos -> RadioGroup con la primera elegida.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "dos.xlsx", varias_hojas(2))
    t = tarjeta(p)
    assert "Archivo: dos.xlsx" in t
    assert "El archivo tiene 2 hojas. ¿Cuál querés importar?" in t
    assert "Se importa una hoja por vez. Si querés otra, repetís la importación." in t
    assert [r.value for r in de_tipo(p.tarjeta, ft.Radio)] == ["Hoja1", "Hoja2"]
    assert p.selector_hojas.value == "Hoja1"
    assert hay_boton(p.tarjeta, "Revisar filas")
    assert hay_boton(p.tarjeta, "Elegir otro")
    assert hay_boton(p.tarjeta, "Cancelar")
    assert boton(p.tarjeta, "Revisar filas").autofocus


def test_hojas_vacias_no_se_ofrecen(app_vacia, pagina):
    # RN-60: la hoja sin celdas no aparece; la cuenta dice 2, no 4.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", varias_hojas(4, vacias=(1, 3)))
    assert [r.value for r in de_tipo(p.tarjeta, ft.Radio)] == ["Hoja2", "Hoja4"]
    assert "El archivo tiene 2 hojas. ¿Cuál querés importar?" in tarjeta(p)
    assert p.selector_hojas.value == "Hoja2"  # la primera de las ofrecidas


def test_nombres_de_hoja_tal_cual(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    libro = armar_libro(
        {"Octubre": {"C3": "Luz", "D3": 100}, "sep 2026": {"C3": "Gas", "D3": 200}}
    )
    leer(p, "x.xlsx", a_bytes(libro))
    assert [r.label for r in de_tipo(p.tarjeta, ft.Radio)] == ["Octubre", "sep 2026"]


def test_exactamente_8_hojas_sin_scroll(app_vacia, pagina):
    # §3.11: el alto fijo solo aplica con más de 8 hojas.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", varias_hojas(8))
    columna = p.selector_hojas.content
    assert columna.height is None and columna.scroll is None


def test_9_hojas_alto_240_y_scroll(app_vacia, pagina):
    # §3.11: más de 8 hojas -> alto máximo 240 y scroll propio.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", varias_hojas(9))
    columna = p.selector_hojas.content
    assert columna.height == 240
    assert columna.scroll == ft.ScrollMode.AUTO
    assert len(de_tipo(p.tarjeta, ft.Radio)) == 9
    assert "El archivo tiene 9 hojas. ¿Cuál querés importar?" in tarjeta(p)


def test_revisar_filas_usa_la_hoja_elegida(app_vacia, pagina):
    # CA-50.1: muestra solo las filas de la hoja elegida.
    libro = armar_libro(
        {
            "Octubre": {"C3": "Luz", "D3": 1000, "C4": "Gas", "D4": 2000},
            "Septiembre": {"C3": "Agua", "D3": 300, "C4": "Sin monto"},
        }
    )
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", a_bytes(libro))
    p.selector_hojas.value = "Septiembre"
    clic(p.tarjeta, "Revisar filas")
    correr_ultima_tarea(pagina)
    assert p.vista is not None
    assert p.lista.hoja.nombre == "Septiembre"
    nombres = [f.nombre for f in p.lista.filas]
    assert "Agua" in nombres and "Luz" not in nombres
    assert p.ocupada is False


def test_revisar_filas_con_la_primera_por_defecto(app_vacia, pagina):
    libro = armar_libro(
        {
            "Octubre": {"C3": "Luz", "D3": 1000, "C4": "Gas", "D4": 2000},
            "Septiembre": {"C3": "Agua", "D3": 300},
        }
    )
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", a_bytes(libro))
    clic(p.tarjeta, "Revisar filas")
    correr_ultima_tarea(pagina)
    assert p.vista is not None
    assert p.lista.hoja.nombre == "Octubre"
    assert len([f for f in p.lista.filas if not f.incompleta]) == 2


def test_hoja_elegida_sin_datos_entre_varias_avisa_debajo(app_vacia, pagina):
    # §3.11: hoja con solo una fecha elegida entre varias -> aviso debajo de las hojas.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", libro_con_hoja_de_fecha())
    assert [r.value for r in de_tipo(p.tarjeta, ft.Radio)] == ["Octubre", "Fechas"]
    p.selector_hojas.value = "Fechas"
    clic(p.tarjeta, "Revisar filas")
    correr_ultima_tarea(pagina)
    assert "No se encontraron datos en la hoja Fechas." in tarjeta(p)
    # Se sigue viendo el selector, con la hoja elegida conservada, y los botones.
    assert de_tipo(p.tarjeta, ft.RadioGroup)
    assert p.selector_hojas.value == "Fechas"
    assert hay_boton(p.tarjeta, "Revisar filas")
    assert hay_boton(p.tarjeta, "Elegir otro")
    assert hay_boton(p.tarjeta, "Cancelar")
    # El aviso va debajo de las hojas.
    controles = p.tarjeta.controls
    i_grupo = controles.index(p.selector_hojas)
    assert any(
        "No se encontraron datos" in " ".join(textos(c))
        for c in controles[i_grupo + 1 :]
    )


def test_tras_hoja_sin_datos_se_puede_elegir_otra(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", libro_con_hoja_de_fecha())
    p.selector_hojas.value = "Fechas"
    clic(p.tarjeta, "Revisar filas")
    correr_ultima_tarea(pagina)
    p.selector_hojas.value = "Octubre"
    clic(p.tarjeta, "Revisar filas")
    correr_ultima_tarea(pagina)
    t = tarjeta(p)
    assert "No se encontraron datos en la hoja Fechas." not in t
    assert p.vista is not None
    assert p.lista.hoja.nombre == "Octubre"
    assert len([f for f in p.lista.filas if not f.incompleta]) == 1


def test_aviso_sin_datos_no_se_acumula_entre_varias(app_vacia, pagina):
    # Elegir tres veces seguidas la hoja sin datos: un solo aviso.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", libro_con_hoja_de_fecha())
    p.selector_hojas.value = "Fechas"
    for _ in range(3):
        clic(p.tarjeta, "Revisar filas")
        correr_ultima_tarea(pagina)
    assert contar_mensajes(p, "No se encontraron datos en la hoja Fechas.") == 1


def test_elegir_otro_vuelve_al_inicio(app_vacia, pagina):
    # §3.11: "Elegir otro" vuelve al estado inicial (sin aviso, "Elegir archivo...").
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", varias_hojas(2))
    clic(p.tarjeta, "Elegir otro")
    assert hay_boton(p.tarjeta, "Elegir archivo...")
    assert not de_tipo(p.tarjeta, ft.RadioGroup)
    assert p.libro is None and p.nombre_archivo is None
    assert INVALIDO not in tarjeta(p)


def test_elegir_otro_desde_el_resultado(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "x.xlsx", planilla_prueba())
    # Desde 8c, en la lista el botón es "Cambiar archivo u hoja" (§3.12) y vuelve al inicio.
    clic(p.vista.control, "Cambiar archivo u hoja")
    assert p.vista is None
    assert hay_boton(p.tarjeta, "Elegir archivo...")


def test_leer_otro_archivo_reemplaza_el_estado(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "dos.xlsx", varias_hojas(2))
    leer(p, "planilla-prueba.xlsx", planilla_prueba())
    assert p.nombre_archivo == "planilla-prueba.xlsx"
    assert not de_tipo(p.tarjeta, ft.RadioGroup)


def test_cancelar_en_elegir_hoja_vuelve_al_origen(app, pagina, con):
    antes = estado_base(con)
    p = abrir_desde_ajustes(app)
    leer(p, "dos.xlsx", varias_hojas(2))
    clic(p.tarjeta, "Cancelar")
    ajustes = app.pantalla("Ajustes")
    assert ajustes.pestanas.selected_index == ajustes.indice_de(ajustes.importar)
    assert estado_base(con) == antes


def test_esc_en_resultado_vuelve_al_origen(app, pagina, con):
    antes = estado_base(con)
    abrir_desde_ajustes(app)
    leer(app._importacion, "planilla-prueba.xlsx", planilla_prueba())
    app._al_presionar_tecla(tecla("Escape"))
    assert app._importacion is None
    assert estado_base(con) == antes


def test_revisar_filas_ocupada_no_lanza_tarea(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "dos.xlsx", varias_hojas(2))
    p.ocupada = True
    p.revisar_hoja(["Hoja1", "Hoja2"])
    assert pagina.tareas_listas == []


# O82 (corregida): ocupada se marca al hacer clic, antes de run_task.
def test_doble_clic_en_revisar_filas(app_vacia, pagina):
    # Igual que con "Elegir archivo...": dos clics antes de que corra la tarea.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "dos.xlsx", varias_hojas(2))
    clic(p.tarjeta, "Revisar filas")
    clic(p.tarjeta, "Revisar filas")
    assert len(pagina.tareas_listas) == 1


# ---------------------------------------------------------------------------
# planilla-prueba.xlsx (CA-50.1) y resultado provisorio
# ---------------------------------------------------------------------------


def test_planilla_prueba_13_completas_5_incompletas(app_vacia, pagina):
    # La lista coincide en cantidad con la tabla esperada de CA-51.1 (13 filas principales).
    # Las incompletas son 16 según CA-51.2 (el texto viejo decía 5).
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "planilla-prueba.xlsx", planilla_prueba())
    assert len([f for f in p.lista.filas if not f.incompleta]) == 13
    assert len(p.lista.incompletas()) == 16
    assert hay_boton(p.vista.control, "Cancelar")


def test_planilla_prueba_desde_ajustes(app, pagina):
    p = abrir_desde_ajustes(app)
    leer(p, "planilla-prueba.xlsx", planilla_prueba())
    assert p.vista is not None
    assert len([f for f in p.lista.filas if not f.incompleta]) == 13


def test_resultado_provisorio_no_guarda_nada(app, pagina, con):
    antes = estado_base(con)
    p = abrir_desde_ajustes(app)
    leer(p, "planilla-prueba.xlsx", planilla_prueba())
    assert estado_base(con) == antes


def test_nombre_de_archivo_mostrado(app_vacia, pagina):
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "Gastos año 2026 (copia).xlsx", planilla_prueba())
    assert 'Gastos año 2026 (copia).xlsx  ·  Hoja "Octubre"' in textos(p.vista.control)


# ---------------------------------------------------------------------------
# Estado de la app al entrar y salir
# ---------------------------------------------------------------------------


def test_mostrar_principal_y_primer_uso_limpian_importacion(app, pagina):
    abrir_desde_ajustes(app)
    assert app._importacion is not None
    app.mostrar_principal(app.mes_id)
    assert app._importacion is None
    abrir_desde_ajustes(app)
    app.mostrar_primer_uso()
    assert app._importacion is None


def test_abrir_cancelar_abrir_varias_veces(app, pagina):
    for _ in range(3):
        abrir_desde_ajustes(app)
        clic(pagina.controls[0], "Cancelar")
        assert app._importacion is None
    assert len(app._pantallas) > 0


def test_salir_de_importacion_ajustes_sin_mes_va_a_inicio(app_vacia):
    # Defensa: origen "ajustes" sin mes seleccionado no rompe y cae en el primer uso.
    app_vacia.mostrar_importacion("ajustes")
    app_vacia.salir_de_importacion("ajustes")
    assert app_vacia.page.title == "Gastos – Bienvenido"


def test_salir_de_importacion_con_mes_inexistente_cae_en_inicio(app):
    # Si el mes ya no existe, no rompe.
    abrir_desde_ajustes(app)
    app.mes_id = 99999
    app._importacion.cancelar()
    assert app._importacion is None


# ---------------------------------------------------------------------------
# Separación lógica / interfaz y funciones nuevas de la lógica
# ---------------------------------------------------------------------------


def test_la_logica_no_importa_la_interfaz():
    # CLAUDE.md: app/logica/ nunca importa nada de app/interfaz ni de flet.
    raiz = pathlib.Path(__file__).resolve().parents[1] / "app" / "logica"
    archivos = list(raiz.glob("*.py"))
    assert archivos
    for archivo_py in archivos:
        arbol = ast.parse(archivo_py.read_text(encoding="utf-8"))
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.Import):
                nombres = [a.name for a in nodo.names]
            elif isinstance(nodo, ast.ImportFrom):
                nombres = [nodo.module or ""]
            else:
                continue
            for n in nombres:
                assert not n.startswith("app.interfaz"), (
                    f"{archivo_py.name} importa {n}"
                )
                assert n.split(".")[0] != "flet", f"{archivo_py.name} importa {n}"


def test_mensaje_sin_datos_y_primera_hoja():
    from app.logica.importar_excel import abrir_libro, mensaje_sin_datos

    assert mensaje_sin_datos("Hoja1") == "No se encontraron datos en la hoja Hoja1."
    libro = abrir_libro(a_bytes(armar_libro({"A": {}, "B": {"C3": "x", "D3": 1}})))
    assert libro.primera_hoja() == "A"
    assert libro.hojas() == ["B"]


def test_aviso_en_pantalla_roles():
    # Componente nuevo: los cuatro roles se construyen y llevan ícono y texto.
    from app.interfaz.componentes import aviso_en_pantalla
    from tests.ayudantes_interfaz import PaginaFalsa

    pg = PaginaFalsa()
    for rol in ("negativo", "pendiente", "positivo", "info"):
        c = aviso_en_pantalla(pg, rol, ft.Icons.INFO_OUTLINE, "hola")
        assert "hola" in textos(c)
        assert de_tipo(c, ft.Icon)


def test_hoja_danada_al_leerla_da_aviso_de_archivo_invalido(app_vacia, pagina):
    # Un .xlsx que abre bien pero falla al leer la hoja: aviso, no diálogo técnico.
    p = abrir_desde_primer_uso(app_vacia, pagina)
    leer(p, "dos.xlsx", varias_hojas(2))

    def falla(nombre):
        raise ValueError("hoja rota inventada")

    p.libro.leer_hoja = falla
    clic(p.tarjeta, "Revisar filas")
    correr_ultima_tarea(pagina)
    assert INVALIDO in tarjeta(p)
    assert hay_boton(p.tarjeta, "Elegir otro archivo")
    assert app_vacia._dialogos == []
    assert p.ocupada is False
