"""Importar Excel (v2): la lista de revisión (docs/diseno.md §3.12).

Muestra la ListaRevision (app/logica/revision_importacion.py), que es la que
guarda todo lo que el usuario decide. Esta pantalla no calcula nada: cuando algo
cambia, le avisa a la lista y después vuelve a mostrar lo que la lista dice.

Para que no se sienta lenta con muchas filas, cada fila arma sus controles una
sola vez y después solo se les cambian los valores (actualizar()).
"""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import aviso_en_pantalla, texto_ayuda
from app.interfaz.dialogos.dialogo_fila_importacion import (
    DialogoBloque,
    DialogoFilaImportacion,
    SelectorConNueva,
)
from app.logica import catalogos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MESES, formatear_ars, formatear_usd, nombre_mes
from app.logica.revision_importacion import (
    TIPOS,
    TIPOS_GASTO,
    FilaRevision,
    ListaRevision,
    Nueva,
)

# Anchos de las columnas (§3.12, "Encabezado de columnas"). Nombre ocupa el resto.
_ANCHOS = {
    "imp": 48,
    "fila": 48,
    "tipo": 150,
    "monto": 110,
    "pagado": 130,
    "categoria": 150,
    "cuota": 64,
    "accion": 48,
}
_FILTROS = {
    "todas": "Todas",
    "importan": "Se importan",
    "avisos": "Con avisos",
    "errores": "Con errores",
}
# Ícono y color de cada clase de nota (§3.12, "Notas y avisos").
_ESTILO_NOTA = {
    "error": (ft.Icons.ERROR_OUTLINE, "negativo"),
    "aviso": (ft.Icons.WARNING_AMBER, "pendiente"),
    "repetida": (ft.Icons.CONTENT_COPY, "pendiente"),
    "compartido": (ft.Icons.PEOPLE_OUTLINE, "info"),
    "info": (ft.Icons.INFO_OUTLINE, "info"),
    "ignorada": (ft.Icons.INFO_OUTLINE, None),  # None: texto secundario.
}
_CLASES_AVISO = {"aviso", "repetida", "compartido"}


def _celda(
    nombre: str, contenido: ft.Control, alinear=ft.Alignment.CENTER_LEFT
) -> ft.Container:
    return ft.Container(width=_ANCHOS[nombre], content=contenido, alignment=alinear)


