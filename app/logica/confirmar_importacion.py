"""Importar Excel (v2): resumen previo, guardado y resultado (RN-71 a RN-73, RN-76).

Guarda lo decidido en la lista de revisión en un solo paso: o se guarda todo, o
nada (gracias a base_datos.Conexion, que deja anidar los "with con:" de las
funciones de siempre dentro de un bloque grande).
"""

from dataclasses import dataclass

from app.logica import catalogos, cuotas, gastos, me_deben, meses, pagos
from app.logica.errores import ErrorDeValidacion
from app.logica.formato import formatear_ars, formatear_usd, nombre_mes, unir_con_y
from app.logica.revision_importacion import (
    ListaRevision,
    Nueva,
    FilaRevision,
    sumar_meses,
)

MENSAJE_ERROR = "No se pudo importar. No se guardó ningún dato."
AVISO_SIN_DESHACER = "Esta importación no se puede deshacer. Si algo sale mal, lo corregís a mano en la app."


def _cantidad(n: int, singular: str, plural: str) -> str:
    return f"1 {singular}" if n == 1 else f"{n} {plural}"


def _importan(lista: ListaRevision, *tipos: str) -> list[FilaRevision]:
    return [f for f in lista.filas if f.se_importa and f.tipo in tipos]


def _fila_sueldo(lista: ListaRevision) -> FilaRevision | None:
    filas = _importan(lista, "sueldo")
    return filas[0] if filas else None


# ---------------------------------------------------------------------------
# Resumen previo (RN-76)
# ---------------------------------------------------------------------------


def resumen_previo(lista: ListaRevision) -> list[str]:
    """Las líneas de "Revisá antes de importar", en orden y solo las que corresponden."""
    lineas: list[str] = []
    mes = lista.nombre_mes_destino
    if not lista.mes_se_crea:
        lineas.append(f"Se va a cargar en {mes} (ya existe).")
    elif lista.es_primer_uso:
        lineas.append(f"Se va a crear {mes}, sin cotización, y cargar ahí los datos.")
    else:
        lineas.append(f"Se va a crear {mes} y cargar ahí los datos.")

    filas_gastos = _importan(lista, "fijo", "unico")
    if filas_gastos:
        total = sum(f.monto_cent for f in filas_gastos)
        pagado = sum(f.pagado_cent or 0 for f in filas_gastos)
        linea = (
            f"{_cantidad(len(filas_gastos), 'gasto', 'gastos')}: {formatear_ars(total)}"
        )
        if pagado:
            linea += f" (pagado {formatear_ars(pagado)})"
        lineas.append(linea)

    filas_cuotas = _importan(lista, "cuota")
    if filas_cuotas:
        detalles = [
            f"{f.nombre} (cuota {f.cuota_actual}/{f.cuota_total}, "
            f"{formatear_ars(f.monto_cent)} por mes)"
            for f in filas_cuotas
        ]
        cuantos = _cantidad(len(filas_cuotas), "plan de cuotas", "planes de cuotas")
        lineas.append(f"{cuantos}: {unir_con_y(detalles)}")

    filas_items = _importan(lista, "me_deben")
    if filas_items:
        por_persona: dict[str, int] = {}  # En el orden en que aparecen.
        for f in filas_items:
            nombre = lista.nombre_persona(f.persona)
            por_persona[nombre] = por_persona.get(nombre, 0) + 1
        detalle = ", ".join(f"{nombre} {n}" for nombre, n in por_persona.items())
        total = sum(f.monto_cent for f in filas_items)
        cuantos = _cantidad(len(filas_items), 'ítem "me deben"', 'ítems "me deben"')
        lineas.append(f"{cuantos}: {detalle} ({formatear_ars(total)} en total)")

    sueldo = _fila_sueldo(lista)
    if sueldo is not None:
        actual = lista.sueldo_actual_cent()
        nuevo = formatear_usd(sueldo.monto_cent)
        if actual is None or actual == sueldo.monto_cent:
            lineas.append(f"Sueldo: {nuevo}")
        else:
            lineas.append(f"Sueldo: {formatear_usd(actual)} -> {nuevo}")
    elif lista.mes_se_crea and lista.es_primer_uso:
        lineas.append(f"Sin sueldo: el sueldo de {mes} queda en {formatear_usd(0)}.")

    categorias, personas = lista.nuevas_en_uso()
    nuevas = [f'la categoría "{n.nombre}"' for n in categorias] + [
        f'la persona "{n.nombre}"' for n in personas
    ]
    if nuevas:
        lineas.append(f"Se crean también: {unir_con_y(nuevas)}.")

    no_importan = sum(1 for f in lista.filas if not f.se_importa)
    if no_importan == 1:
        lineas.append("No se importa 1 fila (ignorada o destildada).")
    elif no_importan:
        lineas.append(f"No se importan {no_importan} filas (ignoradas o destildadas).")

    lineas.append(AVISO_SIN_DESHACER)
    return lineas


# ---------------------------------------------------------------------------
# Guardar (RN-71, RN-72, RN-73, RN-76)
# ---------------------------------------------------------------------------


@dataclass
class Resultado:
    mes_id: int
    anio: int
    mes: int
    gastos: int
    planes: int
    items: int
    sueldo_cent: int | None
    sin_cotizacion: bool  # El mes quedó sin cotización (se creó en el primer uso).

    @property
    def pantalla(self) -> str:
        """Dónde sigue la app: Gastos, o Resumen si no hubo gastos ni cuotas (RN-76)."""
        return "gastos" if self.gastos or self.planes else "resumen"


