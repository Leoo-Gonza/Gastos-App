"""Gastos compartidos: las partes de cada persona (RF-29 a RF-31, RN-32 a RN-34, RN-37).

Un gasto es compartido si tiene al menos una fila en partes_gasto. La parte del
usuario no se guarda: es monto − Σ partes de las personas, así la suma siempre cierra.

Las partes se describen con una lista de (persona_id, monto_manual), donde
monto_manual es None si la parte es automática (partes iguales) o los centavos
que escribió el usuario si la editó a mano.

Este módulo no hace commit: lo usan gastos.py y meses.py dentro de sus transacciones.
"""

import sqlite3

from app.logica import catalogos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, validar_centavos


def parte_igual(monto_cent: int, cantidad_personas: int) -> int:
    """RN-32: parte de cada persona en partes iguales, truncada al centavo.

    Participan las personas más el usuario. Ej.: 66.281 entre 3 -> 22.093,66
    (el usuario se queda con los centavos que sobran: 22.093,68).
    """
    return monto_cent // (cantidad_personas + 1)


def calcular_partes(
    monto_cent: int, personas: list[tuple[int, int | None]]
) -> dict[int, tuple[int, bool]]:
    """Calcula las partes: {persona_id: (monto, es_manual)}.

    Las manuales se respetan; las automáticas son partes iguales (RN-32, RN-33).
    Si la parte del usuario quedaría negativa, lanza un error con campo "partes".
    """
    automatica = parte_igual(monto_cent, len(personas))
    partes = {}
    for persona_id, manual in personas:
        if manual is None:
            partes[persona_id] = (automatica, False)
        else:
            validar_centavos(manual, permitir_cero=True, que="La parte", campo="partes")
            partes[persona_id] = (manual, True)
    suma = sum(monto for monto, _ in partes.values())
    if suma > monto_cent:
        raise ErrorDeValidacion(
            f"Las partes suman {formatear_ars(suma)} y superan el monto "
            f"({formatear_ars(monto_cent)}).",
            "partes",
        )
    return partes


def obtener_partes(con: sqlite3.Connection, gasto_id: int) -> list[sqlite3.Row]:
    """Partes de un gasto con el nombre de la persona, en el orden en que se cargaron."""
    return con.execute(
        """SELECT pg.*, p.nombre AS persona, p.archivado AS persona_archivada
             FROM partes_gasto pg JOIN personas p ON p.id = pg.persona_id
            WHERE pg.gasto_id = ? ORDER BY pg.id""",
        (gasto_id,),
    ).fetchall()


def personas_actuales(
    con: sqlite3.Connection, gasto_id: int
) -> list[tuple[int, int | None]]:
    """Las partes de un gasto en el formato (persona_id, monto_manual o None)."""
    return [
        (p["persona_id"], p["monto_cent"] if p["editada_a_mano"] else None)
        for p in obtener_partes(con, gasto_id)
    ]


def parte_del_usuario(con: sqlite3.Connection, gasto_id: int, monto_cent: int) -> int:
    suma = con.execute(
        "SELECT COALESCE(SUM(monto_cent), 0) AS s FROM partes_gasto WHERE gasto_id = ?",
        (gasto_id,),
    ).fetchone()["s"]
    return monto_cent - suma


def validar_personas(
    con: sqlite3.Connection,
    personas: list[tuple[int, int | None]],
    gasto_id: int | None,
    tipo: str,
) -> None:
    """Personas válidas y no repetidas; archivadas solo si ya estaban en el gasto (RN-49).

    Las cuotas no se comparten (decisión del usuario, paso 5).
    """
    if not personas:
        return
    if tipo == "cuota":
        raise ErrorDeValidacion("Las cuotas no se pueden compartir.", "compartido")
    ids = [persona_id for persona_id, _ in personas]
    if len(ids) != len(set(ids)):
        raise ErrorDeValidacion("Una persona aparece dos veces.", "compartido")
    ya_estaban = set()
    if gasto_id is not None:
        ya_estaban = {p["persona_id"] for p in obtener_partes(con, gasto_id)}
    for persona_id in ids:
        persona = catalogos.obtener(con, catalogos.PERSONAS, persona_id)
        if persona is None:
            raise ErrorDeValidacion(
                "Una de las personas elegidas ya no existe.", "compartido"
            )
        if persona["archivado"] and persona_id not in ya_estaban:
            raise ErrorDeValidacion(
                f"La persona {persona['nombre']} está archivada: desarchivala para compartir gastos.",
                "compartido",
            )


