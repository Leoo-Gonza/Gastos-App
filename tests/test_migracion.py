"""Pruebas de la actualización de la base de la versión 0 a la 1 (RF-48, RN-59, CA-48.x).

Todo se hace con archivos temporales de pytest (tmp_path): una base "vieja" armada con
la estructura del paso 1 (tests/esquema_v0.py) y datos inventados. Nunca se lee ni se
escribe datos-privados/.
"""

import re
import sqlite3

import pytest

from app.logica import base_datos, catalogos, gastos
from app.logica.errores import ErrorDeValidacion
from tests.ayudantes import id_por_nombre
from tests.esquema_v0 import ESQUEMA_V0

# Tablas con datos del usuario que la actualización no puede tocar.
TABLAS = [
    "meses",
    "categorias",
    "medios_pago",
    "personas",
    "gastos",
    "pagos",
    "partes_gasto",
    "items_me_deben",
    "configuracion",
]
COLUMNAS_NUEVAS = {"moneda", "monto_usd_cent", "cotizacion_cent"}
PATRON_RESPALDO = re.compile(r"gastos-\d{8}-\d{6}\.db")


def crear_base_v0(ruta):
    """Base en versión 0 con meses, gastos, pagos, partes y "me deben" (datos inventados)."""
    con = sqlite3.connect(ruta)
    con.executescript(ESQUEMA_V0)
    con.executescript(
        """
        INSERT INTO categorias (id, nombre) VALUES (1, 'Vivienda'), (2, 'Servicios'),
            (3, 'Otros');
        INSERT INTO categorias (id, nombre, archivado) VALUES (4, 'Gym', 1);
        INSERT INTO medios_pago (id, nombre) VALUES (1, 'Efectivo'), (2, 'Visa Santander');
        INSERT INTO personas (id, nombre) VALUES (1, 'Sofía'), (2, 'Marsu');
        INSERT INTO configuracion (clave, valor) VALUES ('datos_iniciales_cargados', '1');
        INSERT INTO meses (id, anio, mes, sueldo_usd_cent, cotizacion_cent)
            VALUES (1, 2026, 9, 120000, 155000), (2, 2026, 10, 120000, NULL);
        INSERT INTO gastos (id, mes_id, nombre, categoria_id, monto_cent, tipo, medio_pago_id)
            VALUES (1, 2, 'Alquiler', 1, 26000000, 'fijo', 1),
                   (2, 2, 'Edenor', 2, 3870000, 'fijo', 2),
                   (3, 2, 'Regalo', 3, 1500012, 'unico', NULL),
                   (4, 1, 'Cuota gym', 4, 2500000, 'fijo', NULL);
        INSERT INTO pagos (gasto_id, monto_cent, fecha)
            VALUES (1, 26000000, '2026-10-01'), (2, 1000000, '2026-10-05');
        INSERT INTO partes_gasto (gasto_id, persona_id, monto_cent, editada_a_mano, cobrado)
            VALUES (2, 1, 1290000, 0, 1), (2, 2, 1290000, 1, 0);
        INSERT INTO items_me_deben (persona_id, descripcion, monto_cent, fecha)
            VALUES (1, 'Préstamo', 500000, '2026-10-02');
        """
    )
    con.commit()
    assert con.execute("PRAGMA user_version").fetchone()[0] == 0
    con.close()


def volcado(con):
    """Contenido de las tablas del usuario, con las columnas de la versión 0."""
    datos = {}
    for tabla in TABLAS:
        columnas = [
            f[1]
            for f in con.execute(f"PRAGMA table_info({tabla})").fetchall()
            if f[1] not in COLUMNAS_NUEVAS or tabla != "gastos"
        ]
        lista = ", ".join(columnas)
        datos[tabla] = [
            tuple(f) for f in con.execute(f"SELECT {lista} FROM {tabla} ORDER BY rowid")
        ]
    return datos


def volcado_de_archivo(ruta):
    con = sqlite3.connect(ruta)
    try:
        return volcado(con)
    finally:
        con.close()


def columnas_de_gastos(con):
    return {f[1] for f in con.execute("PRAGMA table_info(gastos)").fetchall()}


def version_de_archivo(ruta):
    con = sqlite3.connect(ruta)
    try:
        return con.execute("PRAGMA user_version").fetchone()[0]
    finally:
        con.close()


