"""Pruebas del modo Edge (app/interfaz/modo_edge.py) y de main.py.

No se abre ninguna ventana real: subprocess.Popen, os._exit, ft.run y los hilos se
reemplazan con monkeypatch, y el perfil de Edge va a una carpeta temporal (tmp_path),
nunca a la de AppData real ni a datos-privados/.
"""

import os
import runpy
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import flet as ft
import pytest

from app.interfaz import aplicacion, modo_edge

RAIZ = Path(__file__).resolve().parents[1]


class Salida(Exception):
    """Reemplaza a os._exit: corta la ejecución y guarda el código."""

    def __init__(self, codigo):
        super().__init__(codigo)
        self.codigo = codigo


@pytest.fixture
def servidor():
    """Un socket escuchando en 127.0.0.1 (como si Flet ya atendiera)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    s.listen()
    yield s.getsockname()[1]
    s.close()


def _puerto_muerto():
    """Un puerto donde no escucha nadie."""
    return modo_edge.puerto_libre()


# ---------------------------------------------------------------------------
# Funciones sueltas
# ---------------------------------------------------------------------------


def test_comando_edge(tmp_path):
    # Edge en modo aplicación, con perfil propio y sin carteles de primera vez.
    edge = tmp_path / "msedge.exe"
    perfil = tmp_path / "perfil con espacios"
    comando = modo_edge.comando_edge(edge, "http://127.0.0.1:5000", perfil)
    assert comando[0] == str(edge)
    assert "--app=http://127.0.0.1:5000" in comando
    assert f"--user-data-dir={perfil}" in comando
    assert "--no-first-run" in comando
    assert "--no-default-browser-check" in comando
    # Cada opción es un solo argumento (una ruta con espacios no se parte).
    assert all(isinstance(a, str) for a in comando)


def test_puerto_libre_se_puede_usar():
    # El puerto que devuelve está en el rango válido y se puede ocupar.
    puerto = modo_edge.puerto_libre()
    assert 1024 <= puerto <= 65535
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", puerto))
        s.listen()


def test_esperar_servidor_con_alguien_escuchando(servidor):
    # Con el servidor ya atendiendo, responde True enseguida.
    inicio = time.monotonic()
    assert modo_edge.esperar_servidor(servidor, segundos=5) is True
    assert time.monotonic() - inicio < 2


def test_esperar_servidor_sin_nadie_escuchando():
    # Sin servidor, False al vencer el tiempo (en Windows cada intento rechazado
    # tarda ~2 s: ver O49 en el reporte; acá solo se pide que termine).
    inicio = time.monotonic()
    assert modo_edge.esperar_servidor(_puerto_muerto(), segundos=0.3) is False
    assert time.monotonic() - inicio < 10


def test_esperar_servidor_que_arranca_tarde(monkeypatch):
    # Los primeros intentos fallan y después atiende: True (sin sockets reales).
    intentos = []

    class SocketFalso:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, segundos):
            limites.append(segundos)

        def connect_ex(self, direccion):
            intentos.append(direccion)
            return 0 if len(intentos) >= 3 else 10061

    limites = []
    monkeypatch.setattr(modo_edge.socket, "socket", SocketFalso)
    monkeypatch.setattr(modo_edge.time, "sleep", lambda s: None)
    assert modo_edge.esperar_servidor(5000, segundos=5) is True
    assert intentos == [("127.0.0.1", 5000)] * 3
    # Cada intento tiene un límite corto (O49): sin él, en Windows tarda ~2 s.
    assert limites == [0.3] * 3


def test_carpeta_perfil_con_localappdata(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert modo_edge.carpeta_perfil() == tmp_path / "gastos-app" / "edge"


@pytest.mark.parametrize("valor", [None, ""])
def test_carpeta_perfil_sin_localappdata(monkeypatch, tmp_path, valor):
    # Sin LOCALAPPDATA (o vacía) usa la carpeta temporal.
    if valor is None:
        monkeypatch.delenv("LOCALAPPDATA", raising=False)
    else:
        monkeypatch.setenv("LOCALAPPDATA", valor)
    monkeypatch.setattr(modo_edge.tempfile, "gettempdir", lambda: str(tmp_path))
    assert modo_edge.carpeta_perfil() == tmp_path / "gastos-app" / "edge"


def test_puerto_en_uso_archivo_inexistente(tmp_path):
    assert modo_edge.puerto_en_uso(tmp_path / "puerto.txt") is None


@pytest.mark.parametrize("contenido", ["", "abc", "12.5", "puerto: 5000", "\x00"])
def test_puerto_en_uso_contenido_invalido(tmp_path, contenido):
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(contenido, encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None


def test_puerto_en_uso_archivo_no_legible(tmp_path):
    # Borde: "puerto.txt" es una carpeta (OSError): se trata como "no hay app".
    (tmp_path / "puerto.txt").mkdir()
    assert modo_edge.puerto_en_uso(tmp_path / "puerto.txt") is None


@pytest.mark.parametrize("contenido", ["-1", "70000", "99999999999"])
def test_puerto_en_uso_numero_fuera_de_rango(tmp_path, contenido):
    # BUG-24: un puerto.txt con un número que no es un puerto (archivo dañado o
    # editado a mano) tiene que tratarse como "no hay app abierta" (None), igual
    # que el texto inválido. Hoy connect_ex lanza OverflowError y la app no abre.
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(contenido, encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None


def test_bug24_ejecutar_con_puerto_txt_fuera_de_rango(entorno):
    # BUG-24 visto desde el doble clic: con ese puerto.txt la app igual arranca
    # (se pisa el archivo con el puerto nuevo).
    entorno.perfil.mkdir(parents=True)
    archivo = entorno.perfil.parent / "puerto.txt"
    archivo.write_text("70000", encoding="utf-8")
    modo_edge.ejecutar(_principal)
    assert archivo.read_text(encoding="utf-8") == "54321"
    assert len(entorno.registro.run) == 1


def test_puerto_en_uso_puerto_cero(tmp_path):
    # Borde: "0" no es un puerto donde atienda nadie: None, sin error.
    archivo = tmp_path / "puerto.txt"
    archivo.write_text("0", encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None


def test_puerto_en_uso_puerto_muerto(tmp_path):
    # Quedó el archivo de una app que se cerró mal: el puerto no responde.
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(str(_puerto_muerto()), encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None


@pytest.mark.parametrize("formato", ["{}", "{}\n", " {} \r\n"])
def test_puerto_en_uso_puerto_vivo(tmp_path, servidor, formato):
    # La app está abierta: devuelve el puerto (tolera espacios y fin de línea).
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(formato.format(servidor), encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) == servidor


def test_buscar_edge(monkeypatch, tmp_path):
    # La primera ruta conocida que existe; si ninguna, lo que diga el PATH; si no, None.
    primera, segunda = tmp_path / "a" / "msedge.exe", tmp_path / "b" / "msedge.exe"
    monkeypatch.setattr(modo_edge, "_RUTAS_EDGE", [primera, segunda])
    monkeypatch.setattr(modo_edge.shutil, "which", lambda nombre: None)
    assert modo_edge.buscar_edge() is None
    segunda.parent.mkdir()
    segunda.touch()
    assert modo_edge.buscar_edge() == segunda
    primera.parent.mkdir()
    primera.touch()
    assert modo_edge.buscar_edge() == primera


def test_buscar_edge_en_el_path(monkeypatch, tmp_path):
    monkeypatch.setattr(modo_edge, "_RUTAS_EDGE", [tmp_path / "no" / "msedge.exe"])
    monkeypatch.setattr(
        modo_edge.shutil,
        "which",
        lambda nombre: str(tmp_path / "msedge.exe") if nombre == "msedge" else None,
    )
    assert modo_edge.buscar_edge() == tmp_path / "msedge.exe"


# ---------------------------------------------------------------------------
# ejecutar
# ---------------------------------------------------------------------------


@pytest.fixture
def entorno(monkeypatch, tmp_path):
    """Reemplaza todo lo que tocaría el sistema real y registra las llamadas."""
    registro = SimpleNamespace(run=[], popen=[], hilos=[], salidas=[])
    perfil = tmp_path / "gastos-app" / "edge"
    edge = tmp_path / "msedge.exe"
    monkeypatch.setattr(modo_edge, "buscar_edge", lambda: edge)
    monkeypatch.setattr(modo_edge, "carpeta_perfil", lambda: perfil)
    monkeypatch.setattr(modo_edge, "puerto_libre", lambda: 54321)

    def run(main, **kwargs):
        # Lo que había en el entorno en el momento de arrancar Flet.
        kwargs["_prefijo"] = os.environ.get("FLET_DISPLAY_URL_PREFIX")
        registro.run.append((main, kwargs))

    monkeypatch.setattr(modo_edge.ft, "run", run)

    class Popen:
        def __init__(self, comando, **kwargs):
            registro.popen.append(comando)

        def wait(self):
            return 0

    monkeypatch.setattr(modo_edge.subprocess, "Popen", Popen)

    class Hilo:
        def __init__(self, target, daemon=False):
            registro.hilos.append(SimpleNamespace(target=target, daemon=daemon))

        def start(self):
            pass  # Se dispara a mano en las pruebas.

    monkeypatch.setattr(modo_edge.threading, "Thread", Hilo)

    def salir(codigo):
        registro.salidas.append(codigo)
        raise Salida(codigo)

    monkeypatch.setattr(modo_edge.os, "_exit", salir)
    # Para que monkeypatch deje la variable como estaba al terminar la prueba.
    monkeypatch.setenv("FLET_DISPLAY_URL_PREFIX", "valor-previo")
    monkeypatch.delenv("FLET_DISPLAY_URL_PREFIX")
    return SimpleNamespace(registro=registro, perfil=perfil, edge=edge)


def _principal(page):
    """Función main falsa (nunca se ejecuta)."""


def test_ejecutar_sin_edge_usa_el_navegador(entorno, monkeypatch):
    # Sin Edge: ft.run en el navegador predeterminado; no se crea perfil ni puerto.txt.
    monkeypatch.setattr(modo_edge, "buscar_edge", lambda: None)
    modo_edge.ejecutar(_principal)
    r = entorno.registro
    assert len(r.run) == 1
    main, kwargs = r.run[0]
    assert main is _principal
    assert kwargs["view"] == ft.AppView.WEB_BROWSER
    assert r.popen == []
    assert r.hilos == []
    assert not (entorno.perfil.parent / "puerto.txt").exists()


def test_ejecutar_con_la_app_ya_abierta(entorno, servidor):
    # Doble clic con la app abierta: otra ventana de Edge al MISMO puerto, sin
    # arrancar otro servidor ni tocar puerto.txt.
    entorno.perfil.mkdir(parents=True)
    archivo = entorno.perfil.parent / "puerto.txt"
    archivo.write_text(str(servidor), encoding="utf-8")
    modo_edge.ejecutar(_principal)
    r = entorno.registro
    assert r.run == []
    assert r.hilos == []
    assert r.popen == [
        modo_edge.comando_edge(
            entorno.edge, f"http://127.0.0.1:{servidor}", entorno.perfil
        )
    ]
    assert archivo.read_text(encoding="utf-8") == str(servidor)


def test_ejecutar_caso_normal(entorno):
    # Primera apertura: crea el perfil, guarda puerto.txt, arranca Flet web solo en
    # 127.0.0.1 en ese puerto, con FLET_DISPLAY_URL_PREFIX (no abre otro navegador).
    modo_edge.ejecutar(_principal)
    r = entorno.registro
    archivo = entorno.perfil.parent / "puerto.txt"
    assert entorno.perfil.is_dir()
    assert archivo.read_text(encoding="utf-8") == "54321"
    [(main, kwargs)] = r.run
    assert main is _principal
    assert kwargs == {
        "view": ft.AppView.WEB_BROWSER,
        "host": "127.0.0.1",
        "port": 54321,
        "_prefijo": "Gastos:",
    }
    # Edge todavía no se abrió: lo abre el hilo cuando el servidor responde.
    assert r.popen == []
    [hilo] = r.hilos
    assert hilo.daemon is True


def test_ejecutar_con_puerto_txt_viejo(entorno):
    # Quedó un puerto.txt de una app que se cerró mal (puerto muerto): se arranca
    # normal y se pisa el archivo con el puerto nuevo.
    entorno.perfil.mkdir(parents=True)
    archivo = entorno.perfil.parent / "puerto.txt"
    archivo.write_text("basura", encoding="utf-8")
    modo_edge.ejecutar(_principal)
    assert archivo.read_text(encoding="utf-8") == "54321"
    assert len(entorno.registro.run) == 1


def test_hilo_abre_edge_y_al_cerrar_borra_puerto_y_termina(entorno, monkeypatch):
    # El hilo espera al servidor, abre Edge con la URL y el perfil, espera a que
    # se cierre, borra puerto.txt y termina todo con os._exit(0).
    monkeypatch.setattr(modo_edge, "esperar_servidor", lambda puerto: True)
    modo_edge.ejecutar(_principal)
    r = entorno.registro
    with pytest.raises(Salida):
        r.hilos[0].target()
    assert r.popen == [
        modo_edge.comando_edge(entorno.edge, "http://127.0.0.1:54321", entorno.perfil)
    ]
    assert not (entorno.perfil.parent / "puerto.txt").exists()
    assert r.salidas == [0]


def test_hilo_si_el_servidor_no_arranca_termina_con_error(entorno, monkeypatch):
    # Si Flet no atiende a tiempo: os._exit(1) sin abrir Edge.
    monkeypatch.setattr(modo_edge, "esperar_servidor", lambda puerto: False)
    modo_edge.ejecutar(_principal)
    r = entorno.registro
    with pytest.raises(Salida):
        r.hilos[0].target()
    assert r.popen == []
    assert r.salidas == [1]


def test_hilo_con_puerto_txt_ya_borrado(entorno, monkeypatch):
    # Borde: si puerto.txt ya no está al cerrar (lo borró otro), no rompe.
    monkeypatch.setattr(modo_edge, "esperar_servidor", lambda puerto: True)
    modo_edge.ejecutar(_principal)
    (entorno.perfil.parent / "puerto.txt").unlink()
    with pytest.raises(Salida):
        entorno.registro.hilos[0].target()
    assert entorno.registro.salidas == [0]


# ---------------------------------------------------------------------------
# main.py
# ---------------------------------------------------------------------------


@pytest.fixture
def lanzar_main(monkeypatch):
    """Corre main.py como programa con los argumentos dados, sin abrir nada."""
    llamadas = []
    monkeypatch.setattr(ft, "run", lambda *a, **k: llamadas.append(("ft.run", a, k)))
    monkeypatch.setattr(
        modo_edge, "ejecutar", lambda *a, **k: llamadas.append(("edge", a, k))
    )

    def lanzar(*argumentos):
        monkeypatch.setattr("sys.argv", ["main.py", *argumentos])
        runpy.run_path(str(RAIZ / "main.py"), run_name="__main__")
        return llamadas

    lanzar.llamadas = llamadas
    return lanzar


def test_main_sin_argumentos_abre_la_ventana_de_flet(lanzar_main):
    # Sin --edge, igual que antes: ft.run(main) sin opciones extra.
    assert lanzar_main() == [("ft.run", (aplicacion.main,), {})]


def test_main_con_edge_usa_el_modo_edge(lanzar_main):
    assert lanzar_main("--edge") == [("edge", (aplicacion.main,), {})]


@pytest.mark.parametrize("argumentos", [["--Edge"], ["edge"], ["--otra"]])
def test_main_con_otros_argumentos_no_usa_edge(lanzar_main, argumentos):
    # Solo "--edge" exacto elige el modo Edge.
    assert lanzar_main(*argumentos)[0][0] == "ft.run"


def test_main_importado_no_arranca_nada(lanzar_main, monkeypatch):
    # Importar main.py (sin ser el programa principal) no abre nada.
    monkeypatch.setattr("sys.argv", ["pytest", "--edge"])
    runpy.run_path(str(RAIZ / "main.py"), run_name="no_principal")
    assert lanzar_main.llamadas == []


# ---------------------------------------------------------------------------
# Ronda 27: verificación de BUG-24, O49 y O53
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "contenido, se_consulta",
    [
        ("1", True),  # el primer puerto válido
        ("65535", True),  # el último puerto válido
        ("65536", False),  # uno más que el último: fuera de rango
        ("0", False),  # cero no es un puerto donde atienda nadie
        ("-0", False),  # "-0" es 0
        ("+5000", True),  # int() acepta el signo +: es un puerto válido
        ("1_000", True),  # int() acepta guiones bajos: 1000, válido
        (" 65535\n", True),  # con espacios y fin de línea
    ],
)
def test_bug24_bordes_del_rango(tmp_path, monkeypatch, contenido, se_consulta):
    # BUG-24 (bordes): solo se intenta conectar si el número está entre 1 y
    # 65535; fuera de rango devuelve None sin llegar a connect_ex.
    consultados = []

    def esperar(puerto, segundos=30):
        consultados.append((puerto, segundos))
        return False

    monkeypatch.setattr(modo_edge, "esperar_servidor", esperar)
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(contenido, encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None
    if se_consulta:
        assert consultados == [(int(contenido), 1)]
    else:
        assert consultados == []


def test_bug24_puerto_65535_vivo_se_devuelve(tmp_path, monkeypatch):
    # Borde: 65535 es válido; si "responde" se devuelve tal cual.
    monkeypatch.setattr(modo_edge, "esperar_servidor", lambda p, segundos=30: True)
    archivo = tmp_path / "puerto.txt"
    archivo.write_text("65535", encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) == 65535


@pytest.mark.parametrize("contenido", ["65535", "1"])
def test_bug24_bordes_con_socket_real_no_lanzan(tmp_path, contenido):
    # Con sockets reales, los bordes válidos no lanzan error (nadie escucha en
    # el 1 ni, normalmente, en el 65535): None.
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(contenido, encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None


def test_bug24_65536_con_socket_real_no_lanza(tmp_path):
    # El primer número fuera de rango, sin simular nada: None y sin OverflowError.
    archivo = tmp_path / "puerto.txt"
    archivo.write_text("65536", encoding="utf-8")
    assert modo_edge.puerto_en_uso(archivo) is None


def test_o49_settimeout_antes_de_cada_connect(monkeypatch):
    # O49: el límite de 0,3 s se pone ANTES de conectar, en cada socket nuevo
    # (ponerlo después no serviría de nada).
    eventos = []

    class SocketFalso:
        def __init__(self, *args):
            eventos.append("nuevo")

        def __enter__(self):
            return self

        def __exit__(self, *args):
            eventos.append("cerrado")
            return False

        def settimeout(self, segundos):
            eventos.append(("timeout", segundos))

        def connect_ex(self, direccion):
            eventos.append("connect")
            return 0 if eventos.count("connect") >= 2 else 10061

    monkeypatch.setattr(modo_edge.socket, "socket", SocketFalso)
    monkeypatch.setattr(modo_edge.time, "sleep", lambda s: None)
    assert modo_edge.esperar_servidor(5000, segundos=5) is True
    ciclo = ["nuevo", ("timeout", 0.3), "connect", "cerrado"]
    assert eventos == ciclo * 2


def test_o49_puerto_muerto_respeta_el_limite():
    # O49 con sockets reales: con un puerto cerrado y 1 s de límite, termina
    # cerca de 1 s (antes, en Windows, cada intento tardaba ~2 s).
    inicio = time.monotonic()
    assert modo_edge.esperar_servidor(_puerto_muerto(), segundos=1) is False
    assert time.monotonic() - inicio < 1.8


def test_o49_puerto_en_uso_con_puerto_txt_viejo_es_rapido(tmp_path):
    # O49 desde el doble clic: un puerto.txt viejo demora a lo sumo ~1 s.
    archivo = tmp_path / "puerto.txt"
    archivo.write_text(str(_puerto_muerto()), encoding="utf-8")
    inicio = time.monotonic()
    assert modo_edge.puerto_en_uso(archivo) is None
    assert time.monotonic() - inicio < 1.8


def test_o49_limite_cero_no_intenta(monkeypatch):
    # Borde: con 0 segundos no se intenta ninguna conexión: False enseguida.
    def no_crear(*args):
        raise AssertionError("no debería crear sockets")

    monkeypatch.setattr(modo_edge.socket, "socket", no_crear)
    assert modo_edge.esperar_servidor(5000, segundos=0) is False


def test_o53_variables_de_flet_se_quitan_antes_de_arrancar(entorno, monkeypatch):
    # O53: si FLET_SERVER_IP / FLET_SERVER_PORT quedaron definidas (valores
    # inventados), se quitan antes de ft.run para que Flet use 127.0.0.1:puerto.
    monkeypatch.setenv("FLET_SERVER_IP", "0.0.0.0")
    monkeypatch.setenv("FLET_SERVER_PORT", "9999")
    vistas = {}

    def run(main, **kwargs):
        vistas["ip"] = os.environ.get("FLET_SERVER_IP")
        vistas["puerto"] = os.environ.get("FLET_SERVER_PORT")
        vistas["kwargs"] = kwargs

    monkeypatch.setattr(modo_edge.ft, "run", run)
    modo_edge.ejecutar(_principal)
    assert vistas["ip"] is None
    assert vistas["puerto"] is None
    assert vistas["kwargs"]["host"] == "127.0.0.1"
    assert vistas["kwargs"]["port"] == 54321


# ---------------------------------------------------------------------------
# Corrección: Edge colgado con el perfil de la app (lockfile)
# ---------------------------------------------------------------------------


class Corte(Exception):
    """Corta una espera que no termina (prueba de 'no vuelve mientras exista')."""


class RelojFalso:
    """Reemplaza al módulo time dentro de modo_edge: el tiempo avanza solo con
    sleep(), así las esperas de segundos corren al instante."""

    def __init__(self, al_dormir=None):
        self.ahora = 0.0
        self.pausas = []
        self.al_dormir = al_dormir

    def monotonic(self):
        return self.ahora

    def sleep(self, segundos):
        self.pausas.append(segundos)
        self.ahora += segundos
        if self.al_dormir:
            self.al_dormir(self)


class VentanaFalsa:
    """Hace de subprocess.Popen: wait() vuelve enseguida y se anota la llamada."""

    def __init__(self, eventos=None):
        self.llamadas = 0
        self.eventos = eventos if eventos is not None else []

    def wait(self):
        self.llamadas += 1
        self.eventos.append("wait")
        return 0


def _con_reloj(monkeypatch, al_dormir=None):
    reloj = RelojFalso(al_dormir)
    monkeypatch.setattr(modo_edge, "time", reloj)
    return reloj


def test_edge_abierto_con_lockfile(tmp_path):
    # Con el archivo "lockfile" en el perfil, hay un Edge usándolo: True.
    (tmp_path / "lockfile").touch()
    assert modo_edge.edge_abierto(tmp_path) is True


def test_edge_abierto_sin_lockfile(tmp_path):
    # Perfil existente pero sin lockfile: Edge se cerró, False.
    assert modo_edge.edge_abierto(tmp_path) is False


def test_edge_abierto_con_perfil_inexistente(tmp_path):
    # Borde: el perfil todavía no se creó (primera vez): False, sin error.
    assert modo_edge.edge_abierto(tmp_path / "no-existe") is False


def test_edge_abierto_cambia_al_borrar_el_lockfile(tmp_path):
    # Windows borra el lockfile al cerrar Edge: de True pasa a False.
    lock = tmp_path / "lockfile"
    lock.touch()
    assert modo_edge.edge_abierto(tmp_path) is True
    lock.unlink()
    assert modo_edge.edge_abierto(tmp_path) is False


def test_edge_abierto_ignora_otros_archivos(tmp_path):
    # Borde: otros archivos del perfil no cuentan, solo "lockfile" exacto.
    (tmp_path / "lockfile.bak").touch()
    (tmp_path / "Lockfile2").touch()
    assert modo_edge.edge_abierto(tmp_path) is False


def test_esperar_cierre_vuelve_cuando_se_borra_el_lockfile(tmp_path, monkeypatch):
    # El lockfile existe y se borra en la 4.ª pausa (como si el usuario cerrara
    # Edge): la función vuelve justo después, sin esperar el margen de 3 s.
    lock = tmp_path / "lockfile"
    lock.touch()

    def borrar(reloj):
        if len(reloj.pausas) == 4:
            lock.unlink()

    reloj = _con_reloj(monkeypatch, borrar)
    ventana = VentanaFalsa()
    modo_edge.esperar_cierre_edge(tmp_path, ventana)
    assert ventana.llamadas == 1
    assert not lock.exists()
    assert len(reloj.pausas) == 4


def test_esperar_cierre_vuelve_con_hilo_que_borra_el_lockfile(tmp_path):
    # Igual que la anterior pero con tiempo y hilo reales: otro hilo borra el
    # lockfile a los 0,2 s y la función vuelve (la pausa interna es de 1 s).
    lock = tmp_path / "lockfile"
    lock.touch()
    hilo = threading.Timer(0.2, lock.unlink)
    hilo.start()
    inicio = time.monotonic()
    try:
        modo_edge.esperar_cierre_edge(tmp_path, VentanaFalsa())
    finally:
        hilo.join()
    assert not lock.exists()
    assert time.monotonic() - inicio < 5


def test_esperar_cierre_sin_lockfile_vuelve_tras_el_margen(tmp_path, monkeypatch):
    # El lockfile nunca aparece: espera el margen de ~3 s (no menos) y vuelve.
    reloj = _con_reloj(monkeypatch)
    ventana = VentanaFalsa()
    modo_edge.esperar_cierre_edge(tmp_path, ventana)
    assert ventana.llamadas == 1
    assert 3 <= reloj.ahora < 3.5
    assert all(p <= 0.2 for p in reloj.pausas)


def test_esperar_cierre_no_vuelve_mientras_exista_el_lockfile(tmp_path, monkeypatch):
    # Con el lockfile presente (Edge colgado o ventana abierta) no vuelve nunca:
    # tras 1.000 pausas (más de 15 minutos simulados) sigue esperando.
    (tmp_path / "lockfile").touch()

    def cortar(reloj):
        if len(reloj.pausas) >= 1000:
            raise Corte

    reloj = _con_reloj(monkeypatch, cortar)
    with pytest.raises(Corte):
        modo_edge.esperar_cierre_edge(tmp_path, VentanaFalsa())
    assert reloj.ahora > 900


def test_esperar_cierre_no_vuelve_aunque_pase_el_margen(tmp_path, monkeypatch):
    # El proceso lanzado terminó en 0,1 s (Edge le pasó la ventana a otro, el
    # caso del bug): el lockfile existe más de 3 s y la función sigue esperando
    # hasta que se borra, y recién ahí vuelve.
    lock = tmp_path / "lockfile"
    lock.touch()

    def borrar_tarde(reloj):
        if reloj.ahora >= 60:
            lock.unlink()

    reloj = _con_reloj(monkeypatch, borrar_tarde)
    modo_edge.esperar_cierre_edge(tmp_path, VentanaFalsa())
    assert 60 <= reloj.ahora < 62
    assert not lock.exists()


def test_esperar_cierre_lockfile_que_aparece_dentro_del_margen(tmp_path, monkeypatch):
    # Edge tarda 1 s en crear el lockfile (dentro del margen): se detecta y se
    # espera hasta que se borra (a los 10 s).
    lock = tmp_path / "lockfile"

    def ciclo(reloj):
        if 1 <= reloj.ahora < 2 and not lock.exists():
            lock.touch()
        if reloj.ahora >= 10 and lock.exists():
            lock.unlink()

    reloj = _con_reloj(monkeypatch, ciclo)
    modo_edge.esperar_cierre_edge(tmp_path, VentanaFalsa())
    assert not lock.exists()
    assert 10 <= reloj.ahora < 12


def test_esperar_cierre_primero_espera_al_proceso(tmp_path, monkeypatch):
    # Primero ventana.wait() y recién después se mira el lockfile / se duerme.
    eventos = []
    reloj = _con_reloj(monkeypatch)
    reloj.al_dormir = lambda r: eventos.append("sleep")
    modo_edge.esperar_cierre_edge(tmp_path, VentanaFalsa(eventos))
    assert eventos[0] == "wait"
    assert eventos.count("wait") == 1


def test_esperar_cierre_si_wait_falla_propaga_el_error(tmp_path, monkeypatch):
    # Borde: si ventana.wait() lanza un error, no se traga.
    class Rota:
        def wait(self):
            raise OSError("falla inventada")

    _con_reloj(monkeypatch)
    with pytest.raises(OSError):
        modo_edge.esperar_cierre_edge(tmp_path, Rota())


def test_hilo_con_edge_colgado_no_apaga_el_servidor(entorno, monkeypatch):
    # Regresión del bug: el proceso lanzado termina enseguida (wait() vuelve) pero
    # otro Edge con el mismo perfil sigue abierto (lockfile). No se debe llamar a
    # os._exit ni borrar puerto.txt hasta que ese Edge se cierre.
    monkeypatch.setattr(modo_edge, "esperar_servidor", lambda puerto: True)
    modo_edge.ejecutar(_principal)
    r = entorno.registro
    lock = entorno.perfil / "lockfile"
    lock.touch()
    archivo = entorno.perfil.parent / "puerto.txt"
    vistas = []

    def al_dormir(reloj):
        # Durante la espera el servidor sigue vivo: sin salida y con puerto.txt.
        if lock.exists():
            vistas.append((list(r.salidas), archivo.exists()))
        if reloj.ahora >= 30:
            lock.unlink()  # el usuario cierra la última ventana

    _con_reloj(monkeypatch, al_dormir)
    with pytest.raises(Salida):
        r.hilos[0].target()
    assert vistas and all(v == ([], True) for v in vistas)
    assert r.salidas == [0]
    assert not archivo.exists()


def test_ejecutar_usa_esperar_cierre_edge(entorno, monkeypatch):
    # El hilo le pasa a esperar_cierre_edge el perfil y la ventana que abrió.
    monkeypatch.setattr(modo_edge, "esperar_servidor", lambda puerto: True)
    recibidos = []
    monkeypatch.setattr(
        modo_edge, "esperar_cierre_edge", lambda p, v: recibidos.append((p, v))
    )
    modo_edge.ejecutar(_principal)
    with pytest.raises(Salida):
        entorno.registro.hilos[0].target()
    [(perfil, ventana)] = recibidos
    assert perfil == entorno.perfil
    assert hasattr(ventana, "wait")
