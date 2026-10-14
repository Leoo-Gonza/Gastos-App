"""Pruebas del paso 8a-4: resumen previo, guardado y resultado de la importación
(app/logica/confirmar_importacion.py).

Cubre RN-69, RN-71 a RN-73 y RN-76 (§4.12) y los CA del Módulo K de este paso:
CA-50.2 (no queda copia del archivo), CA-55.x (mes destino), CA-56.4 (segunda importación),
CA-57.1, 57.2, 57.4 (todo o nada), 57.9 (resumen previo), 57.10 a 57.12 (resultado y pantalla).
También O67 (categoría o persona archivada / inexistente elegida en editar_fila).

Base de prueba: la del Módulo K (hoy = 2026-10-14; existe solo 2026-10 con sueldo 1.200,
cotización 1.600 y "Alquiler" 260.000 en Vivienda; personas Sofía y Marsu; categoría
"Varios"). Los .xlsx los arma tests/ayudantes_excel.py con datos inventados.
"""

import copy
import hashlib
import os
from datetime import date
from types import SimpleNamespace

import pytest

from app.logica import (
    catalogos,
    confirmar_importacion,
    cuotas,
    gastos,
    me_deben,
    meses,
    pagos,
    resumen,
)
from app.logica.confirmar_importacion import (
    MENSAJE_ERROR,
    Resultado,
    confirmar,
    resumen_previo,
    texto_resultado,
)
from app.logica.errores import ErrorDeValidacion
from tests.ayudantes import insertar_mes
from tests.ayudantes_excel import celdas_planilla, planilla_con, planilla_prueba, xlsx
from tests.test_revision_importacion import (
    HOY,
    cargar_primera_importacion,
    fila,
    foto_de_la_base,
    revisar,
    sin_nombre,
)

# ---------------------------------------------------------------------------
# Ayudantes
# ---------------------------------------------------------------------------


def _ids_categorias(con):
    return {c["nombre"]: c["id"] for c in catalogos.listar(con, catalogos.CATEGORIAS)}


@pytest.fixture
def base(con, mes_id):
    """La base del Módulo K: 2026-10 con Alquiler (Vivienda), Sofía, Marsu y Varios."""
    ids = _ids_categorias(con)
    varios = catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    gastos.agregar_gasto(con, mes_id, "Alquiler", ids["Vivienda"], 26000000, "fijo")
    return SimpleNamespace(
        con=con, mes_id=mes_id, varios=varios, vivienda=ids["Vivienda"],
        servicios=ids["Servicios"], salud=ids["Salud"], sofia=sofia, marsu=marsu,
    )


@pytest.fixture
def base_vacia(con):
    """Sin meses (primer uso), con la categoría Varios y las personas Sofía y Marsu."""
    varios = catalogos.crear(con, catalogos.CATEGORIAS, "Varios")
    sofia = catalogos.crear(con, catalogos.PERSONAS, "Sofía")
    marsu = catalogos.crear(con, catalogos.PERSONAS, "Marsu")
    return SimpleNamespace(con=con, varios=varios, sofia=sofia, marsu=marsu)


def lista_con_sueldo(con, contenido=None):
    """La lista de planilla-prueba.xlsx con la fila 19 (1.300) marcada como sueldo (CA-57.1)."""
    lista = revisar(con, contenido)
    lista.cambiar_tipo(sin_nombre(lista, 19).indice, "sueldo")
    return lista


def solo(lista, *nombres_o_filas):
    """Destilda todo y tilda solo las filas indicadas (por (nombre, fila Excel) o índice)."""
    for f in lista.filas:
        if f.tipo != "ignorar":
            lista.cambiar_tilde(f.indice, False)
    for nombre, fila_excel in nombres_o_filas:
        f = fila(lista, nombre, fila_excel)
        if f.tipo == "ignorar":
            lista.cambiar_tipo(f.indice, "fijo")
        lista.cambiar_tilde(f.indice, True)


def gastos_de(con, mes_id):
    """[(nombre, monto_cent, tipo, categoría, medio, pagado_cent)] de un mes, en orden."""
    return [
        (g["nombre"], g["monto_cent"], g["tipo"], g["categoria"], g["medio_pago"], g["pagado_cent"])
        for g in gastos.listar_gastos(con, mes_id)
    ]


def mes_por(con, anio, mes):
    return meses.obtener_mes_por_fecha(con, anio, mes)


def gasto_por_nombre(con, mes_id, nombre):
    hallados = [g for g in gastos.listar_gastos(con, mes_id) if g["nombre"] == nombre]
    assert len(hallados) == 1, f"{nombre!r}: {len(hallados)} gastos"
    return hallados[0]


def cantidad(con, tabla):
    return con.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


AVANT = "Avant Service cuota 3/ 3 $41.116,66"


# ---------------------------------------------------------------------------
# CA-57.1: confirmar la lista esperada (mes existente, con sueldo)
# ---------------------------------------------------------------------------


def test_ca_57_1_los_gastos_de_octubre_quedan_como_dice_el_criterio(base):
    # CA-57.1: 2026-10 queda con Alquiler (sin cambios), 5 gastos fijos nuevos, la cuota
    # de Avant, todos en Varios y sin medio de pago, con los pagos de Internet y psicologo.
    resultado = confirmar(lista_con_sueldo(base.con))
    assert resultado.mes_id == base.mes_id
    esperados = {
        "Alquiler": (26000000, "fijo", "Vivienda", 0),
        "Servicios": (8200000, "fijo", "Varios", 0),
        "Internet": (3870000, "fijo", "Varios", 3870000),
        "psicologo": (14000000, "fijo", "Varios", 6000000),
        "Monotributo 66.020,12": (6602012, "fijo", "Varios", 0),
        AVANT: (4111666, "cuota", "Varios", 0),
        "Gym": (5000000, "fijo", "Varios", 0),
    }
    obtenidos = {n: (m, t, c, p) for n, m, t, c, _medio, p in gastos_de(base.con, base.mes_id)}
    assert obtenidos == esperados
    assert all(g[4] is None for g in gastos_de(base.con, base.mes_id))  # sin medio de pago


def test_ca_57_1_totales_pagado_pendiente_y_resumen(base):
    # CA-57.1: gastos 677.837 (67783678), pagado 98.700, pendiente 579.137, sueldo 1.300,
    # USD a cambiar 423,65, ahorro 876,35 (cotización 1.600).
    confirmar(lista_con_sueldo(base.con))
    totales = pagos.totales_del_mes(base.con, base.mes_id)
    assert totales == {"total": 67783678, "pagado": 9870000, "pendiente": 57913678}
    r = resumen.calcular_resumen(base.con, base.mes_id)
    assert r.sueldo_usd == 130000
    assert r.cotizacion == 160000
    assert r.usd_a_cambiar == 42365
    assert r.ahorro_usd == 87635


def test_ca_57_1_me_deben_quedan_no_cobrados_con_la_fecha_de_hoy(base):
    # CA-57.1: Sofía 32.900 (Prestamo MP 20.000 e Internet 12.900) y Marsu 6.785.
    confirmar(lista_con_sueldo(base.con))
    assert me_deben.total_de(base.con, base.sofia) == 3290000
    assert me_deben.total_de(base.con, base.marsu) == 678500
    assert me_deben.total_general(base.con) == 3968500
    items = base.con.execute("SELECT * FROM items_me_deben ORDER BY id").fetchall()
    assert [(i["descripcion"], i["monto_cent"], i["cobrado"], i["fecha"]) for i in items] == [
        ("Prestamo MP", 2000000, 0, "2026-10-14"),
        ("Internet", 1290000, 0, "2026-10-14"),
        ("tacones chiqui baby", 678500, 0, "2026-10-14"),
    ]
    assert [i["persona_id"] for i in items] == [base.sofia, base.sofia, base.marsu]


def test_ca_57_1_pagos_con_la_fecha_de_hoy_y_sin_categorias_ni_personas_nuevas(base):
    # CA-57.1: los pagos tienen la fecha de hoy; no se crea ninguna categoría ni persona.
    antes = (cantidad(base.con, "categorias"), cantidad(base.con, "personas"))
    confirmar(lista_con_sueldo(base.con))
    assert (cantidad(base.con, "categorias"), cantidad(base.con, "personas")) == antes
    fechas = {p["fecha"] for p in base.con.execute("SELECT fecha FROM pagos")}
    assert fechas == {"2026-10-14"}
    assert cantidad(base.con, "pagos") == 2  # Internet (completo) y psicologo (parcial)


def test_ca_57_1_pagado_completo_es_un_solo_pago_y_el_parcial_deja_pendiente(base):
    # RN-69: P = M -> un pago por el monto; 0 < P < M -> pago parcial y pendiente M - P.
    confirmar(lista_con_sueldo(base.con))
    internet = gasto_por_nombre(base.con, base.mes_id, "Internet")
    psico = gasto_por_nombre(base.con, base.mes_id, "psicologo")
    assert [(p["monto_cent"]) for p in pagos.listar_pagos(base.con, internet["id"])] == [3870000]
    assert pagos.pendiente(base.con, internet["id"]) == 0
    assert [(p["monto_cent"]) for p in pagos.listar_pagos(base.con, psico["id"])] == [6000000]
    assert pagos.pendiente(base.con, psico["id"]) == 8000000  # 80.000


def test_ca_57_1_el_plan_de_avant_empieza_en_agosto_y_la_cuota_es_3_de_3(base):
    # CA-57.1 + RN-71: plan de 3 cuotas con primera cuota 2026-08; en octubre es la 3/3,
    # sin medio de pago, y como n = N el plan termina ahí (RN-26).
    confirmar(lista_con_sueldo(base.con))
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert plan["nombre"] == AVANT
    assert (plan["primer_anio"], plan["primer_mes"], plan["cantidad_cuotas"]) == (2026, 8, 3)
    assert plan["monto_cuota_cent"] == 4111666
    assert plan["medio_pago_id"] is None
    assert cuotas.numero_de_cuota(plan, 2026, 10) == 3
    assert cuotas.ultima_cuota(plan) == (2026, 10)
    cuota = gasto_por_nombre(base.con, base.mes_id, AVANT)
    assert cuota["plan_cuotas_id"] == plan["id"]
    # Septiembre y agosto no existen: no se crea ningún mes de más.
    assert [(m["anio"], m["mes"]) for m in meses.listar_meses(base.con)] == [(2026, 10)]


def test_ca_57_1_el_sueldo_del_mes_pasa_de_1200_a_1300(base):
    confirmar(lista_con_sueldo(base.con))
    assert meses.obtener_mes(base.con, base.mes_id)["sueldo_usd_cent"] == 130000


def test_sin_fila_de_sueldo_el_sueldo_del_mes_no_cambia(base):
    # RN-70: si ninguna fila es sueldo, el sueldo no cambia.
    resultado = confirmar(revisar(base.con))
    assert resultado.sueldo_cent is None
    assert meses.obtener_mes(base.con, base.mes_id)["sueldo_usd_cent"] == 120000


def test_el_resultado_tiene_las_cantidades_del_caso_ca_57_1(base):
    # CA-57.2 (lógica): 5 gastos, 1 plan, 3 ítems y el sueldo, en Octubre 2026.
    resultado = confirmar(lista_con_sueldo(base.con))
    assert resultado == Resultado(base.mes_id, 2026, 10, 5, 1, 3, 130000, False)
    assert resultado.pantalla == "gastos"


def test_ca_57_2_texto_del_resultado(base):
    # CA-57.2: frase principal y las dos líneas de "Para completar" (sin la cotización).
    resultado = confirmar(lista_con_sueldo(base.con))
    frase, completar = texto_resultado(resultado)
    assert frase == (
        'Se importaron: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo '
        "(US$ 1.300,00) en Octubre 2026."
    )
    assert completar == [
        "Los gastos quedaron sin medio de pago. Podés ponérselo en Gastos.",
        "Si alguno es compartido, marcalo desde el gasto.",
    ]


# ---------------------------------------------------------------------------
# CA-57.9: resumen previo
# ---------------------------------------------------------------------------


