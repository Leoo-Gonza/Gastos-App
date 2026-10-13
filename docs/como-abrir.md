# Cómo abrir la app

## Windows: Gastos.exe (doble clic)

`Gastos.exe` está en la carpeta del proyecto (y, si lo pediste, en el
escritorio). Doble clic y se abre la app en su propia ventana.

**Qué hace por dentro:** no trae la app adentro. Busca la carpeta del
proyecto: primero la carpeta donde está el propio `Gastos.exe`, y si ahí no
está la app, la ruta que tenía el proyecto cuando se armó el .exe (hoy
`C:\Proyectos\gastos-app`). Después abre `main.py --edge` con el Python del
proyecto (`.venv`). La ventana la dibuja Microsoft Edge en "modo
aplicación" (sin pestañas ni barra de direcciones), porque el Control
inteligente de aplicaciones de Windows bloquea la ventana propia de Flet.
Todo pasa dentro de la computadora (127.0.0.1): nada sale a internet.

- Al cerrar la ventana se cierra la app.
- Si Edge no estuviera instalado, la app se abre en el navegador
  predeterminado. En ese caso cerrar la pestaña **no** cierra la app: queda
  corriendo escondida hasta reiniciar la computadora (o cerrarla desde el
  Administrador de tareas, proceso `pythonw.exe`).
- Doble clic con la app ya abierta: se abre otra ventana de la misma app.
  Sin Edge, en cambio, cada doble clic arranca otra copia de la app (otro
  `pythonw.exe` escondido) sobre los mismos datos. No se pierde nada, pero
  conviene usar una sola pestaña.
- Los cambios en el código se ven al volver a abrir; no hace falta rearmar
  el .exe.

**Cuándo rearmar el .exe** (si movés la carpeta del proyecto o cambia
`scripts/lanzador.py`):

    .venv\Scripts\python.exe scripts\construir_exe.py
    .venv\Scripts\python.exe scripts\construir_exe.py --escritorio   (también copia al escritorio)

**Si no abre:** el detalle del error queda en `%TEMP%\gastos-app.log`.
El perfil de Edge de la app está en `%LOCALAPPDATA%\gastos-app\edge`.

## macOS

Doble clic en `scripts/abrir_gastos.command`. La primera vez puede hacer falta
darle permiso: `chmod +x scripts/abrir_gastos.command`.

## Desde una terminal

Windows:

    .venv\Scripts\python.exe main.py          (ventana de Flet)
    .venv\Scripts\python.exe main.py --edge   (ventana de Edge, como Gastos.exe)

macOS:

    .venv/bin/python main.py          (ventana de Flet)
    .venv/bin/python main.py --edge   (sin Edge: se abre en el navegador predeterminado)
