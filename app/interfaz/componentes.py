"""Piezas de pantalla que se repiten en toda la app (docs/diseno.md §2.4 y §2.5)."""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_monto_para_editar, leer_monto

_MONEDAS = {"ARS": "$ ", "USD": "US$ "}


def campo_monto(label: str, moneda: str = "ARS", **opciones) -> ft.TextField:
    """Campo para escribir un monto. Igual en toda la app (§2.4).

    Acepta "66020", "66.020", "66020,12" y "66.020,12". Al salir del campo,
    si el valor es válido lo reescribe prolijo: "66020,5" -> "66.020,50".
    """
    campo = ft.TextField(
        label=label,
        prefix=_MONEDAS[moneda],
        suffix=moneda,
        text_align=ft.TextAlign.RIGHT,
        keyboard_type=ft.KeyboardType.NUMBER,
        # Impide escribir letras o el signo menos. Igual la lógica valida todo.
        input_filter=ft.InputFilter(regex_string=r"[0-9.,]", allow=True),
        hint_text="Ej.: 66.020,12",
        **opciones,
    )

    def al_salir(e):
        try:
            centavos = leer_monto(campo.value, permitir_cero=True)
        except ErrorDeValidacion:
            return  # Si no es válido se deja como está; el error se muestra al guardar.
        campo.value = formatear_monto_para_editar(centavos)

    campo.on_blur = al_salir
    return campo


def leer_campo_monto(
    campo: ft.TextField, permitir_cero: bool = False, que: str = "El monto"
) -> int | None:
    """Devuelve los centavos del campo, o None si no es válido.

    Si no es válido, deja el mensaje debajo del campo (campo.error).
    "que" cambia el sujeto del mensaje: "La cotización tiene que ser mayor a 0."
    """
    try:
        return leer_monto(campo.value or "", permitir_cero=permitir_cero, que=que)
    except ErrorDeValidacion as error:
        campo.error = str(error)
        return None


def titulo(texto: str) -> ft.Text:
    return ft.Text(texto, size=estilos.TAM_TITULO, weight=ft.FontWeight.W_600)


def texto_ayuda(texto: str, **opciones) -> ft.Text:
    return ft.Text(
        texto, size=estilos.TAM_AYUDA, color=estilos.TEXTO_SECUNDARIO, **opciones
    )


def estado_vacio(
    icono: ft.IconData, texto: str, texto_boton: str, al_hacer_clic: Callable
) -> ft.Control:
    """Pantalla sin datos: siempre con un botón que resuelve el vacío (§2.5)."""
    return ft.Container(
        padding=48,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            [
                ft.Icon(icono, size=48, color=estilos.TEXTO_SECUNDARIO),
                ft.Text(texto, size=estilos.TAM_TEXTO, text_align=ft.TextAlign.CENTER),
                ft.FilledButton(texto_boton, icon=ft.Icons.ADD, on_click=al_hacer_clic),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=16,
            tight=True,
        ),
    )


def dialogo_formulario(
    titulo_dialogo: str,
    controles: list[ft.Control],
    al_guardar: Callable,
    al_cancelar: Callable,
    texto_guardar: str = "Guardar",
    boton_izquierda: ft.Control | None = None,
) -> ft.AlertDialog:
    """Diálogo con campos y los botones Cancelar / Guardar (§2.5).

    boton_izquierda es opcional: por ejemplo "Borrar" al editar un gasto.
    """
    botones_derecha = ft.Row(
        [
            ft.TextButton("Cancelar", on_click=al_cancelar),
            ft.FilledButton(texto_guardar, on_click=al_guardar),
        ],
        tight=True,
    )
    return ft.AlertDialog(
        modal=True,
        title=ft.Text(titulo_dialogo),
        content=ft.Column(controles, tight=True, width=480, spacing=12),
        actions=[boton_izquierda or ft.Container(), botones_derecha],
        actions_alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
    )


def boton_peligroso(
    page: ft.Page, texto: str, al_hacer_clic: Callable
) -> ft.FilledButton:
    """Botón rojo para acciones que borran datos."""
    return ft.FilledButton(
        texto,
        on_click=al_hacer_clic,
        style=ft.ButtonStyle(
            bgcolor=estilos.color(page, "negativo"),
            color=estilos.color(page, "sobre_negativo"),
        ),
    )
