"""Diálogo de ingreso extra, en pesos o dólares (RF-24, docs/diseno.md §4.5)."""

import flet as ft

from app.interfaz.componentes import campo_monto, dialogo_formulario, leer_campo_monto
from app.logica import ingresos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_monto_para_editar

_PREFIJOS = {"ARS": "$ ", "USD": "US$ "}


class DialogoIngreso:
    """Alta (ingreso_id None) o edición de un ingreso extra del mes."""

    def __init__(self, app, mes_id: int, ingreso_id: int | None = None) -> None:
        self.app = app
        self.mes_id = mes_id
        self.ingreso_id = ingreso_id
        actual = ingresos.obtener_ingreso(app.con, ingreso_id) if ingreso_id else None

        self.descripcion = ft.TextField(
            label="Descripción", autofocus=True, max_length=60, on_submit=self._guardar
        )
        self.moneda = ft.SegmentedButton(
            segments=[
                ft.Segment(value="ARS", label=ft.Text("Pesos (ARS)")),
                ft.Segment(value="USD", label=ft.Text("Dólares (USD)")),
            ],
            selected=["ARS"],
            allow_empty_selection=False,
            on_change=self._cambiar_moneda,
        )
        self.monto = campo_monto("Monto", "ARS", on_submit=self._guardar)
        if actual:
            self.descripcion.value = actual["descripcion"]
            self.moneda.selected = [actual["moneda"]]
            self.monto.value = formatear_monto_para_editar(actual["monto_cent"])
            self._cambiar_moneda()

        self.dialogo = dialogo_formulario(
            "Editar ingreso extra" if actual else "Nuevo ingreso extra",
            [self.descripcion, self.moneda, self.monto],
            al_guardar=self._guardar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    def _cambiar_moneda(self, e=None) -> None:
        # Mismo campo, otro prefijo y sufijo: así se ve en qué moneda se escribe.
        moneda = self.moneda.selected[0]
        self.monto.prefix = _PREFIJOS[moneda]
        self.monto.suffix = moneda
        if e is not None:
            self.app.page.update()

    def _guardar(self, e=None) -> None:
        self.descripcion.error = None
        self.monto.error = None
        if not (self.descripcion.value or "").strip():
            self.descripcion.error = "Ingresá una descripción."
        monto = leer_campo_monto(self.monto)
        if self.descripcion.error or monto is None:
            self._enfocar_error()
            return
        datos = (self.descripcion.value, self.moneda.selected[0], monto)
        try:
            if self.ingreso_id:
                ingresos.editar_ingreso(self.app.con, self.ingreso_id, *datos)
            else:
                ingresos.agregar_ingreso(self.app.con, self.mes_id, *datos)
        except ErrorDeValidacion as error:
            if error.campo == "descripcion":
                self.descripcion.error = str(error)
            elif error.campo is None:  # Algo cambió por detrás.
                self.app.cerrar_dialogo(self.dialogo)
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            else:
                self.monto.error = str(error)
            self._enfocar_error()
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.app.refrescar()
        self.app.avisar(
            "Ingreso actualizado" if self.ingreso_id else "Ingreso agregado"
        )

    def _enfocar_error(self) -> None:
        self.app.page.update()
        self.app.enfocar(self.descripcion if self.descripcion.error else self.monto)
