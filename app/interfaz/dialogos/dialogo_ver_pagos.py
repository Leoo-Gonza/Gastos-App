"""Diálogo "Ver pagos" de un gasto (RF-15, docs/diseno.md §4.4).

Lista los pagos y permite borrar uno. La confirmación de borrado se hace en
la misma fila ("¿Borrar este pago? No / Sí, borrar") para no abrir un diálogo
encima de otro.
"""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import texto_ayuda
from app.logica import gastos, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, formatear_fecha


class DialogoVerPagos:
    """al_registrar_otro() abre "Registrar pago" para el mismo gasto."""

    def __init__(
        self, app, gasto_id: int, al_registrar_otro: Callable[[], None]
    ) -> None:
        self.app = app
        self.gasto_id = gasto_id
        self.al_registrar_otro = al_registrar_otro
        # Id del pago que está pidiendo confirmación (None = ninguno).
        self.confirmando: int | None = None

        self.lista = ft.Column(spacing=4)
        self.pie = ft.Text(weight=ft.FontWeight.W_600)
        self.boton_otro = ft.TextButton(
            "Registrar otro pago", icon=ft.Icons.ADD, on_click=self._registrar_otro
        )
        self.dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Text(),
            content=ft.Column(
                [self.lista, ft.Divider(), self.pie], tight=True, width=480
            ),
            actions=[
                self.boton_otro,
                ft.FilledButton(
                    "Cerrar", on_click=lambda e: app.cerrar_dialogo(self.dialogo)
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        self._redibujar()

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    def _redibujar(self) -> None:
        gasto = gastos.obtener_gasto(self.app.con, self.gasto_id)
        self.dialogo.title.value = f"Pagos de {gasto['nombre']}"
        lista = pagos.listar_pagos(self.app.con, self.gasto_id)
        if not lista:
            self.lista.controls = [texto_ayuda("Todavía no hay pagos registrados.")]
        else:
            self.lista.controls = [self._fila(p) for p in lista]
        pagado = gastos.total_pagado(self.app.con, self.gasto_id)
        pendiente = gasto["monto_cent"] - pagado
        self.pie.value = (
            f"Pagado {formatear_ars(pagado)} · Pendiente {formatear_ars(pendiente)}"
        )
        # Si ya no falta nada, no tiene sentido ofrecer otro pago.
        self.boton_otro.visible = pendiente > 0

    def _fila(self, pago) -> ft.Control:
        fecha_y_monto = [
            ft.Text(formatear_fecha(pago["fecha"]), width=110),
            ft.Text(
                formatear_ars(pago["monto_cent"]),
                expand=True,
                text_align=ft.TextAlign.RIGHT,
            ),
        ]
        if self.confirmando == pago["id"]:
            acciones = [
                ft.Text(
                    "¿Borrar este pago?", color=estilos.color(self.app.page, "negativo")
                ),
                # autofocus en "No": un Enter sin pensar no borra nada.
                ft.TextButton(
                    "No", autofocus=True, on_click=lambda e: self._confirmar(None)
                ),
                ft.TextButton(
                    "Sí, borrar",
                    style=ft.ButtonStyle(
                        color=estilos.color(self.app.page, "negativo")
                    ),
                    on_click=lambda e: self._borrar(pago["id"]),
                ),
            ]
        else:
            acciones = [
                ft.IconButton(
                    ft.Icons.DELETE_OUTLINE,
                    tooltip="Borrar este pago",
                    on_click=lambda e: self._confirmar(pago["id"]),
                )
            ]
        return ft.Row([*fecha_y_monto, *acciones])

    def _confirmar(self, pago_id: int | None) -> None:
        self.confirmando = pago_id
        self._redibujar()
        self.app.page.update()

    def _borrar(self, pago_id: int) -> None:
        self.confirmando = None
        try:
            pagos.borrar_pago(self.app.con, pago_id)
        except ErrorDeValidacion as error:
            self.app.avisar(str(error))
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self._redibujar()
        # La tabla de atrás también se actualiza, así al cerrar ya está al día.
        self.app.refrescar()

    def _registrar_otro(self, e=None) -> None:
        self.app.cerrar_dialogo(self.dialogo)
        self.al_registrar_otro()
