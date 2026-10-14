"""Paso 8a-1: bloques "with con:" anidados (Conexion, RN-76: todo o nada).

Verifica que solo el bloque más externo guarde o deshaga, que los internos usen
SAVEPOINT, que el contador de nivel vuelva a 0 y que nada deshecho quede en el
archivo. Datos inventados.
"""

import sqlite3
from datetime import date

import pytest

from app.logica import (
    base_datos,
    catalogos,
    compartidos,
    cuotas,
    gastos,
    me_deben,
    meses,
    pagos,
)
from app.logica.errores import ErrorDeValidacion
from tests.ayudantes import cantidad_filas, id_por_nombre

HOY = date(2026, 10, 4)
TABLAS = [
    "meses",
    "gastos",
    "pagos",
    "planes_cuotas",
    "partes_gasto",
    "items_me_deben",
    "categorias",
    "medios_pago",
    "personas",
]


class Falla(Exception):
    """Error propio para provocar fallas sin confundirlo con los de la app."""


def foto(con):
    """Cantidad de filas de cada tabla, para comparar antes y después."""
    return {t: cantidad_filas(con, t) for t in TABLAS}


def nombres_personas(con):
    return {f["nombre"] for f in catalogos.listar(con, catalogos.PERSONAS, True)}


def operaciones_reales(con, mes_id):
    """Usa varias funciones reales de la lógica, cada una con su propio with."""
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    medio = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Inventada")
    persona = catalogos.crear(con, catalogos.PERSONAS, "Sofía Inventada")
    gid = gastos.agregar_gasto(
        con, mes_id, "Alquiler", otros, 5000000, "unico", medio,
        partes=[(persona, None)],
    )
    pagos.registrar_pago(con, gid, 100000, HOY)
    cuotas.crear_plan(con, "Heladera", otros, medio, 1000000, 6, 2026, 8, hoy=HOY)
    me_deben.agregar_item(con, persona, "Préstamo inventado", 2000000)
    meses.crear_mes(con, 2026, 11, 120000, 160000)
    return gid


# ---------------------------------------------------------------------------
# Todo o nada con funciones reales
# ---------------------------------------------------------------------------


def test_bloque_externo_que_falla_no_deja_nada(con, mes_id):
    # Verifica: si el bloque externo falla después de usar funciones reales, se deshace todo.
    antes = foto(con)
    with pytest.raises(Falla):
        with con:
            operaciones_reales(con, mes_id)
            assert foto(con) != antes  # Adentro sí se ve lo cargado.
            raise Falla
    assert foto(con) == antes
    assert not con.in_transaction and con._nivel == 0


def test_bloque_externo_exitoso_deja_todo(con, mes_id):
    # Verifica: si el bloque externo termina bien, queda todo guardado.
    antes = foto(con)
    with con:
        operaciones_reales(con, mes_id)
    despues = foto(con)
    assert despues["gastos"] > antes["gastos"]
    assert despues["pagos"] == 1
    assert despues["planes_cuotas"] == 1
    assert despues["partes_gasto"] == 1
    assert despues["items_me_deben"] == 1
    assert despues["meses"] == 2
    assert despues["medios_pago"] == antes["medios_pago"] + 1
    assert despues["personas"] == antes["personas"] + 1
    # Las cuotas generadas del plan también quedaron.
    cuotas_gen = con.execute(
        "SELECT COUNT(*) FROM gastos WHERE tipo = 'cuota'"
    ).fetchone()[0]
    assert cuotas_gen >= 1
    assert not con.in_transaction and con._nivel == 0


def test_cuotas_generadas_se_deshacen_con_el_bloque_externo(con, mes_id):
    # Verifica: las cuotas generadas por crear_plan no sobreviven al rollback externo.
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    with pytest.raises(Falla):
        with con:
            cuotas.crear_plan(con, "Plan", otros, None, 1000, 3, 2026, 10, hoy=HOY)
            assert cantidad_filas(con, "gastos") == 1
            raise Falla
    assert cantidad_filas(con, "gastos") == 0
    assert cantidad_filas(con, "planes_cuotas") == 0


def test_error_de_validacion_en_funcion_real_dentro_de_bloque_externo(con, mes_id):
    # Verifica: un ErrorDeValidacion de una función real deshace lo anterior del externo.
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    antes = foto(con)
    with pytest.raises(ErrorDeValidacion):
        with con:
            gastos.agregar_gasto(con, mes_id, "Uno", otros, 1000, "unico")
            gastos.agregar_gasto(con, mes_id, "Dos", otros, -5, "unico")
    assert foto(con) == antes


# ---------------------------------------------------------------------------
# Error en bloque interno, atrapado afuera
# ---------------------------------------------------------------------------


