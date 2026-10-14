"""Pruebas del paso 8a-3: la lista de revisión (app/logica/revision_importacion.py).

Cubre RN-66 a RN-75 y RN-78 (§4.12) y los CA del Módulo K de este paso: CA-51.6 (cobrado),
CA-52.x (tipos, tildes, bloques), CA-53.x (edición), CA-54.x (categoría por defecto),
CA-55.x (mes destino), CA-56.x (ya existe, repetida, gasto compartido), el estado del pie y
los errores de CA-57.5 a CA-57.8. También el cambio de importar_excel.py (monto_es_suma,
Celda.es_suma) y la lectura recortada de leer_hoja (O58).

Quedan fuera (son de pantallas o de 8a-4): resumen previo, guardado, resultado y cancelar.

Base de prueba (principio de los CA del Módulo K): hoy = 2026-10-14, existe solo 2026-10 con
sueldo 1.200, cotización 1.600 y el gasto fijo "Alquiler" 260.000 (Vivienda); personas Sofía
y Marsu; categorías de fábrica más "Varios". Los .xlsx se arman con tests/ayudantes_excel.py
con datos inventados (nunca de datos-privados/).
"""

import time
from datetime import date
from types import SimpleNamespace

import pytest
from openpyxl.styles import PatternFill

from app.logica import catalogos, cuotas, gastos, me_deben, meses
from app.logica.errores import ErrorDeValidacion
from app.logica.importar_excel import VACIA, abrir_libro, clasificar
from app.logica.revision_importacion import (
    Bloque,
    FilaRevision,
    ListaRevision,
    Nueva,
    coinciden,
)
from tests.ayudantes import insertar_mes
from tests.ayudantes_excel import (
    a_bytes,
    armar_libro,
    celdas_planilla,
    con_valores_guardados,
    insertar_fila,
    planilla_con,
    planilla_prueba,
    resumen_filas,
    xlsx,
)

HOY = date(2026, 10, 14)

TIPOS = ["fijo", "unico", "cuota", "me_deben", "sueldo", "ignorar"]


# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


@pytest.fixture
def base(con, mes_id):
    """La base del Módulo K: 2026-10 con Alquiler (Vivienda), Sofía, Marsu y Varios."""
    ids = {c["nombre"]: c["id"] for c in catalogos.listar(con, catalogos.CATEGORIAS)}
    varios = catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    gastos.agregar_gasto(con, mes_id, "Alquiler", ids["Vivienda"], 26000000, "fijo")
    return SimpleNamespace(
        con=con,
        mes_id=mes_id,
        varios=varios,
        vivienda=ids["Vivienda"],
        servicios=ids["Servicios"],
        salud=ids["Salud"],
        sofia=sofia,
        marsu=marsu,
    )


@pytest.fixture
def base_sin_varios(con, mes_id):
    """Igual que base, pero sin la categoría "Varios" (CA-54.3)."""
    ids = {c["nombre"]: c["id"] for c in catalogos.listar(con, catalogos.CATEGORIAS)}
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    gastos.agregar_gasto(con, mes_id, "Alquiler", ids["Vivienda"], 26000000, "fijo")
    return SimpleNamespace(
        con=con, mes_id=mes_id, vivienda=ids["Vivienda"], servicios=ids["Servicios"],
        sofia=sofia, marsu=marsu,
    )


def revisar(con, contenido=None, hoja="Octubre", hoy=HOY):
    """Lee una hoja y arma la lista de revisión. Sin contenido: planilla-prueba.xlsx."""
    leida = abrir_libro(contenido or planilla_prueba()).leer_hoja(hoja)
    return ListaRevision(con, leida, hoy=hoy)


def fila(lista, nombre, fila_excel=None):
    """La fila de la lista con ese nombre (y, si se indica, en esa fila del Excel)."""
    hallazgos = [
        f
        for f in lista.filas
        if f.nombre == nombre and (fila_excel is None or f.origen.fila_excel == fila_excel)
    ]
    assert len(hallazgos) == 1, f"{nombre!r} (fila {fila_excel}): {len(hallazgos)} filas"
    return hallazgos[0]


def sin_nombre(lista, fila_excel):
    """La fila sin nombre (número suelto) de esa fila del Excel."""
    hallazgos = [
        f for f in lista.filas if f.nombre is None and f.origen.fila_excel == fila_excel
    ]
    assert hallazgos, f"no hay número suelto en la fila {fila_excel}"
    return hallazgos[0]


