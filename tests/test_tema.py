"""Pruebas de la lógica del tema (Ajustes → Apariencia, diseno.md §3.10):
configuracion.TEMAS, obtener_tema y guardar_tema. Base en memoria."""

import pytest

from app.logica import configuracion
from app.logica.errores import ErrorDeValidacion


def test_temas_posibles():
    # Los tres valores que se guardan, en el orden en que se muestran.
    assert configuracion.TEMAS == ("claro", "oscuro", "sistema")


def test_por_defecto_es_sistema(con):
    # Si nunca se eligió un tema, "Como el sistema".
    assert configuracion.obtener_tema(con) == "sistema"


@pytest.mark.parametrize("tema", ["claro", "oscuro", "sistema"])
def test_guardar_y_obtener(con, tema):
    configuracion.guardar_tema(con, tema)
    assert configuracion.obtener_tema(con) == tema


def test_guardar_reemplaza_el_anterior(con):
    # Una sola fila de tema: el último elegido gana.
    for tema in ["oscuro", "claro", "sistema", "oscuro"]:
        configuracion.guardar_tema(con, tema)
    assert configuracion.obtener_tema(con) == "oscuro"
    filas = con.execute(
        "SELECT COUNT(*) AS n FROM configuracion WHERE clave = 'tema'"
    ).fetchone()
    assert filas["n"] == 1


@pytest.mark.parametrize("tema", ["", "Oscuro", "OSCURO", " claro", "rosa", None, 1])
def test_guardar_tema_invalido(con, tema):
    # Un valor que no es uno de los tres se rechaza (campo "tema") y no se guarda nada.
    configuracion.guardar_tema(con, "claro")
    with pytest.raises(ErrorDeValidacion) as error:
        configuracion.guardar_tema(con, tema)
    assert str(error.value) == "El tema tiene que ser claro, oscuro o sistema."
    assert error.value.campo == "tema"
    assert configuracion.obtener_tema(con) == "claro"


@pytest.mark.parametrize("valor", ["rosa", "", "Oscuro", "sistema "])
def test_valor_invalido_guardado_a_mano_es_sistema(con, valor):
    # Borde: si en la base quedó un valor raro (editado a mano), se usa "sistema".
    with con:
        con.execute(
            "INSERT OR REPLACE INTO configuracion (clave, valor) VALUES ('tema', ?)",
            (valor,),
        )
    assert configuracion.obtener_tema(con) == "sistema"


def test_el_tema_no_toca_la_meta(con):
    # El tema y la meta de ahorro son claves distintas de configuracion.
    configuracion.guardar_meta(con, 50000)
    configuracion.guardar_tema(con, "oscuro")
    assert configuracion.obtener_meta(con) == 50000
    configuracion.quitar_meta(con)
    assert configuracion.obtener_tema(con) == "oscuro"
