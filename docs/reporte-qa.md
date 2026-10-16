# Reporte de QA – Paso 1a (lógica)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: solo app/logica/ (errores, formato, base_datos, catalogos, meses, gastos). Sin interfaz.
- Base: siempre conectar(":memory:") (y archivos temporales de pytest para "reabrir"). No se usó la base real. Datos inventados.

## Cómo correr
```
.venv/Scripts/python.exe -m pytest --cov=app
.venv/Scripts/python.exe -m ruff check tests ; .venv/Scripts/python.exe -m ruff format tests
```

## Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_formato.py | 85 | 82 | 3 |
| test_base_datos.py | 19 | 19 | 0 |
| test_meses.py | 26 | 26 | 0 |
| test_catalogos.py | 45 | 45 | 0 |
| test_gastos.py | 42 | 41 | 1 |
| Total | 217 | 213 | 4 |

Cobertura de app/logica/: 100 % (231/231). Ruff sin errores.
Todos los criterios del paso 1 pasan; las 4 fallas son casos borde (BUG-01 a BUG-03).

## Qué se probó
- CA-04.1 (lógica: base vacía, primer mes con y sin cotización, no se crea un segundo primer mes), CA-04.2 (año 26/99/0/999/10000/-2026; mes 0/13/-1).
- CA-06.1 a CA-06.5, CA-07.1 (otro mes insertado por SQL), CA-07.2 (pagos por SQL; pendiente 40.000), CA-08.1 (borra pagos y partes compartidas, recalcula total), CA-09.1 (total 851.700), CA-09.2 ("$ 1"), CA-10.1 a CA-10.4 y CA-11.2 (para categorías y medios), CA-11.1 (catálogo), CA-12.1 (pago único).
- Formato: ARS (miles, mitad hacia arriba, 2,50→3, negativos simétricos, -0,49→"$ 0"), USD, cotización, monto para editar (ida y vuelta con leer_monto), nombre_mes.
- leer_monto: formatos válidos de diseno §2.4; rechaza punto decimal con el mensaje exacto, >2 decimales, negativos, vacío, texto, formatos raros, cero salvo permitir_cero.
- Base: 13 tablas, claves foráneas activas, datos iniciales, crear_tablas dos veces sin duplicar, datos iniciales borrados que no vuelven (también al reabrir), CHECK/UNIQUE como respaldo.
- Meses: sueldo 0 sí, negativo no; cotización 0/negativa no; bordes 1000/9999; último mes por fecha; mes actual con fecha fija.
- Gastos: tipos inválidos, categoría/medio inexistente, editar todo, quitar medio, editar inválido no cambia nada, monto = pagado (borde RN-23), editar cuota rechazado, archivados conservados al editar pero no elegibles, borrar inexistente, mes vacío, separación por mes, pagado_cent.

## Bugs

### BUG-01 – Monto enorme → OverflowError al guardar (RN-05 / CA-06.2)
- Prueba: test_gastos.py::test_monto_enorme_aceptado_por_leer_monto_no_rompe_al_guardar
- Reproducir: leer_monto("99999999999999999999") → 9999999999999999999900; agregar_gasto(con, mes, "Nafta", 3, ese_monto, "unico").
- Esperado: ErrorDeValidacion con mensaje. Obtenido: OverflowError: Python int too large to convert to SQLite INTEGER.
- Hipótesis: leer_monto/_validar_monto no tienen tope; SQLite admite enteros de 64 bits.

### BUG-02 – nombre_mes con mes 0 o negativo devuelve un mes equivocado (RN-07)
- Prueba: test_formato.py::test_nombre_mes_rechaza_meses_imposibles[0] y [-1]
- Reproducir: nombre_mes(2026, 0). Esperado: error (como con 13). Obtenido: "Diciembre 2026" (-1 → "Noviembre 2026").
- Hipótesis: MESES[mes - 1] con índice negativo cuenta desde el final de la lista.

### BUG-03 – formatear_monto_para_editar con negativos (diseno §2.3)
- Prueba: test_formato.py::test_formatear_monto_para_editar_negativo
- Reproducir: formatear_monto_para_editar(-150). Esperado "-1,50". Obtenido "-2,50". Igual en formatear_cotizacion(-150).
- Hipótesis: divmod(-150, 100) = (-2, 50); falta usar abs() y poner el signo aparte, como hace formatear_usd. Riesgo latente.

## Observaciones
- O1: CA-10.1 dice "Crear 'Salud'", pero ya es una categoría inicial y se rechaza (correcto según RN-50). Ajustar el texto del criterio.
- O2: agregar/editar_gasto no verifican que el monto sea int (100.5 se guarda como REAL, contra RN-01).
- O3: agregar_gasto con mes_id inexistente → sqlite3.IntegrityError, no ErrorDeValidacion.
- O4: eliminar con id inexistente devuelve "borrado"; renombrar con id inexistente no avisa.
- O5: listar ordena con COLLATE NOCASE: "Árbol" y la "Ñ" quedan después de "Vivienda".
- O6: leer_monto acepta dígitos Unicode ("１２３"); en la app lo evita el input_filter.
- O7: leer_monto acepta ceros a la izquierda ("00012") y espacios en medio ("66 020").
- Fuera de alcance: pagado/pendiente con la función de pagos (paso 2), CA-08.2/08.3 (paso 4), confirmar y cancelar de CA-08.1 (interfaz), totales por medio (CA-22.1) y CA-12.1 como plan de cuotas.

## Decisiones del usuario sobre esta ronda
- Se corrigen BUG-01, BUG-02 y BUG-03.
- Se corrigen O2, O3, O4, O5 y O6. O7 queda como está (comportamiento aceptado).
- O1: Ana ajusta el texto de CA-10.1.

---

## Ronda 2

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Motivo: verificar los arreglos de BUG-01 a BUG-03 y de O1 a O6 (O7 queda como está, lo aceptó el usuario).
- Cómo correr: `.venv/Scripts/python.exe -m pytest --cov=app`

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_formato.py | 106 | 105 | 1 |
| test_base_datos.py | 19 | 19 | 0 |
| test_meses.py | 26 | 26 | 0 |
| test_catalogos.py | 57 | 57 | 0 |
| test_gastos.py | 58 | 58 | 0 |
| **Total** | **266** | **265** | **1** |

Cobertura de app/logica/: 100 % (257/257). ruff check y ruff format sobre tests/: sin errores.

### Verificación de los arreglos
| Ítem | Estado | Pruebas |
|---|---|---|
| BUG-01 tope de montos | Corregido | El tope exacto se acepta en leer_monto, agregar_gasto y editar_gasto; un centavo más se rechaza con "El monto es demasiado grande." |
| BUG-02 nombre_mes | Corregido | Mes 0, 13 y -1 lanzan ValueError. |
| BUG-03 negativos | Corregido | -150 → "-1,50"; formatear_cotizacion(-150) → "-$ 1,50 por US$". |
| O1 CA-10.1 | Ajustado | Crear "Educación"; renombrar "Salud" a "Salud y bienestar". |
| O2 monto no entero | Corregido | float, texto, True, False y None se rechazan al agregar y al editar. |
| O3 mes inexistente | Corregido | "El mes no existe." |
| O4 ids inexistentes | Corregido | "Ese elemento ya no existe." en renombrar, eliminar y desarchivar. |
| O5 orden con acentos | Corregido | Árbol, Deudas, educación, Mercado, Ñoquis, Óptica, Otros, … Vivienda. |
| O6 dígitos Unicode | Corregido | Se rechazan dígitos de ancho completo, arábigo-índicos y superíndices. |

### Bugs nuevos
#### BUG-04 – leer_monto con más de 4300 dígitos lanza ValueError de Python
- Criterio afectado: RN-05.
- Prueba: `test_formato.py::test_leer_monto_texto_con_miles_de_digitos_se_rechaza_con_mensaje`
- Reproducir: `leer_monto("9" * 5000)`.
- Esperado: ErrorDeValidacion con mensaje. Obtenido: `ValueError: Exceeds the limit (4300 digits) for integer string conversion`.
- Hipótesis: el tope se controla después de `int(...)`, y Python limita a 4300 dígitos esa conversión. Severidad baja.

### Observaciones nuevas
- O8: `meses.crear_primer_mes` no valida tipo ni tope del sueldo y la cotización (1.5 se guarda con decimales; 10**20 da OverflowError). Desde la interfaz no pasa, pero conviene la misma validación que en gastos.

---

## Ronda 3

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Motivo: verificar los arreglos de BUG-04 y O8 (nueva función `formato.validar_centavos`).
- Cómo correr: `.venv/Scripts/python.exe -m pytest --cov=app`

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_formato.py | 135 | 135 | 0 |
| test_base_datos.py | 19 | 19 | 0 |
| test_meses.py | 42 | 42 | 0 |
| test_catalogos.py | 57 | 57 | 0 |
| test_gastos.py | 58 | 58 | 0 |
| **Total** | **311** | **311** | **0** |

Cobertura de app/logica/: 100 % (260/260). ruff check y ruff format sobre tests/: sin errores.

### Verificación de los arreglos
| Ítem | Estado | Pruebas |
|---|---|---|
| BUG-04 texto larguísimo | Corregido | Textos de 20 caracteres se aceptan; de 21 o más (4301, 5000, 100.000 dígitos) se rechazan con "demasiado grande". Un texto mal formado sigue dando "Monto inválido". |
| O8 sueldo y cotización | Corregido | float, texto, bool y None se rechazan con mensaje; tope + 1 y 10**20 dan "demasiado grande"; el tope exacto se acepta. En los rechazos no se crea el mes. |
| validar_centavos | Probada | Mensajes exactos para cada caso, con y sin permitir_cero, y con el parámetro `que`. |

### Bugs nuevos
Ninguno.

### Observaciones nuevas
- O9 (menor): "000000000000000000001" (21 caracteres, vale $ 1) se rechaza con "El monto es demasiado grande.", mensaje confuso. Solo ocurre con ceros a la izquierda.
- Nota técnica: los casos con textos de miles de dígitos tienen `ids` cortos porque en Windows pytest guarda el nombre de la prueba en la variable de entorno PYTEST_CURRENT_TEST.

**Estado de la parte 1a: terminada (todas las pruebas pasan).**

---

## Ronda 4 – Parte 1b (interfaz)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: main.py, app/interfaz/ y los cambios de lógica (`ErrorDeValidacion.campo`, mensaje nuevo de RN-23).
- Método: sin abrir ventanas, con una `PaginaFalsa` (tests/ayudantes_interfaz.py) y llamando a los handlers directo. No se usó datos-privados/.
- Cómo correr: `.venv/Scripts/python.exe -m pytest --cov=app`

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_formato.py | 135 | 135 | 0 |
| test_base_datos.py | 19 | 19 | 0 |
| test_meses.py | 42 | 42 | 0 |
| test_catalogos.py | 57 | 57 | 0 |
| test_gastos.py | 58 | 58 | 0 |
| test_errores_campo.py | 11 | 11 | 0 |
| test_interfaz_primer_uso.py | 18 | 17 | 1 |
| test_interfaz_gastos.py | 44 | 42 | 2 |
| test_interfaz_ajustes.py | 27 | 25 | 2 |
| test_interfaz_aplicacion.py | 22 | 22 | 0 |
| test_interfaz_casos_borde.py | 10 | 9 | 1 |
| **Total** | **443** | **437** | **6** |

Cobertura: 99 % total; app/logica/ 100 %. Ruff sin errores.

### Bugs
- **BUG-05** – La tabla de gastos no ordena ignorando acentos ("Ómnibus" después de "Psicólogo"). Hipótesis: ordena con `casefold()` y no con la clave sin acentos de catalogos.
- **BUG-06** – "TOTAL (1 gastos)" con un solo gasto. Hipótesis: plural fijo en `_tabla`.
- **BUG-07** – Mensajes distintos del diseño: cotización "0" en primer uso ("El monto…" en vez de "La cotización…"); Ajustes nombre vacío ("El nombre no puede estar vacío." en vez de "Ingresá un nombre."); nombre repetido ('Ya existe "Salud".' en vez de 'Ya existe una categoría llamada "Salud".'). También "Monto inválido" vs. "Escribí solo números" (§4).
- **BUG-08** – Ajustes avisa "eliminado" aunque la eliminación falló (elemento que ya no existe). Hipótesis: `_ejecutar` atrapa el error y no avisa a quien la llamó.

### Observaciones
- O10: con errores, no se pone el foco en el primer campo con error (§2.5).
- O11: los tooltips dicen "Ctrl+N" también en macOS (§1.3 pide "⌘N").
- O12: el tooltip de "Archivar" dice "Archivado" también en Categorías.
- O13: el aviso de sueldo 0 aparece solo al salir del campo; con Enter no se ve.
- O14: el texto de RN-23 en diseno.md §4.1 difiere del implementado.
- O15: con la pantalla desactualizada: editar un gasto inexistente abre "Nuevo gasto"; borrarlo da TypeError; "El gasto ya no existe." se muestra debajo de Monto.
- O16: la confirmación no pone el foco en "Cancelar".

### Para que pruebe el usuario con la ventana real
Aspecto visual (claro y oscuro), foco y Tab, filtros de los campos al pegar, nombres reales de teclas, Cmd en macOS, cierre real de diálogos y Esc, clic en pestañas, clic en el nombre de una fila, menú de tres puntos, duración del SnackBar y "Deshacer".

---

## Ronda 5

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Motivo: verificar los arreglos de BUG-05 a BUG-08 y de O10, O11, O12, O14, O15 y O16 (O13 queda como está, lo aprobó el usuario).
- Cómo correr: `.venv/Scripts/python.exe -m pytest --cov=app`

### Resultado
497 pruebas, pasan las 497. Cobertura 99 % (802 líneas, 2 sin cubrir: `main()` y un caso inalcanzable del diálogo de gasto); app/logica/ 100 %. Ruff sin errores.

Se actualizaron 10 pruebas a los mensajes nuevos del diseño (texto exacto) y se agregó tests/test_interfaz_ronda5.py (27 pruebas).

### Verificación de los arreglos
| Ítem | Estado |
|---|---|
| BUG-05 orden sin acentos | Corregido |
| BUG-06 "TOTAL (1 gasto)" | Corregido |
| BUG-07 mensajes del diseño | Corregido |
| BUG-08 avisos en Ajustes | Corregido |
| O10 foco en el primer error | Corregido |
| O11 atajos según el sistema | Corregido |
| O12 tooltip de Archivar | Corregido |
| O14 texto de RN-23 en el diseño | Corregido |
| O15 gasto que ya no existe | Corregido |
| O16 foco en Cancelar | Corregido |

### Bugs nuevos
Ninguno.

### Observaciones nuevas
- O17 (para el paso 4): si el mes se borra con el diálogo de gasto abierto, "El mes no existe." llama a `app.refrescar()`, que fallaría con TypeError. Probarlo cuando exista "Borrar mes".

**Estado de la parte 1b: pruebas automáticas completas. Falta la prueba manual del usuario con la ventana real.**

---

## Ronda 6 – Paso 1c (gastos en dólares)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: RF-43 a RF-46, RF-48; RN-53 a RN-56, RN-58, RN-59 y sus CA aplicables al paso 1c (pagos, ahorro, compartidos, copia al mes nuevo y previsión quedan para pasos posteriores).
- Datos: base en memoria para lógica e interfaz; para la migración, archivos temporales de pytest con una base versión 0 (tests/esquema_v0.py, del commit 3845e81). Nunca se usó datos-privados/.
- Cómo correr: `.venv/Scripts/python.exe -m pytest --cov=app`

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_migracion.py (nuevo) | 19 | 19 | 0 |
| test_gastos_usd.py (nuevo) | 64 | 64 | 0 |
| test_interfaz_usd.py (nuevo) | 46 | 45 | 1 |
| Rondas anteriores | 497 | 497 | 0 |
| **Total** | **626** | **625** | **1** |

Cobertura 99 % (977 líneas, 1 sin cubrir); app/logica/ 100 %. Ruff sin errores.

### Verificado
Migración v0 → v1 con respaldo (datos idénticos, respaldo en versión 0, sin re-migrar al reabrir, falla a mitad y falla del respaldo dejan la base en versión 0); conversión y formato de cotizaciones; lógica de gastos en USD (CA-43.x, 44.x, 45.x); interfaz del diálogo y de la tabla (CA-44.x, 45.x, 46.x).

### Bugs
- **BUG-09** – El aviso de alta de un gasto en dólares dice 'Gasto "Claude" agregado' y el diseño (§6, paso 1c) pide 'Gasto "Claude" agregado: $ 32.000 (US$ 20,00)'. Hipótesis: `PantallaGastos._al_guardar` solo recibe el nombre.