def foto_de_la_base(con):
    """Todo el contenido de todas las tablas, para comprobar que no se escribió nada."""
    tablas = [
        r["name"]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    ]
    return {t: [tuple(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY 1")] for t in tablas}


def cargar_primera_importacion(b):
    """Deja en la base lo que dejaría importar planilla-prueba.xlsx una vez (CA-56.4)."""
    for nombre, monto in [
        ("Servicios", 8200000),
        ("Internet", 3870000),
        ("psicologo", 14000000),
        ("Monotributo 66.020,12", 6602012),
        ("Gym", 5000000),
    ]:
        gastos.agregar_gasto(b.con, b.mes_id, nombre, b.varios, monto, "fijo")
    cuotas.crear_plan(
        b.con, "Avant Service cuota 3/ 3 $41.116,66", b.varios, None, 4111666, 3, 2026, 8,
        hoy=HOY,
    )
    for persona, descripcion, monto in [
        (b.sofia, "Prestamo MP", 2000000),
        (b.sofia, "Internet", 1290000),
        (b.marsu, "tacones chiqui baby", 678500),
    ]:
        me_deben.agregar_item(b.con, persona, descripcion, monto, HOY)


# ---------------------------------------------------------------------------
# Estado inicial: la lista esperada (CA-51.1, CA-52.1, CA-52.7, CA-56.1, RN-63, RN-66)
# ---------------------------------------------------------------------------

# (fila Excel, nombre, monto_cent, pagado_cent, tipo, bloque)
LISTA_ESPERADA = [
    (3, "Alquiler", 26000000, None, "fijo", "Gasto del Mes"),
    (4, "Servicios", 8200000, None, "fijo", "Gasto del Mes"),
    (5, "Internet", 3870000, 3870000, "fijo", "Gasto del Mes"),
    (6, "Tarjetas de Credito", 58291700, None, "ignorar", "Gasto del Mes"),
    (7, "psicologo", 14000000, 6000000, "fijo", "Gasto del Mes"),
    (12, "Monotributo 66.020,12", 6602012, None, "fijo", "Deudas"),
    (13, "Avant Service cuota 3/ 3 $41.116,66", 4111666, None, "cuota", "Deudas"),
    (15, "Gym", 5000000, None, "fijo", "Deudas"),
    (22, "Prestamo MP", 2000000, None, "me_deben", "Deudas sofia"),
    (23, "Internet", 1290000, None, "me_deben", "Deudas sofia"),
    (24, "Total", 3290000, None, "ignorar", "Deudas sofia"),
    (27, "tacones chiqui baby", 678500, None, "me_deben", "Marsu"),
    (28, "Total", 678500, None, "ignorar", "Marsu"),
]


def test_la_lista_principal_tiene_las_13_filas_esperadas_en_orden(base):
    # CA-51.1 + CA-52.1: 13 filas con su fila de Excel, monto, pagado, tipo y bloque.
    lista = revisar(base.con)
    principales = [f for f in lista.filas if not f.incompleta]
    obtenido = [
        (f.origen.fila_excel, f.nombre, f.monto_cent, f.pagado_cent, f.tipo, f.bloque)
        for f in principales
    ]
    assert obtenido == LISTA_ESPERADA


def test_hay_29_filas_en_total_y_16_incompletas_todas_en_ignorar(base):
    # CA-51.2: el grupo "Filas incompletas" tiene 16 filas y todas son "ignorar".
    lista = revisar(base.con)
    assert len(lista.filas) == 29
    incompletas = lista.incompletas()
    assert len(incompletas) == 16
    assert {f.tipo for f in incompletas} == {"ignorar"}
    assert not any(f.tildada for f in incompletas)


def test_las_incompletas_dicen_falta_el_monto_o_falta_el_nombre(base):
    # CA-51.2: con nombre -> "Falta el monto. Se ignora."; sin nombre -> "Falta el nombre. Se ignora."
    lista = revisar(base.con)
    for f in lista.incompletas():
        esperado = "Falta el nombre. Se ignora." if f.nombre is None else "Falta el monto. Se ignora."
        assert lista.notas(f) == [esperado], f.nombre


def test_bloques_en_el_orden_del_excel_con_sus_conteos(base):
    # CA-51.7: Gasto del Mes (5), Deudas (3), Deudas sofia (3), Marsu (2); sin "Otras filas".
    lista = revisar(base.con)
    assert [(b.titulo, len(b.filas)) for b in lista.bloques()] == [
        ("Gasto del Mes", 5),
        ("Deudas", 3),
        ("Deudas sofia", 3),
        ("Marsu", 2),
    ]
    assert all(isinstance(b, Bloque) for b in lista.bloques())


def test_las_incompletas_pegadas_no_estan_dentro_del_bloque(base):
    # RN-65: "Deuda freezer" y "Obra social" son del bloque "Deudas" para la lógica,
    # pero se muestran en "Filas incompletas", no en bloques().
    lista = revisar(base.con)
    assert fila(lista, "Deuda freezer").bloque == "Deudas"
    assert fila(lista, "Obra social").bloque == "Deudas"
    en_bloques = [f.nombre for b in lista.bloques() for f in b.filas]
    assert "Deuda freezer" not in en_bloques and "Obra social" not in en_bloques


def test_excel_sin_titulos_tiene_un_solo_bloque_filas_detectadas(base):
    # CA-51.7: sin ningún título -> un solo bloque "Filas detectadas".
    lista = revisar(base.con, xlsx({"C3": "Luz", "D3": 1000, "C4": "Gas", "D4": 2000}))
    assert [(b.titulo, len(b.filas)) for b in lista.bloques()] == [("Filas detectadas", 2)]


def test_filas_sin_titulo_van_a_otras_filas_cuando_hay_otros_bloques(base):
    # CA-51.8: con una fila vacía entre "Deudas sofia" y "Prestamo MP", "Deudas sofia"
    # queda sin filas (no se muestra) y esas filas van a "Otras filas" como gasto fijo.
    celdas = insertar_fila(celdas_planilla(), 21)
    lista = revisar(base.con, xlsx(celdas))
    titulos = [b.titulo for b in lista.bloques()]
    assert titulos == ["Gasto del Mes", "Deudas", "Otras filas", "Marsu"]
    otras = {f.nombre: f for f in lista.bloques()[2].filas}
    assert set(otras) == {"Prestamo MP", "Internet", "Total"}
    assert otras["Prestamo MP"].tipo == "fijo"
    assert otras["Internet"].tipo == "fijo"
    assert otras["Total"].tipo == "ignorar"


def test_fila_pegada_al_titulo_no_cambia_la_persona_de_sofia(base):
    # CA-51.8: "Concepto | Importe" pegada a "Deudas sofia" va a incompletas y las
    # filas siguen "me deben" Sofía.
    celdas = insertar_fila(celdas_planilla(), 21, {"D": "Concepto", "E": "Importe"})
    lista = revisar(base.con, xlsx(celdas))
    for nombre in ("Prestamo MP", "Internet"):
        f = [x for x in lista.filas if x.nombre == nombre and x.bloque == "Deudas sofia"][0]
        assert (f.tipo, f.persona) == ("me_deben", base.sofia)
    assert fila(lista, "Concepto").incompleta and fila(lista, "Importe").incompleta


def test_titulo_preestablecido_gasto_del_mes_no_tiene_aviso_ni_marca_en_servicios(base):
    # CA-52.1/CA-56.1: lo único marcado en la base es Alquiler (ya existe).
    lista = revisar(base.con)
    marcadas = [f.nombre for f in lista.filas if f.ya_existe]
    assert marcadas == ["Alquiler"]
    assert not any(f.repetida for f in lista.filas)
    assert [f.nombre for f in lista.filas if f.aviso_compartido] == ["Internet"]


def test_tipos_propuestos_de_la_planilla_con_persona_y_cuota(base):
    # CA-52.1: "me deben" Sofía y Marsu; la cuota es 3 de 3.
    lista = revisar(base.con)
    assert (fila(lista, "Prestamo MP").tipo, fila(lista, "Prestamo MP").persona) == ("me_deben", base.sofia)
    assert fila(lista, "Internet", 23).persona == base.sofia
    assert fila(lista, "tacones chiqui baby").persona == base.marsu
    avant = fila(lista, "Avant Service cuota 3/ 3 $41.116,66")
    assert (avant.tipo, avant.cuota_actual, avant.cuota_total) == ("cuota", 3, 3)


def test_nota_de_la_cuota_importada(base):
    # CA-52.1 / RN-71: texto exacto de la nota del plan.
    lista = revisar(base.con)
    avant = fila(lista, "Avant Service cuota 3/ 3 $41.116,66")
    assert lista.notas(avant) == [
        "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. "
        "Se agrega la cuota 3/3 en Octubre 2026."
    ]


def test_estado_inicial_de_los_tildes(base):
    # CA-52.7, RN-74: tildadas las que se importan, salvo "ya existe"; "ignorar" sin tilde.
    lista = revisar(base.con)
    for f in lista.filas:
        if f.tipo == "ignorar" or f.ya_existe:
            assert f.tildada is False, f.nombre
        else:
            assert f.tildada is True, f.nombre


@pytest.mark.parametrize(
    "nombre,monto,tipo,actual,total",
    [
        ("Cumple 15/10", 5000, "fijo", None, None),  # n > N parece fecha (CA-52.2)
        ("Préstamo 0/5", 5000, "fijo", None, None),  # n = 0 (CA-52.2)
        ("Heladera 2/12", 30000, "cuota", 2, 12),
        ("Pago 12/12", 1000, "cuota", 12, 12),
        ("Pago 1/1", 1000, "cuota", 1, 1),
        ("Pago 13/12", 1000, "fijo", None, None),
        ("Heladera 3 / 6", 1000, "cuota", 3, 6),  # con espacios
        ("Heladera 03/12", 1000, "cuota", 3, 12),  # con ceros
        ("Pago 1/ 2/3", 1000, "cuota", 1, 2),
    ],
)
def test_cuota_en_el_nombre_n_sobre_N(base, nombre, monto, tipo, actual, total):
    # RN-66 regla 3 y CA-52.2: cuota solo si 1 <= n <= N.
    lista = revisar(base.con, xlsx({"C3": nombre, "D3": monto}))
    f = lista.filas[0]
    assert (f.tipo, f.cuota_actual, f.cuota_total) == (tipo, actual, total)


@pytest.mark.parametrize(
    "nombre",
    [
        "Total",
        "total",
        "TOTAL",
        "Total de servicios C/U",
        "Total deudas",
        "Gastos fijos sin deuda",
        "capacidad de endeudamiento",
        "Gastos en dólares",
        "GASTOS EN DOLARES",
        "Falta por pagar",
        "Tarjetas de Crédito",
        "  tarjetas   de credito ",
    ],
)
def test_nombres_que_se_proponen_como_ignorar(base, nombre):
    # RN-66 regla 1: la palabra "total" o los nombres fijos (sin mayúsculas ni acentos).
    lista = revisar(base.con, xlsx({"C3": nombre, "D3": 1000}))
    assert lista.filas[0].tipo == "ignorar"
    assert lista.filas[0].tildada is False


@pytest.mark.parametrize(
    "nombre", ["Subtotal", "Totales", "Tarjetas de Credito Visa", "Gastos fijos", "Falta pagar"]
)
def test_nombres_parecidos_pero_no_iguales_no_se_ignoran(base, nombre):
    # RN-66: "total" es una palabra entera y los nombres fijos tienen que ser iguales.
    lista = revisar(base.con, xlsx({"C3": nombre, "D3": 1000}))
    assert lista.filas[0].tipo == "fijo"


@pytest.mark.parametrize("monto", [0, -5000, -0.01])
def test_monto_cero_o_negativo_se_propone_ignorar_con_nota(base, monto):
    # RN-66/RN-68, CA-57.7: nota exacta de monto no válido.
    lista = revisar(base.con, xlsx({"C3": "Nada", "D3": monto}))
    f = lista.filas[0]
    assert f.tipo == "ignorar" and f.tildada is False
    assert lista.notas(f) == ["Monto no válido. Si querés importarla, corregí el monto."]


def test_descuento_y_nada_pasados_a_fijo_muestran_el_error_de_monto(base):
    # CA-57.7: sin corregir el monto -> "El monto tiene que ser mayor a 0." y no se confirma.
    lista = revisar(base.con, xlsx({"C1": "Descuento", "D1": -5000, "C2": "Nada", "D2": 0}))
    for f in list(lista.filas):
        lista.cambiar_tipo(f.indice, "fijo")
        assert lista.errores(f) == ["El monto tiene que ser mayor a 0."]
    assert lista.puede_confirmar() is False
    # Ya no es "ignorar": la nota de monto no válido desaparece (queda el error).
    assert lista.notas(lista.filas[0]) == []


def test_monto_es_suma_se_ignora_aunque_el_nombre_sea_comun(base):
    # CA-52.5 / RN-66: el monto sale de un SUM (valor guardado 120.000) -> "ignorar".
    contenido = con_valores_guardados(
        xlsx({"C3": "Suma servicios", "D3": "=SUM(D1:D2)", "D1": 50000, "D2": 70000}),
        {"D3": ("n", "120000")},
    )
    lista = revisar(base.con, contenido)
    f = fila(lista, "Suma servicios")
    assert f.monto_cent == 12000000
    assert f.origen.monto_es_suma is True
    assert (f.tipo, f.tildada) == ("ignorar", False)


def test_formula_que_no_es_suma_no_se_ignora(base):
    # RN-66 solo habla de SUM: "=100+200" con valor guardado 300 es un gasto fijo.
    contenido = con_valores_guardados(
        xlsx({"C3": "Luz", "D3": "=100+200"}), {"D3": ("n", "300")}
    )
    f = revisar(base.con, contenido).filas[0]
    assert f.origen.monto_es_suma is False
    assert (f.monto_cent, f.tipo) == (30000, "fijo")


def test_suma_dentro_de_otra_formula_y_en_minusculas(base):
    # Excel guarda SUM(...) dentro de otras cuentas; se detecta sin importar mayúsculas.
    contenido = con_valores_guardados(
        xlsx({"C3": "Mix", "D3": "=10+sum(D1:D2)"}), {"D3": ("n", "130")}
    )
    assert revisar(base.con, contenido).filas[0].tipo == "ignorar"


def test_sum_sin_valor_guardado_no_marca_la_celda_vacia_compartida(base):
    # Un SUM sin valor guardado deja la celda vacía y no ensucia la constante VACIA.
    hoja = abrir_libro(xlsx({"C3": "Luz", "D3": "=SUM(D1:D2)", "D1": 1, "D2": 2})).leer_hoja("Octubre")
    assert hoja.formulas_sin_valor == 1
    assert VACIA.es_suma is False
    luz = [f for f in hoja.filas if f.nombre == "Luz"][0]
    assert luz.monto_cent is None and luz.monto_es_suma is False


def test_celda_es_suma_en_clasificar_por_defecto_falso():
    # Celda.es_suma arranca en False para cualquier valor común.
    for valor in (5, "Luz", "82.000", None):
        assert clasificar(valor).es_suma is False


def test_tipo_de_una_fila_de_me_deben_con_titulo_de_dos_personas(base):
    # CA-52.3: "Sofía y Marsu" -> "me deben" sin persona.
    lista = revisar(base.con, planilla_con({"D21": "Sofía y Marsu"}))
    for n, fx in (("Prestamo MP", 22), ("Internet", 23)):
        f = fila(lista, n, fx)
        assert (f.tipo, f.persona) == ("me_deben", None)
        assert lista.errores(f) == ["Elegí una persona."]


def test_titulo_con_persona_inexistente_deja_las_filas_como_gasto_fijo(base):
    # CA-52.3: "Deudas Juan" (no existe) -> gasto fijo.
    lista = revisar(base.con, planilla_con({"D21": "Deudas Juan"}))
    assert fila(lista, "Prestamo MP").tipo == "fijo"
    assert fila(lista, "Internet", 23).tipo == "fijo"


def test_persona_archivada_no_propone_me_deben(base):
    # CA-52.3: con Marsu archivada, "tacones chiqui baby" viene como gasto fijo.
    base.con.execute("UPDATE personas SET archivado = 1 WHERE id = ?", (base.marsu,))
    lista = revisar(base.con)
    assert fila(lista, "tacones chiqui baby").tipo == "fijo"
    assert fila(lista, "Prestamo MP").tipo == "me_deben"


def test_titulo_con_nombre_de_persona_dentro_de_otra_palabra_no_cuenta(base):
    # RN-65: el nombre tiene que ser una palabra entera ("Marsupiales" no es "Marsu").
    lista = revisar(base.con, planilla_con({"D26": "Marsupiales"}))
    assert fila(lista, "tacones chiqui baby").tipo == "fijo"


def test_titulo_combinado_da_el_mismo_resultado_que_sin_combinar(base):
    # CA-52.4: "Deudas sofia" como celda combinada D21:E21.
    libro = armar_libro({"Octubre": celdas_planilla()}, combinadas={"Octubre": ["D21:E21"]})
    lista = revisar(base.con, a_bytes(libro))
    sin = revisar(base.con)
    tipos = lambda l: [(f.nombre, f.tipo, f.persona, f.tildada) for f in l.filas]  # noqa: E731
    assert tipos(lista) == tipos(sin)


# ---------------------------------------------------------------------------
# Cobrado (CA-51.6, RN-64)
# ---------------------------------------------------------------------------

COBRADO = {"F21": "Cobrado", "F22": 20000, "F23": "x", "F26": "Cobrado", "F27": 3000}

NOTA_3000 = (
    'En la columna Cobrado dice "3.000"; los ítems \'me deben\' no tienen cobro parcial, '
    "quedó como no cobrado."
)


def test_cobrado_numero_igual_al_monto_y_texto_x(base):
    # CA-51.6: 20000 (= monto) y "x" -> cobrados; 3000 (distinto) -> no cobrado con nota.
    lista = revisar(base.con, planilla_con(COBRADO))
    prestamo, internet = fila(lista, "Prestamo MP"), fila(lista, "Internet", 23)
    tacones = fila(lista, "tacones chiqui baby")
    assert prestamo.cobrado is True and prestamo.nota_cobrado is None
    assert internet.cobrado is True and internet.nota_cobrado is None
    assert tacones.cobrado is False
    assert NOTA_3000 in lista.notas(tacones)
    assert NOTA_3000 not in lista.notas(prestamo)


def test_sin_columna_cobrado_ninguna_fila_viene_cobrada(base):
    # RN-64: vacío -> no cobrado, sin nota.
    lista = revisar(base.con)
    for f in lista.filas:
        assert f.cobrado is False and f.nota_cobrado is None


def test_cobrado_no_en_prestamo_viene_con_nota_y_internet_sigue_cobrado(base):
    # CA-51.6: un "no" en F22 es un valor de la fila (no cierra la columna).
    lista = revisar(base.con, planilla_con({**COBRADO, "F22": "no"}))
    prestamo, internet = fila(lista, "Prestamo MP"), fila(lista, "Internet", 23)
    assert prestamo.cobrado is False
    assert (
        'En la columna Cobrado dice "no"; los ítems \'me deben\' no tienen cobro parcial, '
        "quedó como no cobrado."
    ) in lista.notas(prestamo)
    assert internet.cobrado is True


@pytest.mark.parametrize("texto", ["x", "X", " x ", "sí", "Sí", "SI", "si", "✓", "ok", "OK", "Cobrado", "COBRADO"])
def test_textos_que_significan_cobrado(base, texto):
    # RN-64 / RN-67: sin mayúsculas ni acentos ni espacios de más.
    lista = revisar(base.con, planilla_con({"F21": "Cobrado", "F22": texto}))
    assert fila(lista, "Prestamo MP").cobrado is True


@pytest.mark.parametrize("texto", ["no", "No", "falta", "pendiente", "x x", "sí, casi"])
def test_textos_que_no_significan_cobrado_dejan_la_nota_con_el_texto_tal_cual(base, texto):
    # RN-64: cualquier otro texto -> no cobrado y nota con el valor de la celda.
    lista = revisar(base.con, planilla_con({"F21": "Cobrado", "F22": texto}))
    f = fila(lista, "Prestamo MP")
    assert f.cobrado is False
    assert (
        f'En la columna Cobrado dice "{texto}"; los ítems \'me deben\' no tienen cobro '
        "parcial, quedó como no cobrado."
    ) in lista.notas(f)


def test_cobrado_cero_no_cobrado_y_sin_nota(base):
    # RN-64: vacío o 0 -> no cobrado, sin nota.
    lista = revisar(base.con, planilla_con({"F21": "Cobrado", "F22": 0}))
    f = fila(lista, "Prestamo MP")
    assert f.cobrado is False and f.nota_cobrado is None
    assert lista.notas(f) == []


@pytest.mark.parametrize(
    "numero,mostrado", [(3000, "3.000"), (19999.99, "20.000"), (1500000, "1.500.000"), (-500, "-500")]
)
def test_cobrado_numero_distinto_se_muestra_con_el_formato_de_montos(base, numero, mostrado):
    # RN-64: V con el formato de RN-04 si es un número.
    lista = revisar(base.con, planilla_con({"F21": "Cobrado", "F22": numero}))
    nota = fila(lista, "Prestamo MP").nota_cobrado
    assert nota == (
        f'En la columna Cobrado dice "{mostrado}"; los ítems \'me deben\' no tienen cobro '
        "parcial, quedó como no cobrado."
    )


def test_cobrado_que_coincide_con_el_monto_con_decimales(base):
    # El número del Excel 12900,00 contra el monto 12.900: cobrado.
    lista = revisar(base.con, planilla_con({"F21": "Cobrado", "F23": 12900.0}))
    assert fila(lista, "Internet", 23).cobrado is True


def test_encabezado_cobrado_en_fila_sin_monto_no_cierra_la_columna(base):
    # CA-51.6: "Cobrado" en F26 (fila de "Marsu", sin monto) es un encabezado nuevo.
    lista = revisar(base.con, planilla_con(COBRADO))
    assert fila(lista, "Cobrado", 26).incompleta is True
    assert fila(lista, "tacones chiqui baby").origen.cobrado == 300000


def test_numero_en_columna_cobrado_de_una_fila_de_gasto_se_descarta(base):
    # CA-51.6: en un gasto, el valor de "Cobrado" se descarta (no hay nota visible).
    lista = revisar(base.con, planilla_con({"F2": "Cobrado", "F4": 82000, "F5": 777}))
    servicios, internet = fila(lista, "Servicios"), fila(lista, "Internet", 5)
    assert lista.notas(servicios) == [] and lista.notas(internet) == []
    assert servicios.tipo == "fijo" and internet.tipo == "fijo"


def test_cambiar_cobrado_destilda_el_cobrado_y_quita_la_nota(base):
    # CA-51.6: el usuario destilda "cobrado" en "Prestamo MP".
    lista = revisar(base.con, planilla_con(COBRADO))
    prestamo = fila(lista, "Prestamo MP")
    lista.cambiar_cobrado(prestamo.indice, False)
    assert prestamo.cobrado is False
    tacones = fila(lista, "tacones chiqui baby")
    lista.cambiar_cobrado(tacones.indice, True)
    assert tacones.cobrado is True and tacones.nota_cobrado is None
    assert NOTA_3000 not in lista.notas(tacones)


def test_cobrado_no_cambia_el_tipo_ni_el_tilde(base):
    # RN-72: cobrado es solo un dato del ítem.
    lista = revisar(base.con, planilla_con(COBRADO))
    prestamo = fila(lista, "Prestamo MP")
    lista.cambiar_cobrado(prestamo.indice, False)
    assert (prestamo.tipo, prestamo.tildada) == ("me_deben", True)


def test_editar_fila_con_cobrado_explicito_cambia_cobrado_y_quita_la_nota(base):
    # RF-53: el diálogo puede cambiar "cobrado".
    lista = revisar(base.con, planilla_con(COBRADO))
    tacones = fila(lista, "tacones chiqui baby")
    errores = lista.editar_fila(
        tacones.indice, "me_deben", "tacones chiqui baby", 678500, persona=base.marsu, cobrado=True
    )
    assert errores == {}
    assert tacones.cobrado is True and tacones.nota_cobrado is None


def test_editar_fila_sin_tocar_cobrado_conserva_la_nota(base):
    # Si el diálogo no cambia "cobrado", la nota sigue.
    lista = revisar(base.con, planilla_con(COBRADO))
    tacones = fila(lista, "tacones chiqui baby")
    lista.editar_fila(
        tacones.indice, "me_deben", "tacones 2", 678500, persona=base.marsu, cobrado=None
    )
    assert NOTA_3000 in lista.notas(tacones)


def test_la_nota_de_cobrado_solo_se_ve_en_filas_me_deben(base):
    # RN-64: la nota es de los ítems "me deben"; si la fila pasa a otro tipo, no se muestra.
    lista = revisar(base.con, planilla_con(COBRADO))
    tacones = fila(lista, "tacones chiqui baby")
    lista.cambiar_tipo(tacones.indice, "fijo")
    assert NOTA_3000 not in lista.notas(tacones)


# ---------------------------------------------------------------------------
# Tildes (RN-68, RN-74, CA-52.6, CA-52.7)
# ---------------------------------------------------------------------------


def test_tarjetas_no_se_puede_tildar_en_ignorar(base):
    # CA-52.7: "Tarjetas de Credito" viene sin tilde y no se puede tildar.
    lista = revisar(base.con)
    tarjetas = fila(lista, "Tarjetas de Credito")
    assert tarjetas.tildada is False
    with pytest.raises(ErrorDeValidacion):
        lista.cambiar_tilde(tarjetas.indice, True)
    assert tarjetas.tildada is False


def test_ignorar_a_gasto_fijo_se_tilda_sola_y_vuelta_a_ignorar_se_destilda(base):
    # CA-52.7.
    lista = revisar(base.con)
    tarjetas = fila(lista, "Tarjetas de Credito")
    lista.cambiar_tipo(tarjetas.indice, "fijo")
    assert tarjetas.tildada is True
    lista.cambiar_tipo(tarjetas.indice, "ignorar")
    assert tarjetas.tildada is False


def test_alquiler_ya_existe_de_fijo_a_unico_sigue_destildada(base):
    # CA-52.7: cambiar entre tipos que no son "ignorar" no toca el tilde.
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    assert (alquiler.ya_existe, alquiler.tildada) == ("gasto", False)
    lista.cambiar_tipo(alquiler.indice, "unico")
    assert (alquiler.ya_existe, alquiler.tildada) == ("gasto", False)


def test_alquiler_pasado_por_ignorar_y_vuelto_a_fijo_queda_tildada_con_su_nota(base):
    # CA-52.7: la fila "ya existe" que sale de "ignorar" se tilda sola, y su nota cambia.
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    lista.cambiar_tipo(alquiler.indice, "ignorar")
    assert alquiler.tildada is False and alquiler.ya_existe is None
    lista.cambiar_tipo(alquiler.indice, "fijo")
    assert alquiler.tildada is True
    assert lista.notas(alquiler) == [
        "Ya existe en Octubre 2026. Si la importás, queda repetida."
    ]


@pytest.mark.parametrize("desde", TIPOS)
@pytest.mark.parametrize("hacia", TIPOS)
def test_se_puede_cambiar_entre_los_seis_tipos(base, desde, hacia):
    # CA-52.6: cualquier fila a cualquiera de los seis tipos, sin error.
    lista = revisar(base.con)
    f = fila(lista, "Gym")
    lista.cambiar_tipo(f.indice, desde)
    lista.cambiar_tipo(f.indice, hacia)
    assert f.tipo == hacia
    if hacia == "ignorar":
        assert f.tildada is False


def test_cambiar_a_un_tipo_desconocido_falla_y_no_cambia_nada(base):
    lista = revisar(base.con)
    f = fila(lista, "Gym")
    with pytest.raises(ValueError):
        lista.cambiar_tipo(f.indice, "inventado")
    assert f.tipo == "fijo" and lista.hubo_cambios is False


def test_se_puede_destildar_y_volver_a_tildar_una_fila(base):
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.cambiar_tilde(gym.indice, False)
    assert gym.tildada is False and gym.se_importa is False
    lista.cambiar_tilde(gym.indice, True)
    assert gym.tildada is True and gym.se_importa is True


def test_destildar_una_fila_ignorada_no_falla(base):
    # Destildar algo que ya está sin tilde es válido (solo tildar "ignorar" falla).
    lista = revisar(base.con)
    tarjetas = fila(lista, "Tarjetas de Credito")
    lista.cambiar_tilde(tarjetas.indice, False)
    assert tarjetas.tildada is False


def test_cambiar_el_tipo_no_cambia_el_tilde_fuera_de_ignorar(base):
    # RN-74: cambiar el tipo (sin pasar por "ignorar") no toca el tilde, tilde o no.
    lista = revisar(base.con)
    gym, servicios = fila(lista, "Gym"), fila(lista, "Servicios")
    lista.cambiar_tilde(gym.indice, False)
    lista.cambiar_tipo(gym.indice, "unico")
    assert gym.tildada is False
    lista.cambiar_tipo(servicios.indice, "me_deben")
    assert servicios.tildada is True


def test_cambiar_el_nombre_recalcula_la_marca_sin_tocar_el_tilde(base):
    # RN-74: renombrar "Alquiler" (ya existe, destildada) deja la marca y el tilde coherentes.
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    errores = lista.editar_fila(alquiler.indice, "fijo", "Alquiler casa", 26000000, categoria=base.vivienda)
    assert errores == {}
    assert alquiler.ya_existe is None
    assert alquiler.tildada is False  # el tilde no se toca
    # Y al revés: una fila tildada que pasa a llamarse como un gasto existente queda tildada.
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "fijo", "  alquiler ", 5000000)
    assert gym.ya_existe == "gasto" and gym.tildada is True


def test_cambiar_la_persona_recalcula_ya_existe_sin_tocar_el_tilde(base):
    # RN-74: la marca de "me deben" depende de la persona; el tilde no se toca.
    cargar_primera_importacion(base)
    lista = revisar(base.con)
    prestamo = fila(lista, "Prestamo MP")
    assert (prestamo.ya_existe, prestamo.tildada) == ("me_deben", False)
    lista.editar_fila(prestamo.indice, "me_deben", "Prestamo MP", 2000000, persona=base.marsu)
    assert (prestamo.ya_existe, prestamo.tildada) == (None, False)
    lista.cambiar_tilde(prestamo.indice, True)
    lista.editar_fila(prestamo.indice, "me_deben", "Prestamo MP", 2000000, persona=base.sofia)
    assert (prestamo.ya_existe, prestamo.tildada) == ("me_deben", True)


def test_pasar_de_ignorar_a_otro_tipo_con_ya_existe_se_tilda_sola(base):
    # RN-68 (decisión 2026-10-13): también si queda "ya existe".
    cargar_primera_importacion(base)
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert (gym.ya_existe, gym.tildada) == ("gasto", False)
    lista.cambiar_tipo(gym.indice, "ignorar")
    lista.cambiar_tipo(gym.indice, "unico")
    assert (gym.ya_existe, gym.tildada) == ("gasto", True)


def test_editar_fila_desde_ignorar_tilda_y_hacia_ignorar_destilda(base):
    # RN-68: aceptar el diálogo cuenta como cambio de tipo (misma regla del tilde).
    lista = revisar(base.con)
    tarjetas = fila(lista, "Tarjetas de Credito")
    assert lista.editar_fila(tarjetas.indice, "fijo", "Tarjetas de Credito", 58291700) == {}
    assert tarjetas.tildada is True
    assert lista.editar_fila(tarjetas.indice, "ignorar", "Tarjetas de Credito", 58291700) == {}
    assert tarjetas.tildada is False


def test_restaurar_fila_vuelve_a_lo_detectado(base):
    # RF-53 "Volver a lo detectado": tipo, tilde, nombre y monto como los propuso la app.
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    lista.editar_fila(alquiler.indice, "unico", "Otro", 100, categoria=base.salud)
    lista.cambiar_tilde(alquiler.indice, True)
    lista.restaurar_fila(alquiler.indice)
    nueva = lista.filas[alquiler.indice]
    assert (nueva.nombre, nueva.monto_cent, nueva.tipo) == ("Alquiler", 26000000, "fijo")
    assert (nueva.ya_existe, nueva.tildada, nueva.categoria) == ("gasto", False, None)
    assert nueva.indice == alquiler.indice


def test_restaurar_una_incompleta_vuelve_a_ignorar_y_sin_completar(base):
    lista = revisar(base.con)
    obra = fila(lista, "Obra social")
    lista.editar_fila(obra.indice, "fijo", "Obra social", 4500000)
    lista.restaurar_fila(obra.indice)
    nueva = lista.filas[obra.indice]
    assert (nueva.tipo, nueva.monto_cent, nueva.tildada) == ("ignorar", None, False)
    assert nueva.incompleta is True


def test_restaurar_fila_recalcula_el_aviso_de_gasto_compartido_de_las_demas(base):
    # RN-72: el aviso depende de qué gastos están tildados. Internet (gasto, fila 5) pasa a
    # ignorar -> el aviso de la fila 23 desaparece; al restaurarla (vuelve tildada) el aviso
    # tiene que volver.
    lista = revisar(base.con)
    gasto, deuda = fila(lista, "Internet", 5), fila(lista, "Internet", 23)
    lista.cambiar_tipo(gasto.indice, "ignorar")
    assert deuda.aviso_compartido is False
    lista.restaurar_fila(gasto.indice)
    assert lista.filas[gasto.indice].tildada is True
    assert deuda.aviso_compartido is True


# ---------------------------------------------------------------------------
# Acciones de bloque (RN-78, CA-52.8, CA-53.5, CA-53.6)
# ---------------------------------------------------------------------------


def test_destildar_y_tildar_bloque_deudas_sofia(base):
    # CA-52.8: 22 y 23 se destildan y se vuelven a tildar; 24 (Total, ignorar) no se toca.
    lista = revisar(base.con)
    prestamo, internet, total = (
        fila(lista, "Prestamo MP"), fila(lista, "Internet", 23), fila(lista, "Total", 24)
    )
    lista.destildar_bloque("Deudas sofia")
    assert (prestamo.tildada, internet.tildada, total.tildada) == (False, False, False)
    lista.tildar_bloque("Deudas sofia")
    assert (prestamo.tildada, internet.tildada, total.tildada) == (True, True, False)
    assert total.tipo == "ignorar"


def test_tildar_bloque_tilda_tambien_las_ya_existen(base):
    # CA-52.8 con la base de CA-56.4 (segunda importación).
    cargar_primera_importacion(base)
    lista = revisar(base.con)
    assert not any(f.tildada for f in lista.filas)
    lista.tildar_bloque("Deudas sofia")
    assert fila(lista, "Prestamo MP").tildada is True
    assert fila(lista, "Internet", 23).tildada is True
    assert fila(lista, "Total", 24).tildada is False
    lista.tildar_bloque("Gasto del Mes")
    assert fila(lista, "Alquiler").tildada is True
    assert fila(lista, "Tarjetas de Credito").tildada is False


def test_bloque_inexistente_falla(base):
    lista = revisar(base.con)
    with pytest.raises(ValueError):
        lista.tildar_bloque("No existe")
    with pytest.raises(ValueError):
        lista.destildar_bloque("No existe")
    with pytest.raises(ValueError):
        lista.cambiar_bloque("No existe", tipo="fijo")
    # Los títulos de las incompletas no son bloques de la lista principal.
    with pytest.raises(ValueError):
        lista.tildar_bloque("Sueldo")


def test_cambiar_bloque_persona_marsu_en_titulo_sofia_y_marsu(base):
    # CA-53.5: "No cambiar el tipo" + persona Marsu -> las filas 22 y 23 son de Marsu;
    # "Total" sigue en ignorar sin tilde.
    lista = revisar(base.con, planilla_con({"D21": "Sofía y Marsu"}))
    lista.cambiar_bloque("Sofía y Marsu", tipo=None, persona=base.marsu)
    for n, fx in (("Prestamo MP", 22), ("Internet", 23)):
        f = fila(lista, n, fx)
        assert (f.tipo, f.persona) == ("me_deben", base.marsu)
    total = fila(lista, "Total", 24)
    assert (total.tipo, total.tildada) == ("ignorar", False)
    assert lista.errores(fila(lista, "Prestamo MP")) == []


@pytest.mark.parametrize(
    "tipo,mensaje",
    [("cuota", "La cuota se elige fila por fila."), ("sueldo", "Solo una fila puede ser el sueldo.")],
)
def test_cambiar_bloque_no_ofrece_cuota_ni_sueldo(base, tipo, mensaje):
    # RN-78: esos dos tipos no se pueden elegir para todo un bloque.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion, match=mensaje):
        lista.cambiar_bloque("Deudas", tipo=tipo)
    assert lista.hubo_cambios is False
    assert fila(lista, "Gym").tipo == "fijo"


def test_cambiar_bloque_a_me_deben_exige_persona(base):
    # RN-78: "Elegí una persona." y no se cambia nada.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion, match="Elegí una persona."):
        lista.cambiar_bloque("Deudas", tipo="me_deben")
    with pytest.raises(ErrorDeValidacion, match="Elegí una persona."):
        lista.cambiar_bloque("Deudas", tipo="me_deben", persona=None)
    assert fila(lista, "Gym").tipo == "fijo"
    assert lista.hubo_cambios is False


def test_cambiar_bloque_a_me_deben_con_persona(base):
    lista = revisar(base.con)
    lista.cambiar_bloque("Deudas", tipo="me_deben", persona=base.marsu)
    for nombre in ("Monotributo 66.020,12", "Gym"):
        f = fila(lista, nombre)
        assert (f.tipo, f.persona) == ("me_deben", base.marsu)


def test_cambiar_bloque_gasto_unico_con_categoria_tilda_el_total_ignorado(base):
    # CA-53.6: las filas 22, 23 y 24 quedan como gasto único en Servicios y tildadas.
    lista = revisar(base.con)
    lista.cambiar_bloque("Deudas sofia", tipo="unico", categoria=base.servicios)
    for n, fx in (("Prestamo MP", 22), ("Internet", 23), ("Total", 24)):
        f = fila(lista, n, fx)
        assert (f.tipo, f.categoria, f.tildada) == ("unico", base.servicios, True), n


def test_cambiar_bloque_categoria_sin_cambiar_tipo_resiste_al_cambio_de_defecto(base):
    # CA-53.6 + RN-75: Monotributo, Avant y Gym a Vivienda; luego el defecto pasa a
    # Servicios y esas tres siguen en Vivienda. Las incompletas del bloque no cambian.
    lista = revisar(base.con)
    lista.cambiar_bloque("Deudas", tipo=None, categoria=base.vivienda)
    lista.cambiar_categoria_defecto(base.servicios)
    for nombre in ("Monotributo 66.020,12", "Avant Service cuota 3/ 3 $41.116,66", "Gym"):
        assert lista.categoria_de(fila(lista, nombre)) == base.vivienda, nombre
    for nombre in ("Deuda freezer", "Obra social"):
        f = fila(lista, nombre)
        assert (f.tipo, f.categoria, f.tildada) == ("ignorar", None, False)
    assert lista.categoria_de(fila(lista, "Servicios")) == base.servicios


def test_cambiar_bloque_con_categoria_none_vuelve_a_seguir_el_defecto(base):
    # RN-78: elegir "Categoría por defecto" en un bloque.
    lista = revisar(base.con)
    lista.cambiar_bloque("Deudas", categoria=base.vivienda)
    lista.cambiar_bloque("Deudas", categoria=None)
    lista.cambiar_categoria_defecto(base.salud)
    assert lista.categoria_de(fila(lista, "Gym")) == base.salud


def test_cambiar_bloque_a_ignorar_destilda_todo(base):
    lista = revisar(base.con)
    lista.cambiar_bloque("Deudas", tipo="ignorar")
    for nombre in ("Monotributo 66.020,12", "Gym", "Avant Service cuota 3/ 3 $41.116,66"):
        f = fila(lista, nombre)
        assert (f.tipo, f.tildada) == ("ignorar", False)


def test_cambiar_bloque_conserva_el_tilde_de_las_que_no_estaban_en_ignorar(base):
    # RN-78: "las que pasan de ignorar a otro tipo se tildan solas; las demás conservan".
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")  # ya existe, destildada
    tarjetas = fila(lista, "Tarjetas de Credito")  # ignorar
    lista.cambiar_bloque("Gasto del Mes", tipo="unico")
    assert alquiler.tildada is False and alquiler.tipo == "unico"
    assert tarjetas.tildada is True and tarjetas.tipo == "unico"


def test_cambiar_bloque_con_persona_nueva(base):
    # RN-78: en la persona se puede usar una nueva.
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    lista.cambiar_bloque("Deudas", tipo="me_deben", persona=juan)
    assert fila(lista, "Gym").persona == juan
    assert lista.nuevas_en_uso() == ([], [juan])


def test_cambiar_bloque_categoria_solo_a_gastos_y_persona_solo_a_me_deben(base):
    # RN-78: con "No cambiar el tipo", la categoría va a gasto/cuota y la persona a "me deben".
    lista = revisar(base.con)
    lista.cambiar_bloque("Deudas sofia", tipo=None, categoria=base.vivienda, persona=base.marsu)
    assert fila(lista, "Prestamo MP").persona == base.marsu
    assert fila(lista, "Prestamo MP").categoria is None
    lista.cambiar_bloque("Deudas", tipo=None, categoria=base.vivienda, persona=base.marsu)
    assert fila(lista, "Gym").persona is None and fila(lista, "Gym").categoria == base.vivienda


def test_cambiar_bloque_recalcula_ya_existe_y_aviso(base):
    # RN-78: después de aplicar se recalculan "ya existe" y los avisos de gasto compartido.
    lista = revisar(base.con)
    lista.cambiar_bloque("Gasto del Mes", tipo="ignorar")
    assert fila(lista, "Alquiler").ya_existe is None
    assert fila(lista, "Internet", 23).aviso_compartido is False
    lista.cambiar_bloque("Gasto del Mes", tipo="fijo")
    assert fila(lista, "Alquiler").ya_existe == "gasto"
    assert fila(lista, "Internet", 23).aviso_compartido is True


# ---------------------------------------------------------------------------
# Edición de una fila (RF-53, RN-68, CA-53.x)
# ---------------------------------------------------------------------------


def test_editar_nombre_y_monto(base):
    # CA-53.1: "psicologo" -> "Psicólogo" y "Servicios" -> 85.000.
    lista = revisar(base.con)
    psico, servicios = fila(lista, "psicologo"), fila(lista, "Servicios")
    assert lista.editar_fila(psico.indice, "fijo", "Psicólogo", 14000000, pagado_cent=6000000) == {}
    assert lista.editar_fila(servicios.indice, "fijo", "Servicios", 8500000) == {}
    assert (psico.nombre, psico.pagado_cent) == ("Psicólogo", 6000000)
    assert servicios.monto_cent == 8500000


def test_completar_obra_social_con_monto_y_tipo(base):
    # CA-53.2: monto 45.000 + gasto fijo -> se importa, y sigue en "Filas incompletas".
    lista = revisar(base.con)
    obra = fila(lista, "Obra social")
    assert lista.editar_fila(obra.indice, "fijo", "Obra social", 4500000) == {}
    assert (obra.tipo, obra.tildada, obra.monto_cent) == ("fijo", True, 4500000)
    assert obra in lista.incompletas()
    assert obra not in [f for b in lista.bloques() for f in b.filas]
    assert lista.errores(obra) == []


def test_obra_social_a_gasto_fijo_sin_monto_muestra_el_error(base):
    # CA-53.2: cambiar el tipo sin completar el monto -> "Falta el monto." y no se confirma.
    lista = revisar(base.con)
    obra = fila(lista, "Obra social")
    lista.cambiar_tipo(obra.indice, "fijo")
    assert lista.errores(obra) == ["Falta el monto."]
    assert lista.notas(obra) == []  # la nota "Se ignora." pasa a ser el error
    assert lista.puede_confirmar() is False


def test_fila_sin_nombre_pasada_a_gasto_muestra_falta_el_nombre(base):
    # RN-63/RN-68: un número suelto que pasa a gasto fijo sin nombre.
    lista = revisar(base.con)
    suelto = sin_nombre(lista, 9)
    lista.cambiar_tipo(suelto.indice, "fijo")
    assert lista.errores(suelto) == ["Falta el nombre."]


def test_editar_con_errores_no_cambia_nada(base):
    # RN-68: con errores y tipo distinto de "ignorar", el diálogo no se acepta.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    errores = lista.editar_fila(gym.indice, "cuota", "Gym", 5000000)
    assert errores == {"cuota": "Indicá la cuota actual y la cantidad de cuotas."}
    assert (gym.tipo, gym.nombre, gym.cuota_actual) == ("fijo", "Gym", None)
    assert lista.hubo_cambios is False


def test_editar_con_tipo_ignorar_se_acepta_aunque_haya_datos_malos(base):
    # RN-68: se puede aceptar con errores si el tipo elegido es "ignorar".
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "ignorar", "", None) == {}
    assert (gym.tipo, gym.nombre, gym.monto_cent, gym.tildada) == ("ignorar", None, None, False)


def test_editar_devuelve_un_error_por_campo(base):
    # RN-68: nombre, monto, categoría y persona a la vez.
    lista = revisar(base.con)
    f = fila(lista, "Gym")
    assert lista.editar_fila(f.indice, "fijo", "   ", None) == {
        "nombre": "Falta el nombre.",
        "monto": "Falta el monto.",
    }
    lista.cambiar_categoria_defecto(None)
    assert lista.editar_fila(f.indice, "fijo", "Gym", 100) == {"categoria": "Elegí una categoría."}
    assert lista.editar_fila(f.indice, "me_deben", "Gym", 100) == {"persona": "Elegí una persona."}


@pytest.mark.parametrize("monto,esperado", [(0, "El monto tiene que ser mayor a 0."), (-100, "El monto tiene que ser mayor a 0."), (None, "Falta el monto.")])
def test_editar_monto_invalido(base, monto, esperado):
    lista = revisar(base.con)
    assert lista.editar_fila(fila(lista, "Gym").indice, "fijo", "Gym", monto) == {"monto": esperado}


def test_editar_nombre_se_guarda_sin_espacios_de_los_costados(base):
    # RN-67: el nombre se guarda sin los espacios del principio y del final.
    lista = revisar(base.con)
    f = fila(lista, "Gym")
    lista.editar_fila(f.indice, "fijo", "   Gimnasio  ", 5000000)
    assert f.nombre == "Gimnasio"


def test_editar_un_tipo_desconocido_falla_sin_cambiar_nada(base):
    lista = revisar(base.con)
    f = fila(lista, "Gym")
    with pytest.raises(ValueError):
        lista.editar_fila(f.indice, "inventado", "Otro", 100)
    assert (f.nombre, f.tipo) == ("Gym", "fijo")


def test_cuota_sin_actual_ni_cantidad_da_el_error(base):
    # CA-53.3: Gym a cuota por el tipo (sin completar los datos).
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.cambiar_tipo(gym.indice, "cuota")
    assert lista.errores(gym) == ["Indicá la cuota actual y la cantidad de cuotas."]
    assert lista.puede_confirmar() is False


def test_gym_cuota_2_de_6_nota_primera_septiembre(base):
    # CA-53.3: cuota 2 de 6 en 2026-10 -> primera 2026-09, última 2027-02.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=2, cuota_total=6) == {}
    assert lista.notas(gym) == [
        "Plan de 6 cuotas: primera Septiembre 2026, última Febrero 2027. "
        "Se agrega la cuota 2/6 en Octubre 2026."
    ]


def test_cuota_actual_fuera_de_rango(base):
    # CA-53.3: cuota 7 de 6 y cuota 0.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    esperado = {"cuota": "La cuota actual tiene que estar entre 1 y la cantidad de cuotas."}
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=7, cuota_total=6) == esperado
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=0, cuota_total=6) == esperado


