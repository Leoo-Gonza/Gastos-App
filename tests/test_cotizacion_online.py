"""Pruebas de la lógica de la cotización automática (paso 9a, Módulo L: RN-79 a RN-88).

NUNCA se conectan a internet: la función que hace el pedido (cotizacion_online.pedir) se
reemplaza por una falsa con monkeypatch, y la que usa urllib (pedir) se prueba reemplazando
urllib.request.urlopen. Fecha de la computadora y datos inventados.
"""

import asyncio
import json
import time
import urllib.error
import urllib.request

import pytest

from app.logica import configuracion, cotizacion_online
from app.logica.cotizacion_online import (
    MENSAJE_ERROR,
    buscar_con_limite,
    buscar_cotizacion,
    texto_boton,
    url_de,
    validar_respuesta,
)
from app.logica.errores import ErrorDeValidacion

BASE = {
    "compra": 1630.5,
    "venta": 1660,
    "fechaActualizacion": "2026-10-18T17:05:00.000Z",
}


def cuerpo(**cambios):
    """JSON (bytes) de la respuesta base con cambios; un valor _FALTA saca el campo."""
    datos = {**BASE, **cambios}
    datos = {k: v for k, v in datos.items() if v is not _FALTA}
    return json.dumps(datos).encode()


_FALTA = object()


class Fuente:
    """Reemplazo de pedir(): anota los pedidos y responde lo indicado (o tarda o falla)."""

    def __init__(self, contenido=None, estado=200, demora=0.0, error=None):
        self.contenido = cuerpo() if contenido is None else contenido
        self.estado = estado
        self.demora = demora
        self.error = error
        self.pedidos = []

    def __call__(self, url, tiempo_maximo):
        self.pedidos.append((url, tiempo_maximo))
        if self.demora:
            time.sleep(self.demora)
        if self.error:
            raise self.error
        return self.estado, self.contenido


@pytest.fixture
def fuente(monkeypatch):
    f = Fuente()
    monkeypatch.setattr(cotizacion_online, "pedir", f)
    return f


# ---------------------------------------------------------------------------
# Dólar elegido (RN-79, CA-59.1, CA-59.3)
# ---------------------------------------------------------------------------


def test_sin_fila_el_dolar_es_blue(con):
    # CA-59.1: sin la fila dolar_cotizacion se usa Blue.
    assert configuracion.obtener_dolar(con) == "blue"
    assert configuracion.DOLARES == ("blue", "mep", "oficial", "cripto")


@pytest.mark.parametrize("dolar", ["mep", "oficial", "cripto", "blue"])
def test_guardar_y_leer_el_dolar(con, dolar):
    # CA-59.2/59.3: se guarda el valor propio de la app y se lee igual.
    configuracion.guardar_dolar(con, dolar)
    assert configuracion.obtener_dolar(con) == dolar
    fila = con.execute(
        "SELECT valor FROM configuracion WHERE clave = 'dolar_cotizacion'"
    ).fetchone()
    assert fila["valor"] == dolar


@pytest.mark.parametrize("valor", ["xyz", "", "MEP", "bolsa", " mep", "Blue"])
def test_valor_desconocido_en_la_base_se_toma_como_blue(con, valor):
    # CA-59.3: dolar_cotizacion = xyz -> Blue (también mayúsculas y el nombre de la fuente).
    con.execute(
        "INSERT INTO configuracion (clave, valor) VALUES ('dolar_cotizacion', ?)",
        (valor,),
    )
    assert configuracion.obtener_dolar(con) == "blue"
    assert texto_boton(configuracion.obtener_dolar(con)) == "Buscar dólar blue"


@pytest.mark.parametrize("dolar", ["xyz", "", "bolsa", "MEP", None])
def test_guardar_dolar_invalido_se_rechaza_y_no_toca_la_base(con, dolar):
    # Borde: no se puede guardar algo que no sea uno de los cuatro.
    configuracion.guardar_dolar(con, "mep")
    with pytest.raises(ErrorDeValidacion):
        configuracion.guardar_dolar(con, dolar)
    assert configuracion.obtener_dolar(con) == "mep"