### Observaciones
- O18: si falla justamente el respaldo, la pantalla de error dice igual que hay una copia de respaldo.
- O19: si la actualización falla, `conectar()` no cierra la conexión antes de relanzar el error.
- O20: la base actualizada no tiene el CHECK de consistencia de moneda (SQLite no permite agregarlo); lo cubre la lógica. Riesgo aceptado.
- O21: una base con versión mayor a la de la app se abre sin avisar.

### Para que pruebe el usuario con la ventana real
Recuadro de resultado en cada tecla, selector de moneda con clic/flechas/Espacio, segunda línea de la tabla y su tooltip, y la migración real: al abrir debe aparecer un archivo en datos-privados/respaldos/ y los totales deben coincidir con los de antes.

---

## Ronda 7

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Motivo: verificar los arreglos de BUG-09, O18, O19 y O21 (O20 queda como riesgo aceptado).
- Datos: base en memoria y archivos temporales de pytest. Nunca se usó datos-privados/.

### Resultado
644 pruebas, pasan las 644. Cobertura 99 % (997 líneas, 1 sin cubrir); app/logica/ 100 %. Ruff sin errores.

Se actualizaron 6 pruebas a `ErrorDeBase` y a los mensajes nuevos (exigen el texto exacto, la causa original, versión 0 y datos intactos).

### Verificación de los arreglos
| Ítem | Estado |
|---|---|
| BUG-09 aviso de alta en USD con montos | Corregido |
| O18 mensajes de falla (con y sin respaldo) | Corregido |
| O19 conexión cerrada tras una falla | Corregido (verificado renombrando el archivo en Windows) |
| O21 base de una versión más nueva | Corregido |

### Bugs nuevos
Ninguno.

**Estado del paso 1c: pruebas automáticas completas. Falta la prueba manual del usuario con su base real.**

---

## Ronda 8 – Paso 2a (lógica de pagos)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: `app/logica/pagos.py` y `formato.formatear_fecha`. RF-13 a RF-15; RN-20 a RN-23; CA-13.1, CA-13.2, CA-14.1, CA-14.2, CA-15.1; CA-09.1 completo; CA-43.5, CA-07.2, CA-45.4 y CA-45.6 con pagos registrados por la función. Sin interfaz.
- Datos: base en memoria, fechas fijas.

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_pagos.py (nuevo) | 52 | 52 | 0 |
| Resto | 644 | 644 | 0 |
| **Total** | **696** | **696** | **0** |

Cobertura: app/logica/ 100 % (incluido pagos.py). Ruff sin errores.

### Bugs
Ninguno.

### Observaciones
- O22: `registrar_pago` acepta un `datetime` (en Python es un tipo de `date`) y guardaría la hora ("2026-10-04T15:30:00"), que `formatear_fecha` mostraría mal. El `ft.DatePicker` de la interfaz devuelve un `datetime`.
- O23 (informativa): `listar_pagos` de un gasto inexistente devuelve una lista vacía en vez de error.

---

## Ronda 9 – Paso 2b (interfaz de pagos)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: columnas Pag. / Pagado / Pendiente, fila de totales, tilde con Deshacer, destildar con confirmación, DialogoPago, DialogoVerPagos y el arreglo de O22.
- Método: página falsa, "hoy" fijo en 04/10/2026, datos inventados.

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_interfaz_pagos.py (nuevo) | 48 | 47 | 1 |
| test_interfaz_gastos.py (actualizado) | 44 | 44 | 0 |
| test_interfaz_ronda5.py (actualizado) | 27 | 27 | 0 |
| test_interfaz_usd.py (actualizado) | 55 | 55 | 0 |
| Resto | 570 | 570 | 0 |
| **Total** | **744** | **743** | **1** |

Cobertura 99 % (1.239 líneas, 1 sin cubrir). Ruff sin errores. Las 19 pruebas que leían celdas por posición ahora buscan la columna por su título (ayudantes nuevos en tests/ayudantes_interfaz.py).

Verificado: O22, tabla y fila de totales (CA-09.1 completo), tilde con Deshacer (CA-13.1), destildar con confirmación (CA-13.2), Registrar pago (CA-14.1, CA-14.2), Ver pagos (CA-15.1) y gastos en USD (CA-43.5).

### Bugs
- **BUG-10** – Si el gasto se borra por detrás entre la confirmación y "Quitar pagos", aparecen "El gasto ya no existe." y también "Se quitaron los pagos de X". Hipótesis: en `_confirmar_quitar_pagos` el `except ErrorDeValidacion` no hace `return`.

### Observaciones
- O24: no se pudo comprobar sin ventana si Flet dispara `on_dismiss` del calendario después de elegir una fecha. Si no lo hace, el calendario queda contado como diálogo abierto: los atajos se ignoran y el primer Esc no cierra "Registrar pago".

### Para que pruebe el usuario con la ventana real
Tilde (y que siga marcado hasta confirmar), "Parcial" y "Pagado" dentro de la fila, calendario y O24, confirmación en la fila de "Ver pagos", "Deshacer" del aviso.

---

## Ronda 10

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Motivo: verificar BUG-10 (no avisar "Se quitaron…" si falló) y O24 (el calendario se marca cerrado al elegir una fecha).

### Resultado
752 pruebas, pasan las 752 (8 nuevas en test_interfaz_pagos.py). Cobertura 99 % (1.241 líneas, 1 sin cubrir). Ruff sin errores.

| Ítem | Estado |
|---|---|
| BUG-10 | Corregido (solo aparece el error y la tabla queda refrescada) |
| O24 | Corregido (después de elegir fecha, un Esc cierra "Registrar pago" y Ctrl+N vuelve a andar; un on_dismiss tardío no rompe nada) |

### Bugs nuevos
Ninguno.

### Observaciones
- O25 (menor): `app.abrir_dialogo` no se fija si el diálogo ya estaba en la lista. Si el calendario se cerrara sin elegir y Flet no avisara, al reabrirlo quedaría anotado dos veces.

**Estado del paso 2: pruebas automáticas completas. Falta la prueba manual del usuario.**

---

## Ronda 11 – Paso 3a (lógica del resumen)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: `formato.convertir_ars_a_usd`, `meses` (exigir_mes, editar_sueldo, editar_cotizacion), `ingresos.py`, `cambios.py`, `configuracion.py` y `resumen.py`. RF-23 a RF-27, RF-35 a RF-37; RN-12 a RN-19, RN-38, RN-39. CA-23.x a CA-27.x (menos CA-27.6, paso 4), CA-35.1, 35.3, 35.4, CA-36.x, CA-37.x y las partes del paso 3 de CA-43.1, 43.2, 43.7 y 45.1.
- Datos: base en memoria, datos inventados, fechas fijas. Valores esperados calculados a mano con las fórmulas de los requisitos.

### Resultado
| Grupo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_resumen.py (nuevo) | 105 | 105 | 0 |
| Resto de la lógica | 493 | 493 | 0 |
| **Lógica, total** | **598** | **598** | **0** |

Cobertura de app/logica/: 100 % (547 líneas). Ruff sin errores. (Las pruebas de interfaz fallan porque el código de la 3b ya cambió la pantalla de inicio a Resumen; se actualizan en la ronda de la 3b.)

### Bugs
Ninguno.

### Observaciones
- O26: con cotización vacía y F = 0 el ahorro se calcula pero la capacidad es None: la pantalla debe mirar `capacidad is None`.
- O27: `avance_meta` puede ser negativo o mayor a 1; la barra se limita en la pantalla.
- Se corrigió una prueba propia de la ronda 6 que dejaba abierta una conexión en memoria.

---

## Ronda 12 – Paso 3b (interfaz del resumen)

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Alcance: barra superior con la cotización y Ctrl/Cmd+K, PantallaResumen, diálogos de sueldo/cotización/meta, DialogoIngreso, DialogoCambio, pestaña "Meta de ahorro" y el menú Resumen / Gastos / Ajustes.
- Método: página falsa, "hoy" fijo en 04/10/2026.

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_interfaz_resumen.py (nuevo) | 88 | 81 | 7 |
| Interfaz actualizada a pantallas por nombre | 263 | 263 | 0 |
| Lógica | 598 | 598 | 0 |
| **Total** | **949** | **942** | **7** |

Cobertura 98 % (1.875 líneas). Ruff sin errores; sin conexiones sin cerrar.

### Bugs
- **BUG-11** – Los diálogos de sueldo, cotización y meta se cierran con un monto inválido ("0", "1600.5", etc.): el error aparece como aviso y se pierde lo escrito. Hipótesis: `_dialogo_un_monto` trata todo error sin campo como "cambió algo por detrás", y `leer_monto` lanza sus errores sin campo.
- **BUG-12** – Con déficit el porcentaje de la meta dice "0 %" en vez del valor real ("-32 %"). Hipótesis: `max(round(avance * 100), 0)`.

### Observaciones
- O28: `round()` de Python redondea las mitades al par (12,5 % → "12 %").
- O29: textos que difieren del diseño ("Dólares a cambiar" vs "USD a cambiar", etc.).
- O30: CA-36.3 se verificó solo en la lógica (elegir otro mes en pantalla llega en el paso 4).

---

## Ronda 13

- Fecha: 2026-10-04 · Probado por: Lucía (QA)
- Motivo: verificar BUG-11 (diálogos de un monto), BUG-12 y O28 (`formatear_porcentaje`). O29 resuelto en el diseño; O30 se prueba en el paso 4.

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_formato.py (+19) | 177 | 175 | 2 |
| test_interfaz_resumen.py (+28) | 116 | 113 | 3 |
| Resto | 703 | 703 | 0 |
| **Total** | **996** | **991** | **5** |

Cobertura 98 %; app/logica/ 100 %. Ruff sin errores; sin conexiones sin cerrar.

| Ítem | Estado |
|---|---|
| BUG-11 | Corregido (17 inválidos en los tres diálogos: el diálogo queda abierto con el error en el campo) |
| BUG-12 | Corregido ("-32 %" con déficit) |
| O28 | Corregido (mitad hacia arriba: 12,5 % → "13 %") |

### Bugs nuevos
- **BUG-13** – Un porcentaje negativo que redondea a cero se ve "-0 %" (ahorro −US$ 0,01 con meta 300). Hipótesis: `Decimal.quantize` conserva el signo del cero.
- **BUG-14** – "La cotización no puede ser negativo." / "La meta no puede ser negativo.": el mensaje no concuerda en género. Hipótesis: `f"{que} no puede ser negativo."` en `leer_monto` y `validar_centavos`.

---

## Ronda 14

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Motivo: verificar BUG-13 (sin "-0 %") y BUG-14 (género en "no puede ser negativo/a").

### Resultado
1.052 pruebas, pasan las 1.052 (56 nuevas). Cobertura 98 %; app/logica/ 100 %. Ruff sin errores; sin conexiones sin cerrar.

| Ítem | Estado |
|---|---|
| BUG-13 (formato y pantalla) | Corregido |
| BUG-14 (lógica y pantalla, todos los diálogos) | Corregido |

### Bugs nuevos
Ninguno.

### Observaciones
- O31 (menor, a futuro): `_negativo` no contempla datos en plural ("Las…"/"Los…") ni un nombre vacío. Hoy todos los nombres de la app son singulares.

**Estado del paso 3: pruebas automáticas completas. Falta la prueba manual del usuario.**

---

## Ronda 15 – Paso 4a (lógica del historial)

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Alcance: `meses.py` (siguiente, anterior, listar_meses, obtener_mes_por_fecha, mes_inicial, sugerencias_mes_siguiente, crear_mes, crear_mes_siguiente, borrar_ultimo_mes). RF-01 a RF-05, RF-47, RN-07 a RN-11, RN-57. CA-01.1, CA-02.1, CA-02.2, CA-03.1 (sin cuotas), CA-03.2, CA-03.3, CA-03.5, CA-03.6 (parte del fijo archivado), CA-05.1, CA-05.3, CA-27.6, CA-36.3 (O30) y CA-47.1 a CA-47.5.

### Resultado
| Grupo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_historial.py (nuevo) | 66 | 64 | 2 |
| Resto de la lógica | 763 | 763 | 0 |
| Interfaz (sin el código nuevo de la 4a) | 289 | 289 | 0 |

Cobertura de app/logica/: 100 %. Ruff sin errores. Con el código de interfaz de la 4a ya cargado fallan 3 pruebas de interfaz viejas (Ctrl+Shift+N ahora abre "Mes nuevo"; ya no existe `_texto_mes`): se actualizan en la ronda de interfaz.

### Bugs
- **BUG-15** – Al crear el mes, un fijo en dólares que se recalcula fuera de rango da un error técnico (`IntegrityError` si da $ 0, `OverflowError` si es enorme) o se copia por encima del tope. Hipótesis: `crear_mes` no valida el resultado de `convertir_usd_a_ars` con `validar_centavos`. Severidad baja (casos extremos); el mes no queda a medias.

### Observaciones
- O32: ver arriba (pruebas de interfaz a actualizar).

---

## Ronda 16 – Paso 4a (interfaz del historial)

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Alcance: arreglo del BUG-15; barra superior (selector de mes, flechas, "Mes nuevo", "Borrar este mes", franja); Alt+←/→ y Ctrl/Cmd+Shift+N; DialogoMesNuevo, confirmar_borrar_mes, seleccionar_mes, mes_vecino, despues_de_borrar_mes y O17. "Hoy" fijo en octubre 2026.
- Nota: la ronda se cortó dos veces por errores 529 del servidor antes de empezar; se retomó sin cambios perdidos.

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_interfaz_historial.py (nuevo) | 52 | 50 | 2 |
| test_historial.py (+4) | 70 | 70 | 0 |
| 3 pruebas viejas de O32 (actualizadas) | 3 | 3 | 0 |
| Resto | 1.049 | 1.049 | 0 |
| **Total** | **1.174** | **1.172** | **2** |

Cobertura 98 %; app/logica/ y aplicacion.py 100 %. Ruff sin errores.

BUG-15: corregido (en la lógica y desde el diálogo, con el error en el campo cotización).

### Bugs nuevos
- **BUG-16** – Con el mes borrado por detrás, Alt+← y las flechas dan `TypeError`. Hipótesis: `mes_vecino` no verifica si el mes existe (como sí hace `refrescar`, O17).
- **BUG-17** – La confirmación de borrar mes une la lista con comas y le falta la "y" antes del último elemento.

### Observaciones
- O33: el texto de §3.9 del diseño sobre fijos en dólares sin cotización contradice RN-57.
- O34: en macOS el tooltip dice "⌘Shift+N"; la convención es "⇧⌘N".

---

## Ronda 17

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Motivo: verificar BUG-16 (`verificar_mes` en cada punto de entrada), BUG-17 (`unir_con_y`) y O34 (atajos con Shift en macOS). O33 resuelto en el diseño.

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_interfaz_historial.py (+35) | 87 | 85 | 2 |
| test_formato.py (+6) | 227 | 227 | 0 |
| Resto | 901 | 901 | 0 |
| **Total** | **1.215** | **1.213** | **2** |

Cobertura 98 %; app/logica/ y aplicacion.py 100 %. Ruff sin errores.

| Ítem | Estado |
|---|---|
| BUG-16 | Corregido en los 13 puntos de entrada pedidos |
| BUG-17 | Corregido |
| O34 | Corregido ("⇧⌘N" en macOS) |

### Bugs nuevos
- **BUG-18** – "Borrar este mes" y "Editar" de un cambio lanzan `ErrorDeValidacion: El mes no existe.` sin atrapar si el mes se borró por detrás. Hipótesis: no llaman a `app.verificar_mes()`. (Búsqueda posterior en el código: también "Editar ingreso", "Borrar ingreso" y "Borrar cambio" usan el mes sin verificarlo.)

---

## Ronda 18

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Motivo: verificar BUG-18 (`verificar_mes` en borrar mes, editar/borrar ingreso y editar/borrar cambio) y agregar una prueba de inventario contra acciones nuevas sin protección.

### Resultado
1.236 pruebas, pasan las 1.236 (21 nuevas). Cobertura 98 %; app/logica/ y aplicacion.py 100 %. Ruff sin errores.

- BUG-18: corregido en los 5 puntos de entrada (mes borrado por detrás, único mes borrado y mes existente).
- Inventario: `test_inventario_ninguna_accion_rompe_con_el_mes_borrado` dispara todas las acciones de la barra superior, el menú lateral y las pantallas Resumen (15), Gastos (26) y Ajustes (10) con el mes borrado, y exige que ninguna falle. Se comprobó que detecta una acción sin protección (con `verificar_mes` desactivado encuentra "Borrar este mes").

### Bugs nuevos
Ninguno.