@pytest.mark.parametrize("total", [0, -3])
def test_cantidad_de_cuotas_menor_a_1(base, total):
    # CA-53.3: cantidad 0 (o negativa).
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=1, cuota_total=total) == {
        "cuota": "La cantidad de cuotas tiene que ser un número entero de 1 o más."
    }


def test_cantidad_de_cuotas_con_decimales_es_un_error(base):
    # CA-53.3: "cantidad 0 o 2,5: error ... número entero de 1 o más".
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    errores = lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=1, cuota_total=2.5)
    assert errores == {
        "cuota": "La cantidad de cuotas tiene que ser un número entero de 1 o más."
    }


def test_cuota_con_datos_invalidos_no_muestra_la_nota_del_plan(base):
    # RN-71: la nota del plan solo aparece con la cuota actual y la cantidad válidas.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.cambiar_tipo(gym.indice, "cuota")  # sin cuota actual ni cantidad
    assert lista.notas(gym) == []
    gym.cuota_actual, gym.cuota_total = 7, 6  # fuera de rango
    assert lista.notas(gym) == []


def test_cuota_con_solo_un_dato_pide_los_dos(base):
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    esperado = {"cuota": "Indicá la cuota actual y la cantidad de cuotas."}
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=2) == esperado
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_total=2) == esperado