def test_ca_57_9_resumen_previo_con_los_textos_exactos(base):
    lista = lista_con_sueldo(base.con)
    assert resumen_previo(lista) == [
        "Se va a cargar en Octubre 2026 (ya existe).",
        "5 gastos: $ 376.720 (pagado $ 98.700)",
        "1 plan de cuotas: Avant Service cuota 3/ 3 $41.116,66 (cuota 3/3, $ 41.117 por mes)",
        '3 ítems "me deben": Sofía 2, Marsu 1 ($ 39.685 en total)',
        "Sueldo: US$ 1.200,00 -> US$ 1.300,00",
        "No se importan 19 filas (ignoradas o destildadas).",
        "Esta importación no se puede deshacer. Si algo sale mal, lo corregís a mano en la app.",
    ]


def test_ca_57_9_el_pie_dice_se_importan_10_filas(base):
    # CA-57.9: antes de confirmar, el pie cuenta las 10 filas.
    assert lista_con_sueldo(base.con).estado_pie() == (
        'Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo.'
    )


def test_resumen_previo_no_guarda_nada(base):
    # CA-57.9: mostrar el resumen no escribe en la base ni cambia la lista.
    lista = lista_con_sueldo(base.con)
    antes = foto_de_la_base(base.con)
    filas_antes = copy.deepcopy(lista.filas)
    resumen_previo(lista)
    assert foto_de_la_base(base.con) == antes
    assert lista.filas == filas_antes


def test_resumen_previo_sin_pagados_omite_el_parentesis_de_pagado(base):
    # RN-76: "(pagado ...)" solo si hay pagos.
    lista = revisar(base.con)
    solo(lista, ("Servicios", 4))
    assert resumen_previo(lista)[1] == "1 gasto: $ 82.000"


def test_resumen_previo_singulares(base):
    # RN-76: singular y plural ("1 gasto", '1 ítem "me deben"', "1 plan de cuotas", "1 fila").
    lista = revisar(base.con)
    solo(lista, ("Servicios", 4), (AVANT, 13), ("Prestamo MP", 22))
    previo = resumen_previo(lista)
    assert previo[1] == "1 gasto: $ 82.000"
    assert previo[2].startswith("1 plan de cuotas: ")
    assert previo[3] == '1 ítem "me deben": Sofía 1 ($ 20.000 en total)'
    # 13 filas principales + 16 incompletas = 29; se importan 3; no se importan 26.
    assert previo[-2] == "No se importan 26 filas (ignoradas o destildadas)."


def test_resumen_previo_una_sola_fila_que_no_se_importa(base):
    # RN-76: "No se importa 1 fila (ignorada o destildada)." en singular.
    lista = revisar(base.con, xlsx({"C1": "Luz", "D1": 100, "C2": "Gas", "D2": 200}))
    lista.cambiar_tilde(fila(lista, "Gas").indice, False)
    assert "No se importa 1 fila (ignorada o destildada)." in resumen_previo(lista)


def test_resumen_previo_sin_filas_ignoradas_no_dice_no_se_importan(base):
    lista = revisar(base.con, xlsx({"C1": "Luz", "D1": 100}))
    previo = resumen_previo(lista)
    assert not any(linea.startswith("No se import") for linea in previo)
    assert previo[-1].startswith("Esta importación no se puede deshacer")


def test_resumen_previo_mes_que_se_crea(base):
    # RN-76: "Se va a crear Noviembre 2026 y cargar ahí los datos."
    lista = lista_con_sueldo(base.con)
    lista.cambiar_mes_destino(2026, 11)
    assert resumen_previo(lista)[0] == "Se va a crear Noviembre 2026 y cargar ahí los datos."


def test_resumen_previo_sueldo_sin_cambio_muestra_solo_el_valor(base):
    # RN-70/RN-76: si el sueldo no cambia, "Sueldo: US$ 1.200,00" sin flecha.
    lista = revisar(base.con, xlsx({"C1": "Luz", "D1": 100, "B3": 1200}))
    lista.cambiar_tipo(sin_nombre(lista, 3).indice, "sueldo")
    assert "Sueldo: US$ 1.200,00" in resumen_previo(lista)


def test_resumen_previo_primer_uso_sin_cotizacion(base_vacia):
    # RN-76 / CA-57.12: primer uso, sin fila de sueldo.
    lista = revisar(base_vacia.con)
    previo = resumen_previo(lista)
    assert previo[0] == "Se va a crear Octubre 2026, sin cotización, y cargar ahí los datos."
    assert "Sin sueldo: el sueldo de Octubre 2026 queda en US$ 0,00." in previo
    assert not any(linea.startswith("Sueldo:") for linea in previo)


def test_resumen_previo_primer_uso_con_sueldo_no_dice_sin_sueldo(base_vacia):
    # RN-76: con fila de sueldo en el primer uso, "Sueldo: US$ 1.300,00" (no hay actual).
    previo = resumen_previo(lista_con_sueldo(base_vacia.con))
    assert "Sueldo: US$ 1.300,00" in previo
    assert not any(linea.startswith("Sin sueldo") for linea in previo)


def test_resumen_previo_mes_que_se_crea_sin_sueldo_no_dice_sin_sueldo(base):
    # RN-76: "Sin sueldo" es solo del primer uso; con mes que se crea no hay línea de sueldo.
    lista = revisar(base.con)
    lista.cambiar_mes_destino(2026, 11)
    previo = resumen_previo(lista)
    assert not any("ueldo" in linea for linea in previo)


# ---------------------------------------------------------------------------
# CA-57.10 y pantalla final
# ---------------------------------------------------------------------------


def test_ca_57_10_solo_un_item_y_el_sueldo_va_a_resumen(base):
    # CA-57.10: solo "Prestamo MP" (me deben) y el sueldo.
    lista = lista_con_sueldo(base.con)
    solo(lista, ("Prestamo MP", 22))
    lista.cambiar_tilde(sin_nombre(lista, 19).indice, True)
    resultado = confirmar(lista)
    frase, completar = texto_resultado(resultado)
    assert frase == 'Se importaron: 1 ítem "me deben" y el sueldo (US$ 1.300,00) en Octubre 2026.'
    assert resultado.pantalla == "resumen"
    # Solo hay ítems: no hay gastos sin medio de pago, pero sí la sugerencia de compartido.
    assert completar == ["Si alguno es compartido, marcalo desde el gasto."]
    assert gastos_de(base.con, base.mes_id) == [("Alquiler", 26000000, "fijo", "Vivienda", None, 0)]


def test_solo_el_sueldo_va_a_resumen_y_no_tiene_para_completar(base):
    # RN-76: solo sueldo -> pantalla Resumen y ninguna línea de "Para completar".
    lista = lista_con_sueldo(base.con)
    solo(lista)
    lista.cambiar_tilde(sin_nombre(lista, 19).indice, True)
    resultado = confirmar(lista)
    frase, completar = texto_resultado(resultado)
    assert frase == "Se importaron: el sueldo (US$ 1.300,00) en Octubre 2026."
    assert completar == []
    assert resultado.pantalla == "resumen"


def test_solo_una_cuota_va_a_gastos_y_pide_medio_de_pago(base):
    # RN-76: con un plan (aunque no haya gastos) la pantalla es Gastos y avisa del medio.
    lista = revisar(base.con)
    solo(lista, (AVANT, 13))
    resultado = confirmar(lista)
    assert resultado.pantalla == "gastos"
    frase, completar = texto_resultado(resultado)
    assert frase == "Se importaron: 1 plan de cuotas en Octubre 2026."
    assert completar == ["Los gastos quedaron sin medio de pago. Podés ponérselo en Gastos."]


def test_solo_gastos_dice_las_dos_lineas(base):
    lista = revisar(base.con)
    solo(lista, ("Servicios", 4))
    frase, completar = texto_resultado(confirmar(lista))
    assert frase == "Se importaron: 1 gasto en Octubre 2026."
    assert len(completar) == 2


# ---------------------------------------------------------------------------
# CA-55.x: mes destino
# ---------------------------------------------------------------------------


def test_ca_55_2_destino_noviembre_se_crea_con_los_fijos_el_sueldo_y_la_cotizacion(base):
    # CA-55.2: se crea 2026-11 con Alquiler copiado, sueldo 1.300, cotización 1.600 y las
    # filas importadas. "Alquiler" del Excel venía "ya existe" (destildada): no se duplica.
    lista = lista_con_sueldo(base.con)
    assert fila(lista, "Alquiler").ya_existe == "gasto"
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    nuevo = mes_por(base.con, 2026, 11)
    assert resultado.mes_id == nuevo["id"]
    assert (nuevo["sueldo_usd_cent"], nuevo["cotizacion_cent"]) == (130000, 160000)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, nuevo["id"])]
    assert nombres.count("Alquiler") == 1
    assert sorted(nombres) == sorted(
        ["Alquiler", "Servicios", "Internet", "psicologo", "Monotributo 66.020,12", "Gym", AVANT]
    )
    assert pagos.totales_del_mes(base.con, nuevo["id"])["pagado"] == 9870000
    # El alquiler copiado no trae pagos (RN-09) y octubre sigue con su sueldo.
    assert gasto_por_nombre(base.con, nuevo["id"], "Alquiler")["pagado_cent"] == 0
    assert meses.obtener_mes(base.con, base.mes_id)["sueldo_usd_cent"] == 120000


def test_ca_55_2_la_cuota_va_3_de_3_en_noviembre_y_2_de_3_en_octubre(base):
    # CA-55.2: primera cuota 2026-09; 2026-11 tiene la 3/3 y 2026-10 (mes actual) recibe la
    # 2/3 (RN-30); octubre no recibe ningún otro dato importado.
    lista = lista_con_sueldo(base.con)
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert (plan["primer_anio"], plan["primer_mes"]) == (2026, 9)
    nov = gasto_por_nombre(base.con, resultado.mes_id, AVANT)
    octubre = gasto_por_nombre(base.con, base.mes_id, AVANT)
    assert nov["plan_cuotas_id"] == octubre["plan_cuotas_id"] == plan["id"]
    assert cuotas.numero_de_cuota(plan, 2026, 11) == 3
    assert cuotas.numero_de_cuota(plan, 2026, 10) == 2
    assert [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)] == [
        "Alquiler",
        AVANT,
    ]
    assert cantidad(base.con, "pagos") == 2  # Solo en noviembre; la cuota de octubre sin pagos.


def test_ca_55_2_el_mes_nuevo_sin_fila_de_sueldo_copia_el_sueldo_del_ultimo(base):
    # RN-73: el mes que se crea toma el sueldo del último si no hay fila de sueldo.
    lista = revisar(base.con)
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    nuevo = meses.obtener_mes(base.con, resultado.mes_id)
    assert (nuevo["sueldo_usd_cent"], nuevo["cotizacion_cent"]) == (120000, 160000)
    assert resultado.sueldo_cent is None and resultado.sin_cotizacion is False


def test_mes_que_se_crea_copia_tambien_las_cuotas_de_planes_activos(base):
    # RN-09 + RN-73: un plan que ya existe, activo en el mes nuevo, aporta su cuota.
    cuotas.crear_plan(base.con, "Heladera", base.varios, None, 3000000, 12, 2026, 8, hoy=HOY)
    lista = revisar(base.con)
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, resultado.mes_id)]
    assert "Heladera" in nombres and "Alquiler" in nombres


def test_mes_que_se_crea_no_copia_pagos_unicos(base):
    # RN-09: los pagos únicos del último mes no se copian al mes nuevo.
    gastos.agregar_gasto(base.con, base.mes_id, "Regalo", base.varios, 100000, "unico")
    lista = revisar(base.con)
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, resultado.mes_id)]
    assert "Regalo" not in nombres


def test_ca_55_2_el_gasto_unico_del_excel_va_al_mes_destino(base):
    # RN-66: un gasto cambiado a "unico" se guarda con ese tipo.
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Servicios").indice, "unico")
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Servicios")["tipo"] == "unico"


