"""Diálogo de un ítem de "Me deben" cargado a mano (RF-32, docs/diseno.md §4.8).

Ej.: Sofía, "Préstamo MP", $ 20.000, 02/10/2026. Sirve para el alta y la edición.
"""

from datetime import date, datetime

import flet as ft

from app.interfaz.componentes import campo_monto, dialogo_formulario, leer_campo_monto
from app.logica import catalogos, me_deben
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_fecha, formatear_monto_para_editar


class DialogoItem:
    """item_id None = ítem nuevo (persona_id opcional para precargarla)."""

    def __init__(
        self, app, persona_id: int | None = None, item_id: int | None = None
    ) -> None:
        self.app = app
        self.item_id = item_id
        self.actual = me_deben.obtener_item(app.con, item_id) if item_id else None
        if self.actual:
            persona_id = self.actual["persona_id"]

        opciones = [
            ft.DropdownOption(key=str(p["id"]), text=p["nombre"])
            for p in catalogos.listar(app.con, catalogos.PERSONAS)
        ]
        if persona_id is not None and str(persona_id) not in [o.key for o in opciones]:
            # La persona del ítem está archivada: se muestra igual, con sufijo.
            persona = catalogos.obtener(app.con, catalogos.PERSONAS, persona_id)
            if persona is not None:
                opciones.append(
                    ft.DropdownOption(
                        key=str(persona_id), text=f"{persona['nombre']} (archivada)"
                    )
                )
        self.persona = ft.Dropdown(
            label="Persona",
            options=opciones,
            value=str(persona_id) if persona_id is not None else None,
        )
        self.descripcion = ft.TextField(
            label="Descripción",
            max_length=60,
            on_submit=self._guardar,
            autofocus=persona_id is not None,
        )
        self.monto = campo_monto("Monto", "ARS", on_submit=self._guardar)
        # Fecha local a propósito: el día que el usuario ve en su calendario.
        self.fecha = (
            date.fromisoformat(self.actual["fecha"]) if self.actual else date.today()  # noqa: DTZ011
        )
        self.texto_fecha = ft.TextField(
            label="Fecha",
            value=formatear_fecha(self.fecha.isoformat()),
            read_only=True,
            expand=True,
        )
        self.calendario = ft.DatePicker(
            value=self.fecha,
            first_date=date(2000, 1, 1),
            last_date=date(2100, 12, 31),
            help_text="Fecha",
            cancel_text="Cancelar",
            confirm_text="Elegir",
            on_change=self._elegir_fecha,
        )
        if self.actual:
            self.descripcion.value = self.actual["descripcion"]
            self.monto.value = formatear_monto_para_editar(self.actual["monto_cent"])

        self.dialogo = dialogo_formulario(
            "Editar ítem" if self.actual else "Nuevo ítem de Me deben",
            [
                self.persona,
                self.descripcion,
                self.monto,
                ft.Row(
                    [
                        self.texto_fecha,
                        ft.IconButton(
                            ft.Icons.CALENDAR_MONTH,
                            tooltip="Elegir la fecha",
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

    def _elegir_fecha(self, e=None) -> None:
        valor = self.calendario.value
        self.fecha = valor.date() if isinstance(valor, datetime) else valor
        self.texto_fecha.value = formatear_fecha(self.fecha.isoformat())
        self.app.cerrar_dialogo(self.calendario)  # Igual que en pagos (O24).

    def _guardar(self, e=None) -> None:
        self.persona.error_text = None
        self.descripcion.error = None
        self.monto.error = None
        if not self.persona.value:
            self.persona.error_text = "Elegí una persona."
        if not (self.descripcion.value or "").strip():
            self.descripcion.error = "Ingresá una descripción."
        monto = leer_campo_monto(self.monto)
        if self.persona.error_text or self.descripcion.error or monto is None:
            self._enfocar_error()
            return
        datos = (int(self.persona.value), self.descripcion.value, monto, self.fecha)
        try:
            if self.actual:
                me_deben.editar_item(self.app.con, self.item_id, *datos)
            else:
                me_deben.agregar_item(self.app.con, *datos)
        except ErrorDeValidacion as error:
            if error.campo == "persona":
                self.persona.error_text = str(error)
            elif error.campo == "descripcion":
                self.descripcion.error = str(error)
            elif error.campo == "monto":
                self.monto.error = str(error)
            else:  # Algo cambió por detrás (ej. el ítem se borró).
                self.app.cerrar_dialogo(self.dialogo)
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            self._enfocar_error()
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.app.refrescar()
        self.app.avisar("Ítem actualizado" if self.actual else "Ítem agregado")

    def _enfocar_error(self) -> None:
        self.app.page.update()
        for campo, error in (
            (self.persona, self.persona.error_text),
            (self.descripcion, self.descripcion.error),
            (self.monto, self.monto.error),
        ):
            if error:
                self.app.enfocar(campo)
                return
