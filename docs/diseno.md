# Diseño de pantallas – App de gastos personales (v1)

> Documento de diseño UX/UI. Define **cómo se ve y cómo se usa** la app. No define cómo se
> programa la lógica (eso está en `docs/requisitos.md`).
> Base: `docs/requisitos.md` (aprobado) y la planilla de referencia
> (`docs/referencia/Referencia planilla.png`).
> Las referencias RF-xx, RN-xx y CA-xx.y son las de `requisitos.md`.

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
   valores calculados importantes (USD a cambiar, ahorro, capacidad) muestran de dónde salen.

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
| 7 | Ajustes | `SETTINGS_OUTLINED` | Categorías, medios, personas, meta, apariencia | No |

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
| Texto secundario | `#4A5056` | Etiquetas, ayudas | ≈ 8:1 |
| Borde | `#C3C9CE` | Bordes de tarjetas y separadores | – |
| **Pagado / positivo** | `#1E7B34` (fondo suave `#E3F2E6`) | Gasto pagado, cobrado, ahorro, meta alcanzada | ≈ 5,4:1 |
| **Pendiente / aviso** | `#9A5800` (fondo suave `#FFF1DC`) | Pendiente de pago, falta cotización, sueldo 0, parte con diferencia | ≈ 5,3:1 |
| **Negativo / error** | `#B3261E` (fondo suave `#FCE8E6`) | Déficit, capacidad negativa, errores de validación, botón borrar, "a devolver" | ≈ 6,5:1 |
| Info | `#1F5F7A` (fondo suave `#E3EFF4`) | Avisos informativos (mes pasado, alcance de cuotas) | ≈ 7:1 |

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
| Texto y celdas de tabla | 15 | normal | Por defecto en toda la app |
| Totales de tabla | 15 | `W_700` | Fila de totales |
| Etiqueta / ayuda | 13 | normal | Subtítulos, textos de ayuda, ejes de gráficos |

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

---

### 3.3 Gastos (RF-06 a RF-15, RF-22, RF-29 marca)