def test_ca_55_3_mes_existente_que_no_es_el_ultimo(base):
    # CA-55.3: con 2026-09 y 2026-10, destino 2026-09. Avant: primera cuota 2026-07, última
    # 2026-09; 2026-09 tiene la 3/3 (excepción a RN-30) y 2026-10 no tiene cuota de Avant.
    sept = insertar_mes(base.con, 2026, 9, 110000, 150000)
    lista = lista_con_sueldo(base.con)
    lista.cambiar_mes_destino(2026, 9)
    assert lista.aviso_mes() == (
        "Los gastos fijos que importes no se agregan a los meses siguientes que ya existen."
    )
    resultado = confirmar(lista)
    assert resultado.mes_id == sept
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert (plan["primer_anio"], plan["primer_mes"]) == (2026, 7)
    assert cuotas.ultima_cuota(plan) == (2026, 9)
    assert gasto_por_nombre(base.con, sept, AVANT)["plan_cuotas_id"] == plan["id"]
    # Octubre no recibe nada: solo conserva su Alquiler.
    assert [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)] == ["Alquiler"]
    assert meses.obtener_mes(base.con, base.mes_id)["sueldo_usd_cent"] == 120000
    # El sueldo nuevo va al mes destino, no al último.
    assert meses.obtener_mes(base.con, sept)["sueldo_usd_cent"] == 130000
    # En septiembre no había Alquiler (CA-56.5): la fila vuelve a tildarse y se importa.
    # Quedan Alquiler, los 5 gastos y la cuota: 7.
    assert len(gastos.listar_gastos(base.con, sept)) == 7


def test_cuota_en_mes_pasado_no_toca_los_meses_del_medio(base):
    # RN-71: con 2026-08, 09 y 10, destino 2026-08 y una cuota 2 de 6: primera 2026-07.
    # La cuota va en 08 (destino) y en 10 (mes actual, RN-30); 09 (el del medio) no se toca.
    agosto = insertar_mes(base.con, 2026, 8)
    sept = insertar_mes(base.con, 2026, 9)
    lista = revisar(base.con, xlsx({"C1": "Heladera 2/6", "D1": 30000}))
    lista.cambiar_mes_destino(2026, 8)
    resultado = confirmar(lista)
    assert resultado.mes_id == agosto
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert (plan["primer_anio"], plan["primer_mes"]) == (2026, 7)
    nombres = lambda m: [g["nombre"] for g in gastos.listar_gastos(base.con, m)]  # noqa: E731
    assert nombres(agosto) == ["Heladera 2/6"]
    assert nombres(sept) == []
    assert "Heladera 2/6" in nombres(base.mes_id)
    cuota_oct = gasto_por_nombre(base.con, base.mes_id, "Heladera 2/6")
    assert cuotas.numero_de_cuota(plan, 2026, 10) == 4 and cuota_oct["monto_cent"] == 3000000


def test_cuota_en_mes_pasado_con_n_igual_a_N_termina_ahi(base):
    # RN-71: n = N en un mes pasado: el plan terminó, solo existe la cuota del destino.
    sept = insertar_mes(base.con, 2026, 9)
    lista = revisar(base.con, xlsx({"C1": "Prestamo 4/4", "D1": 10000}))
    lista.cambiar_mes_destino(2026, 9)
    confirmar(lista)
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert cuotas.ultima_cuota(plan) == (2026, 9)
    assert cuotas.estado(plan, HOY) == cuotas.TERMINADO
    assert [g["nombre"] for g in gastos.listar_gastos(base.con, sept)] == ["Prestamo 4/4"]
    assert [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)] == ["Alquiler"]


def test_cuota_n_igual_a_N_en_el_mes_actual_se_libera_el_mes_siguiente(base):
    # RN-71/RN-27: Avant 3/3 en 2026-10; el mes siguiente que se cree ya no la tiene.
    confirmar(lista_con_sueldo(base.con))
    nuevo = meses.crear_mes_siguiente(base.con, 130000, 160000)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, nuevo)]
    assert AVANT not in nombres
    assert "Alquiler" in nombres and "Gym" in nombres  # los fijos importados sí se copian


def test_cuota_1_de_N_importada_en_mes_nuevo_no_aparece_en_el_mes_anterior(base):
    # RN-71: cuota 1 de 12 en 2026-11 -> primera cuota 2026-11; octubre no la recibe.
    lista = revisar(base.con, xlsx({"C1": "Notebook 1/12", "D1": 50000}))
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert (plan["primer_anio"], plan["primer_mes"]) == (2026, 11)
    assert "Notebook 1/12" not in [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert "Notebook 1/12" in [g["nombre"] for g in gastos.listar_gastos(base.con, resultado.mes_id)]


def test_cuota_con_pagado_completo_y_parcial_se_aplica_solo_a_la_cuota_del_destino(base):
    # RN-69/RN-71: el pagado de la cuota va a la cuota del mes destino, no a las otras.
    celdas = {"C1": "Pagos", "E1": "Pagado", "C2": "Heladera 2/6", "D2": 30000, "E2": 30000,
              "C3": "Moto 2/6", "D3": 40000, "E3": 10000}
    lista = revisar(base.con, xlsx(celdas))
    lista.cambiar_mes_destino(2026, 11)
    resultado = confirmar(lista)
    heladera = gasto_por_nombre(base.con, resultado.mes_id, "Heladera 2/6")
    moto = gasto_por_nombre(base.con, resultado.mes_id, "Moto 2/6")
    assert pagos.pendiente(base.con, heladera["id"]) == 0
    assert pagos.pendiente(base.con, moto["id"]) == 3000000
    # La cuota que se copia al mes actual (3/6) no tiene pagos.
    heladera_oct = gasto_por_nombre(base.con, base.mes_id, "Heladera 2/6")
    assert heladera_oct["pagado_cent"] == 0
    assert gasto_por_nombre(base.con, base.mes_id, "Moto 2/6")["pagado_cent"] == 0


def test_cuota_con_pagado_en_mes_pasado(base):
    # RN-69/RN-71: la cuota del mes pasado destino con pagado parcial queda con pago.
    sept = insertar_mes(base.con, 2026, 9)
    celdas = {"C1": "Pagos", "E1": "Pagado", "C2": "Moto 1/6", "D2": 40000, "E2": 15000}
    lista = revisar(base.con, xlsx(celdas))
    lista.cambiar_mes_destino(2026, 9)
    confirmar(lista)
    moto = gasto_por_nombre(base.con, sept, "Moto 1/6")
    assert moto["pagado_cent"] == 1500000
    assert pagos.listar_pagos(base.con, moto["id"])[0]["fecha"] == "2026-10-14"


def test_ca_55_4_primer_uso_crea_el_mes_con_sueldo_y_sin_cotizacion(base_vacia):
    # CA-55.4: base sin meses, destino 2026-10, fila 19 como sueldo: sueldo 1.300,00 y sin
    # cotización.
    resultado = confirmar(lista_con_sueldo(base_vacia.con))
    mes = meses.obtener_mes(base_vacia.con, resultado.mes_id)
    assert (mes["anio"], mes["mes"]) == (2026, 10)
    assert mes["sueldo_usd_cent"] == 130000 and mes["cotizacion_cent"] is None
    assert resultado.sin_cotizacion is True
    assert resultado.sueldo_cent == 130000
    assert resumen.calcular_resumen(base_vacia.con, resultado.mes_id).falta_cotizacion is True


def test_ca_55_4_primer_uso_sin_fila_de_sueldo_deja_el_sueldo_en_cero(base_vacia):
    # CA-55.4 / RN-73: sueldo 0 y sin cotización; no se inventa una fila de sueldo.
    resultado = confirmar(revisar(base_vacia.con))
    mes = meses.obtener_mes(base_vacia.con, resultado.mes_id)
    assert mes["sueldo_usd_cent"] == 0 and mes["cotizacion_cent"] is None
    assert resultado.sueldo_cent is None


def test_ca_57_12_primer_uso_resultado_y_pantalla(base_vacia):
    # CA-57.12: el resultado incluye "Cargá la cotización de Octubre 2026 en el Resumen." y
    # la pantalla es Gastos.
    resultado = confirmar(revisar(base_vacia.con))
    assert resultado.pantalla == "gastos"
    frase, completar = texto_resultado(resultado)
    assert frase == (
        'Se importaron: 6 gastos, 1 plan de cuotas y 3 ítems "me deben" en Octubre 2026.'
    )
    assert completar == [
        "Los gastos quedaron sin medio de pago. Podés ponérselo en Gastos.",
        "Si alguno es compartido, marcalo desde el gasto.",
        "Cargá la cotización de Octubre 2026 en el Resumen.",
    ]


def test_primer_uso_los_gastos_y_la_cuota_se_guardan_aunque_el_mes_no_tenga_cotizacion(base_vacia):
    # CA-57.12: el primer uso importa lo mismo que la base normal (Alquiler del Excel entra,
    # porque no existe ningún mes).
    resultado = confirmar(revisar(base_vacia.con))
    nombres = [g["nombre"] for g in gastos.listar_gastos(base_vacia.con, resultado.mes_id)]
    assert sorted(nombres) == sorted(
        ["Alquiler", "Servicios", "Internet", "psicologo", "Monotributo 66.020,12", "Gym", AVANT]
    )


def test_primer_uso_en_un_mes_pasado_pone_la_cuota_en_el_destino(base_vacia):
    # RN-71/RN-73: primer uso con destino 2025-03 (anterior al mes actual): la cuota va ahí.
    lista = revisar(base_vacia.con, xlsx({"C1": "Heladera 2/6", "D1": 30000}))
    lista.cambiar_mes_destino(2025, 3)
    resultado = confirmar(lista)
    assert (resultado.anio, resultado.mes) == (2025, 3)
    assert [g["nombre"] for g in gastos.listar_gastos(base_vacia.con, resultado.mes_id)] == [
        "Heladera 2/6"
    ]
    assert [(m["anio"], m["mes"]) for m in meses.listar_meses(base_vacia.con)] == [(2025, 3)]


def test_ca_55_5_destino_propuesto_es_el_ultimo_mes_y_se_guarda_ahi(base):
    # CA-55.5: con último mes 2026-08 (09 y 10 no existen), el destino propuesto es 2026-08.
    con = base.con
    con.execute("DELETE FROM gastos")
    con.execute("DELETE FROM meses")
    con.commit()
    agosto = insertar_mes(con, 2026, 8)
    lista = revisar(con)
    assert (lista.anio, lista.mes) == (2026, 8)
    resultado = confirmar(lista)
    assert resultado.mes_id == agosto


# ---------------------------------------------------------------------------
# CA-56.4: segunda importación
# ---------------------------------------------------------------------------


def test_ca_56_4_segunda_importacion_todo_viene_ya_existe_y_destildado(base):
    # CA-56.4: tras una primera importación, en la segunda todo viene "ya existe".
    confirmar(lista_con_sueldo(base.con))
    segunda = revisar(base.con)
    for nombre, fila_excel in [
        ("Alquiler", 3), ("Servicios", 4), ("Internet", 5), ("psicologo", 7),
        ("Monotributo 66.020,12", 12), (AVANT, 13), ("Gym", 15),
        ("Prestamo MP", 22), ("Internet", 23), ("tacones chiqui baby", 27),
    ]:
        f = fila(segunda, nombre, fila_excel)
        assert f.ya_existe is not None, (nombre, fila_excel)
        assert f.tildada is False, (nombre, fila_excel)


def test_ca_56_4_notas_de_la_segunda_importacion(base):
    confirmar(lista_con_sueldo(base.con))
    segunda = revisar(base.con)
    assert segunda.notas(fila(segunda, "Servicios", 4)) == [
        "Ya existe en Octubre 2026. Viene destildada."
    ]
    assert segunda.notas(fila(segunda, "Prestamo MP", 22)) == [
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
    ]


def test_avant_en_la_segunda_importacion_gana_la_nota_de_gasto_sobre_la_de_plan(base):
    # Regla nueva: la cuota de Avant ya existe como gasto del mes y como plan; se muestra
    # solo la nota del gasto.
    confirmar(lista_con_sueldo(base.con))
    segunda = revisar(base.con)
    avant = fila(segunda, AVANT, 13)
    assert avant.ya_existe == "gasto"
    notas = segunda.notas(avant)
    assert "Ya existe en Octubre 2026. Viene destildada." in notas
    assert not any("plan de cuotas con este nombre" in n for n in notas)


def test_o69_tildar_una_fila_ya_existe_de_me_deben_y_de_plan_cambia_la_nota(base):
    # O69 / CA-56.4 / CA-56.7: versión tildada "Si la importás, queda repetida.".
    confirmar(lista_con_sueldo(base.con))
    segunda = revisar(base.con)
    prestamo = fila(segunda, "Prestamo MP", 22)
    segunda.cambiar_tilde(prestamo.indice, True)
    assert segunda.notas(prestamo) == [
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Si la importás, queda repetida."
    ]
    segunda.cambiar_tilde(prestamo.indice, False)
    assert segunda.notas(prestamo) == [
        "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada."
    ]
    # Plan terminado "Heladera 2/12" (sin cuota en octubre): nota de plan.
    cuotas.crear_plan(base.con, "Heladera 2/12", base.varios, None, 3000000, 12, 2025, 1, hoy=HOY)
    lista = revisar(base.con, xlsx({"C1": "Heladera 2/12", "D1": 30000}))
    heladera = fila(lista, "Heladera 2/12")
    assert heladera.tipo == "cuota" and heladera.ya_existe == "plan"
    assert lista.notas(heladera)[0] == "Ya existe un plan de cuotas con este nombre. Viene destildada."
    lista.cambiar_tilde(heladera.indice, True)
    assert lista.notas(heladera)[0] == (
        "Ya existe un plan de cuotas con este nombre. Si la importás, queda repetida."
    )
    confirmar(lista)
    planes = base.con.execute("SELECT nombre FROM planes_cuotas WHERE nombre = 'Heladera 2/12'")
    assert len(planes.fetchall()) == 2  # CA-56.7: quedan dos planes


def test_segunda_importacion_sin_tildar_nada_no_se_puede_confirmar(base):
    # RN-68 / CA-57.8: con todo destildado, "No hay filas para importar." y no se guarda nada.
    confirmar(lista_con_sueldo(base.con))
    segunda = revisar(base.con)
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(segunda)
    assert str(error.value) == "No hay filas para importar."
    assert foto_de_la_base(base.con) == antes


def test_segunda_importacion_tildando_todo_duplica_los_datos(base):
    # RN-76: "la importación se puede repetir"; si el usuario tilda todo, queda repetido.
    confirmar(lista_con_sueldo(base.con))
    segunda = revisar(base.con)
    for f in segunda.filas:
        if f.tipo != "ignorar":
            segunda.cambiar_tilde(f.indice, True)
    confirmar(segunda)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert nombres.count("Internet") == 2 and nombres.count("Alquiler") == 2
    assert nombres.count(AVANT) == 2
    assert cantidad(base.con, "planes_cuotas") == 2
    assert cantidad(base.con, "items_me_deben") == 6
    assert me_deben.total_general(base.con) == 3968500 * 2


# ---------------------------------------------------------------------------
# Pagado, cobrado y tipos
# ---------------------------------------------------------------------------


def test_cobrado_marca_el_item_como_cobrado_y_no_suma_al_total(base):
    # CA-51.6 (guardado): los ítems de Sofía cobrados no suman; el de Marsu sí.
    celdas = {**celdas_planilla(), "F21": "Cobrado", "F22": 20000, "F23": "x", "F26": "Cobrado",
              "F27": 3000}
    lista = revisar(base.con, xlsx(celdas))
    assert fila(lista, "Prestamo MP").cobrado and fila(lista, "Internet", 23).cobrado
    confirmar(lista)
    cobrados = {
        i["descripcion"]: i["cobrado"]
        for i in base.con.execute("SELECT descripcion, cobrado FROM items_me_deben")
    }
    assert cobrados == {"Prestamo MP": 1, "Internet": 1, "tacones chiqui baby": 0}
    assert me_deben.total_de(base.con, base.sofia) == 0
    assert me_deben.total_de(base.con, base.marsu) == 678500


def test_cobrado_destildado_por_el_usuario_queda_no_cobrado(base):
    # CA-51.6: si el usuario destilda "cobrado" antes de confirmar, queda no cobrado.
    celdas = {**celdas_planilla(), "F21": "Cobrado", "F22": 20000, "F23": "x"}
    lista = revisar(base.con, xlsx(celdas))
    lista.cambiar_cobrado(fila(lista, "Prestamo MP").indice, False)
    confirmar(lista)
    assert me_deben.total_de(base.con, base.sofia) == 2000000


def test_pagado_en_un_gasto_unico_y_pagado_cero(base):
    # RN-69: pagado 0 -> sin pagos; en un gasto único también aplica.
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Luz", "D2": 100, "E2": 0,
              "C3": "Gas", "D3": 200, "E3": 50}
    lista = revisar(base.con, xlsx(celdas))
    lista.cambiar_tipo(fila(lista, "Gas").indice, "unico")
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Luz")["pagado_cent"] == 0
    gas = gasto_por_nombre(base.con, base.mes_id, "Gas")
    assert gas["tipo"] == "unico" and gas["pagado_cent"] == 5000


