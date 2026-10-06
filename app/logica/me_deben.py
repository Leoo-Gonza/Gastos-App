"""Lo que le deben al usuario (RF-32 a RF-34, RN-35, RN-36, RN-40).

Junta, por persona y acumulado de todos los meses:
- sus partes de gastos compartidos (de compartidos.py), y
- los ítems cargados a mano ("Préstamo MP $ 20.000").
Nada de esto cambia los cálculos del mes (RN-36): se muestra aparte.
"""

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime

from app.logica import catalogos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import clave_orden, validar_centavos

# ----------------------------------------------------------------------
# Ítems cargados a mano
# ----------------------------------------------------------------------


def _validar_item(
    con: sqlite3.Connection,
    persona_id: int | None,
    descripcion: str,
    monto_cent: int,
    persona_actual: int | None = None,
) -> str:
    if persona_id is None:
        raise ErrorDeValidacion("Elegí una persona.", "persona")
    persona = catalogos.obtener(con, catalogos.PERSONAS, persona_id)
    if persona is None:
        raise ErrorDeValidacion("Esa persona ya no existe.", "persona")
    if persona["archivado"] and persona_id != persona_actual:
        raise ErrorDeValidacion(
            f"La persona {persona['nombre']} está archivada.", "persona"
        )
    limpia = " ".join((descripcion or "").split())
    if not limpia:
        raise ErrorDeValidacion("Ingresá una descripción.", "descripcion")
    validar_centavos(monto_cent, campo="monto")
    return limpia


def _fecha_iso(fecha: date | None) -> str:
    # Fecha local a propósito: el día que el usuario ve en su calendario.
    fecha = fecha or date.today()  # noqa: DTZ011
    if isinstance(fecha, datetime):  # Un datetime también es un date: solo el día.
        fecha = fecha.date()
    return fecha.isoformat()


def agregar_item(
    con: sqlite3.Connection,
    persona_id: int | None,
    descripcion: str,
    monto_cent: int,
    fecha: date | None = None,
) -> int:
    """RF-32: un ítem a mano, no cobrado. Ej.: Sofía, "Préstamo MP", 20.000."""
    descripcion = _validar_item(con, persona_id, descripcion, monto_cent)
    with con:
        cursor = con.execute(
            "INSERT INTO items_me_deben (persona_id, descripcion, monto_cent, fecha) "
            "VALUES (?, ?, ?, ?)",
            (persona_id, descripcion, monto_cent, _fecha_iso(fecha)),
        )
    return cursor.lastrowid


def obtener_item(con: sqlite3.Connection, item_id: int) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM items_me_deben WHERE id = ?", (item_id,)
    ).fetchone()


def editar_item(
    con: sqlite3.Connection,
    item_id: int,
    persona_id: int | None,
    descripcion: str,
    monto_cent: int,
    fecha: date | None = None,
) -> None:
    """Editar un ítem a mano (lo pidió el diseño, §7 obs. 3). Sin fecha conserva la suya."""
    actual = obtener_item(con, item_id)
    if actual is None:
        raise ErrorDeValidacion("Ese ítem ya no existe.")
    descripcion = _validar_item(
        con, persona_id, descripcion, monto_cent, persona_actual=actual["persona_id"]
    )
    fecha_iso = _fecha_iso(fecha) if fecha else actual["fecha"]
    with con:
        con.execute(
            "UPDATE items_me_deben SET persona_id = ?, descripcion = ?, monto_cent = ?, "
            "fecha = ? WHERE id = ?",
            (persona_id, descripcion, monto_cent, fecha_iso, item_id),
        )


def borrar_item(con: sqlite3.Connection, item_id: int) -> None:
    with con:
        cursor = con.execute("DELETE FROM items_me_deben WHERE id = ?", (item_id,))
    if cursor.rowcount == 0:
        raise ErrorDeValidacion("Ese ítem ya no existe.")


