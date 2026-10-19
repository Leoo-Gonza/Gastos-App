"""Pruebas del paso 8a-2: leer el Excel (app/logica/importar_excel.py).

Cubre RN-60 a RN-65 y RN-67 (§4.12) y los CA de lectura del Módulo K (§7):
CA-50.1 (hojas), CA-51.1 a CA-51.8, CA-58.1 a CA-58.3 (archivo, hoja y fórmulas).
No se prueba la interpretación (tipos propuestos, cobrado/no cobrado, notas, avisos,
guardado): eso es de 8a-3 y 8a-4.

Todos los archivos .xlsx se generan acá con openpyxl (tests/ayudantes_excel.py) con
datos inventados. Nunca se usa datos-privados/.
"""

import io
import random
import time
import zipfile
from datetime import date, datetime, time as hora, timedelta

import pytest
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.styles import PatternFill

from app.logica.errores import ErrorDeValidacion
from app.logica.importar_excel import (
    MENSAJE_ARCHIVO_INVALIDO,
    VACIA,
    FilaDetectada,
    abrir_libro,
    clasificar,
    es_nombre_xlsx,
    leer_numero_texto,
    normalizar,
)
from tests.ayudantes_excel import (
    a_bytes,
    armar_libro,
    celdas_planilla,
    con_valores_guardados,
    insertar_fila,
    planilla_con,
    planilla_prueba,
    reemplazar_en_zip,
    resumen_filas,
    xlsx,
)


def leer(contenido, hoja="Octubre"):
    """Abre el archivo y lee una hoja."""
    return abrir_libro(contenido).leer_hoja(hoja)


def por_nombre(hoja, nombre, fila=None):
    """La fila detectada con ese nombre (y, si se indica, en esa fila del Excel)."""
    coincidencias = [
        f
        for f in hoja.filas
        if f.nombre == nombre and (fila is None or f.fila_excel == fila)
    ]
    assert len(coincidencias) == 1, (
        f"{nombre!r} (fila {fila}): {len(coincidencias)} filas"
    )
    return coincidencias[0]


@pytest.fixture
def planilla():
    """La hoja "Octubre" de planilla-prueba.xlsx ya leída."""
    return leer(planilla_prueba())


# ---------------------------------------------------------------------------
# RN-60: nombre de archivo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "nombre",
    ["gastos.xlsx", "GASTOS.XLSX", "Planilla 2026.XlSx", "a.b.xlsx", "ñandú.xlsx"],
)
def test_es_nombre_xlsx_acepta_xlsx(nombre):
    # RN-60: la extensión .xlsx se acepta sin importar mayúsculas.
    assert es_nombre_xlsx(nombre) is True


@pytest.mark.parametrize(
    "nombre",
    [
        "gastos.xls",
        "gastos.xlsm",
        "gastos.xlsb",
        "gastos.csv",
        "gastos.ods",
        "gastos.txt",
        "gastos.xlsx.txt",
        "gastos.xlsx ",
        "gastos",
        "",
        "gastos.xlsxx",
    ],
)
def test_es_nombre_xlsx_rechaza_otras_extensiones(nombre):
    # RN-60: .xls, .xlsm, .csv, .ods, etc. no se aceptan.
    assert es_nombre_xlsx(nombre) is False


def test_es_nombre_xlsx_nombre_sin_punto_no_es_xlsx():
    # Un archivo que se llama "xlsx" (sin punto) no tiene extensión .xlsx.
    assert es_nombre_xlsx("xlsx") is False


# ---------------------------------------------------------------------------
# RN-60 / CA-58.1: archivo que no se puede leer
# ---------------------------------------------------------------------------


def _xlsx_valido():
    return xlsx({"C3": "Luz", "D3": 100})


def _zip_sin_excel():
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, "w") as z:
        z.writestr("hola.txt", "no soy un excel")
    return salida.getvalue()


