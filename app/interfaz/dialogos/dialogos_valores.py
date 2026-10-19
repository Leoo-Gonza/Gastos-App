"""Diálogos de un solo monto: sueldo, cotización y meta de ahorro (docs/diseno.md §3.6).

Los tres tienen la misma forma (un campo, Cancelar / Guardar), así que comparten
_dialogo_un_monto y cada función pública solo cambia textos y qué se guarda.

La cotización tiene además, en el mes actual y los futuros, el botón "Buscar
dólar ..." que la trae de internet (v2, RF-60 a RF-62): _BusquedaCotizacion.
"""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import (
    aviso_en_pantalla,
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import configuracion, cotizacion_online, meses
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
    extras: list[ft.Control] | None = None,
    bloqueado: Callable[[], bool] | None = None,
) -> ft.AlertDialog:
    """Arma el diálogo: valida el campo, llama a guardar(centavos) y avisa.

    extras: controles que van entre el campo y las ayudas (la búsqueda de la
    cotización). bloqueado: si devuelve True, Guardar (y Enter) no hacen nada.
    """

    def al_guardar(e=None):
        if bloqueado is not None and bloqueado():
            return  # Mientras busca la cotización no se guarda (RN-86).
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
        [campo, *(extras or []), *[texto_ayuda(a) for a in ayudas]],
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


class _BusquedaCotizacion:
    """Botón "Buscar dólar ...", ruedita, origen y error (§3.6, RN-84 a RN-87).

    Se crea una nueva cada vez que se abre el diálogo: así una búsqueda de un
    diálogo ya cerrado no puede escribir en otro (RN-86).
    """

    def __init__(self, app, campo: ft.TextField, nombre: str, es_futuro: bool) -> None:
        self.app = app
        self.campo = campo
        self.buscando = False
        # Se completan después de armar el diálogo (ver abrir_cotizacion).
        self.dialogo: ft.AlertDialog | None = None
        self.boton_guardar: ft.Control | None = None

        dolar = configuracion.obtener_dolar(app.con)
        self.texto_origen = ft.Text(
            size=estilos.TAM_AYUDA, color=estilos.TEXTO_SECUNDARIO, expand=True
        )
        self.origen = ft.Row(
            [
                ft.Icon(
                    ft.Icons.INFO_OUTLINE,
                    size=16,
                    color=estilos.color(app.page, "info"),
                ),
                self.texto_origen,
            ],
            visible=False,
        )
        self.boton = ft.OutlinedButton(
            cotizacion_online.texto_boton(dolar),
            icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            tooltip="Busca el precio de compra de hoy en internet. No guarda nada.",
            on_click=lambda e: self.buscar(),
        )
        self.ruedita = ft.ProgressRing(
            width=18,
            height=18,
            stroke_width=2,
            visible=False,
            # Para los lectores de pantalla (§3.6, O-39).
            semantics_label="Buscando la cotización",
        )
        self.estado = texto_ayuda("Buscando la cotización…", visible=False)
        self.error = aviso_en_pantalla(
            app.page,
            "negativo",
            ft.Icons.ERROR_OUTLINE,
            cotizacion_online.MENSAJE_ERROR,
        )
        self.error.visible = False
        ayuda = (
            "Trae el precio de compra de hoy desde internet (DolarApi) y completa el "
            "campo. No se guarda hasta que toques Guardar. El dólar se elige en Ajustes."
        )
        if es_futuro:
            ayuda += f" Es la cotización de hoy, no la de {nombre}."
        # En el orden del diseño: origen pegado al campo, error pegado al botón.
        self.controles = [
            self.origen,
            ft.Row([self.boton, self.ruedita, self.estado], spacing=12),
            self.error,
            texto_ayuda(ayuda),
        ]
        # on_change se dispara solo con lo que escribe el usuario, no cuando el
        # código pone campo.value: por eso la búsqueda no borra su propio origen.
        campo.on_change = lambda e: self._al_editar()

    def _al_editar(self) -> None:
        # Un valor cambiado a mano ya no es el de DolarApi (RN-85, RN-87).
        if self.origen.visible or self.error.visible:
            self.origen.visible = self.error.visible = False
            self.app.page.update()

    def _mostrar_buscando(self, buscando: bool) -> None:
        self.buscando = buscando
        self.boton.disabled = buscando
        self.ruedita.visible = self.estado.visible = buscando
        # Solo lectura y no deshabilitado: así el valor se sigue leyendo bien
        # (observación 34). Guardar sí se apaga (observación 35).
        self.campo.read_only = buscando
        if self.boton_guardar is not None:
            self.boton_guardar.disabled = buscando

    def buscar(self) -> None:
        if self.buscando:
            return
        # Todo se marca ya, al hacer clic: dos clics seguidos hacen un solo pedido.
        self._mostrar_buscando(True)
        self.error.visible = False
        self.app.page.update()
        self.app.page.run_task(self._buscar)

    async def _buscar(self) -> None:
        resultado = inesperado = None
        try:
            resultado = await cotizacion_online.buscar_con_limite(self.app.con)
        except ErrorDeValidacion:
            pass  # Sin internet, sin respuesta a tiempo o respuesta inválida.
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            inesperado = error
        if not self.app.esta_abierto(self.dialogo):
            return  # Se cerró mientras buscaba: la respuesta se descarta (RN-86).
        self._mostrar_buscando(False)
        if inesperado is not None:
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(inesperado)
            return
        if resultado is None:
            # El campo y su origen quedan como estaban (RN-87).
            self.error.visible = True
            self.app.page.update()
            self.app.enfocar(self.boton)  # Para reintentar sin guardar por accidente.
            return
        self.campo.value = formatear_monto_para_editar(resultado.centavos)
        self.campo.error = None
        self.texto_origen.value = resultado.origen
        self.origen.visible = True
        self.app.page.update()
        self.app.enfocar(self.campo)


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
    nombre = nombre_mes(mes["anio"], mes["mes"])
    # El botón de búsqueda solo va en el mes actual y los futuros: la fuente da
    # la cotización de hoy, no la de un mes pasado (RN-80).
    actual = meses.mes_actual_calendario()
    busqueda = None
    if (mes["anio"], mes["mes"]) >= actual:
        busqueda = _BusquedaCotizacion(
            app, campo, nombre, (mes["anio"], mes["mes"]) > actual
        )
    dialogo = _dialogo_un_monto(
        app,
        f"Cotización de {nombre}",
        campo,
        ayudas,
        "Ingresá la cotización.",
        "La cotización",
        lambda c: meses.editar_cotizacion(app.con, mes_id, c),
        lambda c: f"Cotización actualizada: {formatear_cotizacion(c)}",
        extras=busqueda.controles if busqueda else None,
        bloqueado=(lambda: busqueda.buscando) if busqueda else None,
    )
    if busqueda is not None:
        busqueda.dialogo = dialogo
        # dialogo_formulario pone [Cancelar, Guardar] en la segunda acción.
        busqueda.boton_guardar = dialogo.actions[1].controls[1]
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