**Objetivo del usuario:** cargar los gastos del mes, marcar lo que pagó y ver cuánto le falta
pagar. Equivale a "Gasto del Mes" y "Deudas" de la planilla.

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
| | Visa Santander            |    $ 91.117 |                                                |
| | Mastercard Nación         |   $ 131.000 |                                                |
| | Transferencia             |   $ 260.000 |                                                |
| | Sin medio de pago         |    $ 30.000 |                                                |
| +-----------------------------------------+                                                |
+--------------------------------------------------------------------------------------------+
```

(En el boceto los montos van pegados al `$` por espacio; en la app llevan el formato de §2.3:
`$ 260.000`.)

**Columnas de la tabla** (`ft.DataTable`, `heading_row_color` = superficie variante,
`data_row_min_height=48`):

| Columna | Contenido | Componente |
|---|---|---|
| Pag. | Tilde "pagado" (RF-13). Marcado si pendiente = 0 (RN-22). | `ft.Checkbox` con `tooltip="Marcar como pagado"` |
| Nombre | Nombre + ícono `PEOPLE` (16 px, tooltip "Compartido con Sofía y Marsu") si es compartido. Clic → editar. | `ft.DataCell(ft.Row([...]), on_tap=…)` |
| Categoría | Nombre; si está archivada, en texto secundario con tooltip "Categoría archivada". | `ft.Text` |
| Tipo | "Fijo", "Único" o "Cuota n/N" (une tipo y cuota actual de RF-09 en una sola columna). | `ft.Text` |
| Medio de pago | Nombre o "—". | `ft.Text` |
| Monto | ARS. | `numeric=True` |
| Pagado | ARS; si es parcial, debajo una etiqueta chica "Parcial" en *pendiente*. | `numeric=True` |
| Pendiente | ARS en *pendiente*; si es 0, el texto "Pagado" en *positivo* con ícono `CHECK`. | `numeric=True` |
| (acciones) | Menú: Editar · Registrar pago · Ver pagos · Borrar. Para cuotas, además "Ver plan" (va a Cuotas). | `ft.PopupMenuButton` |

**Orden de las filas:** primero fijos, luego cuotas, luego pagos únicos; dentro de cada grupo,
por nombre. (Opcional más adelante: ordenar por columna con `DataColumn(on_sort=…)`.)

**Fila de totales (RF-09):** una última `ft.DataRow` con fondo de superficie variante y texto
en negrita: "TOTAL (23 gastos)", total gastos, total pagado y total pendiente ("Gastos",
"Pagado" y "Falta por pagar" de la planilla). Los totales se redondean desde el valor exacto
(RN-04).

**Por medio de pago (RF-22):** `ft.Card` con una `ft.DataTable` de dos columnas, debajo de la
tabla principal. "Sin medio de pago" siempre al final. Este bloque reemplaza la línea "Tarjetas
de Crédito" de la planilla, así que lleva el texto de ayuda: "Incluye todos los gastos del mes
(fijos, cuotas y únicos) agrupados por cómo se pagan."

**Estados**

| Situación | Cómo se ve |
|---|---|
| Sin gastos | Estado vacío: ícono `RECEIPT_LONG`, "Todavía no cargaste gastos en Octubre 2026.", botón "Agregar gasto (Ctrl+N)". No se muestran la fila de totales ni "Por medio de pago". |
| Con datos | Como el boceto. |
| Todo pagado | La fila de totales muestra "Falta por pagar $ 0" con ícono `CHECK_CIRCLE` en *positivo*. |
| Mes no actual | Franja informativa de §1.2. |

**Flujo: cargar un gasto (RF-06)**

1. Clic en "Agregar gasto" (o `Ctrl/Cmd+N`).
2. Diálogo §4.1 con foco en "Nombre". Tipo por defecto: "Fijo mensual".
3. Escribe nombre, elige categoría, monto, tipo y (opcional) medio de pago. Tab avanza de campo.
4. Enter o "Guardar" → valida. Si hay errores se muestran debajo de cada campo y el diálogo
   sigue abierto.
5. Si está todo bien: se cierra, la fila aparece en la tabla, los totales y "Por medio de pago"
   se actualizan, SnackBar "Gasto "Nafta" agregado".

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
cuánto le falta; cargar planes nuevos, editarlos o cancelarlos.

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
| registrados.                              |
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
| | Mes       | Gastos estimados | USD a cambiar | Ahorro estimado | Se libera              | |
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
| 1. Gastos por categoría (RN-46), mes seleccionado | **Barras horizontales**, ordenadas de mayor a menor | Una fila por categoría: nombre (izquierda), barra proporcional al mayor, monto ARS y porcentaje del total. | Un solo color: *primario*. | **Sin librería de gráficos**: cada fila es un `ft.Row` con `ft.Text` (ancho fijo 160), `ft.ProgressBar(value=monto/máximo, height=18)` y dos `ft.Text`. Es más simple, los nombres largos se leen completos y el dato exacto está escrito. |
| 2. Ahorro mes a mes (RN-47), todo el historial | **Barras verticales** | Eje X: meses (`oct 26`). Eje Y: USD, con 0 marcado. Tooltip: "Octubre 2026: US$ 303,36". | Positivo: *positivo*. Negativo (déficit): *negativo*, la barra baja del 0. Mes sin cotización: sin barra y etiqueta "s/cot." debajo del mes. | `BarChart` (ver nota). Si hay meta, una línea de texto arriba: "Meta: US$ 300,00". |
| 3. Previsión de gastos (RN-48) | **Barras verticales** | Eje X: los 12 meses previstos. Eje Y: ARS abreviado ("$ 800 mil"). Tooltip con el monto completo. | *Primario*. | `BarChart`. |

Por qué barras y no torta: las barras permiten comparar tamaños a simple vista y se leen igual
con daltonismo; la torta obliga a comparar ángulos y a usar muchos colores.

Debajo de los gráficos 2 y 3 hay un `ft.ExpansionTile("Ver como tabla")` con los mismos datos
en una `ft.DataTable` (accesibilidad: lectores de pantalla y quien prefiera números).

**Nota sobre el componente de gráficos:** en Flet 0.2x es `ft.BarChart` (con
`ft.BarChartGroup`, `ft.BarChartRod`, `ft.ChartAxis`, `ft.ChartAxisLabel`). En Flet 1.x los
gráficos se movieron al paquete aparte `flet-charts` (`import flet_charts as fch`,
`fch.BarChart`). Antes del paso 7 hay que verificar qué versión está instalada y, si hace
falta, agregar `flet-charts` a `requirements.txt`.

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
|  • 4 cuotas de planes activos                             |
| No se copian pagos únicos, ingresos extra ni cambios.     |
|                                                           |
|                           [Cancelar] [Crear mes]          |
+-----------------------------------------------------------+
```

