"""Importar Excel (v2): elegir archivo y hoja (RF-49, RF-50, RF-58, docs/diseno.md §3.11).

Es una pantalla completa, sin menú ni barra superior, como el primer uso. Se
abre desde el primer uso o desde Ajustes, y "Cancelar" vuelve a ese lugar.

Después de elegir la hoja se muestra la lista de revisión (lista_revision.py).
"Confirmar importación" abre el resumen previo, guarda todo o nada y muestra el
resultado (§3.13). Cancelar pregunta si hubo cambios en la revisión (§3.14).
"""

import asyncio
from pathlib import Path

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import aviso_en_pantalla, texto_ayuda
from app.interfaz.lista_revision import VistaRevision
from app.logica import confirmar_importacion
from app.logica.confirmar_importacion import AVISO_SIN_DESHACER, MENSAJE_ERROR
from app.logica.errores import ErrorDeValidacion
from app.logica.importar_excel import (
    MENSAJE_ARCHIVO_INVALIDO,
    HojaLeida,
    LibroExcel,
    abrir_libro,
    es_nombre_xlsx,
    mensaje_sin_datos,
)
from app.logica.formato import nombre_mes
from app.logica.revision_importacion import ListaRevision


class PantallaImportar:
    def __init__(self, app, origen: str) -> None:
        """origen: "primer_uso" o "ajustes" (adónde vuelve "Cancelar")."""
        self.app = app
        self.origen = origen
        self.libro: LibroExcel | None = None
        self.nombre_archivo: str | None = None
        # True mientras se elige o se lee el archivo: evita abrir dos selectores
        # o leer dos veces si se hace doble clic, y que Esc cancele a mitad.
        self.ocupada = False
        # La lista de revisión, cuando ya se eligió la hoja (si no, None).
        self.vista: VistaRevision | None = None
        self.lista: ListaRevision | None = None
        # True mientras se guarda la importación: los botones del resumen previo
        # quedan apagados y Esc no lo cierra (§3.13, "Mientras guarda").
        self.guardando = False

        self.tarjeta = ft.Column(spacing=16, tight=True)
        # La tarjeta de elegir archivo, centrada. La lista de revisión ocupa toda
        # la ventana: al mostrarla se cambia el contenido de self.control.
        self._elegir = ft.Container(
            expand=True,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                [
                    ft.Text(
                        "Importar desde Excel",
                        size=estilos.TAM_TITULO,
                        weight=ft.FontWeight.W_600,
                    ),
                    texto_ayuda(
                        "Elegí un archivo .xlsx. "
                        "Antes de guardar nada vas a poder revisar todo."
                    ),
                    ft.Card(
                        width=520,
                        content=ft.Container(padding=24, content=self.tarjeta),
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
                spacing=16,
            ),
        )
        self.control = ft.Container(expand=True, content=self._elegir)
        self._mostrar_inicio()

    # ------------------------------------------------------------------
    # Estados de la tarjeta
    # ------------------------------------------------------------------

    def _botones(self, *botones: ft.Control) -> ft.Row:
        return ft.Row(list(botones), alignment=ft.MainAxisAlignment.END)

    def _cancelar_boton(self) -> ft.TextButton:
        return ft.TextButton("Cancelar", on_click=lambda e: self.cancelar())

    def _dibujar(self, controles: list[ft.Control]) -> None:
        self.tarjeta.controls = controles
        self.app.page.update()

    def _mostrar_inicio(self, aviso: ft.Control | None = None) -> None:
        """Sin archivo todavía. Con aviso: el archivo anterior tuvo un problema."""
        self.libro = None
        self.nombre_archivo = None
        self.vista = self.lista = None
        self.control.content = self._elegir
        # Con un error, el botón dice "Elegir otro archivo" (§3.11).
        texto = "Elegir otro archivo" if aviso else "Elegir archivo..."
        controles = [
            ft.Icon(ft.Icons.TABLE_VIEW, size=40, color=estilos.TEXTO_SECUNDARIO),
            ft.Text(
                "El archivo solo se lee: no se modifica, no se copia "
                "y no se guarda en la app."
            ),
        ]
        if aviso:
            controles.append(aviso)
        controles += [
            ft.Row(
                [
                    ft.FilledButton(
                        texto,
                        icon=ft.Icons.UPLOAD_FILE,
                        autofocus=True,
                        on_click=lambda e: self.elegir_archivo(),
                    )
                ],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            self._botones(self._cancelar_boton()),
        ]
        self._dibujar(controles)

    def _mostrar_leyendo(self) -> None:
        # Mientras lee no hay botones habilitados: solo se espera (§3.11).
        self._dibujar(
            [
                ft.Row(
                    [
                        ft.ProgressRing(width=20, height=20, stroke_width=2),
                        ft.Text("Leyendo el archivo..."),
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                self._botones(ft.TextButton("Cancelar", disabled=True)),
            ]
        )

    def _linea_archivo(self) -> ft.Row:
        return ft.Row(
            [
                ft.Text(f"Archivo: {self.nombre_archivo}", expand=True),
                ft.TextButton("Elegir otro", on_click=lambda e: self._mostrar_inicio()),
            ]
        )

    def _mostrar_hojas(self, hojas: list[str], aviso: ft.Control | None = None) -> None:
        """El archivo tiene varias hojas con datos: se elige una (RF-50)."""
        elegida = self.selector_hojas.value if aviso else hojas[0]
        self.selector_hojas = ft.RadioGroup(
            value=elegida,
            content=ft.Column(
                [ft.Radio(value=h, label=h) for h in hojas],
                # Con muchas hojas, la lista tiene alto fijo y scroll propio (§3.11).
                height=240 if len(hojas) > 8 else None,
                scroll=ft.ScrollMode.AUTO if len(hojas) > 8 else None,
                spacing=0,
            ),
        )
        controles = [
            self._linea_archivo(),
            ft.Text(f"El archivo tiene {len(hojas)} hojas. ¿Cuál querés importar?"),
            self.selector_hojas,
            texto_ayuda(
                "Se importa una hoja por vez. Si querés otra, repetís la importación."
            ),
        ]
        if aviso:
            controles.append(aviso)
        controles.append(
            self._botones(
                self._cancelar_boton(),
                # autofocus: así Enter lo activa sin tener que buscarlo.
                ft.FilledButton(
                    "Revisar filas",
                    autofocus=True,
                    on_click=lambda e: self.revisar_hoja(hojas),
                ),
            )
        )
        self._dibujar(controles)

    def _mostrar_lista(self, hoja: HojaLeida) -> None:
        """La lista de revisión de la hoja elegida (§3.12), a toda la ventana."""
        # Una lista nueva cada vez: una ya confirmada no se puede reusar (O81).
        self.lista = ListaRevision(self.app.con, hoja)
        self.vista = VistaRevision(
            self.app,
            self.lista,
            self.nombre_archivo,
            al_cambiar_archivo=self.cambiar_archivo,
            al_cancelar=self.cancelar,
            al_confirmar=self.confirmar,
        )
        self.control.content = self.vista.control
        self.app.page.update()

    def _aviso_archivo_invalido(self) -> ft.Control:
        return aviso_en_pantalla(
            self.app.page, "negativo", ft.Icons.ERROR_OUTLINE, MENSAJE_ARCHIVO_INVALIDO
        )

    def _aviso_sin_datos(self, nombre_hoja: str) -> ft.Control:
        return aviso_en_pantalla(
            self.app.page,
            "pendiente",
            ft.Icons.WARNING_AMBER,
            mensaje_sin_datos(nombre_hoja),
        )

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------

    def elegir_archivo(self) -> None:
        """Botón "Elegir archivo...". El selector del sistema es asíncrono:
        run_task lo ejecuta sin trabar la ventana."""
        if self.ocupada:
            return
        # Se marca ya, al hacer clic: si se marcara cuando la tarea empieza, dos
        # clics muy rápidos alcanzarían a encolar dos tareas (O82).
        self.ocupada = True
        self.app.page.run_task(self._elegir_y_leer)

    async def _elegir_y_leer(self) -> None:
        self.ocupada = True
        try:
            archivos = await self.app.selector_de_archivos().pick_files(
                dialog_title="Elegir una planilla de Excel",
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["xlsx"],
                # Con los bytes se puede leer aunque no haya ruta: en la ventana
                # de Edge (modo navegador) el selector nunca da la ruta.
                with_data=True,
            )
            if not archivos:
                return  # Cerró el selector sin elegir: todo queda como estaba.
            archivo = archivos[0]
            await self.leer_archivo(archivo.name, archivo.bytes, archivo.path)
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            self.app.error_inesperado(error)
        finally:
            self.ocupada = False

    async def leer_archivo(
        self, nombre: str, contenido: bytes | None, ruta: str | None = None
    ) -> None:
        """Abre el archivo elegido y decide qué sigue (§3.11, "Después de elegir").

        Separado de _elegir_y_leer para poder probarlo sin abrir el selector.
        """
        self.ocupada = True
        try:
            # El selector filtra .xlsx, pero igual se controla (RN-60): en algunos
            # sistemas se puede escribir cualquier nombre en el selector.
            if not es_nombre_xlsx(nombre):
                self._mostrar_inicio(self._aviso_archivo_invalido())
                return
            self._mostrar_leyendo()
            try:
                # Leer un Excel grande tarda: se hace en otro hilo (to_thread) para
                # que la ventana siga respondiendo y se vea "Leyendo el archivo...".
                if contenido is None and ruta:
                    contenido = await asyncio.to_thread(Path(ruta).read_bytes)
                if contenido is None:
                    raise ErrorDeValidacion(MENSAJE_ARCHIVO_INVALIDO)
                libro = await asyncio.to_thread(abrir_libro, contenido)
                hojas = await asyncio.to_thread(libro.hojas)
            except (ErrorDeValidacion, OSError):
                self._mostrar_inicio(self._aviso_archivo_invalido())
                return
            self.libro, self.nombre_archivo = libro, nombre

            if not hojas:
                # Ninguna hoja tiene datos (RN-60). Si ni siquiera hay hojas, el
                # archivo es raro: se trata como no válido.
                primera = libro.primera_hoja()
                aviso = (
                    self._aviso_sin_datos(primera)
                    if primera
                    else self._aviso_archivo_invalido()
                )
                self._mostrar_inicio(aviso)
                return
            if len(hojas) == 1:
                # Una sola hoja: no se pregunta nada (CA-50.1).
                await self._leer_hoja(hojas[0], hojas)
            else:
                self._mostrar_hojas(hojas)
        finally:
            self.ocupada = False

    def revisar_hoja(self, hojas: list[str]) -> None:
        """Botón "Revisar filas" con la hoja elegida."""
        if self.ocupada:
            return
        self.ocupada = True  # Ya al hacer clic, como en elegir_archivo (O82).
        self.app.page.run_task(self._revisar_hoja, self.selector_hojas.value, hojas)

    async def _revisar_hoja(self, nombre_hoja: str, hojas: list[str]) -> None:
        self.ocupada = True
        try:
            await self._leer_hoja(nombre_hoja, hojas)
        finally:
            self.ocupada = False

    async def _leer_hoja(self, nombre_hoja: str, hojas: list[str]) -> None:
        self._mostrar_leyendo()
        try:
            hoja = await asyncio.to_thread(self.libro.leer_hoja, nombre_hoja)
        except Exception:  # noqa: BLE001 (un .xlsx dañado por dentro puede fallar acá)
            self._mostrar_inicio(self._aviso_archivo_invalido())
            return
        if hoja.sin_datos:
            aviso = self._aviso_sin_datos(nombre_hoja)
            if len(hojas) == 1:
                self._mostrar_inicio(aviso)
            else:
                # Entre varias: el aviso va debajo de las hojas y se puede elegir otra.
                self._mostrar_hojas(hojas, aviso)
            return
        self._mostrar_lista(hoja)

    # ------------------------------------------------------------------
    # Confirmar: resumen previo, guardado y resultado (§3.13)
    # ------------------------------------------------------------------

    def confirmar(self) -> None:
        """"Confirmar importación" (o Ctrl+Enter): abre el resumen previo."""
        if self.vista is None or self.lista is None or self.app.hay_dialogo_abierto():
            return
        lineas = confirmar_importacion.resumen_previo(self.lista)
        # El aviso de "no se puede deshacer" va aparte, como aviso info. La
        # primera línea (el mes) y las del final van sin viñeta, como en §3.13.
        lineas = [linea for linea in lineas if linea != AVISO_SIN_DESHACER]
        controles: list[ft.Control] = [ft.Text(lineas[0])]
        for linea in lineas[1:]:
            if linea.startswith(("Se crean también", "No se importa")):
                controles.append(ft.Text(linea))
            elif linea.startswith("Sin sueldo"):
                # Algo que queda por completar: color pendiente, sin viñeta (O93).
                controles.append(
                    ft.Text(linea, color=estilos.color(self.app.page, "pendiente"))
                )
            else:
                controles.append(ft.Text(f"•  {linea}"))
        controles.append(
            aviso_en_pantalla(
                self.app.page, "info", ft.Icons.INFO_OUTLINE, AVISO_SIN_DESHACER
            )
        )
        self.progreso = ft.ProgressRing(
            width=20, height=20, stroke_width=2, visible=False
        )
        self.boton_volver = ft.TextButton(
            "Volver a la revisión",
            # Foco en la opción segura: un Enter sin pensar no importa nada (§5).
            autofocus=True,
            on_click=lambda e: self._volver_a_la_revision(),
        )
        self.boton_importar = ft.FilledButton(
            "Importar", on_click=lambda e: self.importar()
        )
        self.dialogo_resumen = ft.AlertDialog(
            modal=True,
            title=ft.Text("Revisá antes de importar"),
            content=ft.Column(controles, tight=True, width=520, spacing=12),
            actions=[self.progreso, self.boton_volver, self.boton_importar],
            actions_alignment=ft.MainAxisAlignment.END,
            # Esc mientras guarda: devolver True deja el diálogo abierto (O86).
            data=lambda: self.guardando,
        )
        self.app.abrir_dialogo(self.dialogo_resumen)

    def _volver_a_la_revision(self) -> None:
        if not self.guardando:
            self.app.cerrar_dialogo(self.dialogo_resumen)

    def importar(self) -> None:
        """Botón "Importar" del resumen previo."""
        if self.guardando:
            return
        # Se marca ya, al hacer clic: un doble clic no guarda dos veces (como O82).
        self.guardando = True
        self.progreso.visible = True
        self.boton_volver.disabled = self.boton_importar.disabled = True
        self.app.page.update()
        self.app.page.run_task(self._guardar)

    async def _guardar(self) -> None:
        try:
            # En otro hilo, para que la ruedita se vea mientras se guarda.
            resultado = await asyncio.to_thread(
                confirmar_importacion.confirmar, self.lista
            )
        except Exception as error:  # noqa: BLE001 (todo error va al mismo diálogo)
            self.guardando = False
            self.app.cerrar_dialogo(self.dialogo_resumen)
            # confirmar() envuelve la causa real en ErrorDeValidacion(MENSAJE_ERROR):
            # el detalle técnico útil es el de la causa. La revisión queda igual.
            self.app.error_inesperado(
                error.__cause__ or error,
                titulo="No se pudo importar",
                mensaje=MENSAJE_ERROR,
                texto_boton="Volver a la revisión",
            )
            return
        self.guardando = False
        self.app.cerrar_dialogo(self.dialogo_resumen)
        self._mostrar_resultado(resultado)

    def _mostrar_resultado(self, resultado: confirmar_importacion.Resultado) -> None:
        principal, completar = confirmar_importacion.texto_resultado(resultado)
        controles: list[ft.Control] = [ft.Text(principal)]
        if completar:
            controles.append(ft.Text("Para completar:", weight=ft.FontWeight.W_600))
            controles += [texto_ayuda(f"•  {linea}") for linea in completar]
        # Solo "me deben" o sueldo: se va al Resumen; si no, a Gastos (§3.13).
        pantalla = "Gastos" if resultado.pantalla == "gastos" else "Resumen"

        def ver() -> bool:
            self.app.cerrar_dialogo(dialogo)
            self.app.mostrar_importado(resultado.mes_id, pantalla)
            return True  # Para Esc: el diálogo ya se cerró acá.

        dialogo = ft.AlertDialog(
            modal=True,
            title=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.CHECK_CIRCLE,
                        color=estilos.color(self.app.page, "positivo"),
                    ),
                    ft.Text("Importación terminada"),
                ]
            ),
            content=ft.Column(controles, tight=True, width=520, spacing=8),
            actions=[
                ft.FilledButton(
                    f"Ver {nombre_mes(resultado.anio, resultado.mes)}",
                    autofocus=True,
                    on_click=lambda e: ver(),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            # Lo importado ya está guardado: Esc también lleva al mes, para no
            # quedar en una revisión que ya no se puede usar.
            data=ver,
        )
        self.app.abrir_dialogo(dialogo)

    # ------------------------------------------------------------------
    # Teclado, cancelar y cambiar archivo (§3.14)
    # ------------------------------------------------------------------

    def al_presionar_tecla(self, e: ft.KeyboardEvent) -> None:
        """Teclas durante la importación (los atajos de la app no actúan)."""
        if e.key == "Escape":
            # Con la fila de "nueva categoría" abierta, Esc cierra solo esa fila.
            if self.vista is not None and self.vista.cerrar_en_linea():
                return
            self.cancelar()
            return
        es_mac = self.app.page.platform == ft.PagePlatform.MACOS
        if (e.meta if es_mac else e.ctrl) and e.key == "Enter" and self.vista is not None:
            self.vista.confirmar()

    def cancelar(self) -> None:
        """Cancelar o Esc: vuelve a donde se abrió, sin guardar nada (§3.14).
        Si hubo cambios en la revisión, pregunta antes."""
        if self.ocupada or self.guardando:
            return
        if self.lista is None or not self.lista.hubo_cambios:
            self.app.salir_de_importacion(self.origen)
            return
        explicacion = (
            "Se pierden los cambios que hiciste en la revisión. No se guarda nada."
        )
        nuevas = self.lista.categorias_nuevas + self.lista.personas_nuevas
        if nuevas:
            nombres = ", ".join(n.nombre for n in nuevas)
            explicacion += (
                f"\nTambién se descartan las categorías y personas nuevas: {nombres}."
            )
        self.app.confirmar(
            "¿Descartar la importación?",
            explicacion,
            "Descartar",
            lambda: self.app.salir_de_importacion(self.origen),
            texto_volver="Seguir revisando",
        )

    def cambiar_archivo(self) -> None:
        """"Cambiar archivo u hoja" en la revisión: vuelve a elegir el archivo."""
        if self.lista is None or not self.lista.hubo_cambios:
            self._mostrar_inicio()
            return
        self.app.confirmar(
            "¿Volver a elegir el archivo?",
            "Se pierden los cambios que hiciste en la revisión.",
            "Volver a elegir",
            self._mostrar_inicio,
            texto_volver="Seguir revisando",
        )
