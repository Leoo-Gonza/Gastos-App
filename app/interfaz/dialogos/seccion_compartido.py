"""Sección "Compartido" del diálogo de gasto (RF-29 a RF-31, docs/diseno.md §4.1).

Es un componente aparte para que el diálogo de gasto no crezca de más. El
diálogo le pasa una función que devuelve el monto actual en pesos (o None si
todavía no es válido), y la sección se encarga de:
- el interruptor "Compartido" y las personas con su tilde;
- la parte de cada persona (automática o "manual") y "Tu parte" al instante;
- los avisos sobre partes ya cobradas (RN-34 y O40).
"""

from collections.abc import Callable

import flet as ft

from app.interfaz import estilos
from app.interfaz.componentes import campo_monto, texto_ayuda
from app.logica import catalogos, compartidos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, formatear_monto_para_editar, leer_monto


class SeccionCompartido:
    def __init__(
        self, app, gasto_id: int | None, monto_en_pesos: Callable[[], int | None]
    ) -> None:
        self.app = app
        self.monto_en_pesos = monto_en_pesos
        # Las partes que ya tenía el gasto (para los avisos de cobros, RN-34 y O40).
        self.previas = {
            p["persona_id"]: p
            for p in (compartidos.obtener_partes(app.con, gasto_id) if gasto_id else [])
        }

        # Personas para elegir: las no archivadas y las archivadas que ya estaban.
        personas = list(catalogos.listar(app.con, catalogos.PERSONAS))
        for persona_id, p in self.previas.items():
            if p["persona_archivada"]:
                personas.append(
                    {"id": persona_id, "nombre": f"{p['persona']} (archivada)"}
                )
        self.nombres = {p["id"]: p["nombre"] for p in personas}

        self.interruptor = ft.Switch(
            label="Compartido",
            value=bool(self.previas),
            on_change=self._cambiar_interruptor,
        )
        self.tildes = {
            p["id"]: ft.Checkbox(
                label=p["nombre"],
                value=p["id"] in self.previas,
                on_change=lambda e: self._cambiar_personas(),
            )
            for p in personas
        }
        # Una parte por persona: el campo, si es manual y la etiqueta "manual".
        self.campos: dict[int, ft.TextField] = {}
        self.manual: dict[int, bool] = {
            pid: bool(p["editada_a_mano"]) for pid, p in self.previas.items()
        }
        for pid in self.tildes:
            campo = campo_monto("Parte", "ARS", width=180, dense=True)
            # pid=pid: cada campo recuerda a su persona (si no, todas usarían la última).
            campo.on_change = lambda e, pid=pid: self._editar_parte(pid)
            if pid in self.previas:
                campo.value = formatear_monto_para_editar(
                    self.previas[pid]["monto_cent"]
                )
            self.campos[pid] = campo

        self.filas = ft.Column(spacing=4)
        self.tu_parte = ft.Text(weight=ft.FontWeight.W_600)
        self.avisos = ft.Column(spacing=2)
        self.error = ft.Text(color=estilos.color(app.page, "negativo"), visible=False)
        self.boton_repartir = ft.TextButton(
            "Repartir en partes iguales", on_click=lambda e: self.repartir()
        )
        self.detalle = ft.Column(
            [
                ft.Row(list(self.tildes.values()), wrap=True),
                self.filas,
                self.tu_parte,
                self.boton_repartir,
                self.avisos,
                self.error,
            ],
            spacing=8,
        )
        sin_personas = not self.tildes
        if sin_personas:
            self.interruptor.disabled = True
            ayuda = texto_ayuda(
                "Agregá personas en Ajustes → Personas para compartir gastos."
            )
        else:
            ayuda = ft.Container()
        self.control = ft.Column([self.interruptor, ayuda, self.detalle], spacing=8)
        self._dibujar()

    # ------------------------------------------------------------------

    def _elegidas(self) -> list[int]:
        return [pid for pid, tilde in self.tildes.items() if tilde.value]

    def _cambiar_interruptor(self, e=None) -> None:
        self._dibujar()
        self.app.page.update()

    def _cambiar_personas(self) -> None:
        self._dibujar()
        self.app.page.update()

    def _editar_parte(self, persona_id: int) -> None:
        """Escribir en una parte la marca como "manual" (RN-33)."""
        self.manual[persona_id] = True
        self.recalcular()

    def repartir(self) -> None:
        """Botón "Repartir en partes iguales": todas vuelven a ser automáticas."""
        self.manual = {}
        self.recalcular()

    def _dibujar(self) -> None:
        activo = bool(self.interruptor.value)
        self.detalle.visible = activo
        self.filas.controls = [
            ft.Row(
                [
                    ft.Text(self.nombres[pid], width=140),
                    self.campos[pid],
                    texto_ayuda("manual", visible=self.manual.get(pid, False)),
                ]
            )
            for pid in self._elegidas()
        ]
        self.recalcular(actualizar=False)

    def recalcular(self, actualizar: bool = True) -> None:
        """Completa las partes automáticas y "Tu parte" con el monto actual.

        Lo llama el diálogo cada vez que cambia el monto (también en dólares).
        """
        self.error.visible = False
        elegidas = self._elegidas()
        monto = self.monto_en_pesos()
        if monto is not None and elegidas:
            igual = compartidos.parte_igual(monto, len(elegidas))
            for pid in elegidas:
                if not self.manual.get(pid, False):
                    self.campos[pid].value = formatear_monto_para_editar(igual)
        # Las etiquetas "manual" siguen al estado de cada parte.
        for fila, pid in zip(self.filas.controls, elegidas, strict=True):
            fila.controls[2].visible = self.manual.get(pid, False)

        partes = self._valores()
        if monto is None or partes is None:
            self.tu_parte.value = "Tu parte: —"
        else:
            tuya = monto - sum(partes.values())
            self.tu_parte.value = f"Tu parte: {formatear_ars(tuya)}"
            if tuya < 0:
                self.mostrar_error(
                    f"Las partes suman {formatear_ars(sum(partes.values()))} y superan el "
                    f"monto ({formatear_ars(monto)})."
                )
        self._dibujar_avisos(partes or {})
        if actualizar:
            self.app.page.update()

    def _valores(self) -> dict[int, int] | None:
        """{persona_id: centavos} de las partes escritas, o None si alguna no es válida."""
        valores = {}
        for pid in self._elegidas():
            try:
                valores[pid] = leer_monto(
                    self.campos[pid].value or "", permitir_cero=True
                )
            except ErrorDeValidacion:
                return None
        return valores

    def _dibujar_avisos(self, partes: dict[int, int]) -> None:
        """Avisos sobre partes que ya estaban cobradas (RN-34 y O40)."""
        avisos = []
        activo = bool(self.interruptor.value)
        for pid, previa in self.previas.items():
            cobrado = previa["cobrado_cent"]
            if not cobrado:
                continue
            nombre = previa["persona"]
            if not activo or pid not in partes:
                # O40: sacar a una persona que ya pagó borra ese registro.
                avisos.append(
                    f"La parte de {nombre} ya estaba cobrada ({formatear_ars(cobrado)}). "
                    'Si la sacás, ese cobro deja de figurar en "Me deben".'
                )
            elif previa["cobrado"] and partes[pid] != previa["monto_cent"]:
                diferencia = partes[pid] - cobrado
                if diferencia >= 0:
                    detalle = f"falta {formatear_ars(diferencia)}"
                else:
                    detalle = f"a devolver {formatear_ars(-diferencia)}"
                avisos.append(
                    f"La parte de {nombre} ya estaba cobrada ({formatear_ars(cobrado)}). "
                    f"Va a quedar pendiente: {detalle}."
                )
        color = estilos.color(self.app.page, "pendiente")
        self.avisos.controls = [
            ft.Text(a, size=estilos.TAM_AYUDA, color=color) for a in avisos
        ]

    def mostrar_error(self, mensaje: str) -> None:
        self.error.value = mensaje
        self.error.visible = True

    def leer(self) -> list[tuple[int, int | None]] | None:
        """Las partes para guardar: [(persona_id, manual o None)], [] si no es
        compartido, o None si hay un error (que queda a la vista)."""
        self.error.visible = False
        for campo in self.campos.values():
            campo.error = None
        if not self.interruptor.value:
            return []
        elegidas = self._elegidas()
        if not elegidas:
            self.mostrar_error("Elegí al menos una persona o desactivá Compartido.")
            return None
        resultado = []
        for pid in elegidas:
            if self.manual.get(pid, False):
                try:
                    valor = leer_monto(self.campos[pid].value or "", permitir_cero=True)
                except ErrorDeValidacion as error:
                    self.campos[pid].error = str(error)
                    self.mostrar_error(f"Revisá la parte de {self.nombres[pid]}.")
                    return None
                resultado.append((pid, valor))
            else:
                resultado.append((pid, None))
        return resultado
