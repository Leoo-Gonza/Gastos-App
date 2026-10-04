"""Pruebas de app/logica/formato.py: formateo de montos (RN-04, diseno.md §2.3)
y lectura de montos escritos por el usuario (RN-04, RN-05, diseno.md §2.4)."""

import pytest

from app.logica.errores import ErrorDeValidacion
from app.logica.formato import (
    MONTO_MAXIMO_CENT,
    clave_orden,
    formatear_ars,
    formatear_cotizacion,
    formatear_monto_para_editar,
    formatear_usd,
    leer_monto,
    nombre_mes,
    validar_centavos,
)

# ---------------------------------------------------------------------------
# formatear_ars
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (6602012, "$ 66.020"),  # RN-04: 66.020,12 -> "66.020"
        (2209368, "$ 22.094"),  # RN-04: 22.093,68 -> "22.094"
        (143461700, "$ 1.434.617"),  # punto de miles en millones
        (0, "$ 0"),
        (49, "$ 0"),  # 0,49 baja
        (50, "$ 1"),  # 0,50 sube (mitad hacia arriba)
        (150, "$ 2"),  # 1,50 sube (no redondeo bancario, que daría 2 igual)
        (250, "$ 3"),  # 2,50 sube: el redondeo bancario daría "2"
        (99950, "$ 1.000"),  # el redondeo agrega un dígito de miles
        (100000, "$ 1.000"),
        (99900, "$ 999"),
    ],
)
def test_formatear_ars_redondea_mitad_hacia_arriba_y_separa_miles(centavos, esperado):
    # Verifica el formato de pesos: sin decimales, mitad hacia arriba, punto de miles.
    assert formatear_ars(centavos) == esperado


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (-50641700, "-$ 506.417"),  # ejemplo de diseno.md §2.3 ("Sin capacidad")
        (-290000, "-$ 2.900"),  # ejemplo "a devolver"
        (-50, "-$ 1"),  # -0,50 se ve "-1" (simétrico), no "0"
        (-49, "$ 0"),  # -0,49 redondea a 0 y no debe verse "-$ 0"
        (-250, "-$ 3"),
    ],
)
def test_formatear_ars_negativos(centavos, esperado):
    # Verifica el signo menos antes de la moneda y el redondeo simétrico de negativos.
    assert formatear_ars(centavos) == esperado


# ---------------------------------------------------------------------------
# formatear_usd
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (89664, "US$ 896,64"),
        (120000, "US$ 1.200,00"),
        (0, "US$ 0,00"),
        (5, "US$ 0,05"),  # centavos de un dígito llevan cero adelante
        (123456789, "US$ 1.234.567,89"),
        (-9664, "-US$ 96,64"),  # ejemplo de diseno.md §2.3 ("Déficit")
        (-5, "-US$ 0,05"),
    ],
)
def test_formatear_usd(centavos, esperado):
    # Verifica dólares con 2 decimales, coma decimal y punto de miles, incluso negativos.
    assert formatear_usd(centavos) == esperado


# ---------------------------------------------------------------------------
# formatear_cotizacion
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (160000, "$ 1.600 por US$"),
        (143250, "$ 1.432,50 por US$"),
        (143205, "$ 1.432,05 por US$"),  # centavos de un dígito
        (100, "$ 1 por US$"),
    ],
)
def test_formatear_cotizacion(centavos, esperado):
    # Verifica que la cotización muestre decimales solo si tiene centavos (RN-02).
    assert formatear_cotizacion(centavos) == esperado


# ---------------------------------------------------------------------------
# formatear_monto_para_editar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (6602050, "66.020,50"),  # diseno.md §2.4: "66020,5" -> "66.020,50"
        (6602000, "66.020"),
        (6602012, "66.020,12"),
        (5, "0,05"),
        (100, "1"),
    ],
)
def test_formatear_monto_para_editar(centavos, esperado):
    # Verifica el texto que se pone dentro del campo: sin "$" y sin perder centavos.
    assert formatear_monto_para_editar(centavos) == esperado


