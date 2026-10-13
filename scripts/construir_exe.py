"""Arma Gastos.exe (Windows).

Uso, desde la carpeta del proyecto:
    .venv\\Scripts\\python.exe scripts\\construir_exe.py              (deja Gastos.exe en el proyecto)
    .venv\\Scripts\\python.exe scripts\\construir_exe.py --escritorio (y una copia en el escritorio)

Solo hace falta volver a correrlo si cambia scripts/lanzador.py o si movés la
carpeta del proyecto. Los cambios en app/ se ven sin rearmar el .exe.
"""

import ctypes
import shutil
import subprocess
import sys
from pathlib import Path

PROYECTO = Path(__file__).resolve().parents[1]
BUILD = PROYECTO / "build"


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

    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--onefile",  # Un solo archivo .exe.
            "--noconsole",  # Sin ventana negra de consola.
            "--name=Gastos",
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
