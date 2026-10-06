"""Herramientas para probar la interfaz de Flet sin abrir ninguna ventana.

PaginaFalsa reemplaza a ft.Page con solo lo que usan las pantallas. Los controles
de Flet son dataclasses: se pueden crear, recorrer e inspeccionar sin ventana, y
sus handlers (on_click, on_blur, ...) se llaman directo.
"""

import dataclasses
from types import SimpleNamespace

import flet as ft


class PaginaFalsa:
    """Imita a ft.Page. Guarda lo que se mostró para poder revisarlo."""

    def __init__(self, plataforma=ft.PagePlatform.WINDOWS):
        self.window = SimpleNamespace(
            width=None, height=None, min_width=None, min_height=None
        )
        self.controls = []
        self.platform = plataforma
        self.platform_brightness = ft.Brightness.LIGHT
        self.theme_mode = None
        self.title = ""
        self.padding = None
        self.theme = None
        self.dark_theme = None
        self.on_keyboard_event = None
        self.mostrados = []  # Diálogos y SnackBars, en el orden en que se mostraron.
        self.tareas = []  # Funciones pasadas a run_task (ej. control.focus).
        self.actualizaciones = 0

    def add(self, *controles):
        self.controls.extend(controles)

    def update(self):
        self.actualizaciones += 1

    def show_dialog(self, dialogo):
        dialogo.open = True
        self.mostrados.append(dialogo)

    def run_task(self, funcion, *args):
        self.tareas.append(funcion)

    def avisos(self):
        """Textos de los SnackBar mostrados, en orden."""
        return [d.content.value for d in self.mostrados if isinstance(d, ft.SnackBar)]

    def ultimo_aviso(self):
        avisos = [d for d in self.mostrados if isinstance(d, ft.SnackBar)]
        return avisos[-1] if avisos else None


def recorrer(control):
    """Devuelve el control y todos los controles que tiene adentro."""
    vistos = set()
    pendientes = [control]
    resultado = []
    while pendientes:
        actual = pendientes.pop(0)
        if not isinstance(actual, ft.BaseControl) or id(actual) in vistos:
            continue
        vistos.add(id(actual))
        resultado.append(actual)
        for campo in dataclasses.fields(actual):
            if campo.name.startswith("_") or campo.name == "parent":
                continue
            valor = getattr(actual, campo.name, None)
            if isinstance(valor, ft.BaseControl):
                pendientes.append(valor)
            elif isinstance(valor, list):
                pendientes.extend(v for v in valor if isinstance(v, ft.BaseControl))
    return resultado


def textos(control):
    """Todos los textos visibles dentro de un control (Text y botones con texto)."""
    salida = []
    for c in recorrer(control):
        if isinstance(c, ft.Text) and c.value is not None:
            salida.append(c.value)
        contenido = getattr(c, "content", None)
        if isinstance(contenido, str):
            salida.append(contenido)
        etiqueta = getattr(c, "label", None)
        if isinstance(etiqueta, str):
            salida.append(etiqueta)
    return salida


def boton(control, texto):
    """El primer botón (o ítem de menú) cuyo texto es "texto"."""
    for c in recorrer(control):
        if getattr(c, "content", None) == texto and hasattr(c, "on_click"):
            return c
    raise AssertionError(f"No hay un botón {texto!r}")


def hay_boton(control, texto):
    try:
        boton(control, texto)
    except AssertionError:
        return False
    return True


def de_tipo(control, tipo):
    return [c for c in recorrer(control) if isinstance(c, tipo)]


def clic(control, texto):
    boton(control, texto).on_click(None)


def dialogo_arriba(app):
    """El diálogo abierto de más arriba (o None)."""
    return app._dialogos[-1] if app._dialogos else None


def titulo_dialogo(dialogo):
    return dialogo.title.value


def dialogo_gasto_abierto(app):
    """El objeto DialogoGasto del diálogo abierto (dueño del método del botón Guardar)."""
    return boton(dialogo_arriba(app), "Guardar").on_click.__self__