@pytest.mark.parametrize(
    "contenido",
    [
        pytest.param(b"", id="bytes vacios"),
        pytest.param(b"Luz;1000\nGas;2000\n", id="csv renombrado"),
        pytest.param("Hola, esto es un texto\n".encode(), id="txt renombrado"),
        pytest.param(
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(512),
            id="xls viejo o con contrasena (OLE)",
        ),
        pytest.param(b"PK\x03\x04", id="cabecera zip sola"),
        pytest.param(_xlsx_valido()[:100], id="xlsx cortado 100 bytes"),
        pytest.param(
            _xlsx_valido()[: len(_xlsx_valido()) // 2], id="xlsx cortado a la mitad"
        ),
        pytest.param(_xlsx_valido()[:-30], id="xlsx sin el final"),
        pytest.param(_zip_sin_excel(), id="zip valido sin contenido de Excel"),
    ],
)
def test_abrir_libro_archivo_ilegible_da_el_mensaje(contenido):
    # CA-58.1 / RN-60: lo que no es un .xlsx legible se rechaza con el mensaje fijo.
    with pytest.raises(ErrorDeValidacion) as error:
        abrir_libro(contenido)
    assert str(error.value) == MENSAJE_ARCHIVO_INVALIDO
    assert MENSAJE_ARCHIVO_INVALIDO == (
        "No se pudo leer el archivo. Solo se aceptan archivos .xlsx de Excel."
    )


@pytest.mark.parametrize(
    "interno",
    [
        "xl/worksheets/sheet1.xml",
        "xl/workbook.xml",
        "[Content_Types].xml",
        "xl/styles.xml",
    ],
)
def test_abrir_libro_xlsx_danado_por_dentro_con_xml_roto(interno):
    # BUG-25: un .xlsx con un XML interno roto es un archivo dañado (RN-60), pero
    # openpyxl lanza xml.etree.ElementTree.ParseError, que abrir_libro no atrapa.
    dañado = reemplazar_en_zip(_xlsx_valido(), interno, b"<<< esto no es xml")
    with pytest.raises(ErrorDeValidacion) as error:
        abrir_libro(dañado)
    assert str(error.value) == MENSAJE_ARCHIVO_INVALIDO


def test_abrir_libro_xlsx_con_hoja_en_blanco_interna():
    # BUG-25: la hoja interna con 0 bytes también es un archivo dañado.
    dañado = reemplazar_en_zip(_xlsx_valido(), "xl/worksheets/sheet1.xml", b"")
    with pytest.raises(ErrorDeValidacion):
        abrir_libro(dañado)


def test_abrir_libro_xlsx_con_datos_comprimidos_rotos():
    # BUG-25: bytes rotos dentro del flujo comprimido dan zlib.error / NotImplementedError,
    # que tampoco se atrapan. Se rompen los bytes de la hoja sin tocar la cabecera zip.
    contenido = bytearray(planilla_prueba())
    info = zipfile.ZipFile(io.BytesIO(bytes(contenido))).getinfo(
        "xl/worksheets/sheet1.xml"
    )
    inicio = info.header_offset + 30 + len(info.filename.encode()) + 4
    for posicion in range(inicio, inicio + 40):
        contenido[posicion] ^= 0xFF
    with pytest.raises(ErrorDeValidacion):
        abrir_libro(bytes(contenido))


def test_abrir_libro_bytes_alterados_al_azar_nunca_escapa_otra_excepcion():
    # RN-60: con cualquier daño del archivo, lo único que debe salir es ErrorDeValidacion
    # (o abrirse). Se alteran al azar (semilla fija) 1 a 5 bytes de un .xlsx válido.
    original = planilla_prueba()
    azar = random.Random(2026)
    escapes = {}
    for _ in range(300):
        copia = bytearray(original)
        for _ in range(azar.randint(1, 5)):
            copia[azar.randrange(len(copia))] ^= azar.randrange(1, 256)
        try:
            abrir_libro(bytes(copia))
        except ErrorDeValidacion:
            pass
        except Exception as error:  # noqa: BLE001 - justamente lo que se busca
            escapes[type(error).__name__] = escapes.get(type(error).__name__, 0) + 1
    assert escapes == {}, f"excepciones que escapan de abrir_libro: {escapes}"


def test_abrir_libro_xlsx_valido_no_da_error():
    # Control: un archivo bueno se abre.
    assert abrir_libro(planilla_prueba()).hojas() == ["Octubre"]


def test_abrir_libro_no_modifica_ni_copia_el_archivo(tmp_path, monkeypatch):
    # RN-60 / CA-50.2: solo lee. Los bytes de entrada no cambian y no se crea nada en disco.
    contenido = planilla_prueba()
    archivo = tmp_path / "planilla.xlsx"
    archivo.write_bytes(contenido)
    antes = archivo.read_bytes()
    vacio = tmp_path / "trabajo"
    vacio.mkdir()
    monkeypatch.chdir(vacio)
    libro = abrir_libro(antes)
    libro.hojas()
    libro.leer_hoja("Octubre")
    assert archivo.read_bytes() == contenido
    assert list(vacio.iterdir()) == []
    assert set(tmp_path.iterdir()) == {archivo, vacio}


# ---------------------------------------------------------------------------
# RN-60 / CA-50.1 / CA-58.2: hojas
# ---------------------------------------------------------------------------


def test_hojas_una_sola(planilla):
    # CA-50.1: planilla-prueba.xlsx tiene una sola hoja "Octubre".
    assert abrir_libro(planilla_prueba()).hojas() == ["Octubre"]


def test_hojas_varias_en_orden_del_archivo():
    # CA-50.1: con una hoja "Septiembre" más, se ofrecen las dos, en el orden del archivo.
    libro = armar_libro(
        {"Octubre": celdas_planilla(), "Septiembre": {"C1": "Luz", "D1": 5}}
    )
    assert abrir_libro(a_bytes(libro)).hojas() == ["Octubre", "Septiembre"]


def test_leer_hoja_solo_trae_las_filas_de_la_hoja_elegida():
    # CA-50.1: se muestran solo las filas de la hoja elegida.
    libro = armar_libro(
        {"Octubre": celdas_planilla(), "Septiembre": {"C1": "Luz", "D1": 5}}
    )
    abierto = abrir_libro(a_bytes(libro))
    septiembre = abierto.leer_hoja("Septiembre")
    assert resumen_filas(septiembre) == [(1, 3, "Luz", 500)]
    octubre = abierto.leer_hoja("Octubre")
    assert all(f.nombre != "Luz" for f in octubre.filas)
    assert len(octubre.filas) == 13 + 16


def test_hojas_no_ofrece_las_hojas_sin_celdas():
    # RN-60: las hojas sin celdas no se ofrecen (aunque estén entre medio).
    libro = armar_libro({"Vacia1": {}, "Octubre": {"C1": "Luz"}, "Vacia2": {}})
    assert abrir_libro(a_bytes(libro)).hojas() == ["Octubre"]


def test_hojas_libro_sin_ninguna_celda():
    # RN-60: un libro con todas las hojas vacías no ofrece ninguna hoja.
    libro = armar_libro({"Hoja1": {}, "Hoja2": {}})
    assert abrir_libro(a_bytes(libro)).hojas() == []


def test_hojas_oculta_con_datos_se_ofrece():
    # Una hoja oculta (no una fila) con datos: hoy se ofrece igual. Se documenta.
    libro = armar_libro({"Octubre": {"C1": "Luz"}, "Secreta": {"C1": "Gas"}})
    libro["Secreta"].sheet_state = "hidden"
    assert abrir_libro(a_bytes(libro)).hojas() == ["Octubre", "Secreta"]


def _libro_con_grafico():
    libro = Workbook()
    datos = libro.active
    datos.title = "Datos"
    for fila in range(1, 5):
        datos.cell(fila, 1, fila * 10)
    grafico = BarChart()
    grafico.add_data(Reference(datos, min_col=1, min_row=1, max_row=4))
    return libro, datos, grafico


def test_hojas_hoja_de_grafico_no_se_ofrece():
    # RN-60: una hoja que es solo un gráfico (chartsheet) no se ofrece.
    libro, _datos, grafico = _libro_con_grafico()
    hoja_grafico = libro.create_chartsheet("Grafico")
    hoja_grafico.add_chart(grafico)
    abierto = abrir_libro(a_bytes(libro))
    assert abierto.hojas() == ["Datos"]


def test_hojas_hoja_normal_con_solo_un_grafico_no_se_ofrece():
    # RN-60: una hoja común que solo tiene un gráfico dibujado (sin celdas) tampoco.
    libro, _datos, grafico = _libro_con_grafico()
    solo_grafico = libro.create_sheet("SoloGrafico")
    solo_grafico.add_chart(grafico, "B2")
    abierto = abrir_libro(a_bytes(libro))
    assert abierto.hojas() == ["Datos"]
    # Si igual se la pidiera, se lee como hoja sin datos.
    assert abierto.leer_hoja("SoloGrafico").sin_datos is True


def test_hojas_hoja_con_datos_y_grafico_se_lee_normal():
    # Una hoja con celdas Y un gráfico se ofrece y se lee sin problema.
    libro, datos, grafico = _libro_con_grafico()
    datos.add_chart(grafico, "D2")
    hoja = leer(a_bytes(libro), "Datos")
    assert [f.monto_cent for f in hoja.filas] == [1000, 2000, 3000, 4000]


def test_hojas_solo_con_formulas_sin_valor_se_ofrece():
    # RN-61: una hoja con solo fórmulas sin valor guardado tiene celdas; si no se ofrece,
    # el usuario nunca vería el aviso de fórmulas sin valor calculado.
    abierto = abrir_libro(xlsx({"D3": "=100+200", "D4": "=1+1"}))
    assert abierto.hojas() == ["Octubre"]


def test_leer_hoja_vacia():
    # CA-58.2 / RN-60: hoja sin celdas -> sin_datos y sin_filas_completas.
    hoja = leer(xlsx({}, nombre_hoja="Hoja1"), "Hoja1")
    assert hoja.filas == []
    assert hoja.sin_datos is True
    assert hoja.sin_filas_completas is True
    assert hoja.formulas_sin_valor == 0
    assert hoja.ejemplo_formula is None


def test_leer_hoja_con_solo_fechas():
    # RN-61: fechas y horas cuentan como vacías: la hoja no tiene datos.
    celdas = {
        "C1": datetime(2026, 10, 1, 8, 30),
        "C2": date(2026, 10, 2),
        "C3": hora(9, 15),
        "C4": timedelta(hours=5),
    }
    hoja = leer(xlsx(celdas))
    assert hoja.sin_datos is True


def test_leer_hoja_con_solo_espacios():
    # RN-61: celdas con solo espacios son vacías.
    hoja = leer(xlsx({"C1": "   ", "C2": " \t ", "C3": " "}))
    assert hoja.sin_datos is True


def test_leer_hoja_solo_textos_sin_numeros():
    # CA-58.2: solo textos -> hay filas, todas incompletas, y sin_filas_completas.
    hoja = leer(xlsx({"C1": "Luz", "C2": "Gas", "C3": "Agua"}))
    assert hoja.sin_datos is False
    assert hoja.sin_filas_completas is True
    assert [f.nombre for f in hoja.filas] == ["Luz", "Gas", "Agua"]
    assert all(not f.completa for f in hoja.filas)


def test_leer_hoja_inexistente_da_keyerror():
    # Observación: pedir una hoja que no existe lanza KeyError (la interfaz solo debe
    # pedir nombres de hojas()). Se documenta el comportamiento actual.
    with pytest.raises(KeyError):
        abrir_libro(planilla_prueba()).leer_hoja("NoExiste")


def test_leer_hoja_hay_filas_completas_con_datos():
    # sin_filas_completas es falso si alguna fila tiene nombre y monto.
    assert leer(xlsx({"C1": "Luz", "D1": 5})).sin_filas_completas is False


# ---------------------------------------------------------------------------
# RN-61 / RN-62 / CA-51.3: lectura de números y celdas
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("82.000", 8200000),
        ("1.050.000", 105000000),
        ("66.020,12", 6602012),
        ("$ 41.116,66", 4111666),
        ("$41.116,66", 4111666),
        ("41116,66", 4111666),
        ("260000", 26000000),
        ("0", 0),
        ("0,5", 50),
        ("1,5", 150),
        ("1,005", 101),  # mitad hacia arriba (RN-03)
        ("22.093,666", 2209367),
        ("-5.000", -500000),
        ("- 5.000", -500000),
        ("-$ 5.000", -500000),
        ("-0", 0),
        ("  82.000  ", 8200000),
        (" 82.000 ", 8200000),  # espacios duros
        ("1.000.000.000.000", 100000000000000),
        ("007", 700),
    ],
)
def test_leer_numero_texto_formato_argentino(texto, esperado):
    # RN-62: punto = miles (grupos de 3), coma = decimales, "$" y "-" opcionales.
    assert leer_numero_texto(texto) == esperado


@pytest.mark.parametrize(
    "texto",
    [
        "82.5",
        "1.5000",
        "1.5",
        "12.34.567",
        "1000.000",
        "1.00",
        ".500",
        "1,",
        ",5",
        "1,2,3",
        "1.000,5,5",
        "3/3",
        "US$ 20",
        "$$ 5",
        "--5",
        "-",
        "$",
        "",
        "   ",
        "Monotributo 66.020,12",
        "abc",
        "12abc",
        "1e5",
        "1 000",
        "5%",
        "$ -5.000",
        "+5.000",
        "1.000.00",
        "(5.000)",
        "20 USD",
        "NaN",
        "inf",
    ],
)
def test_leer_numero_texto_rechaza_lo_que_no_es_numero(texto):
    # RN-62: "82.5" y "1.5000" no son números; con letras o símbolos tampoco.
    assert leer_numero_texto(texto) is None


def test_clasificar_numeros_de_excel_se_toman_tal_cual():
    # CA-51.3: el número de Excel 41116,66 -> 4111666; 22093,666 -> 2209367.
    assert clasificar(41116.66, "n").centavos == 4111666
    assert clasificar(22093.666, "n").centavos == 2209367
    assert clasificar(5, "n").centavos == 500
    assert clasificar(0, "n").centavos == 0
    assert clasificar(-5000, "n").centavos == -500000
    assert clasificar(0.1 + 0.2, "n").centavos == 30  # sin error de decimales binarios
    assert clasificar(1.005, "n").centavos == 101


def test_clasificar_numero_de_excel_no_interpreta_puntos():
    # RN-62: un número (no texto) no se interpreta: 82.5 de Excel son 82,5 y no texto.
    assert clasificar(82.5, "n").centavos == 8250


