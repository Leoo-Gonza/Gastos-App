"""Importar Excel (v2): editar una fila, cambiar un bloque y crear categorías o
personas durante la revisión (docs/diseno.md §4.9, §4.10 y §4.11).

Nada de esto escribe en la base: todo cambia la ListaRevision en memoria.
"""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import campo_monto, dialogo_formulario, texto_ayuda
from app.logica import catalogos, cuotas
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_monto_para_editar, formatear_usd, leer_monto
from app.logica.revision_importacion import TIPOS, TIPOS_GASTO, ListaRevision, Nueva

# Valor del selector cuando no se eligió nada (distinto de "categoría por defecto").
SIN_ELEGIR = object()
_DEFECTO = "defecto"


def clave_de(valor) -> str | None:
    """El valor de un dropdown para un id, una Nueva o "por defecto" (None)."""
    if valor is SIN_ELEGIR:
        return None
    if valor is None:
        return _DEFECTO
    if isinstance(valor, Nueva):
        return f"nueva:{valor.nombre}"
    return f"id:{valor}"


class SelectorConNueva:
    """Dropdown de categorías o personas con "+" para agregar una nueva en línea
    (§4.11). La nueva no se guarda en la base: queda en la lista de la revisión.

    con_defecto: agrega la primera opción "Categoría por defecto (Varios)".
    """

    def __init__(
        self,
        app,
        lista: ListaRevision,
        tabla: str,
        label: str,
        con_defecto: bool = False,
        al_cambiar: Callable[[], None] | None = None,
    ) -> None:
        self.app = app
        self.lista = lista
        self.tabla = tabla
        self.con_defecto = con_defecto
        self.al_cambiar = al_cambiar
        es_categoria = tabla == catalogos.CATEGORIAS
        self.dropdown = ft.Dropdown(
            label=label, expand=True, on_select=lambda e: self._cambio()
        )
        self.nombre = ft.TextField(
            label="Nombre de la categoría" if es_categoria else "Nombre de la persona",
            expand=True,
            max_length=60,
            on_submit=lambda e: self.agregar(),
        )
        self.fila_nueva = ft.Column(
            [
                ft.Row(
                    [
                        self.nombre,
                        ft.TextButton("Agregar", on_click=lambda e: self.agregar()),
                        ft.TextButton("Cancelar", on_click=lambda e: self.cerrar()),
                    ]
                ),
                texto_ayuda("Se crea al confirmar la importación. Si cancelás, no se crea."),
            ],
            spacing=4,
            visible=False,
        )
        self.control = ft.Column(
            [
                ft.Row(
                    [
                        self.dropdown,
                        ft.IconButton(
                            ft.Icons.ADD,
                            tooltip="Nueva categoría" if es_categoria else "Nueva persona",
                            on_click=lambda e: self.abrir(),
                        ),
                    ]
                ),
                self.fila_nueva,
            ],
            spacing=4,
        )
        self.cargar_opciones()

    def _nuevas(self) -> list[Nueva]:
        if self.tabla == catalogos.CATEGORIAS:
            return self.lista.categorias_nuevas
        return self.lista.personas_nuevas

    def cargar_opciones(self) -> None:
        opciones = []
        if self.con_defecto:
            defecto = self.lista.categoria_defecto
            if isinstance(defecto, Nueva):
                nombre = defecto.nombre
            else:
                nombre = next(
                    (
                        c["nombre"]
                        for c in catalogos.listar(self.app.con, self.tabla)
                        if c["id"] == defecto
                    ),
                    "sin elegir",
                )
            opciones.append(
                ft.DropdownOption(key=_DEFECTO, text=f"Categoría por defecto ({nombre})")
            )
        opciones += [
            ft.DropdownOption(key=f"id:{c['id']}", text=c["nombre"])
            for c in catalogos.listar(self.app.con, self.tabla)
        ]
        opciones += [
            ft.DropdownOption(key=clave_de(n), text=f"{n.nombre} (nueva)")
            for n in self._nuevas()
        ]
        self.dropdown.options = opciones

    @property
    def valor(self):
        """Un id, una Nueva, None (categoría por defecto) o SIN_ELEGIR."""
        clave = self.dropdown.value
        if clave is None:
            return SIN_ELEGIR
        if clave == _DEFECTO:
            return None
        if clave.startswith("nueva:"):
            nombre = clave.removeprefix("nueva:")
            return next(n for n in self._nuevas() if n.nombre == nombre)
        return int(clave.removeprefix("id:"))

    @valor.setter
    def valor(self, valor) -> None:
        clave = clave_de(valor)
        # Si ya no está entre las opciones (ej. se archivó), queda sin elegir.
        claves = {o.key for o in self.dropdown.options}
        self.dropdown.value = clave if clave in claves else None

    def _cambio(self) -> None:
        self.dropdown.error_text = None
        if self.al_cambiar:
            self.al_cambiar()

    def abrir(self) -> None:
        self.fila_nueva.visible = True
        self.app.page.update()
        self.app.enfocar(self.nombre)

    def cerrar(self) -> bool:
        """Cierra la fila de "nueva". Devuelve True si estaba abierta."""
        if not self.fila_nueva.visible:
            return False
        self.fila_nueva.visible = False
        self.nombre.value = ""
        self.nombre.error = None
        self.app.page.update()
        return True

    def agregar(self) -> None:
        self.nombre.error = None
        try:
            if self.tabla == catalogos.CATEGORIAS:
                nueva = self.lista.agregar_categoria(self.nombre.value or "")
            else:
                nueva = self.lista.agregar_persona(self.nombre.value or "")
        except ErrorDeValidacion as error:
            self.nombre.error = str(error)
            self.app.page.update()
            self.app.enfocar(self.nombre)
            return
        self.cargar_opciones()
        self.valor = nueva  # Queda elegida (§4.11).
        self.cerrar()
        self._cambio()


