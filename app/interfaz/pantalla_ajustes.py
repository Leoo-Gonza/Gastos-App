"""Ajustes: categorías, medios de pago, personas, meta de ahorro, apariencia e
importar Excel (RF-10, RF-11, RF-28, RF-36, RF-49, docs/diseno.md §3.10)."""

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import (
    campo_monto,
    dialogo_formulario,
    leer_campo_monto,
    texto_ayuda,
    titulo,
)
from app.logica import catalogos, configuracion
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_monto_para_editar, formatear_usd

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
    # "persona" es femenino para cualquier persona: "archivada" vale para todos.
    catalogos.PERSONAS: {
        "singular": "persona",
        "nuevo": "Nueva persona",
        "archivado": "Archivada",
        "mostrar": "Mostrar archivadas",
        "tooltip_archivar": "Tiene gastos compartidos o ítems en Me deben: no se puede "
        "borrar. Archivada no aparece al compartir gastos nuevos.",
        "eliminar": "¿Eliminar a la persona {}?",
        "vacio": "No hay personas. Agregá a las personas con las que compartís gastos.",
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


class PestanaMeta:
    """Pestaña "Meta de ahorro" (RF-36, §3.10): el campo de la meta, sin diálogo."""

    def __init__(self, app) -> None:
        self.app = app
        self.campo = campo_monto(
            "Meta de ahorro mensual",
            "USD",
            hint_text="Ej.: 300,00",
            width=320,
            on_submit=lambda e: self.guardar(),
        )
        self.boton_quitar = ft.TextButton(
            "Quitar meta", on_click=lambda e: self.quitar()
        )
        self.control = ft.Column(
            [
                texto_ayuda("Es la misma meta para todos los meses."),
                self.campo,
                ft.Row(
                    [
                        ft.FilledButton(
                            "Guardar meta", on_click=lambda e: self.guardar()
                        ),
                        self.boton_quitar,
                    ]
                ),
            ],
            spacing=16,
        )

    def refrescar(self) -> None:
        meta = configuracion.obtener_meta(self.app.con)
        self.campo.value = formatear_monto_para_editar(meta) if meta is not None else ""
        self.campo.error = None
        self.boton_quitar.visible = meta is not None
        self.app.page.update()

    def nuevo(self) -> None:
        """Atajo Ctrl+N en esta pestaña: lleva el cursor al campo."""
        self.app.enfocar(self.campo)

    def guardar(self) -> None:
        self.campo.error = None
        if not (self.campo.value or "").strip():
            self.campo.error = "Ingresá la meta."
        else:
            meta = leer_campo_monto(self.campo, que="La meta")
            if meta is not None:
                try:
                    configuracion.guardar_meta(self.app.con, meta)
                except ErrorDeValidacion as error:
                    self.campo.error = str(error)
        if self.campo.error:
            self.app.page.update()
            self.app.enfocar(self.campo)
            return
        self.refrescar()
        self.app.avisar(f"Meta de ahorro: {formatear_usd(meta)}")

    def quitar(self) -> None:
        configuracion.quitar_meta(self.app.con)
        self.refrescar()
        self.app.avisar("Meta de ahorro quitada")


class PestanaApariencia:
    """Pestaña "Apariencia" (§3.10): tema claro, oscuro o como el sistema."""

    def __init__(self, app) -> None:
        self.app = app
        self.opciones = ft.RadioGroup(
            content=ft.Column(
                [
                    ft.Radio(value="claro", label="Claro"),
                    ft.Radio(value="oscuro", label="Oscuro"),
                    ft.Radio(value="sistema", label="Como el sistema"),
                ]
            ),
            on_change=lambda e: self.elegir(e.control.value),
        )
        self.control = ft.Column(
            [
                self.opciones,
                texto_ayuda(
                    f"Atajos: {app.atajo('N')} nuevo, {app.atajo('K')} cotización, "
                    f"{app.atajo('N', shift=True)} mes nuevo, Alt+← / Alt+→ cambiar de mes."
                ),
            ],
            spacing=16,
        )

    def refrescar(self) -> None:
        self.opciones.value = configuracion.obtener_tema(self.app.con)
        self.app.page.update()

    def nuevo(self) -> None:
        """Ctrl+N no tiene acción en esta pestaña."""

    def elegir(self, tema: str) -> None:
        configuracion.guardar_tema(self.app.con, tema)
        estilos.aplicar_tema(self.app.page, tema)
        # Algunos colores se eligen al dibujar: se vuelve a armar la ventana con
        # el tema nuevo, sin perder el mes ni la pantalla.
        self.app.mostrar_principal(self.app.mes_id)
        # BUG-23: la pantalla de Ajustes se armó de nuevo y arrancaría en la
        # primera pestaña: se vuelve a Apariencia para ver lo que se eligió.
        if self.app.mes_id is not None:
            ajustes = self.app.pantalla("Ajustes")
            ajustes.pestanas.selected_index = ajustes.indice_de(ajustes.apariencia)
            ajustes.refrescar()
            self.app.page.update()
        self.app.avisar("Tema actualizado")


class PestanaImportar:
    """Pestaña "Importar Excel" (v2, §3.10): explica y abre la importación."""

    def __init__(self, app) -> None:
        self.app = app
        puntos = [
            "Antes de guardar, revisás y corregís todo fila por fila.",
            "El archivo no se modifica ni se guarda en la app.",
            "Lo importado se agrega al mes que elijas: "
            "no se borra nada de lo que ya cargaste.",
            "Si importás dos veces la misma planilla, "
            "las filas repetidas vienen destildadas.",
        ]
        self.control = ft.Column(
            [
                ft.Text(
                    "Importar desde Excel",
                    size=estilos.TAM_SECCION,
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(
                    "Traé gastos, cuotas, lo que te deben y el sueldo "
                    "desde una planilla .xlsx."
                ),
                ft.Column([texto_ayuda(f"•  {p}") for p in puntos], spacing=4),
                ft.Row(
                    [
                        ft.FilledButton(
                            "Importar Excel",
                            icon=ft.Icons.UPLOAD_FILE,
                            on_click=lambda e: app.mostrar_importacion("ajustes"),
                        )
                    ]
                ),
            ],
            spacing=16,
        )

    def refrescar(self) -> None:
        """No muestra datos de la base: no hay nada que refrescar."""

    def nuevo(self) -> None:
        """Ctrl+N no tiene acción en esta pestaña (§3.10)."""


class PantallaAjustes:
    def __init__(self, app) -> None:
        self.app = app
        self.listas = [
            ListaCatalogo(app, catalogos.CATEGORIAS),
            ListaCatalogo(app, catalogos.MEDIOS_PAGO),
            ListaCatalogo(app, catalogos.PERSONAS),
        ]
        self.meta = PestanaMeta(app)
        self.apariencia = PestanaApariencia(app)
        self.importar = PestanaImportar(app)
        # Todas las pestañas, en el orden en que se ven.
        self._pestanas = [*self.listas, self.meta, self.apariencia, self.importar]
        # En Flet 1.0 las pestañas son tres piezas: Tabs (el conjunto),
        # TabBar (los títulos) y TabBarView (el contenido de cada una).
        self.pestanas = ft.Tabs(
            length=len(self._pestanas),
            selected_index=0,
            expand=True,
            on_change=lambda e: self.refrescar(),
            content=ft.Column(
                [
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Categorías"),
                            ft.Tab(label="Medios de pago"),
                            ft.Tab(label="Personas"),
                            ft.Tab(label="Meta de ahorro"),
                            ft.Tab(label="Apariencia"),
                            ft.Tab(label="Importar Excel"),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True, controls=[p.control for p in self._pestanas]
                    ),
                ],
                expand=True,
            ),
        )
        self.control = ft.Column(
            [titulo("Ajustes"), self.pestanas], spacing=16, expand=True
        )

    def indice_de(self, pestana) -> int:
        """Posición de una pestaña (para elegirla sin escribir el número a mano)."""
        return self._pestanas.index(pestana)

    def _lista_visible(self):
        return self._pestanas[self.pestanas.selected_index or 0]

    def refrescar(self) -> None:
        # Se refrescan todas: así al cambiar de pestaña ya está actualizada.
        for pestana in self._pestanas:
            pestana.refrescar()

    def nuevo(self) -> None:
        """Atajo Ctrl+N: nuevo elemento en la pestaña visible."""
        self._lista_visible().nuevo()
