"""Importar Excel (v2): elegir archivo y hoja (RF-49, RF-50, RF-58, docs/diseno.md §3.11).

Es una pantalla completa, sin menú ni barra superior, como el primer uso. Se
abre desde el primer uso o desde Ajustes, y "Cancelar" vuelve a ese lugar.

Paso 8b: termina mostrando cuántas filas se detectaron. La lista de revisión
(§3.12) llega en el paso 8c.
"""

import asyncio
from pathlib import Path

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import aviso_en_pantalla, texto_ayuda
from app.logica.errores import ErrorDeValidacion
from app.logica.importar_excel import (
    MENSAJE_ARCHIVO_INVALIDO,
    HojaLeida,
    LibroExcel,
    abrir_libro,
    es_nombre_xlsx,
    mensaje_sin_datos,
)


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

        self.tarjeta = ft.Column(spacing=16, tight=True)
        self.control = ft.Container(
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
        """Paso 8b: por ahora solo la cantidad. En el 8c va la lista de revisión."""
        # Se cuentan como en la lista: los títulos de bloque no son filas (RN-65).
        completas = sum(1 for f in hoja.filas if f.completa)
        incompletas = sum(1 for f in hoja.filas if not f.completa and not f.es_titulo)
        # O83: "1 fila" en singular (y "1 fila incompleta").
        def filas(n: int, final: str = "") -> str:
            return f"1 fila{final}" if n == 1 else f"{n} filas{final and final + 's'}"

        texto = (
            f"En la hoja {hoja.nombre} se detectaron {filas(completas)} con texto y "
            f"monto, y {filas(incompletas, ' incompleta')}."
        )
        self._dibujar(
            [
                self._linea_archivo(),
                aviso_en_pantalla(
                    self.app.page, "info", ft.Icons.INFO_OUTLINE, texto
                ),
                self._botones(self._cancelar_boton()),
            ]
        )

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

    def cancelar(self) -> None:
        """Cancelar o Esc: vuelve a donde se abrió, sin guardar nada (§3.14).
        En el paso de elegir archivo no hay nada que perder: no se pregunta."""
        if self.ocupada:
            return
        self.app.salir_de_importacion(self.origen)