def respaldos(tmp_path):
    carpeta = tmp_path / "respaldos"
    return sorted(carpeta.glob("*.db")) if carpeta.exists() else []


@pytest.fixture
def base_v0(tmp_path):
    ruta = tmp_path / "gastos.db"
    crear_base_v0(ruta)
    return ruta


# ---------------------------------------------------------------------------
# CA-48.1: actualización exitosa
# ---------------------------------------------------------------------------


def test_ca_48_1_la_base_pasa_a_version_1_sin_perder_datos(base_v0):
    antes = volcado_de_archivo(base_v0)
    con = base_datos.conectar(base_v0)
    try:
        assert base_datos.version_de(con) == 1
        assert COLUMNAS_NUEVAS <= columnas_de_gastos(con)
        # Mismos datos en todas las tablas (gastos, pagos, partes, "me deben"...).
        assert volcado(con) == antes
        # Todos los gastos existentes quedan en pesos, sin dólares ni cotización.
        filas = con.execute(
            "SELECT moneda, monto_usd_cent, cotizacion_cent FROM gastos"
        )
        assert {tuple(f) for f in filas} == {("ARS", None, None)}
    finally:
        con.close()


def test_ca_48_1_totales_y_pagos_identicos(base_v0):
    con = base_datos.conectar(base_v0)
    try:
        assert gastos.total_gastos(con, 2) == 26000000 + 3870000 + 1500012
        assert gastos.total_pagado(con, 1) == 26000000
        assert gastos.total_pagado(con, 2) == 1000000
        lista = gastos.listar_gastos(con, 2)
        assert [(f["nombre"], f["moneda"], f["monto_usd_cent"]) for f in lista] == [
            ("Alquiler", "ARS", None),
            ("Edenor", "ARS", None),
            ("Regalo", "ARS", None),
        ]
        # Categorías archivadas y datos iniciales no cambian.
        assert len(catalogos.listar(con, catalogos.CATEGORIAS)) == 3
        assert catalogos.obtener(con, catalogos.CATEGORIAS, 4)["archivado"] == 1
    finally:
        con.close()


def test_ca_48_1_se_crea_un_respaldo_con_los_datos_originales(base_v0, tmp_path):
    antes = volcado_de_archivo(base_v0)
    con = base_datos.conectar(base_v0)
    con.close()
    [respaldo] = respaldos(tmp_path)
    assert PATRON_RESPALDO.fullmatch(respaldo.name)
    # El respaldo se puede abrir, está en versión 0 (hecho antes del cambio)...
    assert version_de_archivo(respaldo) == 0
    copia = sqlite3.connect(respaldo)
    try:
        assert "moneda" not in columnas_de_gastos(copia)
        # ...y tiene exactamente los mismos datos que la base original.
        assert volcado(copia) == antes
    finally:
        copia.close()


def test_los_gastos_viejos_se_pueden_editar_y_pasar_a_dolares(base_v0):
    con = base_datos.conectar(base_v0)
    try:
        gastos.editar_gasto(
            con, 3, "Regalo", 3, None, "unico", None, "USD", 2000, 160000
        )
        fila = gastos.obtener_gasto(con, 3)
        assert (fila["moneda"], fila["monto_cent"]) == ("USD", 3200000)
    finally:
        con.close()


def test_la_base_actualizada_conserva_los_check_de_las_columnas_nuevas(base_v0):
    # Los ALTER TABLE agregan CHECK de cada columna (moneda válida, valores > 0).
    con = base_datos.conectar(base_v0)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE gastos SET moneda = 'EUR' WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE gastos SET monto_usd_cent = 0 WHERE id = 1")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute("UPDATE gastos SET cotizacion_cent = -1 WHERE id = 1")
    finally:
        con.close()


def test_en_la_base_actualizada_la_logica_rechaza_usd_incompleto(base_v0):
    # La base actualizada no tiene el CHECK de consistencia (SQLite no permite
    # agregarlo con ALTER TABLE): lo garantiza la lógica.
    con = base_datos.conectar(base_v0)
    try:
        with pytest.raises(ErrorDeValidacion):
            gastos.agregar_gasto(
                con, 2, "Claude", 3, None, "unico", None, "USD", 2000, None
            )
        with pytest.raises(ErrorDeValidacion):
            gastos.agregar_gasto(
                con, 2, "Claude", 3, None, "cuota", None, "USD", 2000, 160000
            )
    finally:
        con.close()


