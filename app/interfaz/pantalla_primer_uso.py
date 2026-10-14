"""Primer uso: crear el primer mes (RF-04, docs/diseno.md §3.1)."""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import campo_monto, leer_campo_monto, texto_ayuda
from app.logica import meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MESES


class PantallaPrimerUso:
    def __init__(self, app) -> None:
        self.app = app
        anio_actual, mes_actual = meses.mes_actual_calendario()

        self.mes = ft.Dropdown(
            label="Mes",
            value=str(mes_actual),
            # La clave de cada opción es el número de mes como texto ("1".."12").
            options=[
                ft.DropdownOption(key=str(n), text=nombre)
                for n, nombre in enumerate(MESES, 1)
            ],
            expand=True,
        )
        self.anio = ft.TextField(
            label="Año",
            value=str(anio_actual),
            max_length=4,
            width=120,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"[0-9]", allow=True),
        )
        self.sueldo = campo_monto(
            "Sueldo", "USD", autofocus=True, on_submit=self._crear
        )
        self.cotizacion = campo_monto(
            "Cotización (opcional)",
            "ARS",
            helper="Podés dejarla vacía y cargarla después.",
            on_submit=self._crear,
        )
        # El aviso de sueldo 0 se agrega a lo que ya hace campo_monto al salir del campo.
        formatear_al_salir = self.sueldo.on_blur

        def al_salir_del_sueldo(e):
            formatear_al_salir(e)
            self._avisar_si_sueldo_cero()

        self.sueldo.on_blur = al_salir_del_sueldo

        tarjeta = ft.Card(
            width=480,
            content=ft.Container(
                padding=24,
                content=ft.Column(
                    [
                        ft.Row([self.mes, self.anio], spacing=12),
                        self.sueldo,
                        self.cotizacion,
                        ft.Row(
                            [ft.FilledButton("Crear mes", on_click=self._crear)],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ],
                    spacing=16,
                    tight=True,
                ),
            ),
        )
        self.control = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Text(
                        "Bienvenido a tu app de gastos",
                        size=estilos.TAM_TITULO,
                        weight=ft.FontWeight.W_600,
                    ),
                    texto_ayuda(
                        "Para empezar, creá el primer mes que querés registrar."
                    ),
                    tarjeta,
                    # v2: quien tiene una planilla puede empezar importándola.
                    # Es un botón de texto para que "Crear mes" siga siendo la
                    # acción principal (§3.1).
                    ft.Row(
                        [
                            ft.Text(
                                "¿Tenés una planilla?",
                                size=14,
                                color=estilos.TEXTO_SECUNDARIO,
                            ),
                            ft.TextButton(
                                "Importar Excel",
                                icon=ft.Icons.UPLOAD_FILE,
                                on_click=lambda e: app.mostrar_importacion(
                                    "primer_uso"
                                ),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        tight=True,
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                spacing=16,
            ),
        )

    def _avisar_si_sueldo_cero(self) -> None:
        es_cero = leer_campo_monto(self.sueldo, permitir_cero=True) == 0
        # Acá solo interesa el aviso; los errores se muestran al tocar "Crear mes".
        self.sueldo.error = None
        if es_cero:
            self.sueldo.helper = "El sueldo de este mes es 0"
            self.sueldo.helper_style = ft.TextStyle(
                color=estilos.color(self.app.page, "pendiente")
            )
        else:
            self.sueldo.helper = None

    def _crear(self, e=None) -> None:
        for campo in (self.anio, self.sueldo, self.cotizacion):
            campo.error = None
        self.mes.error_text = None

        # Primero se revisa cada campo por separado, para mostrar todos los errores juntos.
        anio = int(self.anio.value) if self.anio.value else None
        if anio is None or len(self.anio.value) != 4:
            self.anio.error = "El año tiene que tener 4 dígitos. Ej.: 2026"
        if not (self.sueldo.value or "").strip():
            self.sueldo.error = "Ingresá el sueldo. Si este mes no cobrás, poné 0."
            sueldo = None
        else:
            sueldo = leer_campo_monto(self.sueldo, permitir_cero=True, que="El sueldo")
        cotizacion = None
        if (self.cotizacion.value or "").strip():
            cotizacion = leer_campo_monto(self.cotizacion, que="La cotización")

        if self._enfocar_primer_error():
            return

        try:
            mes_id = meses.crear_primer_mes(
                self.app.con, anio, int(self.mes.value), sueldo, cotizacion
            )
        except ErrorDeValidacion as error:
            # La lógica dice en qué campo está el problema (error.campo).
            campos = {
                "anio": self.anio,
                "sueldo": self.sueldo,
                "cotizacion": self.cotizacion,
            }
            if error.campo in campos:
                campos[error.campo].error = str(error)
            else:
                self.mes.error_text = str(error)
            self._enfocar_primer_error()
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.error_inesperado(error)
            return
        self.app.mostrar_principal(mes_id)

    def _enfocar_primer_error(self) -> bool:
        """Lleva el cursor al primer campo con error. Devuelve True si había alguno."""
        self.app.page.update()
        for campo in (self.anio, self.sueldo, self.cotizacion):
            if campo.error:
                self.app.enfocar(campo)
                return True
        return bool(self.mes.error_text)
