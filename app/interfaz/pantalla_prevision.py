"""Previsión de los próximos 12 meses (RF-38, RF-39, docs/diseno.md §3.7).

No depende del mes seleccionado: siempre mira desde el mes del calendario.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import estado_vacio, texto_ayuda, titulo
from app.interfaz.dialogos import dialogos_valores
from app.logica import meses, prevision
from app.logica.formato import (
    formatear_ars,
    formatear_cotizacion,
    formatear_mes_corto,
    formatear_usd,
    nombre_mes,
)


class PantallaPrevision:
    def __init__(self, app) -> None:
        self.app = app
        self.subtitulo = texto_ayuda("")
        self.cuerpo = ft.Column(spacing=16)
        self.control = ft.Column(
            [titulo("Previsión de los próximos 12 meses"), self.subtitulo, self.cuerpo],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def refrescar(self) -> None:
        p = prevision.calcular_prevision(self.app.con)
        actual = nombre_mes(p.anio_actual, p.mes_actual)
        if p.estado == prevision.SIN_MES_ACTUAL:
            self.subtitulo.value = ""
            self.cuerpo.controls = [self._sin_mes_actual(p, actual)]
            return

        desde = nombre_mes(p.meses[0].anio, p.meses[0].mes)
        if p.cotizacion is not None:
            cotizacion = f"la cotización ({formatear_cotizacion(p.cotizacion)}) y "
        else:
            cotizacion = ""
        self.subtitulo.value = (
            f"Desde {desde}. Con {cotizacion}el sueldo ({formatear_usd(p.sueldo_usd)}) de "
            f"{actual} (mes actual). Solo gastos fijos y cuotas; sin inflación ni ingresos extra."
        )
        controles: list[ft.Control] = []
        if p.estado == prevision.SIN_COTIZACION:
            controles.append(self._aviso_sin_cotizacion(actual))
        controles += [
            self._tabla(p),
            ft.TextButton(
                "Ver el gráfico de previsión",
                icon=ft.Icons.BAR_CHART,
                on_click=lambda e: self._ir_al_grafico(),
            ),
        ]
        self.cuerpo.controls = controles

    def _sin_mes_actual(self, p, actual: str) -> ft.Control:
        """RN-45: sin el mes actual no hay previsión. Si es justo el que sigue, se ofrece crearlo."""
        texto = f"Creá el mes {actual} para ver la previsión."
        ultimo = meses.obtener_ultimo_mes(self.app.con)
        siguiente = meses.siguiente(ultimo["anio"], ultimo["mes"]) if ultimo else None
        if siguiente == (p.anio_actual, p.mes_actual):
            return estado_vacio(
                ft.Icons.TRENDING_UP,
                texto,
                "Mes nuevo",
                lambda e: self.app.crear_mes_nuevo(),
            )
        return ft.Container(padding=48, content=ft.Text(texto, size=estilos.TAM_TEXTO))

    def _aviso_sin_cotizacion(self, actual: str) -> ft.Control:
        color = estilos.color(self.app.page, "pendiente")
        return ft.Container(
            padding=12,
            border_radius=8,
            bgcolor=estilos.color(self.app.page, "pendiente_suave"),
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.WARNING_AMBER, color=color),
                    ft.Text(
                        f"Falta la cotización de {actual}: se muestran solo los gastos en pesos.",
                        color=color,
                        expand=True,
                    ),
                    ft.TextButton(
                        "Cargar cotización",
                        on_click=lambda e: self._cargar_cotizacion(),
                    ),
                ]
            ),
        )

    def _cargar_cotizacion(self) -> None:
        """La previsión usa el mes actual: se carga la cotización de ese mes."""
        p = prevision.calcular_prevision(self.app.con)
        actual = meses.obtener_mes_por_fecha(self.app.con, p.anio_actual, p.mes_actual)
        if actual is None:
            self.app.refrescar()
            return
        dialogos_valores.abrir_cotizacion(self.app, actual["id"])

    def _ir_al_grafico(self) -> None:
        if self.app.verificar_mes():
            self.app.seleccionar_mes(self.app.mes_id, pantalla="Gráficos")
            self.app.pantalla("Gráficos").mostrar_pestana(2)

    def _tabla(self, p) -> ft.DataTable:
        filas = []
        positivo = estilos.color(self.app.page, "positivo")
        negativo = estilos.color(self.app.page, "negativo")
        for m in p.meses:
            if m.ahorro is None:
                ahorro: ft.Control = ft.Text("—")
                usd: ft.Control = ft.Text("—")
            else:
                usd = ft.Text(formatear_usd(m.usd_a_cambiar))
                if m.ahorro < 0:
                    # El color nunca es la única señal: también la palabra "Déficit".
                    ahorro = ft.Text(
                        f"{formatear_usd(m.ahorro)} Déficit", color=negativo
                    )
                else:
                    ahorro = ft.Text(formatear_usd(m.ahorro))
            liberados = ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ARROW_DOWNWARD, size=14, color=positivo),
                            ft.Text(
                                f"{nombre} +{formatear_ars(monto)}", color=positivo
                            ),
                        ],
                        tight=True,
                        spacing=4,
                    )
                    for nombre, monto in m.liberados
                ],
                spacing=0,
                tight=True,
            )
            filas.append(
                ft.DataRow(
                    color=estilos.color(self.app.page, "positivo_suave")
                    if m.liberados
                    else None,
                    cells=[
                        ft.DataCell(ft.Text(formatear_mes_corto(m.anio, m.mes))),
                        ft.DataCell(ft.Text(formatear_ars(m.gastos))),
                        ft.DataCell(usd),
                        ft.DataCell(ahorro),
                        ft.DataCell(liberados),
                    ],
                )
            )
        return ft.DataTable(
            heading_row_color=estilos.SUPERFICIE_VARIANTE,
            data_row_max_height=72,
            columns=[
                ft.DataColumn(ft.Text("Mes")),
                ft.DataColumn(ft.Text("Gastos estimados"), numeric=True),
                ft.DataColumn(ft.Text("Dólares a cambiar"), numeric=True),
                ft.DataColumn(ft.Text("Ahorro estimado"), numeric=True),
                ft.DataColumn(ft.Text("Se libera")),
            ],
            rows=filas,
        )

    def nuevo(self) -> None:
        """Ctrl+N no tiene acción en esta pantalla (no se carga nada acá)."""