### Observaciones
- O35 (menor): "Mes nuevo" no llama a `verificar_mes`; no se rompe (crea el siguiente al último que existe), pero la pantalla de atrás sigue mostrando el mes borrado mientras el diálogo está abierto. Se deja como está.

**Estado de la parte 4a: pruebas automáticas completas. Falta la prueba manual del usuario.**

---

## Ronda 19 – Paso 4b (lógica de cuotas)

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Alcance: `cuotas.py` (funciones puras, consultas, alta, edición, cancelación, sincronización y generación al crear un mes), `meses.crear_mes` con cuotas y la clave "cuotas" de las sugerencias, `gastos.borrar_gasto` (cuota omitida) y `gastos.totales_por_medio`. RF-16 a RF-22, RN-24 a RN-31, RN-52. CA-16.x a CA-22.x, CA-08.2, CA-08.3, CA-03.1 (cuota), CA-03.4, CA-03.6 (cuota con medio archivado) y CA-37.x con planes reales.

### Resultado
| Grupo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_cuotas.py (nuevo) | 111 | 109 | 2 |
| test_historial.py (sugerencias actualizadas) | 70 | 70 | 0 |
| Resto de la lógica | 667 | 667 | 0 |
| **Lógica, total** | **848** | **846** | **2** |

Cobertura: cuotas.py, gastos.py y meses.py al 100 %. Ruff sin errores. (79 pruebas de interfaz viejas fallan porque ya entró la interfaz de la 4b: se actualizan en la ronda de interfaz.)

### Bugs
- **BUG-19** – Cancelar un plan ya terminado (o que todavía no empezó) le cambia la "última cuota" a un mes sin cuota (ej. plan de ene–mar cancelado en octubre → última 2026-09). Hipótesis: `cancelar_plan` no mira el estado y `ultima_cuota` de un cancelado no se limita a la última real.
- **BUG-20** – `listar_planes` no ignora los acentos al ordenar (usa `ORDER BY … COLLATE NOCASE`).

### Observaciones
- O36: ver arriba (pruebas de interfaz a actualizar).

---

## Ronda 20 – Paso 4b (interfaz de cuotas)

- Fecha: 2026-10-05 · Probado por: Lucía (QA)
- Alcance: arreglos de BUG-19 y BUG-20; pantalla Cuotas, DialogoPlan, cuotas en Gastos ("Cuota n/N", editar, borrar), tarjeta "Por medio de pago", cuotas en "Mes nuevo"; menú con 4 destinos; Cuotas en el inventario de acciones. (La ronda se cortó una vez por el límite de uso y se retomó.)

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_interfaz_cuotas.py (nuevo) | 52 | 51 | 1 |
| test_cuotas.py (+8) | 119 | 119 | 0 |
| test_interfaz_historial.py (+1) | 109 | 108 | 1 |
| **Total** | **1.409** | **1.407** | **2** |

Cobertura 98 %; app/logica/ 100 %. Ruff sin errores. Las 79 pruebas viejas de O36 pasan (la tabla de gastos se busca por su primera columna; navegación con 4 destinos).

| Ítem | Estado |
|---|---|
| BUG-19 (lógica y pantalla) | Corregido |
| BUG-20 | Corregido |

### Bugs nuevos
- **BUG-21** – El texto de ayuda de "Por medio de pago" es la versión anterior a los gastos en dólares (§3.3).
- **BUG-22** – En Cuotas, cambiar el filtro con el mes visto borrado por detrás da `TypeError`. Lo encontró el inventario de acciones. Hipótesis: `_cambiar_filtro` llama al `refrescar` de la pantalla sin `verificar_mes`.

### Observaciones
- O37: "Nuevo plan" en Cuotas no llama a `verificar_mes` (el botón de Gastos sí). No rompe.
- O38: el aviso al editar un plan difiere del ejemplo del diseño ("ej."): no es bug.

---

## Ronda 21

- Fecha: 2026-10-06 · Probado por: Lucía (QA)
- Motivo: verificar BUG-21 (texto de "Por medio de pago"), BUG-22 (filtro de Cuotas con el mes borrado) y O37 ("Nuevo plan" verifica el mes). O38 queda como está.

### Resultado
1.420 pruebas, pasan las 1.420 (11 nuevas). Cobertura 98 %. Ruff sin errores. El inventario de acciones pasa en las 4 pantallas: Resumen (15), Gastos (33), Cuotas (16) y Ajustes (10).

| Ítem | Estado |
|---|---|
| BUG-21 | Corregido |
| BUG-22 | Corregido (el filtro elegido se respeta al pasar al último mes) |
| O37 | Corregido |

### Bugs nuevos
Ninguno.

### Observaciones
- O39 (informativa): el filtro de Cuotas se mantiene al cambiar de mes y de pantalla; vuelve a "Activos" solo si la pantalla se arma de nuevo (primer uso). Comportamiento esperado.

**Estado del paso 4: pruebas automáticas completas.** La prueba manual del usuario queda pendiente porque Windows bloquea la ventana de Flet en este equipo (Control de aplicaciones).

---

## Ronda 22 – Paso 5a (lógica de compartidos)

- Fecha: 2026-10-06 · Probado por: Lucía (QA)
- Alcance: `compartidos.py`, `me_deben.py`, `gastos.agregar_gasto`/`editar_gasto` con partes, `meses.crear_mes(…, avisos)` y `total_me_deben` en el resumen. RF-28 a RF-34, RN-32 a RN-37, RN-40. CA-28.x (lógica), CA-29.x a CA-34.x, CA-35.2, CA-05.2, CA-43.6 (partes), CA-45.7 y CA-47.6 a CA-47.8.

### Resultado
1.498 pruebas, pasan las 1.498 (78 nuevas en test_compartidos.py). app/logica/ al 100 %. Ruff sin errores.

### Bugs
Ninguno.

### Observaciones
- O40: si se saca a una persona de un gasto compartido cuya parte ya estaba cobrada, la parte (y lo cobrado) desaparece de "me deben". Los requisitos no lo definen.
- O41: si una parte con diferencia ("a devolver $ 2.900") se marca y se desmarca, lo ya cobrado vuelve a 0 y se pierde ese registro.

---

## Ronda 23 – Paso 5b (interfaz de compartidos)

- Fecha: 2026-10-06 · Probado por: Lucía (QA)
- Alcance: O41 en la lógica, `formatear_mes_corto`, `personas_compartido`; sección "Compartido" del diálogo de gasto; ícono y texto al borrar en Gastos; pantalla Me deben; DialogoItem; pestaña Personas; tarjeta "Te deben"; textos al crear y borrar el mes; "Me deben" en el inventario de acciones. (La ronda se cortó una vez por el límite de uso y se retomó.)

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_interfaz_compartidos.py (nuevo) | 62 | 62 | 0 |
| test_interfaz_historial.py (+1) | 110 | 110 | 0 |
| Pruebas viejas actualizadas | 11 | 11 | 0 |
| **Total** | **1.562** | **1.562** | **0** |

Cobertura 97 %; app/logica/ 100 %. Ruff sin errores. El inventario pasa en las 5 pantallas: Resumen (15), Gastos (39), Cuotas (16), Me deben (13) y Ajustes (38).

Verificado en pantalla: CA-28.x, 29.x, 30.x, 31.x, 32.x, 33.x, 34.x, 35.2, 05.2, 43.6, 45.7, 47.8; O40 (aviso al sacar a alguien que ya pagó) y O41 ("Deshacer" restaura exactamente).

### Bugs nuevos
Ninguno.

### Observaciones
- O42 (informativa): el tooltip y el texto de borrar listan las personas en el orden en que se guardaron las partes (desde el diálogo, alfabético).
- O43 (informativa): "Archivada" en la tarjeta es un texto chico, no un chip.

**Estado del paso 5: pruebas automáticas completas.** La prueba manual queda pendiente (ventana bloqueada por Windows).

---

## Ronda 24 – Pasos 6 y 7 (previsión y gráficos)

- Fecha: 2026-10-06 · Probado por: Lucía (QA)
- Alcance: lógica (`prevision.py`, `graficos.py`, tema en `configuracion.py`) e interfaz (pantallas Previsión y Gráficos, pestaña Apariencia, menú con 7 destinos). RF-38 a RF-42, RN-41 a RN-48. CA-38.1 a 38.11, CA-39.1, 39.2, CA-40.1, CA-41.1 a 41.3, CA-42.1. (La ronda se cortó una vez por el límite de uso y se retomó ampliada.)

### Resultado
| Archivo | Pruebas | Pasan | Fallan |
|---|---|---|---|
| test_prevision.py (nuevo) | 37 | 37 | 0 |
| test_tema.py (nuevo) | 18 | 18 | 0 |
| test_interfaz_prevision_graficos.py (nuevo) | 63 | 62 | 1 |
| **Total de la suite** | **1.684** | **1.683** | **1** |

Cobertura 97 %; prevision.py, graficos.py, configuracion.py, pantalla_prevision.py, pantalla_graficos.py, estilos.py y aplicacion.py al 100 %. Ruff sin errores. El inventario de acciones incluye Previsión (8) y Gráficos (7).

### Bugs nuevos
- **BUG-23** – Al elegir un tema, la app vuelve a la pestaña "Categorías" de Ajustes en vez de quedarse en "Apariencia". Hipótesis: `mostrar_principal` crea una `PantallaAjustes` nueva que arranca en la primera pestaña.

### Observaciones
- O44: el encabezado "Dólares a cambiar" difiere del boceto de §3.7 ("USD a cambiar").
- O45: textos de requisitos (CA-39.1 "+41.117 libres", CA-38.7 "Creá el mes 2026-10") difieren del diseño y la pantalla ("Avant +$ 41.117", "Octubre 2026").
- O46: "Cargar cotización" y "Mes nuevo" de Previsión no entran en el inventario (están cubiertos por pruebas propias).
- O47: en casos límite, una barra negativa podría salirse 1 px de su zona por redondeos separados.

---

## Ronda 25 – Verificación final de los pasos 6 y 7

- Fecha: 2026-10-06 · Probado por: Lucía (QA)
- Motivo: verificar BUG-23 (al elegir un tema se perdía la pestaña Apariencia) y O47 (barras que podían salirse de su zona). O44 y O45 resueltos en los documentos; O46 queda como está.

### Resultado
1.704 pruebas, pasan las 1.704 (20 nuevas). Cobertura 97 %. Ruff sin errores.

| Ítem | Estado |
|---|---|
| BUG-23 | Corregido (la opción queda marcada, en la pestaña Apariencia; también con el mes borrado por detrás) |
| O47 | Corregido (11 combinaciones fijas y un barrido de 169 pares: ninguna barra supera su zona) |

### Bugs nuevos
Ninguno.

### Observaciones
- O48: un valor muy chico frente a otro muy grande (ej. déficit de US$ 0,01 frente a un ahorro de US$ 1.200) queda con barra de 0 px; el dato sigue en el tooltip y en "Ver como tabla". Se deja como está.

**Estado de los pasos 6 y 7: pruebas automáticas completas. La app queda completa según los requisitos de la v1.** La prueba manual queda pendiente (ventana bloqueada por Windows).

## Ronda 26 – Abrir con doble clic (Gastos.exe + modo Edge)

### Qué se probó
56 pruebas nuevas, sin abrir Edge ni el .exe reales (todo simulado con monkeypatch).

- **tests/test_modo_edge.py (39):** comando_edge, puerto_libre, esperar_servidor (escuchando, sin nadie, servidor que arranca tarde), carpeta_perfil (con, sin y con LOCALAPPDATA vacía), buscar_edge, puerto_en_uso (archivo inexistente, carpeta, texto inválido, "0", puerto muerto, puerto vivo con espacios), ejecutar (sin Edge, app ya abierta, caso normal, puerto.txt viejo), el hilo que abre Edge (cierre normal, servidor que no arranca, puerto.txt ya borrado) y main.py con y sin --edge.
- **tests/test_lanzador.py (17):** buscar_proyecto (carpeta del exe, ruta guardada con espacios y ñ, carpeta sin main.py), carpeta_del_exe, avisos sin proyecto y sin pythonw.exe, comando de lanzamiento (cwd, PYTHONUTF8, DETACHED_PROCESS, log), construir_exe (la línea RUTA_PROYECTO coincide con la que se reemplaza; la copia en build/ tiene la ruta real; opciones de PyInstaller; --escritorio; si PyInstaller falla no copia nada), .gitignore, requirements.txt y el .command de macOS.

### Resultado
1.760 pruebas: pasan 1.756, fallan 4 (BUG-24). Cobertura de app/: 97 % (modo_edge.py: 100 %). La app sin --edge sigue igual.

### Bugs nuevos
- **BUG-24:** si `%LOCALAPPDATA%\gastos-app\puerto.txt` tiene un número fuera de rango (70000, -1, 99999999999), `esperar_servidor` lanza `OverflowError: connect_ex(): port must be 0-65535` y la app no abre (el error solo queda en `%TEMP%\gastos-app.log`) hasta borrar el archivo a mano. Esperado: tratarlo como "no hay app abierta". Gravedad baja. Pruebas: `test_puerto_en_uso_numero_fuera_de_rango` (3 casos) y `test_bug24_ejecutar_con_puerto_txt_fuera_de_rango`.

### Revisión de docs/como-abrir.md
- D1: busca primero la carpeta del exe y después la ruta guardada al armarlo (no siempre `C:\Proyectos\gastos-app`).
- D2: "Desde una terminal" usa rutas de Windows; en macOS es `.venv/bin/python`, y `--edge` ahí abre el navegador predeterminado, no Edge.
- D3: sin Edge, cerrar la pestaña no cierra la app (queda corriendo escondida con pythonw).

### Observaciones
- O49: `esperar_servidor` con puerto cerrado tarda ~2 s por intento en Windows (el socket no tiene timeout): pasa el límite y demora la apertura con un puerto.txt viejo.
- O50: el lanzador abre el log con "w": un segundo doble clic borra el detalle del primer arranque.
- O51: cada ventana de Edge es una sesión de Flet con su conexión; dos ventanas no se refrescan entre sí (las protecciones BUG-16/18 cubren el caso de datos cambiados por detrás).
- O52: carreras con puerto.txt (dos dobles clics casi simultáneos; otro programa en el puerto de un puerto.txt viejo). Casos raros.
- O53: si existen las variables FLET_SERVER_IP o FLET_SERVER_PORT, Flet las usa por encima de host/port.

---

## Ronda 27 – Verificación de las correcciones de la ronda 26 (Abrir con doble clic)

- Fecha: 2026-10-12 · Probado por: Lucía (QA)
- Motivo: verificar BUG-24 (puerto.txt con un número fuera de rango), O49 (límite de tiempo por intento en `esperar_servidor`), O50 (el log se agrega en vez de pisarse) y D1, D2, D3 en docs/como-abrir.md. También se verificó O53 (variables FLET_SERVER_IP / FLET_SERVER_PORT), que se corrigió en el mismo cambio.

### Qué se probó
20 pruebas nuevas, todo simulado con monkeypatch (sin abrir Edge ni el .exe).

- **tests/test_modo_edge.py (+17):** bordes del rango de puertos (1, 65535, 65536, 0, "-0", "+5000", "1_000", " 65535\n"): solo se intenta conectar entre 1 y 65535; 65535 vivo se devuelve; 1, 65535 y 65536 con sockets reales sin error. O49: `settimeout(0.3)` va antes de cada `connect_ex`, en cada socket nuevo; con un puerto cerrado y 1 s de límite termina en ~1,0 s (medido: 0,49 s con límite 0,3; 1,0 s con 1; 2,04 s con 2); un puerto.txt viejo demora como mucho ~1 s; con límite 0 no crea sockets. O53: las dos variables se quitan antes de `ft.run`.
- **tests/test_lanzador.py (+3):** O50: el log se abre con "a" y en UTF-8; lo que había (con tildes) se conserva; dos dobles clics dejan las dos líneas en orden; sin log previo lo crea vacío.
- Sockets simulados: en toda la suite hay uno solo (`test_esperar_servidor_que_arranca_tarde`), ya actualizado. Las demás pruebas usan sockets reales y no necesitan cambios.

### Resultado
1.780 pruebas, pasan las 1.780 (20 nuevas). Cobertura de app/ 97 % (modo_edge.py: 100 %). Ruff no se pudo correr: Windows (Control de aplicaciones) bloquea ruff.exe (WinError 4551). Es una limitación del equipo, no un bug; las líneas nuevas se revisaron a mano.

