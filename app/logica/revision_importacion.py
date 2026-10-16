"""Importar Excel (v2): la lista de revisión, en memoria (RN-66 a RN-75, RN-78).

Parte de las filas que detectó importar_excel.py y guarda lo que el usuario va
decidiendo (tipo, tilde, correcciones, categoría, persona, mes destino). No
escribe nada en la base: solo la lee para saber qué ya existe. El guardado
(todo o nada, RN-76) está en otro paso.
"""

import re
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from app.logica import catalogos, cuotas, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    formatear_ars,
    formatear_monto_para_editar,
    formatear_usd,
    nombre_mes,
    unir_con_y,
    validar_centavos,
)
from app.logica.importar_excel import FilaDetectada, HojaLeida, normalizar

# Tipos de fila (RF-52) y cómo se muestran.
TIPOS = {
    "fijo": "Gasto fijo",
    "unico": "Gasto único",
    "cuota": "Cuota",
    "me_deben": "Me deben",
    "sueldo": "Sueldo (USD)",
    "ignorar": "Ignorar",
}
# Los tipos que terminan siendo un gasto del mes (con categoría y pagado).
TIPOS_GASTO = ("fijo", "unico", "cuota")

BLOQUE_SIN_TITULO = "Otras filas"
BLOQUE_UNICO = "Filas detectadas"

# RN-66: nombres que se proponen como "ignorar" (valores calculados de la planilla).
_NOMBRES_IGNORADOS = {
    normalizar(n)
    for n in (
        "Gastos fijos sin deuda",
        "Capacidad de Endeudamiento",
        "Gastos en dolares",
        "Falta por pagar",
        "Tarjetas de Credito",
    )
}
# RN-66 regla 3: "n/N" en el nombre, con o sin espacios ("cuota 3/ 3").
_CUOTA_EN_NOMBRE = re.compile(r"(\d+)\s*/\s*(\d+)")
# RN-64: textos que en la columna "Cobrado" quieren decir "cobrado" (ya normalizados).
_TEXTOS_COBRADO = {"si", "x", "✓", "ok", "cobrado"}


@dataclass(frozen=True)
class Nueva:
    """Una categoría o persona creada durante la revisión: se guarda recién al
    confirmar, y solo si quedó en uso (RN-72, RN-75)."""

    nombre: str


@dataclass
class FilaRevision:
    """Una fila de la lista de revisión: lo que vino del Excel y lo que decidió el usuario.

    categoria: None = sigue la categoría por defecto (RN-75); si no, un id o una Nueva.
    persona: el id de una persona, una Nueva o None (sin elegir).
    Las marcas (ya_existe, repetida, aviso_compartido) las recalcula la lista.
    """

    indice: int
    origen: FilaDetectada
    nombre: str | None
    monto_cent: int | None
    pagado_cent: int | None
    tipo: str
    tildada: bool = False
    categoria: int | Nueva | None = None
    persona: int | Nueva | None = None
    cuota_actual: int | None = None
    cuota_total: int | None = None
    cobrado: bool = False
    nota_cobrado: str | None = None
    ya_existe: str | None = None  # None, "gasto", "plan" o "me_deben".
    repetida: bool = False
    aviso_compartido: bool = False

    @property
    def incompleta(self) -> bool:
        """Vino del Excel sin nombre o sin monto: se muestra en "Filas incompletas"
        aunque después se complete (RN-63)."""
        return not self.origen.completa

    @property
    def se_importa(self) -> bool:
        return self.tildada and self.tipo != "ignorar"

    @property
    def bloque(self) -> str | None:
        return self.origen.bloque


@dataclass
class Bloque:
    titulo: str
    filas: list[FilaRevision] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Comparaciones (RN-67, RN-72)
# ---------------------------------------------------------------------------


def _contiene_palabras(largo: str, corto: str) -> bool:
    """¿Las palabras de "corto" aparecen, como palabras enteras y seguidas, en "largo"?"""
    return f" {corto} " in f" {largo} "


def coinciden(nombre_a: str, nombre_b: str) -> bool:
    """RN-72: iguales, o todas las palabras del más corto están enteras en el
    más largo ("Servicios Luz Gas" coincide con "Servicios"; "Pesos Check" no
    coincide con "Pesos checks")."""
    a, b = normalizar(nombre_a), normalizar(nombre_b)
    if not a or not b:
        return False
    if a == b:
        return True
    corto, largo = sorted((a, b), key=lambda t: len(t.split()))
    return set(corto.split()) <= set(largo.split())


