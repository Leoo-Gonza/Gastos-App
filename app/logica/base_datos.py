"""Conexión a SQLite y creación de las tablas (modelo de docs/requisitos.md §5)."""

import sqlite3
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
    -- Un gasto es cuota si y solo si tiene plan.
    CHECK ((tipo = 'cuota') = (plan_cuotas_id IS NOT NULL)),
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
    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)

    # check_same_thread=False: Flet ejecuta los clics en hilos distintos al que
    # abrió la conexión. Con un solo usuario no hay escrituras simultáneas.
    con = sqlite3.connect(ruta, check_same_thread=False)
    # Row permite leer las columnas por nombre: fila["nombre"] en vez de fila[1].
    con.row_factory = sqlite3.Row
    # SQLite no controla las claves foráneas salvo que se lo pida en cada conexión.
    con.execute("PRAGMA foreign_keys = ON")
    crear_tablas(con)
    return con


def crear_tablas(con: sqlite3.Connection) -> None:
    with con:
        con.executescript(_ESQUEMA)
        _cargar_datos_iniciales(con)


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