def test_error_en_interno_despues_de_insert_deshace_solo_lo_interno(
    con, mes_id, monkeypatch
):
    # Verifica: agregar_gasto falla DESPUÉS de su INSERT (en guardar_partes); se deshace
    # solo ese gasto y lo demás del bloque externo se guarda.
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    persona = catalogos.crear(con, catalogos.PERSONAS, "Ana Inventada")

    def rota(*args, **kwargs):
        # Comprueba que el INSERT del gasto ya ocurrió cuando se llega acá.
        cuantos = con.execute(
            "SELECT COUNT(*) FROM gastos WHERE nombre = 'Roto'"
        ).fetchone()[0]
        assert cuantos == 1
        raise Falla

    with con:
        gastos.agregar_gasto(con, mes_id, "Bueno 1", otros, 1000, "unico")
        with monkeypatch.context() as m:
            m.setattr(compartidos, "guardar_partes", rota)
            try:
                gastos.agregar_gasto(
                    con, mes_id, "Roto", otros, 3000, "unico", partes=[(persona, None)]
                )
            except Falla:
                pass
        gastos.agregar_gasto(con, mes_id, "Bueno 2", otros, 2000, "unico")
    nombres = sorted(f["nombre"] for f in gastos.listar_gastos(con, mes_id))
    assert nombres == ["Bueno 1", "Bueno 2"]
    assert not con.in_transaction and con._nivel == 0


def test_error_en_interno_con_restriccion_de_la_base(con, mes_id):
    # Verifica: una violación de restricción (FK) dentro de un interno, tras un INSERT
    # válido, deshace el interno y deja seguir al externo.
    with con:
        con.execute("INSERT INTO personas (nombre) VALUES ('Externa')")
        try:
            with con:
                con.execute("INSERT INTO personas (nombre) VALUES ('Interna')")
                con.execute(
                    "INSERT INTO pagos (gasto_id, monto_cent, fecha) "
                    "VALUES (99999, 1, '2026-10-05')"
                )
        except sqlite3.IntegrityError:
            pass
        con.execute("INSERT INTO personas (nombre) VALUES ('Externa 2')")
    nombres = nombres_personas(con)
    assert {"Externa", "Externa 2"} <= nombres
    assert "Interna" not in nombres


def test_error_en_interno_no_atrapado_deshace_todo(con, mes_id):
    # Verifica: si el error del interno sigue hacia afuera, el externo también deshace todo.
    antes = foto(con)
    with pytest.raises(Falla):
        with con:
            con.execute("INSERT INTO personas (nombre) VALUES ('A')")
            with con:
                con.execute("INSERT INTO personas (nombre) VALUES ('B')")
                raise Falla
    assert foto(con) == antes
    assert con._nivel == 0 and not con.in_transaction


def test_interno_liberado_y_luego_error_externo_deshace_todo(con):
    # Verifica: aunque el interno se haya liberado bien, un fallo posterior del externo
    # deshace también lo del interno (el RELEASE no guarda).
    antes = foto(con)
    with pytest.raises(Falla):
        with con:
            with con:
                con.execute("INSERT INTO personas (nombre) VALUES ('Interna ok')")
            raise Falla
    assert foto(con) == antes


# ---------------------------------------------------------------------------
# Niveles
# ---------------------------------------------------------------------------


def test_tres_niveles_todo_bien(con):
    # Verifica: tres niveles exitosos guardan todo, y el nivel se ve 1, 2, 3 adentro.
    niveles = []
    with con:
        niveles.append(con._nivel)
        con.execute("INSERT INTO personas (nombre) VALUES ('N1')")
        with con:
            niveles.append(con._nivel)
            con.execute("INSERT INTO personas (nombre) VALUES ('N2')")
            with con:
                niveles.append(con._nivel)
                con.execute("INSERT INTO personas (nombre) VALUES ('N3')")
    assert niveles == [1, 2, 3]
    assert {"N1", "N2", "N3"} <= nombres_personas(con)
    assert con._nivel == 0 and not con.in_transaction


def test_tres_niveles_falla_el_tercero_atrapado_en_el_segundo(con):
    # Verifica: se deshace solo el nivel 3; los niveles 1 y 2 se guardan.
    with con:
        con.execute("INSERT INTO personas (nombre) VALUES ('N1')")
        with con:
            con.execute("INSERT INTO personas (nombre) VALUES ('N2')")
            try:
                with con:
                    con.execute("INSERT INTO personas (nombre) VALUES ('N3')")
                    raise Falla
            except Falla:
                pass
            con.execute("INSERT INTO personas (nombre) VALUES ('N2b')")
    nombres = nombres_personas(con)
    assert {"N1", "N2", "N2b"} <= nombres
    assert "N3" not in nombres
    assert con._nivel == 0