def test_el_pagado_de_una_fila_me_deben_no_crea_pagos(base):
    # RN-69: en "me deben" el pagado no se usa.
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Luz", "D2": 100, "E2": 50}
    lista = revisar(base.con, xlsx(celdas))
    f = fila(lista, "Luz")
    lista.cambiar_tipo(f.indice, "me_deben")
    lista.editar_fila(f.indice, "me_deben", "Luz", 10000, pagado_cent=5000, persona=base.sofia)
    confirmar(lista)
    assert cantidad(base.con, "pagos") == 0
    assert cantidad(base.con, "items_me_deben") == 1


def test_pagado_igual_al_monto_con_centavos_queda_completo(base):
    # RN-69: P = M con centavos (66.020,12) -> pagado completo exacto.
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Monotributo", "D2": 66020.12, "E2": 66020.12}
    confirmar(revisar(base.con, xlsx(celdas)))
    g = gasto_por_nombre(base.con, base.mes_id, "Monotributo")
    assert (g["monto_cent"], g["pagado_cent"]) == (6602012, 6602012)


def test_el_nombre_editado_y_el_monto_corregido_se_guardan(base):
    # CA-53.1: "Psicólogo" y 85.000 en lugar de "psicologo" y "Servicios" 82.000.
    lista = revisar(base.con)
    psico = fila(lista, "psicologo")
    assert lista.editar_fila(psico.indice, "fijo", "Psicólogo", psico.monto_cent,
                             pagado_cent=psico.pagado_cent) == {}
    serv = fila(lista, "Servicios")
    assert lista.editar_fila(serv.indice, "fijo", "Servicios", 8500000) == {}
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Psicólogo")["pagado_cent"] == 6000000
    assert gasto_por_nombre(base.con, base.mes_id, "Servicios")["monto_cent"] == 8500000


def test_ca_53_2_fila_incompleta_completada_se_importa(base):
    # CA-53.2: "Obra social" completada con monto 45.000 y tipo gasto fijo.
    lista = revisar(base.con)
    obra = fila(lista, "Obra social")
    assert lista.editar_fila(obra.indice, "fijo", "Obra social", 4500000) == {}
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Obra social")["monto_cent"] == 4500000


def test_ca_53_3_gym_como_cuota_2_de_6(base):
    # CA-53.3: plan "Gym" de 6 cuotas de 50.000 con primera cuota 2026-09; en octubre "2/6".
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "cuota", "Gym", 5000000, cuota_actual=2,
                             cuota_total=6) == {}
    confirmar(lista)
    plan = base.con.execute("SELECT * FROM planes_cuotas WHERE nombre = 'Gym'").fetchone()
    assert (plan["primer_anio"], plan["primer_mes"], plan["cantidad_cuotas"]) == (2026, 9, 6)
    assert cuotas.numero_de_cuota(plan, 2026, 10) == 2


def test_ca_53_4_persona_nueva_juan_se_crea_con_su_item(base):
    # CA-53.4: Servicios como "me deben" de Juan (persona nueva): al confirmar existe Juan.
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    serv = fila(lista, "Servicios")
    assert lista.editar_fila(serv.indice, "me_deben", "Servicios", 8200000, persona=juan) == {}
    confirmar(lista)
    juan_id = [p["id"] for p in catalogos.listar(base.con, catalogos.PERSONAS)
               if p["nombre"] == "Juan"]
    assert len(juan_id) == 1
    assert me_deben.total_de(base.con, juan_id[0]) == 8200000


# ---------------------------------------------------------------------------
# CA-57.11: categorías y personas nuevas, usadas y no usadas
# ---------------------------------------------------------------------------


def _nombres(con, tabla):
    return [c["nombre"] for c in catalogos.listar(con, tabla, incluir_archivados=True)]


def test_ca_57_11_persona_nueva_que_deja_de_usarse_no_se_crea(base):
    # CA-57.11: Juan creada para "Servicios" como "me deben" y después "Servicios" vuelve a
    # gasto fijo: al confirmar no existe Juan y el resumen previo no lo menciona.
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    serv = fila(lista, "Servicios")
    lista.editar_fila(serv.indice, "me_deben", "Servicios", 8200000, persona=juan)
    lista.editar_fila(serv.indice, "fijo", "Servicios", 8200000, categoria=None, persona=juan)
    assert not any("Se crean también" in linea for linea in resumen_previo(lista))
    confirmar(lista)
    assert "Juan" not in _nombres(base.con, catalogos.PERSONAS)


def test_ca_57_11_categoria_nueva_como_defecto_se_crea_y_se_usa(base):
    # CA-57.11: "Importado" como categoría por defecto: resumen previo y guardado.
    lista = revisar(base.con)
    lista.cambiar_categoria_defecto(lista.agregar_categoria("Importado"))
    previo = resumen_previo(lista)
    assert 'Se crean también: la categoría "Importado".' in previo
    # La línea va antes de "No se importan..." y de la advertencia final (RN-76).
    assert previo.index('Se crean también: la categoría "Importado".') < previo.index(
        previo[-2]
    )
    confirmar(lista)
    importado = [c for c in catalogos.listar(base.con, catalogos.CATEGORIAS)
                 if c["nombre"] == "Importado"]
    assert len(importado) == 1
    plan_cuota = gasto_por_nombre(base.con, base.mes_id, AVANT)
    assert plan_cuota["categoria"] == "Importado"
    assert gasto_por_nombre(base.con, base.mes_id, "Gym")["categoria"] == "Importado"
    # Alquiler (el que ya estaba) conserva Vivienda.
    assert gasto_por_nombre(base.con, base.mes_id, "Alquiler")["categoria"] == "Vivienda"
    plan = base.con.execute("SELECT categoria_id FROM planes_cuotas").fetchone()
    assert plan["categoria_id"] == importado[0]["id"]


def test_ca_57_11_categoria_nueva_solo_en_gym_destildada_no_se_crea(base):
    # CA-57.11: "Importado" elegida solo en "Gym" y después "Gym" destildada: no existe.
    lista = revisar(base.con)
    importado = lista.agregar_categoria("Importado")
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=importado)
    lista.cambiar_tilde(gym.indice, False)
    assert not any("Se crean también" in linea for linea in resumen_previo(lista))
    confirmar(lista)
    assert "Importado" not in _nombres(base.con, catalogos.CATEGORIAS)


def test_categoria_nueva_usada_solo_por_una_cuota_se_crea(base):
    # RN-75: una categoría nueva usada solo por una fila de cuota también queda en uso.
    lista = revisar(base.con)
    nueva = lista.agregar_categoria("Electro")
    avant = fila(lista, AVANT)
    lista.editar_fila(avant.indice, "cuota", AVANT, avant.monto_cent, categoria=nueva,
                      cuota_actual=3, cuota_total=3)
    confirmar(lista)
    assert "Electro" in _nombres(base.con, catalogos.CATEGORIAS)
    assert base.con.execute(
        "SELECT c.nombre FROM planes_cuotas p JOIN categorias c ON c.id = p.categoria_id"
    ).fetchone()[0] == "Electro"


