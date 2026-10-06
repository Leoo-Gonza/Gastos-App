"""Diálogo de plan de cuotas: alta y edición (RF-16, RF-19, docs/diseno.md §3.4 y §4.2).

Los planes son solo en pesos. La vista previa muestra al instante la última
cuota, el total y qué cuota va en el mes actual.
"""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
)
from app.logica import catalogos, cuotas, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    MESES,
    formatear_ars,
    formatear_monto_para_editar,
    leer_monto,
    nombre_mes,
)

_SIN_MEDIO = "ninguno"


class DialogoPlan:
    """plan_id None = plan nuevo; si no, se edita ese plan."""

    def __init__(self, app, plan_id: int | None = None) -> None:
        self.app = app
        self.plan_id = plan_id
        self.actual = cuotas.obtener_plan(app.con, plan_id) if plan_id else None
        self.anio_actual, self.mes_actual = meses.mes_actual_calendario()
        self.nombre_actual = nombre_mes(self.anio_actual, self.mes_actual)

        self.nombre = ft.TextField(
            label="Nombre", autofocus=True, max_length=60, on_submit=self._guardar
        )
        self.categoria = ft.Dropdown(label="Categoría", expand=True)
        self.medio = ft.Dropdown(label="Medio de pago", expand=True)
        self.monto = campo_monto("Monto de la cuota", "ARS", on_submit=self._guardar)
        self.cantidad = ft.TextField(
            label="Cantidad de cuotas",
            width=160,
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"[0-9]", allow=True),
            on_submit=self._guardar,
        )
        self.primer_mes = ft.Dropdown(
            label="Primera cuota: mes",
            expand=True,
            options=[
                ft.DropdownOption(key=str(n), text=nombre)
                for n, nombre in enumerate(MESES, 1)
            ],
            value=str(self.mes_actual),
        )
        self.primer_anio = ft.TextField(
            label="Año",
            width=110,
            max_length=4,
            value=str(self.anio_actual),
            keyboard_type=ft.KeyboardType.NUMBER,
            input_filter=ft.InputFilter(regex_string=r"[0-9]", allow=True),
            on_submit=self._guardar,
        )
        self.vista_previa = ft.Text(size=estilos.TAM_TEXTO)
        # La vista previa se recalcula en cada cambio de estos campos.
        for campo in (self.monto, self.cantidad, self.primer_anio):
            campo.on_change = lambda e: self._actualizar_vista_previa()
        self.primer_mes.on_select = lambda e: self._actualizar_vista_previa()

        self._cargar_opciones()
        if self.actual:
            self._precargar()
        self._actualizar_vista_previa()

        if self.actual:
            aviso = (
                f"Los cambios se aplican desde {self.nombre_actual}. "
                "Las cuotas que ya tienen pagos no se modifican."
            )
        else:
            aviso = (
                f"Las cuotas se agregan desde el mes actual ({self.nombre_actual}) y en los "
                "meses siguientes que ya existan. Los meses anteriores no se modifican."
            )
        info = estilos.color(app.page, "info")
        self.dialogo = dialogo_formulario(
            "Editar plan de cuotas" if self.actual else "Nuevo plan de cuotas",
            [
                ft.Container(
                    padding=12,
                    border_radius=8,
                    bgcolor=estilos.color(app.page, "info_suave"),
                    content=ft.Text(aviso, color=info, size=estilos.TAM_AYUDA),
                ),
                self.nombre,
                self.categoria,
                self.medio,
                self.monto,
                texto_ayuda("Las cuotas se cargan en pesos."),
                self.cantidad,
                ft.Row([self.primer_mes, self.primer_anio]),
                ft.Container(
                    padding=12,
                    border_radius=8,
                    bgcolor=estilos.color(app.page, "info_suave"),
                    content=self.vista_previa,
                ),
            ],
            al_guardar=self._guardar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
        )

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    # ------------------------------------------------------------------

    def _cargar_opciones(self) -> None:
        """Categorías y medios no archivados; los archivados que ya tenía el plan, con sufijo."""
        con = self.app.con
        self.categoria.options = [
            ft.DropdownOption(key=str(c["id"]), text=c["nombre"])
            for c in catalogos.listar(con, catalogos.CATEGORIAS)
        ]
        self.medio.options = [
            ft.DropdownOption(key=_SIN_MEDIO, text="Sin medio de pago")
        ] + [
            ft.DropdownOption(key=str(m["id"]), text=m["nombre"])
            for m in catalogos.listar(con, catalogos.MEDIOS_PAGO)
        ]
        self.medio.value = _SIN_MEDIO
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

    def _precargar(self) -> None:
        p = self.actual
        self.nombre.value = p["nombre"]
        self.categoria.value = str(p["categoria_id"])
        if p["medio_pago_id"] is not None:
            self.medio.value = str(p["medio_pago_id"])
        self.monto.value = formatear_monto_para_editar(p["monto_cuota_cent"])
        self.cantidad.value = str(p["cantidad_cuotas"])
        self.primer_mes.value = str(p["primer_mes"])
        self.primer_anio.value = str(p["primer_anio"])

    def _datos_para_vista_previa(self) -> dict | None:
        """Los datos del formulario si alcanzan para calcular; si no, None."""
        try:
            monto = leer_monto(self.monto.value or "")
            cantidad = int(self.cantidad.value or "0")
            anio = int(self.primer_anio.value or "0")
            mes = int(self.primer_mes.value or "0")
        except (ErrorDeValidacion, ValueError):
            return None
        if cantidad < 1 or not 1000 <= anio <= 9999 or not 1 <= mes <= 12:
            return None
        return {
            "id": self.plan_id or 0,
            "monto_cuota_cent": monto,
            "cantidad_cuotas": cantidad,
            "primer_anio": anio,
            "primer_mes": mes,
            "cancelado_anio": None,
            "cancelado_mes": None,
        }

    def _actualizar_vista_previa(self) -> None:
        """ "Última cuota: Octubre 2026 · Total del plan: $ 123.350 · En Octubre 2026 va la 3/3"."""
        plan = self._datos_para_vista_previa()
        if plan is None:
            self.vista_previa.value = "Completá el monto, la cantidad de cuotas y la primera cuota para ver el plan."
            self.vista_previa.color = estilos.TEXTO_SECUNDARIO
            return
        ultima = nombre_mes(*cuotas.ultima_cuota(plan))
        total = formatear_ars(plan["cantidad_cuotas"] * plan["monto_cuota_cent"])
        n = cuotas.numero_de_cuota(plan, self.anio_actual, self.mes_actual)
        if n < 1:
            cuota = "todavía no empezó"
        elif n > plan["cantidad_cuotas"]:
            cuota = "ya terminó"
        else:
            cuota = f"va la cuota {n}/{plan['cantidad_cuotas']}"
        self.vista_previa.value = (
            f"Última cuota: {ultima} · Total del plan: {total} · "
            f"En {self.nombre_actual} (mes actual) {cuota}"
        )
        self.vista_previa.color = estilos.color(self.app.page, "info")

    def _guardar(self, e=None) -> None:
        for campo in (self.nombre, self.monto, self.cantidad, self.primer_anio):
            campo.error = None
        self.categoria.error_text = None
        if not (self.nombre.value or "").strip():
            self.nombre.error = "Ingresá un nombre."
        if not self.categoria.value:
            self.categoria.error_text = "Elegí una categoría."
        monto = leer_campo_monto(self.monto, que="El monto de la cuota")
        cantidad = (
            int(self.cantidad.value) if (self.cantidad.value or "").isdigit() else 0
        )
        if cantidad < 1:
            self.cantidad.error = "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1."
        anio_txt = self.primer_anio.value or ""
        if len(anio_txt) != 4 or not anio_txt.isdigit():
            self.primer_anio.error = "El año tiene que tener 4 dígitos."
        if (
            self.nombre.error
            or self.categoria.error_text
            or monto is None
            or self.cantidad.error
            or self.primer_anio.error
        ):
            self._enfocar_error()
            return

        medio = None if self.medio.value == _SIN_MEDIO else int(self.medio.value)
        datos = (
            self.nombre.value,
            int(self.categoria.value),
            medio,
            monto,
            cantidad,
            int(anio_txt),
            int(self.primer_mes.value),
        )
        try:
            if self.actual:
                cuotas.editar_plan(self.app.con, self.plan_id, *datos)
                plan_id = self.plan_id
            else:
                plan_id = cuotas.crear_plan(self.app.con, *datos)
        except ErrorDeValidacion as error:
            campos = {
                "nombre": self.nombre,
                "monto": self.monto,
                "cantidad": self.cantidad,
                "primera": self.primer_anio,
            }
            if error.campo in campos:
                campos[error.campo].error = str(error)
            elif error.campo == "categoria":
                self.categoria.error_text = str(error)
            elif error.campo == "medio_pago":
                self.medio.error_text = str(error)
            else:
                self.app.cerrar_dialogo(self.dialogo)
                self.app.refrescar()
                self.app.avisar(str(error))
                return
            self._enfocar_error()
            return
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.cerrar_dialogo(self.dialogo)
            self.app.error_inesperado(error)
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.app.refrescar()
        self.app.avisar(self._aviso_guardado(plan_id))

    def _aviso_guardado(self, plan_id: int) -> str:
        """Dice qué pasó con la cuota del mes actual (§3.4)."""
        if self.actual:
            return (
                f"Plan actualizado. Los cambios se aplican desde {self.nombre_actual}."
            )
        if (
            meses.obtener_mes_por_fecha(self.app.con, self.anio_actual, self.mes_actual)
            is None
        ):
            return (
                f"Plan creado. No se agregaron cuotas: {self.nombre_actual} todavía no existe. "
                "La cuota aparecerá al crear ese mes."
            )
        plan = cuotas.obtener_plan(self.app.con, plan_id)
        if cuotas.activo_en(self.app.con, plan, self.anio_actual, self.mes_actual):
            n = cuotas.numero_de_cuota(plan, self.anio_actual, self.mes_actual)
            return (
                f"Plan creado. Se agregó la cuota {n}/{plan['cantidad_cuotas']} "
                f"en {self.nombre_actual}."
            )
        return "Plan creado."

    def _enfocar_error(self) -> None:
        self.app.page.update()
        orden = [
            (self.nombre, self.nombre.error),
            (self.categoria, self.categoria.error_text),
            (self.monto, self.monto.error),
            (self.cantidad, self.cantidad.error),
            (self.primer_anio, self.primer_anio.error),
        ]
        for campo, error in orden:
            if error:
                self.app.enfocar(campo)
                return
