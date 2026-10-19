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
from app.interfaz.dialogos import dialogos_mes, dialogos_valores
from app.interfaz.pantalla_ajustes import PantallaAjustes
from app.interfaz.pantalla_cuotas import PantallaCuotas
from app.interfaz.pantalla_gastos import PantallaGastos
from app.interfaz.pantalla_graficos import PantallaGraficos
from app.interfaz.pantalla_importar import PantallaImportar
from app.interfaz.pantalla_me_deben import PantallaMeDeben
from app.interfaz.pantalla_prevision import PantallaPrevision
from app.interfaz.pantalla_primer_uso import PantallaPrimerUso
from app.interfaz.pantalla_resumen import PantallaResumen
from app.logica import base_datos, configuracion, meses
from app.logica.formato import formatear_cotizacion, nombre_mes

# Destinos del menú lateral (§1.1 del diseño). El número de cada uno (1, 2, …)
# es también su atajo Ctrl + número. Resumen es la pantalla de inicio (paso 3).
_DESTINOS = [
    ("Resumen", ft.Icons.SPACE_DASHBOARD_OUTLINED, ft.Icons.SPACE_DASHBOARD),
    ("Gastos", ft.Icons.RECEIPT_LONG_OUTLINED, ft.Icons.RECEIPT_LONG),
    ("Cuotas", ft.Icons.CREDIT_CARD_OUTLINED, ft.Icons.CREDIT_CARD),
    ("Me deben", ft.Icons.PEOPLE_OUTLINE, ft.Icons.PEOPLE),
    ("Previsión", ft.Icons.TRENDING_UP, ft.Icons.TRENDING_UP),
    ("Gráficos", ft.Icons.BAR_CHART_OUTLINED, ft.Icons.BAR_CHART),
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
        # La pantalla de importar Excel, mientras está abierta (si no, None).
        self._importacion: PantallaImportar | None = None
        # El selector de archivos del sistema. Flet deja de atender un servicio
        # que no se guarda en ningún lado, por eso queda acá (se crea al usarlo).
        self._selector_de_archivos: ft.FilePicker | None = None

        page.window.width = 1280
        page.window.height = 800
        page.window.min_width = 1100
        page.window.min_height = 700
        page.padding = 0
        # El tema elegido en Ajustes → Apariencia (por defecto, como el sistema).
        estilos.aplicar_tema(page, configuracion.obtener_tema(con))
        page.on_keyboard_event = self._al_presionar_tecla

    # ------------------------------------------------------------------
    # Arranque y estructura
    # ------------------------------------------------------------------

    def iniciar(self) -> None:
        # Al abrir se ve el mes del calendario si existe; si no, el último (§1.2).
        inicial = meses.mes_inicial(self.con)
        if inicial is not None:
            self.mostrar_principal(inicial["id"])
        else:
            self.mostrar_primer_uso()

    def mostrar_primer_uso(self) -> None:
        """Pantalla completa sin menú, para crear el primer mes (§3.1)."""
        self._pantallas = []  # Sin menú: los atajos no hacen nada en esta pantalla.
        self._importacion = None
        self.page.title = "Gastos – Bienvenido"
        self.page.controls.clear()
        self.page.add(PantallaPrimerUso(self).control)

    def mostrar_importacion(self, origen: str) -> None:
        """Pantalla completa de importar Excel, sin menú ni barra (§3.11).

        origen: "primer_uso" o "ajustes", para volver ahí al cancelar.
        """
        # Sin pantallas del menú: mientras se importa, los atajos no hacen nada
        # (no se puede cambiar de mes ni de pantalla con una revisión a medias).
        self._pantallas = []
        self._importacion = PantallaImportar(self, origen)
        self.page.title = "Gastos – Importar Excel"
        self.page.controls.clear()
        self.page.add(self._importacion.control)
        self.page.update()

    def salir_de_importacion(self, origen: str) -> None:
        """Cancelar la importación: vuelve al primer uso o a la pestaña de Ajustes."""
        mes = meses.obtener_mes(self.con, self.mes_id) if self.mes_id else None
        if origen != "ajustes" or mes is None:
            self.iniciar()
            return
        self.mostrar_principal(self.mes_id)
        # mostrar_principal arma Ajustes de nuevo y arrancaría en la primera
        # pestaña: se vuelve a "Importar Excel" (§3.10), como en BUG-23.
        ajustes = self.pantalla("Ajustes")
        ajustes.pestanas.selected_index = ajustes.indice_de(ajustes.importar)
        ajustes.refrescar()
        self.page.update()

    def mostrar_importado(self, mes_id: int, pantalla: str) -> None:
        """Después de importar: la ventana principal con el mes destino, en la
        pantalla pedida ("Gastos" o "Resumen"). Sirve igual desde el primer uso
        (arma el menú y la barra) que desde Ajustes (§3.13)."""
        self._indice = [texto for texto, _, _ in _DESTINOS].index(pantalla)
        self.mostrar_principal(mes_id)

    def selector_de_archivos(self) -> ft.FilePicker:
        """El mismo FilePicker para toda la app (se registra en la página al crearse)."""
        if self._selector_de_archivos is None:
            self._selector_de_archivos = ft.FilePicker()
        return self._selector_de_archivos

    def mostrar_principal(self, mes_id: int) -> None:
        self.mes_id = mes_id
        self._importacion = None
        self._pantallas = [
            PantallaResumen(self),
            PantallaGastos(self),
            PantallaCuotas(self),
            PantallaMeDeben(self),
            PantallaPrevision(self),
            PantallaGraficos(self),
            PantallaAjustes(self),
        ]

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
        # Selector de mes con flechas, "Mes nuevo" y "Borrar este mes" (§1.2).
        self._selector_mes = ft.Dropdown(
            width=260,
            on_select=lambda e: self.seleccionar_mes(int(e.control.value)),
        )
        self._boton_anterior = ft.IconButton(
            ft.Icons.CHEVRON_LEFT,
            tooltip="Mes anterior (Alt+←)",
            on_click=lambda e: self.mes_vecino(-1),
        )
        self._boton_siguiente = ft.IconButton(
            ft.Icons.CHEVRON_RIGHT,
            tooltip="Mes siguiente (Alt+→)",
            on_click=lambda e: self.mes_vecino(+1),
        )
        self._boton_mes_nuevo = ft.OutlinedButton(
            "Mes nuevo", icon=ft.Icons.ADD, on_click=lambda e: self.crear_mes_nuevo()
        )
        self._item_borrar_mes = ft.PopupMenuItem(
            content="Borrar este mes",
            icon=ft.Icons.DELETE_OUTLINE,
            on_click=lambda e: self.borrar_mes(),
        )
        self._menu_mes = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Más opciones",
            items=[self._item_borrar_mes],
        )
        # Franja que avisa que se está viendo un mes que no es el actual (§1.2).
        self._texto_franja = ft.Text(color=estilos.color(self.page, "info"))
        self._franja = ft.Container(
            padding=ft.Padding.symmetric(horizontal=24, vertical=8),
            bgcolor=estilos.color(self.page, "info_suave"),
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.INFO_OUTLINE,
                        color=estilos.color(self.page, "info"),
                        size=18,
                    ),
                    self._texto_franja,
                ]
            ),
            visible=False,
        )
        # Cotización siempre visible y editable con un clic o Ctrl+K (§1.2).
        self._texto_cotizacion = ft.Text()
        self._icono_cotizacion = ft.Icon(ft.Icons.EDIT_OUTLINED, size=18)
        self._cotizacion = ft.Container(
            padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            border_radius=8,
            ink=True,
            tooltip=f"Editar la cotización ({self.atajo('K')})",
            on_click=lambda e: self.editar_cotizacion(),
            content=ft.Row(
                [self._texto_cotizacion, self._icono_cotizacion], tight=True
            ),
        )
        barra_superior = ft.Container(
            height=64,
            padding=ft.Padding.symmetric(horizontal=24),
            border=ft.Border.only(bottom=ft.BorderSide(1, estilos.BORDE)),
            content=ft.Row(
                [
                    ft.Row(
                        [
                            self._boton_anterior,
                            self._selector_mes,
                            self._boton_siguiente,
                            self._boton_mes_nuevo,
                            self._menu_mes,
                        ],
                        spacing=4,
                    ),
                    self._cotizacion,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            ),
        )
        self._contenido = ft.Container(expand=True, padding=24)

        self.page.controls.clear()
        self.page.add(
            ft.Row(
                [
                    self._rail,
                    ft.VerticalDivider(width=1),
                    ft.Column(
                        [barra_superior, self._franja, self._contenido],
                        expand=True,
                        spacing=0,
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
        if mes is None:
            # O17: el mes que se veía ya no existe (se borró). Se pasa al último
            # que quede, o a la pantalla de primer uso si no queda ninguno.
            self.despues_de_borrar_mes()
            return
        nombre = nombre_mes(mes["anio"], mes["mes"])
        self.page.title = f"Gastos – {nombre}"
        self._dibujar_selector_de_mes(mes)
        self._dibujar_cotizacion(mes["cotizacion_cent"])
        self._pantallas[self._indice].refrescar()
        self.page.update()

    def _dibujar_cotizacion(self, cotizacion: int | None) -> None:
        """Barra superior: la cotización, o un aviso naranja si falta (§1.2, RN-18)."""
        if cotizacion is None:
            self._texto_cotizacion.value = "Cotización sin cargar – Cargar"
            self._icono_cotizacion.icon = ft.Icons.WARNING_AMBER
            self._cotizacion.bgcolor = estilos.color(self.page, "pendiente_suave")
            self._texto_cotizacion.color = estilos.color(self.page, "pendiente")
            self._icono_cotizacion.color = estilos.color(self.page, "pendiente")
        else:
            self._texto_cotizacion.value = (
                f"Cotización {formatear_cotizacion(cotizacion)}"
            )
            self._icono_cotizacion.icon = ft.Icons.EDIT_OUTLINED
            self._cotizacion.bgcolor = None
            self._texto_cotizacion.color = None
            self._icono_cotizacion.color = None

    def _dibujar_selector_de_mes(self, mes) -> None:
        """Selector, flechas, "Mes nuevo", "Borrar este mes" y franja (§1.2)."""
        todos = meses.listar_meses(self.con)  # Del más nuevo al más viejo.
        actual = meses.mes_actual_calendario()
        opciones = []
        for m in todos:
            texto = nombre_mes(m["anio"], m["mes"])
            if (m["anio"], m["mes"]) == actual:
                texto += " · mes actual"
            opciones.append(ft.DropdownOption(key=str(m["id"]), text=texto))
        self._selector_mes.options = opciones
        self._selector_mes.value = str(mes["id"])

        ids = [m["id"] for m in todos]
        posicion = ids.index(mes["id"])
        # La lista va del más nuevo al más viejo: "anterior" es el que sigue en la lista.
        self._boton_anterior.disabled = posicion == len(ids) - 1
        self._boton_siguiente.disabled = posicion == 0
        siguiente = nombre_mes(*meses.siguiente(todos[0]["anio"], todos[0]["mes"]))
        self._boton_mes_nuevo.tooltip = (
            f"Crear {siguiente} ({self.atajo('N', shift=True)})"
        )

        es_ultimo = posicion == 0
        self._item_borrar_mes.disabled = not es_ultimo
        self._item_borrar_mes.content = (
            "Borrar este mes"
            if es_ultimo
            else f"Solo se puede borrar el último mes ({nombre_mes(todos[0]['anio'], todos[0]['mes'])})"
        )

        es_actual = (mes["anio"], mes["mes"]) == actual
        self._franja.visible = not es_actual
        self._texto_franja.value = (
            f"Estás viendo {nombre_mes(mes['anio'], mes['mes'])}. "
            "Los cambios que hagas se guardan en ese mes."
        )

    def seleccionar_mes(self, mes_id: int, pantalla: str | None = None) -> None:
        """Cambia el mes que se está viendo (y opcionalmente la pantalla)."""
        self.mes_id = mes_id
        if pantalla is not None:
            self.ir_a([texto for texto, _, _ in _DESTINOS].index(pantalla))
        else:
            self.refrescar()

    def verificar_mes(self) -> bool:
        """True si el mes que se está viendo todavía existe.

        Si se borró (la pantalla quedó vieja), pasa al último mes que quede (o al
        primer uso), avisa y devuelve False: quien llamó no debe seguir (BUG-16).
        """
        if self.mes_id is not None and meses.obtener_mes(self.con, self.mes_id):
            return True
        self.despues_de_borrar_mes()
        self.avisar("El mes que estabas viendo ya no existe.")
        return False

    def mes_vecino(self, paso: int) -> None:
        """paso = -1: mes anterior; +1: mes siguiente (flechas y Alt+←/→)."""
        if not self.verificar_mes():
            return
        mes = meses.obtener_mes(self.con, self.mes_id)
        mover = meses.anterior if paso < 0 else meses.siguiente
        vecino = meses.obtener_mes_por_fecha(self.con, *mover(mes["anio"], mes["mes"]))
        if vecino is not None:
            self.seleccionar_mes(vecino["id"])

    def borrar_mes(self) -> None:
        """Menú "Borrar este mes": pide confirmación (solo el último mes)."""
        if not self.verificar_mes():  # BUG-18
            return
        dialogos_mes.confirmar_borrar_mes(self, self.mes_id)

    def crear_mes_nuevo(self) -> None:
        """Botón "Mes nuevo" y Ctrl+Shift+N."""
        dialogos_mes.DialogoMesNuevo(self).abrir()

    def despues_de_borrar_mes(self) -> None:
        """Se selecciona el nuevo último mes; si no queda ninguno, primer uso (§3.9)."""
        ultimo = meses.obtener_ultimo_mes(self.con)
        if ultimo is None:
            self.mes_id = None
            self.mostrar_primer_uso()
        else:
            self.seleccionar_mes(ultimo["id"])

    def pantalla(self, nombre: str):
        """La pantalla del menú con ese nombre ("Resumen", "Gastos", "Ajustes")."""
        indice = [texto for texto, _, _ in _DESTINOS].index(nombre)
        return self._pantallas[indice]

    def editar_cotizacion(self) -> None:
        """Abre el diálogo de cotización del mes (barra superior o Ctrl+K)."""
        if not self.verificar_mes():
            return
        dialogos_valores.abrir_cotizacion(self, self.mes_id)

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

    def esta_abierto(self, dialogo: ft.AlertDialog) -> bool:
        """True si ese diálogo sigue abierto (no se cerró con Cancelar, Esc, etc.)."""
        return dialogo in self._dialogos

    def atajo(self, tecla: str, shift: bool = False) -> str:
        """Texto de un atajo para mostrar, con la convención de cada sistema.

        Windows: "Ctrl+N", "Ctrl+Shift+N". macOS: "⌘N", "⇧⌘N" (O34).
        """
        if self.page.platform == ft.PagePlatform.MACOS:
            return f"{'⇧' if shift else ''}⌘{tecla}"
        return f"Ctrl+{'Shift+' if shift else ''}{tecla}"

    def enfocar(self, control: ft.Control) -> None:
        # focus() en Flet 1.0 es asíncrona (async): run_task la ejecuta sin
        # que esta función tenga que ser async también.
        self.page.run_task(control.focus)

    def confirmar(
        self,
        pregunta: str,
        explicacion: str,
        texto_boton: str,
        al_confirmar: Callable,
        texto_volver: str = "Cancelar",
    ) -> None:
        """Confirmación antes de borrar algo (§2.5). Cancelar es lo más fácil.

        texto_volver cambia el botón de salir: "Volver" cuando la acción misma se
        llama "Cancelar plan", para no tener dos "Cancelar" opuestos (§3.4).
        """

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
                    texto_volver,
                    autofocus=True,
                    on_click=lambda e: self.cerrar_dialogo(dialogo),
                ),
                boton_peligroso(self.page, texto_boton, confirmar),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.abrir_dialogo(dialogo)

    def avisar(
        self, texto: str, al_deshacer: Callable | None = None, duracion: int = 4000
    ) -> None:
        """Mensaje breve abajo de la ventana (SnackBar), opcionalmente con "Deshacer".

        duracion en milisegundos (ej. 6000 para el aviso de cambio de mes, §3.12).
        """
        aviso = ft.SnackBar(ft.Text(texto), duration=duracion)
        if al_deshacer:
            aviso.action = "Deshacer"
            aviso.on_action = lambda e: al_deshacer()
        self.page.show_dialog(aviso)

    def error_inesperado(
        self,
        error: Exception,
        titulo: str = "No se pudo guardar",
        mensaje: str = "Los datos no se modificaron.",
        texto_boton: str = "Cerrar",
    ) -> None:
        """Algo falló que no es culpa de un dato mal cargado (§2.5).

        Muestra el detalle técnico para poder copiarlo y pasárselo al agente.
        La importación cambia los textos: "No se pudo importar" (§3.13, O91).
        """
        detalle = "".join(traceback.format_exception(error))
        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text(titulo),
            content=ft.Column(
                [
                    ft.Text(mensaje),
                    texto_ayuda(detalle, selectable=True),
                ],
                tight=True,
                width=560,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton(
                    texto_boton,
                    autofocus=True,
                    on_click=lambda e: self.cerrar_dialogo(dialogo),
                )
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
                arriba = self._dialogos[-1]
                # Un diálogo puede guardar en "data" algo para cerrar primero (ej.
                # la fila de "nueva categoría"): si lo cerró, el diálogo sigue (O86).
                if callable(arriba.data) and arriba.data():
                    return
                self.cerrar_dialogo(arriba)
            return
        if self._importacion is not None:
            # Importando: ningún atajo de la app. Esc cancela y Ctrl+Enter confirma
            # (§3.13, §3.14); eso lo decide la pantalla de importar.
            self._importacion.al_presionar_tecla(e)
            return
        if not self._pantallas:
            return  # Todavía en la pantalla de primer uso.

        # Alt+← / Alt+→ (Option en macOS): mes anterior / siguiente.
        if e.alt and e.key in ("Arrow Left", "ArrowLeft"):
            self.mes_vecino(-1)
            return
        if e.alt and e.key in ("Arrow Right", "ArrowRight"):
            self.mes_vecino(+1)
            return

        # En macOS se usa Cmd (meta) en lugar de Ctrl.
        es_mac = self.page.platform == ft.PagePlatform.MACOS
        modificador = e.meta if es_mac else e.ctrl
        if not modificador:
            return
        if e.key.isdigit():
            self.ir_a(int(e.key) - 1)
        elif e.key.upper() == "K":
            self.editar_cotizacion()
        elif e.key.upper() == "N" and e.shift:
            self.crear_mes_nuevo()
        elif e.key.upper() == "N":
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
