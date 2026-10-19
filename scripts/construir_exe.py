"""Arma Gastos.exe (Windows).

Uso, desde la carpeta del proyecto:
    .venv\\Scripts\\python.exe scripts\\construir_exe.py              (deja Gastos.exe en el proyecto)
    .venv\\Scripts\\python.exe scripts\\construir_exe.py --escritorio (y una copia en el escritorio)

Solo hace falta volver a correrlo si cambia scripts/lanzador.py o si movés la
carpeta del proyecto. Los cambios en app/ se ven sin rearmar el .exe.
"""

import ctypes
import shutil
import struct
import subprocess
import sys
from pathlib import Path

import flet_web

PROYECTO = Path(__file__).resolve().parents[1]
BUILD = PROYECTO / "build"

# Logo de Flet (el rosa y azul que ya muestra la ventana), en dos tamaños.
# El .ico no admite más de 256 px, por eso no va el de 512.
LOGOS = [
    Path(flet_web.__file__).parent / "web" / "favicon.png",  # 32 px
    Path(flet_web.__file__).parent / "web" / "icons" / "icon-192.png",
]


def armar_icono(destino: Path) -> None:
    """Arma un .ico con los PNG del logo adentro, sin convertirlos.

    Windows acepta PNG dentro de un .ico, así que alcanza con escribir la
    cabecera a mano y no hace falta instalar Pillow.
    """
    imagenes = [ruta.read_bytes() for ruta in LOGOS]
    # Cabecera: 0 (reservado), 1 (tipo ícono), cantidad de imágenes.
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    indice = b""
    posicion = 6 + 16 * len(imagenes)  # Las imágenes van después del índice.
    for png in imagenes:
        # El ancho y el alto de un PNG están en los bytes 16 a 24.
        ancho, alto = struct.unpack(">II", png[16:24])
        # Una entrada por imagen: ancho, alto (1 byte cada uno), colores de
        # paleta, reservado, planos, bits por píxel, tamaño y dónde empieza.
        indice += struct.pack("<BBBBHHII", ancho, alto, 0, 0, 1, 32, len(png), posicion)
        posicion += len(png)
    destino.write_bytes(cabecera + indice + b"".join(imagenes))


def carpeta_escritorio() -> Path:
    """El escritorio real (puede estar dentro de OneDrive)."""
    buffer = ctypes.create_unicode_buffer(260)
    # 0x10 = CSIDL_DESKTOPDIRECTORY: Windows dice dónde está el escritorio.
    ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buffer)
    return Path(buffer.value)


def main() -> None:
    BUILD.mkdir(exist_ok=True)
    # Copia del lanzador con la ruta real del proyecto adentro.
    fuente = (PROYECTO / "scripts" / "lanzador.py").read_text(encoding="utf-8")
    fuente = fuente.replace(
        'RUTA_PROYECTO = r"C:\\Proyectos\\gastos-app"',
        f'RUTA_PROYECTO = r"{PROYECTO}"',
    )
    lanzador = BUILD / "Gastos.py"
    lanzador.write_text(fuente, encoding="utf-8")
    icono = BUILD / "Gastos.ico"
    armar_icono(icono)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",  # Un solo archivo .exe.
            "--noconsole",  # Sin ventana negra de consola.
            "--name=Gastos",
            f"--icon={icono}",  # Sin esto, PyInstaller pone su ícono (el disquete).
            "--noconfirm",
            f"--distpath={BUILD / 'dist'}",
            f"--workpath={BUILD / 'trabajo'}",
            f"--specpath={BUILD}",
            str(lanzador),
        ],
        check=True,
    )
    exe = PROYECTO / "Gastos.exe"
    shutil.copy2(BUILD / "dist" / "Gastos.exe", exe)
    print(f"Listo: {exe}")
    if "--escritorio" in sys.argv:
        destino = carpeta_escritorio() / "Gastos.exe"
        shutil.copy2(exe, destino)
        print(f"Copia en el escritorio: {destino}")


if __name__ == "__main__":
    main()