def confirmar(lista: ListaRevision) -> Resultado:
    """Guarda todo en un solo paso. Si algo falla, no queda nada guardado y se
    lanza ErrorDeValidacion(MENSAJE_ERROR); el detalle queda en __cause__."""
    if lista.confirmada:
        # Un doble clic en "Importar" no puede guardar todo dos veces (O76).
        raise ErrorDeValidacion("Esta importación ya se guardó.")
    if not lista.puede_confirmar():
        raise ErrorDeValidacion(lista.estado_pie())
    con = lista.con
    try:
        with con:
            resultado = _guardar(lista)
    except Exception as error:
        raise ErrorDeValidacion(MENSAJE_ERROR) from error
    lista.confirmada = True
    return resultado


def _guardar(lista: ListaRevision) -> Resultado:
    con, hoy = lista.con, lista.hoy

    # 1. Categorías y personas nuevas, solo las que quedaron en uso.
    categorias, personas = lista.nuevas_en_uso()
    ids: dict[tuple[str, Nueva], int] = {}
    for nueva in categorias:
        ids[("cat", nueva)] = catalogos.crear(con, catalogos.CATEGORIAS, nueva.nombre)
    for nueva in personas:
        ids[("per", nueva)] = catalogos.crear(con, catalogos.PERSONAS, nueva.nombre)

    def id_de(valor, tipo: str) -> int:
        return ids[(tipo, valor)] if isinstance(valor, Nueva) else valor

    # 2. El mes destino (RN-73) y el sueldo (RN-70).
    sueldo = _fila_sueldo(lista)
    sueldo_cent = sueldo.monto_cent if sueldo else None
    sin_cotizacion = False
    if not lista.mes_se_crea:
        mes_id = lista.mes_existente()["id"]
        if sueldo_cent is not None:
            meses.editar_sueldo(con, mes_id, sueldo_cent)
    elif lista.es_primer_uso:
        mes_id = meses.crear_primer_mes(con, lista.anio, lista.mes, sueldo_cent or 0)
        sin_cotizacion = True
    else:
        ultimo = meses.obtener_ultimo_mes(con)
        mes_id = meses.crear_mes(
            con,
            lista.anio,
            lista.mes,
            sueldo_cent if sueldo_cent is not None else ultimo["sueldo_usd_cent"],
            ultimo["cotizacion_cent"],
        )

    def aplicar_pagado(gasto_id: int, fila: FilaRevision) -> None:
        """RN-69: igual al monto -> pagado completo; menor -> pago parcial."""
        if not fila.pagado_cent:
            return
        if fila.pagado_cent == fila.monto_cent:
            pagos.marcar_pagado(con, gasto_id, hoy)
        else:
            pagos.registrar_pago(con, gasto_id, fila.pagado_cent, hoy)

    # 3. Gastos fijos y pagos únicos, con sus pagos.
    filas_gastos = _importan(lista, "fijo", "unico")
    for fila in filas_gastos:
        gasto_id = gastos.agregar_gasto(
            con,
            mes_id,
            fila.nombre,
            id_de(lista.categoria_de(fila), "cat"),
            fila.monto_cent,
            fila.tipo,
        )
        aplicar_pagado(gasto_id, fila)

    # 4. Planes de cuotas (RN-71): primera cuota = mes destino − (n − 1) meses.
    filas_cuotas = _importan(lista, "cuota")
    for fila in filas_cuotas:
        primer_anio, primer_mes = sumar_meses(
            lista.anio, lista.mes, -(fila.cuota_actual - 1)
        )
        plan_id = cuotas.crear_plan(
            con,
            fila.nombre,
            id_de(lista.categoria_de(fila), "cat"),
            None,  # Sin medio de pago (RN-77).
            fila.monto_cent,
            fila.cuota_total,
            primer_anio,
            primer_mes,
            hoy,
        )
        # La cuota va en el mes destino aunque sea anterior al actual (excepción a RN-30).
        cuota_id = cuotas.cuota_en_mes(con, plan_id, mes_id)
        aplicar_pagado(cuota_id, fila)

    # 5. Ítems "me deben" (RN-72).
    filas_items = _importan(lista, "me_deben")
    for fila in filas_items:
        item_id = me_deben.agregar_item(
            con, id_de(fila.persona, "per"), fila.nombre, fila.monto_cent, hoy
        )
        if fila.cobrado:
            me_deben.marcar_item_cobrado(con, item_id, True)

    return Resultado(
        mes_id,
        lista.anio,
        lista.mes,
        len(filas_gastos),
        len(filas_cuotas),
        len(filas_items),
        sueldo_cent,
        sin_cotizacion,
    )


# ---------------------------------------------------------------------------
# Resultado (RN-76)
# ---------------------------------------------------------------------------


def texto_resultado(resultado: Resultado) -> tuple[str, list[str]]:
    """(frase principal, líneas de "Para completar:") del diálogo "Importación terminada"."""
    partes = []
    if resultado.gastos:
        partes.append(_cantidad(resultado.gastos, "gasto", "gastos"))
    if resultado.planes:
        partes.append(_cantidad(resultado.planes, "plan de cuotas", "planes de cuotas"))
    if resultado.items:
        partes.append(_cantidad(resultado.items, 'ítem "me deben"', 'ítems "me deben"'))
    if resultado.sueldo_cent is not None:
        partes.append(f"el sueldo ({formatear_usd(resultado.sueldo_cent)})")
    mes = nombre_mes(resultado.anio, resultado.mes)
    principal = f"Se importaron: {unir_con_y(partes)} en {mes}."

    completar = []
    if resultado.gastos or resultado.planes:
        completar.append(
            "Los gastos quedaron sin medio de pago. Podés ponérselo en Gastos."
        )
    if resultado.gastos or resultado.items:
        completar.append("Si alguno es compartido, marcalo desde el gasto.")
    if resultado.sin_cotizacion:
        completar.append(f"Cargá la cotización de {mes} en el Resumen.")
    return principal, completar
