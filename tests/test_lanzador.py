"""Pruebas de scripts/lanzador.py (Gastos.exe) y scripts/construir_exe.py.

No se lanza ningún .exe ni se corre PyInstaller: subprocess, el cartel de Windows
(MessageBoxW) y las carpetas se reemplazan con monkeypatch y tmp_path. Rutas inventadas.
"""

import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

RAIZ = Path(__file__).resolve().parents[1]
LANZADOR = RAIZ / "scripts" / "lanzador.py"
CONSTRUIR = RAIZ / "scripts" / "construir_exe.py"
LINEA_RUTA = 'RUTA_PROYECTO = r"C:\\Proyectos\\gastos-app"'


def _cargar(ruta, nombre):
    """Importa un script de scripts/ (no es un paquete) como módulo nuevo."""
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def lanzador():
    return _cargar(LANZADOR, "lanzador_en_prueba")


def _proyecto(carpeta, con_python=True):
    """Una carpeta de proyecto inventada: main.py y (opcional) .venv\\Scripts\\pythonw.exe."""
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / "main.py").write_text("# inventado\n", encoding="utf-8")
    if con_python:
        python = carpeta / ".venv" / "Scripts" / "pythonw.exe"
        python.parent.mkdir(parents=True)
        python.touch()
    return carpeta


@pytest.fixture
def sistema(monkeypatch, lanzador, tmp_path):
    """Registra los carteles y los Popen; el log va a una carpeta temporal."""
    r = SimpleNamespace(carteles=[], popen=[], temp=tmp_path / "temp")
    r.temp.mkdir()
    windll = SimpleNamespace(
        user32=SimpleNamespace(MessageBoxW=lambda *a: r.carteles.append(a))
    )
    monkeypatch.setattr(lanzador, "ctypes", SimpleNamespace(windll=windll))

    def popen(comando, **kwargs):
        r.popen.append((comando, kwargs))

    monkeypatch.setattr(
        lanzador,
        "subprocess",
        SimpleNamespace(
            Popen=popen,
            DETACHED_PROCESS=getattr(subprocess, "DETACHED_PROCESS", 0x8),
            CREATE_NEW_PROCESS_GROUP=getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200
            ),
        ),
    )
    monkeypatch.setattr(lanzador.tempfile, "gettempdir", lambda: str(r.temp))
    return r


def _exe_en(monkeypatch, lanzador, carpeta):
    """Simula que Gastos.exe (congelado por PyInstaller) está en "carpeta"."""
    monkeypatch.setattr(lanzador.sys, "frozen", True, raising=False)
    monkeypatch.setattr(lanzador.sys, "executable", str(carpeta / "Gastos.exe"))


# ---------------------------------------------------------------------------
# buscar_proyecto
# ---------------------------------------------------------------------------


def test_carpeta_del_exe_congelado(monkeypatch, lanzador, tmp_path):
    _exe_en(monkeypatch, lanzador, tmp_path / "Escritorio")
    assert lanzador.carpeta_del_exe() == tmp_path / "Escritorio"


def test_carpeta_del_exe_sin_congelar(monkeypatch, lanzador):
    # Corriendo el .py (sin PyInstaller): la carpeta del script.
    monkeypatch.delattr(lanzador.sys, "frozen", raising=False)
    assert lanzador.carpeta_del_exe() == LANZADOR.parent


def test_buscar_proyecto_prefiere_la_carpeta_del_exe(monkeypatch, lanzador, tmp_path):
    # Gastos.exe dentro de un proyecto: se usa ese, aunque RUTA_PROYECTO sea otro.
    junto = _proyecto(tmp_path / "proyecto copiado")
    guardada = _proyecto(tmp_path / "guardada")
    _exe_en(monkeypatch, lanzador, junto)
    monkeypatch.setattr(lanzador, "RUTA_PROYECTO", str(guardada))
    assert lanzador.buscar_proyecto() == junto


