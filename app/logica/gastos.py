"""Gastos de un mes: alta, edición, baja, lista y total (RF-06 a RF-09)."""

import sqlite3

from app.logica import catalogos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, validar_centavos

# Nombres para mostrar de cada tipo. Los gastos tipo "cuota" se crean desde un
# plan de cuotas (paso 4), no con agregar_gasto.
TIPOS = {"fijo": "Fijo mensual", "unico": "Pago único", "cuota": "Cuota"}
_TIPOS_EDITABLES = ("fijo", "unico")


def _validar_nombre(nombre: str) -> str:
    limpio = " ".join(nombre.split())
    if not limpio:
        raise ErrorDeValidacion("Ingresá un nombre para el gasto.", "nombre")
    return limpio


def _validar_mes(con: sqlite3.Connection, mes_id: int) -> None:
    if con.execute("SELECT 1 FROM meses WHERE id = ?", (mes_id,)).fetchone() is None:
        raise ErrorDeValidacion("El mes no existe.")


def _validar_tipo(tipo: str) -> None:
    if tipo not in _TIPOS_EDITABLES:
        raise ErrorDeValidacion(
            "El tipo tiene que ser 'Fijo mensual' o 'Pago único'.", "tipo"
        )


def _validar_categoria(
    con: sqlite3.Connection, categoria_id: int | None, id_actual: int | None = None
) -> None:
    if categoria_id is None:
        raise ErrorDeValidacion("Elegí una categoría.", "categoria")
    fila = catalogos.obtener(con, catalogos.CATEGORIAS, categoria_id)
    if fila is None:
        raise ErrorDeValidacion("La categoría elegida no existe.", "categoria")
    # Una categoría archivada no se puede elegir para cargar algo nuevo (RN-49),
    # pero un gasto que ya la tenía puede conservarla al editarse.
    if fila["archivado"] and categoria_id != id_actual:
        raise ErrorDeValidacion("La categoría elegida está archivada.", "categoria")


def _validar_medio_pago(
    con: sqlite3.Connection, medio_pago_id: int | None, id_actual: int | None = None
) -> None:
    if medio_pago_id is None:
        return  # El medio de pago es opcional.
    fila = catalogos.obtener(con, catalogos.MEDIOS_PAGO, medio_pago_id)
    if fila is None:
        raise ErrorDeValidacion("El medio de pago elegido no existe.", "medio_pago")
    if fila["archivado"] and medio_pago_id != id_actual:
        raise ErrorDeValidacion(
            "El medio de pago elegido está archivado.", "medio_pago"
        )


def total_pagado(con: sqlite3.Connection, gasto_id: int) -> int:
    """Suma de los pagos de un gasto, en centavos."""
    fila = con.execute(
        "SELECT COALESCE(SUM(monto_cent), 0) AS total FROM pagos WHERE gasto_id = ?",
        (gasto_id,),
    ).fetchone()
    return fila["total"]


def obtener_gasto(con: sqlite3.Connection, gasto_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM gastos WHERE id = ?", (gasto_id,)).fetchone()


def agregar_gasto(
    con: sqlite3.Connection,
    mes_id: int,
    nombre: str,
    categoria_id: int | None,
    monto_cent: int,
    tipo: str,
    medio_pago_id: int | None = None,
) -> int:
    """RF-06: da de alta un gasto y devuelve su id."""
    _validar_mes(con, mes_id)
    nombre = _validar_nombre(nombre)
    _validar_categoria(con, categoria_id)
    validar_centavos(monto_cent, campo="monto")
    _validar_tipo(tipo)
    _validar_medio_pago(con, medio_pago_id)

    with con:
        cursor = con.execute(
            """INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, medio_pago_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (mes_id, nombre, categoria_id, monto_cent, tipo, medio_pago_id),
        )
    return cursor.lastrowid


def editar_gasto(
    con: sqlite3.Connection,
    gasto_id: int,
    nombre: str,
    categoria_id: int | None,
    monto_cent: int,
    tipo: str,
    medio_pago_id: int | None = None,
) -> None:
    """RF-07: modifica un gasto. Solo afecta a este mes (RN-11)."""
    actual = obtener_gasto(con, gasto_id)
    if actual is None:
        raise ErrorDeValidacion("El gasto ya no existe.")
    if actual["tipo"] == "cuota":
        raise ErrorDeValidacion("Las cuotas se editan desde su plan de cuotas.")

    nombre = _validar_nombre(nombre)
    _validar_categoria(con, categoria_id, id_actual=actual["categoria_id"])
    validar_centavos(monto_cent, campo="monto")
    _validar_tipo(tipo)
    _validar_medio_pago(con, medio_pago_id, id_actual=actual["medio_pago_id"])

    # RN-23: el monto no puede quedar por debajo de lo que ya se pagó.
    pagado = total_pagado(con, gasto_id)
    if monto_cent < pagado:
        raise ErrorDeValidacion(
            f"No podés bajar el monto a menos de lo que ya pagaste ({formatear_ars(pagado)}).",
            "monto",
        )

    with con:
        con.execute(
            """UPDATE gastos
               SET nombre = ?, categoria_id = ?, monto_cent = ?, tipo = ?, medio_pago_id = ?
               WHERE id = ?""",
            (nombre, categoria_id, monto_cent, tipo, medio_pago_id, gasto_id),
        )


def borrar_gasto(con: sqlite3.Connection, gasto_id: int) -> None:
    """RF-08 / RN-51: borra el gasto. Sus pagos y partes compartidas se borran solos
    gracias a ON DELETE CASCADE en la base de datos.

    La confirmación ("¿Seguro?") la pide la pantalla antes de llamar a esta función.
    """
    with con:
        con.execute("DELETE FROM gastos WHERE id = ?", (gasto_id,))


def listar_gastos(con: sqlite3.Connection, mes_id: int) -> list[sqlite3.Row]:
    """RF-09: gastos del mes con el nombre de su categoría y medio de pago.

    Incluye pagado_cent (suma de pagos) para que la pantalla no tenga que
    hacer una consulta por cada fila.
    """
    return con.execute(
        """SELECT g.id, g.nombre, g.monto_cent, g.tipo,
                  g.categoria_id, c.nombre AS categoria, c.archivado AS categoria_archivada,
                  g.medio_pago_id, m.nombre AS medio_pago, m.archivado AS medio_pago_archivado,
                  (SELECT COALESCE(SUM(p.monto_cent), 0)
                     FROM pagos p WHERE p.gasto_id = g.id) AS pagado_cent
             FROM gastos g
             JOIN categorias c ON c.id = g.categoria_id
             LEFT JOIN medios_pago m ON m.id = g.medio_pago_id
            WHERE g.mes_id = ?
            ORDER BY g.id""",
        (mes_id,),
    ).fetchall()


def total_gastos(con: sqlite3.Connection, mes_id: int) -> int:
    """Suma de los montos del mes, en centavos (sin redondear, RN-04)."""
    fila = con.execute(
        "SELECT COALESCE(SUM(monto_cent), 0) AS total FROM gastos WHERE mes_id = ?",
        (mes_id,),
    ).fetchone()
    return fila["total"]