3. El mes no se elige: es siempre el siguiente al último (RN-08), así no hay cómo
   equivocarse. Sueldo y cotización vienen sugeridos (CA-03.2).
4. "Crear mes" → la app selecciona el mes nuevo, muestra Resumen y SnackBar "Noviembre 2026
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

### 4.1 Gasto (alta y edición) – RF-06, RF-07, RF-29, RF-30, RF-31

```
+------------------------------------------------------------+
| Nuevo gasto – Octubre 2026          (o "Editar gasto")     |
|                                                            |
| Nombre          [ Internet                         ]       |
| Categoría       [ Servicios                     v ] [+]    |
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

| Campo | Componente | Validación / mensaje |
|---|---|---|
| Nombre | `ft.TextField(autofocus=True, max_length=60)` | Vacío: "Ingresá un nombre." |
| Categoría | `ft.Dropdown` con categorías no archivadas + `ft.IconButton(ADD, tooltip="Nueva categoría")` | Sin elegir: "Elegí una categoría." El botón "+" muestra **dentro del mismo diálogo** una fila `[Nombre de la categoría] [Agregar]` (no abre otro diálogo). Si no hay ninguna categoría, la fila aparece abierta con el texto "Todavía no tenés categorías. Creá la primera." |
| Monto | Campo de monto ARS (§2.4) | Mensajes comunes + RN-23 en edición: "No podés bajar el monto a menos de lo ya pagado ($ 60.000)." |
| Tipo | `ft.SegmentedButton` con "Fijo mensual" y "Pago único" (por defecto Fijo) | – |
| Medio de pago | `ft.Dropdown` con "Sin medio de pago" como primera opción + medios no archivados | Opcional. |
| Compartido | `ft.Switch` | Se habilita desde el paso 5. |
| Personas | `ft.Checkbox` por persona no archivada | Con el switch activo y ninguna tildada: "Elegí al menos una persona o desactivá Compartido." |
| Parte de cada persona | Campo de monto ARS chico (ancho 160) + etiqueta "manual" si fue editada | Mensajes comunes, pero acepta 0 (el modelo permite ≥ 0). Si "Tu parte" queda negativa (RN-33): "Las partes suman $ 42.900 y superan el monto ($ 38.700)." en *negativo* debajo de la tabla. |
| Tu parte | `ft.Text` (solo lectura), se recalcula en cada tecla (`on_change`) | – |

**Edición: casos especiales**

- **Categoría, medio o persona archivados ya asignados al gasto:** se muestran en el
  `Dropdown` con el sufijo "(archivada)" para no obligar a cambiarlos al editar otro campo.
  No se ofrecen en un alta (RN-49, CA-06.5).
- **Gasto de una cuota:** en lugar del selector de tipo se muestra el texto fijo "Cuota 3/6
  de Préstamo X" con un enlace "Editar el plan". Los demás campos se pueden editar y el cambio
  vale **solo para este mes** (RN-11); se avisa: "Este cambio vale solo para Octubre 2026.
  Para cambiar todas las cuotas, editá el plan."
- **Cambio de monto en un gasto compartido (RN-34):** mientras se escribe el monto nuevo, la
  tabla de partes muestra los valores recalculados. Si una parte ya cobrada cambia, debajo
  aparece en *pendiente*: "La parte de Sofía ya estaba cobrada ($ 12.900). Va a quedar
  pendiente: falta $ 2.100." (o "a devolver $ 2.900"). Si "Tu parte" quedaría negativa, se
  rechaza: "Con este monto tu parte quedaría en -$ 1.667. Subí el monto o bajá las partes
  manuales."
- Título: "Editar gasto – Octubre 2026"; en edición, botón extra a la izquierda
  `ft.TextButton("Borrar", color=negativo)`.

### 4.2 Plan de cuotas – RF-16, RF-19

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
| Resumen del gasto | `ft.Text` | "Seguro de moto · Monto $ 180.000 · Pagado $ 60.000 · Pendiente $ 120.000" |
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
| Moneda | `ft.SegmentedButton` "ARS" / "USD" (por defecto ARS). Al cambiar, el campo monto cambia `prefix_text` y `suffix_text`. | Siempre hay una elegida (CA-24.3 no puede darse desde la interfaz; la lógica igual valida). |
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

---

## 5. Accesibilidad (resumen)

- **Contraste:** todos los pares de color de §2.1 cumplen 4,5:1 o más, en ambos temas.
- **Tamaños:** texto base 15, mínimo 13; filas de tabla de 48 px de alto; botones e íconos
  clickeables de al menos 40 × 40 px (tamaño por defecto de `IconButton`).
- **No solo color:** cada estado tiene texto o ícono ("Pagado", "Parcial", "Déficit", "Sin
  capacidad de endeudamiento", "a devolver", "Archivada").
- **Teclado:** todo se puede hacer con teclado: Tab recorre los controles en orden visual,
  Espacio marca tildes, Enter guarda, Esc cancela, atajos de §1.3. En cada diálogo el foco
  arranca en el primer campo; en las confirmaciones, en "Cancelar".
- **Lectores de pantalla:** todos los `IconButton` tienen `tooltip`; los gráficos tienen su
  versión en tabla.
- **Etiquetas siempre visibles:** el rail muestra texto bajo cada ícono; los campos usan
  `label` (no solo `hint_text`, que desaparece al escribir).
- **Errores claros:** cada mensaje dice qué está mal y cómo arreglarlo, en español y sin
  términos técnicos.

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
  otro lado; quedan guardados para el paso 3).
- **Gastos** (§3.3) con columnas **Nombre, Categoría, Tipo, Medio de pago, Monto** y el menú
  con **Editar** y **Borrar**. Fila de totales solo con **Total gastos**. Estado vacío.
- **Diálogo de gasto** (§4.1) sin la sección Compartido; con creación de categoría en línea.
- **Confirmación de borrado** de gasto (versión simple).
- **Ajustes:** pestañas **Categorías** y **Medios de pago** (§3.10), con archivar/desarchivar.
- **Sistema visual** (§2) completo: paleta, tipografía, formato de montos, campo de monto
  (§2.4), SnackBars. Conviene hacerlo bien desde el principio porque se usa en todo.
- Atajos: `Ctrl/Cmd+N` (nuevo gasto), `Ctrl/Cmd+1/2`, Enter y Esc en diálogos.

Qué puede probar el usuario: crear el primer mes, cargar, editar y borrar gastos, ver el total,
crear/renombrar/archivar categorías y medios.

### Paso 2 – Pagos y pendiente

- **Gastos:** se agregan la columna **Pag.** (tilde), **Pagado** y **Pendiente**, la etiqueta
  "Parcial", y en la fila de totales **Pagado** y **Falta por pagar**.
- Menú de fila: **Registrar pago** y **Ver pagos**.
- Diálogos §4.3 y §4.4; confirmación de destildar; SnackBar con "Deshacer" al marcar pagado.
- Validación RN-23 en el diálogo de edición de gasto.

### Paso 3 – Sueldo, cotización, cambios y ahorro (Resumen)

- **Rail:** se agrega **Resumen** como primer destino y pasa a ser la pantalla de inicio.
- **Barra superior:** se agrega la **cotización** con su estado "sin cargar" y `Ctrl/Cmd+K`.
- **Resumen** (§3.2) completo **salvo** la tarjeta "Te deben" (llega en el paso 5). La
  capacidad usa cuotas = 0.
- Diálogos de sueldo, cotización y meta (§3.6), ingreso extra (§4.5) y cambio (§4.6).
- **Ajustes:** pestaña **Meta de ahorro**.
- Estados: sin cotización, sueldo 0, déficit, pesos sobrantes, capacidad negativa.

### Paso 4 – Cuotas e historial de meses

- **Barra superior:** **selector de mes**, flechas, **Mes nuevo**, menú **Borrar este mes**,
  franja de "mes pasado", atajos `Alt+←/→` y `Ctrl/Cmd+Shift+N`.
- Diálogos de **crear mes** y **borrar mes** (§3.9).
- **Rail:** se agrega **Cuotas** (§3.4) con filtro, tabla, diálogo de plan (§4.2) y
  cancelación.
- **Gastos:** columna Tipo muestra "Cuota n/N"; botón "Plan cuotas"; confirmación especial
  para borrar una cuota (RN-52); edición de gasto-cuota (texto fijo + "Editar el plan");
  bloque **Por medio de pago** (RF-22).
- **Resumen:** la capacidad pasa a restar las cuotas reales.

### Paso 5 – Compartidos y "me deben"

- **Gastos:** sección **Compartido** del diálogo (§4.1) con partes, "manual", "Tu parte" y
  avisos de RN-34; ícono de compartido en la tabla; texto extra en la confirmación de borrado.
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
- Verificar la versión de Flet y el paquete de gráficos (nota de §3.8).
- **Previsión:** enlace "Ver el gráfico de previsión".
- **Ajustes:** pestaña **Apariencia** (puede adelantarse a cualquier paso; es independiente).

### Sugerencia de organización de archivos de la interfaz

Solo como orientación para el agente que programa:

```
app/interfaz/
  main.py            # arma la ventana, el rail, la barra y cambia de pantalla
  estilos.py         # colores por tema, tamaños de texto, constantes
  componentes.py     # campo de monto, confirmación, estado vacío, aviso, SnackBar
  barra_superior.py
  pantalla_resumen.py
  pantalla_gastos.py
  pantalla_cuotas.py
  pantalla_me_deben.py
  pantalla_prevision.py
  pantalla_graficos.py
  pantalla_ajustes.py
  dialogos/          # un archivo por diálogo de §4
