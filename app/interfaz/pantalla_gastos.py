"""Gastos del mes (RF-06 a RF-09, docs/diseno.md §3.3).

En el paso 1: tabla con alta, edición y baja, y el total. Las columnas de
pagos llegan en el paso 2 y "Por medio de pago" en el paso 4.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import estado_vacio, titulo
from app.interfaz.dialogos.dialogo_gasto import DialogoGasto
from app.logica import gastos, meses
from app.logica.formato import clave_orden, formatear_ars, nombre_mes

# Cómo se muestra cada tipo en la tabla, y en qué orden van los grupos (§3.3).
_TIPO_CORTO = {"fijo": "Fijo", "cuota": "Cuota", "unico": "Único"}
_ORDEN_TIPO = {"fijo": 0, "cuota": 1, "unico": 2}


def _cantidad_gastos(n: int) -> str:
    return "1 gasto" if n == 1 else f"{n} gastos"


class PantallaGastos:
    def __init__(self, app) -> None:
        self.app = app
        self.titulo = titulo("")
        self.cuerpo = ft.Column(spacing=16)
        self.control = ft.Column(
            [
                ft.Row(
                    [
                        self.titulo,
                        ft.FilledButton(
                            "Agregar gasto",
                            icon=ft.Icons.ADD,
                            tooltip=f"Agregar gasto ({app.atajo('N')})",
                            on_click=lambda e: self.nuevo(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                self.cuerpo,
            ],
            spacing=24,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _nombre_mes(self) -> str:
        mes = meses.obtener_mes(self.app.con, self.app.mes_id)
        return nombre_mes(mes["anio"], mes["mes"])

    def refrescar(self) -> None:
        nombre = self._nombre_mes()
        self.titulo.value = f"Gastos de {nombre}"
        filas = gastos.listar_gastos(self.app.con, self.app.mes_id)

        if not filas:
            self.cuerpo.controls = [
                estado_vacio(
                    ft.Icons.RECEIPT_LONG,
                    f"Todavía no cargaste gastos en {nombre}.",
                    f"Agregar gasto ({self.app.atajo('N')})",
                    lambda e: self.nuevo(),
                )
            ]
            return

        # Primero fijos, después cuotas, después únicos; dentro de cada grupo, por nombre.
        filas = sorted(
            filas, key=lambda f: (_ORDEN_TIPO[f["tipo"]], clave_orden(f["nombre"]))
        )
        total = gastos.total_gastos(self.app.con, self.app.mes_id)
        self.cuerpo.controls = [self._tabla(filas, total)]

    def _tabla(self, filas, total: int) -> ft.DataTable:
        negrita = ft.FontWeight.W_700
        fila_total = ft.DataRow(
            color=estilos.SUPERFICIE_VARIANTE,
            cells=[
                ft.DataCell(
                    ft.Text(f"TOTAL ({_cantidad_gastos(len(filas))})", weight=negrita)
                ),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text(formatear_ars(total), weight=negrita)),
                ft.DataCell(ft.Text("")),
            ],
        )
        return ft.DataTable(
            heading_row_color=estilos.SUPERFICIE_VARIANTE,
            data_row_min_height=48,
            columns=[
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text("Categoría")),
                ft.DataColumn(ft.Text("Tipo")),
                ft.DataColumn(ft.Text("Medio de pago")),
                # numeric=True alinea los montos a la derecha: miles bajo miles.
                ft.DataColumn(ft.Text("Monto"), numeric=True),
                ft.DataColumn(ft.Text("")),
            ],
            rows=[self._fila(f) for f in filas] + [fila_total],
        )

    def _fila(self, f) -> ft.DataRow:
        categoria = ft.Text(f["categoria"])
        if f["categoria_archivada"]:
            categoria.color = estilos.TEXTO_SECUNDARIO
            categoria.tooltip = "Categoría archivada"
        medio = ft.Text(f["medio_pago"] or "—")
        if f["medio_pago_archivado"]:
            medio.color = estilos.TEXTO_SECUNDARIO
            medio.tooltip = "Medio de pago archivado"

        # "f=f" fija el valor de esta fila dentro de la lambda. Sin eso, todas
        # las lambdas usarían la última fila del for.
        acciones = ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Acciones",
            items=[
                ft.PopupMenuItem(
                    content="Editar",
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda e, f=f: self.editar(f["id"]),
                ),
                ft.PopupMenuItem(
                    content="Borrar",
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=lambda e, f=f: self.borrar(f["id"]),
                ),
            ],
        )
        return ft.DataRow(
            cells=[
                # Clic en el nombre también abre "Editar" (§2.5).
                ft.DataCell(
                    ft.Text(f["nombre"]), on_tap=lambda e, f=f: self.editar(f["id"])
                ),
                ft.DataCell(categoria),
                ft.DataCell(ft.Text(_TIPO_CORTO[f["tipo"]])),
                ft.DataCell(medio),
                ft.DataCell(ft.Text(formatear_ars(f["monto_cent"]))),
                ft.DataCell(acciones),
            ]
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def nuevo(self) -> None:
        """Abre el diálogo de gasto nuevo. También lo usa el atajo Ctrl+N."""
        DialogoGasto(
            self.app, self.app.mes_id, self._nombre_mes(), al_guardar=self._al_guardar
        ).abrir()

    def _gasto_que_ya_no_existe(self, gasto_id: int) -> bool:
        """Si el gasto se borró y la tabla quedó vieja, avisa y la actualiza."""
        if gastos.obtener_gasto(self.app.con, gasto_id) is not None:
            return False
        self.app.refrescar()
        self.app.avisar("Ese gasto ya no existe.")
        return True

    def editar(self, gasto_id: int) -> None:
        if self._gasto_que_ya_no_existe(gasto_id):
            return
        DialogoGasto(
            self.app,
            self.app.mes_id,
            self._nombre_mes(),
            al_guardar=self._al_guardar,
            gasto_id=gasto_id,
            al_borrar=self.borrar,
        ).abrir()

    def _al_guardar(self, nombre: str, es_nuevo: bool) -> None:
        self.app.refrescar()
        self.app.avisar(f'Gasto "{nombre}" {"agregado" if es_nuevo else "actualizado"}')

    def borrar(self, gasto_id: int) -> None:
        if self._gasto_que_ya_no_existe(gasto_id):
            return
        gasto = gastos.obtener_gasto(self.app.con, gasto_id)
        pagado = gastos.total_pagado(self.app.con, gasto_id)

        def confirmado():
            try:
                gastos.borrar_gasto(self.app.con, gasto_id)
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.error_inesperado(error)
                return
            self.app.refrescar()
            self.app.avisar(f'Gasto "{gasto["nombre"]}" borrado')

        self.app.confirmar(
            f"¿Borrar el gasto {gasto['nombre']}?",
            f"Se borran también sus pagos ({formatear_ars(pagado)} pagado). "
            "Esta acción no se puede deshacer.",
            "Borrar",
            confirmado,
        )
