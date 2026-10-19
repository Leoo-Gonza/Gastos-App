"""Cotización automática (v2): buscar el dólar de hoy en DolarApi (RN-79 a RN-87).

Solo pide, valida y arma los textos. No guarda nada: la cotización buscada se
escribe en el campo del diálogo y el usuario decide si la guarda (RN-84).

Las pruebas nunca se conectan a internet: reemplazan la función pedir() por una
falsa (por ejemplo con monkeypatch).
"""

import asyncio
import json
import math
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from app.logica import configuracion
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import MONTO_MAXIMO_CENT

MENSAJE_ERROR = "No se pudo obtener la cotización. Revisá tu conexión o cargala a mano."
URL_BASE = "https://dolarapi.com/v1/dolares/"
TIEMPO_MAXIMO = 10  # Segundos (RN-86).

# Hora de Argentina: UTC−3 fijo. Argentina no usa horario de verano desde 2009, y
# así no hace falta el paquete tzdata, que zoneinfo pide en Windows (§5.14).
_HORA_ARGENTINA = timezone(timedelta(hours=-3))

# Dólar elegido (valor guardado en la base) -> (casa en DolarApi, nombre en pantalla).
# En la base va un valor propio ("mep") y no el de la fuente ("bolsa"): si la
# fuente cambia sus nombres, lo guardado sigue valiendo (§5.11).
_DOLARES = {
    "blue": ("blue", "blue"),
    "mep": ("bolsa", "MEP"),
    "oficial": ("oficial", "oficial"),
    "cripto": ("cripto", "cripto"),
}


@dataclass
class CotizacionBuscada:
    centavos: int  # ARS por USD, en centavos (RN-83).
    origen: str  # "Dólar blue compra, 18/10/2026 14:05 (DolarApi)" (RN-85).


def _datos(dolar: str) -> tuple[str, str]:
    # Un valor desconocido se toma como Blue (RN-79), igual que en configuracion.
    return _DOLARES.get(dolar, _DOLARES["blue"])


def texto_boton(dolar: str) -> str:
    """ "Buscar dólar blue", "Buscar dólar MEP", etc. (RN-79)."""
    return f"Buscar dólar {_datos(dolar)[1]}"


def url_de(dolar: str) -> str:
    return URL_BASE + _datos(dolar)[0]


def pedir(url: str, tiempo_maximo: float) -> tuple[int, bytes]:
    """Hace el pedido de lectura (GET) y devuelve (estado HTTP, contenido).

    No lleva parámetros ni contenido: no se envía ningún dato del usuario (RN-81).
    """
    pedido = urllib.request.Request(
        url, method="GET", headers={"Accept": "application/json"}
    )
    try:
        with urllib.request.urlopen(pedido, timeout=tiempo_maximo) as respuesta:
            return respuesta.status, respuesta.read()
    except urllib.error.HTTPError as error:
        # urlopen lanza un error con 404, 500, etc.: se devuelve el estado igual,
        # así todos los casos se revisan en un solo lugar (validar_respuesta).
        return error.code, b""


def _a_centavos(compra) -> int | None:
    """Precio de compra -> centavos, redondeando mitad hacia arriba (RN-83).

    None si no es un número válido. bool se descarta aparte porque en Python
    True es un int (True == 1).
    """
    if isinstance(compra, bool) or not isinstance(compra, (int, float)):
        return None
    if not math.isfinite(compra):  # json acepta NaN e Infinity.
        return None
    try:
        # str() da el número como se escribió (1630.555), sin el error de los
        # float (1630.55499...): así el redondeo al centavo es el esperado.
        pesos = Decimal(str(compra)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
    return int(pesos * 100)


def _fecha_argentina(texto) -> str | None:
    """ "2026-10-18T17:05:00.000Z" -> "18/10/2026 14:05" (RN-85). None si no sirve."""
    if not isinstance(texto, str):
        return None
    try:
        fecha = datetime.fromisoformat(texto)
        if fecha.tzinfo is None:
            return None  # Sin huso horario no se sabe de qué hora es (P-2).
        # OverflowError: una fecha extrema (año 1) que al pasar a UTC−3 cae
        # antes del primer día que Python puede representar (BUG-39a).
        argentina = fecha.astimezone(_HORA_ARGENTINA)
    except (ValueError, OverflowError):
        return None
    # strftime descarta los segundos (no los redondea), como pide RN-85.
    return argentina.strftime("%d/%m/%Y %H:%M")


def validar_respuesta(dolar: str, estado: int, contenido: bytes) -> CotizacionBuscada:
    """Revisa la respuesta de DolarApi (RN-82). Si no sirve, ErrorDeValidacion."""
    if estado != 200:
        raise ErrorDeValidacion(MENSAJE_ERROR)
    try:
        datos = json.loads(contenido)
    # ValueError incluye un contenido que no es UTF-8. RecursionError: miles de
    # corchetes anidados ("[[[[...") agotan la pila al leerlos (BUG-39b).
    except (ValueError, RecursionError):
        raise ErrorDeValidacion(MENSAJE_ERROR) from None
    if not isinstance(datos, dict):
        raise ErrorDeValidacion(MENSAJE_ERROR)
    centavos = _a_centavos(datos.get("compra"))
    fecha = _fecha_argentina(datos.get("fechaActualizacion"))
    # centavos < 1: negativa, 0, o algo como 0.004 que redondea a 0 (RN-06).
    # Más que el tope de la app no se podría guardar: también es error (BUG-39c).
    if centavos is None or not 1 <= centavos <= MONTO_MAXIMO_CENT or fecha is None:
        raise ErrorDeValidacion(MENSAJE_ERROR)
    nombre = _datos(dolar)[1]
    return CotizacionBuscada(centavos, f"Dólar {nombre} compra, {fecha} (DolarApi)")


def buscar_cotizacion(
    dolar: str, tiempo_maximo: float = TIEMPO_MAXIMO
) -> CotizacionBuscada:
    """Pide la cotización del dólar elegido y la valida. Tarda: llamarla en otro hilo."""
    try:
        estado, contenido = pedir(url_de(dolar), tiempo_maximo)
    except Exception:  # noqa: BLE001 (sin internet, sin respuesta, DNS...: todo es el mismo error)
        raise ErrorDeValidacion(MENSAJE_ERROR) from None
    return validar_respuesta(dolar, estado, contenido)


async def buscar_con_limite(
    con, tiempo_maximo: float = TIEMPO_MAXIMO
) -> CotizacionBuscada:
    """Busca el dólar elegido en Ajustes sin trabar la ventana, con 10 s como máximo.

    El límite cuenta desde que se llama hasta tener la respuesta completa (RN-86):
    si llega después, se descarta y es un error.
    """
    dolar = configuracion.obtener_dolar(con)
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(buscar_cotizacion, dolar, tiempo_maximo), tiempo_maximo
        )
    except TimeoutError:
        raise ErrorDeValidacion(MENSAJE_ERROR) from None