def test_buscar_proyecto_usa_la_ruta_guardada(monkeypatch, lanzador, tmp_path):
    # Gastos.exe en el escritorio (sin main.py al lado): la ruta guardada al armarlo.
    guardada = _proyecto(tmp_path / "Mis Proyectos" / "gastos-ñ")
    escritorio = tmp_path / "Escritorio"
    escritorio.mkdir()
    _exe_en(monkeypatch, lanzador, escritorio)
    monkeypatch.setattr(lanzador, "RUTA_PROYECTO", str(guardada))
    assert lanzador.buscar_proyecto() == guardada


def test_buscar_proyecto_sin_main_py_no_cuenta(monkeypatch, lanzador, tmp_path):
    # Una carpeta que existe pero sin main.py no es el proyecto: None.
    vacia = tmp_path / "vacia"
    vacia.mkdir()
    _exe_en(monkeypatch, lanzador, vacia)
    monkeypatch.setattr(lanzador, "RUTA_PROYECTO", str(tmp_path / "no existe"))
    assert lanzador.buscar_proyecto() is None


# ---------------------------------------------------------------------------
# main del lanzador
# ---------------------------------------------------------------------------


def test_sin_proyecto_avisa_y_no_lanza(monkeypatch, lanzador, sistema, tmp_path):
    monkeypatch.setattr(lanzador, "buscar_proyecto", lambda: None)
    monkeypatch.setattr(lanzador, "RUTA_PROYECTO", r"D:\Inventada\gastos")
    lanzador.main()
    [(ventana, texto, titulo, tipo)] = sistema.carteles
    assert (ventana, titulo, tipo) == (None, "Gastos", 0x10)
    assert texto.startswith("No encuentro la carpeta de la app.")
    assert r"D:\Inventada\gastos" in texto
    assert sistema.popen == []


def test_sin_pythonw_avisa_y_no_lanza(monkeypatch, lanzador, sistema, tmp_path):
    proyecto = _proyecto(tmp_path / "proyecto", con_python=False)
    monkeypatch.setattr(lanzador, "buscar_proyecto", lambda: proyecto)
    lanzador.main()
    [(_, texto, titulo, _)] = sistema.carteles
    assert titulo == "Gastos"
    assert str(proyecto / ".venv" / "Scripts" / "pythonw.exe") in texto
    assert "python -m venv .venv" in texto
    assert "pip install -r requirements.txt" in texto
    assert sistema.popen == []


def test_lanza_pythonw_main_py_edge(monkeypatch, lanzador, sistema, tmp_path):
    # Todo en orden: pythonw main.py --edge, en la carpeta del proyecto, separado
    # del lanzador, con UTF-8 y la salida al log de %TEMP%. Sin carteles.
    proyecto = _proyecto(tmp_path / "proyecto con espacios")
    monkeypatch.setattr(lanzador, "buscar_proyecto", lambda: proyecto)
    monkeypatch.setenv("VARIABLE_INVENTADA", "sigue")
    lanzador.main()
    assert sistema.carteles == []
    [(comando, kwargs)] = sistema.popen
    assert comando == [
        str(proyecto / ".venv" / "Scripts" / "pythonw.exe"),
        "main.py",
        "--edge",
    ]
    assert Path(kwargs["cwd"]) == proyecto
    assert kwargs["env"]["PYTHONUTF8"] == "1"
    assert kwargs["env"]["VARIABLE_INVENTADA"] == "sigue"
    flags = lanzador.subprocess.DETACHED_PROCESS
    flags |= lanzador.subprocess.CREATE_NEW_PROCESS_GROUP
    assert kwargs["creationflags"] == flags
    registro = sistema.temp / "gastos-app.log"
    assert Path(kwargs["stdout"].name) == registro
    assert kwargs["stderr"] is kwargs["stdout"]
    assert registro.exists()


# ---------------------------------------------------------------------------
# construir_exe
# ---------------------------------------------------------------------------