def _leer_entero(campo: ft.TextField) -> int | None:
    texto = (campo.value or "").strip()
    if not texto.isdigit():
        return None
    if len(texto) > 6:
        # Python no convierte textos de miles de dígitos (BUG-37). Cualquier
        # número así ya pasa el tope: la lógica dice "demasiado grande".
        return cuotas.MAXIMO_CUOTAS + 1
    return int(texto)


class DialogoFilaImportacion:
    """"Editar fila 12 del Excel" (§4.9). al_aceptar() se llama si cambió algo."""

    def __init__(self, app, lista: ListaRevision, indice: int, al_aceptar: Callable) -> None:
        self.app = app
        self.lista = lista
        self.indice = indice
        self.al_aceptar = al_aceptar
        fila = lista.filas[indice]
        numero = fila.origen.fila_excel

        self.tipo = ft.Dropdown(
            label="Tipo",
            value=fila.tipo,
            options=[ft.DropdownOption(key=k, text=t) for k, t in TIPOS.items()],
            on_select=lambda e: self._mostrar_segun_tipo(),
        )
        self.nombre = ft.TextField(
            label="Nombre", value=fila.nombre or "", max_length=60, on_submit=self._aceptar
        )
        self.monto = campo_monto("Monto", "ARS", on_submit=self._aceptar)
        if fila.monto_cent is not None:
            self.monto.value = formatear_monto_para_editar(fila.monto_cent)
        self.ayuda_sueldo = texto_ayuda(self._texto_sueldo_actual())
        self.pagado = campo_monto("Pagado (opcional)", "ARS", on_submit=self._aceptar)
        if fila.pagado_cent:
            self.pagado.value = formatear_monto_para_editar(fila.pagado_cent)
        self.bloque_pagado = ft.Column(
            [
                self.pagado,
                texto_ayuda("Lo que ya pagaste. Si es igual al monto, queda pagado completo."),
            ],
            spacing=4,
        )
        self.categoria = SelectorConNueva(
            app, lista, catalogos.CATEGORIAS, "Categoría", con_defecto=True
        )
        self.categoria.valor = fila.categoria

        def campo_entero(label: str, valor) -> ft.TextField:
            return ft.TextField(
                label=label,
                value="" if valor is None else str(valor),
                expand=True,
                # El tope es 600 cuotas: 3 dígitos alcanzan, y así no se puede pegar
                # un número tan largo que Python no pueda convertirlo (BUG-37).
                max_length=3,
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.InputFilter(regex_string=r"[0-9]", allow=True),
                on_change=lambda e: self._actualizar_plan(),
                on_submit=self._aceptar,
            )

        self.cuota_actual = campo_entero("Cuota actual", fila.cuota_actual)
        self.cuota_total = campo_entero("Cantidad de cuotas", fila.cuota_total)
        self.texto_plan = texto_ayuda("")
        self.vista_plan = ft.Container(
            padding=12,
            border_radius=8,
            bgcolor=estilos.color(app.page, "info_suave"),
            content=self.texto_plan,
        )
        self.bloque_cuota = ft.Column(
            [
                ft.Row([self.cuota_actual, self.cuota_total], spacing=12),
                texto_ayuda("Ej.: cuota 3 de 12"),
                self.vista_plan,
            ],
            spacing=4,
        )
        self.persona = SelectorConNueva(app, lista, catalogos.PERSONAS, "Persona")
        self.persona.valor = fila.persona if fila.persona is not None else SIN_ELEGIR
        self.cobrado = ft.Switch(label="Ya me lo pagaron (cobrado)", value=fila.cobrado)

        self.dialogo = dialogo_formulario(
            f"Editar fila {numero} del Excel",
            [
                self.tipo,
                self.nombre,
                self.monto,
                self.ayuda_sueldo,
                self.bloque_pagado,
                self.categoria.control,
                self.bloque_cuota,
                self.persona.control,
                self.cobrado,
            ],
            al_guardar=self._aceptar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
            texto_guardar="Aceptar",
            boton_izquierda=ft.TextButton(
                "Volver a lo detectado", on_click=self._restaurar
            ),
        )
        # El diálogo tiene muchos campos: con scroll entra en ventanas bajas.
        self.dialogo.content.scroll = ft.ScrollMode.AUTO
        # Esc con una fila de "nueva" abierta cierra solo esa fila (§4.11, O86).
        self.dialogo.data = lambda: self.categoria.cerrar() or self.persona.cerrar()
        self._mostrar_segun_tipo(actualizar=False)
        self._mostrar_errores(lista.errores_por_campo(fila))

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)
        self._enfocar_primer_error()

    def _texto_sueldo_actual(self) -> str:
        existente = self.lista.mes_existente()
        mes = self.lista.nombre_mes_destino
        if existente is None:
            return f"{mes} todavía no existe."
        return f"Hoy el sueldo de {mes} es {formatear_usd(existente['sueldo_usd_cent'])}."

    def _mostrar_segun_tipo(self, actualizar: bool = True) -> None:
        """Se muestran solo los campos del tipo elegido. Lo escrito en los demás
        se conserva (están ocultos, no borrados), como en §4.1."""
        tipo = self.tipo.value
        es_sueldo = tipo == "sueldo"
        self.monto.label = "Sueldo" if es_sueldo else "Monto"
        self.monto.prefix = "US$ " if es_sueldo else "$ "
        self.monto.suffix = "USD" if es_sueldo else "ARS"
        self.ayuda_sueldo.visible = es_sueldo
        self.bloque_pagado.visible = tipo in TIPOS_GASTO
        self.categoria.control.visible = tipo in TIPOS_GASTO
        self.bloque_cuota.visible = tipo == "cuota"
        self.persona.control.visible = tipo == "me_deben"
        self.cobrado.visible = tipo == "me_deben"
        self._actualizar_plan(actualizar=False)
        if actualizar:
            self.app.page.update()

    def _actualizar_plan(self, actualizar: bool = True) -> None:
        texto = self.lista.texto_plan(
            _leer_entero(self.cuota_actual), _leer_entero(self.cuota_total)
        )
        self.texto_plan.value = texto or ""
        self.vista_plan.visible = texto is not None
        if actualizar:
            self.app.page.update()

    def _limpiar_errores(self) -> None:
        for campo in (self.nombre, self.monto, self.pagado, self.cuota_actual, self.cuota_total):
            campo.error = None
        self.categoria.dropdown.error_text = None
        self.persona.dropdown.error_text = None

    def _mostrar_errores(self, errores: dict[str, str]) -> None:
        self._limpiar_errores()
        if "nombre" in errores:
            self.nombre.error = errores["nombre"]
        if "monto" in errores:
            self.monto.error = errores["monto"]
        if "pagado" in errores:
            self.pagado.error = errores["pagado"]
        if "categoria" in errores:
            self.categoria.dropdown.error_text = errores["categoria"]
        if "persona" in errores:
            self.persona.dropdown.error_text = errores["persona"]
        if "cuota" in errores:
            # El error de "cuota actual" va en ese campo; los demás, en la cantidad.
            if errores["cuota"].startswith("La cuota actual"):
                self.cuota_actual.error = errores["cuota"]
            else:
                self.cuota_total.error = errores["cuota"]

    def _enfocar_primer_error(self) -> None:
        for campo in (self.nombre, self.monto, self.pagado, self.cuota_actual, self.cuota_total):
            if campo.error and campo.visible is not False:
                self.app.enfocar(campo)
                return
        for selector in (self.categoria, self.persona):
            if selector.dropdown.error_text and selector.control.visible:
                self.app.enfocar(selector.dropdown)
                return
        self.app.enfocar(self.nombre)

    def _leer_monto(self, campo: ft.TextField) -> tuple[bool, int | None]:
        """(se_pudo_leer, centavos). Vacío = None. Los montos en 0 los rechaza la
        lógica con su mensaje ("El monto tiene que ser mayor a 0.")."""
        texto = (campo.value or "").strip()
        if not texto:
            return True, None
        try:
            return True, leer_monto(texto, permitir_cero=True)
        except ErrorDeValidacion as error:
            campo.error = str(error)
            return False, None

    def _aceptar(self, e=None) -> None:
        self._limpiar_errores()
        tipo = self.tipo.value
        ok_monto, monto = self._leer_monto(self.monto)
        ok_pagado, pagado = self._leer_monto(self.pagado)
        if not (ok_monto and ok_pagado):
            self.app.page.update()
            self._enfocar_primer_error()
            return
        es_gasto, es_me_deben = tipo in TIPOS_GASTO, tipo == "me_deben"
        categoria = self.categoria.valor if es_gasto else None
        persona = self.persona.valor if es_me_deben else self.lista.filas[self.indice].persona
        errores = self.lista.editar_fila(
            self.indice,
            tipo,
            self.nombre.value,
            monto,
            pagado_cent=pagado if es_gasto else None,
            categoria=None if categoria is SIN_ELEGIR else categoria,
            persona=None if persona is SIN_ELEGIR else persona,
            cuota_actual=_leer_entero(self.cuota_actual) if tipo == "cuota" else None,
            cuota_total=_leer_entero(self.cuota_total) if tipo == "cuota" else None,
            cobrado=self.cobrado.value if es_me_deben else None,
        )
        if errores:
            # Con errores y un tipo que se importa, el diálogo no se cierra (§4.9).
            self._mostrar_errores(errores)
            self.app.page.update()
            self._enfocar_primer_error()
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.al_aceptar()

    def _restaurar(self, e=None) -> None:
        self.lista.restaurar_fila(self.indice)
        self.app.cerrar_dialogo(self.dialogo)
        self.al_aceptar()


