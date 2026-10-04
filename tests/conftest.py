"""Fixtures compartidos por todas las pruebas.

Todas las pruebas usan una base SQLite en memoria (":memory:"), nunca la base real
de datos-privados/. Los datos son inventados.
"""

import sys
from pathlib import Path

import pytest

# Permite "import app" aunque pytest se ejecute sin configurar pythonpath.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from app.logica import base_datos, meses


@pytest.fixture
def con():
    """Conexión a una base nueva en memoria, con tablas y datos iniciales."""
    conexion = base_datos.conectar(":memory:")
    yield conexion
    conexion.close()


@pytest.fixture
def mes_id(con):
    """Mes base de los criterios (§7): 2026-10, sueldo 1.200 USD, cotización 1.600."""
    return meses.crear_primer_mes(con, 2026, 10, 120000, 160000)