def test_guardar_dolar_dos_veces_deja_una_sola_fila(con):
    configuracion.guardar_dolar(con, "mep")
    configuracion.guardar_dolar(con, "cripto")
    filas = con.execute(
        "SELECT valor FROM configuracion WHERE clave = 'dolar_cotizacion'"
    ).fetchall()
    assert [f["valor"] for f in filas] == ["cripto"]


@pytest.mark.parametrize(
    ("dolar", "boton", "casa"),
    [
        ("blue", "Buscar dólar blue", "blue"),
        ("mep", "Buscar dólar MEP", "bolsa"),
        ("oficial", "Buscar dólar oficial", "oficial"),
        ("cripto", "Buscar dólar cripto", "cripto"),
    ],
)
def test_textos_y_direcciones_por_dolar(dolar, boton, casa):
    # CA-59.1/59.2: texto del botón y dirección exacta (MEP -> "bolsa").
    assert texto_boton(dolar) == boton
    assert url_de(dolar) == f"https://dolarapi.com/v1/dolares/{casa}"


def test_dolar_desconocido_en_texto_y_url_es_blue():
    assert texto_boton("xyz") == "Buscar dólar blue"
    assert url_de("xyz") == "https://dolarapi.com/v1/dolares/blue"


# ---------------------------------------------------------------------------
# Validación (RN-82, RN-83, RN-85, RN-87)
# ---------------------------------------------------------------------------


def test_respuesta_base_usa_la_compra_no_la_venta():
    # CA-59.5 / CA-61.1: 1630,50 (163050 centavos), no la venta 1.660.
    r = validar_respuesta("blue", 200, cuerpo())
    assert r.centavos == 163050
    assert r.origen == "Dólar blue compra, 18/10/2026 14:05 (DolarApi)"


@pytest.mark.parametrize(
    ("dolar", "nombre"),
    [("mep", "MEP"), ("oficial", "oficial"), ("cripto", "cripto"), ("blue", "blue")],
)
def test_origen_con_el_nombre_del_dolar(dolar, nombre):
    # CA-59.2: el origen lleva el nombre del dólar elegido.
    assert validar_respuesta(dolar, 200, cuerpo()).origen == (
        f"Dólar {nombre} compra, 18/10/2026 14:05 (DolarApi)"
    )


@pytest.mark.parametrize(
    ("compra", "centavos"),
    [
        (1630, 163000),  # CA-61.4: entera
        (1630.555, 163056),  # CA-61.9: mitad hacia arriba
        (1630.554, 163055),
        (1630.545, 163055),  # 1630.545 -> mitad hacia arriba = 1630.55
        (0.005, 1),  # redondea a 1 centavo: válido
        (0.01, 1),
        (2.675, 268),  # el float 2.675 es 2.67499..: tiene que dar 2,68 (se usa str)
        (1.005, 101),
        (1e3, 100000),
        (123456789.99, 12345678999),
    ],
)
def test_compra_a_centavos(compra, centavos):
    assert validar_respuesta("blue", 200, cuerpo(compra=compra)).centavos == centavos


@pytest.mark.parametrize(
    "compra",
    [
        0,
        -5,
        None,
        "abc",
        "1630.5",
        True,
        False,
        0.004,
        0.0,
        -0.0,
        [],
        {},
        [1630.5],
        -1630.5,
    ],
)
def test_ca_62_3_compra_invalida(compra):
    # CA-62.3: cada una es un error con el mismo mensaje.
    with pytest.raises(ErrorDeValidacion, match="No se pudo obtener la cotización"):
        validar_respuesta("blue", 200, cuerpo(compra=compra))


def test_ca_62_3_sin_el_campo_compra():
    with pytest.raises(ErrorDeValidacion) as e:
        validar_respuesta("blue", 200, cuerpo(compra=_FALTA))
    assert str(e.value) == MENSAJE_ERROR


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_compra_no_finita_es_error(literal):
    # Borde: json acepta NaN e Infinity (y 1e999 da inf).
    texto = (
        '{"compra": ' + literal + ', "fechaActualizacion": "2026-10-18T17:05:00Z"}'
    ).encode()
    with pytest.raises(ErrorDeValidacion):
        validar_respuesta("blue", 200, texto)


