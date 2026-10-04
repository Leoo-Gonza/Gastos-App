"""Pruebas de app/logica/catalogos.py: categorías y medios de pago
(RF-10, RF-11, CA-10.x, CA-11.x, RN-49, RN-50)."""

import pytest

from app.logica import catalogos, gastos
from app.logica.errores import ErrorDeValidacion
from tests.ayudantes import id_por_nombre, insertar_mes, insertar_plan

# Las reglas de nombre y archivado son las mismas para categorías y medios (CA-11.2),
# así que varias pruebas se corren para las dos listas.
AMBAS = pytest.mark.parametrize("tabla", [catalogos.CATEGORIAS, catalogos.MEDIOS_PAGO])


def _nombres(con, tabla, incluir_archivados=False):
    return [f["nombre"] for f in catalogos.listar(con, tabla, incluir_archivados)]


def _agregar_gasto_con(con, mes_id, tabla, id_):
    """Crea un gasto que usa la categoría o el medio indicado."""
    if tabla == catalogos.CATEGORIAS:
        return gastos.agregar_gasto(con, mes_id, "Cuota gym", id_, 2500000, "fijo")
    categoria = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    return gastos.agregar_gasto(
        con, mes_id, "Cuota gym", categoria, 2500000, "fijo", id_
    )


# ---------------------------------------------------------------------------
# Crear y renombrar
# ---------------------------------------------------------------------------


@AMBAS
def test_crear_devuelve_id_y_aparece_en_la_lista(con, tabla):
    # RF-10 / RF-11: crear un elemento nuevo.
    nuevo = catalogos.crear(con, tabla, "Gym")
    assert catalogos.obtener(con, tabla, nuevo)["nombre"] == "Gym"
    assert "Gym" in _nombres(con, tabla)


@AMBAS
def test_crear_normaliza_espacios(con, tabla):
    # Los espacios sobrantes se quitan: "  Gym   del  barrio " -> "Gym del barrio".
    nuevo = catalogos.crear(con, tabla, "  Gym   del  barrio ")
    assert catalogos.obtener(con, tabla, nuevo)["nombre"] == "Gym del barrio"


def test_ca_10_1_crear_educacion(con):
    # CA-10.1 (texto nuevo): se puede crear "Educación" y queda disponible.
    nueva = catalogos.crear(con, catalogos.CATEGORIAS, "Educación")
    assert catalogos.obtener(con, catalogos.CATEGORIAS, nueva)["nombre"] == "Educación"
    assert "Educación" in _nombres(con, catalogos.CATEGORIAS)


def test_ca_10_1_renombrar_salud_se_ve_en_los_gastos(con, mes_id):
    # CA-10.1 (texto nuevo): renombrar la categoría inicial "Salud" a "Salud y
    # bienestar"; los gastos que la usaban muestran el nombre nuevo, con el mismo id.
    salud = id_por_nombre(con, catalogos.CATEGORIAS, "Salud")
    gastos.agregar_gasto(con, mes_id, "Psicólogo", salud, 14000000, "fijo")
    catalogos.renombrar(con, catalogos.CATEGORIAS, salud, "Salud y bienestar")
    fila = gastos.listar_gastos(con, mes_id)[0]
    assert fila["categoria"] == "Salud y bienestar"
    assert fila["categoria_id"] == salud
    assert "Salud" not in _nombres(con, catalogos.CATEGORIAS)


def test_crear_salud_cuando_ya_existe_como_inicial(con):
    # "Salud" ya es categoría inicial: crearla otra vez se rechaza (RN-50).
    with pytest.raises(ErrorDeValidacion, match="Ya existe"):
        catalogos.crear(con, catalogos.CATEGORIAS, "Salud")


@AMBAS
def test_renombrar_a_si_mismo_cambiando_mayusculas(con, tabla):
    # Renombrar "Gym" a "GYM" no choca consigo mismo.
    nuevo = catalogos.crear(con, tabla, "Gym")
    catalogos.renombrar(con, tabla, nuevo, "GYM")
    assert catalogos.obtener(con, tabla, nuevo)["nombre"] == "GYM"