@pytest.mark.parametrize("centavos", [6602050, 6602000, 5, 100, 123456789])
def test_editar_y_volver_a_leer_da_el_mismo_monto(centavos):
    # Verifica la ida y vuelta: lo que se muestra para editar se vuelve a leer igual.
    assert leer_monto(formatear_monto_para_editar(centavos)) == centavos


def test_formatear_monto_para_editar_negativo():
    # Caso borde: un monto negativo (-1,50) debería verse "-1,50".
    # Hoy los montos editables son > 0, pero la función no lo impide.
    assert formatear_monto_para_editar(-150) == "-1,50"


# ---------------------------------------------------------------------------
# leer_monto: casos válidos
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("66020", 6602000),
        ("66.020", 6602000),
        ("66020,12", 6602012),
        ("66.020,12", 6602012),  # CA-06.4: se guarda exacto
        ("66020,5", 6602050),  # un decimal = decenas de centavos
        ("1.434.617", 143461700),
        ("0,5", 50),
        ("0,05", 5),
        ("  30.000  ", 3000000),  # espacios alrededor
        ("1", 100),
    ],
)
def test_leer_monto_acepta_formatos_validos(texto, esperado):
    # Verifica los formatos aceptados por diseno.md §2.4 y que el resultado está en centavos.
    assert leer_monto(texto) == esperado


def test_leer_monto_devuelve_entero():
    # RN-01: el monto se guarda como entero en centavos, nunca como float.
    assert isinstance(leer_monto("66.020,12"), int)


# ---------------------------------------------------------------------------
# leer_monto: casos inválidos
# ---------------------------------------------------------------------------


def test_leer_monto_rechaza_punto_decimal_con_mensaje_de_coma():
    # Regla del punto (diseno.md §2.4): "66020.12" se rechaza con el mensaje exacto.
    with pytest.raises(ErrorDeValidacion) as error:
        leer_monto("66020.12")
    assert str(error.value) == "Usá coma para los decimales. Ej.: 66.020,12"


def test_leer_monto_rechaza_punto_decimal_con_un_decimal():
    # "66020.5" también es punto decimal (teclado numérico) y debe pedir coma.
    with pytest.raises(ErrorDeValidacion, match="coma"):
        leer_monto("66020.5")


@pytest.mark.parametrize("texto", ["66020,123", "66.020,1234", "0,001"])
def test_leer_monto_rechaza_mas_de_dos_decimales(texto):
    # RN-04: la entrada acepta hasta 2 decimales.
    with pytest.raises(ErrorDeValidacion, match="2 decimales"):
        leer_monto(texto)


@pytest.mark.parametrize("texto", ["-5.000", "-5000", "-0,50", "-0"])
def test_leer_monto_rechaza_negativos(texto):
    # CA-06.2 / RN-05: negativos se rechazan con mensaje.
    with pytest.raises(ErrorDeValidacion, match="negativo"):
        leer_monto(texto)


@pytest.mark.parametrize("texto", ["", "   ", "\t"])
def test_leer_monto_rechaza_vacio(texto):
    # CA-06.2 / RN-05: monto vacío se rechaza.
    with pytest.raises(ErrorDeValidacion, match="Ingresá un monto"):
        leer_monto(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "abc",
        "12abc",
        "$ 100",
        "1.2345",
        "6.60.20",
        "66.02",
        ",50",
        "66020,",
        "1,2,3",
        "+500",
    ],
)
def test_leer_monto_rechaza_texto_y_formatos_raros(texto):
    # CA-06.2 / RN-05: texto no numérico o mal formado se rechaza con un mensaje.
    with pytest.raises(ErrorDeValidacion):
        leer_monto(texto)


@pytest.mark.parametrize("texto", ["0", "0,00", "0.000", "000"])
def test_leer_monto_rechaza_cero_por_defecto(texto):
    # CA-06.2 / RN-05: cero no es un monto válido para gastos.
    with pytest.raises(ErrorDeValidacion, match="mayor a 0"):
        leer_monto(texto)