@pytest.mark.parametrize(
    "contenido",
    [
        b"<html>Error</html>",  # CA-62.3: no es JSON
        b"[]",  # no es un objeto
        b"",
        b"   ",
        b"null",
        b"1630.5",
        b'"texto"',
        b"true",
        b"{",
        b"\xff\xfe\x00no es utf8",
        b'[{"compra": 1630.5, "fechaActualizacion": "2026-10-18T17:05:00Z"}]',
    ],
)
def test_contenido_que_no_es_un_objeto_json(contenido):
    with pytest.raises(ErrorDeValidacion) as e:
        validar_respuesta("blue", 200, contenido)
    assert str(e.value) == MENSAJE_ERROR


@pytest.mark.parametrize(
    "estado", [500, 404, 201, 204, 301, 302, 403, 429, 503, 0, 199, 400]
)
def test_ca_62_3_estado_distinto_de_200(estado):
    # CA-62.3: solo 200 sirve, aunque el contenido sea perfecto.
    with pytest.raises(ErrorDeValidacion):
        validar_respuesta("blue", estado, cuerpo())


@pytest.mark.parametrize(
    "fecha",
    [
        _FALTA,  # CA-62.4
        "ayer",
        "2026-10-18T14:05:00",  # sin huso horario
        "",
        None,
        20261018,
        "2026-10-18",
        "2026-13-45T10:00:00Z",
        "2026-02-30T10:00:00Z",
        "18/10/2026 14:05",
        "2026-10-18T25:00:00Z",
        True,
        [],
    ],
)
def test_ca_62_4_fecha_no_valida(fecha):
    with pytest.raises(ErrorDeValidacion) as e:
        validar_respuesta("blue", 200, cuerpo(fechaActualizacion=fecha))
    assert str(e.value) == MENSAJE_ERROR


@pytest.mark.parametrize(
    ("fecha", "esperado"),
    [
        ("2026-10-18T02:30:00Z", "17/10/2026 23:30"),  # CA-61.6: cambia el día
        ("2026-10-18T14:05:00-03:00", "18/10/2026 14:05"),
        (
            "2026-10-18T17:05:59Z",
            "18/10/2026 14:05",
        ),  # segundos descartados, no redondeados
        ("2026-10-18T17:05:59.999Z", "18/10/2026 14:05"),
        ("2026-10-18T17:05:00.000Z", "18/10/2026 14:05"),
        ("2026-10-18T17:05:00+00:00", "18/10/2026 14:05"),
        ("2026-10-18T20:05:00+03:00", "18/10/2026 14:05"),  # otro huso
        ("2026-10-19T00:00:00Z", "18/10/2026 21:00"),
        ("2026-10-18T03:00:00Z", "18/10/2026 00:00"),  # medianoche exacta en Argentina
        ("2026-10-18T02:59:59Z", "17/10/2026 23:59"),
        ("2026-01-01T00:00:00Z", "31/12/2025 21:00"),  # cruza el año
        (
            "2026-03-01T01:00:00Z",
            "28/02/2026 22:00",
        ),  # cruza el mes (2026 no es bisiesto)
        ("2024-03-01T01:00:00Z", "29/02/2024 22:00"),  # año bisiesto
        ("2026-10-18T00:05:00Z", "17/10/2026 21:05"),
        ("2026-07-15T12:00:00Z", "15/07/2026 09:00"),  # invierno: igual UTC-3 fijo
        ("2026-12-15T12:00:00Z", "15/12/2026 09:00"),
    ],
)
def test_hora_de_argentina(fecha, esperado):
    # CA-61.6 / RN-85: UTC-3 fijo, DD/MM/AAAA HH:MM con ceros.
    r = validar_respuesta("blue", 200, cuerpo(fechaActualizacion=fecha))
    assert r.origen == f"Dólar blue compra, {esperado} (DolarApi)"


def test_la_hora_de_la_computadora_no_influye(monkeypatch):
    # CA-61.6: se muestra la hora de la fuente aunque la computadora diga otra cosa.
    import time as modulo_time

    monkeypatch.setattr(
        modulo_time, "time", lambda: 1_792_353_600.0
    )  # 2026-10-18 20:00 UTC
    r = validar_respuesta("blue", 200, cuerpo())
    assert "18/10/2026 14:05" in r.origen


@pytest.mark.parametrize("venta", [_FALTA, "abc", None, -4, [], True])
def test_ca_62_5_la_venta_no_se_usa(venta):
    # CA-62.5: sin venta, o con una venta rara, igual es válida.
    r = validar_respuesta("blue", 200, cuerpo(venta=venta))
    assert r.centavos == 163050