class DialogoBloque:
    """"Cambiar las filas de Deudas sofia" (§4.10)."""

    def __init__(self, app, lista: ListaRevision, titulo: str, al_aplicar: Callable) -> None:
        self.app = app
        self.lista = lista
        self.titulo = titulo
        self.al_aplicar = al_aplicar
        filas = next(b.filas for b in lista.bloques() if b.titulo == titulo)
        n = len(filas)

        opciones = [ft.DropdownOption(key="", text="No cambiar el tipo")]
        for clave, texto in TIPOS.items():
            # Cuota y sueldo se eligen fila por fila (§4.10).
            tooltip = {
                "cuota": "La cuota se elige fila por fila.",
                "sueldo": "Solo una fila puede ser el sueldo.",
            }.get(clave)
            opciones.append(
                ft.DropdownOption(
                    key=clave, text=texto, disabled=tooltip is not None, tooltip=tooltip
                )
            )
        self.tipo = ft.Dropdown(
            label="Tipo", value="", options=opciones, on_select=lambda e: self._mostrar()
        )
        self.persona = SelectorConNueva(app, lista, catalogos.PERSONAS, "Persona")
        self.categoria = SelectorConNueva(
            app, lista, catalogos.CATEGORIAS, "Categoría", con_defecto=True
        )
        hay_ignoradas = any(f.tipo == "ignorar" for f in filas)
        filas_texto = "la fila" if n == 1 else f"las {n} filas"
        ayuda = f"Se cambian {filas_texto} de este bloque"
        ayuda += ", incluidas las que están ignoradas." if hay_ignoradas else "."
        ayuda += " Después podés ajustar cada una."

        self.dialogo = dialogo_formulario(
            f"Cambiar las filas de {titulo}",
            [self.tipo, self.persona.control, self.categoria.control, texto_ayuda(ayuda)],
            al_guardar=self._aplicar,
            al_cancelar=lambda e: app.cerrar_dialogo(self.dialogo),
            texto_guardar=f"Aplicar a {filas_texto}",
        )
        self.dialogo.content.width = 420
        self.dialogo.data = lambda: self.categoria.cerrar() or self.persona.cerrar()  # O86
        self._mostrar(actualizar=False)

    def abrir(self) -> None:
        self.app.abrir_dialogo(self.dialogo)

    def _mostrar(self, actualizar: bool = True) -> None:
        tipo = self.tipo.value or None
        self.persona.control.visible = tipo in (None, "me_deben")
        self.categoria.control.visible = tipo in (None, "fijo", "unico")
        if actualizar:
            self.app.page.update()

    def _aplicar(self, e=None) -> None:
        tipo = self.tipo.value or None
        self.persona.dropdown.error_text = None
        persona = self.persona.valor if self.persona.control.visible else SIN_ELEGIR
        categoria = self.categoria.valor if self.categoria.control.visible else SIN_ELEGIR
        try:
            self.lista.cambiar_bloque(
                self.titulo,
                tipo,
                categoria=ListaRevision.SIN_CAMBIO if categoria is SIN_ELEGIR else categoria,
                persona=ListaRevision.SIN_CAMBIO if persona is SIN_ELEGIR else persona,
            )
        except ErrorDeValidacion as error:
            self.persona.dropdown.error_text = str(error)
            self.app.page.update()
            return
        self.app.cerrar_dialogo(self.dialogo)
        self.al_aplicar()