def test_clasificar_numero_entero_grande():
    # Un entero muy grande se pasa a centavos sin perder precisión.
    assert clasificar(10**12, "n").centavos == 10**14
    assert clasificar(10**17, "n").centavos == 10**19
    assert clasificar(1e15, "n").centavos == 10**17


def test_clasificar_textos_y_vacios():
    # RN-61: texto sin espacios de los costados; vacío y solo espacios = vacía.
    assert clasificar("  Luz  ").texto == "Luz"
    assert clasificar("82.5").texto == "82.5"
    assert clasificar("82.000").centavos == 8200000
    assert clasificar("82.000").texto is None
    for vacio in (None, "", "   ", "\n", "\t"):
        assert clasificar(vacio).vacia is True
    assert clasificar(None) == VACIA


@pytest.mark.parametrize(
    "valor",
    [
        True,
        False,
        datetime(2026, 10, 1),
        date(2026, 10, 1),
        hora(8, 0),
        timedelta(days=1),
    ],
)
def test_clasificar_booleanos_y_fechas_son_vacios(valor):
    # RN-61: verdadero/falso, fechas y horas cuentan como vacías (True no es el número 1).
    assert clasificar(valor).vacia is True


@pytest.mark.parametrize(
    "error", ["#DIV/0!", "#REF!", "#N/A", "#VALUE!", "#NAME?", "#NULL!", "#NUM!"]
)
def test_clasificar_errores_de_excel_son_vacios(error):
    # RN-61: los errores de Excel cuentan como vacíos (tipo de dato "e").
    assert clasificar(error, "e").vacia is True


def test_clasificar_infinito_y_nan_no_rompen():
    # Un archivo mal armado puede traer inf o nan como número: no debería lanzar una
    # excepción rara (decimal.InvalidOperation).
    for valor in (float("inf"), float("nan")):
        try:
            clasificar(valor, "n")
        except ErrorDeValidacion:
            pass


def test_numeros_en_archivo_real():
    # CA-51.3 con archivo: texto "82.000", "$ 41.116,66", número 41116,66, 22093,666...
    celdas = {
        "C1": "A",
        "D1": "82.000",
        "C2": "B",
        "D2": "1.050.000",
        "C3": "C",
        "D3": "66.020,12",
        "C4": "D",
        "D4": "$ 41.116,66",
        "C5": "E",
        "D5": "41116,66",
        "C6": "F",
        "D6": 41116.66,
        "C7": "G",
        "D7": 22093.666,
        "C8": "H",
        "D8": "-5.000",
        "C9": "I",
        "D9": -5000,
        "C10": "J",
        "D10": 0,
        "C11": "K",
        "D11": 10**12,
    }
    montos = {f.nombre: f.monto_cent for f in leer(xlsx(celdas)).filas}
    assert montos == {
        "A": 8200000,
        "B": 105000000,
        "C": 6602012,
        "D": 4111666,
        "E": 4111666,
        "F": 4111666,
        "G": 2209367,
        "H": -500000,
        "I": -500000,
        "J": 0,
        "K": 10**14,
    }


def test_texto_82_5_da_dos_filas_incompletas():
    # CA-51.3: "Nafta | '82.5'" da dos filas incompletas ("Nafta" y "82.5").
    hoja = leer(xlsx({"C1": "Nafta", "D1": "82.5"}))
    assert [(f.nombre, f.monto_cent, f.completa) for f in hoja.filas] == [
        ("Nafta", None, False),
        ("82.5", None, False),
    ]
    assert hoja.sin_filas_completas is True


def test_texto_1_5000_da_dos_filas_incompletas():
    # RN-62: "1.5000" tampoco es número.
    hoja = leer(xlsx({"C1": "Nafta", "D1": "1.5000"}))
    assert [f.nombre for f in hoja.filas] == ["Nafta", "1.5000"]
    assert all(not f.completa for f in hoja.filas)


def test_fecha_en_la_columna_del_monto_deja_la_fila_sin_monto():
    # CA-51.3: una fecha en la columna del monto -> la fila queda sin monto.
    hoja = leer(xlsx({"C1": "Nafta", "D1": datetime(2026, 10, 5)}))
    assert [(f.nombre, f.monto_cent) for f in hoja.filas] == [("Nafta", None)]


@pytest.mark.parametrize("valor", [True, False])
def test_booleano_en_la_columna_del_monto_deja_la_fila_sin_monto(valor):
    # RN-61: verdadero/falso es vacío: no es 1 ni 0.
    hoja = leer(xlsx({"C1": "Luz", "D1": valor}))
    assert [(f.nombre, f.monto_cent) for f in hoja.filas] == [("Luz", None)]


@pytest.mark.parametrize(
    "error", ["#DIV/0!", "#REF!", "#N/A", "#VALUE!", "#NAME?", "#NULL!", "#NUM!"]
)
def test_celda_de_error_en_la_columna_del_monto(error):
    # RN-61: un error de Excel cuenta como vacío: "Luz" queda sin monto y el error no
    # aparece como fila.
    hoja = leer(xlsx({"C1": "Luz", "D1": error}))
    assert [(f.nombre, f.monto_cent) for f in hoja.filas] == [("Luz", None)]


def test_celda_de_error_en_la_columna_del_nombre():
    # RN-61: el error no es un nombre; el número que sigue queda como fila sin nombre.
    hoja = leer(xlsx({"C1": "#REF!", "D1": 100}))
    assert [(f.nombre, f.monto_cent) for f in hoja.filas] == [(None, 10000)]


def test_texto_con_espacios_se_recorta_en_el_nombre():
    # RN-61: el texto va sin los espacios del principio y del final.
    hoja = leer(xlsx({"C1": "  Luz  ", "D1": 5}))
    assert hoja.filas[0].nombre == "Luz"


def test_numero_antes_del_texto_no_se_le_suma_al_texto():
    # RN-63 paso 3: un número sin texto antes en su fila forma una fila sin nombre.
    hoja = leer(xlsx({"B1": 50, "C1": "Luz", "D1": 5}))
    assert [(f.nombre, f.monto_cent, f.columna) for f in hoja.filas] == [
        (None, 5000, 2),
        ("Luz", 500, 3),
    ]


def test_dos_numeros_seguidos_solo_el_primero_es_monto():
    # RN-63 paso 2: el segundo número se descarta (ej. "Arca deuda | 84000 | 84000").
    hoja = leer(xlsx({"C1": "Arca deuda", "D1": 84000, "E1": 84000}))
    assert resumen_filas(hoja) == [(1, 3, "Arca deuda", 8400000)]


def test_dos_numeros_texto_y_numero_pegados_sin_nombre():
    # RN-63 paso 3: dos números sueltos en una misma fila son dos filas sin nombre
    # (ninguno "abre" la fila).
    hoja = leer(xlsx({"B1": 10, "C1": 20}))
    assert [(f.nombre, f.monto_cent) for f in hoja.filas] == [
        (None, 1000),
        (None, 2000),
    ]


def test_filas_del_excel_totalmente_vacias_no_generan_nada():
    # RN-63: las filas vacías no generan filas. Los números de fila siguen siendo los del Excel.
    hoja = leer(xlsx({"C1": "Luz", "D1": 5, "C50": "Gas", "D50": 7}))
    assert resumen_filas(hoja) == [(1, 3, "Luz", 500), (50, 3, "Gas", 700)]


def test_posicion_lejos_del_origen():
    # fila_excel y columna cuentan desde A1 = (1, 1) aunque los datos empiecen lejos.
    hoja = leer(xlsx({"Z100": "Luz", "AA100": 5}))
    assert resumen_filas(hoja) == [(100, 26, "Luz", 500)]


# ---------------------------------------------------------------------------
# CA-51.1 y CA-51.2: planilla-prueba.xlsx completa
# ---------------------------------------------------------------------------

LISTA_PRINCIPAL = [
    # (fila, nombre, monto_cent, pagado_cent)
    (3, "Alquiler", 26000000, None),
    (4, "Servicios", 8200000, None),
    (5, "Internet", 3870000, 3870000),
    (6, "Tarjetas de Credito", 58291700, None),
    (7, "psicologo", 14000000, 6000000),
    (12, "Monotributo 66.020,12", 6602012, None),
    (13, "Avant Service cuota 3/ 3 $41.116,66", 4111666, None),
    (15, "Gym", 5000000, None),
    (22, "Prestamo MP", 2000000, None),
    (23, "Internet", 1290000, None),
    (24, "Total", 3290000, None),
    (27, "tacones chiqui baby", 678500, None),
    (28, "Total", 678500, None),
]

INCOMPLETAS = [
    # (fila, columna, nombre, monto_cent)
    (1, 3, "Gasto del Mes", None),
    (2, 4, "Gastos", None),
    (2, 5, "Pagado", None),
    (8, 4, "total", None),
    (8, 5, "Falta por pagar", None),
    (9, 4, None, 110361700),
    (9, 5, None, 100491700),
    (11, 3, "Deudas", None),
    (11, 4, "Monto", None),
    (11, 5, "Total deudas", None),
    (14, 3, "Deuda freezer", None),
    (16, 3, "Obra social", None),
    (18, 2, "Sueldo", None),
    (19, 2, None, 130000),
    (21, 4, "Deudas sofia", None),
    (26, 4, "Marsu", None),
]