| Ítem | Estado |
|---|---|
| BUG-24 | Corregido (las 4 pruebas de la ronda 26 pasan; bordes 1 y 65535 se consultan, 0 y 65536 no) |
| O49 | Corregido (límite de 0,3 s antes de cada intento; el tiempo total respeta el límite pedido) |
| O50 | Corregido (log en modo "a", se conserva el contenido anterior) |
| O53 | Corregido (FLET_SERVER_IP y FLET_SERVER_PORT se quitan antes de arrancar) |
| D1 | Corregido (primero la carpeta del .exe, después la ruta guardada al armarlo) |
| D2 | Corregido (sección de macOS con `.venv/bin/python` y aclaración de que `--edge` abre el navegador predeterminado) |
| D3 | Corregido (sin Edge, cerrar la pestaña no cierra la app; cómo cerrarla desde el Administrador de tareas) |

### Bugs nuevos
Ninguno.

### Observaciones
- O54 (documentación, baja): como-abrir.md dice "Doble clic con la app ya abierta: se abre otra ventana de la misma app". Es cierto con Edge. Sin Edge, `ejecutar` no usa puerto.txt, así que cada doble clic arranca otra copia de la app (otro `pythonw.exe` escondido) sobre los mismos datos. Las protecciones BUG-16/18 cubren los datos cambiados por detrás. El caso es raro, porque Edge viene con Windows. Se sugiere aclararlo en esa línea o en la de "Si Edge no estuviera instalado".

---

## Ronda 28 (2026-10-12): verificación de O54 (documentación)

### Qué se revisó
El texto nuevo de docs/como-abrir.md ("Doble clic con la app ya abierta"), comparado con `ejecutar` en app/interfaz/modo_edge.py y con la observación O54 de la ronda 27.

### Qué se probó
- Lectura del código: sin Edge, `ejecutar` llama a `ft.run(..., view=WEB_BROWSER)` y vuelve, sin consultar puerto.txt ni reutilizar la app abierta. Con Edge, `puerto_en_uso` detecta la app y solo se abre otra ventana.
- Ejecución (con `buscar_edge`, `ft.run` y `Popen` simulados): dos llamadas seguidas a `ejecutar` sin Edge hacen 2 llamadas a `ft.run`, 0 consultas a `puerto_en_uso` y 0 ventanas de Edge. Es decir, cada doble clic arranca otra copia de la app.
- Suite completa con `pytest --cov=app`. No se escribieron pruebas nuevas (solo cambió documentación).

### Resultado
1.780 pruebas, pasan las 1.780. Cobertura de app/ 97 %.

| Ítem | Estado |
|---|---|
| O54 | Corregida: el texto coincide con el comportamiento real (con Edge, otra ventana; sin Edge, otra copia con otro `pythonw.exe` escondido sobre los mismos datos) y con lo que describía O54 |

### Bugs nuevos
Ninguno.

---

## Ronda 29 (2026-10-13): paso 8a-1, bloques `with con:` anidados (RN-76, todo o nada)

### Qué se revisó
La clase nueva `Conexion` de app/logica/base_datos.py (subclase de sqlite3.Connection, usada por `conectar()` con `factory=Conexion`): BEGIN explícito en el nivel 0, SAVEPOINT `nivel_N` en los internos, commit/rollback solo en el más externo.

### Qué se probó (29 pruebas nuevas en tests/test_transacciones.py)
- Bloque externo que falla después de usar funciones reales (catalogos.crear, agregar_gasto con partes, registrar_pago, crear_plan con sus cuotas generadas, agregar_item, crear_mes): no queda nada en ninguna tabla. Variante con ErrorDeValidacion real (monto negativo en el segundo gasto).
- Bloque externo exitoso: queda todo (gastos, pagos, plan, cuotas generadas, partes, me deben, 2 meses, catálogos).
- Error en bloque interno DESPUÉS de un INSERT (monkeypatch de `compartidos.guardar_partes`, que se llama tras el INSERT del gasto; y una violación de clave foránea real), atrapado afuera: se deshace solo el interno y el resto se guarda. Si el error no se atrapa, se deshace todo. Un interno ya liberado también se deshace si falla el externo después.
- Tres niveles: todo bien; falla el 3.º atrapado en el 2.º; falla el 2.º con el 3.º ya liberado; falla todo hasta afuera.
- `_nivel` vuelve a 0 e `in_transaction` a False tras éxito y tras error; la conexión sigue usable; 50 repeticiones sin savepoints colgados.
- Sin anidar: guarda al terminar, deshace y propaga el error, `with con as c` devuelve la misma conexión, transacción ya abierta a mano antes del with.
- Base en archivo (tmp_path): lo deshecho no queda al reabrir; lo interno deshecho no queda y lo externo sí; otra conexión no ve nada hasta el commit externo; importación simulada completa que falla no deja rastro tras reabrir.
- crear_tablas / actualizar_estructura: base nueva en archivo y reapertura, base v0 migrada (nivel 0, sin transacción abierta, versión actual), y bloques anidados sobre la base migrada. Además pasan sin cambios las pruebas de tests/test_migracion.py.

### Resultado
1.809 pruebas, pasan las 1.809 (29 nuevas; las 1.780 anteriores siguen verdes). Cobertura de app/ 97 %. Ruff no se pudo correr: Windows (Control de aplicaciones) bloquea ruff.exe (WinError 4551). Es una limitación del equipo, no un bug; las líneas nuevas se revisaron a mano.

### Bugs nuevos
Ninguno.

### Observaciones
- O55 (baja, a tener en cuenta en 8a-2): un `con.commit()` o `con.rollback()` manual dentro de un bloque interno cierra la transacción y el RELEASE posterior falla con `sqlite3.OperationalError: no such savepoint: nivel_1`. El nivel igual vuelve a 0 y la conexión queda usable. Reproducir: `with c: with c: c.execute("INSERT ..."); c.commit()`. Hoy ninguna función de app/ hace commit/rollback dentro de un `with` (solo `actualizar_estructura`, que no usa `with`), así que no afecta al código actual.
- O56 (baja): `crear_tablas` usa `executescript`, que hace commit implícito, dentro de su `with con:`. Funciona porque se llama desde `conectar()` en nivel 0. Si algún día se llamara dentro de un bloque externo, ese commit rompería el todo o nada. No hay llamadas así hoy; conviene no hacerlo en la importación.
- O57 (baja): `_nivel` es un contador de la conexión, no por hilo. La app usa un solo usuario y `check_same_thread=False`; si dos hilos entraran a un `with` a la vez los niveles se mezclarían. No se probó con hilos por no ser un caso de uso actual.
- La importación debe hacerse con `with con:` externo y llamar a las funciones de la lógica adentro; los respaldos (`hacer_respaldo`/`backup`) no se deben hacer dentro del bloque.

---

## Ronda 30 (2026-10-14): paso 8a-2, leer el Excel (app/logica/importar_excel.py)

### Qué se revisó
El módulo nuevo `app/logica/importar_excel.py`, que solo LEE el .xlsx: `es_nombre_xlsx`, `abrir_libro`, `LibroExcel.hojas()` / `leer_hoja()`, `FilaDetectada`, `HojaLeida`, `clasificar`, `leer_numero_texto` y `normalizar`. Contra docs/requisitos.md §4.12 (RN-60 a RN-65 y RN-67) y los CA de lectura del Módulo K: CA-50.1 (hojas), CA-51.1 a CA-51.8, CA-58.1 a CA-58.3 (y CA-58.4 simulado). Quedan fuera, por ser de 8a-3 y 8a-4: tipos propuestos, notas, mensaje de pagado mayor que monto, interpretación de cobrado, lista de revisión y guardado.

### Qué se probó (244 pruebas nuevas en tests/test_importar_excel.py; ayudantes en tests/ayudantes_excel.py)
Los archivos se generan con openpyxl (`planilla-prueba.xlsx` celda por celda, y variantes); nunca se usa datos-privados/.
- Nombre de archivo (RN-60): .xlsx en cualquier mayúscula; rechazo de .xls, .xlsm, .xlsb, .csv, .ods, .txt, ".xlsx.txt", vacío.
- Archivo ilegible (CA-58.1): bytes vacíos, .txt y .csv renombrados, OLE (.xls viejo o con contraseña), cabecera zip sola, .xlsx cortado (100 bytes, mitad, sin el final), zip válido sin contenido de Excel. Archivo dañado por dentro: XML roto en hoja / workbook / content types / estilos, hoja interna de 0 bytes, bytes comprimidos rotos y 300 alteraciones al azar (semilla fija).
- Solo lectura (RN-60, CA-50.2): los bytes no cambian y no se crea nada en disco.
- Hojas (CA-50.1, CA-58.2): una hoja, varias en orden, solo trae las filas de la hoja elegida, hojas vacías no se ofrecen, hoja oculta, hoja de gráfico (chartsheet), hoja con solo un gráfico, hoja con datos y gráfico, hoja vacía, hoja con solo fechas / horas / espacios, hoja con solo textos, hoja inexistente.
- Números (RN-61, RN-62, CA-51.3): 20 textos válidos y 33 inválidos para `leer_numero_texto` ("82.000", "1.050.000", "66.020,12", "$ 41.116,66", "41116,66", "-5.000", "82.5", "1.5000", "3/3", "US$ 20", etc.); números de Excel (41116,66; 22093,666 -> 2209367; 0,1+0,2; 1,005; enteros grandes); booleanos, fechas, horas y los 7 errores de Excel como vacíos; "Nafta | 82.5" en dos filas incompletas; fecha en la columna del monto.
- planilla-prueba.xlsx completa (CA-51.1, CA-51.2): las 13 filas de la lista principal con fila, monto y pagado; las 16 incompletas exactas (nombre, fila, columna); el 66021 no aparece; orden de lectura; 29 filas en total.
- Filas ocultas (CA-51.4), columna oculta, filas vacías, datos lejos de A1 (Z100).
- Pagado (CA-51.5): 9 encabezados reconocidos (Pago, Pagos, Abonado, ABONADO, con espacios y acentos), 6 no reconocidos (Pagué, Pagado?...), la "x" junto a Servicios, "Falta por pagar" cierra la columna, E11 = "Pagado" trae pagado 66.021 a Monotributo.
- Cobrado (CA-51.6, solo valor crudo): 20000 / "x" / 3000 en la fila correcta, "no" en F22, "Cobrado" en F21 y F26 como encabezados, número en fila de gasto, variantes del encabezado.
- Bloques (CA-51.7, CA-51.8): bloques de la planilla, títulos, filas pegadas, conteo 5/3/3/2, Excel sin títulos, fila nueva "Concepto/Importe", fila vacía entre título y filas, título "Préstamos", título combinado B1:C1 que cubre dos columnas, "Deudas sofia" combinada D21:E21 (CA-52.4, lectura), celdas combinadas con las otras celdas vacías.
- Fórmulas (CA-58.3, CA-58.4): sin valor guardado (cuenta, ejemplo "D3", primera en orden de lectura, columna "AA7"); con valor guardado (número, 0, texto, texto numérico, error, booleano), mezcla de con y sin valor.
- `normalizar` (RN-67): mayúsculas, acentos, espacios repetidos, tabulaciones y espacios duros.
- Otros: nombres con ñ y emoji, texto de 5.000 caracteres, saltos de línea, 3.000 filas, celda con formato en la fila 30.000.

### Resultado
2.053 pruebas en total: pasan 2.042, fallan 10, 1 omitida (pendiente). Cobertura de app/ 98 %; `importar_excel.py` 100 %. Del archivo nuevo: 244 pruebas, 233 pasan, 10 fallan, 1 omitida. Las 1.809 anteriores siguen verdes.

Todos los CA de lectura pasan (CA-50.1, CA-51.1 a CA-51.8, CA-58.1 con archivos cortados, CA-58.2, CA-58.3), salvo lo que explican los bugs de abajo.

### Bugs
- **BUG-25 (media): `abrir_libro` deja escapar excepciones con un .xlsx dañado por dentro.** Atrapa `BadZipFile, KeyError, ValueError, OSError, TypeError`, pero un .xlsx con un XML interno roto lanza `xml.etree.ElementTree.ParseError` (es un `SyntaxError`), con datos comprimidos rotos lanza `zlib.error`, con una cabecera zip alterada `NotImplementedError`, y con un estilo fuera de rango `IndexError`. En vez del mensaje de RN-60 se vería un error sin controlar. En 300 alteraciones al azar de un .xlsx válido escaparon 114 (109 `zlib.error` y 5 `NotImplementedError`). Reproducir: `abrir_libro(reemplazar_en_zip(xlsx({"C3": "Luz"}), "xl/worksheets/sheet1.xml", b"<<< no es xml"))`. Esperado: `ErrorDeValidacion` con `MENSAJE_ARCHIVO_INVALIDO`. Causa: la lista de excepciones del `except` en `abrir_libro` es corta; openpyxl no define una excepción propia para estos casos. Pruebas: `test_abrir_libro_xlsx_danado_por_dentro_con_xml_roto` (4 casos), `test_abrir_libro_xlsx_con_hoja_en_blanco_interna`, `test_abrir_libro_xlsx_con_datos_comprimidos_rotos`, `test_abrir_libro_bytes_alterados_al_azar_nunca_escapa_otra_excepcion`. CA-58.1 pide el mensaje para un .xlsx "cortado", y eso sí pasa; falla el dañado por dentro (RN-60: "dañado").
- **BUG-26 (media-baja): una fórmula que devuelve texto vacío se cuenta como "sin valor calculado".** Excel guarda `=SI(A1>0;A1;"")` con `<v></v>`. openpyxl lo lee como `None`, y `leer_hoja` lo confunde con una fórmula nunca calculada. Resultado: aviso falso "Hay N fórmulas sin valor calculado... Abrí el archivo en Excel, guardalo y volvé a importarlo" en un archivo que ya estaba guardado por Excel (y el usuario no puede arreglarlo). Reproducir: `con_valores_guardados(xlsx({"C3": "Luz", "D3": '=IF(1>2,5,"")'}), {"D3": ("str", "")})` y leer la hoja: `formulas_sin_valor == 1`, esperado 0. Causa: `leer_hoja` trata como "sin valor" toda celda con fórmula cuyo valor es `None`, sin distinguir si el XML trae un `<v>` vacío de tipo `str`. Prueba: `test_formula_con_resultado_texto_vacio_guardado_no_es_sin_valor`. Nota: el archivo se simula tocando el XML de openpyxl; conviene confirmarlo con un archivo real de Excel (ver pendientes).
- **BUG-27 (baja): una hoja que solo tiene fórmulas sin valor guardado no se ofrece.** `hojas()` mira los valores con `data_only=True`, así que esas celdas son `None` y la hoja queda fuera: el usuario nunca ve el aviso de fórmulas sin valor calculado (RN-61); si es la única hoja, la app no tiene hojas para ofrecer. Reproducir: `abrir_libro(xlsx({"D3": "=100+200", "D4": "=1+1"})).hojas()` devuelve `[]`, esperado `["Octubre"]`. Prueba: `test_hojas_solo_con_formulas_sin_valor_se_ofrece`. Caso raro (un archivo hecho por otro programa y con solo fórmulas).
- **BUG-28 (baja, hoy no se alcanza desde un archivo): `clasificar` con `inf` o `nan` lanza `decimal.InvalidOperation`.** `_a_centavos` no los contempla. Desde un .xlsx no llega: openpyxl ya rechaza `<v>inf</v>` / `<v>nan</v>` (da `ValueError`, que `abrir_libro` atrapa). Se reporta porque la función es pública. Prueba: `test_clasificar_infinito_y_nan_no_rompen`.

### Observaciones
- O58 (rendimiento, baja): `leer_hoja` recorre todas las filas hasta la última celda con algo, aunque esté vacía y solo tenga formato. Medido: una celda con relleno en la fila 20.000 (columna T) tarda 1,2 s en leerse; en la fila 100.000, 6,4 s. En la fila 1.048.576 (el máximo de Excel) sería del orden de un minuto o más, con mucha memoria (extrapolado, no medido). Pasa con planillas a las que se les dio formato hasta abajo. `hojas()` recorre lo mismo. Mejora posible: leer con `read_only=True` o ignorar las celdas vacías al armar la grilla.
- O59: `leer_hoja("NoExiste")` lanza `KeyError` (hoy solo se la llamaría con nombres de `hojas()`). Probado para dejarlo documentado.
- O60: una hoja oculta con datos se ofrece como cualquier otra. RN-60 no dice nada; se documenta con una prueba.
- O61 (para 8a-3): `clasificar` no pone tope: un entero de 10^17 pesos da 10^19 centavos, mayor que `MONTO_MAXIMO_CENT` (999.999.999.999,00) y que el entero de 64 bits de SQLite. La validación de RN-68/RN-05 debe rechazarlo en la revisión y no al guardar.
- O62 (para 8a-3): un número en la columna de pagado junto a una fila sin monto ("Luz" sin monto y un 3 en "Pagado") queda como `pagado_cent=300` de una fila incompleta. RN-63/RN-64 no lo definen; hay que decidir si se descarta.
- O63: con E11 = "Pagado" (CA-51.5), la columna E vuelve a ser de pagado desde la fila 12 y también traen pagado Prestamo MP (20.000), Internet (12.900), Total (32.900), tacones (6.785) y el segundo Total. Es coherente con RN-64 al pie de la letra (el encabezado de E22 es el "Pagado" de E11) y CA-51.5 solo afirma lo de Monotributo; conviene que Ana confirme que es lo esperado.
- O64: los .xlsx de las pruebas los escribe openpyxl, que guarda los textos "en línea" (`inlineStr`); Excel usa cadenas compartidas. La lectura es de openpyxl en los dos casos, pero solo un archivo real lo confirma.

