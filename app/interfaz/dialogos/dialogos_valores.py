"""Diálogos de un solo monto: sueldo, cotización y meta de ahorro (docs/diseno.md §3.6).

Los tres tienen la misma forma (un campo, Cancelar / Guardar), así que comparten
_dialogo_un_monto y cada función pública solo cambia textos y qué se guarda.
"""

from collections.abc import Callable

import flet as ft

from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import configuracion, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    formatear_cotizacion,
    formatear_monto_para_editar,
    formatear_usd,
    nombre_mes,
)


def _dialogo_un_monto(
    app,
    titulo: str,
    campo: ft.TextField,
    ayudas: list[str],
    mensaje_vacio: str,
    que: str,
    guardar: Callable[[int], None],
    aviso: Callable[[int], str],
    permitir_cero: bool = False,
    boton_izquierda: ft.Control | None = None,
) -> ft.AlertDialog:
    """Arma el diálogo: valida el campo, llama a guardar(centavos) y avisa."""

    def al_guardar(e=None):
        campo.error = None
        centavos = None
        if not (campo.value or "").strip():
            campo.error = mensaje_vacio
        else:
            # Paso 1: leer lo escrito. Si está mal, el error queda debajo del
            # campo y el diálogo sigue abierto (BUG-11: antes se cerraba).
            centavos = leer_campo_monto(campo, permitir_cero=permitir_cero, que=que)
        if centavos is not None:
            # Paso 2: guardar. Acá un error sin campo sí significa que algo
            # cambió por detrás (ej. el mes se borró): se cierra y se avisa.
            try:
                guardar(centavos)
            except ErrorDeValidacion as error:
                if error.campo is None:
                    app.cerrar_dialogo(dialogo)
                    app.avisar(str(error))
                    return
                campo.error = str(error)
            except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
                app.cerrar_dialogo(dialogo)
                app.error_inesperado(error)
                return
        if campo.error:
            app.page.update()
            app.enfocar(campo)
            return
        app.cerrar_dialogo(dialogo)
        app.refrescar()
        app.avisar(aviso(centavos))

    campo.autofocus = True
    campo.on_submit = al_guardar
    dialogo = dialogo_formulario(
        titulo,
        [campo, *[texto_ayuda(a) for a in ayudas]],
        al_guardar=al_guardar,
        al_cancelar=lambda e: app.cerrar_dialogo(dialogo),
        boton_izquierda=boton_izquierda,
    )
    return dialogo


def abrir_sueldo(app, mes_id: int) -> None:
    """RF-23: sueldo en USD del mes. Acepta 0 (con aviso en el Resumen)."""
    mes = meses.exigir_mes(app.con, mes_id)
    campo = campo_monto("Sueldo", "USD", hint_text="Ej.: 1.200,00")
    campo.value = formatear_monto_para_editar(mes["sueldo_usd_cent"])
    dialogo = _dialogo_un_monto(
        app,
        f"Sueldo de {nombre_mes(mes['anio'], mes['mes'])}",
        campo,
        [],
        "Ingresá el sueldo. Si este mes no cobrás, poné 0.",
        "El sueldo",
        lambda c: meses.editar_sueldo(app.con, mes_id, c),
        lambda c: f"Sueldo actualizado: {formatear_usd(c)}",
        permitir_cero=True,
    )
    app.abrir_dialogo(dialogo)


def abrir_cotizacion(app, mes_id: int) -> None:
    """RF-25: cotización del mes. Una vez cargada no se puede dejar vacía."""
    mes = meses.exigir_mes(app.con, mes_id)
    campo = campo_monto("Cotización", "ARS", sufijo="por US$", hint_text="Ej.: 1.600")
    if mes["cotizacion_cent"] is not None:
        campo.value = formatear_monto_para_editar(mes["cotizacion_cent"])
    ayudas = [
        (
            "Se usa para calcular los dólares a cambiar. No modifica los cambios ya "
            "registrados ni los gastos en dólares ya cargados."
        )
    ]
    en_dolares = app.con.execute(
        "SELECT COUNT(*) AS n FROM gastos WHERE mes_id = ? AND moneda = 'USD'",
        (mes_id,),
    ).fetchone()["n"]
    if en_dolares:
        cuantos = "1 gasto" if en_dolares == 1 else f"{en_dolares} gastos"
        ayudas.append(
            f"Este mes tiene {cuantos} en dólares. Si querés actualizarlos, "
            "editalos uno por uno."
        )
    dialogo = _dialogo_un_monto(
        app,
        f"Cotización de {nombre_mes(mes['anio'], mes['mes'])}",
        campo,
        ayudas,
        "Ingresá la cotización.",
        "La cotización",
        lambda c: meses.editar_cotizacion(app.con, mes_id, c),
        lambda c: f"Cotización actualizada: {formatear_cotizacion(c)}",
    )
    app.abrir_dialogo(dialogo)


def abrir_meta(app) -> None:
    """RF-36: meta de ahorro mensual en USD, la misma para todos los meses."""
    actual = configuracion.obtener_meta(app.con)
    campo = campo_monto("Meta de ahorro", "USD", hint_text="Ej.: 300,00")
    boton_quitar = None
    if actual is not None:
        campo.value = formatear_monto_para_editar(actual)

        def quitar(e):
            configuracion.quitar_meta(app.con)
            app.cerrar_dialogo(dialogo)
            app.refrescar()
            app.avisar("Meta de ahorro quitada")

        boton_quitar = ft.TextButton("Quitar meta", on_click=quitar)
    dialogo = _dialogo_un_monto(
        app,
        "Meta de ahorro",
        campo,
        ["Es la misma para todos los meses."],
        "Ingresá la meta.",
        "La meta",
        lambda c: configuracion.guardar_meta(app.con, c),
        lambda c: f"Meta de ahorro: {formatear_usd(c)}",
        boton_izquierda=boton_quitar,
    )
    app.abrir_dialogo(dialogo)