@pytest.mark.parametrize("texto", ["0", "0,00"])
def test_leer_monto_permite_cero_para_sueldo(texto):
    # RN-05: el sueldo puede ser 0, con permitir_cero=True.
    assert leer_monto(texto, permitir_cero=True) == 0


def test_leer_monto_permitir_cero_sigue_rechazando_negativos():
    # permitir_cero no habilita negativos (sueldo >= 0).
    with pytest.raises(ErrorDeValidacion):
        leer_monto("-1", permitir_cero=True)


# ---------------------------------------------------------------------------
# nombre_mes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("anio", "mes", "esperado"),
    [
        (2026, 10, "Octubre 2026"),
        (2026, 1, "Enero 2026"),
        (2026, 12, "Diciembre 2026"),
        (2027, 9, "Septiembre 2027"),
    ],
)
def test_nombre_mes(anio, mes, esperado):
    # Verifica el nombre largo en español + año (diseno.md §2.3).
    assert nombre_mes(anio, mes) == esperado


@pytest.mark.parametrize("mes", [0, 13, -1])
def test_nombre_mes_rechaza_meses_imposibles(mes):
    # Fecha imposible: un mes fuera de 1..12 no debe devolver un nombre (ej. "Diciembre").
    with pytest.raises(ValueError):
        nombre_mes(2026, mes)


# ---------------------------------------------------------------------------
# Ronda 2: tope de montos (BUG-01), negativos (BUG-03), dígitos (O6)
# ---------------------------------------------------------------------------


def test_tope_es_999_999_999_999_pesos():
    # El tope acordado es $ 999.999.999.999 (expresado en centavos).
    assert MONTO_MAXIMO_CENT == 99_999_999_999_900


@pytest.mark.parametrize(
    "texto", ["999.999.999.999", "999999999999", "999999999999,00"]
)
def test_leer_monto_acepta_el_tope_exacto(texto):
    # El tope exacto es válido.
    assert leer_monto(texto) == MONTO_MAXIMO_CENT


@pytest.mark.parametrize(
    "texto",
    [
        "999.999.999.999,01",  # tope + 1 centavo
        "1.000.000.000.000",
        "99999999999999999999",
        "1" + "0" * 30,
    ],
)
def test_leer_monto_rechaza_mas_que_el_tope(texto):
    # BUG-01: más que el tope se rechaza con mensaje, no con un error técnico.
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        leer_monto(texto)


def test_leer_monto_tope_tambien_con_permitir_cero():
    # El tope vale también para el sueldo (permitir_cero=True).
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        leer_monto("999.999.999.999,01", permitir_cero=True)


def test_leer_monto_texto_con_miles_de_digitos_se_rechaza_con_mensaje():
    # Caso borde: pegar un número larguísimo (5000 dígitos) en el campo. Tiene que
    # rechazarse con ErrorDeValidacion, no con un error técnico de Python.
    with pytest.raises(ErrorDeValidacion):
        leer_monto("9" * 5000)


@pytest.mark.parametrize(
    "texto",
    [
        "１２３",  # "123" de ancho completo
        "٣٠",  # dígitos arábigo-índicos
        "66.０２０",  # mezcla de dígitos comunes y de ancho completo
        "1²",  # superíndice
    ],
)
def test_o6_leer_monto_rechaza_digitos_que_no_son_0_a_9(texto):
    # O6: solo se aceptan los dígitos 0-9.
    with pytest.raises(ErrorDeValidacion):
        leer_monto(texto)


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [(-150, "-1,50"), (-6602050, "-66.020,50"), (-100, "-1"), (-5, "-0,05")],
)
def test_formatear_monto_para_editar_negativos(centavos, esperado):
    # BUG-03: negativos con el signo adelante y los centavos correctos.
    assert formatear_monto_para_editar(centavos) == esperado


@pytest.mark.parametrize(
    ("centavos", "esperado"),
    [
        (-150, "-$ 1,50 por US$"),
        (-160000, "-$ 1.600 por US$"),
        (-143250, "-$ 1.432,50 por US$"),
    ],
)
def test_formatear_cotizacion_negativa(centavos, esperado):
    # BUG-03: el signo va antes de la moneda, como en formatear_ars (diseno.md §2.3).
    assert formatear_cotizacion(centavos) == esperado