### Pendiente
- CA-52.5 / CA-58.4 con un archivo guardado por Excel o LibreOffice (fórmulas con valor guardado, cadenas compartidas, celdas combinadas reales, `SUM` con valor calculado): no se puede generar desde acá. Hay una prueba omitida (`test_pendiente_archivo_real_guardado_por_excel`). El usuario va a armar `tests/formulas-guardadas-excel.xlsx` con "Luz" en C3 y `=100+200` en D3 (más una fórmula que devuelva "" para confirmar BUG-26). Mientras tanto, `con_valores_guardados` simula el valor guardado editando el XML.
- No se probó 8a-3 ni 8a-4 (tipos propuestos, notas, lista de revisión, guardado).

### Limitaciones
- Ruff no se pudo correr: Windows (Control de aplicaciones) bloquea ruff.exe. Las líneas nuevas se revisaron a mano.

---

## Ronda 31 (2026-10-14): verificación de BUG-25 a BUG-28 y O58 (importar_excel.py)

### Qué se revisó
Las correcciones en `app/logica/importar_excel.py`: `abrir_libro` atrapa cualquier `Exception` (BUG-25); una fórmula sin valor se cuenta solo si el valor es `None` y el `data_type` del libro de valores es "n" (BUG-26); `hojas()` mira el libro de fórmulas (BUG-27); `clasificar` devuelve vacío con inf, -inf y nan (BUG-28); `leer_hoja` recorre las dos hojas a la par con `zip(strict=True)` (O58).

### Qué se probó (13 pruebas nuevas en tests/test_importar_excel.py, sección "Ronda 31")
- Las 10 pruebas que fallaban en la ronda 30 ahora pasan, sin cambiarlas: XML roto en hoja / workbook / content types / estilos, hoja de 0 bytes, datos comprimidos rotos, 300 alteraciones al azar (0 escapes), hojas con solo fórmulas, inf / nan, fórmula con resultado "".
- BUG-25: la causa original queda en `__cause__`; pasar `None`, un `str` o un `int` en vez de bytes también da el mensaje.
- BUG-26: error ("e"), booleano ("b"), texto vacío ("str"), número y 0 guardados no cuentan; solo cuenta la fórmula sin valor, y el ejemplo es esa celda. Una celda vacía común nunca cuenta como fórmula.
- BUG-27: una hoja de solo fórmulas se ofrece, una vacía sigue sin ofrecerse, y la hoja de fórmulas se lee como sin datos con 1 fórmula sin valor.
- BUG-28: inf, -inf y nan dan vacío.
- O58, `zip(strict=True)`: hoja con solo formato lejos, combinadas más filas y columnas ocultas más formato lejos más fórmula sin valor, y la planilla completa con relleno en celdas vacías. Ninguna dio error por dimensiones distintas, y la planilla da el mismo resultado que sin relleno.

### Resultado
2.066 pruebas: pasan 2.065, 1 omitida (pendiente de archivo real de Excel). Fallan 0. Cobertura de app/ 98 %; `importar_excel.py` 100 %. Ruff sigue bloqueado por Windows (limitación del equipo).

| Ítem | Estado |
|---|---|
| BUG-25 | Corregido (0 escapes en 300 alteraciones al azar; también bytes vacíos, None y tipos que no son bytes) |
| BUG-26 | Corregido en las pruebas con valores guardados simulados; falta confirmarlo con un archivo real de Excel (pendiente) |
| BUG-27 | Corregido |
| BUG-28 | Corregido |
| O58 | Parcial: mejora solo con pocas columnas (ver abajo) |

### Bugs nuevos
Ninguno.

### Observaciones
- O58 (rendimiento): la medición del coordinador se confirma solo en parte. Midiendo solo `leer_hoja` con una celda con relleno en la fila 100.000: en la columna A o D tarda 1,9 s, pero en la columna T (20 columnas) tarda 6,1 a 6,5 s, igual que antes de la corrección (6,4 s). El tiempo depende de filas por columnas (2 millones de celdas que crea `iter_rows` en cada libro), no de la búsqueda de fórmulas. Una celda con formato en la fila 1.048.576 y varias columnas sigue siendo un riesgo. La prueba nueva usa la columna D (menos de 4 s). Mejora posible: `read_only=True` o recortar por la última celda con valor.
- O65: `hojas()` ahora no se ve afectado por el formato lejano (corta con el primer valor), pero `leer_hoja` sí.
- Pendientes de la ronda 30 (CA-52.5 / CA-58.4 con archivo real de Excel) siguen igual. O61, O62 (8a-3) y O63 (Ana) no se probaron, como se pidió.


---

## Ronda 32 (2026-10-14): paso 8a-3, lista de revisión de la importación (revision_importacion.py)

### Qué se revisó
- `app/logica/revision_importacion.py` (nuevo): `ListaRevision` y su API completa.
- `app/logica/importar_excel.py`: `FilaDetectada.monto_es_suma`, `Celda.es_suma` y la lectura recortada de `leer_hoja` (O58).
- Contra docs/requisitos.md: RN-66 a RN-75 y RN-78 (§4.12) y, del Módulo K, CA-51.6, CA-52.x, CA-53.x, CA-54.x, CA-55.x, CA-56.x, el estado del pie, y los errores de CA-57.5 a CA-57.8. Quedan fuera (como se pidió) resumen previo, guardado, resultado y cancelar (CA-57.1 a 57.4, 57.9 salvo el texto del pie, 57.10 a 57.13).
- Base: la del principio del Módulo K (hoy 2026-10-14; 2026-10 con sueldo 1.200, cotización 1.600, Alquiler 260.000 en Vivienda; Sofía y Marsu; Varios). Todos los .xlsx se arman con `tests/ayudantes_excel.py` (datos inventados; no se leyó datos-privados/).

### Qué se probó (385 pruebas nuevas en tests/test_revision_importacion.py)
- Estado inicial: las 13 filas de la lista principal con fila de Excel, monto, pagado, tipo y bloque (CA-51.1, CA-52.1); 29 filas en total y 16 incompletas con su nota "Falta el monto/nombre. Se ignora." (CA-51.2); bloques en orden y con sus conteos, "Otras filas" y "Filas detectadas" (CA-51.7, CA-51.8); tildes iniciales.
- Tipo propuesto (RN-66): cuota n/N (9 casos de borde: 15/10, 0/5, 12/12, 13/12, con espacios y ceros), 12 nombres que se ignoran y 5 parecidos que no ("Subtotal", "Totales"...), monto 0 o negativo con su nota, SUM (con valor guardado simulado, en minúsculas, dentro de otra cuenta, sin valor guardado, y fórmula que no es SUM), persona del título (Juan inexistente, Marsu archivada, "Sofía y Marsu", "Marsupiales", combinada D21:E21).
- Cobrado (CA-51.6, RN-64): número igual, "x", "no", 3000 (nota exacta), 12 textos que significan cobrado y 6 que no, 0, números distintos con formato, destildar cobrado, editar con y sin `cobrado`, la nota solo en filas "me deben".
- Tildes (RN-68, RN-74, CA-52.6, CA-52.7): Tarjetas no se puede tildar; desde y hacia "ignorar" (también con "ya existe": nota "Si la importás, queda repetida."); los 36 pares de cambio de tipo; cambiar nombre, tipo o persona recalcula la marca sin tocar el tilde; restaurar fila.
- Acciones de bloque (RN-78, CA-52.8, CA-53.5, CA-53.6): tildar y destildar (también las "ya existe" con la base de CA-56.4), cambiar tipo/categoría/persona, rechazo de cuota y sueldo, "Elegí una persona.", categoría None, persona nueva, filas incompletas intactas, bloque inexistente.
- Edición (CA-53.1 a CA-53.4): errores por campo, no aplica nada con errores salvo "ignorar", completar "Obra social", cuota 2/6 (nota exacta), 7/6, 0, negativa, 2,5, solo un dato; persona nueva "Juan"; "sofía" rechazada.
- Categorías y personas nuevas (RN-75, CA-54.x, CA-57.11): textos exactos de vacío, ya existe (con y sin acento/mayúsculas), archivada (categoría y persona), "Ya agregaste...", campo "nombre"; `nuevas_en_uso` con filas destildadas, ignoradas, de otro tipo, defecto nuevo, cuota, varias; sin "Varios"; no se escribe en la base.
- Mes destino (RN-73, CA-55.x, CA-56.5): opciones, rechazos con su mensaje, defecto con distintos "hoy", huecos entre meses, primer uso (sin meses: opciones libres, mes 13, año 26, sueldo sin flecha, sin "ya existe" de gastos pero sí de "me deben"), aviso del mes que no es el último, nota del sueldo, mensajes temporales exactos (singular, plural, ambos, ninguno), nota de la cuota al cambiar el mes y cruzando de año.
- Ya existe y repetida (RN-74, CA-56.x): " telefono " vs "Teléfono", cualquier tipo de gasto, plan en cualquier estado, mes a crear con fijos copiados (no con pagos únicos) y cuotas de planes activos o terminados, ítems cobrados o de otra persona, segunda importación completa (textos exactos), repetida entre tipos, entre personas, y que desaparece al pasar a ignorar.
- Aviso de gasto compartido (RN-72, CA-56.6): Internet de Sofía, desaparece si la fila 5 se ignora o destilda, vuelve con un gasto Internet del mes, "Servicios Luz Gas", "Pesos Check" contra "Pesos checks" (en el archivo y en el mes), mes a crear (fijos y cuotas), primer uso, cambio de nombre, y 15 pares para `coinciden`.
- Pagado y sueldo (RN-69, RN-70, CA-57.5, CA-57.6): los textos exactos del error de pagado, subir el monto, bajar el pagado, negativo, cero, igual; dos y tres sueldos en todas las filas y en el pie; sueldo sin nombre pero con monto.
- Pie (RN-68, CA-57.8, CA-57.9): el texto exacto de "Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo.", singular, solo sueldo, "No hay filas para importar." (todo destildado, todo ignorado, hoja sin filas completas), "Hay 2 filas con errores...", prioridad del error de dos sueldos.
- `hubo_cambios`: falso al armar y con las consultas; verdadero con cada una de las 12 acciones; falso con acciones rechazadas.
- O61 y O62 (ver abajo), `monto_es_suma`, y la lectura recortada de O58 (unas 20 pruebas).

### Resultado
2.451 pruebas en total: pasan 2.442, fallan 8, 1 omitida (pendiente de archivo real de Excel, igual que antes). Del archivo nuevo: 385 pruebas, 377 pasan, 8 fallan. Las 2.066 anteriores siguen verdes. Cobertura de app/: 98 %; `revision_importacion.py` 100 % e `importar_excel.py` 100 % (medido con las pruebas nuevas). Ruff sigue bloqueado por Windows: las líneas nuevas se revisaron a mano.

Los CA de este paso pasan salvo lo que explican los bugs de abajo: CA-51.6 (salvo el formato de un cobrado negativo, BUG-35), CA-52.1 a CA-52.8, CA-53.1 a CA-53.6 (CA-53.3 falla solo con la cantidad 2,5, BUG-30), CA-54.1 a CA-54.3, CA-55.1 a CA-55.5, CA-56.1 a CA-56.6 (cada caso pasa; el aviso queda viejo en dos combinaciones, BUG-31 y BUG-32), CA-57.5 a CA-57.8 y el texto del pie de CA-57.9.

### Bugs

| Id | Gravedad | Resumen |
|---|---|---|
| BUG-29 | Media-baja | `leer_hoja` sigue tardando 6 a 8 s en una hoja sin valores pero con formato lejos (O58 queda abierto en ese caso) |
| BUG-30 | Media-baja | Cantidad de cuotas con decimales (2,5) no da error |
| BUG-31 | Media | `restaurar_fila` deja viejo el aviso de gasto compartido de las demás filas |
| BUG-32 | Media | `cambiar_mes_destino` deja viejo el aviso de gasto compartido |
| BUG-33 | Media-baja | Más de 600 cuotas (o años imposibles) pasan la revisión y fallarían al guardar |
| BUG-34 | Media-baja | La nota de una cuota con números enormes tarda mucho y dice años imposibles |
| BUG-35 | Baja | Nota de cobrado con número negativo muestra "-$ 500" |

- **BUG-29: O58 solo se resuelve cuando la hoja tiene algún valor.** Verifiqué tu medición: con "Luz" en C3 y una celda con relleno en T100000, `leer_hoja` tarda 0,005 s (antes 6,4 s); en A100000 también. Y no cambia ningún resultado (ver "O58" abajo). Pero si la hoja no tiene ningún valor (solo formato), `con_valor` queda vacío, `ultima_fila = ultima_col = 0` y `iter_rows(max_row=0, max_col=0)` de openpyxl trata el 0 como "no indicado" (usa `max_row or self.max_row`) y recorre toda la hoja: 6,3 a 7,7 s medidos con relleno en T100000. Reproducir: `armar_libro({"Octubre": {}})`, poner `["T100000"].fill = PatternFill("solid", fgColor="FFFF00")`, `abrir_libro(a_bytes(libro)).leer_hoja("Octubre")`. Esperado: menos de 3 s y `sin_datos`. Causa: el `or` interno de `iter_rows`; hay que no llamar a `iter_rows` (devolver la `HojaLeida` sin filas) cuando `ultima_fila == 0`. Alcance: `hojas()` ya no ofrece esa hoja, pero CA-58.2 ("No se encontraron datos en la hoja Hoja1") hace que la pantalla pueda llamar a `leer_hoja` justo con una hoja vacía. Prueba: `test_o58_hoja_vacia_con_formato_lejos_es_rapida`.
- **BUG-30: cantidad de cuotas con decimales.** CA-53.3 pide el error "La cantidad de cuotas tiene que ser un número entero de 1 o más." con 0 o 2,5. Con 0 anda; con `cuota_total=2.5` y `cuota_actual=1` no devuelve ningún error (`_errores_por_campo` solo mira `total < 1` y `1 <= n <= total`). Reproducir: `lista.editar_fila(i, "cuota", "Gym", 5000000, cuota_actual=1, cuota_total=2.5)` devuelve `{}`. Causa: falta comprobar que `total` (y `n`) sean enteros. Si la pantalla convierte el texto antes de llamar y descarta los decimales no se ve, pero la lógica no se defiende. Prueba: `test_cantidad_de_cuotas_con_decimales_es_un_error`.
- **BUG-31: restaurar una fila deja viejo el aviso de los "me deben".** `restaurar_fila` arma la fila nueva (sin tilde), recalcula las marcas y recién después le pone el tilde. Como el aviso de gasto compartido (RN-72) mira qué gastos están tildados, la fila 23 "Internet" (me deben) queda sin aviso aunque la fila 5 "Internet" (gasto) vuelva tildada. Reproducir: base de CA-56.6; pasar la fila 5 a "ignorar" (el aviso de la 23 desaparece, correcto); `restaurar_fila(fila 5)`: la fila 5 queda tildada pero `fila 23.aviso_compartido` sigue en False. Esperado: True. Causa: falta volver a llamar `_recalcular_marcas()` después de asignar `nueva.tildada` (el constructor ya lo hace dos veces por esto mismo). Prueba: `test_restaurar_fila_recalcula_el_aviso_de_gasto_compartido_de_las_demas`.
- **BUG-32: cambiar el mes deja viejo el aviso de gasto compartido.** `cambiar_mes_destino` recalcula las marcas y después cambia los tildes (destilda y vuelve a tildar), sin recalcular el aviso. Reproducir: 2026-09 y 2026-10 existen; 2026-10 tiene un gasto "Internet" y 2026-09 no. Con destino 2026-10, la fila 5 "Internet" viene "ya existe" y destildada, y la 23 muestra el aviso (por el gasto del mes). Se cambia a 2026-09: la fila 5 se vuelve a tildar (se importa), pero la 23 pierde el aviso. Esperado: sigue con el aviso, ahora por la fila 5 (RN-73: "Cambiar el mes destino recalcula ... los avisos de posible gasto compartido"). Causa: mismo orden que BUG-31; hay que recalcular después de tocar los tildes. Prueba: `test_al_cambiar_de_mes_el_aviso_de_gasto_compartido_se_recalcula`.
- **BUG-33: la revisión acepta cuotas que `crear_plan` rechaza.** `crear_plan` rechaza más de 600 cuotas ("La cantidad de cuotas es demasiado grande.") y una primera cuota con año fuera de 1000 a 9999, pero la revisión no pone tope: `editar_fila` con `cuota_total=601` devuelve `{}`, y una fila del Excel "Algo 100000/100000" viene como cuota 100000 de 100000, sin errores y con la nota "primera Julio -6307". Al confirmar, el guardado fallaría y se perdería toda la importación (todo o nada, RN-76) con un mensaje genérico, sin decir qué fila lo causó. El tope de 600 no está en los requisitos (RN-29 dice solo "entero >= 1"): conviene que Ana lo escriba en RN-68 y que se valide en la revisión. Prueba: `test_cuota_con_mas_de_600_cuotas_da_error_en_la_revision`.
- **BUG-34: la nota de la cuota recorre n meses de a uno.** `_nota_cuota` hace un bucle de n-1 pasos: con n = N = 10.000.000 cada llamada a `notas()` tarda 2,3 s, y con "Algo 1000000000/1000000000" en el Excel quedaría colgada varios minutos en cada redibujado de la lista. Además dice años imposibles ("primera Julio -6307"). Se resuelve con la cuenta directa de meses y con el tope de BUG-33. Pruebas: `test_cuota_con_numeros_enormes_en_el_nombre_no_cuelga_la_nota` y `test_cuota_con_numeros_enormes_no_da_una_nota_con_anio_imposible`.
- **BUG-35: cobrado negativo.** `_numero_sin_signo` hace `removeprefix("$ ")`, pero `formatear_ars` de un negativo da "-$ 500", así que la nota dice `En la columna Cobrado dice "-$ 500"`. Esperado "-500" (el formato sin el "$"). Reproducir: F21 "Cobrado" y -500 en F22 de la planilla de prueba. Prueba: `test_cobrado_numero_distinto_se_muestra_con_el_formato_de_montos[-500--500]`.