def guardar_partes(
    con: sqlite3.Connection,
    gasto_id: int,
    monto_cent: int,
    personas: list[tuple[int, int | None]],
) -> None:
    """Deja las partes del gasto como dice "personas" (lista vacía = no compartido).

    Para cada parte que ya existía y estaba cobrada (RN-34):
    - si su monto no cambió, sigue cobrada;
    - si cambió, vuelve a pendiente y se conserva lo cobrado, para mostrar la
      diferencia ("falta $ X" o "a devolver $ X").
    Sin commit: la llama gastos.py dentro de su transacción.
    """
    nuevas = calcular_partes(monto_cent, personas) if personas else {}
    viejas = {p["persona_id"]: p for p in obtener_partes(con, gasto_id)}
    for persona_id, vieja in viejas.items():
        if persona_id not in nuevas:
            con.execute("DELETE FROM partes_gasto WHERE id = ?", (vieja["id"],))
    for persona_id, (monto, manual) in nuevas.items():
        vieja = viejas.get(persona_id)
        if vieja is None:
            con.execute(
                "INSERT INTO partes_gasto (gasto_id, persona_id, monto_cent, editada_a_mano) "
                "VALUES (?, ?, ?, ?)",
                (gasto_id, persona_id, monto, int(manual)),
            )
            continue
        cobrado = vieja["cobrado"]
        if cobrado and monto != vieja["monto_cent"]:
            cobrado = 0  # RN-34: cambió el monto: vuelve a pendiente; cobrado_cent se conserva.
        con.execute(
            "UPDATE partes_gasto SET monto_cent = ?, editada_a_mano = ?, cobrado = ? "
            "WHERE id = ?",
            (monto, int(manual), cobrado, vieja["id"]),
        )


def copiar_partes(
    con: sqlite3.Connection, origen_id: int, destino_id: int, monto_cent: int
) -> bool:
    """RN-37: copia las partes de un fijo al mes nuevo, sin cobrar.

    Las automáticas se calculan sobre el monto nuevo y las manuales se mantienen.
    Si así la parte del usuario quedaría negativa, todas pasan a partes iguales y
    devuelve True (para avisar al usuario). Sin commit.
    """
    personas = personas_actuales(con, origen_id)
    if not personas:
        return False
    repartido = False
    try:
        partes = calcular_partes(monto_cent, personas)
    except ErrorDeValidacion:
        partes = calcular_partes(monto_cent, [(p, None) for p, _ in personas])
        repartido = True
    for persona_id, (monto, manual) in partes.items():
        con.execute(
            "INSERT INTO partes_gasto (gasto_id, persona_id, monto_cent, editada_a_mano) "
            "VALUES (?, ?, ?, ?)",
            (destino_id, persona_id, monto, int(manual)),
        )
    return repartido


def marcar_cobrada(
    con: sqlite3.Connection, parte_id: int, cobrada: bool
) -> tuple[bool, int]:
    """RF-34: tilde "cobrado" de una parte.

    Marcar registra como cobrada la parte completa (RN-34); desmarcar deja lo
    cobrado en 0. Devuelve cómo estaba antes (cobrado, cobrado_cent), para que
    "Deshacer" pueda volver exactamente a ese estado (O41).
    Esta sí hace commit: se usa directo desde la pantalla Me deben.
    """
    parte = con.execute(
        "SELECT * FROM partes_gasto WHERE id = ?", (parte_id,)
    ).fetchone()
    if parte is None:
        raise ErrorDeValidacion("Esa parte ya no existe.")
    with con:
        con.execute(
            "UPDATE partes_gasto SET cobrado = ?, cobrado_cent = ? WHERE id = ?",
            (int(cobrada), parte["monto_cent"] if cobrada else 0, parte_id),
        )
    return bool(parte["cobrado"]), parte["cobrado_cent"]


def restaurar_cobro(
    con: sqlite3.Connection, parte_id: int, cobrado: bool, cobrado_cent: int
) -> None:
    """ "Deshacer" de marcar/desmarcar: deja la parte como estaba (O41).

    Así no se pierde, por ejemplo, "cobrado $ 12.900 · a devolver $ 2.900".
    """
    validar_centavos(cobrado_cent, permitir_cero=True, que="Lo cobrado")
    with con:
        cursor = con.execute(
            "UPDATE partes_gasto SET cobrado = ?, cobrado_cent = ? WHERE id = ?",
            (int(cobrado), cobrado_cent, parte_id),
        )
    if cursor.rowcount == 0:
        raise ErrorDeValidacion("Esa parte ya no existe.")