def test_nota_de_la_cuota_se_recalcula_si_cambia_el_mes_destino(base):
    # RN-71: la nota se recalcula si cambia la cuota o el mes destino.
    lista = revisar(base.con)
    avant = fila(lista, "Avant Service cuota 3/ 3 $41.116,66")
    lista.cambiar_mes_destino(2026, 11)
    assert lista.notas(avant) == [
        "Plan de 3 cuotas: primera Septiembre 2026, última Noviembre 2026. "
        "Se agrega la cuota 3/3 en Noviembre 2026."
    ]


def test_nota_de_la_cuota_cruza_el_anio(base):
    # RN-71: en el primer uso con destino 2026-02, cuota 3 de 3 empieza en 2025-12.
    con = base.con
    con.execute("DELETE FROM gastos")
    con.execute("DELETE FROM meses")
    lista = revisar(con)
    lista.cambiar_mes_destino(2026, 2)
    avant = fila(lista, "Avant Service cuota 3/ 3 $41.116,66")
    assert "primera Diciembre 2025, última Febrero 2026" in lista.notas(avant)[0]


def test_cambiar_servicios_a_me_deben_pide_persona_y_se_resuelve_con_una_nueva(base):
    # CA-53.4: "Elegí una persona."; se crea "Juan", se elige y desaparece el error.
    lista = revisar(base.con)
    servicios = fila(lista, "Servicios")
    lista.cambiar_tipo(servicios.indice, "me_deben")
    assert lista.errores(servicios) == ["Elegí una persona."]
    assert lista.puede_confirmar() is False
    juan = lista.agregar_persona("Juan")
    assert lista.editar_fila(servicios.indice, "me_deben", "Servicios", 8200000, persona=juan) == {}
    assert servicios.persona == juan
    assert lista.errores(servicios) == []
    assert lista.puede_confirmar() is True


def test_sofia_en_minusculas_se_rechaza_como_persona_nueva(base):
    # CA-53.4.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_persona("sofía")
    assert str(error.value) == 'Ya existe una persona llamada "Sofía".'


def test_editar_conserva_el_origen_y_el_bloque(base):
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "unico", "Otro nombre", 100)
    assert gym.bloque == "Deudas" and gym.origen.fila_excel == 15 and gym.origen.nombre == "Gym"


# ---------------------------------------------------------------------------
# Categorías y personas nuevas (RN-72, RN-75, CA-54.x, CA-57.11)
# ---------------------------------------------------------------------------


def test_la_categoria_por_defecto_viene_varios(base):
    # CA-54.1.
    lista = revisar(base.con)
    assert lista.categoria_defecto == base.varios
    for nombre in ("Servicios", "Internet", "Gym", "Avant Service cuota 3/ 3 $41.116,66"):
        f = [x for x in lista.filas if x.nombre == nombre][0]
        assert lista.categoria_de(f) == base.varios


def test_categoria_distinta_en_una_fila_resiste_al_cambio_de_defecto(base):
    # CA-54.2: Internet en Servicios; el defecto pasa a Vivienda; las demás a Vivienda.
    lista = revisar(base.con)
    internet = fila(lista, "Internet", 5)
    lista.editar_fila(
        internet.indice, "fijo", "Internet", 3870000, pagado_cent=3870000, categoria=base.servicios
    )
    lista.cambiar_categoria_defecto(base.vivienda)
    assert lista.categoria_de(internet) == base.servicios
    for nombre in ("Servicios", "psicologo", "Gym", "Avant Service cuota 3/ 3 $41.116,66"):
        f = [x for x in lista.filas if x.nombre == nombre][0]
        assert lista.categoria_de(f) == base.vivienda, nombre


def test_elegir_categoria_por_defecto_en_una_fila_vuelve_a_seguir_el_defecto(base):
    # RN-75.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=base.salud)
    assert lista.categoria_de(gym) == base.salud
    lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=None)
    lista.cambiar_categoria_defecto(base.vivienda)
    assert lista.categoria_de(gym) == base.vivienda


def test_sin_varios_no_hay_categoria_por_defecto_y_cada_gasto_da_error(base_sin_varios):
    # CA-54.3.
    lista = revisar(base_sin_varios.con)
    assert lista.categoria_defecto is None
    gastos_y_cuota = [f for f in lista.filas if f.tipo in ("fijo", "unico", "cuota") and f.tildada]
    assert len(gastos_y_cuota) == 5 + 1
    for f in gastos_y_cuota:
        assert lista.errores(f) == ["Elegí una categoría."], f.nombre
    assert lista.puede_confirmar() is False
    # Las "me deben" no necesitan categoría.
    assert lista.errores(fila(lista, "Prestamo MP")) == []


def test_sin_varios_se_resuelve_creando_una_categoria_nueva_como_defecto(base_sin_varios):
    # CA-54.3 / CA-57.11: la categoría "Importado" como defecto sale de la lista de "en uso".
    lista = revisar(base_sin_varios.con)
    importado = lista.agregar_categoria("Importado")
    assert importado == Nueva("Importado")
    lista.cambiar_categoria_defecto(importado)
    assert lista.puede_confirmar() is True
    assert lista.nuevas_en_uso() == ([importado], [])


def test_categoria_nueva_creada_y_no_usada_no_queda_en_uso_ni_en_la_base(base):
    # CA-54.3: crear "Importado" y no usarla (o cancelar) no la crea.
    lista = revisar(base.con)
    lista.agregar_categoria("Importado")
    assert lista.nuevas_en_uso() == ([], [])
    assert "Importado" not in [c["nombre"] for c in catalogos.listar(base.con, catalogos.CATEGORIAS)]


def test_categoria_nueva_elegida_solo_en_gym_y_gym_destildada_no_queda_en_uso(base):
    # CA-57.11.
    lista = revisar(base.con)
    importado = lista.agregar_categoria("Importado")
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=importado)
    assert lista.nuevas_en_uso() == ([importado], [])
    lista.cambiar_tilde(gym.indice, False)
    assert lista.nuevas_en_uso() == ([], [])


def test_categoria_nueva_por_defecto_queda_en_uso_aunque_ninguna_fila_la_eligio(base):
    # CA-57.11: "elegida a mano o por ser la categoría por defecto".
    lista = revisar(base.con)
    importado = lista.agregar_categoria("Importado")
    lista.cambiar_categoria_defecto(importado)
    assert lista.nuevas_en_uso() == ([importado], [])


def test_categoria_nueva_solo_cuenta_si_la_usa_una_fila_de_gasto_que_se_importa(base):
    # RN-75: una fila "me deben", "ignorar" o destildada con la categoría nueva no la usa.
    lista = revisar(base.con)
    importado = lista.agregar_categoria("Importado")
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=importado)
    lista.cambiar_tipo(gym.indice, "me_deben")
    assert lista.nuevas_en_uso() == ([], [])
    lista.cambiar_tipo(gym.indice, "ignorar")
    assert lista.nuevas_en_uso() == ([], [])


def test_categoria_nueva_usada_por_una_cuota_queda_en_uso(base):
    lista = revisar(base.con)
    importado = lista.agregar_categoria("Importado")
    avant = fila(lista, "Avant Service cuota 3/ 3 $41.116,66")
    lista.editar_fila(avant.indice, "cuota", avant.nombre, 4111666, categoria=importado,
                      cuota_actual=3, cuota_total=3)
    assert lista.nuevas_en_uso() == ([importado], [])


def test_persona_nueva_solo_si_alguna_fila_me_deben_que_se_importa_la_usa(base):
    # CA-57.11: "Juan" para "Servicios" como me deben; si vuelve a gasto fijo, no se crea.
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    servicios = fila(lista, "Servicios")
    lista.editar_fila(servicios.indice, "me_deben", "Servicios", 8200000, persona=juan)
    assert lista.nuevas_en_uso() == ([], [juan])
    lista.cambiar_tipo(servicios.indice, "fijo")
    assert lista.nuevas_en_uso() == ([], [])
    lista.cambiar_tipo(servicios.indice, "me_deben")
    assert lista.nuevas_en_uso() == ([], [juan])
    lista.cambiar_tilde(servicios.indice, False)
    assert lista.nuevas_en_uso() == ([], [])
    lista.cambiar_tilde(servicios.indice, True)
    lista.editar_fila(servicios.indice, "me_deben", "Servicios", 8200000, persona=base.marsu)
    assert lista.nuevas_en_uso() == ([], [])


def test_persona_nueva_se_puede_elegir_en_otras_filas(base):
    # RN-72: la persona nueva se puede elegir en las demás filas mientras dura la revisión.
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    for nombre in ("Prestamo MP", "tacones chiqui baby"):
        f = fila(lista, nombre)
        assert lista.editar_fila(f.indice, "me_deben", nombre, f.monto_cent, persona=juan) == {}
    assert lista.nuevas_en_uso() == ([], [juan])
    assert lista.nombre_persona(juan) == "Juan"


def test_varias_nuevas_solo_devuelve_las_usadas_y_en_orden_de_alta(base):
    lista = revisar(base.con)
    a, b, c = (lista.agregar_categoria(n) for n in ("Aa", "Bb", "Cc"))
    lista.editar_fila(fila(lista, "Gym").indice, "fijo", "Gym", 5000000, categoria=c)
    lista.editar_fila(fila(lista, "Servicios").indice, "fijo", "Servicios", 8200000, categoria=a)
    assert lista.nuevas_en_uso()[0] == [a, c]
    assert b not in lista.nuevas_en_uso()[0]


@pytest.mark.parametrize("texto", ["", "   ", "\t"])
def test_nombre_nuevo_vacio(base, texto):
    # RN-75: "Ingresá un nombre."
    lista = revisar(base.con)
    for agregar in (lista.agregar_categoria, lista.agregar_persona):
        with pytest.raises(ErrorDeValidacion) as error:
            agregar(texto)
        assert str(error.value) == "Ingresá un nombre."
        assert error.value.campo == "nombre"


@pytest.mark.parametrize("escrito", ["Salud", "salud", "SALUD", " salud  "])
def test_categoria_nueva_que_ya_existe(base, escrito):
    # RN-75: sin mayúsculas ni espacios de más; el texto usa el nombre existente.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_categoria(escrito)
    assert str(error.value) == 'Ya existe una categoría llamada "Salud".'


@pytest.mark.parametrize("escrito", ["sofía", "Sofia", "SOFÍA"])
def test_persona_nueva_que_ya_existe_sin_acentos_ni_mayusculas(base, escrito):
    # RN-75 + RN-67.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_persona(escrito)
    assert str(error.value) == 'Ya existe una persona llamada "Sofía".'


def test_categoria_nueva_que_existe_sin_acento(base):
    # RN-67: "Mercado" vs "mercádo" y una categoría con acento "Alimentación".
    catalogos.crear(base.con, catalogos.CATEGORIAS, "Alimentación")
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_categoria("alimentacion")
    assert str(error.value) == 'Ya existe una categoría llamada "Alimentación".'


def test_categoria_archivada_texto_exacto(base):
    # RN-75: texto con "(está archivada). Podés desarchivarla en Ajustes."
    base.con.execute("UPDATE categorias SET archivado = 1 WHERE id = ?", (base.salud,))
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_categoria("salud")
    assert str(error.value) == (
        'Ya existe una categoría llamada "Salud" (está archivada). Podés desarchivarla en Ajustes.'
    )


def test_persona_archivada_texto_exacto(base):
    # RN-75: para personas, el mismo texto con "una persona".
    base.con.execute("UPDATE personas SET archivado = 1 WHERE id = ?", (base.marsu,))
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_persona("MARSU")
    assert str(error.value) == (
        'Ya existe una persona llamada "Marsu" (está archivada). Podés desarchivarla en Ajustes.'
    )


def test_persona_ya_agregada_en_la_importacion(base):
    # RN-75: "Ya agregaste una persona llamada "Juan" en esta importación."
    lista = revisar(base.con)
    lista.agregar_persona("Juan")
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_persona("juan")
    assert str(error.value) == 'Ya agregaste una persona llamada "Juan" en esta importación.'
    assert error.value.campo == "nombre"
    assert len(lista.personas_nuevas) == 1


def test_categoria_ya_agregada_en_la_importacion(base):
    lista = revisar(base.con)
    lista.agregar_categoria("Importado")
    with pytest.raises(ErrorDeValidacion) as error:
        lista.agregar_categoria(" IMPORTADO ")
    assert str(error.value) == 'Ya agregaste una categoría llamada "Importado" en esta importación.'


def test_una_categoria_y_una_persona_pueden_llamarse_igual(base):
    # RN-75: las comparaciones son dentro de cada lista (categorías y personas aparte).
    lista = revisar(base.con)
    assert lista.agregar_categoria("Marsu") == Nueva("Marsu")
    assert lista.agregar_persona("Varios") == Nueva("Varios")


def test_nombre_nuevo_se_limpia_los_espacios(base):
    # RN-67: el nombre se guarda sin espacios de más.
    lista = revisar(base.con)
    assert lista.agregar_persona("  Juan   Pérez ").nombre == "Juan Pérez"


def test_un_nombre_rechazado_no_agrega_nada_ni_marca_cambios(base):
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion):
        lista.agregar_persona("Sofía")
    with pytest.raises(ErrorDeValidacion):
        lista.agregar_categoria("")
    assert lista.personas_nuevas == [] and lista.categorias_nuevas == []
    assert lista.hubo_cambios is False


def test_agregar_no_escribe_en_la_base(base):
    # RN-72/RN-75: se guardan recién al confirmar.
    antes = foto_de_la_base(base.con)
    lista = revisar(base.con)
    lista.agregar_persona("Juan")
    lista.agregar_categoria("Importado")
    assert foto_de_la_base(base.con) == antes


def test_nombre_persona_de_un_id_archivado_o_inexistente(base):
    lista = revisar(base.con)
    assert lista.nombre_persona(base.sofia) == "Sofía"
    assert lista.nombre_persona(None) == ""
    assert lista.nombre_persona(99999) == ""


# ---------------------------------------------------------------------------
# Mes destino (RN-73, CA-55.x, CA-56.5)
# ---------------------------------------------------------------------------


def test_mes_destino_por_defecto_y_opciones(base):
    # CA-55.1: viene 2026-10; se ofrecen 2026-10 y 2026-11, no 2026-09 ni 2026-12.
    lista = revisar(base.con)
    assert (lista.anio, lista.mes) == (2026, 10)
    assert lista.meses_posibles() == [(2026, 10), (2026, 11)]
    assert lista.nombre_mes_destino == "Octubre 2026"
    assert lista.es_primer_uso is False
    assert lista.mes_se_crea is False


@pytest.mark.parametrize("anio,mes", [(2026, 9), (2026, 12), (2027, 10), (2025, 10), (2026, 0)])
def test_mes_destino_no_ofrecido_se_rechaza_y_no_cambia(base, anio, mes):
    # CA-55.1.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion):
        lista.cambiar_mes_destino(anio, mes)
    assert (lista.anio, lista.mes) == (2026, 10)
    assert lista.hubo_cambios is False


