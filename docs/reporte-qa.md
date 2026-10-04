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