### Respuestas a lo que se pidió mirar
- **Tildes:** estado inicial, paso desde y hacia "ignorar" (también "ya existe"), cambio de nombre/tipo/persona sin tocar el tilde y el mensaje exacto del mes ("Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó. 1 fila se volvió a tildar.") pasan. El plural no está escrito en los requisitos; las pruebas esperan "2 filas pasaron a "ya existe" y se destildaron" y "2 filas se volvieron a tildar", y el código lo hace así.
- **"Ya existe" con mes a crear y primer uso:** pasan (fijos copiados sí, pagos únicos no; cuotas de planes activos sí, terminados no; un plan terminado marca solo a las filas de tipo cuota). En el primer uso ningún gasto es "ya existe", pero los ítems "me deben" sí (RN-74 no depende del mes).
- **Aviso compartido:** "Servicios Luz Gas" sí, "Pesos Check" vs "Pesos checks" no, desaparece al destildar o ignorar la fila de gasto. Pasa, salvo los dos casos de BUG-31 y BUG-32 (aviso viejo tras restaurar y tras cambiar el mes).
- **Categorías y personas nuevas:** todos los textos de RN-75 pasan, incluidas archivada y "Ya agregaste...". `nuevas_en_uso` solo devuelve las usadas por filas que se importan (destildadas, ignoradas, de otro tipo o con otra persona no cuentan).
- **O61 (monto enorme):** el error es el de `validar_centavos`: "El monto es demasiado grande." (10^17 pesos da 10^19 centavos; 1.000.000.000.000 pesos ya es demasiado; 999.999.999.999 pasa). También en el diálogo, en cuota, "me deben", sueldo y gasto único, y no aparece en filas destildadas. Con un pagado enorme y monto normal se ve el error de "pagado mayor que el monto". Resuelto.
- **O62 (número en la columna de pagado en una fila sin monto):** hoy el número queda como `pagado_cent` de la fila incompleta ("Luz" sin monto y un 3 bajo "Pagado": `pagado_cent = 300`, `monto_cent = None`). No se ve en la lista (la fila dice "Falta el monto. Se ignora."). Al pasarla a gasto fijo el error es solo "Falta el monto."; pero al completar el monto con un valor menor aparece "El pagado ($ 3) es mayor que el monto ($ 1)." por un dato que el usuario nunca vio. Decisión pendiente de Ana: o se descarta el pagado de una fila sin monto, o se muestra. Prueba que lo documenta: `test_o62_numero_en_pagado_de_una_fila_sin_monto_hoy`.
- **hubo_cambios:** falso al armar la lista (también con marcas "ya existe" y tildes calculados) y con cualquier consulta; verdadero con las 12 acciones del usuario (cambiar tipo, tilde, cobrado, editar, restaurar, agregar categoría o persona, categoría por defecto, tres acciones de bloque, mes destino). No cambia con acciones rechazadas ni con elegir el mismo mes. Se mantiene verdadero aunque el usuario deshaga el cambio (coherente con RN-76).
- **O58:** tu medición de la columna T se confirma (0,005 s con datos; 6,4 s antes) y no cambia ningún resultado: la planilla completa, celdas combinadas que se pasan de los datos (D21:K21, H30:K40, G1:G40), filas y columnas ocultas con datos lejos, fórmulas sin valor más allá de los datos (Z50, C400, AA3, hoja de solo fórmulas), fechas, espacios y errores de Excel lejos, y la lista de revisión de punta a punta dan lo mismo con y sin formato lejano. Queda abierto el caso de BUG-29.

### Observaciones
- O66: `editar_fila` pisa lo que no se le pasa: `pagado_cent`, `categoria`, `persona` y `cuota_*` tienen valor por defecto `None` y se guardan tal cual. Editar solo el nombre sin repetir el pagado lo borra, y sin repetir la categoría la vuelve a "categoría por defecto" (RN-75). La pantalla tiene que pasar siempre todos los campos actuales.
- O67: `editar_fila` acepta `categoria` y `persona` que no existen o están archivadas (probado con la categoría 999999). La pantalla solo ofrece activas, pero el guardado de 8a-4 debería validar y fallar con un mensaje claro.
- O68: RN-67 dice que el nombre se guarda "sin los espacios del principio y del final", pero `editar_fila` también junta los espacios repetidos del medio ("Luz   y gas" queda "Luz y gas"), mientras que el nombre que viene del Excel conserva los del medio. No afecta las comparaciones (se normalizan igual).
- O69: las notas "ya existe" de las filas "me deben" y de plan siguen diciendo "Viene destildada." aunque el usuario ya las haya tildado (los requisitos solo definen el texto destildado para estos dos casos; para el gasto sí hay versión tildada). Conviene que Ana defina el texto tildado.
- O70: el mensaje de pagado mayor puede decir dos montos iguales: pagado 1.234,51 y monto 1.234,50 se muestran como "El pagado ($ 1.235) es mayor que el monto ($ 1.235)." porque los montos se muestran sin decimales (RN-04). Es lo que dice el ejemplo de los requisitos (66.021 y 66.020), pero cuando la diferencia es de centavos queda confuso.
- O71: un gasto con un valor en la columna de cobrado (por ejemplo una "x" al lado de "Servicios") queda con `cobrado = True`, aunque RN-64 dice que en las demás filas se descarta. No se ve (la nota y el tilde solo salen en filas "me deben"), pero si el usuario pasa esa fila a "me deben" ya viene cobrada. Si es lo deseado, habría que escribirlo en RN-64.
- O72: el singular del pie con errores ("Hay 1 fila con errores. Corregila, ignorala o destildala para continuar.") y la nota "Plan de 1 cuotas: ..." (cuando N = 1) no están en los requisitos; el primero es razonable, el segundo tiene un error de concordancia.
- O73: un nombre con fecha, como "Seguro 5/10/2026", se propone como cuota 5 de 10 (la regla n/N de RN-66 se cumple con "5/10"). Es lo que dicen los requisitos al pie de la letra, pero es una propuesta fácil de errar; el usuario la cambia en la revisión.
- O74: `leer_hoja` usa `hoja_formulas._cells` (atributo privado de openpyxl). Con `openpyxl==3.1.5` fijado anda; si se actualiza la librería hay que volver a correr las pruebas `test_o58_*`.
- O75: si el usuario destilda a mano una fila y después un cambio de mes la marca "ya existe" y otro cambio de mes la desmarca, la fila se vuelve a tildar sola (RN-74: "las que dejan de serlo se vuelven a tildar"); se pierde el destilde manual. Es lo pedido; se anota por si molesta en el uso.

### Pendiente
- Sin cambios: CA-52.5 / CA-58.4 con un archivo real guardado por Excel o LibreOffice (aquí el valor guardado de SUM se simula con `con_valores_guardados`). Con un archivo real habría que confirmar también que Excel guarda las funciones en inglés (`SUM(`), como supone `es_suma`.
- Pantallas, guardado, resultado y cancelar (8a-4 y siguientes).

### Limitaciones
- Ruff no se pudo correr: Windows (Control de aplicaciones) bloquea ruff.exe. Las líneas nuevas se revisaron a mano; las pruebas tienen algunas líneas largas y dos `lambda` con `noqa`.

---

## Ronda 33 (2026-10-14): verificación de BUG-29 a BUG-35 y O72

### Qué se revisó
Las correcciones en `importar_excel.py`, `revision_importacion.py` y `cuotas.py` (constante `MAXIMO_CUOTAS = 600`). Se corrieron, sin cambiarlas, las 8 pruebas que fallaban en la ronda 32, y se agregaron 23 pruebas de bordes (sección "Ronda 33" de tests/test_revision_importacion.py).

### Estado de cada bug

| Id | Estado | Cómo se verificó |
|---|---|---|
| BUG-29 | Corregido | Hoja sin valores y con relleno en T100000: de 6 a 8 s a menos de 3 s (la prueba pasa), sin filas |
| BUG-30 | Corregido | 2,5 como cantidad y 1,5 o 2,0 como cuota actual dan error; un bool tampoco vale |
| BUG-31 | Corregido | Restaurar la fila 5 devuelve el aviso a la fila 23 |
| BUG-32 | Corregido | Cambiar a 2026-09 mantiene el aviso de la fila 23 |
| BUG-33 | Corregido | Cantidad 599 y 600 sin error; 601 y 10^9 dan "La cantidad de cuotas es demasiado grande."; "n/N" con N > 600 queda gasto fijo |
| BUG-34 | Corregido | Sin bucles: "Algo 1000000000/1000000000" queda gasto fijo y no tarda; cuota inválida o > 600 sin nota |
| BUG-35 | Corregido | La nota dice "-500" |
| O72 | Corregido | "Plan de 1 cuota: ..." |

### Bordes probados
- Cantidad 599, 600, 601 y 10^9 (por el diálogo); N = 600 y 601 en el nombre, con n = 1, 600 y 601.
- Cuota actual 0, -1 o 700 con cantidad 601: hay error y no hay nota.
- Notas que cruzan años: cuota 15 de 24 en 2026-02 (primera Diciembre 2024, última Noviembre 2026); 1 de 24 en 2026-10 (hasta Septiembre 2028); 2 de 3 en 2026-01; 1 de 2 en 2026-12 (hasta Enero 2027); 600 de 600 (primera Noviembre 1976); y recálculo al cambiar el mes destino en el primer uso.

### Resultado
2.474 pruebas: pasan 2.473, 1 omitida (archivo real de Excel), fallan 0. Del archivo de la revisión: 408 pruebas, todas pasan. Cobertura de app/ 98 %; `importar_excel.py` 100 %; `revision_importacion.py` 99 %. Bugs nuevos: ninguno.

### Pendiente
O62, O69, O70 y O63 quedan con Ana; O67 va al guardado (8a-4). Sigue pendiente el archivo real de Excel (CA-52.5 / CA-58.4). Ruff sigue bloqueado por Windows.

---

## Ronda 34 (2026-10-14): paso 8a-4, guardado de la importación y ajustes de reglas

### Qué se revisó
- `app/logica/confirmar_importacion.py` (nuevo): `resumen_previo`, `confirmar` (todo o nada), `Resultado` y `texto_resultado`.
- `cuotas.cuota_en_mes` y `cuotas.MAXIMO_CUOTAS`; los renombres públicos `ListaRevision.con`, `.hoy`, `.mes_existente()` y `revision_importacion.sumar_meses`.
- Las reglas nuevas O62, O63, O69 y O70 (el texto de Ana puede llegar después; se probó contra lo descrito en el pedido).
- Pruebas nuevas en `tests/test_confirmar_importacion.py` (133 pruebas). Se actualizaron las 3 pruebas que documentaban el comportamiento viejo (ver abajo).

### Pruebas viejas actualizadas a las reglas nuevas (no se aflojó ninguna)
| Prueba | Antes | Ahora |
|---|---|---|
| `test_pagado_numero_sin_fila_con_nombre_no_es_pagado` (tests/test_importar_excel.py) | el 99 de E4 no formaba fila | con la fila 3 vacía cierra el "Pagado": el 99 es un número sin nombre (fila 4, monto 9.900, sin pagado). Se agregó una prueba hermana sin fila vacía (E3 con otro pagado), donde el 99 sigue sin formar fila |
| `test_pagado_mayor_por_pocos_centavos_...` (tests/test_revision_importacion.py) | "El pagado ($ 1.235) es mayor que el monto ($ 1.235)." | "El pagado ($ 1.234,51) es mayor que el monto ($ 1.234,50)." y 1.234,56 vs 1.234,50 (renombrada `..._se_muestra_con_centavos`) |
| `test_o62_numero_en_pagado_de_una_fila_sin_monto_hoy` | `pagado_cent == 300` en la fila sin monto | `pagado_cent is None`; al completar el monto no hay error de pagado (renombrada `..._se_descarta`) |

### Resultado
2.607 pruebas: pasan 2.606, 1 omitida (archivo real de Excel), falla 1 (BUG-36, a propósito: la prueba pide el comportamiento correcto). De las 133 nuevas pasan 132. Cobertura de app/ 98 %; `confirmar_importacion.py` 100 %; `cuotas.py` 100 %; `revision_importacion.py` 99 %.

### Qué se probó y qué pasó
| CA / regla | Qué se verificó | Resultado |
|---|---|---|
| CA-57.1 | Gastos de 2026-10 (nombre, monto, tipo, categoría Varios, sin medio, pagos); totales 677.837 / pagado 98.700 / pendiente 579.137; sueldo 1.300; USD a cambiar 423,65 (`42365`); ahorro 876,35 (`87635`); Sofía 32.900 y Marsu 6.785 no cobrados con fecha de hoy; sin categorías ni personas nuevas; plan de Avant (primera 2026-08, cuota 3/3, última 2026-10, sin medio) | Pasa |
| CA-57.2 / 57.10 / 57.12 | Frase principal y "Para completar" (con y sin la línea de cotización); pantalla Gastos o Resumen (solo ítems, solo sueldo, solo cuota, solo gasto); primer uso | Pasa |
| CA-57.9 | Las 7 líneas del resumen previo con los textos exactos; singulares; "pagado" solo si hay pagos; mes que se crea; primer uso con y sin sueldo; "Sueldo: US$ 1.200,00" sin flecha si no cambia; el resumen no escribe en la base ni toca la lista | Pasa |
| CA-55.2 | Destino 2026-11: se crea con Alquiler copiado (uno solo), sueldo 1.300, cotización 1.600; cuota 3/3 en noviembre y 2/3 en octubre; octubre no recibe otro dato ni cambia su sueldo; sin fila de sueldo toma el del último mes | Pasa |
| CA-55.3 | Destino 2026-09 con 2026-10 existente: cuota 3/3 en septiembre, octubre sin cuota; sueldo al mes destino; septiembre recibe también "Alquiler" (no existía ahí, CA-56.5) | Pasa |
| CA-55.4 / 55.5 | Primer uso con y sin sueldo (sueldo 0, sin cotización, `falta_cotizacion`); destino propuesto = último mes | Pasa |
| RN-71 | Cuota en mes pasado (los meses del medio no se tocan, el actual recibe la suya), n = N (plan terminado, mes siguiente sin cuota), n = 1 en mes nuevo, pagado completo y parcial solo en la cuota del destino, 600 cuotas, 600/600 (primera 1976-11), primer uso en 2025-03 | Pasa |
| CA-56.4 / O69 | Segunda importación: todo "ya existe" y destildado; notas con y sin tilde; Avant: gana la nota de gasto sobre la de plan; sin tildar nada no se puede confirmar; tildando todo queda duplicado | Pasa |
| CA-57.11 | Persona nueva que deja de usarse no se crea; categoría nueva como defecto, solo en una cuota, solo en "Gym" destildada; 2 categorías y 2 personas nuevas | Pasa |
| CA-57.4 | 12 puntos de fallo con monkeypatch (después de crear el mes, la categoría, la persona, el primer y el último gasto, pagos, plan, cuota del destino, primer y último ítem, marcar cobrado): no queda nada en ninguna tabla, la lista queda igual (filas, nuevas, mes, categoría por defecto), `__cause__` es el error, la conexión queda sin transacción abierta, y el reintento funciona y deja lo mismo que una importación sin fallo. También fallo real de la base, fallo en el primer uso (sigue sin meses) y fallo en el sueldo | Pasa |
| CA-50.2 | La lógica no crea archivos, no guarda la ruta ni ".xlsx" en la base, y borrar el .xlsx no cambia nada | Pasa |
| RN-69 | Pagado completo (un pago por el monto), parcial, 0, centavos, en gasto único y en cuota; en "me deben" se ignora | Pasa |
| Cobrado | Ítems cobrados no suman al total; destildar "cobrado" lo deja pendiente | Pasa |
| O62, O63, O70 | Pagado de fila sin monto se descarta; fila vacía cierra el "Pagado"; error con centavos si los montos se ven iguales | Pasa |
| Renombres | `.con`, `.hoy`, `mes_existente()`, `sumar_meses` existen y los viejos ya no | Pasa |
| No se puede confirmar | Sin filas, 2 sueldos, 1 y 2 filas con errores: lanza el texto del pie y no guarda | Pasa |