def test_tres_niveles_falla_el_segundo_con_el_tercero_ya_liberado(con):
    # Verifica: si falla el nivel 2 después de que el 3 terminó bien, se deshacen 2 y 3.
    with con:
        con.execute("INSERT INTO personas (nombre) VALUES ('N1')")
        try:
            with con:
                con.execute("INSERT INTO personas (nombre) VALUES ('N2')")
                with con:
                    con.execute("INSERT INTO personas (nombre) VALUES ('N3')")
                raise Falla
        except Falla:
            pass
    nombres = nombres_personas(con)
    assert "N1" in nombres and not ({"N2", "N3"} & nombres)


def test_tres_niveles_falla_todo_hasta_afuera(con):
    # Verifica: error en el tercero sin atrapar deshace todo y deja nivel 0.
    antes = foto(con)
    with pytest.raises(Falla):
        with con:
            with con:
                with con:
                    con.execute("INSERT INTO personas (nombre) VALUES ('N3')")
                    raise Falla
    assert foto(con) == antes
    assert con._nivel == 0 and not con.in_transaction


def test_nivel_e_in_transaction_en_cada_paso(con):
    # Verifica: in_transaction es True adentro y False al salir, en éxito y en error.
    assert con._nivel == 0 and not con.in_transaction
    with con:
        assert con.in_transaction and con._nivel == 1
    assert con._nivel == 0 and not con.in_transaction
    with pytest.raises(Falla):
        with con:
            assert con.in_transaction
            raise Falla
    assert con._nivel == 0 and not con.in_transaction


def test_la_conexion_sirve_despues_de_un_error(con, mes_id):
    # Verifica: tras un error anidado se puede seguir usando la conexión normalmente.
    with pytest.raises(Falla):
        with con:
            with con:
                raise Falla
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gid = gastos.agregar_gasto(con, mes_id, "Después", otros, 1000, "unico")
    assert gastos.obtener_gasto(con, gid) is not None
    assert not con.in_transaction


def test_se_puede_reusar_el_bloque_muchas_veces(con):
    # Verifica: no quedan savepoints colgados después de muchas vueltas.
    antes = cantidad_filas(con, "personas")
    for i in range(50):
        with con:
            with con:
                con.execute("INSERT INTO personas (nombre) VALUES (?)", (f"P{i}",))
    assert con._nivel == 0
    assert cantidad_filas(con, "personas") == antes + 50


# ---------------------------------------------------------------------------
# Sin anidar: igual que antes
# ---------------------------------------------------------------------------


def test_sin_anidar_guarda_al_terminar(con, mes_id):
    # Verifica: un with simple guarda y no deja transacción abierta.
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gastos.agregar_gasto(con, mes_id, "Simple", otros, 1000, "unico")
    assert not con.in_transaction
    assert cantidad_filas(con, "gastos") == 1


def test_sin_anidar_error_deshace_y_propaga(con):
    # Verifica: un with simple que falla deshace y deja pasar el error original.
    with pytest.raises(Falla):
        with con:
            con.execute("INSERT INTO personas (nombre) VALUES ('X')")
            raise Falla
    assert "X" not in nombres_personas(con)
    assert not con.in_transaction


def test_with_devuelve_la_misma_conexion(con):
    # Verifica: "with con as c" entrega la conexión (como sqlite3 común).
    with con as c:
        assert c is con


def test_es_instancia_de_conexion(con):
    # Verifica: conectar() usa la clase nueva y sigue siendo una sqlite3.Connection.
    assert isinstance(con, base_datos.Conexion)
    assert isinstance(con, sqlite3.Connection)


def test_with_entra_con_transaccion_ya_abierta(con):
    # Verifica: si ya hay una transacción abierta al entrar al nivel 0, no hay BEGIN
    # doble y se guarda al salir.
    con.execute("BEGIN")
    with con:
        con.execute("INSERT INTO personas (nombre) VALUES ('Previa')")
    assert not con.in_transaction
    assert "Previa" in nombres_personas(con)


def test_commit_explicito_dentro_de_externo_no_rompe(con):
    # Verifica (borde): un con.commit() manual dentro de un with externo seguido de un
    # error no deja el nivel desbalanceado.
    with pytest.raises(Falla):
        with con:
            con.execute("INSERT INTO personas (nombre) VALUES ('Antes')")
            con.commit()
            raise Falla
    assert con._nivel == 0 and not con.in_transaction


