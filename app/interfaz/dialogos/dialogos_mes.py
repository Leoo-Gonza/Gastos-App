"""Crear el mes siguiente y borrar el último (RF-03, RF-05, docs/diseno.md §3.9)."""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_monto_para_editar, nombre_mes, unir_con_y


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


class DialogoMesNuevo:
    """El mes no se elige: siempre es el siguiente al último (RN-08)."""

    def __init__(self, app) -> None:
        self.app = app
        s = meses.sugerencias_mes_siguiente(app.con)
        self.sugerencias = s
        self.nombre = nombre_mes(s["anio"], s["mes"])
        ultimo = meses.obtener_ultimo_mes(app.con)

        self.sueldo = campo_monto(
            "Sueldo", "USD", autofocus=True, on_submit=self._crear
        )
        self.sueldo.value = formatear_monto_para_editar(s["sueldo_usd_cent"])
        self.cotizacion = campo_monto(
            "Cotización", "ARS", sufijo="por US$", on_submit=self._crear
        )
        if s["cotizacion_cent"] is not None:
            self.cotizacion.value = formatear_monto_para_editar(s["cotizacion_cent"])
        self.cotizacion.on_change = lambda e: self._actualizar_aviso_dolares()

        self.aviso_dolares = ft.Text(size=estilos.TAM_AYUDA)
        self._actualizar_aviso_dolares()
        copia = [
            ft.Text(f"Se va a copiar de {nombre_mes(ultimo['anio'], ultimo['mes'])}:"),
            ft.Text(
                f"• {_plural(s['fijos'], 'gasto fijo', 'gastos fijos')}, sin pagos"
            ),
        ]
        if s["fijos_en_dolares"]:
            copia.append(self.aviso_dolares)
        if s["cuotas"]:
            copia.append(
                ft.Text(
                    f"• {_plural(s['cuotas'], 'cuota', 'cuotas')} de planes activos"
                )
            )
        copia.append(
            texto_ayuda("No se copian pagos únicos, ingresos extra ni cambios.")
        )

        self.dialogo = dialogo_formulario(
            f"Crear {self.nombre}",
            [
                texto_ayuda("Solo se puede crear el mes siguiente al último."),
                self.sueldo,
                self.cotizacion,
                texto_ayuda("Sugeridos del mes anterior. Podés cambiarlos."),
                *copia,
            ],
            al_guardar=self._crear,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
            texto_guardar="Crear mes",
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    def _actualizar_aviso_dolares(self) -> None:
        """La línea de los fijos en dólares cambia si se deja la cotización vacía."""
        n = self.sugerencias["fijos_en_dolares"]
        if (self.cotizacion.value or "").strip():
            self.aviso_dolares.value = (
                f"  ({n} en dólares: se pasan a pesos con la cotización de arriba)"
            )
            self.aviso_dolares.color = estilos.TEXTO_SECUNDARIO
        else:
            # RN-57: sin cotización del mes nuevo, conservan la del gasto copiado.
            if n == 1:
                quien = "el gasto en dólares conserva la cotización con la que se cargó"
            else:
                quien = f"los {n} gastos en dólares conservan la cotización con la que se cargaron"
            self.aviso_dolares.value = f"  Sin cotización, {quien}."
            self.aviso_dolares.color = estilos.color(self.app.page, "pendiente")

    def _crear(self, e=None) -> None:
        self.sueldo.error = None
        self.cotizacion.error = None
        if not (self.sueldo.value or "").strip():
            self.sueldo.error = "Ingresá el sueldo. Si este mes no cobrás, poné 0."
            sueldo = None
        else:
            sueldo = leer_campo_monto(self.sueldo, permitir_cero=True, que="El sueldo")
        cotizacion = None
        if (self.cotizacion.value or "").strip():
            cotizacion = leer_campo_monto(self.cotizacion, que="La cotización")
        if self.sueldo.error or self.cotizacion.error:
            self._enfocar_error()
            return
        s = self.sugerencias
        try:
            mes_id = meses.crear_mes(
                self.app.con, s["anio"], s["mes"], sueldo, cotizacion
            )
        except ErrorDeValidacion as error:
            campos = {"sueldo": self.sueldo, "cotizacion": self.cotizacion}
            if error.campo in campos:
                campos[error.campo].error = str(error)
                self._enfocar_error()
                return
            # Ej.: alguien creó el mes por otro lado y ya no es "el siguiente".
            self.app.cerrar_dialogo(self.dialogo)
            self.app.avisar(str(error))
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.app.seleccionar_mes(mes_id, pantalla="Resumen")
        creado = _plural(s["fijos"], "gasto fijo", "gastos fijos")
        if s["cuotas"]:
            creado += f" y {_plural(s['cuotas'], 'cuota', 'cuotas')}"
        self.app.avisar(f"{self.nombre} creado: {creado}.")

    def _enfocar_error(self) -> None:
        self.app.page.update()
        self.app.enfocar(self.sueldo if self.sueldo.error else self.cotizacion)


def confirmar_borrar_mes(app, mes_id: int) -> None:
    """RN-10: confirmación que dice qué se pierde. Solo para el último mes."""
    mes = meses.exigir_mes(app.con, mes_id)
    nombre = nombre_mes(mes["anio"], mes["mes"])
    contar = app.con.execute(
        """SELECT
             (SELECT COUNT(*) FROM gastos WHERE mes_id = :m) AS gastos,
             (SELECT COUNT(*) FROM pagos p JOIN gastos g ON g.id = p.gasto_id
               WHERE g.mes_id = :m) AS pagos,
             (SELECT COUNT(*) FROM ingresos_extra WHERE mes_id = :m) AS extras,
             (SELECT COUNT(*) FROM cambios WHERE mes_id = :m) AS cambios""",
        {"m": mes_id},
    ).fetchone()
    detalle = unir_con_y(
        [
            _plural(contar["gastos"], "gasto", "gastos"),
            _plural(contar["pagos"], "pago", "pagos"),
            _plural(contar["extras"], "ingreso extra", "ingresos extra"),
            _plural(contar["cambios"], "cambio", "cambios"),
        ]
    )

    def confirmado():
        try:
            meses.borrar_ultimo_mes(app.con, mes_id)
        except ErrorDeValidacion as error:
            app.avisar(str(error))
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            app.error_inesperado(error)
            return
        app.despues_de_borrar_mes()
        app.avisar(f"{nombre} borrado")

    app.confirmar(
        f"¿Borrar {nombre}?",
        f"Se borran {detalle} de este mes. No se borran los planes de cuotas ni los "
        'ítems cargados a mano en "Me deben". Esta acción no se puede deshacer.',
        "Borrar mes",
        confirmado,
    )