### Bugs

#### BUG-36 (baja): una cuota con primera cuota antes del año 1000 pasa la revisión y falla al guardar
- **Causa:** `_errores_por_campo` valida que n esté entre 1 y N y que N <= 600, pero no que el año de la primera cuota (destino − (n − 1) meses) sea de 4 dígitos. `crear_plan` sí lo valida ("El año tiene que tener 4 dígitos.") y el guardado falla.
- **Cómo reproducir:** base sin meses, hoja con "Casa 600/600 | 1000", `lista.cambiar_mes_destino(1000, 6)`. `lista.puede_confirmar()` es True, la nota dice "primera Julio 950" y `confirmar(lista)` lanza "No se pudo importar. No se guardó ningún dato." (la causa es "El año tiene que tener 4 dígitos."). No queda nada guardado.
- **Prueba:** `test_cuota_cuya_primera_cuota_queda_antes_del_ano_1000_no_pasa_la_validacion` (falla hoy). `test_cuota_con_primera_cuota_antes_del_ano_1000_falla_sin_guardar_nada` pasa: confirma que no queda nada a medias.
- **Impacto:** casi nulo en el uso real (hace falta un primer uso con año 1000 a 1049 y cuota 600 de 600). Se corrige con un error de fila en la revisión, como BUG-33.

### Observaciones
- **O67 (qué pasa):** categoría o persona archivada o inexistente elegida con `editar_fila` (y categoría por defecto archivada) NO da error en la lista: `puede_confirmar()` es True y el pie dice "Se importan N filas". Al confirmar, el guardado falla y se ve solo "No se pudo importar. No se guardó ningún dato."; no queda nada guardado (probado con categoría archivada, inexistente, en cuota, por defecto, y persona archivada e inexistente). Lo seguro anda; falta claridad: la causa real ("La categoría elegida está archivada.", "La persona Marsu está archivada.") queda solo en `__cause__`. Una categoría mala en una fila que no se importa no molesta. Conviene que Ana decida si la revisión valida esto con un error de fila (como "Elegí una categoría.") o si basta con el mensaje genérico. La pantalla solo ofrece activas, así que solo pasa si algo se archiva mientras dura la revisión.
- **O76:** `confirmar` no "gasta" la lista. Confirmar dos veces la misma lista (doble clic en "Importar") duplica todo; con una persona o categoría nueva, la segunda vez falla con el mensaje genérico y no guarda nada más. La pantalla tiene que desactivar el botón mientras guarda y no volver a la revisión después de un éxito.
- **O77:** cuota con destino 9999-12: la nota y el plan llegan al año 10000 ("última Noviembre 10000") y se guarda sin error. Inofensivo; se anota por si la pantalla lo muestra con 5 dígitos.
- **O78:** en el primer uso la fila "Alquiler" del Excel no es "ya existe" (no hay ningún mes), por eso importa 6 gastos y no 5. Es coherente con RN-74; CA-57.12 no dice la cantidad.
- **O79:** el nombre con espacios de más ("  Luz   y gas  ") se guarda como "Luz y gas" (lo limpia `agregar_gasto`), pero la lista antes de guardar conserva los espacios del medio (ver O68).
- O63 y O69 todavía no tenían texto en requisitos.md al momento de la ronda para todos los casos; las pruebas siguen el comportamiento descrito en el pedido (CA-51.8 y CA-56.4 ya recogen O69).

### Respuestas a lo que se pidió mirar
- **CA-57.4 en los tres puntos pedidos** (después de crear el mes, después de crear una categoría nueva, en el último ítem): pasan, y otros 9 puntos más. En todos, la base queda idéntica a la de antes (foto de todas las tablas), incluido el sueldo y el mes nuevo.
- **Totales de la base del Módulo K:** gastos `67783678`, pagado `9870000`, pendiente `57913678`, USD a cambiar `42365`, ahorro `87635`, Sofía `3290000`, Marsu `678500`. Coinciden con CA-57.1.

### Pendiente
- Pantallas del guardado (8e): botón "Importar", diálogo de resultado, error al guardar y cancelar.
- Archivo real de Excel (CA-52.5 / CA-58.4).

### Limitaciones
- Ruff no se pudo correr (Windows bloquea ruff.exe). Las líneas nuevas se revisaron a mano; hay líneas largas en las pruebas y una `lambda` con `noqa`.
- El fallo a mitad del guardado se simula con monkeypatch (y una vez con un fallo real de la base); no se probó un corte de luz o un disco lleno.

---

## Ronda 35 (2026-10-14): verificación de BUG-36, O67, O76 y O77

### Qué se revisó
Las correcciones en `revision_importacion.py` (`_errores_por_campo`, `_elegible`, atributo `confirmada`) y `confirmar_importacion.py` (`confirmar`). Se actualizaron las 11 pruebas de la ronda 34 que documentaban el comportamiento viejo y se agregaron pruebas nuevas, todas en `tests/test_confirmar_importacion.py` (ahora 157 pruebas).

### Estado de cada ítem
| Id | Estado | Cómo se verificó |
|---|---|---|
| BUG-36 | Corregido | Destino 1000-06 y cuota 600/600: la fila muestra "Con esta cuota, el plan quedaría en un año no válido. Revisá la cuota actual y la cantidad.", sin nota de plan; no se puede confirmar; `confirmar` lanza el texto del pie y no guarda nada (ni el primer mes). Límites: 600/600 en 1049-12 es válida (primera Enero 1000) y en 1049-11 no. El error se recalcula al cambiar el mes destino (aparece y desaparece), el diálogo de edición lo rechaza y una fila destildada no lo muestra. Sin regresión: 600/600 en 2026-10 se guarda |
| O77 | Corregido | Destino 9999-12 y cuota 1/12 (última cuota 10000-11): error de fila y no se guarda. 12/12 en 9999-12 y 1/12 en 9999-01 son válidas; 1/12 en 9999-12 no |
| O67 | Corregido | `editar_fila` devuelve `{"categoria": "Elegí una categoría."}` o `{"persona": "Elegí una persona."}` (y no cambia la fila) con categoría archivada, inexistente, Nueva ajena a la revisión (también en cuota) y persona archivada o inexistente. Categoría o persona archivada mientras dura la revisión, y categoría por defecto archivada: error de fila, pie "Hay N filas con errores...", `confirmar` lanza el pie y no guarda nada; al desarchivar o elegir otra, se puede confirmar. Categorías activas y Nuevas de la revisión se siguen aceptando; una fila destildada con categoría mala no molesta |
| O76 | Corregido | `confirmada` empieza en False; tras un guardado bien hecho pasa a True y una segunda llamada lanza "Esta importación ya se guardó." (sin `__cause__`, base idéntica), también con persona nueva, en el primer uso y aunque la lista ya no sea confirmable (gana sobre "No hay filas para importar."). Si el guardado falla, o si la lista tiene errores, `confirmada` sigue en False y se puede reintentar (probado con monkeypatch) |

### CA-57.4 con fallo real de la base (sin monkeypatch)
Como la revisión ya detecta el archivado y los años, el fallo real se provoca con un trigger de SQLite (`RAISE(ABORT)`), que la revisión no puede ver. 9 puntos con la lista completa de CA-57.4 (destino 2026-11, Juan y "Importado" nuevos, un ítem cobrado, un pago parcial): al insertar el mes, la categoría, la persona, un gasto a mitad (Gym), la cuota que se copia al mes actual, el pago parcial, el plan, el último ítem "me deben" y al marcar cobrado. Además, el UPDATE del sueldo de un mes existente y el primer uso con fallo en los ítems. En todos: mensaje "No se pudo importar. No se guardó ningún dato.", la causa real en `__cause__`, la base idéntica a la de antes (foto de todas las tablas), la lista intacta, `confirmada` en False, sin transacción abierta y, al sacar el trigger, el reintento funciona. Las 12 pruebas con monkeypatch de la ronda 34 siguen pasando.

### Resultado
2.632 pruebas: pasan 2.631, 1 omitida (archivo real de Excel), fallan 0. Cobertura de app/ 98 %; `confirmar_importacion.py` 100 %; `revision_importacion.py` 99 %. Bugs nuevos: ninguno.

### Observaciones
- **Texto para Ana:** el mensaje "Con esta cuota, el plan quedaría en un año no válido. Revisá la cuota actual y la cantidad." no está en requisitos.md (RN-68); habría que agregarlo a la tabla de errores y agregar "Esta importación ya se guardó." a RN-76. La nota de plan no aparece cuando hay este error.
- **O80:** una categoría o persona que se archiva durante la revisión ahora se ve como "Elegí una categoría." / "Elegí una persona." aunque el usuario la había elegido; el texto no explica que está archivada. Es razonable (pasa solo si se archiva en otro lugar mientras dura la revisión).
- **O81:** `confirmada` no se incluye en "lo que cuenta como cambio" (`hubo_cambios`) ni se reinicia: una lista confirmada queda inutilizable y la pantalla tiene que armar una nueva para otra importación. Es lo pedido.
- Pendientes sin cambios: pantallas del guardado (8e) y archivo real de Excel (CA-52.5 / CA-58.4). Ruff sigue bloqueado por Windows.

---

## Ronda 36 (2026-10-14): paso 8b, entradas y elegir archivo de la importación de Excel

### Qué se probó
Archivo nuevo `tests/test_interfaz_importar.py` (100 pruebas, 2 de ellas xfail). Sin ventanas: página falsa, `app.selector_de_archivos` reemplazado por un selector falso y las tareas de `run_task` ejecutadas a mano con `asyncio.run`. Archivos inventados con `tests/ayudantes_excel.py`. Se actualizó `test_pestanas_y_titulo` de `tests/test_interfaz_ajustes.py` (ahora 6 pestañas, cambio esperado por diseno.md §3.10).

| Área | Qué se verificó | Resultado |
|---|---|---|
| CA-49.1 primer uso | Línea "¿Tenés una planilla?" + TextButton "Importar Excel" después de "Crear mes" (orden del árbol); abre pantalla completa sin rail, título "Gastos – Importar Excel"; Cancelar y Esc vuelven al formulario, base sin cambios | Pasa |
| CA-49.2 Ajustes | Sexta pestaña, última; Ctrl+N no hace nada; abre sin rail; Cancelar y Esc vuelven a la pestaña "Importar Excel" y al mismo mes; base sin cambios; abrir/cancelar 3 veces | Pasa |
| Atajos (§1.3) | Ctrl+1/3/7, Ctrl+N, Ctrl+Shift+N, Ctrl+K, Ctrl+coma, Alt+flechas (y Cmd en macOS) no hacen nada durante la importación; otras teclas no cancelan; al salir vuelven a funcionar | Pasa |
| Selector | Llamado con título "Elegir una planilla de Excel", CUSTOM, `["xlsx"]`, `with_data=True`; cerrar sin elegir (lista vacía o None) no cambia nada; lee de los bytes; con `bytes` None lee del disco; ruta inexistente o sin bytes ni ruta da el aviso (no crash); el archivo no se modifica ni se copia; excepción del selector muestra el diálogo de error y libera `ocupada`; un solo FilePicker | Pasa |
| CA-58.1 | `.txt`, `.csv`, `.xls`, `.xlsm`, `.ods`, sin extensión (por nombre); `.txt` y `.csv` renombrados a `.xlsx`; `.xlsx` cortado, de 0 bytes, con hoja interna rota, zip sin estructura de Excel, hoja que falla al leerla: texto exacto, aviso negativo con ERROR_OUTLINE, botón "Elegir otro archivo", sin "Revisar filas"; el aviso se reemplaza (no se acumula); `.XLSX` en mayúsculas se acepta | Pasa |
| CA-58.2 | Una hoja vacía ("Sheet" y con nombre propio), varias hojas todas vacías (nombra la primera), hoja con solo una fecha, nombre con Ñ y paréntesis: "No se encontraron datos en la hoja X." con WARNING_AMBER; hoja con solo textos no es error en esta pantalla | Pasa |
| Elegir hoja (RF-50, CA-50.1) | Una hoja: no pregunta; una con datos y otras vacías: no pregunta; varias: RadioGroup, primera elegida, textos exactos, vacías no se ofrecen, Revisar filas con foco; 8 hojas sin scroll, 9 con alto 240 y scroll; "Revisar filas" lee la hoja elegida; hoja sin datos entre varias: aviso debajo de las hojas con la selección conservada, se puede elegir otra, el aviso no se acumula en 3 intentos; "Elegir otro" vuelve al inicio | Pasa |
| `planilla-prueba.xlsx` | "En la hoja Octubre se detectaron 13 filas con texto y monto, y 5 filas incompletas." (primer uso, Ajustes y por el selector); no guarda nada | Pasa |
| Ocupada | Leyendo: "Leyendo el archivo..." con ProgressRing y botones deshabilitados (también visto durante la lectura real); con `ocupada` los clics no lanzan tareas y Esc/Cancelar no actúan; se libera siempre | Pasa |
| Lógica sin interfaz | Ningún módulo de `app/logica/` importa `app.interfaz` ni `flet` (análisis del código); `mensaje_sin_datos`, `primera_hoja`, `aviso_en_pantalla` (4 roles) | Pasa |

### Resultado
Suite completa: 2.732 pruebas: 2.729 pasan, 1 omitida (archivo real de Excel), 0 fallan, 2 xfail (observación O82). Cobertura de `app/` 98 %; `pantalla_importar.py` 100 % con la prueba de hoja dañada.

### Bugs
Ninguno nuevo.

### Observaciones
- **O82 (baja, teórica):** `ocupada` se pone en True cuando la tarea de `run_task` arranca, no cuando se hace clic. Dos clics procesados antes de que Flet corra la tarea encolarían dos tareas (dos selectores, o dos lecturas). En Flet, el manejador de clic termina y la tarea suele arrancar antes del siguiente evento, así que probablemente no se puede dar; la página falsa no puede confirmarlo. Reproducción en pruebas: `test_dos_clics_antes_de_que_corra_la_tarea` y `test_doble_clic_en_revisar_filas` (marcadas xfail, no strict; si se corrige poniendo `self.ocupada = True` en `elegir_archivo`/`revisar_hoja` antes de `run_task`, pasan solas). Hay que mirarlo a mano con un doble clic rápido en la ventana real.
- **O83:** el texto provisorio dice "1 filas" (plural fijo). Es temporal hasta el 8c; se anota por si se conserva.
- **O84:** el selector real de archivos (`ft.FilePicker` y sus parámetros reales, el caso de Edge sin ruta) no se pudo probar sin ventana; queda para prueba manual: abrir con Elegir archivo..., cerrar con Cancelar del sistema, elegir `planilla-prueba.xlsx`, elegir un `.txt` escribiendo el nombre.
- Pendiente de prueba manual: aspecto (foco inicial, scroll de 9+ hojas, colores de avisos en tema oscuro).

