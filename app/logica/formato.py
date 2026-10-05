"""Formateo de montos para mostrar y lectura de montos escritos por el usuario.

Internamente todos los montos son enteros en centavos (RN-01). Este módulo es el
único lugar donde se convierten a texto y desde texto.
"""

import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal

from app.logica.errores import ErrorDeValidacion

MESES = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

# Tope de cualquier monto: $ 999.999.999.999 (o US$). Es muchísimo más que cualquier
# gasto real y evita números que no entran en un INTEGER de SQLite (64 bits).
MONTO_MAXIMO_CENT = 999_999_999_999_00
# Margen sobre los 18 caracteres del máximo, por si hay ceros a la izquierda.
_LARGO_MAXIMO_TEXTO = 20

# re.ASCII hace que \d sea solo 0-9. Sin eso, Python también acepta dígitos de
# otros alfabetos (ej. "１２３" de ancho completo).

# Un monto válido es la parte entera, con o sin puntos de miles, y opcionalmente
# una coma con 1 o 2 decimales. Ej.: "66020", "66.020", "66020,1", "66.020,12".
_PATRON_MONTO = re.compile(r"(\d+|\d{1,3}(\.\d{3})+)(,\d{1,2})?", re.ASCII)

# "66020.12": alguien usó punto como decimal (típico del teclado numérico).
_PATRON_PUNTO_DECIMAL = re.compile(r"\d+\.\d{1,2}", re.ASCII)

# "66020,123": más de 2 decimales.
_PATRON_MUCHOS_DECIMALES = re.compile(r"[\d.]+,\d{3,}", re.ASCII)


def _con_puntos_de_miles(numero: int) -> str:
    # Python separa miles con coma ("1,434,617"); en Argentina se usa punto.
    return f"{numero:,}".replace(",", ".")


