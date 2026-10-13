"""Gastos.exe: el programa del doble clic.

Este archivo se convierte en Gastos.exe con scripts/construir_exe.py. No trae
la app adentro: busca la carpeta del proyecto y abre la app con el Python del
proyecto (.venv), en una ventana de Edge (python main.py --edge).

Por qué así y no un .exe con todo adentro: cada cambio que hagas en el código
se ve al instante, sin volver a armar el .exe; y el .exe queda chico.
"""

import ctypes
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Carpeta del proyecto. construir_exe.py la reemplaza por la ruta real al armar
# el .exe (así el .exe funciona también si lo copiás al escritorio).
RUTA_PROYECTO = r"C:\Proyectos\gastos-app"


def carpeta_del_exe() -> Path:
    # Dentro del .exe, sys.executable es el propio Gastos.exe.
    return Path(sys.executable if getattr(sys, "frozen", False) else __file__).parent


def buscar_proyecto() -> Path | None:
    """Primero la carpeta del .exe; si no, la ruta guardada al armarlo."""
    for carpeta in (carpeta_del_exe(), Path(RUTA_PROYECTO)):
        if (carpeta / "main.py").exists():
            return carpeta
    return None


def avisar(texto: str) -> None:
    """Un cartel de Windows (el .exe no tiene consola donde escribir)."""
    ctypes.windll.user32.MessageBoxW(
        None, texto, "Gastos", 0x10
    )  # 0x10 = ícono de error


def main() -> None:
    proyecto = buscar_proyecto()
    if proyecto is None:
        avisar(
            "No encuentro la carpeta de la app.\n\n"
            f"Tiene que estar en {RUTA_PROYECTO}, o Gastos.exe tiene que "
            "estar dentro de esa carpeta."
        )
        return
    # pythonw.exe es el Python "sin consola": no aparece la ventana negra.
    python = proyecto / ".venv" / "Scripts" / "pythonw.exe"
    if not python.exists():
        avisar(
            f"Falta el entorno de Python del proyecto ({python}).\n\n"
            "Crealo con: python -m venv .venv  y después  "
            ".venv\\Scripts\\pip install -r requirements.txt"
        )
        return
    # Si algo falla al arrancar, el detalle queda en este archivo. Se agrega al
    # final ("a"): con "w", un segundo doble clic borraría lo que escribe la
    # primera apertura (O50).
    registro = Path(tempfile.gettempdir()) / "gastos-app.log"
    with registro.open("a", encoding="utf-8") as salida:
        subprocess.Popen(
            [str(python), "main.py", "--edge"],
            cwd=proyecto,
            stdout=salida,
            stderr=salida,
            # Para que la app siga abierta aunque este lanzador termine.
            creationflags=subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NEW_PROCESS_GROUP,
            env={**os.environ, "PYTHONUTF8": "1"},
        )


if __name__ == "__main__":
    main()