class FilaVista:
    """Los controles de una fila. Siempre lee la fila por su índice: "Volver a lo
    detectado" reemplaza el objeto de la fila en la lista."""

    def __init__(self, vista: "VistaRevision", indice: int) -> None:
        self.vista = vista
        self.indice = indice
        page = vista.app.page
        numero = self.fila.origen.fila_excel

        self.tilde = ft.Checkbox(
            on_change=lambda e: vista.cambiar_tilde(indice, e.control.value)
        )
        self.tipo = ft.Dropdown(
            dense=True,
            width=_ANCHOS["tipo"] - 8,
            text_size=14,
            options=[ft.DropdownOption(key=k, text=t) for k, t in TIPOS.items()],
            on_select=lambda e: vista.cambiar_tipo(indice, e.control.value),
        )
        self.nombre = ft.Text(size=estilos.TAM_TEXTO)
        self.notas = ft.Column(spacing=2)
        self.monto = ft.Text(size=estilos.TAM_TEXTO, text_align=ft.TextAlign.RIGHT)
        self.pagado = ft.Text(size=estilos.TAM_TEXTO, text_align=ft.TextAlign.RIGHT)
        self.estado_pagado = ft.Text(
            size=estilos.TAM_AYUDA, text_align=ft.TextAlign.RIGHT
        )
        self.cobrado = ft.Checkbox(
            label="Cobrado",
            on_change=lambda e: vista.cambiar_cobrado(indice, e.control.value),
        )
        self.categoria = ft.Text(size=estilos.TAM_TEXTO)
        self.cuota = ft.Text(size=estilos.TAM_TEXTO)
        self.lapiz = ft.IconButton(
            ft.Icons.EDIT,
            tooltip=f"Editar fila {numero}",
            on_click=lambda e: vista.editar(indice),
        )

        self.control = ft.Container(
            # La clave permite que "Ir al primer error" desplace la lista hasta acá.
            key=ft.ScrollKey(f"fila-{indice}"),
            padding=ft.Padding.symmetric(horizontal=8, vertical=4),
            content=ft.Row(
                [
                    _celda("imp", self.tilde, ft.Alignment.CENTER),
                    _celda(
                        "fila",
                        ft.Text(
                            str(numero),
                            size=estilos.TAM_AYUDA,
                            color=estilos.TEXTO_SECUNDARIO,
                            tooltip=f"Fila {numero} del Excel",
                        ),
                        ft.Alignment.CENTER_RIGHT,
                    ),
                    _celda("tipo", self.tipo),
                    ft.Container(
                        expand=True,
                        # Clic en el nombre también abre la edición (§3.12).
                        on_click=lambda e: vista.editar(indice),
                        content=ft.Column([self.nombre, self.notas], spacing=2),
                    ),
                    _celda("monto", self.monto, ft.Alignment.CENTER_RIGHT),
                    _celda(
                        "pagado",
                        ft.Column(
                            [self.pagado, self.estado_pagado, self.cobrado],
                            spacing=0,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                        ),
                        ft.Alignment.CENTER_RIGHT,
                    ),
                    _celda("categoria", self.categoria),
                    _celda("cuota", self.cuota, ft.Alignment.CENTER),
                    _celda("accion", self.lapiz, ft.Alignment.CENTER),
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )
        self._color_error = estilos.color(page, "negativo")

    @property
    def fila(self) -> FilaRevision:
        return self.vista.lista.filas[self.indice]

    def actualizar(self) -> None:
        """Copia a los controles lo que dice la lista sobre esta fila."""
        vista, fila, page = self.vista, self.fila, self.vista.app.page
        lista = vista.lista
        errores = lista.errores(fila)
        apagada = not fila.se_importa
        secundario = estilos.TEXTO_SECUNDARIO if apagada else None

        self.tilde.value = fila.tildada
        ignorada = fila.tipo == "ignorar"
        self.tilde.disabled = ignorada
        self.tilde.tooltip = (
            "Esta fila se ignora. Cambiá el tipo para importarla."
            if ignorada
            else "Importar esta fila"
        )
        self.tipo.value = fila.tipo

        if fila.nombre:
            self.nombre.value, self.nombre.italic = fila.nombre, False
            self.nombre.color = secundario
        else:
            self.nombre.value, self.nombre.italic = "(sin nombre)", True
            self.nombre.color = estilos.TEXTO_SECUNDARIO

        if fila.monto_cent is None:
            self.monto.value, self.monto.color = "(sin monto)", estilos.TEXTO_SECUNDARIO
        else:
            formato = formatear_usd if fila.tipo == "sueldo" else formatear_ars
            self.monto.value, self.monto.color = formato(fila.monto_cent), secundario

        # Pagado (gastos y cuotas) o tilde "Cobrado" (me deben).
        con_pagado = fila.tipo in TIPOS_GASTO and bool(fila.pagado_cent)
        self.pagado.visible = self.estado_pagado.visible = con_pagado
        if con_pagado:
            self.pagado.value, self.pagado.color = (
                formatear_ars(fila.pagado_cent),
                secundario,
            )
            if fila.monto_cent is not None and fila.pagado_cent == fila.monto_cent:
                self.estado_pagado.value = "✓ Completo"
                self.estado_pagado.color = estilos.color(page, "positivo")
            elif fila.monto_cent is not None and fila.pagado_cent < fila.monto_cent:
                falta = formatear_ars(fila.monto_cent - fila.pagado_cent)
                self.estado_pagado.value = f"Parcial · falta {falta}"
                self.estado_pagado.color = estilos.color(page, "pendiente")
            else:
                self.estado_pagado.visible = False
        self.cobrado.visible = fila.tipo == "me_deben"
        self.cobrado.value = fila.cobrado

        # Categoría (gastos y cuotas) o persona (me deben).
        self.categoria.tooltip = None
        self.categoria.color = secundario
        if fila.tipo in TIPOS_GASTO:
            nombre = vista.nombre_de(lista.categoria_de(fila), catalogos.CATEGORIAS)
            if fila.categoria is not None:
                # Elegida a mano: no sigue la categoría por defecto (RN-75).
                nombre = f"• {nombre}"
                self.categoria.tooltip = "Elegida a mano"
            self.categoria.value = nombre
        elif fila.tipo == "me_deben":
            nombre = vista.nombre_de(fila.persona, catalogos.PERSONAS)
            if nombre:
                self.categoria.value = nombre
            else:
                self.categoria.value = "Elegí persona"
                self.categoria.color = self._color_error
        else:
            self.categoria.value = ""

        if fila.tipo == "cuota":
            if fila.cuota_actual is None or fila.cuota_total is None:
                self.cuota.value, self.cuota.color = "Falta", self._color_error
            else:
                self.cuota.value = f"{fila.cuota_actual}/{fila.cuota_total}"
                self.cuota.color = secundario
        else:
            self.cuota.value, self.cuota.color = "-", estilos.TEXTO_SECUNDARIO

        # Notas: primero los errores, después avisos e info (§3.12).
        notas = [("error", e) for e in errores] + lista.notas_con_clase(fila)
        self.notas.controls = [self._nota(clase, texto) for clase, texto in notas]
        self.notas.visible = bool(notas)

        # Con error: fondo rojo suave y borde izquierdo (el color no es la única señal:
        # también está el ícono y el texto del error).
        if errores:
            self.control.bgcolor = estilos.color(page, "negativo_suave")
            self.control.border = ft.Border.only(
                left=ft.BorderSide(4, self._color_error)
            )
        else:
            self.control.bgcolor = None
            self.control.border = None

    def _nota(self, clase: str, texto: str) -> ft.Row:
        icono, rol = _ESTILO_NOTA[clase]
        color = (
            estilos.color(self.vista.app.page, rol) if rol else estilos.TEXTO_SECUNDARIO
        )
        return ft.Row(
            [
                ft.Icon(icono, size=16, color=color),
                ft.Text(texto, size=estilos.TAM_AYUDA, color=color, expand=True),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

    def tiene_avisos(self) -> bool:
        return any(
            c in _CLASES_AVISO for c, _ in self.vista.lista.notas_con_clase(self.fila)
        )

    def tiene_errores(self) -> bool:
        return bool(self.vista.lista.errores(self.fila))

    def pasa_filtro(self, filtro: str) -> bool:
        if filtro == "importan":
            return self.fila.se_importa
        if filtro == "avisos":
            return self.tiene_avisos()
        if filtro == "errores":
            return self.tiene_errores()
        return True


class BloqueVista:
    """Un bloque del Excel (o "Filas incompletas") como grupo plegable."""

    def __init__(
        self,
        vista: "VistaRevision",
        titulo: str,
        filas: list[FilaVista],
        incompletas: bool = False,
    ) -> None:
        self.vista = vista
        self.titulo = titulo
        self.filas = filas
        self.incompletas = incompletas
        self.subtitulo = ft.Row(spacing=4, wrap=True)
        titulo_visible = ft.Text(
            titulo.upper(), size=14, weight=ft.FontWeight.W_600, expand=True
        )
        cabecera = [titulo_visible]
        controles = [f.control for f in filas]
        if incompletas:
            controles.insert(
                0,
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=8),
                    content=texto_ayuda(
                        "Son textos sin monto (títulos, encabezados) o montos sin texto "
                        "(totales). Si alguna es un dato que querés traer, por ejemplo el "
                        "sueldo, completala y cambiale el tipo."
                    ),
                ),
            )
        else:
            cabecera.append(
                ft.PopupMenuButton(
                    icon=ft.Icons.MORE_VERT,
                    tooltip="Acciones del bloque",
                    items=[
                        ft.PopupMenuItem(
                            content="Tildar todas las filas",
                            on_click=lambda e: vista.tildar_bloque(titulo, True),
                        ),
                        ft.PopupMenuItem(
                            content="Destildar todas las filas",
                            on_click=lambda e: vista.tildar_bloque(titulo, False),
                        ),
                        ft.PopupMenuItem(
                            content="Cambiar tipo o categoría de todas...",
                            on_click=lambda e: vista.cambiar_bloque(titulo),
                        ),
                    ],
                )
            )
        fondo = estilos.SUPERFICIE_VARIANTE if incompletas else None
        self.control = ft.ExpansionTile(
            title=ft.Row(cabecera),
            subtitle=self.subtitulo,
            # Los bloques vienen abiertos; "Filas incompletas", plegado (§3.12).
            expanded=not incompletas,
            maintain_state=True,
            bgcolor=fondo,
            collapsed_bgcolor=fondo,
            controls=controles,
        )

    def actualizar(self, filtro: str) -> None:
        lista_filas = [f.fila for f in self.filas]
        importan = sum(1 for f in lista_filas if f.se_importa)
        con_error = sum(1 for f in self.filas if f.tiene_errores())
        n = len(lista_filas)
        if self.incompletas:
            cuantas = "1 fila" if n == 1 else f"{n} filas"
            detalle = (
                f"se importan {importan}"
                if importan
                else "todas se ignoran, salvo que las completes"
            )
            partes = [f"{cuantas} · {detalle}"]
        else:
            numeros = [f.origen.fila_excel for f in lista_filas]
            desde, hasta = min(numeros), max(numeros)
            rango = f"fila {desde}" if desde == hasta else f"filas {desde} a {hasta}"
            partes = [f"{rango} · se importan {importan} de {n}"]
        controles: list[ft.Control] = [
            ft.Text(partes[0], size=estilos.TAM_AYUDA, color=estilos.TEXTO_SECUNDARIO)
        ]
        if con_error:
            # Un bloque plegado nunca esconde un error (§3.12).
            negativo = estilos.color(self.vista.app.page, "negativo")
            controles += [
                ft.Icon(ft.Icons.ERROR_OUTLINE, size=14, color=negativo),
                ft.Text(
                    f"· {con_error} con error", size=estilos.TAM_AYUDA, color=negativo
                ),
            ]
        self.subtitulo.controls = controles
        visibles = 0
        for fila in self.filas:
            fila.control.visible = fila.pasa_filtro(filtro)
            visibles += fila.control.visible
        self.control.visible = visibles > 0

    def tiene_errores(self) -> bool:
        return any(f.tiene_errores() for f in self.filas)


class VistaRevision:
    """La pantalla de revisión completa: cabecera fija, lista con scroll y pie fijo."""

    def __init__(
        self,
        app,
        lista: ListaRevision,
        nombre_archivo: str,
        al_cambiar_archivo: Callable[[], None],
        al_cancelar: Callable[[], None],
        al_confirmar: Callable[[], None],
    ) -> None:
        self.app = app
        self.lista = lista
        self.al_confirmar = al_confirmar
        self.filtro = "todas"
        self.mes_invalido = False
        page = app.page
        hoja = lista.hoja

        # -- Avisos del archivo (arriba de los controles generales) --
        self.avisos_archivo = ft.Column(spacing=8)

        # -- Mes destino (RN-73) --
        self.ayuda_mes = ft.Column(spacing=4)
        if lista.es_primer_uso:
            self.mes = ft.Dropdown(
                label="Mes",
                value=str(lista.mes),
                options=[
                    ft.DropdownOption(key=str(n), text=t)
                    for n, t in enumerate(MESES, 1)
                ],
                expand=True,
                on_select=lambda e: self._cambiar_mes_primer_uso(),
            )
            self.anio = ft.TextField(
                label="Año",
                value=str(lista.anio),
                max_length=4,
                width=120,
                keyboard_type=ft.KeyboardType.NUMBER,
                input_filter=ft.InputFilter(regex_string=r"[0-9]", allow=True),
                on_change=lambda e: self._cambiar_mes_primer_uso(),
            )
            control_mes = ft.Row([self.mes, self.anio], spacing=12)
        else:
            self.anio = None
            self.mes = ft.Dropdown(
                label="Mes destino",
                expand=True,
                on_select=lambda e: self._cambiar_mes(e.control.value),
            )
            self._cargar_meses()
            control_mes = self.mes

        # -- Categoría por defecto (RN-75) --
        self.categoria_defecto = SelectorConNueva(
            app,
            lista,
            catalogos.CATEGORIAS,
            "Categoría por defecto",
            al_cambiar=self._cambiar_categoria_defecto,
        )
        self.categoria_defecto.valor = lista.categoria_defecto

        generales = ft.Card(
            content=ft.Container(
                padding=16,
                content=ft.ResponsiveRow(
                    [
                        ft.Column(
                            [control_mes, self.ayuda_mes],
                            spacing=8,
                            col={"sm": 12, "md": 6},
                        ),
                        ft.Column(
                            [
                                self.categoria_defecto.control,
                                texto_ayuda(
                                    "Se usa en los gastos y cuotas que no cambies a mano. "
                                    "Los gastos quedan sin medio de pago: lo completás "
                                    "después en Gastos."
                                ),
                            ],
                            spacing=8,
                            col={"sm": 12, "md": 6},
                        ),
                    ],
                    spacing=16,
                ),
            )
        )

        # -- Filtro --
        self.selector_filtro = ft.SegmentedButton(
            segments=[
                ft.Segment(value=v, label=ft.Text(t)) for v, t in _FILTROS.items()
            ],
            selected=["todas"],
            allow_empty_selection=False,
            on_change=lambda e: self.cambiar_filtro(e.control.selected[0]),
        )

        # -- Filas y bloques --
        self.filas = [FilaVista(self, i) for i in range(len(lista.filas))]
        self.bloques = [
            BloqueVista(self, b.titulo, [self.filas[f.indice] for f in b.filas])
            for b in lista.bloques()
        ]
        incompletas = lista.incompletas()
        self.bloque_incompletas = (
            BloqueVista(
                self,
                "Filas incompletas",
                [self.filas[f.indice] for f in incompletas],
                incompletas=True,
            )
            if incompletas
            else None
        )
        if self.bloque_incompletas and (
            hoja.sin_filas_completas or self.bloque_incompletas.tiene_errores()
        ):
            self.bloque_incompletas.control.expanded = True
        todos = self.bloques + (
            [self.bloque_incompletas] if self.bloque_incompletas else []
        )
        self.sin_resultados = ft.Container(
            padding=32,
            alignment=ft.Alignment.CENTER,
            visible=False,
            content=ft.Column(
                [
                    ft.Text("Ninguna fila coincide con este filtro."),
                    ft.TextButton(
                        "Ver todas", on_click=lambda e: self.cambiar_filtro("todas")
                    ),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                tight=True,
            ),
        )
        self.lista_filas = ft.ListView(
            [b.control for b in todos] + [self.sin_resultados], expand=True, spacing=4
        )

        encabezado = ft.Container(
            bgcolor=estilos.SUPERFICIE_VARIANTE,
            padding=ft.Padding.symmetric(horizontal=8, vertical=6),
            content=ft.Row(
                [
                    _celda("imp", self._titulo_columna("Imp."), ft.Alignment.CENTER),
                    _celda(
                        "fila", self._titulo_columna("Fila"), ft.Alignment.CENTER_RIGHT
                    ),
                    _celda("tipo", self._titulo_columna("Tipo")),
                    ft.Container(expand=True, content=self._titulo_columna("Nombre")),
                    _celda(
                        "monto",
                        self._titulo_columna("Monto"),
                        ft.Alignment.CENTER_RIGHT,
                    ),
                    _celda(
                        "pagado",
                        self._titulo_columna("Pagado / Cobrado"),
                        ft.Alignment.CENTER_RIGHT,
                    ),
                    _celda("categoria", self._titulo_columna("Categoría / Persona")),
                    _celda("cuota", self._titulo_columna("Cuota"), ft.Alignment.CENTER),
                    _celda("accion", ft.Container()),
                ],
                spacing=8,
            ),
        )

        # -- Pie fijo --
        self.icono_pie = ft.Icon(ft.Icons.ERROR_OUTLINE, size=18, visible=False)
        self.texto_pie = ft.Text(expand=True)
        self.ir_al_error = ft.TextButton(
            "Ir al primer error",
            visible=False,
            on_click=lambda e: self.ir_al_primer_error(),
        )
        self.boton_confirmar = ft.FilledButton(
            "Confirmar importación", on_click=lambda e: self.confirmar()
        )
        pie = ft.Container(
            padding=ft.Padding.symmetric(horizontal=24, vertical=12),
            border=ft.Border.only(top=ft.BorderSide(1, estilos.BORDE)),
            content=ft.Row(
                [
                    ft.Row(
                        [self.icono_pie, self.texto_pie, self.ir_al_error],
                        expand=True,
                        spacing=8,
                    ),
                    ft.TextButton("Cancelar", on_click=lambda e: al_cancelar()),
                    self.boton_confirmar,
                ]
            ),
        )

        cabecera = ft.Container(
            padding=ft.Padding.only(left=24, right=24, top=24),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Importar desde Excel",
                                size=estilos.TAM_TITULO,
                                weight=ft.FontWeight.W_600,
                            ),
                            ft.TextButton(
                                "Cambiar archivo u hoja",
                                on_click=lambda e: al_cambiar_archivo(),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    texto_ayuda(f'{nombre_archivo}  ·  Hoja "{hoja.nombre}"'),
                    self.avisos_archivo,
                    generales,
                    self.selector_filtro,
                    encabezado,
                ],
                spacing=12,
            ),
        )
        # Arriba y abajo quedan fijos; solo la lista hace scroll (§3.12).
        self.control = ft.Column(
            [
                cabecera,
                ft.Container(
                    content=self.lista_filas,
                    expand=True,
                    padding=ft.Padding.symmetric(horizontal=24),
                ),
                pie,
            ],
            expand=True,
            spacing=8,
        )
        self._color_negativo = estilos.color(page, "negativo")
        self.actualizar()

    @staticmethod
    def _titulo_columna(texto: str) -> ft.Text:
        return ft.Text(texto, size=estilos.TAM_AYUDA, weight=ft.FontWeight.W_600)

    # ------------------------------------------------------------------
    # Dibujar
    # ------------------------------------------------------------------

    def nombre_de(self, valor, tabla: str) -> str:
        """Nombre de una categoría o persona (id o Nueva) para mostrar en la fila."""
        if isinstance(valor, Nueva):
            return f"{valor.nombre} (nueva)"
        if valor is None:
            return ""
        return self._nombres[tabla].get(valor, "")

    def actualizar(self) -> None:
        """Vuelve a mostrar todo lo que dice la lista. Se llama después de cada cambio.

        Los controles no se arman de nuevo: solo cambian sus valores, y Flet manda
        a la ventana nada más que lo que cambió.
        """
        # Los nombres se piden una vez por actualización, no una vez por fila.
        self._nombres = {
            tabla: {
                c["id"]: c["nombre"]
                for c in catalogos.listar(self.app.con, tabla, incluir_archivados=True)
            }
            for tabla in (catalogos.CATEGORIAS, catalogos.PERSONAS)
        }
        for fila in self.filas:
            fila.actualizar()
        todos = self.bloques + (
            [self.bloque_incompletas] if self.bloque_incompletas else []
        )
        for bloque in todos:
            bloque.actualizar(self.filtro)
        self.sin_resultados.visible = not any(b.control.visible for b in todos)
        self._actualizar_filtro()
        self._actualizar_avisos_archivo()
        self._actualizar_ayuda_mes()
        self._actualizar_categoria_defecto()
        self._actualizar_pie()
        self.app.page.update()

    def _actualizar_filtro(self) -> None:
        cantidades = {
            filtro: sum(1 for f in self.filas if f.pasa_filtro(filtro))
            for filtro in _FILTROS
        }
        for segmento in self.selector_filtro.segments:
            n = cantidades[segmento.value]
            segmento.label = ft.Text(f"{_FILTROS[segmento.value]} ({n})")
            # "Con errores" se marca en cuanto hay alguno, para que no se pierda.
            if segmento.value == "errores":
                segmento.icon = (
                    ft.Icon(ft.Icons.ERROR_OUTLINE, color=self._color_negativo)
                    if n
                    else None
                )

    def _actualizar_avisos_archivo(self) -> None:
        page, hoja = self.app.page, self.lista.hoja
        avisos = []
        if hoja.formulas_sin_valor:
            avisos.append(
                aviso_en_pantalla(
                    page,
                    "pendiente",
                    ft.Icons.WARNING_AMBER,
                    f"Hay {hoja.formulas_sin_valor} fórmulas sin valor calculado "
                    f"(ej. {hoja.ejemplo_formula}). Abrí el archivo en Excel, guardalo y "
                    "volvé a importarlo para ver esos montos.",
                )
            )
        if hoja.sin_filas_completas:
            avisos.append(
                aviso_en_pantalla(
                    page,
                    "pendiente",
                    ft.Icons.WARNING_AMBER,
                    "No se encontraron filas con un texto y un monto.",
                )
            )
        sueldos = self.lista.cantidad_sueldos()
        if sueldos > 1:
            avisos.append(
                aviso_en_pantalla(
                    page,
                    "negativo",
                    ft.Icons.ERROR_OUTLINE,
                    f"Marcaste {sueldos} filas como sueldo; dejá una sola.",
                )
            )
        self.avisos_archivo.controls = avisos
        self.avisos_archivo.visible = bool(avisos)

    def _cargar_meses(self) -> None:
        """Opciones del mes destino: del más nuevo al más viejo, y el siguiente al
        último como "se crea al confirmar" (§3.12)."""
        actual = meses.mes_actual_calendario()
        opciones = []
        for anio, mes in reversed(self.lista.meses_posibles()):
            texto = nombre_mes(anio, mes)
            if self.lista.mes_existente(anio, mes) is None:
                texto += " · se crea al confirmar"
            elif (anio, mes) == actual:
                texto += " · mes actual"
            opciones.append(ft.DropdownOption(key=f"{anio}-{mes}", text=texto))
        self.mes.options = opciones
        self.mes.value = f"{self.lista.anio}-{self.lista.mes}"

    def _actualizar_ayuda_mes(self) -> None:
        lista, page = self.lista, self.app.page
        nombre = lista.nombre_mes_destino
        lineas: list[ft.Control] = []
        if self.mes_invalido:
            pass  # El error ya está en el campo del año.
        elif lista.es_primer_uso:
            lineas.append(
                texto_ayuda(
                    "Se crea al confirmar, sin cotización: la cargás después en el Resumen. "
                    "Si no marcás una fila como sueldo, el sueldo del mes queda en US$ 0,00."
                )
            )
        elif lista.mes_se_crea:
            ultimo = meses.obtener_ultimo_mes(self.app.con)
            lineas.append(
                texto_ayuda(
                    f"{nombre} todavía no existe: se crea al confirmar, con los gastos fijos "
                    f"y las cuotas de {nombre_mes(ultimo['anio'], ultimo['mes'])}, y con su "
                    "sueldo y su cotización."
                )
            )
        else:
            lineas.append(
                texto_ayuda(
                    f"{nombre} ya existe: se agregan los datos, sin borrar nada de lo que "
                    "ya tiene."
                )
            )
            if lista.cantidad_sueldos():
                lineas.append(
                    texto_ayuda(
                        "El sueldo de este mes se reemplaza por el de la fila marcada "
                        "como sueldo."
                    )
                )
            aviso = lista.aviso_mes()
            if aviso:
                lineas.append(
                    aviso_en_pantalla(page, "pendiente", ft.Icons.WARNING_AMBER, aviso)
                )
        self.ayuda_mes.controls = lineas

    def _actualizar_categoria_defecto(self) -> None:
        selector = self.categoria_defecto
        selector.cargar_opciones()
        selector.valor = self.lista.categoria_defecto
        # Sin categoría por defecto (o archivada mientras tanto), se marca (§3.12).
        selector.dropdown.error_text = (
            "Elegí una categoría para los gastos y cuotas."
            if selector.dropdown.value is None
            else None
        )

    def _actualizar_pie(self) -> None:
        lista = self.lista
        hay_errores = bool(lista.filas_con_errores())
        self.texto_pie.value = lista.estado_pie()
        bloqueado = not lista.puede_confirmar() or self.mes_invalido
        self.icono_pie.visible = hay_errores or lista.cantidad_sueldos() > 1
        self.icono_pie.color = self._color_negativo
        self.texto_pie.color = self._color_negativo if self.icono_pie.visible else None
        self.ir_al_error.visible = hay_errores
        self.boton_confirmar.disabled = bloqueado
        # Un botón gris siempre dice por qué (§3.12).
        if self.mes_invalido:
            self.boton_confirmar.tooltip = "Corregí el mes destino."
        elif hay_errores:
            self.boton_confirmar.tooltip = "Primero corregí las filas con errores."
        elif not any(f.se_importa for f in lista.filas):
            self.boton_confirmar.tooltip = "Tildá al menos una fila."
        else:
            self.boton_confirmar.tooltip = self.app.atajo("Enter")

    # ------------------------------------------------------------------
    # Cambios del usuario
    # ------------------------------------------------------------------

    def _hacer(self, accion: Callable[[], object]) -> None:
        """Ejecuta un cambio en la lista y vuelve a dibujar. Un ErrorDeValidacion
        se avisa abajo; otro error es inesperado."""
        try:
            accion()
        except ErrorDeValidacion as error:
            self.app.avisar(str(error))
        except Exception as error:  # noqa: BLE001 (a propósito: ver error_inesperado)
            # Durante la revisión no se guarda nada: el título no dice "guardar" (O91).
            self.app.error_inesperado(error, titulo="No se pudo importar")
        self.actualizar()

    def cambiar_tilde(self, indice: int, tildada: bool) -> None:
        self._hacer(lambda: self.lista.cambiar_tilde(indice, bool(tildada)))

    def cambiar_tipo(self, indice: int, tipo: str) -> None:
        self._hacer(lambda: self.lista.cambiar_tipo(indice, tipo))

    def cambiar_cobrado(self, indice: int, cobrado: bool) -> None:
        self._hacer(lambda: self.lista.cambiar_cobrado(indice, bool(cobrado)))

    def tildar_bloque(self, titulo: str, tildar: bool) -> None:
        if tildar:
            self._hacer(lambda: self.lista.tildar_bloque(titulo))
        else:
            self._hacer(lambda: self.lista.destildar_bloque(titulo))

    def cambiar_bloque(self, titulo: str) -> None:
        DialogoBloque(self.app, self.lista, titulo, self.actualizar).abrir()

    def editar(self, indice: int) -> None:
        DialogoFilaImportacion(self.app, self.lista, indice, self.actualizar).abrir()

    def cambiar_filtro(self, filtro: str) -> None:
        self.filtro = filtro
        self.selector_filtro.selected = [filtro]
        self.actualizar()

    def _cambiar_mes(self, clave: str) -> None:
        anio, mes = (int(x) for x in clave.split("-"))
        mensaje = None

        def cambiar():
            nonlocal mensaje
            mensaje = self.lista.cambiar_mes_destino(anio, mes)

        self._hacer(cambiar)
        if mensaje:
            # Cambiaron tildes sin que el usuario los toque: siempre se avisa (§3.12).
            self.app.avisar(mensaje, duracion=6000)

    def _cambiar_mes_primer_uso(self) -> None:
        """Base sin meses: mes y año libres, con las validaciones de §3.1."""
        self.anio.error = None
        texto = self.anio.value or ""
        if len(texto) != 4:
            self.anio.error = "El año tiene que tener 4 dígitos. Ej.: 2026"
            self.mes_invalido = True
            self.actualizar()
            return
        mensaje = None
        try:
            mensaje = self.lista.cambiar_mes_destino(int(texto), int(self.mes.value))
            self.mes_invalido = False
        except ErrorDeValidacion as error:
            self.anio.error = str(error)
            self.mes_invalido = True
        self.actualizar()
        if mensaje:
            self.app.avisar(mensaje, duracion=6000)

    def _cambiar_categoria_defecto(self) -> None:
        valor = self.categoria_defecto.valor
        if isinstance(valor, (int, Nueva)):
            self._hacer(lambda: self.lista.cambiar_categoria_defecto(valor))

    def ir_al_primer_error(self) -> None:
        """Lleva la lista a la primera fila con error, abre su bloque y enfoca el lápiz."""
        fila = next((f for f in self.filas if f.tiene_errores()), None)
        if fila is None:
            return
        if not fila.pasa_filtro(self.filtro):
            self.cambiar_filtro("todas")
        todos = self.bloques + (
            [self.bloque_incompletas] if self.bloque_incompletas else []
        )
        for bloque in todos:
            if fila in bloque.filas:
                bloque.control.expanded = True
        self.app.page.update()

        async def desplazar():
            # scroll_to es asíncrona en Flet 1.0: por eso va en una tarea.
            await self.lista_filas.scroll_to(
                scroll_key=f"fila-{fila.indice}", duration=300
            )

        self.app.page.run_task(desplazar)
        self.app.enfocar(fila.lapiz)

    def confirmar(self) -> None:
        if self.boton_confirmar.disabled:
            return
        self.al_confirmar()

    def cerrar_en_linea(self) -> bool:
        """Esc con la fila de "nueva categoría" abierta: cierra solo esa fila."""
        return self.categoria_defecto.cerrar()