def _redondear_a_pesos(centavos: int) -> int:
    # Redondeo "mitad hacia arriba" (RN-04): 50 centavos suben al peso siguiente.
    # Se aplica sobre el valor absoluto para que -0,50 se vea "-1" y no "0".
    signo = -1 if centavos < 0 else 1
    return signo * ((abs(centavos) + 50) // 100)


def formatear_ars(centavos: int) -> str:
    """6602012 -> "$ 66.020". Pesos sin decimales (RN-04)."""
    pesos = _redondear_a_pesos(centavos)
    signo = "-" if pesos < 0 else ""
    return f"{signo}$ {_con_puntos_de_miles(abs(pesos))}"


def formatear_usd(centavos: int) -> str:
    """89664 -> "US$ 896,64". Dólares con 2 decimales (RN-04)."""
    signo = "-" if centavos < 0 else ""
    enteros, resto = divmod(abs(centavos), 100)
    return f"{signo}US$ {_con_puntos_de_miles(enteros)},{resto:02d}"


def formatear_cotizacion(centavos: int) -> str:
    """160000 -> "$ 1.600 por US$"; 143250 -> "$ 1.432,50 por US$"."""
    return f"{formatear_cotizacion_corta(centavos)} por US$"


def formatear_cotizacion_corta(centavos: int) -> str:
    """160000 -> "$ 1.600"; 143250 -> "$ 1.432,50".

    A diferencia de formatear_ars, conserva los centavos si los tiene: si se
    redondeara, la cuenta "US$ 19,99 × $ 1.433" no daría el resultado mostrado.
    """
    signo = "-" if centavos < 0 else ""
    return f"{signo}$ {_pesos_y_centavos(abs(centavos))}"


def formatear_detalle_usd(monto_usd_cent: int, cotizacion_cent: int) -> str:
    """(2000, 160000) -> "US$ 20,00 × $ 1.600". Explica de dónde salen los pesos."""
    return f"{formatear_usd(monto_usd_cent)} × {formatear_cotizacion_corta(cotizacion_cent)}"


def convertir_usd_a_ars(monto_usd_cent: int, cotizacion_cent: int) -> int:
    """Pesos (en centavos) que hay que pagar por un monto en dólares (RN-53).

    La cotización está en centavos de peso por dólar, así que el producto queda
    con 100 de más: se divide por 100 redondeando al centavo, mitad hacia arriba
    (RN-03). Ej.: US$ 19,99 × $ 1.432,50 -> 1999 × 143250 / 100 = 2863567,5 -> 2863568.
    """
    # Sumar 50 antes de la división entera es el redondeo "mitad hacia arriba"
    # (los dos valores son positivos: los valida validar_centavos antes).
    return (monto_usd_cent * cotizacion_cent + 50) // 100


def _pesos_y_centavos(centavos: int) -> str:
    # Recibe un valor sin signo: divmod con negativos redondea hacia abajo
    # (divmod(-150, 100) da (-2, 50)) y mostraría "-2,50" en vez de "-1,50".
    enteros, resto = divmod(centavos, 100)
    texto = _con_puntos_de_miles(enteros)
    if resto:
        texto += f",{resto:02d}"
    return texto


def formatear_monto_para_editar(centavos: int) -> str:
    """Texto para poner dentro de un campo de monto: 6602050 -> "66.020,50".

    A diferencia de formatear_ars, no lleva "$" y conserva los centavos, porque
    al editar no se puede perder precisión.
    """
    signo = "-" if centavos < 0 else ""
    return signo + _pesos_y_centavos(abs(centavos))


def _negativo(que: str) -> str:
    """ "negativa" si el dato es femenino ("La cotización", "La meta"); si no, "negativo".

    El nombre del dato siempre empieza con su artículo, así que alcanza con mirarlo
    (BUG-14). Evita "La cotización no puede ser negativo."
    """
    return "negativa" if que.split()[0] in ("La", "Las") else "negativo"


def leer_monto(texto: str, permitir_cero: bool = False, que: str = "El monto") -> int:
    """Convierte lo que escribió el usuario a centavos: "66.020,12" -> 6602012.

    Lanza ErrorDeValidacion con un mensaje para mostrar si el texto no es válido.
    Por defecto el monto tiene que ser mayor a 0 (RN-05); el sueldo usa
    permitir_cero=True porque puede ser 0. "que" personaliza los mensajes, como en
    validar_centavos: que="La cotización" -> "La cotización tiene que ser mayor a 0."
    """
    limpio = texto.strip().replace(" ", "")
    if not limpio:
        raise ErrorDeValidacion("Ingresá un monto.")
    if limpio.startswith("-"):
        raise ErrorDeValidacion(f"{que} no puede ser {_negativo(que)}.")

    if _PATRON_MONTO.fullmatch(limpio) is None:
        if _PATRON_PUNTO_DECIMAL.fullmatch(limpio):
            raise ErrorDeValidacion("Usá coma para los decimales. Ej.: 66.020,12")
        if _PATRON_MUCHOS_DECIMALES.fullmatch(limpio):
            raise ErrorDeValidacion("Usá como máximo 2 decimales.")
        raise ErrorDeValidacion("Escribí solo números. Ej.: 66.020,12")

    # Se rechaza por largo ANTES de int(): Python se niega a convertir textos de
    # más de 4300 dígitos y tiraría un error técnico. El monto máximo válido
    # ("999.999.999.999,99") tiene 18 caracteres.
    if len(limpio) > _LARGO_MAXIMO_TEXTO:
        raise ErrorDeValidacion(f"{que} es demasiado grande.")

    # partition separa en lo de antes y lo de después de la coma.
    # Si no hay coma, decimales queda vacío.
    parte_entera, _, decimales = limpio.partition(",")
    # ljust completa con ceros a la derecha: "5" -> "50" (o sea, 0,5 = 50 centavos).
    centavos = int(parte_entera.replace(".", "")) * 100 + int(decimales.ljust(2, "0"))

    validar_centavos(centavos, permitir_cero=permitir_cero, que=que)
    return centavos


def validar_centavos(
    monto_cent: int,
    permitir_cero: bool = False,
    que: str = "El monto",
    campo: str | None = None,
) -> None:
    """Controla que un monto ya convertido sea válido para guardar (RN-01, RN-05).

    La lógica la usa aunque la pantalla ya haya pasado por leer_monto, para no
    depender de que quien la llama haya validado. "que" personaliza el mensaje:
    que="El sueldo" -> "El sueldo es demasiado grande." "campo" se copia al error.
    """
    # bool se excluye aparte porque en Python True y False también son int (1 y 0).
    if not isinstance(monto_cent, int) or isinstance(monto_cent, bool):
        raise ErrorDeValidacion(
            f"{que} tiene que ser un número entero de centavos.", campo
        )
    if permitir_cero:
        if monto_cent < 0:
            raise ErrorDeValidacion(f"{que} no puede ser {_negativo(que)}.", campo)
    elif monto_cent <= 0:
        raise ErrorDeValidacion(f"{que} tiene que ser mayor a 0.", campo)
    if monto_cent > MONTO_MAXIMO_CENT:
        raise ErrorDeValidacion(f"{que} es demasiado grande.", campo)


def nombre_mes(anio: int, mes: int) -> str:
    """(2026, 10) -> "Octubre 2026"."""
    # Sin este control, mes 0 daría MESES[-1] = "Diciembre": en Python un índice
    # negativo cuenta desde el final de la lista.
    if not 1 <= mes <= 12:
        raise ValueError(f"Mes inválido: {mes}")
    return f"{MESES[mes - 1]} {anio}"


def clave_orden(texto: str) -> str:
    """Clave para ordenar textos como en un diccionario: sin acentos ni mayúsculas.

    sorted(nombres, key=clave_orden) pone "Árbol" junto a las palabras con A.
    """
    # NFD separa cada letra de su acento ("Á" -> "A" + "´"); después se descartan
    # los acentos (combining) y se pasa a minúsculas con casefold.
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_acentos.casefold()


def formatear_fecha(fecha_iso: str) -> str:
    """ "2026-10-04" -> "04/10/2026".

    Las fechas se guardan en formato ISO (AAAA-MM-DD) porque así se ordenan bien
    como texto; en pantalla se muestran como se usan en Argentina.
    """
    anio, mes, dia = fecha_iso.split("-")
    return f"{dia}/{mes}/{anio}"


def convertir_ars_a_usd(pesos_cent: int, cotizacion_cent: int) -> int:
    """Dólares (en centavos) que equivalen a unos pesos (RN-15, RN-16).

    pesos_cent × 100 ÷ cotizacion_cent, redondeado al centavo, mitad hacia arriba
    (RN-03). Ej.: $ 1.434.617 a $ 1.600 -> 143461700 × 100 / 160000 = 89663,56
    -> 89664 (US$ 896,64). Solo valores positivos (los negativos los maneja quien llama).
    """
    # Redondeo "mitad hacia arriba" con enteros: (2a + b) // (2b) es a/b redondeado.
    numerador = pesos_cent * 100
    return (2 * numerador + cotizacion_cent) // (2 * cotizacion_cent)


def formatear_porcentaje(proporcion: float, decimales: int = 0) -> str:
    """1.0112 -> "101 %"; con decimales=2 -> "101,12 %". Negativos: -0.3221 -> "-32 %".

    Redondea "mitad hacia arriba", como el resto de la app (RN-03): 0.125 -> "13 %".
    round() de Python no sirve acá porque redondea las mitades al par (12,5 -> 12).
    Decimal trabaja con números decimales exactos y permite elegir el redondeo.
    """
    # str() antes de Decimal: así 0.125 se toma como 0,125 y no como el float
    # binario aproximado (0,12499999…), que redondearía mal.
    valor = Decimal(str(proporcion)) * 100
    redondeado = valor.quantize(Decimal(1).scaleb(-decimales), rounding=ROUND_HALF_UP)
    # BUG-13: Decimal guarda el signo también en el cero (-0,001 redondea a "-0").
    # Si el resultado es cero, se usa un cero sin signo, como hace formatear_ars.
    if redondeado == 0:
        redondeado = abs(redondeado)
    return f"{redondeado:.{decimales}f}".replace(".", ",") + " %"