# ---------------------------------------------------------------------------
# CA-48.2: abrir otra vez no repite la actualización
# ---------------------------------------------------------------------------


def test_ca_48_2_reabrir_no_repite_ni_pierde_gastos_en_usd(base_v0, tmp_path):
    con = base_datos.conectar(base_v0)
    gid = gastos.agregar_gasto(
        con, 2, "Claude", 3, None, "unico", None, "USD", 2000, 160000
    )
    con.close()

    con = base_datos.conectar(base_v0)  # segunda apertura
    try:
        assert base_datos.version_de(con) == 1
        assert len(respaldos(tmp_path)) == 1  # no se hizo otro respaldo
        fila = gastos.obtener_gasto(con, gid)
        assert (fila["moneda"], fila["monto_usd_cent"], fila["monto_cent"]) == (
            "USD",
            2000,
            3200000,
        )
        # Llamar a actualizar_estructura con la base al día no hace nada.
        assert base_datos.actualizar_estructura(con, tmp_path / "respaldos") is None
        assert len(respaldos(tmp_path)) == 1
    finally:
        con.close()


def test_base_nueva_queda_en_version_1_sin_respaldo(tmp_path):
    ruta = tmp_path / "nueva.db"
    con = base_datos.conectar(ruta)
    try:
        assert base_datos.version_de(con) == 1
        assert COLUMNAS_NUEVAS <= columnas_de_gastos(con)
    finally:
        con.close()
    assert respaldos(tmp_path) == []
    con = base_datos.conectar(ruta)  # reabrir una base nueva tampoco respalda
    con.close()
    assert respaldos(tmp_path) == []


def test_base_en_memoria_queda_en_version_1(con):
    assert base_datos.version_de(con) == base_datos.VERSION_ACTUAL == 1


def test_base_nueva_tiene_el_check_de_consistencia(con, mes_id):
    # Base nueva: el CHECK rechaza un USD sin cotización, ARS con dólares y USD en cuota.
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    casos = [
        ("USD", 2000, None, "unico", None),
        ("USD", None, 160000, "unico", None),
        ("ARS", 2000, None, "unico", None),
        ("ARS", None, 160000, "fijo", None),
    ]
    for moneda, usd, cot, tipo, plan in casos:
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, "
                "plan_cuotas_id, moneda, monto_usd_cent, cotizacion_cent) "
                "VALUES (?, 'X', ?, 100, ?, ?, ?, ?, ?)",
                (mes_id, otros, tipo, plan, moneda, usd, cot),
            )
    con.execute(
        "INSERT INTO planes_cuotas (id, nombre, categoria_id, monto_cuota_cent, "
        "cantidad_cuotas, primer_anio, primer_mes) VALUES (1, 'Heladera', ?, 100, 3, 2026, 8)",
        (otros,),
    )
    with pytest.raises(sqlite3.IntegrityError):
        con.execute(
            "INSERT INTO gastos (mes_id, nombre, categoria_id, monto_cent, tipo, "
            "plan_cuotas_id, moneda, monto_usd_cent, cotizacion_cent) "
            "VALUES (?, 'X', ?, 100, 'cuota', 1, 'USD', 2000, 160000)",
            (mes_id, otros),
        )


# ---------------------------------------------------------------------------
# CA-48.3: falla a mitad de camino (O18: ErrorDeBase con mensaje para mostrar)
# ---------------------------------------------------------------------------

INVALIDA = "ALTER TABLE tabla_que_no_existe ADD COLUMN x INTEGER"


def _con_sentencia_invalida(monkeypatch, posicion="al_final"):
    originales = list(base_datos._ACTUALIZACIONES[1])
    if posicion == "al_final":
        sentencias = originales + [INVALIDA]
    else:
        sentencias = originales[:1] + [INVALIDA] + originales[1:]
    monkeypatch.setattr(base_datos, "_ACTUALIZACIONES", {1: sentencias})


def _sigue_igual(ruta, antes):
    """La base sigue en versión 0, sin columnas nuevas y con los mismos datos."""
    assert version_de_archivo(ruta) == 0
    crudo = sqlite3.connect(ruta)
    try:
        assert not (COLUMNAS_NUEVAS & columnas_de_gastos(crudo))
        assert volcado(crudo) == antes
    finally:
        crudo.close()