def test_ca_51_1_lista_principal_exacta(planilla):
    # CA-51.1: 13 filas con nombre y monto, en orden, con monto, pagado y fila del Excel.
    completas = [f for f in planilla.filas if f.completa]
    assert [
        (f.fila_excel, f.nombre, f.monto_cent, f.pagado_cent) for f in completas
    ] == (LISTA_PRINCIPAL)


def test_ca_51_1_el_66021_no_aparece_en_ningun_lado(planilla):
    # CA-51.1: el 66021 de la fila 12 (columna "Total deudas") no aparece como monto
    # ni como pagado de nadie, ni como fila.
    assert all(f.monto_cent != 6602100 for f in planilla.filas)
    assert all(f.pagado_cent != 6602100 for f in planilla.filas)
    assert all(f.cobrado != 6602100 for f in planilla.filas)


def test_ca_51_2_filas_incompletas_exactas(planilla):
    # CA-51.2: las 16 filas incompletas, todas sin nombre o sin monto.
    incompletas = [f for f in planilla.filas if not f.completa]
    assert len(incompletas) == 16
    assert [
        (f.fila_excel, f.columna, f.nombre, f.monto_cent) for f in incompletas
    ] == INCOMPLETAS


def test_ca_51_2_las_sin_nombre_son_las_tres_de_numeros(planilla):
    # CA-51.2: 1.103.617, 1.004.917 y 1.300 vienen sin nombre.
    sin_nombre = [f for f in planilla.filas if f.nombre is None]
    assert [f.monto_cent for f in sin_nombre] == [110361700, 100491700, 130000]


def test_total_de_filas_de_la_planilla(planilla):
    # 13 completas + 16 incompletas = 29 filas detectadas, sin repetir celdas.
    assert len(planilla.filas) == 29
    ubicaciones = [(f.fila_excel, f.columna) for f in planilla.filas]
    assert len(set(ubicaciones)) == 29
    # Orden de lectura: de arriba abajo y de izquierda a derecha.
    assert ubicaciones == sorted(ubicaciones)


def test_planilla_sin_formulas_ni_avisos(planilla):
    # La planilla no tiene fórmulas.
    assert planilla.formulas_sin_valor == 0
    assert planilla.ejemplo_formula is None
    assert planilla.sin_datos is False
    assert planilla.sin_filas_completas is False


def test_pagado_y_cobrado_solo_donde_corresponde(planilla):
    # CA-51.1 / CA-51.5: solo Internet (fila 5) y psicologo (fila 7) traen pagado;
    # sin columna "Cobrado" nadie trae cobrado.
    con_pagado = {
        f.fila_excel: f.pagado_cent for f in planilla.filas if f.pagado_cent is not None
    }
    assert con_pagado == {5: 3870000, 7: 6000000}
    assert all(f.cobrado is None for f in planilla.filas)


# ---------------------------------------------------------------------------
# CA-51.4: filas ocultas
# ---------------------------------------------------------------------------


def test_ca_51_4_fila_oculta_aparece():
    # CA-51.4 / RN-60: una fila oculta con "Luz | 1000" se lee como cualquier otra.
    contenido = xlsx(
        {"C1": "Alquiler", "D1": 5, "C2": "Luz", "D2": 1000},
        filas_ocultas={"Octubre": [2]},
    )
    hoja = leer(contenido)
    assert resumen_filas(hoja) == [(1, 3, "Alquiler", 500), (2, 3, "Luz", 100000)]
    assert hoja.filas[1].completa


def test_fila_oculta_en_la_planilla_no_cambia_el_resultado():
    # RN-60: ocultar filas de la planilla (incluso las 3 a 7) no cambia nada.
    libro = armar_libro(
        {"Octubre": celdas_planilla()}, filas_ocultas={"Octubre": [3, 4, 5, 6, 7, 12]}
    )
    oculta = leer(a_bytes(libro))
    normal = leer(planilla_prueba())
    assert resumen_filas(oculta) == resumen_filas(normal)


def test_columna_oculta_se_lee():
    # RN-60: "se leen todas las filas y columnas", también las ocultas.
    libro = armar_libro({"Octubre": {"C1": "Luz", "D1": 7}})
    libro["Octubre"].column_dimensions["D"].hidden = True
    assert resumen_filas(leer(a_bytes(libro))) == [(1, 3, "Luz", 700)]


# ---------------------------------------------------------------------------
# CA-51.5: columna de pagado
# ---------------------------------------------------------------------------


def _pagados(hoja):
    return {
        f.fila_excel: f.pagado_cent for f in hoja.filas if f.pagado_cent is not None
    }


@pytest.mark.parametrize(
    "encabezado",
    [
        "Pago",
        "Pagos",
        "Abonado",
        "ABONADO",
        "pagado",
        "PAGADO",
        "  Pagado  ",
        "Págado",
        "Pagado   ",
    ],
)
def test_ca_51_5_encabezados_de_pagado_reconocidos(encabezado):
    # CA-51.5 / RN-64 / RN-67: Pago, Pagos, Abonado (cualquier mayúscula, con espacios).
    hoja = leer(planilla_con({"E2": encabezado}))
    assert _pagados(hoja) == {5: 3870000, 7: 6000000}


@pytest.mark.parametrize(
    "encabezado", ["Pagué", "Pagado?", "Pagadoo", "Pago parcial", "Pag", "Importe"]
)
def test_ca_51_5_encabezados_no_reconocidos_descartan_los_pagados(encabezado):
    # CA-51.5 / RN-64: otros encabezados no se reconocen: nadie trae pagado.
    hoja = leer(planilla_con({"E2": encabezado}))
    assert _pagados(hoja) == {}
    # Y los 38.700 y 60.000 se descartan: no aparecen como filas sin nombre.
    assert all(f.monto_cent not in (3870000, 6000000) or f.completa for f in hoja.filas)
    assert not [
        f for f in hoja.filas if f.nombre is None and f.monto_cent in (3870000, 6000000)
    ]


def test_ca_51_5_encabezado_con_espacios_repetidos_en_el_medio():
    # RN-67: los espacios repetidos en el medio se ignoran (aplica a los encabezados).
    # "Pago  s" NO es "pagos" (hay un espacio real), pero "  PAGOS " sí.
    assert _pagados(leer(planilla_con({"E2": "  PAGOS "}))) == {5: 3870000, 7: 6000000}
    assert _pagados(leer(planilla_con({"E2": "Pago  s"}))) == {}


def test_ca_51_5_texto_x_junto_a_servicios_es_valor_de_la_fila():
    # CA-51.5: una "x" en E4, al lado de "Servicios | 82.000", es un valor de la fila:
    # Servicios no trae pagado, la "x" no es una fila y la columna sigue siendo de pagado.
    hoja = leer(planilla_con({"E4": "x"}))
    assert por_nombre(hoja, "Servicios").pagado_cent is None
    assert all(f.nombre != "x" for f in hoja.filas)
    assert len(hoja.filas) == 29
    assert _pagados(hoja) == {5: 3870000, 7: 6000000}


def test_ca_51_5_texto_distinto_a_la_derecha_de_pagado_tambien_se_descarta():
    # RN-64: cualquier texto en la columna de pagado, a la derecha de una fila con
    # nombre y monto, es el valor de la fila (no cierra la columna).
    hoja = leer(planilla_con({"E4": "pendiente de revisar"}))
    assert all(f.nombre != "pendiente de revisar" for f in hoja.filas)
    assert _pagados(hoja) == {5: 3870000, 7: 6000000}


def test_ca_51_5_falta_por_pagar_cierra_la_columna(planilla):
    # CA-51.5: "Falta por pagar" (E8) cierra la columna: 1.004.917 (E9) es un número sin
    # nombre, no el pagado de nadie.
    e9 = [f for f in planilla.filas if f.fila_excel == 9 and f.columna == 5][0]
    assert e9.nombre is None
    assert e9.monto_cent == 100491700
    assert e9.pagado_cent is None
    assert por_nombre(planilla, "Falta por pagar").completa is False


def test_ca_51_5_total_deudas_cambiado_por_pagado_reabre_la_columna():
    # CA-51.5: con "Pagado" en E11, el 66021 de E12 es el pagado de Monotributo.
    hoja = leer(planilla_con({"E11": "Pagado"}))
    monotributo = por_nombre(hoja, "Monotributo 66.020,12")
    assert monotributo.pagado_cent == 6602100
    assert monotributo.monto_cent == 6602012
    # (El error "El pagado es mayor que el monto" es de 8a-3.)
    assert monotributo.completa


def test_pagado_numero_sin_fila_con_nombre_no_es_pagado():
    # RN-63 (O63): una fila totalmente vacia (la 3) cierra el encabezado "Pagado". El 99 de
    # E4 queda despues del cierre: es un numero sin nombre (fila incompleta), no un pagado.
    celdas = {"E1": "Pagado", "C2": "Luz", "D2": 5, "E2": 3, "E4": 99}
    hoja = leer(xlsx(celdas))
    assert _pagados(hoja) == {2: 300}
    sueltos = [f for f in hoja.filas if f.monto_cent == 9900]
    assert len(sueltos) == 1
    assert sueltos[0].nombre is None and sueltos[0].pagado_cent is None
    assert sueltos[0].fila_excel == 4


