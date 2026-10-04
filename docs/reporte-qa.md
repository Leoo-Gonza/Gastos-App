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
