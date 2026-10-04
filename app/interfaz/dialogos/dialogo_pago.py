"""Diálogo "Registrar pago" de un gasto (RF-14, docs/diseno.md §4.3)."""

from collections.abc import Callable
from datetime import date, datetime

import flet as ft

from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import gastos, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    formatear_ars,
    formatear_detalle_usd,
    formatear_fecha,
    formatear_monto_para_editar,
)


class DialogoPago:
    """al_guardar(monto_cent, quedo_pagado) se llama después de registrar el pago."""

    def __init__(
        self, app, gasto_id: int, al_guardar: Callable[[int, bool], None]
    ) -> None:
        self.app = app
        self.gasto_id = gasto_id
        self.al_guardar = al_guardar
        gasto = gastos.obtener_gasto(app.con, gasto_id)
        self.nombre = gasto["nombre"]
        pagado = gastos.total_pagado(app.con, gasto_id)
        self.pendiente = gasto["monto_cent"] - pagado
        # Fecha local a propósito: el día que el usuario ve en su calendario.
        self.fecha = date.today()  # noqa: DTZ011

        resumen = [
            ft.Text(
                f"{self.nombre} · Monto {formatear_ars(gasto['monto_cent'])} · "
                f"Pagado {formatear_ars(pagado)} · Pendiente {formatear_ars(self.pendiente)}"
            )
        ]
        if gasto["moneda"] == "USD":
            detalle = formatear_detalle_usd(
                gasto["monto_usd_cent"], gasto["cotizacion_cent"]
            )
            resumen.append(
                texto_ayuda(f"Gasto en dólares: {detalle}. Se paga en pesos.")
            )

        self.monto = campo_monto(
            "Monto del pago",
            "ARS",
            autofocus=True,
            on_submit=self._guardar,
            expand=True,
        )
        boton_todo = ft.TextButton("Pagar todo lo pendiente", on_click=self._pagar_todo)
        self.texto_fecha = ft.TextField(
            label="Fecha",
            value=formatear_fecha(self.fecha.isoformat()),
            read_only=True,
            expand=True,
        )
        # El calendario es otro diálogo de Flet: se abre encima del de pago.
        self.calendario = ft.DatePicker(
            value=self.fecha,
            first_date=date(2000, 1, 1),
            last_date=date(2100, 12, 31),
            help_text="Fecha del pago",
            cancel_text="Cancelar",
            confirm_text="Elegir",
            on_change=self._elegir_fecha,
        )
        self.dialogo = dialogo_formulario(
            "Registrar pago",
            [
                *resumen,
                ft.Row([self.monto, boton_todo]),
                ft.Row(
                    [
                        self.texto_fecha,
                        ft.IconButton(
                            ft.Icons.CALENDAR_MONTH,
                            tooltip="Elegir la fecha",
                            # Por la app, así Esc cierra el calendario y no el pago.
                            on_click=lambda e: app.abrir_dialogo(self.calendario),
                        ),
                    ]
                ),
            ],
            al_guardar=self._guardar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    def _pagar_todo(self, e=None) -> None:
        self.monto.value = formatear_monto_para_editar(self.pendiente)
        self.monto.error = None
        self.app.page.update()

    def _elegir_fecha(self, e=None) -> None:
        valor = self.calendario.value
        # El calendario puede devolver un datetime (fecha con hora): se usa solo la fecha.
        self.fecha = valor.date() if isinstance(valor, datetime) else valor
        self.texto_fecha.value = formatear_fecha(self.fecha.isoformat())
        # O24: el calendario se cierra solo al elegir, pero no es seguro que Flet
        # avise (on_dismiss). Se marca cerrado acá: si Flet avisa igual, cerrarlo
        # dos veces no hace nada. Así Esc y los atajos siguen andando.
        self.app.cerrar_dialogo(self.calendario)

    def _guardar(self, e=None) -> None:
        self.monto.error = None
        monto = leer_campo_monto(self.monto)
        if monto is None:
            self.app.page.update()
            self.app.enfocar(self.monto)
            return
        try:
            pagos.registrar_pago(self.app.con, self.gasto_id, monto, self.fecha)
        except ErrorDeValidacion as error:
            if error.campo is None:  # Ej.: el gasto se borró por detrás.
                self.app.cerrar_dialogo(self.dialogo)
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            self.monto.error = str(error)
            self.app.page.update()
            self.app.enfocar(self.monto)
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.al_guardar(monto, monto == self.pendiente)