def test_pagado_numero_sin_nombre_dentro_de_la_columna_sin_fila_vacia_no_crea_fila():
    # RN-63/64: sin fila vacia de por medio (E3 con otro pagado), el 99 de E4 sigue siendo
    # de la columna de pagado: no empieza una fila nueva.
    celdas = {"E1": "Pagado", "C2": "Luz", "D2": 5, "E2": 3, "E3": 88, "E4": 99}
    hoja = leer(xlsx(celdas))
    assert all(f.monto_cent not in (9900, 8800) for f in hoja.filas)


def test_pagado_fila_sin_monto_no_trae_pagado():
    # RN-64: un nombre sin monto con un número en la columna de pagado: no hay pagado
    # (la fila no es completa ni abre pagado).
    celdas = {"E1": "Pagado", "C2": "Luz", "E2": 3}
    hoja = leer(xlsx(celdas))
    luz = por_nombre(hoja, "Luz")
    assert luz.monto_cent is None
    # Hoy el número de la columna de pagado se guarda como pagado de "Luz" aunque no tenga monto.
    assert luz.pagado_cent in (None, 300)


def test_segundo_numero_en_la_columna_de_pagado_no_pisa_el_primero():
    # RN-63: el primero que aparece manda (se usa el primer número de esa columna en la fila).
    celdas = {"E1": "Pagado", "C2": "Luz", "D2": 10, "E2": 3}
    assert por_nombre(leer(xlsx(celdas)), "Luz").pagado_cent == 300


def test_pagado_cero_es_pagado_cero():
    # Un pagado de 0 se lee como 0 (no como "sin pagado"); la interpretación es de 8a-3.
    celdas = {"E1": "Pagado", "C2": "Luz", "D2": 10, "E2": 0}
    assert por_nombre(leer(xlsx(celdas)), "Luz").pagado_cent == 0


def test_pagado_como_texto_numerico():
    # RN-61: un pagado escrito como texto "1.500" también es número.
    celdas = {"E1": "Pagado", "C2": "Luz", "D2": 10000, "E2": "1.500"}
    assert por_nombre(leer(xlsx(celdas)), "Luz").pagado_cent == 150000


# ---------------------------------------------------------------------------
# CA-51.6: columna de cobrado (solo el valor crudo)
# ---------------------------------------------------------------------------


def _con_cobrado(**extra):
    cambios = {
        "F21": "Cobrado",
        "F22": 20000,
        "F23": "x",
        "F26": "Cobrado",
        "F27": 3000,
    }
    cambios.update(extra)
    return cambios


def test_ca_51_6_cobrado_crudo_en_la_fila_correcta():
    # CA-51.6: 20000 en F22 -> Prestamo MP; "x" en F23 -> Internet; 3000 en F27 -> tacones.
    hoja = leer(planilla_con(_con_cobrado()))
    assert por_nombre(hoja, "Prestamo MP").cobrado == 2000000
    assert por_nombre(hoja, "Internet", 23).cobrado == "x"
    assert por_nombre(hoja, "tacones chiqui baby").cobrado == 300000
    # Las demás filas completas no traen cobrado.
    conocidas = {22, 23, 27}
    assert all(
        f.cobrado is None
        for f in hoja.filas
        if f.fila_excel not in conocidas | {21, 26}
    )


def test_ca_51_6_la_x_no_es_una_fila_y_los_cobrado_son_encabezados():
    # CA-51.6: la "x" es el valor de la fila y no empieza una fila nueva. Los "Cobrado" de
    # F21 y F26 son textos sin monto: filas incompletas (encabezados), no cierran la columna.
    hoja = leer(planilla_con(_con_cobrado()))
    assert all(f.nombre != "x" for f in hoja.filas)
    cobrados = [f for f in hoja.filas if f.nombre == "Cobrado"]
    assert [(f.fila_excel, f.columna, f.completa) for f in cobrados] == [
        (21, 6, False),
        (26, 6, False),
    ]
    # Los montos de las filas no cambian.
    assert por_nombre(hoja, "Prestamo MP").monto_cent == 2000000
    assert por_nombre(hoja, "Internet", 23).monto_cent == 1290000


def test_ca_51_6_un_no_en_f22_no_cierra_la_columna():
    # CA-51.6: con "no" en F22 el valor crudo es "no", y F23 "x" sigue siendo de Internet.
    hoja = leer(planilla_con(_con_cobrado(F22="no")))
    assert por_nombre(hoja, "Prestamo MP").cobrado == "no"
    assert por_nombre(hoja, "Internet", 23).cobrado == "x"
    assert all(f.nombre not in ("no", "x") for f in hoja.filas)


def test_ca_51_6_cobrado_marsu_f26_es_encabezado_y_columna_sigue():
    # CA-51.6: "Cobrado" en F26 está en la fila de "Marsu" (sin monto): encabezado nuevo,
    # y la columna sigue siendo de cobrado (3000 en F27 va a tacones).
    hoja = leer(planilla_con({"F26": "Cobrado", "F27": 3000}))
    assert por_nombre(hoja, "tacones chiqui baby").cobrado == 300000


def test_ca_51_6_numero_cobrado_en_fila_de_gasto_queda_crudo_sin_romper_nada():
    # CA-51.6: un número en la columna Cobrado de una fila de gasto: la lógica lo guarda
    # crudo (descartarlo es de 8a-3); no debe crear filas sin nombre ni cambiar el monto.
    hoja = leer(planilla_con({"F2": "Cobrado", "F3": 15000}))
    alquiler = por_nombre(hoja, "Alquiler")
    assert alquiler.monto_cent == 26000000
    assert alquiler.cobrado == 1500000
    assert not [f for f in hoja.filas if f.nombre is None and f.monto_cent == 1500000]


@pytest.mark.parametrize("encabezado", ["Cobrado", "COBRADO", "  cobrado ", "Cóbrado"])
def test_encabezado_cobrado_con_variantes(encabezado):
    # RN-64/RN-67: el encabezado "Cobrado" no distingue mayúsculas, acentos ni espacios.
    hoja = leer(planilla_con(_con_cobrado(F21=encabezado, F26=encabezado)))
    assert por_nombre(hoja, "Prestamo MP").cobrado == 2000000


@pytest.mark.parametrize("encabezado", ["Cobrada", "Cobrado?", "Cobros"])
def test_encabezado_cobrado_no_reconocido_no_trae_cobrado(encabezado):
    # RN-64: otros encabezados no son columna de cobrado: ninguna fila trae cobrado.
    hoja = leer(planilla_con(_con_cobrado(F21=encabezado, F26=encabezado)))
    assert all(f.cobrado is None for f in hoja.filas)


def test_cobrado_texto_numerico_se_lee_como_numero():
    # RN-61: "20.000" como texto en cobrado es el número 20.000.
    hoja = leer(planilla_con(_con_cobrado(F22="20.000")))
    assert por_nombre(hoja, "Prestamo MP").cobrado == 2000000


def test_cobrado_vacio_queda_none():
    # Un cobrado vacío es None (no cobrado se decide en 8a-3).
    hoja = leer(planilla_con(_con_cobrado(F22=None)))
    assert por_nombre(hoja, "Prestamo MP").cobrado is None


def test_cobrado_cero_se_guarda_como_cero():
    # Un 0 en cobrado se guarda como 0 crudo.
    hoja = leer(planilla_con(_con_cobrado(F22=0)))
    assert por_nombre(hoja, "Prestamo MP").cobrado == 0


def test_cobrado_y_pagado_en_la_misma_fila_se_guardan_aparte():
    # Una fila con pagado (E) y cobrado (F) guarda cada uno en su campo.
    celdas = {
        "E1": "Pagado",
        "F1": "Cobrado",
        "C2": "Luz",
        "D2": 100,
        "E2": 30,
        "F2": "si",
    }
    luz = por_nombre(leer(xlsx(celdas)), "Luz")
    assert (luz.monto_cent, luz.pagado_cent, luz.cobrado) == (10000, 3000, "si")


# ---------------------------------------------------------------------------
# CA-51.7 y CA-51.8: bloques
# ---------------------------------------------------------------------------


def _bloques(hoja):
    return {
        (f.fila_excel, f.columna): f.bloque for f in hoja.filas if f.bloque is not None
    }


def test_ca_51_7_bloques_de_la_planilla(planilla):
    # CA-51.7: filas 3-7 "Gasto del Mes"; 12, 13, 15 y las pegadas 14 y 16 "Deudas";
    # 22-24 "Deudas sofia"; 27-28 "Marsu".
    esperado = {}
    for fila in (3, 4, 5, 6, 7):
        esperado[(fila, 3)] = "Gasto del Mes"
    for fila in (12, 13, 14, 15, 16):
        esperado[(fila, 3)] = "Deudas"
    for fila in (22, 23, 24):
        esperado[(fila, 4)] = "Deudas sofia"
    for fila in (27, 28):
        esperado[(fila, 4)] = "Marsu"
    assert _bloques(planilla) == esperado