def test_ca_11_1_medios_distintos(con, mes_id):
    # CA-11.1 (catálogo): "Visa Santander" y "Mastercard Nación" son medios distintos
    # y cada gasto queda con el suyo.
    visa = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Visa Santander")
    master = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Mastercard Nación")
    assert visa != master
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gastos.agregar_gasto(con, mes_id, "Seguro de moto", otros, 13100000, "fijo", visa)
    gastos.agregar_gasto(con, mes_id, "Teléfono", otros, 2000000, "fijo", master)
    medios = {f["nombre"]: f["medio_pago"] for f in gastos.listar_gastos(con, mes_id)}
    assert medios == {
        "Seguro de moto": "Visa Santander",
        "Teléfono": "Mastercard Nación",
    }


# ---------------------------------------------------------------------------
# CA-10.2 / CA-11.2: nombres vacíos o repetidos
# ---------------------------------------------------------------------------


@AMBAS
@pytest.mark.parametrize("nombre", ["", "   ", "\t\n"])
def test_ca_10_2_nombre_vacio_se_rechaza(con, tabla, nombre):
    # RN-50: el nombre no puede estar vacío (ni ser solo espacios).
    antes = len(_nombres(con, tabla, True))
    with pytest.raises(ErrorDeValidacion, match="vacío"):
        catalogos.crear(con, tabla, nombre)
    assert len(_nombres(con, tabla, True)) == antes


@AMBAS
def test_ca_10_2_renombrar_a_vacio_se_rechaza(con, tabla):
    nuevo = catalogos.crear(con, tabla, "Gym")
    with pytest.raises(ErrorDeValidacion):
        catalogos.renombrar(con, tabla, nuevo, "  ")
    assert catalogos.obtener(con, tabla, nuevo)["nombre"] == "Gym"


@AMBAS
@pytest.mark.parametrize("repetido", ["gym", "GYM", "  Gym  ", "gYm"])
def test_ca_10_2_nombre_repetido_sin_distinguir_mayusculas(con, tabla, repetido):
    # RN-50: "gym" si existe "Gym" se rechaza.
    catalogos.crear(con, tabla, "Gym")
    with pytest.raises(ErrorDeValidacion, match="Ya existe"):
        catalogos.crear(con, tabla, repetido)


@AMBAS
def test_ca_10_2_nombre_repetido_con_letras_acentuadas(con, tabla):
    # RN-50 con letras que COLLATE NOCASE no entiende: "ÑANDÚ" repite a "Ñandú".
    catalogos.crear(con, tabla, "Ñandú")
    with pytest.raises(ErrorDeValidacion):
        catalogos.crear(con, tabla, "ñandú")


@AMBAS
def test_ca_10_2_repetido_de_un_archivado_avisa_que_esta_archivado(con, mes_id, tabla):
    # CA-10.2: repetido aunque esté archivado; el mensaje sugiere desarchivar.
    gym = catalogos.crear(con, tabla, "Gym")
    _agregar_gasto_con(con, mes_id, tabla, gym)
    assert catalogos.eliminar(con, tabla, gym) == "archivado"
    with pytest.raises(ErrorDeValidacion, match="archivados"):
        catalogos.crear(con, tabla, "gym")


@AMBAS
def test_ca_10_2_renombrar_a_un_nombre_existente(con, tabla):
    catalogos.crear(con, tabla, "Gym")
    otro = catalogos.crear(con, tabla, "Club")
    with pytest.raises(ErrorDeValidacion, match="Ya existe"):
        catalogos.renombrar(con, tabla, otro, "GYM")
    assert catalogos.obtener(con, tabla, otro)["nombre"] == "Club"


# ---------------------------------------------------------------------------
# CA-10.3 / CA-11.2: eliminar y archivar
# ---------------------------------------------------------------------------


@AMBAS
def test_ca_10_3_eliminar_sin_uso_se_borra(con, tabla):
    # RN-49: una que no está en uso se borra de verdad.
    nuevo = catalogos.crear(con, tabla, "Gym")
    assert catalogos.eliminar(con, tabla, nuevo) == "borrado"
    assert catalogos.obtener(con, tabla, nuevo) is None
    assert "Gym" not in _nombres(con, tabla, incluir_archivados=True)


