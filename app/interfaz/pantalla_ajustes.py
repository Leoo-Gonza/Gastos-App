"""Ajustes: categorías y medios de pago (RF-10, RF-11, docs/diseno.md §3.10).

Personas, meta de ahorro y apariencia se agregan en pasos siguientes.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import dialogo_formulario, titulo
from app.logica import catalogos
from app.logica.errores import ErrorDeValidacion

# Textos de cada lista. Cambian el género ("archivada"/"archivado") y el nombre.
_TEXTOS = {
    catalogos.CATEGORIAS: {
        "singular": "categoría",
        "nuevo": "Nueva categoría",
        "archivado": "Archivada",
        "mostrar": "Mostrar archivadas",
        "tooltip_archivar": "Se usa en gastos: no se puede borrar. "
        "Archivada no aparece al cargar datos nuevos.",
        "eliminar": "¿Eliminar la categoría {}?",
        "vacio": "No hay categorías.",
    },
    catalogos.MEDIOS_PAGO: {
        "singular": "medio de pago",
        "nuevo": "Nuevo medio de pago",
        "archivado": "Archivado",
        "mostrar": "Mostrar archivados",
        "tooltip_archivar": "Se usa en gastos: no se puede borrar. "
        "Archivado no aparece al cargar datos nuevos.",
        "eliminar": "¿Eliminar el medio de pago {}?",
        "vacio": "No hay medios de pago.",
    },
}


class ListaCatalogo:
    """Una pestaña de Ajustes. Es la misma para categorías, medios y (más
    adelante) personas: solo cambian la tabla y los textos (§3.10)."""

    def __init__(self, app, tabla: str) -> None:
        self.app = app
        self.tabla = tabla
        self.textos = _TEXTOS[tabla]
        self.mostrar_archivados = ft.Switch(
            label=self.textos["mostrar"],
            value=False,
            on_change=lambda e: self.refrescar(),
        )
        self.lista = ft.Column(spacing=0)
        self.control = ft.Column(
            [
                ft.Row(
                    [
                        self.mostrar_archivados,
                        ft.FilledButton(
                            self.textos["nuevo"],
                            icon=ft.Icons.ADD,
                            tooltip=f"{self.textos['nuevo']} ({app.atajo('N')})",
                            on_click=lambda e: self.nuevo(),
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.END,
                    spacing=24,
                ),
                self.lista,
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def refrescar(self) -> None:
        filas = catalogos.listar(
            self.app.con, self.tabla, incluir_archivados=self.mostrar_archivados.value
        )
        if not filas:
            self.lista.controls = [
                ft.Text(self.textos["vacio"], color=estilos.TEXTO_SECUNDARIO)
            ]
        else:
            self.lista.controls = [self._fila(f) for f in filas]
        self.app.page.update()

    def _fila(self, fila) -> ft.ListTile:
        archivado = bool(fila["archivado"])
        botones = [
            ft.TextButton(
                "Renombrar",
                on_click=lambda e: self.renombrar(fila["id"], fila["nombre"]),
            )
        ]
        if archivado:
            botones.append(
                ft.TextButton("Desarchivar", on_click=lambda e: self.desarchivar(fila))
            )
        elif catalogos.esta_en_uso(self.app.con, self.tabla, fila["id"]):
            # Se dice "Archivar" y no "Eliminar" para que se sepa antes de hacer
            # clic que no se va a borrar (RN-49).
            botones.append(
                ft.TextButton(
                    "Archivar",
                    tooltip=self.textos["tooltip_archivar"],
                    on_click=lambda e: self.eliminar(fila),
                )
            )
        else:
            botones.append(
                ft.TextButton("Eliminar", on_click=lambda e: self.eliminar(fila))
            )

        return ft.ListTile(
            title=ft.Text(
                fila["nombre"], color=estilos.TEXTO_SECUNDARIO if archivado else None
            ),
            subtitle=ft.Text(self.textos["archivado"], size=estilos.TAM_AYUDA)
            if archivado
            else None,
            trailing=ft.Row(botones, tight=True),
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def nuevo(self) -> None:
        self._dialogo_nombre(
            self.textos["nuevo"],
            "",
            lambda nombre: catalogos.crear(self.app.con, self.tabla, nombre),
            "Agregado",
        )

    def renombrar(self, id_: int, nombre_actual: str) -> None:
        self._dialogo_nombre(
            f"Renombrar {self.textos['singular']}",
            nombre_actual,
            lambda nombre: catalogos.renombrar(self.app.con, self.tabla, id_, nombre),
            "Renombrado",
        )

    def _dialogo_nombre(
        self, titulo_dialogo: str, valor: str, guardar, aviso: str
    ) -> None:
        """Diálogo de un solo campo "Nombre", para crear y para renombrar (§4.7)."""
        campo = ft.TextField(label="Nombre", value=valor, autofocus=True, max_length=60)

        def al_guardar(e=None):
            campo.error = None
            try:
                guardar(campo.value or "")
            except ErrorDeValidacion as error:
                campo.error = str(error)
                self.app.page.update()
                self.app.enfocar(campo)
                return
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                self.app.cerrar_dialogo(dialogo)
                self.app.error_inesperado(error)
                return
            self.app.cerrar_dialogo(dialogo)
            self.refrescar()
            self.app.avisar(f'{aviso}: "{" ".join(campo.value.split())}"')

        campo.on_submit = al_guardar
        dialogo = dialogo_formulario(
            titulo_dialogo,
            [campo],
            al_guardar=al_guardar,
            al_cancelar=lambda e: self.app.cerrar_dialogo(dialogo),
        )
        self.app.abrir_dialogo(dialogo)

    def eliminar(self, fila) -> None:
        """Si está en uso se archiva sin preguntar (es reversible); si no, se
        pide confirmación porque se borra de verdad."""
        nombre = fila["nombre"]

        def eliminar_y_avisar():
            ok, resultado = self._ejecutar(
                lambda: catalogos.eliminar(self.app.con, self.tabla, fila["id"])
            )
            if not ok:
                return  # _ejecutar ya mostró el error: no se avisa "eliminado".
            # La lógica decide si se borró o se archivó (puede haber cambiado
            # desde que se dibujó la lista), así que el aviso usa su respuesta.
            if resultado == "archivado":
                self.app.avisar(
                    f'"{nombre}" archivado',
                    al_deshacer=lambda: self.desarchivar(fila, avisar=False),
                )
            else:
                self.app.avisar(f'"{nombre}" eliminado')

        if catalogos.esta_en_uso(self.app.con, self.tabla, fila["id"]):
            eliminar_y_avisar()
            return

        def confirmado():
            eliminar_y_avisar()

        self.app.confirmar(
            self.textos["eliminar"].format(nombre),
            "No se usa en ningún gasto. Esta acción no se puede deshacer.",
            "Eliminar",
            confirmado,
        )

    def desarchivar(self, fila, avisar: bool = True) -> None:
        ok, _ = self._ejecutar(
            lambda: catalogos.desarchivar(self.app.con, self.tabla, fila["id"])
        )
        if ok and avisar:
            self.app.avisar(f'"{fila["nombre"]}" vuelve a aparecer al cargar datos')

    def _ejecutar(self, accion) -> tuple[bool, object]:
        """Ejecuta la acción, muestra el error si falla y refresca la lista.

        Devuelve (salió_bien, lo_que_devolvió_la_acción), así quien la llama
        sabe si tiene que avisar el éxito.
        """
        ok, resultado = False, None
        try:
            resultado = accion()
            ok = True
        except ErrorDeValidacion as error:
            self.app.avisar(str(error))
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.error_inesperado(error)
        self.refrescar()
        return ok, resultado


class PantallaAjustes:
    def __init__(self, app) -> None:
        self.app = app
        self.listas = [
            ListaCatalogo(app, catalogos.CATEGORIAS),
            ListaCatalogo(app, catalogos.MEDIOS_PAGO),
        ]
        # En Flet 1.0 las pestañas son tres piezas: Tabs (el conjunto),
        # TabBar (los títulos) y TabBarView (el contenido de cada una).
        self.pestanas = ft.Tabs(
            length=len(self.listas),
            selected_index=0,
            expand=True,
            on_change=lambda e: self.refrescar(),
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Categorías"),
                            ft.Tab(label="Medios de pago"),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True, controls=[lista.control for lista in self.listas]
                    ),
                ],
                expand=True,
            ),
        )
        self.control = ft.Column(
            [titulo("Ajustes"), self.pestanas], spacing=16, expand=True
        )

    def _lista_visible(self) -> ListaCatalogo:
        return self.listas[self.pestanas.selected_index or 0]

    def refrescar(self) -> None:
        # Se refrescan las dos: así al cambiar de pestaña ya está actualizada.
        for lista in self.listas:
            lista.refrescar()

    def nuevo(self) -> None:
        """Atajo Ctrl+N: nuevo elemento en la pestaña visible."""
        self._lista_visible().nuevo()