def test_la_linea_de_ruta_existe_una_vez_en_el_lanzador():
    # construir_exe.py reemplaza ESTA línea exacta. Si alguien la cambia en
    # lanzador.py (comillas, ruta, espacios), esta prueba falla.
    fuente = LANZADOR.read_text(encoding="utf-8")
    assert fuente.count(LINEA_RUTA) == 1


def test_construir_exe_busca_la_misma_linea():
    # El texto que busca construir_exe.py es la misma línea del lanzador.
    arbol = ast.parse(CONSTRUIR.read_text(encoding="utf-8"))
    buscados = [
        n.args[0].value
        for n in ast.walk(arbol)
        if isinstance(n, ast.Call)
        and getattr(n.func, "attr", None) == "replace"
        and n.args
        and isinstance(n.args[0], ast.Constant)
    ]
    assert buscados == [LINEA_RUTA]


@pytest.fixture
def construir(monkeypatch, tmp_path):
    """construir_exe con un proyecto inventado (ruta con espacios y ñ) y sin PyInstaller."""
    proyecto = tmp_path / "Mis Proyectos" / "gastos-ñ"
    (proyecto / "scripts").mkdir(parents=True)
    (proyecto / "scripts" / "lanzador.py").write_text(
        LANZADOR.read_text(encoding="utf-8"), encoding="utf-8"
    )
    modulo = _cargar(CONSTRUIR, "construir_en_prueba")
    monkeypatch.setattr(modulo, "PROYECTO", proyecto)
    monkeypatch.setattr(modulo, "BUILD", proyecto / "build")
    corridas = []

    def run(comando, check):
        corridas.append((comando, check))
        dist = proyecto / "build" / "dist"
        dist.mkdir(parents=True, exist_ok=True)
        (dist / "Gastos.exe").write_bytes(b"exe inventado")

    monkeypatch.setattr(modulo.subprocess, "run", run)
    escritorio = tmp_path / "Escritorio"
    escritorio.mkdir()
    monkeypatch.setattr(modulo, "carpeta_escritorio", lambda: escritorio)
    monkeypatch.setattr(sys, "argv", ["construir_exe.py"])
    return SimpleNamespace(
        modulo=modulo, proyecto=proyecto, corridas=corridas, escritorio=escritorio
    )


def test_construir_exe_pone_la_ruta_real(construir):
    # La copia del lanzador en build/ tiene la ruta real del proyecto (y nada más
    # cambia); como módulo, RUTA_PROYECTO vale exactamente esa ruta.
    construir.modulo.main()
    copia = construir.proyecto / "build" / "Gastos.py"
    texto = copia.read_text(encoding="utf-8")
    assert LINEA_RUTA not in texto
    assert f'RUTA_PROYECTO = r"{construir.proyecto}"' in texto
    original = LANZADOR.read_text(encoding="utf-8")
    assert texto.replace(str(construir.proyecto), r"C:\Proyectos\gastos-app") == (
        original
    )
    assert _cargar(copia, "gastos_armado").RUTA_PROYECTO == str(construir.proyecto)


def test_construir_exe_llama_a_pyinstaller_y_copia(construir):
    # PyInstaller en un solo archivo, sin consola, llamado Gastos; el .exe queda en
    # el proyecto y no en el escritorio (sin --escritorio).
    construir.modulo.main()
    [(comando, check)] = construir.corridas
    assert check is True
    assert comando[:3] == [sys.executable, "-m", "PyInstaller"]
    for opcion in ["--onefile", "--noconsole", "--name=Gastos", "--noconfirm"]:
        assert opcion in comando
    assert comando[-1] == str(construir.proyecto / "build" / "Gastos.py")
    assert (construir.proyecto / "Gastos.exe").read_bytes() == b"exe inventado"
    assert not (construir.escritorio / "Gastos.exe").exists()


def test_construir_exe_con_escritorio(construir, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["construir_exe.py", "--escritorio"])
    construir.modulo.main()
    assert (construir.escritorio / "Gastos.exe").read_bytes() == b"exe inventado"