def test_commit_explicito_dentro_de_interno_deja_nivel_en_0(con):
    # Verifica (borde): un commit() manual dentro de un interno hace fallar el RELEASE;
    # aun así el nivel debe volver a 0 para no dejar la conexión rota.
    try:
        with con:
            with con:
                con.execute("INSERT INTO personas (nombre) VALUES ('C')")
                con.commit()
    except sqlite3.OperationalError:
        pass
    assert con._nivel == 0, "el nivel debe volver a 0 aunque falle el RELEASE"


# ---------------------------------------------------------------------------
# Base en archivo
# ---------------------------------------------------------------------------


def _nombres_de_personas(ruta):
    crudo = sqlite3.connect(ruta)
    try:
        return {f[0] for f in crudo.execute("SELECT nombre FROM personas")}
    finally:
        crudo.close()


def test_archivo_lo_deshecho_no_queda_al_reabrir(tmp_path):
    # Verifica: en una base en archivo, un rollback externo no deja nada al reabrir.
    ruta = tmp_path / "gastos.db"
    con = base_datos.conectar(ruta)
    antes = _nombres_de_personas(ruta)
    with pytest.raises(Falla):
        with con:
            catalogos.crear(con, catalogos.PERSONAS, "Fantasma")
            with con:
                catalogos.crear(con, catalogos.PERSONAS, "Fantasma 2")
            raise Falla
    con.close()
    assert _nombres_de_personas(ruta) == antes


def test_archivo_lo_guardado_queda_y_lo_interno_deshecho_no(tmp_path):
    # Verifica: tras éxito externo y un interno deshecho, el archivo tiene lo correcto.
    ruta = tmp_path / "gastos.db"
    con = base_datos.conectar(ruta)
    with con:
        catalogos.crear(con, catalogos.PERSONAS, "Queda")
        try:
            with con:
                catalogos.crear(con, catalogos.PERSONAS, "No queda")
                raise Falla
        except Falla:
            pass
    con.close()
    nombres = _nombres_de_personas(ruta)
    assert "Queda" in nombres and "No queda" not in nombres


def test_archivo_otra_conexion_no_ve_lo_no_confirmado(tmp_path):
    # Verifica: mientras el bloque externo está abierto, otra conexión no ve los datos
    # (ningún bloque interno hizo commit parcial).
    ruta = tmp_path / "gastos.db"
    con = base_datos.conectar(ruta)
    with con:
        with con:
            catalogos.crear(con, catalogos.PERSONAS, "Pendiente")
        assert "Pendiente" not in _nombres_de_personas(ruta)
    assert "Pendiente" in _nombres_de_personas(ruta)
    con.close()


def test_archivo_importacion_completa_se_deshace(tmp_path):
    # Verifica: con funciones reales y base en archivo, el fallo final no deja rastro.
    ruta = tmp_path / "gastos.db"
    con = base_datos.conectar(ruta)
    mes = meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
    antes = foto(con)
    with pytest.raises(Falla):
        with con:
            operaciones_reales(con, mes)
            raise Falla
    assert foto(con) == antes
    con.close()
    reabierta = base_datos.conectar(ruta)
    assert foto(reabierta) == antes
    reabierta.close()


# ---------------------------------------------------------------------------
# crear_tablas / actualizar_estructura
# ---------------------------------------------------------------------------


def test_base_nueva_en_archivo_se_crea_y_reabre(tmp_path):
    # Verifica: crear_tablas con la clase nueva funciona en base nueva y al reabrir.
    ruta = tmp_path / "nueva.db"
    base_datos.conectar(ruta).close()
    con = base_datos.conectar(ruta)
    assert base_datos.version_de(con) == base_datos.VERSION_ACTUAL
    assert not con.in_transaction and con._nivel == 0
    con.close()


def test_migracion_de_base_vieja_deja_nivel_0(tmp_path):
    # Verifica: migrar una base v0 con la conexión nueva termina en nivel 0, sin
    # transacción abierta y en la versión actual.
    from tests.test_migracion import crear_base_v0

    ruta = tmp_path / "vieja.db"
    crear_base_v0(ruta)
    con = base_datos.conectar(ruta)
    assert base_datos.version_de(con) == base_datos.VERSION_ACTUAL
    assert con._nivel == 0 and not con.in_transaction
    con.close()


def test_base_migrada_admite_bloques_anidados(tmp_path):
    # Verifica: después de migrar, los bloques anidados deshacen bien.
    from tests.test_migracion import crear_base_v0

    ruta = tmp_path / "vieja.db"
    crear_base_v0(ruta)
    con = base_datos.conectar(ruta)
    antes = foto(con)
    with pytest.raises(Falla):
        with con:
            catalogos.crear(con, catalogos.PERSONAS, "Nueva")
            raise Falla
    assert foto(con) == antes
    con.close()