def test_persona_y_categoria_nuevas_en_uso_en_el_resumen_previo(base):
    # RN-76: 'Se crean también: la categoría "Importado" y la persona "Juan".'
    lista = revisar(base.con)
    lista.cambiar_categoria_defecto(lista.agregar_categoria("Importado"))
    juan = lista.agregar_persona("Juan")
    prestamo = fila(lista, "Prestamo MP")
    lista.editar_fila(prestamo.indice, "me_deben", "Prestamo MP", 2000000, persona=juan)
    assert 'Se crean también: la categoría "Importado" y la persona "Juan".' in resumen_previo(lista)
    confirmar(lista)
    assert "Juan" in _nombres(base.con, catalogos.PERSONAS)
    assert "Importado" in _nombres(base.con, catalogos.CATEGORIAS)


def test_dos_categorias_y_dos_personas_nuevas_usadas(base):
    lista = revisar(base.con)
    a, b = lista.agregar_categoria("Alfa"), lista.agregar_categoria("Beta")
    j, k = lista.agregar_persona("Juan"), lista.agregar_persona("Kira")
    lista.editar_fila(fila(lista, "Gym").indice, "fijo", "Gym", 5000000, categoria=a)
    lista.editar_fila(fila(lista, "Servicios").indice, "fijo", "Servicios", 8200000, categoria=b)
    lista.editar_fila(fila(lista, "Prestamo MP").indice, "me_deben", "Prestamo MP", 2000000, persona=j)
    lista.editar_fila(fila(lista, "tacones chiqui baby").indice, "me_deben", "tacones chiqui baby",
                      678500, persona=k)
    assert 'Se crean también: la categoría "Alfa", la categoría "Beta", la persona "Juan" y la persona "Kira".' in resumen_previo(lista)
    confirmar(lista)
    assert {"Alfa", "Beta"} <= set(_nombres(base.con, catalogos.CATEGORIAS))
    assert {"Juan", "Kira"} <= set(_nombres(base.con, catalogos.PERSONAS))
    assert gasto_por_nombre(base.con, base.mes_id, "Gym")["categoria"] == "Alfa"
    assert gasto_por_nombre(base.con, base.mes_id, "Servicios")["categoria"] == "Beta"


def test_categoria_nueva_en_primer_uso(base_vacia):
    lista = revisar(base_vacia.con)
    lista.cambiar_categoria_defecto(lista.agregar_categoria("Importado"))
    resultado = confirmar(lista)
    assert gastos_de(base_vacia.con, resultado.mes_id)[0][3] == "Importado"


# ---------------------------------------------------------------------------
# CA-50.2: no queda copia ni ruta del archivo
# ---------------------------------------------------------------------------


def test_ca_50_2_no_queda_copia_ni_ruta_del_archivo(base, tmp_path, monkeypatch):
    # CA-50.2 (lógica): el .xlsx queda igual, no aparece ningún archivo nuevo, y en la base
    # no hay ni el nombre del archivo ni ".xlsx". Borrar el .xlsx no cambia nada.
    carpeta_datos = tmp_path / "datos"
    carpeta_datos.mkdir()
    archivo = tmp_path / "planilla-prueba.xlsx"
    archivo.write_bytes(planilla_prueba())
    huella = hashlib.sha256(archivo.read_bytes()).hexdigest()
    monkeypatch.chdir(carpeta_datos)
    antes = sorted(os.listdir(tmp_path)) + sorted(os.listdir(carpeta_datos))
    confirmar(lista_con_sueldo(base.con, archivo.read_bytes()))
    assert hashlib.sha256(archivo.read_bytes()).hexdigest() == huella
    assert sorted(os.listdir(tmp_path)) + sorted(os.listdir(carpeta_datos)) == antes
    volcado = "\n".join(base.con.iterdump())
    assert "planilla-prueba" not in volcado and ".xlsx" not in volcado
    foto = foto_de_la_base(base.con)
    archivo.unlink()
    assert foto_de_la_base(base.con) == foto


# ---------------------------------------------------------------------------
# CA-57.4: todo o nada
# ---------------------------------------------------------------------------


def _fallar_en(monkeypatch, modulo, nombre, numero, despues=True):
    """Hace que la llamada número `numero` (1, 2, ...) a modulo.nombre lance un error.

    despues=True: primero hace lo suyo y recién después falla (deja datos escritos que
    después hay que deshacer). despues=False: falla antes de escribir.
    """
    original = getattr(modulo, nombre)
    contador = {"n": 0}

    def envoltorio(*args, **kwargs):
        contador["n"] += 1
        if contador["n"] == numero:
            if despues:
                original(*args, **kwargs)
            raise RuntimeError("fallo simulado")
        return original(*args, **kwargs)

    monkeypatch.setattr(modulo, nombre, envoltorio)
    return original


def _lista_completa_con_nuevos(con, destino=(2026, 11)):
    """Lista de CA-57.4: destino 2026-11, sueldo, Juan (persona nueva) en "Prestamo MP",
    categoría nueva "Importado" por defecto, un ítem cobrado y un pagado parcial."""
    lista = lista_con_sueldo(con)
    lista.cambiar_mes_destino(*destino)
    lista.cambiar_categoria_defecto(lista.agregar_categoria("Importado"))
    juan = lista.agregar_persona("Juan")
    prestamo = fila(lista, "Prestamo MP")
    lista.editar_fila(prestamo.indice, "me_deben", "Prestamo MP", 2000000, persona=juan,
                      cobrado=True)
    return lista


def _estado_de_la_lista(lista):
    return (
        copy.deepcopy(lista.filas),
        list(lista.categorias_nuevas),
        list(lista.personas_nuevas),
        lista.anio,
        lista.mes,
        lista.categoria_defecto,
        lista.hubo_cambios,
        lista.confirmada,
    )


PUNTOS_DE_FALLO = [
    # (módulo, función, número de llamada, descripción)
    pytest.param(meses, "crear_mes", 1, id="despues-de-crear-el-mes"),
    pytest.param(catalogos, "crear", 1, id="despues-de-crear-la-categoria-nueva"),
    pytest.param(catalogos, "crear", 2, id="despues-de-crear-la-persona-nueva"),
    pytest.param(gastos, "agregar_gasto", 1, id="despues-del-primer-gasto"),
    pytest.param(gastos, "agregar_gasto", 5, id="despues-del-ultimo-gasto"),
    pytest.param(pagos, "marcar_pagado", 1, id="despues-del-primer-pago-completo"),
    pytest.param(pagos, "registrar_pago", 1, id="despues-del-pago-parcial"),
    pytest.param(cuotas, "crear_plan", 1, id="despues-de-crear-el-plan"),
    pytest.param(cuotas, "cuota_en_mes", 1, id="despues-de-la-cuota-del-destino"),
    pytest.param(me_deben, "agregar_item", 1, id="despues-del-primer-item"),
    pytest.param(me_deben, "agregar_item", 3, id="despues-del-ultimo-item"),
    pytest.param(me_deben, "marcar_item_cobrado", 1, id="despues-de-marcar-cobrado"),
]


@pytest.mark.parametrize(("modulo", "nombre", "numero"), PUNTOS_DE_FALLO)
def test_ca_57_4_si_falla_a_mitad_no_queda_nada_y_la_lista_sigue_intacta(
    base, monkeypatch, modulo, nombre, numero
):
    # CA-57.4: el fallo (simulado) en distintos puntos deja la base exactamente como estaba
    # (ni mes nuevo, ni categoría, ni persona, ni gastos, pagos, planes, ítems), avisa con el
    # mensaje de RN-76 y deja la lista tal cual para reintentar.
    lista = _lista_completa_con_nuevos(base.con)
    antes = foto_de_la_base(base.con)
    estado = _estado_de_la_lista(lista)
    original = _fallar_en(monkeypatch, modulo, nombre, numero)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "No se pudo importar. No se guardó ningún dato."
    assert isinstance(error.value.__cause__, RuntimeError)
    assert foto_de_la_base(base.con) == antes
    assert mes_por(base.con, 2026, 11) is None
    assert "Importado" not in _nombres(base.con, catalogos.CATEGORIAS)
    assert "Juan" not in _nombres(base.con, catalogos.PERSONAS)
    assert _estado_de_la_lista(lista) == estado
    assert lista.puede_confirmar() is True
    assert base.con.in_transaction is False
    # Reintentar (ya sin el fallo) funciona y deja lo mismo que una importación sin fallo.
    monkeypatch.setattr(modulo, nombre, original)
    resultado = confirmar(lista)
    assert resultado.gastos == 5 and resultado.planes == 1 and resultado.items == 3
    assert mes_por(base.con, 2026, 11) is not None


def test_ca_57_4_el_reintento_deja_lo_mismo_que_una_importacion_sin_fallo(
    con, mes_id, monkeypatch
):
    # CA-57.4: tras fallar y reintentar queda exactamente lo mismo que si nunca hubiera
    # fallado (mismos ids, mismos datos), con dos bases iguales.
    def armar(c):
        ids = _ids_categorias(c)
        catalogos.crear(c, catalogos.CATEGORIAS, "Varios")
        catalogos.crear(c, catalogos.PERSONAS, "Sofía")
        catalogos.crear(c, catalogos.PERSONAS, "Marsu")
        gastos.agregar_gasto(c, mes_id, "Alquiler", ids["Vivienda"], 26000000, "fijo")

    from app.logica import base_datos

    otra = base_datos.conectar(":memory:")
    try:
        meses.crear_primer_mes(otra, 2026, 10, 120000, 160000)
        armar(con)
        armar(otra)
        limpia = _lista_completa_con_nuevos(otra)
        confirmar(limpia)

        con_fallo = _lista_completa_con_nuevos(con)
        original = _fallar_en(monkeypatch, me_deben, "agregar_item", 3)
        with pytest.raises(ErrorDeValidacion):
            confirmar(con_fallo)
        monkeypatch.setattr(me_deben, "agregar_item", original)
        confirmar(con_fallo)
        assert foto_de_la_base(con) == foto_de_la_base(otra)
    finally:
        otra.close()


def test_ca_57_4_fallo_sin_escribir_antes_tampoco_deja_nada(base, monkeypatch):
    # CA-57.4: fallo que ocurre antes de escribir lo suyo (despues=False) en el último ítem.
    lista = _lista_completa_con_nuevos(base.con)
    antes = foto_de_la_base(base.con)
    _fallar_en(monkeypatch, me_deben, "agregar_item", 3, despues=False)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert foto_de_la_base(base.con) == antes


def test_ca_57_4_fallo_con_mes_existente_no_cambia_el_sueldo(base, monkeypatch):
    # CA-57.4: con mes existente, si falla al final el sueldo vuelve a 1.200.
    lista = lista_con_sueldo(base.con)
    antes = foto_de_la_base(base.con)
    _fallar_en(monkeypatch, me_deben, "agregar_item", 3)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert meses.obtener_mes(base.con, base.mes_id)["sueldo_usd_cent"] == 120000
    assert foto_de_la_base(base.con) == antes


def test_ca_57_4_fallo_en_el_sueldo_de_un_mes_existente(base, monkeypatch):
    # CA-57.4: falla el cambio de sueldo (antes de los gastos): nada guardado.
    lista = lista_con_sueldo(base.con)
    antes = foto_de_la_base(base.con)
    _fallar_en(monkeypatch, meses, "editar_sueldo", 1)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert foto_de_la_base(base.con) == antes


def test_ca_57_4_fallo_en_primer_uso_no_deja_ni_el_primer_mes(base_vacia, monkeypatch):
    # CA-57.4: en el primer uso, si falla, la base sigue sin meses (vuelve al formulario).
    lista = lista_con_sueldo(base_vacia.con)
    antes = foto_de_la_base(base_vacia.con)
    _fallar_en(monkeypatch, gastos, "agregar_gasto", 5)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == MENSAJE_ERROR
    assert meses.hay_meses(base_vacia.con) is False
    assert foto_de_la_base(base_vacia.con) == antes
    assert lista.es_primer_uso is True


