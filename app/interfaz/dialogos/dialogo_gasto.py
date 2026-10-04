"""Diálogo de alta y edición de un gasto (RF-06, RF-07, RF-43 a RF-45, docs/diseno.md §4.1).

El gasto puede ser en pesos o en dólares. La sección "Compartido" llega en el paso 5.
"""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import catalogos, gastos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    convertir_usd_a_ars,
    formatear_ars,
    formatear_cotizacion_corta,
    formatear_detalle_usd,
    formatear_monto_para_editar,
    leer_monto,
)

# Las opciones de un Dropdown necesitan una clave de texto. Esta representa
# "sin medio de pago" (None en la base).
_SIN_MEDIO = "ninguno"

_AYUDA_TIPO = {
    "ARS": "Los fijos se copian al mes siguiente.",
    "USD": "Los fijos se copian al mes siguiente con los mismos dólares "
    "y la cotización del mes nuevo.",
}
_AYUDA_COTIZACION = "Escribí la cotización que te cobran (oficial, tarjeta o MEP). La app no suma impuestos."
_SIN_RESULTADO = "Completá el monto y la cotización para ver cuántos pesos vas a pagar."


class DialogoGasto:
    """Si gasto_id es None se da de alta un gasto nuevo; si no, se edita ese gasto.

    al_guardar(gasto_id, es_nuevo) se llama después de guardar bien.
    al_borrar(gasto_id) se llama si el usuario toca "Borrar" (solo en edición).
    """

    def __init__(
        self,
        app,
        mes_id: int,
        titulo_mes: str,
        al_guardar: Callable[[int, bool], None],
        gasto_id: int | None = None,
        al_borrar: Callable[[int], None] | None = None,
    ) -> None:
        self.app = app
        self.mes_id = mes_id
        self.gasto_id = gasto_id
        self.al_guardar = al_guardar
        self.al_borrar = al_borrar
        self.actual = gastos.obtener_gasto(app.con, gasto_id) if gasto_id else None
        # Cotización del mes: se sugiere en los gastos en dólares (RN-54).
        self.cotizacion_mes = meses.obtener_mes(app.con, mes_id)["cotizacion_cent"]

        self.nombre = ft.TextField(
            label="Nombre", autofocus=True, max_length=60, on_submit=self._guardar
        )
        self.categoria = ft.Dropdown(label="Categoría", expand=True)
        self.moneda = ft.SegmentedButton(
            segments=[
                ft.Segment(value="ARS", label=ft.Text("Pesos (ARS)")),
                ft.Segment(value="USD", label=ft.Text("Dólares (USD)")),
            ],
            selected=["ARS"],
            allow_empty_selection=False,
            on_change=self._cambiar_moneda,
        )

        # Bloque en pesos: un solo campo.
        self.monto = campo_monto("Monto", "ARS", on_submit=self._guardar)
        self.aviso_paso_a_pesos = texto_ayuda(
            "Al guardar en pesos, el gasto deja de guardar los dólares y la cotización.",
            visible=False,
        )
        self.bloque_pesos = ft.Column([self.monto, self.aviso_paso_a_pesos], spacing=4)

        # Bloque en dólares: monto, cotización del día y el resultado en pesos.
        self.monto_usd = campo_monto(
            "Monto en dólares", "USD", hint_text="Ej.: 20,00", on_submit=self._guardar
        )
        self.cotizacion = campo_monto(
            "Cotización del día", "ARS", sufijo="por US$", on_submit=self._guardar
        )
        # on_change se dispara en cada tecla: así el resultado se ve al instante.
        self.monto_usd.on_change = lambda e: self._actualizar_resultado()
        self.cotizacion.on_change = lambda e: self._actualizar_resultado()
        self.boton_usar_la_del_mes = ft.TextButton(
            visible=False, on_click=self._usar_la_del_mes
        )
        self.texto_resultado = ft.Text(size=18, weight=ft.FontWeight.W_600)
        self.nota_resultado = texto_ayuda("Los pesos quedan fijos con esta cotización.")
        self.resultado = ft.Container(
            padding=12,
            border_radius=8,
            bgcolor=estilos.color(app.page, "info_suave"),
            content=ft.Column([self.texto_resultado, self.nota_resultado], spacing=2),
        )
        self.bloque_dolares = ft.Column(
            [
                self.monto_usd,
                self.cotizacion,
                self.boton_usar_la_del_mes,
                self.resultado,
            ],
            spacing=8,
            visible=False,
        )

        self.tipo = ft.SegmentedButton(
            segments=[
                ft.Segment(value="fijo", label=ft.Text("Fijo mensual")),
                ft.Segment(value="unico", label=ft.Text("Pago único")),
            ],
            selected=["fijo"],
            allow_empty_selection=False,
        )
        self.ayuda_tipo = texto_ayuda(_AYUDA_TIPO["ARS"])
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
        self._preparar_cotizacion()
        if self.actual:
            self._precargar()
        self._mostrar_bloque_de_la_moneda()

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
                # La moneda va antes del monto: primero "en qué me cobran" y
                # después el número, con el prefijo correcto ($ o US$).
                self.moneda,
                self.bloque_pesos,
                self.bloque_dolares,
                self.tipo,
                self.ayuda_tipo,
                self.medio,
            ],
            al_guardar=self._guardar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
            boton_izquierda=boton_borrar,
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    def _moneda_elegida(self) -> str:
        return self.moneda.selected[0]

    # ------------------------------------------------------------------
    # Carga inicial
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

    def _preparar_cotizacion(self) -> None:
        """Sugiere la cotización del mes; si el mes no tiene, el campo queda vacío."""
        if self.cotizacion_mes is not None:
            self.cotizacion.value = formatear_monto_para_editar(self.cotizacion_mes)
            self.cotizacion.helper = _AYUDA_COTIZACION
        else:
            self.cotizacion.helper = "Este mes no tiene cotización: escribí la del día."

    def _precargar(self) -> None:
        self.nombre.value = self.actual["nombre"]
        self.categoria.value = str(self.actual["categoria_id"])
        self.tipo.selected = [self.actual["tipo"]]
        if self.actual["medio_pago_id"] is not None:
            self.medio.value = str(self.actual["medio_pago_id"])

        if self.actual["moneda"] == "USD":
            self.moneda.selected = ["USD"]
            self.monto_usd.value = formatear_monto_para_editar(
                self.actual["monto_usd_cent"]
            )
            # Se abre con la cotización que se guardó en el gasto, no con la del mes.
            self.cotizacion.value = formatear_monto_para_editar(
                self.actual["cotizacion_cent"]
            )
            self.cotizacion.helper = _AYUDA_COTIZACION
            mes = self.cotizacion_mes
            if mes is not None and mes != self.actual["cotizacion_cent"]:
                self.boton_usar_la_del_mes.content = (
                    f"Usar la del mes ({formatear_cotizacion_corta(mes)})"
                )
                self.boton_usar_la_del_mes.visible = True
        else:
            self.monto.value = formatear_monto_para_editar(self.actual["monto_cent"])

    # ------------------------------------------------------------------
    # Moneda y resultado en pesos
    # ------------------------------------------------------------------

    def _mostrar_bloque_de_la_moneda(self) -> None:
        en_dolares = self._moneda_elegida() == "USD"
        self.bloque_pesos.visible = not en_dolares
        self.bloque_dolares.visible = en_dolares
        self.ayuda_tipo.value = _AYUDA_TIPO[self._moneda_elegida()]
        self._actualizar_resultado()

    def _cambiar_moneda(self, e=None) -> None:
        # Los errores del bloque que se oculta se limpian: no quedan rojos escondidos.
        for campo in (self.monto, self.monto_usd, self.cotizacion):
            campo.error = None
        en_dolares = self._moneda_elegida() == "USD"

        # Un gasto que era en dólares y pasa a pesos: se precargan sus pesos
        # actuales, que son el monto real que tenía (§4.1).
        era_en_dolares = self.actual is not None and self.actual["moneda"] == "USD"
        if not en_dolares and era_en_dolares:
            if not (self.monto.value or "").strip():
                self.monto.value = formatear_monto_para_editar(
                    self.actual["monto_cent"]
                )
            self.aviso_paso_a_pesos.visible = True

        self._mostrar_bloque_de_la_moneda()
        self.app.page.update()
        campo = self.monto_usd if en_dolares else self.monto
        if not (campo.value or "").strip():
            self.app.enfocar(campo)

    def _usar_la_del_mes(self, e=None) -> None:
        self.cotizacion.value = formatear_monto_para_editar(self.cotizacion_mes)
        self.cotizacion.error = None
        self.boton_usar_la_del_mes.visible = False
        self._actualizar_resultado()
        self.app.page.update()

    def _actualizar_resultado(self) -> None:
        """Muestra "US$ 20,00 × $ 1.600 = $ 32.000 a pagar" mientras se escribe.

        Si todavía falta un dato o no es válido, muestra una ayuda (sin color de
        error: los errores aparecen recién al guardar).
        """
        self.texto_resultado.color = None
        try:
            usd = leer_monto(self.monto_usd.value or "")
            cotizacion = leer_monto(self.cotizacion.value or "")
        except ErrorDeValidacion:
            self.texto_resultado.value = _SIN_RESULTADO
            self.texto_resultado.size = estilos.TAM_AYUDA
            self.texto_resultado.weight = None
            self.nota_resultado.visible = False
            return
        pesos = convertir_usd_a_ars(usd, cotizacion)
        self.texto_resultado.value = (
            f"{formatear_detalle_usd(usd, cotizacion)} = {formatear_ars(pesos)} a pagar"
        )
        self.texto_resultado.size = 18
        self.texto_resultado.weight = ft.FontWeight.W_600
        self.nota_resultado.visible = True

    # ------------------------------------------------------------------
    # Categoría en línea
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Guardar
    # ------------------------------------------------------------------

    def _leer_montos(self) -> dict | None:
        """Lee el bloque de la moneda elegida. Devuelve los datos para la lógica,
        o None si algún campo tiene error (el error queda debajo del campo)."""
        if self._moneda_elegida() == "ARS":
            monto = leer_campo_monto(self.monto)
            return None if monto is None else {"moneda": "ARS", "monto_cent": monto}

        usd = cotizacion = None
        if not (self.monto_usd.value or "").strip():
            self.monto_usd.error = "Ingresá el monto en dólares."
        else:
            usd = leer_campo_monto(self.monto_usd)
        if not (self.cotizacion.value or "").strip():
            self.cotizacion.error = "Ingresá la cotización del día."
        else:
            cotizacion = leer_campo_monto(self.cotizacion, que="La cotización")
        if usd is None or cotizacion is None:
            return None
        return {
            "moneda": "USD",
            "monto_cent": None,
            "monto_usd_cent": usd,
            "cotizacion_cent": cotizacion,
        }

    def _guardar(self, e=None) -> None:
        for campo in (self.nombre, self.monto, self.monto_usd, self.cotizacion):
            campo.error = None
        self.categoria.error_text = None
        self.medio.error_text = None
        self._actualizar_resultado()

        # Controles simples en pantalla, para mostrar todos los errores a la vez.
        if not (self.nombre.value or "").strip():
            self.nombre.error = "Ingresá un nombre."
        if not self.categoria.value:
            self.categoria.error_text = "Elegí una categoría."
        montos = self._leer_montos()
        if self.nombre.error or self.categoria.error_text or montos is None:
            self._enfocar_primer_error()
            return

        medio = None if self.medio.value == _SIN_MEDIO else int(self.medio.value)
        datos = {
            "nombre": self.nombre.value,
            "categoria_id": int(self.categoria.value),
            "tipo": self.tipo.selected[0],
            "medio_pago_id": medio,
            **montos,  # ** "desarma" el diccionario: agrega sus claves a datos.
        }
        try:
            if self.actual:
                gastos.editar_gasto(self.app.con, self.gasto_id, **datos)
                gasto_id = self.gasto_id
            else:
                gasto_id = gastos.agregar_gasto(self.app.con, self.mes_id, **datos)
        except ErrorDeValidacion as error:
            self._mostrar_error(error)
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return

        self.app.cerrar_dialogo(self.dialogo)
        # Se pasa el id: la pantalla lee el gasto guardado para armar el aviso.
        self.al_guardar(gasto_id, self.actual is None)

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
        campos = {
            "nombre": self.nombre,
            "monto_usd": self.monto_usd,
            "cotizacion": self.cotizacion,
        }
        if error.campo in campos:
            campos[error.campo].error = mensaje
        elif error.campo == "categoria":
            self.categoria.error_text = mensaje
        elif error.campo == "medio_pago":
            self.medio.error_text = mensaje
        elif error.campo == "resultado":
            # Ej. RN-23 en dólares: el problema es el resultado en pesos (§4.1).
            self.texto_resultado.value = mensaje
            self.texto_resultado.size = estilos.TAM_TEXTO
            self.texto_resultado.color = estilos.color(self.app.page, "negativo")
            self.nota_resultado.visible = False
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
            (self.monto_usd, self.monto_usd.error),
            (self.cotizacion, self.cotizacion.error),
            (self.medio, self.medio.error_text),
        ]
        for campo, error in con_error:
            if error:
                self.app.enfocar(campo)
                return
        if self.texto_resultado.color is not None:
            self.app.enfocar(
                self.monto_usd
            )  # Error en el resultado: se corrige desde acá.

    def _borrar(self, e) -> None:
        self.app.cerrar_dialogo(self.dialogo)
        if self.al_borrar:
            self.al_borrar(self.gasto_id)
