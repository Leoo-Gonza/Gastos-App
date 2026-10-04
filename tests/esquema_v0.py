"""Estructura de la base en la versión 0 (paso 1, antes de los gastos en dólares).

Copiada tal cual de app/logica/base_datos.py del commit 3845e81 ("Paso 1b"). Sirve
para armar, en archivos temporales, una base "vieja" como la que tiene el usuario y
probar la actualización a la versión 1 (RN-59, CA-48.x). No contiene datos reales.
"""

ESQUEMA_V0 = """
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
