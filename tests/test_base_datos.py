"""Pruebas de app/logica/base_datos.py: creación de tablas, datos iniciales y
restricciones del modelo (docs/requisitos.md §5)."""

import sqlite3

import pytest

from app.logica import base_datos, catalogos
from tests.ayudantes import cantidad_filas, insertar_mes

TABLAS_ESPERADAS = {
    "meses",
    "categorias",
    "medios_pago",
    "personas",
    "planes_cuotas",
    "cuotas_omitidas",
    "gastos",
    "pagos",
    "ingresos_extra",
    "cambios",
    "partes_gasto",
    "items_me_deben",
    "configuracion",
}


def _nombres(con, tabla):
    return sorted(
        f["nombre"] for f in catalogos.listar(con, tabla, incluir_archivados=True)
    )


def test_conectar_crea_todas_las_tablas_del_modelo(con):
    # §5: las tablas del modelo existen desde el principio.
    filas = con.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).fetchall()
    assert TABLAS_ESPERADAS <= {f["name"] for f in filas}


def test_claves_foraneas_activadas(con):
    # §5: PRAGMA foreign_keys = ON (necesario para ON DELETE CASCADE de RN-51).
    assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_categorias_iniciales(con):
    # Decisión aprobada: la app arranca con estas 7 categorías, sin archivar.
    assert _nombres(con, catalogos.CATEGORIAS) == sorted(
        ["Vivienda", "Servicios", "Transporte", "Mercado", "Salud", "Deudas", "Otros"]
    )
    assert all(not f["archivado"] for f in catalogos.listar(con, catalogos.CATEGORIAS))


def test_medios_de_pago_iniciales(con):
    # RF-11: valores iniciales Tarjeta de crédito, Efectivo, Transferencia.
    assert _nombres(con, catalogos.MEDIOS_PAGO) == sorted(
        ["Tarjeta de crédito", "Efectivo", "Transferencia"]
    )


def test_personas_empieza_vacia(con):
    # No hay personas iniciales.
    assert cantidad_filas(con, "personas") == 0


def test_crear_tablas_dos_veces_no_falla_ni_duplica(con):
    # Ejecutar crear_tablas otra vez (como al reabrir la app) no da error ni duplica datos.
    base_datos.crear_tablas(con)
    base_datos.crear_tablas(con)
    assert cantidad_filas(con, "categorias") == 7
    assert cantidad_filas(con, "medios_pago") == 3


def test_crear_tablas_no_borra_datos_existentes(con, mes_id):
    # Volver a crear las tablas no pierde un mes ya cargado.
    base_datos.crear_tablas(con)
    assert cantidad_filas(con, "meses") == 1


def test_categorias_borradas_no_vuelven_al_llamar_crear_tablas(con):
    # Los datos iniciales se cargan una sola vez: si se borran todos, no reaparecen.
    for tabla in (catalogos.CATEGORIAS, catalogos.MEDIOS_PAGO):
        for fila in catalogos.listar(con, tabla):
            assert catalogos.eliminar(con, tabla, fila["id"]) == "borrado"
    base_datos.crear_tablas(con)
    assert cantidad_filas(con, "categorias") == 0
    assert cantidad_filas(con, "medios_pago") == 0


def test_categorias_borradas_no_vuelven_al_reabrir_un_archivo(tmp_path):
    # Igual que la anterior, pero cerrando y reabriendo un archivo temporal (no la base real).
    ruta = tmp_path / "prueba.db"
    con = base_datos.conectar(ruta)
    for fila in catalogos.listar(con, catalogos.CATEGORIAS):
        catalogos.eliminar(con, catalogos.CATEGORIAS, fila["id"])
    con.close()

    con = base_datos.conectar(ruta)
    try:
        assert cantidad_filas(con, "categorias") == 0
        assert cantidad_filas(con, "medios_pago") == 3  # los medios no se tocaron
    finally:
        con.close()


def test_conectar_crea_la_carpeta_si_no_existe(tmp_path):
    # La app crea la carpeta de la base si todavía no existe (primer uso).
    ruta = tmp_path / "carpeta" / "nueva" / "prueba.db"
    con = base_datos.conectar(ruta)
    con.close()
    assert ruta.exists()


def test_filas_se_leen_por_nombre_de_columna(con):
    # row_factory = Row: se puede leer fila["nombre"].
    fila = con.execute("SELECT nombre FROM categorias LIMIT 1").fetchone()
    assert isinstance(fila["nombre"], str)


# --- Restricciones del modelo (red de seguridad por debajo de la lógica) ---


def test_no_puede_haber_dos_meses_iguales(con, mes_id):
    # RN-07 / §5.1: UNIQUE(anio, mes).
    with pytest.raises(sqlite3.IntegrityError):
        insertar_mes(con, 2026, 10)


@pytest.mark.parametrize(("anio", "mes"), [(26, 10), (2026, 0), (2026, 13)])
def test_la_base_rechaza_meses_invalidos(con, anio, mes):
    # RN-07 / §5.1: CHECK de año de 4 dígitos y mes 1..12 en la propia base.
    with pytest.raises(sqlite3.IntegrityError):
        insertar_mes(con, anio, mes)


@pytest.mark.parametrize("monto", [0, -100])
def test_la_base_rechaza_gastos_con_monto_no_positivo(con, mes_id, monto):
    # RN-05 / §5.5: CHECK monto_cent > 0, aunque alguien saltee la validación de la lógica.
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo) "
            "VALUES (?, 'X', 1, ?, 'unico')",
            (mes_id, monto),
        )


def test_la_base_rechaza_cotizacion_cero(con):
    # RN-06 / §5.1: CHECK cotizacion_cent > 0.
    with pytest.raises(sqlite3.IntegrityError):
        insertar_mes(con, 2026, 11, cotizacion=0)


def test_la_base_rechaza_nombres_de_categoria_repetidos(con):
    # RN-50 / §5.2: UNIQUE COLLATE NOCASE como respaldo.
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO categorias (nombre) VALUES ('VIVIENDA')")
