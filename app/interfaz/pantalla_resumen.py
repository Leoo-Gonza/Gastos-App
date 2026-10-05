"""Resumen del mes: la pantalla principal (RF-23 a RF-27, RF-35 a RF-37, docs/diseno.md §3.2).

Solo muestra: todas las cuentas las hace app/logica/resumen.py. La tarjeta
"Te deben" llega en el paso 5.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import texto_ayuda, titulo
from app.interfaz.dialogos import dialogos_valores
from app.interfaz.dialogos.dialogo_cambio import DialogoCambio
from app.interfaz.dialogos.dialogo_ingreso import DialogoIngreso
from app.logica import cambios, gastos, ingresos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    convertir_usd_a_ars,
    formatear_ars,
    formatear_cotizacion,
    formatear_cotizacion_corta,
    formatear_fecha,
    formatear_porcentaje,
    formatear_usd,
    nombre_mes,
)
from app.logica.resumen import Resumen, calcular_resumen

_TAM_MONTO = 30


class PantallaResumen:
    def __init__(self, app) -> None:
        self.app = app
        self.titulo = titulo("")
        self.cuerpo = ft.Column(spacing=16)
        self.control = ft.Column(
            [self.titulo, self.cuerpo],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    # ------------------------------------------------------------------
    # Dibujo
    # ------------------------------------------------------------------

    def refrescar(self) -> None:
        mes = meses.obtener_mes(self.app.con, self.app.mes_id)
        self.titulo.value = f"Resumen de {nombre_mes(mes['anio'], mes['mes'])}"
        r = calcular_resumen(self.app.con, self.app.mes_id)
        cantidad = len(gastos.listar_gastos(self.app.con, self.app.mes_id))

        controles: list[ft.Control] = []
        if r.sueldo_usd == 0:
            controles.append(
                self._aviso("El sueldo de este mes es 0.", ft.Icons.WARNING_AMBER)
            )
        controles += [
            self._seccion("EN PESOS"),
            ft.ResponsiveRow(
                [
                    self._tarjeta(
                        "Total gastos",
                        self._monto(formatear_ars(r.total_gastos)),
                        [
                            texto_ayuda(
                                "1 gasto" if cantidad == 1 else f"{cantidad} gastos"
                            )
                        ],
                    ),
                    self._tarjeta(
                        "Falta pagar",
                        self._monto(
                            formatear_ars(r.pendiente_de_pago),
                            "pendiente" if r.pendiente_de_pago else "positivo",
                        ),
                        [
                            texto_ayuda(
                                f"Pagado {formatear_ars(r.total_gastos - r.pendiente_de_pago)}"
                            )
                        ],
                    ),
                    self._tarjeta_pesos_a_cubrir(r),
                ]
            ),
            self._seccion("EN DÓLARES"),
            ft.ResponsiveRow(
                [
                    self._tarjeta_sueldo(r),
                    self._tarjeta_usd_a_cambiar(r),
                    self._tarjeta_ahorro(r),
                ]
            ),
            ft.ResponsiveRow([self._tarjeta_capacidad(r)]),
            self._como_se_calcula(r),
            self._tabla_ingresos(),
            self._tabla_cambios(),
        ]
        self.cuerpo.controls = controles

    def _aviso(self, texto: str, icono: ft.IconData) -> ft.Container:
        """Aviso en pantalla (§2.5): fondo suave del color "pendiente", ícono y texto."""
        color = estilos.color(self.app.page, "pendiente")
        return ft.Container(
            padding=12,
            border_radius=8,
            bgcolor=estilos.color(self.app.page, "pendiente_suave"),
            content=ft.Row([ft.Icon(icono, color=color), ft.Text(texto, color=color)]),
        )

    def _seccion(self, texto: str) -> ft.Text:
        return ft.Text(
            texto,
            size=estilos.TAM_AYUDA,
            weight=ft.FontWeight.W_600,
            color=estilos.TEXTO_SECUNDARIO,
        )

    def _monto(self, texto: str, rol: str | None = None) -> ft.Text:
        color = estilos.color(self.app.page, rol) if rol else None
        return ft.Text(texto, size=_TAM_MONTO, weight=ft.FontWeight.W_700, color=color)

    def _tarjeta(
        self,
        etiqueta: str,
        principal: ft.Control,
        abajo: list[ft.Control],
        accion: ft.Control | None = None,
        borde_rol: str | None = None,
        md: int = 4,
    ) -> ft.Card:
        """Tarjeta del resumen: etiqueta, monto grande y detalle debajo (§3.2).

        col={"sm": 12, "md": 4}: en ventana angosta ocupa todo el ancho; si no, un tercio.
        """
        encabezado = [
            ft.Text(
                etiqueta,
                size=estilos.TAM_AYUDA,
                color=estilos.TEXTO_SECUNDARIO,
                expand=True,
            )
        ]
        if accion:
            encabezado.append(accion)
        borde = None
        if borde_rol:
            borde = ft.Border.all(2, estilos.color(self.app.page, borde_rol))
        return ft.Card(
            col={"sm": 12, "md": md},
            content=ft.Container(
                padding=16,
                border=borde,
                border_radius=12,
                content=ft.Column([ft.Row(encabezado), principal, *abajo], spacing=4),
            ),
        )

    def _falta_cotizacion(self) -> list[ft.Control]:
        """Lo que se muestra en lugar de un monto cuando no hay cotización (RN-18)."""
        return [
            ft.Text(
                "Cargá la cotización",
                size=estilos.TAM_SECCION,
                color=estilos.color(self.app.page, "pendiente"),
            ),
            ft.TextButton(
                "Cargar cotización", on_click=lambda e: self.editar_cotizacion()
            ),
        ]

    def _tarjeta_pesos_a_cubrir(self, r: Resumen) -> ft.Card:
        abajo = [texto_ayuda("Gastos − extras en pesos − pesos de cambios")]
        if r.pesos_sobrantes:
            sobrante = f"Pesos sobrantes {formatear_ars(r.pesos_sobrantes)}"
            if r.sobrantes_usd is not None:
                sobrante += f" = {formatear_usd(r.sobrantes_usd)} (se suman al ahorro)"
            abajo = [
                ft.Text(
                    sobrante,
                    size=estilos.TAM_AYUDA,
                    color=estilos.color(self.app.page, "positivo"),
                )
            ]
        return self._tarjeta(
            "Pesos a cubrir", self._monto(formatear_ars(r.pesos_a_cubrir)), abajo
        )

    def _tarjeta_sueldo(self, r: Resumen) -> ft.Card:
        principal = self._monto(formatear_usd(r.sueldo_usd))
        if r.sueldo_usd == 0:
            principal = ft.Row(
                [
                    ft.Icon(
                        ft.Icons.WARNING_AMBER,
                        color=estilos.color(self.app.page, "pendiente"),
                    ),
                    principal,
                ]
            )
        return self._tarjeta(
            "Sueldo",
            principal,
            [],
            accion=ft.IconButton(
                ft.Icons.EDIT_OUTLINED,
                tooltip="Editar sueldo",
                on_click=lambda e: self.editar_sueldo(),
            ),
        )

    def _tarjeta_usd_a_cambiar(self, r: Resumen) -> ft.Card:
        if r.usd_a_cambiar is None:
            return self._tarjeta(
                "Dólares a cambiar",
                self._falta_cotizacion()[0],
                self._falta_cotizacion()[1:],
            )
        abajo = []
        if r.cotizacion is not None and r.pesos_a_cubrir:
            abajo = [
                texto_ayuda(
                    f"{formatear_ars(r.pesos_a_cubrir)} ÷ "
                    f"{formatear_cotizacion_corta(r.cotizacion)}"
                )
            ]
        return self._tarjeta(
            "Dólares a cambiar", self._monto(formatear_usd(r.usd_a_cambiar)), abajo
        )

    def _tarjeta_ahorro(self, r: Resumen) -> ft.Card:
        if r.ahorro_usd is None:
            return self._tarjeta(
                "Ahorro del mes",
                self._falta_cotizacion()[0],
                self._falta_cotizacion()[1:],
            )
        deficit = r.ahorro_usd < 0
        rol = "negativo" if deficit else "positivo"
        principal = self._monto(formatear_usd(r.ahorro_usd), rol)
        if deficit:
            # El color nunca es la única señal: ícono y la palabra "Déficit".
            principal = ft.Row(
                [
                    ft.Icon(
                        ft.Icons.TRENDING_DOWN,
                        color=estilos.color(self.app.page, "negativo"),
                    ),
                    principal,
                ]
            )
        return self._tarjeta(
            "Déficit" if deficit else "Ahorro del mes", principal, [self._meta(r)]
        )

    def _meta(self, r: Resumen) -> ft.Control:
        """Barra de avance de la meta (RN-39), o el botón para definirla."""
        if r.meta_usd is None:
            return ft.TextButton(
                "Definir meta de ahorro", on_click=lambda e: self.editar_meta()
            )
        avance = r.avance_meta if r.avance_meta is not None else 0.0
        # La barra va de 0 a 1 (0 % a 100 %); el texto muestra el valor real.
        barra = max(0.0, min(avance, 1.0))
        alcanzada = avance >= 1
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.TextButton(
                            f"Meta {formatear_usd(r.meta_usd)}",
                            on_click=lambda e: self.editar_meta(),
                        ),
                        ft.Text(
                            # El número muestra el valor real, aunque sea negativo
                            # o pase el 100 % (RN-39); solo la barra se limita.
                            formatear_porcentaje(avance),
                            tooltip=formatear_porcentaje(avance, decimales=2),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.ProgressBar(
                    value=barra,
                    bar_height=10,
                    border_radius=5,
                    color=estilos.color(self.app.page, "positivo")
                    if alcanzada
                    else None,
                ),
            ],
            spacing=2,
        )

    def _tarjeta_capacidad(self, r: Resumen) -> ft.Card:
        if r.capacidad is None:
            return self._tarjeta(
                "Capacidad de endeudamiento",
                self._falta_cotizacion()[0],
                self._falta_cotizacion()[1:],
                md=6,
            )
        negativa = r.capacidad < 0
        principal = self._monto(
            f"{formatear_ars(r.capacidad)} por mes", "negativo" if negativa else None
        )
        abajo: list[ft.Control] = []
        if negativa:
            abajo.append(
                ft.Row(
                    [
                        ft.Icon(
                            ft.Icons.ERROR_OUTLINE,
                            color=estilos.color(self.app.page, "negativo"),
                            size=18,
                        ),
                        ft.Text(
                            "Sin capacidad de endeudamiento",
                            color=estilos.color(self.app.page, "negativo"),
                        ),
                    ]
                )
            )
        k = r.cotizacion
        meta = r.meta_usd or 0
        lineas = [
            self._linea(
                f"Sueldo en pesos ({formatear_usd(r.sueldo_usd)} × "
                f"{formatear_cotizacion_corta(k)})",
                formatear_ars(convertir_usd_a_ars(r.sueldo_usd, k)),
            ),
            self._linea(
                "− Gastos fijos y cuotas del mes",
                formatear_ars(r.gastos_fijos_y_cuotas),
            ),
            self._linea(
                f"− Meta de ahorro ({formatear_usd(meta)} × "
                f"{formatear_cotizacion_corta(k)})",
                formatear_ars(convertir_usd_a_ars(meta, k)),
            ),
            self._linea(
                "= Capacidad de endeudamiento", formatear_ars(r.capacidad), negrita=True
            ),
            texto_ayuda("Los pagos únicos y los ingresos extra no se cuentan."),
        ]
        abajo.append(ft.ExpansionTile(title=ft.Text("Ver cálculo"), controls=lineas))
        return self._tarjeta(
            "Capacidad de endeudamiento",
            principal,
            abajo,
            borde_rol="negativo" if negativa else None,
            md=6,
        )

    def _linea(self, etiqueta: str, valor: str, negrita: bool = False) -> ft.Row:
        peso = ft.FontWeight.W_700 if negrita else None
        return ft.Row(
            [ft.Text(etiqueta, expand=True, weight=peso), ft.Text(valor, weight=peso)],
        )

    def _como_se_calcula(self, r: Resumen) -> ft.ExpansionTile:
        """Desglose de RN-14 a RN-17, como se veía la cuenta en la planilla."""
        lineas = [
            self._linea("Total gastos", formatear_ars(r.total_gastos)),
            self._linea("− Ingresos extra en pesos", formatear_ars(r.extras_ars)),
            self._linea("− Pesos de cambios realizados", formatear_ars(r.cambiado_ars)),
            self._linea(
                "= Pesos a cubrir", formatear_ars(r.pesos_a_cubrir), negrita=True
            ),
        ]
        if r.pesos_sobrantes:
            lineas.append(
                self._linea("Pesos sobrantes", formatear_ars(r.pesos_sobrantes))
            )
        if r.cotizacion is None:
            lineas.append(
                texto_ayuda("Sin cotización no se pueden calcular los dólares.")
            )
        else:
            lineas.append(
                self._linea("÷ Cotización", formatear_cotizacion(r.cotizacion))
            )
        if r.usd_a_cambiar is not None:
            lineas.append(
                self._linea(
                    "= Dólares a cambiar", formatear_usd(r.usd_a_cambiar), negrita=True
                )
            )
        lineas += [
            ft.Divider(),
            self._linea("Sueldo", formatear_usd(r.sueldo_usd)),
            self._linea("+ Ingresos extra en dólares", formatear_usd(r.extras_usd)),
            self._linea("− Dólares ya cambiados", formatear_usd(r.cambiado_usd)),
        ]
        if r.ahorro_usd is not None:
            lineas += [
                self._linea("− Dólares a cambiar", formatear_usd(r.usd_a_cambiar)),
                self._linea(
                    "+ Pesos sobrantes en dólares", formatear_usd(r.sobrantes_usd)
                ),
                self._linea(
                    "= Ahorro del mes", formatear_usd(r.ahorro_usd), negrita=True
                ),
            ]
        return ft.ExpansionTile(
            title=ft.Text("Cómo se calcula el ahorro"), controls=lineas
        )

    # ------------------------------------------------------------------
    # Tablas de ingresos extra y cambios
    # ------------------------------------------------------------------

    def _encabezado_tabla(self, texto: str, boton: str, accion) -> ft.Row:
        return ft.Row(
            [
                self._seccion(texto),
                ft.OutlinedButton(
                    boton, icon=ft.Icons.ADD, on_click=lambda e: accion()
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _menu(self, editar, borrar) -> ft.PopupMenuButton:
        return ft.PopupMenuButton(
            icon=ft.Icons.MORE_VERT,
            tooltip="Acciones",
            items=[
                ft.PopupMenuItem(
                    content="Editar",
                    icon=ft.Icons.EDIT_OUTLINED,
                    on_click=lambda e: editar(),
                ),
                ft.PopupMenuItem(
                    content="Borrar",
                    icon=ft.Icons.DELETE_OUTLINE,
                    on_click=lambda e: borrar(),
                ),
            ],
        )

    def _tabla_ingresos(self) -> ft.Column:
        filas = ingresos.listar_ingresos(self.app.con, self.app.mes_id)
        if not filas:
            contenido: ft.Control = texto_ayuda("Sin ingresos extra este mes.")
        else:
            contenido = ft.DataTable(
                heading_row_color=estilos.SUPERFICIE_VARIANTE,
                columns=[
                    ft.DataColumn(ft.Text("Descripción")),
                    ft.DataColumn(ft.Text("Moneda")),
                    ft.DataColumn(ft.Text("Monto"), numeric=True),
                    ft.DataColumn(ft.Text("")),
                ],
                rows=[
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(i["descripcion"])),
                            ft.DataCell(ft.Text(i["moneda"])),
                            ft.DataCell(
                                ft.Text(
                                    formatear_ars(i["monto_cent"])
                                    if i["moneda"] == "ARS"
                                    else formatear_usd(i["monto_cent"])
                                )
                            ),
                            # i=i: cada menú usa su propio ingreso (no el último del for).
                            ft.DataCell(
                                self._menu(
                                    lambda i=i: self._editar_ingreso(i),
                                    lambda i=i: self._borrar_ingreso(i),
                                )
                            ),
                        ]
                    )
                    for i in filas
                ],
            )
        return ft.Column(
            [
                self._encabezado_tabla(
                    "INGRESOS EXTRA", "Agregar ingreso", self.nuevo_ingreso
                ),
                contenido,
            ]
        )

    def _tabla_cambios(self) -> ft.Column:
        filas = cambios.listar_cambios(self.app.con, self.app.mes_id)
        if not filas:
            contenido: ft.Control = texto_ayuda(
                "Todavía no registraste cambios este mes."
            )
        else:
            totales = cambios.totales(self.app.con, self.app.mes_id)
            negrita = ft.FontWeight.W_700
            contenido = ft.DataTable(
                heading_row_color=estilos.SUPERFICIE_VARIANTE,
                columns=[
                    ft.DataColumn(ft.Text("Fecha")),
                    ft.DataColumn(ft.Text("Dólares cambiados"), numeric=True),
                    ft.DataColumn(ft.Text("Cotización"), numeric=True),
                    ft.DataColumn(ft.Text("Pesos recibidos"), numeric=True),
                    ft.DataColumn(ft.Text("")),
                    ft.DataColumn(ft.Text("")),
                ],
                rows=[self._fila_cambio(c) for c in filas]
                + [
                    ft.DataRow(
                        color=estilos.SUPERFICIE_VARIANTE,
                        cells=[
                            ft.DataCell(ft.Text("Total", weight=negrita)),
                            ft.DataCell(
                                ft.Text(formatear_usd(totales["usd"]), weight=negrita)
                            ),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(
                                ft.Text(formatear_ars(totales["ars"]), weight=negrita)
                            ),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("")),
                        ],
                    )
                ],
            )
        return ft.Column(
            [
                self._encabezado_tabla(
                    "CAMBIOS DE DÓLARES REALIZADOS",
                    "Registrar cambio",
                    self.nuevo_cambio,
                ),
                contenido,
            ]
        )

    def _fila_cambio(self, c) -> ft.DataRow:
        corregido = c["ars_cent"] != cambios.ars_sugeridos(
            c["usd_cent"], c["cotizacion_cent"]
        )
        return ft.DataRow(
            cells=[
                ft.DataCell(ft.Text(formatear_fecha(c["fecha"]))),
                ft.DataCell(ft.Text(formatear_usd(c["usd_cent"]))),
                ft.DataCell(ft.Text(formatear_cotizacion_corta(c["cotizacion_cent"]))),
                ft.DataCell(ft.Text(formatear_ars(c["ars_cent"]))),
                ft.DataCell(
                    texto_ayuda("corregido a mano") if corregido else ft.Text("")
                ),
                ft.DataCell(
                    self._menu(
                        lambda: self._editar_cambio(c),
                        lambda: self._borrar_cambio(c),
                    )
                ),
            ]
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def nuevo(self) -> None:
        """Atajo Ctrl+N en el Resumen: registrar un cambio de dólares (§1.3)."""
        self.nuevo_cambio()

    def nuevo_cambio(self) -> None:
        if not self.app.verificar_mes():
            return
        DialogoCambio(self.app, self.app.mes_id).abrir()

    def nuevo_ingreso(self) -> None:
        if not self.app.verificar_mes():
            return
        DialogoIngreso(self.app, self.app.mes_id).abrir()

    def editar_sueldo(self) -> None:
        if not self.app.verificar_mes():
            return
        dialogos_valores.abrir_sueldo(self.app, self.app.mes_id)

    def editar_cotizacion(self) -> None:
        self.app.editar_cotizacion()  # Ya verifica que el mes exista.

    def editar_meta(self) -> None:
        dialogos_valores.abrir_meta(self.app)

    # Todas las acciones de las tablas verifican antes que el mes exista
    # (BUG-18): si se borró, la app pasa al último mes y avisa.

    def _editar_ingreso(self, ingreso) -> None:
        if self.app.verificar_mes():
            DialogoIngreso(self.app, self.app.mes_id, ingreso["id"]).abrir()

    def _editar_cambio(self, cambio) -> None:
        if self.app.verificar_mes():
            DialogoCambio(self.app, self.app.mes_id, cambio["id"]).abrir()

    def _borrar_ingreso(self, ingreso) -> None:
        if not self.app.verificar_mes():
            return

        def confirmado():
            try:
                ingresos.borrar_ingreso(self.app.con, ingreso["id"])
            except ErrorDeValidacion as error:  # Ej.: se borró por detrás.
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.error_inesperado(error)
                return
            self.app.refrescar()
            self.app.avisar(f'Ingreso "{ingreso["descripcion"]}" borrado')

        self.app.confirmar(
            f"¿Borrar el ingreso {ingreso['descripcion']}?",
            "Esta acción no se puede deshacer.",
            "Borrar",
            confirmado,
        )

    def _borrar_cambio(self, cambio) -> None:
        if not self.app.verificar_mes():
            return

        def confirmado():
            try:
                cambios.borrar_cambio(self.app.con, cambio["id"])
            except ErrorDeValidacion as error:  # Ej.: se borró por detrás.
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.error_inesperado(error)
                return
            self.app.refrescar()
            self.app.avisar("Cambio borrado")

        self.app.confirmar(
            f"¿Borrar el cambio del {formatear_fecha(cambio['fecha'])}?",
            f"{formatear_usd(cambio['usd_cent'])} por {formatear_ars(cambio['ars_cent'])}. "
            "Esta acción no se puede deshacer.",
            "Borrar",
            confirmado,
        )
