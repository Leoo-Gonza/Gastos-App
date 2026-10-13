"""Abrir la app en una ventana de Microsoft Edge en "modo aplicación".

Windows (Control inteligente de aplicaciones) bloquea en este equipo el programa
de Flet que dibuja la ventana. Edge viene con Windows y está firmado por
Microsoft, así que no se bloquea. En modo aplicación (--app) Edge abre una
ventana sin pestañas ni barra de direcciones: a la vista es una app más.

Cómo funciona:
1. Flet sirve la app en esta misma computadora (127.0.0.1, un puerto libre).
   Nada sale a internet: los datos siguen en datos-privados/.
2. Se abre Edge apuntando a esa dirección.
3. Cuando se cierra la ventana de Edge, se cierra también la app.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable
from pathlib import Path

import flet as ft

# Dónde suele estar Edge en Windows.
_RUTAS_EDGE = [
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    / "Microsoft/Edge/Application/msedge.exe",
]


def buscar_edge() -> Path | None:
    """La ruta de msedge.exe, o None si no está instalado."""
    for ruta in _RUTAS_EDGE:
        if ruta.exists():
            return ruta
    encontrado = shutil.which("msedge")
    return Path(encontrado) if encontrado else None


def puerto_libre() -> int:
    """Un puerto TCP libre en esta computadora (el sistema elige uno que no se use)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def comando_edge(edge: Path, url: str, perfil: Path) -> list[str]:
    """Los argumentos para abrir Edge como ventana de aplicación.

    --user-data-dir: un perfil propio de la app. Así Edge abre un proceso aparte
    (no se mezcla con el Edge que el usuario ya tenga abierto) y se puede saber
    cuándo se cerró la ventana. Las demás opciones evitan carteles de Edge
    (bienvenida, "¿navegador predeterminado?", sincronización).
    """
    return [
        str(edge),
        f"--app={url}",
        f"--user-data-dir={perfil}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-sync",
        "--window-size=1280,800",
    ]


def esperar_servidor(puerto: int, segundos: float = 30) -> bool:
    """Espera a que Flet empiece a atender en el puerto. True si llegó a tiempo."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            # En Windows, un intento a un puerto cerrado tarda ~2 s si no se le
            # pone un límite (Windows reintenta antes de rendirse) (O49).
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                return True
        time.sleep(0.2)
    return False


def carpeta_perfil() -> Path:
    """El perfil de Edge de la app: siempre el mismo, así la bienvenida de Edge
    aparece a lo sumo la primera vez. Va en AppData (la carpeta temporal se
    limpia sola) y no en el proyecto, para no mezclarlo con el código."""
    base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(base) / "gastos-app" / "edge"


def puerto_en_uso(archivo: Path) -> int | None:
    """Si la app ya está abierta, el puerto donde atiende; si no, None."""
    try:
        puerto = int(archivo.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    # Un número que no es un puerto (archivo dañado o editado a mano) cuenta
    # como "no hay app abierta"; connect_ex fallaría con OverflowError (BUG-24).
    if not 1 <= puerto <= 65535:
        return None
    return puerto if esperar_servidor(puerto, segundos=1) else None


def ejecutar(main: Callable[[ft.Page], None]) -> None:
    """Corre la app y la muestra en una ventana de Edge. Vuelve cuando se cierra."""
    edge = buscar_edge()
    if edge is None:
        # Sin Edge, se abre en el navegador predeterminado (sigue funcionando).
        ft.run(main, view=ft.AppView.WEB_BROWSER)
        return

    perfil = carpeta_perfil()
    perfil.mkdir(parents=True, exist_ok=True)
    archivo_puerto = perfil.parent / "puerto.txt"
    abierta = puerto_en_uso(archivo_puerto)
    if abierta is not None:
        # Doble clic con la app ya abierta: otra ventana conectada a la misma
        # app. Edge la suma a su proceso (mismo perfil) y este programa termina.
        subprocess.Popen(comando_edge(edge, f"http://127.0.0.1:{abierta}", perfil))
        return

    puerto = puerto_libre()
    archivo_puerto.write_text(str(puerto), encoding="utf-8")
    url = f"http://127.0.0.1:{puerto}"

    def abrir_ventana():
        if not esperar_servidor(puerto):
            os._exit(1)
        ventana = subprocess.Popen(comando_edge(edge, url, perfil))
        # Hasta que el usuario cierra la ventana (y las otras que se hayan
        # abierto con doble clic: Edge mantiene el proceso mientras quede una).
        ventana.wait()
        archivo_puerto.unlink(missing_ok=True)
        # La app no tiene más ventana: se termina todo (también el servidor).
        os._exit(0)

    threading.Thread(target=abrir_ventana, daemon=True).start()
    # FLET_DISPLAY_URL_PREFIX evita que Flet abra además el navegador predeterminado:
    # la ventana la abre abrir_ventana() con Edge.
    os.environ["FLET_DISPLAY_URL_PREFIX"] = "Gastos:"
    # Flet prefiere estas variables a host/port: si quedaran definidas, el
    # servidor atendería en otro lugar y Edge no lo encontraría (O53).
    os.environ.pop("FLET_SERVER_IP", None)
    os.environ.pop("FLET_SERVER_PORT", None)
    ft.run(main, view=ft.AppView.WEB_BROWSER, host="127.0.0.1", port=puerto)