def _es_entero(valor) -> bool:
    # bool aparte: en Python True y False también son int.
    return isinstance(valor, int) and not isinstance(valor, bool)


def sumar_meses(anio: int, mes: int, cantidad: int) -> tuple[int, int]:
    """(anio, mes) más "cantidad" meses (puede ser negativa)."""
    total = anio * 12 + (mes - 1) + cantidad
    return total // 12, total % 12 + 1


def _numero_sin_signo(centavos: int) -> str:
    """ "3.000" para la nota de cobrado: el formato de montos sin el "$ ".

    replace y no removeprefix: los negativos se formatean "-$ 500" (BUG-35)."""
    return formatear_ars(centavos).replace("$ ", "", 1)


# ---------------------------------------------------------------------------
# La lista
# ---------------------------------------------------------------------------


class ListaRevision:
    """La revisión de una hoja. Se arma con la base abierta para saber qué existe."""

    def __init__(
        self, con: sqlite3.Connection, hoja: HojaLeida, hoy: date | None = None
    ) -> None:
        self.con = con
        self.hoja = hoja
        self.hoy = hoy or date.today()  # noqa: DTZ011 (fecha local del usuario)
        self.hubo_cambios = False  # RN-76: lo que hizo el usuario, no la app.
        self.confirmada = False  # Después de guardar no se puede volver a usar (O76).
        self.categorias_nuevas: list[Nueva] = []
        self.personas_nuevas: list[Nueva] = []

        self._personas = catalogos.listar(con, catalogos.PERSONAS)
        self.categoria_defecto: int | Nueva | None = next(
            (
                c["id"]
                for c in catalogos.listar(con, catalogos.CATEGORIAS)
                if normalizar(c["nombre"]) == "varios"
            ),
            None,
        )
        self.anio, self.mes = self._mes_por_defecto()
        self.filas = [self._fila_inicial(i, f) for i, f in enumerate(hoja.filas)]
        self._recalcular_marcas()
        for fila in self.filas:
            # Al principio: tildadas las que se importan, salvo las "ya existe" (RN-74).
            fila.tildada = fila.tipo != "ignorar" and fila.ya_existe is None
        # Otra vez: el aviso de gasto compartido depende de qué filas están tildadas.
        self._recalcular_marcas()

    # -- Armado inicial (RN-64, RN-65, RN-66) --------------------------------

    def _persona_del_titulo(self, titulo: str | None) -> tuple[bool, int | None]:
        """RN-65: (¿el título nombra personas?, la persona si es una sola)."""
        if titulo is None:
            return False, None
        nombradas = [
            p["id"]
            for p in self._personas
            if _contiene_palabras(normalizar(titulo), normalizar(p["nombre"]))
        ]
        if not nombradas:
            return False, None
        return True, nombradas[0] if len(nombradas) == 1 else None

    def _fila_inicial(self, indice: int, origen: FilaDetectada) -> FilaRevision:
        fila = FilaRevision(
            indice,
            origen,
            nombre=origen.nombre,
            monto_cent=origen.monto_cent,
            pagado_cent=origen.pagado_cent,
            tipo="ignorar",
        )
        nombre = normalizar(origen.nombre or "")
        cuota = _CUOTA_EN_NOMBRE.search(origen.nombre or "")
        nombra_personas, persona = self._persona_del_titulo(origen.bloque)
        if not origen.completa:
            pass  # Las incompletas siempre "ignorar" (RN-63).
        elif (
            re.search(r"\btotal\b", nombre)
            or nombre in _NOMBRES_IGNORADOS
            or origen.monto_es_suma
            or origen.monto_cent <= 0
        ):
            pass  # RN-66 regla 1.
        elif nombra_personas:
            fila.tipo, fila.persona = "me_deben", persona
        elif cuota and 1 <= int(cuota.group(1)) <= int(cuota.group(2)) <= cuotas.MAXIMO_CUOTAS:
            fila.tipo = "cuota"
            fila.cuota_actual, fila.cuota_total = int(cuota.group(1)), int(cuota.group(2))
        else:
            fila.tipo = "fijo"
        self._leer_cobrado(fila)
        return fila

    def _leer_cobrado(self, fila: FilaRevision) -> None:
        """RN-64: interpreta el valor crudo de la columna "Cobrado"."""
        valor = fila.origen.cobrado
        fila.cobrado, fila.nota_cobrado = False, None
        if valor is None or valor == 0:
            return
        if isinstance(valor, int):
            if valor == fila.monto_cent:
                fila.cobrado = True
                return
            mostrado = _numero_sin_signo(valor)
        else:
            if normalizar(valor) in _TEXTOS_COBRADO:
                fila.cobrado = True
                return
            mostrado = valor
        fila.nota_cobrado = (
            f'En la columna Cobrado dice "{mostrado}"; los ítems \'me deben\' no tienen '
            "cobro parcial, quedó como no cobrado."
        )

    # -- Mes destino (RN-73) -------------------------------------------------

    @property
    def es_primer_uso(self) -> bool:
        return not meses.hay_meses(self.con)

    def meses_posibles(self) -> list[tuple[int, int]]:
        """Los meses existentes y el siguiente al último (RN-08). En el primer uso,
        cualquier mes vale: devuelve [] y la pantalla ofrece año y mes libres."""
        if self.es_primer_uso:
            return []
        existentes = [(m["anio"], m["mes"]) for m in meses.listar_meses(self.con)]
        ultimo = meses.obtener_ultimo_mes(self.con)
        return sorted(existentes + [meses.siguiente(ultimo["anio"], ultimo["mes"])])

    def _mes_por_defecto(self) -> tuple[int, int]:
        actual = meses.mes_actual_calendario(self.hoy)
        posibles = self.meses_posibles()
        if not posibles or actual in posibles:
            return actual
        ultimo = meses.obtener_ultimo_mes(self.con)
        return ultimo["anio"], ultimo["mes"]

    def mes_existente(self, anio: int | None = None, mes: int | None = None):
        anio = self.anio if anio is None else anio
        mes = self.mes if mes is None else mes
        return meses.obtener_mes_por_fecha(self.con, anio, mes)

    @property
    def mes_se_crea(self) -> bool:
        return self.mes_existente() is None

    @property
    def nombre_mes_destino(self) -> str:
        return nombre_mes(self.anio, self.mes)

    def aviso_mes(self) -> str | None:
        """RN-73: aviso si el mes destino existe pero no es el último."""
        existente = self.mes_existente()
        ultimo = meses.obtener_ultimo_mes(self.con)
        if existente is not None and existente["id"] != ultimo["id"]:
            return (
                "Los gastos fijos que importes no se agregan a los meses siguientes "
                "que ya existen."
            )
        return None

    def cambiar_mes_destino(self, anio: int, mes: int) -> str | None:
        """RN-73/RN-74: cambia el mes y recalcula las marcas. Devuelve el mensaje
        temporal si algún tilde cambió, o None."""
        if self.es_primer_uso:
            meses.validar_anio_mes(anio, mes)
        elif (anio, mes) not in self.meses_posibles():
            raise ErrorDeValidacion("Ese mes no se puede elegir.", "mes")
        if (anio, mes) == (self.anio, self.mes):
            return None
        antes = {f.indice: f.ya_existe for f in self.filas}
        self.anio, self.mes = anio, mes
        self.hubo_cambios = True
        self._recalcular_marcas()
        destildadas = retildadas = 0
        for fila in self.filas:
            if fila.tipo == "ignorar":
                continue
            era, es = antes[fila.indice] is not None, fila.ya_existe is not None
            if es and not era and fila.tildada:
                fila.tildada = False
                destildadas += 1
            elif era and not es and not fila.tildada:
                fila.tildada = True
                retildadas += 1
        # Otra vez: el aviso de gasto compartido depende de los tildes (BUG-32).
        self._recalcular_marcas()
        partes = []
        if destildadas:
            partes.append(
                '1 fila pasó a "ya existe" y se destildó'
                if destildadas == 1
                else f'{destildadas} filas pasaron a "ya existe" y se destildaron'
            )
        if retildadas:
            partes.append(
                "1 fila se volvió a tildar"
                if retildadas == 1
                else f"{retildadas} filas se volvieron a tildar"
            )
        if not partes:
            return None
        return "Cambiaste el mes: " + ". ".join(partes) + "."

    def sueldo_actual_cent(self) -> int | None:
        """El sueldo que tiene (o tendrá al crearse) el mes destino; None en el primer uso."""
        existente = self.mes_existente()
        if existente is not None:
            return existente["sueldo_usd_cent"]
        ultimo = meses.obtener_ultimo_mes(self.con)
        return None if ultimo is None else ultimo["sueldo_usd_cent"]

    # -- Marcas: "ya existe", "repetida", posible gasto compartido (RN-72, RN-74) --

    def _gastos_del_mes_destino(self) -> list[str]:
        """Nombres de los gastos del mes destino; si se va a crear, los que va a
        tener al crearse: fijos copiados del último mes y cuotas de planes activos."""
        existente = self.mes_existente()
        if existente is not None:
            filas = self.con.execute(
                "SELECT nombre FROM gastos WHERE mes_id = ?", (existente["id"],)
            )
            return [f["nombre"] for f in filas]
        ultimo = meses.obtener_ultimo_mes(self.con)
        if ultimo is None:
            return []
        fijos = self.con.execute(
            "SELECT nombre FROM gastos WHERE mes_id = ? AND tipo = 'fijo'", (ultimo["id"],)
        )
        planes = self.con.execute("SELECT * FROM planes_cuotas").fetchall()
        activos = [
            p["nombre"] for p in planes if cuotas.activo_en(self.con, p, self.anio, self.mes)
        ]
        return [f["nombre"] for f in fijos] + activos

    def _recalcular_marcas(self) -> None:
        nombres_mes = self._gastos_del_mes_destino()
        gastos_mes = {normalizar(n) for n in nombres_mes}
        planes = {
            normalizar(p["nombre"])
            for p in self.con.execute("SELECT nombre FROM planes_cuotas")
        }
        items = {
            (i["persona_id"], normalizar(i["descripcion"]))
            for i in self.con.execute(
                "SELECT persona_id, descripcion FROM items_me_deben WHERE cobrado = 0"
            )
        }
        for fila in self.filas:
            nombre = normalizar(fila.nombre or "")
            fila.ya_existe = None
            if fila.tipo in TIPOS_GASTO and nombre:
                if nombre in gastos_mes:
                    fila.ya_existe = "gasto"
                elif fila.tipo == "cuota" and nombre in planes:
                    fila.ya_existe = "plan"
            elif fila.tipo == "me_deben" and isinstance(fila.persona, int):
                if (fila.persona, nombre) in items:
                    fila.ya_existe = "me_deben"

        # Repetidas en el archivo: mismo nombre y mismo grupo (gastos entre sí,
        # o "me deben" de la misma persona).
        def grupo(f: FilaRevision):
            if f.tipo in TIPOS_GASTO:
                return "gastos"
            if f.tipo == "me_deben":
                return ("me_deben", f.persona)
            return None

        vistos: dict[tuple, int] = {}
        for fila in self.filas:
            if fila.nombre and grupo(fila) is not None:
                clave = (grupo(fila), normalizar(fila.nombre))
                vistos[clave] = vistos.get(clave, 0) + 1
        for fila in self.filas:
            clave = (grupo(fila), normalizar(fila.nombre or ""))
            fila.repetida = bool(fila.nombre) and grupo(fila) is not None and vistos[clave] > 1

        # Aviso de posible gasto compartido (RN-72).
        gastos_que_se_importan = [
            f.nombre for f in self.filas if f.se_importa and f.tipo in TIPOS_GASTO and f.nombre
        ]
        for fila in self.filas:
            fila.aviso_compartido = (
                fila.tipo == "me_deben"
                and bool(fila.nombre)
                and any(
                    coinciden(fila.nombre, otro)
                    for otro in gastos_que_se_importan + nombres_mes
                )
            )

    # -- Cambios del usuario (RF-52, RF-53, RN-68, RN-74) ---------------------

    def _fila(self, indice: int) -> FilaRevision:
        return self.filas[indice]

    def _aplicar_tipo(self, fila: FilaRevision, tipo: str) -> None:
        """Cambia el tipo con la regla del tilde de RN-68: desde "ignorar" se tilda
        sola; a "ignorar" queda sin tilde; en los demás casos no se toca."""
        if tipo not in TIPOS:
            raise ValueError(f"Tipo desconocido: {tipo}")
        anterior = fila.tipo
        fila.tipo = tipo
        if tipo == "ignorar":
            fila.tildada = False
        elif anterior == "ignorar":
            fila.tildada = True

    def cambiar_tipo(self, indice: int, tipo: str) -> None:
        self._aplicar_tipo(self._fila(indice), tipo)
        self.hubo_cambios = True
        self._recalcular_marcas()

    def cambiar_tilde(self, indice: int, tildada: bool) -> None:
        fila = self._fila(indice)
        if fila.tipo == "ignorar" and tildada:
            raise ErrorDeValidacion("Una fila ignorada no se puede tildar.")
        fila.tildada = tildada
        self.hubo_cambios = True
        self._recalcular_marcas()

    def cambiar_cobrado(self, indice: int, cobrado: bool) -> None:
        fila = self._fila(indice)
        fila.cobrado = cobrado
        fila.nota_cobrado = None  # La nota explicaba lo que leyó la app, ya no aplica.
        self.hubo_cambios = True

    def editar_fila(
        self,
        indice: int,
        tipo: str,
        nombre: str | None,
        monto_cent: int | None,
        pagado_cent: int | None = None,
        categoria: int | Nueva | None = None,
        persona: int | Nueva | None = None,
        cuota_actual: int | None = None,
        cuota_total: int | None = None,
        cobrado: bool | None = None,
    ) -> dict[str, str]:
        """El diálogo de edición (RF-53). Devuelve los errores por campo; si hay
        errores y el tipo no es "ignorar", no cambia nada (RN-68)."""
        nombre = " ".join(nombre.split()) if nombre else None
        prueba = FilaRevision(
            indice,
            self._fila(indice).origen,
            nombre=nombre,
            monto_cent=monto_cent,
            pagado_cent=pagado_cent,
            tipo=tipo,
            tildada=True,
            categoria=categoria,
            persona=persona,
            cuota_actual=cuota_actual,
            cuota_total=cuota_total,
        )
        errores = self._errores_por_campo(prueba)
        errores.pop("sueldo", None)  # La cantidad de sueldos se ve en la lista.
        if errores and tipo != "ignorar":
            return errores
        fila = self._fila(indice)
        self._aplicar_tipo(fila, tipo)
        fila.nombre, fila.monto_cent, fila.pagado_cent = nombre, monto_cent, pagado_cent
        fila.categoria, fila.persona = categoria, persona
        fila.cuota_actual, fila.cuota_total = cuota_actual, cuota_total
        if cobrado is not None and cobrado != fila.cobrado:
            fila.cobrado, fila.nota_cobrado = cobrado, None
        self.hubo_cambios = True
        self._recalcular_marcas()
        return {}

    def restaurar_fila(self, indice: int) -> None:
        """"Volver a lo detectado": la fila como la propuso la app."""
        nueva = self._fila_inicial(indice, self._fila(indice).origen)
        self.filas[indice] = nueva
        self._recalcular_marcas()
        nueva.tildada = nueva.tipo != "ignorar" and nueva.ya_existe is None
        self._recalcular_marcas()  # El aviso depende del tilde nuevo (BUG-31).
        self.hubo_cambios = True

    # -- Categorías y personas (RN-72, RN-75) --------------------------------

    def _validar_nueva(self, tabla: str, nombre: str, nuevas: list[Nueva]) -> str:
        limpio = " ".join(nombre.split())
        un = "una categoría" if tabla == catalogos.CATEGORIAS else "una persona"
        if not limpio:
            raise ErrorDeValidacion("Ingresá un nombre.", "nombre")
        for existente in catalogos.listar(self.con, tabla, incluir_archivados=True):
            if normalizar(existente["nombre"]) == normalizar(limpio):
                mensaje = f'Ya existe {un} llamada "{existente["nombre"]}"'
                if existente["archivado"]:
                    mensaje += " (está archivada). Podés desarchivarla en Ajustes."
                else:
                    mensaje += "."
                raise ErrorDeValidacion(mensaje, "nombre")
        for nueva in nuevas:
            if normalizar(nueva.nombre) == normalizar(limpio):
                raise ErrorDeValidacion(
                    f'Ya agregaste {un} llamada "{nueva.nombre}" en esta importación.',
                    "nombre",
                )
        return limpio

    def agregar_categoria(self, nombre: str) -> Nueva:
        nueva = Nueva(self._validar_nueva(catalogos.CATEGORIAS, nombre, self.categorias_nuevas))
        self.categorias_nuevas.append(nueva)
        self.hubo_cambios = True
        return nueva

    def agregar_persona(self, nombre: str) -> Nueva:
        nueva = Nueva(self._validar_nueva(catalogos.PERSONAS, nombre, self.personas_nuevas))
        self.personas_nuevas.append(nueva)
        self.hubo_cambios = True
        return nueva

    def cambiar_categoria_defecto(self, categoria: int | Nueva | None) -> None:
        self.categoria_defecto = categoria
        self.hubo_cambios = True

    def categoria_de(self, fila: FilaRevision) -> int | Nueva | None:
        """La categoría efectiva: la propia o, si sigue la de por defecto, esa."""
        return fila.categoria if fila.categoria is not None else self.categoria_defecto

    def nuevas_en_uso(self) -> tuple[list[Nueva], list[Nueva]]:
        """Las categorías y personas nuevas que hay que crear al confirmar (RN-72, RN-75)."""
        importan = [f for f in self.filas if f.se_importa]
        categorias = {self.categoria_de(f) for f in importan if f.tipo in TIPOS_GASTO}
        personas = {f.persona for f in importan if f.tipo == "me_deben"}
        return (
            [n for n in self.categorias_nuevas if n in categorias],
            [n for n in self.personas_nuevas if n in personas],
        )

    # -- Acciones de bloque (RN-78) ------------------------------------------

    def bloques(self) -> list[Bloque]:
        """La lista principal agrupada por título de bloque, en el orden del Excel."""
        principales = [f for f in self.filas if not f.incompleta]
        hay_titulos = any(f.bloque for f in principales)
        resultado: dict[str, Bloque] = {}
        for fila in principales:
            if fila.bloque:
                titulo = fila.bloque
            else:
                titulo = BLOQUE_SIN_TITULO if hay_titulos else BLOQUE_UNICO
            resultado.setdefault(titulo, Bloque(titulo)).filas.append(fila)
        return list(resultado.values())

    def incompletas(self) -> list[FilaRevision]:
        return [f for f in self.filas if f.incompleta]

    def _filas_del_bloque(self, titulo: str) -> list[FilaRevision]:
        for bloque in self.bloques():
            if bloque.titulo == titulo:
                return bloque.filas
        raise ValueError(f"Bloque desconocido: {titulo}")

    def tildar_bloque(self, titulo: str) -> None:
        for fila in self._filas_del_bloque(titulo):
            if fila.tipo != "ignorar":
                fila.tildada = True
        self.hubo_cambios = True
        self._recalcular_marcas()

    def destildar_bloque(self, titulo: str) -> None:
        for fila in self._filas_del_bloque(titulo):
            fila.tildada = False
        self.hubo_cambios = True
        self._recalcular_marcas()

    SIN_CAMBIO = object()  # Para "no cambiar" la categoría o la persona.

    def cambiar_bloque(
        self,
        titulo: str,
        tipo: str | None = None,
        categoria=SIN_CAMBIO,
        persona=SIN_CAMBIO,
    ) -> None:
        """ "Cambiar tipo o categoría de todas..." (RN-78). tipo=None: no cambiar el tipo.
        categoria=None vuelve a la categoría por defecto."""
        if tipo in ("cuota", "sueldo"):
            raise ErrorDeValidacion(
                "La cuota se elige fila por fila."
                if tipo == "cuota"
                else "Solo una fila puede ser el sueldo."
            )
        if tipo == "me_deben" and persona in (self.SIN_CAMBIO, None):
            raise ErrorDeValidacion("Elegí una persona.", "persona")
        for fila in self._filas_del_bloque(titulo):
            if tipo is not None:
                self._aplicar_tipo(fila, tipo)
            if categoria is not self.SIN_CAMBIO and fila.tipo in TIPOS_GASTO:
                fila.categoria = categoria
            if persona is not self.SIN_CAMBIO and persona is not None and fila.tipo == "me_deben":
                fila.persona = persona
        self.hubo_cambios = True
        self._recalcular_marcas()

    # -- Errores, notas y estado (RN-68 a RN-71, RN-74) ----------------------

    def cantidad_sueldos(self) -> int:
        return sum(1 for f in self.filas if f.se_importa and f.tipo == "sueldo")

    def _errores_por_campo(self, fila: FilaRevision) -> dict[str, str]:
        """Los errores de RN-68 de una fila que se importa, por campo."""
        errores: dict[str, str] = {}
        if not fila.se_importa:
            return errores
        if not fila.nombre and fila.tipo != "sueldo":
            errores["nombre"] = "Falta el nombre."
        if fila.monto_cent is None:
            errores["monto"] = "Falta el monto."
        else:
            try:
                validar_centavos(fila.monto_cent)
            except ErrorDeValidacion as error:
                errores["monto"] = str(error)
        if fila.tipo in TIPOS_GASTO and not self._elegible(
            self.categoria_de(fila), catalogos.CATEGORIAS, self.categorias_nuevas
        ):
            errores["categoria"] = "Elegí una categoría."
        if fila.tipo == "me_deben" and not self._elegible(
            fila.persona, catalogos.PERSONAS, self.personas_nuevas
        ):
            errores["persona"] = "Elegí una persona."
        if fila.tipo == "cuota":
            n, total = fila.cuota_actual, fila.cuota_total
            if n is None or total is None:
                errores["cuota"] = "Indicá la cuota actual y la cantidad de cuotas."
            elif not _es_entero(total) or total < 1:
                errores["cuota"] = (
                    "La cantidad de cuotas tiene que ser un número entero de 1 o más."
                )
            elif total > cuotas.MAXIMO_CUOTAS:
                # Mismo tope y texto que crear_plan: si no, el guardado fallaría (BUG-33).
                errores["cuota"] = "La cantidad de cuotas es demasiado grande."
            elif not _es_entero(n) or not 1 <= n <= total:
                errores["cuota"] = (
                    "La cuota actual tiene que estar entre 1 y la cantidad de cuotas."
                )
            else:
                # crear_plan exige años de 4 dígitos: se avisa acá y no al guardar,
                # donde fallaría toda la importación (BUG-36, O77).
                primera = sumar_meses(self.anio, self.mes, -(n - 1))
                ultima = sumar_meses(*primera, total - 1)
                for anio, mes in (primera, ultima):
                    try:
                        meses.validar_anio_mes(anio, mes)
                    except ErrorDeValidacion:
                        errores["cuota"] = (
                            "Con esta cuota, el plan quedaría en un año no válido. "
                            "Revisá la cuota actual y la cantidad."
                        )
                        break
        if fila.tipo in TIPOS_GASTO and fila.pagado_cent:
            if fila.pagado_cent < 0:
                errores["pagado"] = "El pagado no puede ser negativo."
            elif fila.monto_cent is not None and fila.pagado_cent > fila.monto_cent:
                pagado, monto = formatear_ars(fila.pagado_cent), formatear_ars(fila.monto_cent)
                if pagado == monto:
                    # Redondeados a pesos se ven iguales: se muestran con centavos
                    # para que se entienda la diferencia (O70, RN-69).
                    pagado = "$ " + formatear_monto_para_editar(fila.pagado_cent)
                    monto = "$ " + formatear_monto_para_editar(fila.monto_cent)
                errores["pagado"] = f"El pagado ({pagado}) es mayor que el monto ({monto})."
        if fila.tipo == "sueldo" and self.cantidad_sueldos() > 1:
            errores["sueldo"] = (
                f"Marcaste {self.cantidad_sueldos()} filas como sueldo; dejá una sola."
            )
        return errores

    def _elegible(self, valor, tabla: str, nuevas: list[Nueva]) -> bool:
        """¿Se puede usar al guardar? Una Nueva de esta revisión, o un id activo.
        Algo archivado mientras dura la revisión cuenta como sin elegir (O67)."""
        if isinstance(valor, Nueva):
            return valor in nuevas
        return valor is not None and any(
            c["id"] == valor for c in catalogos.listar(self.con, tabla)
        )

    def errores(self, fila: FilaRevision) -> list[str]:
        return list(self._errores_por_campo(fila).values())

    def errores_por_campo(self, fila: FilaRevision) -> dict[str, str]:
        """Los errores de la fila por campo ("nombre", "monto", "categoria",
        "persona", "cuota", "pagado", "sueldo"), para el diálogo de edición."""
        return self._errores_por_campo(fila)

    def _nota_cuota(self, fila: FilaRevision) -> str | None:
        if "cuota" in self._errores_por_campo(fila) or fila.cuota_actual is None:
            return None
        return self.texto_plan(fila.cuota_actual, fila.cuota_total)

    def texto_plan(self, n, total) -> str | None:
        """Vista previa del plan con el mes destino (RN-71), o None si la cuota
        no es válida. La usa el diálogo de edición en cada tecla."""
        if not (_es_entero(n) and _es_entero(total) and 1 <= n <= total):
            return None
        if total > cuotas.MAXIMO_CUOTAS:
            return None
        # Primera cuota = mes destino − (n − 1) meses (RN-71). Con aritmética y no
        # mes por mes: un bucle con números grandes colgaba la app (BUG-34).
        primera = sumar_meses(self.anio, self.mes, -(n - 1))
        ultima = sumar_meses(*primera, total - 1)
        for anio, mes in (primera, ultima):
            try:
                meses.validar_anio_mes(anio, mes)
            except ErrorDeValidacion:
                return None
        cuotas_texto = "1 cuota" if total == 1 else f"{total} cuotas"
        return (
            f"Plan de {cuotas_texto}: primera {nombre_mes(*primera)}, "
            f"última {nombre_mes(*ultima)}. "
            f"Se agrega la cuota {n}/{total} en {self.nombre_mes_destino}."
        )

    def notas(self, fila: FilaRevision) -> list[str]:
        """Notas y avisos que no son errores, en el orden en que se muestran."""
        return [texto for _, texto in self.notas_con_clase(fila)]

    def notas_con_clase(self, fila: FilaRevision) -> list[tuple[str, str]]:
        """Como notas(), pero cada una con su clase, para elegir ícono y color:
        "ignorada" (fila incompleta), "aviso", "repetida", "compartido" o "info"."""
        notas: list[tuple[str, str]] = []
        if fila.tipo == "ignorar":
            if fila.incompleta:
                notas.append(
                    (
                        "ignorada",
                        "Falta el monto. Se ignora."
                        if fila.origen.nombre is not None
                        else "Falta el nombre. Se ignora.",
                    )
                )
            elif fila.origen.monto_cent is not None and fila.origen.monto_cent <= 0:
                notas.append(
                    ("aviso", "Monto no válido. Si querés importarla, corregí el monto.")
                )
        if fila.ya_existe == "gasto":
            notas.append(
                (
                    "aviso",
                    f"Ya existe en {self.nombre_mes_destino}. "
                    + ("Si la importás, queda repetida." if fila.tildada else "Viene destildada."),
                )
            )
        elif fila.ya_existe == "plan":
            notas.append(
                (
                    "aviso",
                    "Ya existe un plan de cuotas con este nombre. "
                    + ("Si la importás, queda repetida." if fila.tildada else "Viene destildada."),
                )
            )
        elif fila.ya_existe == "me_deben":
            persona = self.nombre_persona(fila.persona)
            notas.append(
                (
                    "aviso",
                    f"{persona} ya tiene un ítem sin cobrar con esta descripción. "
                    + ("Si la importás, queda repetida." if fila.tildada else "Viene destildada."),
                )
            )
        if fila.repetida:
            notas.append(
                (
                    "repetida",
                    "Repetida en el archivo. Si no es un error del Excel, podés importarla igual.",
                )
            )
        if fila.aviso_compartido:
            notas.append(
                (
                    "compartido",
                    "¿Es parte de un gasto compartido? Si es así, ignorala y marcá el gasto "
                    "como compartido después.",
                )
            )
        if fila.tipo == "me_deben" and fila.nota_cobrado:
            notas.append(("aviso", fila.nota_cobrado))
        if fila.tipo == "cuota":
            nota = self._nota_cuota(fila)
            if nota:
                notas.append(("info", nota))
        if fila.tipo == "sueldo" and fila.monto_cent and fila.monto_cent > 0:
            actual = self.sueldo_actual_cent()
            nuevo = formatear_usd(fila.monto_cent)
            if actual is None or actual == fila.monto_cent:
                notas.append(("info", f"Sueldo del mes: {nuevo}."))
            else:
                notas.append(("info", f"Sueldo del mes: {formatear_usd(actual)} -> {nuevo}."))
        return notas

    def nombre_persona(self, persona: int | Nueva | None) -> str:
        if isinstance(persona, Nueva):
            return persona.nombre
        for p in catalogos.listar(self.con, catalogos.PERSONAS, incluir_archivados=True):
            if p["id"] == persona:
                return p["nombre"]
        return ""

    def filas_con_errores(self) -> list[FilaRevision]:
        return [f for f in self.filas if self.errores(f)]

    def puede_confirmar(self) -> bool:
        return any(f.se_importa for f in self.filas) and not self.filas_con_errores()

    def conteo(self) -> dict[str, int]:
        importan = [f for f in self.filas if f.se_importa]
        return {
            "filas": len(importan),
            "gastos": sum(f.tipo in ("fijo", "unico") for f in importan),
            "planes": sum(f.tipo == "cuota" for f in importan),
            "me_deben": sum(f.tipo == "me_deben" for f in importan),
            "sueldo": sum(f.tipo == "sueldo" for f in importan),
        }

    def estado_pie(self) -> str:
        """RN-68: por qué se puede o no confirmar."""
        c = self.conteo()
        if c["filas"] == 0:
            return "No hay filas para importar."
        if c["sueldo"] > 1:
            return f"Marcaste {c['sueldo']} filas como sueldo; dejá una sola."
        con_errores = len(self.filas_con_errores())
        if con_errores == 1:
            return "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar."
        if con_errores:
            return (
                f"Hay {con_errores} filas con errores. Corregilas, ignoralas o destildalas "
                "para continuar."
            )
        partes = []
        if c["gastos"]:
            partes.append("1 gasto" if c["gastos"] == 1 else f"{c['gastos']} gastos")
        if c["planes"]:
            partes.append(
                "1 plan de cuotas" if c["planes"] == 1 else f"{c['planes']} planes de cuotas"
            )
        if c["me_deben"]:
            partes.append(
                '1 ítem "me deben"' if c["me_deben"] == 1 else f'{c["me_deben"]} ítems "me deben"'
            )
        if c["sueldo"]:
            partes.append("el sueldo")
        verbo = "Se importa 1 fila" if c["filas"] == 1 else f"Se importan {c['filas']} filas"
        return f"{verbo}: {unir_con_y(partes)}."