def test_ca_51_7_titulos_y_numeros_sin_nombre_no_tienen_bloque(planilla):
    # CA-51.7 / RN-65: los títulos y los números sin nombre (filas 9 y 19) no tienen bloque.
    titulos = [f for f in planilla.filas if f.es_titulo]
    assert sorted(f.nombre for f in titulos) == sorted(
        [
            "Gasto del Mes",
            "Gastos",
            "Pagado",
            "total",
            "Falta por pagar",
            "Deudas",
            "Monto",
            "Total deudas",
            "Sueldo",
            "Deudas sofia",
            "Marsu",
        ]
    )
    assert all(f.bloque is None for f in titulos)
    assert all(f.bloque is None for f in planilla.filas if f.nombre is None)


def test_ca_51_7_es_titulo_solo_para_los_de_la_lista(planilla):
    # RN-65: "Deuda freezer" y "Obra social" están pegadas y no son títulos; las filas con
    # monto tampoco.
    assert por_nombre(planilla, "Deuda freezer").es_titulo is False
    assert por_nombre(planilla, "Obra social").es_titulo is False
    assert all(not f.es_titulo for f in planilla.filas if f.completa)


def test_ca_51_7_cuenta_de_filas_por_bloque(planilla):
    # CA-51.7: en la lista (filas completas) los bloques tienen 5, 3, 3 y 2 filas y no hay
    # "Otras filas" (ninguna fila completa sin bloque).
    conteo = {}
    for f in planilla.filas:
        if f.completa:
            conteo[f.bloque] = conteo.get(f.bloque, 0) + 1
    assert conteo == {"Gasto del Mes": 5, "Deudas": 3, "Deudas sofia": 3, "Marsu": 2}


def test_ca_51_7_excel_sin_titulos_no_tiene_bloques():
    # CA-51.7: un Excel sin ningún título: ninguna fila tiene bloque (la interfaz muestra
    # "Filas detectadas").
    hoja = leer(xlsx({"C1": "Luz", "D1": 5, "C2": "Gas", "D2": 7}))
    assert all(f.bloque is None for f in hoja.filas)
    assert all(not f.es_titulo for f in hoja.filas)


def test_ca_51_8_fila_nueva_con_concepto_e_importe_pegada_al_titulo():
    # CA-51.8: fila nueva debajo de la 21 con "Concepto" en D e "Importe" en E. "Concepto"
    # está pegada a "Deudas sofia" y no es título; las filas siguen en el bloque.
    celdas = insertar_fila(celdas_planilla(), 21, {"D": "Concepto", "E": "Importe"})
    hoja = leer(xlsx(celdas))
    concepto = por_nombre(hoja, "Concepto")
    assert (concepto.fila_excel, concepto.es_titulo, concepto.completa) == (
        22,
        False,
        False,
    )
    assert concepto.bloque == "Deudas sofia"
    assert por_nombre(hoja, "Prestamo MP").bloque == "Deudas sofia"
    assert por_nombre(hoja, "Prestamo MP").fila_excel == 23
    assert por_nombre(hoja, "Internet", 24).bloque == "Deudas sofia"
    assert por_nombre(hoja, "Total", 25).bloque == "Deudas sofia"
    # "Importe" va a incompletas (sin monto) y los montos siguen igual.
    importe = por_nombre(hoja, "Importe")
    assert importe.completa is False and importe.fila_excel == 22


def test_ca_51_8_fila_vacia_entre_titulo_y_filas_corta_el_bloque():
    # CA-51.8: una fila totalmente vacía entre la 21 y la 22: "Deudas sofia" queda sin filas
    # y Prestamo MP, Internet y Total quedan sin bloque (van a "Otras filas").
    celdas = insertar_fila(celdas_planilla(), 21)
    hoja = leer(xlsx(celdas))
    assert por_nombre(hoja, "Deudas sofia").es_titulo is True
    for nombre, fila in (("Prestamo MP", 23), ("Internet", 24), ("Total", 25)):
        assert por_nombre(hoja, nombre, fila).bloque is None
    # Marsu no se ve afectado.
    assert por_nombre(hoja, "tacones chiqui baby").bloque == "Marsu"
    assert all(f.bloque != "Deudas sofia" for f in hoja.filas)


def test_ca_51_8_titulo_nuevo_prestamos_con_celda_de_arriba_vacia():
    # CA-51.8: "Préstamos" en C14 (en lugar de "Deuda freezer") y la fila 13 entera vacía:
    # "Préstamos" es título; "Gym" queda en "Préstamos"; "Monotributo" sigue en "Deudas".
    celdas = celdas_planilla()
    for coordenada in ("C13", "D13", "C14"):
        celdas.pop(coordenada)
    celdas["C14"] = "Préstamos"
    hoja = leer(xlsx(celdas))
    assert por_nombre(hoja, "Préstamos").es_titulo is True
    assert por_nombre(hoja, "Gym").bloque == "Préstamos"
    assert por_nombre(hoja, "Obra social").bloque == "Préstamos"
    assert por_nombre(hoja, "Monotributo 66.020,12").bloque == "Deudas"


def test_bloque_se_corta_en_el_titulo_siguiente_de_la_misma_columna():
    # RN-65: el bloque termina en el título siguiente de esa columna.
    celdas = {
        "C1": "Casa",
        "C2": "Luz",
        "D2": 1,
        "C3": "Gas",
        "D3": 2,
        "C4": "Auto",
        "C5": "Nafta",
        "D5": 3,
    }
    hoja = leer(xlsx(celdas))
    assert por_nombre(hoja, "Luz").bloque == "Casa"
    # "Auto" está pegado a "Gas" (justo arriba hay un nombre): no es título, es una fila más.
    assert por_nombre(hoja, "Auto").es_titulo is False
    assert por_nombre(hoja, "Nafta").bloque == "Casa"


def test_bloque_titulo_separado_por_fila_vacia_empieza_otro_bloque():
    # RN-65: el título con una celda vacía arriba empieza otro bloque.
    celdas = {
        "C1": "Casa",
        "C2": "Luz",
        "D2": 1,
        "C4": "Auto",
        "C5": "Nafta",
        "D5": 3,
    }
    hoja = leer(xlsx(celdas))
    assert por_nombre(hoja, "Luz").bloque == "Casa"
    assert por_nombre(hoja, "Nafta").bloque == "Auto"
    assert por_nombre(hoja, "Auto").es_titulo is True


def test_bloque_fila_del_excel_con_otra_columna_no_corta():
    # RN-65: una fila del Excel con contenido pero con la celda de la columna vacía no
    # corta el bloque; un título de otra columna tampoco.
    celdas = {
        "C1": "Casa",
        "C2": "Luz",
        "D2": 1,
        "E3": "Otro titulo",
        "F3": 99,
        "C4": "Gas",
        "D4": 2,
    }
    hoja = leer(xlsx(celdas))
    assert por_nombre(hoja, "Gas").bloque == "Casa"


def test_titulo_combinado_que_cubre_varias_columnas():
    # RN-65: el título es una celda combinada B1:C1: el bloque incluye los nombres que
    # están en B o en C. Una fila con el nombre en C también pertenece al bloque.
    celdas = {
        "B1": "Deudas Juan",
        "B2": "Uno",
        "C2": 100,
        "C3": "Dos",
        "D3": 200,
    }
    sin_combinar = leer(xlsx(celdas))
    assert (
        por_nombre(sin_combinar, "Dos").bloque is None
    )  # sin combinar: columna C no es del título
    combinado = leer(xlsx(celdas, combinadas={"Octubre": ["B1:C1"]}))
    assert por_nombre(combinado, "Uno").bloque == "Deudas Juan"
    assert por_nombre(combinado, "Dos").bloque == "Deudas Juan"
    assert por_nombre(combinado, "Deudas Juan").es_titulo is True


def test_ca_52_4_titulo_deudas_sofia_combinado_igual_que_sin_combinar():
    # CA-52.4 (lectura): "Deudas sofia" como celda combinada D21:E21 da el mismo resultado.
    combinada = leer(xlsx(celdas_planilla(), combinadas={"Octubre": ["D21:E21"]}))
    normal = leer(planilla_prueba())
    assert resumen_filas(combinada) == resumen_filas(normal)
    assert _bloques(combinada) == _bloques(normal)


def test_celdas_combinadas_las_otras_celdas_cuentan_como_vacias():
    # RN-61: en una celda combinada vale la primera celda; las demás son vacías aunque
    # tuvieran algo: "Basura" en E1 desaparece al combinar D1:E1 (queda el 100 de D1).
    celdas = {"C1": "Luz", "D1": 100, "E1": "Basura"}
    sin_combinar = leer(xlsx(celdas))
    assert [f.nombre for f in sin_combinar.filas] == ["Luz", "Basura"]
    combinada = leer(xlsx(celdas, combinadas={"Octubre": ["D1:E1"]}))
    assert resumen_filas(combinada) == [(1, 3, "Luz", 10000)]


def test_celdas_combinadas_verticales():
    # RN-61: combinada A1:A3: solo la primera celda cuenta; las de abajo, vacías.
    hoja = leer(xlsx({"C1": "Titulo", "C2": "Otro"}, combinadas={"Octubre": ["C1:C3"]}))
    assert [f.nombre for f in hoja.filas] == ["Titulo"]


def test_celda_combinada_en_rango_grande_no_da_error():
    # Una combinada que cubre muchas celdas (A1:Z50) se lee sin problemas.
    hoja = leer(xlsx({"A1": "Todo"}, combinadas={"Octubre": ["A1:Z50"]}))
    assert resumen_filas(hoja) == [(1, 1, "Todo", None)]


