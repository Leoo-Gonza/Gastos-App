"""Me deben: lo que te debe cada persona, de todos los meses (RF-32 a RF-34, docs/diseno.md §3.5).

Equivale a las tablas "Deudas sofia" y "Marsu" de la planilla. No depende del
mes seleccionado: es acumulado (RN-35).
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import estado_vacio, texto_ayuda, titulo
from app.interfaz.dialogos.dialogo_item import DialogoItem
from app.logica import compartidos, me_deben
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, formatear_fecha, formatear_mes_corto


class PantallaMeDeben:
    def __init__(self, app) -> None:
        self.app = app
        self.total = ft.Text(size=estilos.TAM_TITULO, weight=ft.FontWeight.W_700)
        self.mostrar_cobrados = ft.Switch(
            label="Mostrar cobrados", value=False, on_change=lambda e: self._redibujar()
        )
        self.cuerpo = ft.Column(spacing=16)
        self.control = ft.Column(
            [
                ft.Row(
                    [
                        titulo("Me deben"),
                        ft.Row(
                            [self.total, self.mostrar_cobrados], spacing=24, tight=True
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                texto_ayuda("Acumulado de todos los meses."),
                self.cuerpo,
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def refrescar(self) -> None:
        con = self.app.con
        personas = me_deben.personas_para_mostrar(con)
        total = me_deben.total_general(con)
        self.total.value = f"Total: {formatear_ars(total)}"
        if not personas:
            self.cuerpo.controls = [
                estado_vacio(
                    ft.Icons.PEOPLE_OUTLINE,
                    "Agregá a las personas con las que compartís gastos.",
                    "Ir a Personas",
                    lambda e: self._ir_a_personas(),
                )
            ]
            return
        self.cuerpo.controls = [
            ft.ResponsiveRow([self._tarjeta(p) for p in personas], run_spacing=16)
        ]

    def _redibujar(self) -> None:
        self.refrescar()
        self.app.page.update()

    def _ir_a_personas(self) -> None:
        if not self.app.verificar_mes():
            return
        self.app.seleccionar_mes(self.app.mes_id, pantalla="Ajustes")
        ajustes = self.app.pantalla("Ajustes")
        ajustes.pestanas.selected_index = 2  # Categorías, Medios de pago, Personas.
        ajustes.refrescar()
        self.app.page.update()

    # ------------------------------------------------------------------
    # Tarjeta de cada persona
    # ------------------------------------------------------------------

    def _tarjeta(self, persona) -> ft.Card:
        con = self.app.con
        lineas = me_deben.lineas_de(con, persona["id"], self.mostrar_cobrados.value)
        total = me_deben.total_de(con, persona["id"])
        encabezado = [
            ft.CircleAvatar(content=ft.Text(persona["nombre"][:1].upper())),
            ft.Column(
                [
                    ft.Text(
                        persona["nombre"],
                        weight=ft.FontWeight.W_600,
                        size=estilos.TAM_SECCION,
                    ),
                    *([texto_ayuda("Archivada")] if persona["archivado"] else []),
                ],
                spacing=0,
                expand=True,
            ),
            ft.Column(
                [
                    ft.Text(
                        formatear_ars(total),
                        weight=ft.FontWeight.W_700,
                        size=estilos.TAM_SECCION,
                        color=estilos.color(self.app.page, "negativo")
                        if total < 0
                        else None,
                    ),
                    *(
                        [
                            ft.Text(
                                "Le tenés que devolver",
                                size=estilos.TAM_AYUDA,
                                color=estilos.color(self.app.page, "negativo"),
                            )
                        ]
                        if total < 0
                        else []
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.END,
                spacing=0,
            ),
        ]
        contenido: list[ft.Control] = [
            ft.Row(encabezado),
            ft.Row(
                [
                    ft.TextButton(
                        "Agregar ítem",
                        icon=ft.Icons.ADD,
                        on_click=lambda e: self.nuevo_item(persona["id"]),
                    )
                ],
                alignment=ft.MainAxisAlignment.END,
            ),
            ft.Divider(),
        ]
        if not lineas:
            positivo = estilos.color(self.app.page, "positivo")
            contenido.append(
                ft.Row(
                    [
                        ft.Icon(ft.Icons.CHECK_CIRCLE, color=positivo),
                        ft.Text(
                            f"{persona['nombre']} no te debe nada.", color=positivo
                        ),
                    ]
                )
            )
        else:
            contenido += [self._linea(linea) for linea in lineas]
        return ft.Card(
            col={"md": 6, "xl": 4},
            content=ft.Container(padding=16, content=ft.Column(contenido, spacing=4)),
        )

    def _linea(self, linea) -> ft.ListTile:
        if linea.tipo == "parte":
            origen = f"Gasto de {formatear_mes_corto(linea.anio, linea.mes)}"
        else:
            origen = f"A mano · {formatear_fecha(linea.fecha)}"
        subtitulo = [
            ft.Text(origen, size=estilos.TAM_AYUDA, color=estilos.TEXTO_SECUNDARIO)
        ]
        # RN-34: una parte que cambió después de cobrarla muestra la diferencia.
        if linea.tipo == "parte" and not linea.cobrado and linea.cobrado_cent:
            diferencia = linea.monto - linea.cobrado_cent
            if diferencia >= 0:
                texto = f"Cobrado {formatear_ars(linea.cobrado_cent)} · falta {formatear_ars(diferencia)}"
                rol = "pendiente"
            else:
                texto = (
                    f"Cobrado {formatear_ars(linea.cobrado_cent)} · "
                    f"a devolver {formatear_ars(-diferencia)}"
                )
                rol = "negativo"
            subtitulo.append(
                ft.Text(
                    texto,
                    size=estilos.TAM_AYUDA,
                    color=estilos.color(self.app.page, rol),
                )
            )
        if linea.cobrado:
            subtitulo.append(
                ft.Text(
                    "Cobrado",
                    size=estilos.TAM_AYUDA,
                    color=estilos.color(self.app.page, "positivo"),
                )
            )

        derecha: list[ft.Control] = [ft.Text(formatear_ars(linea.monto))]
        if linea.tipo == "item":
            # Solo los ítems a mano se editan acá; las partes, desde el gasto.
            derecha.append(
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    tooltip="Acciones",
                    items=[
                        ft.PopupMenuItem(
                            content="Editar",
                            icon=ft.Icons.EDIT_OUTLINED,
                            on_click=lambda e: self.editar_item(linea.id),
                        ),
                        ft.PopupMenuItem(
                            content="Borrar",
                            icon=ft.Icons.DELETE_OUTLINE,
                            on_click=lambda e: self.borrar_item(linea),
                        ),
                    ],
                )
            )
        return ft.ListTile(
            leading=ft.Checkbox(
                value=linea.cobrado,
                tooltip="Marcar como cobrado",
                on_change=lambda e: self._cambiar_cobrado(linea, e.control.value),
            ),
            title=ft.Text(
                linea.descripcion,
                color=estilos.TEXTO_SECUNDARIO if linea.cobrado else None,
            ),
            subtitle=ft.Column(subtitulo, spacing=0, tight=True),
            trailing=ft.Row(derecha, tight=True),
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def _cambiar_cobrado(self, linea, cobrado: bool) -> None:
        """RF-34: tildar o destildar. "Deshacer" vuelve exactamente a como estaba (O41)."""
        con = self.app.con
        try:
            if linea.tipo == "parte":
                previo = compartidos.marcar_cobrada(con, linea.id, cobrado)

                def deshacer():
                    try:
                        compartidos.restaurar_cobro(con, linea.id, *previo)
                    except ErrorDeValidacion:
                        pass  # Ya no existe: no hay nada que deshacer.
                    self.app.refrescar()
            else:
                me_deben.marcar_item_cobrado(con, linea.id, cobrado)

                def deshacer():
                    try:
                        me_deben.marcar_item_cobrado(con, linea.id, not cobrado)
                    except ErrorDeValidacion:
                        pass
                    self.app.refrescar()
        except ErrorDeValidacion as error:
            self.app.refrescar()
            self.app.avisar(str(error))
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.error_inesperado(error)
            return
        self.app.refrescar()
        texto = "Marcado como cobrado" if cobrado else "Marcado como pendiente"
        self.app.avisar(texto, al_deshacer=deshacer)

    def nuevo(self) -> None:
        """Ctrl+N en esta pantalla: un ítem nuevo; la persona se elige en el diálogo."""
        DialogoItem(self.app).abrir()

    def nuevo_item(self, persona_id: int) -> None:
        DialogoItem(self.app, persona_id=persona_id).abrir()

    def editar_item(self, item_id: int) -> None:
        if me_deben.obtener_item(self.app.con, item_id) is None:
            self.app.refrescar()
            self.app.avisar("Ese ítem ya no existe.")
            return
        DialogoItem(self.app, item_id=item_id).abrir()

    def borrar_item(self, linea) -> None:
        def confirmado():
            try:
                me_deben.borrar_item(self.app.con, linea.id)
            except ErrorDeValidacion as error:
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.error_inesperado(error)
                return
            self.app.refrescar()
            self.app.avisar(f'Ítem "{linea.descripcion}" borrado')

        self.app.confirmar(
            f"¿Borrar el ítem {linea.descripcion}?",
            f"{formatear_ars(linea.monto)}. Esta acción no se puede deshacer.",
            "Borrar",
            confirmado,
        )
