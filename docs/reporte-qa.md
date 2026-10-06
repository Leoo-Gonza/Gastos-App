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