@AMBAS
def test_ca_10_3_eliminar_en_uso_se_archiva(con, tabla):
    # CA-10.3: "Gym" con un gasto en 2026-09 queda archivada; 2026-09 sigue mostrando
    # "Gym"; no se ofrece para cargas nuevas.
    septiembre = insertar_mes(con, 2026, 9)
    gym = catalogos.crear(con, tabla, "Gym")
    _agregar_gasto_con(con, septiembre, tabla, gym)

    assert catalogos.esta_en_uso(con, tabla, gym) is True
    assert catalogos.eliminar(con, tabla, gym) == "archivado"
    assert catalogos.obtener(con, tabla, gym)["archivado"] == 1
    # No se ofrece para cargas nuevas (CA-06.5)...
    assert "Gym" not in _nombres(con, tabla)
    # ...pero sigue en la lista completa y en el historial.
    assert "Gym" in _nombres(con, tabla, incluir_archivados=True)
    fila = gastos.listar_gastos(con, septiembre)[0]
    columna = "categoria" if tabla == catalogos.CATEGORIAS else "medio_pago"
    assert fila[columna] == "Gym"
    assert (
        fila[columna + ("_archivada" if columna == "categoria" else "_archivado")] == 1
    )


@AMBAS
def test_eliminar_en_uso_por_un_plan_de_cuotas_se_archiva(con, tabla):
    # RN-49: "en uso" incluye planes de cuotas, no solo gastos.
    gym = catalogos.crear(con, tabla, "Gym")
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    if tabla == catalogos.CATEGORIAS:
        insertar_plan(con, "Bicicleta", gym)
    else:
        insertar_plan(con, "Bicicleta", otros, gym)
    assert catalogos.eliminar(con, tabla, gym) == "archivado"


@AMBAS
def test_ca_10_3_no_se_puede_cargar_un_gasto_nuevo_con_un_archivado(con, mes_id, tabla):
    # RN-49: archivada no se puede elegir para un gasto nuevo.
    gym = catalogos.crear(con, tabla, "Gym")
    _agregar_gasto_con(con, mes_id, tabla, gym)
    catalogos.eliminar(con, tabla, gym)
    with pytest.raises(ErrorDeValidacion, match="archivad"):
        _agregar_gasto_con(con, mes_id, tabla, gym)


def test_eliminar_en_uso_no_borra_el_gasto(con, mes_id):
    # Archivar la categoría no toca los gastos que la usan.
    gym = catalogos.crear(con, catalogos.CATEGORIAS, "Gym")
    gastos.agregar_gasto(con, mes_id, "Cuota gym", gym, 2500000, "fijo")
    catalogos.eliminar(con, catalogos.CATEGORIAS, gym)
    assert gastos.total_gastos(con, mes_id) == 2500000


def test_eliminar_persona_en_uso_se_archiva(con):
    # RN-49 también vale para personas (usadas en "me deben"; tabla del paso 5).
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    with con:
        con.execute(
            "INSERT INTO items_me_deben (persona_id, descripcion, monto_cent, fecha) "
            "VALUES (?, 'Préstamo', 500000, '2026-10-01')",
            (sofia,),
        )
    assert catalogos.eliminar(con, catalogos.PERSONAS, sofia) == "archivado"


# ---------------------------------------------------------------------------
# CA-10.4 / CA-11.2: desarchivar
# ---------------------------------------------------------------------------


@AMBAS
def test_ca_10_4_desarchivar_vuelve_a_ofrecerse(con, mes_id, tabla):
    # CA-10.4: desarchivar "Gym" la vuelve a ofrecer y permite cargar gastos nuevos.
    gym = catalogos.crear(con, tabla, "Gym")
    _agregar_gasto_con(con, mes_id, tabla, gym)
    catalogos.eliminar(con, tabla, gym)
    catalogos.desarchivar(con, tabla, gym)
    assert "Gym" in _nombres(con, tabla)
    _agregar_gasto_con(con, mes_id, tabla, gym)  # no lanza error
    assert len(gastos.listar_gastos(con, mes_id)) == 2


# ---------------------------------------------------------------------------
# Otros
# ---------------------------------------------------------------------------