app/logica/
  formato.py         # formatear ARS/USD/fechas y leer montos escritos (sin Flet)
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
   dice "editable" y meta 0 se rechaza (CA-36.2). Sin un "Quitar meta", una vez cargada no
   se puede volver a "sin meta". Propongo el botón "Quitar meta"; falta confirmarlo.
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
7. **Porcentaje de la meta.** CA-36.1 dice "101 % (101,12 %)". Interpreté: la barra muestra
   "101 %" y el tooltip "101,12 %". Si se quiere el valor exacto visible, se muestra
   "101,12 %" directamente.
8. **Gasto de tipo cuota editado a mano.** RF-07 permite editar "cualquier campo", pero cambiar
   el tipo de una cuota a "fijo" o "único" rompería el vínculo con el plan (y `plan_cuotas_id`
   tiene que ser NULL si el tipo no es cuota). Diseñé el tipo como **no editable** en los
   gastos de cuota. También conviene que Ana aclare qué pasa si el usuario cambia a mano el
   monto de una cuota de un mes futuro y después edita el plan (RN-30 solo protege las cuotas
   **con pagos**; el monto editado a mano se pisaría).
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
13. **Versión de Flet y gráficos.** Python 3.14 probablemente implique Flet 1.x, donde los
    gráficos están en el paquete `flet-charts` y algunas APIs cambiaron (por ejemplo, cómo se
    abren los diálogos: `page.open(dlg)` en 0.2x vs. `page.show_dialog(dlg)` en 1.x). Los
    nombres de componentes de este documento son orientativos; hay que verificarlos contra la
    versión instalada en `.venv`.
14. **Punto decimal del teclado numérico.** Con punto de miles y coma decimal (RN-04), un
    "66020.12" escrito con el teclado numérico es ambiguo. Diseñé rechazarlo con un mensaje
    claro en vez de adivinar.