def test_mes_destino_rechazado_dice_que_ese_mes_no_se_puede_elegir(base):
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.cambiar_mes_destino(2026, 12)
    assert str(error.value) == "Ese mes no se puede elegir."
    assert error.value.campo == "mes"


def test_mes_actual_siguiente_al_ultimo_es_el_defecto(base):
    # RN-73: hoy 2026-11 -> el mes actual se puede crear (RN-08) y es el defecto.
    lista = revisar(base.con, hoy=date(2026, 11, 3))
    assert (lista.anio, lista.mes) == (2026, 11)
    assert lista.mes_se_crea is True


@pytest.mark.parametrize("hoy", [date(2026, 9, 30), date(2027, 1, 1), date(2026, 12, 1)])
def test_mes_actual_no_ofrecido_propone_el_ultimo_mes(base, hoy):
    # RN-73: si el mes actual ni existe ni se puede crear, se propone el último.
    lista = revisar(base.con, hoy=hoy)
    assert (lista.anio, lista.mes) == (2026, 10)


def test_con_ultimo_mes_2026_08_se_propone_2026_08(con):
    # CA-55.5.
    meses.crear_primer_mes(con, 2026, 8, 120000, 160000)
    lista = revisar(con)
    assert (lista.anio, lista.mes) == (2026, 8)
    assert lista.meses_posibles() == [(2026, 8), (2026, 9)]


def test_con_un_hueco_de_meses_solo_se_ofrecen_los_existentes_y_el_siguiente(con):
    # RN-73: existentes (2026-08 y 2026-10) y el siguiente al último (2026-11).
    insertar_mes(con, 2026, 8)
    insertar_mes(con, 2026, 10)
    lista = revisar(con)
    assert lista.meses_posibles() == [(2026, 8), (2026, 10), (2026, 11)]
    with pytest.raises(ErrorDeValidacion):
        lista.cambiar_mes_destino(2026, 9)


def test_destino_2026_11_se_crea_y_el_sueldo_muestra_el_cambio(base):
    # CA-55.2: fila 19 como sueldo.
    lista = revisar(base.con)
    suelto = sin_nombre(lista, 19)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    lista.cambiar_mes_destino(2026, 11)
    assert lista.mes_se_crea is True
    assert lista.sueldo_actual_cent() == 120000
    assert lista.notas(suelto) == ["Sueldo del mes: US$ 1.200,00 -> US$ 1.300,00."]


def test_sueldo_igual_al_actual_no_muestra_flecha(base):
    # RN-70: "Sueldo del mes: US$ 1.300,00." si no cambia.
    lista = revisar(base.con, xlsx({"B1": "Sueldo", "B2": 1200}))
    suelto = sin_nombre(lista, 2)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    assert lista.notas(suelto) == ["Sueldo del mes: US$ 1.200,00."]
    assert lista.errores(suelto) == []


def test_sueldo_en_el_mes_destino_existente_usa_el_sueldo_de_ese_mes(base):
    # RN-70: el sueldo actual es el del mes destino (2026-09 tiene otro).
    insertar_mes(base.con, 2026, 9, sueldo=100000)
    lista = revisar(base.con)
    suelto = sin_nombre(lista, 19)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    lista.cambiar_mes_destino(2026, 9)
    assert lista.sueldo_actual_cent() == 100000
    assert lista.notas(suelto) == ["Sueldo del mes: US$ 1.000,00 -> US$ 1.300,00."]


def test_sueldo_actual_del_mes_a_crear_es_el_del_ultimo_mes(base):
    lista = revisar(base.con)
    lista.cambiar_mes_destino(2026, 11)
    assert lista.sueldo_actual_cent() == 120000


def test_aviso_si_el_mes_destino_existe_pero_no_es_el_ultimo(base):
    # CA-55.3: 2026-09 y 2026-10 existentes, destino 2026-09.
    insertar_mes(base.con, 2026, 9)
    lista = revisar(base.con)
    assert lista.aviso_mes() is None  # el destino por defecto es el último
    lista.cambiar_mes_destino(2026, 9)
    assert lista.aviso_mes() == (
        "Los gastos fijos que importes no se agregan a los meses siguientes que ya existen."
    )
    lista.cambiar_mes_destino(2026, 11)
    assert lista.aviso_mes() is None  # se va a crear, no existe


def test_destino_primer_uso_cualquier_mes_valido(con):
    # CA-55.4: base sin meses.
    lista = revisar(con)
    assert lista.es_primer_uso is True
    assert lista.meses_posibles() == []
    assert (lista.anio, lista.mes) == (2026, 10)
    assert lista.mes_se_crea is True
    assert lista.aviso_mes() is None
    assert lista.sueldo_actual_cent() is None
    lista.cambiar_mes_destino(2024, 3)
    assert (lista.anio, lista.mes) == (2024, 3)


@pytest.mark.parametrize(
    "anio,mes,mensaje",
    [
        (2026, 13, "El mes tiene que estar entre 1 y 12."),
        (2026, 0, "El mes tiene que estar entre 1 y 12."),
        (26, 10, "El año tiene que tener 4 dígitos."),
        (12345, 1, "El año tiene que tener 4 dígitos."),
    ],
)
def test_primer_uso_rechaza_mes_o_anio_invalido(con, anio, mes, mensaje):
    # CA-55.4: mes 13 o año "26" se rechazan.
    lista = revisar(con)
    with pytest.raises(ErrorDeValidacion) as error:
        lista.cambiar_mes_destino(anio, mes)
    assert str(error.value) == mensaje
    assert (lista.anio, lista.mes) == (2026, 10)
    assert lista.hubo_cambios is False


def test_primer_uso_sueldo_sin_mes_anterior_no_tiene_flecha(con):
    # CA-55.4 / RN-70: no hay sueldo anterior, no hay "->".
    lista = revisar(con)
    suelto = sin_nombre(lista, 19)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    assert lista.notas(suelto) == ["Sueldo del mes: US$ 1.300,00."]


def test_primer_uso_ninguna_fila_viene_ya_existe_y_todas_las_que_se_importan_tildadas(con):
    # RN-74: sin meses no hay gastos con los que comparar, ni siquiera "Alquiler".
    catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    lista = revisar(con)
    assert not any(f.ya_existe for f in lista.filas)
    assert fila(lista, "Alquiler").tildada is True


def test_primer_uso_usa_los_items_me_deben_existentes_para_ya_existe(con):
    # RN-74: "me deben" no depende del mes: también se marca en el primer uso.
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    me_deben.agregar_item(con, sofia, "Prestamo MP", 2000000, HOY)
    lista = revisar(con)
    assert fila(lista, "Prestamo MP").ya_existe == "me_deben"
    assert fila(lista, "Internet", 23).ya_existe is None


def test_primer_uso_el_aviso_de_gasto_compartido_funciona(con):
    # RN-72 en el primer uso: solo cuentan las filas del Excel.
    catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    lista = revisar(con)
    assert fila(lista, "Internet", 23).aviso_compartido is True
    lista.cambiar_tipo(fila(lista, "Internet", 5).indice, "ignorar")
    assert fila(lista, "Internet", 23).aviso_compartido is False


def test_mes_destino_igual_al_actual_no_cambia_nada(base):
    lista = revisar(base.con)
    assert lista.cambiar_mes_destino(2026, 10) is None
    assert lista.hubo_cambios is False


def test_alquiler_sigue_ya_existe_en_2026_11_y_no_hay_mensaje(base):
    # CA-55.2: "Alquiler" del Excel también venía "ya existe" en 2026-11 (Alquiler se copia).
    lista = revisar(base.con)
    assert lista.cambiar_mes_destino(2026, 11) is None
    alquiler = fila(lista, "Alquiler")
    assert (alquiler.ya_existe, alquiler.tildada) == ("gasto", False)
    assert lista.notas(alquiler) == ["Ya existe en Noviembre 2026. Viene destildada."]


def test_mensaje_al_pasar_a_2026_09_y_volver_a_2026_11(base):
    # CA-56.5: 2026-09 sin Alquiler y 2026-10 con Alquiler.
    insertar_mes(base.con, 2026, 9)
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    assert (alquiler.ya_existe, alquiler.tildada) == ("gasto", False)
    assert lista.cambiar_mes_destino(2026, 9) == "Cambiaste el mes: 1 fila se volvió a tildar."
    assert (alquiler.ya_existe, alquiler.tildada) == (None, True)
    assert lista.cambiar_mes_destino(2026, 11) == (
        'Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó.'
    )
    assert (alquiler.ya_existe, alquiler.tildada) == ("gasto", False)


def test_mensaje_con_una_fila_que_entra_y_otra_que_sale_de_ya_existe(base):
    # RN-74: texto exacto del ejemplo, con las dos partes.
    insertar_mes(base.con, 2026, 9)
    mes_9 = base.con.execute("SELECT id FROM meses WHERE mes = 9").fetchone()["id"]
    gastos.agregar_gasto(base.con, mes_9, "Gym", base.varios, 5000000, "fijo")
    lista = revisar(base.con)
    assert fila(lista, "Gym").ya_existe is None
    assert lista.cambiar_mes_destino(2026, 9) == (
        'Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó. 1 fila se volvió a tildar.'
    )
    assert fila(lista, "Gym").tildada is False
    assert fila(lista, "Alquiler").tildada is True


def test_mensaje_en_plural(base):
    # RN-74 ("nombra solo lo que pasó"): varias filas, en plural.
    insertar_mes(base.con, 2026, 9)
    mes_9 = base.con.execute("SELECT id FROM meses WHERE mes = 9").fetchone()["id"]
    for nombre in ("Gym", "Servicios"):
        gastos.agregar_gasto(base.con, mes_9, nombre, base.varios, 100, "fijo")
    lista = revisar(base.con)
    assert lista.cambiar_mes_destino(2026, 9) == (
        'Cambiaste el mes: 2 filas pasaron a "ya existe" y se destildaron. '
        "1 fila se volvió a tildar."
    )
    assert lista.cambiar_mes_destino(2026, 10) == (
        'Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó. '
        "2 filas se volvieron a tildar."
    )


def test_sin_cambio_de_tildes_no_hay_mensaje_aunque_cambie_el_mes(base):
    # RN-74: "Si ningún tilde cambió, no hay mensaje."
    insertar_mes(base.con, 2026, 9)
    lista = revisar(base.con)
    lista.cambiar_tilde(fila(lista, "Alquiler").indice, True)  # el usuario la tildó
    assert lista.cambiar_mes_destino(2026, 9) is None
    assert (lista.anio, lista.mes) == (2026, 9)
    assert lista.hubo_cambios is True


def test_filas_en_ignorar_no_cuentan_en_el_mensaje_del_mes(base):
    # RN-74: las ignoradas ni tienen marca ni tilde.
    insertar_mes(base.con, 2026, 9)
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Alquiler").indice, "ignorar")
    assert lista.cambiar_mes_destino(2026, 9) is None
    assert fila(lista, "Alquiler").tildada is False


def test_al_cambiar_de_mes_el_aviso_de_gasto_compartido_se_recalcula(base):
    # RN-73: "Cambiar el mes destino recalcula ... los avisos de posible gasto compartido".
    # 2026-10 tiene un gasto "Internet": la fila 5 viene "ya existe" y destildada; el aviso de la
    # fila 23 se ve igual (por el gasto del mes). En 2026-09 (sin Internet) la fila 5 se vuelve a
    # tildar, así que el aviso tiene que seguir (ahora por la fila 5).
    insertar_mes(base.con, 2026, 9)
    gastos.agregar_gasto(base.con, base.mes_id, "Internet", base.varios, 100, "fijo")
    lista = revisar(base.con)
    assert fila(lista, "Internet", 5).tildada is False
    assert fila(lista, "Internet", 23).aviso_compartido is True
    lista.cambiar_mes_destino(2026, 9)
    assert fila(lista, "Internet", 5).tildada is True
    assert fila(lista, "Internet", 23).aviso_compartido is True


# ---------------------------------------------------------------------------
# "Ya existe" y "repetida" (RN-74, CA-56.x)
# ---------------------------------------------------------------------------


def test_alquiler_ya_existe_destildada_y_nota_exacta(base):
    # CA-56.1.
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    assert lista.notas(alquiler) == ["Ya existe en Octubre 2026. Viene destildada."]
    lista.cambiar_tilde(alquiler.indice, True)
    assert lista.notas(alquiler) == [
        "Ya existe en Octubre 2026. Si la importás, queda repetida."
    ]


def test_ya_existe_ignora_mayusculas_acentos_y_espacios(base):
    # CA-56.2 + RN-67: " telefono " del Excel contra "Teléfono" del mes.
    gastos.agregar_gasto(base.con, base.mes_id, "Teléfono", base.varios, 100, "unico")
    lista = revisar(base.con, xlsx({"C5": " telefono ", "D5": 1000}))
    f = lista.filas[0]
    assert f.ya_existe == "gasto" and f.tildada is False


def test_ya_existe_compara_con_gastos_de_cualquier_tipo_y_cualquier_fila_de_gasto(base):
    # RN-74: pago único existente + fila "cuota" con el mismo nombre -> "ya existe".
    gastos.agregar_gasto(base.con, base.mes_id, "Heladera 2/12", base.varios, 100, "unico")
    lista = revisar(base.con, xlsx({"C1": "Heladera 2/12", "D1": 30000}))
    assert lista.filas[0].tipo == "cuota"
    assert lista.filas[0].ya_existe == "gasto"


def test_ya_existe_no_confunde_nombres_parecidos(base):
    gastos.agregar_gasto(base.con, base.mes_id, "Pesos checks", base.varios, 100, "fijo")
    lista = revisar(base.con, xlsx({"C1": "Pesos check", "D1": 1000, "C2": "Alquileres", "D2": 5}))
    assert [f.ya_existe for f in lista.filas] == [None, None]


def test_segunda_importacion_marca_todo_como_ya_existe(base):
    # CA-56.4.
    cargar_primera_importacion(base)
    lista = revisar(base.con)
    importables = [f for f in lista.filas if f.tipo in ("fijo", "cuota", "me_deben")]
    assert len(importables) == 10
    for f in importables:
        assert f.ya_existe is not None, f.nombre
        assert f.tildada is False, f.nombre
    assert lista.estado_pie() == "No hay filas para importar."
    assert lista.puede_confirmar() is False


def test_segunda_importacion_textos_de_las_notas(base):
    # CA-56.4: textos exactos de "me deben" y de gasto.
    cargar_primera_importacion(base)
    lista = revisar(base.con)
    assert lista.notas(fila(lista, "Prestamo MP")) == [
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
    ]
    assert lista.notas(fila(lista, "tacones chiqui baby")) == [
        "Marsu ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
    ]
    assert lista.notas(fila(lista, "Gym")) == ["Ya existe en Octubre 2026. Viene destildada."]


def test_item_me_deben_cobrado_no_cuenta_como_ya_existe(base):
    # RN-74: solo los ítems NO cobrados.
    item = me_deben.agregar_item(base.con, base.sofia, "Prestamo MP", 2000000, HOY)
    me_deben.marcar_item_cobrado(base.con, item, True)
    lista = revisar(base.con)
    assert fila(lista, "Prestamo MP").ya_existe is None


def test_item_me_deben_de_otra_persona_no_cuenta(base):
    me_deben.agregar_item(base.con, base.marsu, "Prestamo MP", 2000000, HOY)
    lista = revisar(base.con)
    assert fila(lista, "Prestamo MP").ya_existe is None


def test_item_me_deben_compara_la_descripcion_sin_acentos_ni_mayusculas(base):
    me_deben.agregar_item(base.con, base.sofia, "PRÉSTAMO mp", 100, HOY)
    lista = revisar(base.con, xlsx({"D21": "Deudas sofia", "D22": "prestamo MP", "E22": 5000}))
    assert fila(lista, "prestamo MP").ya_existe == "me_deben"


def test_fila_me_deben_sin_persona_no_se_marca_ya_existe(base):
    me_deben.agregar_item(base.con, base.sofia, "Servicios", 100, HOY)
    lista = revisar(base.con)
    servicios = fila(lista, "Servicios")
    lista.cambiar_tipo(servicios.indice, "me_deben")
    assert servicios.ya_existe is None
    lista.editar_fila(servicios.indice, "me_deben", "Servicios", 8200000, persona=base.sofia)
    assert servicios.ya_existe == "me_deben"


def test_fila_me_deben_con_persona_nueva_no_se_marca_ya_existe(base):
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    servicios = fila(lista, "Servicios")
    lista.editar_fila(servicios.indice, "me_deben", "Servicios", 8200000, persona=juan)
    assert servicios.ya_existe is None


def test_plan_de_cuotas_con_ese_nombre_marca_la_fila_cuota(base):
    # RN-74: "Ya existe un plan de cuotas con este nombre. Viene destildada." (plan terminado:
    # no tiene cuota en 2026-10, así que solo lo detecta la regla del plan).
    cuotas.crear_plan(base.con, "Heladera 2/12", base.varios, None, 100000, 3, 2026, 1, hoy=HOY)
    lista = revisar(base.con, xlsx({"C1": "Heladera 2/12", "D1": 30000}))
    f = lista.filas[0]
    assert (f.tipo, f.ya_existe, f.tildada) == ("cuota", "plan", False)
    assert lista.notas(f)[0] == (
        "Ya existe un plan de cuotas con este nombre. Viene destildada."
    )


