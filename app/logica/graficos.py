"""Datos de los gráficos (RF-40 a RF-42, RN-46 a RN-48).

Solo calcula: cómo se dibujan las barras lo decide la pantalla de gráficos.
"""

import sqlite3
from datetime import date

from app.logica import meses, prevision
from app.logica.formato import clave_orden
from app.logica.resumen import calcular_resumen


def gastos_por_categoria(con: sqlite3.Connection, mes_id: int) -> list[tuple[str, int]]:
    """RN-46: [(categoría, tu parte en centavos)], de mayor a menor.

    De un gasto compartido cuenta solo tu parte (monto − partes de las personas);
    los gastos en dólares, por su monto en pesos. Las categorías en 0 no aparecen.
    """
    filas = con.execute(
        """SELECT c.nombre AS categoria,
                  SUM(g.monto_cent - (SELECT COALESCE(SUM(pg.monto_cent), 0)
                                        FROM partes_gasto pg WHERE pg.gasto_id = g.id))
                      AS propio
             FROM gastos g JOIN categorias c ON c.id = g.categoria_id
            WHERE g.mes_id = ?
            GROUP BY g.categoria_id""",
        (mes_id,),
    ).fetchall()
    datos = [(f["categoria"], f["propio"]) for f in filas if f["propio"] > 0]
    # De mayor a menor; con montos iguales, por nombre (para que el orden sea estable).
    return sorted(datos, key=lambda par: (-par[1], clave_orden(par[0])))


def ahorro_por_mes(con: sqlite3.Connection) -> list[tuple[int, int, int | None]]:
    """RN-47: [(año, mes, ahorro en centavos de USD o None)] de todo el historial,
    del más viejo al más nuevo. None = sin cotización (RN-18)."""
    resultado = []
    for m in reversed(meses.listar_meses(con)):
        resumen = calcular_resumen(con, m["id"])
        resultado.append((m["anio"], m["mes"], resumen.ahorro_usd))
    return resultado


def prevision_de_gastos(
    con: sqlite3.Connection, hoy: date | None = None
) -> list[tuple[int, int, int]]:
    """RN-48: [(año, mes, gastos estimados)] de los 12 meses de la previsión."""
    return [
        (m.anio, m.mes, m.gastos) for m in prevision.calcular_prevision(con, hoy).meses
    ]