@pytest.mark.parametrize("posicion", ["al_final", "en_el_medio"])
def test_ca_48_3_si_falla_la_base_queda_en_version_0(
    base_v0, tmp_path, monkeypatch, posicion
):
    antes = volcado_de_archivo(base_v0)
    _con_sentencia_invalida(monkeypatch, posicion)

    with pytest.raises(base_datos.ErrorDeBase) as error:
        base_datos.conectar(base_v0)

    # O18: el mensaje dice que no se modificó nada y dónde está el respaldo.
    [respaldo] = respaldos(tmp_path)
    assert str(error.value) == (
        "No se pudo actualizar la base. Tus datos no se modificaron. "
        f"Hay una copia de respaldo en {respaldo}."
    )
    # El error original de SQLite queda guardado para el detalle técnico.
    assert isinstance(error.value.__cause__, sqlite3.OperationalError)
    assert "tabla_que_no_existe" in str(error.value.__cause__)
    _sigue_igual(base_v0, antes)


def test_ca_48_3_sin_carpeta_de_respaldos_no_menciona_respaldo(base_v0, monkeypatch):
    # O18: si no se hizo respaldo (sin carpeta), el mensaje no lo promete.
    antes = volcado_de_archivo(base_v0)
    _con_sentencia_invalida(monkeypatch)
    crudo = sqlite3.connect(base_v0)
    try:
        with pytest.raises(base_datos.ErrorDeBase) as error:
            base_datos.actualizar_estructura(crudo, None)
        assert base_datos.version_de(crudo) == 0
    finally:
        crudo.close()
    assert (
        str(error.value)
        == "No se pudo actualizar la base. Tus datos no se modificaron."
    )
    assert isinstance(error.value.__cause__, sqlite3.OperationalError)
    _sigue_igual(base_v0, antes)


def test_ca_48_3_despues_de_una_falla_se_puede_actualizar_bien(base_v0, monkeypatch):
    # Si la próxima vez la actualización funciona, se aplica completa.
    _con_sentencia_invalida(monkeypatch)
    with pytest.raises(base_datos.ErrorDeBase):
        base_datos.conectar(base_v0)
    monkeypatch.undo()
    con = base_datos.conectar(base_v0)
    try:
        assert base_datos.version_de(con) == 1
        assert COLUMNAS_NUEVAS <= columnas_de_gastos(con)
    finally:
        con.close()


# ---------------------------------------------------------------------------
# CA-48.4: no se puede crear el respaldo (O18)
# ---------------------------------------------------------------------------

MENSAJE_SIN_RESPALDO = (
    "No se pudo hacer la copia de respaldo, así que la base no se actualizó. "
    "Tus datos no se modificaron."
)


def test_ca_48_4_sin_respaldo_la_base_no_se_modifica(base_v0, tmp_path):
    # Se impide crear la carpeta de respaldos: en su lugar hay un archivo con ese nombre.
    (tmp_path / "respaldos").write_text("no soy una carpeta")
    antes = volcado_de_archivo(base_v0)
    with pytest.raises(base_datos.ErrorDeBase) as error:
        base_datos.conectar(base_v0)
    assert str(error.value) == MENSAJE_SIN_RESPALDO
    assert isinstance(error.value.__cause__, OSError)
    _sigue_igual(base_v0, antes)


def test_ca_48_4_falla_simulada_del_respaldo(base_v0, monkeypatch):
    def falla(con, carpeta):
        raise OSError("disco lleno (simulado)")

    antes = volcado_de_archivo(base_v0)
    monkeypatch.setattr(base_datos, "hacer_respaldo", falla)
    with pytest.raises(base_datos.ErrorDeBase) as error:
        base_datos.conectar(base_v0)
    assert str(error.value) == MENSAJE_SIN_RESPALDO
    assert str(error.value.__cause__) == "disco lleno (simulado)"
    _sigue_igual(base_v0, antes)


# ---------------------------------------------------------------------------
# O19: si falla, conectar() cierra la conexión
# ---------------------------------------------------------------------------


def _se_puede_borrar_y_renombrar(ruta):
    """En Windows un archivo abierto no se puede renombrar ni borrar: si funciona,
    la conexión se cerró."""
    nueva = ruta.with_name("renombrada.db")
    ruta.rename(nueva)
    nueva.unlink()
    assert not nueva.exists()