def test_plan_existente_no_marca_filas_que_no_son_cuota(base):
    # RN-74: la regla del plan es solo para filas de tipo cuota.
    cuotas.crear_plan(base.con, "Heladera", base.varios, None, 100000, 3, 2026, 1, hoy=HOY)
    lista = revisar(base.con, xlsx({"C1": "Heladera", "D1": 30000}))
    assert lista.filas[0].tipo == "fijo" and lista.filas[0].ya_existe is None
    lista.cambiar_tipo(lista.filas[0].indice, "cuota")
    assert lista.filas[0].ya_existe == "plan"


def test_plan_terminado_igual_marca_ya_existe(base):
    # RN-74: "en cualquier estado" (acá, un plan que terminó antes del mes destino).
    cuotas.crear_plan(base.con, "Heladera 2/12", base.varios, None, 100000, 3, 2026, 1, hoy=HOY)
    lista = revisar(base.con, xlsx({"C1": "Heladera 2/12", "D1": 30000}))
    assert lista.filas[0].ya_existe == "plan"


def test_ya_existe_con_mes_que_se_va_a_crear_usa_fijos_del_ultimo_mes(base):
    # RN-74: destino 2026-11 (no existe): se comparan los fijos que se copiarían.
    gastos.agregar_gasto(base.con, base.mes_id, "Regalo", base.varios, 100, "unico")
    lista = revisar(base.con, xlsx({"C1": "Alquiler", "D1": 5, "C2": "Regalo", "D2": 5}))
    assert [f.ya_existe for f in lista.filas] == ["gasto", "gasto"]
    lista.cambiar_mes_destino(2026, 11)
    # El pago único no se copia al mes nuevo; el fijo sí.
    assert [f.ya_existe for f in lista.filas] == ["gasto", None]


def test_ya_existe_con_mes_a_crear_incluye_cuotas_de_planes_activos(base):
    # RN-74/RN-09: Avant (primer 2026-09, 3 cuotas) tiene cuota en 2026-11, pero no en 2026-12.
    cuotas.crear_plan(base.con, "Avant", base.varios, None, 100, 3, 2026, 9, hoy=HOY)
    lista = revisar(base.con, xlsx({"C1": "Avant", "D1": 5}))
    lista.cambiar_mes_destino(2026, 11)
    assert lista.filas[0].ya_existe == "gasto"


def test_ya_existe_con_mes_a_crear_no_incluye_planes_ya_terminados(base):
    # El plan terminó en 2026-10: en 2026-11 no tendrá cuota, así que un gasto "Avant" no es
    # "ya existe" (pero una fila de tipo cuota sí, por el plan).
    cuotas.crear_plan(base.con, "Avant", base.varios, None, 100, 3, 2026, 8, hoy=HOY)
    lista = revisar(base.con, xlsx({"C1": "Avant", "D1": 5}))
    assert lista.filas[0].ya_existe == "gasto"  # en 2026-10 todavía tiene la cuota 3/3
    lista.cambiar_mes_destino(2026, 11)
    assert lista.filas[0].ya_existe is None
    lista.cambiar_tipo(lista.filas[0].indice, "cuota")
    assert lista.filas[0].ya_existe == "plan"


def test_ya_existe_con_mes_a_crear_cuando_no_hay_gastos_fijos_en_el_ultimo_mes(con, mes_id):
    # Sin ningún gasto en el último mes: nada es "ya existe" en el mes a crear.
    lista = revisar(con, xlsx({"C1": "Alquiler", "D1": 5}))
    lista.cambiar_mes_destino(2026, 11)
    assert lista.filas[0].ya_existe is None


def test_repetida_en_el_archivo_nafta_dos_veces(base):
    # CA-56.3.
    lista = revisar(base.con, xlsx({"C1": "Nafta", "D1": 30000, "C2": "Nafta", "D2": 30000}))
    for f in lista.filas:
        assert f.repetida is True and f.tildada is True
        assert lista.notas(f) == [
            "Repetida en el archivo. Si no es un error del Excel, podés importarla igual."
        ]
    assert lista.puede_confirmar() is True


def test_repetida_en_el_archivo_ignora_mayusculas_y_espacios(base):
    lista = revisar(base.con, xlsx({"C1": "Nafta", "D1": 100, "C2": "  NAFTA ", "D2": 100}))
    assert all(f.repetida for f in lista.filas)


def test_internet_gasto_y_me_deben_no_son_repetidas(base):
    # CA-56.3 (segunda parte).
    lista = revisar(base.con)
    assert fila(lista, "Internet", 5).repetida is False
    assert fila(lista, "Internet", 23).repetida is False
    assert not any(f.repetida for f in lista.filas)


def test_repetida_entre_gastos_de_distinto_tipo(base):
    # RN-74: fijo, pago único y cuota son el mismo grupo.
    lista = revisar(base.con, xlsx({"C1": "Luz", "D1": 100, "C2": "Luz", "D2": 100, "C3": "Luz 1/3", "D3": 1}))
    lista.cambiar_tipo(lista.filas[1].indice, "unico")
    assert lista.filas[0].repetida and lista.filas[1].repetida
    assert lista.filas[2].repetida is False  # el nombre "Luz 1/3" es otro


def test_repetida_pesos_check_de_sofia_y_marsu_no_son_repetidas(base):
    # RN-74: "me deben" de personas distintas.
    celdas = {
        "D21": "Deudas sofia", "D22": "Pesos Check", "E22": 100,
        "D26": "Marsu", "D27": "Pesos Check", "E27": 100,
    }
    lista = revisar(base.con, xlsx(celdas))
    assert [f.repetida for f in lista.filas if f.nombre == "Pesos Check"] == [False, False]


def test_repetida_me_deben_de_la_misma_persona(base):
    celdas = {"D21": "Deudas sofia", "D22": "Pesos Check", "E22": 100, "D23": "pesos check", "E23": 100}
    lista = revisar(base.con, xlsx(celdas))
    assert [f.repetida for f in lista.filas if f.nombre.lower() == "pesos check"] == [True, True]


def test_repetida_deja_de_serlo_si_una_pasa_a_ignorar(base):
    lista = revisar(base.con, xlsx({"C1": "Nafta", "D1": 100, "C2": "Nafta", "D2": 100}))
    lista.cambiar_tipo(lista.filas[0].indice, "ignorar")
    assert [f.repetida for f in lista.filas] == [False, False]


def test_repetida_no_cuenta_a_las_incompletas(base):
    # Dos filas incompletas con el mismo nombre ("Total" sin monto, por ejemplo) no son
    # "repetidas": están en ignorar.
    lista = revisar(base.con, xlsx({"C1": "Nafta", "C3": "Nafta"}))
    assert [f.repetida for f in lista.filas] == [False, False]


# ---------------------------------------------------------------------------
# Aviso de posible gasto compartido (RN-72, CA-56.6)
# ---------------------------------------------------------------------------

AVISO = (
    "¿Es parte de un gasto compartido? Si es así, ignorala y marcá el gasto como compartido "
    "después."
)


def test_internet_de_sofia_muestra_el_aviso_y_las_demas_no(base):
    # CA-56.6.
    lista = revisar(base.con)
    internet = fila(lista, "Internet", 23)
    assert AVISO in lista.notas(internet)
    assert (internet.tipo, internet.persona, internet.tildada) == ("me_deben", base.sofia, True)
    assert lista.puede_confirmar() is True
    assert lista.notas(fila(lista, "Prestamo MP")) == []
    assert lista.notas(fila(lista, "tacones chiqui baby")) == []


def test_el_aviso_desaparece_si_la_fila_de_gasto_pasa_a_ignorar_o_se_destilda(base):
    # CA-56.6.
    lista = revisar(base.con)
    gasto, deuda = fila(lista, "Internet", 5), fila(lista, "Internet", 23)
    lista.cambiar_tipo(gasto.indice, "ignorar")
    assert deuda.aviso_compartido is False
    lista.cambiar_tipo(gasto.indice, "fijo")
    assert deuda.aviso_compartido is True
    lista.cambiar_tilde(gasto.indice, False)
    assert deuda.aviso_compartido is False
    lista.cambiar_tilde(gasto.indice, True)
    assert deuda.aviso_compartido is True


def test_el_aviso_vuelve_si_el_mes_tiene_un_gasto_internet(base):
    # CA-56.6: pasando la fila 5 a ignorar, si 2026-10 tiene "Internet", el aviso aparece.
    gastos.agregar_gasto(base.con, base.mes_id, "Internet", base.varios, 100, "unico")
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Internet", 5).indice, "ignorar")
    assert fila(lista, "Internet", 23).aviso_compartido is True


def test_servicios_luz_gas_muestra_el_aviso_por_servicios(base):
    # CA-56.6: nueva fila "Servicios Luz Gas | 35500" en el bloque de Sofía.
    celdas = insertar_fila(celdas_planilla(), 23, {"D": "Servicios Luz Gas", "E": 35500})
    lista = revisar(base.con, xlsx(celdas))
    nueva = fila(lista, "Servicios Luz Gas")
    assert (nueva.tipo, nueva.persona) == ("me_deben", base.sofia)
    assert nueva.aviso_compartido is True
    assert AVISO in lista.notas(nueva)


def test_pesos_check_no_coincide_con_pesos_checks_en_el_archivo(base):
    # CA-56.6: solo "Pesos checks" en el archivo -> sin aviso.
    celdas = insertar_fila(celdas_planilla(), 23, {"D": "Pesos Check", "E": 142406})
    celdas["C30"], celdas["D30"] = "Pesos checks", 1000
    lista = revisar(base.con, xlsx(celdas))
    assert fila(lista, "Pesos Check").aviso_compartido is False
    assert fila(lista, "Pesos checks").tipo == "fijo"


def test_pesos_check_no_coincide_con_pesos_checks_en_el_mes(base):
    # CA-56.6: solo "Pesos checks" en el mes -> sin aviso.
    gastos.agregar_gasto(base.con, base.mes_id, "Pesos checks", base.varios, 100, "fijo")
    celdas = insertar_fila(celdas_planilla(), 23, {"D": "Pesos Check", "E": 142406})
    lista = revisar(base.con, xlsx(celdas))
    assert fila(lista, "Pesos Check").aviso_compartido is False


def test_el_aviso_cuenta_gastos_del_mes_destino_de_cualquier_tipo(base):
    # RN-72: "un gasto del mes destino" (los que ya tiene).
    gastos.agregar_gasto(base.con, base.mes_id, "Prestamo MP personal", base.varios, 100, "unico")
    lista = revisar(base.con)
    assert fila(lista, "Prestamo MP").aviso_compartido is True


def test_el_aviso_en_un_mes_a_crear_usa_fijos_copiados_y_cuotas_activas(base):
    # RN-72: si el mes se va a crear, "los que va a tener al crearse" (RN-09).
    gastos.agregar_gasto(base.con, base.mes_id, "Prestamo MP", base.varios, 100, "fijo")
    gastos.agregar_gasto(base.con, base.mes_id, "Unico Marsu", base.varios, 100, "unico")
    cuotas.crear_plan(base.con, "tacones plan", base.varios, None, 100, 6, 2026, 9, hoy=HOY)
    celdas = {**celdas_planilla(), "C30": "Unico Marsu", "D30": 5}
    lista = revisar(base.con, xlsx(celdas))
    lista.cambiar_tipo(fila(lista, "Unico Marsu").indice, "me_deben")
    lista.editar_fila(fila(lista, "Unico Marsu").indice, "me_deben", "Unico Marsu", 500, persona=base.marsu)
    # Destino 2026-11: "Prestamo MP" (fijo) se copia -> aviso; "Unico Marsu" (único) no se copia.
    # "tacones chiqui baby" no coincide con "tacones plan" (la cuota sí se genera).
    lista.cambiar_mes_destino(2026, 11)
    assert fila(lista, "Prestamo MP").aviso_compartido is True
    assert fila(lista, "tacones chiqui baby").aviso_compartido is False
    lista.cambiar_tipo(fila(lista, "Unico Marsu").indice, "ignorar")
    lista.cambiar_tipo(fila(lista, "Unico Marsu").indice, "me_deben")
    lista.editar_fila(fila(lista, "Unico Marsu").indice, "me_deben", "tacones", 500, persona=base.marsu)
    assert fila(lista, "tacones", 30).aviso_compartido is True  # coincide con el plan "tacones plan"


def test_la_fila_me_deben_no_avisa_contra_otra_fila_me_deben_ni_ignorada(base):
    # RN-72: solo contra gastos fijos, únicos y cuotas tildados.
    celdas = {"D21": "Deudas sofia", "D22": "Gas", "E22": 100, "D23": "Gas natural", "E23": 100}
    lista = revisar(base.con, xlsx(celdas))
    assert not any(f.aviso_compartido for f in lista.filas)
    # Una "ignorar" con el mismo nombre tampoco.
    lista2 = revisar(base.con, xlsx({**celdas, "C30": "Total Gas", "D30": 1}))
    assert not any(f.aviso_compartido for f in lista2.filas)


def test_el_aviso_se_recalcula_al_cambiar_el_nombre(base):
    # RN-72: "Se recalcula cuando cambian nombres".
    lista = revisar(base.con)
    prestamo = fila(lista, "Prestamo MP")
    lista.editar_fila(prestamo.indice, "me_deben", "internet banda", 2000000, persona=base.sofia)
    assert prestamo.aviso_compartido is True
    lista.editar_fila(prestamo.indice, "me_deben", "Prestamo", 2000000, persona=base.sofia)
    assert prestamo.aviso_compartido is False


@pytest.mark.parametrize(
    "a,b,esperado",
    [
        ("Internet", "Internet", True),
        ("Servicios Luz Gas", "Servicios", True),
        ("Servicios", "Servicios Luz Gas", True),
        ("Pesos Check", "Pesos checks", False),
        ("Prestamo MP", "Alquiler", False),
        ("Teléfono", "telefono", True),
        ("  INTERNET ", "internet", True),
        ("Internet   hogar", "internet hogar", True),
        ("Luz", "Luz y Gas", True),
        ("Internet hogar", "Internet oficina", False),
        ("Luz", "Luces", False),
        ("", "Luz", False),
        ("Luz", "", False),
        ("", "", False),
        ("   ", "   ", False),
    ],
)
def test_coinciden_regla_de_palabras_enteras(a, b, esperado):
    # RN-72/RN-67: iguales, o todas las palabras del más corto enteras en el más largo.
    assert coinciden(a, b) is esperado
    assert coinciden(b, a) is esperado  # simétrica


# ---------------------------------------------------------------------------
# Pagado (RN-69, CA-57.5)
# ---------------------------------------------------------------------------

LUZ = {"C1": "Gasto", "D1": "Monto", "E1": "Pagado", "C2": "Luz", "D2": 10000, "E2": 12000}


def test_pagado_mayor_que_el_monto_es_un_error_y_no_se_confirma(base):
    # CA-57.5.
    lista = revisar(base.con, xlsx(LUZ))
    luz = fila(lista, "Luz")
    assert lista.errores(luz) == ["El pagado ($ 12.000) es mayor que el monto ($ 10.000)."]
    assert lista.puede_confirmar() is False


def test_subir_el_monto_a_12000_resuelve_el_error(base):
    # CA-57.5.
    lista = revisar(base.con, xlsx(LUZ))
    luz = fila(lista, "Luz")
    assert lista.editar_fila(luz.indice, "fijo", "Luz", 1200000, pagado_cent=1200000) == {}
    assert lista.errores(luz) == [] and lista.puede_confirmar() is True


def test_bajar_el_pagado_a_4000_resuelve_el_error(base):
    # CA-57.5: pendiente 6.000.
    lista = revisar(base.con, xlsx(LUZ))
    luz = fila(lista, "Luz")
    assert lista.editar_fila(luz.indice, "fijo", "Luz", 1000000, pagado_cent=400000) == {}
    assert lista.puede_confirmar() is True


def test_el_dialogo_no_acepta_pagado_mayor_que_el_monto(base):
    # RN-68: los errores del diálogo incluyen el pagado.
    lista = revisar(base.con, xlsx(LUZ))
    luz = fila(lista, "Luz")
    assert lista.editar_fila(luz.indice, "fijo", "Luz", 1000000, pagado_cent=1200000) == {
        "pagado": "El pagado ($ 12.000) es mayor que el monto ($ 10.000)."
    }


def test_pagado_negativo_es_un_error(base):
    # CA-57.5: −100.
    contenido = xlsx({**LUZ, "E2": -100})
    lista = revisar(base.con, contenido)
    assert lista.errores(fila(lista, "Luz")) == ["El pagado no puede ser negativo."]
    assert lista.puede_confirmar() is False


def test_pagado_cero_se_importa_sin_pagos_y_sin_error(base):
    # CA-57.5.
    lista = revisar(base.con, xlsx({**LUZ, "E2": 0}))
    assert lista.errores(fila(lista, "Luz")) == []
    assert lista.puede_confirmar() is True


def test_pagado_igual_al_monto_no_es_error(base):
    lista = revisar(base.con, xlsx({**LUZ, "E2": 10000}))
    assert lista.errores(fila(lista, "Luz")) == []


