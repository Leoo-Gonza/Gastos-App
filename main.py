"""Arranca la app de gastos.

python main.py          -> ventana de Flet (como hasta ahora).
python main.py --edge   -> ventana de Microsoft Edge en modo aplicación
                           (la que usa Gastos.exe; ver app/interfaz/modo_edge.py).
"""

import sys

import flet as ft

from app.interfaz.aplicacion import main

if __name__ == "__main__":
    if "--edge" in sys.argv:
        from app.interfaz import modo_edge

        modo_edge.ejecutar(main)
    else:
        ft.run(main)