def test_campos_extra_y_casa_distinta_no_importan():
    datos = json.dumps(
        {**BASE, "casa": "otra", "nombre": 5, "moneda": None, "extra": [1, 2]}
    ).encode()
    assert validar_respuesta("mep", 200, datos).centavos == 163050


def test_contenido_con_bom_utf8_se_acepta():
    # Borde: algunos servidores mandan BOM.
    r = validar_respuesta("blue", 200, b"\xef\xbb\xbf" + cuerpo())
    assert r.centavos == 163050


# --- Bordes de validación que los CA no listan -------------------------------


def test_fecha_extrema_no_rompe_con_un_error_tecnico():
    # Borde: una fecha en el año 1 no se puede pasar a UTC-3. Tiene que ser el mismo error
    # de siempre y no un OverflowError que el diálogo trataría como "error inesperado".
    with pytest.raises(ErrorDeValidacion):
        validar_respuesta(
            "blue", 200, cuerpo(fechaActualizacion="0001-01-01T00:00:00Z")
        )


def test_json_muy_anidado_no_rompe_con_un_error_tecnico():
    # Borde: "[[[[..." hace que json.loads lance RecursionError (no es ValueError).
    with pytest.raises(ErrorDeValidacion):
        validar_respuesta("blue", 200, b"[" * 100_000)


@pytest.mark.parametrize("compra", [1e13, 1e20, 10**30])
def test_compra_enorme_no_deberia_completar_el_campo(compra):
    # Borde: una cotización mayor al máximo de la app (999.999.999.999,99) no se podría
    # guardar: tendría que ser un error y no completar el campo con un valor inválido.
    with pytest.raises(ErrorDeValidacion):
        validar_respuesta("blue", 200, cuerpo(compra=compra))


# ---------------------------------------------------------------------------
# buscar_cotizacion (RN-87) y buscar_con_limite (RN-86)
# ---------------------------------------------------------------------------


def test_buscar_cotizacion_hace_un_pedido_a_la_direccion_del_dolar(fuente):
    # CA-59.1 / CA-62.7 (lógica): un pedido, a la URL del dólar, con el tiempo máximo.
    r = buscar_cotizacion("mep")
    assert fuente.pedidos == [("https://dolarapi.com/v1/dolares/bolsa", 10)]
    assert r.centavos == 163050


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.URLError("sin internet"),
        TimeoutError(),
        OSError("DNS"),
        ConnectionResetError(),
        RuntimeError("cualquier cosa"),
        ValueError("x"),
    ],
)
def test_ca_62_1_cualquier_falla_del_pedido_es_el_mismo_error(monkeypatch, error):
    # CA-62.1: sin conexión, DNS, cortes: mismo mensaje, sin detalles técnicos.
    monkeypatch.setattr(cotizacion_online, "pedir", Fuente(error=error))
    with pytest.raises(ErrorDeValidacion) as e:
        buscar_cotizacion("blue")
    assert str(e.value) == MENSAJE_ERROR
    assert e.value.__cause__ is None


def test_mensaje_de_error_exacto():
    assert (
        MENSAJE_ERROR
        == "No se pudo obtener la cotización. Revisá tu conexión o cargala a mano."
    )


def test_buscar_con_limite_usa_el_dolar_de_ajustes(con, monkeypatch):
    # CA-59.2: con MEP elegido el pedido va a "bolsa" y el origen dice MEP.
    f = Fuente()
    monkeypatch.setattr(cotizacion_online, "pedir", f)
    configuracion.guardar_dolar(con, "mep")
    r = asyncio.run(buscar_con_limite(con))
    assert [u for u, _ in f.pedidos] == ["https://dolarapi.com/v1/dolares/bolsa"]
    assert r.origen.startswith("Dólar MEP compra")


def test_buscar_con_limite_sin_eleccion_usa_blue(con, fuente):
    asyncio.run(buscar_con_limite(con))
    assert fuente.pedidos[0][0] == "https://dolarapi.com/v1/dolares/blue"


def test_el_limite_por_defecto_es_10_segundos(con, fuente):
    # RN-86: 10 s, y ese mismo valor llega al pedido (timeout de la conexión).
    assert cotizacion_online.TIEMPO_MAXIMO == 10
    asyncio.run(buscar_con_limite(con))
    assert fuente.pedidos[0][1] == 10


