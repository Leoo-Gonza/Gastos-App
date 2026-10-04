"""Conexión a SQLite, creación de las tablas y actualización de bases viejas.

Modelo de datos: docs/requisitos.md §5. Actualizaciones: RN-59.
"""

import sqlite3
from datetime import datetime
from pathlib import Path

# La base real vive en datos-privados/, que está excluida de git.
# parents[2] sube de app/logica/base_datos.py a la raíz del proyecto.
RUTA_POR_DEFECTO = Path(__file__).resolve().parents[2] / "datos-privados" / "gastos.db"

CATEGORIAS_INICIALES = [
    "Vivienda",
    "Servicios",
    "Transporte",
    "Mercado",
    "Salud",
    "Deudas",
    "Otros",
]
MEDIOS_PAGO_INICIALES = ["Tarjeta de crédito", "Efectivo", "Transferencia"]

# Versión de la estructura de la base. Se guarda dentro del archivo con
# PRAGMA user_version (un número que SQLite reserva para esto).
#   0: estructura del paso 1.
#   1: gastos en dólares (columnas moneda, monto_usd_cent y cotizacion_cent).
VERSION_ACTUAL = 1


class ErrorDeBase(Exception):
    """La base no se pudo abrir o actualizar. El mensaje es para mostrar en pantalla
    y dice si los datos se modificaron y si hay copia de respaldo (RN-59)."""


# Qué hay que ejecutar para pasar de una versión a la siguiente.
# ALTER TABLE ADD COLUMN agrega columnas sin tocar los datos que ya existen:
# los gastos viejos quedan con moneda 'ARS' (el valor por defecto) y sin dólares.
_ACTUALIZACIONES = {
    1: [
        (
            "ALTER TABLE gastos ADD COLUMN moneda TEXT NOT NULL DEFAULT 'ARS' "
            "CHECK (moneda IN ('ARS', 'USD'))"
        ),
        "ALTER TABLE gastos ADD COLUMN monto_usd_cent INTEGER CHECK (monto_usd_cent > 0)",
        "ALTER TABLE gastos ADD COLUMN cotizacion_cent INTEGER CHECK (cotizacion_cent > 0)",
    ],
}