def test_pagado_mayor_por_pocos_centavos_se_muestra_con_centavos(base):
    # RN-69 (O70): si los dos montos redondeados se ven iguales, se muestran con centavos.
    lista = revisar(base.con, xlsx({**LUZ, "D2": 1234.5, "E2": 1234.51}))
    assert lista.errores(fila(lista, "Luz")) == [
        "El pagado ($ 1.234,51) es mayor que el monto ($ 1.234,50)."
    ]
    lista = revisar(base.con, xlsx({**LUZ, "D2": 1234.5, "E2": 1234.56}))
    assert lista.errores(fila(lista, "Luz")) == [
        "El pagado ($ 1.234,56) es mayor que el monto ($ 1.234,50)."
    ]


def test_planilla_con_e11_pagado_monotributo_muestra_el_error_de_pagado(base):
    # CA-51.5 (error en la revisión): Monotributo pagado 66.021 vs monto 66.020,12.
    lista = revisar(base.con, planilla_con({"E11": "Pagado"}))
    assert lista.errores(fila(lista, "Monotributo 66.020,12")) == [
        "El pagado ($ 66.021) es mayor que el monto ($ 66.020)."
    ]


def test_el_pagado_no_se_valida_en_filas_me_deben_ni_sueldo_ni_ignoradas(base):
    # RN-69: solo gastos fijos, únicos y cuotas.
    lista = revisar(base.con, planilla_con({"E11": "Pagado"}))
    for nombre in ("Prestamo MP", "Total"):
        f = [x for x in lista.filas if x.nombre == nombre][0]
        assert lista.errores(f) == [], nombre
    assert lista.errores(fila(lista, "Monotributo 66.020,12")) != []
    lista.cambiar_tipo(fila(lista, "Monotributo 66.020,12").indice, "me_deben")
    assert lista.errores(fila(lista, "Monotributo 66.020,12")) == ["Elegí una persona."]


def test_un_error_de_pagado_en_una_fila_destildada_no_impide_confirmar(base):
    lista = revisar(base.con, xlsx(LUZ))
    lista.cambiar_tilde(fila(lista, "Luz").indice, False)
    assert lista.filas_con_errores() == []


# ---------------------------------------------------------------------------
# Sueldo (RN-70, CA-57.6)
# ---------------------------------------------------------------------------


def test_dos_filas_de_sueldo_dan_el_error_en_las_dos_y_en_el_pie(base):
    # CA-57.6: filas 19 (1.300) y 9 (1.004.917) como sueldo.
    lista = revisar(base.con)
    a = sin_nombre(lista, 19)
    b = [f for f in lista.filas if f.nombre is None and f.monto_cent == 100491700][0]
    lista.cambiar_tipo(a.indice, "sueldo")
    lista.cambiar_tipo(b.indice, "sueldo")
    mensaje = "Marcaste 2 filas como sueldo; dejá una sola."
    assert lista.errores(a) == [mensaje] and lista.errores(b) == [mensaje]
    assert lista.estado_pie() == mensaje
    assert lista.puede_confirmar() is False


def test_tres_filas_de_sueldo_dicen_tres(base):
    lista = revisar(base.con)
    sueltos = [f for f in lista.filas if f.nombre is None]
    for f in sueltos[:3]:
        lista.cambiar_tipo(f.indice, "sueldo")
    assert lista.estado_pie() == "Marcaste 3 filas como sueldo; dejá una sola."


def test_sueldo_destildado_no_cuenta_como_sueldo(base):
    lista = revisar(base.con)
    a, b = sin_nombre(lista, 19), [f for f in lista.filas if f.nombre is None][0]
    lista.cambiar_tipo(a.indice, "sueldo")
    lista.cambiar_tipo(b.indice, "sueldo")
    lista.cambiar_tilde(b.indice, False)
    assert lista.errores(a) == []
    assert lista.puede_confirmar() is True


def test_el_dialogo_acepta_un_sueldo_aunque_haya_otro(base):
    # RN-68: el error de dos sueldos se ve en la lista, no en el diálogo.
    lista = revisar(base.con)
    a, b = sin_nombre(lista, 19), [f for f in lista.filas if f.nombre is None][0]
    lista.cambiar_tipo(a.indice, "sueldo")
    assert lista.editar_fila(b.indice, "sueldo", None, b.monto_cent) == {}
    assert b.tipo == "sueldo"


def test_sueldo_no_necesita_nombre_pero_si_monto(base):
    # RN-70.
    lista = revisar(base.con)
    sueldo_titulo = fila(lista, "Sueldo")  # la fila "Sueldo" no tiene monto
    lista.cambiar_tipo(sueldo_titulo.indice, "sueldo")
    assert lista.errores(sueldo_titulo) == ["Falta el monto."]
    lista.cambiar_tipo(sueldo_titulo.indice, "ignorar")
    suelto = sin_nombre(lista, 19)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    assert lista.errores(suelto) == []


def test_sueldo_con_monto_cero_o_negativo(base):
    lista = revisar(base.con, xlsx({"B1": "Sueldo", "B2": -5}))
    suelto = sin_nombre(lista, 2)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    assert lista.errores(suelto) == ["El monto tiene que ser mayor a 0."]
    assert lista.notas(suelto) == []


def test_el_sueldo_no_exige_categoria_ni_persona(base_sin_varios):
    lista = revisar(base_sin_varios.con)
    suelto = sin_nombre(lista, 19)
    lista.cambiar_tipo(suelto.indice, "sueldo")
    assert lista.errores(suelto) == []


# ---------------------------------------------------------------------------
# Estado del pie, conteo y confirmar (RN-68, CA-57.8, CA-57.9)
# ---------------------------------------------------------------------------


def test_pie_con_sueldo_y_todo_lo_demas(base):
    # CA-57.9: el texto exacto del pie.
    lista = revisar(base.con)
    lista.cambiar_tipo(sin_nombre(lista, 19).indice, "sueldo")
    assert lista.conteo() == {"filas": 10, "gastos": 5, "planes": 1, "me_deben": 3, "sueldo": 1}
    assert lista.estado_pie() == (
        'Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo.'
    )
    assert lista.puede_confirmar() is True


def test_pie_sin_sueldo(base):
    lista = revisar(base.con)
    assert lista.estado_pie() == (
        'Se importan 9 filas: 5 gastos, 1 plan de cuotas y 3 ítems "me deben".'
    )


def test_pie_en_singular(base):
    # RN-68: "mencionando solo lo que hay, en singular o plural".
    lista = revisar(base.con)
    for f in lista.filas:
        lista.cambiar_tilde(f.indice, False)
    lista.cambiar_tilde(fila(lista, "Gym").indice, True)
    assert lista.estado_pie() == "Se importa 1 fila: 1 gasto."
    lista.cambiar_tilde(fila(lista, "Prestamo MP").indice, True)
    assert lista.estado_pie() == 'Se importan 2 filas: 1 gasto y 1 ítem "me deben".'


def test_pie_solo_sueldo(base):
    lista = revisar(base.con)
    for f in lista.filas:
        lista.cambiar_tilde(f.indice, False)
    lista.cambiar_tipo(sin_nombre(lista, 19).indice, "sueldo")
    assert lista.estado_pie() == "Se importa 1 fila: el sueldo."
    assert lista.puede_confirmar() is True


def test_pie_sin_filas_para_importar_todo_destildado(base):
    # CA-57.8.
    lista = revisar(base.con)
    for f in lista.filas:
        lista.cambiar_tilde(f.indice, False)
    assert lista.estado_pie() == "No hay filas para importar."
    assert lista.puede_confirmar() is False


def test_pie_sin_filas_para_importar_todo_ignorado(base):
    # CA-57.8.
    lista = revisar(base.con)
    for f in lista.filas:
        lista.cambiar_tipo(f.indice, "ignorar")
    assert lista.estado_pie() == "No hay filas para importar."
    assert lista.puede_confirmar() is False
    assert lista.conteo() == {"filas": 0, "gastos": 0, "planes": 0, "me_deben": 0, "sueldo": 0}


def test_pie_de_un_excel_sin_filas_completas(base):
    lista = revisar(base.con, xlsx({"C1": "Solo", "C2": "Texto"}))
    assert lista.estado_pie() == "No hay filas para importar."


def test_pie_con_dos_filas_con_errores(base):
    # CA-57.8: texto exacto, plural.
    lista = revisar(base.con)
    for nombre in ("Obra social", "Deuda freezer"):
        lista.cambiar_tipo(fila(lista, nombre).indice, "fijo")
    assert len(lista.filas_con_errores()) == 2
    assert lista.estado_pie() == (
        "Hay 2 filas con errores. Corregilas, ignoralas o destildalas para continuar."
    )
    assert lista.puede_confirmar() is False


def test_pie_con_una_fila_con_errores_en_singular(base):
    # RN-68 pide "mencionando ... singular o plural"; el texto singular no está definido
    # en los requisitos: se verifica que sea el singular natural del plural dado.
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Obra social").indice, "fijo")
    assert lista.estado_pie() == (
        "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar."
    )


def test_pie_se_corrige_ignorando_o_destildando_las_filas_con_error(base):
    lista = revisar(base.con)
    a, b = fila(lista, "Obra social"), fila(lista, "Deuda freezer")
    lista.cambiar_tipo(a.indice, "fijo")
    lista.cambiar_tipo(b.indice, "fijo")
    lista.cambiar_tipo(a.indice, "ignorar")
    lista.cambiar_tilde(b.indice, False)
    assert lista.filas_con_errores() == []
    assert lista.estado_pie().startswith("Se importan 9 filas")
    assert lista.puede_confirmar() is True


def test_los_sueldos_dobles_tienen_prioridad_en_el_pie_sobre_los_errores(base):
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Obra social").indice, "fijo")
    sueltos = [f for f in lista.filas if f.nombre is None]
    lista.cambiar_tipo(sueltos[0].indice, "sueldo")
    lista.cambiar_tipo(sueltos[1].indice, "sueldo")
    assert lista.estado_pie() == "Marcaste 2 filas como sueldo; dejá una sola."


def test_el_pie_cuenta_cuotas_y_gastos_unicos(base):
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Gym").indice, "unico")
    assert lista.conteo()["gastos"] == 5  # Gym sigue contando como gasto
    assert lista.conteo()["planes"] == 1


def test_las_filas_con_error_solo_son_las_que_se_importan(base):
    # RN-68: errores de filas destildadas o ignoradas no se muestran.
    lista = revisar(base.con)
    obra = fila(lista, "Obra social")
    assert lista.errores(obra) == []
    lista.cambiar_tipo(obra.indice, "fijo")
    lista.cambiar_tilde(obra.indice, False)
    assert lista.errores(obra) == []


# ---------------------------------------------------------------------------
# Montos enormes (O61) y número en la columna de pagado sin monto (O62)
# ---------------------------------------------------------------------------


def test_o61_monto_enorme_da_el_error_de_validar_centavos(base):
    # O61: 10^17 pesos -> 10^19 centavos. El error es el de validar_centavos.
    lista = revisar(base.con, xlsx({"C1": "Gigante", "D1": 10**17}))
    f = lista.filas[0]
    assert f.monto_cent == 10**19
    assert lista.errores(f) == ["El monto es demasiado grande."]
    assert lista.puede_confirmar() is False


@pytest.mark.parametrize(
    "monto,hay_error",
    [(999999999999, False), (999999999999.99, True), (1000000000000, True)],
)
def test_o61_borde_del_monto_maximo(base, monto, hay_error):
    # 999.999.999.999 es el máximo; un centavo más es demasiado.
    lista = revisar(base.con, xlsx({"C1": "Casi", "D1": monto}))
    errores = lista.errores(lista.filas[0])
    assert (errores == ["El monto es demasiado grande."]) is hay_error
    assert errores in ([], ["El monto es demasiado grande."])


def test_o61_monto_enorme_corregido_en_el_dialogo_y_monto_enorme_escrito_a_mano(base):
    lista = revisar(base.con, xlsx({"C1": "Gigante", "D1": 10**17}))
    f = lista.filas[0]
    assert lista.editar_fila(f.indice, "fijo", "Gigante", 10**19) == {
        "monto": "El monto es demasiado grande."
    }
    assert lista.editar_fila(f.indice, "fijo", "Gigante", 5000) == {}
    assert lista.puede_confirmar() is True


def test_o61_monto_enorme_en_filas_que_no_se_importan_no_da_error(base):
    lista = revisar(base.con, xlsx({"C1": "Gigante", "D1": 10**17}))
    lista.cambiar_tilde(lista.filas[0].indice, False)
    assert lista.filas_con_errores() == []


@pytest.mark.parametrize("tipo", ["me_deben", "cuota", "sueldo", "unico"])
def test_o61_monto_enorme_en_cualquier_tipo(base, tipo):
    lista = revisar(base.con, xlsx({"C1": "Gigante 1/3", "D1": 10**17}))
    f = lista.filas[0]
    lista.cambiar_tipo(f.indice, tipo)
    assert "El monto es demasiado grande." in lista.errores(f)


def test_o61_monto_enorme_en_pagado_da_error_de_pagado_mayor(base):
    # Con monto razonable y un pagado enorme: "el pagado es mayor que el monto".
    contenido = xlsx({**LUZ, "E2": 10**17})
    lista = revisar(base.con, contenido)
    errores = lista.errores(fila(lista, "Luz"))
    assert len(errores) == 1 and errores[0].startswith("El pagado ($ ")


def test_o62_numero_en_pagado_de_una_fila_sin_monto_se_descarta(base):
    # RN-63/64 (O62): "Luz" sin monto y un 3 bajo "Pagado": el pagado se descarta.
    lista = revisar(base.con, xlsx({"C1": "Gasto", "D1": "Monto", "E1": "Pagado", "C2": "Luz", "E2": 3}))
    luz = fila(lista, "Luz")
    assert luz.monto_cent is None and luz.pagado_cent is None
    assert luz.tipo == "ignorar" and luz.incompleta
    assert lista.notas(luz) == ["Falta el monto. Se ignora."]
    lista.cambiar_tipo(luz.indice, "fijo")
    assert lista.errores(luz) == ["Falta el monto."]
    # Al completar el monto no aparece ningun error de pagado (CA-51.5).
    assert lista.editar_fila(luz.indice, "fijo", "Luz", 100, pagado_cent=luz.pagado_cent) == {}


# ---------------------------------------------------------------------------
# hubo_cambios (RN-76: solo acciones del usuario)
# ---------------------------------------------------------------------------


def test_al_armar_la_lista_no_hay_cambios(base):
    # Lo que la app hace sola (tipos, marcas, tildes) no cuenta.
    assert revisar(base.con).hubo_cambios is False
    cargar_primera_importacion(base)
    assert revisar(base.con).hubo_cambios is False


def test_consultar_no_marca_cambios(base):
    # Ninguna consulta cuenta como cambio.
    lista = revisar(base.con)
    lista.bloques()
    lista.incompletas()
    lista.conteo()
    lista.estado_pie()
    lista.puede_confirmar()
    lista.filas_con_errores()
    lista.meses_posibles()
    lista.aviso_mes()
    lista.sueldo_actual_cent()
    lista.nuevas_en_uso()
    lista.cantidad_sueldos()
    for f in lista.filas:
        lista.errores(f)
        lista.notas(f)
        lista.categoria_de(f)
    assert lista.hubo_cambios is False


ACCIONES = {
    "cambiar_tipo": lambda l, b: l.cambiar_tipo(fila(l, "Gym").indice, "unico"),
    "cambiar_tilde": lambda l, b: l.cambiar_tilde(fila(l, "Gym").indice, False),
    "cambiar_cobrado": lambda l, b: l.cambiar_cobrado(fila(l, "Prestamo MP").indice, True),
    "editar_fila": lambda l, b: l.editar_fila(fila(l, "Gym").indice, "fijo", "Gimnasio", 100),
    "restaurar_fila": lambda l, b: l.restaurar_fila(fila(l, "Gym").indice),
    "agregar_categoria": lambda l, b: l.agregar_categoria("Importado"),
    "agregar_persona": lambda l, b: l.agregar_persona("Juan"),
    "cambiar_categoria_defecto": lambda l, b: l.cambiar_categoria_defecto(b.vivienda),
    "tildar_bloque": lambda l, b: l.tildar_bloque("Deudas"),
    "destildar_bloque": lambda l, b: l.destildar_bloque("Deudas"),
    "cambiar_bloque": lambda l, b: l.cambiar_bloque("Deudas", tipo="unico"),
    "cambiar_mes_destino": lambda l, b: l.cambiar_mes_destino(2026, 11),
}


@pytest.mark.parametrize("accion", sorted(ACCIONES))
def test_cada_accion_del_usuario_marca_hubo_cambios(base, accion):
    # RN-76: cambiar un tipo, un tilde (también cobrado), un dato, la categoría por defecto,
    # el mes, una acción de bloque, o agregar una categoría o persona nueva.
    lista = revisar(base.con)
    ACCIONES[accion](lista, base)
    assert lista.hubo_cambios is True