TRIGGERS = [
    pytest.param("meses", "INSERT", "NEW.mes = 11", id="al-crear-el-mes"),
    pytest.param("categorias", "INSERT", "NEW.nombre = 'Importado'", id="al-crear-la-categoria"),
    pytest.param("personas", "INSERT", "NEW.nombre = 'Juan'", id="al-crear-la-persona"),
    pytest.param("gastos", "INSERT", "NEW.nombre = 'Gym' AND NEW.mes_id > 1", id="en-un-gasto-a-mitad"),
    pytest.param("gastos", "INSERT", "NEW.tipo = 'cuota' AND NEW.mes_id = 1", id="en-la-cuota-copiada-al-mes-actual"),
    pytest.param("pagos", "INSERT", "NEW.monto_cent = 6000000", id="en-el-pago-parcial"),
    pytest.param("planes_cuotas", "INSERT", "1", id="al-crear-el-plan"),
    pytest.param("items_me_deben", "INSERT", "NEW.descripcion = 'tacones chiqui baby'", id="en-el-ultimo-item"),
    pytest.param("items_me_deben", "UPDATE", "NEW.cobrado = 1", id="al-marcar-cobrado"),
]


@pytest.mark.parametrize(("tabla", "evento", "cuando"), TRIGGERS)
def test_ca_57_4_fallo_real_de_la_base_sin_monkeypatch(base, tabla, evento, cuando):
    # CA-57.4 con un error REAL de SQLite: un trigger con RAISE(ABORT) en distintos puntos
    # del guardado (la revisión no puede detectarlo antes). No queda nada, la lista sigue
    # intacta, "confirmada" sigue en False y, sacando el trigger, se puede reintentar.
    lista = _lista_completa_con_nuevos(base.con)
    base.con.execute(
        f"CREATE TRIGGER falla BEFORE {evento} ON {tabla} WHEN {cuando} "
        "BEGIN SELECT RAISE(ABORT, 'fallo real de la base'); END"
    )
    antes = foto_de_la_base(base.con)
    estado = _estado_de_la_lista(lista)
    assert lista.puede_confirmar() is True
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == MENSAJE_ERROR
    assert "fallo real de la base" in str(error.value.__cause__)
    assert foto_de_la_base(base.con) == antes
    assert _estado_de_la_lista(lista) == estado
    assert lista.confirmada is False
    assert base.con.in_transaction is False
    base.con.execute("DROP TRIGGER falla")
    resultado = confirmar(lista)
    assert resultado.items == 3 and lista.confirmada is True


def test_ca_57_4_fallo_real_al_cambiar_el_sueldo_de_un_mes_existente(base):
    # CA-57.4: error real de la base al actualizar el sueldo del mes existente.
    lista = lista_con_sueldo(base.con)
    base.con.execute(
        "CREATE TRIGGER falla BEFORE UPDATE ON meses "
        "BEGIN SELECT RAISE(ABORT, 'fallo real de la base'); END"
    )
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == MENSAJE_ERROR
    assert foto_de_la_base(base.con) == antes
    assert meses.obtener_mes(base.con, base.mes_id)["sueldo_usd_cent"] == 120000
    assert lista.confirmada is False


def test_ca_57_4_fallo_real_en_el_primer_uso_no_deja_ni_el_primer_mes(base_vacia):
    lista = lista_con_sueldo(base_vacia.con)
    base_vacia.con.execute(
        "CREATE TRIGGER falla BEFORE INSERT ON items_me_deben "
        "BEGIN SELECT RAISE(ABORT, 'fallo real de la base'); END"
    )
    antes = foto_de_la_base(base_vacia.con)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert foto_de_la_base(base_vacia.con) == antes
    assert meses.hay_meses(base_vacia.con) is False


def test_despues_de_un_fallo_la_conexion_sigue_sirviendo(base, monkeypatch):
    # RN-76: el fallo no deja la conexión con un "with" abierto: las demás funciones de la
    # app guardan normalmente y el bloque más externo vuelve a hacer commit.
    lista = lista_con_sueldo(base.con)
    _fallar_en(monkeypatch, me_deben, "agregar_item", 2)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert base.con._nivel == 0
    gastos.agregar_gasto(base.con, base.mes_id, "Despues del fallo", base.varios, 1000, "fijo")
    assert base.con.in_transaction is False
    base.con.rollback()  # si hubiera quedado algo sin guardar, esto lo borraría
    assert "Despues del fallo" in [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]


# ---------------------------------------------------------------------------
# No se puede confirmar
# ---------------------------------------------------------------------------


def test_confirmar_sin_filas_para_importar_lanza_el_pie_y_no_guarda(base):
    # RN-68 / CA-57.8: "No hay filas para importar."
    lista = revisar(base.con)
    solo(lista)
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "No hay filas para importar."
    assert foto_de_la_base(base.con) == antes


def test_confirmar_con_dos_sueldos_lanza_el_pie_y_no_guarda(base):
    # CA-57.6 (lógica): "Marcaste 2 filas como sueldo; dejá una sola."
    lista = lista_con_sueldo(base.con)
    lista.cambiar_tipo(sin_nombre(lista, 9).indice, "sueldo")
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "Marcaste 2 filas como sueldo; dejá una sola."
    assert foto_de_la_base(base.con) == antes


def test_confirmar_con_filas_con_errores_lanza_el_pie_y_no_guarda(base):
    # CA-57.8: "Hay 2 filas con errores. Corregilas, ignoralas o destildalas para continuar."
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Obra social").indice, "fijo")
    lista.cambiar_tipo(fila(lista, "Deuda freezer").indice, "fijo")
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == (
        "Hay 2 filas con errores. Corregilas, ignoralas o destildalas para continuar."
    )
    assert foto_de_la_base(base.con) == antes


def test_confirmar_con_una_fila_con_error_usa_el_singular(base):
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Obra social").indice, "fijo")
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == (
        "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar."
    )


def test_ca_57_5_pagado_mayor_que_el_monto_impide_confirmar_y_con_centavos(base):
    # CA-57.5 / O70: "Gas | 1234,50 | 1234,56" -> mensaje con centavos y no se guarda.
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Gas", "D2": 1234.5, "E2": 1234.56}
    lista = revisar(base.con, xlsx(celdas))
    assert lista.errores(fila(lista, "Gas")) == [
        "El pagado ($ 1.234,56) es mayor que el monto ($ 1.234,50)."
    ]
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)


def test_ca_57_5_subir_el_monto_o_bajar_el_pagado_permite_confirmar(base):
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Luz", "D2": 10000, "E2": 12000}
    lista = revisar(base.con, xlsx(celdas))
    luz = fila(lista, "Luz")
    assert lista.editar_fila(luz.indice, "fijo", "Luz", 1200000, pagado_cent=1200000) == {}
    confirmar(lista)
    g = gasto_por_nombre(base.con, base.mes_id, "Luz")
    assert pagos.pendiente(base.con, g["id"]) == 0


def test_ca_57_5_pagado_bajado_deja_pendiente(base):
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Luz", "D2": 10000, "E2": 12000}
    lista = revisar(base.con, xlsx(celdas))
    luz = fila(lista, "Luz")
    assert lista.editar_fila(luz.indice, "fijo", "Luz", 1000000, pagado_cent=400000) == {}
    confirmar(lista)
    g = gasto_por_nombre(base.con, base.mes_id, "Luz")
    assert pagos.pendiente(base.con, g["id"]) == 600000


# ---------------------------------------------------------------------------
# O67: categoría o persona archivada / inexistente elegida con editar_fila
# ---------------------------------------------------------------------------


def _archivar_categoria(con, nombre):
    cid = _ids_categorias(con)[nombre]
    with con:
        con.execute("UPDATE categorias SET archivado = 1 WHERE id = ?", (cid,))
    return cid


def test_o67_categoria_archivada_elegida_en_editar_fila_no_se_acepta(base):
    # O67: editar_fila rechaza una categoría archivada con "Elegí una categoría." y no
    # cambia la fila.
    archivada = _archivar_categoria(base.con, "Salud")
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    antes = copy.deepcopy(gym)
    assert lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=archivada) == {
        "categoria": "Elegí una categoría."
    }
    assert fila(lista, "Gym") == antes
    assert lista.puede_confirmar() is True


def test_o67_categoria_inexistente_elegida_en_editar_fila_no_se_acepta(base):
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=999999) == {
        "categoria": "Elegí una categoría."
    }
    assert fila(lista, "Gym").categoria is None


def test_o67_categoria_nueva_ajena_a_la_revision_no_se_acepta(base):
    # O67: una Nueva que no se agregó en esta revisión no vale.
    from app.logica.revision_importacion import Nueva

    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=Nueva("Fantasma")) == {
        "categoria": "Elegí una categoría."
    }


def test_o67_categoria_activa_y_categoria_nueva_siguen_aceptandose(base):
    lista = revisar(base.con)
    nueva = lista.agregar_categoria("Importado")
    assert lista.editar_fila(fila(lista, "Gym").indice, "fijo", "Gym", 5000000,
                             categoria=base.servicios) == {}
    assert lista.editar_fila(fila(lista, "Servicios").indice, "fijo", "Servicios", 8200000,
                             categoria=nueva) == {}


def test_o67_categoria_archivada_despues_de_elegirla_da_error_de_fila_y_no_guarda_nada(base):
    # O67: la categoría se archiva mientras dura la revisión: la fila pasa a "Elegí una
    # categoría.", el pie cuenta el error y confirmar lanza el texto del pie sin guardar.
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    assert lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=base.salud) == {}
    _archivar_categoria(base.con, "Salud")
    assert lista.errores(gym) == ["Elegí una categoría."]
    assert lista.puede_confirmar() is False
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == (
        "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar."
    )
    assert foto_de_la_base(base.con) == antes
    # Desarchivada, vuelve a funcionar.
    catalogos.desarchivar(base.con, catalogos.CATEGORIAS, base.salud)
    assert lista.errores(gym) == []
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Gym")["categoria"] == "Salud"


def test_o67_categoria_archivada_en_una_cuota_no_se_acepta(base):
    archivada = _archivar_categoria(base.con, "Salud")
    lista = revisar(base.con)
    avant = fila(lista, AVANT)
    assert lista.editar_fila(avant.indice, "cuota", AVANT, avant.monto_cent, categoria=archivada,
                             cuota_actual=3, cuota_total=3) == {"categoria": "Elegí una categoría."}


def test_o67_categoria_por_defecto_archivada_da_error_en_las_filas_que_la_usan(base):
    # O67: la categoría por defecto archivada cuenta como sin elegir: error en las filas
    # de gasto y cuota que la usan.
    archivada = _archivar_categoria(base.con, "Salud")
    lista = revisar(base.con)
    lista.cambiar_categoria_defecto(archivada)
    assert lista.errores(fila(lista, "Gym")) == ["Elegí una categoría."]
    assert lista.errores(fila(lista, AVANT)) == ["Elegí una categoría."]
    assert lista.puede_confirmar() is False
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert foto_de_la_base(base.con) == antes
    lista.cambiar_categoria_defecto(base.varios)
    assert lista.puede_confirmar() is True
    confirmar(lista)


def test_o67_categoria_archivada_en_una_fila_que_no_se_importa_no_molesta(base):
    # O67: la categoría mala solo importa si la fila se importa.
    archivada = _archivar_categoria(base.con, "Salud")
    lista = revisar(base.con)
    gym = fila(lista, "Gym")
    lista.editar_fila(gym.indice, "fijo", "Gym", 5000000, categoria=archivada)
    lista.cambiar_tilde(gym.indice, False)
    confirmar(lista)
    assert "Gym" not in [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]


def test_o67_persona_archivada_elegida_en_editar_fila_no_se_acepta(base):
    with base.con:
        base.con.execute("UPDATE personas SET archivado = 1 WHERE id = ?", (base.marsu,))
    lista = revisar(base.con)
    tacones = fila(lista, "tacones chiqui baby")
    assert lista.editar_fila(tacones.indice, "me_deben", "tacones chiqui baby", 678500,
                             persona=base.marsu) == {"persona": "Elegí una persona."}


