"""Meses: primer mes, mes siguiente, borrar el último, consultas y edición.

Reglas: RF-01 a RF-05, RN-07 a RN-11 y RN-57 (docs/requisitos.md).
"""

import sqlite3
from datetime import date

from app.logica import compartidos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT, convertir_usd_a_ars, validar_centavos


def mes_actual_calendario(hoy: date | None = None) -> tuple[int, int]:
    """(año, mes) de hoy según el reloj del sistema.

    Recibe "hoy" opcional para que las pruebas puedan fijar la fecha y no
    dependan del día en que se corren.
    """
    # Se usa la fecha local de la computadora a propósito: el "mes actual" es
    # el que ve el usuario en su calendario, no el de otra zona horaria.
    hoy = hoy or date.today()  # noqa: DTZ011
    return hoy.year, hoy.month


def validar_anio_mes(anio: int, mes: int) -> None:
    """RN-07: año de 4 dígitos y mes de 1 a 12."""
    if not 1000 <= anio <= 9999:
        raise ErrorDeValidacion("El año tiene que tener 4 dígitos.", "anio")
    if not 1 <= mes <= 12:
        raise ErrorDeValidacion("El mes tiene que estar entre 1 y 12.", "mes")


def hay_meses(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM meses LIMIT 1").fetchone() is not None


def crear_primer_mes(
    con: sqlite3.Connection,
    anio: int,
    mes: int,
    sueldo_usd_cent: int,
    cotizacion_cent: int | None = None,
) -> int:
    """RF-04: crea el primer mes y devuelve su id.

    La cotización es opcional: puede quedar sin cargar (RN-18).
    """
    if hay_meses(con):
        raise ErrorDeValidacion(
            "Ya existe un mes. Los siguientes se crean con 'Mes nuevo'."
        )
    validar_anio_mes(anio, mes)
    validar_centavos(
        sueldo_usd_cent, permitir_cero=True, que="El sueldo", campo="sueldo"
    )
    if cotizacion_cent is not None:
        validar_centavos(cotizacion_cent, que="La cotización", campo="cotizacion")

    with con:
        cursor = con.execute(
            "INSERT INTO meses (anio, mes, sueldo_usd_cent, cotizacion_cent) VALUES (?, ?, ?, ?)",
            (anio, mes, sueldo_usd_cent, cotizacion_cent),
        )
    return cursor.lastrowid


def obtener_mes(con: sqlite3.Connection, mes_id: int) -> sqlite3.Row | None:
    return con.execute("SELECT * FROM meses WHERE id = ?", (mes_id,)).fetchone()


def obtener_ultimo_mes(con: sqlite3.Connection) -> sqlite3.Row | None:
    """El mes más reciente, o None si todavía no hay ninguno."""
    return con.execute(
        "SELECT * FROM meses ORDER BY anio DESC, mes DESC LIMIT 1"
    ).fetchone()


def exigir_mes(con: sqlite3.Connection, mes_id: int) -> sqlite3.Row:
    """Devuelve el mes, o lanza un error si ya no existe (ej. se borró por detrás)."""
    mes = obtener_mes(con, mes_id)
    if mes is None:
        raise ErrorDeValidacion("El mes no existe.")
    return mes


def editar_sueldo(con: sqlite3.Connection, mes_id: int, sueldo_usd_cent: int) -> None:
    """RF-23: cambia el sueldo en USD del mes. Puede ser 0 (con aviso en pantalla)."""
    exigir_mes(con, mes_id)
    validar_centavos(
        sueldo_usd_cent, permitir_cero=True, que="El sueldo", campo="sueldo"
    )
    with con:
        con.execute(
            "UPDATE meses SET sueldo_usd_cent = ? WHERE id = ?",
            (sueldo_usd_cent, mes_id),
        )


def editar_cotizacion(
    con: sqlite3.Connection, mes_id: int, cotizacion_cent: int
) -> None:
    """RF-25: cambia la cotización del mes en cualquier momento.

    No se puede volver a dejar vacía (decisión del usuario): solo cambiarla por
    otra. Los gastos en dólares ya cargados no cambian (RN-55).
    """
    exigir_mes(con, mes_id)
    if cotizacion_cent is None:
        raise ErrorDeValidacion("Ingresá la cotización.", "cotizacion")
    validar_centavos(cotizacion_cent, que="La cotización", campo="cotizacion")
    with con:
        con.execute(
            "UPDATE meses SET cotizacion_cent = ? WHERE id = ?",
            (cotizacion_cent, mes_id),
        )


# ----------------------------------------------------------------------
# Historial de meses (paso 4)
# ----------------------------------------------------------------------


def siguiente(anio: int, mes: int) -> tuple[int, int]:
    """(2026, 12) -> (2027, 1)."""
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def anterior(anio: int, mes: int) -> tuple[int, int]:
    """(2027, 1) -> (2026, 12)."""
    return (anio - 1, 12) if mes == 1 else (anio, mes - 1)


def listar_meses(con: sqlite3.Connection) -> list[sqlite3.Row]:
    """Todos los meses, del más nuevo al más viejo (como el selector de mes)."""
    return con.execute("SELECT * FROM meses ORDER BY anio DESC, mes DESC").fetchall()


def obtener_mes_por_fecha(
    con: sqlite3.Connection, anio: int, mes: int
) -> sqlite3.Row | None:
    return con.execute(
        "SELECT * FROM meses WHERE anio = ? AND mes = ?", (anio, mes)
    ).fetchone()


def mes_inicial(con: sqlite3.Connection, hoy: date | None = None) -> sqlite3.Row | None:
    """El mes que se muestra al abrir la app: el del calendario si existe; si no, el último."""
    actual = obtener_mes_por_fecha(con, *mes_actual_calendario(hoy))
    return actual or obtener_ultimo_mes(con)


def sugerencias_mes_siguiente(con: sqlite3.Connection) -> dict:
    """Lo que se propone al crear el mes siguiente (RN-09): año, mes, sueldo y
    cotización del último mes, y cuántos gastos fijos se van a copiar."""
    ultimo = obtener_ultimo_mes(con)
    if ultimo is None:
        raise ErrorDeValidacion("Todavía no hay meses: creá el primero.")
    anio, mes = siguiente(ultimo["anio"], ultimo["mes"])
    fijos = con.execute(
        "SELECT COUNT(*) AS total, COALESCE(SUM(moneda = 'USD'), 0) AS en_dolares "
        "FROM gastos WHERE mes_id = ? AND tipo = 'fijo'",
        (ultimo["id"],),
    ).fetchone()
    return {
        "anio": anio,
        "mes": mes,
        "sueldo_usd_cent": ultimo["sueldo_usd_cent"],
        "cotizacion_cent": ultimo["cotizacion_cent"],
        "fijos": fijos["total"],
        "fijos_en_dolares": fijos["en_dolares"],
        "cuotas": _cuotas_que_se_generarian(con, anio, mes),
    }


def _cuotas_que_se_generarian(con: sqlite3.Connection, anio: int, mes: int) -> int:
    from app.logica import cuotas  # Ver la nota en crear_mes sobre el import.

    return cuotas.cuotas_que_se_generarian(con, anio, mes)


def crear_mes(
    con: sqlite3.Connection,
    anio: int,
    mes: int,
    sueldo_usd_cent: int,
    cotizacion_cent: int | None = None,
    avisos: list[str] | None = None,
) -> int:
    """RF-03: crea un mes nuevo, que tiene que ser el siguiente al último (RN-08).

    Copia los gastos fijos del último mes sin pagos (RN-09); los fijos en dólares
    toman la cotización del mes nuevo, o conservan la suya si el mes nuevo no
    tiene (RN-57). Los fijos compartidos se copian con sus partes, sin cobrar (RN-37).
    No copia pagos únicos, ingresos extra ni cambios.
    Todo pasa en una sola transacción: o se crea el mes completo, o nada.

    avisos (opcional): lista donde se agregan mensajes para mostrar al usuario,
    por ejemplo si las partes de un gasto se repartieron en partes iguales.
    """
    ultimo = obtener_ultimo_mes(con)
    if ultimo is None:
        raise ErrorDeValidacion("Todavía no hay meses: creá el primero.")
    validar_anio_mes(anio, mes)
    esperado = siguiente(ultimo["anio"], ultimo["mes"])
    if (anio, mes) != esperado:
        raise ErrorDeValidacion(
            f"Solo se puede crear el mes siguiente al último ({esperado[1]:02d}/{esperado[0]}).",
            "mes",
        )
    validar_centavos(
        sueldo_usd_cent, permitir_cero=True, que="El sueldo", campo="sueldo"
    )
    if cotizacion_cent is not None:
        validar_centavos(cotizacion_cent, que="La cotización", campo="cotizacion")

    fijos = con.execute(
        "SELECT * FROM gastos WHERE mes_id = ? AND tipo = 'fijo' ORDER BY id",
        (ultimo["id"],),
    ).fetchall()
    # Primero se calculan y validan todas las copias, antes de guardar nada.
    copias = []
    for gasto in fijos:
        monto_cent = gasto["monto_cent"]
        cotizacion_gasto = gasto["cotizacion_cent"]
        if gasto["moneda"] == "USD":
            # RN-57: mismos dólares, cotización del mes nuevo (si tiene).
            if cotizacion_cent is not None:
                cotizacion_gasto = cotizacion_cent
            monto_cent = convertir_usd_a_ars(gasto["monto_usd_cent"], cotizacion_gasto)
            # BUG-15: igual que al cargar un gasto en dólares (RN-54), los pesos
            # tienen que ser mayores a 0 y no pasar el tope.
            if not 0 < monto_cent <= MONTO_MAXIMO_CENT:
                pesos = "da $ 0" if monto_cent == 0 else "da un monto demasiado grande"
                raise ErrorDeValidacion(
                    f'Con esta cotización, el gasto "{gasto["nombre"]}" en dólares {pesos}. '
                    "Revisá la cotización.",
                    "cotizacion",
                )
        copias.append((gasto, monto_cent, cotizacion_gasto))

    with con:
        cursor = con.execute(
            "INSERT INTO meses (anio, mes, sueldo_usd_cent, cotizacion_cent) VALUES (?, ?, ?, ?)",
            (anio, mes, sueldo_usd_cent, cotizacion_cent),
        )
        nuevo_id = cursor.lastrowid
        for gasto, monto_cent, cotizacion_gasto in copias:
            # Se copian aunque la categoría o el medio estén archivados (RN-09).
            copia = con.execute(
                """INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo,
                                       medio_pago_id, moneda, monto_usd_cent, cotizacion_cent)
                   VALUES (?, ?, ?, ?, 'fijo', ?, ?, ?, ?)""",
                (
                    nuevo_id,
                    gasto["nombre"],
                    gasto["categoria_id"],
                    monto_cent,
                    gasto["medio_pago_id"],
                    gasto["moneda"],
                    gasto["monto_usd_cent"],
                    cotizacion_gasto,
                ),
            )
            # RN-37: las partes, sin cobrar. Si hubo que repartirlas en partes
            # iguales (la parte del usuario quedaba negativa), se avisa.
            repartido = compartidos.copiar_partes(
                con, gasto["id"], copia.lastrowid, monto_cent
            )
            if repartido and avisos is not None:
                avisos.append(
                    f"Las partes de {gasto['nombre']} se repartieron en partes iguales "
                    "porque cambió el monto."
                )
        # RN-09: una cuota por cada plan activo en el mes nuevo, en la misma
        # transacción. Se importa acá adentro porque cuotas.py usa este módulo
        # (meses): importarlo arriba armaría un círculo de imports.
        from app.logica import cuotas

        cuotas.generar_cuotas_del_mes(con, nuevo_id)
    return nuevo_id


def crear_mes_siguiente(
    con: sqlite3.Connection, sueldo_usd_cent: int, cotizacion_cent: int | None = None
) -> int:
    """Atajo de crear_mes: calcula solo cuál es el mes siguiente al último."""
    ultimo = obtener_ultimo_mes(con)
    if ultimo is None:
        raise ErrorDeValidacion("Todavía no hay meses: creá el primero.")
    anio, mes = siguiente(ultimo["anio"], ultimo["mes"])
    return crear_mes(con, anio, mes, sueldo_usd_cent, cotizacion_cent)


def borrar_ultimo_mes(con: sqlite3.Connection, mes_id: int) -> None:
    """RF-05 / RN-10: borra el último mes con sus gastos, pagos, partes, extras y cambios.

    Gracias a ON DELETE CASCADE, la base borra sola todo lo que cuelga del mes.
    Los planes de cuotas, las cuotas omitidas y los ítems manuales de "me deben"
    no dependen del mes y no se tocan. La confirmación la pide la pantalla.
    """
    mes = exigir_mes(con, mes_id)
    ultimo = obtener_ultimo_mes(con)
    if mes["id"] != ultimo["id"]:
        raise ErrorDeValidacion("Solo se puede borrar el último mes.")
    with con:
        con.execute("DELETE FROM meses WHERE id = ?", (mes_id,))
