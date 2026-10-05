"""Diálogo de cambio de dólares realizado (RF-26, RN-13, docs/diseno.md §4.6).

Los pesos recibidos se completan solos (USD × cotización) mientras se escribe,
y se pueden corregir a mano si hubo comisión.
"""

from datetime import date, datetime

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import cambios, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    formatear_cotizacion_corta,
    formatear_fecha,
    formatear_monto_para_editar,
    formatear_usd,
    leer_monto,
)


class DialogoCambio:
    """Alta (cambio_id None) o edición de un cambio del mes."""

    def __init__(self, app, mes_id: int, cambio_id: int | None = None) -> None:
        self.app = app
        self.mes_id = mes_id
        self.cambio_id = cambio_id
        actual = cambios.obtener_cambio(app.con, cambio_id) if cambio_id else None
        cotizacion_mes = meses.exigir_mes(app.con, mes_id)["cotizacion_cent"]

        # Fecha local a propósito: el día que el usuario ve en su calendario.
        self.fecha = date.fromisoformat(actual["fecha"]) if actual else date.today()  # noqa: DTZ011
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
            help_text="Fecha del cambio",
            cancel_text="Cancelar",
            confirm_text="Elegir",
            on_change=self._elegir_fecha,
        )
        self.usd = campo_monto(
            "Dólares cambiados",
            "USD",
            hint_text="Ej.: 500,00",
            autofocus=True,
            on_submit=self._guardar,
        )
        self.cotizacion = campo_monto(
            "Cotización del cambio", "ARS", sufijo="por US$", on_submit=self._guardar
        )
        self.ars = campo_monto("Pesos recibidos", "ARS", on_submit=self._guardar)
        self.ayuda_ars = texto_ayuda("")
        self.aviso_recalculo = ft.Text(
            "Se recalculó con los valores nuevos. Si hubo comisión, corregilo.",
            size=estilos.TAM_AYUDA,
            color=estilos.color(app.page, "pendiente"),
            visible=False,
        )
        self.boton_recalcular = ft.TextButton(
            "Volver a calcular",
            visible=False,
            on_click=lambda e: self._recalcular(avisar=False),
        )
        # True si el usuario escribió los pesos a mano (distintos de los sugeridos).
        self.corregido_a_mano = False

        # on_change: se recalcula en cada tecla (RN-13).
        self.usd.on_change = lambda e: self._recalcular(avisar=self.corregido_a_mano)
        self.cotizacion.on_change = lambda e: self._recalcular(
            avisar=self.corregido_a_mano
        )
        self.ars.on_change = lambda e: self._revisar_correccion()

        if actual:
            self.usd.value = formatear_monto_para_editar(actual["usd_cent"])
            self.cotizacion.value = formatear_monto_para_editar(
                actual["cotizacion_cent"]
            )
            self.ars.value = formatear_monto_para_editar(actual["ars_cent"])
            self._revisar_correccion()
        elif cotizacion_mes is not None:
            # La cotización del cambio suele parecerse a la del mes (§3.2).
            self.cotizacion.value = formatear_monto_para_editar(cotizacion_mes)

        self.dialogo = dialogo_formulario(
            "Editar cambio de dólares" if actual else "Registrar cambio de dólares",
            [
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
                self.usd,
                self.cotizacion,
                self.ars,
                ft.Row([self.ayuda_ars, self.boton_recalcular], wrap=True),
                self.aviso_recalculo,
            ],
            al_guardar=self._guardar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    # ------------------------------------------------------------------

    def _sugeridos(self) -> tuple[int, int, int] | None:
        """(usd, cotización, pesos sugeridos) si los dos campos son válidos."""
        try:
            usd = leer_monto(self.usd.value or "")
            cotizacion = leer_monto(self.cotizacion.value or "")
        except ErrorDeValidacion:
            return None
        return usd, cotizacion, cambios.ars_sugeridos(usd, cotizacion)

    def _recalcular(self, avisar: bool) -> None:
        """Completa los pesos con USD × cotización (RN-13)."""
        sugeridos = self._sugeridos()
        if sugeridos is None:
            self.ayuda_ars.value = ""
            return
        usd, cotizacion, ars = sugeridos
        self.ars.value = formatear_monto_para_editar(ars)
        self.ars.error = None
        self.ayuda_ars.value = f"Calculado: {formatear_usd(usd)} × {formatear_cotizacion_corta(cotizacion)}"
        self.aviso_recalculo.visible = avisar
        self.corregido_a_mano = False
        self.boton_recalcular.visible = False
        self.app.page.update()

    def _revisar_correccion(self) -> None:
        """Si los pesos escritos difieren de los sugeridos, se marca "Corregido a mano"."""
        sugeridos = self._sugeridos()
        try:
            escritos = leer_monto(self.ars.value or "")
        except ErrorDeValidacion:
            escritos = None
        self.corregido_a_mano = sugeridos is not None and escritos not in (
            None,
            sugeridos[2],
        )
        self.boton_recalcular.visible = self.corregido_a_mano
        if sugeridos:
            self.ayuda_ars.value = (
                "Corregido a mano"
                if self.corregido_a_mano
                else f"Calculado: {formatear_usd(sugeridos[0])} × "
                f"{formatear_cotizacion_corta(sugeridos[1])}"
            )
        self.aviso_recalculo.visible = False
        self.app.page.update()

    def _elegir_fecha(self, e=None) -> None:
        valor = self.calendario.value
        self.fecha = valor.date() if isinstance(valor, datetime) else valor
        self.texto_fecha.value = formatear_fecha(self.fecha.isoformat())
        # Igual que en "Registrar pago" (O24): no depender de on_dismiss.
        self.app.cerrar_dialogo(self.calendario)

    def _guardar(self, e=None) -> None:
        for campo in (self.usd, self.cotizacion, self.ars):
            campo.error = None
        usd = leer_campo_monto(self.usd, que="El monto en dólares")
        if not (self.cotizacion.value or "").strip():
            self.cotizacion.error = "Ingresá la cotización del cambio."
            cotizacion = None
        else:
            cotizacion = leer_campo_monto(self.cotizacion, que="La cotización")
        ars = leer_campo_monto(self.ars, que="El monto en pesos")
        if None in (usd, cotizacion, ars):
            self._enfocar_error()
            return
        try:
            if self.cambio_id:
                cambios.editar_cambio(
                    self.app.con, self.cambio_id, usd, cotizacion, ars, self.fecha
                )
            else:
                cambios.agregar_cambio(
                    self.app.con, self.mes_id, usd, cotizacion, ars, self.fecha
                )
        except ErrorDeValidacion as error:
            campos = {"usd": self.usd, "cotizacion": self.cotizacion, "ars": self.ars}
            if error.campo in campos:
                campos[error.campo].error = str(error)
                self._enfocar_error()
                return
            self.app.cerrar_dialogo(self.dialogo)
            self.app.refrescar()
            self.app.avisar(str(error))
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.app.refrescar()
        self.app.avisar("Cambio actualizado" if self.cambio_id else "Cambio registrado")

    def _enfocar_error(self) -> None:
        self.app.page.update()
        for campo in (self.usd, self.cotizacion, self.ars):
            if campo.error:
                self.app.enfocar(campo)
                return