# ---------------------------------------------------------------------------
# Ronda 3: largo máximo del texto (BUG-04) y validar_centavos (O8)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("0" * 19 + "1", 100),  # 20 caracteres con ceros a la izquierda: válido
        ("0" * 17 + "1,5", 150),  # 20 caracteres con decimales
        ("  " + "0" * 19 + "1  ", 100),  # los espacios no cuentan para el largo
        ("0.000.000.000.001,50", 150),  # 20 caracteres con puntos de miles
    ],
)
def test_bug04_texto_de_20_caracteres_se_acepta(texto, esperado):
    # BUG-04 (borde): hasta 20 caracteres (sin contar espacios) se acepta.
    assert leer_monto(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "0" * 20 + "1",  # 21 caracteres, aunque valga solo $ 1
        "9" * 4301,  # el caso que antes daba ValueError de Python
        "9" * 5000,
        "9" * 100_000,
    ],
    # ids cortos: con el texto completo como nombre, Windows no puede guardar el
    # nombre de la prueba en la variable de entorno PYTEST_CURRENT_TEST.
    ids=["21_caracteres", "4301_digitos", "5000_digitos", "100000_digitos"],
)
def test_bug04_texto_de_mas_de_20_caracteres_se_rechaza_con_mensaje(texto):
    # BUG-04: más de 20 caracteres se rechaza con ErrorDeValidacion, no con ValueError.
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        leer_monto(texto)


def test_bug04_texto_largo_y_mal_formado_da_el_mensaje_del_formato():
    # Un texto largo con letras da el mensaje de formato (el patrón va primero).
    with pytest.raises(
        ErrorDeValidacion, match="^Escribí solo números. Ej.: 66.020,12$"
    ):
        leer_monto("9" * 5000 + "abc")


def test_bug04_texto_largo_con_punto_decimal_pide_coma():
    with pytest.raises(ErrorDeValidacion, match="coma"):
        leer_monto("9" * 5000 + ".5")


# --- validar_centavos ---


@pytest.mark.parametrize("monto", [1, 100, 6602012, MONTO_MAXIMO_CENT])
def test_validar_centavos_acepta_enteros_positivos_hasta_el_tope(monto):
    # O8: enteros de 1 al tope son válidos (no devuelve nada ni lanza error).
    assert validar_centavos(monto) is None


@pytest.mark.parametrize(
    ("monto", "mensaje"),
    [
        (0, "El monto tiene que ser mayor a 0."),
        (-1, "El monto tiene que ser mayor a 0."),
        (MONTO_MAXIMO_CENT + 1, "El monto es demasiado grande."),
        (10**30, "El monto es demasiado grande."),
        (1.5, "El monto tiene que ser un número entero de centavos."),
        (100.0, "El monto tiene que ser un número entero de centavos."),
        ("100", "El monto tiene que ser un número entero de centavos."),
        (None, "El monto tiene que ser un número entero de centavos."),
        (True, "El monto tiene que ser un número entero de centavos."),
        (False, "El monto tiene que ser un número entero de centavos."),
    ],
)
def test_validar_centavos_rechaza_con_mensaje_exacto(monto, mensaje):
    # O8: cada caso inválido da su mensaje para mostrar.
    with pytest.raises(ErrorDeValidacion) as error:
        validar_centavos(monto)
    assert str(error.value) == mensaje


def test_validar_centavos_permitir_cero():
    # Con permitir_cero=True, 0 y el tope valen; negativos y tope + 1 no.
    validar_centavos(0, permitir_cero=True)
    validar_centavos(MONTO_MAXIMO_CENT, permitir_cero=True)
    with pytest.raises(ErrorDeValidacion, match="^El monto no puede ser negativo.$"):
        validar_centavos(-1, permitir_cero=True)
    with pytest.raises(ErrorDeValidacion, match="demasiado grande"):
        validar_centavos(MONTO_MAXIMO_CENT + 1, permitir_cero=True)
    with pytest.raises(ErrorDeValidacion, match="entero de centavos"):
        validar_centavos(False, permitir_cero=True)