def test_o67_persona_inexistente_elegida_en_editar_fila_no_se_acepta(base):
    lista = revisar(base.con)
    tacones = fila(lista, "tacones chiqui baby")
    assert lista.editar_fila(tacones.indice, "me_deben", "tacones chiqui baby", 678500,
                             persona=999999) == {"persona": "Elegí una persona."}


def test_persona_archivada_despues_de_armar_la_lista_da_error_de_fila(base):
    # RN-65 + O67: el título "Marsu" propuso la persona al armar la lista. Si se archiva
    # después, la fila queda en "Elegí una persona.", no se puede confirmar y no se guarda
    # nada. Destildándola, el resto se importa.
    lista = revisar(base.con)
    with base.con:
        base.con.execute("UPDATE personas SET archivado = 1 WHERE id = ?", (base.marsu,))
    tacones = fila(lista, "tacones chiqui baby")
    assert lista.errores(tacones) == ["Elegí una persona."]
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value).startswith("Hay 1 fila con errores")
    assert foto_de_la_base(base.con) == antes
    lista.cambiar_tilde(tacones.indice, False)
    confirmar(lista)
    assert cantidad(base.con, "items_me_deben") == 2


# ---------------------------------------------------------------------------
# Bordes del guardado
# ---------------------------------------------------------------------------


def test_confirmar_dos_veces_la_misma_lista_no_guarda_dos_veces(base):
    # O76: la segunda llamada (doble clic) lanza "Esta importación ya se guardó." y no toca
    # la base.
    lista = revisar(base.con)
    solo(lista, ("Servicios", 4))
    assert lista.confirmada is False
    confirmar(lista)
    assert lista.confirmada is True
    despues_de_la_primera = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "Esta importación ya se guardó."
    assert error.value.__cause__ is None
    assert foto_de_la_base(base.con) == despues_de_la_primera
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert nombres.count("Servicios") == 1