**Correcciones después de la ronda 36 (agente principal):**
- **O82 corregida:** `elegir_archivo` y `revisar_hoja` ponen `ocupada = True` al hacer clic, antes de `run_task`. Se sacó la marca xfail de las dos pruebas, que ahora pasan.
- **O83 corregida:** "1 fila con texto y monto" / "1 fila incompleta". Se ajustaron las dos pruebas que esperaban "1 filas".
- Suite completa: 2.732 pruebas: 2.731 pasan, 1 omitida (archivo real de Excel).

---

## Ronda 37 (2026-10-16): pasos 8c y 8d, lista de revisión y edición de la importación de Excel

### Qué se probó
Archivo nuevo `tests/test_interfaz_revision.py`: 202 funciones de prueba, 219 casos con los parametrizados (217 pasan, 2 xfail por un bug y una observación abiertos). Sin ventanas: página falsa, el archivo se lee con `PantallaImportar.leer_archivo` y los handlers de los controles (tilde, tipo, dropdowns, botones, diálogos) se llaman a mano. "Hoy" se fija en 2026-10-14. Base de los CA: 2026-10, sueldo 1.200, cotización 1.600, Alquiler 260.000 en Vivienda, Sofía, Marsu y Varios. Archivos inventados con `tests/ayudantes_excel.py`; no se leyó `datos-privados/`.

Además se adaptaron las 13 pruebas de `tests/test_interfaz_importar.py` (ronda 36) que verificaban el texto provisorio "En la hoja X se detectaron N filas...". Ahora comprueban que se muestra la lista (`p.vista is not None`, `p.lista.hoja.nombre`, cantidad de filas principales, nombre de archivo y hoja en la cabecera, y "Cambiar archivo u hoja" en lugar de "Elegir otro"). El texto viejo decía "5 filas incompletas"; la lista muestra 16, que es lo que dice CA-51.2 (la prueba de `planilla-prueba.xlsx` ahora verifica 13 y 16). No se relajó ninguna verificación: cada prueba sigue comprobando la hoja y el contenido elegidos.

| Área | Qué se verificó | Resultado |
|---|---|---|
| Lista esperada (CA-51.1, 51.2, 51.7, 52.1, 52.4) | 4 bloques en orden (GASTO DEL MES, DEUDAS, DEUDAS SOFIA, MARSU), las 13 filas con número de fila, tipo, tilde, monto, categoría o persona y cuota; subtítulos "filas X a Y · se importan N de M"; bloques abiertos; sin "Otras filas" ni bloques vacíos; "Filas incompletas" con 16 filas plegado, notas "Falta el monto/nombre. Se ignora.", "(sin nombre)" en cursiva; título como celda combinada; el 66.021 no aparece; sin títulos, "Filas detectadas"; fila vacía intermedia, "Otras filas" | Pasa |
| Tilde y tipo (RF-52, CA-52.2, 52.3, 52.6, 52.7) | Tilde deshabilitado con tooltip en "ignorar"; seis tipos con textos y orden exactos; cualquier fila a los seis tipos; se tilda sola al salir de "ignorar"; Alquiler (fijo, único, ignorar, fijo) con la nota "queda repetida"; cuotas y falsas cuotas (Heladera 2/12, Cumple 15/10, Algo 601/601, Heladera 1/1); título con persona inexistente o archivada | Pasa |
| Notas y avisos (§3.12) | Textos, íconos y colores de: ya existe (gasto, plan, me deben), repetida, gasto compartido (aparece y desaparece al ignorar o destildar la fila 5), cobrado no reconocido, cuota, sueldo con y sin flecha, monto no válido (-5.000, 0, -1.234,56) | Pasa |
| Pagado y cobrado (CA-51.5, 51.6) | "✓ Completo" y "Parcial · falta $ 80.000" con colores; tilde Cobrado solo en "me deben"; columna F de CA-51.6 (cobrados, nota del "3.000"); destildar cobrado borra la nota; pagado mayor que el monto que viene del Excel | Pasa |
| Mes destino (CA-55.1, 55.2, 55.3, 55.5, 56.5) | Opciones y orden, "mes actual", "se crea al confirmar", las ayudas, segunda línea del sueldo, aviso de mes que no es el último, destino 2026-08, SnackBar de 6 s al re-tildar y al pasar a "ya existe", sin aviso si nada cambia, mes fuera de las opciones | Pasa |
| Primer uso (CA-55.4) | Mes y año libres con valores del calendario; año "26", "", "202", "20266", "0000" y "0999" dan error en el campo y botón bloqueado con tooltip "Corregí el mes destino."; corregir rehabilita; las notas de cuota usan el mes elegido | Pasa |
| Categoría por defecto (CA-54.x, RN-75) | Viene Varios con "+"; elegida a mano con "• " y tooltip "Elegida a mano" y la por defecto después (CA-54.2); se conserva al cambiar de tipo; sin Varios hay error en las 6 filas, en el dropdown, el botón y el pie (CA-54.3); "Importado" nueva queda elegida con "(nueva)" y al cancelar la base queda idéntica; "Varios" archivada durante la revisión | Pasa |
| Crear categoría o persona (§4.11, CA-53.4) | Fila en línea con Agregar y Cancelar y la ayuda; vacío, "salud", "regalos" archivada, repetida en la importación; "Juan" se crea y se elige en otras filas; "sofía", "SOFIA" y "  Sofia  " se rechazan con 'Ya existe una persona llamada "Sofía".'; Enter agrega; no se escribe nada en la base; una nueva sin uso no se crearía | Pasa |
| Filtros y conteos | "Todas (29) / Se importan (9) / Con avisos (2) / Con errores (0)"; se actualizan con cada cambio; la cuota (info) no cuenta como aviso; filtro sin resultados con "Ninguna fila coincide con este filtro." y "Ver todas"; ícono en "Con errores"; el filtro se vuelve a aplicar al editar; el grupo de incompletas aparece con "Se importan" si se completó una fila | Pasa |
| Errores y botón (RN-68) | Fondo negativo suave, borde izquierdo de 4 px, ícono y texto en negativo; orden errores, avisos, info; pie en singular y plural, "No hay filas para importar."; tooltips "Primero corregí las filas con errores." y "Tildá al menos una fila."; "Ir al primer error" (abre el bloque, desplaza con la clave `fila-N`, foco al lápiz, vuelve el filtro a "Todas", abre "Filas incompletas"); subtítulo "N con error" con el bloque plegado; dos sueldos (aviso del archivo, error en ambas filas, pie y botón) | Pasa |
| Diálogo de fila (§4.9, CA-53.1 a 53.4, 53.7) | Título, botones, clic en la fila y en el lápiz; campos visibles por tipo y texto conservado al cambiar; sueldo en US$ con "Hoy el sueldo de Octubre 2026 es US$ 1.200,00." o "todavía no existe"; nombre vacío, monto 0, vacío, "abc", "-5", demasiado grande; pagado mayor, completo, parcial y 0; Cancelar y Esc no aplican nada; "Volver a lo detectado" (también en "ya existe" y con errores); foco en el primer error; Obra social completada queda en "Filas incompletas" con subtítulo "16 filas · se importan 1"; cuota 2/6, 7/6, 0, 601 ("demasiado grande") y 600 con la nota; vista previa del plan en cada tecla; tipo "ignorar" se acepta con errores | Pasa |
| Diálogo de bloque (§4.10, CA-53.5, 53.6) | Título, ayuda con y sin "incluidas las que están ignoradas", singular, "Aplicar a las N filas"; "Cuota" y "Sueldo (USD)" deshabilitados con tooltip; campos por tipo; "Sofía y Marsu" con persona Marsu; "Deudas sofia" a gasto único en Servicios (la 24 se tilda sola); "Deudas" a Vivienda y la por defecto a Servicios no la cambia; incompletas sin cambios; "me deben" sin persona da error; con persona nueva; "ignorar"; sin elegir nada no cambia; Cancelar | Pasa |
| Acciones de bloque (CA-52.8, 56.x) | Tildar y destildar (la 24 sigue ignorada); con la base de CA-56.4 "Tildar todas" tilda las "ya existe"; segunda importación completa (CA-56.4) con las notas exactas; CA-56.2, 56.3, 56.6, 56.7 | Pasa |
| Teclado (aplicacion.py, pantalla_importar.py) | Ctrl+Enter (Cmd+Enter en macOS, y ahí Ctrl no) confirma; Enter solo no; con el botón deshabilitado o un diálogo abierto no hace nada; Esc cierra la fila "nueva categoría" de la pantalla y el segundo Esc cancela; Esc en un diálogo lo cierra sin cancelar la importación; los atajos de la app no actúan | Pasa (salvo O86) |
| Cambiar archivo u hoja y cancelar | Vuelve a la tarjeta de inicio, arma una lista nueva al elegir de nuevo, cada hoja arma su lista | Pasa |
| Sin escrituras (RF-57) | Sesión larga (tipos, tildes, mes 2026-11, categoría y persona nuevas, dos diálogos, bloque, sueldo, filtros, cambiar archivo): foto de todas las tablas idéntica antes y después; abrir un archivo con "Deudas Juan" tampoco crea nada | Pasa |
| Lógica (`revision_importacion.py`) | `notas()` da los mismos textos que `notas_con_clase()`; clases válidas; `errores_por_campo`; `texto_plan` con 13 casos (1 cuota, 600, 601, 0, 7/6, None, texto, decimal, bool, año fuera de rango); la lógica no importa `app.interfaz` ni `flet` (análisis del código de todos los módulos) | Pasa |

### Resultado
- `tests/test_interfaz_revision.py`: 217 pasan, 2 xfail (BUG-37 y O86).
- `tests/test_interfaz_importar.py`: 100 pasan (13 adaptadas).
- Suite completa con `pytest --cov=app`: 2.948 pasan, 1 omitida (archivo real de Excel), 2 xfail, 0 fallan. Cobertura de `app/` 98 %; `dialogo_fila_importacion.py` 100 %, `pantalla_importar.py` 100 %, `revision_importacion.py` 100 %, `lista_revision.py` 99 % (queda una línea inalcanzable: el aviso de cambio de mes en el primer uso, que nunca devuelve mensaje).
- Rendimiento: con una hoja de 300 filas, abrir tarda 0,3 s y un cambio de tilde o de tipo 0,04 s (sin ventana real).

### Bugs
- **BUG-37 (baja):** los campos "Cuota actual" y "Cantidad de cuotas" del diálogo de edición no tienen tope de largo y `_leer_entero` (`dialogo_fila_importacion.py`) hace `int(texto)`. Con más de 4.300 dígitos pegados, Python lanza `ValueError: Exceeds the limit (4300 digits)` al escribir (`on_change`, vista previa del plan) y al tocar "Aceptar". Reproducir: abrir el diálogo de "Gym", tipo "Cuota", poner "1" y "9" × 5.000 y tocar Aceptar. Esperado: el error "La cantidad de cuotas es demasiado grande." Causa probable: falta `max_length` (por ejemplo 4) o un control de largo antes de `int()`, como hace `leer_monto` (tope de 20 caracteres). Prueba: `test_cuotas_con_miles_de_digitos_no_rompen_el_dialogo` (xfail no estricto; pasa sola al corregir).

### Observaciones
- **O86 (baja):** diseno.md §4.11 dice que en la fila en línea de "nueva categoría" o "nueva persona" dentro de un diálogo, Esc cierra solo esa fila. Hoy `Aplicacion._al_presionar_tecla` cierra todo el diálogo (y se pierde lo escrito). En la pantalla principal sí funciona (se pidió). Prueba: `test_esc_con_la_fila_en_linea_del_dialogo_cierra_solo_esa_fila` (xfail no estricto). Arreglo posible: preguntar por la fila en línea del diálogo antes de cerrarlo, como hace `PantallaImportar.al_presionar_tecla`.
- **O85 (cosmética):** el subtítulo de un bloque con error dice "filas 12 a 15 · se importan 3 de 3" + ícono + "1 con error"; el diseño (§3.12) pide "· 1 con error" (con el punto medio).
- **O87 (cosmética):** el diseño pide que "Con errores" aparezca con fondo negativo suave; la implementación le pone solo un ícono ERROR_OUTLINE. Y "Completo" se muestra con el carácter "✓" en el texto, no con un ícono CHECK (la señal sin color se cumple igual).
- **O88:** el diálogo de edición no valida la cantidad de sueldos (`editar_fila` quita ese error a propósito): se puede crear un segundo sueldo desde el diálogo y la lista lo marca en las dos filas y bloquea la confirmación. Contradice un poco la frase de §4.9 de que el diálogo no deja errores creados por él. Prueba que documenta el comportamiento: `test_el_dialogo_permite_crear_un_segundo_sueldo_y_la_lista_lo_marca`.
- **O89:** CA-53.3 pide el error "La cantidad de cuotas tiene que ser un número entero de 1 o más." para 0 y 2,5. En la pantalla funciona con 0; "2,5" no se puede escribir (filtro de dígitos) y, si llegara por otro camino, el diálogo dice "Indicá la cuota actual y la cantidad de cuotas." (porque `_leer_entero` lo trata como vacío). Inofensivo; se anota por el texto del CA.
- **O90:** dos títulos de bloque con el mismo texto (por ejemplo "Fijos" en las filas 1 y 7, con otro título en el medio) se funden en un solo bloque en la lista (`ListaRevision.bloques()` agrupa por texto): el subtítulo dice "filas 2 a 8" y las acciones de bloque afectan a las dos partes. Probablemente raro; confirmar con Ana si RN-65 lo prevé.
- **O91:** el error inesperado reutiliza el diálogo "No se pudo guardar / Los datos no se modificaron." también durante la revisión, donde no se estaba guardando nada. No es incorrecto, pero sorprende.
- **O92:** si "Varios" (o la categoría elegida) se archiva mientras dura la revisión, la fila sigue mostrando su nombre ("Varios") junto al error "Elegí una categoría."; el diálogo ofrece "Categoría por defecto (sin elegir)". Es lo mismo que O80.
- **Texto del diseño:** el boceto de §3.12 dice "se importan 4 de 5" en "Gasto del Mes" con Alquiler "ya existe" y destildado; con esa base son 3 de 5 (las pruebas verifican 3). Igual con "Con avisos (3)": con la base de los CA son 2 (Alquiler e Internet de Sofía).
- **Esperado en este paso (no es bug):** "Confirmar importación" y Ctrl+Enter solo avisan "Todavía no se puede guardar: eso llega en el próximo paso." y Cancelar sale sin preguntar aunque haya cambios. Las tres pruebas que dependen de ese aviso (`test_ctrl_enter_confirma_y_hoy_solo_avisa_que_falta_el_guardado`, `test_clic_en_confirmar_hace_lo_mismo_que_ctrl_enter` y `test_cmd_enter_en_macos_confirma_y_ctrl_enter_no`) hay que reemplazarlas en el 8e.

### Limitaciones y pendiente de prueba manual
- Con página falsa no se ve: el aspecto real (alineación de las columnas con anchos fijos, ancho mínimo de unos 1.000 px en una ventana de 1.100, scroll de la lista con la cabecera fija arriba y el pie abajo), el desplazamiento real de `scroll_to` con la clave de la fila dentro de un `ExpansionTile`, el foco real al lápiz, el menú de tres puntos dentro del título del `ExpansionTile` (que no pliegue el bloque al tocarlo), el orden de Tab y las flechas de los selectores, los colores en tema oscuro y el SnackBar de 6 s. Conviene probarlo a mano con `planilla-prueba.xlsx`.
- Los handlers se llaman directamente: si Flet mandara el evento con otra forma (por ejemplo `e.control.selected` del filtro o `on_select` de los dropdowns), solo se vería en la ventana real.
- Ruff sigue sin poder correrse en este equipo (Windows lo bloquea); hay líneas largas en las pruebas nuevas.
- Pendiente 8e: guardado, resumen previo, resultado y confirmación al cancelar.

**Correcciones después de la ronda 37 (agente principal):**
- **BUG-37 corregido:** los campos de cuota tienen `max_length=3` (el tope es 600) y `_leer_entero` trata un texto de más de 6 dígitos como "demasiado grande" sin llamar a `int()`. Se sacó la marca xfail de la prueba.
- **O86 corregida:** con un diálogo abierto, Esc primero llama a `dialogo.data` (si es una función); los diálogos de la importación la usan para cerrar solo la fila de "nueva categoría/persona". Se sacó la marca xfail.
- **O85 corregida:** el subtítulo dice "· 1 con error". Se ajustó la prueba que esperaba el texto sin "·".
- Quedan abiertas O87 a O92 (menores) para revisar con el usuario o en el 8e.
- Suite completa: 2.951 pruebas: 2.950 pasan, 1 omitida (archivo real de Excel).
