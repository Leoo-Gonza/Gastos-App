---
name: grill-me
description: Entrevista a fondo al usuario para afinar una funcionalidad antes de escribir requisitos o código.
disable-model-invocation: true
argument-hint: "[funcionalidad a definir]"
---

Entrevistá al usuario sobre esta funcionalidad: $ARGUMENTS

El objetivo es que no quede nada ambiguo antes de pasarle el resultado a Ana
(requisitos). El usuario está aprendiendo: hablale en español, simple y sin
jerga innecesaria.

## Antes de la primera pregunta

- Leé lo que ya está decidido, para no preguntar lo que ya está escrito:
  docs/requisitos.md (sobre todo §6 "Correspondencia con la planilla" y §8
  "Fuera de la v1"), docs/diseno.md y, si sirve, docs/referencia/.
- NUNCA leas datos-privados/. Si necesitás saber cómo son los datos reales,
  preguntale al usuario.

## Cómo preguntar

- **Una pregunta por mensaje.** Si hay varias decisiones chicas y técnicas,
  podés juntarlas en una lista numerada para confirmar de una vez.
- Empezá por la decisión que más condiciona el resto (alcance, para quién
  es, de dónde salen los datos) y bajá hacia los detalles.
- Ofrecé opciones concretas (A, B, C…) con su ventaja y su costo, y decí
  cuál recomendás y por qué. Usá ejemplos con los datos del usuario
  (ej. "Alquiler 260000") en vez de ejemplos abstractos.
- Si una respuesta trae algo nuevo (ej. "después la van a usar mis
  familiares"), resumilo en una línea y repensá las preguntas que siguen.
- Insistí en los casos borde: datos vacíos, repetidos, negativos, cancelar
  a mitad, qué pasa con lo que ya está cargado.
- No escribas código ni archivos durante la entrevista.

## Al terminar

1. Mostrale al usuario un resumen corto de lo acordado: para qué sirve,
   cómo funciona paso a paso y qué queda para después.
2. Pasale a Ana (agente `ana`) todo lo acordado, con los casos borde y las
   decisiones que le tocan a ella, para que lo formalice en
   docs/requisitos.md.
3. Contale al usuario lo que sigue: Antonio diseña las pantallas y después
   se muestra el plan de código para su aprobación.