def test_construir_exe_falla_si_pyinstaller_falla(construir, monkeypatch):
    # Si PyInstaller falla (check=True), no se copia un .exe viejo ni a medias.
    def falla(comando, check):
        raise subprocess.CalledProcessError(1, comando)

    monkeypatch.setattr(construir.modulo.subprocess, "run", falla)
    with pytest.raises(subprocess.CalledProcessError):
        construir.modulo.main()
    assert not (construir.proyecto / "Gastos.exe").exists()


# ---------------------------------------------------------------------------
# Archivos de apoyo
# ---------------------------------------------------------------------------


def test_gitignore_excluye_lo_que_genera_el_armado():
    lineas = (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    for patron in ["build/", "dist/", "*.spec", "Gastos.exe", "datos-privados/"]:
        assert patron in lineas


def test_requirements_tiene_las_nuevas_dependencias():
    nombres = {
        re.split(r"[=<>]", linea)[0].strip().lower()
        for linea in (RAIZ / "requirements.txt")
        .read_text(encoding="utf-8")
        .splitlines()
        if linea.strip() and not linea.startswith("#")
    }
    assert {"flet", "flet-web", "pyinstaller"} <= nombres


def test_command_de_macos():
    # El .command va a la raíz del proyecto y corre main.py con el Python del .venv.
    texto = (RAIZ / "scripts" / "abrir_gastos.command").read_text(encoding="utf-8")
    assert texto.startswith("#!/bin/bash")
    assert 'cd "$(dirname "$0")/.."' in texto
    assert "./.venv/bin/python main.py" in texto


# ---------------------------------------------------------------------------
# Ronda 27: O50 (el log se agrega, no se pisa)
# ---------------------------------------------------------------------------


def test_o50_el_log_se_abre_para_agregar(monkeypatch, lanzador, sistema, tmp_path):
    # O50: lo que dejó un arranque anterior en el log sigue ahí después de otro
    # doble clic (texto inventado, con tildes para verificar UTF-8).
    proyecto = _proyecto(tmp_path / "proyecto")
    monkeypatch.setattr(lanzador, "buscar_proyecto", lambda: proyecto)
    registro = sistema.temp / "gastos-app.log"
    registro.write_text(
        "Error inventado del primer arranque: año, cotización\n", encoding="utf-8"
    )
    lanzador.main()
    [(_, kwargs)] = sistema.popen
    assert kwargs["stdout"].mode == "a"
    assert kwargs["stdout"].encoding.lower().replace("-", "") == "utf8"
    assert registro.read_text(encoding="utf-8") == (
        "Error inventado del primer arranque: año, cotización\n"
    )


def test_o50_dos_dobles_clics_conservan_ambos_registros(
    monkeypatch, lanzador, sistema, tmp_path
):
    # O50: dos aperturas seguidas; cada "proceso" escribe en el log y al final
    # están las dos líneas, en orden.
    proyecto = _proyecto(tmp_path / "proyecto")
    monkeypatch.setattr(lanzador, "buscar_proyecto", lambda: proyecto)
    lineas = iter(["arranque 1\n", "arranque 2\n"])

    def popen(comando, **kwargs):
        sistema.popen.append((comando, kwargs))
        kwargs["stdout"].write(next(lineas))

    monkeypatch.setattr(lanzador.subprocess, "Popen", popen)
    lanzador.main()
    lanzador.main()
    registro = sistema.temp / "gastos-app.log"
    assert registro.read_text(encoding="utf-8") == "arranque 1\narranque 2\n"


def test_o50_sin_log_previo_lo_crea(monkeypatch, lanzador, sistema, tmp_path):
    # Borde: la primera vez el log no existe; "a" lo crea vacío.
    proyecto = _proyecto(tmp_path / "proyecto")
    monkeypatch.setattr(lanzador, "buscar_proyecto", lambda: proyecto)
    registro = sistema.temp / "gastos-app.log"
    assert not registro.exists()
    lanzador.main()
    assert registro.read_text(encoding="utf-8") == ""
