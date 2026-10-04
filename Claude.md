# App de gastos personales

## Descripción
App de escritorio (Windows y macOS) para gestionar gastos mensuales en
pesos y dólares, deudas en cuotas, ahorro y previsiones a futuro.
Reemplaza una planilla de Excel.

## Stack
Python 3.14, Flet (interfaz), SQLite con sqlite3 (datos), openpyxl
(importar Excel), pytest (pruebas), ruff (formato).
Entorno virtual en .venv. Dependencias en requirements.txt: si agregás
una librería, actualizá ese archivo.

## Estructura
- app/logica/: datos y cálculos. NUNCA importa nada de la interfaz.
- app/interfaz/: pantallas de Flet. Solo muestra y llama a la lógica.
- tests/: pruebas de Lucía.
- docs/: requisitos, diseño, diagramas y reportes.
- datos-privados/: datos reales del usuario. NUNCA leer ni subir a git.

## El equipo
- /grill-me: entrevista al usuario antes de cada funcionalidad grande.
- Ana: formaliza los requisitos en docs/requisitos.md.
- Antonio: diseña las pantallas en docs/diseno.md.
- Vos (agente principal): programás.
- Lucía: prueba y reporta en docs/reporte-qa.md.

## Modo de trabajo (IMPORTANTE)
- El usuario está aprendiendo Python y Claude Code. Después de cada
  cambio, explicá en español QUÉ hiciste y POR QUÉ elegiste esa solución.
- Trabajá en pasos chicos que el usuario pueda probar.
- Antes de escribir código, mostrá el plan y esperá aprobación.
- Comentarios en español en las partes no obvias.
- Después de cada funcionalidad, pedile a Lucía que la pruebe.
  No está terminada hasta que pasen sus pruebas.
- Si Lucía reporta un bug, explicá la causa antes de corregirlo.
- Nunca hagas git push: el usuario sube los cambios.