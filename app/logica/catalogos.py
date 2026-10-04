"""Listas editables por el usuario: categorías, medios de pago y personas.

Las tres tablas tienen la misma forma (id, nombre, archivado) y las mismas reglas
(RN-49, RN-50), así que comparten estas funciones. La tabla se elige con las
constantes CATEGORIAS, MEDIOS_PAGO o PERSONAS.
"""

import sqlite3
import unicodedata

from app.logica.errores import ErrorDeValidacion

CATEGORIAS = "categorias"
MEDIOS_PAGO = "medios_pago"
PERSONAS = "personas"

# Para cada lista: qué tablas y columnas la usan. Sirve para saber si un
# elemento está "en uso" y entonces se archiva en vez de borrarse (RN-49).
_USOS = {
    CATEGORIAS: [("gastos", "categoria_id"), ("planes_cuotas", "categoria_id")],
    MEDIOS_PAGO: [("gastos", "medio_pago_id"), ("planes_cuotas", "medio_pago_id")],
    PERSONAS: [("partes_gasto", "persona_id"), ("items_me_deben", "persona_id")],
}


def _validar_tabla(tabla: str) -> None:
    # Los nombres de tabla no se pueden pasar como parámetro "?" en SQL, así que
    # se arman con f-string. Por eso solo se aceptan los de esta lista fija.
    if tabla not in _USOS:
        raise ValueError(f"Lista desconocida: {tabla}")


def _validar_nombre(
    con: sqlite3.Connection, tabla: str, nombre: str, excluir_id: int | None = None
) -> str:
    # split + join quita espacios al principio y al final, y deja uno solo entre palabras.
    limpio = " ".join(nombre.split())
    if not limpio:
        raise ErrorDeValidacion("El nombre no puede estar vacío.")

    # La comparación sin mayúsculas se hace en Python con casefold() porque
    # COLLATE NOCASE de SQLite no reconoce letras como Ñ o Á.
    for fila in con.execute(f"SELECT id, nombre, archivado FROM {tabla}"):
        if fila["id"] != excluir_id and fila["nombre"].casefold() == limpio.casefold():
            mensaje = f'Ya existe "{fila["nombre"]}".'
            if fila["archivado"]:
                mensaje += " Está en la lista de archivados: podés desarchivarlo."
            raise ErrorDeValidacion(mensaje)
    return limpio


def listar(
    con: sqlite3.Connection, tabla: str, incluir_archivados: bool = False
) -> list[sqlite3.Row]:
    """Elementos ordenados por nombre. Sin archivados, salvo que se pidan."""
    _validar_tabla(tabla)
    condicion = "" if incluir_archivados else "WHERE archivado = 0"
    filas = con.execute(
        f"SELECT id, nombre, archivado FROM {tabla} {condicion}"
    ).fetchall()
    # Se ordena en Python y no con ORDER BY porque SQLite pone "Árbol" después
    # de "Vivienda": no sabe que la Á es una A.
    return sorted(filas, key=lambda fila: _clave_orden(fila["nombre"]))


def _clave_orden(nombre: str) -> str:
    # NFD separa cada letra de su acento ("Á" -> "A" + "´"); después se descartan
    # los acentos (combining) y se pasa a minúsculas con casefold.
    descompuesto = unicodedata.normalize("NFD", nombre)
    sin_acentos = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return sin_acentos.casefold()


def _exigir_existente(con: sqlite3.Connection, tabla: str, id_: int) -> None:
    if obtener(con, tabla, id_) is None:
        raise ErrorDeValidacion("Ese elemento ya no existe.")


def obtener(con: sqlite3.Connection, tabla: str, id_: int) -> sqlite3.Row | None:
    _validar_tabla(tabla)
    return con.execute(
        f"SELECT id, nombre, archivado FROM {tabla} WHERE id = ?", (id_,)
    ).fetchone()


def crear(con: sqlite3.Connection, tabla: str, nombre: str) -> int:
    """Crea un elemento y devuelve su id."""
    _validar_tabla(tabla)
    limpio = _validar_nombre(con, tabla, nombre)
    with con:
        cursor = con.execute(f"INSERT INTO {tabla} (nombre) VALUES (?)", (limpio,))
    return cursor.lastrowid


def renombrar(con: sqlite3.Connection, tabla: str, id_: int, nombre: str) -> None:
    _validar_tabla(tabla)
    _exigir_existente(con, tabla, id_)
    limpio = _validar_nombre(con, tabla, nombre, excluir_id=id_)
    with con:
        con.execute(f"UPDATE {tabla} SET nombre = ? WHERE id = ?", (limpio, id_))


def esta_en_uso(con: sqlite3.Connection, tabla: str, id_: int) -> bool:
    _validar_tabla(tabla)
    for tabla_uso, columna in _USOS[tabla]:
        fila = con.execute(
            f"SELECT 1 FROM {tabla_uso} WHERE {columna} = ? LIMIT 1", (id_,)
        ).fetchone()
        if fila:
            return True
    return False


def eliminar(con: sqlite3.Connection, tabla: str, id_: int) -> str:
    """Borra el elemento, o lo archiva si está en uso (RN-49).

    Devuelve "borrado" o "archivado" para que la pantalla avise qué pasó.
    """
    _validar_tabla(tabla)
    _exigir_existente(con, tabla, id_)
    with con:
        if esta_en_uso(con, tabla, id_):
            con.execute(f"UPDATE {tabla} SET archivado = 1 WHERE id = ?", (id_,))
            return "archivado"
        con.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_,))
        return "borrado"


def desarchivar(con: sqlite3.Connection, tabla: str, id_: int) -> None:
    _validar_tabla(tabla)
    _exigir_existente(con, tabla, id_)
    with con:
        con.execute(f"UPDATE {tabla} SET archivado = 0 WHERE id = ?", (id_,))