def test_confirmar_dos_veces_con_persona_nueva_da_el_mismo_aviso(base):
    # O76: con una persona nueva también es "ya se guardó" (no el mensaje genérico).
    lista = revisar(base.con)
    juan = lista.agregar_persona("Juan")
    solo(lista, ("Servicios", 4))
    serv = fila(lista, "Servicios")
    lista.editar_fila(serv.indice, "me_deben", "Servicios", 8200000, persona=juan)
    confirmar(lista)
    antes = foto_de_la_base(base.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "Esta importación ya se guardó."
    assert foto_de_la_base(base.con) == antes


def test_confirmar_dos_veces_en_el_primer_uso_y_con_mes_nuevo(base_vacia):
    lista = revisar(base_vacia.con)
    confirmar(lista)
    antes = foto_de_la_base(base_vacia.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "Esta importación ya se guardó."
    assert foto_de_la_base(base_vacia.con) == antes


def test_confirmar_una_lista_ya_guardada_avisa_antes_que_el_pie(base):
    # O76: el aviso de "ya se guardó" gana sobre "No hay filas para importar." y similares.
    lista = revisar(base.con)
    solo(lista, ("Servicios", 4))
    confirmar(lista)
    lista.cambiar_tilde(fila(lista, "Servicios").indice, False)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == "Esta importación ya se guardó."


def test_si_el_guardado_falla_la_lista_no_queda_confirmada_y_se_puede_reintentar(base, monkeypatch):
    # O76: confirmada solo pasa a True al terminar bien.
    lista = revisar(base.con)
    solo(lista, ("Servicios", 4), ("Prestamo MP", 22))
    original = _fallar_en(monkeypatch, me_deben, "agregar_item", 1)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == MENSAJE_ERROR
    assert lista.confirmada is False
    monkeypatch.setattr(me_deben, "agregar_item", original)
    confirmar(lista)
    assert lista.confirmada is True
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert nombres.count("Servicios") == 1
    assert cantidad(base.con, "items_me_deben") == 1


def test_confirmar_con_errores_no_marca_confirmada(base):
    lista = revisar(base.con)
    lista.cambiar_tipo(fila(lista, "Obra social").indice, "fijo")
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert lista.confirmada is False


def test_cuota_de_600_cuotas_se_guarda(base):
    # CA-53.7: cuota 1 de 600 -> el plan de 600 cuotas se guarda sin fallar.
    lista = revisar(base.con, xlsx({"C1": "Casa 1/600", "D1": 1000}))
    confirmar(lista)
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert plan["cantidad_cuotas"] == 600
    assert cuotas.ultima_cuota(plan) == (2076, 9)


def test_cuota_600_de_600_se_guarda_con_primera_cuota_en_1976(base):
    lista = revisar(base.con, xlsx({"C1": "Casa 600/600", "D1": 1000}))
    confirmar(lista)
    plan = base.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert (plan["primer_anio"], plan["primer_mes"]) == (1976, 11)
    assert gasto_por_nombre(base.con, base.mes_id, "Casa 600/600")["tipo"] == "cuota"


ANIO_NO_VALIDO = "Con esta cuota, el plan quedaría en un año no válido. Revisá la cuota actual y la cantidad."


def test_bug_36_cuota_con_primera_cuota_antes_del_ano_1000_da_error_de_fila(base_vacia):
    # BUG-36: destino 1000-06 y cuota 600 de 600 (primera cuota en el año 950): error en
    # la fila, sin nota de plan, y no se puede confirmar.
    lista = revisar(base_vacia.con, xlsx({"C1": "Casa 600/600", "D1": 1000}))
    lista.cambiar_mes_destino(1000, 6)
    casa = fila(lista, "Casa 600/600")
    assert lista.errores(casa) == [ANIO_NO_VALIDO]
    assert not any(n.startswith("Plan de") for n in lista.notas(casa))
    assert lista.puede_confirmar() is False


def test_bug_36_confirmar_lanza_el_pie_y_no_guarda_nada(base_vacia):
    lista = revisar(base_vacia.con, xlsx({"C1": "Casa 600/600", "D1": 1000}))
    lista.cambiar_mes_destino(1000, 6)
    antes = foto_de_la_base(base_vacia.con)
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert str(error.value) == (
        "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar."
    )
    assert foto_de_la_base(base_vacia.con) == antes
    assert meses.hay_meses(base_vacia.con) is False


def test_bug_36_limites_del_ano_1000_en_la_primera_cuota(base_vacia):
    # 600/600 en 1049-12 -> primera 1000-01 (válida); en 1049-11 -> 999-12 (inválida).
    lista = revisar(base_vacia.con, xlsx({"C1": "Casa 600/600", "D1": 1000}))
    casa = fila(lista, "Casa 600/600")
    lista.cambiar_mes_destino(1049, 12)
    assert lista.errores(casa) == []
    assert "primera Enero 1000" in " ".join(lista.notas(casa))
    lista.cambiar_mes_destino(1049, 11)
    assert lista.errores(casa) == [ANIO_NO_VALIDO]


def test_bug_36_el_error_se_recalcula_al_cambiar_el_mes_destino(base_vacia):
    lista = revisar(base_vacia.con, xlsx({"C1": "Casa 600/600", "D1": 1000}))
    casa = fila(lista, "Casa 600/600")
    assert lista.errores(casa) == []
    lista.cambiar_mes_destino(1000, 6)
    assert lista.errores(casa) == [ANIO_NO_VALIDO]
    lista.cambiar_mes_destino(2026, 10)
    assert lista.errores(casa) == []
    assert any(n.startswith("Plan de 600 cuotas") for n in lista.notas(casa))


def test_bug_36_el_dialogo_de_edicion_no_acepta_el_plan_en_un_ano_invalido(base_vacia):
    lista = revisar(base_vacia.con, xlsx({"C1": "Casa 1/12", "D1": 1000}))
    lista.cambiar_mes_destino(1000, 6)
    casa = fila(lista, "Casa 1/12")
    assert lista.editar_fila(casa.indice, "cuota", "Casa", 100000, cuota_actual=12,
                             cuota_total=600) == {"cuota": ANIO_NO_VALIDO}
    assert lista.editar_fila(casa.indice, "cuota", "Casa", 100000, cuota_actual=1,
                             cuota_total=12) == {}


def test_bug_36_una_fila_destildada_no_muestra_el_error(base_vacia):
    lista = revisar(base_vacia.con, xlsx({"C1": "Casa 600/600", "D1": 1000}))
    lista.cambiar_mes_destino(1000, 6)
    lista.cambiar_tilde(fila(lista, "Casa 600/600").indice, False)
    assert lista.filas_con_errores() == []


def test_bug_36_la_misma_fila_en_un_mes_normal_sigue_guardandose(base):
    # Sin regresión: 600/600 en 2026-10 (primera 1976-11) se guarda.
    confirmar(revisar(base.con, xlsx({"C1": "Casa 600/600", "D1": 1000})))


def test_o77_cuota_cuya_ultima_cuota_cae_en_el_ano_10000_da_error_de_fila(base_vacia):
    # O77: destino 9999-12 y cuota 1 de 12: la última cuota sería 10000-11 (5 dígitos).
    lista = revisar(base_vacia.con, xlsx({"C1": "Algo 1/12", "D1": 1000}))
    lista.cambiar_mes_destino(9999, 12)
    algo = fila(lista, "Algo 1/12")
    assert lista.errores(algo) == [ANIO_NO_VALIDO]
    assert not any(n.startswith("Plan de") for n in lista.notas(algo))
    antes = foto_de_la_base(base_vacia.con)
    with pytest.raises(ErrorDeValidacion):
        confirmar(lista)
    assert foto_de_la_base(base_vacia.con) == antes


def test_o77_12_de_12_en_diciembre_9999_es_valida_y_se_guarda(base_vacia):
    # Primera 9999-01, última 9999-12.
    lista = revisar(base_vacia.con, xlsx({"C1": "Algo 12/12", "D1": 1000}))
    lista.cambiar_mes_destino(9999, 12)
    assert lista.errores(fila(lista, "Algo 12/12")) == []
    confirmar(lista)
    plan = base_vacia.con.execute("SELECT * FROM planes_cuotas").fetchone()
    assert cuotas.ultima_cuota(plan) == (9999, 12)


def test_o77_1_de_12_en_enero_9999_es_valida_y_en_diciembre_9999_no(base_vacia):
    lista = revisar(base_vacia.con, xlsx({"C1": "Algo 1/12", "D1": 1000}))
    lista.cambiar_mes_destino(9999, 1)
    assert lista.errores(fila(lista, "Algo 1/12")) == []
    lista.cambiar_mes_destino(9999, 12)
    assert lista.errores(fila(lista, "Algo 1/12")) == [ANIO_NO_VALIDO]


def test_nombre_con_espacios_se_guarda_sin_espacios_de_mas(base):
    # RN-67/O68: el nombre se guarda limpio.
    lista = revisar(base.con, xlsx({"C1": "  Luz   y gas  ", "D1": 100}))
    confirmar(lista)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert "Luz y gas" in nombres


def test_monto_de_un_centavo_y_monto_grande_se_guardan(base):
    lista = revisar(base.con, xlsx({"C1": "Chico", "D1": 0.01, "C2": "Grande", "D2": 999999999999}))
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Chico")["monto_cent"] == 1
    assert gasto_por_nombre(base.con, base.mes_id, "Grande")["monto_cent"] == 99999999999900


def test_gastos_con_el_mismo_nombre_repetido_en_el_archivo_se_guardan_los_dos(base):
    # CA-56.3: "Nafta" dos veces: quedan dos Nafta de 30.000.
    lista = revisar(base.con, xlsx({"C1": "Nafta", "D1": 30000, "C2": "Nafta", "D2": 30000}))
    confirmar(lista)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert nombres.count("Nafta") == 2


def test_ca_56_1_alquiler_tildado_queda_repetido(base):
    # CA-56.1: si se tilda el Alquiler "ya existe", quedan dos.
    lista = revisar(base.con)
    alquiler = fila(lista, "Alquiler")
    assert lista.notas(alquiler) == ["Ya existe en Octubre 2026. Viene destildada."]
    lista.cambiar_tilde(alquiler.indice, True)
    assert lista.notas(alquiler) == ["Ya existe en Octubre 2026. Si la importás, queda repetida."]
    confirmar(lista)
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert nombres.count("Alquiler") == 2


def test_ca_56_1_alquiler_destildado_queda_uno_solo(base):
    confirmar(revisar(base.con))
    nombres = [g["nombre"] for g in gastos.listar_gastos(base.con, base.mes_id)]
    assert nombres.count("Alquiler") == 1


def test_ca_54_1_sin_tocar_la_categoria_quedan_en_varios_y_sin_medio(base):
    # CA-54.1: gastos y plan en Varios, sin medio de pago ("Sin medio de pago" en el total).
    confirmar(revisar(base.con))
    totales = dict(gastos.totales_por_medio(base.con, base.mes_id))
    assert "Sin medio de pago" in totales
    assert sum(totales.values()) == pagos.totales_del_mes(base.con, base.mes_id)["total"]


def test_ca_54_2_categoria_propia_de_una_fila_sobrevive_al_cambio_de_defecto(base):
    # CA-54.2: Internet en Servicios; el resto toma la categoría por defecto nueva.
    lista = revisar(base.con)
    internet = fila(lista, "Internet", 5)
    lista.editar_fila(internet.indice, "fijo", "Internet", 3870000, pagado_cent=3870000,
                      categoria=base.servicios)
    lista.cambiar_categoria_defecto(base.vivienda)
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Internet")["categoria"] == "Servicios"
    assert gasto_por_nombre(base.con, base.mes_id, "Gym")["categoria"] == "Vivienda"
    assert gasto_por_nombre(base.con, base.mes_id, AVANT)["categoria"] == "Vivienda"


def test_la_fecha_de_hoy_de_la_lista_es_la_de_pagos_e_items(base):
    # La fecha sale de lista.hoy (no del reloj), así las pruebas y la pantalla coinciden.
    lista = revisar(base.con, hoy=date(2026, 10, 20))
    confirmar(lista)
    assert {p["fecha"] for p in base.con.execute("SELECT fecha FROM pagos")} == {"2026-10-20"}
    assert {i["fecha"] for i in base.con.execute("SELECT fecha FROM items_me_deben")} == {
        "2026-10-20"
    }


# ---------------------------------------------------------------------------
# Renombres públicos (ListaRevision.con, .hoy, mes_existente, sumar_meses)
# ---------------------------------------------------------------------------


def test_nombres_publicos_de_la_lista(base):
    from app.logica import revision_importacion

    lista = revisar(base.con)
    assert lista.con is base.con
    assert lista.hoy == HOY
    assert lista.mes_existente()["id"] == base.mes_id
    assert lista.mes_existente(2026, 11) is None
    assert revision_importacion.sumar_meses(2026, 10, -2) == (2026, 8)
    assert revision_importacion.sumar_meses(2026, 1, -1) == (2025, 12)
    assert revision_importacion.sumar_meses(2026, 12, 1) == (2027, 1)
    for viejo in ("_con", "_hoy", "_mes_existente"):
        assert not hasattr(lista, viejo)
    assert not hasattr(revision_importacion, "_sumar_meses")


# ---------------------------------------------------------------------------
# cuotas.cuota_en_mes y MAXIMO_CUOTAS
# ---------------------------------------------------------------------------


def test_cuota_en_mes_devuelve_la_cuota_existente(base):
    plan = cuotas.crear_plan(base.con, "Heladera", base.varios, None, 3000000, 12, 2026, 8,
                             hoy=HOY)
    existente = gasto_por_nombre(base.con, base.mes_id, "Heladera")["id"]
    assert cuotas.cuota_en_mes(base.con, plan, base.mes_id) == existente
    assert cantidad(base.con, "gastos") == 2  # Alquiler y la cuota: no crea otra.


def test_cuota_en_mes_crea_la_cuota_en_un_mes_pasado_si_el_plan_esta_activo(base):
    agosto = insertar_mes(base.con, 2026, 8)
    plan = cuotas.crear_plan(base.con, "Heladera", base.varios, None, 3000000, 12, 2026, 8,
                             hoy=HOY)
    assert base.con.execute("SELECT COUNT(*) FROM gastos WHERE mes_id = ?", (agosto,)).fetchone()[0] == 0
    gasto_id = cuotas.cuota_en_mes(base.con, plan, agosto)
    assert gastos.obtener_gasto(base.con, gasto_id)["mes_id"] == agosto
    assert cuotas.cuota_en_mes(base.con, plan, agosto) == gasto_id  # segunda vez: la misma


def test_cuota_en_mes_devuelve_none_si_el_plan_no_tiene_cuota_ese_mes(base):
    julio = insertar_mes(base.con, 2026, 7)
    plan = cuotas.crear_plan(base.con, "Heladera", base.varios, None, 3000000, 12, 2026, 8,
                             hoy=HOY)
    assert cuotas.cuota_en_mes(base.con, plan, julio) is None


def test_cuota_en_mes_con_plan_o_mes_inexistente(base):
    with pytest.raises(ErrorDeValidacion):
        cuotas.cuota_en_mes(base.con, 999, base.mes_id)
    plan = cuotas.crear_plan(base.con, "Heladera", base.varios, None, 3000000, 12, 2026, 8,
                             hoy=HOY)
    with pytest.raises(ErrorDeValidacion):
        cuotas.cuota_en_mes(base.con, plan, 999)


def test_cuota_en_mes_no_crea_cuota_si_fue_omitida_a_mano(base):
    # RN-24: una cuota que el usuario borró a mano (omitida) no se vuelve a crear.
    plan = cuotas.crear_plan(base.con, "Heladera", base.varios, None, 3000000, 12, 2026, 8,
                             hoy=HOY)
    cuota = gasto_por_nombre(base.con, base.mes_id, "Heladera")["id"]
    gastos.borrar_gasto(base.con, cuota)
    assert cuotas.cuota_en_mes(base.con, plan, base.mes_id) is None


def test_maximo_de_cuotas(base):
    assert cuotas.MAXIMO_CUOTAS == 600
    cuotas.crear_plan(base.con, "Casa", base.varios, None, 100000, 600, 2026, 10, hoy=HOY)
    with pytest.raises(ErrorDeValidacion) as error:
        cuotas.crear_plan(base.con, "Casa2", base.varios, None, 100000, 601, 2026, 10, hoy=HOY)
    assert str(error.value) == "La cantidad de cuotas es demasiado grande."


# ---------------------------------------------------------------------------
# Reglas nuevas: O63 y O70 vistas desde el guardado
# ---------------------------------------------------------------------------


def test_o63_fila_vacia_cierra_el_pagado_y_el_numero_de_abajo_no_es_pagado(base):
    # O63: el "Pagado" vale hasta la primera fila vacía. El 7 de abajo es un número sin
    # nombre (no se importa) y la fila "Gas" no trae pagado.
    celdas = {"C1": "Gasto", "E1": "Pagado", "C2": "Luz", "D2": 100, "E2": 40,
              "C4": "Gas", "D4": 200, "E4": 7}
    lista = revisar(base.con, xlsx(celdas))
    assert fila(lista, "Luz").pagado_cent == 4000
    assert fila(lista, "Gas").pagado_cent is None
    confirmar(lista)
    assert gasto_por_nombre(base.con, base.mes_id, "Luz")["pagado_cent"] == 4000
    assert gasto_por_nombre(base.con, base.mes_id, "Gas")["pagado_cent"] == 0


def test_o62_pagado_de_fila_sin_monto_completada_se_importa_sin_pagos(base):
    # CA-51.5: "Servicios" sin monto y 3 bajo "Pagado"; completada con monto 1: sin pagos.
    celdas = celdas_planilla()
    celdas.pop("D4")
    celdas["E4"] = 3
    lista = revisar(base.con, xlsx(celdas))
    serv = fila(lista, "Servicios")
    assert serv.pagado_cent is None
    assert lista.editar_fila(serv.indice, "fijo", "Servicios", 100) == {}
    confirmar(lista)
    g = gasto_por_nombre(base.con, base.mes_id, "Servicios")
    assert (g["monto_cent"], g["pagado_cent"]) == (100, 0)


def test_planilla_con_e11_pagado_la_lista_tiene_error_y_no_se_confirma(base):
    # CA-51.5: Monotributo con pagado 66.021 > 66.020,12 -> no se puede confirmar.
    lista = revisar(base.con, planilla_con({"E11": "Pagado"}))
    with pytest.raises(ErrorDeValidacion) as error:
        confirmar(lista)
    assert "Hay 1 fila con errores" in str(error.value)


# ---------------------------------------------------------------------------
# texto_resultado: bordes
# ---------------------------------------------------------------------------


def test_texto_resultado_singulares_y_union():
    r = Resultado(1, 2026, 11, 1, 1, 1, None, False)
    frase, completar = texto_resultado(r)
    assert frase == (
        'Se importaron: 1 gasto, 1 plan de cuotas y 1 ítem "me deben" en Noviembre 2026.'
    )
    assert len(completar) == 2


def test_texto_resultado_dos_partes_se_unen_con_y():
    frase, _ = texto_resultado(Resultado(1, 2026, 10, 2, 0, 0, 130000, False))
    assert frase == "Se importaron: 2 gastos y el sueldo (US$ 1.300,00) en Octubre 2026."


def test_texto_resultado_sin_cotizacion_agrega_la_linea():
    _, completar = texto_resultado(Resultado(1, 2026, 10, 0, 0, 1, None, True))
    assert completar == [
        "Si alguno es compartido, marcalo desde el gasto.",
        "Cargá la cotización de Octubre 2026 en el Resumen.",
    ]


def test_texto_resultado_solo_sueldo_con_mes_sin_cotizacion():
    # El mes se creó sin cotización y solo se importó el sueldo: solo la línea de la cotización.
    r = Resultado(1, 2026, 10, 0, 0, 0, 130000, True)
    assert texto_resultado(r)[1] == ["Cargá la cotización de Octubre 2026 en el Resumen."]
    assert r.pantalla == "resumen"


def test_constantes_de_los_textos():
    assert MENSAJE_ERROR == "No se pudo importar. No se guardó ningún dato."
    assert confirmar_importacion.AVISO_SIN_DESHACER == (
        "Esta importación no se puede deshacer. Si algo sale mal, lo corregís a mano en la app."
    )


# ---------------------------------------------------------------------------
# Escenario completo de punta a punta
# ---------------------------------------------------------------------------


def test_cargar_primera_importacion_y_confirmar_da_lo_mismo_que_el_ayudante(base):
    # Cruce de datos: el ayudante de las pruebas de la revisión (cargar_primera_importacion)
    # deja lo mismo que confirmar() sobre una base con un mes: mismos nombres y montos.
    confirmar(lista_con_sueldo(base.con))
    de_confirmar = sorted(
        (g["nombre"], g["monto_cent"]) for g in gastos.listar_gastos(base.con, base.mes_id)
    )
    from app.logica import base_datos

    otra = base_datos.conectar(":memory:")
    try:
        mes = meses.crear_primer_mes(otra, 2026, 10, 120000, 160000)
        catalogos.crear(otra, catalogos.CATEGORIAS, "Varios")
        sofia = catalogos.crear(otra, catalogos.PERSONAS, "Sofía")
        marsu = catalogos.crear(otra, catalogos.PERSONAS, "Marsu")
        gastos.agregar_gasto(otra, mes, "Alquiler", _ids_categorias(otra)["Vivienda"], 26000000,
                             "fijo")
        b = SimpleNamespace(con=otra, mes_id=mes, varios=_ids_categorias(otra)["Varios"],
                            sofia=sofia, marsu=marsu)
        cargar_primera_importacion(b)
        del_ayudante = sorted(
            (g["nombre"], g["monto_cent"]) for g in gastos.listar_gastos(otra, mes)
        )
    finally:
        otra.close()
    assert de_confirmar == del_ayudante