def tecla(key, ctrl=False, meta=False, shift=False, alt=False):
    """Evento de teclado falso, con los campos que lee la app."""
    return SimpleNamespace(key=key, ctrl=ctrl, meta=meta, shift=shift, alt=alt)


def _titulos_de(tabla):
    return [c.label.value for c in tabla.columns]


def tabla_gastos(pantalla_gastos):
    """La tabla de gastos (la que empieza con la columna "Pag."), no la de
    "Por medio de pago" que va debajo (paso 4b)."""
    tablas = [
        t
        for t in de_tipo(pantalla_gastos.cuerpo, ft.DataTable)
        if _titulos_de(t)[:1] == ["Pag."]
    ]
    assert len(tablas) == 1, "No hay (una sola) tabla de gastos"
    return tablas[0]


def tabla_por_medio(pantalla_gastos):
    """La tabla "Por medio de pago" de la pantalla Gastos como [(medio, total)]."""
    tablas = [
        t
        for t in de_tipo(pantalla_gastos.cuerpo, ft.DataTable)
        if _titulos_de(t) == ["Medio de pago", "Total"]
    ]
    assert len(tablas) == 1, "No hay tabla por medio de pago"
    return [tuple(c.content.value for c in fila.cells) for fila in tablas[0].rows]


def titulos(pantalla_gastos):
    """Títulos de las columnas, en orden."""
    return [c.label.value for c in tabla_gastos(pantalla_gastos).columns]


def columna(pantalla_gastos, titulo):
    """Índice de la columna con ese título (así las pruebas no dependen de la posición)."""
    return titulos(pantalla_gastos).index(titulo)


def filas_tabla(pantalla_gastos):
    """Filas de la tabla (incluye la de total) como diccionarios {título: texto}.

    El texto de una celda con varios controles (ej. "$ 32.000" y "US$ 20,00 × $ 1.600")
    se une con " | ". Las celdas sin texto (tilde, menú) quedan en None.
    """
    nombres = titulos(pantalla_gastos)
    return [
        dict(zip(nombres, (_texto_celda(c) for c in fila.cells), strict=True))
        for fila in tabla_gastos(pantalla_gastos).rows
    ]


def fila_de(pantalla_gastos, nombre):
    """La DataRow del gasto con ese nombre."""
    i = columna(pantalla_gastos, "Nombre")
    for fila in tabla_gastos(pantalla_gastos).rows:
        contenido = fila.cells[i].content
        if isinstance(contenido, ft.Text) and contenido.value == nombre:
            return fila
    raise AssertionError(f"No hay fila {nombre!r}")


def celda(pantalla_gastos, nombre, titulo):
    """La DataCell de la columna "titulo" en la fila del gasto "nombre"."""
    return fila_de(pantalla_gastos, nombre).cells[columna(pantalla_gastos, titulo)]


def item_menu(pantalla_gastos, nombre, texto):
    """El ítem "texto" del menú de acciones de la fila."""
    menu = celda(pantalla_gastos, nombre, "").content
    for item in menu.items:
        if item.content == texto:
            return item
    raise AssertionError(f"No hay ítem {texto!r}")


def _texto_celda(celda):
    contenido = celda.content
    if isinstance(contenido, ft.Text):
        return contenido.value
    partes = [
        t.value for t in recorrer(contenido) if isinstance(t, ft.Text) and t.value
    ]
    return " | ".join(partes) if partes else None


def ir(app, nombre):
    """Muestra la pantalla del menú con ese nombre ("Resumen", "Gastos", "Ajustes")."""
    app.ir_a(app._pantallas.index(app.pantalla(nombre)))
    return app.pantalla(nombre)


def nombre_visible(app):
    """Nombre de la pantalla que se está viendo, según el destino elegido en el menú."""
    return app._rail.destinations[app._indice].label


def mes_seleccionado(app):
    """Texto del mes elegido en el selector de la barra, sin " · mes actual"."""
    selector = app._selector_mes
    [opcion] = [o for o in selector.options if o.key == selector.value]
    return opcion.text.split(" · ")[0]
