"""Diálogo de alta y edición de un gasto (RF-06, RF-07, docs/diseno.md §4.1).

La sección "Compartido" llega en el paso 5.
"""

from collections.abc import Callable

import flet as ft

from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import catalogos, gastos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_monto_para_editar

# Las opciones de un Dropdown necesitan una clave de texto. Esta representa
# "sin medio de pago" (None en la base).
_SIN_MEDIO = "ninguno"


class DialogoGasto:
    """Si gasto_id es None se da de alta un gasto nuevo; si no, se edita ese gasto.

    al_guardar(nombre, es_nuevo) se llama después de guardar bien.
    al_borrar(gasto_id) se llama si el usuario toca "Borrar" (solo en edición).
    """

    def __init__(
        self,
        app,
        mes_id: int,
        titulo_mes: str,
        al_guardar: Callable[[str, bool], None],
        gasto_id: int | None = None,
        al_borrar: Callable[[int], None] | None = None,
    ) -> None:
        self.app = app
        self.mes_id = mes_id
        self.gasto_id = gasto_id
        self.al_guardar = al_guardar
        self.al_borrar = al_borrar
        self.actual = gastos.obtener_gasto(app.con, gasto_id) if gasto_id else None

        self.nombre = ft.TextField(
            label="Nombre", autofocus=True, max_length=60, on_submit=self._guardar
        )
        self.categoria = ft.Dropdown(label="Categoría", expand=True)
        self.monto = campo_monto("Monto", "ARS", on_submit=self._guardar)
        self.tipo = ft.SegmentedButton(
            segments=[
                ft.Segment(value="fijo", label=ft.Text("Fijo mensual")),
                ft.Segment(value="unico", label=ft.Text("Pago único")),
            ],
            selected=["fijo"],
            allow_empty_selection=False,
        )
        self.medio = ft.Dropdown(label="Medio de pago", expand=True)

        # Creación de una categoría sin salir del diálogo (§4.1).
        self.nueva_categoria = ft.TextField(
            label="Nombre de la categoría",
            expand=True,
            on_submit=self._agregar_categoria,
        )
        self.fila_nueva_categoria = ft.Row(
            [
                self.nueva_categoria,
                ft.TextButton("Agregar", on_click=self._agregar_categoria),
            ],
            visible=False,
        )
        self.aviso_sin_categorias = texto_ayuda(
            "Todavía no tenés categorías. Creá la primera.", visible=False
        )

        self._cargar_opciones()
        if self.actual:
            self._precargar()

        boton_borrar = None
        if self.actual:
            boton_borrar = ft.TextButton(
                "Borrar",
                icon=ft.Icons.DELETE_OUTLINE,
                on_click=self._borrar,
                style=ft.ButtonStyle(color=ft.Colors.ERROR),
            )
        titulo = "Editar gasto" if self.actual else "Nuevo gasto"
        self.dialogo = dialogo_formulario(
            f"{titulo} – {titulo_mes}",
            [
                self.nombre,
                ft.Row(
                    [
                        self.categoria,
                        ft.IconButton(
                            ft.Icons.ADD,
                            tooltip="Nueva categoría",
                            on_click=self._mostrar_nueva_categoria,
                        ),
                    ]
                ),
                self.aviso_sin_categorias,
                self.fila_nueva_categoria,
                self.monto,
                self.tipo,
                texto_ayuda("Los fijos se copian al mes siguiente."),
                self.medio,
            ],
            al_guardar=self._guardar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
            boton_izquierda=boton_borrar,
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    # ------------------------------------------------------------------

    def _cargar_opciones(self) -> None:
        """Llena los desplegables con las categorías y medios no archivados.

        Si el gasto que se edita usa uno archivado, se agrega igual con el
        sufijo "(archivada)" para no obligar a cambiarlo (§4.1).
        """
        con = self.app.con
        categorias = catalogos.listar(con, catalogos.CATEGORIAS)
        self.categoria.options = [
            ft.DropdownOption(key=str(c["id"]), text=c["nombre"]) for c in categorias
        ]
        medios = catalogos.listar(con, catalogos.MEDIOS_PAGO)
        self.medio.options = [
            ft.DropdownOption(key=_SIN_MEDIO, text="Sin medio de pago")
        ] + [ft.DropdownOption(key=str(m["id"]), text=m["nombre"]) for m in medios]
        if self.actual:
            cat = catalogos.obtener(
                con, catalogos.CATEGORIAS, self.actual["categoria_id"]
            )
            if cat["archivado"]:
                self.categoria.options.append(
                    ft.DropdownOption(
                        key=str(cat["id"]), text=f"{cat['nombre']} (archivada)"
                    )
                )
            if self.actual["medio_pago_id"] is not None:
                medio = catalogos.obtener(
                    con, catalogos.MEDIOS_PAGO, self.actual["medio_pago_id"]
                )
                if medio["archivado"]:
                    self.medio.options.append(
                        ft.DropdownOption(
                            key=str(medio["id"]), text=f"{medio['nombre']} (archivado)"
                        )
                    )
        sin_categorias = not self.categoria.options
        self.aviso_sin_categorias.visible = sin_categorias
        self.fila_nueva_categoria.visible = (
            sin_categorias or self.fila_nueva_categoria.visible
        )
        if self.medio.value is None:
            self.medio.value = _SIN_MEDIO

    def _precargar(self) -> None:
        self.nombre.value = self.actual["nombre"]
        self.categoria.value = str(self.actual["categoria_id"])
        self.monto.value = formatear_monto_para_editar(self.actual["monto_cent"])
        self.tipo.selected = [self.actual["tipo"]]
        if self.actual["medio_pago_id"] is not None:
            self.medio.value = str(self.actual["medio_pago_id"])

    def _mostrar_nueva_categoria(self, e) -> None:
        self.fila_nueva_categoria.visible = True
        self.app.page.update()
        self.app.enfocar(self.nueva_categoria)

    def _agregar_categoria(self, e) -> None:
        self.nueva_categoria.error = None
        try:
            nuevo_id = catalogos.crear(
                self.app.con, catalogos.CATEGORIAS, self.nueva_categoria.value or ""
            )
        except ErrorDeValidacion as error:
            self.nueva_categoria.error = str(error)
            self.app.page.update()
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.error_inesperado(error)
            return
        self.nueva_categoria.value = ""
        self.fila_nueva_categoria.visible = False
        self._cargar_opciones()
        self.categoria.value = str(nuevo_id)
        self.categoria.error_text = None
        self.app.page.update()

    def _guardar(self, e=None) -> None:
        self.nombre.error = None
        self.monto.error = None
        self.categoria.error_text = None
        self.medio.error_text = None

        # Controles simples en pantalla, para mostrar todos los errores a la vez.
        if not (self.nombre.value or "").strip():
            self.nombre.error = "Ingresá un nombre."
        if not self.categoria.value:
            self.categoria.error_text = "Elegí una categoría."
        monto = leer_campo_monto(self.monto)
        if self.nombre.error or self.categoria.error_text or monto is None:
            self._enfocar_primer_error()
            return

        medio = None if self.medio.value == _SIN_MEDIO else int(self.medio.value)
        datos = {
            "nombre": self.nombre.value,
            "categoria_id": int(self.categoria.value),
            "monto_cent": monto,
            "tipo": self.tipo.selected[0],
            "medio_pago_id": medio,
        }
        try:
            if self.actual:
                gastos.editar_gasto(self.app.con, self.gasto_id, **datos)
            else:
                gastos.agregar_gasto(self.app.con, self.mes_id, **datos)
        except ErrorDeValidacion as error:
            self._mostrar_error(error)
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return

        self.app.cerrar_dialogo(self.dialogo)
        self.al_guardar(" ".join(self.nombre.value.split()), self.actual is None)

    def _mostrar_error(self, error: ErrorDeValidacion) -> None:
        """Pone el mensaje de la lógica debajo del campo que corresponde."""
        mensaje = str(error)
        if error.campo is None:
            # No es un dato mal cargado sino algo que cambió por detrás
            # (ej. "El gasto ya no existe."): se cierra y se actualiza la tabla.
            self.app.cerrar_dialogo(self.dialogo)
            self.app.refrescar()
            self.app.avisar(mensaje)
            return
        if error.campo == "nombre":
            self.nombre.error = mensaje
        elif error.campo == "categoria":
            self.categoria.error_text = mensaje
        elif error.campo == "medio_pago":
            self.medio.error_text = mensaje
        else:
            self.monto.error = mensaje
        self._enfocar_primer_error()

    def _enfocar_primer_error(self) -> None:
        """Lleva el cursor al primer campo con error, en el orden del formulario."""
        self.app.page.update()
        con_error = [
            (self.nombre, self.nombre.error),
            (self.categoria, self.categoria.error_text),
            (self.monto, self.monto.error),
            (self.medio, self.medio.error_text),
        ]
        for campo, error in con_error:
            if error:
                self.app.enfocar(campo)
                return

    def _borrar(self, e) -> None:
        self.app.cerrar_dialogo(self.dialogo)
        if self.al_borrar:
            self.al_borrar(self.gasto_id)
