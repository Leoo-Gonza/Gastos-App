# Diseño de pantallas – App de gastos personales (v1 y v2)

> Documento de diseño UX/UI. Define **cómo se ve y cómo se usa** la app. No define cómo se
> programa la lógica (eso está en `docs/requisitos.md`).
> Base: `docs/requisitos.md` (aprobado) y la planilla de referencia
> (`docs/referencia/Referencia planilla.png`).
> Las referencias RF-xx, RN-xx y CA-xx.y son las de `requisitos.md`.
> **Gastos en dólares** (funcionalidad aprobada después de la v1 inicial): mientras sus
> requisitos no tengan número en `requisitos.md`, se los cita por su descripción.
> **Importar Excel** (v2) es el Módulo K de `requisitos.md` (RF-49 a RF-58): pantallas
> §3.11 a §3.14, diálogos §4.9 a §4.11 y Paso 8.
> **Cotización automática** (v2) es el Módulo L de `requisitos.md` (RF-59 a RF-62, RN-79 a
> RN-88, ampliación de RF-25): botón en el diálogo de la cotización (§3.6, subsección "Buscar
> la cotización en internet"), pestaña "Cotización" de Ajustes (§3.10) y Paso 9.

---

## 0. Principios de diseño

1. **Una pantalla, una pregunta.** Cada pantalla responde una pregunta del usuario:
   "¿cómo vengo este mes?" (Resumen), "¿qué tengo que pagar?" (Gastos), "¿cuándo termino
   de pagar?" (Cuotas), "¿quién me debe?" (Me deben), "¿cómo voy a estar?" (Previsión).
2. **Los números grandes se leen sin esfuerzo.** Siempre con separador de miles, moneda
   visible (`$` para pesos, `US$` para dólares), alineados a la derecha en las tablas.
3. **Toda edición se hace en un diálogo.** Las pantallas principales solo muestran datos y
   botones; los campos de texto viven en diálogos (`ft.AlertDialog`). Ventajas: es más simple
   de programar (un patrón que se repite), los atajos de teclado no chocan con la escritura y
   el usuario siempre tiene "Cancelar".
4. **El color nunca es la única señal.** "Pagado", "Pendiente", "Déficit" y "Sin capacidad"
   se indican con color **y** con texto o ícono.
5. **Componentes estándar de Flet.** Nada de controles personalizados complejos. Si algo se
   puede hacer con `DataTable`, `Card`, `AlertDialog` y `ProgressBar`, se hace así.
6. **Mostrar el cálculo.** El usuario viene de una planilla donde veía las cuentas. Los
   valores calculados importantes (USD a cambiar, ahorro, capacidad, pesos de un gasto en
   dólares) muestran de dónde salen.

---

## 1. Navegación general

### 1.1 Estructura de la ventana

```
+--------------------------------------------------------------------------------------------+
| BARRA SUPERIOR                                                                             |
| [<] [ Octubre 2026 (mes actual) v ] [>]   [+ Mes nuevo]  [:]     Cotización: $ 1.600 [lápiz]|
+--------+-----------------------------------------------------------------------------------+
|  RAIL  |                                                                                   |
|        |                                                                                   |
| [#]    |                                                                                   |
|Resumen |                         CONTENIDO DE LA PANTALLA                                   |
|        |                         (con scroll vertical propio)                               |
| [=]    |                                                                                   |
|Gastos  |                                                                                   |
|        |                                                                                   |
| [tarj] |                                                                                   |
|Cuotas  |                                                                                   |
|        |                                                                                   |
| [pers] |                                                                                   |
|Me deben|                                                                                   |
|        |                                                                                   |
| [graf] |                                                                                   |
|Previsión                                                                                   |
|        |                                                                                   |
| [barr] |                                                                                   |
|Gráficos|                                                                                   |
|        |                                                                                   |
| ------ |                                                                                   |
| [eng]  |                                                                                   |
|Ajustes |                                                                                   |
+--------+-----------------------------------------------------------------------------------+
```

Componentes de Flet:

| Zona | Componente | Detalle |
|---|---|---|
| Ventana | `page` | Tamaño inicial 1280 × 800; mínimo `page.window.min_width = 1100`, `min_height = 700`. Título: "Gastos – Octubre 2026". |
| Estructura | `ft.Row([rail, ft.VerticalDivider(width=1), ft.Column([barra, contenido], expand=True)], expand=True)` | |
| Navegación | `ft.NavigationRail` | `label_type=ft.NavigationRailLabelType.ALL` (etiquetas siempre visibles, no solo íconos). `min_width=88`. `on_change` cambia el contenido. |
| Barra superior | `ft.Container` con un `ft.Row` | Altura 64, color de superficie, borde inferior. |
| Contenido | `ft.Container(expand=True, padding=24)` con un `ft.Column(scroll=ft.ScrollMode.AUTO)` | Se reemplaza el control al cambiar de pantalla. |
| Mensajes breves | `ft.SnackBar` | 4 segundos. Con acción "Deshacer" cuando aplica. |

Destinos del `NavigationRail` (el número es también el atajo `Ctrl/Cmd + número`):

| # | Etiqueta | Ícono (`ft.Icons.…`) | Pantalla | Depende del mes seleccionado |
|---|---|---|---|---|
| 1 | Resumen | `SPACE_DASHBOARD_OUTLINED` | Resumen del mes | Sí |
| 2 | Gastos | `RECEIPT_LONG_OUTLINED` | Gastos del mes | Sí |
| 3 | Cuotas | `CREDIT_CARD_OUTLINED` | Planes de cuotas | Sí (cuota n/N y restante) |
| 4 | Me deben | `PEOPLE_OUTLINE` | Me deben | No (acumulado) |
| 5 | Previsión | `TRENDING_UP` | Previsión 12 meses | No (usa el mes actual) |
| 6 | Gráficos | `BAR_CHART` | Gráficos | En parte |
| 7 | Ajustes | `SETTINGS_OUTLINED` | Categorías, medios, personas, meta, cotización, apariencia | No |

La pantalla de inicio al abrir la app es **Resumen** (desde el paso 3; antes, Gastos).

### 1.2 Barra superior y selector de mes

```
+--------------------------------------------------------------------------------------------+
| [<]  [ Octubre 2026 · mes actual  v ]  [>]    [+ Mes nuevo]  [:]                           |
|                                                       Cotización  $ 1.600 por US$  [lápiz] |
+--------------------------------------------------------------------------------------------+
```

| Elemento | Componente | Comportamiento |
|---|---|---|
| Mes anterior / siguiente | `ft.IconButton(ft.Icons.CHEVRON_LEFT / CHEVRON_RIGHT)` | Tooltip "Mes anterior (Alt+←)" / "Mes siguiente (Alt+→)". Deshabilitado en el primer / último mes. |
| Selector de mes | `ft.Dropdown` (ancho 260) | Lista **todos los meses existentes**, del más nuevo al más viejo: "Noviembre 2026", "Octubre 2026 · mes actual", "Septiembre 2026"… Los nombres de mes salen de una lista fija en español (no depender del idioma del sistema operativo). |
| Mes nuevo | `ft.OutlinedButton("Mes nuevo", icon=ft.Icons.ADD)` | Tooltip "Crear Noviembre 2026 (Ctrl+Shift+N)". Abre el diálogo de mes nuevo (§3.9). |
| Más opciones | `ft.PopupMenuButton` (ícono `MORE_VERT`) | Una opción: "Borrar este mes". Habilitada solo si el mes seleccionado es el último; si no, deshabilitada con el texto "Solo se puede borrar el último mes (Noviembre 2026)". |
| Cotización | `ft.Container` clickeable con texto + `ft.IconButton(EDIT)` | Muestra "Cotización $ 1.600 por US$". Clic o `Ctrl/Cmd+K` abre el diálogo de cotización (§3.6). |

**Estados de la cotización en la barra**

| Estado | Se ve |
|---|---|
| Cargada | "Cotización $ 1.600 por US$" en color de texto normal. |
| Sin cargar (RN-18) | Fondo color *pendiente*, ícono `WARNING_AMBER`, texto "Cotización sin cargar – Cargar". |

**Aviso de mes pasado o futuro.** Si el mes seleccionado no es el mes actual, debajo de la
barra aparece una franja informativa (`ft.Container` color *info* suave, una línea):

> "Estás viendo Septiembre 2026. Los cambios que hagas se guardan en ese mes."

Motivo: los meses pasados son editables (RN-11) y es fácil olvidarse de qué mes está
seleccionado.

**Cambio de mes.** Al cambiar el mes seleccionado se refresca la pantalla visible y el título
de la ventana. El mes seleccionado se guarda en memoria (no hace falta guardarlo en la base).
Al abrir la app se selecciona el **mes actual** si existe; si no, el **último mes**.

### 1.3 Atajos de teclado

En macOS se usa `Cmd` en lugar de `Ctrl` y `Option` en lugar de `Alt`. Se programan con
`page.on_keyboard_event` (campos `e.key`, `e.ctrl`, `e.meta`, `e.alt`, `e.shift`) y se usa
`e.meta` si `page.platform` es macOS. **Mientras hay un diálogo abierto, los atajos globales
se ignoran** (solo valen Enter y Esc).

| Atajo | Acción |
|---|---|
| `Ctrl/Cmd + 1` … `7` | Ir a la pantalla 1 a 7 del rail |
| `Ctrl/Cmd + N` | "Nuevo" de la pantalla visible: Gastos → nuevo gasto; Cuotas → nuevo plan; Me deben → nuevo ítem; Resumen → registrar cambio de USD; Ajustes → nuevo elemento de la pestaña |
| `Ctrl/Cmd + Shift + N` | Mes nuevo |
| `Ctrl/Cmd + K` | Editar la cotización del mes |
| `Alt + ←` / `Alt + →` | Mes anterior / siguiente |
| `Ctrl/Cmd + ,` | Ajustes (convención de macOS) |
| `Ctrl/Cmd + /` | Diálogo con la lista de atajos |
| `Enter` (en un diálogo) | Guardar (con `on_submit` de los `TextField`) |
| `Esc` (en un diálogo) | Cancelar y cerrar |

Se evitan a propósito `Cmd+Q`, `Cmd+W`, `Cmd+H` y `Cmd+M`, que en macOS cierran, ocultan o
minimizan la app. Los tooltips de los botones muestran el atajo correcto según el sistema
("Ctrl+N" en Windows, "⌘N" en macOS).

#### Atajos durante la importación (v2)

Mientras la importación está abierta (pasos de §3.11 a §3.13) **se desactivan los atajos
globales** (`Ctrl/Cmd+1..7`, `N`, `K`, `Alt+←/→`, `Ctrl/Cmd+,`): no hay rail ni barra
superior y el mes seleccionado de la app no debe cambiar a mitad de la revisión. Valen estos:

| Atajo | Acción (solo en la importación) |
|---|---|
| `Esc` | Igual que "Cancelar" (si hubo cambios, pregunta antes: §3.14). Dentro de un diálogo, cierra el diálogo. |
| `Ctrl/Cmd + Enter` | "Confirmar importación" (abre el resumen), si no hay errores. |
| `Enter` / `Esc` en diálogos | Aceptar / cancelar, como en toda la app. |

---

## 2. Sistema visual

### 2.1 Paleta

El color principal es el azul petróleo de los encabezados de la planilla, para que el usuario
reconozca su herramienta. Se configura con `page.theme = ft.Theme(color_scheme_seed=PRIMARIO)`
y `page.dark_theme = ft.Theme(color_scheme_seed=PRIMARIO)`; Flet deriva el resto de los
colores de Material 3. Los **colores semánticos** se definen a mano (un diccionario por tema
en `app/interfaz/estilos.py`) porque deben ser exactos.

**Tema claro**

| Rol | Color | Uso | Contraste sobre fondo |
|---|---|---|---|
| Primario | `#1F5F7A` | Rail seleccionado, botones principales, barras de gráficos | ≈ 7:1 sobre blanco |
| Fondo | `#F6F8F9` | Fondo de la ventana | – |
| Superficie | `#FFFFFF` | Tarjetas, tablas, diálogos | – |
| Superficie variante | `#E9EEF1` | Encabezado de tablas, fila de totales | – |
| Texto | `#1A1C1E` | Texto principal | ≈ 16:1 |
| Texto secundario | `#4A5056` | Etiquetas, ayudas, detalle "US$ 20,00 × $ 1.600" | ≈ 8:1 |
| Borde | `#C3C9CE` | Bordes de tarjetas y separadores | – |
| **Pagado / positivo** | `#1E7B34` (fondo suave `#E3F2E6`) | Gasto pagado, cobrado, ahorro, meta alcanzada | ≈ 5,4:1 |
| **Pendiente / aviso** | `#9A5800` (fondo suave `#FFF1DC`) | Pendiente de pago, falta cotización, sueldo 0, parte con diferencia | ≈ 5,3:1 |
| **Negativo / error** | `#B3261E` (fondo suave `#FCE8E6`) | Déficit, capacidad negativa, errores de validación, botón borrar, "a devolver" | ≈ 6,5:1 |
| Info | `#1F5F7A` (fondo suave `#E3EFF4`) | Avisos informativos (mes pasado, alcance de cuotas, resultado en pesos de un gasto en dólares) | ≈ 7:1 |

**Tema oscuro**

| Rol | Color | Contraste sobre superficie |
|---|---|---|
| Primario | `#8CCDF0` | ≈ 9:1 |
| Fondo | `#111416` | – |
| Superficie | `#1B2024` | – |
| Superficie variante | `#262C31` | – |
| Texto | `#E3E6E8` | ≈ 13:1 |
| Texto secundario | `#B7BEC4` | ≈ 8:1 |
| Borde | `#3D454C` | – |
| Pagado / positivo | `#74D38F` (fondo `#1D3324`) | ≈ 8:1 |
| Pendiente / aviso | `#FFB95C` (fondo `#3A2C14`) | ≈ 9:1 |
| Negativo / error | `#FF8A80` (fondo `#3D1F1D`) | ≈ 6,5:1 |
| Info | `#8CCDF0` (fondo `#1A3340`) | ≈ 9:1 |

Todos los pares texto/fondo cumplen al menos **4,5:1** (WCAG AA). El tema se elige en
Ajustes → Apariencia: "Claro", "Oscuro" o "Como el sistema" (`page.theme_mode`).

### 2.2 Tipografía

Se usa la **fuente del sistema** (la que Flet usa por defecto en cada plataforma). No se
agregan fuentes, para simplificar.

| Estilo | Tamaño | Peso | Uso |
|---|---|---|---|
| Título de pantalla | 24 | `W_600` | "Gastos de Octubre 2026" |
| Título de sección / tarjeta | 16 | `W_600` | "Ingresos extra", "Por medio de pago" |
| Monto destacado (KPI) | 30 | `W_700` | Montos de las tarjetas del Resumen |
| Resultado de conversión (diálogo de gasto en USD) | 18 | `W_600` | "= $ 32.000 a pagar" |
| Texto y celdas de tabla | 15 | normal | Por defecto en toda la app |
| Totales de tabla | 15 | `W_700` | Fila de totales |
| Etiqueta / ayuda | 13 | normal | Subtítulos, textos de ayuda, ejes de gráficos, detalle en USD bajo un monto |

Nada se muestra por debajo de **13 px**. Los tamaños se definen como constantes en
`estilos.py` para poder agrandarlos todos de una vez si hiciera falta.

### 2.3 Formato de montos y fechas

El formateo es una función pura que conviene poner en `app/logica/formato.py` (sin importar
Flet), así Lucía puede probarla (CA-06.4, CA-09.2). La interfaz solo la llama.

| Dato | Formato | Ejemplos |
|---|---|---|
| ARS | `$` + espacio + entero redondeado (mitad hacia arriba) + punto de miles. **Sin decimales** (RN-04) | `$ 1.434.617` · `$ 66.020` · `$ 22.094` · `$ 0` |
| USD | `US$` + espacio + 2 decimales con coma + punto de miles | `US$ 896,64` · `US$ 1.200,00` · `US$ 0,00` |
| Negativos | Signo menos antes de la moneda + palabra que lo explica | `-US$ 96,64` (Déficit) · `-$ 506.417` (Sin capacidad) · `-$ 2.900` (a devolver) |
| Cotización | `$ 1.600 por US$`; si tiene centavos, con 2 decimales: `$ 1.432,50 por US$` | |
| Gasto en dólares (detalle) | `US$` monto + ` × ` + `$` cotización (misma regla de decimales que la cotización) | `US$ 20,00 × $ 1.600` · `US$ 12,99 × $ 1.432,50` |
| Porcentaje | Entero en la barra, 2 decimales en el tooltip | `101 %` (tooltip "101,12 %") |
| Mes largo | Nombre en español + año | `Octubre 2026` |
| Mes corto (tablas) | 3 letras + año | `oct 2026` |
| Fecha | `DD/MM/AAAA` (se guarda en ISO, RN del modelo) | `04/10/2026` |
| Cuota | `n/N` | `3/3`, `8/12` |
| Abreviado (solo ejes de gráficos) | mil / M | `$ 800 mil`, `$ 1,2 M` |

**Por qué `$` y `US$`:** en Argentina "$" se lee como pesos; "US$" deja claro que son dólares
sin tener que leer una columna aparte. Así la moneda está visible en cada número.

**En las tablas** los montos van en columnas `ft.DataColumn(numeric=True)`, que los alinea a la
derecha: las unidades, miles y millones quedan una debajo de la otra.

### 2.4 Campos de monto (entrada)

Todos los montos se ingresan con el mismo control, para que se comporte igual en toda la app:

```python
ft.TextField(
    label="Monto",
    prefix_text="$ ",  # o "US$ "
    suffix_text="ARS",  # o "USD"
    text_align=ft.TextAlign.RIGHT,
    keyboard_type=ft.KeyboardType.NUMBER,
    input_filter=ft.InputFilter(regex_string=r"[0-9.,]", allow=True),
    hint_text="Ej.: 66.020,12",
)
```

- Acepta "66020", "66.020", "66020,12" y "66.020,12" (RN-04: coma decimal, hasta 2 decimales).
- El `input_filter` impide escribir letras y el signo menos; igual la lógica valida (RN-05).
- Al salir del campo (`on_blur`), si el valor es válido se reescribe formateado: "66020,5" →
  "66.020,50".
- **Regla del punto:** el punto solo se acepta como separador de miles (grupos de 3 dígitos).
  "66020.12" se rechaza con "Usá coma para los decimales. Ej.: 66.020,12". Así no se
  interpreta mal lo que escribe el teclado numérico, que en muchos teclados pone punto.
- Conviene que sea una función `campo_monto(moneda, label, ...)` en `componentes.py`, que
  reciba "ARS" o "USD" y ponga prefijo, sufijo y ejemplo. Se usa en los diálogos de gasto,
  pago, sueldo, cotización, ingreso extra, cambio, partes y "me deben".

### 2.5 Patrones comunes

| Patrón | Componentes | Reglas |
|---|---|---|
| Formulario | `ft.AlertDialog(modal=True)` con `content=ft.Column(tight=True, width=480)` y acciones `[ft.TextButton("Cancelar"), ft.FilledButton("Guardar")]` | El primer campo tiene `autofocus=True`. Enter guarda; Esc cancela. Los errores se muestran en `error_text` del campo, debajo, en rojo; el diálogo no se cierra. Al guardar, se pone el foco en el primer campo con error. |
| Confirmación destructiva | `ft.AlertDialog(modal=True)` | Título en forma de pregunta ("¿Borrar el gasto Nafta?"), texto que dice **qué se va a perder**, botones "Cancelar" (foco por defecto) y "Borrar" (`ft.FilledButton` con fondo *negativo*). |
| Mensaje de éxito | `ft.SnackBar` | "Gasto agregado", "Pago registrado". Con "Deshacer" en marcar pagado/cobrado. |
| Error inesperado | `ft.AlertDialog` | "No se pudo guardar. Los datos no se modificaron." + detalle técnico en texto chico (para copiarlo y mostrárselo al agente). |
| Estado vacío | `ft.Column` centrada: ícono 48 px, texto 15, botón de acción | Siempre con un botón que resuelve el vacío ("Agregar gasto"). |
| Aviso en pantalla | `ft.Container` con fondo suave del color semántico, `border_radius=8`, ícono + texto | No usar `ft.Banner` (ocupa la parte superior y es más difícil de manejar). |
| Acciones por fila | `ft.PopupMenuButton` (ícono `MORE_VERT`) en la última columna | Tooltip "Acciones". Además, clic en el nombre (`DataCell(on_tap=…)`) abre "Editar". |
| Botones de ícono | `ft.IconButton(..., tooltip=…)` | **Siempre** con tooltip (lo leen los lectores de pantalla). |
| Mostrar u ocultar partes de un formulario | Agrupar los campos en un `ft.Column` o `ft.Container` y cambiar su `visible` | Se usa para "Compartido" y para los campos de pesos / dólares del diálogo de gasto. Más simple que reconstruir el diálogo. |

---

## 3. Pantallas

### 3.1 Primer uso (RF-04)

**Objetivo del usuario:** empezar a usar la app creando el primer mes.

**Cuándo aparece:** cuando la base no tiene ningún mes (y también después de borrar el único
mes). Es una pantalla completa, **sin rail ni barra superior**.

```
+--------------------------------------------------------------------------------------------+
|                                                                                            |
|                         Bienvenido a tu app de gastos                                      |
|              Para empezar, creá el primer mes que querés registrar.                        |
|                                                                                            |
|                 +---------------------------------------------------+                      |
|                 |  Mes            [ Octubre       v ]                |                      |
|                 |  Año            [ 2026           ]                |                      |
|                 |  Sueldo         [ US$      1.200,00  USD ]        |                      |
|                 |  Cotización     [ $        1.600     ARS ]        |                      |
|                 |                 Podés dejarla vacía y cargarla    |                      |
|                 |                 después.                          |                      |
|                 |                                                   |                      |
|                 |                          [ Crear mes ]            |                      |
|                 +---------------------------------------------------+                      |
+--------------------------------------------------------------------------------------------+
```

**Componentes:** `ft.Card` centrada (ancho 480); `ft.Dropdown` con los 12 meses en español
(valor inicial: mes del calendario); `ft.TextField` año (valor inicial: año del calendario,
`max_length=4`); campos de monto (§2.4); `ft.FilledButton("Crear mes")`.

**Validaciones (RN-05, RN-06, RN-07):**

| Campo | Regla | Mensaje |
|---|---|---|
| Año | 4 dígitos | "El año tiene que tener 4 dígitos. Ej.: 2026" |
| Mes | 1 a 12 (lo garantiza el `Dropdown`) | "Elegí un mes." |
| Sueldo | vacío | "Ingresá el sueldo. Si este mes no cobrás, poné 0." |
| Sueldo | < 0 / no numérico | "El sueldo no puede ser negativo." / "El sueldo tiene que ser un número. Ej.: 1.200,00" |
| Sueldo | = 0 | Se acepta. Debajo del campo, en color *pendiente*: "El sueldo de este mes es 0" |
| Cotización | vacía | Se acepta (RN-06). |
| Cotización | ≤ 0 / no numérica | "La cotización tiene que ser mayor a 0." |

**Flujo:** completar → "Crear mes" → la app muestra la estructura completa con ese mes
seleccionado y la pantalla Gastos (paso 1) o Resumen (paso 3 en adelante).

#### Importar Excel desde el primer uso (v2: RF-49, CA-49.1)

El formulario de "Crear mes" queda **igual** (es "empezar de cero": no agrega ningún clic a
quien no tiene planilla). Debajo de la tarjeta del formulario se agrega una línea:

```
|                 [ ...formulario de primer mes de §3.1, sin cambios... ]                    |
|                                                                                            |
|                ¿Tenés una planilla?  [icono planilla] Importar Excel                       |
```

- `ft.Row` centrada con `ft.Text("¿Tenés una planilla?")` (texto secundario, 14) y
  `ft.TextButton("Importar Excel", icon=ft.Icons.UPLOAD_FILE)`. Es un botón de texto para que
  "Crear mes" siga siendo la acción principal de la pantalla.
- Orden de Tab: los campos del formulario, "Crear mes" y después "Importar Excel".
- Al **cancelar** una importación iniciada desde acá se vuelve a esta pantalla.

Decidido por el usuario el 2026-10-13 (observación 21).

---

### 3.2 Resumen (RF-23, RF-25, RF-27, RF-35, RF-36, RF-37, RF-24, RF-26, RN-40 total "me deben")

**Objetivo del usuario:** saber de un vistazo cómo viene el mes: cuánto gasta, cuántos dólares
tiene que cambiar, cuánto ahorra y si puede tomar más deudas. Cargar sueldo, cotización,
ingresos extra y cambios de USD.

**Distribución**

```
+--------------------------------------------------------------------------------------------+
| Resumen de Octubre 2026                                                                    |
|                                                                                            |
| [!] El sueldo de este mes es 0.                                       (solo si sueldo = 0) |
|                                                                                            |
| EN PESOS                                                                                   |
| +----------------------+ +----------------------+ +--------------------------------------+ |
| | Total gastos         | | Falta pagar          | | Pesos a cubrir                       | |
| | $ 1.434.617          | | $ 1.034.617          | | $ 1.434.617                          | |
| | 23 gastos            | | Pagado $ 400.000     | | Gastos - extras ARS - cambios ARS    | |
| +----------------------+ +----------------------+ +--------------------------------------+ |
|                                                                                            |
| EN DÓLARES                                                                                 |
| +----------------------+ +----------------------+ +--------------------------------------+ |
| | Sueldo        [lápiz]| | USD a cambiar        | | Ahorro del mes                       | |
| | US$ 1.200,00         | | US$ 896,64           | | US$ 303,36                           | |
| |                      | | $ 1.434.617 ÷ 1.600  | | Meta US$ 300,00  [#########] 101 %   | |
| +----------------------+ +----------------------+ +--------------------------------------+ |
|                                                                                            |
| +-------------------------------------------+ +------------------------------------------+ |
| | Capacidad de endeudamiento                | | Te deben (todas las personas)            | |
| | $ 613.583 por mes                         | | $ 461.913                                | |
| | > Ver cálculo                             | | Acumulado de todos los meses  [Ver >]    | |
| +-------------------------------------------+ +------------------------------------------+ |
|                                                                                            |
| > Cómo se calcula el ahorro                                         (ExpansionTile)       |
|                                                                                            |
| INGRESOS EXTRA                                                     [+ Agregar ingreso]    |
| +----------------------------------------------------------------------------------------+ |
| | Descripción             | Moneda |              Monto |                            [:] | |
| | Venta bici              | ARS    |          $ 100.000 |                            [:] | |
| | Freelance               | USD    |          US$ 50,00 |                            [:] | |
| +----------------------------------------------------------------------------------------+ |
|                                                                                            |
| CAMBIOS DE USD REALIZADOS                                     [+ Registrar cambio]        |
| +----------------------------------------------------------------------------------------+ |
| | Fecha       |    USD cambiados |  Cotización |     ARS recibidos |                  [:] | |
| | 05/10/2026  |       US$ 500,00 |     $ 1.500 |         $ 745.000 | corregido a mano [:] | |
| | Total       |       US$ 500,00 |             |         $ 745.000 |                      | |
| +----------------------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------------------+
```

**Componentes**

| Parte | Componente |
|---|---|
| Tarjetas | `ft.ResponsiveRow` con `ft.Card` (`col={"sm": 12, "md": 4}`); dentro, `ft.Column` con etiqueta (13), monto (30 bold) y subtítulo (13). Se acomodan solas si la ventana es angosta. |
| Sueldo | Tarjeta con `ft.IconButton(EDIT, tooltip="Editar sueldo")` que abre §3.6. |
| Meta | `ft.ProgressBar(value=avance_limitado, height=10, border_radius=5)` + `ft.Text("101 %", tooltip="101,12 %")`. Sin meta: en su lugar un `ft.TextButton("Definir meta de ahorro")`. |
| Capacidad | `ft.Card` + `ft.ExpansionTile("Ver cálculo")` con el desglose (RN-38). |
| Te deben | `ft.Card` clickeable (`on_click` → pantalla Me deben). |
| Cómo se calcula | `ft.ExpansionTile` cerrado por defecto con el desglose de RN-14 a RN-17. |
| Ingresos extra y cambios | `ft.DataTable` + botón `ft.OutlinedButton` con ícono `ADD`. |

Los gastos en dólares entran en "Total gastos" por su monto en pesos (el que quedó fijo al
cargarlos), igual que cualquier otro gasto. El Resumen no los muestra aparte.

**Desglose "Cómo se calcula el ahorro"** (texto alineado, con los números del mes):

```
Total gastos                       $ 1.434.617
- Ingresos extra en pesos          $   100.000
- Pesos de cambios realizados      $   745.000
= Pesos a cubrir                   $   589.617
÷ Cotización                       $ 1.600 por US$
= USD a cambiar                    US$ 368,51

Sueldo                             US$ 1.200,00
+ Ingresos extra en dólares        US$    50,00
- USD ya cambiados                 US$   500,00
- USD a cambiar                    US$   368,51
+ Pesos sobrantes en dólares       US$     0,00
= Ahorro del mes                   US$   381,49
```

**Desglose de capacidad (RN-38):**

```
Sueldo en pesos (US$ 1.200,00 × 1.600)     $ 1.920.000
- Gastos fijos mensuales                   $   785.300
- Cuotas del mes                           $    41.117
- Meta de ahorro (US$ 300,00 × 1.600)      $   480.000
= Capacidad de endeudamiento               $   613.583
Los pagos únicos y los ingresos extra no se cuentan.
```

**Estados**

| Situación | Cómo se ve |
|---|---|
| Normal | Como el boceto. Ahorro positivo en color *positivo*. |
| Pesos sobrantes (F < 0, RN-16) | "Pesos a cubrir" muestra `$ 0` y abajo, en *positivo*: "Pesos sobrantes $ 60.000 = US$ 37,50 (se suman al ahorro)". USD a cambiar `US$ 0,00`. |
| Ahorro negativo (RN-17) | La tarjeta cambia la etiqueta a **"Déficit"**, monto `-US$ 96,64` en *negativo*, ícono `TRENDING_DOWN`. Barra de meta en 0 %. |
| Sin cotización y F ≠ 0 (RN-18) | USD a cambiar, Ahorro y Capacidad muestran, en lugar del monto, el texto "Cargá la cotización" (color *pendiente*, tamaño 16) y un `ft.TextButton("Cargar cotización")`. Total gastos, Falta pagar y Pesos a cubrir se ven normales. |
| Sin cotización y F = 0 | Ahorro se calcula y se muestra normal; Capacidad muestra "Cargá la cotización". |
| Sueldo 0 (RN-05) | Aviso arriba en color *pendiente*: "El sueldo de este mes es 0." La tarjeta Sueldo muestra `US$ 0,00` con ícono `WARNING_AMBER`. |
| Capacidad negativa (RN-38) | Monto `-$ 506.417` en *negativo*, borde de la tarjeta en *negativo* (2 px), ícono `ERROR_OUTLINE` y el texto "Sin capacidad de endeudamiento". |
| Sin meta | No hay barra; botón "Definir meta de ahorro". |
| Meta superada | Barra llena en *positivo*, texto "101 %". |
| Sin ingresos extra / sin cambios | Dentro de la tabla, una fila de texto secundario: "Sin ingresos extra este mes." / "Todavía no registraste cambios este mes." |
| Te deben = 0 | "$ 0 – Nadie te debe nada". |

**Flujo: registrar un cambio de USD (RF-26, RN-13)**

1. En Resumen, clic en "Registrar cambio" (o `Ctrl/Cmd+N`).
2. Se abre el diálogo §4.6 con la fecha de hoy y la **cotización del cambio precargada con la
   cotización del mes** (si existe), porque suele ser parecida.
3. El usuario escribe los USD (ej. 500). Mientras escribe, "ARS recibidos" se completa solo:
   `$ 750.000` y abajo la ayuda "Calculado: US$ 500,00 × 1.500".
4. Si hubo comisión, corrige ARS a 745.000. Aparece la marca "Corregido a mano" y un
   `ft.TextButton("Volver a calcular")`.
5. Si después cambia USD o la cotización del cambio, ARS se vuelve a calcular (RN-13) y se
   muestra el aviso "Se recalculó con los valores nuevos. Si hubo comisión, corregilo."
6. "Guardar" → se cierra el diálogo, SnackBar "Cambio registrado", y las tarjetas Pesos a
   cubrir, USD a cambiar y Ahorro se actualizan en el momento (RN-19).


**Textos en pantalla (decisión del usuario, paso 3).** En la app se usan "dólares" y "pesos"
en lugar de las siglas, porque se leen más natural: "Dólares a cambiar" (en vez de "USD a
cambiar"), "CAMBIOS DE DÓLARES REALIZADOS", columnas "Dólares cambiados" y "Pesos
recibidos", y la ayuda "Calculado: US$ 500,00 × $ 1.500". Los montos siguen llevando `$` y
`US$`. El desglose de capacidad junta "Gastos fijos y cuotas del mes" en una sola línea.
Los porcentajes de la meta se redondean "mitad hacia arriba" (12,5 % → "13 %") y el número
muestra el valor real aunque sea negativo ("-32 %"); solo la barra se limita entre 0 y 100 %.

---

### 3.3 Gastos (RF-06 a RF-15, RF-22, RF-29 marca, gastos en dólares)

**Objetivo del usuario:** cargar los gastos del mes (en pesos o en dólares), marcar lo que
pagó y ver cuánto le falta pagar. Equivale a "Gasto del Mes" y "Deudas" de la planilla.

**Distribución**

```
+--------------------------------------------------------------------------------------------+
| Gastos de Octubre 2026                                    [+ Agregar gasto] [+ Plan cuotas]|
|                                                                                            |
| +----------------------------------------------------------------------------------------+ |
| |Pag.| Nombre             | Categoría  | Tipo      | Medio de pago   |    Monto |  Pagado |  Pendiente |   |
| |----+--------------------+------------+-----------+-----------------+----------+---------+------------+---|
| |[x] | Alquiler           | Vivienda   | Fijo      | Transferencia   | $260.000 |$260.000 | Pagado     |[:]|
| |[ ] | Internet  [pers]   | Servicios  | Fijo      | Visa Santander  |  $38.700 |      $0 |   $38.700  |[:]|
| |[ ] | Claude             | Trabajo    | Fijo      | Visa Santander  |  $32.000 |      $0 |   $32.000  |[:]|
| |    |                    |            |           |                 | US$ 20,00 × $ 1.600 |  |         |   |
| |[ ] | Seguro de moto     | Seguros    | Fijo      | Mastercard Nac. | $180.000 | $60.000 |  $120.000  |[:]|
| |    |                    |            |           |                 |          | Parcial |            |   |
| |[ ] | Avant Service      | Deudas     | Cuota 3/3 | Visa Santander  |  $41.117 |      $0 |   $41.117  |[:]|
| |[ ] | Nafta              | Transporte | Único     | —               |  $30.000 |      $0 |   $30.000  |[:]|
| |----+--------------------+------------+-----------+-----------------+----------+---------+------------+---|
| |    | TOTAL (23 gastos)  |            |           |                 |$1.434.617|$400.000 | $1.034.617 |   |
| +----------------------------------------------------------------------------------------+ |
|                                                                                            |
| POR MEDIO DE PAGO                                                                          |
| +-----------------------------------------+                                                |
| | Medio de pago             |       Total |                                                |
| | Visa Santander            |   $ 123.117 |                                                |
| | Mastercard Nación         |   $ 131.000 |                                                |
| | Transferencia             |   $ 260.000 |                                                |
| | Sin medio de pago         |    $ 30.000 |                                                |
| +-----------------------------------------+                                                |
+--------------------------------------------------------------------------------------------+
```

(En el boceto los montos van pegados al `$` por espacio; en la app llevan el formato de §2.3:
`$ 260.000`. La línea "US$ 20,00 × $ 1.600" va **dentro de la celda Monto**, debajo del monto
en pesos y alineada a la derecha; en el boceto se desborda solo por falta de espacio.)

**Columnas de la tabla** (`ft.DataTable`, `heading_row_color` = superficie variante,
`data_row_min_height=48`, `data_row_max_height=64` para que entren las celdas de dos líneas):

| Columna | Contenido | Componente |
|---|---|---|
| Pag. | Tilde "pagado" (RF-13). Marcado si pendiente = 0 (RN-22). | `ft.Checkbox` con `tooltip="Marcar como pagado"` |
| Nombre | Nombre + ícono `PEOPLE` (16 px, tooltip "Compartido con Sofía y Marsu") si es compartido. Clic → editar. | `ft.DataCell(ft.Row([...]), on_tap=…)` |
| Categoría | Nombre; si está archivada, en texto secundario con tooltip "Categoría archivada". | `ft.Text` |
| Tipo | "Fijo", "Único" o "Cuota n/N" (une tipo y cuota actual de RF-09 en una sola columna). | `ft.Text` |
| Medio de pago | Nombre o "—". | `ft.Text` |
| Monto | **Siempre en ARS** (texto 15, es lo que se paga). Si el gasto es en dólares, debajo una segunda línea en texto secundario 13: "US$ 20,00 × $ 1.600". | `numeric=True`; la celda es un `ft.Column([monto, detalle], horizontal_alignment=END, spacing=0)` con `tooltip` en el contenedor. |
| Pagado | ARS; si es parcial, debajo una etiqueta chica "Parcial" en *pendiente*. | `numeric=True` |
| Pendiente | ARS en *pendiente*; si es 0, el texto "Pagado" en *positivo* con ícono `CHECK`. | `numeric=True` |
| (acciones) | Menú: Editar · Registrar pago · Ver pagos · Borrar. Para cuotas, además "Ver plan" (va a Cuotas). | `ft.PopupMenuButton` |

**Gastos en dólares en la tabla**

- El **monto principal es en pesos**, porque se pagan en pesos (decisión aprobada). La línea
  secundaria "US$ 20,00 × $ 1.600" explica de dónde sale, sin ocupar una columna aparte.
- Tooltip de la celda: "Gasto en dólares: US$ 20,00 a $ 1.600 por US$ = $ 32.000. Los pesos
  quedan fijos con esa cotización."
- No se agrega color ni ícono especial: el texto `US$` ya lo identifica, y así el color queda
  reservado para estados (pagado, pendiente, negativo).
- Pagado y Pendiente se ven en pesos, como en cualquier gasto.
- **La fila de totales sigue siendo solo en ARS** y suma el monto en pesos de cada gasto. No
  se muestra un total en dólares (mezclaría cotizaciones distintas y no se usa para pagar).
- "Por medio de pago" también suma los pesos.

**Orden de las filas:** primero fijos, luego cuotas, luego pagos únicos; dentro de cada grupo,
por nombre. La moneda no cambia el orden. (Opcional más adelante: ordenar por columna con
`DataColumn(on_sort=…)`.)

**Fila de totales (RF-09):** una última `ft.DataRow` con fondo de superficie variante y texto
en negrita: "TOTAL (23 gastos)", total gastos, total pagado y total pendiente ("Gastos",
"Pagado" y "Falta por pagar" de la planilla), todos en ARS. Los totales se redondean desde el
valor exacto (RN-04).

**Por medio de pago (RF-22):** `ft.Card` con una `ft.DataTable` de dos columnas, debajo de la
tabla principal. "Sin medio de pago" siempre al final. Este bloque reemplaza la línea "Tarjetas
de Crédito" de la planilla, así que lleva el texto de ayuda: "Incluye todos los gastos del mes
(fijos, cuotas y únicos, en pesos y en dólares) agrupados por cómo se pagan. Los gastos en
dólares se suman por sus pesos."

**Estados**

| Situación | Cómo se ve |
|---|---|
| Sin gastos | Estado vacío: ícono `RECEIPT_LONG`, "Todavía no cargaste gastos en Octubre 2026.", botón "Agregar gasto (Ctrl+N)". No se muestran la fila de totales ni "Por medio de pago". |
| Con datos | Como el boceto. |
| Todo pagado | La fila de totales muestra "Falta por pagar $ 0" con ícono `CHECK_CIRCLE` en *positivo*. |
| Mes no actual | Franja informativa de §1.2. |

**Flujo: cargar un gasto en pesos (RF-06)**

1. Clic en "Agregar gasto" (o `Ctrl/Cmd+N`).
2. Diálogo §4.1 con foco en "Nombre". Moneda por defecto: "Pesos". Tipo por defecto:
   "Fijo mensual".
3. Escribe nombre, elige categoría, monto, tipo y (opcional) medio de pago. Tab avanza de campo.
4. Enter o "Guardar" → valida. Si hay errores se muestran debajo de cada campo y el diálogo
   sigue abierto.
5. Si está todo bien: se cierra, la fila aparece en la tabla, los totales y "Por medio de pago"
   se actualizan, SnackBar "Gasto "Nafta" agregado".

**Flujo: cargar un gasto en dólares**

1. Clic en "Agregar gasto". Escribe "Claude" y elige la categoría.
2. En "Moneda" elige **Dólares (USD)** (clic o Tab hasta el selector y flechas/Espacio).
   Desaparece el campo "Monto" en pesos y aparecen "Monto en dólares" y "Cotización del día";
   el foco pasa a "Monto en dólares".
3. "Cotización del día" ya viene con la del mes ($ 1.600). Si el mes no tiene cotización,
   viene vacía con la ayuda "Este mes no tiene cotización: escribí la del día."
4. Escribe 20. En cada tecla, la línea de resultado muestra
   "US$ 20,00 × $ 1.600 = **$ 32.000 a pagar**".
5. Si pagó con tarjeta, cambia la cotización a la que le cobró (ej. 2.080): el resultado pasa a
   "US$ 20,00 × $ 2.080 = $ 41.600 a pagar".
6. Elige tipo y medio de pago y guarda. En la tabla aparece "Claude · $ 41.600" con la línea
   "US$ 20,00 × $ 2.080". SnackBar: "Gasto "Claude" agregado: $ 41.600 (US$ 20,00)".

**Flujo: marcar pagado (RF-13, RN-22)**

1. Clic en el tilde de la fila → se registra un pago por todo el pendiente.
2. La fila muestra Pendiente "Pagado"; los totales se actualizan.
3. SnackBar "Alquiler marcado como pagado" con acción **"Deshacer"** (borra ese pago).

**Flujo: destildar pagado (RN-22)** — es destructivo, así que pide confirmación:

> **¿Quitar los pagos de Seguro de moto?**
> Se van a borrar los 2 pagos registrados ($ 180.000). El gasto vuelve a quedar pendiente
> por $ 180.000.
> [Cancelar] [Quitar pagos]

**Flujo: pago parcial (RF-14, RN-21)**

1. Menú de la fila → "Registrar pago".
2. Diálogo §4.3: muestra "Monto $ 180.000 · Pagado $ 60.000 · Pendiente $ 120.000".
3. Escribe el monto (ej. 50.000). Botón auxiliar "Pagar todo lo pendiente" que completa el
   campo con $ 120.000.
4. "Guardar" → valida (> 0 y ≤ pendiente). Se cierra; la fila muestra Pagado $ 110.000
   "Parcial" y Pendiente $ 70.000. SnackBar "Pago de $ 50.000 registrado".
5. Si con ese pago el pendiente llega a 0, el tilde aparece marcado solo (CA-14.1).

Los pagos de un gasto en dólares también se registran **en pesos** (se pagan en pesos); el
diálogo agrega debajo del resumen la línea secundaria "Gasto en dólares: US$ 20,00 × $ 1.600".

**Flujo: ver y borrar pagos (RF-15)**

1. Menú de la fila → "Ver pagos". Diálogo §4.4 con la lista de pagos (fecha, monto, botón
   borrar).
2. Clic en el ícono de borrar de un pago → confirmación en línea: la fila del pago cambia a
   "¿Borrar este pago? [No] [Sí, borrar]" (evita abrir un diálogo encima de otro).
3. Al confirmar, la lista y los totales del diálogo se actualizan; al cerrar, la tabla también.

**Flujo: borrar un gasto (RF-08, RN-51, RN-52)**

Confirmación para un gasto común:

> **¿Borrar el gasto Nafta?**
> Se borran también sus pagos ($ 0 pagado). Esta acción no se puede deshacer.

Si es compartido, se agrega: "También desaparecen las partes de Sofía y Marsu de 'Me deben'."

Si es la cuota de un plan:

> **¿Borrar la cuota 4/6 de Préstamo X en Noviembre 2026?**
> Se borra solo la cuota de este mes. El plan sigue en los demás meses y esta cuota no se
> vuelve a generar en Noviembre 2026.
> Si querés terminar la deuda antes, usá "Cancelar plan" en la pantalla Cuotas.
> [Cancelar] [Borrar cuota]

---

### 3.4 Cuotas (RF-16 a RF-21)

**Objetivo del usuario:** ver todas sus deudas en cuotas, en qué cuota va, cuándo terminan y
cuánto le falta; cargar planes nuevos, editarlos o cancelarlos. Los planes son **solo en
pesos** (los gastos en dólares no aplican a cuotas).

**Distribución**

```
+--------------------------------------------------------------------------------------------+
| Planes de cuotas                                                      [+ Nuevo plan]       |
| Cuota y restante calculados para Octubre 2026 (mes seleccionado).                          |
|                                                                                            |
| [ Activos (4) | Terminados (2) | Cancelados (1) ]                                          |
|                                                                                            |
| +----------------------------------------------------------------------------------------+ |
| | Nombre        | Categoría | Medio          |   Cuota | Cuota del mes | Primera  | Última   |  Restante |   |
| | Avant Service | Deudas    | Visa Santander | $41.117 | 3/3           | ago 2026 | oct 2026 |        $0 |[:]|
| | Plan B        | Deudas    | —              | $10.000 | 8/12          | mar 2026 | feb 2027 |   $40.000 |[:]|
| | Heladera      | Hogar     | Mastercard Nac.| $25.000 | No empezó     | dic 2026 | nov 2027 |  $300.000 |[:]|
| |---------------+-----------+----------------+---------+---------------+----------+----------+-----------+---|
| | Total         |           |                | $76.117 |               |          |          |  $340.000 |   |
| +----------------------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------------------+
```

**Componentes**

| Parte | Componente |
|---|---|
| Filtro (RF-21) | `ft.SegmentedButton` con 3 segmentos y `allow_multiple_selection=False`. Las cantidades van en la etiqueta. Por defecto "Activos". |
| Tabla | `ft.DataTable`. "Cuota", "Restante" con `numeric=True`. |
| Cuota del mes | "n/N"; o "No empezó" (texto secundario); o "Terminado" (*positivo* + ícono `CHECK`); o "Cancelado" (texto secundario + ícono `BLOCK`). |
| Acciones | `ft.PopupMenuButton`: "Editar plan", "Cancelar plan" (solo activos), "Ir a la cuota del mes" (si existe; va a Gastos). |
| Total | Fila final: suma de cuotas (en "Activos" es lo que se paga por mes en cuotas) y suma de restantes. |

**Aclaración visible sobre los dos meses de referencia.** El filtro activos/terminados/
cancelados se calcula con el **mes actual** (CA-21.1) y la columna "Cuota del mes"/"Restante"
con el **mes seleccionado** (RF-17). Para que no confunda, el subtítulo dice siempre para qué
mes se calculan la cuota y el restante, y el tooltip del filtro dice "Según el mes actual
(Octubre 2026)".

**Estados**

| Situación | Cómo se ve |
|---|---|
| Sin planes | Estado vacío: ícono `CREDIT_CARD`, "No tenés planes de cuotas cargados.", botón "Nuevo plan". |
| Filtro sin resultados | Texto en la tabla: "No hay planes terminados." (según el filtro). |
| Mes seleccionado ≠ mes actual | La franja informativa de §1.2 y el subtítulo con el mes seleccionado. |

**Flujo: cargar un plan de cuotas (RF-16, RF-18, RN-29, RN-30)**

1. Clic en "Nuevo plan" (desde Cuotas o desde Gastos).
2. Diálogo §4.2. Arriba, aviso *info*: "Las cuotas se agregan desde el mes actual
   (Octubre 2026) y en los meses siguientes que ya existan. Los meses anteriores no se
   modifican."
3. Completa nombre, categoría, medio (opcional), monto de la cuota, cantidad de cuotas y mes y
   año de la primera cuota.
4. Mientras completa, una **vista previa** debajo del formulario se actualiza:
   "Última cuota: Octubre 2026 · Total del plan: $ 123.350 · En Octubre 2026 va la cuota 3/3".
5. "Guardar" → se cierra, el plan aparece en la tabla, y SnackBar "Plan creado. Se agregó la
   cuota 3/3 en Octubre 2026." (o "No se agregaron cuotas: Octubre 2026 todavía no existe.
   La cuota aparecerá al crear ese mes." en el caso CA-18.3).

**Flujo: editar un plan (RF-19)**

Mismo diálogo con los datos cargados. Aviso *info* arriba: "Los cambios se aplican desde
Octubre 2026. Las cuotas que ya tienen pagos no se modifican." Al guardar, SnackBar con lo
que pasó (ej. "Se actualizaron las cuotas de Octubre 2026 y Noviembre 2026").

**Flujo: cancelar un plan (RF-20, RN-31)** — confirmación con el resultado concreto:

> **¿Cancelar el plan Plan B?**
> Se borran sus cuotas de Octubre 2026 y Noviembre 2026 y no se generan más.
> Las cuotas de meses anteriores se conservan.
> [Volver] [Cancelar plan]

Si la cuota del mes actual tiene pagos:

> La cuota de Octubre 2026 ya tiene pagos: se conserva y pasa a ser la última.
> Se borra la de Noviembre 2026.

(El botón de confirmar dice "Cancelar plan" y el de salir dice "Volver", para no tener dos
botones "Cancelar" con significados opuestos.)

---

### 3.5 Me deben (RF-28 personas en uso, RF-32, RF-33, RF-34)

**Objetivo del usuario:** saber cuánto le debe cada persona (sumando todos los meses), anotar
préstamos sueltos y tildar lo que ya cobró. Equivale a "Deudas sofia" y "Marsu" de la planilla.

**Distribución** (una tarjeta por persona, lado a lado como en la planilla):

```
+--------------------------------------------------------------------------------------------+
| Me deben                                    Total: $ 461.913      [ ] Mostrar cobrados     |
|                                                                                            |
| +------------------------------------------+ +------------------------------------------+ |
| | (S) Sofía                    $ 255.114   | | (M) Marsu                    $ 206.899   | |
| |                          [+ Agregar ítem]| |                          [+ Agregar ítem]| |
| |------------------------------------------| |------------------------------------------| |
| | [ ] Préstamo MP               $ 20.000   | | [ ] Internet                  $ 12.900   | |
| |     A mano · 02/10/2026            [:]   | |     Gasto de oct 2026                    | |
| | [ ] Internet                  $ 12.900   | | [ ] tacones                    $ 6.785   | |
| |     Gasto de oct 2026                    | |     A mano · 15/09/2026            [:]   | |
| | [ ] Internet                  $ 15.000   | | ...                                      | |
| |     Gasto de nov 2026                    | |                                          | |
| |     Cobrado $ 12.900 · falta $ 2.100     | |                                          | |
| | [ ] Servicios Luz Gas         $ 10.000   | |                                          | |
| |     Gasto de dic 2026                    | |                                          | |
| |     Cobrado $ 12.900 · a devolver $ 2.900| |                                          | |
| +------------------------------------------+ +------------------------------------------+ |
+--------------------------------------------------------------------------------------------+
```

**Componentes**

| Parte | Componente |
|---|---|
| Total general (RN-40) | `ft.Text` 24 bold. |
| Mostrar cobrados | `ft.Switch(label="Mostrar cobrados", value=False)`. La lista crece todos los meses; por defecto se ven solo las líneas pendientes. |
| Tarjeta de persona | `ft.Card` en un `ft.ResponsiveRow` (`col={"md": 6, "xl": 4}`), así 2 personas quedan lado a lado y 3 o más bajan de renglón. Encabezado: `ft.CircleAvatar` con la inicial, nombre, total de la persona (RN-35) y botón "Agregar ítem". Si la persona está archivada, chip "Archivada". |
| Línea | `ft.ListTile(leading=ft.Checkbox(...), title=descripción, subtitle=origen, trailing=monto)`. |
| Origen | "Gasto de oct 2026" (parte de gasto compartido) o "A mano · 02/10/2026" (ítem manual). |
| Diferencia (RN-34) | Segunda línea del subtítulo: "Cobrado $ 12.900 · falta $ 2.100" en *pendiente*, o "Cobrado $ 12.900 · a devolver $ 2.900" en *negativo*. |
| Acciones de ítems manuales | `ft.PopupMenuButton`: "Editar", "Borrar" (ver Observaciones). Las partes de gastos no tienen menú: se editan desde el gasto. |
| Línea cobrada (si se muestran) | Texto tachado no; se ve en texto secundario con el tilde marcado y la etiqueta "Cobrado" en *positivo*. |

Las partes de un gasto en dólares compartido se muestran y se cobran **en pesos** (son
porciones del monto en pesos del gasto).

**Estados**

| Situación | Cómo se ve |
|---|---|
| Sin personas | Estado vacío: "Agregá a las personas con las que compartís gastos.", botón "Ir a Personas" (Ajustes). |
| Persona sin deudas pendientes | En su tarjeta: "Sofía no te debe nada." con ícono `CHECK_CIRCLE` *positivo*. Total `$ 0`. |
| Total de una persona negativo (solo "a devolver") | Total en *negativo* con la leyenda "Le tenés que devolver". |

**Flujo: marcar un gasto como compartido y cobrar (RF-29, RF-30, RF-34)**

1. En Gastos, clic en el nombre del gasto (ej. Internet) → diálogo de edición §4.1.
2. Activa el `ft.Switch` "Compartido". Aparecen las personas (no archivadas) con un
   `ft.Checkbox` cada una.
3. Tilda Sofía y Marsu. Aparece la tabla de partes ya calculada en partes iguales:
   Sofía $ 12.900 · Marsu $ 12.900 · **Tu parte $ 12.900** (solo lectura).
4. (Opcional) Cambia la parte de Sofía a 15.000. Al lado aparece la etiqueta "manual" y "Tu
   parte" pasa a $ 10.800 al instante. Botón "Repartir en partes iguales" vuelve todas a
   automáticas.
5. "Guardar". En la tabla de Gastos, Internet muestra el ícono de compartido. El total de
   gastos **no cambia** (sigue contando $ 38.700, RN-12).
6. Cuando Sofía le paga: pantalla Me deben → tarjeta de Sofía → tilda "Internet · Gasto de
   oct 2026". El total de Sofía y el total general bajan; SnackBar "Marcado como cobrado" con
   "Deshacer". Con "Mostrar cobrados" apagado, la línea desaparece de la vista.

**Flujo: agregar un ítem a mano (RF-32)**

1. "Agregar ítem" en la tarjeta de la persona (o `Ctrl/Cmd+N`, que pregunta la persona).
2. Diálogo §4.8: persona (precargada), descripción, monto, fecha (hoy).
3. "Guardar" → aparece como no cobrado y suma al total.

---

### 3.6 Diálogos de sueldo, cotización y meta (RF-23, RF-25, RF-36)

Son diálogos chicos de un solo campo, que se abren desde el Resumen, la barra superior o
Ajustes.

```
+-------------------------------------------+
| Cotización de Octubre 2026                |
|                                           |
| [ $              1.600   ARS ] por US$    |
| Se usa para calcular los dólares a        |
| cambiar. No modifica los cambios ya       |
| registrados ni los gastos en dólares ya   |
| cargados.                                 |
|                                           |
|                    [Cancelar] [Guardar]   |
+-------------------------------------------+
```

| Diálogo | Campo | Validación y mensaje |
|---|---|---|
| Sueldo | Monto USD | Vacío: "Ingresá el sueldo. Si este mes no cobrás, poné 0." Negativo: "El sueldo no puede ser negativo." 0: se acepta y queda el aviso en Resumen. |
| Cotización | Monto ARS por USD | ≤ 0: "La cotización tiene que ser mayor a 0." Vacía: "Ingresá la cotización." (una vez cargada no se ofrece borrarla; ver Observaciones). |
| Meta de ahorro | Monto USD | ≤ 0: "La meta tiene que ser mayor a 0." Ayuda: "Es la misma para todos los meses." Botón secundario "Quitar meta" si hay una (ver Observaciones). |

Al guardar cualquiera de los tres, todo lo que depende se recalcula al instante (RN-19) y
SnackBar "Cotización actualizada: $ 1.700 por US$".

**Cotización del mes y gastos en dólares.** Los gastos en dólares guardan su propia
"cotización del día" y sus pesos quedan fijos (decisión aprobada), así que cambiar la
cotización del mes **no** los recalcula; por eso el texto de ayuda lo dice. Si el mes tiene
gastos en dólares, debajo se agrega: "Este mes tiene 2 gastos en dólares. Si querés
actualizarlos, editalos uno por uno."

#### Buscar la cotización en internet (v2: RF-25, RF-60, RF-61, RF-62, RN-80 a RN-88)

**Objetivo del usuario:** completar la cotización del mes con el dólar de hoy sin tener que
mirarla en otro lado ni tipearla. Sigue teniendo el control: el botón solo **completa el
campo**; lo que se guarda lo decide él con "Guardar", como siempre (RN-84).

**Dónde está.** Solo en este diálogo (el de la cotización **del mes**), sea cual sea la
forma de abrirlo: `Ctrl/Cmd+K`, el lápiz de la barra, "Cargar cotización" del Resumen o de la
Previsión. **No está** en el formulario de primer uso (§3.1), en "Mes nuevo" (§3.9), en la
cotización del día de un gasto en dólares (§4.1), en el cambio de USD (§4.6) ni en la
importación (RN-88). Esos campos se ven exactamente como antes.

**Cuándo está (RN-80).** Solo si el mes seleccionado es el mes actual o uno futuro. En un
**mes pasado no hay botón, ni deshabilitado, ni su ayuda**: el diálogo se ve como el boceto de
arriba, sin ningún cambio. Se decide al abrir el diálogo.

**Distribución – mes actual o futuro, antes de buscar**

```
+------------------------------------------------+
| Cotización de Octubre 2026                     |
|                                                |
| [ $              1.600   ARS ] por US$         |
|                                                |
| [nube] Buscar dólar blue                       |
| Trae el precio de compra de hoy desde          |
| internet (DolarApi) y completa el campo.       |
| No se guarda hasta que toques Guardar.         |
| El dólar se elige en Ajustes.                  |
|                                                |
| Se usa para calcular los dólares a cambiar.    |
| No modifica los cambios ya registrados ni      |
| los gastos en dólares ya cargados.             |
|                                                |
|                      [Cancelar] [Guardar]      |
+------------------------------------------------+
```

**Orden vertical de los elementos** (de arriba abajo; cada uno se oculta con `visible`, no
se reconstruye el diálogo):

| # | Elemento | Siempre / condicional |
|---|---|---|
| 1 | Campo de cotización (como hoy, `campo_monto("ARS")`, `autofocus=True`) | Siempre |
| 2 | **Origen** debajo del campo | Solo tras una búsqueda válida y sin editar el campo |
| 3 | **Fila de búsqueda**: botón + ruedita + estado | Solo mes actual o futuro |
| 4 | **Mensaje de error** | Solo tras una búsqueda fallida |
| 5 | Ayuda del botón | Solo mes actual o futuro |
| 6 | Texto actual de ayuda de §3.6 (y la línea de gastos en dólares si corresponde) | Siempre |

El origen va **pegado al campo** porque habla del valor del campo; el error va **pegado al
botón** porque es el resultado de tocarlo. Los dos pueden verse a la vez (ver "Error después
de un acierto").

**Componentes de Flet**

| Parte | Componente | Detalle |
|---|---|---|
| Botón | `ft.OutlinedButton("Buscar dólar blue", icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED)` | Es secundario a propósito: "Guardar" sigue siendo la única acción principal (`FilledButton`). El texto cambia con el dólar elegido en Ajustes: "Buscar dólar blue" / "Buscar dólar MEP" / "Buscar dólar oficial" / "Buscar dólar cripto" (RN-79). Tooltip: "Busca el precio de compra de hoy en internet. No guarda nada." |
| Ruedita | `ft.ProgressRing(width=18, height=18, stroke_width=2, visible=False, semantics_label="Buscando la cotización")` | A la derecha del botón, en la misma fila (`ft.Row(spacing=12)`), para que el botón no se mueva al aparecer. |
| Texto de estado | `ft.Text` 13, texto secundario, `visible=False`, junto a la ruedita | "Buscando la cotización…". |
| Origen | `ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, size=16, color=info), ft.Text(origen, size=13, color=texto_secundario)])`, `visible=False` | Texto exacto: "Dólar blue compra, 18/10/2026 14:05 (DolarApi)". Lo arma la lógica (9a); la interfaz solo lo muestra. Si no entra en una línea, baja a otra (`expand=True` en el texto). |
| Error | `ft.Container` con fondo *negativo* suave, `border_radius=8`, ícono `ERROR_OUTLINE` + texto 13 en *negativo* (patrón "Aviso en pantalla" de §2.5) | Texto exacto: "No se pudo obtener la cotización. Revisá tu conexión o cargala a mano." Sin detalles técnicos. |
| Ayuda del botón | `texto_ayuda` (13, texto secundario) | Ver el boceto. En un mes **futuro** se agrega una frase: "Es la cotización de hoy, no la de Noviembre 2026." (observación 37). |

**Los cuatro estados de la fila de búsqueda**

```
(1) Reposo                       (2) Buscando (hasta 10 s)
[nube] Buscar dólar blue         [nube] Buscar dólar blue  (o) Buscando la cotización…
                                 (botón gris, no se puede tocar; "Guardar" también gris)

(3) Resultado válido             (4) Error
[ $          1.630,50  ARS ]     [ $              1.600   ARS ] por US$
(i) Dólar blue compra,           [nube] Buscar dólar blue
    18/10/2026 14:05 (DolarApi)  +--------------------------------------------------+
[nube] Buscar dólar blue         | (!) No se pudo obtener la cotización. Revisá tu  |
                                 |     conexión o cargala a mano.                   |
                                 +--------------------------------------------------+
```

**Estado buscando (RN-86)**

- Al tocar el botón, **en el mismo instante** (antes de lanzar el pedido): el botón se
  deshabilita con el mismo texto, aparece la ruedita con su texto de estado, el error anterior
  se oculta y el campo pasa a **solo lectura**. Deshabilitar primero es lo que garantiza que
  dos clics seguidos hagan un solo pedido.
- El campo queda **bloqueado** con `read_only=True` y no con `disabled=True` (decisión de la
  pregunta P-3; el porqué está en la observación 34): el valor se sigue leyendo con el
  contraste normal: es el valor que queda si la búsqueda falla o se cancela.
- El origen que hubiera de una búsqueda anterior **se queda** (el campo no cambió).
- "Guardar" se **deshabilita** (decisión del usuario, observación 35) y `Enter` en el campo
  no guarda. "Cancelar" sigue activo, normal, sin ruedita ni atenuado. Al terminar la
  búsqueda (bien o con error), "Guardar" se vuelve a habilitar.
- Máximo 10 segundos. Si se cumplen sin respuesta completa, es un error (estado 4). Ese
  tiempo lo controla la lógica (9a), no la interfaz.

**Al terminar la búsqueda**

| Resultado | Qué pasa en el diálogo | Foco |
|---|---|---|
| Válido | El campo pasa a la cotización con sus decimales (`1.630,50`; `1.630` si es entera), vuelve a ser editable; se muestra el origen; se oculta el error; el botón se rehabilita. **No se guarda nada**: el Resumen de atrás sigue con la cotización guardada. | Al campo, con el cursor al final y sin seleccionar (así `Enter` guarda y escribir corrige). |
| Error | El campo queda **como estaba**; el origen anterior (si el campo no se editó) se conserva; aparece el mensaje de error; el botón se rehabilita (sirve para reintentar). | Al botón de buscar, para reintentar con `Enter`/Espacio sin que un `Enter` guarde por accidente. |

En los dos casos, el foco solo se mueve si el usuario no lo llevó a otro lado mientras
esperaba (por ejemplo, a "Cancelar"); si Flet no permite saberlo, se deja donde estaba.

**Cuándo desaparece el origen (RN-85)**

| Hecho | Origen |
|---|---|
| El usuario cambia el texto del campo (escribir, borrar, pegar), aunque después vuelva a dejar el mismo valor | **Desaparece** y no vuelve solo. |
| Nueva búsqueda válida | Se reemplaza por el nuevo. |
| Búsqueda con error | Se conserva (el campo no cambió). |
| Salir del campo (`on_blur`) y que la app reescriba el formato ("1.630,5" → "1.630,50") | No cambia: solo desaparece con un cambio hecho por el usuario. |
| Cerrar el diálogo con Guardar o Cancelar (Guardar, solo cuando no busca) | Desaparece. Al reabrirlo no se ve, aunque la cotización guardada sea la que vino de DolarApi (no se guarda). |

Nota para quien programe: el `on_change` de un `TextField` de Flet se dispara por lo que
escribe el usuario, no por asignar `campo.value` desde el código. Eso es lo que se necesita
(la búsqueda escribe el valor sin ocultar el origen que acaba de mostrar); verificarlo en Flet
1.0.3.

**Cuándo desaparece el error (RN-87)**: al empezar otra búsqueda, al cambiar el campo a mano
y al cerrar el diálogo.

**Cerrar el diálogo mientras busca (RN-86)**

- `Cancelar` y `Esc` funcionan igual que siempre y **cierran en el acto**, sin
  confirmación y sin esperar. Ninguna cierra "después de que termine".
- La respuesta que llega después (válida o error) **se descarta en silencio**: no escribe
  nada, no muestra mensajes ni SnackBars y no guarda. Al reabrir el diálogo empieza limpio.
- `Guardar` está deshabilitado durante la búsqueda (observación 35).
- Para descartar bien, cada vez que se abre el diálogo se crea una "ficha" nueva; la búsqueda
  la recuerda y, al volver, solo escribe en pantalla si el diálogo sigue abierto y la ficha es
  la misma.

**Teclado**

- Orden de Tab: campo → "Buscar dólar …" → "Cancelar" → "Guardar".
- `Enter` en el campo = Guardar (durante la búsqueda no hace nada). `Enter` o Espacio sobre el
  botón = buscar. `Esc` = Cancelar.
- No se agrega un atajo propio para buscar: dentro de un diálogo los atajos globales se
  ignoran (§1.3), y con Tab alcanza (observación 38).
- Con el botón deshabilitado, Tab lo saltea; por eso el estado se explica también con texto
  ("Buscando la cotización…") y no solo con el botón gris.

**Tema oscuro.** Los colores salen de §2.1: error `#FF8A80` sobre `#3D1F1D` (≈ 6,5:1), origen
en `#B7BEC4` (≈ 8:1) con el ícono en `#8CCDF0`, ruedita y borde del botón en el primario
`#8CCDF0` (≈ 9:1) sobre la superficie `#1B2024`. En el tema claro: error `#B3261E` sobre
`#FCE8E6`, origen `#4A5056`, ícono, ruedita y borde del botón `#1F5F7A`. El botón
deshabilitado usa el color que Flet le da; no hace falta que cumpla el contraste, y por eso
el texto de estado a su lado lleva el significado.

**Flujo paso a paso (mes actual, con DolarApi funcionando)**

1. `Ctrl/Cmd+K`. El diálogo muestra el campo con "1.600" y "Buscar dólar blue".
2. Toca el botón. Aparece "Buscando la cotización…"; el campo no se puede escribir.
3. A los 2 segundos, el campo dice "1.630,50" y debajo "Dólar blue compra, 18/10/2026 14:05
   (DolarApi)". La ruedita desaparece. El Resumen de atrás sigue en $ 1.600.
4. Decide: `Enter` o "Guardar" → se cierra, SnackBar "Cotización actualizada: $ 1.630,50 por
   US$" y el Resumen se recalcula (RN-19). O "Cancelar" / `Esc` → la cotización sigue en
   $ 1.600.

**Flujo alternativo – error y carga a mano**

1. Sin internet, toca el botón. Tras la espera (de inmediato si no hay red, hasta 10
   segundos si no responde), aparece el mensaje de error y el campo sigue en "1.600".
2. Puede reintentar con el botón, o escribir la cotización a mano: al empezar a escribir, el
   mensaje desaparece. "Guardar" funciona igual que siempre.

**Error después de un acierto (CA-62.6).** Si ya había buscado bien (campo en "1.630,50" con
su origen) y una segunda búsqueda falla, se ven **a la vez**: el campo "1.630,50", su origen y
el mensaje de error debajo del botón. Es correcto: el origen sigue siendo verdad para ese
valor.

**Estados del diálogo**

| Situación | Cómo se ve |
|---|---|
| Mes pasado | Sin botón, sin ruedita, sin ayuda del botón: igual que el boceto original de §3.6. |
| Mes actual, reposo | Boceto de "Distribución". |
| Mes futuro, reposo | Igual, con la frase extra en la ayuda del botón. |
| Mes sin cotización (campo vacío) | Igual; el botón completa el campo vacío. Es el uso más común de la función. |
| Buscando | Estado (2). |
| Búsqueda válida | Estado (3). |
| Búsqueda con error | Estado (4). |
| Error de validación al guardar (campo vacío o ≤ 0) | Como siempre: `error_text` en el campo (§2.5). No interfiere con el origen, que ya no está si el campo se vació. |

**Después de guardar.** No hay ninguna marca de "buscada en internet" en la barra ni en el
Resumen: la cotización guardada es un número más (RN-85, §5.14 de requisitos).

---

### 3.7 Previsión (RF-38, RF-39)

**Objetivo del usuario:** ver cómo van a ser los próximos 12 meses solo con gastos fijos y
cuotas, y cuándo se libera plata por cuotas que terminan.

**Distribución**

```
+--------------------------------------------------------------------------------------------+
| Previsión de los próximos 12 meses                                                         |
| Desde Noviembre 2026. Con la cotización ($ 1.600 por US$) y el sueldo (US$ 1.200,00) de    |
| Octubre 2026 (mes actual). Solo gastos fijos y cuotas; sin inflación ni ingresos extra.    |
|                                                                                            |
| +----------------------------------------------------------------------------------------+ |
| | Mes       | Gastos estimados | Dólares a cambiar | Ahorro estimado | Se libera          | |
| | nov 2026  |        $ 810.000 |    US$ 506,25 |      US$ 693,75 | Avant +$ 41.117        | |
| | dic 2026  |        $ 810.000 |    US$ 506,25 |      US$ 693,75 |                        | |
| | ...       |                  |               |                 |                        | |
| | mar 2027  |        $ 800.000 |    US$ 500,00 |      US$ 700,00 | Plan B +$ 10.000       | |
| | ...       |                  |               |                 |                        | |
| | oct 2027  |        $ 800.000 |    US$ 500,00 |      US$ 700,00 |                        | |
| +----------------------------------------------------------------------------------------+ |
|                                                                                            |
| Ver el gráfico de previsión >                                                              |
+--------------------------------------------------------------------------------------------+
```

**Componentes:** `ft.DataTable` con 12 filas. Las filas con liberaciones tienen fondo
*positivo* suave y el texto "Avant +$ 41.117" en *positivo* con ícono `ARROW_DOWNWARD`
(baja el gasto). Si se liberan varios planes, van uno debajo del otro en la celda
(`ft.Column`). Ahorro estimado negativo: `-US$ …` en *negativo* con la palabra "Déficit".
Enlace `ft.TextButton` al gráfico de previsión (Gráficos, pestaña 3).

**Estados (RN-45)**

| Situación | Cómo se ve |
|---|---|
| Mes actual no existe | Sin tabla. Estado vacío: "Creá el mes Octubre 2026 para ver la previsión." + botón "Mes nuevo" si el siguiente al último es justamente ese mes; si no, solo el texto. |
| Mes actual sin cotización | Aviso *pendiente*: "Falta la cotización de Octubre 2026: se muestran solo los gastos en pesos." + botón "Cargar cotización". Las columnas USD y Ahorro muestran "—". |
| Normal | Como el boceto. |

Gastos fijos en dólares en la previsión: ver Observaciones (falta definir con qué cotización
se estiman).

---

### 3.8 Gráficos (RF-40, RF-41, RF-42)

**Objetivo del usuario:** ver en qué se le va la plata, cómo evolucionó su ahorro y cómo bajan
los gastos en el futuro.

**Distribución:** `ft.Tabs` con 3 pestañas.

```
+--------------------------------------------------------------------------------------------+
| Gráficos                                                                                   |
| [ Gastos por categoría ] [ Ahorro mes a mes ] [ Previsión de gastos ]                      |
|--------------------------------------------------------------------------------------------|
| Tu parte de los gastos de Octubre 2026, por categoría                                      |
|                                                                                            |
| Vivienda        ███████████████████████████████████████   $ 260.000   75 %                |
| Servicios       █████                                      $ 34.994   10 %                 |
| Transporte      ████                                       $ 30.000    9 %                 |
| Comunicaciones  ███                                        $ 20.000    6 %                 |
|                                                                                            |
| En los gastos compartidos se cuenta solo tu parte.                                         |
+--------------------------------------------------------------------------------------------+
```

| Gráfico | Tipo | Ejes / contenido | Color | Componente de Flet |
|---|---|---|---|---|
| 1. Gastos por categoría (RN-46), mes seleccionado | **Barras horizontales**, ordenadas de mayor a menor | Una fila por categoría: nombre (izquierda), barra proporcional al mayor, monto ARS y porcentaje del total. Los gastos en dólares cuentan por sus pesos. | Un solo color: *primario*. | **Sin librería de gráficos**: cada fila es un `ft.Row` con `ft.Text` (ancho fijo 160), `ft.ProgressBar(value=monto/máximo, height=18)` y dos `ft.Text`. Es más simple, los nombres largos se leen completos y el dato exacto está escrito. |
| 2. Ahorro mes a mes (RN-47), todo el historial | **Barras verticales** | Eje X: meses (`oct 26`). Eje Y: USD, con 0 marcado. Tooltip: "Octubre 2026: US$ 303,36". | Positivo: *positivo*. Negativo (déficit): *negativo*, la barra baja del 0. Mes sin cotización: sin barra y etiqueta "s/cot." debajo del mes. | `BarChart` (ver nota). Si hay meta, una línea de texto arriba: "Meta: US$ 300,00". |
| 3. Previsión de gastos (RN-48) | **Barras verticales** | Eje X: los 12 meses previstos. Eje Y: ARS abreviado ("$ 800 mil"). Tooltip con el monto completo. | *Primario*. | `BarChart`. |

Por qué barras y no torta: las barras permiten comparar tamaños a simple vista y se leen igual
con daltonismo; la torta obliga a comparar ángulos y a usar muchos colores.

Debajo de los gráficos 2 y 3 hay un `ft.ExpansionTile("Ver como tabla")` con los mismos datos
en una `ft.DataTable` (accesibilidad: lectores de pantalla y quien prefiera números).

**Nota sobre el componente de gráficos:** el proyecto usa **Flet 1.0.3**. En Flet 1.x los
gráficos están en el paquete aparte `flet-charts` (`import flet_charts as fch`,
`fch.BarChart`, con sus grupos, barras y ejes). Antes del paso 7 hay que agregar
`flet-charts` a `requirements.txt` y verificar los nombres exactos de las clases en esa
versión.

**Estados**

| Gráfico | Vacío | Aviso |
|---|---|---|
| Por categoría | "No hay gastos en Octubre 2026 para graficar." | – |
| Ahorro | Con 1 solo mes se ve 1 barra (no es un error). | Si algún mes no tiene cotización: "Los meses marcados 's/cot.' no tienen cotización cargada." |
| Previsión | Mismos mensajes que la pantalla Previsión (§3.7). | Sin cotización: el gráfico se ve igual (son ARS). |

---

### 3.9 Meses: crear y borrar (RF-02, RF-03, RF-05)

No es una pantalla, son dos diálogos que se abren desde la barra superior.

**Flujo: crear mes nuevo (RF-03, RN-08, RN-09)**

1. Clic en "Mes nuevo" (o `Ctrl/Cmd+Shift+N`).
2. Diálogo:

```
+-----------------------------------------------------------+
| Crear Noviembre 2026                                      |
| Solo se puede crear el mes siguiente al último.           |
|                                                           |
| Sueldo       [ US$        1.200,00  USD ]                 |
| Cotización   [ $          1.600     ARS ] por US$         |
|              Sugeridos del mes anterior. Podés cambiarlos.|
|                                                           |
| Se va a copiar de Octubre 2026:                           |
|  • 12 gastos fijos, sin pagos                             |
|    (2 en dólares: se pasan a pesos con la cotización      |
|     de arriba)                                            |
|  • 4 cuotas de planes activos                             |
| No se copian pagos únicos, ingresos extra ni cambios.     |
|                                                           |
|                           [Cancelar] [Crear mes]          |
+-----------------------------------------------------------+
```

3. El mes no se elige: es siempre el siguiente al último (RN-08), así no hay cómo
   equivocarse. Sueldo y cotización vienen sugeridos (CA-03.2).
4. **Gastos fijos en dólares:** se copian con el mismo monto en dólares y su "cotización del
   día" pasa a ser la cotización del mes nuevo (la del campo de arriba); los pesos se
   recalculan con ella (decisión aprobada). La línea "(2 en dólares: …)" solo aparece si hay
   alguno. Si el usuario deja la cotización vacía y hay fijos en dólares, la línea cambia a
   *pendiente*: "Sin cotización, los 2 gastos en dólares conservan la cotización con la que
   se cargaron." (o, con uno solo, "el gasto en dólares conserva la cotización con la que se
   cargó"). Así lo define RN-57: sin cotización del mes nuevo, cada fijo en dólares conserva
   la suya.
   Si con la cotización nueva algún fijo en dólares diera $ 0 o un monto demasiado grande,
   el mes no se crea y el error aparece en el campo cotización (BUG-15).
5. "Crear mes" → la app selecciona el mes nuevo, muestra Resumen y SnackBar "Noviembre 2026
   creado: 12 gastos fijos y 4 cuotas."

Validaciones iguales a §3.1 (sueldo y cotización).

**Flujo: borrar el último mes (RF-05, RN-10)**

1. Menú "⋮" de la barra → "Borrar este mes" (solo habilitado en el último mes).
2. Confirmación:

> **¿Borrar Noviembre 2026?**
> Se borran 23 gastos, 15 pagos, 2 ingresos extra y 1 cambio de este mes.
> Las partes compartidas de este mes desaparecen de "Me deben".
> No se borran los planes de cuotas ni los ítems cargados a mano en "Me deben".
> [Cancelar] [Borrar mes]

3. Al confirmar, se selecciona el nuevo último mes. Si no queda ninguno, se muestra la
   pantalla de primer uso (§3.1).

---

### 3.10 Ajustes (RF-10, RF-11, RF-28, RF-36, apariencia)

**Objetivo del usuario:** administrar las listas que usa al cargar datos y las preferencias.

**Distribución:** `ft.Tabs` con: Categorías · Medios de pago · Personas · Meta de ahorro ·
Apariencia.

```
+--------------------------------------------------------------------------------------------+
| Ajustes                                                                                    |
| [ Categorías ] [ Medios de pago ] [ Personas ] [ Meta de ahorro ] [ Apariencia ]           |
|--------------------------------------------------------------------------------------------|
|                                         [ ] Mostrar archivadas      [+ Nueva categoría]    |
| +----------------------------------------------------------------------------------------+ |
| | Vivienda                                                   [Renombrar] [Eliminar]      | |
| | Servicios                                                  [Renombrar] [Archivar]      | |
| | Gym                         (Archivada)                    [Renombrar] [Desarchivar]   | |
| +----------------------------------------------------------------------------------------+ |
+--------------------------------------------------------------------------------------------+
```

**Listas (categorías, medios de pago, personas)** — las tres pestañas son iguales; conviene
programar **un solo componente reutilizable** que reciba el tipo de lista.

| Parte | Componente |
|---|---|
| Lista | `ft.ListView` de `ft.ListTile`, ordenada por nombre. |
| Archivada | `ft.Chip`/`ft.Container` chico "Archivada" en texto secundario; el nombre también en texto secundario. |
| Mostrar archivadas | `ft.Switch`, apagado por defecto. |
| Botones | `ft.TextButton`. El botón de baja dice **"Eliminar"** si no está en uso y **"Archivar"** si está en uso (RN-49), así el usuario sabe antes de hacer clic qué va a pasar. Tooltip de "Archivar": "Se usa en gastos: no se puede borrar. Archivada no aparece al cargar datos nuevos." |
| Crear / renombrar | Diálogo de un campo "Nombre". |

Validaciones (RN-50): vacío → "Ingresá un nombre."; repetido → "Ya existe una categoría
llamada "Salud"." (si la existente está archivada: "…llamada "Salud" (está archivada).
Podés desarchivarla.").

Eliminar (sin uso) pide confirmación corta: "¿Eliminar la categoría Salud?". Archivar no pide
confirmación (es reversible) y muestra SnackBar con "Deshacer".

**Meta de ahorro:** el mismo campo del diálogo §3.6, embebido en la pestaña, con el texto "Es
la misma meta para todos los meses."

**Apariencia:** `ft.RadioGroup` con "Claro", "Oscuro", "Como el sistema". Se guarda en la tabla
`configuracion` (clave `tema`) para recordarlo al reabrir. Además, un recordatorio de atajos
(`Ctrl/Cmd + /`).

#### Pestaña "Importar Excel" (v2: RF-49)

Se agrega una **sexta pestaña, la última: "Importar Excel"**. Orden final: Categorías · Medios
de pago · Personas · Meta de ahorro · Apariencia · Importar Excel.

```
| Ajustes                                                                                    |
| [ Categorías ] [ Medios de pago ] [ Personas ] [ Meta ] [ Apariencia ] [ Importar Excel ]  |
|--------------------------------------------------------------------------------------------|
|  Importar desde Excel                                                                      |
|  Traé gastos, cuotas, lo que te deben y el sueldo desde una planilla .xlsx.                |
|                                                                                            |
|   - Antes de guardar, revisás y corregís todo fila por fila.                               |
|   - El archivo no se modifica ni se guarda en la app.                                      |
|   - Lo importado se agrega al mes que elijas: no se borra nada de lo que ya cargaste.      |
|   - Si importás dos veces la misma planilla, las filas repetidas vienen destildadas.       |
|                                                                                            |
|   [ Importar Excel ]                                                                       |
+--------------------------------------------------------------------------------------------+
```

- Contenido: `ft.Column` con título de sección (16, `W_600`), `texto_ayuda` para la lista y
  `ft.FilledButton("Importar Excel", icon=ft.Icons.UPLOAD_FILE)`.
- Es una pestaña (y no un botón suelto en la barra) para que se encuentre donde el usuario ya
  busca "lo que se puede configurar o cargar en bloque" y para no ocupar lugar en las pestañas
  de listas. `Ctrl/Cmd+N` no tiene acción en esta pestaña (igual que Apariencia).
- Al **cancelar** se vuelve a **esta pestaña** (no a la primera). Al **terminar** la
  importación se muestra Gastos (o Resumen) del mes destino, como en §3.13.

#### Pestaña "Cotización" (v2: RF-59)

Con la cotización automática (Paso 9) se agrega una pestaña, **entre "Meta de ahorro" y
"Apariencia"**. Orden final, 7 pestañas: Categorías · Medios de pago · Personas · Meta de
ahorro · **Cotización** · Apariencia · Importar Excel ("Importar Excel" sigue siendo la
última). Se la ubica junto a "Meta de ahorro" porque las dos son valores que alimentan el
cálculo del ahorro; ver la observación 33 por la alternativa.

**Objetivo del usuario:** elegir de qué dólar quiere traer la cotización cuando toque
"Buscar dólar …" en el diálogo de la cotización del mes (§3.6).

```
| Ajustes                                                                                    |
| [ ... ] [ Meta de ahorro ] [ Cotización ] [ Apariencia ] [ Importar Excel ]                |
|--------------------------------------------------------------------------------------------|
|  Dólar para la cotización                                                                  |
|  Es el dólar que busca el botón "Buscar dólar…" del diálogo de la cotización del mes.      |
|                                                                                            |
|   (o) Blue                                                                                 |
|   ( ) MEP                                                                                  |
|   ( ) Oficial                                                                              |
|   ( ) Cripto                                                                               |
|                                                                                            |
|   Siempre se usa el precio de compra: lo que te pagan cuando vendés tus dólares.           |
|   Si no elegís otro, se usa Blue.                                                          |
|   Cambiarlo no modifica ninguna cotización ya guardada ni busca nada: solo cambia lo que   |
|   se busca la próxima vez.                                                                 |
|   La búsqueda consulta DolarApi (dolarapi.com) solo cuando tocás el botón y no envía       |
|   ningún dato tuyo.                                                                        |
+--------------------------------------------------------------------------------------------+
```

| Parte | Componente | Detalle |
|---|---|---|
| Título | `ft.Text("Dólar para la cotización")` 16 `W_600` | Es el nombre exacto del selector (RF-59). |
| Selector | `ft.RadioGroup` con cuatro `ft.Radio`, uno debajo del otro (`ft.Column`) | Etiquetas exactas: "Blue", "MEP", "Oficial", "Cripto", en ese orden. **Son las mismas que usa Apariencia**, así el usuario ya sabe cómo se usa. Sin ninguna opción de "compra" o "venta" (CA-59.1). |
| Ayuda | `texto_ayuda` (13, texto secundario) debajo del selector | Los cuatro párrafos del boceto. |

**Cuándo se guarda: al instante, sin botón "Guardar"**, igual que Apariencia. Cada vez que
cambia la selección (`on_change`):

1. Se guarda la clave `dolar_cotizacion` en `configuracion` con `blue`, `mep`, `oficial` o
   `cripto`.
2. SnackBar: "Dólar para la cotización: MEP".
3. **No se hace ningún pedido a internet** y no cambia ninguna cotización (RN-79, RN-88).

La próxima vez que se abra el diálogo de la cotización, el botón ya dice "Buscar dólar MEP".
Si había un diálogo abierto, no puede ser: los diálogos son modales y Ajustes no se toca
mientras tanto.

**Estados**

| Situación | Cómo se ve |
|---|---|
| Sin valor guardado, o un valor que no es uno de los cuatro | "Blue" elegido, sin ningún aviso. La base no se modifica hasta que el usuario elija algo (RN-79). |
| Falla el guardado | El radio vuelve a la opción anterior y se muestra el "Error inesperado" de §2.5. |

**Teclado.** Tab entra al grupo; flechas y Espacio cambian la opción (como en Apariencia).
`Ctrl/Cmd+N` no tiene acción en esta pestaña (igual que Apariencia). El tooltip del botón de
búsqueda del diálogo (§3.6) y su ayuda ("El dólar se elige en Ajustes.") remiten a esta
pestaña.

**Ancho de las pestañas.** Con 7 pestañas, a la ventana mínima de 1100 px no entran todas
las etiquetas de una vez. La barra de pestañas tiene que poder desplazarse
(`ft.Tabs`/`TabBar` con `scrollable=True`; verificar el nombre en Flet 1.0.3) y la pestaña
elegida tiene que quedar visible. Ver observación 33.

### 3.11 Importar Excel: elegir archivo y hoja (RF-49, RF-50, RF-58, RN-60, RN-61)

**Objetivo del usuario:** traer los datos de una planilla `.xlsx` sin tener que tipearlos.

**Recorrido completo (visión general)**

```
 [Primer uso o Ajustes]
          |
          v
 1. Elegir archivo (y hoja)  --->  3.11   (error de archivo: se queda acá)
          |
          v
 2. Lista de revisión        --->  3.12   (acá se hace el trabajo)
          |  [Confirmar importación]
          v
 3. Resumen previo           --->  3.13   (diálogo)
          |  [Importar]
          v
 4. Resultado y mes destino  --->  3.13   (diálogo + la app muestra el mes)

 En cualquier momento antes de "Importar": [Cancelar]  --->  3.14  (no se guarda nada)
```

**Es una pantalla completa, sin rail ni barra superior**, igual que Primer uso. Motivos:
(1) se abre igual desde el primer uso (donde no hay rail) y desde Ajustes; (2) la lista de
revisión necesita todo el ancho (hay 8 columnas); (3) evita que el usuario navegue a otra
pantalla o cambie de mes con una revisión a medias. Siempre tiene "Cancelar" visible.

**Distribución – paso 1, sin archivo todavía**

```
+--------------------------------------------------------------------------------------------+
|                                                                                            |
|                                   Importar desde Excel                                     |
|             Elegí un archivo .xlsx. Antes de guardar nada vas a poder revisar todo.        |
|                                                                                            |
|                 +---------------------------------------------------+                      |
|                 |  [icono planilla]                                 |                      |
|                 |                                                   |                      |
|                 |  El archivo solo se lee: no se modifica, no se    |                      |
|                 |  copia y no se guarda en la app.                  |                      |
|                 |                                                   |                      |
|                 |            [ Elegir archivo... ]                  |                      |
|                 |                                                   |                      |
|                 |                            [ Cancelar ]           |                      |
|                 +---------------------------------------------------+                      |
+--------------------------------------------------------------------------------------------+
```

**Componentes de Flet**

| Parte | Componente |
|---|---|
| Tarjeta | `ft.Card` centrada, ancho 520, mismo estilo que §3.1. |
| Elegir archivo | `ft.FilledButton("Elegir archivo...", icon=ft.Icons.UPLOAD_FILE)` que abre el selector del sistema con `ft.FilePicker` (`allowed_extensions=["xlsx"]`, título del diálogo del sistema "Elegir una planilla de Excel"). Foco inicial. |
| Mientras lee | `ft.ProgressRing` chico + texto "Leyendo el archivo..." (puede tardar con planillas grandes). Los botones quedan deshabilitados. |
| Cancelar | `ft.TextButton("Cancelar")`. Sin confirmación (todavía no hay nada que perder). |

El selector solo ofrece `.xlsx`, pero igual se valida al leer (RN-60: un `.txt` renombrado
pasa el filtro y debe rechazarse).

**Después de elegir el archivo**

| Caso | Qué pasa |
|---|---|
| Archivo con **una sola hoja** con datos | No se pregunta nada: pasa directo a la lista de revisión (CA-50.1). |
| Archivo con **varias hojas** con datos | La misma tarjeta muestra el paso de hoja (abajo). Las hojas sin celdas no se ofrecen (RN-60). |
| Archivo inválido | Aviso de error en la misma tarjeta (abajo). |

**Distribución – elegir hoja**

```
|                 +---------------------------------------------------+                      |
|                 |  Archivo: planilla-prueba.xlsx   [Elegir otro]    |                      |
|                 |                                                   |                      |
|                 |  El archivo tiene 2 hojas. ¿Cuál querés importar? |                      |
|                 |   (o) Octubre                                     |                      |
|                 |   ( ) Septiembre                                  |                      |
|                 |                                                   |                      |
|                 |  Se importa una hoja por vez. Si querés otra,     |                      |
|                 |  repetís la importación.                          |                      |
|                 |                                                   |                      |
|                 |               [ Cancelar ] [ Revisar filas ]      |                      |
|                 +---------------------------------------------------+                      |
```

- `ft.RadioGroup` con una `ft.Radio` por hoja (nombre tal cual está en el Excel). La primera
  viene elegida. Si hay más de 8 hojas, la lista tiene alto máximo 240 y scroll propio.
- "Revisar filas" = `ft.FilledButton`. Enter lo activa.
- "Elegir otro" = `ft.TextButton` chico junto al nombre del archivo: vuelve al estado inicial.

**Estados de error y aviso del archivo (RF-58)**

Todos usan el patrón "Aviso en pantalla" de §2.5 (fondo suave + ícono + texto) dentro de la
tarjeta, arriba de los botones.

| Situación | Dónde se ve | Texto exacto | Qué puede hacer el usuario |
|---|---|---|---|
| Archivo dañado, protegido con contraseña, con otra extensión o que no es `.xlsx` real | Aviso *negativo*, ícono `ERROR_OUTLINE`, en la tarjeta de elegir archivo | "No se pudo leer el archivo. Solo se aceptan archivos .xlsx de Excel." | Botón "Elegir otro archivo" o "Cancelar". No cambia nada. |
| Hoja sin ninguna celda con texto o número (archivo de una sola hoja) | Aviso *pendiente*, ícono `WARNING_AMBER` | "No se encontraron datos en la hoja Hoja1." | "Elegir otro archivo" o "Cancelar". |
| Hoja sin datos elegida entre varias | Mismo aviso, debajo de las hojas | "No se encontraron datos en la hoja Hoja1." | Elegir otra hoja y "Revisar filas", "Elegir otro archivo" o "Cancelar". |
| Hoja solo con textos (ninguna fila con texto y monto) | **No es un error de esta pantalla:** se muestra la lista de revisión con un aviso arriba (§3.12) | "No se encontraron filas con un texto y un monto." | Completar a mano. |
| Fórmulas sin valor guardado | Aviso arriba de la lista de revisión (§3.12), no acá | "Hay N fórmulas sin valor calculado (ej. D9). Abrí el archivo en Excel, guardalo y volvé a importarlo para ver esos montos." | Seguir igual, o cancelar y repetir. |

El mensaje de error del archivo se reemplaza (no se acumula) cada vez que se elige otro
archivo. Cuando el archivo tiene error, "Revisar filas" no aparece.

---

### 3.12 Importar Excel: lista de revisión (RF-51 a RF-56, RN-61 a RN-75)

**Objetivo del usuario:** revisar lo que la app entendió de su planilla, corregir lo que
esté mal y decidir qué se importa, sin que se guarde nada hasta confirmar.

Es la pantalla central: en la planilla de referencia hay alrededor de 30 filas detectadas
más las incompletas. El diseño se apoya en **tres ideas** para que no abrume:

1. **Las decisiones masivas son en la fila; las ediciones son en un diálogo.** En cada fila
   solo hay dos controles que no piden escribir: el **tilde** y el **tipo**. Todo lo demás
   (nombre, monto, pagado, categoría, persona, cuotas) se edita en un diálogo (§4.9),
   igual que en el resto de la app (principio 3 de §0). Así no hay 30 filas con 6 campos de
   texto cada una, y los atajos no chocan con la escritura.
2. **Se agrupa por bloque del Excel.** Cada título de la planilla ("Gasto del Mes", "Deudas",
   "Deudas sofia", "Marsu") arma un grupo plegable con sus filas, en el orden del Excel.
3. **Lo que no se importa se apaga.** Las filas ignoradas o destildadas se ven en color de
   texto secundario (no con transparencia, para mantener el contraste) y el grupo "Filas
   incompletas" viene plegado.

**Flujo paso a paso**

1. Llega desde §3.11. Lo primero que ve: los controles generales (mes destino y categoría
   por defecto), ya con valores propuestos, y la lista con tildes y tipos propuestos.
2. Mira de arriba abajo cada bloque. Lo que está bien, no lo toca.
3. Para cada fila que no quiere o que está mal clasificada: destilda, o cambia el tipo.
4. Para corregir un dato (nombre, monto, categoría, persona, cuota): clic en la fila o en el
   lápiz, se abre el diálogo §4.9, "Aceptar".
5. Mira las filas con aviso (ícono ámbar) y decide. Las filas con error (fondo rojo suave)
   tiene que arreglarlas, ignorarlas o destildarlas.
6. Abre "Filas incompletas" por si hay algo que quiere traer (ej. el sueldo) y lo completa.
7. Cuando el pie dice "Se importan N filas…" sin errores, "Confirmar importación" (§3.13).

**Distribución general**

```
+--------------------------------------------------------------------------------------------+
| Importar desde Excel                                       [Cambiar archivo u hoja]        |
| planilla-prueba.xlsx  ·  Hoja "Octubre"                                                    |
|                                                                                            |
| [!] Hay 1 fórmulas sin valor calculado (ej. D3). Abrí el archivo en Excel, guardalo y     |  <- solo si
|     volvé a importarlo para ver esos montos.                                               |     hay avisos
|                                                                                            |     del archivo
| +----------------------------------------------------------------------------------------+ |
| | Mes destino                        Categoría por defecto                               | |
| | [ Octubre 2026 · mes actual   v ]  [ Varios                v ] [+]                     | |
| | Octubre 2026 ya existe: se        Se usa en los gastos y cuotas que no cambies a       | |
| | agregan los datos, sin borrar     mano. Los gastos quedan sin medio de pago: lo        | |
| | nada de lo que ya tiene.          completás después en Gastos.                         | |
| +----------------------------------------------------------------------------------------+ |
|                                                                                            |
| [ Todas (29) | Se importan (9) | Con avisos (3) | Con errores (0) ]                        |
|                                                                                            |
|  Imp. | Fila | Tipo         | Nombre                | Monto | Pagado/Cobrado | Categ./Persona | Cuota |
|--------------------------------------------------------------------------------------------|
| v GASTO DEL MES · filas 3 a 7 · se importan 4 de 5                           [:]           |
|  [ ]  |   3  | Gasto fijo v | Alquiler              | $ 260.000 |            | Varios     |  -  | [lapiz]
|       |      |              | (!) Ya existe en Octubre 2026. Viene destildada.                       |
|  [x]  |   4  | Gasto fijo v | Servicios             |  $ 82.000 |            | Varios     |  -  | [lapiz]
|  [x]  |   5  | Gasto fijo v | Internet              |  $ 38.700 | $ 38.700   | Varios     |  -  | [lapiz]
|       |      |              |                       |           | Completo   |            |     |
|  [ ]  |   6  | Ignorar    v | Tarjetas de Credito   | $ 582.917 |            |            |  -  | [lapiz]
|  [x]  |   7  | Gasto fijo v | psicologo             | $ 140.000 | $ 60.000   | Varios     |  -  | [lapiz]
|       |      |              |                       |           | Parcial · falta $ 80.000 |     |
|                                                                                            |
| v DEUDAS · filas 12 a 15 · se importan 3 de 3                                [:]           |
|  [x]  |  12  | Gasto fijo v | Monotributo 66.020,12 |  $ 66.020 |            | Varios     |  -  | [lapiz]
|  [x]  |  13  | Cuota      v | Avant Service cuota 3/ 3 $41.116,66 | $ 41.117 |    | Varios     | 3/3 | [lapiz]
|       |      |              | (i) Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026.        |
|  [x]  |  15  | Gasto fijo v | Gym                   |  $ 50.000 |            | Varios     |  -  | [lapiz]
|                                                                                            |
| v DEUDAS SOFIA · filas 22 a 24 · se importan 2 de 3                          [:]           |
|  [x]  |  22  | Me deben   v | Prestamo MP           |  $ 20.000 | [ ] Cobrado| Sofía      |  -  | [lapiz]
|  [x]  |  23  | Me deben   v | Internet              |  $ 12.900 | [ ] Cobrado| Sofía      |  -  | [lapiz]
|       |      |              | (i) ¿Es parte de un gasto compartido? Si es así, ignorala y marcá      |
|       |      |              |     el gasto como compartido después.                                  |
|  [ ]  |  24  | Ignorar    v | Total                 |  $ 32.900 |            |            |  -  | [lapiz]
|                                                                                            |
| v MARSU · filas 27 a 28 · se importan 1 de 2                                 [:]           |
|  ...                                                                                       |
|                                                                                            |
| > FILAS INCOMPLETAS · 16 filas · todas se ignoran, salvo que las completes   (plegado)     |
+--------------------------------------------------------------------------------------------+
| Se importan 9 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben".   [Cancelar] [Confirmar importación] |
+--------------------------------------------------------------------------------------------+
```

La **barra de arriba** (título, archivo, controles generales, filtros, encabezado de columnas)
y el **pie** (estado + botones) quedan **fijos**; solo la lista con los bloques hace scroll.
Así "Cancelar" y "Confirmar importación" nunca se pierden de vista.

#### Controles generales (RF-54, RF-55, RN-73, RN-75)

`ft.Card` con dos columnas (`ft.ResponsiveRow`, cada una `col={"sm": 12, "md": 6}`).

**Mes destino**

| Caso | Control | Textos |
|---|---|---|
| Hay meses (viene de Ajustes) | `ft.Dropdown(label="Mes destino")`. Opciones: todos los meses existentes (del más nuevo al más viejo, con "· mes actual" donde corresponda) y, si se puede crear, un último ítem "Noviembre 2026 · se crea al confirmar" (el siguiente al último, RN-08). Por defecto: el mes actual si existe o se puede crear; si no, el último (RN-73). | Ayuda debajo, según el caso (tabla siguiente). |
| Base sin meses (viene de primer uso) | `ft.Dropdown(label="Mes")` con los 12 meses + `ft.TextField(label="Año", max_length=4)`, valores iniciales los del calendario; igual que §3.1. | Mismos errores de §3.1: "El año tiene que tener 4 dígitos. Ej.: 2026". |

Ayuda debajo del control (`texto_ayuda`, y en *pendiente* con ícono si es una advertencia):

| Situación del mes elegido | Texto |
|---|---|
| Existe y es el último | "Octubre 2026 ya existe: se agregan los datos, sin borrar nada de lo que ya tiene." |
| Existe y hay una fila de sueldo | Se suma una segunda línea: "El sueldo de este mes se reemplaza por el de la fila marcada como sueldo." |
| Existe pero **no** es el último | Aviso *pendiente* con `WARNING_AMBER`: "Los gastos fijos que importes no se agregan a los meses siguientes que ya existen." |
| No existe, es el siguiente al último | "Noviembre 2026 todavía no existe: se crea al confirmar, con los gastos fijos y las cuotas de Octubre 2026, y con su sueldo y su cotización." |
| No existe, base sin meses | "Se crea al confirmar, sin cotización: la cargás después en el Resumen. Si no marcás una fila como sueldo, el sueldo del mes queda en US$ 0,00." |

Cambiar el mes **recalcula** las marcas "ya existe" y los avisos de gasto compartido (RN-73,
RN-74). Como eso cambia tildes sin que el usuario las toque, **siempre** se avisa con un
`SnackBar` de 6 segundos: "Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó. 1 fila
se volvió a tildar." (solo se nombra lo que pasó; si nada cambió, no hay aviso).

**Categoría por defecto (RF-54, RN-75)**

- `ft.Dropdown(label="Categoría por defecto")` con las categorías activas (más las
  categorías nuevas ya agregadas en esta importación, que se ven con el sufijo " (nueva)") y
  `ft.IconButton(ft.Icons.ADD, tooltip="Nueva categoría")` al lado. Viene "Varios" si existe.
- El botón "+" abre debajo, **en la misma pantalla**, la fila `[Nombre de la categoría]
  [Agregar]` (mismo patrón que §4.1; ver §4.11).
- Si no hay "Varios" ni otra elegida: el dropdown queda vacío con `error_text` "Elegí una
  categoría para los gastos y cuotas." y las filas de gasto y cuota sin categoría propia
  muestran el error de la fila (tabla de errores, más abajo).
- Ayuda: "Se usa en los gastos y cuotas que no cambies a mano. Los gastos quedan sin medio de
  pago: lo completás después en Gastos."
- Cambiar la categoría por defecto cambia las filas que no se tocaron; las cambiadas a mano
  conservan la suya (RN-75). Se nota en la fila: la categoría elegida a mano se muestra con
  un punto "•" delante ("• Servicios"), con tooltip "Elegida a mano".

#### Filtro y resumen de la lista

- `ft.SegmentedButton` de un solo valor (mismo componente que el filtro de Cuotas §3.4):
  "Todas (29)" · "Se importan (9)" · "Con avisos (3)" · "Con errores (0)". Por defecto "Todas".
  Cada etiqueta lleva su cantidad.
- "Con errores" aparece con fondo *negativo* suave en cuanto hay alguno, para que no se
  pierda. Los bloques sin filas que cumplan el filtro se ocultan; el grupo "Filas
  incompletas" también.
- No hay buscador: con 30 filas no hace falta.

#### Encabezado de columnas (fijo)

Una sola fila de encabezados arriba de la lista (no se repite en cada bloque), en fondo
superficie variante, texto 13 `W_600`:

| Columna | Ancho | Contenido | Alineación |
|---|---|---|---|
| Imp. | 48 | Tilde "importar" | centro |
| Fila | 48 | Número de fila del Excel (RF-51): "12" (texto 13, secundario). Tooltip "Fila 12 del Excel". | derecha |
| Tipo | 150 | Selector del tipo | izquierda |
| Nombre | flexible (mín. 220) | Nombre + debajo las notas y avisos de la fila | izquierda |
| Monto | 110 | `$ 260.000`; `US$ 1.300,00` si es sueldo | derecha |
| Pagado / Cobrado | 130 | Pagado (gastos y cuotas) o tilde "Cobrado" (me deben) | derecha |
| Categoría / Persona | 150 | Según el tipo | izquierda |
| Cuota | 64 | "3/3" (solo cuotas) | centro |
| (acción) | 48 | Lápiz | – |

Suma mínima fija: 48 + 48 + 150 + 110 + 130 + 150 + 64 + 48 = 748 px + Nombre 220 + márgenes
= **unos 1.000 px**, que entra en la ventana mínima de 1100 (la importación no tiene rail).

#### La fila

Cada fila es un `ft.Container` con un `ft.Row` y, debajo, una columna de notas. **No se usa
`ft.DataTable`** porque las filas llevan controles (tilde, selector) y una segunda línea de
notas de largo variable; un `Row` con anchos fijos da el mismo resultado visual y es más
simple de controlar. Altura mínima 48, crece con las notas.

| Parte | Componente | Detalle |
|---|---|---|
| Imp. | `ft.Checkbox(tooltip="Importar esta fila")` | En filas "ignorar" está **deshabilitado** y sin tilde, con tooltip "Esta fila se ignora. Cambiá el tipo para importarla." Al elegir un tipo distinto de "Ignorar" en una fila ignorada, **se tilda sola**. |
| Tipo | `ft.Dropdown(dense=True, width=150, text_size=14)` | Opciones, en este orden y con estos textos: "Gasto fijo", "Gasto único", "Cuota", "Me deben", "Sueldo (USD)", "Ignorar". |
| Nombre | `ft.Text` 15 | Clic en la fila abre §4.9. Si falta: "(sin nombre)" en texto secundario cursiva. |
| Monto | `ft.Text` 15, derecha | Formato de §2.3. Si falta: "(sin monto)" en secundario. |
| Pagado | `ft.Column` derecha | Línea 1 monto pagado; línea 2 (13): "Completo" con ícono `CHECK` en *positivo*, o "Parcial · falta $ 80.000" en *pendiente*. Vacío si no hay pagado. |
| Cobrado | `ft.Checkbox(label="Cobrado")` | Solo en filas "me deben". Es editable en la fila (no pide escribir). |
| Categoría / Persona | `ft.Text` | Gastos y cuotas: nombre de la categoría. Me deben: nombre de la persona, o "Elegí persona" en *negativo* si falta. Sueldo e ignorar: vacío. |
| Cuota | `ft.Text` | "n/N" solo si el tipo es cuota; si falta, "Falta" en *negativo*. En las demás, "-". |
| Lápiz | `ft.IconButton(ft.Icons.EDIT, tooltip="Editar fila 12")` | Abre §4.9. |

**Qué muestra cada tipo**

| Tipo | Monto | Pagado / Cobrado | Categoría / Persona | Cuota |
|---|---|---|---|---|
| Gasto fijo | ARS | Pagado | Categoría | - |
| Gasto único | ARS | Pagado | Categoría | - |
| Cuota | ARS (monto de la cuota) | Pagado (solo de la cuota del mes destino, RN-71) | Categoría | n/N |
| Me deben | ARS | Tilde Cobrado | Persona | - |
| Sueldo (USD) | **US$ 1.300,00** (cambia de moneda al elegir este tipo) | - | - | - |
| Ignorar | ARS, atenuado | - | - | - |

**Estados visuales de una fila**

| Estado | Cómo se ve |
|---|---|
| Se importa (tildada, tipo ≠ ignorar) | Texto normal. |
| No se importa (destildada o "Ignorar") | Todo el texto en color secundario. **No** se baja la opacidad: se mantiene el contraste 4,5:1 de §2.1. |
| Con aviso | Ícono `WARNING_AMBER` o `INFO_OUTLINE` + texto en la línea de notas. Sin fondo. |
| Con error (bloquea) | Fondo *negativo* suave, borde izquierdo de 4 px en *negativo*, ícono `ERROR_OUTLINE` + texto en *negativo* en la línea de notas. |
| Recién editada | Sin marca especial (no hace falta). |

#### Notas y avisos (segunda línea bajo el nombre)

Texto 13. Una fila puede tener varias, una por línea, en este orden: errores, avisos, info.
Cada una lleva ícono, y el color nunca es la única señal (principio 4).

| Nota | Ícono y color | Texto exacto | ¿Bloquea? |
|---|---|---|---|
| Ya existe (gasto, RN-74) | `WARNING_AMBER`, *pendiente* | "Ya existe en Octubre 2026. Viene destildada." (si el usuario la tildó: "Ya existe en Octubre 2026. Si la importás, queda repetida.") | No |
| Ya existe (plan) | `WARNING_AMBER`, *pendiente* | "Ya existe un plan de cuotas con este nombre. Viene destildada." | No |
| Ya existe (me deben) | `WARNING_AMBER`, *pendiente* | "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada." | No |
| Repetida en el archivo | `CONTENT_COPY`, *pendiente* | "Repetida en el archivo. Si no es un error del Excel, podés importarla igual." | No |
| Posible gasto compartido (RN-72) | `PEOPLE_OUTLINE`, *info* | "¿Es parte de un gasto compartido? Si es así, ignorala y marcá el gasto como compartido después." | No |
| Cobrado no reconocido (RN-64) | `WARNING_AMBER`, *pendiente* | "En la columna Cobrado dice "3.000"; los ítems 'me deben' no tienen cobro parcial, quedó como no cobrado." | No |
| Monto no válido (RN-68) | `WARNING_AMBER`, *pendiente* | "Monto no válido. Si querés importarla, corregí el monto." | No (la fila viene ignorada) |
| Cuota (RN-71) | `INFO_OUTLINE`, *info* | "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. Se agrega la cuota 3/3 en Octubre 2026." | No |
| Sueldo (RN-70) | `INFO_OUTLINE`, *info* | "Sueldo del mes: US$ 1.200,00 -> US$ 1.300,00." (si no cambia: "Sueldo del mes: US$ 1.300,00.") | No |
| Fila incompleta ignorada | `INFO_OUTLINE`, secundario | "Falta el monto. Se ignora." / "Falta el nombre. Se ignora." | No |
| **Error:** falta nombre | `ERROR_OUTLINE`, *negativo* | "Falta el nombre." | Sí |
| **Error:** falta monto | idem | "Falta el monto." / "El monto tiene que ser mayor a 0." | Sí |
| **Error:** sin categoría | idem | "Elegí una categoría." | Sí |
| **Error:** sin persona | idem | "Elegí una persona." | Sí |
| **Error:** cuota incompleta | idem | "Indicá la cuota actual y la cantidad de cuotas." | Sí |
| **Error:** cuota fuera de rango | idem | "La cuota actual tiene que estar entre 1 y la cantidad de cuotas." / "La cantidad de cuotas tiene que ser un número entero de 1 o más." | Sí |
| **Error:** pagado mayor | idem | "El pagado ($ 12.000) es mayor que el monto ($ 10.000)." | Sí |
| **Error:** pagado negativo | idem | "El pagado no puede ser negativo." | Sí |
| **Error:** varios sueldos (RN-70) | idem, en **todas** las filas de sueldo | "Marcaste 2 filas como sueldo; dejá una sola." | Sí |

Los textos de errores son los de `docs/requisitos.md` donde existen y siguen el estilo de §4
("qué está mal y cómo arreglarlo"). El error "varios sueldos" se repite además en el pie.

**Posible gasto compartido: cómo se ve sin molestar.** El aviso largo ocupa dos líneas.
Como es de tipo informativo, lleva `INFO_OUTLINE` y color *info* (no ámbar) para no
competir con los avisos de "ya existe". No se agrega ningún botón: el usuario decide
cambiando el tipo a "Ignorar", y el aviso de las otras filas se recalcula solo.

#### Bloques (RN-65)

Cada bloque es un `ft.ExpansionTile` (plegable) que contiene las filas.

```
v GASTO DEL MES  ·  filas 3 a 7  ·  se importan 4 de 5                     [:]
```

- Título: el texto del título de bloque tal como está en el Excel, en mayúsculas visuales,
  texto 14 `W_600`. Subtítulo 13: "filas 3 a 7 · se importan 4 de 5".
- Todos los bloques de la lista principal vienen **abiertos**. Si el usuario los pliega, el
  subtítulo sigue mostrando "se importan N de M" y, si hay errores, "· 1 con error" en
  *negativo* con ícono (un bloque plegado nunca esconde un error). Un bloque con errores no
  se puede plegar sin que quede esa marca visible.
- Las filas que no cuelgan de ningún título (si las hay) van en un bloque "Otras filas".
- Si el Excel no tiene ningún título, hay un solo bloque, "Filas detectadas", sin plegar.
- El orden de los bloques y de las filas es el del Excel (RF-51).
- Menú `ft.PopupMenuButton` (`MORE_VERT`, tooltip "Acciones del bloque") con:
  - "Tildar todas las filas"
  - "Destildar todas las filas"
  - "Cambiar tipo o categoría de todas..." (abre §4.10)

  Existe porque un título como "Sofía y Marsu" o un bloque sin persona deja 5 o 6 filas
  "me deben" sin persona (RN-65), y arreglarlas una por una sería tedioso.

#### Grupo "Filas incompletas" (RF-51, RN-63)

```
> FILAS INCOMPLETAS  ·  16 filas  ·  todas se ignoran, salvo que las completes
```

- Mismo `ft.ExpansionTile`, **plegado** por defecto, siempre al final de la lista, con fondo
  superficie variante para distinguirlo.
- Dentro, un texto de ayuda: "Son textos sin monto (títulos, encabezados) o montos sin texto
  (totales). Si alguna es un dato que querés traer, por ejemplo el sueldo, completala y
  cambiale el tipo."
- Las filas son iguales a las demás (mismo `Row`, mismos controles), con tipo "Ignorar" y
  notas "Falta el monto. Se ignora." / "Falta el nombre. Se ignora.".
- Se completan con el diálogo §4.9 (campos Nombre y Monto), y se les cambia el tipo con el
  selector. Una fila completada **no se mueve** de este grupo (que las filas salten de lugar
  desorienta); el subtítulo del grupo pasa a "16 filas · se importan 2".
- Se abre sola, sin que el usuario la abra, en dos casos: (1) la hoja no tiene ninguna fila
  con texto y monto (aviso "No se encontraron filas con un texto y un monto."); (2) tiene una
  fila con error.
- Excepción RN-70: una fila "Sueldo (USD)" se puede importar sin nombre. Así, el "1.300" suelto
  de la planilla solo necesita cambiarle el tipo a "Sueldo (USD)".

**Avisos del archivo arriba de la lista** (aviso en pantalla de §2.5, uno por línea, sobre
los controles generales)

| Aviso | Color / ícono | Texto |
|---|---|---|
| Fórmulas sin valor (RN-61) | *pendiente*, `WARNING_AMBER` | "Hay N fórmulas sin valor calculado (ej. D9). Abrí el archivo en Excel, guardalo y volvé a importarlo para ver esos montos." |
| Sin filas completas (RN-60) | *pendiente*, `WARNING_AMBER` | "No se encontraron filas con un texto y un monto." |
| Varios sueldos (RN-70) | *negativo*, `ERROR_OUTLINE` | "Marcaste 2 filas como sueldo; dejá una sola." |

#### Pie fijo: estado y botones

```
+--------------------------------------------------------------------------------------------+
| Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo.           |
|                                                      [ Cancelar ]  [ Confirmar importación ]|
+--------------------------------------------------------------------------------------------+
```

El pie siempre dice **por qué** el botón está habilitado o no (un botón gris sin explicación
es inaccesible):

| Estado | Texto del pie (izquierda) | Botón "Confirmar importación" |
|---|---|---|
| Todo bien | "Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo." (solo lo que hay) | Habilitado (`FilledButton`). Tooltip "Ctrl+Enter". |
| Hay errores | `ERROR_OUTLINE` *negativo*: "Hay 2 filas con errores. Corregilas, ignoralas o destildalas para continuar." (con una sola: "Hay 1 fila con errores. Corregila, ignorala o destildala para continuar.") + `ft.TextButton("Ir al primer error")` | Deshabilitado. Tooltip: "Primero corregí las filas con errores." |
| Dos o más sueldos | "Marcaste 2 filas como sueldo; dejá una sola." | Deshabilitado. |
| Nada para importar | "No hay filas para importar." | Deshabilitado. Tooltip "Tildá al menos una fila." |
| Sin categoría por defecto y hay gastos | Cae en "Hay errores" (cada fila de gasto sin categoría tiene su error). | Deshabilitado. |

"Ir al primer error": desplaza la lista hasta la primera fila con error (`ListView.scroll_to`
con la clave de esa fila), despliega su bloque si estaba plegado y le pone el foco al lápiz.

El texto de conteo se actualiza en cada cambio (tilde, tipo, edición, mes).

#### Cómo se edita en Flet (resumen para quien programa)

- La pantalla guarda en memoria **una lista de objetos "fila de revisión"** (nombre, monto,
  pagado, tipo, tilde, categoría, persona, cuota actual y total, cobrado, notas). Los
  controles solo muestran esa lista; **nada se escribe en la base hasta confirmar** (RF-57).
- Cada fila arma su propio `Row` una vez. Cuando algo cambia, se **actualiza solo esa fila**
  (`fila.control.update()`), más el subtítulo de su bloque, el contador del filtro y el pie.
  No se reconstruye toda la lista: con 60 selectores a la vez se sentiría lenta.
- Cambios que recalculan otras filas (nombre, tipo, tilde o mes destino): se recalculan
  "ya existe", "repetida" y "posible gasto compartido" de todas las filas afectadas
  (RN-72, RN-74) y se redibujan solo las notas de las que cambiaron.
- La lista es un `ft.ListView` con los `ExpansionTile` adentro; el encabezado de columnas y
  el pie quedan fuera del `ListView`, en la `ft.Column` principal.
- Un campo de texto **nunca** está en la lista: solo checkboxes, selectores e íconos. Así,
  Enter/Esc y los atajos no chocan con la escritura (§0, principio 3).

**Teclado en la lista:** Tab recorre, por fila: tilde, tipo, (tilde "Cobrado" si es "me
deben"), lápiz. Espacio marca tildes; flechas abren/cambian el selector. Para no tener que
dar 90 Tab: los filtros, el pliegue de bloques ("Todas / Se importan / Con avisos") y "Ir al
primer error" reducen el recorrido; y `Enter` sobre una fila enfocada (lápiz) abre §4.9.

**Estados de pantalla**

| Situación | Cómo se ve |
|---|---|
| Normal | Como el boceto. |
| Solo filas incompletas | Aviso "No se encontraron filas con un texto y un monto."; no hay bloques; "Filas incompletas" abierto. |
| Filtro sin resultados | Texto centrado: "Ninguna fila coincide con este filtro." con `TextButton("Ver todas")`. |
| Pie con "No hay filas para importar." | Como la tabla del pie. |
| Mes destino con base vacía y año inválido | `error_text` en el campo año y "Confirmar importación" deshabilitado con tooltip "Corregí el mes destino." |

---

### 3.13 Importar Excel: confirmar y resultado (RF-57, RN-76, RN-70, RN-73)

**Objetivo del usuario:** estar seguro de qué se va a guardar antes de guardarlo, y saber qué
pasó después.

**Flujo**

1. En la lista de revisión, "Confirmar importación" (o `Ctrl/Cmd+Enter`).
2. Se abre el diálogo de **resumen previo** (modal, `ft.AlertDialog`).
3. "Importar" → se guarda todo en un solo paso (todo o nada, RN-76).
4. Se abre el diálogo de **resultado**; "Ver Octubre 2026" cierra y muestra el mes.

**Diálogo 1 – Resumen previo**

```
+-----------------------------------------------------------------+
| Revisá antes de importar                                        |
|                                                                 |
| Se va a cargar en Octubre 2026 (ya existe).                     |
|                                                                 |
|  • 5 gastos: $ 376.720 (pagado $ 98.700)                        |
|  • 1 plan de cuotas: Avant Service cuota 3/ 3 $41.116,66        |
|    (cuota 3/3, $ 41.117 por mes)                                |
|  • 3 ítems "me deben": Sofía 2, Marsu 1 ($ 39.685 en total)     |
|  • Sueldo: US$ 1.200,00 -> US$ 1.300,00                         |
|                                                                 |
| Se crean también: la categoría "Importado" y la persona "Juan". |
|                                                                 |
| No se importan 19 filas (ignoradas o destildadas).              |
|                                                                 |
| [i] Esta importación no se puede deshacer. Si algo sale mal,    |
|     lo corregís a mano en la app.                               |
|                                                                 |
|                        [Volver a la revisión] [Importar]        |
+-----------------------------------------------------------------+
```

- Ancho 520. Foco en **"Volver a la revisión"** (confirmación: el foco va a la opción
  segura, §5 de `diseno.md`). Esc = volver.
- `ft.Text` por línea con viñeta; solo se muestran las líneas que tienen algo (sin "0 planes
  de cuotas"). Singular y plural correctos ("1 gasto", "5 gastos").
- Montos con formato de §2.3. Los "$ 376.720" son la suma de los gastos que se importan
  (sin las cuotas, que se muestran aparte); "pagado" aparece solo si hay pagos.
- Primera línea según el mes: "Se va a cargar en Octubre 2026 (ya existe)." / "Se va a crear
  Noviembre 2026 y cargar ahí los datos." / (primer uso) "Se va a crear Octubre 2026, sin
  cotización, y cargar ahí los datos."
- Línea de sueldo solo si hay una fila de sueldo. Con mes nuevo de primer uso y sin fila de
  sueldo: línea *pendiente* "Sin sueldo: el sueldo de Octubre 2026 queda en US$ 0,00."
- "Se crean también": solo categorías y personas nuevas que **se usan** en alguna fila que
  se importa (ver observación 26).
- Aviso *info* final con el texto de "sin deshacer".
- Botones: `ft.TextButton("Volver a la revisión")` y `ft.FilledButton("Importar")`. El texto
  del segundo es "Importar" (y no "Confirmar") para repetir la acción que está pasando.

**Mientras guarda:** el diálogo muestra un `ft.ProgressRing` y los botones se deshabilitan
(es un instante, pero evita un doble clic).

**Diálogo 2 – Resultado exitoso**

```
+-----------------------------------------------------------------+
| [check verde] Importación terminada                             |
|                                                                 |
| Se importaron: 5 gastos, 1 plan de cuotas, 3 ítems "me deben"   |
| y el sueldo (US$ 1.300,00) en Octubre 2026.                     |
|                                                                 |
| Para completar:                                                 |
|  • Los gastos quedaron sin medio de pago. Podés ponérselo en    |
|    Gastos.                                                      |
|  • Si alguno es compartido, marcalo desde el gasto.             |
|  • Cargá la cotización de Octubre 2026 en el Resumen.           |
|                                                                 |
|                                     [ Ver Octubre 2026 ]        |
+-----------------------------------------------------------------+
```

- El primer párrafo es el texto de RN-76: "Se importaron: N gastos, N planes de cuotas, N ítems
  'me deben' y el sueldo (X USD) en Octubre 2026.", **mencionando solo lo que hubo**. Aquí
  el sueldo se muestra "US$ 1.300,00" (moneda visible, §2.3).
- Se usa un **diálogo** y no un `SnackBar` porque el mensaje es largo, importante y
  convendría poder releerlo; el SnackBar se va a los 4 segundos.
- "Para completar": cada línea aparece solo si corresponde (la primera si hubo gastos o
  cuotas; la segunda si hubo gastos "me deben" o gastos; la tercera solo si el mes se creó
  sin cotización). Texto 13, secundario.
- **No hay botón "Deshacer"** (CA-57.2).
- Un solo botón, `ft.FilledButton("Ver Octubre 2026")`, con foco y Enter. Al cerrarlo, la app
  selecciona el mes destino, **muestra la pantalla Gastos** (lo importado es mayormente
  gastos) y refresca todo (RN-19). Si solo se importaron "me deben" y/o sueldo, muestra
  Resumen.
- Desde el primer uso, "Ver Octubre 2026" arma la ventana principal (rail y barra) con ese
  mes seleccionado, como "Crear mes" en §3.1.

**Diálogo 3 – Error al guardar (RN-76, CA-57.4)**

Es el "Error inesperado" de §2.5, con el texto de la requisito:

> **No se pudo importar**
> No se pudo importar. No se guardó ningún dato.
> (detalle técnico en texto chico, para copiarlo)
> [Volver a la revisión]

La revisión **se conserva** tal cual estaba, para poder reintentar o cancelar. El título del
diálogo es "No se pudo importar" y el cuerpo repite la frase del requisito; así se lee igual
en el lector de pantalla y en el diálogo.

---

### 3.14 Importar Excel: cancelar y salir (RF-57, RN-76, CA-57.3)

**Cancelar** significa descartar todo: no se guarda ningún gasto, pago, plan, ítem, mes
nuevo, persona ni categoría nueva.

| Dónde | Qué hace |
|---|---|
| Botón "Cancelar" (pie de la revisión, y tarjeta de §3.11) | Si **no hubo cambios** del usuario: vuelve directo. Si **hubo**: confirmación (abajo). |
| `Esc` con la pantalla de importación en foco | Igual que "Cancelar". |
| "Cambiar archivo u hoja" (encabezado de la revisión) | Si hubo cambios: misma confirmación, con otro título (abajo). Si no: vuelve al paso de §3.11. |
| Cerrar la ventana de la app durante la revisión | Cierra sin preguntar (decidido por el usuario, observación 31): no se intercepta el cierre de la ventana. No se pierde nada guardado, solo la revisión en curso. |

**Qué cuenta como "cambios del usuario"** (RN-76): cambiar un tipo, un tilde, un dato de una
fila, la categoría por defecto, el mes destino o agregar una categoría o persona nueva.
Las marcas automáticas (tipos propuestos, "ya existe") no cuentan.

**Confirmación – cancelar**

> **¿Descartar la importación?**
> Se pierden los cambios que hiciste en la revisión. No se guarda nada.
> [Seguir revisando] [Descartar]

- Foco en "Seguir revisando". "Descartar" es `boton_peligroso` (fondo *negativo*).
- Si hay categorías o personas nuevas sin usar o usadas, el texto agrega: "También se
  descartan las categorías y personas nuevas: Importado, Juan."

**Confirmación – cambiar archivo u hoja**

> **¿Volver a elegir el archivo?**
> Se pierden los cambios que hiciste en la revisión.
> [Seguir revisando] [Volver a elegir]

**Destino al cancelar:** desde el primer uso, vuelve al formulario de §3.1; desde Ajustes, a la pestaña "Importar Excel". En ambos casos sin mensaje extra.

---

## 4. Diálogos y formularios

Mensajes comunes a todos los montos (RN-04, RN-05):

| Caso | Mensaje |
|---|---|
| Vacío | "Ingresá un monto." |
| No numérico | "Escribí solo números. Ej.: 66.020,12" |
| Punto como decimal | "Usá coma para los decimales. Ej.: 66.020,12" |
| Más de 2 decimales | "Usá como máximo 2 decimales." |
| Cero o negativo | "El monto tiene que ser mayor a 0." |

### 4.1 Gasto (alta y edición) – RF-06, RF-07, RF-29, RF-30, RF-31, gastos en dólares

**En pesos (por defecto)**

```
+------------------------------------------------------------+
| Nuevo gasto – Octubre 2026          (o "Editar gasto")     |
|                                                            |
| Nombre          [ Internet                         ]       |
| Categoría       [ Servicios                     v ] [+]    |
| Moneda          ( Pesos (ARS) | Dólares (USD) )            |
| Monto           [ $                38.700   ARS ]          |
| Tipo            ( Fijo mensual | Pago único )              |
|                 Los fijos se copian al mes siguiente.      |
| Medio de pago   [ Visa Santander                v ]        |
|                                                            |
| Compartido      [on]                                       |
|   [x] Sofía   [x] Marsu                                    |
|   +-------------------------------------------------+      |
|   | Sofía        [ $  15.000 ]  manual              |      |
|   | Marsu        [ $  12.900 ]                      |      |
|   | Tu parte        $ 10.800                        |      |
|   +-------------------------------------------------+      |
|   [Repartir en partes iguales]                             |
|                                                            |
|                                 [Cancelar] [Guardar]       |
+------------------------------------------------------------+
```

**En dólares** (mismo diálogo; solo cambia el bloque de monto)

```
+------------------------------------------------------------+
| Nuevo gasto – Octubre 2026                                 |
|                                                            |
| Nombre          [ Claude                           ]       |
| Categoría       [ Trabajo                       v ] [+]    |
| Moneda          ( Pesos (ARS) | Dólares (USD) )            |
|                                  ^^^^^^^^^^^^^ elegido     |
| Monto en dólares   [ US$             20,00   USD ]         |
| Cotización del día [ $             1.600     ARS ] por US$ |
|                    Escribí la cotización que te cobran     |
|                    (oficial, tarjeta o MEP). La app no     |
|                    suma impuestos.                         |
| +--------------------------------------------------------+ |
| | US$ 20,00 × $ 1.600 = $ 32.000 a pagar                 | |
| | Los pesos quedan fijos con esta cotización.            | |
| +--------------------------------------------------------+ |
| Tipo            ( Fijo mensual | Pago único )              |
|                 Los fijos se copian al mes siguiente con   |
|                 los mismos dólares y la cotización del     |
|                 mes nuevo.                                 |
| Medio de pago   [ Visa Santander                v ]        |
|                                                            |
| Compartido      [off]                                      |
|                                                            |
|                                 [Cancelar] [Guardar]       |
+------------------------------------------------------------+
```

**Por qué el selector de moneda va antes del monto:** el usuario decide primero "en qué me
cobran" y después escribe el número; el campo que aparece justo debajo ya tiene el prefijo
correcto (`$` o `US$`), así no hay forma de escribir dólares en un campo de pesos.

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Nombre | `ft.TextField(autofocus=True, max_length=60)` | Vacío: "Ingresá un nombre." |
| Categoría | `ft.Dropdown` con categorías no archivadas + `ft.IconButton(ADD, tooltip="Nueva categoría")` | Sin elegir: "Elegí una categoría." El botón "+" muestra **dentro del mismo diálogo** una fila `[Nombre de la categoría] [Agregar]` (no abre otro diálogo). Si no hay ninguna categoría, la fila aparece abierta con el texto "Todavía no tenés categorías. Creá la primera." |
| Moneda | `ft.SegmentedButton` con `ft.Segment(value="ARS", label=ft.Text("Pesos (ARS)"))` y `ft.Segment(value="USD", label=ft.Text("Dólares (USD)"))`; `selected=["ARS"]`, `allow_multiple_selection=False`, `allow_empty_selection=False`, `on_change` muestra/oculta los bloques. | Siempre hay una elegida. No se muestra en gastos de cuota (los planes son solo en pesos). |
| **Bloque pesos** (visible con ARS) | | |
| Monto | Campo de monto ARS (§2.4), `label="Monto"` | Mensajes comunes + RN-23 en edición: "No podés bajar el monto a menos de lo que ya pagaste ($ 60.000)." |
| **Bloque dólares** (visible con USD) | `ft.Column` con los 3 elementos siguientes | |
| Monto en dólares | Campo de monto USD (§2.4): `label="Monto en dólares"`, `prefix_text="US$ "`, `suffix_text="USD"`, `hint_text="Ej.: 20,00"` | Vacío: "Ingresá el monto en dólares." Cero o negativo: "El monto tiene que ser mayor a 0." Resto: mensajes comunes. |
| Cotización del día | Campo de monto ARS: `label="Cotización del día"`, `prefix_text="$ "`, `suffix_text="por US$"`, `helper_text="Escribí la cotización que te cobran (oficial, tarjeta o MEP). La app no suma impuestos."` Alta: precargada con la cotización del mes; si el mes no tiene, vacía y `helper_text="Este mes no tiene cotización: escribí la del día."` | Vacía: "Ingresá la cotización del día." Cero o negativa: "La cotización tiene que ser mayor a 0." Resto: mensajes comunes. |
| Resultado | `ft.Container` color *info* suave, `border_radius=8`, con `ft.Text` 18 `W_600`: "US$ 20,00 × $ 1.600 = $ 32.000 a pagar" y debajo, texto 13: "Los pesos quedan fijos con esta cotización." Se recalcula en el `on_change` de los dos campos (en cada tecla). | Si falta un dato o no es válido todavía: texto secundario "Completá el monto y la cotización para ver cuántos pesos vas a pagar." (sin color de error mientras escribe; los errores aparecen al guardar). |
| Tipo | `ft.SegmentedButton` con "Fijo mensual" y "Pago único" (por defecto Fijo) | Ayuda debajo según la moneda: ARS "Los fijos se copian al mes siguiente."; USD "Los fijos se copian al mes siguiente con los mismos dólares y la cotización del mes nuevo." |
| Medio de pago | `ft.Dropdown` con "Sin medio de pago" como primera opción + medios no archivados | Opcional. |
| Compartido | `ft.Switch` | Se habilita desde el paso 5. Funciona igual en ARS y USD: las partes son **en pesos**, sobre el monto en pesos (el resultado de la conversión). |
| Personas | `ft.Checkbox` por persona no archivada | Con el switch activo y ninguna tildada: "Elegí al menos una persona o desactivá Compartido." |
| Parte de cada persona | Campo de monto ARS chico (ancho 160) + etiqueta "manual" si fue editada | Mensajes comunes, pero acepta 0 (el modelo permite ≥ 0). Si "Tu parte" queda negativa (RN-33): "Las partes suman $ 42.900 y superan el monto ($ 38.700)." en *negativo* debajo de la tabla. |
| Tu parte | `ft.Text` (solo lectura), se recalcula en cada tecla (`on_change`) | – |

**Cálculo del resultado en pesos.** Es el mismo cálculo que los ARS sugeridos de un cambio
(RN-13): `usd_cent × cotización_cent ÷ 100`, redondeado al centavo según RN-03, y se muestra
sin decimales (RN-04). Ej.: US$ 12,99 × $ 1.432,50 = 18.608,175 → se guarda 18.608,18 y se ve
"$ 18.608". La función que calcula está en la lógica; la interfaz solo la llama en cada tecla.

**Cambiar de moneda con datos ya escritos**

- Cada bloque **conserva lo que se escribió** mientras el diálogo está abierto. Ej.: escribió
  38.700 en pesos, pasa a dólares, vuelve a pesos: sigue el 38.700. Ocultar y mostrar con
  `visible` lo resuelve sin código extra.
- **No se convierte** automáticamente un monto de una moneda a otra (si escribió 20 en pesos
  y se dio cuenta de que eran dólares, el 20 no se transforma en $ 32.000). Al pasar a una
  moneda cuyo campo está vacío, el foco va a ese campo.
- Al guardar **solo cuenta el bloque visible**; lo escrito en el otro se descarta y no se
  valida.
- Las validaciones del bloque oculto se limpian al cambiar de moneda (no quedan errores
  rojos escondidos).

**Validaciones al guardar en USD (orden en que se muestran)**

1. Nombre y categoría (igual que en pesos).
2. Monto en dólares: vacío → "Ingresá el monto en dólares."; ≤ 0 → "El monto tiene que ser
   mayor a 0."; formato → mensajes comunes.
3. Cotización del día: vacía → "Ingresá la cotización del día."; ≤ 0 → "La cotización tiene
   que ser mayor a 0."; formato → mensajes comunes.
4. En edición, RN-23 sobre el resultado en pesos: si queda por debajo de lo pagado, el error
   va en el recuadro de resultado (en *negativo*): "Con estos valores el gasto queda en
   $ 30.000, menos de lo que ya pagaste ($ 32.000). Subí el monto o la cotización."
5. Compartido: si con el nuevo resultado en pesos "Tu parte" queda negativa, el mismo mensaje
   de RN-34 que en pesos.

**Edición de un gasto en dólares**

- Se abre con **"Dólares (USD)" seleccionado**, el monto en dólares y la **cotización del día
  que se guardó en ese gasto** (no la del mes). El resultado muestra los pesos actuales.
- Si la cotización guardada es distinta de la del mes, debajo del campo aparece un
  `ft.TextButton("Usar la del mes ($ 1.650)")` que reemplaza el valor del campo. Así es fácil
  actualizarla sin escribir.
- Cambiar el monto en dólares o la cotización recalcula el resultado al instante; al guardar,
  los pesos del gasto pasan a ser el nuevo resultado (decisión aprobada). Si el gasto tiene
  pagos, se aplica RN-23 (punto 4 de arriba).
- **Pasar un gasto en dólares a pesos:** al elegir "Pesos (ARS)" el campo "Monto" viene
  precargado con los pesos actuales del gasto (ej. 32.000), y aparece el aviso *info*: "Al
  guardar en pesos, el gasto deja de guardar los dólares y la cotización." Precargar acá sí
  tiene sentido porque esos pesos son el monto real que tenía el gasto.
- **Pasar un gasto en pesos a dólares:** el bloque de dólares aparece con el monto vacío y la
  cotización del mes precargada, igual que en un alta.

**Edición: otros casos especiales**

- **Categoría, medio o persona archivados ya asignados al gasto:** se muestran en el
  `Dropdown` con el sufijo "(archivada)" para no obligar a cambiarlos al editar otro campo.
  No se ofrecen en un alta (RN-49, CA-06.5).
- **Gasto de una cuota:** en lugar de los selectores de moneda y tipo se muestra el texto fijo
  "Cuota 3/6 de Préstamo X (en pesos)" con un enlace "Editar el plan". Los demás campos se
  pueden editar y el cambio vale **solo para este mes** (RN-11); se avisa: "Este cambio vale
  solo para Octubre 2026. Para cambiar todas las cuotas, editá el plan."
- **Cambio de monto en un gasto compartido (RN-34):** mientras se escribe el monto nuevo (o,
  en dólares, el monto o la cotización), la tabla de partes muestra los valores recalculados.
  Si una parte ya cobrada cambia, debajo aparece en *pendiente*: "La parte de Sofía ya estaba
  cobrada ($ 12.900). Va a quedar pendiente: falta $ 2.100." (o "a devolver $ 2.900"). Si "Tu
  parte" quedaría negativa, se rechaza: "Con este monto tu parte quedaría en -$ 1.667. Subí el
  monto o bajá las partes manuales."
- Título: "Editar gasto – Octubre 2026"; en edición, botón extra a la izquierda
  `ft.TextButton("Borrar", color=negativo)`.

**Teclado en el diálogo:** el orden de Tab sigue el orden visual (Nombre → Categoría →
Moneda → Monto o Monto en dólares → Cotización del día → Tipo → Medio → Compartido). En el
`SegmentedButton` se cambia de opción con las flechas o Espacio. Enter en cualquier campo
guarda.

### 4.2 Plan de cuotas – RF-16, RF-19

Los planes son **solo en pesos**: este diálogo no tiene selector de moneda. Junto al campo del
monto, texto de ayuda: "Las cuotas se cargan en pesos."

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Nombre | `ft.TextField` | "Ingresá un nombre." |
| Categoría | `ft.Dropdown` (+ creación en línea como §4.1) | "Elegí una categoría." |
| Medio de pago | `ft.Dropdown` (opcional) | – |
| Monto de la cuota | Campo de monto ARS | Mensajes comunes. |
| Cantidad de cuotas | `ft.TextField(keyboard_type=NUMBER, input_filter=solo dígitos, width=120)` | "La cantidad de cuotas tiene que ser un número entero mayor o igual a 1." |
| Primera cuota | `ft.Dropdown` de mes + `ft.TextField` de año (4 dígitos) | "El año tiene que tener 4 dígitos." Puede ser un mes pasado (RN-29): no se valida contra el presente. |
| Vista previa | `ft.Container` *info* | "Última cuota: Octubre 2026 · Total del plan: $ 123.350 · En Octubre 2026 (mes actual) va la cuota 3/3" o "…todavía no empezó". |

### 4.3 Registrar pago – RF-14

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Resumen del gasto | `ft.Text` | "Seguro de moto · Monto $ 180.000 · Pagado $ 60.000 · Pendiente $ 120.000". Si el gasto es en dólares, debajo en texto secundario: "Gasto en dólares: US$ 20,00 × $ 1.600". |
| Monto del pago | Campo de monto ARS + `ft.TextButton("Pagar todo lo pendiente")` | Mensajes comunes. Mayor al pendiente (RN-21): "El pago no puede superar lo pendiente ($ 120.000)." |
| Fecha | `ft.TextField` (solo lectura, "04/10/2026") + `ft.IconButton(CALENDAR_MONTH)` que abre `ft.DatePicker` | Por defecto hoy. |

### 4.4 Ver pagos – RF-15

Lista de los pagos (`ft.Column` de filas): fecha · monto · `ft.IconButton(DELETE_OUTLINE,
tooltip="Borrar este pago")`. Al pie: "Pagado $ 110.000 · Pendiente $ 70.000". Botón
"Registrar otro pago" y "Cerrar". Sin pagos: "Todavía no hay pagos registrados."

### 4.5 Ingreso extra – RF-24

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Descripción | `ft.TextField` | "Ingresá una descripción." |
| Moneda | `ft.SegmentedButton` "Pesos (ARS)" / "Dólares (USD)" (por defecto ARS), igual que en §4.1. Al cambiar, el campo monto cambia `prefix_text` y `suffix_text`. | Siempre hay una elegida (CA-24.3 no puede darse desde la interfaz; la lógica igual valida). |
| Monto | Campo de monto en la moneda elegida | Mensajes comunes. |

### 4.6 Cambio de USD realizado – RF-26

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Fecha | Como en §4.3 | – |
| USD cambiados | Campo de monto USD | Mensajes comunes. |
| Cotización del cambio | Campo de monto ARS, precargado con la cotización del mes | "La cotización tiene que ser mayor a 0." |
| ARS recibidos | Campo de monto ARS, se completa solo (RN-13) | Mensajes comunes. Etiqueta "Corregido a mano" + botón "Volver a calcular" cuando difiere del producto. |

### 4.7 Persona / categoría / medio de pago – RF-10, RF-11, RF-28

Un solo campo "Nombre". Mensajes de §3.10.

### 4.8 Ítem "me deben" – RF-32

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Persona | `ft.Dropdown` (personas no archivadas), precargado si se abrió desde su tarjeta | "Elegí una persona." |
| Descripción | `ft.TextField` | "Ingresá una descripción." |
| Monto | Campo de monto ARS | Mensajes comunes. |
| Fecha | Como en §4.3, por defecto hoy | – |

### 4.9 Editar fila de la importación – RF-53

Se abre con clic en la fila o en el lápiz. Modal, ancho 480, con `dialogo_formulario`
(el mismo que usan los demás diálogos), título "Editar fila 12 del Excel". Los botones son
**"Cancelar"** y **"Aceptar"** (no "Guardar", porque no se guarda nada todavía). A la
izquierda, `ft.TextButton("Volver a lo detectado")`: restaura nombre, monto, pagado, tipo y
tilde a lo que leyó la app.

Foco inicial: el primer campo que tenga error; si no hay, "Nombre".

| Campo | Componente | Cuándo se ve | Validación y mensajes |
|---|---|---|---|
| Tipo | `ft.Dropdown` con los 6 tipos de §3.12 | Siempre | – |
| Nombre | `ft.TextField` (autofocus) | Siempre; opcional si el tipo es "Sueldo (USD)" o "Ignorar" | "Ingresá un nombre." |
| Monto | `campo_monto("Monto", "ARS")`; para sueldo `campo_monto("Sueldo", "USD")` | Siempre | Mensajes comunes de §4. "El monto tiene que ser mayor a 0." |
| Pagado | `campo_monto("Pagado (opcional)", "ARS")` + ayuda "Lo que ya pagaste. Si es igual al monto, queda pagado completo." | Gasto fijo, gasto único y cuota | "El pagado ($ 12.000) es mayor que el monto ($ 10.000)." / "El pagado no puede ser negativo." Vacío o 0: sin pagos. |
| Categoría | `ft.Dropdown` + `IconButton(ADD, tooltip="Nueva categoría")` + fila en línea (§4.11). Primera opción: "Categoría por defecto (Varios)". | Gasto fijo, gasto único y cuota | "Elegí una categoría." |
| Cuota actual y Cantidad de cuotas | Dos `ft.TextField` de números enteros (`input_filter` solo dígitos), en una fila, con la ayuda "Ej.: cuota 3 de 12" | Solo cuota | "Indicá la cuota actual y la cantidad de cuotas." / "La cuota actual tiene que estar entre 1 y la cantidad de cuotas." / "La cantidad de cuotas tiene que ser un número entero de 1 o más." |
| Vista previa del plan | `texto_ayuda` en recuadro *info* | Solo cuota con datos válidos | "Plan de 3 cuotas: primera Agosto 2026, última Octubre 2026. Se agrega la cuota 3/3 en Octubre 2026." (se actualiza en cada tecla; usa el mes destino) |
| Persona | `ft.Dropdown` (personas activas y las nuevas ya agregadas) + `IconButton(ADD, tooltip="Nueva persona")` + fila en línea (§4.11) | Solo me deben | "Elegí una persona." |
| Cobrado | `ft.Switch(label="Ya me lo pagaron (cobrado)")` | Solo me deben | – |

- Mostrar y ocultar los bloques según el tipo con `visible`, **conservando lo escrito** en
  cada uno (igual que el selector de moneda de §4.1).
- Al cambiar de tipo dentro del diálogo, si el tipo anterior era "Ignorar", la fila se tilda
  sola al aceptar (misma regla que en la lista).
- Cuando "Aceptar" valida, los errores van debajo de cada campo (como en §2.5) y el diálogo
  no se cierra. Si el usuario deja la fila con errores y acepta, **se permite solo si el
  tipo es "Ignorar"**; con otro tipo, el diálogo no se cierra hasta que esté todo válido
  (así la lista no queda con errores creados por el diálogo; los errores de la lista son
  los que vienen del Excel).
- En una fila de **sueldo**, debajo del monto: "Hoy el sueldo de Octubre 2026 es US$ 1.200,00."
  (si el mes no existe: "Octubre 2026 todavía no existe.").

### 4.10 Cambiar tipo o categoría de todas las filas de un bloque – RF-52, RF-53

Desde el menú del bloque, "Cambiar tipo o categoría de todas...". Diálogo chico (ancho 420),
título "Cambiar las filas de Deudas sofia".

Con "No cambiar el tipo" se muestran los dos campos de abajo: la categoría se aplica a las
filas de gasto o cuota del bloque y la persona a las filas "me deben"; un campo que se deja
sin elegir no cambia nada.

| Campo | Componente | Detalle |
|---|---|---|
| Tipo | `ft.Dropdown` con "No cambiar el tipo" (primera opción, elegida al abrir) y los 6 tipos | Con "No cambiar el tipo" se aplica solo la categoría o la persona: es la forma de **cambiar la categoría de todas las filas** de un bloque en un solo paso (observación 29). |
| Persona | `ft.Dropdown` + `+` (§4.11) | Con tipo "Me deben": obligatoria ("Elegí una persona."). Con "No cambiar el tipo": opcional, se aplica a las filas "me deben" del bloque. |
| Categoría | `ft.Dropdown` + `+` | Solo si el tipo es gasto fijo, gasto único o cuota. Primera opción "Categoría por defecto (Varios)". |

Texto de ayuda fijo: "Se cambian las 5 filas de este bloque. Después podés ajustar cada
una." Botones **"Cancelar"** y **"Aplicar a las 5 filas"**. Excepciones:

- Las filas que ya están **ignoradas por una regla** (por ejemplo "Total") también cambian;
  el usuario eligió "todas". Para no hacerlo sin querer, el texto de ayuda lo dice así:
  "Se cambian las 5 filas de este bloque, incluidas las que están ignoradas."
- "Cuota" no está disponible acá (cada cuota necesita su n/N): la opción se muestra
  deshabilitada con el tooltip "La cuota se elige fila por fila."
- "Sueldo (USD)" tampoco (solo puede haber una): deshabilitada con "Solo una fila puede ser
  el sueldo."

### 4.11 Crear categoría o persona nueva desde la revisión – RF-53, RF-54, RN-72, RN-75

**Dónde aparece el "+":** al lado de (1) el dropdown de categoría por defecto de la lista,
(2) el dropdown de categoría de §4.9 y §4.10 y (3) el dropdown de persona de §4.9 y §4.10.

**Patrón:** el mismo de §4.1 ("dentro del mismo diálogo, no se abre otro encima"). Al tocar
`IconButton(ft.Icons.ADD, tooltip="Nueva categoría")` o `tooltip="Nueva persona"`, aparece
debajo del dropdown una fila:

```
[ Nombre de la categoría________________ ] [ Agregar ]
[ Cancelar ]
```

`ft.Row` con `ft.TextField(label="Nombre de la categoría" / "Nombre de la persona",
autofocus=True, on_submit=agregar)`, `ft.TextButton("Agregar")` y `ft.TextButton("Cancelar")`.
Enter agrega, Esc cierra solo esa fila (no el diálogo).

**Qué hace "Agregar" (diferencia clave con §4.1):** **no escribe en la base.** Agrega el
nombre a una lista temporal de la importación, lo muestra en los dropdowns con el sufijo
**" (nueva)"** y lo deja elegido. Debajo de la fila, texto de ayuda: "Se crea al confirmar la
importación. Si cancelás, no se crea." Se puede elegir en las demás filas mientras dure la
revisión (RN-72).

**Validaciones** (RN-50, mensajes de §3.10, comparando según RN-67: sin mayúsculas ni
acentos):

| Caso | Mensaje (`error` del campo) |
|---|---|
| Vacío | "Ingresá un nombre." |
| Ya existe (activa) | "Ya existe una categoría llamada "Salud"." / "Ya existe una persona llamada "Sofía"." |
| Ya existe archivada | "Ya existe una categoría llamada "Salud" (está archivada). Podés desarchivarla en Ajustes." |
| Ya agregada en esta importación | "Ya agregaste una persona llamada "Juan" en esta importación." |

El caso de CA-53.4 ("sofía" se rechaza) se cubre con la comparación sin acentos.

**Lista de nuevos visible.** Debajo del pie de la lista, no se muestra nada aparte, para no
ocupar lugar. Se ven en: los dropdowns (con "(nueva)"), el resumen previo (§3.13, "Se crean
también…") y la confirmación de cancelar (§3.14).

---

## 5. Accesibilidad (resumen)

- **Contraste:** todos los pares de color de §2.1 cumplen 4,5:1 o más, en ambos temas.
- **Tamaños:** texto base 15, mínimo 13; filas de tabla de 48 px de alto (hasta 64 con
  dos líneas); botones e íconos clickeables de al menos 40 × 40 px (tamaño por defecto de
  `IconButton`).
- **No solo color:** cada estado tiene texto o ícono ("Pagado", "Parcial", "Déficit", "Sin
  capacidad de endeudamiento", "a devolver", "Archivada"). Los gastos en dólares se
  reconocen por el texto "US$", no por un color.
- **Teclado:** todo se puede hacer con teclado: Tab recorre los controles en orden visual,
  Espacio marca tildes y elige opciones de los selectores, Enter guarda, Esc cancela, atajos
  de §1.3. En cada diálogo el foco arranca en el primer campo; en las confirmaciones, en
  "Cancelar".
- **Lectores de pantalla:** todos los `IconButton` tienen `tooltip`; los gráficos tienen su
  versión en tabla; la celda de monto de un gasto en dólares tiene tooltip con la cuenta
  completa.
- **Etiquetas siempre visibles:** el rail muestra texto bajo cada ícono; los campos usan
  `label` (no solo `hint_text`, que desaparece al escribir). Los segmentos de moneda dicen
  "Pesos (ARS)" y "Dólares (USD)", no solo un símbolo.
- **Errores claros:** cada mensaje dice qué está mal y cómo arreglarlo, en español y sin
  términos técnicos.

### Importar Excel (v2)

- **Contraste:** las filas apagadas usan el texto secundario de §2.1 (≥ 4,5:1 en ambos
  temas), **no** `opacity`. El fondo de error es el *negativo suave* de §2.1.
- **No solo color:** errores = ícono `ERROR_OUTLINE` + texto; avisos = `WARNING_AMBER` o
  `INFO_OUTLINE` + texto; "se importa" = tilde; "no se importa" = tilde vacío + texto
  secundario + tipo "Ignorar" o tilde deshabilitado con tooltip.
- **Tamaños:** texto de filas 15; notas 13 (no menos); íconos y checkboxes de 40 x 40 como
  mínimo para clic; el lápiz tiene tooltip "Editar fila 12".
- **Teclado:** todo se puede hacer sin mouse. Orden de Tab por fila: tilde, tipo, (cobrado),
  lápiz. Atajos de §1.3: `Esc` cancelar, `Ctrl/Cmd+Enter` confirmar. El pie lleva "Ir al
  primer error" para no recorrer toda la lista. En los diálogos de confirmación el foco
  arranca en la opción segura ("Seguir revisando", "Volver a la revisión").
- **Lectores de pantalla:** el checkbox "Importar esta fila" lleva el nombre y número de fila
  en el tooltip ("Importar fila 12: Monotributo"); cada fila con error expone el texto del
  error; el contador del pie se actualiza como texto normal (no solo con color).
- **Lenguaje:** los mensajes dicen qué está mal y cómo arreglarlo, sin términos técnicos
  ("fórmulas sin valor calculado" lleva su instrucción para resolverlo).

### Cotización automática (v2)

- **Contraste:** error, origen, ruedita y botón usan los pares de §2.1 en ambos temas
  (≥ 4,5:1); detalle por tema en §3.6. El campo bloqueado mientras busca es de **solo
  lectura, no deshabilitado**, para conservar el contraste normal del valor (observación 34).
- **No solo color ni solo ícono:** buscando = ruedita **y** el texto "Buscando la
  cotización…"; error = ícono `ERROR_OUTLINE` **y** el mensaje; origen = ícono `INFO_OUTLINE`
  **y** el texto con dólar, fecha y hora. El botón deshabilitado no es la única señal de que
  hay una búsqueda en curso.
- **Tamaños:** botón de 40 px de alto como mínimo; textos de ayuda, estado, origen y error en
  13 (nunca menos).
- **Teclado:** todo con teclado. Orden de Tab: campo, "Buscar dólar …", "Cancelar",
  "Guardar". `Enter` en el campo guarda, `Esc` cancela, también durante la búsqueda. Al
  terminar la búsqueda el foco va al campo (si salió bien) o al botón de buscar (si falló),
  salvo que el usuario ya lo haya movido. En Ajustes, el grupo de opciones se recorre con
  flechas y Espacio.
- **Lectores de pantalla:** la ruedita lleva `semantics_label` ("Buscando la cotización"); el
  mensaje de error y el origen son texto normal, y el contenedor del error se marca como
  región "en vivo" si Flet 1.0.3 lo permite (verificarlo), para que se lea al aparecer.
- **Lenguaje:** el error dice qué pasó y qué hacer ("Revisá tu conexión o cargala a mano"),
  sin códigos ni términos como "HTTP" o "JSON".

---

## 6. Orden de implementación (alineado con requisitos.md §9)

Cada paso deja la app **usable y probable**. Lo que no está construido todavía no se muestra
(no hay botones deshabilitados "para después").

### Paso 1 – Base de datos + ABM de gastos de un mes

Pantallas y partes que se construyen:

- **Estructura de la ventana** (§1.1) con `NavigationRail` de **2 destinos**: Gastos y Ajustes.
- **Barra superior mínima:** solo el nombre del mes ("Octubre 2026") como texto. Sin selector,
  sin mes nuevo, sin cotización.
- **Primer uso** (§3.1) completo (pide sueldo y cotización aunque todavía no se muestren en
  otro lado; quedan guardados para el paso 3; la cotización ya se usa en el paso 1c).
- **Gastos** (§3.3) con columnas **Nombre, Categoría, Tipo, Medio de pago, Monto** y el menú
  con **Editar** y **Borrar**. Fila de totales solo con **Total gastos**. Estado vacío.
- **Diálogo de gasto** (§4.1) en pesos, sin selector de moneda y sin la sección Compartido;
  con creación de categoría en línea.
- **Confirmación de borrado** de gasto (versión simple).
- **Ajustes:** pestañas **Categorías** y **Medios de pago** (§3.10), con archivar/desarchivar.
- **Sistema visual** (§2) completo: paleta, tipografía, formato de montos, campo de monto
  (§2.4), SnackBars. Conviene hacerlo bien desde el principio porque se usa en todo.
- Atajos: `Ctrl/Cmd+N` (nuevo gasto), `Ctrl/Cmd+1/2`, Enter y Esc en diálogos.

Qué puede probar el usuario: crear el primer mes, cargar, editar y borrar gastos, ver el total,
crear/renombrar/archivar categorías y medios.

### Paso 1c – Gastos en dólares

Se construye sobre la pantalla Gastos del paso 1; no agrega pantallas nuevas.

- **Diálogo de gasto** (§4.1):
  - Selector **Moneda** (`ft.SegmentedButton` "Pesos (ARS)" / "Dólares (USD)") entre
    Categoría y Monto, con ARS por defecto.
  - **Bloque dólares:** "Monto en dólares" (US$), "Cotización del día" ($, precargada con la
    del mes guardada en el primer uso, o vacía y obligatoria si no hay) con su texto de ayuda,
    y el **recuadro de resultado** "US$ 20,00 × $ 1.600 = $ 32.000 a pagar" que se actualiza en
    cada tecla.
  - Mostrar/ocultar bloques con `visible`, conservando lo escrito en cada uno.
  - Validaciones y mensajes del bloque dólares.
  - **Edición** de un gasto en dólares: precarga de moneda, monto en dólares y cotización
    guardada; botón "Usar la del mes"; paso de dólares a pesos con el monto precargado y aviso.
  - Texto de ayuda del Tipo según la moneda.
- **Tabla de gastos** (§3.3): segunda línea "US$ 20,00 × $ 1.600" en la celda Monto, tooltip
  con la cuenta completa y `data_row_max_height=64`. Los totales siguen en pesos.
- **Formato** (§2.3): función para el detalle "US$ 20,00 × $ 1.600" (en `formato.py`, para
  que Lucía la pruebe) y la función de conversión en la lógica.
- SnackBar de alta con pesos y dólares: "Gasto "Claude" agregado: $ 32.000 (US$ 20,00)".

Qué puede probar el usuario:

- Cargar "Claude" US$ 20 a $ 1.600 y ver "$ 32.000 a pagar" mientras escribe; al guardar, ver
  $ 32.000 en la tabla con "US$ 20,00 × $ 1.600" debajo y el total sumando 32.000.
- Cambiar la cotización del día a 2.080 antes de guardar y ver $ 41.600.
- Intentar guardar con monto en dólares vacío o 0, o con cotización vacía o 0, y ver los
  mensajes.
- Escribir algo en pesos, pasar a dólares y volver: lo escrito sigue ahí.
- Editar el gasto en dólares, cambiar la cotización y ver que el monto en pesos se recalcula;
  pasarlo a pesos y ver el monto precargado.

Lo que **no** se ve todavía en 1c (llega en pasos posteriores, ver cada paso): pagos de un
gasto en dólares (paso 2), el aviso de gastos en dólares en el diálogo de cotización
(paso 3), la copia al mes nuevo (paso 4) y las partes compartidas en pesos (paso 5).

### Paso 2 – Pagos y pendiente

- **Gastos:** se agregan la columna **Pag.** (tilde), **Pagado** y **Pendiente**, la etiqueta
  "Parcial", y en la fila de totales **Pagado** y **Falta por pagar**.
- Menú de fila: **Registrar pago** y **Ver pagos**.
- Diálogos §4.3 (con la línea "Gasto en dólares: …" cuando corresponde) y §4.4; confirmación
  de destildar; SnackBar con "Deshacer" al marcar pagado.
- Validación RN-23 en el diálogo de edición de gasto, también sobre el resultado en pesos de
  un gasto en dólares.

### Paso 3 – Sueldo, cotización, cambios y ahorro (Resumen)

- **Rail:** se agrega **Resumen** como primer destino y pasa a ser la pantalla de inicio.
- **Barra superior:** se agrega la **cotización** con su estado "sin cargar" y `Ctrl/Cmd+K`.
- **Resumen** (§3.2) completo **salvo** la tarjeta "Te deben" (llega en el paso 5). La
  capacidad usa cuotas = 0.
- Diálogos de sueldo, cotización (con el aviso sobre gastos en dólares) y meta (§3.6),
  ingreso extra (§4.5) y cambio (§4.6).
- **Ajustes:** pestaña **Meta de ahorro**.
- Estados: sin cotización, sueldo 0, déficit, pesos sobrantes, capacidad negativa.

### Paso 4 – Cuotas e historial de meses

- **Barra superior:** **selector de mes**, flechas, **Mes nuevo**, menú **Borrar este mes**,
  franja de "mes pasado", atajos `Alt+←/→` y `Ctrl/Cmd+Shift+N`.
- Diálogos de **crear mes** (con la línea de fijos en dólares) y **borrar mes** (§3.9).
- **Rail:** se agrega **Cuotas** (§3.4) con filtro, tabla, diálogo de plan (§4.2) y
  cancelación.
- **Gastos:** columna Tipo muestra "Cuota n/N"; botón "Plan cuotas"; confirmación especial
  para borrar una cuota (RN-52); edición de gasto-cuota (texto fijo + "Editar el plan", sin
  selector de moneda); bloque **Por medio de pago** (RF-22).
- **Resumen:** la capacidad pasa a restar las cuotas reales.

### Paso 5 – Compartidos y "me deben"

- **Gastos:** sección **Compartido** del diálogo (§4.1) con partes, "manual", "Tu parte" y
  avisos de RN-34 (también al cambiar monto o cotización de un gasto en dólares); ícono de
  compartido en la tabla; texto extra en la confirmación de borrado.
- **Rail:** se agrega **Me deben** (§3.5) con tarjetas por persona, "Mostrar cobrados",
  diálogo de ítem (§4.8) y "Deshacer" al cobrar.
- **Ajustes:** pestaña **Personas**.
- **Resumen:** tarjeta **Te deben**.
- **Borrar mes:** texto sobre las partes compartidas.

### Paso 6 – Previsión

- **Rail:** se agrega **Previsión** (§3.7) con la tabla, liberaciones y sus estados. El enlace
  al gráfico se agrega en el paso 7.

### Paso 7 – Gráficos

- **Rail:** se agrega **Gráficos** (§3.8) con las 3 pestañas y sus tablas alternativas.
- Agregar `flet-charts` a `requirements.txt` (nota de §3.8).
- **Previsión:** enlace "Ver el gráfico de previsión".
- **Ajustes:** pestaña **Apariencia** (puede adelantarse a cualquier paso; es independiente).

### Paso 8 – Importar Excel (v2)

Se construye cuando la v1 está completa. Cada sub-paso es probable por separado y por Lucía:

- **8a – Lógica (sin pantallas).** Leer el .xlsx, detectar filas y bloques, proponer tipos,
  la lista de revisión en memoria y el guardado todo o nada (`requisitos.md` §9). Se prueba
  solo con pytest.
- **8b – Entradas y elegir archivo.** Botón "Importar Excel" debajo del formulario de primer uso (§3.1 modificado), pestaña
  "Importar Excel" de Ajustes, pantalla de §3.11 con `FilePicker`, elegir hoja y los avisos
  de error de archivo. Termina mostrando, por ahora, la cantidad de filas detectadas
  (sin editar nada).
- **8c – Lista de revisión de solo lectura.** §3.12 sin edición: bloques, filas, tipos
  propuestos, notas y avisos, filtros, "Filas incompletas", controles generales (mes y
  categoría), pie con conteo. Tilde y tipo ya editables.
- **8d – Edición.** Diálogos §4.9 y §4.10, creación en línea de categorías y personas (§4.11),
  errores por fila y bloqueo de "Confirmar importación".
- **8e – Confirmar y cancelar.** Resumen previo, guardado todo o nada, resultado, errores,
  cancelar con confirmación (§3.13 y §3.14; cerrar la ventana no pregunta).

Qué puede probar el usuario al final: importar `planilla-prueba.xlsx` y ver las 13 filas de la
lista esperada con sus tipos y avisos; cambiar tipos, corregir un monto, crear a "Juan",
cambiar el mes destino y ver cómo se destildan las repetidas; cancelar y verificar que no
quedó nada; confirmar y ver el resultado y el mes.

### Paso 9 – Cotización automática (v2)

Última funcionalidad de la v2. Sin pantallas nuevas, sin cambios en la estructura de la base
ni dependencias nuevas (`requisitos.md` §9, paso 9). Se divide en dos sub-pasos que se prueban
por separado, igual que el paso 8:

- **9a – Lógica (sin pantallas).** En `app/logica/`: leer y guardar el dólar elegido (Blue por
  defecto y ante valores desconocidos); decidir si un mes tiene botón (RN-80); armar la
  dirección del pedido; pedir con tiempo máximo de 10 segundos; validar la respuesta; pasar la
  compra a centavos; y armar los textos del botón, del origen (con la hora de Argentina) y del
  error. La función que hace el pedido a internet es reemplazable, así Lucía prueba todo con
  pytest y **sin internet**. No importa nada de Flet.
- **9b – Interfaz.** Dos partes que se pueden probar una por una:
  1. **Ajustes → pestaña "Cotización"** (§3.10): `RadioGroup` con Blue, MEP, Oficial y
     Cripto, texto de ayuda y guardado al instante con SnackBar.
  2. **Diálogo de la cotización del mes** (§3.6, "Buscar la cotización en internet"): botón
     solo en el mes actual y los futuros, ruedita y campo en solo lectura mientras busca,
     campo completado sin guardar, origen debajo del campo (y que desaparezca al editar),
     mensaje de error, un solo pedido aunque se toque dos veces, y descartar la respuesta si
     el diálogo se cerró o pasaron los 10 segundos.
- **Cómo no trabar la ventana (para quien programa):** el pedido a internet no puede correr
  dentro del manejador del clic sin más, porque la ventana quedaría congelada hasta 10
  segundos. Usar un manejador asincrónico o un hilo aparte y, al volver, actualizar los
  controles y llamar a `update()`; verificar el mecanismo exacto en Flet 1.0.3.

Qué puede probar el usuario al final:

- En Ajustes → Cotización, ver "Blue" elegido; elegir MEP, cerrar la app, abrirla y ver que
  sigue en MEP. Abrir el diálogo de la cotización (`Ctrl/Cmd+K`) y ver "Buscar dólar MEP".
- En el mes actual, tocar el botón con internet: ver la ruedita, el campo completado y el
  origen con fecha y hora. Tocar "Cancelar" y ver que la cotización no cambió; repetir y tocar
  "Guardar" y ver el Resumen recalculado.
- Escribir en el campo después de buscar y ver que el origen desaparece.
- Desconectar internet, tocar el botón y ver el mensaje de error con el campo intacto.
- Entrar a un mes pasado (selector de mes) y ver que el diálogo no tiene botón.
- Tocar el botón y cerrar el diálogo enseguida con `Esc`: no pasa nada después.

### Sugerencia de organización de archivos de la interfaz

Solo como orientación para el agente que programa:

```
app/interfaz/
  main.py            # arma la ventana, el rail, la barra y cambia de pantalla
  estilos.py         # colores por tema, tamaños de texto, constantes
  componentes.py     # campo de monto, selector de moneda, confirmación, estado vacío, aviso
  barra_superior.py
  pantalla_resumen.py
  pantalla_gastos.py
  pantalla_cuotas.py
  pantalla_me_deben.py
  pantalla_prevision.py
  pantalla_graficos.py
  pantalla_ajustes.py
  pantalla_importar.py   # v2: §3.11 a §3.14
  dialogos/          # un archivo por diálogo de §4 (v2: dialogo_fila_importacion.py)
app/logica/
  formato.py         # formatear ARS/USD/fechas/detalle en USD y leer montos escritos (sin Flet)
```

Cada pantalla expone una función `refrescar()` que vuelve a pedir los datos a la lógica y
redibuja. Después de guardar cualquier cosa se llama al `refrescar()` de la pantalla visible
y de la barra superior. Es simple y alcanza para el volumen de datos de un solo usuario.

---

## 7. Observaciones

Puntos de los requisitos que no se pueden diseñar del todo bien o que necesitan una decisión.
**No cambié los requisitos**; los anoto para que Ana los revise con el usuario.

1. **Categorías iniciales.** La categoría es obligatoria (RF-06), pero los requisitos solo
   definen valores iniciales para medios de pago (RF-11), no para categorías. Con la base
   vacía el usuario no puede cargar su primer gasto sin crear antes una categoría. Lo resolví
   con la creación de categoría dentro del diálogo de gasto. Alternativa a decidir: cargar
   categorías iniciales (ej. Vivienda, Servicios, Transporte, Comunicaciones, Salud, Deudas,
   Otros).
2. **Quitar la meta de ahorro.** Existe el estado "sin meta" (RN-38, RN-39), pero RF-36 solo
   dice "editable" y meta 0 se rechaza (CA-36.2). Sin un "Quitar meta", una vez cargada no se
   puede volver a "sin meta". Propongo el botón "Quitar meta"; falta confirmarlo.
3. **Editar y borrar ítems manuales de "me deben".** RF-32 solo habla de cargarlos. Para
   corregir errores de tipeo hace falta editarlos o borrarlos. Propongo "Editar" y "Borrar"
   en su menú; falta confirmarlo.
4. **Borrar la cotización.** RN-06/RN-18 permiten un mes sin cotización, pero no dicen si una
   cotización cargada se puede volver a dejar vacía. Diseñé que no (solo se edita). Si se
   quiere permitir, se agrega un botón "Quitar cotización".
5. **Cotización obligatoria al crear el primer mes.** CA-04.1 dice que se pide la cotización,
   pero RN-06 dice que puede quedar sin cargar. Diseñé el campo como opcional, con el texto
   "Podés dejarla vacía y cargarla después". Si debe ser obligatoria, solo cambia la
   validación.
6. **Formato de la cotización.** RN-04 define ARS sin decimales, pero la cotización puede tener
   centavos (RN-02: 1.432,50). Propongo mostrarla sin decimales si es entera y con 2 si no.
   Lo mismo vale para la "cotización del día" de los gastos en dólares.
7. **Porcentaje de la meta.** CA-36.1 dice "101 % (101,12 %)". Interpreté: la barra muestra
   "101 %" y el tooltip "101,12 %". Si se quiere el valor exacto visible, se muestra
   "101,12 %" directamente.
8. **Gasto de tipo cuota editado a mano.** RF-07 permite editar "cualquier campo", pero cambiar
   el tipo de una cuota a "fijo" o "único" rompería el vínculo con el plan (y `plan_cuotas_id`
   tiene que ser NULL si el tipo no es cuota). Diseñé el tipo como **no editable** en los
   gastos de cuota (y tampoco la moneda, porque los planes son solo en pesos). También
   conviene que Ana aclare qué pasa si el usuario cambia a mano el monto de una cuota de un
   mes futuro y después edita el plan (RN-30 solo protege las cuotas **con pagos**; el monto
   editado a mano se pisaría).
9. **Fecha de los pagos.** El modelo guarda fecha en `pagos`, pero ningún RF dice que el
   usuario la cargue. Diseñé: fecha de hoy por defecto, editable en el pago parcial; el tilde
   usa la fecha de hoy.
10. **Dos meses de referencia en Cuotas.** El filtro usa el mes actual (CA-21.1) y la cuota
    n/N y el restante usan el mes seleccionado (RF-17). Es correcto pero puede confundir; lo
    mitigué mostrando siempre en pantalla qué mes se usa para cada cosa.
11. **Lista "me deben" que crece sin fin.** Al ser acumulada y copiarse los fijos compartidos
    cada mes, la lista crece con cada mes. Diseñé un filtro "Mostrar cobrados" apagado por
    defecto. No cambia ningún cálculo, solo lo que se ve.
12. **Categoría/medio/persona archivados al editar.** RN-49 dice que lo archivado no aparece
    "para cargar datos nuevos". Interpreté que al **editar** un gasto que ya los usa sí se
    muestran (con "(archivada)"), para no obligar a cambiarlos.
13. **Versión de Flet y gráficos.** El proyecto usa Flet 1.0.3: los gráficos están en el
    paquete `flet-charts` y los diálogos se abren con `page.show_dialog(dlg)` (no
    `page.open(dlg)` de 0.2x). Los nombres de componentes de este documento son orientativos;
    hay que verificarlos contra la versión instalada en `.venv` (por ejemplo, en
    `ft.SegmentedButton` la propiedad `selected` es una lista de valores).
14. **Punto decimal del teclado numérico.** Con punto de miles y coma decimal (RN-04), un
    "66020.12" escrito con el teclado numérico es ambiguo. Diseñé rechazarlo con un mensaje
    claro en vez de adivinar.

**Gastos en dólares**

15. **Mes nuevo sin cotización y fijos en dólares.** La decisión aprobada dice que los fijos en
    USD se copian "con la cotización del mes nuevo", pero el mes nuevo puede crearse sin
    cotización (RN-06). Opciones: (a) copiarlos con la cotización que tenían en el mes
    anterior y avisarlo; (b) exigir la cotización al crear el mes si hay fijos en dólares;
    (c) dejarlos sin pesos hasta que se cargue (rompe "monto > 0"). Diseñé el aviso en el
    diálogo de crear mes y recomiendo **(b)**: es la más simple de explicar y no deja datos a
    medias. Falta que Ana lo defina.
16. **Fijos en dólares en la previsión.** RN-42 usa los fijos del mes actual "con el mismo
    monto". Un fijo en dólares, ¿se estima con sus pesos fijos del mes actual o se reconvierte
    con `K_actual`? Hoy dan lo mismo solo si su cotización del día es igual a la del mes.
    Propongo usar los pesos del mes actual (es coherente con "mismo monto" y no cambia
    RN-42); falta confirmarlo.
17. **Cambiar la cotización del mes no actualiza los gastos en dólares.** Es lo aprobado (los
    pesos quedan fijos), pero el usuario podría esperar lo contrario. Lo mitigué con el texto
    del diálogo de cotización y el botón "Usar la del mes" al editar. Si se quisiera un
    "actualizar todos los gastos en dólares con la cotización del mes", sería una función
    nueva.
18. **RN-05 y RN-23 para gastos en dólares.** Hace falta que los requisitos digan que el
    monto en dólares y la cotización del día deben ser > 0, y que RN-23 se aplica al
    resultado en pesos al editar. Diseñé los mensajes asumiendo eso.
19. **Copia al mes nuevo de un fijo en dólares con pagos o partes.** Los fijos se copian sin
    pagos (RN-09) y con su configuración de compartido (RN-37); las partes automáticas se
    recalculan sobre los pesos nuevos, pero una parte **manual** se copia con su valor en
    pesos aunque el gasto haya cambiado de monto por la cotización nueva. Si con eso "Tu
    parte" queda negativa, no está definido qué hace la copia. Falta definirlo.
20. **Total en dólares de la tabla.** No se muestra un total en dólares de los gastos en USD
    (mezclaría cotizaciones distintas). Si el usuario lo quisiera (ej. "este mes pago US$ 45
    de suscripciones"), se podría agregar como texto debajo de la tabla.

Continúan la numeración de §7 de `docs/diseno.md`. Las observaciones 21, 22, 26, 29, 30 y 31
las decidió el usuario el 2026-10-13; 23 a 25, 27 y 28 son para Ana.

**Importar Excel**

21. **Primer uso – decidido:** el formulario queda como está, con "¿Tenés una planilla?
    [Importar Excel]" debajo (no agrega un clic a quien empieza de cero). Se descartó una
    pantalla de elección con dos tarjetas.
22. **Pantalla completa sin rail – decidido: sí.** La importación es una pantalla propia (sin
    rail ni barra superior, también cuando viene de Ajustes), para no salir a otra pantalla
    a mitad de la revisión.
23. **Agrupar por bloques depende de la lógica.** RN-65 define "título de bloque" para
    cualquier texto sin monto, y el diseño agrupa la lista por esos títulos. La lógica tiene
    que entregar, por cada fila detectada, el título del bloque al que pertenece (o ninguno).
    Si no se quiere, el diseño funciona con un único bloque "Filas detectadas".
24. **Acciones de bloque nuevas.** "Tildar todas", "Destildar todas" y "Cambiar el tipo de
    todas..." (§4.10) no figuran en RF-52/RF-53. Las agregué como comodidad (sobre todo para
    "Sofía y Marsu" sin persona). No cambian ninguna regla; si Ana no las quiere, se
    quitan sin afectar el resto.
25. **Tilde automático al cambiar de tipo.** Al pasar una fila de "Ignorar" a otro tipo, la
    fila se tilda sola, y mientras es "Ignorar" el tilde está deshabilitado. RN-68 solo dice
    que una fila se importa si está tildada y no es "ignorar"; esto lo hace más fácil y
    evita una fila "con tipo pero sin tilde" que parece importarse y no.
26. **Personas y categorías nuevas que no se usan – decidido:** al confirmar se crean
    **solo** las nuevas que quedaron en uso en alguna fila que se importa (si el usuario creó
    "Juan" y después pasó la fila a "Ignorar", no se crea). Ana debe reflejarlo en RN-72 y
    RN-75.
27. **Mensaje del pagado con signo de moneda.** El texto de CA-57.5 es "El pagado (12.000) es
    mayor que el monto (10.000)." sin `$`. Lo usé tal cual por el requisito, pero la regla
    de §0 pide moneda visible; sugiero "El pagado ($ 12.000) es mayor que el monto
    ($ 10.000)." Si se cambia, hay que actualizar CA-57.5.
28. **Textos nuevos no definidos en los requisitos.** Los mensajes "Ya existe en Octubre 2026.
    Viene destildada.", "Repetida en el archivo...", "Falta el nombre/monto. Se ignora.", el
    texto de cuota/sueldo en la fila y los del diálogo de resultado son míos. Los exactos
    de los requisitos (aviso de gasto compartido, nota de cobrado, "Monto no válido",
    "Marcaste N filas...", "No hay filas para importar.", "No se pudo importar...",
    "¿Descartar la importación?", archivo dañado, hoja vacía y fórmulas) se usaron tal cual.
    Si los criterios de aceptación necesitan textos exactos para los míos, Ana debe fijarlos.
29. **Edición solo con diálogo, no en la fila – decidido:** categoría y persona se cambian
    en el diálogo de §4.9 (la fila queda liviana). Para no abrir 10 diálogos, la acción de
    bloque de §4.10 pasa a ser "Cambiar tipo o categoría de todas...", con la opción "No
    cambiar el tipo" para cambiar solo la categoría (o la persona) de todo el bloque.
30. **Pantalla después de importar – decidido: Gastos** (ahí se completan medios de pago y
    compartidos). Si solo se importaron "me deben" o sueldo, Resumen, porque en Gastos no se
    vería nada nuevo.
31. **Cerrar la ventana con cambios – decidido: no se pregunta.** Solo "Cancelar" y `Esc`
    piden confirmación; cerrar la ventana cierra sin preguntar (no se intercepta el cierre).
    Ana debe ajustar RN-76 y CA-57.3, que hoy piden preguntar también al cerrar.
32. **Componentes de Flet a verificar.** Como en la observación 13, los nombres son
    orientativos para Flet 1.0.x: en particular `ft.FilePicker` (en 1.0 es un servicio y el
    selector es asincrónico), `ft.Dropdown(dense=...)`, `ft.ExpansionTile` y
    `ListView.scroll_to`. Verificarlos contra la versión instalada en `.venv`.

**Cotización automática**

Las preguntas P-1 a P-4 de `requisitos.md` §10 (redondeo al centavo, fecha inválida = error,
campo bloqueado mientras busca, sin aviso por cotización de día anterior) las confirmó el
usuario como las propuso Ana; el diseño las sigue. Las observaciones 33 a 38 son decisiones
de diseño para que el usuario las confirme; la 36 es además para Ana.

33. **Dónde va el selector del dólar – a decidir.** Lo puse en una pestaña nueva
    "Cotización" entre "Meta de ahorro" y "Apariencia" (§3.10): se encuentra fácil, tiene
    espacio para la ayuda y sigue el patrón de Apariencia. Costo: Ajustes pasa a **7 pestañas**
    y a 1100 px de ancho no entran todas, así que la barra tiene que poder desplazarse.
    Alternativa: no crear pestaña y poner el selector debajo del campo de la meta, renombrando
    esa pestaña "Ahorro y dólar" (6 pestañas, sin desplazamiento). Recomiendo la pestaña nueva
    por claridad; si al probar el desplazamiento molesta, se pasa a la alternativa sin tocar
    nada más. **Decidido por el usuario (2026-10-18): pestaña nueva "Cotización".**
34. **Campo "bloqueado" = solo lectura, no deshabilitado.** Mientras busca, el campo de la
    cotización usa `read_only=True`. Con `disabled=True` Flet lo atenúa y el valor se lee
    mal, y el usuario tiene que ver qué valor queda si la búsqueda falla o se cancela. Para el usuario es lo mismo (no puede escribir). Si se
    prefiere el aspecto atenuado, es un cambio de una línea.
35. **"Guardar" durante la búsqueda guarda el valor viejo.** Es lo que piden los requisitos
    (RN-86: Guardar y Cancelar siguen disponibles) y puede sorprender: el usuario toca
    "Buscar", impaciente toca "Guardar" y se guarda lo de antes, no lo que iba a traer. Lo
    mitigué con el texto de estado ("Si guardás ahora, se guarda el valor que ves."). Si el
    usuario prefiere evitarlo del todo, la alternativa es deshabilitar "Guardar" mientras
    busca (máximo 10 segundos); eso exigiría cambiar RN-86 y CA-61.7/CA-61.8, así que lo dejo
    como pregunta para el usuario y para Ana. **Decidido por el usuario (2026-10-18): Guardar
    se deshabilita mientras busca.** RN-86, CA-61.7 y CA-61.8 ya se actualizaron y el texto
    "Si guardás ahora, se guarda el valor que ves." se eliminó.
36. **Textos nuevos, míos, no definidos en los requisitos** (Ana debe fijarlos si los
    criterios de aceptación los verifican): "Buscando la cotización…", la ayuda del botón ("Trae el precio de compra de hoy desde
    internet (DolarApi) y completa el campo. No se guarda hasta que toques Guardar. El dólar
    se elige en Ajustes."), el tooltip del botón, los párrafos de ayuda y el título de
    pestaña de Ajustes, el nombre de la pestaña "Cotización" y el SnackBar "Dólar para la
    cotización: MEP". Los textos del botón, el origen y el error son los exactos de los
    requisitos (RN-79, RN-85, RN-87).
37. **Mes futuro: aviso de que se trae la cotización de hoy.** En un mes futuro el botón
    completa la cotización de hoy (RN-80). Agregué en la ayuda: "Es la cotización de hoy, no
    la de Noviembre 2026.", para que no se la tome por una cotización prevista. Si no se
    quiere, se quita sin afectar nada más.
38. **Foco y atajos.** Tras una búsqueda correcta el foco vuelve al campo (así `Enter` guarda);
    tras un error va al botón (para reintentar sin guardar por accidente). No agregué un atajo
    de teclado para "Buscar": dentro de los diálogos los atajos globales se ignoran (§1.3) y
    con Tab alcanza. Si el usuario lo quisiera, podría ser `Ctrl/Cmd+B` solo dentro de este
    diálogo.
39. **Componentes de Flet a verificar (Flet 1.0.3).** Como en las observaciones 13 y 32:
    `ft.ProgressRing` (y su `semantics_label`), `TextField.read_only`, que `on_change` no se
    dispare al asignar `value` desde el código, `control.focus()` después de `update()`, los
    manejadores asincrónicos o hilos para no congelar la ventana, `ft.RadioGroup` dentro de
    una pestaña y el desplazamiento de `ft.Tabs` con 7 pestañas.
