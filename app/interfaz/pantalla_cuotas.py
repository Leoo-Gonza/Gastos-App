"""Planes de cuotas (RF-16 a RF-21, docs/diseno.md §3.4).

Dos meses de referencia, como pide el diseño:
- el filtro activos / terminados / cancelados usa el mes ACTUAL (calendario);
- la columna "Cuota del mes" y el restante usan el mes SELECCIONADO.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import estado_vacio, texto_ayuda, titulo
from app.interfaz.dialogos.dialogo_plan import DialogoPlan
from app.logica import catalogos, cuotas, gastos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    formatear_ars,
    formatear_mes_corto,
    nombre_mes,
    unir_con_y,
)

_ETIQUETAS = {
    cuotas.ACTIVO: "Activos",
    cuotas.TERMINADO: "Terminados",
    cuotas.CANCELADO: "Cancelados",
}


def _mes_corto(anio_mes: tuple[int, int] | None) -> str:
    """(2026, 10) -> "oct 2026"; None (plan sin cuotas) -> "—"."""
    if anio_mes is None:
        return "—"
    return formatear_mes_corto(*anio_mes)


class PantallaCuotas:
    def __init__(self, app) -> None:
        self.app = app
        self.filtro_elegido = cuotas.ACTIVO
        self.subtitulo = texto_ayuda("")
        self.filtro = ft.SegmentedButton(
            segments=[
                ft.Segment(value=v, label=ft.Text(t)) for v, t in _ETIQUETAS.items()
            ],
            selected=[cuotas.ACTIVO],
            allow_empty_selection=False,
            on_change=self._cambiar_filtro,
        )
        self.cuerpo = ft.Column(spacing=16)
        self.control = ft.Column(
            [
                ft.Row(
                    [
                        titulo("Planes de cuotas"),
                        ft.FilledButton(
                            "Nuevo plan",
                            icon=ft.Icons.ADD,
                            tooltip=f"Nuevo plan ({app.atajo('N')})",
                            on_click=lambda e: self.nuevo(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.subtitulo,
                self.filtro,
                self.cuerpo,
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _mes_visto(self) -> tuple[int, int]:
        mes = meses.obtener_mes(self.app.con, self.app.mes_id)
        return mes["anio"], mes["mes"]

    def refrescar(self) -> None:
        anio, mes = self._mes_visto()
        actual = nombre_mes(*meses.mes_actual_calendario())
        self.subtitulo.value = f"Cuota y restante calculados para {nombre_mes(anio, mes)} (mes seleccionado)."
        todos = cuotas.listar_planes(self.app.con, anio, mes)
        # Las cantidades van en la etiqueta del filtro: "Activos (4)".
        for segmento in self.filtro.segments:
            cuantos = sum(1 for d in todos if d.estado == segmento.value)
            segmento.label = ft.Text(f"{_ETIQUETAS[segmento.value]} ({cuantos})")
        self.filtro.tooltip = f"Según el mes actual ({actual})"

        if not todos:
            self.filtro.visible = False
            self.cuerpo.controls = [
                estado_vacio(
                    ft.Icons.CREDIT_CARD,
                    "No tenés planes de cuotas cargados.",
                    "Nuevo plan",
                    lambda e: self.nuevo(),
                )
            ]
            return
        self.filtro.visible = True
        visibles = [d for d in todos if d.estado == self.filtro_elegido]
        if not visibles:
            texto = f"No hay planes {_ETIQUETAS[self.filtro_elegido].lower()}."
            self.cuerpo.controls = [texto_ayuda(texto)]
            return
        self.cuerpo.controls = [self._tabla(visibles, anio, mes)]

    def _cambiar_filtro(self, e=None) -> None:
        self.filtro_elegido = self.filtro.selected[0]
        # BUG-22: refrescar() de esta pantalla no pasa por la protección de la app.
        if not self.app.verificar_mes():
            return
        self.refrescar()
        self.app.page.update()

    def _tabla(self, detalles, anio: int, mes: int) -> ft.DataTable:
        negrita = ft.FontWeight.W_700
        total_cuotas = sum(d.plan["monto_cuota_cent"] for d in detalles)
        total_restante = sum(d.restante for d in detalles)
        fila_total = ft.DataRow(
            color=estilos.SUPERFICIE_VARIANTE,
            cells=[
                ft.DataCell(ft.Text("Total", weight=negrita)),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text(formatear_ars(total_cuotas), weight=negrita)),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text(formatear_ars(total_restante), weight=negrita)),
                ft.DataCell(ft.Text("")),
            ],
        )
        return ft.DataTable(
            heading_row_color=estilos.SUPERFICIE_VARIANTE,
            data_row_min_height=48,
            columns=[
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text("Categoría")),
                ft.DataColumn(ft.Text("Medio")),
                ft.DataColumn(ft.Text("Cuota"), numeric=True),
                ft.DataColumn(ft.Text("Cuota del mes")),
                ft.DataColumn(ft.Text("Primera")),
                ft.DataColumn(ft.Text("Última")),
                ft.DataColumn(ft.Text("Restante"), numeric=True),
                ft.DataColumn(ft.Text("")),
            ],
            rows=[self._fila(d, anio, mes) for d in detalles] + [fila_total],
        )

    def _celda_cuota_del_mes(self, d) -> ft.Control:
        if d.estado == cuotas.CANCELADO:
            return ft.Row(
                [
                    ft.Icon(ft.Icons.BLOCK, size=16, color=estilos.TEXTO_SECUNDARIO),
                    ft.Text("Cancelado", color=estilos.TEXTO_SECUNDARIO),
                ],
                tight=True,
            )
        if d.cuota_texto == "terminado":
            positivo = estilos.color(self.app.page, "positivo")
            return ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK, size=16, color=positivo),
                    ft.Text("Terminado", color=positivo),
                ],
                tight=True,
            )
        if d.cuota_texto == "no empezó":
            return ft.Text("No empezó", color=estilos.TEXTO_SECUNDARIO)
        return ft.Text(d.cuota_texto)

    def _fila(self, d, anio: int, mes: int) -> ft.DataRow:
        plan = d.plan
        con = self.app.con
        categoria = catalogos.obtener(con, catalogos.CATEGORIAS, plan["categoria_id"])
        medio = (
            catalogos.obtener(con, catalogos.MEDIOS_PAGO, plan["medio_pago_id"])
            if plan["medio_pago_id"] is not None
            else None
        )
        items = [
            ft.PopupMenuItem(
                content="Editar plan",
                icon=ft.Icons.EDIT_OUTLINED,
                on_click=lambda e: self.editar(plan["id"]),
            )
        ]
        if d.estado == cuotas.ACTIVO:
            items.append(
                ft.PopupMenuItem(
                    content="Cancelar plan",
                    icon=ft.Icons.BLOCK,
                    on_click=lambda e: self.cancelar(plan["id"]),
                )
            )
        tiene_cuota = con.execute(
            "SELECT 1 FROM gastos WHERE mes_id = ? AND plan_cuotas_id = ?",
            (self.app.mes_id, plan["id"]),
        ).fetchone()
        if tiene_cuota:
            items.append(
                ft.PopupMenuItem(
                    content="Ir a la cuota del mes",
                    icon=ft.Icons.RECEIPT_LONG_OUTLINED,
                    on_click=lambda e: self.app.seleccionar_mes(
                        self.app.mes_id, pantalla="Gastos"
                    ),
                )
            )
        return ft.DataRow(
            cells=[
                ft.DataCell(
                    ft.Text(plan["nombre"]), on_tap=lambda e: self.editar(plan["id"])
                ),
                ft.DataCell(ft.Text(categoria["nombre"])),
                ft.DataCell(ft.Text(medio["nombre"] if medio else "—")),
                ft.DataCell(ft.Text(formatear_ars(plan["monto_cuota_cent"]))),
                ft.DataCell(self._celda_cuota_del_mes(d)),
                ft.DataCell(
                    ft.Text(_mes_corto((plan["primer_anio"], plan["primer_mes"])))
                ),
                ft.DataCell(ft.Text(_mes_corto(d.ultima))),
                ft.DataCell(ft.Text(formatear_ars(d.restante))),
                ft.DataCell(
                    ft.PopupMenuButton(
                        icon=ft.Icons.MORE_VERT, tooltip="Acciones", items=items
                    )
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def nuevo(self) -> None:
        """Botón "Nuevo plan" y Ctrl+N en esta pantalla."""
        if self.app.verificar_mes():  # O37: igual que el botón de Gastos.
            DialogoPlan(self.app).abrir()

    def editar(self, plan_id: int) -> None:
        if cuotas.obtener_plan(self.app.con, plan_id) is None:
            self.app.refrescar()
            self.app.avisar("Ese plan de cuotas ya no existe.")
            return
        DialogoPlan(self.app, plan_id).abrir()

    def cancelar(self, plan_id: int) -> None:
        """RF-20: confirmación que dice exactamente qué cuotas se borran (§3.4)."""
        plan = cuotas.obtener_plan(self.app.con, plan_id)
        if plan is None:
            self.app.refrescar()
            self.app.avisar("Ese plan de cuotas ya no existe.")
            return
        explicacion = self._que_pasa_al_cancelar(plan)

        def confirmado():
            try:
                cuotas.cancelar_plan(self.app.con, plan_id)
            except ErrorDeValidacion as error:
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.error_inesperado(error)
                return
            self.app.refrescar()
            self.app.avisar(f'Plan "{plan["nombre"]}" cancelado')

        self.app.confirmar(
            f"¿Cancelar el plan {plan['nombre']}?",
            explicacion,
            "Cancelar plan",
            confirmado,
            texto_volver="Volver",
        )

    def _que_pasa_al_cancelar(self, plan) -> str:
        """Arma el texto con los meses concretos que se van a tocar (RN-31)."""
        con = self.app.con
        anio, mes = meses.mes_actual_calendario()
        filas = con.execute(
            """SELECT g.id, m.anio, m.mes FROM gastos g JOIN meses m ON m.id = g.mes_id
                WHERE g.plan_cuotas_id = ? AND (m.anio, m.mes) >= (?, ?)
                ORDER BY m.anio, m.mes""",
            (plan["id"], anio, mes),
        ).fetchall()
        partes = []
        se_borran = []
        for f in filas:
            nombre = nombre_mes(f["anio"], f["mes"])
            con_pagos = gastos.total_pagado(con, f["id"]) > 0
            if (f["anio"], f["mes"]) == (anio, mes) and con_pagos:
                partes.append(
                    f"La cuota de {nombre} ya tiene pagos: se conserva y pasa a ser la última."
                )
            elif not con_pagos:
                se_borran.append(nombre)
        if se_borran:
            if len(se_borran) == 1:
                partes.append(f"Se borra su cuota de {se_borran[0]}.")
            else:
                partes.append(f"Se borran sus cuotas de {unir_con_y(se_borran)}.")
        partes.append(
            "No se generan más cuotas. Las cuotas de meses anteriores se conservan."
        )
        return " ".join(partes)
