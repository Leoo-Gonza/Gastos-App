"""Gráficos (RF-40 a RF-42, docs/diseno.md §3.8).

Las barras se dibujan con rectángulos de Flet (Container y ProgressBar), sin una
librería de gráficos (decisión del usuario): funcionan en la app de escritorio
sin pasos extra y se pueden probar igual que el resto. Cada gráfico tiene
además "Ver como tabla" con los mismos números.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import texto_ayuda, titulo
from app.logica import configuracion, graficos, meses, prevision
from app.logica.formato import (
    formatear_ars,
    formatear_mes_corto,
    formatear_porcentaje,
    formatear_usd,
    nombre_mes,
)

_ALTO = 200  # Alto total del área de barras verticales, en píxeles.
_ANCHO_BARRA = 28


class PantallaGraficos:
    def __init__(self, app) -> None:
        self.app = app
        self.categorias = ft.Column(spacing=8)
        self.ahorro = ft.Column(spacing=8)
        self.prevision = ft.Column(spacing=8)
        self.pestanas = ft.Tabs(
            length=3,
            selected_index=0,
            expand=True,
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Gastos por categoría"),
                            ft.Tab(label="Ahorro mes a mes"),
                            ft.Tab(label="Previsión de gastos"),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            ft.Column([self.categorias], scroll=ft.ScrollMode.AUTO),
                            ft.Column([self.ahorro], scroll=ft.ScrollMode.AUTO),
                            ft.Column([self.prevision], scroll=ft.ScrollMode.AUTO),
                        ],
                    ),
                ],
                expand=True,
            ),
        )
        self.control = ft.Column(
            [titulo("Gráficos"), self.pestanas], spacing=16, expand=True
        )

    def mostrar_pestana(self, indice: int) -> None:
        self.pestanas.selected_index = indice
        self.app.page.update()

    def refrescar(self) -> None:
        self.categorias.controls = self._por_categoria()
        self.ahorro.controls = self._ahorro_mes_a_mes()
        self.prevision.controls = self._prevision_de_gastos()

    def nuevo(self) -> None:
        """Ctrl+N no tiene acción en esta pantalla."""

    # ------------------------------------------------------------------
    # 1. Gastos por categoría (RN-46): barras horizontales
    # ------------------------------------------------------------------

    def _por_categoria(self) -> list[ft.Control]:
        mes = meses.obtener_mes(self.app.con, self.app.mes_id)
        nombre = nombre_mes(mes["anio"], mes["mes"])
        datos = graficos.gastos_por_categoria(self.app.con, self.app.mes_id)
        if not datos:
            return [texto_ayuda(f"No hay gastos en {nombre} para graficar.")]
        total = sum(v for _, v in datos)
        mayor = datos[0][1]  # Ya vienen de mayor a menor.
        filas = [
            ft.Row(
                [
                    ft.Text(categoria, width=160, tooltip=categoria),
                    ft.ProgressBar(
                        value=valor / mayor,
                        bar_height=18,
                        border_radius=4,
                        color=ft.Colors.PRIMARY,
                        expand=True,
                    ),
                    ft.Text(
                        formatear_ars(valor), width=120, text_align=ft.TextAlign.RIGHT
                    ),
                    ft.Text(
                        formatear_porcentaje(valor / total),
                        width=60,
                        text_align=ft.TextAlign.RIGHT,
                    ),
                ]
            )
            for categoria, valor in datos
        ]
        return [
            ft.Text(
                f"Tu parte de los gastos de {nombre}, por categoría",
                size=estilos.TAM_SECCION,
                weight=ft.FontWeight.W_600,
            ),
            *filas,
            texto_ayuda("En los gastos compartidos se cuenta solo tu parte."),
        ]

    # ------------------------------------------------------------------
    # Barras verticales (ahorro y previsión)
    # ------------------------------------------------------------------

    def _barras(self, puntos: list[tuple[str, int | None, str, str]]) -> ft.Control:
        """Dibuja barras verticales con una línea de 0.

        puntos: [(etiqueta, valor o None, tooltip, rol de color)]. Los valores
        negativos bajan de la línea de 0; None se muestra sin barra.
        """
        valores = [v for _, v, _, _ in puntos if v is not None]
        mayor = max([v for v in valores if v > 0], default=0)
        menor = -min([v for v in valores if v < 0], default=0)
        rango = (mayor + menor) or 1
        alto_arriba = round(_ALTO * mayor / rango)
        alto_abajo = _ALTO - alto_arriba if menor else 0
        columnas = []
        for etiqueta, valor, tooltip, rol in puntos:
            color = estilos.color(self.app.page, rol) if rol else ft.Colors.PRIMARY
            arriba = abajo = ft.Container(width=_ANCHO_BARRA)
            if valor is not None and valor > 0:
                arriba = ft.Container(
                    width=_ANCHO_BARRA,
                    # min(): por redondeos, la barra nunca pasa del alto de su zona (O47).
                    height=min(alto_arriba, max(1, round(_ALTO * valor / rango))),
                    bgcolor=color,
                    border_radius=ft.BorderRadius.only(top_left=4, top_right=4),
                    tooltip=tooltip,
                )
            elif valor is not None and valor < 0:
                abajo = ft.Container(
                    width=_ANCHO_BARRA,
                    height=min(alto_abajo, max(1, round(_ALTO * -valor / rango))),
                    bgcolor=color,
                    border_radius=ft.BorderRadius.only(bottom_left=4, bottom_right=4),
                    tooltip=tooltip,
                )
            columnas.append(
                ft.Column(
                    [
                        ft.Container(
                            height=alto_arriba,
                            alignment=ft.Alignment.BOTTOM_CENTER,
                            content=arriba,
                        ),
                        # La línea de 0.
                        ft.Container(
                            height=1, width=_ANCHO_BARRA + 12, bgcolor=estilos.BORDE
                        ),
                        ft.Container(
                            height=alto_abajo,
                            alignment=ft.Alignment.TOP_CENTER,
                            content=abajo,
                        ),
                        ft.Text(etiqueta, size=estilos.TAM_AYUDA, tooltip=tooltip),
                    ],
                    spacing=0,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )
        return ft.Row(columnas, spacing=8, scroll=ft.ScrollMode.AUTO)

    def _como_tabla(
        self, titulo_col: str, filas: list[tuple[str, str]]
    ) -> ft.ExpansionTile:
        """ "Ver como tabla": los mismos datos en números (§3.8, accesibilidad)."""
        return ft.ExpansionTile(
            title=ft.Text("Ver como tabla"),
            controls=[
                ft.DataTable(
                    columns=[
                        ft.DataColumn(ft.Text("Mes")),
                        ft.DataColumn(ft.Text(titulo_col), numeric=True),
                    ],
                    rows=[
                        ft.DataRow(
                            cells=[ft.DataCell(ft.Text(a)), ft.DataCell(ft.Text(b))]
                        )
                        for a, b in filas
                    ],
                )
            ],
        )

    # ------------------------------------------------------------------
    # 2. Ahorro mes a mes (RN-47)
    # ------------------------------------------------------------------

    def _ahorro_mes_a_mes(self) -> list[ft.Control]:
        datos = graficos.ahorro_por_mes(self.app.con)
        puntos = []
        filas = []
        sin_cotizacion = False
        for anio, mes, ahorro in datos:
            corto = formatear_mes_corto(anio, mes)
            if ahorro is None:
                sin_cotizacion = True
                puntos.append(
                    (
                        f"{corto}\ns/cot.",
                        None,
                        f"{nombre_mes(anio, mes)}: sin cotización",
                        "",
                    )
                )
                filas.append((corto, "sin cotización"))
                continue
            rol = "negativo" if ahorro < 0 else "positivo"
            tooltip = f"{nombre_mes(anio, mes)}: {formatear_usd(ahorro)}"
            puntos.append((corto, ahorro, tooltip, rol))
            filas.append((corto, formatear_usd(ahorro)))
        controles: list[ft.Control] = [
            ft.Text(
                "Ahorro en dólares, mes a mes",
                size=estilos.TAM_SECCION,
                weight=ft.FontWeight.W_600,
            ),
        ]
        meta = configuracion.obtener_meta(self.app.con)
        if meta is not None:
            controles.append(texto_ayuda(f"Meta: {formatear_usd(meta)}"))
        controles.append(self._barras(puntos))
        if sin_cotizacion:
            controles.append(
                texto_ayuda('Los meses marcados "s/cot." no tienen cotización cargada.')
            )
        controles.append(self._como_tabla("Ahorro", filas))
        return controles

    # ------------------------------------------------------------------
    # 3. Previsión de gastos (RN-48)
    # ------------------------------------------------------------------

    def _prevision_de_gastos(self) -> list[ft.Control]:
        p = prevision.calcular_prevision(self.app.con)
        if p.estado == prevision.SIN_MES_ACTUAL:
            actual = nombre_mes(p.anio_actual, p.mes_actual)
            return [texto_ayuda(f"Creá el mes {actual} para ver la previsión.")]
        puntos = [
            (
                formatear_mes_corto(m.anio, m.mes),
                m.gastos,
                f"{nombre_mes(m.anio, m.mes)}: {formatear_ars(m.gastos)}",
                "",
            )
            for m in p.meses
        ]
        filas = [
            (formatear_mes_corto(m.anio, m.mes), formatear_ars(m.gastos))
            for m in p.meses
        ]
        return [
            ft.Text(
                "Gastos estimados de los próximos 12 meses",
                size=estilos.TAM_SECCION,
                weight=ft.FontWeight.W_600,
            ),
            texto_ayuda(
                "Solo gastos fijos y cuotas: bajan a medida que terminan las cuotas."
            ),
            self._barras(puntos),
            self._como_tabla("Gastos estimados", filas),
        ]