# Se crean las 12 tablas desde el principio, aunque el paso 1 use pocas: así no hace
# falta modificar la estructura de una base que ya tiene datos reales.
# "IF NOT EXISTS" permite ejecutar esto cada vez que se abre la app sin romper nada.
_ESQUEMA = """
CREATE TABLE IF NOT EXISTS meses (
    id INTEGER PRIMARY KEY,
    anio INTEGER NOT NULL CHECK (anio BETWEEN 1000 AND 9999),
    mes INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    sueldo_usd_cent INTEGER NOT NULL CHECK (sueldo_usd_cent >= 0),
    cotizacion_cent INTEGER CHECK (cotizacion_cent > 0),
    UNIQUE (anio, mes)
);

CREATE TABLE IF NOT EXISTS categorias (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
    archivado INTEGER NOT NULL DEFAULT 0 CHECK (archivado IN (0, 1))
);

CREATE TABLE IF NOT EXISTS medios_pago (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
    archivado INTEGER NOT NULL DEFAULT 0 CHECK (archivado IN (0, 1))
);

CREATE TABLE IF NOT EXISTS personas (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL UNIQUE COLLATE NOCASE,
    archivado INTEGER NOT NULL DEFAULT 0 CHECK (archivado IN (0, 1))
);

CREATE TABLE IF NOT EXISTS planes_cuotas (
    id INTEGER PRIMARY KEY,
    nombre TEXT NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES categorias (id),
    medio_pago_id INTEGER REFERENCES medios_pago (id),
    monto_cuota_cent INTEGER NOT NULL CHECK (monto_cuota_cent > 0),
    cantidad_cuotas INTEGER NOT NULL CHECK (cantidad_cuotas >= 1),
    primer_anio INTEGER NOT NULL,
    primer_mes INTEGER NOT NULL CHECK (primer_mes BETWEEN 1 AND 12),
    cancelado_anio INTEGER,
    cancelado_mes INTEGER CHECK (cancelado_mes BETWEEN 1 AND 12)
);

CREATE TABLE IF NOT EXISTS cuotas_omitidas (
    plan_cuotas_id INTEGER NOT NULL REFERENCES planes_cuotas (id) ON DELETE CASCADE,
    anio INTEGER NOT NULL,
    mes INTEGER NOT NULL CHECK (mes BETWEEN 1 AND 12),
    PRIMARY KEY (plan_cuotas_id, anio, mes)
);

CREATE TABLE IF NOT EXISTS gastos (
    id INTEGER PRIMARY KEY,
    mes_id INTEGER NOT NULL REFERENCES meses (id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    categoria_id INTEGER NOT NULL REFERENCES categorias (id),
    monto_cent INTEGER NOT NULL CHECK (monto_cent > 0),
    tipo TEXT NOT NULL CHECK (tipo IN ('fijo', 'cuota', 'unico')),
    medio_pago_id INTEGER REFERENCES medios_pago (id),
    plan_cuotas_id INTEGER REFERENCES planes_cuotas (id),
    moneda TEXT NOT NULL DEFAULT 'ARS' CHECK (moneda IN ('ARS', 'USD')),
    monto_usd_cent INTEGER CHECK (monto_usd_cent > 0),
    cotizacion_cent INTEGER CHECK (cotizacion_cent > 0),
    -- Un gasto es cuota si y solo si tiene plan.
    CHECK ((tipo = 'cuota') = (plan_cuotas_id IS NOT NULL)),
    -- En USD tiene dólares y cotización; en ARS, ninguno de los dos. Las cuotas, solo ARS.
    -- (Las bases actualizadas con ALTER TABLE no tienen este control: SQLite no
    -- permite agregarlo después. Ahí lo garantiza la lógica de gastos.py.)
    CHECK (
        (moneda = 'ARS' AND monto_usd_cent IS NULL AND cotizacion_cent IS NULL)
        OR (moneda = 'USD' AND monto_usd_cent IS NOT NULL
            AND cotizacion_cent IS NOT NULL AND tipo <> 'cuota')
    ),
    UNIQUE (mes_id, plan_cuotas_id)
);

CREATE TABLE IF NOT EXISTS pagos (
    id INTEGER PRIMARY KEY,
    gasto_id INTEGER NOT NULL REFERENCES gastos (id) ON DELETE CASCADE,
    monto_cent INTEGER NOT NULL CHECK (monto_cent > 0),
    fecha TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingresos_extra (
    id INTEGER PRIMARY KEY,
    mes_id INTEGER NOT NULL REFERENCES meses (id) ON DELETE CASCADE,
    descripcion TEXT NOT NULL,
    moneda TEXT NOT NULL CHECK (moneda IN ('ARS', 'USD')),
    monto_cent INTEGER NOT NULL CHECK (monto_cent > 0)
);

CREATE TABLE IF NOT EXISTS cambios (
    id INTEGER PRIMARY KEY,
    mes_id INTEGER NOT NULL REFERENCES meses (id) ON DELETE CASCADE,
    fecha TEXT NOT NULL,
    usd_cent INTEGER NOT NULL CHECK (usd_cent > 0),
    cotizacion_cent INTEGER NOT NULL CHECK (cotizacion_cent > 0),
    ars_cent INTEGER NOT NULL CHECK (ars_cent > 0)
);

CREATE TABLE IF NOT EXISTS partes_gasto (
    id INTEGER PRIMARY KEY,
    gasto_id INTEGER NOT NULL REFERENCES gastos (id) ON DELETE CASCADE,
    persona_id INTEGER NOT NULL REFERENCES personas (id),
    monto_cent INTEGER NOT NULL CHECK (monto_cent >= 0),
    editada_a_mano INTEGER NOT NULL DEFAULT 0 CHECK (editada_a_mano IN (0, 1)),
    cobrado INTEGER NOT NULL DEFAULT 0 CHECK (cobrado IN (0, 1)),
    cobrado_cent INTEGER NOT NULL DEFAULT 0 CHECK (cobrado_cent >= 0),
    UNIQUE (gasto_id, persona_id)
);

CREATE TABLE IF NOT EXISTS items_me_deben (
    id INTEGER PRIMARY KEY,
    persona_id INTEGER NOT NULL REFERENCES personas (id),
    descripcion TEXT NOT NULL,
    monto_cent INTEGER NOT NULL CHECK (monto_cent > 0),
    fecha TEXT NOT NULL,
    cobrado INTEGER NOT NULL DEFAULT 0 CHECK (cobrado IN (0, 1))
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def conectar(ruta: Path | str = RUTA_POR_DEFECTO) -> sqlite3.Connection:
    """Abre la base (la crea si no existe) y deja las tablas listas.

    Las pruebas pasan ruta=":memory:" para usar una base temporal en memoria.
    """
    en_memoria = str(ruta) == ":memory:"
    if not en_memoria:
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: Flet ejecuta los clics en hilos distintos al que
    # abrió la conexión. Con un solo usuario no hay escrituras simultáneas.
    con = sqlite3.connect(ruta, check_same_thread=False)
    # Row permite leer las columnas por nombre: fila["nombre"] en vez de fila[1].
    con.row_factory = sqlite3.Row
    # SQLite no controla las claves foráneas salvo que se lo pida en cada conexión.
    con.execute("PRAGMA foreign_keys = ON")
    # Los respaldos se guardan junto a la base: datos-privados/respaldos/.
    carpeta_respaldos = None if en_memoria else Path(ruta).parent / "respaldos"
    try:
        crear_tablas(con, carpeta_respaldos)
    except BaseException:
        # Si no se pudo dejar lista, se cierra antes de avisar el error: así el
        # archivo no queda abierto.
        con.close()
        raise
    return con


def crear_tablas(
    con: sqlite3.Connection, carpeta_respaldos: Path | None = None
) -> None:
    """Crea las tablas que falten y actualiza la estructura si la base es vieja."""
    if version_de(con) > VERSION_ACTUAL:
        # Una base creada por una versión más nueva de la app: esta versión no
        # conoce su estructura y podría romperla.
        raise ErrorDeBase(
            "Esta base es de una versión más nueva de la app. "
            "Actualizá la app antes de abrirla. Tus datos no se modificaron."
        )
    base_nueva = not _existe_tabla(con, "gastos")
    with con:
        con.executescript(_ESQUEMA)
        _cargar_datos_iniciales(con)
    if base_nueva:
        # Una base recién creada ya tiene la estructura completa (_ESQUEMA).
        con.execute(f"PRAGMA user_version = {VERSION_ACTUAL}")
    else:
        actualizar_estructura(con, carpeta_respaldos)


def version_de(con: sqlite3.Connection) -> int:
    return con.execute("PRAGMA user_version").fetchone()[0]


def _existe_tabla(con: sqlite3.Connection, nombre: str) -> bool:
    fila = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (nombre,)
    ).fetchone()
    return fila is not None


def actualizar_estructura(
    con: sqlite3.Connection, carpeta_respaldos: Path | None = None
) -> Path | None:
    """Lleva una base vieja a VERSION_ACTUAL (RN-59). Devuelve la ruta del respaldo.

    Antes de cambiar nada hace una copia de respaldo (si se indica la carpeta).
    Cada versión se aplica en una transacción: si algo falla, esa versión
    queda sin aplicar (la base no queda a medias) y el error sigue hacia arriba.
    """
    version = version_de(con)
    if version >= VERSION_ACTUAL:
        return None
    respaldo = None
    if carpeta_respaldos:
        try:
            respaldo = hacer_respaldo(con, carpeta_respaldos)
        except Exception as error:
            # Sin respaldo no se toca nada.
            raise ErrorDeBase(
                "No se pudo hacer la copia de respaldo, así que la base no se actualizó. "
                "Tus datos no se modificaron."
            ) from error
    for nueva_version in range(version + 1, VERSION_ACTUAL + 1):
        try:
            # BEGIN explícito: Python no abre solo una transacción para ALTER TABLE.
            con.execute("BEGIN")
            for sentencia in _ACTUALIZACIONES[nueva_version]:
                con.execute(sentencia)
            # user_version también es parte de la transacción.
            con.execute(f"PRAGMA user_version = {nueva_version}")
            con.commit()
        except Exception as error:
            con.rollback()
            mensaje = "No se pudo actualizar la base. Tus datos no se modificaron."
            if respaldo:
                mensaje += f" Hay una copia de respaldo en {respaldo}."
            # "from error" conserva el error original para el detalle técnico.
            raise ErrorDeBase(mensaje) from error
    return respaldo


def hacer_respaldo(con: sqlite3.Connection, carpeta: Path) -> Path:
    """Copia completa de la base en carpeta/gastos-AAAAMMDD-HHMMSS.db.

    Usa backup() de SQLite y no una copia del archivo, porque copia bien aunque
    la base esté abierta.
    """
    carpeta.mkdir(parents=True, exist_ok=True)
    # Hora local a propósito: el nombre lo lee el usuario.
    marca = datetime.now().strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005
    destino = carpeta / f"gastos-{marca}.db"
    copia = sqlite3.connect(destino)
    try:
        con.backup(copia)
    finally:
        copia.close()
    return destino


def _cargar_datos_iniciales(con: sqlite3.Connection) -> None:
    # Se marca en configuracion para hacerlo una sola vez: si el usuario después
    # borra todas las categorías, no tienen que volver a aparecer.
    ya_cargados = con.execute(
        "SELECT 1 FROM configuracion WHERE clave = 'datos_iniciales_cargados'"
    ).fetchone()
    if ya_cargados:
        return
    con.executemany(
        "INSERT OR IGNORE INTO categorias (nombre) VALUES (?)",
        [(nombre,) for nombre in CATEGORIAS_INICIALES],
    )
    con.executemany(
        "INSERT OR IGNORE INTO medios_pago (nombre) VALUES (?)",
        [(nombre,) for nombre in MEDIOS_PAGO_INICIALES],
    )
    con.execute(
        "INSERT INTO configuracion (clave, valor) VALUES ('datos_iniciales_cargados', '1')"
    )