@pytest.mark.parametrize(
    ("monto", "permitir_cero", "que", "mensaje"),
    [
        (-1, True, "El sueldo", "El sueldo no puede ser negativo."),
        (
            1.5,
            True,
            "El sueldo",
            "El sueldo tiene que ser un número entero de centavos.",
        ),
        (MONTO_MAXIMO_CENT + 1, True, "El sueldo", "El sueldo es demasiado grande."),
        (0, False, "La cotización", "La cotización tiene que ser mayor a 0."),
    ],
)
def test_validar_centavos_personaliza_el_sujeto(monto, permitir_cero, que, mensaje):
    # O8: el parámetro "que" cambia el sujeto del mensaje.
    with pytest.raises(ErrorDeValidacion) as error:
        validar_centavos(monto, permitir_cero=permitir_cero, que=que)
    assert str(error.value) == mensaje


# ---------------------------------------------------------------------------
# Ronda 5: clave_orden (BUG-05) y mensajes con "que" (BUG-07)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "clave"),
    [
        ("Árbol", "arbol"),
        ("ÑANDÚ", "nandu"),
        ("Psicólogo", "psicologo"),
        ("Óptica", "optica"),
        ("Pingüino", "pinguino"),
        ("Nafta", "nafta"),
        ("", ""),
    ],
)
def test_clave_orden_quita_acentos_y_mayusculas(texto, clave):
    # BUG-05: la clave de orden ignora acentos (Á como A, Ñ como N) y mayúsculas.
    assert clave_orden(texto) == clave


def test_clave_orden_ordena_como_un_diccionario():
    nombres = ["Psicólogo", "Ómnibus", "nafta", "Árbol", "Zapatillas", "Ñoquis"]
    assert sorted(nombres, key=clave_orden) == [
        "Árbol",
        "nafta",
        "Ñoquis",
        "Ómnibus",
        "Psicólogo",
        "Zapatillas",
    ]


@pytest.mark.parametrize("texto", ["abc", "12abc", "1.2345", "$ 100", "+500"])
def test_texto_no_numerico_dice_escribi_solo_numeros(texto):
    # BUG-07 / diseno.md §4: el mensaje de texto no numérico es el del diseño.
    with pytest.raises(ErrorDeValidacion) as error:
        leer_monto(texto)
    assert str(error.value) == "Escribí solo números. Ej.: 66.020,12"


@pytest.mark.parametrize(
    ("texto", "permitir_cero", "que", "mensaje"),
    [
        ("-5", True, "El sueldo", "El sueldo no puede ser negativo."),
        ("0", False, "La cotización", "La cotización tiene que ser mayor a 0."),
        (
            "999.999.999.999,01",
            False,
            "La cotización",
            "La cotización es demasiado grande.",
        ),
        ("0" * 21, True, "El sueldo", "El sueldo es demasiado grande."),
        ("-5", False, "El monto", "El monto no puede ser negativo."),
        ("0", False, "El monto", "El monto tiene que ser mayor a 0."),
    ],
)
def test_leer_monto_usa_que_en_los_mensajes(texto, permitir_cero, que, mensaje):
    # BUG-07: "que" nombra el dato en los mensajes de negativo, cero y tope.
    with pytest.raises(ErrorDeValidacion) as error:
        leer_monto(texto, permitir_cero=permitir_cero, que=que)
    assert str(error.value) == mensaje


@pytest.mark.parametrize(
    ("texto", "mensaje"),
    [
        ("", "Ingresá un monto."),
        ("66020.12", "Usá coma para los decimales. Ej.: 66.020,12"),
        ("66020,123", "Usá como máximo 2 decimales."),
        ("abc", "Escribí solo números. Ej.: 66.020,12"),
    ],
)
def test_mensajes_de_formato_no_cambian_con_que(texto, mensaje):
    # Los mensajes de formato son iguales para cualquier dato.
    with pytest.raises(ErrorDeValidacion) as error:
        leer_monto(texto, que="La cotización")
    assert str(error.value) == mensaje
