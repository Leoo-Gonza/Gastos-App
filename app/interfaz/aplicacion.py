"""Ventana principal: arma la estructura, cambia de pantalla y maneja diálogos.

Es el único lugar que conoce a todas las pantallas. Cada pantalla recibe la
Aplicacion para usar la conexión, el mes seleccionado y los diálogos.
"""

import sqlite3
import traceback
from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import boton_peligroso, texto_ayuda
from app.interfaz.pantalla_ajustes import PantallaAjustes
from app.interfaz.pantalla_gastos import PantallaGastos
from app.interfaz.pantalla_primer_uso import PantallaPrimerUso
from app.logica import base_datos, meses
from app.logica.formato import nombre_mes

# Destinos del menú lateral en el paso 1 (§6 del diseño). El número de cada uno
# (1, 2, …) es también su atajo Ctrl + número.
_DESTINOS = [
    ("Gastos", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG),
    ("Ajustes", ft.Icons.SETTINGS_OUTLINED, ft.Icons.SETTINGS),
]


class Aplicacion:
    def __init__(self, page: ft.Page, con: sqlite3.Connection) -> None:
        self.page = page
        self.con = con
        self.mes_id: int | None = None
        # Diálogos abiertos, del más viejo al más nuevo. Sirve para que Esc
        # cierre el de arriba y para ignorar los atajos mientras hay uno abierto.
        self._dialogos: list[ft.AlertDialog] = []
        self._pantallas: list = []
        self._indice = 0

        page.window.width = 1280
        page.window.height = 800
        page.window.min_width = 1100
        page.window.min_height = 700
        page.padding = 0
        estilos.aplicar_tema(page)
        page.on_keyboard_event = self._al_presionar_tecla

    # ------------------------------------------------------------------
    # Arranque y estructura
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        if meses.hay_meses(self.con):
            self.mostrar_principal(meses.obtener_ultimo_mes(self.con)["id"])
        else:
            self.mostrar_primer_uso()

    def mostrar_primer_uso(self) -> None:
        """Pantalla completa sin menú, para crear el primer mes (§3.1)."""
        self.page.title = "Gastos – Bienvenido"
        self.page.controls.clear()
        self.page.add(PantallaPrimerUso(self).control)

    def mostrar_principal(self, mes_id: int) -> None:
        self.mes_id = mes_id
        self._pantallas = [PantallaGastos(self), PantallaAjustes(self)]

        self._rail = ft.NavigationRail(
            selected_index=self._indice,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=88,
            destinations=[
                ft.NavigationRailDestination(
                    icon=icono, selected_icon=icono_sel, label=texto
                )
                for texto, icono, icono_sel in _DESTINOS
            ],
            on_change=lambda e: self.ir_a(e.control.selected_index),
        )
        self._texto_mes = ft.Text(size=estilos.TAM_SECCION, weight=ft.FontWeight.W_600)
        barra_superior = ft.Container(
            height=64,
            padding=ft.Padding.symmetric(horizontal=24),
            alignment=ft.Alignment.CENTER_LEFT,
            border=ft.Border.only(bottom=ft.BorderSide(1, estilos.BORDE)),
            content=self._texto_mes,
        )
        self._contenido = ft.Container(expand=True, padding=24)

        self.page.controls.clear()
        self.page.add(
            ft.Row(
                [
                    self._rail,
                    ft.VerticalDivider(width=1),
                    ft.Column(
                        [barra_superior, self._contenido], expand=True, spacing=0
                    ),
                ],
                expand=True,
                spacing=0,
            )
        )
        self.ir_a(self._indice)

    def ir_a(self, indice: int) -> None:
        """Muestra la pantalla número "indice" del menú lateral."""
        if not 0 <= indice < len(self._pantallas):
            return
        self._indice = indice
        self._rail.selected_index = indice
        self._contenido.content = self._pantallas[indice].control
        self.refrescar()

    def refrescar(self) -> None:
        """Vuelve a pedir los datos a la lógica y redibuja la pantalla visible."""
        mes = meses.obtener_mes(self.con, self.mes_id)
        nombre = nombre_mes(mes["anio"], mes["mes"])
        self.page.title = f"Gastos – {nombre}"
        self._texto_mes.value = nombre
        self._pantallas[self._indice].refrescar()
        self.page.update()

    # ------------------------------------------------------------------
    # Diálogos y avisos
    # ------------------------------------------------------------------

    def abrir_dialogo(self, dialogo: ft.AlertDialog) -> None:
        self._dialogos.append(dialogo)
        # on_dismiss avisa cuando el diálogo se cerró por cualquier motivo.
        dialogo.on_dismiss = lambda e: self._olvidar_dialogo(dialogo)
        self.page.show_dialog(dialogo)

    def cerrar_dialogo(self, dialogo: ft.AlertDialog) -> None:
        dialogo.open = False
        self._olvidar_dialogo(dialogo)
        self.page.update()

    def _olvidar_dialogo(self, dialogo: ft.AlertDialog) -> None:
        if dialogo in self._dialogos:
            self._dialogos.remove(dialogo)

    def hay_dialogo_abierto(self) -> bool:
        return bool(self._dialogos)

    def atajo(self, tecla: str) -> str:
        """Texto de un atajo para mostrar: "Ctrl+N" en Windows, "⌘N" en macOS."""
        if self.page.platform == ft.PagePlatform.MACOS:
            return f"⌘{tecla}"
        return f"Ctrl+{tecla}"

    def enfocar(self, control: ft.Control) -> None:
        # focus() en Flet 1.0 es asíncrona (async): run_task la ejecuta sin
        # que esta función tenga que ser async también.
        self.page.run_task(control.focus)

    def confirmar(
        self, pregunta: str, explicacion: str, texto_boton: str, al_confirmar: Callable
    ) -> None:
        """Confirmación antes de borrar algo (§2.5). Cancelar es lo más fácil."""

        def confirmar(e):
            self.cerrar_dialogo(dialogo)
            al_confirmar()

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text(pregunta),
            content=ft.Text(explicacion, width=440),
            actions=[
                # autofocus: si se aprieta Enter sin pensar, se cancela (no se borra).
                ft.TextButton(
                    "Cancelar",
                    autofocus=True,
                    on_click=lambda e: self.cerrar_dialogo(dialogo),
                ),
                boton_peligroso(self.page, texto_boton, confirmar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.abrir_dialogo(dialogo)

    def avisar(self, texto: str, al_deshacer: Callable | None = None) -> None:
        """Mensaje breve abajo de la ventana (SnackBar), opcionalmente con "Deshacer"."""
        aviso = ft.SnackBar(ft.Text(texto), duration=4000)
        if al_deshacer:
            aviso.action = "Deshacer"
            aviso.on_action = lambda e: al_deshacer()
        self.page.show_dialog(aviso)

    def error_inesperado(self, error: Exception) -> None:
        """Algo falló que no es culpa de un dato mal cargado (§2.5).

        Muestra el detalle técnico para poder copiarlo y pasárselo al agente.
        """
        detalle = "".join(traceback.format_exception(error))
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text("No se pudo guardar"),
            content=ft.Column(
                [
                    ft.Text("Los datos no se modificaron."),
                    texto_ayuda(detalle, selectable=True),
                ],
                tight=True,
                width=560,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Cerrar", on_click=lambda e: self.cerrar_dialogo(dialogo))
            ],
        )
        self.abrir_dialogo(dialogo)

    # ------------------------------------------------------------------
    # Atajos de teclado (§1.3)
    # ------------------------------------------------------------------

    def _al_presionar_tecla(self, e: ft.KeyboardEvent) -> None:
        if self._dialogos:
            # Con un diálogo abierto, los atajos se ignoran. Esc cierra el de arriba.
            if e.key == "Escape":
                self.cerrar_dialogo(self._dialogos[-1])
            return
        if not self._pantallas:
            return  # Todavía en la pantalla de primer uso.

        # En macOS se usa Cmd (meta) en lugar de Ctrl.
        es_mac = self.page.platform == ft.PagePlatform.MACOS
        modificador = e.meta if es_mac else e.ctrl
        if not modificador:
            return
        if e.key.isdigit():
            self.ir_a(int(e.key) - 1)
        elif e.key.upper() == "N" and not e.shift:
            self._pantallas[self._indice].nuevo()
        elif e.key == ",":
            self.ir_a(len(_DESTINOS) - 1)  # Ajustes, como en macOS.


def main(page: ft.Page) -> None:
    """Punto de entrada que recibe Flet al abrir la ventana."""
    try:
        con = base_datos.conectar()
    except Exception as error:  # noqa: BLE001 (a propósito: se muestra en la ventana)
        # Ej.: falló la actualización de la base (RN-59). La base queda como
        # estaba y hay una copia en datos-privados/respaldos/.
        mostrar_error_al_abrir(page, error)
        return
    Aplicacion(page, con).iniciar()


def mostrar_error_al_abrir(page: ft.Page, error: Exception) -> None:
    """Pantalla de error cuando la base no se pudo abrir o actualizar."""
    page.title = "Gastos – No se pudo abrir"
    page.add(
        ft.Container(
            padding=32,
            content=ft.Column(
                [
                    ft.Text(
                        "No se pudo abrir la base de datos",
                        size=estilos.TAM_TITULO,
                        weight=ft.FontWeight.W_600,
                    ),
                    # ErrorDeBase ya trae el mensaje exacto (si hay respaldo y dónde).
                    # Otro error es inesperado: no se promete nada sobre un respaldo.
                    ft.Text(
                        str(error)
                        if isinstance(error, base_datos.ErrorDeBase)
                        else "Ocurrió un error inesperado al abrir la base."
                    ),
                    texto_ayuda(
                        "".join(traceback.format_exception(error)), selectable=True
                    ),
                ],
                spacing=12,
            ),
        )
    )
