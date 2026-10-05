"""Gastos del mes (RF-06 a RF-09, docs/diseno.md §3.3).

Tabla con alta, edición y baja (paso 1), gastos en dólares (paso 1c) y pagos:
tilde "pagado", pagos parciales y pendiente (paso 2). "Por medio de pago"
llega en el paso 4.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import estado_vacio, titulo
from app.interfaz.dialogos.dialogo_gasto import DialogoGasto
from app.interfaz.dialogos.dialogo_pago import DialogoPago
from app.interfaz.dialogos.dialogo_ver_pagos import DialogoVerPagos
from app.logica import gastos, meses, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    clave_orden,
    formatear_ars,
    formatear_cotizacion,
    formatear_detalle_usd,
    formatear_usd,
    nombre_mes,
)

# Cómo se muestra cada tipo en la tabla, y en qué orden van los grupos (§3.3).
_TIPO_CORTO = {"fijo": "Fijo", "cuota": "Cuota", "unico": "Único"}
_ORDEN_TIPO = {"fijo": 0, "cuota": 1, "unico": 2}


def _celda_monto(f) -> ft.Control:
    """Monto en pesos (lo que se paga). Si el gasto es en dólares, debajo va en
    letra chica de dónde salen esos pesos: "US$ 20,00 × $ 1.600" (§3.3)."""
    pesos = ft.Text(formatear_ars(f["monto_cent"]))
    if f["moneda"] != "USD":
        return pesos
    usd, cotizacion = f["monto_usd_cent"], f["cotizacion_cent"]
    return ft.Column(
        [
            pesos,
            ft.Text(
                formatear_detalle_usd(usd, cotizacion),
                size=estilos.TAM_AYUDA,
                color=estilos.TEXTO_SECUNDARIO,
            ),
        ],
        spacing=0,
        horizontal_alignment=ft.CrossAxisAlignment.END,
        tight=True,
        tooltip=f"Gasto en dólares: {formatear_usd(usd)} a {formatear_cotizacion(cotizacion)} "
        f"= {formatear_ars(f['monto_cent'])}. Los pesos quedan fijos con esa cotización.",
    )


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
        totales = pagos.totales_del_mes(self.app.con, self.app.mes_id)
        self.cuerpo.controls = [self._tabla(filas, totales)]

    def _tabla(self, filas, totales: dict[str, int]) -> ft.DataTable:
        negrita = ft.FontWeight.W_700
        fila_total = ft.DataRow(
            color=estilos.SUPERFICIE_VARIANTE,
            cells=[
                ft.DataCell(ft.Text("")),
                ft.DataCell(
                    ft.Text(f"TOTAL ({_cantidad_gastos(len(filas))})", weight=negrita)
                ),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                ft.DataCell(ft.Text("")),
                # "Gastos", "Pagado" y "Falta por pagar" de la planilla (RF-09).
                ft.DataCell(ft.Text(formatear_ars(totales["total"]), weight=negrita)),
                ft.DataCell(ft.Text(formatear_ars(totales["pagado"]), weight=negrita)),
                ft.DataCell(self._celda_pendiente(totales["pendiente"], es_total=True)),
                ft.DataCell(ft.Text("")),
            ],
        )
        return ft.DataTable(
            heading_row_color=estilos.SUPERFICIE_VARIANTE,
            data_row_min_height=48,
            # 64 deja lugar para la segunda línea (dólares o "Parcial").
            data_row_max_height=64,
            columns=[
                ft.DataColumn(ft.Text("Pag.")),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text("Categoría")),
                ft.DataColumn(ft.Text("Tipo")),
                ft.DataColumn(ft.Text("Medio de pago")),
                # numeric=True alinea los montos a la derecha: miles bajo miles.
                ft.DataColumn(ft.Text("Monto"), numeric=True),
                ft.DataColumn(ft.Text("Pagado"), numeric=True),
                ft.DataColumn(ft.Text("Pendiente"), numeric=True),
                ft.DataColumn(ft.Text("")),
            ],
            rows=[self._fila(f) for f in filas] + [fila_total],
        )

    def _celda_pagado(self, f) -> ft.Control:
        pagado = ft.Text(formatear_ars(f["pagado_cent"]))
        if not 0 < f["pagado_cent"] < f["monto_cent"]:
            return pagado
        # Pago parcial: etiqueta chica debajo, en color "pendiente" (§3.3).
        return ft.Column(
            [
                pagado,
                ft.Text(
                    "Parcial",
                    size=estilos.TAM_AYUDA,
                    color=estilos.color(self.app.page, "pendiente"),
                ),
            ],
            spacing=0,
            horizontal_alignment=ft.CrossAxisAlignment.END,
            tight=True,
        )

    def _celda_pendiente(self, pendiente: int, es_total: bool = False) -> ft.Control:
        """Lo que falta en color "pendiente"; si es 0, "Pagado" con un tilde en verde.

        El color nunca es la única señal: siempre hay texto o ícono (§0).
        """
        peso = ft.FontWeight.W_700 if es_total else None
        if pendiente > 0:
            return ft.Text(
                formatear_ars(pendiente),
                color=estilos.color(self.app.page, "pendiente"),
                weight=peso,
            )
        positivo = estilos.color(self.app.page, "positivo")
        return ft.Row(
            [
                ft.Icon(
                    ft.Icons.CHECK_CIRCLE if es_total else ft.Icons.CHECK,
                    color=positivo,
                    size=16,
                ),
                ft.Text(
                    formatear_ars(0) if es_total else "Pagado",
                    color=positivo,
                    weight=peso,
                ),
            ],
            tight=True,
            spacing=4,
            alignment=ft.MainAxisAlignment.END,
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
        pendiente = f["monto_cent"] - f["pagado_cent"]

        # "f=f" fija el valor de esta fila dentro de la lambda. Sin eso, todas
        # las lambdas usarían la última fila del for.
        tilde = ft.Checkbox(
            # RN-22: marcado si no falta nada, con el tilde o con pagos parciales.
            value=pendiente == 0,
            tooltip="Marcar como pagado",
            on_change=lambda e, f=f: self._cambiar_tilde(f, e.control),
        )
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
                    content="Registrar pago",
                    icon=ft.Icons.PAYMENTS_OUTLINED,
                    on_click=lambda e, f=f: self.registrar_pago(f["id"]),
                ),
                ft.PopupMenuItem(
                    content="Ver pagos",
                    icon=ft.Icons.RECEIPT_OUTLINED,
                    on_click=lambda e, f=f: self.ver_pagos(f["id"]),
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
                ft.DataCell(tilde),
                # Clic en el nombre también abre "Editar" (§2.5).
                ft.DataCell(
                    ft.Text(f["nombre"]), on_tap=lambda e, f=f: self.editar(f["id"])
                ),
                ft.DataCell(categoria),
                ft.DataCell(ft.Text(_TIPO_CORTO[f["tipo"]])),
                ft.DataCell(medio),
                ft.DataCell(_celda_monto(f)),
                ft.DataCell(self._celda_pagado(f)),
                ft.DataCell(self._celda_pendiente(pendiente)),
                ft.DataCell(acciones),
            ]
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def nuevo(self) -> None:
        """Abre el diálogo de gasto nuevo. También lo usa el atajo Ctrl+N."""
        if not self.app.verificar_mes():
            return
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

    def _al_guardar(self, gasto_id: int, es_nuevo: bool) -> None:
        gasto = gastos.obtener_gasto(self.app.con, gasto_id)
        aviso = f'Gasto "{gasto["nombre"]}" {"agregado" if es_nuevo else "actualizado"}'
        if es_nuevo and gasto["moneda"] == "USD":
            # Ej.: 'Gasto "Claude" agregado: $ 32.000 (US$ 20,00)' (§6, paso 1c).
            aviso += f": {formatear_ars(gasto['monto_cent'])} ({formatear_usd(gasto['monto_usd_cent'])})"
        self.app.refrescar()
        self.app.avisar(aviso)

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

    # ------------------------------------------------------------------
    # Pagos (paso 2)
    # ------------------------------------------------------------------

    def _cambiar_tilde(self, f, tilde: ft.Checkbox) -> None:
        if self._gasto_que_ya_no_existe(f["id"]):
            return
        if tilde.value:
            self._marcar_pagado(f)
        else:
            # Destildar borra pagos: hasta que confirme, el tilde sigue marcado.
            tilde.value = True
            self._confirmar_quitar_pagos(f)

    def _marcar_pagado(self, f) -> None:
        """RN-22: un pago por todo lo pendiente, con "Deshacer" (§3.3)."""
        try:
            pago_id = pagos.marcar_pagado(self.app.con, f["id"])
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.error_inesperado(error)
            return
        self.app.refrescar()
        if pago_id is None:
            return  # Ya estaba pagado: no hay nada que deshacer.

        def deshacer():
            # "Deshacer" borra solo el pago que agregó el tilde.
            try:
                pagos.borrar_pago(self.app.con, pago_id)
            except ErrorDeValidacion:
                pass  # Ya se había borrado por otro lado.
            self.app.refrescar()

        self.app.avisar(f"{f['nombre']} marcado como pagado", al_deshacer=deshacer)

    def _confirmar_quitar_pagos(self, f) -> None:
        lista = pagos.listar_pagos(self.app.con, f["id"])
        pagado = sum(p["monto_cent"] for p in lista)
        if len(lista) == 1:
            cantidad = "Se va a borrar el pago registrado"
        else:
            cantidad = f"Se van a borrar los {len(lista)} pagos registrados"

        def confirmado():
            try:
                pagos.quitar_pagos(self.app.con, f["id"])
            except ErrorDeValidacion as error:
                # Ej.: el gasto se borró por detrás. Se actualiza la tabla y se
                # avisa el error; return evita avisar también "Se quitaron…" (BUG-10).
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.error_inesperado(error)
                return
            self.app.refrescar()
            self.app.avisar(f"Se quitaron los pagos de {f['nombre']}")

        self.app.page.update()
        self.app.confirmar(
            f"¿Quitar los pagos de {f['nombre']}?",
            f"{cantidad} ({formatear_ars(pagado)}). El gasto vuelve a "
            f"quedar pendiente por {formatear_ars(f['monto_cent'])}.",
            "Quitar pagos",
            confirmado,
        )

    def registrar_pago(self, gasto_id: int) -> None:
        if self._gasto_que_ya_no_existe(gasto_id):
            return
        if pagos.pendiente(self.app.con, gasto_id) == 0:
            self.app.avisar("Este gasto ya está pagado.")
            return

        def al_guardar(monto: int, quedo_pagado: bool):
            self.app.refrescar()
            nombre = gastos.obtener_gasto(self.app.con, gasto_id)["nombre"]
            aviso = f"Pago de {formatear_ars(monto)} registrado"
            if quedo_pagado:
                aviso += f": {nombre} quedó pagado"
            self.app.avisar(aviso)

        DialogoPago(self.app, gasto_id, al_guardar).abrir()

    def ver_pagos(self, gasto_id: int) -> None:
        if self._gasto_que_ya_no_existe(gasto_id):
            return
        DialogoVerPagos(
            self.app, gasto_id, al_registrar_otro=lambda: self.registrar_pago(gasto_id)
        ).abrir()