def test_ca_62_2_sin_respuesta_a_tiempo_es_error_y_no_espera_a_la_fuente(
    con, monkeypatch
):
    # CA-62.2 (escala 0,2 s en vez de 10 s): la fuente tarda 1 s; el error llega al
    # vencer el límite, sin esperar la respuesta tardía.
    monkeypatch.setattr(cotizacion_online, "pedir", Fuente(demora=1.0))

    async def probar():
        inicio = time.monotonic()
        with pytest.raises(ErrorDeValidacion) as e:
            await buscar_con_limite(con, tiempo_maximo=0.2)
        return time.monotonic() - inicio, str(e.value)

    # asyncio.run espera al hilo al cerrar, pero el tiempo se mide adentro.
    demora, mensaje = asyncio.run(probar())
    assert mensaje == MENSAJE_ERROR
    assert 0.15 <= demora < 0.7


def test_ca_62_2_respuesta_tardia_valida_se_descarta(con, monkeypatch):
    # CA-62.2: una respuesta base que llega después del límite NO se usa.
    monkeypatch.setattr(cotizacion_online, "pedir", Fuente(demora=0.5))
    with pytest.raises(ErrorDeValidacion):
        asyncio.run(buscar_con_limite(con, tiempo_maximo=0.1))


def test_respuesta_justo_dentro_del_limite_se_acepta(con, monkeypatch):
    monkeypatch.setattr(cotizacion_online, "pedir", Fuente(demora=0.1))
    r = asyncio.run(buscar_con_limite(con, tiempo_maximo=2))
    assert r.centavos == 163050


def test_buscar_con_limite_no_traba_el_bucle(con, monkeypatch):
    # El pedido corre en otro hilo: mientras espera, el bucle sigue atendiendo tareas.
    monkeypatch.setattr(cotizacion_online, "pedir", Fuente(demora=0.4))

    async def probar():
        latidos = 0

        async def latir():
            nonlocal latidos
            while True:
                await asyncio.sleep(0.02)
                latidos += 1

        tarea = asyncio.create_task(latir())
        await buscar_con_limite(con, tiempo_maximo=2)
        tarea.cancel()
        return latidos

    assert asyncio.run(probar()) >= 8


def test_error_de_validacion_de_la_respuesta_sale_tal_cual(con, monkeypatch):
    monkeypatch.setattr(cotizacion_online, "pedir", Fuente(contenido=cuerpo(compra=0)))
    with pytest.raises(ErrorDeValidacion) as e:
        asyncio.run(buscar_con_limite(con))
    assert str(e.value) == MENSAJE_ERROR


# ---------------------------------------------------------------------------
# El pedido real, sin red: se reemplaza urllib.request.urlopen (CA-62.7, RN-81)
# ---------------------------------------------------------------------------


class RespuestaFalsa:
    def __init__(self, status=200, contenido=b"{}"):
        self.status = status
        self._contenido = contenido

    def read(self):
        return self._contenido

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def urlopen_falso(monkeypatch):
    llamadas = []
    comportamiento = {"respuesta": RespuestaFalsa(200, b'{"ok": 1}'), "error": None}

    def urlopen(pedido, *args, **kwargs):
        llamadas.append((pedido, args, kwargs))
        if comportamiento["error"]:
            raise comportamiento["error"]
        return comportamiento["respuesta"]

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    return llamadas, comportamiento


def test_ca_62_7_el_pedido_es_un_get_sin_parametros_ni_contenido(urlopen_falso):
    llamadas, _ = urlopen_falso
    estado, contenido = cotizacion_online.pedir(url_de("blue"), 10)
    assert (estado, contenido) == (200, b'{"ok": 1}')
    assert len(llamadas) == 1
    pedido, args, kwargs = llamadas[0]
    assert pedido.full_url == "https://dolarapi.com/v1/dolares/blue"
    assert pedido.get_method() == "GET"
    assert pedido.data is None
    assert "?" not in pedido.full_url and "#" not in pedido.full_url
    assert kwargs.get("timeout") == 10
    # Solo se pide JSON: ningún encabezado con datos del usuario.
    assert {k.lower() for k in pedido.headers} <= {"accept"}


