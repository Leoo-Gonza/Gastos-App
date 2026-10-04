"""Gastos de un mes: alta, edición, baja, lista y total (RF-06 a RF-09).

Un gasto puede ser en pesos o en dólares (RF-43 a RF-46). Los de dólares se
pagan en pesos: monto_cent siempre es el monto en ARS, así los totales y los
pagos funcionan igual para los dos.
"""

import sqlite3

from app.logica import catalogos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import convertir_usd_a_ars, formatear_ars, validar_centavos

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


def _resolver_monto(
    moneda: str,
    monto_cent: int | None,
    monto_usd_cent: int | None,
    cotizacion_cent: int | None,
) -> tuple[int, int | None, int | None]:
    """Valida el monto según la moneda y devuelve lo que se guarda:
    (monto en ARS, monto en USD o None, cotización o None).

    En USD los pesos se calculan acá (RN-53): quien llama no los pasa.
    """
    if moneda == "ARS":
        validar_centavos(monto_cent, campo="monto")
        return monto_cent, None, None
    if moneda != "USD":
        raise ErrorDeValidacion("La moneda tiene que ser ARS o USD.", "moneda")

    # RN-54: dólares y cotización obligatorios y mayores a 0.
    validar_centavos(monto_usd_cent, que="El monto en dólares", campo="monto_usd")
    validar_centavos(cotizacion_cent, que="La cotización", campo="cotizacion")
    monto_ars = convertir_usd_a_ars(monto_usd_cent, cotizacion_cent)
    if monto_ars == 0:
        raise ErrorDeValidacion(
            "Con estos valores el gasto da $ 0. Revisá el monto y la cotización.",
            "resultado",
        )
    validar_centavos(monto_ars, que="El monto en pesos", campo="resultado")
    return monto_ars, monto_usd_cent, cotizacion_cent


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
    monto_cent: int | None,
    tipo: str,
    medio_pago_id: int | None = None,
    moneda: str = "ARS",
    monto_usd_cent: int | None = None,
    cotizacion_cent: int | None = None,
) -> int:
    """RF-06 / RF-44: da de alta un gasto y devuelve su id.

    En pesos se pasa monto_cent. En dólares se pasa moneda="USD", monto_usd_cent
    y cotizacion_cent (la del día); monto_cent se ignora y se calcula.
    """
    _validar_mes(con, mes_id)
    nombre = _validar_nombre(nombre)
    _validar_categoria(con, categoria_id)
    monto_cent, monto_usd_cent, cotizacion_cent = _resolver_monto(
        moneda, monto_cent, monto_usd_cent, cotizacion_cent
    )
    _validar_tipo(tipo)
    _validar_medio_pago(con, medio_pago_id)

    with con:
        cursor = con.execute(
            """INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo,
                                   medio_pago_id, moneda, monto_usd_cent, cotizacion_cent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                mes_id,
                nombre,
                categoria_id,
                monto_cent,
                tipo,
                medio_pago_id,
                moneda,
                monto_usd_cent,
                cotizacion_cent,
            ),
        )
    return cursor.lastrowid


def editar_gasto(
    con: sqlite3.Connection,
    gasto_id: int,
    nombre: str,
    categoria_id: int | None,
    monto_cent: int | None,
    tipo: str,
    medio_pago_id: int | None = None,
    moneda: str = "ARS",
    monto_usd_cent: int | None = None,
    cotizacion_cent: int | None = None,
) -> None:
    """RF-07 / RF-45: modifica un gasto. Solo afecta a este mes (RN-11).

    Se puede cambiar la moneda (RN-56). Los parámetros son los mismos que en
    agregar_gasto.
    """
    actual = obtener_gasto(con, gasto_id)
    if actual is None:
        raise ErrorDeValidacion("El gasto ya no existe.")
    if actual["tipo"] == "cuota":
        raise ErrorDeValidacion("Las cuotas se editan desde su plan de cuotas.")

    nombre = _validar_nombre(nombre)
    _validar_categoria(con, categoria_id, id_actual=actual["categoria_id"])
    monto_cent, monto_usd_cent, cotizacion_cent = _resolver_monto(
        moneda, monto_cent, monto_usd_cent, cotizacion_cent
    )
    _validar_tipo(tipo)
    _validar_medio_pago(con, medio_pago_id, id_actual=actual["medio_pago_id"])

    # RN-23: el monto en pesos no puede quedar por debajo de lo que ya se pagó.
    # En dólares se controla sobre el resultado de la conversión (RN-55).
    pagado = total_pagado(con, gasto_id)
    if monto_cent < pagado:
        if moneda == "USD":
            raise ErrorDeValidacion(
                f"Con estos valores el gasto queda en {formatear_ars(monto_cent)}, menos de "
                f"lo que ya pagaste ({formatear_ars(pagado)}). Subí el monto o la cotización.",
                "resultado",
            )
        raise ErrorDeValidacion(
            f"No podés bajar el monto a menos de lo que ya pagaste ({formatear_ars(pagado)}).",
            "monto",
        )

    with con:
        con.execute(
            """UPDATE gastos
               SET nombre = ?, categoria_id = ?, monto_cent = ?, tipo = ?, medio_pago_id = ?,
                   moneda = ?, monto_usd_cent = ?, cotizacion_cent = ?
               WHERE id = ?""",
            (
                nombre,
                categoria_id,
                monto_cent,
                tipo,
                medio_pago_id,
                moneda,
                monto_usd_cent,
                cotizacion_cent,
                gasto_id,
            ),
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
                  g.moneda, g.monto_usd_cent, g.cotizacion_cent,
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