def test_o19_falla_de_actualizacion_cierra_la_conexion(base_v0, monkeypatch):
    _con_sentencia_invalida(monkeypatch)
    with pytest.raises(base_datos.ErrorDeBase):
        base_datos.conectar(base_v0)
    _se_puede_borrar_y_renombrar(base_v0)


def test_o19_falla_de_respaldo_cierra_la_conexion(base_v0, tmp_path):
    (tmp_path / "respaldos").write_text("no soy una carpeta")
    with pytest.raises(base_datos.ErrorDeBase):
        base_datos.conectar(base_v0)
    _se_puede_borrar_y_renombrar(base_v0)


def test_o19_base_mas_nueva_cierra_la_conexion(base_v0):
    _poner_version(base_v0, 2)
    with pytest.raises(base_datos.ErrorDeBase):
        base_datos.conectar(base_v0)
    _se_puede_borrar_y_renombrar(base_v0)


def test_o19_si_no_falla_la_conexion_queda_abierta_y_usable(base_v0):
    con = base_datos.conectar(base_v0)
    try:
        assert con.execute("SELECT COUNT(*) FROM gastos").fetchone()[0] == 4
    finally:
        con.close()


# ---------------------------------------------------------------------------
# O21: base de una versión más nueva de la app
# ---------------------------------------------------------------------------


def _poner_version(ruta, version):
    crudo = sqlite3.connect(ruta)
    try:
        crudo.execute(f"PRAGMA user_version = {version}")
        crudo.commit()
    finally:
        crudo.close()


@pytest.mark.parametrize("version", [2, 99])
def test_o21_base_mas_nueva_no_se_toca(base_v0, tmp_path, version):
    _poner_version(base_v0, version)
    antes = volcado_de_archivo(base_v0)
    with pytest.raises(base_datos.ErrorDeBase) as error:
        base_datos.conectar(base_v0)
    assert str(error.value) == (
        "Esta base es de una versión más nueva de la app. "
        "Actualizá la app antes de abrirla. Tus datos no se modificaron."
    )
    assert version_de_archivo(base_v0) == version
    assert volcado_de_archivo(base_v0) == antes
    crudo = sqlite3.connect(base_v0)
    try:
        assert not (COLUMNAS_NUEVAS & columnas_de_gastos(crudo))  # no se agregó nada
    finally:
        crudo.close()
    assert respaldos(tmp_path) == []


def test_o21_base_en_la_version_actual_abre_normal(base_v0):
    con = base_datos.conectar(base_v0)
    con.close()
    con = base_datos.conectar(base_v0)  # ya en versión 1 = VERSION_ACTUAL
    try:
        assert base_datos.version_de(con) == base_datos.VERSION_ACTUAL
    finally:
        con.close()


def test_error_de_base_es_una_excepcion_con_mensaje():
    assert issubclass(base_datos.ErrorDeBase, Exception)
    assert str(base_datos.ErrorDeBase("Texto para mostrar")) == "Texto para mostrar"


# ---------------------------------------------------------------------------
# Funciones públicas sueltas
# ---------------------------------------------------------------------------


def test_hacer_respaldo_crea_copia_completa(tmp_path, con, mes_id):
    ruta = base_datos.hacer_respaldo(con, tmp_path / "carpeta" / "nueva")
    assert ruta.parent == tmp_path / "carpeta" / "nueva"
    assert PATRON_RESPALDO.fullmatch(ruta.name)
    copia = sqlite3.connect(ruta)
    try:
        assert copia.execute("SELECT anio, mes FROM meses").fetchall() == [(2026, 10)]
    finally:
        copia.close()


def test_version_de_una_base_vieja_es_0(base_v0):
    crudo = sqlite3.connect(base_v0)
    try:
        assert base_datos.version_de(crudo) == 0
    finally:
        crudo.close()


def test_actualizar_estructura_sin_carpeta_no_respalda(base_v0, tmp_path):
    crudo = sqlite3.connect(base_v0)
    try:
        assert base_datos.actualizar_estructura(crudo, None) is None
        assert base_datos.version_de(crudo) == 1
    finally:
        crudo.close()
    assert respaldos(tmp_path) == []


def test_actualizar_estructura_devuelve_la_ruta_del_respaldo(base_v0, tmp_path):
    crudo = sqlite3.connect(base_v0)
    try:
        ruta = base_datos.actualizar_estructura(crudo, tmp_path / "respaldos")
    finally:
        crudo.close()
    assert ruta == respaldos(tmp_path)[0]