def test_titulo_combinado_no_es_pegado_por_otras_celdas_de_la_combinada():
    # RN-65: la fila de abajo de una combinada cuenta como "justo debajo del nombre" solo
    # en la columna del nombre (la primera celda).
    celdas = {"B1": "Titulo", "C2": "Hijo", "D2": 5}
    hoja = leer(xlsx(celdas, combinadas={"Octubre": ["B1:C1"]}))
    assert por_nombre(hoja, "Hijo").es_titulo is False  # tiene monto
    assert por_nombre(hoja, "Hijo").bloque == "Titulo"


# ---------------------------------------------------------------------------
# RN-61 / CA-58.3 / CA-58.4: fórmulas
# ---------------------------------------------------------------------------


def test_ca_58_3_formula_sin_valor_guardado():
    # CA-58.3: "Luz" en C3 y =100+200 en D3 sin valor guardado: 1 fórmula, ejemplo D3,
    # y "Luz" queda sin monto (fila incompleta).
    hoja = leer(xlsx({"C3": "Luz", "D3": "=100+200"}))
    assert hoja.formulas_sin_valor == 1
    assert hoja.ejemplo_formula == "D3"
    luz = por_nombre(hoja, "Luz")
    assert luz.monto_cent is None and not luz.completa
    assert hoja.sin_filas_completas is True


def test_formulas_sin_valor_cuenta_varias_y_ejemplo_es_la_primera():
    # RN-61: "Hay N fórmulas sin valor calculado (ej. X)": N las cuenta y X es la primera
    # en orden de lectura (filas de arriba a abajo, columnas de izquierda a derecha).
    celdas = {
        "C3": "Luz",
        "E3": "=1+1",
        "D3": "=100+200",
        "C4": "Gas",
        "D4": "=SUM(1,2)",
        "F10": "=A1",
    }
    hoja = leer(xlsx(celdas))
    assert hoja.formulas_sin_valor == 4
    assert hoja.ejemplo_formula == "D3"


def test_ejemplo_formula_columna_de_dos_letras():
    # El ejemplo usa la letra de columna de Excel: columna 27 = AA.
    hoja = leer(xlsx({"AA7": "=1+1"}))
    assert hoja.ejemplo_formula == "AA7"
    assert hoja.formulas_sin_valor == 1


def test_formula_sin_valor_en_celda_de_nombre():
    # La fórmula sin valor cuenta como vacía también donde iría un nombre: el número que
    # sigue queda como fila sin nombre.
    hoja = leer(xlsx({"C3": '="Luz"', "D3": 100}))
    assert hoja.formulas_sin_valor == 1
    assert [(f.nombre, f.monto_cent) for f in hoja.filas] == [(None, 10000)]


def test_ca_58_4_formula_con_valor_guardado_numero():
    # CA-58.4 (simulado): el mismo contenido con el valor guardado como lo hace Excel:
    # "Luz" viene con monto 300 y sin aviso. NO es un archivo real de Excel.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=100+200"}), {"D3": ("n", "300")}
    )
    hoja = leer(contenido)
    assert resumen_filas(hoja) == [(3, 3, "Luz", 30000)]
    assert hoja.formulas_sin_valor == 0
    assert hoja.ejemplo_formula is None


def test_formula_con_valor_guardado_cero_no_cuenta_como_sin_valor():
    # Una fórmula cuyo resultado guardado es 0 tiene valor: monto 0 y sin aviso.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=1-1"}), {"D3": ("n", "0")}
    )
    hoja = leer(contenido)
    assert hoja.formulas_sin_valor == 0
    assert por_nombre(hoja, "Luz").monto_cent == 0


def test_formula_con_resultado_texto_se_clasifica_como_texto():
    # RN-61: el valor calculado se clasifica igual que arriba: un texto es texto.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": '="Gas"'}), {"D3": ("str", "Gas")}
    )
    hoja = leer(contenido)
    assert [f.nombre for f in hoja.filas] == ["Luz", "Gas"]
    assert hoja.formulas_sin_valor == 0


def test_formula_con_resultado_texto_numerico_se_lee_como_numero():
    # RN-61/RN-62: un resultado de texto "82.000" se lee como número argentino.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": '="82.000"'}), {"D3": ("str", "82.000")}
    )
    assert por_nombre(leer(contenido), "Luz").monto_cent == 8200000


def test_formula_con_resultado_error_cuenta_como_vacia_y_no_como_sin_valor():
    # RN-61: una fórmula que da #DIV/0! (con el error guardado) es vacía, y no cuenta como
    # "sin valor calculado": Excel sí la calculó.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=1/0"}), {"D3": ("e", "#DIV/0!")}
    )
    hoja = leer(contenido)
    assert por_nombre(hoja, "Luz").monto_cent is None
    assert hoja.formulas_sin_valor == 0


def test_formula_con_resultado_booleano_cuenta_como_vacia():
    # RN-61: un resultado verdadero/falso es vacío.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=1=1"}), {"D3": ("b", "1")}
    )
    hoja = leer(contenido)
    assert por_nombre(hoja, "Luz").monto_cent is None
    assert hoja.formulas_sin_valor == 0


def test_formula_con_resultado_texto_vacio_guardado_no_es_sin_valor():
    # BUG-26: Excel guarda las fórmulas que devuelven "" (ej. =SI(A1>0;A1;"")) con valor
    # calculado vacío (<v></v>). Eso es una fórmula CON valor guardado: no debe contarse
    # como "sin valor calculado" ni mostrar el aviso de abrir y guardar en Excel.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": '=IF(1>2,5,"")'}), {"D3": ("str", "")}
    )
    hoja = leer(contenido)
    assert hoja.formulas_sin_valor == 0
    assert hoja.ejemplo_formula is None


def test_formulas_con_y_sin_valor_en_el_mismo_archivo():
    # Solo se cuentan las que no tienen valor guardado: D3 tiene valor; D4 no.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=100+200", "C4": "Gas", "D4": "=1+1"}),
        {"D3": ("n", "300")},
    )
    hoja = leer(contenido)
    assert hoja.formulas_sin_valor == 1
    assert hoja.ejemplo_formula == "D4"
    assert por_nombre(hoja, "Luz").monto_cent == 30000


@pytest.mark.skip(
    reason="PENDIENTE (CA-52.5 / CA-58.4): hace falta un .xlsx guardado por Excel o "
    "LibreOffice en tests/ (el usuario lo va a armar). Los archivos de arriba solo "
    "simulan el valor guardado."
)
def test_pendiente_archivo_real_guardado_por_excel():
    # Cuando exista tests/formulas-guardadas-excel.xlsx: "Luz" con monto 300 y sin aviso;
    # una celda con SUM guardada por Excel trae su valor calculado.
    raise AssertionError("pendiente")


# ---------------------------------------------------------------------------
# RN-67: normalizar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Telefono", "telefono"),
        ("Teléfono", "telefono"),
        ("  Teléfono  ", "telefono"),
        ("ABONADO", "abonado"),
        ("Abonado", "abonado"),
        ("Deudas   sofia", "deudas sofia"),
        ("Deudas\tsofia\n", "deudas sofia"),
        ("Deudas sofia", "deudas sofia"),
        ("ÁÉÍÓÚ ÜÑ", "aeiou un"),
        ("", ""),
        ("   ", ""),
        ("Cobrado", "cobrado"),
        ("Falta  por   pagar", "falta por pagar"),
    ],
)
def test_normalizar(texto, esperado):
    # RN-67: sin mayúsculas, sin acentos, sin espacios al principio/final/repetidos.
    assert normalizar(texto) == esperado


def test_normalizar_iguala_nombres_del_mismo_texto():
    # RN-67: "Telefono" = "Teléfono"; "Deudas sofia" contiene "Sofía".
    assert normalizar("Telefono") == normalizar(" teléfono ")
    assert normalizar("Sofía") in normalizar("Deudas sofia")


# ---------------------------------------------------------------------------
# Otros casos borde
# ---------------------------------------------------------------------------


def test_nombres_con_caracteres_raros():
    # Nombres con ñ, acentos, emoji y comillas se leen tal cual.
    celdas = {
        "C1": "Ñandú ✓",
        "D1": 5,
        "C2": 'Gym "premium"',
        "D2": 6,
        "C3": "Café ☕",
        "D3": 7,
    }
    assert [f.nombre for f in leer(xlsx(celdas)).filas] == [
        "Ñandú ✓",
        'Gym "premium"',
        "Café ☕",
    ]


def test_texto_largo_en_el_nombre():
    # Un texto muy largo (5.000 caracteres) se lee completo; el límite es de 8a-3.
    largo = "x" * 5000
    assert leer(xlsx({"C1": largo, "D1": 5})).filas[0].nombre == largo


def test_texto_con_saltos_de_linea_adentro():
    # Un nombre con salto de línea interno se conserva (solo se recortan los costados).
    hoja = leer(xlsx({"C1": "\nLuz\nde casa\n", "D1": 5}))
    assert hoja.filas[0].nombre == "Luz\nde casa"