def test_acciones_que_fallan_no_marcan_cambios(base):
    # Una acción rechazada no cambió nada.
    lista = revisar(base.con)
    with pytest.raises(ErrorDeValidacion):
        lista.cambiar_tilde(fila(lista, "Tarjetas de Credito").indice, True)
    with pytest.raises(ErrorDeValidacion):
        lista.agregar_persona("Sofía")
    with pytest.raises(ErrorDeValidacion):
        lista.agregar_categoria("")
    with pytest.raises(ErrorDeValidacion):
        lista.cambiar_mes_destino(2030, 1)
    with pytest.raises(ErrorDeValidacion):
        lista.cambiar_bloque("Deudas", tipo="cuota")
    assert lista.editar_fila(fila(lista, "Gym").indice, "fijo", "", 100) != {}
    assert lista.hubo_cambios is False


def test_hubo_cambios_sigue_verdadero_aunque_el_usuario_deshaga(base):
    # RN-76: "qué cuenta como cambio" es haber actuado, no que el resultado difiera.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.cambiar_tilde(gym.indice, False)
    lista.cambiar_tilde(gym.indice, True)
    assert lista.hubo_cambios is True


# ---------------------------------------------------------------------------
# La revisión no escribe en la base
# ---------------------------------------------------------------------------


def test_la_revision_no_escribe_en_la_base(base):
    # La lista solo LEE: ninguna acción cambia las tablas (RN-76, guardado en 8a-4).
    cargar_primera_importacion(base)
    antes = foto_de_la_base(base.con)
    cambios_antes = base.con.total_changes
    lista = revisar(base.con, planilla_con(COBRADO))
    lista.cambiar_tipo(sin_nombre(lista, 19).indice, "sueldo")
    lista.cambiar_mes_destino(2026, 11)
    lista.agregar_persona("Juan")
    lista.agregar_categoria("Importado")
    lista.cambiar_categoria_defecto(Nueva("Importado"))
    lista.cambiar_bloque("Deudas sofia", tipo="unico", categoria=base.servicios)
    lista.tildar_bloque("Gasto del Mes")
    lista.editar_fila(fila(lista, "Gym").indice, "cuota", "Gym", 100, cuota_actual=1, cuota_total=2)
    lista.restaurar_fila(fila(lista, "Gym").indice)
    lista.estado_pie()
    assert foto_de_la_base(base.con) == antes
    assert base.con.total_changes == cambios_antes


# ---------------------------------------------------------------------------
# Casos borde de datos
# ---------------------------------------------------------------------------


def test_hoja_sin_ninguna_fila(base):
    # Una hoja con solo fechas no tiene filas: la lista queda vacía y no se rompe.
    lista = revisar(base.con, xlsx({"C1": date(2026, 1, 1)}))
    assert lista.filas == [] and lista.bloques() == [] and lista.incompletas() == []
    assert lista.estado_pie() == "No hay filas para importar."
    assert lista.puede_confirmar() is False


def test_nombre_con_caracteres_raros(base):
    lista = revisar(base.con, xlsx({"C1": "Ñandú ☕ \"comillas\" 'x' <b>", "D1": 1000}))
    f = lista.filas[0]
    assert f.tipo == "fijo" and lista.errores(f) == []


def test_nombre_larguisimo(base):
    lista = revisar(base.con, xlsx({"C1": "x" * 5000, "D1": 1000}))
    assert lista.filas[0].tipo == "fijo"
    assert lista.notas(lista.filas[0]) == []


def test_muchas_filas_se_arman_en_poco_tiempo(base):
    # 2.000 gastos con el mes lleno de gastos: las marcas no hacen la lista inusable.
    celdas = {}
    for i in range(1, 2001):
        celdas[f"C{i}"] = f"Gasto {i}"
        celdas[f"D{i}"] = 100 + i
    t0 = time.perf_counter()
    lista = revisar(base.con, xlsx(celdas))
    lista.cambiar_tipo(lista.filas[0].indice, "unico")
    duracion = time.perf_counter() - t0
    assert len(lista.filas) == 2000
    assert duracion < 20


def test_cuota_con_mas_de_600_cuotas_da_error_en_la_revision(base):
    # RN-29 (crear_plan rechaza más de 600 cuotas): si la revisión lo deja pasar, el error
    # recién aparece al guardar y tira abajo toda la importación (todo o nada, RN-76).
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    errores = lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=1, cuota_total=601)
    assert errores != {}


def test_cuota_con_numeros_enormes_en_el_nombre_no_cuelga_la_nota(base):
    # RN-66 regla 3 + RN-71: "Algo 10000000/10000000" cumple 1 <= n <= N. Calcular la nota
    # (primera cuota = mes destino - (n-1) meses) no puede tardar: la cuenta es un bucle.
    lista = revisar(base.con, xlsx({"C1": "Algo 10000000/10000000", "D1": 1000}))
    f = lista.filas[0]
    t0 = time.perf_counter()
    lista.notas(f)
    duracion = time.perf_counter() - t0
    assert duracion < 1, f"{duracion:.1f} s"


def test_cuota_con_numeros_enormes_no_da_una_nota_con_anio_imposible(base):
    # La nota no puede decir "primera Julio -6307".
    lista = revisar(base.con, xlsx({"C1": "Algo 100000/100000", "D1": 1000}))
    f = lista.filas[0]
    assert "-" not in " ".join(lista.notas(f))


# ---------------------------------------------------------------------------
# importar_excel.py: lectura recortada de leer_hoja (O58)
# ---------------------------------------------------------------------------


def con_relleno(celdas, relleno, nombre_hoja="Octubre", **opciones):
    """El .xlsx de `celdas` con una celda vacía pero con formato (relleno) en `relleno`."""
    libro = armar_libro({nombre_hoja: celdas}, **opciones)
    libro[nombre_hoja][relleno].fill = PatternFill("solid", fgColor="FFFF00")
    return a_bytes(libro)


def hoja_completa(contenido):
    """Todo lo que lee leer_hoja, para comparar dos lecturas."""
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    return (
        [
            (f.fila_excel, f.columna, f.nombre, f.monto_cent, f.pagado_cent, f.cobrado,
             f.bloque, f.es_titulo, f.monto_es_suma)
            for f in hoja.filas
        ],
        hoja.formulas_sin_valor,
        hoja.ejemplo_formula,
    )


@pytest.mark.parametrize("celda", ["A100000", "D100000", "T100000", "AZ5000", "T20"])
def test_o58_relleno_lejano_en_cualquier_columna_es_rapido(celda):
    # O58: una celda con formato lejos (incluida la columna T) no tiene que demorar.
    contenido = con_relleno({"C3": "Luz", "D3": 1000}, celda)
    t0 = time.perf_counter()
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    duracion = time.perf_counter() - t0
    assert len(hoja.filas) == 1
    assert duracion < 3, f"{celda}: {duracion:.1f} s"


@pytest.mark.parametrize("celda", ["T100000", "A100000", "Z50", "T20"])
def test_o58_el_relleno_lejano_no_cambia_ningun_resultado(celda):
    # O58: la planilla de prueba lee igual con y sin formato lejos.
    assert hoja_completa(con_relleno(celdas_planilla(), celda)) == hoja_completa(planilla_prueba())


def test_o58_hoja_vacia_con_formato_lejos_es_rapida():
    # O58: una hoja sin ningún valor pero con formato en T100000. Antes de recortar tardaba
    # ~7 s; el recorte no tiene que dejar este caso sin cubrir.
    libro = armar_libro({"Octubre": {}})
    libro["Octubre"]["T100000"].fill = PatternFill("solid", fgColor="FFFF00")
    contenido = a_bytes(libro)
    t0 = time.perf_counter()
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    duracion = time.perf_counter() - t0
    assert hoja.filas == [] and hoja.sin_datos
    assert duracion < 3, f"{duracion:.1f} s"


def test_o58_hoja_completamente_vacia():
    hoja = abrir_libro(xlsx({})).leer_hoja("Octubre")
    assert hoja.filas == [] and hoja.formulas_sin_valor == 0 and hoja.ejemplo_formula is None


def test_o58_formula_sin_valor_mas_alla_de_los_datos_se_cuenta():
    # El recorte llega hasta la última celda con fórmula aunque no tenga valor guardado.
    contenido = xlsx({"C3": "Luz", "D3": 1000, "Z50": "=1+1"})
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    assert (hoja.formulas_sin_valor, hoja.ejemplo_formula) == (1, "Z50")
    assert [f.nombre for f in hoja.filas] == ["Luz"]


def test_o58_formula_sin_valor_en_una_fila_debajo_y_en_una_columna_a_la_derecha():
    contenido = xlsx({"C3": "Luz", "D3": 1000, "C400": "=A1", "AA3": "=2*3"})
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    assert hoja.formulas_sin_valor == 2
    assert hoja.ejemplo_formula == "AA3"  # la primera en orden de lectura (filas primero)


def test_o58_hoja_de_solo_formulas_sin_valor():
    hoja = abrir_libro(xlsx({"D9": "=100+200", "F2": "=1"})).leer_hoja("Octubre")
    assert hoja.filas == [] and hoja.formulas_sin_valor == 2


def test_o58_valores_en_filas_y_columnas_ocultas_lejos_se_leen():
    contenido = xlsx(
        {"C3": "Luz", "D3": 1000, "H300": "Gas", "I300": 2000},
        filas_ocultas={"Octubre": [300]},
    )
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    assert resumen_filas(hoja) == [(3, 3, "Luz", 100000), (300, 8, "Gas", 200000)]


def test_o58_columna_oculta_lejos_se_lee():
    libro = armar_libro({"Octubre": {"C3": "Luz", "D3": 1000, "Q3": "Gas", "R3": 2000}})
    libro["Octubre"].column_dimensions["Q"].hidden = True
    hoja = abrir_libro(a_bytes(libro)).leer_hoja("Octubre")
    assert [f.nombre for f in hoja.filas] == ["Luz", "Gas"]


def test_o58_combinadas_que_se_extienden_mas_alla_de_los_datos():
    # Un título combinado D21:K21 cubre columnas donde no hay nada, y hay otra combinada
    # lejos (H30:K40) sin valores: el resultado es el mismo que sin combinar.
    libro = armar_libro(
        {"Octubre": celdas_planilla()}, combinadas={"Octubre": ["D21:K21", "H30:K40"]}
    )
    assert hoja_completa(a_bytes(libro)) == hoja_completa(planilla_prueba())


def test_o58_combinada_vertical_con_filas_debajo_del_ultimo_dato():
    # Una combinada en una columna sin datos (G1:G40) llega más abajo que el último valor.
    libro = armar_libro({"Octubre": celdas_planilla()}, combinadas={"Octubre": ["G1:G40"]})
    assert hoja_completa(a_bytes(libro)) == hoja_completa(planilla_prueba())


def test_o58_celdas_con_valor_que_cuentan_como_vacias_mas_alla_de_los_datos():
    # Una fecha, un espacio y un error de Excel lejos agrandan la grilla pero no crean filas.
    contenido = xlsx(
        {"C3": "Luz", "D3": 1000, "M80": date(2026, 1, 1), "N90": "   ", "O95": "#DIV/0!"}
    )
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    assert resumen_filas(hoja) == [(3, 3, "Luz", 100000)]


def test_o58_bloque_se_corta_igual_con_contenido_vacio_debajo():
    # El bloque de "Gasto" termina en la primera fila totalmente vacía, aunque más abajo
    # haya celdas que cuentan como vacías (fecha) o formato.
    contenido = con_relleno(
        {"C1": "Gasto", "C2": "Luz", "D2": 5, "C4": "Gas", "D4": 6, "Z60": date(2026, 1, 1)},
        "T100",
    )
    hoja = abrir_libro(contenido).leer_hoja("Octubre")
    assert [(f.nombre, f.bloque) for f in hoja.filas] == [
        ("Gasto", None), ("Luz", "Gasto"), ("Gas", None)
    ]


def test_o58_lista_de_revision_igual_con_y_sin_relleno(base):
    # De punta a punta: la lista de revisión no cambia por el formato lejano.
    con_formato = revisar(base.con, con_relleno(celdas_planilla(), "T100000"))
    sin_formato = revisar(base.con)
    resumir = lambda l: [  # noqa: E731
        (f.nombre, f.monto_cent, f.pagado_cent, f.tipo, f.tildada, f.ya_existe, f.bloque)
        for f in l.filas
    ]
    assert resumir(con_formato) == resumir(sin_formato)
    assert con_formato.estado_pie() == sin_formato.estado_pie()


# ---------------------------------------------------------------------------
# Ronda 33: bordes de cuotas tras corregir BUG-29 a BUG-35
# ---------------------------------------------------------------------------

DEMASIADO = {"cuota": "La cantidad de cuotas es demasiado grande."}


@pytest.mark.parametrize("total,hay_error", [(599, False), (600, False), (601, True), (10**9, True)])
def test_cantidad_de_cuotas_borde_600_y_601(base, total, hay_error):
    # RN-29 / BUG-33: hasta 600 cuotas se acepta; más, con el mismo texto de crear_plan.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    errores = lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=1, cuota_total=total)
    assert errores == ({} if not hay_error else DEMASIADO)


@pytest.mark.parametrize("n", [0, 700, -1])
def test_cuota_actual_invalida_con_cantidad_mayor_a_600(base, n):
    # Con cantidad > 600 siempre hay error y nunca hay nota (no se cuelga ni inventa años).
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.cambiar_tipo(gym.indice, "cuota")
    gym.cuota_actual, gym.cuota_total = n, 601
    assert lista.errores(gym) != []
    assert lista.notas(gym) == []


@pytest.mark.parametrize(
    "nombre,tipo",
    [("Algo 600/600", "cuota"), ("Algo 1/600", "cuota"), ("Algo 1/601", "fijo"), ("Algo 601/601", "fijo")],
)
def test_n_sobre_N_en_el_nombre_con_N_en_el_borde_de_600(base, nombre, tipo):
    # BUG-33: "n/N" con N > 600 no se propone como cuota.
    f = revisar(base.con, xlsx({"C1": nombre, "D1": 1000})).filas[0]
    assert f.tipo == tipo
    if tipo == "fijo":
        assert (f.cuota_actual, f.cuota_total) == (None, None)


def test_nombre_con_numeros_gigantes_queda_fijo_sin_colgarse(base):
    t0 = time.perf_counter()
    lista = revisar(base.con, xlsx({"C1": "Algo 1000000000/1000000000", "D1": 1000}))
    lista.notas(lista.filas[0])
    assert lista.filas[0].tipo == "fijo" and time.perf_counter() - t0 < 1


@pytest.mark.parametrize("actual,total", [(1.5, 3), (1, 2.5), (2.0, 3), (True, 3)])
def test_cuota_actual_o_cantidad_no_enteras_dan_error_y_no_hay_nota(base, actual, total):
    # BUG-30: ambos tienen que ser enteros (un bool no vale).
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    errores = lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=actual, cuota_total=total)
    assert "cuota" in errores


@pytest.mark.parametrize(
    "hoy,actual,total,primera,ultima",
    [
        (date(2026, 2, 10), 15, 24, "Diciembre 2024", "Noviembre 2026"),  # hacia atrás, cruza años
        (date(2026, 10, 14), 1, 24, "Octubre 2026", "Septiembre 2028"),  # hacia adelante
        (date(2026, 1, 5), 2, 3, "Diciembre 2025", "Febrero 2026"),
        (date(2026, 12, 5), 1, 2, "Diciembre 2026", "Enero 2027"),
        (date(2026, 10, 14), 600, 600, "Noviembre 1976", "Octubre 2026"),
    ],
)
def test_nota_de_cuotas_que_cruzan_anios(con, hoy, actual, total, primera, ultima):
    # BUG-34: cuenta con aritmética de meses, sin saltos de año mal contados.
    meses.crear_primer_mes(con, hoy.year, hoy.month, 120000, 160000)
    lista = revisar(con, xlsx({"C1": f"Pago {actual}/{total}", "D1": 1000}), hoy=hoy)
    f = lista.filas[0]
    assert (f.tipo, f.cuota_actual, f.cuota_total) == ("cuota", actual, total)
    assert lista.notas(f) == [
        f"Plan de {total} cuotas: primera {primera}, última {ultima}. "
        f"Se agrega la cuota {actual}/{total} en {nombre_mes_de(hoy)}."
    ]


def nombre_mes_de(hoy):
    from app.logica.formato import nombre_mes

    return nombre_mes(hoy.year, hoy.month)


def test_nota_de_una_sola_cuota_en_singular(base):
    # O72.
    f = revisar(base.con, xlsx({"C1": "Pago 1/1", "D1": 1000})).filas[0]
    lista = revisar(base.con, xlsx({"C1": "Pago 1/1", "D1": 1000}))
    assert lista.notas(lista.filas[0]) == [
        "Plan de 1 cuota: primera Octubre 2026, última Octubre 2026. "
        "Se agrega la cuota 1/1 en Octubre 2026."
    ]


def test_cambiar_mes_en_primer_uso_con_cuota_larga_cruza_anios(con):
    # La nota se recalcula al cambiar el mes, también hacia atrás de varios años.
    lista = revisar(con, xlsx({"C1": "Pago 15/24", "D1": 1000}))
    lista.cambiar_mes_destino(2026, 2)
    assert "primera Diciembre 2024, última Noviembre 2026" in lista.notas(lista.filas[0])[0]
