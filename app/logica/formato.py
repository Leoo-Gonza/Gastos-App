"""Formateo de montos para mostrar y lectura de montos escritos por el usuario.

Internamente todos los montos son enteros en centavos (RN-01). Este módulo es el
único lugar donde se convierten a texto y desde texto.
"""

import re

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
    signo = "-" if centavos < 0 else ""
    return f"{signo}$ {_pesos_y_centavos(abs(centavos))} por US$"


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


def leer_monto(texto: str, permitir_cero: bool = False) -> int:
    """Convierte lo que escribió el usuario a centavos: "66.020,12" -> 6602012.

    Lanza ErrorDeValidacion con un mensaje para mostrar si el texto no es válido.
    Por defecto el monto tiene que ser mayor a 0 (RN-05); el sueldo usa
    permitir_cero=True porque puede ser 0.
    """
    limpio = texto.strip().replace(" ", "")
    if not limpio:
        raise ErrorDeValidacion("Ingresá un monto.")
    if limpio.startswith("-"):
        raise ErrorDeValidacion("El monto no puede ser negativo.")

    if _PATRON_MONTO.fullmatch(limpio) is None:
        if _PATRON_PUNTO_DECIMAL.fullmatch(limpio):
            raise ErrorDeValidacion("Usá coma para los decimales. Ej.: 66.020,12")
        if _PATRON_MUCHOS_DECIMALES.fullmatch(limpio):
            raise ErrorDeValidacion("Usá como máximo 2 decimales.")
        raise ErrorDeValidacion("Monto inválido. Ej.: 66.020,12")

    # Se rechaza por largo ANTES de int(): Python se niega a convertir textos de
    # más de 4300 dígitos y tiraría un error técnico. El monto máximo válido
    # ("999.999.999.999,99") tiene 18 caracteres.
    if len(limpio) > _LARGO_MAXIMO_TEXTO:
        raise ErrorDeValidacion("El monto es demasiado grande.")

    # partition separa en lo de antes y lo de después de la coma.
    # Si no hay coma, decimales queda vacío.
    parte_entera, _, decimales = limpio.partition(",")
    # ljust completa con ceros a la derecha: "5" -> "50" (o sea, 0,5 = 50 centavos).
    centavos = int(parte_entera.replace(".", "")) * 100 + int(decimales.ljust(2, "0"))

    validar_centavos(centavos, permitir_cero=permitir_cero)
    return centavos


def validar_centavos(
    monto_cent: int, permitir_cero: bool = False, que: str = "El monto"
) -> None:
    """Controla que un monto ya convertido sea válido para guardar (RN-01, RN-05).

    La lógica la usa aunque la pantalla ya haya pasado por leer_monto, para no
    depender de que quien la llama haya validado. "que" personaliza el mensaje:
    que="El sueldo" -> "El sueldo es demasiado grande."
    """
    # bool se excluye aparte porque en Python True y False también son int (1 y 0).
    if not isinstance(monto_cent, int) or isinstance(monto_cent, bool):
        raise ErrorDeValidacion(f"{que} tiene que ser un número entero de centavos.")
    if permitir_cero:
        if monto_cent < 0:
            raise ErrorDeValidacion(f"{que} no puede ser negativo.")
    elif monto_cent <= 0:
        raise ErrorDeValidacion(f"{que} tiene que ser mayor a 0.")
    if monto_cent > MONTO_MAXIMO_CENT:
        raise ErrorDeValidacion(f"{que} es demasiado grande.")


def nombre_mes(anio: int, mes: int) -> str:
    """(2026, 10) -> "Octubre 2026"."""
    # Sin este control, mes 0 daría MESES[-1] = "Diciembre": en Python un índice
    # negativo cuenta desde el final de la lista.
    if not 1 <= mes <= 12:
        raise ValueError(f"Mes inválido: {mes}")
    return f"{MESES[mes - 1]} {anio}"