def test_ca_62_7_el_pedido_no_depende_de_la_base(con, urlopen_falso, mes_id):
    # CA-62.7: con gastos, sueldo y personas cargados el pedido es exactamente el mismo.
    from app.logica import catalogos, gastos

    llamadas, _ = urlopen_falso
    antes = None
    asyncio.run(_buscar_y_ignorar(con))
    antes = [
        (p.full_url, p.get_method(), p.data, dict(p.headers)) for p, _, _ in llamadas
    ]
    otros = con.execute("SELECT id FROM categorias LIMIT 1").fetchone()["id"]
    gastos.agregar_gasto(con, mes_id, "Alquiler inventado", otros, 260000, "fijo")
    catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    llamadas.clear()
    asyncio.run(_buscar_y_ignorar(con))
    despues = [
        (p.full_url, p.get_method(), p.data, dict(p.headers)) for p, _, _ in llamadas
    ]
    assert len(antes) == len(despues) == 1
    assert antes == despues


async def _buscar_y_ignorar(con):
    try:
        await buscar_con_limite(con, tiempo_maximo=2)
    except ErrorDeValidacion:
        pass  # La respuesta falsa no es válida: acá solo importa el pedido.


@pytest.mark.parametrize("codigo", [404, 500, 503])
def test_http_error_se_devuelve_como_estado(urlopen_falso, codigo):
    # urlopen lanza HTTPError con 404/500: pedir() lo devuelve como (código, b"").
    _, comp = urlopen_falso
    comp["error"] = urllib.error.HTTPError("https://x", codigo, "m", {}, None)
    assert cotizacion_online.pedir(url_de("blue"), 10) == (codigo, b"")


def test_url_error_sale_de_pedir_y_buscar_cotizacion_lo_convierte(urlopen_falso):
    _, comp = urlopen_falso
    comp["error"] = urllib.error.URLError("sin internet")
    with pytest.raises(urllib.error.URLError):
        cotizacion_online.pedir(url_de("blue"), 10)
    with pytest.raises(ErrorDeValidacion) as e:
        buscar_cotizacion("blue")
    assert str(e.value) == MENSAJE_ERROR


def test_timeout_de_socket_se_convierte_en_error(urlopen_falso):
    _, comp = urlopen_falso
    comp["error"] = TimeoutError("timed out")
    with pytest.raises(ErrorDeValidacion):
        buscar_cotizacion("blue")


def test_flujo_completo_sin_red(urlopen_falso):
    # De punta a punta con urlopen falso: respuesta base -> 163050 y origen.
    _, comp = urlopen_falso
    comp["respuesta"] = RespuestaFalsa(200, cuerpo())
    r = buscar_cotizacion("oficial")
    assert (r.centavos, r.origen) == (
        163050,
        "Dólar oficial compra, 18/10/2026 14:05 (DolarApi)",
    )


def test_el_modulo_no_se_conecta_al_importarlo_ni_al_leer_textos(monkeypatch):
    # RN-88 (nivel lógica): texto_boton/url_de/obtener_dolar no hacen ningún pedido.
    def prohibido(*a, **k):
        raise AssertionError("se intentó conectar a internet")

    monkeypatch.setattr(urllib.request, "urlopen", prohibido)
    monkeypatch.setattr(cotizacion_online, "pedir", prohibido)
    texto_boton("blue")
    url_de("mep")


def test_borde_exacto_del_tope_de_la_cotizacion():
    # RN-05: MONTO_MAXIMO_CENT se acepta; un centavo más se rechaza (BUG-39c corregido).
    from app.logica.formato import MONTO_MAXIMO_CENT

    justo = f'{{"compra": {MONTO_MAXIMO_CENT // 100}.{MONTO_MAXIMO_CENT % 100:02d}, "fechaActualizacion": "2026-10-18T17:05:00Z"}}'.encode()
    assert validar_respuesta("blue", 200, justo).centavos == MONTO_MAXIMO_CENT
    pasado = f'{{"compra": {MONTO_MAXIMO_CENT // 100}.{MONTO_MAXIMO_CENT % 100 + 1:02d}, "fechaActualizacion": "2026-10-18T17:05:00Z"}}'.encode()
    with pytest.raises(ErrorDeValidacion):
        validar_respuesta("blue", 200, pasado)