def test_listar_ordena_por_nombre_sin_distinguir_mayusculas(con):
    # La lista sale ordenada alfabéticamente ignorando mayúsculas.
    catalogos.crear(con, catalogos.CATEGORIAS, "alquiler extra")
    nombres = _nombres(con, catalogos.CATEGORIAS)
    assert nombres == sorted(nombres, key=str.casefold)


def test_lista_desconocida_se_rechaza(con):
    # Solo se aceptan las tres tablas conocidas (protege el SQL armado con f-string).
    with pytest.raises(ValueError):
        catalogos.listar(con, "gastos; DROP TABLE meses")
    with pytest.raises(ValueError):
        catalogos.crear(con, "meses", "X")


# ---------------------------------------------------------------------------
# Ronda 2: O4 (ids inexistentes) y O5 (orden con acentos)
# ---------------------------------------------------------------------------


@AMBAS
@pytest.mark.parametrize("accion", ["renombrar", "eliminar", "desarchivar"])
def test_o4_id_inexistente_avisa(con, tabla, accion):
    # O4: renombrar, eliminar o desarchivar algo que ya no existe avisa con mensaje
    # (antes eliminar devolvía "borrado" y los otros no hacían nada).
    antes = _nombres(con, tabla, incluir_archivados=True)
    with pytest.raises(ErrorDeValidacion, match="ya no existe"):
        if accion == "renombrar":
            catalogos.renombrar(con, tabla, 9999, "Nuevo")
        elif accion == "eliminar":
            catalogos.eliminar(con, tabla, 9999)
        else:
            catalogos.desarchivar(con, tabla, 9999)
    assert _nombres(con, tabla, incluir_archivados=True) == antes


@AMBAS
def test_o4_eliminar_dos_veces_el_mismo(con, tabla):
    # O4: el segundo intento de borrar (ej. con dos ventanas) avisa que ya no existe.
    nuevo = catalogos.crear(con, tabla, "Gym")
    assert catalogos.eliminar(con, tabla, nuevo) == "borrado"
    with pytest.raises(ErrorDeValidacion, match="ya no existe"):
        catalogos.eliminar(con, tabla, nuevo)


def test_o4_renombrar_inexistente_a_nombre_repetido_avisa_que_no_existe(con):
    # O4: si el elemento no existe, el aviso es "ya no existe" y no "Ya existe ...".
    with pytest.raises(ErrorDeValidacion, match="ya no existe"):
        catalogos.renombrar(con, catalogos.CATEGORIAS, 9999, "Salud")


def test_o5_listar_ordena_ignorando_acentos_y_mayusculas(con):
    # O5: "Árbol" va con la A, "Ñoquis" con la N, "Óptica" con la O, y las
    # minúsculas no quedan al final.
    for nombre in ["Árbol", "Ñoquis", "educación", "Óptica"]:
        catalogos.crear(con, catalogos.CATEGORIAS, nombre)
    assert _nombres(con, catalogos.CATEGORIAS) == [
        "Árbol",
        "Deudas",
        "educación",
        "Mercado",
        "Ñoquis",
        "Óptica",
        "Otros",
        "Salud",
        "Servicios",
        "Transporte",
        "Vivienda",
    ]


def test_o5_orden_tambien_con_archivados_y_medios(con, mes_id):
    # O5: el orden vale con incluir_archivados=True y para medios de pago.
    nuevo = catalogos.crear(con, catalogos.MEDIOS_PAGO, "Ágil Pagos")
    otros = id_por_nombre(con, catalogos.CATEGORIAS, "Otros")
    gastos.agregar_gasto(con, mes_id, "X", otros, 100, "unico", nuevo)
    assert catalogos.eliminar(con, catalogos.MEDIOS_PAGO, nuevo) == "archivado"
    assert _nombres(con, catalogos.MEDIOS_PAGO, incluir_archivados=True) == [
        "Ágil Pagos",
        "Efectivo",
        "Tarjeta de crédito",
        "Transferencia",
    ]
    assert _nombres(con, catalogos.MEDIOS_PAGO) == [
        "Efectivo",
        "Tarjeta de crédito",
        "Transferencia",
    ]