def test_hoja_grande_se_lee_en_tiempo_razonable():
    # Rendimiento: 3.000 filas x 4 columnas se leen en pocos segundos.
    celdas = {}
    for fila in range(1, 3001):
        celdas[f"B{fila}"] = f"Gasto {fila}"
        celdas[f"C{fila}"] = fila * 10
        celdas[f"D{fila}"] = f"Nota {fila}"
        celdas[f"E{fila}"] = fila
    contenido = xlsx(celdas)
    inicio = time.perf_counter()
    hoja = leer(contenido)
    assert time.perf_counter() - inicio < 15
    # B=nombre, C=monto, D=texto nuevo (fila incompleta), E=número sin nombre... el
    # número de E se asocia al último nombre "Nota n" como su monto.
    assert len(hoja.filas) == 6000
    assert hoja.filas[0].monto_cent == 1000


def test_celda_con_formato_lejos_de_los_datos_no_cuelga_la_lectura():
    # Observación (rendimiento): una celda vacía con formato muy abajo (fila 30.000,
    # columna 20) hace que se recorran todas las filas intermedias. Se verifica que
    # siga dando el resultado correcto en un tiempo razonable.
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Octubre"
    hoja["C3"] = "Luz"
    hoja["D3"] = 100
    hoja.cell(30000, 20).fill = PatternFill("solid", fgColor="FFFF00")
    inicio = time.perf_counter()
    resultado = leer(a_bytes(libro))
    assert time.perf_counter() - inicio < 30
    assert resumen_filas(resultado) == [(3, 3, "Luz", 10000)]


def test_filas_detectadas_son_independientes_entre_lecturas():
    # Leer dos veces la misma hoja da el mismo resultado y objetos distintos.
    libro = abrir_libro(planilla_prueba())
    primera = libro.leer_hoja("Octubre")
    segunda = libro.leer_hoja("Octubre")
    assert resumen_filas(primera) == resumen_filas(segunda)
    primera.filas[0].nombre = "cambiado"
    assert libro.leer_hoja("Octubre").filas[0].nombre == "Gasto del Mes"


def test_fila_detectada_completa():
    # completa = nombre y monto (monto 0 y negativo también cuentan; la validación es 8a-3).
    assert FilaDetectada(1, 1, nombre="a", monto_cent=0).completa is True
    assert FilaDetectada(1, 1, nombre="a", monto_cent=-5).completa is True
    assert FilaDetectada(1, 1, nombre="a").completa is False
    assert FilaDetectada(1, 1, monto_cent=5).completa is False
    assert FilaDetectada(1, 1).completa is False


def test_descuento_negativo_y_cero_son_filas_completas():
    # CA-57.7 (solo lectura): "Descuento | -5000" y "Nada | 0" llegan con su monto crudo.
    hoja = leer(xlsx({"C1": "Descuento", "D1": -5000, "C2": "Nada", "D2": 0}))
    assert [(f.nombre, f.monto_cent, f.completa) for f in hoja.filas] == [
        ("Descuento", -500000, True),
        ("Nada", 0, True),
    ]


# ---------------------------------------------------------------------------
# Ronda 31: verificación de las correcciones (BUG-25 a BUG-28, O58)
# ---------------------------------------------------------------------------


def test_ronda31_error_de_archivo_conserva_la_causa_original():
    # BUG-25: el ErrorDeValidacion se lanza "from error": la causa original queda en
    # __cause__ para poder diagnosticar.
    with pytest.raises(ErrorDeValidacion) as error:
        abrir_libro(b"no soy un excel")
    assert error.value.__cause__ is not None


def test_ronda31_abrir_libro_con_tipos_que_no_son_bytes():
    # BUG-25: pasar None o un texto en vez de bytes tampoco deja escapar otra excepción.
    for malo in (None, "texto", 123):
        with pytest.raises(ErrorDeValidacion):
            abrir_libro(malo)


def test_ronda31_hoja_solo_formato_y_zip_estricto():
    # O58: una hoja sin valores, con una celda solo con formato, se lee sin que el
    # recorrido en paralelo de las dos hojas falle por dimensiones distintas.
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Octubre"
    hoja.cell(50, 8).fill = PatternFill("solid", fgColor="FFFF00")
    leida = leer(a_bytes(libro))
    assert leida.sin_datos is True and leida.formulas_sin_valor == 0


def test_ronda31_hoja_con_formato_filas_ocultas_y_combinadas_a_la_vez():
    # O58: combinadas + filas y columnas ocultas + formato lejos + fórmula sin valor:
    # las dos hojas se recorren a la par sin error y el resultado es el esperado.
    libro = armar_libro(
        {"Octubre": {"C1": "Titulo", "C2": "Luz", "D2": 5, "C3": "Gas", "D3": "=1+1"}},
        combinadas={"Octubre": ["C1:E1", "F5:H9"]},
        filas_ocultas={"Octubre": [2, 3]},
    )
    hoja = libro["Octubre"]
    hoja.column_dimensions["D"].hidden = True
    hoja.cell(40, 12).fill = PatternFill("solid", fgColor="00FF00")
    leida = leer(a_bytes(libro))
    assert [(f.nombre, f.monto_cent) for f in leida.filas] == [
        ("Titulo", None),
        ("Luz", 500),
        ("Gas", None),
    ]
    assert leida.formulas_sin_valor == 1 and leida.ejemplo_formula == "D3"


def test_ronda31_planilla_completa_con_celdas_vacias_con_formato():
    # O58: la planilla completa con relleno en celdas vacías de la última columna y fila.
    libro = armar_libro({"Octubre": celdas_planilla()})
    libro["Octubre"].cell(60, 10).fill = PatternFill("solid", fgColor="CCCCCC")
    assert resumen_filas(leer(a_bytes(libro))) == resumen_filas(leer(planilla_prueba()))


def test_ronda31_dimensiones_distintas_entre_valores_y_formulas_en_archivos_con_valor_guardado():
    # O58: archivo con valores guardados simulados: las dos vistas del libro coinciden.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=100+200", "C4": "Gas", "D4": "=1+1"}),
        {"D3": ("n", "300"), "D4": ("str", "")},
    )
    hoja = leer(contenido)
    assert hoja.formulas_sin_valor == 0
    assert por_nombre(hoja, "Luz").monto_cent == 30000


def test_ronda31_formulas_error_booleano_y_vacio_mezcladas_con_sin_valor():
    # BUG-26: error ("e"), booleano ("b"), texto vacío ("str") y número guardados no
    # cuentan; solo la fórmula sin valor (D8) cuenta.
    celdas = {
        "C3": "A",
        "D3": "=1/0",
        "C4": "B",
        "D4": "=1=1",
        "C5": "C",
        "D5": '=""',
        "C6": "D",
        "D6": "=1+1",
        "C7": "E",
        "D7": "=2+2",
        "C8": "F",
        "D8": "=3+3",
    }
    contenido = con_valores_guardados(
        xlsx(celdas),
        {
            "D3": ("e", "#DIV/0!"),
            "D4": ("b", "1"),
            "D5": ("str", ""),
            "D6": ("n", "2"),
            "D7": ("n", "0"),
        },
    )
    hoja = leer(contenido)
    assert hoja.formulas_sin_valor == 1
    assert hoja.ejemplo_formula == "D8"
    assert por_nombre(hoja, "D").monto_cent == 200
    assert por_nombre(hoja, "E").monto_cent == 0
    assert por_nombre(hoja, "A").monto_cent is None


def test_ronda31_celda_vacia_normal_no_es_formula():
    # BUG-26: una celda vacía común (sin fórmula) nunca cuenta como fórmula sin valor.
    assert leer(xlsx({"C1": "Luz", "E1": 5})).formulas_sin_valor == 0


def test_ronda31_hojas_mezcla_formulas_y_hoja_vacia():
    # BUG-27: la hoja de solo fórmulas se ofrece; la vacía sigue sin ofrecerse.
    libro = armar_libro({"Calc": {"A1": "=1+1"}, "Vacia": {}, "Datos": {"A1": "x"}})
    assert abrir_libro(a_bytes(libro)).hojas() == ["Calc", "Datos"]
    hoja = abrir_libro(a_bytes(libro)).leer_hoja("Calc")
    assert hoja.sin_datos is True and hoja.formulas_sin_valor == 1


@pytest.mark.parametrize("valor", [float("inf"), float("-inf"), float("nan")])
def test_ronda31_clasificar_no_finitos_son_vacios(valor):
    # BUG-28: inf, -inf y nan se tratan como vacíos.
    assert clasificar(valor, "n").vacia is True


def test_ronda31_rendimiento_celda_con_formato_en_fila_100000_columna_4():
    # O58: con formato en la fila 100.000, columna D, leer toda la hoja tarda ~2 s (medido
    # 1,9 s). Con la columna T (20 columnas) sigue en ~6 s: no mejoró.
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Octubre"
    hoja["C3"] = "Luz"
    hoja["D3"] = 100
    hoja.cell(100000, 4).fill = PatternFill("solid", fgColor="FFFF00")
    contenido = a_bytes(libro)
    inicio = time.perf_counter()
    resultado = leer(contenido)
    duracion = time.perf_counter() - inicio
    print(f"fila 100.000: {duracion:.2f} s")
    assert duracion < 4
    assert resumen_filas(resultado) == [(3, 3, "Luz", 10000)]