def marcar_item_cobrado(con: sqlite3.Connection, item_id: int, cobrado: bool) -> None:
    """RF-34: tilde "cobrado" de un ítem a mano (se puede desmarcar)."""
    with con:
        cursor = con.execute(
            "UPDATE items_me_deben SET cobrado = ? WHERE id = ?",
            (int(cobrado), item_id),
        )
    if cursor.rowcount == 0:
        raise ErrorDeValidacion("Ese ítem ya no existe.")


# ----------------------------------------------------------------------
# Lista por persona
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class Linea:
    """Una línea de "me deben": una parte de gasto o un ítem a mano."""

    tipo: str  # "parte" o "item"
    id: int  # id de la parte (partes_gasto) o del ítem (items_me_deben)
    descripcion: str
    monto: int  # la parte, o el monto del ítem
    cobrado: bool
    cobrado_cent: int  # lo ya cobrado de una parte (0 en los ítems)
    pendiente: int  # lo que suma al total (RN-35); negativo = "a devolver"
    anio: int | None  # mes del gasto (solo partes)
    mes: int | None
    fecha: str | None  # fecha ISO (solo ítems)


def lineas_de(
    con: sqlite3.Connection, persona_id: int, incluir_cobradas: bool = False
) -> list[Linea]:
    """RF-33: las líneas de una persona, de todos los meses.

    Por defecto solo las pendientes. Orden: las partes por mes y después los ítems
    por fecha, de lo más viejo a lo más nuevo.
    """
    lineas = []
    for p in con.execute(
        """SELECT pg.*, g.nombre AS gasto, m.anio, m.mes
             FROM partes_gasto pg
             JOIN gastos g ON g.id = pg.gasto_id
             JOIN meses m ON m.id = g.mes_id
            WHERE pg.persona_id = ?
            ORDER BY m.anio, m.mes, pg.id""",
        (persona_id,),
    ):
        cobrada = bool(p["cobrado"])
        # RN-35: una parte no cobrada aporta lo que falta (parte − ya cobrado).
        pendiente = 0 if cobrada else p["monto_cent"] - p["cobrado_cent"]
        if cobrada and not incluir_cobradas:
            continue
        lineas.append(
            Linea(
                "parte",
                p["id"],
                p["gasto"],
                p["monto_cent"],
                cobrada,
                p["cobrado_cent"],
                pendiente,
                p["anio"],
                p["mes"],
                None,
            )
        )
    for i in con.execute(
        "SELECT * FROM items_me_deben WHERE persona_id = ? ORDER BY fecha, id",
        (persona_id,),
    ):
        cobrado = bool(i["cobrado"])
        if cobrado and not incluir_cobradas:
            continue
        lineas.append(
            Linea(
                "item",
                i["id"],
                i["descripcion"],
                i["monto_cent"],
                cobrado,
                0,
                0 if cobrado else i["monto_cent"],
                None,
                None,
                i["fecha"],
            )
        )
    return lineas


def total_de(con: sqlite3.Connection, persona_id: int) -> int:
    """RN-35: total pendiente de una persona (negativo si solo hay "a devolver")."""
    return sum(linea.pendiente for linea in lineas_de(con, persona_id))


def total_general(con: sqlite3.Connection) -> int:
    """RN-40: lo que le deben entre todas las personas, acumulado."""
    personas = con.execute("SELECT id FROM personas").fetchall()
    return sum(total_de(con, p["id"]) for p in personas)


def personas_para_mostrar(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """Las personas de la pantalla Me deben: las no archivadas y las archivadas que
    todavía tienen algo pendiente. Ordenadas por nombre sin acentos."""
    filas = con.execute("SELECT * FROM personas").fetchall()
    visibles = [p for p in filas if not p["archivado"] or lineas_de(con, p["id"])]
    return sorted(visibles, key=lambda p: clave_orden(p["nombre"]))
