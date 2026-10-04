"""Pruebas del atributo "campo" de ErrorDeValidacion (ronda 4): la lógica dice qué
dato falló para que la pantalla ponga el mensaje debajo del campo correcto."""

import pytest

from app.logica import catalogos, gastos, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import validar_centavos
from tests.ayudantes import id_por_nombre, insertar_pago


def _campo_de(funcion, *args, **kwargs):
    with pytest.raises(ErrorDeValidacion) as error:
        funcion(*args, **kwargs)
    return error.value.campo


def test_por_defecto_campo_es_none():
    assert ErrorDeValidacion("x").campo is None
    assert str(ErrorDeValidacion("Mensaje", "monto")) == "Mensaje"


@pytest.mark.parametrize(
    ("args", "campo"),
    [
        ((26, 10, 120000, 160000), "anio"),
        ((2026, 13, 120000, 160000), "mes"),
        ((2026, 10, -1, 160000), "sueldo"),
        ((2026, 10, 1.5, 160000), "sueldo"),
        ((2026, 10, 120000, 0), "cotizacion"),
        ((2026, 10, 120000, 10**20), "cotizacion"),
    ],
)
def test_campo_en_crear_primer_mes(con, args, campo):
    assert _campo_de(meses.crear_primer_mes, con, *args) == campo


def test_campo_en_agregar_gasto(con, mes_id):
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    assert (
        _campo_de(gastos.agregar_gasto, con, mes_id, " ", otros, 100, "fijo")
        == "nombre"
    )
    assert (
        _campo_de(gastos.agregar_gasto, con, mes_id, "X", None, 100, "fijo")
        == "categoria"
    )
    assert (
        _campo_de(gastos.agregar_gasto, con, mes_id, "X", 999, 100, "fijo")
        == "categoria"
    )
    assert (
        _campo_de(gastos.agregar_gasto, con, mes_id, "X", otros, 0, "fijo") == "monto"
    )
    assert (
        _campo_de(gastos.agregar_gasto, con, mes_id, "X", otros, 100, "cuota") == "tipo"
    )
    assert (
        _campo_de(gastos.agregar_gasto, con, mes_id, "X", otros, 100, "fijo", 999)
        == "medio_pago"
    )
    # Un mes que no existe no es culpa de un campo del formulario.
    assert _campo_de(gastos.agregar_gasto, con, 999, "X", otros, 100, "fijo") is None


def test_rn_23_mensaje_nuevo_con_campo_monto(con, mes_id):
    # RN-23: mensaje nuevo con lo pagado formateado, en el campo "monto".
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gid = gastos.agregar_gasto(con, mes_id, "Seguro", otros, 18000000, "fijo")
    insertar_pago(con, gid, 6000000)
    with pytest.raises(ErrorDeValidacion) as error:
        gastos.editar_gasto(con, gid, "Seguro", otros, 5000000, "fijo")
    assert (
        str(error.value)
        == "No podés bajar el monto a menos de lo que ya pagaste ($ 60.000)."
    )
    assert error.value.campo == "monto"


def test_campo_en_catalogos(con):
    assert _campo_de(catalogos.crear, con, catalogos.CATEGORIAS, "") == "nombre"
    assert _campo_de(catalogos.crear, con, catalogos.CATEGORIAS, "salud") == "nombre"
    assert _campo_de(catalogos.eliminar, con, catalogos.CATEGORIAS, 999) is None


def test_validar_centavos_pasa_el_campo():
    assert _campo_de(validar_centavos, 0, campo="monto") == "monto"
    assert _campo_de(validar_centavos, 0) is None
