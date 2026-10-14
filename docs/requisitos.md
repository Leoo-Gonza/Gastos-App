# Requisitos – App de gastos personales (v1 y v2)

> Documento de requisitos. Sale de la entrevista (/grill-me) confirmada por el usuario,
> de sus respuestas a dos rondas de preguntas abiertas, de la entrevista sobre gastos en
> dólares (y sus preguntas abiertas), de la entrevista sobre importar la planilla de Excel
> (2026-10-13, primera funcionalidad de la v2, y sus preguntas abiertas), de las decisiones
> del usuario sobre el diseño de la importación (2026-10-13, `docs/diseno.md` §7,
> observaciones 21 a 32) y de la planilla de referencia
> (`docs/referencia/Referencia planilla.png`).
> Define QUÉ hace la app, no CÓMO se programa.

---

## 1. Descripción general

App de escritorio (Windows y macOS) que reemplaza la planilla de Excel con la que el
usuario maneja sus finanzas mensuales.

Situación del usuario:

- Vive en Argentina. Cobra el sueldo en **dólares (USD)** y paga casi todos sus gastos en
  **pesos argentinos (ARS)**.
- Cada mes cambia USD a ARS para cubrir los gastos. **Lo que sobra en USD es su ahorro.**
- Tiene deudas en cuotas (tarjetas, préstamos, deudas con personas).
- Comparte gastos de la casa con dos personas (Sofía y Marsu): paga el total y después
  ellas le devuelven su parte. Lleva la cuenta de lo que le deben.
- Algunos gastos están expresados en dólares (ej. una suscripción de US$ 20), pero los paga
  en pesos (RF-43 a RF-48).

Ejemplo real de la planilla: gastos 1.434.617 ARS ÷ cotización 1.600 ≈ 897 USD a cambiar;
1.200 − 897 = 303 USD de ahorro.

Objetivos de la v1:

1. Cargar los gastos del mes (en ARS o en USD), marcar qué está pagado y saber cuánto falta
   pagar.
2. Saber cuántos USD hay que cambiar y cuánto se ahorra, con la cotización que el usuario
   carga a mano.
3. Seguir las deudas en cuotas (cuota actual, cuándo terminan, cuánto se libera).
4. Repartir gastos compartidos y saber cuánto le debe cada persona.
5. Ver la capacidad de endeudamiento, una previsión de los próximos 12 meses y tres gráficos.

Objetivos de la v2 (en curso):

6. Importar una planilla de Excel para arrancar sin cargar todo a mano (Módulo K). Más
   adelante la usarán familiares, cada uno con su propio Excel de formato distinto: la
   importación no depende del formato de la planilla del usuario.

---

## 2. Glosario

| Término | Significado |
|---|---|
| **Mes** | Período identificado por año y mes (ej. 2026-10). Cada mes guarda sus propios gastos, cotización, sueldo, ingresos extra y cambios. |
| **Mes seleccionado** | El mes que el usuario está mirando o editando. Puede ser cualquier mes existente. |
| **Mes actual** | El mes del **calendario del sistema** (hoy 2026-10). No depende del mes seleccionado. Lo usan los planes de cuotas (RN-30, RN-31) y la previsión (RN-41). |
| **Último mes** | El mes más reciente que existe en la app. |
| **Sueldo** | Ingreso principal en USD del mes (hoy 1.200 USD). |
| **Ingreso extra** | Ingreso adicional del mes, en ARS o en USD. |
| **Cotización** | Cantidad de ARS que se obtienen por 1 USD. La carga el usuario a mano. Ej.: 1.600. |
| **Cotización del mes** | La cotización cargada en el mes; se usa para pesos a cubrir, USD a cambiar y ahorro. |
| **Cambio realizado** | Operación ya hecha: "cambié X USD a una cotización Y y recibí Z ARS". |
| **Gasto** | Salida de dinero que se paga en ARS dentro de un mes. Tipo: fijo mensual, en cuotas o pago único. Su monto puede estar expresado en ARS o en USD (RF-43). |
| **Gasto en dólares** | Gasto fijo mensual o de pago único expresado en USD (ej. US$ 20,00). Se paga en pesos: tiene un monto en ARS que sale de multiplicar por la cotización del gasto (RN-53). |
| **Cotización del gasto** | Cotización que el usuario carga en un gasto en dólares (ej. la del dólar tarjeta). Es propia del gasto y puede ser distinta de la cotización del mes. |
| **Gasto fijo mensual** | Gasto que se repite todos los meses (alquiler, internet). Se copia al crear un mes nuevo. |
| **Gasto en cuotas** | Gasto generado por un plan de cuotas en cada mes en que el plan está activo. Siempre en ARS. |
| **Pago único** | Gasto que solo existe en el mes en que se carga. No se copia. |
| **Plan de cuotas** | La deuda completa: monto de la cuota (ARS), cantidad de cuotas y mes de la primera cuota. |
| **Cuota actual** | Número de cuota que corresponde a un mes, mostrado como "n/total" (ej. "3/3"). |
| **Cuota omitida** | Mes en el que el usuario borró a mano la cuota de un plan. El plan sigue, pero en ese mes la cuota no se vuelve a generar (RN-52). |
| **Medio de pago** | Cómo se paga un gasto (cada tarjeta, efectivo, transferencia…). Opcional. |
| **Pago** | Monto pagado de un gasto, siempre en ARS. Un gasto puede tener varios pagos parciales. |
| **Pendiente** | Lo que falta pagar de un gasto: monto en ARS − suma de pagos. |
| **Pesos a cubrir** | ARS que todavía hay que conseguir cambiando USD (RN-14). |
| **USD a cambiar** | Pesos a cubrir ÷ cotización del mes (RN-15). |
| **Pesos sobrantes** | ARS que sobran cuando lo obtenido supera los gastos (RN-16). Se convierten a USD y suman al ahorro. |
| **Ahorro del mes** | USD que quedan después de cubrir todos los gastos del mes (RN-17). |
| **Persona** | Alguien con quien el usuario comparte gastos o que le debe plata (Sofía, Marsu). |
| **Gasto compartido** | Gasto que el usuario paga completo y reparte con una o más personas. |
| **Parte** | Porción de un gasto compartido que le corresponde a cada participante. |
| **Parte propia** | Porción del gasto que le corresponde al usuario. En un gasto no compartido es el monto completo. |
| **Me deben** | Lista acumulada por persona (no por mes): sus partes de gastos compartidos + ítems cargados a mano, cada uno con tilde de "cobrado". |
| **Archivar** | Ocultar una categoría, medio de pago o persona para cargas nuevas, sin borrarla del historial. Se puede desarchivar. |
| **Capacidad de endeudamiento** | ARS por mes que sobran después de pagar fijos y cuotas y de ahorrar la meta (RN-38). |
| **Meta de ahorro** | Monto único en USD que el usuario quiere ahorrar por mes. |
| **Previsión** | Estimación de los 12 meses siguientes al mes actual, con la cotización actual y sin inflación. |
| **Versión de la base** | Número que indica qué estructura tiene el archivo de la base (0 = sin gastos en dólares; 1 = con gastos en dólares). Evita repetir actualizaciones (RN-59). |
| **Importación** | Carga de datos desde un archivo `.xlsx` de Excel, con una revisión previa en la que el usuario decide fila por fila (Módulo K). El archivo no se guarda en la app. |
| **Lista de revisión** | Pantalla de la importación con las filas detectadas, donde el usuario elige el tipo de cada fila, corrige y confirma. Nada se guarda hasta confirmar. |
| **Fila detectada** | Línea de la lista de revisión armada a partir de una fila del Excel: un nombre (texto), un monto y, si hay, un pagado o un cobrado (RN-63, RN-64). |
| **Fila incompleta** | Fila detectada a la que le falta el nombre o el monto (ej. "Obra social" sin número, un título, o un número suelto). Se muestra en un grupo aparte (RN-63). |
| **Título de bloque** | Texto sin monto que encabeza un grupo de filas en la misma columna del Excel y que no está pegado a la fila de arriba (ej. "Deudas sofia", "Marsu") (RN-65). |
| **Fila pegada** | Texto sin monto que tiene justo arriba, en la misma columna, el nombre de otra fila detectada (ej. "Deuda freezer" debajo de "Avant Service…"). No es un título: queda como fila incompleta del bloque en el que está (RN-65). |
| **Bloque** | Grupo de filas de la lista de revisión que cuelgan del mismo título de bloque. Tiene acciones para cambiar todas sus filas juntas (RN-78). |
| **Tipo de fila** | Qué se hace con una fila detectada: gasto fijo mensual, gasto pago único, cuota, me deben, sueldo (USD) o ignorar. |
| **Mes destino** | Mes en el que se cargan los datos importados (RN-73). |

---

## 3. Requisitos funcionales

Numeración: RF-xx. Los criterios de aceptación de cada RF están en la sección 7 con el
número CA-xx.y, donde xx es el número del RF. Los módulos A a J son la v1; el módulo K es
la v2.

### Módulo A – Meses e historial

- **RF-01** La app guarda los datos separados por mes: sueldo, cotización, gastos (con sus
  pagos y partes compartidas), ingresos extra y cambios realizados.
- **RF-02** El usuario puede elegir cualquier mes existente para verlo y editarlo. Los meses
  pasados son editables (RN-11).
- **RF-03** El usuario puede crear un mes nuevo, que siempre es el siguiente al último mes
  (RN-08). Al crearlo se aplican las copias y sugerencias de RN-09.
- **RF-04** Si no existe ningún mes (primer uso), la app permite crear el primero eligiendo
  año y mes y cargando sueldo y cotización.
- **RF-05** El usuario puede borrar el último mes, y solo ese (RN-10).

### Módulo B – Gastos

- **RF-06** Alta de gasto en el mes seleccionado con: nombre (obligatorio), categoría
  (obligatoria), monto (obligatorio; en ARS, o en USD con su cotización según RF-43 y RF-44),
  tipo (fijo mensual o pago único) y medio de pago (opcional). Los gastos en cuotas se crean
  a través de un plan de cuotas (RF-16).
- **RF-07** Edición de cualquier campo de un gasto del mes seleccionado, respetando RN-23
  (no bajar el monto por debajo de lo pagado).
- **RF-08** Baja de un gasto del mes seleccionado, con confirmación (RN-51). Si es la cuota
  de un plan, se borra solo la de ese mes y el plan sigue (RN-52).
- **RF-09** Lista de gastos del mes seleccionado con: nombre, categoría, tipo, cuota actual
  (si es en cuotas), medio de pago, monto, pagado y pendiente. Al pie: total de gastos,
  total pagado y total pendiente del mes (columnas "Gastos", "Pagado" y "Falta por pagar" de
  la planilla). Los gastos en dólares muestran además el detalle de RF-46.
- **RF-10** ABM de categorías: crear, renombrar y eliminar. Una categoría en uso no se borra:
  se archiva, y se puede desarchivar (RN-49).
- **RF-11** ABM de medios de pago: crear, renombrar y eliminar. Cada tarjeta puede ser un medio
  distinto (ej. "Visa Santander", "Mastercard Nación"). Un medio en uso se archiva, y se puede
  desarchivar (RN-49). Valores iniciales sugeridos: Tarjeta de crédito, Efectivo,
  Transferencia.
- **RF-12** Las deudas con personas (ej. "Deuda Jeho") se cargan como gasto de pago único o
  como plan de cuotas. No hay un módulo aparte.

### Módulo C – Pagos

- **RF-13** Tilde "pagado": marca el gasto como pagado completo. Destildarlo borra todos los
  pagos del gasto (RN-22).
- **RF-14** Pago parcial: el usuario registra un monto pagado (ej. de 180.000 pagó 60.000).
  Puede haber varios pagos parciales. La app muestra pagado y pendiente por gasto (RN-20, RN-21).
- **RF-15** El usuario puede ver los pagos de un gasto y eliminar uno en particular (para
  corregir errores).

### Módulo D – Deudas en cuotas

- **RF-16** Alta de plan de cuotas con: nombre, categoría, medio de pago (opcional), monto de
  la cuota en ARS, cantidad total de cuotas y mes de la primera cuota (RN-29). Los planes no
  tienen selector de moneda: son siempre en ARS.
- **RF-17** Para cada plan, la app calcula y muestra: cuota actual ("n/total") respecto del
  mes seleccionado, mes de la última cuota y monto restante (RN-24 a RN-28).
- **RF-18** Al dar de alta un plan, la app genera los gastos correspondientes en el mes actual
  y en los meses futuros que ya existan, nunca en meses anteriores al mes actual (RN-30).
- **RF-19** Edición de un plan: los cambios se aplican al mes actual y a los futuros
  existentes, nunca a los anteriores, conservando las cuotas que ya tienen pagos (RN-30).
- **RF-20** Cancelación anticipada de un plan: deja de generar cuotas desde el mes actual, o
  desde el siguiente si la cuota del mes actual ya tiene pagos (RN-31).
- **RF-21** Lista de planes con filtro: activos, terminados y cancelados.
- **RF-22** Total por medio de pago del mes seleccionado: suma de sus gastos agrupados por
  medio de pago. Incluye todos los tipos de gasto (en la planilla, la tabla "Deudas" sumaba
  cuotas y también Gym, Claude, Monotributo, etc.). Los gastos sin medio se agrupan como
  "Sin medio de pago". Este total reemplaza la línea "Tarjetas de Crédito" de la planilla,
  que **no** se carga como gasto.

### Módulo E – Ingresos, cotización y cambios

- **RF-23** Ver y editar el sueldo en USD del mes seleccionado. Se permite 0, con aviso (RN-05).
- **RF-24** ABM de ingresos extra del mes: descripción, moneda (ARS o USD) y monto.
- **RF-25** Ver y editar la cotización del mes seleccionado en cualquier momento. Al cambiarla
  se recalculan de inmediato todos los valores que dependen de ella (RN-19). El monto en ARS
  de los gastos en dólares **no** cambia (RN-55).
- **RF-26** ABM de cambios realizados del mes: fecha, USD cambiados, cotización del cambio y
  ARS recibidos. Los ARS se completan solos (USD × cotización) y se pueden corregir a mano
  (RN-13).
- **RF-27** La app calcula pesos a cubrir, USD a cambiar, pesos sobrantes y ahorro del mes
  (RN-12 a RN-18). La cotización del mes se aplica solo a lo que falta cubrir; los cambios
  ya realizados mantienen sus propios ARS.

### Módulo F – Gastos compartidos y "me deben"

- **RF-28** ABM de personas (inicialmente Sofía y Marsu). Una persona en uso se archiva, y se
  puede desarchivar (RN-49).
- **RF-29** Un gasto puede marcarse como compartido eligiendo una o más personas. Por defecto
  se divide en partes iguales entre el usuario y las personas elegidas (RN-32).
- **RF-30** El usuario puede editar a mano la parte de cada persona; la parte del usuario se
  calcula sola (RN-33).
- **RF-31** Si cambia el monto de un gasto compartido, las partes se recalculan y las partes
  ya cobradas se tratan según RN-34.
- **RF-32** Ítems "me deben" cargados a mano por persona: descripción, monto ARS y fecha
  (ej. "Préstamo MP 20.000", "tacones 6.785").
- **RF-33** Lista "me deben" por persona, acumulada (todos los meses): sus partes de gastos
  compartidos (indicando gasto y mes) y sus ítems manuales, y el total pendiente de cobro
  (RN-35). Si una parte cobrada cambió de monto, se muestra lo ya cobrado y la diferencia.
- **RF-34** Tilde "cobrado" en cada línea de "me deben", que se puede marcar y desmarcar.

### Módulo G – Resumen del mes (pantalla principal)

- **RF-35** La pantalla principal muestra, para el mes seleccionado: sueldo (USD),
  cotización, total gastos (ARS), pesos a cubrir (ARS), USD a cambiar, pesos sobrantes
  (si hay), ahorro (USD; si es negativo, como déficit), total pendiente de pago (ARS) y el
  total que le deben (ARS, acumulado de todas las personas, RN-40).
- **RF-36** Meta de ahorro: una sola meta mensual en USD, editable. La pantalla principal
  muestra la barra de avance del ahorro del mes contra la meta (RN-39).
- **RF-37** La pantalla principal muestra la capacidad de endeudamiento del mes (RN-38). Si es
  negativa se muestra en rojo con un aviso.

### Módulo H – Previsiones

- **RF-38** Tabla de los 12 meses siguientes al mes actual con, por mes: gastos ARS
  estimados, USD a cambiar y ahorro estimado. Solo considera sueldo, gastos fijos mensuales
  (los en dólares, convertidos con la cotización actual) y cuotas (RN-41 a RN-43, RN-45).
- **RF-39** En cada mes de la previsión se indica qué cuotas se liberan ese mes y cuánto
  (ej. en la fila de abril: "Avant +$ 41.117") (RN-44).

### Módulo I – Gráficos

- **RF-40** Gráfico de gastos del mes seleccionado por categoría, con la parte propia del
  usuario (RN-46).
- **RF-41** Gráfico de ahorro en USD mes a mes, con todos los meses del historial (RN-47).
- **RF-42** Gráfico de previsión de gastos ARS de los 12 meses de la previsión (RN-48).

### Módulo J – Gastos en dólares

- **RF-43** Selector de moneda (ARS o USD) en el alta y la edición de gastos **fijos
  mensuales y de pago único**. Los gastos en cuotas no tienen selector (siempre ARS). Un gasto
  en dólares se paga en pesos: su monto en ARS cuenta en todos los cálculos igual que el de
  cualquier gasto (total de gastos, pesos a cubrir, USD a cambiar, ahorro, pagos, pendiente,
  total por medio de pago, partes compartidas, capacidad de endeudamiento y gráfico por
  categoría) (RN-55). La previsión es la excepción: usa la cotización actual (RN-42).
- **RF-44** Al elegir USD, la app pide el **monto en USD** y la **cotización del gasto**. La
  cotización aparece completada con la cotización del mes; si el mes no tiene cotización, el
  campo queda vacío y es obligatorio (RN-54). Mientras el usuario escribe, la app muestra al
  instante los pesos a pagar: "US$ 20,00 × $ 1.600 = $ 32.000" (RN-53). La app no calcula
  impuestos ni recargos (RN-58).
- **RF-45** Edición de un gasto en dólares: se pueden cambiar el monto en USD y la cotización
  del gasto, y el monto en ARS se recalcula. También se puede cambiar la moneda del gasto
  (ARS ↔ USD) (RN-56). Si cambia la cotización del mes, el monto en ARS del gasto **no**
  cambia (RN-55).
- **RF-46** En la lista de gastos (RF-09), los gastos en dólares muestran el monto en ARS (en
  la columna de monto, como todos) y además el detalle "US$ 20,00 × $ 1.600" (cotización con
  el formato de RN-04).
- **RF-47** Al crear un mes nuevo, los gastos fijos en dólares se copian con el mismo monto en
  USD y con la cotización del mes nuevo (o la del gasto copiado, si el mes nuevo no tiene
  cotización), recalculando el monto en ARS (RN-57). Si es un gasto compartido y sus partes
  manuales ya no entran en el nuevo monto, se reparten en partes iguales y la app avisa
  (RN-37).
- **RF-48** La incorporación de gastos en dólares no debe perder ni alterar los datos ya
  cargados por el usuario: antes de actualizar la base se hace una copia de respaldo, y todos
  los gastos existentes quedan como gastos en ARS con sus mismos montos, pagos y partes. La
  actualización se aplica una sola vez (RN-59).

### Módulo K – Importar Excel (v2)

- **RF-49** Puntos de entrada y pantalla. La importación se ofrece en dos lugares:
  - en la pantalla de primer uso (RF-04): el formulario para crear el primer mes queda
    **igual** y debajo aparece "¿Tenés una planilla?" con el botón "Importar Excel" (así no
    agrega ningún paso a quien empieza de cero);
  - en Ajustes, en una pestaña "Importar Excel" (la última), con el botón "Importar Excel".
  Es opcional: la app se puede usar sin importar nada. La importación ocupa una **pantalla
  completa, sin rail ni barra superior**, venga del primer uso o de Ajustes: mientras dura no
  se puede ir a otra pantalla ni cambiar de mes, y siempre tiene "Cancelar" a la vista
  (RN-76).
- **RF-50** Elegir archivo y hoja. El usuario adjunta un archivo `.xlsx` de **cualquier
  formato** (no tiene que parecerse a la planilla del usuario: cada familiar puede tener la
  suya). Si el archivo tiene varias hojas, el usuario elige cuál importar; si tiene una sola,
  se usa esa sin preguntar. El archivo solo se lee: no se modifica, no se copia y no se
  guarda en la app (RN-60).
- **RF-51** Lista de revisión. A partir de la hoja elegida, la app arma la lista de filas
  detectadas (texto + monto, y el pagado o el cobrado si los hay), en el orden del Excel e
  indicando el número de fila del Excel de cada una. Las filas se agrupan en **bloques**
  según el título de bloque del Excel al que pertenecen (RN-65). Aparte, en un grupo "Filas
  incompletas", muestra los textos sin monto y los montos sin texto (RN-61 a RN-64). Nada se
  guarda hasta confirmar (RF-57).
- **RF-52** Tipo de cada fila: gasto fijo mensual, gasto pago único, cuota, me deben, sueldo
  (USD) o ignorar. La app propone un tipo cuando puede (RN-65, RN-66) y el usuario lo puede
  cambiar. Cada fila tiene además un tilde "importar", que sigue al tipo "ignorar" (RN-68):
  una fila "ignorar" no se puede tildar y, al pasarla a otro tipo, se tilda sola. En cada
  bloque, el usuario puede tildar o destildar todas sus filas de una vez (RN-78).
  "Compartido" **no** es un tipo de importación: se marca después en la pantalla de gastos
  (RF-29).
- **RF-53** Corrección por fila. Antes de confirmar, el usuario puede corregir en cada fila:
  nombre, monto, monto pagado (gastos y cuotas), categoría (gastos y cuotas), cuota actual y
  cantidad de cuotas (cuotas), persona y tilde "cobrado" (me deben), con la opción de crear
  una persona nueva (RN-72). Las filas incompletas se pueden completar (escribir el nombre o
  el monto que falta) y cambiar de tipo. Con la acción de bloque "Cambiar tipo o categoría de
  todas..." puede cambiar en un solo paso el tipo, la categoría o la persona de todas las
  filas de un bloque (RN-78).
- **RF-54** Categoría por defecto: una categoría para toda la importación (propuesta:
  "Varios", si existe), que se puede cambiar en general y fila por fila (RN-75). El medio de
  pago **no** se pide: los gastos importados quedan sin medio de pago y se completa después
  en la app (RF-07).
- **RF-55** Mes destino: por defecto el mes actual; se puede elegir otro antes de confirmar.
  Si el mes destino no existe, se crea al confirmar (RN-73).
- **RF-56** Duplicados: las filas cuyo nombre coincide con un gasto que ya existe en el mes
  destino se marcan "ya existe" y vienen destildadas; las filas con nombre repetido dentro del
  mismo Excel se marcan "repetida en el archivo" (RN-74). Las filas "me deben" que podrían ser
  la parte de un gasto compartido muestran un aviso, sin cambiar su tipo (RN-72).
- **RF-57** Confirmar y cancelar. Al confirmar, la app muestra primero un **resumen previo**
  de lo que se va a guardar; al aceptarlo guarda todas las filas que se importan de una sola
  vez (todo o nada), muestra el resultado y después el mes destino en la pantalla **Gastos**
  (o en **Resumen**, si solo se importaron ítems "me deben" y/o el sueldo) (RN-76). Cancelar
  en cualquier momento antes de guardar descarta todo sin guardar nada: "Cancelar" y `Esc`
  piden confirmación si el usuario ya cambió algo; cerrar la ventana de la app cierra sin
  preguntar. Una importación confirmada no se puede deshacer (§8).
- **RF-58** Avisos sobre el archivo: archivo dañado o que no es `.xlsx`, hoja sin datos y
  fórmulas sin valor calculado (RN-60, RN-61).

---

## 4. Reglas de negocio

### 4.1 Montos, monedas y validaciones generales

- **RN-01 – Almacenamiento de montos.** Todos los montos se guardan como **enteros en
  centavos** (ARS y USD). Ej.: 66.020,12 ARS → `6602012`; 1.200 USD → `120000`. Motivo:
  los números con decimales de punto flotante acumulan errores de redondeo al sumar
  (0,1 + 0,2 ≠ 0,3); con enteros las sumas son exactas.
- **RN-02 – Almacenamiento de la cotización.** Entero en **centavos de ARS por 1 USD**.
  Ej.: 1.600 → `160000`; 1.432,50 → `143250`. Vale para la cotización del mes, la de cada
  cambio y la de cada gasto en dólares.
- **RN-03 – Redondeo en cálculos.** Solo se redondea al dividir (conversiones entre monedas,
  incluida la conversión USD → ARS de los gastos en dólares, RN-53, y división de partes).
  Las conversiones se redondean al centavo más cercano, mitad hacia arriba (0,5 → 1). Las
  sumas y restas nunca redondean. La división de partes sigue RN-32.
- **RN-04 – Visualización.** Internamente todo sigue en centavos. En pantalla:
  - **ARS sin decimales**, redondeado al peso más cercano (mitad hacia arriba), con punto
    de miles: 66.020,12 → "66.020"; 22.093,68 → "22.094".
  - **USD con 2 decimales**: "896,64".
  - **Cotizaciones** (del mes, de los cambios y de los gastos en dólares): **con sus
    decimales cuando los tienen** ("$ 1.432,50") y **sin decimales cuando son enteras**
    ("$ 1.600"). No se redondean. Vale en todas partes: barra/resumen, diálogos, detalle
    "US$ 19,99 × $ 1.432,50" en la lista y vista previa del alta y la edición.
  - Los totales se redondean a partir del valor exacto, no sumando valores ya redondeados.
  - La entrada de montos y cotizaciones acepta hasta 2 decimales (coma decimal).
- **RN-05 – Montos válidos.** Montos de gastos (en ARS o en USD), cuotas, pagos, ingresos
  extra, USD y ARS de cambios, ítems "me deben" y meta de ahorro deben ser **mayores a 0**. Se
  rechazan negativos, cero, vacíos y texto no numérico, con un mensaje. El **sueldo** debe ser
  ≥ 0; si es 0 se acepta y se muestra el aviso "El sueldo de este mes es 0".
- **RN-06 – Cotización válida.** Mayor a 0. No se puede guardar 0 ni negativa. La cotización
  del mes puede quedar sin cargar (RN-18); la de un gasto en dólares es obligatoria (RN-54).
- **RN-07 – Meses válidos.** Año de 4 dígitos y mes de 1 a 12. No puede haber dos meses con
  el mismo año y mes.

### 4.2 Meses e historial

- **RN-08 – Mes nuevo.** Solo se puede crear el mes siguiente al último mes (ej. si el último
  es 2026-10, solo 2026-11). No se pueden saltear meses ni crear meses anteriores al primero.
- **RN-09 – Contenido del mes nuevo.**
  - Copia los gastos fijos mensuales del último mes: nombre, categoría, monto, moneda, medio de
    pago y configuración de compartido (RN-37). Los fijos en dólares se copian según RN-57.
    Todos quedan **sin pagos**.
  - Genera un gasto por cada plan de cuotas activo en el mes nuevo (RN-24): no cancelado y
    sin cuota omitida en ese mes.
  - Los gastos fijos y cuotas se copian o generan **aunque usen una categoría, medio de pago o
    persona archivada** (RN-49).
  - **No** copia gastos de pago único (en ARS ni en USD), ingresos extra ni cambios realizados.
  - Sugiere el sueldo y la cotización del último mes (editables).
  - Si un gasto fijo se eliminó en el último mes, ya no se copia más.
- **RN-10 – Borrar mes.** Solo se puede borrar el último mes, con confirmación. Se borran sus
  gastos, pagos, partes compartidas (que desaparecen de "me deben"), ingresos extra y cambios.
  No se borran los planes de cuotas, las cuotas omitidas ni los ítems manuales de "me deben".
- **RN-11 – Independencia y edición de meses.** Todos los meses son editables. Editar un gasto
  de un mes no modifica los gastos de otros meses (ej. subir el alquiler en noviembre no
  cambia octubre).

### 4.3 Pesos a cubrir, USD a cambiar y ahorro

Variables (todas del mismo mes):

| Símbolo | Significado |
|---|---|
| `S` | Sueldo en USD |
| `G` | Total de gastos del mes en ARS |
| `E_ars` | Suma de ingresos extra en ARS |
| `E_usd` | Suma de ingresos extra en USD |
| `C_usd` | Suma de USD cambiados |
| `C_ars` | Suma de ARS recibidos en los cambios |
| `K` | Cotización del mes (ARS por USD) |

- **RN-12 – Total de gastos.** `G = Σ monto en ARS de todos los gastos del mes`, pagados o
  no. Los gastos compartidos cuentan por su **monto completo**, porque el usuario paga todo y
  después le devuelven. Los gastos en dólares cuentan por su monto en ARS (RN-55).
- **RN-13 – ARS recibidos en un cambio.** Valor sugerido: `usd × cotización_del_cambio`
  (en centavos: `usd_cent × cot_cent ÷ 100`, redondeado según RN-03). El usuario puede
  corregirlo a mano (ej. si hubo comisión); se usa el valor guardado. Si después cambia los
  USD o la cotización del cambio, la app vuelve a sugerir el producto y el usuario puede
  corregirlo de nuevo. Ej.: 500 USD a 1.500 → 750.000 sugeridos.
- **RN-14 – Pesos a cubrir.** `F = G − E_ars − C_ars`. `Pesos a cubrir = máx(F, 0)`.
  Lo que le deben al usuario **no** reduce `F` (RN-36).
- **RN-15 – USD a cambiar.** `U = Pesos a cubrir ÷ K`, redondeado según RN-03
  (en centavos: `pesos_cent × 100 ÷ K_cent`). Si `Pesos a cubrir = 0`, `U = 0`.
- **RN-16 – Pesos sobrantes.** Si `F < 0`, hay `P = −F` pesos sobrantes. Se muestran como
  "Pesos sobrantes" y se convierten a USD con la cotización del mes:
  `P_usd = P ÷ K` (RN-03). **No** pasan al mes siguiente. Si `F ≥ 0`, `P = 0` y `P_usd = 0`.
- **RN-17 – Ahorro del mes.** `Ahorro = S + E_usd − C_usd − U + P_usd`.
  Puede ser negativo (déficit): se muestra en rojo con la palabra "Déficit".
- **RN-18 – Sin cotización.** Si el mes no tiene cotización y `F ≠ 0`, la app no calcula USD
  a cambiar, pesos sobrantes en USD, ahorro ni capacidad de endeudamiento: muestra "Cargá la
  cotización". Si `F = 0`, el ahorro se calcula igual (`S + E_usd − C_usd`).
- **RN-19 – Recalcular.** Cualquier cambio en gastos, ingresos extra, cambios realizados,
  sueldo, cotización o meta recalcula RN-12 a RN-17, RN-38 y RN-39 de inmediato. Los pagos y
  los tildes de "cobrado" **no** afectan estos cálculos.

Ejemplo de verificación (planilla): `S = 1.200`, `G = 1.434.617`, `K = 1.600`, sin extras
ni cambios → `F = 1.434.617`; `U = 896,64`; `Ahorro = 303,36` (la planilla mostraba 897 y 303
porque redondeaba a enteros).

### 4.4 Pagos y pendiente

- **RN-20 – Pagado y pendiente.** `Pagado(gasto) = Σ pagos del gasto`;
  `Pendiente(gasto) = monto − Pagado`;
  `Total pendiente del mes = Σ Pendiente de los gastos del mes`. Pagos y pendiente son
  siempre en ARS, también en los gastos en dólares (sobre su monto en ARS).
- **RN-21 – Tope del pago.** Un pago parcial debe ser > 0 y ≤ pendiente del gasto. No se puede
  pagar de más.
- **RN-22 – Tilde "pagado".** Marcarlo registra un pago por el pendiente (queda en 0). Un
  gasto con pendiente 0 se ve con el tilde marcado, se haya pagado con el tilde o con
  parciales. **Destildarlo borra todos los pagos del gasto** (pendiente = monto).
- **RN-23 – Monto menor a lo pagado.** No se puede bajar el monto de un gasto por debajo de lo
  ya pagado: se rechaza con un mensaje que indique el monto pagado. En un gasto en dólares
  vale para el monto en ARS resultante de cualquier edición (monto USD, cotización o moneda).

### 4.5 Cuotas

- **RN-24 – Cuota de un mes.** Para un plan con primera cuota en `P` y `N` cuotas, en el mes
  `M`: `n = (año_M − año_P) × 12 + (mes_M − mes_P) + 1`.
  El plan está **activo** en `M` si `1 ≤ n ≤ N`, no está cancelado en `M` (RN-31) y `M` no es
  una cuota omitida (RN-52). La cuota se muestra como "n/N".
- **RN-25 – Última cuota.** `Última = P + (N − 1) meses`. Ej.: primera 2026-08, 3 cuotas →
  última 2026-10. Si el plan se canceló, la última cuota es el mes anterior al primer mes sin
  cuota (RN-31).
- **RN-26 – Plan terminado.** Terminado en `M` si `n > N`. No genera gastos después de su
  última cuota.
- **RN-27 – Monto liberado.** La cuota se paga en el mes de la última cuota; la plata se libera
  **desde el mes siguiente**. Ej.: Avant termina en marzo → "desde abril: +41.117 libres".
- **RN-28 – Monto restante.** Respecto del mes seleccionado: `(N − n) × monto_cuota` (cuotas
  posteriores a la del mes). Si el plan no empezó, `N × monto_cuota`; si terminó o está
  cancelado, 0.
- **RN-29 – Validaciones del plan.** Cantidad de cuotas: entero ≥ 1 y **como máximo 600**
  (50 años; más que eso es un error de tipeo). Con más de 600 se rechaza con el mensaje "La
  cantidad de cuotas es demasiado grande." Monto de cuota > 0, en ARS (las cuotas en dólares
  están fuera de la v1). La primera cuota puede ser un mes pasado (deudas ya empezadas, ej.
  Avant en 3/3).
- **RN-30 – Alcance de alta y edición.** Crear o editar un plan crea, actualiza o elimina sus
  gastos **solo en el mes actual (calendario) y en los meses futuros que ya existan**. Los
  meses anteriores al mes actual nunca se modifican, aunque la primera cuota sea anterior y
  aunque el mes seleccionado sea otro.
  - Si la cuota del mes actual **ya tiene pagos**, se conserva tal cual (monto y pagos) y el
    cambio se aplica desde el mes siguiente.
  - Si **no tiene pagos**, el cambio se aplica desde el mes actual.
  - La misma regla vale para la cuota de cada mes futuro existente: si ya tiene pagos, se
    conserva tal cual.
  - En los meses con cuota omitida (RN-52) no se regenera la cuota.
  - Si el mes actual todavía no fue creado, no se genera nada en él; la cuota aparece cuando
    se cree (RN-09).
- **RN-31 – Cancelación anticipada.** Cancelar un plan registra el **primer mes sin cuota**:
  - el mes actual, si su cuota no tiene pagos (o no existe): se elimina la cuota del mes
    actual;
  - el mes siguiente, si la cuota del mes actual ya tiene pagos: esa cuota se conserva y pasa
    a ser la última.
  Se eliminan las cuotas de los meses futuros existentes desde el primer mes sin cuota (salvo
  las que ya tengan pagos, RN-30) y no se generan más. Los meses anteriores conservan sus
  cuotas.

### 4.6 Gastos compartidos y "me deben"

- **RN-32 – Partes iguales.** Con `p` personas elegidas participan `p + 1`. La parte de cada
  persona es `monto ÷ (p + 1)` truncado al centavo; la parte del usuario es
  `monto − Σ partes de las personas` (se queda con los centavos sobrantes).
  Ej.: Internet 38.700 entre 3 → 12.900 c/u. Edenor 66.281 entre 3 → Sofía 22.093,66,
  Marsu 22.093,66, usuario 22.093,68. En un gasto en dólares, `monto` es su monto en ARS.
- **RN-33 – Partes editadas a mano.** El usuario edita las partes de las personas; la del
  usuario siempre se calcula como `monto − Σ partes de las personas`. Si da negativa, se
  rechaza con un mensaje. Una parte editada a mano queda marcada como "manual".
- **RN-34 – Cambio de monto de un gasto compartido.**
  - Las partes automáticas se recalculan como `nuevo monto ÷ (p + 1)` truncado; las manuales
    se mantienen; la parte del usuario vuelve a ser `monto − Σ partes de las personas`. Si
    queda negativa, se rechaza el cambio de monto con un mensaje.
  - Para cada parte que ya estaba cobrada:
    - si su monto **no cambió** (ej. parte manual), **sigue cobrada**;
    - si su monto **cambió**, vuelve a **pendiente** (tilde desmarcado) y se muestran lo ya
      cobrado y la diferencia: `diferencia = parte nueva − ya cobrado`. Si la diferencia es
      positiva, es lo que falta cobrar; si es negativa, se muestra como "a devolver".
  - Marcar de nuevo el tilde registra como cobrada la parte nueva completa.
  - En un gasto en dólares, cualquier edición que cambie su monto en ARS (monto USD,
    cotización del gasto o moneda) es un cambio de monto a los efectos de esta regla.
- **RN-35 – Total adeudado por persona (acumulado).**
  `Total(persona) = Σ (parte − ya cobrado) de sus partes no marcadas como cobradas, de todos los meses + Σ ítems manuales no cobrados`.
  Una parte que nunca se cobró aporta la parte completa; una con diferencia aporta la
  diferencia (negativa si es "a devolver").
- **RN-36 – Sin efecto en el cálculo del mes.** Lo que le deben (cobrado o no) no modifica
  `G`, pesos a cubrir, USD a cambiar ni ahorro. Se muestra aparte.
- **RN-37 – Copia al mes nuevo.** Al copiar un gasto fijo compartido se copian las personas y
  las partes (automáticas o manuales). Las partes nuevas quedan **no cobradas** (ya cobrado = 0).
  Si es un fijo en dólares y su monto en ARS cambia al copiarse (RN-57):
  - las partes automáticas se calculan sobre el nuevo monto en ARS (RN-32) y las manuales se
    mantienen, como en RN-34;
  - si con las partes manuales la parte del usuario quedaría **negativa**, **todas** las
    partes de ese gasto en el mes nuevo vuelven a ser automáticas (partes iguales, RN-32) y,
    al terminar de crear el mes, la app avisa: "Las partes de X se repartieron en partes
    iguales porque cambió el monto." (X = nombre del gasto). El mes se crea igual; las partes
    del mes anterior no cambian.

### 4.7 Resumen, capacidad y meta

- **RN-38 – Capacidad de endeudamiento (ARS/mes).** Lo que sobra después de pagar todo y
  ahorrar la meta:
  `Capacidad = S × K − Σ gastos fijos mensuales del mes − Σ gastos en cuotas del mes − Meta × K`.
  - Gastos fijos y cuotas por su monto completo en ARS (RN-12), también los fijos en dólares
    (con su monto en ARS guardado).
    No entran los pagos únicos ni los ingresos extra.
  - Sin meta cargada, `Meta = 0`.
  - Puede ser negativa: se muestra en rojo con el aviso "Sin capacidad de endeudamiento".
  - Sin cotización: "Cargá la cotización" (RN-18).
- **RN-39 – Avance de la meta.** `Avance = Ahorro ÷ Meta × 100 %`. La barra se limita entre
  0 % y 100 %; el número muestra el valor real (puede superar 100 %). Con ahorro negativo la
  barra queda en 0 %. Sin meta, no se muestra la barra.
- **RN-40 – Total que le deben.** Suma de RN-35 para todas las personas, acumulada. No depende
  del mes seleccionado.

### 4.8 Previsiones

- **RN-41 – Meses previstos.** Los 12 meses siguientes al mes actual (calendario), sin incluir
  el actual e independientemente del mes seleccionado. Ej.: mes actual 2026-10 → 2026-11 a
  2027-10.
- **RN-42 – Gastos estimados del mes `M`.**
  `G(M) = Σ gastos fijos mensuales del mes actual (completo aunque sea compartido) + Σ cuotas de planes activos en M` (RN-24, sin cuotas omitidas).
  - Fijos en ARS: con su mismo monto.
  - Fijos en dólares: `monto en USD × K_actual` (con RN-53), la misma lógica que al crear un
    mes nuevo (RN-57), y **no** su monto en ARS guardado. Si el mes actual no tiene
    cotización, se usa la cotización guardada en el gasto. Ej.: Claude US$ 20,00 guardado a
    1.600 (32.000) con cotización actual 1.700 → 34.000 en cada mes previsto.
  - **No** incluye pagos únicos.
- **RN-43 – USD a cambiar y ahorro estimados.** `U(M) = G(M) ÷ K_actual` (RN-15);
  `Ahorro(M) = S_actual − U(M)`. **No** incluye ingresos extra ni cambios realizados. Sin
  inflación. `S_actual` y `K_actual` son el sueldo y la cotización del mes actual.
- **RN-44 – Cuotas liberadas.** En la fila del mes `M` se listan los planes cuya última cuota
  es el mes anterior a `M`, con el monto liberado (RN-27). Si un plan termina en el mes actual,
  su liberación aparece en la primera fila. Si termina en el último mes de la tabla, su
  liberación queda fuera de la tabla.
- **RN-45 – Datos faltantes.** Si el mes actual no existe en la app, la previsión no se calcula
  y muestra "Creá el mes AAAA-MM para ver la previsión". Si existe pero no tiene cotización,
  muestra solo los gastos ARS (los fijos en dólares con la cotización guardada en cada gasto,
  RN-42) y avisa que falta la cotización.

### 4.9 Gráficos

- **RN-46 – Por categoría.** Suma de la **parte propia** del usuario de cada gasto del mes
  (en ARS, también para los gastos en dólares), agrupada por categoría. Categorías sin gastos
  no aparecen.
- **RN-47 – Ahorro.** Un punto por mes del historial, con RN-17 y la cotización guardada en
  cada mes. Los meses sin ahorro calculable (RN-18) se muestran vacíos.
- **RN-48 – Previsión.** Los 12 valores `G(M)` de RN-42.

### 4.10 Bajas y archivado

- **RN-49 – Archivar y desarchivar.** Una categoría, medio de pago o persona **en uso** (con
  al menos un gasto, plan, parte o ítem asociado, de cualquier mes) no se borra: se archiva.
  Archivada, no aparece en las listas para cargar datos nuevos, pero sigue apareciendo en el
  historial y en "me deben", y los gastos fijos y cuotas que la usan se siguen copiando a los
  meses nuevos (RN-09). Se puede **desarchivar**, y vuelve a aparecer en las listas. Una que
  no está en uso se borra.
- **RN-50 – Nombres.** Los nombres de categorías, medios de pago y personas no pueden estar
  vacíos ni repetirse (sin distinguir mayúsculas), incluidos los archivados.
- **RN-51 – Borrar un gasto.** Con confirmación. Borra también sus pagos y sus partes
  compartidas.
- **RN-52 – Borrar la cuota de un mes.** Borrar a mano el gasto de una cuota borra solo la de
  ese mes; el plan sigue activo en los demás meses. Ese mes queda registrado como **cuota
  omitida**: la cuota no se vuelve a generar en ese mes (ni al editar el plan, ni al borrar y
  volver a crear el mes) y no se cuenta en la previsión.

### 4.11 Gastos en dólares

- **RN-53 – Conversión USD → ARS.**
  `monto_ars_cent = redondeo(monto_usd_cent × cotizacion_cent ÷ 100)`, al centavo más cercano,
  mitad hacia arriba (RN-03).
  - US$ 20,00 × 1.600 → `2000 × 160000 ÷ 100 = 3200000` → $ 32.000.
  - US$ 19,99 × 1.432,50 → `1999 × 143250 ÷ 100 = 2863567,5` → `2863568` (28.635,68), en
    pantalla "US$ 19,99 × $ 1.432,50 = $ 28.636" (cotización con decimales, monto en ARS sin
    decimales, RN-04).
  La vista previa del alta y la edición (RF-44) usa la misma fórmula que el valor guardado.
- **RN-54 – Validaciones de un gasto en dólares.**
  - Monto en USD > 0 (RN-05) y cotización del gasto > 0 (RN-06); ambos obligatorios. Se
    rechazan cero, negativos, vacíos y texto no numérico, con un mensaje.
  - La cotización del gasto se sugiere con la cotización del mes. Si el mes no tiene
    cotización, el campo queda vacío y no se puede guardar el gasto hasta completarlo.
  - El monto en ARS resultante debe ser > 0 (RN-05): si el redondeo da 0 (ej. US$ 0,01 ×
    0,40 = 0,004), se rechaza.
  - Solo los tipos "fijo mensual" y "pago único" pueden ser en USD. Las cuotas son siempre en
    ARS.
- **RN-55 – Monto en ARS fijo.** El monto en ARS de un gasto en dólares se calcula al
  guardarlo y queda fijo. **No** cambia si después cambia la cotización del mes: en ese caso
  cambian USD a cambiar y ahorro (porque cambia `K`), pero no `G`. Solo cambia si el usuario
  edita el monto en USD, la cotización del gasto o la moneda (RN-56), y en ese caso:
  - se recalcula con RN-53;
  - si queda por debajo de lo ya pagado, se rechaza la edición (RN-23);
  - si el gasto es compartido, las partes se tratan según RN-34.
  El monto en ARS es el que se usa en todos los cálculos del mes (RN-12, RN-20, RN-22, RF-22,
  RN-32, RN-38, RN-46). La previsión de meses futuros usa en cambio la cotización actual
  (RN-42).
- **RN-56 – Cambio de moneda al editar.** Está permitido.
  - **ARS → USD:** se piden monto en USD y cotización del gasto (sugerida: la del mes), igual
    que en el alta; el monto en ARS pasa a ser el resultado de RN-53.
  - **USD → ARS:** se pide el monto en ARS (obligatorio, RN-05); el monto en USD y la
    cotización del gasto se descartan.
  - En ambos casos aplican RN-23 (no quedar por debajo de lo pagado) y RN-34 (compartidos).
- **RN-57 – Copia de un fijo en dólares al mes nuevo.** Se copia con el **mismo monto en USD**
  y con cotización del gasto = **cotización del mes nuevo**; si el mes nuevo no tiene
  cotización, conserva la cotización del gasto copiado. El monto en ARS se recalcula con RN-53.
  Si después se cambia la cotización del mes nuevo, el gasto copiado no cambia (RN-55).
  Si el gasto es compartido, las partes se tratan según RN-37.
  Consecuencia aceptada por el usuario: si en el mes anterior había usado una cotización con
  recargo (ej. dólar tarjeta), en el mes nuevo el gasto toma la cotización del mes y, si
  corresponde, tiene que corregirla a mano.
- **RN-58 – Sin impuestos.** La app no calcula impuestos, percepciones ni recargos (dólar
  tarjeta, etc.). El usuario escribe directamente la cotización que corresponda.
- **RN-59 – Actualización de la base existente.** La base del usuario ya tiene datos reales.
  - **Versión de la base:** la estructura se identifica con un número de versión guardado en
    la propia base. Una base sin gastos en dólares es la **versión 0**; con gastos en dólares,
    la **versión 1**. La actualización solo se aplica si la base está en una versión menor;
    así no se repite al volver a abrir la app.
  - **Respaldo previo:** antes de modificar la estructura se crea una copia completa de la
    base en `datos-privados/respaldos/gastos-AAAAMMDD-HHMMSS.db` (fecha y hora del momento
    del respaldo). Si el respaldo no se puede crear, la actualización no se hace y la app
    avisa.
  - **Todo o nada:** la actualización (agregar las columnas y pasar a versión 1) se hace en
    un solo paso: o se completa entera, o la base queda exactamente como estaba (versión 0,
    sin columnas nuevas, mismos datos) y la app avisa.
  - **Resultado:** todos los gastos existentes quedan con moneda ARS, sin monto en USD ni
    cotización del gasto, y con exactamente los mismos montos, pagos y partes que antes.

### 4.12 Importar Excel (v2)

La importación no puede depender del formato de la planilla del usuario: las reglas de
detección (RN-61 a RN-66) valen para cualquier `.xlsx`. Los ejemplos usan la planilla de
referencia, cuyas columnas son: C = nombres, D = montos ("Gastos" / "Monto") y E = "Pagado"
o "Total deudas"; los bloques de personas tienen el nombre en D y el monto en E.

Los textos entre comillas de esta sección son **exactos** (se verifican en las pruebas). En
los ejemplos, "Octubre 2026" es el mes destino, "Sofía" la persona y los números, los de la
fila; en la app se reemplazan por los valores reales, con el formato de RN-04 y "US$" delante
de los montos en USD.

- **RN-60 – Archivo aceptado.**
  - Solo archivos `.xlsx`. Un archivo con otra extensión (`.xls`, `.xlsm`, `.csv`, `.ods`…),
    dañado, protegido con contraseña o que no es realmente un `.xlsx` (ej. un `.txt`
    renombrado) se rechaza con el mensaje "No se pudo leer el archivo. Solo se aceptan
    archivos .xlsx de Excel." y no cambia nada.
  - El archivo **solo se lee**: no se modifica, no se copia a la carpeta de la app y no se
    guarda su ruta. Después de importar, en la app solo quedan los datos confirmados; borrar o
    mover el Excel no afecta a la app.
  - Se importa **una hoja por vez** (la elegida, RF-50). Para importar otra hoja se repite la
    importación. Las hojas que no tienen celdas (ej. hojas que solo tienen un gráfico) no se
    ofrecen.
  - Se leen todas las filas y columnas de la hoja, incluidas las ocultas.
  - Si la hoja elegida no tiene ninguna celda con texto o número: "No se encontraron datos en
    la hoja X." El usuario puede elegir otra hoja u otro archivo, o cancelar.
  - Si la hoja solo tiene filas incompletas (ninguna con texto y monto), la lista se muestra
    igual, con el aviso "No se encontraron filas con un texto y un monto." (se pueden
    completar a mano).
- **RN-61 – Contenido de las celdas.** Cada celda cuenta como:
  - **número:** celda numérica de Excel (el valor se toma tal cual), o texto que se puede leer
    como número en formato argentino (RN-62);
  - **texto:** cualquier otro texto, sin los espacios del principio y del final;
  - **vacía:** celda vacía o solo con espacios, fechas, horas, valores verdadero/falso y
    errores de Excel (`#DIV/0!`, `#REF!`, etc.).
  - **Fórmulas:** se usa el valor calculado que Excel guardó en el archivo, y se clasifica
    igual que arriba. Si una fórmula no tiene valor guardado (archivo creado por otro programa
    y nunca abierto y guardado en Excel), la celda cuenta como vacía y arriba de la lista se ve
    el aviso "Hay N fórmulas sin valor calculado (ej. D9). Abrí el archivo en Excel, guardalo
    y volvé a importarlo para ver esos montos." Se puede seguir con la importación igual.
  - **Celdas combinadas:** el valor está en la primera celda (arriba a la izquierda); las demás
    cuentan como vacías.
- **RN-62 – Números escritos como texto.** Se leen con formato argentino: punto = separador
  de miles, coma = decimales.
  - "82.000" → 82.000; "1.050.000" → 1.050.000; "66.020,12" → 66.020,12; "260000" →
    260.000; "41116,66" → 41.116,66.
  - Se aceptan un "$" y espacios antes del número ("$ 82.000", "$41.116,66") y un "-"
    adelante (negativo, ver RN-68).
  - El punto solo vale como separador de miles si separa grupos de exactamente 3 dígitos. Si
    no ("82.5", "1.5000"), el texto **no** es un número: se trata como texto.
  - Un texto con letras u otros símbolos no es número ("Monotributo 66.020,12", "3/3",
    "US$ 20").
  - Los números de Excel (no texto) se toman tal cual, sin interpretar puntos ni comas: el
    número 41116,66 de Excel → 41.116,66.
  - Todos los montos se pasan a centavos (RN-01). Si tienen más de 2 decimales se redondean al
    centavo más cercano, mitad hacia arriba (RN-03): 22.093,666 → 22.093,67.
  - Los montos se toman en **ARS**, salvo el de la fila de sueldo, que se toma en **USD**
    (RN-70). La importación no convierte monedas.
- **RN-63 – Armado de las filas detectadas.** Para cada fila del Excel se recorren sus celdas
  de izquierda a derecha:
  1. Cada celda de **texto** empieza una fila detectada nueva, con ese texto como nombre.
     Excepción: un texto en una columna de pagado o de cobrado que es el **valor** de una fila
     (RN-64) no empieza una fila nueva. Un texto en esas columnas que no es valor de ninguna
     fila cierra la columna y sí empieza una fila nueva, como cualquier texto (RN-64).
  2. El primer **número** después de ese texto (antes del texto siguiente) es su **monto**. Un
     número en una columna de pagado es su **pagado** y uno en una columna de cobrado es su
     **cobrado** (RN-64); esos números nunca empiezan una fila nueva. Los demás números se
     descartan (ej. columnas "Total deudas" u "Objetivo" de la planilla).
  3. Cada **número** que no tiene un texto antes en esa fila del Excel (y no está en una
     columna de pagado o de cobrado) forma una fila detectada **sin nombre**.
  Resultado:
  - Filas con nombre y monto → **lista principal**.
  - Filas con nombre y sin monto (títulos, encabezados, "Obra social" sin número) y filas sin
    nombre (números sueltos, como los totales debajo de su título) → grupo **"Filas
    incompletas"**, con tipo "ignorar". Se pueden completar y cambiar de tipo (RF-53); hasta
    que se complete lo que falta no se pueden importar, salvo como sueldo, que no necesita
    nombre (RN-70).
  - Una fila detectada que termina **sin monto** en el Excel queda también **sin pagado**: el
    número que tenga en una columna de pagado se descarta (RN-64), como el pagado de cualquier
    fila sin monto. Si el usuario después completa el monto en la revisión, la fila sigue sin
    pagado (si corresponde, lo escribe a mano, RF-53). Ej.: "Luz" sin monto y un 3 en la
    columna "Pagado" → fila incompleta "Luz", sin pagado; completándola con monto 1 y tipo
    gasto fijo, se importa sin pagos (no aparece "El pagado ($ 3) es mayor que el monto
    ($ 1).").
  - Cada fila incompleta muestra la nota "Falta el monto. Se ignora." o "Falta el nombre. Se
    ignora.". Si el usuario le cambia el tipo sin completar lo que falta, la nota pasa a ser
    el error de RN-68 ("Falta el monto." / "Falta el nombre."). Una fila incompleta que se
    completa sigue en el grupo "Filas incompletas" (no se mueve de lugar).
  - Ejemplos de la planilla: "Alquiler | 260000" → fila con monto 260.000; "Arca deuda |
    84000 | 84000" → monto 84.000, y el segundo 84.000 (columna "Total deudas") se descarta;
    "Edenor" y el "66.281" de la fila de abajo → dos filas incompletas (el usuario puede
    escribir "Edenor" como nombre del 66.281); el "1200" debajo de "Sueldo" → fila sin
    nombre, que el usuario puede marcar como sueldo.
  - Las filas del Excel totalmente vacías no generan nada.
- **RN-64 – Columnas de pagado y de cobrado.** El **encabezado** de una columna, para una
  celda, es la primera celda de texto que hay **arriba, en la misma columna**, sin contar los
  textos que se leyeron como **valor** de una fila (ver "Textos dentro de una columna de
  pagado o de cobrado", abajo) y **sin pasar por una fila del Excel totalmente vacía**. Los
  encabezados se comparan según RN-67.
  - **Alcance de un encabezado.** Un "Pagado" o un "Cobrado" vale desde su celda hacia abajo
    hasta la **primera fila del Excel totalmente vacía** o hasta el **texto siguiente** en esa
    columna (que no sea valor de una fila), lo que llegue primero. Una fila totalmente vacía
    **cierra todos los encabezados** de todas las columnas, igual que cierra los bloques
    (RN-65): debajo de ella, una columna no es de pagado ni de cobrado hasta que aparezca un
    encabezado nuevo. Así, un "Pagado" de una tabla no se aplica a otra tabla separada por una
    fila vacía. Ej.: "Pagado" en E1, "Luz | 5 | 3" en la fila 2, la fila 3 vacía y un 99 en
    E4 → Luz trae pagado 3; el 99 es un número sin nombre (RN-63), no un pagado.
  - **Columna de pagado:** su encabezado es "Pagado", "Pago", "Pagos" o "Abonado". Un número
    en esa columna es el pagado de la fila y se aplica según RN-69. Si la fila no tiene monto
    en el Excel (fila incompleta), ese número se descarta y la fila queda sin pagado, también
    si el usuario completa el monto después (RN-63). Ej.: en "Gasto del Mes"
    la columna E tiene el encabezado "Pagado"; en la tabla "Deudas" la columna E dice "Total
    deudas", y por eso su 84.000 no es un pago. Si el Excel no tiene columna de pagado,
    ninguna fila trae pagado. Otros encabezados ("Pagué", "Pagado?") no se reconocen.
  - **Columna de cobrado:** su encabezado es "Cobrado". Solo se usa en las filas de tipo "me
    deben" (en las demás se descarta). Como los ítems "me deben" no tienen cobro parcial
    (RF-34), el valor se lee así:
    - vacío o 0 → no cobrado;
    - un número igual al monto de la fila → **cobrado**;
    - un texto "sí", "si", "x", "✓", "ok" o "cobrado" → **cobrado**;
    - cualquier otro valor (un número distinto del monto, o textos como "no" o "falta") → no
      cobrado, con la nota "En la columna Cobrado dice "V"; los ítems 'me deben' no tienen
      cobro parcial, quedó como no cobrado." (V = el valor de la celda, con el formato de
      RN-04 si es un número).
    El usuario puede cambiar el tilde "cobrado" de cualquier fila "me deben" en la revisión
    (RF-53).
  - **Textos dentro de una columna de pagado o de cobrado.** Un texto en una de estas
    columnas es una de dos cosas:
    - **El valor de una fila**, si en la misma fila del Excel, a su izquierda, hay una fila
      detectada con nombre y monto (ej. una "x" en la columna "Cobrado" al lado de "Internet |
      12900"). En una columna de pagado, ese texto se descarta: el pagado tiene que ser un
      número, así que la fila queda sin pagado. En una columna de cobrado, se lee con las
      reglas de arriba. En los dos casos no empieza una fila nueva y la columna sigue igual.
    - **Un encabezado nuevo**, en cualquier otro caso (la fila del Excel no tiene, a su
      izquierda, una fila con nombre y monto). El texto **cierra** la columna y pasa a ser el
      encabezado de las celdas de abajo: si es un nombre de pagado ("Pagado", "Pago",
      "Pagos", "Abonado") o "Cobrado", la columna sigue siendo de ese tipo; si no, deja de
      ser de pagado o de cobrado. Como cualquier otro texto, empieza una fila detectada
      (incompleta si no tiene monto, RN-63) y puede ser un título (RN-65).
    Ej. en la planilla de referencia: "Falta por pagar" (E8) está en la columna "Pagado" de
    "Gasto del Mes", en una fila del Excel sin ninguna fila con monto ("total" en D8 no tiene
    monto): cierra la columna. Por eso el 1.004.917 de E9 no es el pagado de nadie: es un
    número sin nombre (RN-63), y "Falta por pagar" es una fila incompleta más, como "Pagado"
    o "Gastos".
- **RN-65 – Títulos de bloque y personas.**
  - **Fila pegada.** Una fila detectada con nombre está **pegada** si la celda que está
    **justo arriba de su nombre, en la misma columna**, es el nombre de otra fila detectada
    (con o sin monto, incluido un título). Si esa celda está vacía, tiene un número o no
    existe (primera fila de la hoja), la fila no está pegada.
  - **Título.** Un título es el nombre de una fila incompleta sin monto (texto sin monto en
    su fila, RN-63) que **no está pegada**. Un texto sin monto pegado **no** es título: es
    una fila incompleta más del bloque en el que está.
    Ej. en la planilla de referencia: "Gasto del Mes" (C1, primera fila), "Deudas" (C11,
    arriba vacía), "Sueldo" (B18), "Deudas sofia" (D21) y "Marsu" (D26) son títulos;
    "Deuda freezer" (C14, justo debajo de "Avant Service…") y "Obra social" (C16, justo
    debajo de "Gym") están pegadas y no son títulos. Los encabezados de columna con la celda
    de arriba vacía o con un número ("Gastos" y "Pagado" en la fila 2, "total" y "Falta por
    pagar" en la fila 8, "Monto" y "Total deudas" en la fila 11) también son títulos, pero
    sus bloques no tienen filas, porque debajo, en su columna, no hay nombres.
  - **Bloque.** El bloque de un título está formado por las filas detectadas con nombre que
    están debajo, con el nombre en la misma columna que el título (o en una de las columnas
    que cubre, si el título es una celda combinada). Recorriendo hacia abajo, el bloque
    **termina** solo en:
    - la primera **fila del Excel totalmente vacía**, o
    - el **título siguiente** en esa columna.
    Una fila del Excel con contenido pero con la celda de esa columna vacía **no** corta el
    bloque: se saltea (ej. la fila 2, con "Gastos" y "Pagado" en D y E, y las filas 8 y 9 no
    cortan "Gasto del Mes"; la fila 10, vacía, sí). Un título de **otra** columna tampoco lo
    corta. Las filas incompletas pegadas quedan **dentro** del bloque, como filas incompletas
    (siguen en "ignorar", RN-66). Los títulos y las filas sin nombre (números sueltos) no
    pertenecen a ningún bloque.
  - Con la planilla de referencia: "Gasto del Mes" → filas 3 a 7; "Deudas" → filas 12, 13 y
    15, más las incompletas "Deuda freezer" (14) y "Obra social" (16); "Deudas sofia" → filas
    22 a 24; "Marsu" → filas 27 y 28.
  - Si el título contiene, como palabra, el nombre de una **persona activa** (comparando según
    RN-67), las filas del bloque se proponen como "me deben" con esa persona. Ej.: "Deudas
    sofia" → Sofía; "Marsu" → Marsu.
  - Si el título no contiene el nombre de ninguna persona activa (la persona no existe, está
    archivada, o el título es algo como "Deudas"), el título no propone nada: sus filas siguen
    las demás reglas de RN-66. El usuario puede marcarlas como "me deben" a mano y elegir o
    crear la persona (RN-72).
  - Si el título contiene el nombre de dos o más personas activas, se propone "me deben" sin
    persona: el usuario tiene que elegirla.
  - **Agrupación de la lista de revisión.** La lógica entrega, para **cada fila detectada con
    nombre** (de la lista principal y también las incompletas pegadas), el título del bloque
    al que pertenece (el texto del título tal como está en el Excel), o ninguno. La lista
    principal se agrupa por ese título, con los bloques y las filas en el orden del Excel. Las
    filas sin título van juntas en un bloque "Otras filas"; si ninguna fila tiene título, hay
    un solo bloque, "Filas detectadas". Los bloques sin filas en la lista principal no se
    muestran. Las filas incompletas (también las pegadas a un bloque) se muestran en su propio
    grupo "Filas incompletas" (RN-63), no dentro del bloque: así cada bloque muestra solo lo
    que se puede importar tal como viene y su conteo "se importan N de M" cuenta solo esas
    filas.
- **RN-66 – Tipo propuesto.** Se aplica la primera regla que se cumple:
  1. **Ignorar** si:
     - el nombre contiene la palabra "total" (ej. "Total", "total", "Total de servicios C/U",
       "Total deudas");
     - el nombre es igual a "Gastos fijos sin deuda", "Capacidad de Endeudamiento", "Gastos
       en dolares", "Falta por pagar" o "Tarjetas de Credito" (comparando según RN-67).
       "Tarjetas de Credito" se ignora porque sus gastos se cargan uno por uno (RF-22, §6);
     - el monto sale de una fórmula de suma (`SUM`), es decir, es un valor calculado;
     - el monto es 0 o negativo (RN-68).
  2. **Me deben**, con la persona del título, si la fila está en el bloque de un título con
     nombre de persona (RN-65).
  3. **Cuota** si el nombre contiene "n/N" (dos números enteros separados por "/", con o sin
     espacios) con 1 ≤ n ≤ N y N ≤ 600 (tope de RN-29). Se proponen cuota actual n y cantidad
     de cuotas N. Ej.: "Avant Service cuota 3/ 3 $41.116,66" → cuota 3 de 3. Si n = 0, n > N
     (ej. "Cumple 15/10", que parece una fecha) o N > 600 (ej. "Algo 601/601"), no se propone
     cuota.
  4. **Gasto fijo mensual** en cualquier otro caso.
  - Las filas incompletas se proponen siempre como "ignorar" (RN-63).
  - Es solo una propuesta: el usuario puede cambiar el tipo de cualquier fila.
- **RN-67 – Comparación de nombres.** Para "ya existe", "repetida en el archivo", el aviso de
  posible gasto compartido (RN-72), títulos con personas, los encabezados de pagado y de
  cobrado, los textos de cobrado y la lista de RN-66, los textos se comparan **sin distinguir
  mayúsculas ni acentos, e ignorando los espacios del principio, del final y los repetidos en
  el medio**: "Telefono" = "Teléfono"; "Deudas sofia" contiene "Sofía"; "ABONADO" =
  "Abonado". El nombre se guarda tal como quedó en la fila (sin los espacios del principio y
  del final).
- **RN-68 – Validaciones por fila.** Una fila **se importa** si está tildada y su tipo no es
  "ignorar". Cada fila que se importa debe cumplir:
  - nombre no vacío (salvo sueldo, RN-70);
  - monto > 0 (RN-05). Las filas con monto 0 o negativo en el Excel (ej. un descuento
    "-5.000") se proponen como "ignorar" con la nota "Monto no válido. Si querés importarla,
    corregí el monto."; si el usuario les cambia el tipo, tiene que corregir el monto;
  - los montos corregidos a mano siguen las reglas de entrada del resto de la app (RN-04,
    RN-05);
  - gastos y cuotas: con categoría (RN-75);
  - cuota: cantidad de cuotas entera entre 1 y 600 y cuota actual entera entre 1 y la
    cantidad (RN-29);
  - me deben: con persona (RN-72);
  - pagado según RN-69;
  - como máximo una fila de sueldo (RN-70).
  Si una fila que se importa no cumple, muestra el error y el botón Confirmar no se puede usar
  hasta que el usuario la corrija, la pase a "ignorar" o la destilde. Tampoco se puede
  confirmar si no hay ninguna fila para importar: "No hay filas para importar." Las notas y
  avisos que no son errores (cobrado no reconocido, RN-64; posible gasto compartido, RN-72;
  "ya existe" y "repetida en el archivo", RN-74; notas de cuota y de sueldo, RN-70 y RN-71)
  no impiden confirmar.
  - **Textos de los errores de una fila:**

    | Error | Texto |
    |---|---|
    | Falta el nombre | "Falta el nombre." |
    | Falta el monto | "Falta el monto." |
    | Monto 0 o negativo | "El monto tiene que ser mayor a 0." |
    | Gasto o cuota sin categoría | "Elegí una categoría." |
    | "Me deben" sin persona | "Elegí una persona." |
    | Cuota sin cuota actual o sin cantidad | "Indicá la cuota actual y la cantidad de cuotas." |
    | Cuota actual fuera de rango | "La cuota actual tiene que estar entre 1 y la cantidad de cuotas." |
    | Cantidad de cuotas no válida | "La cantidad de cuotas tiene que ser un número entero de 1 o más." |
    | Cantidad de cuotas mayor que 600 | "La cantidad de cuotas es demasiado grande." (RN-29) |
    | Pagado mayor que el monto | "El pagado ($ 12.000) es mayor que el monto ($ 10.000)." (RN-69; con centavos si los dos montos se ven iguales) |
    | Pagado negativo | "El pagado no puede ser negativo." |
    | Dos o más sueldos | "Marcaste 2 filas como sueldo; dejá una sola." (RN-70) |
    | Cuota cuya primera o última cuota cae en un año no válido (RN-07) | "Con esta cuota, el plan quedaría en un año no válido. Revisá la cuota actual y la cantidad." (sin nota de plan) |
    | Categoría o persona archivada o borrada mientras dura la revisión | "Elegí una categoría." / "Elegí una persona." |

  - **Estado al pie de la lista.** Siempre dice por qué se puede o no confirmar:
    - todo bien: "Se importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el
      sueldo." (mencionando solo lo que hay, en singular o plural según corresponda; el
      número de filas cuenta todas las que se importan, incluida la de sueldo);
    - con errores: "Hay 2 filas con errores. Corregilas, ignoralas o destildalas para
      continuar.";
    - con dos o más sueldos: "Marcaste 2 filas como sueldo; dejá una sola.";
    - sin filas para importar: "No hay filas para importar.".
  - **Tilde y tipo "ignorar".** Una fila de tipo "ignorar" no tiene tilde y no se puede
    tildar. Al cambiar el tipo de una fila de "ignorar" a cualquier otro, la fila **se tilda
    sola**, **también si está marcada "ya existe"** (decisión del usuario, 2026-10-13); en ese
    caso su nota pasa a la versión tildada de RN-74 (ej. "Ya existe en Octubre 2026. Si la
    importás, queda repetida.").
    Pasa lo mismo al aceptar el diálogo de edición de la fila o con la acción de bloque de
    RN-78. Al pasar una fila a "ignorar", queda sin tilde. Fuera de esos casos, cambiar el
    tipo no cambia el tilde (RN-74).
  - **Edición de una fila.** Los datos de una fila (nombre, monto, pagado, categoría, cuota,
    persona) se corrigen en un diálogo que no se puede aceptar con errores, salvo que el tipo
    elegido sea "ignorar". Así, los errores que quedan en la lista son los que vienen del
    Excel o de cambiar el tipo en la lista.
- **RN-69 – Pagado al importar.** Solo para gastos fijos, pagos únicos y cuotas. Con `M` =
  monto y `P` = pagado de la fila:
  - `P` vacío o 0 → sin pagos;
  - `P = M` → pagado completo: un pago por el monto (como el tilde, RN-22);
  - `0 < P < M` → un pago parcial por `P`; pendiente `M − P`;
  - `P > M` → error en la fila: "El pagado ($ P) es mayor que el monto ($ M)." (montos con el
    formato de RN-04, ej. "El pagado ($ 12.000) es mayor que el monto ($ 10.000)."). No se
    puede confirmar hasta que el usuario suba el monto, baje o borre el pagado, o no importe
    la fila (RN-21, RN-23). La app no recorta el pagado por su cuenta, para no esconder un
    error del Excel. Si los dos montos, redondeados a pesos (RN-04), se ven iguales (la
    diferencia es de centavos), en este mensaje los dos se muestran **con sus centavos**
    (siempre 2 decimales, con punto de miles): pagado 1.234,56 y monto 1.234,50 → "El pagado
    ($ 1.234,56) es mayor que el monto ($ 1.234,50)." y no "El pagado ($ 1.235) es mayor que
    el monto ($ 1.235)."; pagado 1.234,51 y monto 1.234,50 → "El pagado ($ 1.234,51) es mayor
    que el monto ($ 1.234,50).". Si se ven distintos, van sin decimales como siempre (ej.
    66.021 y 66.020,12 → "El pagado ($ 66.021) es mayor que el monto ($ 66.020).");
  - `P` negativo → error en la fila: "El pagado no puede ser negativo."
  - El pagado se puede corregir o borrar en la revisión (RF-53). La fecha del pago es el día de
    la importación.
  - En las filas "me deben" y "sueldo" el pagado no se usa (en "me deben" se usa el cobrado,
    RN-64 y RN-72).
- **RN-70 – Sueldo.** Una fila de tipo "sueldo (USD)" carga su monto como **sueldo en USD del
  mes destino**, reemplazando el que tenía. La fila muestra el cambio con la nota "Sueldo del
  mes: US$ 1.200,00 -> US$ 1.300,00." (si el sueldo no cambia: "Sueldo del mes:
  US$ 1.300,00."). No necesita nombre (ej. el "1200" suelto de la planilla). El monto debe
  ser > 0. Solo una fila puede ser sueldo: si hay dos o más, no se puede confirmar; el error
  "Marcaste N filas como sueldo; dejá una sola." se ve en **todas** las filas de sueldo,
  arriba de la lista y en el pie. Si ninguna fila es sueldo, el sueldo del mes no cambia (si
  el mes se crea, ver RN-73). El sueldo en pesos no forma parte de la importación (§8).
- **RN-71 – Cuotas importadas.** Una fila de tipo cuota crea un **plan de cuotas** (RF-16)
  con: nombre de la fila, categoría de la fila, sin medio de pago, monto de cuota = monto de
  la fila (ARS), cantidad de cuotas = N y **primera cuota = mes destino − (n − 1) meses**.
  Ej.: cuota 3 de 3 importada en 2026-10 → primera 2026-08, última 2026-10 (RN-25); cuota 1
  de 12 en 2026-10 → primera 2026-10.
  - Las cuotas se generan según RN-30 (mes actual y meses futuros existentes) y **además en el
    mes destino**, aunque sea anterior al mes actual. Es una excepción a RN-30: el usuario
    está cargando justamente ese mes. Los meses existentes entre el mes destino y el mes actual
    no se modifican.
  - El pagado de la fila (RN-69) se aplica solo a la cuota del mes destino.
  - Si n = N, la del mes destino es la última cuota: el plan termina ahí (RN-26) y se libera
    desde el mes siguiente (RN-27).
  - El nombre propuesto es el texto completo de la celda (ej. "Avant Service cuota 3/ 3
    $41.116,66"); el usuario lo puede acortar en la revisión.
  - Las cuotas importadas son siempre en ARS (RN-29).
  - Con la cuota actual y la cantidad válidas, la fila muestra la nota "Plan de 3 cuotas:
    primera Agosto 2026, última Octubre 2026. Se agrega la cuota 3/3 en Octubre 2026." (se
    recalcula si cambian la cuota o el mes destino). Con N = 1 va en singular: "Plan de 1
    cuota: primera Octubre 2026, última Octubre 2026. Se agrega la cuota 1/1 en Octubre
    2026."
- **RN-72 – "Me deben" importado.** Una fila de tipo "me deben" crea un **ítem manual**
  (RF-32) de la persona elegida, con descripción = nombre de la fila, monto = monto (ARS),
  fecha = día de la importación y **cobrado** según el tilde de la fila: viene marcado si la
  columna de cobrado lo indica (RN-64) y, si no, desmarcado; el usuario lo puede cambiar. No
  depende del mes destino (la lista es acumulada, RN-35).
  - Persona: la propuesta por el título (RN-65) o la que elija el usuario entre las personas
    activas. También puede crear una **persona nueva** escribiendo su nombre (RN-50, mensajes
    en RN-75). Mientras dura la revisión, la persona nueva se puede elegir en las demás filas.
    Se guarda recién al confirmar y **solo si quedó en uso**: es decir, si es la persona de
    alguna fila "me deben" que se importa (tildada y con ese tipo al confirmar). Si el
    usuario la creó y después esa fila pasó a otro tipo, se destildó o cambió de persona, no
    se crea. Si se cancela, no se crea.
  - **Aviso de posible gasto compartido.** En la planilla, los bloques de personas tienen
    líneas que son su parte de un gasto compartido (ej. "Internet 12.900"). Si se importan
    como "me deben" y después el gasto se marca como compartido (RF-29), la deuda queda
    contada dos veces. Por eso, una fila "me deben" muestra el aviso "¿Es parte de un gasto
    compartido? Si es así, ignorala y marcá el gasto como compartido después." cuando su
    nombre **coincide** con el nombre de:
    - otra fila del mismo Excel que se va a importar como gasto fijo, pago único o cuota
      (tildada y con ese tipo en ese momento), o
    - un gasto del mes destino (los que ya tiene o, si se va a crear, los que va a tener al
      crearse, RN-09).
    "Coincide" quiere decir: los dos nombres son iguales según RN-67, o todas las palabras del
    nombre más corto aparecen como palabras enteras en el más largo. Ej.: "Internet" coincide
    con "Internet"; "Servicios Luz Gas" coincide con "Servicios"; "Pesos Check" no coincide
    con "Pesos checks" ("check" ≠ "checks"); "Prestamo MP" no coincide con nada de la
    planilla.
    El aviso no cambia el tipo propuesto ni el tilde y no impide confirmar: decide el
    usuario. Se recalcula cuando cambian nombres, tipos, tildes o el mes destino.
  - Las partes de gastos compartidos no se importan (RN-77).
- **RN-73 – Mes destino.**
  - Opciones: cualquier mes existente, o el mes que se puede crear según RN-08 (el siguiente
    al último mes). Con la base sin meses (primer uso), cualquier año y mes válidos (RN-07).
  - Por defecto: el mes actual, si existe o se puede crear; si no, el último mes. Ej.: último
    mes 2026-08 y mes actual 2026-10 → 2026-10 no se puede crear (RN-08) y se propone 2026-08.
  - Si el mes destino **existe**, lo importado se **agrega**: no se borra ni se modifica nada
    de lo que ya tiene, salvo el sueldo si hay una fila de sueldo (RN-70).
  - Si el mes destino **no existe**, se crea al confirmar, en el mismo paso que el resto
    (RN-76):
    - si es el siguiente al último mes: como RF-03 y RN-09 (copia los fijos y genera las
      cuotas de los planes activos), con el sueldo y la cotización del último mes, sin
      preguntar; la fila de sueldo, si hay, reemplaza el sueldo;
    - si es el primer mes (primer uso): con el sueldo de la fila de sueldo, o 0 si no hay (con
      el aviso de RN-05), y **sin cotización** (RN-18). La cotización no se importa: se carga
      en el resumen como siempre (RF-25).
  - Si el mes destino existe pero no es el último, la revisión avisa: "Los gastos fijos que
    importes no se agregan a los meses siguientes que ya existen." (RN-11; solo se copian a los
    meses nuevos desde el último mes, RN-09).
  - Cambiar el mes destino recalcula las marcas "ya existe" (RN-74) y los avisos de posible
    gasto compartido (RN-72).
- **RN-74 – "Ya existe" y "repetida en el archivo".**
  - Una fila de gasto fijo, pago único o cuota se marca **"ya existe"** si su nombre (RN-67)
    coincide con el de un gasto del mes destino, de cualquier tipo. Si el mes destino se va a
    crear, se compara con los gastos que va a tener al crearse (fijos copiados y cuotas
    generadas, RN-09). Una fila de cuota también se marca "ya existe" si hay un plan de cuotas
    con ese nombre (en cualquier estado).
  - Si una fila de cuota coincide **a la vez** con un gasto del mes destino y con un plan de
    cuotas, se muestra solo la nota de gasto ("Ya existe en Octubre 2026. …"), porque se mira
    primero el mes destino. Ej.: "Avant Service cuota 3/ 3 $41.116,66" en la segunda
    importación de la planilla en 2026-10 (CA-56.4).
  - Una fila "me deben" se marca "ya existe" si la persona tiene un ítem manual **no cobrado**
    con la misma descripción.
  - Las filas "ya existe" vienen **destildadas**. Si el usuario las tilda, se importan igual
    (quedan dos con el mismo nombre). La nota de la marca depende del tilde: destildada dice
    "Viene destildada." y tildada dice "Si la importás, queda repetida." (tabla de abajo); se
    actualiza cada vez que cambia el tilde.
  - Al cambiar el mes destino, las marcas se recalculan: las filas que pasan a "ya existe" se
    destildan y las que dejan de serlo se vuelven a tildar. Al cambiar el nombre, el tipo o la
    persona de una fila, se recalcula su marca pero no se toca su tilde (salvo el paso desde
    "ignorar", RN-68).
  - Cuando al cambiar el mes destino cambia algún tilde, la app lo avisa con un mensaje
    temporal que nombra solo lo que pasó. Ej.: "Cambiaste el mes: 1 fila pasó a "ya existe" y
    se destildó. 1 fila se volvió a tildar." Si ningún tilde cambió, no hay mensaje.
  - Las filas con el mismo nombre dentro del Excel se marcan **"repetida en el archivo"** si
    son del mismo grupo: gastos (fijo, pago único y cuota) entre sí, o "me deben" de la misma
    persona. Vienen tildadas y **no** impiden confirmar: puede ser un error del Excel o dos
    gastos distintos con el mismo nombre. Ej.: "Internet" de "Gasto del Mes" (gasto) e
    "Internet" de "Deudas sofia" (me deben) no son repetidas (pero la de Sofía tiene el aviso
    de posible gasto compartido, RN-72); "Pesos Check" de Sofía y de Marsu tampoco (personas
    distintas).
  - **Textos de las notas:**

    | Marca | Texto |
    |---|---|
    | Ya existe (gasto en el mes destino), destildada | "Ya existe en Octubre 2026. Viene destildada." |
    | Ya existe (gasto en el mes destino), tildada | "Ya existe en Octubre 2026. Si la importás, queda repetida." |
    | Ya existe (plan de cuotas), destildada | "Ya existe un plan de cuotas con este nombre. Viene destildada." |
    | Ya existe (plan de cuotas), tildada | "Ya existe un plan de cuotas con este nombre. Si la importás, queda repetida." |
    | Ya existe ("me deben"), destildada | "Sofía ya tiene un ítem sin cobrar con esta descripción. Viene destildada." |
    | Ya existe ("me deben"), tildada | "Sofía ya tiene un ítem sin cobrar con esta descripción. Si la importás, queda repetida." |
    | Repetida en el archivo | "Repetida en el archivo. Si no es un error del Excel, podés importarla igual." |

- **RN-75 – Categoría por defecto y categorías nuevas.**
  - Arriba de la lista se elige una categoría por defecto entre las categorías activas; se
    propone "Varios" si existe. El usuario también puede crear una categoría nueva escribiendo
    el nombre (RN-50).
  - Las filas de gasto y cuota usan la categoría por defecto, salvo las que el usuario cambió
    una por una (en la fila o con la acción de bloque, RN-78). Cambiar la categoría por
    defecto cambia las filas que no se tocaron; las cambiadas a mano conservan la suya.
    Elegir "Categoría por defecto" en una fila hace que vuelva a seguir la categoría por
    defecto.
  - Sin categoría por defecto elegida (ej. no existe "Varios"), las filas de gasto y cuota sin
    categoría propia tienen error (RN-68).
  - Una categoría nueva se puede elegir en todas las filas mientras dura la revisión. Se
    guarda recién al confirmar y **solo si quedó en uso**: es decir, si es la categoría de
    alguna fila de gasto fijo, pago único o cuota que se importa (elegida a mano o por ser la
    categoría por defecto). Si nadie la usa, o si se cancela, no se crea.
  - **Nombres nuevos (categorías y personas).** Se validan con RN-50, comparando según RN-67
    (sin mayúsculas ni acentos), contra las existentes (activas y archivadas) y contra las ya
    agregadas en esta importación:

    | Caso | Texto |
    |---|---|
    | Vacío | "Ingresá un nombre." |
    | Ya existe (activa) | "Ya existe una categoría llamada "Salud"." / "Ya existe una persona llamada "Sofía"." |
    | Ya existe archivada | "Ya existe una categoría llamada "Salud" (está archivada). Podés desarchivarla en Ajustes." (para personas, el mismo texto con "una persona") |
    | Ya agregada en esta importación | "Ya agregaste una persona llamada "Juan" en esta importación." (para categorías, el mismo texto con "una categoría") |

- **RN-76 – Confirmar y cancelar.**
  - **Resumen previo.** "Confirmar importación" (o `Ctrl/Cmd+Enter`) todavía no guarda nada:
    muestra "Revisá antes de importar" con, en este orden y solo las líneas que corresponden:
    - la primera línea según el mes destino: "Se va a cargar en Octubre 2026 (ya existe)." /
      "Se va a crear Noviembre 2026 y cargar ahí los datos." / (primer uso) "Se va a crear
      Octubre 2026, sin cotización, y cargar ahí los datos.";
    - "5 gastos: $ 376.720 (pagado $ 98.700)" (suma de los gastos que se importan, sin las
      cuotas; "(pagado …)" solo si hay pagos);
    - "1 plan de cuotas: Avant Service cuota 3/ 3 $41.116,66 (cuota 3/3, $ 41.117 por mes)";
    - "3 ítems "me deben": Sofía 2, Marsu 1 ($ 39.685 en total)";
    - "Sueldo: US$ 1.200,00 -> US$ 1.300,00", solo si hay una fila de sueldo. Si el mes se
      crea en el primer uso y no hay fila de sueldo: "Sin sueldo: el sueldo de Octubre 2026
      queda en US$ 0,00.";
    - "Se crean también: la categoría "Importado" y la persona "Juan"." solo con las nuevas
      que quedaron en uso (RN-72, RN-75);
    - "No se importan 19 filas (ignoradas o destildadas)." (todas las filas detectadas,
      incluidas las incompletas, que no se importan);
    - "Esta importación no se puede deshacer. Si algo sale mal, lo corregís a mano en la app."
    Singular y plural según corresponda ("1 gasto", "5 gastos"). Botones "Volver a la
    revisión" (vuelve a la lista sin cambiar nada) e "Importar" (guarda).
  - **Todo o nada:** al tocar "Importar" se guardan en un solo paso el mes destino (si hay que
    crearlo), las categorías y personas nuevas que quedaron en uso, los gastos con sus pagos,
    los planes con sus cuotas, los ítems "me deben" y el sueldo. Si algo falla, no queda nada
    guardado (ni siquiera el mes nuevo) y la app avisa con el título "No se pudo importar" y
    el texto "No se pudo importar. No se guardó ningún dato." Con "Volver a la revisión", la
    revisión sigue **tal cual estaba**, para reintentar o cancelar.
  - **Una sola vez:** una revisión ya guardada no se puede volver a guardar (ej. un doble
    clic en "Importar"): "Esta importación ya se guardó." y no cambia nada. Para importar de
    nuevo se empieza otra importación. Mientras se guarda, el botón "Importar" está
    deshabilitado.
  - **Resultado:** al terminar, la app muestra "Importación terminada" con:
    - "Se importaron: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo
      (US$ 1.300,00) en Octubre 2026." (mencionando solo lo que hubo);
    - bajo "Para completar:", solo las líneas que corresponden: "Los gastos quedaron sin medio
      de pago. Podés ponérselo en Gastos." (si se importaron gastos o cuotas); "Si alguno es
      compartido, marcalo desde el gasto." (si se importaron gastos o ítems "me deben");
      "Cargá la cotización de Octubre 2026 en el Resumen." (solo si el mes se creó sin
      cotización);
    - el botón "Ver Octubre 2026". No hay opción de deshacer.
    Al tocar "Ver Octubre 2026", la app queda con el mes destino como mes seleccionado, todo
    recalculado (RN-19), en la pantalla **Gastos**; si solo se importaron ítems "me deben"
    y/o el sueldo, en la pantalla **Resumen**. Si la importación empezó en el primer uso, la
    app pasa a la ventana normal (con rail y barra superior), como al crear el primer mes.
  - **Cancelar:** en cualquier momento antes de "Importar" se puede cancelar, y entonces no se
    guarda nada: ni gastos, ni pagos, ni planes, ni ítems, ni mes nuevo, ni personas o
    categorías nuevas.
    - Con el botón "Cancelar" o con `Esc`: si el usuario **no** cambió nada en la revisión,
      sale directo. Si cambió algo, la app pregunta "¿Descartar la importación?" con el texto
      "Se pierden los cambios que hiciste en la revisión. No se guarda nada." (y, si agregó
      categorías o personas nuevas, "También se descartan las categorías y personas nuevas:
      Importado, Juan.") y los botones "Seguir revisando" y "Descartar".
    - Con "Cambiar archivo u hoja": si cambió algo, la app pregunta "¿Volver a elegir el
      archivo?" con el texto "Se pierden los cambios que hiciste en la revisión." y los
      botones "Seguir revisando" y "Volver a elegir"; si no, vuelve directo a elegir archivo.
    - **Cerrar la ventana de la app** durante la importación cierra la app **sin preguntar**
      (decisión del usuario, 2026-10-13). Se pierde solo la revisión en curso; no se guarda
      nada de ella y no se pierde nada de lo que ya estaba guardado.
    - **Qué cuenta como cambio del usuario:** cambiar un tipo, un tilde (también "cobrado"),
      un dato de una fila, la categoría por defecto o el mes destino, usar una acción de
      bloque, o agregar una categoría o persona nueva. Lo que la app hace sola (tipos
      propuestos, marcas "ya existe", tildes recalculados) no cuenta.
    - Al cancelar se vuelve al lugar desde donde se empezó: al formulario de primer uso o a la
      pestaña "Importar Excel" de Ajustes, sin mensaje extra.
  - **Sin deshacer:** una importación confirmada no se puede deshacer como un todo (decisión
    del usuario, §8). Si salió mal, se corrige a mano en la app (editar o borrar gastos,
    planes e ítems) o, si el mes destino es el último, se puede borrar el mes (RN-10).
  - La importación se puede repetir; las marcas de RN-74 ayudan a no duplicar.
- **RN-77 – Qué no se importa.** Cotización (del mes y de los gastos), medio de pago, gastos
  compartidos y sus partes, gastos en dólares (todos los gastos se importan en ARS; para
  expresarlos en USD se editan después, RN-56), sueldo en pesos (§8), ingresos extra, cambios
  realizados, meta de ahorro y cuotas omitidas. Tampoco fórmulas ni formatos (colores, celdas
  combinadas): solo valores.
- **RN-78 – Acciones de bloque.** Cada bloque de la lista principal (RN-65, incluidos "Otras
  filas" y "Filas detectadas"; no el grupo "Filas incompletas") tiene tres acciones que
  cambian todas sus filas de una vez. Sirven, por ejemplo, para un título "Sofía y Marsu" o un
  bloque sin persona que deja varias filas "me deben" sin persona. No cambian ninguna otra
  regla: después de aplicarlas, cada fila se puede ajustar por separado. Se aplican solo a
  las filas del bloque que están en la lista principal (no a sus filas incompletas, que se
  muestran en su propio grupo).
  - **"Tildar todas las filas":** tilda todas las filas del bloque que no son "ignorar",
    incluidas las "ya existe". Las "ignorar" no cambian (RN-68).
  - **"Destildar todas las filas":** destilda todas las filas del bloque.
  - **"Cambiar tipo o categoría de todas...":** el usuario elige:
    - **Tipo:** "No cambiar el tipo" (viene elegido) o uno de gasto fijo, gasto único, me
      deben o ignorar. "Cuota" no se ofrece (cada cuota necesita su cuota actual y cantidad:
      "La cuota se elige fila por fila.") ni "Sueldo (USD)" ("Solo una fila puede ser el
      sueldo.").
    - Con tipo gasto fijo o gasto único: una **categoría** (opcional; si no se elige, cada
      fila conserva la suya). Con tipo "me deben": una **persona**, obligatoria ("Elegí una
      persona."). Con tipo "ignorar": nada más.
    - Con "No cambiar el tipo": una categoría y una persona, las dos opcionales. La categoría
      se aplica a las filas de gasto fijo, pago único y cuota del bloque; la persona, a las
      filas "me deben". Un campo que se deja sin elegir no cambia nada.
    - En la categoría y la persona se puede crear una nueva (RN-72, RN-75). Elegir una
      categoría así cuenta como cambiarla a mano (RN-75); elegir "Categoría por defecto" hace
      que las filas vuelvan a seguir la categoría por defecto.
    - Se aplica a **todas** las filas del bloque, incluidas las que están en "ignorar": las que
      pasan de "ignorar" a otro tipo se tildan solas (RN-68); las demás conservan su tilde.
      Texto del diálogo: "Se cambian las 5 filas de este bloque. Después podés ajustar cada
      una." y, si el bloque tiene filas en "ignorar", "Se cambian las 5 filas de este bloque,
      incluidas las que están ignoradas." Botones "Cancelar" y "Aplicar a las 5 filas".
    - Después de aplicar se recalculan las marcas "ya existe" y "repetida" (RN-74) y los
      avisos de posible gasto compartido (RN-72).

---

## 5. Modelo de datos propuesto (SQLite)

Convenciones:

- Montos: `INTEGER` en centavos (RN-01), con sufijo `_cent` en el nombre.
- Cotización: `INTEGER` en centavos de ARS por USD (RN-02).
- Meses: año y mes como dos `INTEGER` (permite ordenar y calcular cuotas con RN-24 sin
  procesar texto).
- Fechas: `TEXT` en formato ISO `AAAA-MM-DD` (SQLite no tiene tipo fecha; ISO se ordena
  bien como texto).
- Booleanos: `INTEGER` 0/1 (SQLite no tiene booleano).
- Claves foráneas activadas (`PRAGMA foreign_keys = ON`).
- El mes actual no se guarda: se toma del reloj del sistema cada vez que se necesita.
- Versión de la estructura: `PRAGMA user_version` (0 = sin gastos en dólares; 1 = con gastos
  en dólares) (RN-59).

### 5.1 `meses`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| anio | INTEGER NOT NULL | 4 dígitos |
| mes | INTEGER NOT NULL | CHECK 1..12 |
| sueldo_usd_cent | INTEGER NOT NULL | CHECK ≥ 0. Por mes, para que el historial no cambie si sube el sueldo. |
| cotizacion_cent | INTEGER NULL | CHECK > 0. NULL = no cargada (RN-18). |
| | | UNIQUE(anio, mes) (RN-07) |

### 5.2 `categorias`, `medios_pago`, `personas`
Las tres tienen la misma forma:

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT NOT NULL UNIQUE COLLATE NOCASE | RN-50 |
| archivado | INTEGER NOT NULL DEFAULT 0 | 0/1 (RN-49). Desarchivar = volver a 0. |

Los medios de pago son una tabla (y no texto libre) para poder agrupar sin errores de tipeo
(RF-22).

### 5.3 `planes_cuotas`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| nombre | TEXT NOT NULL | Ej. "Avant Service" |
| categoria_id | INTEGER NOT NULL FK → categorias | |
| medio_pago_id | INTEGER NULL FK → medios_pago | |
| monto_cuota_cent | INTEGER NOT NULL | CHECK > 0. Siempre ARS (sin columna de moneda). |
| cantidad_cuotas | INTEGER NOT NULL | CHECK ≥ 1 |
| primer_anio | INTEGER NOT NULL | |
| primer_mes | INTEGER NOT NULL | CHECK 1..12 |
| cancelado_anio | INTEGER NULL | Primer mes sin cuota por cancelación (RN-31). NULL = no cancelado. |
| cancelado_mes | INTEGER NULL | CHECK 1..12 |

El plan es la deuda y vive fuera de los meses; cada mes tiene su gasto concreto. La cuota
actual, la última cuota y el restante se **calculan** (RN-24 a RN-28), así no pueden quedar
desincronizados.

### 5.4 `cuotas_omitidas`
| Campo | Tipo | Notas |
|---|---|---|
| plan_cuotas_id | INTEGER NOT NULL FK → planes_cuotas ON DELETE CASCADE | |
| anio | INTEGER NOT NULL | |
| mes | INTEGER NOT NULL | CHECK 1..12 |
| | | PRIMARY KEY(plan_cuotas_id, anio, mes) |

Hace falta una tabla aparte porque, una vez borrado el gasto, no queda rastro en `gastos`
de que esa cuota no debe volver a generarse (RN-52). Usa año y mes (no `mes_id`) para que la
omisión sobreviva si el mes se borra y se vuelve a crear.

### 5.5 `gastos`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| mes_id | INTEGER NOT NULL FK → meses ON DELETE CASCADE | |
| nombre | TEXT NOT NULL | |
| categoria_id | INTEGER NOT NULL FK → categorias | |
| monto_cent | INTEGER NOT NULL | CHECK > 0. **Monto en ARS para todos los gastos**, también los en dólares (resultado de RN-53). |
| moneda | TEXT NOT NULL DEFAULT 'ARS' | CHECK IN ('ARS', 'USD'). Moneda en la que está expresado el gasto. |
| monto_usd_cent | INTEGER NULL | CHECK > 0. Obligatorio si moneda = 'USD'; NULL si moneda = 'ARS'. |
| cotizacion_cent | INTEGER NULL | CHECK > 0. Cotización del gasto. Obligatoria si moneda = 'USD'; NULL si moneda = 'ARS'. |
| tipo | TEXT NOT NULL | CHECK IN ('fijo', 'cuota', 'unico') |
| medio_pago_id | INTEGER NULL FK → medios_pago | |
| plan_cuotas_id | INTEGER NULL FK → planes_cuotas | Obligatorio si tipo = 'cuota'; NULL en otro caso. |
| | | UNIQUE(mes_id, plan_cuotas_id): un plan genera como máximo un gasto por mes. |
| | | CHECK: si moneda = 'USD', entonces tipo ≠ 'cuota' (RN-54). |

Cada mes tiene **copias** de sus gastos (no referencias a una lista maestra), para que editar
un mes no altere los demás (RN-11).

Decisiones sobre los gastos en dólares:

- `monto_cent` sigue siendo el monto en ARS de **todos** los gastos. Así los totales, los
  pagos, el pendiente, el total por medio de pago, las partes compartidas y la capacidad se
  siguen calculando igual, sin preguntar la moneda.
- El monto en ARS se **guarda** (no se calcula cada vez) porque tiene que quedar fijo aunque
  cambie la cotización del mes (RN-55). Se guardan también el monto en USD y la cotización del
  gasto para poder mostrar "US$ 20,00 × $ 1.600", recalcular al editar, copiar al mes nuevo
  (RN-57) y estimar la previsión con la cotización actual (RN-42).
- **Migración (versión 0 → 1, RN-59):** la base del usuario ya tiene datos reales, así que
  estas tres columnas se agregan con una migración:
  1. Se lee `PRAGMA user_version`; si ya es 1 (o más), no se hace nada.
  2. Se hace la copia de respaldo con la **API de backup de SQLite** en
     `datos-privados/respaldos/gastos-AAAAMMDD-HHMMSS.db` (la API copia la base de forma
     consistente aunque esté abierta, a diferencia de copiar el archivo a mano).
  3. Dentro de **una transacción**: `ALTER TABLE gastos ADD COLUMN ...` para las tres
     columnas y `PRAGMA user_version = 1`. Si algo falla, se deshace todo y la base queda en
     versión 0.
  Por el `DEFAULT 'ARS'`, los gastos existentes quedan como ARS con `monto_usd_cent` y
  `cotizacion_cent` en NULL.

### 5.6 `pagos`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| gasto_id | INTEGER NOT NULL FK → gastos ON DELETE CASCADE | |
| monto_cent | INTEGER NOT NULL | CHECK > 0. Siempre ARS. |
| fecha | TEXT NOT NULL | ISO |

Una tabla de pagos (en vez de un campo "pagado") permite varios pagos parciales y borrarlos
uno por uno (RF-14, RF-15). Pagado y pendiente se calculan (RN-20).

### 5.7 `ingresos_extra`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| mes_id | INTEGER NOT NULL FK → meses ON DELETE CASCADE | |
| descripcion | TEXT NOT NULL | |
| moneda | TEXT NOT NULL | CHECK IN ('ARS', 'USD') |
| monto_cent | INTEGER NOT NULL | CHECK > 0, en la moneda indicada |

### 5.8 `cambios`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| mes_id | INTEGER NOT NULL FK → meses ON DELETE CASCADE | |
| fecha | TEXT NOT NULL | ISO |
| usd_cent | INTEGER NOT NULL | CHECK > 0 |
| cotizacion_cent | INTEGER NOT NULL | CHECK > 0 |
| ars_cent | INTEGER NOT NULL | CHECK > 0. Se guarda porque el usuario puede corregirlo a mano (RN-13). |

### 5.9 `partes_gasto`
Una fila por persona que participa de un gasto compartido. La parte del usuario **no** se
guarda: es `monto − Σ partes` (así la suma siempre cierra).

| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| gasto_id | INTEGER NOT NULL FK → gastos ON DELETE CASCADE | |
| persona_id | INTEGER NOT NULL FK → personas | |
| monto_cent | INTEGER NOT NULL | CHECK ≥ 0 |
| editada_a_mano | INTEGER NOT NULL DEFAULT 0 | 0/1. Automática (RN-32) o manual (RN-33/RN-34). Vuelve a 0 en el caso de RN-37. |
| cobrado | INTEGER NOT NULL DEFAULT 0 | 0/1. Estado del tilde. |
| cobrado_cent | INTEGER NOT NULL DEFAULT 0 | CHECK ≥ 0. Monto ya cobrado. Al marcar el tilde = `monto_cent`; al desmarcarlo a mano = 0. Si cambia la parte (RN-34) se conserva para mostrar la diferencia. |
| | | UNIQUE(gasto_id, persona_id) |

Se guarda lo cobrado (y no solo un tilde) porque, si la parte cambia después de cobrarla,
hay que mostrar la diferencia contra lo que ya se cobró (RN-34). Un gasto es compartido si
tiene al menos una fila en esta tabla.

### 5.10 `items_me_deben`
| Campo | Tipo | Notas |
|---|---|---|
| id | INTEGER PK | |
| persona_id | INTEGER NOT NULL FK → personas | |
| descripcion | TEXT NOT NULL | |
| monto_cent | INTEGER NOT NULL | CHECK > 0 |
| fecha | TEXT NOT NULL | ISO |
| cobrado | INTEGER NOT NULL DEFAULT 0 | 0/1 |

Sin `mes_id`: la lista es acumulada por persona (RN-35).

### 5.11 `configuracion`
| Campo | Tipo | Notas |
|---|---|---|
| clave | TEXT PK | |
| valor | TEXT NOT NULL | Uso inicial: `meta_ahorro_usd_cent` (meta única, RF-36). Sin fila = sin meta. |

### 5.12 Valores que se calculan y NO se guardan
Mes actual, total de gastos, pagado, pendiente, pesos a cubrir, USD a cambiar, pesos
sobrantes, ahorro, cuota actual, última cuota, restante, parte del usuario, diferencias de
cobro, total que le deben, capacidad de endeudamiento y previsiones. Guardarlos duplicaría
información que podría quedar vieja al cambiar la cotización o un gasto. (Excepción
deliberada: el monto en ARS de un gasto en dólares **sí** se guarda, porque tiene que quedar
fijo, RN-55.)

### 5.13 Importar Excel: sin cambios en el modelo
La importación (Módulo K) **no agrega tablas ni columnas** y no cambia la versión de la base
(sigue en 1, RN-59; no hace falta migración ni respaldo):

- El archivo no se guarda (RN-60), así que no hay tabla de archivos ni de importaciones.
- Lo confirmado se guarda en las tablas que ya existen: `meses` (mes nuevo y sueldo),
  `categorias` y `personas` (solo las creadas en la revisión que quedaron en uso, RN-72 y
  RN-75), `gastos`, `pagos`, `planes_cuotas` (con `primer_anio`/`primer_mes` calculados
  según RN-71) e `items_me_deben` (con `cobrado` según RN-72).
- La lista de revisión (filas detectadas con su número de fila y su título de bloque, tipos,
  tildes, correcciones, categorías y personas nuevas, notas y avisos) existe solo en memoria
  mientras dura la revisión; por eso cancelar o cerrar la ventana no deja rastro (RN-76).
- Los datos importados no quedan marcados como "importados": una vez confirmados son iguales
  a los cargados a mano. Como no hay "deshacer la importación" (RN-76, §8), no hace falta esa
  marca.

---

## 6. Correspondencia con la planilla

| Planilla | En la app |
|---|---|
| "Gasto del Mes" (Gastos / Pagado / Falta por pagar) | Lista de gastos del mes (RF-09) con pagos (RF-13, RF-14) |
| Línea "Tarjetas de Credito 582.917" | Total por medio de pago (RF-22). **No** se carga como gasto: los gastos que la componen se cargan uno por uno. |
| Tabla "Deudas" | Gastos y planes de cuotas con medio de pago (RF-16, RF-22) |
| "Avant Service cuota 3/3" | Plan de cuotas con cuota actual calculada (RF-17) |
| "Gastos en dolares 897" / "Sueldo − Gastos en dolares 303" | USD a cambiar y ahorro (RN-15, RN-17). Ojo: en la planilla "Gastos en dolares" es el **total de gastos convertido a USD**, no tiene relación con los gastos en dólares de RF-43. |
| (no existe en la planilla) Gastos expresados en USD, ej. una suscripción de US$ 20 | Gastos en dólares (RF-43 a RF-48): se cargan en USD con su cotización y cuentan por su monto en ARS. |
| "Gastos fijos sin deuda / Sueldo / Capacidad de Endeudamiento" | Capacidad de endeudamiento con la nueva fórmula (RN-38) |
| Edenor, Metrogas, "Total de servicios C/U" | Gastos compartidos (RF-29) |
| "Deudas sofia", "Marsu" | Lista "me deben" por persona (RF-33) |
| Columna "Objetivo" (134.000, 31.000) | Descartada: no tiene equivalente en la app |
| La hoja entera (y la de cualquier familiar, con otro formato) | Importación con revisión (Módulo K, RF-49 a RF-58). Los totales y valores calculados se proponen como "ignorar" (RN-66); los bloques de personas, como "me deben" (RN-65), con aviso si la línea parece la parte de un gasto compartido (RN-72). |

---

## 7. Criterios de aceptación

Cada CA-xx.y corresponde al RF-xx. Datos base (salvo que se indique otra cosa): **mes actual
(calendario) 2026-10**, que también es el mes seleccionado y el último mes; sueldo 1.200 USD,
cotización 1.600, sin ingresos extra, cambios ni meta. Para probar la lógica, el mes actual
debe poder fijarse en las pruebas (no depender del día en que se corren). Los valores entre
paréntesis en centavos son los internos; lo demás es lo que se ve en pantalla (RN-04).

### Módulo A – Meses e historial
- **CA-01.1** Cargar un gasto en 2026-10 y crear 2026-11: al volver a 2026-10 el gasto sigue
  con el mismo monto.
- **CA-02.1** Con 2026-09 y 2026-10 creados, se puede elegir 2026-09 y ver sus gastos,
  cotización y ahorro propios.
- **CA-02.2** Editar el monto de un gasto de 2026-09 (mes pasado) está permitido y no cambia
  el gasto con el mismo nombre en 2026-10.
- **CA-03.1** En 2026-10 hay: Alquiler (fijo, 260.000, pagado), Regalo (pago único, 15.000) y
  un plan de 3 cuotas desde 2026-09. Al crear 2026-11: aparece Alquiler 260.000 con pendiente
  260.000; no aparece Regalo; aparece la cuota "3/3".
- **CA-03.2** Al crear 2026-11, se sugieren cotización 1.600 y sueldo 1.200; se pueden
  cambiar antes de confirmar.
- **CA-03.3** Los ingresos extra y cambios de 2026-10 no aparecen en 2026-11.
- **CA-03.4** Un plan con última cuota 2026-10 no genera gasto en 2026-11. Un plan cancelado
  tampoco.
- **CA-03.5** Con último mes 2026-10, solo se puede crear 2026-11: intentar crear 2026-12 o
  2026-09 se rechaza.
- **CA-03.6** En 2026-10 hay un fijo "Gym" con categoría "Gym" archivada y una cuota de un plan
  con medio "Visa Santander" archivado. Al crear 2026-11 se copian ambos con esa categoría y
  ese medio.
- **CA-04.1** Con la base vacía, la app pide crear el primer mes con año, mes, sueldo y
  cotización.
- **CA-04.2** Año de 2 dígitos, mes 0 o 13: se rechaza.
- **CA-05.1** Con 2026-09 y 2026-10: borrar 2026-09 no está permitido; borrar 2026-10 pide
  confirmación y, al confirmar, desaparecen sus gastos, pagos, extras y cambios.
- **CA-05.2** Si un gasto compartido de 2026-10 tenía la parte de Sofía 12.900 sin cobrar,
  después de borrar 2026-10 esa línea ya no está en "me deben" de Sofía. Los ítems manuales de
  Sofía siguen.
- **CA-05.3** Después de borrar 2026-10, se puede volver a crear 2026-10 y copia los fijos de
  2026-09.

### Módulo B – Gastos
- **CA-06.1** Alta de "Nafta", categoría Transporte, 30.000, pago único: aparece en la lista y
  el total de gastos sube 30.000.
- **CA-06.2** Alta con monto −5.000, 0, vacío o "abc": se rechaza con mensaje y no se crea nada.
- **CA-06.3** Alta sin nombre o sin categoría: se rechaza.
- **CA-06.4** Monto "66.020,12" se guarda exacto (`6602012`) y en pantalla se ve "66.020".
- **CA-06.5** Una categoría archivada no aparece en la lista de categorías al dar de alta.
- **CA-07.1** Editar Nafta de 30.000 a 35.000: el total sube 5.000 y no cambia en otros meses.
- **CA-07.2** Gasto de 180.000 con 60.000 pagados: editar el monto a 50.000 se rechaza con
  mensaje; a 100.000 se acepta y el pendiente queda 40.000.
- **CA-08.1** Borrar un gasto pide confirmación; al confirmar desaparece con sus pagos y los
  totales se recalculan; al cancelar no cambia nada.
- **CA-08.2** Plan de 6 cuotas de 10.000 desde 2026-08, con 2026-10 y 2026-11 creados. Borrar
  a mano la cuota de 2026-11: desaparece solo esa; 2026-10 conserva "3/6"; el plan sigue
  activo; al crear 2026-12 aparece "5/6".
- **CA-08.3** En el caso CA-08.2, borrar 2026-12 y 2026-11 y volver a crearlos: 2026-11 sigue
  sin cuota y 2026-12 vuelve a tener "5/6".
- **CA-09.1** Con los 8 gastos de la planilla sin "Tarjetas de Crédito" (Alquiler 260.000,
  Servicios 82.000, Seguro de moto 131.000, Mercado 150.000, Nafta 30.000, Teléfono 20.000,
  Internet 38.700, Psicólogo 140.000) el total es 851.700 y el pendiente 851.700; tras
  marcar pagado el Alquiler: pagado 260.000, pendiente 591.700.
- **CA-09.2** Gastos de 0,40 + 0,40 + 0,40 ARS: el total se ve "1" (1,20 redondeado), no "0".
- **CA-10.1** Crear "Educación"; renombrar la categoría inicial "Salud" a "Salud y bienestar":
  los gastos que la usaban muestran el nombre nuevo.
- **CA-10.2** Nombre vacío o repetido ("salud" si existe "Salud", aunque esté archivada): se
  rechaza.
- **CA-10.3** Eliminar una categoría sin uso: se borra. Eliminar "Gym" con un gasto en
  2026-09: queda archivada; 2026-09 sigue mostrando "Gym"; no se ofrece para cargas nuevas.
- **CA-10.4** Desarchivar "Gym": vuelve a ofrecerse al dar de alta un gasto.
- **CA-11.1** Crear "Visa Santander" y "Mastercard Nación": son medios distintos y se totalizan
  por separado (CA-22.1).
- **CA-11.2** Mismas reglas de nombre, archivado y desarchivado que CA-10.2 a CA-10.4.
- **CA-12.1** "Deuda Jeho" se puede cargar como pago único de 159.000 o como plan de cuotas.

### Módulo C – Pagos
- **CA-13.1** Marcar el tilde en Alquiler 260.000: pagado 260.000, pendiente 0, el total
  pendiente del mes baja 260.000. Total de gastos, USD a cambiar y ahorro **no** cambian.
- **CA-13.2** Gasto de 180.000 con dos pagos parciales (60.000 y 50.000): al destildar
  "pagado" se borran los dos pagos y el pendiente vuelve a 180.000.
- **CA-14.1** Gasto de 180.000, pago parcial 60.000: pagado 60.000, pendiente 120.000. Segundo
  pago de 120.000: pendiente 0 y el tilde aparece marcado.
- **CA-14.2** Con pendiente 120.000, pago de 130.000: se rechaza. Pago de 0 o negativo: se
  rechaza.
- **CA-15.1** Con pagos de 60.000 y 50.000 sobre 180.000, eliminar el de 60.000: pagado
  50.000, pendiente 130.000.

### Módulo D – Cuotas
- **CA-16.1** Alta "Avant Service", 41.116,66, 3 cuotas, primera 2026-08: en 2026-10 aparece un
  gasto de "41.117" (`4111666`) con cuota "3/3".
- **CA-16.2** Cantidad de cuotas 0, negativa o con decimales, o monto ≤ 0: se rechaza.
  Cantidad 601: se rechaza con "La cantidad de cuotas es demasiado grande."; con 600 se crea
  el plan.
- **CA-17.1** El plan de CA-16.1 muestra última cuota 2026-10 y restante 0.
- **CA-17.2** Plan de 12 cuotas de 10.000 desde 2026-03: en 2026-10 muestra "8/12", última
  cuota 2027-02, restante 40.000. Seleccionando 2026-09 muestra "7/12" y restante 50.000.
- **CA-17.3** Plan de 12 cuotas desde 2025-11: última cuota 2026-10 (cruce de año).
- **CA-17.4** Plan de 12 cuotas con primera cuota 2026-12 visto desde 2026-10: no genera gasto
  en 2026-10, figura como "no empezó" y restante = 12 × cuota.
- **CA-18.1** Con 2026-09 y 2026-10 existentes y **2026-09 seleccionado**, alta de un plan de
  6 cuotas desde 2026-08: se genera la cuota "3/6" en 2026-10 (mes actual) y **no** se agrega
  nada en 2026-09.
- **CA-18.2** Si además existe 2026-11, el alta genera también la cuota "4/6" en 2026-11.
- **CA-18.3** Con último mes 2026-09 (2026-10 todavía no creado), el alta del mismo plan no
  genera gastos; al crear 2026-10 aparece la cuota "3/6".
- **CA-19.1** Plan de CA-18.2 (10.000) sin pagos en 2026-10: cambiar la cuota a 12.000 deja
  2026-10 y 2026-11 en 12.000; un gasto de ese plan en 2026-09 (si existía) sigue en 10.000.
- **CA-19.2** Igual que CA-19.1 pero la cuota de 2026-10 tiene un pago de 5.000: 2026-10
  sigue en 10.000 con su pago y pendiente 5.000; 2026-11 pasa a 12.000.
- **CA-19.3** Si la cuota de 2026-11 fue borrada a mano (cuota omitida), editar el plan no la
  vuelve a crear.
- **CA-20.1** Cancelar el plan de CA-18.2 sin pagos en 2026-10: desaparecen sus cuotas de
  2026-10 y 2026-11; al crear 2026-12 no se genera; las cuotas de meses anteriores a 2026-10
  siguen; la última cuota pasa a ser 2026-09.
- **CA-20.2** Cancelar el plan de CA-18.2 con un pago de 5.000 en la cuota de 2026-10: la
  cuota de 2026-10 se conserva (10.000, pendiente 5.000); desaparece la de 2026-11; la última
  cuota pasa a ser 2026-10; al crear 2026-12 no se genera.
- **CA-20.3** El plan cancelado muestra restante 0 y aparece en el filtro "cancelados".
- **CA-21.1** El filtro "terminados" muestra solo planes con última cuota anterior al mes
  actual; "cancelados" solo los cancelados; "activos" el resto. El resultado es el mismo con
  cualquier mes seleccionado.
- **CA-22.1** En 2026-10: Gym 50.000 (Visa Santander), Avant 41.116,66 (Visa Santander),
  Seguro 131.000 (Mastercard Nación), Alquiler 260.000 (Transferencia), Nafta 30.000 (sin
  medio): Visa Santander 91.117; Mastercard Nación 131.000; Transferencia 260.000; Sin medio
  de pago 30.000.

### Módulo E – Ingresos, cotización y cambios
Base: gastos del mes 1.434.617.
- **CA-23.1** Sueldo 1.200: USD a cambiar 896,64; ahorro 303,36. Cambiar el sueldo a 1.300:
  ahorro 403,36.
- **CA-23.2** Sueldo 0: se acepta, se ve el aviso "El sueldo de este mes es 0" y el ahorro
  es −896,64 (déficit). Sueldo negativo: se rechaza.
- **CA-24.1** Extra ARS 100.000: pesos a cubrir 1.334.617; USD a cambiar 834,14; ahorro 365,86.
- **CA-24.2** Extra USD 50: USD a cambiar 896,64; ahorro 353,36.
- **CA-24.3** Extra con monto ≤ 0 o moneda distinta de ARS/USD: se rechaza.
- **CA-25.1** Cambiar la cotización a 1.700: USD a cambiar 843,89; ahorro 356,11, sin
  reiniciar la app.
- **CA-25.2** Cotización 0 o negativa: se rechaza.
- **CA-25.3** Mes sin cotización y con gastos: USD a cambiar, ahorro y capacidad muestran
  "Cargá la cotización" (no un error ni 0).
- **CA-25.4** Cotización del mes 1.432,50: el resumen y el diálogo de edición la muestran como
  "$ 1.432,50" (no "$ 1.433"); cotización 1.600 se muestra "$ 1.600" (sin ",00").
- **CA-26.1** Cambio de 500 USD a 1.500: el campo ARS se completa con 750.000.
- **CA-26.2** Corregir esos ARS a 745.000 y guardar: el cambio muestra 745.000.
- **CA-26.3** Cambio con USD, cotización o ARS ≤ 0: se rechaza.
- **CA-26.4** Un cambio a cotización 1.432,50 muestra su cotización como "$ 1.432,50".
- **CA-27.1** Con el cambio de CA-26.1 (750.000) y cotización 1.600: pesos a cubrir 684.617;
  USD a cambiar 427,89; ahorro 272,11. Cambiar la cotización del mes a 1.700 no modifica los
  750.000 del cambio.
- **CA-27.2** Con el cambio corregido de CA-26.2 (745.000) y cotización 1.600: pesos a cubrir
  689.617; USD a cambiar 431,01; ahorro 268,99.
- **CA-27.3** Gastos 100.000, cambio de 100 USD a 1.600 (160.000), cotización 1.600: pesos a
  cubrir 0; USD a cambiar 0; pesos sobrantes 60.000 = 37,50 USD; ahorro 1.137,50.
- **CA-27.4** Gastos 100.000, extra ARS 150.000, sin cambios, cotización 1.600: pesos
  sobrantes 50.000 = 31,25 USD; ahorro 1.231,25.
- **CA-27.5** El caso CA-27.3 sin cotización del mes: ahorro "Cargá la cotización". Gastos
  160.000 con el mismo cambio y sin cotización (F = 0): ahorro 1.100,00.
- **CA-27.6** Al crear 2026-11 después de CA-27.3, los 60.000 sobrantes no aparecen en 2026-11.

### Módulo F – Compartidos y "me deben"
- **CA-28.1** Crear, renombrar y eliminar una persona sin uso. Una persona con partes o ítems
  (cobrados o no) queda archivada: no se ofrece al marcar compartidos nuevos, pero sigue en
  "me deben".
- **CA-28.2** Desarchivar esa persona: vuelve a ofrecerse al marcar un gasto como compartido.
- **CA-29.1** Internet 38.700 compartido con Sofía y Marsu: 12.900 cada uno, incluido el
  usuario.
- **CA-29.2** Edenor 66.281 con Sofía y Marsu: Sofía `2209366`, Marsu `2209366`, usuario
  `2209368` (en pantalla 22.094 cada uno). La suma interna da `6628100`.
- **CA-29.3** Internet compartido solo con Sofía: 19.350 c/u.
- **CA-29.4** El total de gastos del mes incluye los 38.700 completos de Internet.
- **CA-30.1** En Internet 38.700, editar la parte de Sofía a 15.000 (Marsu 12.900): la parte del
  usuario pasa a 10.800.
- **CA-30.2** Editar Sofía a 30.000 con Marsu 12.900 (usuario −4.200): se rechaza con mensaje.
- **CA-31.1** Internet sin partes manuales, monto de 38.700 a 45.000: 15.000 c/u.
- **CA-31.2** Internet con Sofía manual 15.000 y Marsu automática: monto a 45.000 → Marsu
  15.000, Sofía 15.000, usuario 15.000; monto a 30.000 → Marsu 10.000, Sofía 15.000,
  usuario 5.000.
- **CA-31.3** En el caso CA-31.2, monto a 20.000 (Marsu 6.666,66, Sofía 15.000, usuario
  −1.666,66): se rechaza y el monto sigue como estaba.
- **CA-31.4** Internet 38.700 con partes automáticas y la de Sofía (12.900) cobrada. Monto a
  45.000: la parte de Sofía pasa a 15.000, su tilde queda desmarcado y la línea muestra
  "cobrado 12.900, falta 2.100"; el total de Sofía suma 2.100 por esa línea.
- **CA-31.5** Mismo caso, monto a 30.000: la parte de Sofía pasa a 10.000, tilde desmarcado,
  la línea muestra "cobrado 12.900, a devolver 2.900"; el total de Sofía resta 2.900 por esa
  línea.
- **CA-31.6** Parte manual de Sofía 15.000 cobrada, monto de Internet de 38.700 a 45.000: la
  parte de Sofía no cambia y sigue cobrada.
- **CA-31.7** En el caso CA-31.4, volver a marcar el tilde: la línea queda cobrada con 15.000
  y no aporta nada al total de Sofía.
- **CA-32.1** Cargar "Préstamo MP" 20.000 a Sofía: aparece en su lista como no cobrado.
- **CA-32.2** Ítem con monto ≤ 0 o sin descripción: se rechaza.
- **CA-33.1** Sofía con Internet 12.900 (2026-10) y Préstamo MP 20.000: total 32.900.
- **CA-33.2** Al crear 2026-11 con Internet fijo compartido, la lista de Sofía muestra Internet
  de 2026-10 y de 2026-11 (indicando el mes) y su total pasa a 45.800, sin importar qué mes
  esté seleccionado.
- **CA-34.1** Marcar cobrado el Préstamo MP: total de Sofía 12.900. Desmarcarlo: 32.900.
- **CA-34.2** Marcar o desmarcar cobrados no cambia total de gastos, pesos a cubrir, USD a
  cambiar ni ahorro.
- **CA-34.3** Al crear 2026-11, Internet aparece compartido con Sofía y Marsu con sus partes
  como no cobradas, aunque en 2026-10 estuvieran cobradas. Las partes manuales se copian
  con su valor.

### Módulo G – Resumen
- **CA-35.1** Con gastos 1.434.617 y 400.000 pagados, la pantalla principal muestra: sueldo
  1.200,00 USD, cotización 1.600, total gastos 1.434.617, pesos a cubrir 1.434.617, USD a
  cambiar 896,64, ahorro 303,36, total pendiente 1.034.617.
- **CA-35.2** El total que le deben es la suma de los totales de todas las personas
  (acumulado) y es el mismo al seleccionar 2026-09 o 2026-10.
- **CA-35.3** Con sueldo 800: ahorro −96,64 mostrado en rojo como "Déficit".
- **CA-35.4** En el caso CA-27.3 se ve "Pesos sobrantes: 60.000".
- **CA-36.1** Cargar meta 300: con ahorro 303,36 la barra está llena y el texto dice 101 %
  (101,12 %). Cambiar la meta a 600: barra al 50,56 %.
- **CA-36.2** Ahorro negativo: barra en 0 %. Sin meta: no hay barra. Meta 0 o negativa: se
  rechaza.
- **CA-36.3** La meta es la misma en todos los meses: cambiarla en 2026-10 cambia la barra de
  2026-09.
- **CA-37.1** Sueldo 1.200, cotización 1.600, gastos fijos 785.300, cuotas del mes 41.117,
  meta 300 USD, pago único 15.000: capacidad = 1.920.000 − 785.300 − 41.117 − 480.000 =
  **613.583 ARS** (el pago único no cuenta).
- **CA-37.2** Igual que CA-37.1 sin meta: capacidad 1.093.583.
- **CA-37.3** Igual que CA-37.1 con meta 1.000 USD: capacidad **−506.417**, en rojo con el
  aviso "Sin capacidad de endeudamiento".
- **CA-37.4** Igual que CA-37.1 con cotización 1.700: 2.040.000 − 785.300 − 41.117 − 510.000 =
  703.583.

### Módulo H – Previsiones
Base: mes actual 2026-10, fijos que suman 800.000 (uno de ellos Internet 38.700 compartido),
Avant 41.117 con última cuota 2026-10, plan B de 10.000 con última cuota 2027-02, un pago
único de 15.000 en 2026-10.
- **CA-38.1** La tabla tiene 12 filas: 2026-11 a 2027-10. No incluye 2026-10. Es la misma con
  2026-09 seleccionado.
- **CA-38.2** 2026-11 a 2027-02: gastos 810.000; USD a cambiar 506,25; ahorro 693,75.
  2027-03 en adelante: gastos 800.000; USD a cambiar 500,00; ahorro 700,00.
- **CA-38.3** El pago único de 15.000 no aparece en ninguna fila; Internet cuenta 38.700
  completo.
- **CA-38.4** Agregar en 2026-10 un extra USD 100 y un extra ARS 50.000: la tabla no cambia.
- **CA-38.5** Cambiar la cotización actual a 2.000: 2026-11 USD a cambiar 405,00 y ahorro
  795,00, sin otros cambios.
- **CA-38.6** Si la cuota de 2026-12 del plan B fue borrada a mano (cuota omitida), la fila
  2026-12 muestra 800.000 y las demás no cambian.
- **CA-38.7** Sin cotización en el mes actual: se ven los gastos ARS y el aviso de que falta
  la cotización. Si 2026-10 no existe (último mes 2026-09): se ve "Creá el mes Octubre 2026 para
  ver la previsión".
- **CA-38.8** A la base se agrega en 2026-10 el fijo "Claude" US$ 20,00 guardado con
  cotización 1.600 (32.000) y después se cambia la cotización de 2026-10 a 1.700 (Claude sigue
  en 32.000 en el mes, RN-55). En la previsión Claude cuenta **34.000** en cada fila:
  2026-11 a 2027-02 gastos 844.000, USD a cambiar 496,47, ahorro 703,53; desde 2027-03
  gastos 834.000, USD a cambiar 490,59, ahorro 709,41.
- **CA-38.9** Claude fijo US$ 20,00 guardado con cotización 2.100 (dólar tarjeta, 42.000) y
  cotización actual 1.600: en la previsión cuenta 32.000 (2026-11: gastos 842.000).
- **CA-38.10** Claude fijo US$ 20,00 guardado con cotización 1.600 y 2026-10 sin cotización:
  la previsión muestra gastos 842.000 en 2026-11 (Claude a 1.600, la cotización del gasto) y
  el aviso de que falta la cotización.
- **CA-38.11** Un pago único en USD de 2026-10 no aparece en la previsión.
- **CA-39.1** La fila 2026-11 indica "Avant +$ 41.117" y la fila 2027-03 "Plan B +$ 10.000".
  Ninguna otra fila indica liberaciones.
- **CA-39.2** Un plan con última cuota 2027-10 no muestra liberación en la tabla.

### Módulo I – Gráficos
- **CA-40.1** Gastos de 2026-10: Alquiler 260.000 (Vivienda), Nafta 30.000 (Transporte),
  Teléfono 20.000 (Comunicaciones), Internet 38.700 compartido entre 3 y Edenor 66.281
  compartido entre 3 (Servicios). El gráfico muestra Vivienda 260.000, Transporte 30.000,
  Comunicaciones 20.000 y Servicios 34.994 (12.900 + 22.093,68). Categorías sin gastos no
  aparecen.
- **CA-41.1** Con 2026-08 (ahorro 250,00), 2026-09 (280,00) y 2026-10 (303,36), el gráfico
  muestra tres puntos en ese orden con esos valores.
- **CA-41.2** Cambiar la cotización de 2026-10 a 1.700 cambia solo ese punto (a 356,11).
- **CA-41.3** Un mes sin cotización y con gastos aparece vacío, sin error.
- **CA-42.1** El gráfico de previsión muestra los mismos 12 valores de gastos que la tabla
  (en la base de módulo H: 810.000 hasta 2027-02 y 800.000 desde 2027-03; en el caso CA-38.8:
  844.000 y 834.000).

### Módulo J – Gastos en dólares
Base: mes 2026-10 con cotización del mes 1.600 y los gastos de la base del módulo E
(1.434.617), salvo que se indique otra cosa.
- **CA-43.1** Alta de "Claude", pago único, moneda USD, US$ 20,00, cotización 1.600: se guarda
  `monto_usd_cent = 2000`, `cotizacion_cent = 160000`, `monto_cent = 3200000`; el total de
  gastos pasa a 1.466.617; pesos a cubrir 1.466.617; USD a cambiar 916,64; ahorro 283,36.
- **CA-43.2** El mismo gasto con cotización del gasto 2.100 (dólar tarjeta): monto 42.000;
  total 1.476.617; USD a cambiar 922,89 (se calcula con la cotización del mes, 1.600);
  ahorro 277,11.
- **CA-43.3** En el formulario de alta de un plan de cuotas no hay selector de moneda.
  Intentar guardar un gasto en USD de tipo cuota (por ejemplo, directamente en la lógica) se
  rechaza.
- **CA-43.4** Claude (US$ 20,00 × 1.600 = 32.000) con medio "Visa Santander" junto con Gym
  50.000 (Visa Santander): el total de Visa Santander es 82.000.
- **CA-43.5** Marcar pagado Claude registra un pago de 32.000 ARS y su pendiente queda en 0.
  Un pago parcial de 10.000 deja pendiente 22.000.
- **CA-43.6** "Netflix" fijo US$ 15,00 × 1.600 = 24.000, compartido con Sofía y Marsu: 8.000
  cada uno, incluido el usuario. El gráfico por categoría suma 8.000 (parte propia).
- **CA-43.7** Capacidad: con los datos de CA-37.1 (613.583) más Claude como **fijo** US$ 20,00
  × 1.600: capacidad 581.583. Como pago único no cambia la capacidad (613.583).
- **CA-44.1** Al elegir USD con cotización del mes 1.600, el campo cotización aparece con
  1.600; al escribir 20 en USD se ve "US$ 20,00 × $ 1.600 = $ 32.000" sin guardar todavía.
- **CA-44.2** US$ 19,99 con cotización 1.432,50: la vista previa muestra
  "US$ 19,99 × $ 1.432,50 = $ 28.636" y se guarda `monto_cent = 2863568`.
- **CA-44.3** En un mes sin cotización, al elegir USD el campo cotización está vacío; guardar
  sin completarlo se rechaza con mensaje. Completándolo con 1.550, US$ 20,00 se guarda como
  31.000.
- **CA-44.4** Monto USD 0, −5, vacío o "abc": se rechaza. Cotización del gasto 0, negativa o
  vacía: se rechaza. Nada se guarda.
- **CA-44.5** US$ 0,01 con cotización 0,40 (resultado 0,004 ARS, que redondea a 0): se rechaza.
- **CA-45.1** Con Claude guardado (US$ 20,00 × 1.600 = 32.000), cambiar la cotización del
  **mes** a 1.700: Claude sigue en 32.000; total 1.466.617; USD a cambiar 862,72; ahorro 337,28.
- **CA-45.2** Editar Claude y poner cotización del gasto 1.700: monto 34.000; total 1.468.617.
- **CA-45.3** Editar Claude y poner US$ 25,00 (cotización 1.600): monto 40.000.
- **CA-45.4** Claude con un pago de 30.000: editar la cotización a 1.400 (28.000) se rechaza
  con un mensaje que indica lo pagado; a 1.550 (31.000) se acepta y el pendiente queda 1.000.
  Editar el monto a US$ 18,00 con cotización 1.600 (28.800) se rechaza.
- **CA-45.5** Cambiar "Nafta" (ARS 30.000) a USD con US$ 25,00 × 1.600: monto 40.000 y se
  muestra el detalle en USD. Volver a ARS con 35.000: monto 35.000, sin monto USD ni
  cotización del gasto guardados.
- **CA-45.6** Claude con 32.000 pagados: pasarlo a ARS con 30.000 se rechaza (RN-23).
- **CA-45.7** Netflix de CA-43.6 con la parte de Sofía (8.000) cobrada: editar la cotización
  del gasto a 1.700 (25.500): las partes automáticas pasan a 8.500; la de Sofía queda
  desmarcada con "cobrado 8.000, falta 500".
- **CA-45.8** Al editar un gasto con cotización 1.432,50, el diálogo muestra la cotización
  como "1.432,50".
- **CA-46.1** En la lista de gastos, Claude se ve con monto "32.000" y el detalle
  "US$ 20,00 × $ 1.600". Los gastos en ARS no muestran detalle en USD.
- **CA-46.2** Un gasto US$ 19,99 × 1.432,50 se ve en la lista con monto "28.636" y el detalle
  "US$ 19,99 × $ 1.432,50" (no "$ 1.433").
- **CA-47.1** Claude fijo US$ 20,00 × 1.600 en 2026-10. Crear 2026-11 con cotización 1.700:
  en 2026-11 Claude es US$ 20,00 × 1.700 = 34.000, sin pagos. Claude de 2026-10 sigue en 32.000.
- **CA-47.2** Igual, creando 2026-11 sin cotización: Claude conserva la cotización 1.600 y
  queda en 32.000.
- **CA-47.3** Claude fijo US$ 20,00 × 2.100 (dólar tarjeta) en 2026-10; crear 2026-11 con
  cotización 1.700: en 2026-11 queda US$ 20,00 × 1.700 = 34.000.
- **CA-47.4** Después de CA-47.1, cambiar la cotización de 2026-11 a 1.800: Claude de 2026-11
  sigue en 34.000.
- **CA-47.5** Un pago único en USD de 2026-10 no aparece en 2026-11.
- **CA-47.6** Netflix fijo US$ 15,00 compartido entre 3 con partes automáticas, creado 2026-11
  con cotización 1.700: monto 25.500 y partes de 8.500, no cobradas.
- **CA-47.7** Netflix fijo US$ 15,00 × 1.600 (24.000) con Sofía manual 12.000 y Marsu manual
  10.000 (usuario 2.000). Crear 2026-11 con cotización 1.500: monto 22.500; Sofía 12.000 y
  Marsu 10.000 se mantienen (manuales), usuario 500; no hay aviso.
- **CA-47.8** Mismo Netflix, crear 2026-11 con cotización 1.400: monto 21.000; como el usuario
  quedaría en −1.000, las tres partes pasan a 7.000 (automáticas) y al crear el mes se ve
  "Las partes de Netflix se repartieron en partes iguales porque cambió el monto." El mes se
  crea igual y las partes de 2026-10 siguen siendo 12.000 / 10.000 / 2.000.
- **CA-48.1** Con una base en versión 0 que ya tiene meses, gastos, pagos y partes cargados
  (en las pruebas, una base y una carpeta de respaldos temporales; nadie lee
  `datos-privados/`): al abrir la versión con gastos en dólares existe un respaldo
  `respaldos/gastos-AAAAMMDD-HHMMSS.db` hecho antes del cambio, que se puede abrir y contiene
  los mismos datos que la base original; la base queda en versión 1; todos los gastos
  aparecen como ARS; totales, pagos, pendientes y "me deben" son idénticos a los de antes.
- **CA-48.2** Abrir la app una segunda vez con la base en versión 1 no vuelve a aplicar la
  actualización (no intenta agregar las columnas de nuevo) ni pierde los gastos en USD
  cargados mientras tanto.
- **CA-48.3** Si la actualización falla a mitad de camino (simulado en las pruebas), la base
  sigue en versión 0, sin las columnas nuevas y con los mismos datos, y la app avisa.
- **CA-48.4** Si no se puede crear el respaldo (simulado en las pruebas), la base no se
  modifica (sigue en versión 0) y la app avisa.

### Módulo K – Importar Excel (v2)
Base: mes actual 2026-10 y fecha de hoy fijadas en las pruebas. Existe solo 2026-10 (es el
último mes), con sueldo 1.200, cotización 1.600 y el gasto fijo "Alquiler" 260.000
(Vivienda), sin pagos. Personas activas: Sofía y Marsu. Categorías activas, entre otras:
Varios, Vivienda y Servicios. Sin ítems "me deben" ni planes.

Archivo `planilla-prueba.xlsx`: lo generan las pruebas (nunca se usa un archivo de
`datos-privados/`), con una sola hoja "Octubre". Las celdas no indicadas están vacías;
"(texto)" quiere decir un número escrito como texto; el resto de los números son números de
Excel.

| Fila | B | C | D | E |
|---|---|---|---|---|
| 1 | | Gasto del Mes | | |
| 2 | | | Gastos | Pagado |
| 3 | | Alquiler | 260000 | |
| 4 | | Servicios | "82.000" (texto) | |
| 5 | | Internet | 38700 | 38700 |
| 6 | | Tarjetas de Credito | 582917 | |
| 7 | | psicologo | 140000 | 60000 |
| 8 | | | total | Falta por pagar |
| 9 | | | 1103617 | 1004917 |
| 11 | | Deudas | Monto | Total deudas |
| 12 | | Monotributo 66.020,12 | "66.020,12" (texto) | 66021 |
| 13 | | Avant Service cuota 3/ 3 $41.116,66 | 41116,66 | |
| 14 | | Deuda freezer | | |
| 15 | | Gym | 50000 | |
| 16 | | Obra social | | |
| 18 | Sueldo | | | |
| 19 | 1300 | | | |
| 21 | | | Deudas sofia | |
| 22 | | | Prestamo MP | 20000 |
| 23 | | | Internet | 12900 |
| 24 | | | Total | 32900 |
| 26 | | | Marsu | |
| 27 | | | tacones chiqui baby | 6785 |
| 28 | | | Total | 6785 |

Cómo se lee la columna E (RN-64): de la fila 3 a la 7 es columna de pagado (encabezado
"Pagado" en E2), así que 38.700 (E5) y 60.000 (E7) son pagados. "Falta por pagar" (E8) cierra
esa columna; desde ahí E deja de ser de pagado: 1.004.917 (E9) es un número sin nombre y
66021 (E12, bajo "Total deudas") se descarta. Las filas 10, 17, 20 y 25, totalmente vacías,
también cierran cualquier encabezado (RN-64).

Lista principal esperada con esta base (la usan varios CA):

| Fila | Nombre | Monto | Pagado | Tipo propuesto | Bloque | Marca / aviso / tilde |
|---|---|---|---|---|---|---|
| 3 | Alquiler | 260.000 | | Gasto fijo | Gasto del Mes | "ya existe", destildada |
| 4 | Servicios | 82.000 | | Gasto fijo | Gasto del Mes | tildada |
| 5 | Internet | 38.700 | 38.700 | Gasto fijo | Gasto del Mes | tildada |
| 6 | Tarjetas de Credito | 582.917 | | Ignorar | Gasto del Mes | — |
| 7 | psicologo | 140.000 | 60.000 | Gasto fijo | Gasto del Mes | tildada |
| 12 | Monotributo 66.020,12 | 66.020,12 | | Gasto fijo | Deudas | tildada |
| 13 | Avant Service cuota 3/ 3 $41.116,66 | 41.116,66 | | Cuota 3 de 3 | Deudas | tildada |
| 15 | Gym | 50.000 | | Gasto fijo | Deudas | tildada |
| 22 | Prestamo MP | 20.000 | | Me deben – Sofía | Deudas sofia | tildada, no cobrado |
| 23 | Internet | 12.900 | | Me deben – Sofía | Deudas sofia | aviso de posible gasto compartido, tildada, no cobrado |
| 24 | Total | 32.900 | | Ignorar | Deudas sofia | — |
| 27 | tacones chiqui baby | 6.785 | | Me deben – Marsu | Marsu | tildada, no cobrado |
| 28 | Total | 6.785 | | Ignorar | Marsu | — |

- **CA-49.1** Con la base vacía (sin meses), la pantalla de primer uso muestra el formulario
  para crear el primer mes igual que en la v1 (CA-04.1) y, debajo, "¿Tenés una planilla?" con
  el botón "Importar Excel". Crear el mes con el formulario funciona igual que antes, sin
  pasar por la importación. "Importar Excel" abre la importación en pantalla completa, sin
  rail ni barra superior; "Cancelar" (sin haber cambiado nada) vuelve al formulario de primer
  uso y la base sigue sin meses.
- **CA-49.2** Con meses cargados, Ajustes tiene como última pestaña "Importar Excel", con el
  botón "Importar Excel". La importación se abre en pantalla completa, sin rail ni barra
  superior (no se puede cambiar de mes ni de pantalla mientras dura). "Cancelar" (sin haber
  cambiado nada) vuelve a la pestaña "Importar Excel" de Ajustes.
- **CA-50.1** Con `planilla-prueba.xlsx` (una sola hoja) la app no pregunta la hoja y muestra
  la lista. Si el archivo tiene además una hoja "Septiembre", la app pregunta cuál usar y
  muestra solo las filas de la hoja elegida.
- **CA-50.2** Después de confirmar una importación, en la carpeta de datos de la app no hay
  ninguna copia del `.xlsx`; borrar el `.xlsx` no cambia nada en la app; el `.xlsx` tiene
  exactamente el mismo contenido que antes de importar.
- **CA-51.1** La lista principal tiene exactamente las 13 filas de la tabla esperada, en ese
  orden, con esos montos y pagados, y cada una indica su número de fila del Excel. El 66021 de
  la fila 12 (columna "Total deudas") no aparece en ningún lado.
- **CA-51.2** El grupo "Filas incompletas" contiene exactamente estas 16 filas, todas como
  "ignorar": "Gasto del Mes", "Gastos", "Pagado", "total", "Falta por pagar", 1.103.617 (sin
  nombre), 1.004.917 (sin nombre), "Deudas", "Monto", "Total deudas", "Deuda freezer", "Obra
  social", "Sueldo", 1.300 (sin nombre), "Deudas sofia" y "Marsu". Las que tienen nombre
  muestran "Falta el monto. Se ignora." y las que no, "Falta el nombre. Se ignora.". "Falta
  por pagar" está porque, como todo encabezado, es un texto sin monto; además cierra la
  columna de pagado (RN-64), y por eso 1.004.917 aparece como número sin nombre y no como
  pagado de ninguna fila. "Deuda freezer" y "Obra social" aparecen en este grupo (no dentro
  del bloque "Deudas"), aunque la lógica las asigna al bloque "Deudas" (CA-51.7).
- **CA-51.3** Lectura de números (en centavos): textos "82.000" → `8200000`; "1.050.000" →
  `105000000`; "66.020,12" → `6602012`; "$ 41.116,66" → `4111666`; "41116,66" →
  `4111666`; número de Excel 41116,66 → `4111666`; número de Excel 22093,666 → `2209367`.
  Una fila "Nafta | "82.5"" da dos filas incompletas ("Nafta" y "82.5"). Una fecha en la
  columna del monto deja la fila sin monto.
- **CA-51.4** Una fila oculta del Excel con "Luz | 1000" aparece en la lista principal.
- **CA-51.5** Columna de pagado (RN-64), sobre `planilla-prueba.xlsx`:
  - Cambiando E2 a "Pago", "Pagos", "Abonado" o "ABONADO", Internet y psicologo siguen
    trayendo pagado 38.700 y 60.000. Con "Pagué", ninguna fila trae pagado (los 38.700 y
    60.000 se descartan).
  - Con E2 "Pagado" y un texto "x" en E4 (al lado de "Servicios | 82.000"): la "x" es un
    valor de la fila, no un encabezado. Servicios no trae pagado, la "x" no aparece como fila
    (ni en la lista ni en "Filas incompletas") y la columna sigue siendo de pagado: Internet
    y psicologo siguen trayendo 38.700 y 60.000.
  - Pagado de una fila sin monto (RN-63): borrando el monto de Servicios (D4 vacía) y
    poniendo 3 en E4, "Servicios" queda en "Filas incompletas" con "Falta el monto. Se
    ignora." y sin pagado. Completándola con monto 1 y tipo gasto fijo, no muestra ningún
    error de pagado y al confirmar se importa sin pagos (pendiente 1).
  - "Falta por pagar" (E8) cierra la columna de pagado: 1.004.917 (E9) no es el pagado de
    ninguna fila (CA-51.2).
  - Cambiando "Total deudas" (E11) por "Pagado", la columna E es de pagado solo para las
    filas 12 a 16: la fila 17, totalmente vacía, cierra ese encabezado (RN-64).
    Monotributo trae pagado 66.021 y muestra el error "El pagado ($ 66.021) es mayor que el
    monto ($ 66.020)." (se ven distintos, así que van sin centavos, RN-69). Avant y Gym no
    traen pagado (E13 y E15 están vacías). Los bloques "Deudas sofia" y "Marsu" quedan igual
    que en la lista esperada: los números de E22 a E28 son sus montos (no pagados), con los
    mismos tipos y tildes.
- **CA-51.6** Columna de cobrado: a `planilla-prueba.xlsx` se le agrega en la columna F:
  "Cobrado" en F21, 20000 en F22, "x" en F23, "Cobrado" en F26 y 3000 en F27. Entonces
  "Prestamo MP" e "Internet" (Sofía) vienen con el tilde "cobrado" marcado; "tacones chiqui
  baby" viene sin cobrar y con la nota "En la columna Cobrado dice "3.000"; los ítems 'me
  deben' no tienen cobro parcial, quedó como no cobrado." Confirmando sin cambios, los dos
  ítems de Sofía quedan cobrados (su total no suma nada por ellos) y el de Marsu queda no
  cobrado (Marsu 6.785). Si el usuario destilda "cobrado" en "Prestamo MP" antes de
  confirmar, ese ítem queda no cobrado (Sofía 20.000). Con un "no" en F22, "Prestamo MP" viene
  sin cobrar y con la nota (el "no" es un valor de la fila, no cierra la columna: "Internet"
  sigue cobrado por la "x" de F23). "Cobrado" en F26 está en una fila sin monto ("Marsu"), así
  que es un encabezado nuevo y la columna sigue siendo de cobrado. Un número en una columna
  "Cobrado" en una fila de gasto se descarta.
- **CA-51.7** Título de bloque que entrega la lógica (RN-65) con `planilla-prueba.xlsx`:
  filas 3 a 7 → "Gasto del Mes" (la fila 2 y las filas 8 y 9 no cortan el bloque; la 10,
  vacía, sí); filas 12, 13 y 15 → "Deudas", y también las incompletas 14 "Deuda freezer" y
  16 "Obra social" (están pegadas, no son títulos); filas 22, 23 y 24 → "Deudas sofia";
  filas 27 y 28 → "Marsu". Los títulos y los números sin nombre (filas 9 y 19) no tienen
  bloque. En la lista se ven, en este orden, los bloques "Gasto del Mes" (5 filas), "Deudas"
  (3 filas), "Deudas sofia" (3 filas) y "Marsu" (2 filas); no hay bloque "Otras filas" ni
  bloques vacíos ("Gastos", "Monto", "Sueldo", etc.). Un Excel sin ningún título muestra un
  solo bloque, "Filas detectadas".
- **CA-51.8** Variantes de bloque, sobre `planilla-prueba.xlsx`:
  - Insertando una fila del Excel nueva debajo de la 21 con "Concepto" en D e "Importe" en E
    (las filas 22 a 28 bajan una): "Concepto" está pegada a "Deudas sofia" y no es título;
    "Prestamo MP" e "Internet" siguen en el bloque "Deudas sofia" y siguen viniendo como "me
    deben" Sofía. "Concepto" e "Importe" van a "Filas incompletas".
  - Insertando en cambio una fila del Excel totalmente vacía entre la 21 y la 22: el bloque
    "Deudas sofia" queda sin filas; "Prestamo MP", "Internet" y "Total" van al bloque "Otras
    filas" y "Prestamo MP" e "Internet" vienen como gasto fijo.
  - Poniendo un texto "Préstamos" en C14 en lugar de "Deuda freezer" y dejando vacía la fila
    13 entera (borrando Avant): "Préstamos" tiene la celda de arriba vacía, es un título, y
    "Gym" (fila 15) queda en el bloque "Préstamos"; "Monotributo" sigue en "Deudas".
- **CA-51.9** Una fila vacía cierra el encabezado de pagado (RN-64): un Excel con "Pagado" en
  E1, "Luz | 5 | 3" en C2, D2 y E2, la fila 3 totalmente vacía y 99 en E4. "Luz" viene con
  monto 5 y pagado 3; el 99 aparece en "Filas incompletas" como número sin nombre ("Falta el
  nombre. Se ignora."), no como pagado.
- **CA-52.1** "Tarjetas de Credito" y los dos "Total" vienen como "ignorar"; "Avant Service
  cuota 3/ 3 $41.116,66" como cuota 3 de 3, con la nota "Plan de 3 cuotas: primera Agosto
  2026, última Octubre 2026. Se agrega la cuota 3/3 en Octubre 2026."; "Prestamo MP" e
  "Internet" (filas 22 y 23) como "me deben" Sofía; "tacones chiqui baby" como "me deben"
  Marsu; el resto como gasto fijo.
- **CA-52.2** Filas "Cumple 15/10 | 5000" y "Préstamo 0/5 | 5000" vienen como gasto fijo (no
  cuota). "Heladera 2/12 | 30000" viene como cuota 2 de 12. "Algo 601/601 | 1000" y "Algo
  100000/100000 | 1000" vienen como gasto fijo (N > 600, RN-66); "Algo 1/600 | 1000" viene
  como cuota 1 de 600. "Heladera 1/1 | 30000" viene como cuota 1 de 1 con la nota "Plan de 1
  cuota: primera Octubre 2026, última Octubre 2026. Se agrega la cuota 1/1 en Octubre 2026."
- **CA-52.3** Con el título de la fila 21 cambiado a "Deudas Juan" (no existe la persona
  Juan), "Prestamo MP" e "Internet" vienen como gasto fijo. Con Marsu archivada,
  "tacones chiqui baby" viene como gasto fijo. Con el título "Sofía y Marsu", sus filas vienen
  como "me deben" sin persona.
- **CA-52.4** Con el título "Deudas sofia" como celda combinada D21:E21, el resultado es el
  mismo que en CA-52.1.
- **CA-52.5** Archivo de prueba guardado con Excel o LibreOffice (se guarda en `tests/`, sin
  datos reales) con "Suma servicios | =SUM(D1:D2)" cuyo valor guardado es 120000: la fila
  viene con monto 120.000 y tipo "ignorar".
- **CA-52.6** Se puede cambiar el tipo de cualquier fila a cualquiera de los seis tipos.
- **CA-52.7** Tilde y tipo "ignorar": "Tarjetas de Credito" (fila 6) viene sin tilde y su
  tilde no se puede marcar. Al cambiarle el tipo a gasto fijo, queda tildada sola; al
  volverla a "ignorar", queda sin tilde. "Alquiler" (fila 3, "ya existe", destildada) pasada
  de gasto fijo a gasto único sigue destildada; pasada a "ignorar" y después a gasto fijo,
  queda **tildada** y con la nota "Ya existe en Octubre 2026. Si la importás, queda
  repetida.".
- **CA-52.8** Acciones de bloque en "Deudas sofia" (filas 22, 23 y 24): "Destildar todas las
  filas" destilda 22 y 23; 24 ("Total", ignorar) sigue sin tilde. "Tildar todas las filas"
  vuelve a tildar 22 y 23; 24 sigue en "ignorar" y sin tilde. Con la base de CA-56.4 (segunda
  importación), "Tildar todas las filas" tilda también las filas "ya existe" del bloque.
- **CA-53.1** Cambiar el nombre "psicologo" a "Psicólogo" y el monto de "Servicios" a
  "85.000", y confirmar: se guardan "Psicólogo" y 85.000.
- **CA-53.2** Completar la fila incompleta "Obra social" con monto 45.000 y tipo gasto fijo:
  al confirmar existe "Obra social" 45.000. Cambiándole el tipo a gasto fijo sin completar el
  monto, la fila muestra el error "Falta el monto." y no se puede confirmar.
- **CA-53.3** Cambiar "Gym" a cuota sin cuota actual ni cantidad: error "Indicá la cuota
  actual y la cantidad de cuotas.". Con cuota 2 de 6: al confirmar existe un plan "Gym" de 6
  cuotas de 50.000 con primera cuota 2026-09, y en 2026-10 se ve la cuota "2/6". Cuota 7 de 6:
  error "La cuota actual tiene que estar entre 1 y la cantidad de cuotas."; cantidad 0 o 2,5:
  error "La cantidad de cuotas tiene que ser un número entero de 1 o más.".
- **CA-53.4** Cambiar "Servicios" a "me deben": la persona viene vacía, la fila muestra
  "Elegí una persona." y no se puede confirmar hasta elegirla. Crear la persona nueva "Juan"
  y elegirla: al confirmar existe Juan con el ítem "Servicios" 82.000 no cobrado. Crear una
  persona nueva "sofía": se rechaza con "Ya existe una persona llamada "Sofía"."
- **CA-53.5** "Cambiar tipo o categoría de todas..." con el título de la fila 21 cambiado a
  "Sofía y Marsu" (filas 22 y 23 "me deben" sin persona): con "No cambiar el tipo" y persona
  Marsu, las filas 22 y 23 quedan "me deben" Marsu y la 24 ("Total") sigue en "ignorar" sin
  tilde; al confirmar, Marsu tiene "Prestamo MP" 20.000 e "Internet" 12.900. En el diálogo,
  "Cuota" y "Sueldo (USD)" no se pueden elegir como tipo.
- **CA-53.6** En el bloque "Deudas sofia", "Cambiar tipo o categoría de todas..." con tipo
  "Gasto único" y categoría Servicios: las filas 22, 23 y 24 quedan como gasto único en
  Servicios y tildadas (la 24 se tilda sola al dejar "ignorar"). En el bloque "Deudas", con
  "No cambiar el tipo" y categoría Vivienda: Monotributo, Avant y Gym quedan en Vivienda; si
  después la categoría por defecto pasa a Servicios, esas tres siguen en Vivienda. Las
  incompletas "Deuda freezer" y "Obra social" no cambian.
- **CA-53.7** Tope de cuotas en la revisión (RN-29, RN-68): editando Avant (fila 13) con
  cuota 1 de 601, el diálogo muestra "La cantidad de cuotas es demasiado grande." y no se
  puede aceptar (en la lógica, editar la fila con cantidad 601 devuelve ese error). Con cuota
  1 de 600 no hay error, la nota dice "Plan de 600 cuotas: primera Octubre 2026, última
  Septiembre 2076. Se agrega la cuota 1/600 en Octubre 2026." y al confirmar existe el plan
  de 600 cuotas (el guardado no falla).
- **CA-54.1** La categoría por defecto viene "Varios". Al confirmar sin tocarla, los gastos y
  el plan importados quedan en Varios y sin medio de pago (en el total por medio de pago
  suman en "Sin medio de pago", RF-22).
- **CA-54.2** Cambiar la categoría de "Internet" (fila 5) a Servicios y después la categoría
  por defecto a Vivienda: Internet queda en Servicios; las demás filas de gasto y la cuota
  pasan a Vivienda.
- **CA-54.3** Sin la categoría "Varios": no hay categoría por defecto, cada fila de gasto y de
  cuota muestra "Elegí una categoría." y no se puede confirmar hasta elegir una. Crear la
  categoría nueva "Importado" y cancelar: "Importado" no existe.
- **CA-55.1** El mes destino viene 2026-10. Se ofrecen 2026-10 y 2026-11; no se ofrecen
  2026-09 ni 2026-12.
- **CA-55.2** Destino 2026-11 (no existe), con la fila 19 como sueldo: la fila de sueldo
  muestra "Sueldo del mes: US$ 1.200,00 -> US$ 1.300,00.". Al confirmar existe 2026-11 con
  Alquiler copiado (RN-09), sueldo 1.300,00, cotización 1.600 y las filas importadas.
  "Alquiler" del Excel también venía "ya existe". Avant crea un plan con primera cuota
  2026-09: 2026-11 tiene la cuota "3/3" y 2026-10 (mes actual) recibe la cuota "2/3"
  (RN-30); 2026-10 no recibe ningún otro dato importado y su sueldo sigue en 1.200.
- **CA-55.3** Con 2026-09 y 2026-10 existentes y destino 2026-09: la revisión avisa "Los
  gastos fijos que importes no se agregan a los meses siguientes que ya existen.". Avant crea
  un plan con primera cuota 2026-07 y última 2026-09; 2026-09 tiene la cuota "3/3"
  (excepción a RN-30) y 2026-10 no tiene cuota de Avant.
- **CA-55.4** Base sin meses, desde el primer uso, destino 2026-10 y la fila 19 como sueldo: se
  crea 2026-10 con sueldo 1.300,00 y sin cotización (el resumen muestra "Cargá la
  cotización"). Sin marcar sueldo: sueldo 0 y el aviso "El sueldo de este mes es 0". Mes 13 o
  año "26": se rechaza.
- **CA-55.5** Con último mes 2026-08 (2026-09 y 2026-10 no existen), el destino propuesto es
  2026-08.
- **CA-56.1** "Alquiler" viene "ya existe", destildada y con la nota "Ya existe en Octubre
  2026. Viene destildada."; al confirmar sin tocarla, 2026-10 tiene un solo Alquiler. Si se
  tilda, la nota pasa a "Ya existe en Octubre 2026. Si la importás, queda repetida." y al
  confirmar quedan dos.
- **CA-56.2** Con un gasto "Teléfono" en 2026-10, una fila " telefono " del Excel viene
  "ya existe".
- **CA-56.3** Un Excel con "Nafta | 30000" en dos filas: las dos vienen tildadas y con la nota
  "Repetida en el archivo. Si no es un error del Excel, podés importarla igual.", y se puede
  confirmar: quedan dos Nafta de 30.000. En `planilla-prueba.xlsx`, "Internet" (fila 5,
  gasto) e "Internet" (fila 23, me deben) no se marcan como repetidas.
- **CA-56.4** Importar `planilla-prueba.xlsx` dos veces en 2026-10: en la segunda, todas las
  filas de gasto, la de Avant y las tres de "me deben" vienen "ya existe" y destildadas. Las
  de "me deben" muestran, por ejemplo, "Sofía ya tiene un ítem sin cobrar con esta
  descripción. Viene destildada." y las de gasto "Ya existe en Octubre 2026. Viene
  destildada.". Avant (que coincide con su cuota de 2026-10 y con su plan) muestra la nota
  de gasto, "Ya existe en Octubre 2026. Viene destildada.", y no la de plan (RN-74). Al
  tildar "Prestamo MP", su nota pasa a "Sofía ya tiene un ítem sin cobrar con esta
  descripción. Si la importás, queda repetida."; al destildarla, vuelve a "Viene
  destildada.".
- **CA-56.5** Con 2026-09 (sin Alquiler) y 2026-10 (con Alquiler) existentes: con destino
  2026-10, "Alquiler" viene "ya existe" y destildada; al cambiar el destino a 2026-09 la marca
  desaparece, la fila vuelve a tildarse y se ve el mensaje "Cambiaste el mes: 1 fila se volvió
  a tildar."; al cambiar a 2026-11 (que va a copiar Alquiler de 2026-10) vuelve a "ya existe",
  se destilda y se ve "Cambiaste el mes: 1 fila pasó a "ya existe" y se destildó.".
- **CA-56.6** Aviso de posible gasto compartido, con `planilla-prueba.xlsx`:
  - "Internet" (fila 23, me deben Sofía) muestra "¿Es parte de un gasto compartido? Si es así,
    ignorala y marcá el gasto como compartido después.", porque la fila 5 "Internet" se va a
    importar como gasto fijo. Sigue como "me deben" Sofía y tildada, y se puede confirmar.
    "Prestamo MP" y "tacones chiqui baby" no muestran el aviso.
  - Pasando la fila 5 a "ignorar" (o destildándola), el aviso de la fila 23 desaparece. Si
    además 2026-10 tiene un gasto "Internet", el aviso vuelve a aparecer.
  - Agregando una fila "Servicios Luz Gas | 35500" en el bloque de Sofía (fila 24, antes del
    "Total"), muestra el aviso porque "Servicios" (fila 4) es gasto fijo. Una fila "Pesos
    Check | 142406" en el bloque de Sofía no lo muestra si en el archivo y en el mes solo hay
    "Pesos checks".
- **CA-56.7** Nota "ya existe" de un plan de cuotas: con un plan terminado "Heladera 2/12"
  (sin cuota en 2026-10) y un Excel con "Heladera 2/12 | 30000", la fila viene como cuota,
  "ya existe", destildada y con la nota "Ya existe un plan de cuotas con este nombre. Viene
  destildada."; al tildarla, la nota pasa a "Ya existe un plan de cuotas con este nombre. Si
  la importás, queda repetida." y al confirmar quedan dos planes "Heladera 2/12".
- **CA-57.1** Confirmar con la base, la lista esperada y la fila 19 (1.300) como sueldo, sin
  otros cambios. 2026-10 queda con: Alquiler 260.000 (el de antes, sin cambios), Servicios
  82.000, Internet 38.700 (pagado), psicologo 140.000 (pagado 60.000, pendiente 80.000),
  Monotributo 66.020,12 (`6602012`, se ve "66.020"), "Avant Service cuota 3/ 3 $41.116,66"
  41.116,66 con cuota "3/3" (plan de 3 cuotas desde 2026-08) y Gym 50.000; todos fijos salvo
  la cuota, en Varios y sin medio de pago. Totales: gastos 677.837 (`67783678`), pagado
  98.700, pendiente 579.137. Sueldo 1.300,00; USD a cambiar 423,65; ahorro 876,35. Me deben:
  Sofía 32.900 (Prestamo MP 20.000 e Internet 12.900) y Marsu 6.785 (tacones chiqui baby),
  no cobrados y con la fecha de hoy. Los pagos tienen la fecha de hoy. No se crea ninguna
  categoría ni persona.
- **CA-57.2** Después de CA-57.1 se ve "Importación terminada" con "Se importaron: 5 gastos,
  1 plan de cuotas, 3 ítems "me deben" y el sueldo (US$ 1.300,00) en Octubre 2026." y, bajo
  "Para completar:", "Los gastos quedaron sin medio de pago. Podés ponérselo en Gastos." y
  "Si alguno es compartido, marcalo desde el gasto." (no aparece la línea de la cotización,
  porque 2026-10 la tiene). Al tocar "Ver Octubre 2026", la app muestra 2026-10 como mes
  seleccionado, en la pantalla Gastos, con el rail y la barra superior. No hay ninguna opción
  para deshacer la importación.
- **CA-57.3** Desde Ajustes: cambiar tipos, crear la persona "Juan", elegir destino 2026-11 y
  tocar "Cancelar" (o `Esc`): la app pregunta "¿Descartar la importación?" con "Se pierden los
  cambios que hiciste en la revisión. No se guarda nada." y "También se descartan las
  categorías y personas nuevas: Juan.". "Seguir revisando" vuelve a la revisión sin perder
  nada. "Descartar" vuelve a la pestaña "Importar Excel" de Ajustes, y no existen 2026-11 ni
  Juan, ni gastos, pagos, planes o ítems nuevos, y 2026-10 sigue igual (sueldo 1.200). Sin
  ningún cambio en la revisión, "Cancelar" sale sin preguntar. Con cambios, "Cambiar archivo u
  hoja" pregunta "¿Volver a elegir el archivo?".
- **CA-57.4** Si el guardado falla a mitad (simulado en las pruebas) con destino 2026-11: no
  existe 2026-11 ni ningún dato importado, y se ve "No se pudo importar" con el texto "No se
  pudo importar. No se guardó ningún dato." Con "Volver a la revisión" la lista está igual
  que antes de confirmar (mismos tipos, tildes, correcciones, Juan y destino).
- **CA-57.5** Excel con "Luz | 10000 | 12000" bajo un encabezado "Pagado": la fila muestra "El
  pagado ($ 12.000) es mayor que el monto ($ 10.000)." y no se puede confirmar. Subiendo el
  monto a 12.000 se importa pagada completa; bajando el pagado a 4.000, queda pendiente
  6.000. Pagado −100: error "El pagado no puede ser negativo.". Pagado 0: se importa sin
  pagos. Con "Gas | 1234,50 | 1234,56" (números de Excel): "El pagado ($ 1.234,56) es mayor
  que el monto ($ 1.234,50)."; con "Gas | 1234,50 | 1234,51": "El pagado ($ 1.234,51) es
  mayor que el monto ($ 1.234,50)." (nunca "El pagado ($ 1.235) es mayor que el monto
  ($ 1.235).").
- **CA-57.6** Con las filas 19 y 9 (1.004.917) marcadas como sueldo: no se puede confirmar y
  se ve "Marcaste 2 filas como sueldo; dejá una sola." en las dos filas y en el pie.
- **CA-57.7** Excel con "Descuento | -5000" y "Nada | 0": vienen como "ignorar" con la nota
  "Monto no válido. Si querés importarla, corregí el monto."; pasadas a gasto fijo sin
  corregir el monto, muestran "El monto tiene que ser mayor a 0." y no se puede confirmar.
- **CA-57.8** Con todas las filas en "ignorar" o destildadas: no se puede confirmar y se ve
  "No hay filas para importar." Con dos filas con error: el pie dice "Hay 2 filas con
  errores. Corregilas, ignoralas o destildalas para continuar." y no se puede confirmar.
- **CA-57.9** Resumen previo, en el caso de CA-57.1: antes de confirmar, el pie dice "Se
  importan 10 filas: 5 gastos, 1 plan de cuotas, 3 ítems "me deben" y el sueldo." Al tocar
  "Confirmar importación" todavía no se guarda nada y se ve "Revisá antes de importar" con:
  "Se va a cargar en Octubre 2026 (ya existe).", "5 gastos: $ 376.720 (pagado $ 98.700)",
  "1 plan de cuotas: Avant Service cuota 3/ 3 $41.116,66 (cuota 3/3, $ 41.117 por mes)",
  "3 ítems "me deben": Sofía 2, Marsu 1 ($ 39.685 en total)", "Sueldo: US$ 1.200,00 ->
  US$ 1.300,00", "No se importan 19 filas (ignoradas o destildadas)." y "Esta importación no
  se puede deshacer. Si algo sale mal, lo corregís a mano en la app."; no aparece "Se crean
  también". "Volver a la revisión" vuelve a la lista sin cambios y sin nada guardado;
  "Importar" guarda lo de CA-57.1.
- **CA-57.10** Importando solo "Prestamo MP" (me deben) y la fila 19 como sueldo (todas las
  demás filas destildadas o en "ignorar"): el resultado dice "Se importaron: 1 ítem "me deben"
  y el sueldo (US$ 1.300,00) en Octubre 2026." y "Ver Octubre 2026" muestra la pantalla
  Resumen (no Gastos).
- **CA-57.11** Personas y categorías nuevas solo si se usan: crear la persona "Juan" para
  "Servicios" como "me deben" (CA-53.4) y después volver "Servicios" a gasto fijo: al
  confirmar no existe Juan y el resumen previo no lo menciona. Crear la categoría nueva
  "Importado" y elegirla como categoría por defecto: el resumen previo dice "Se crean también:
  la categoría "Importado"." y, al confirmar, los gastos y el plan quedan en Importado. Si en
  cambio "Importado" se elige solo en "Gym" y después "Gym" se destilda, al confirmar
  "Importado" no existe.
- **CA-57.12** Base sin meses y con la categoría Varios: desde el primer uso, importar
  `planilla-prueba.xlsx` con destino Octubre 2026, sin marcar ninguna fila como sueldo. El
  resumen previo dice "Se va a crear Octubre 2026, sin cotización, y cargar ahí los datos." y
  "Sin sueldo: el sueldo de Octubre 2026 queda en US$ 0,00."; el resultado incluye "Cargá la
  cotización de Octubre 2026 en el Resumen."; "Ver Octubre 2026" muestra la ventana normal
  (con rail y barra superior) con 2026-10 seleccionado, en la pantalla Gastos.
- **CA-57.13** Con cambios en la revisión (por ejemplo, los de CA-57.3), cerrar la ventana de
  la app la cierra sin preguntar. Al volver a abrir la app no existen 2026-11 ni Juan ni
  ningún dato importado, y 2026-10 sigue igual.
- **CA-58.1** Un `.xls`, un `.csv`, un `.txt` renombrado a `.xlsx` y un `.xlsx` cortado
  (dañado): se ve "No se pudo leer el archivo. Solo se aceptan archivos .xlsx de Excel." y no
  cambia nada.
- **CA-58.2** Una hoja vacía: "No se encontraron datos en la hoja Hoja1." y se puede elegir
  otra hoja, otro archivo o cancelar. Una hoja con solo textos (sin números): se muestra la
  lista con el aviso "No se encontraron filas con un texto y un monto." y todas en "Filas
  incompletas".
- **CA-58.3** Un archivo generado por las pruebas con "Luz" en C3 y la fórmula `=100+200` en
  D3 (sin valor guardado, porque nunca se abrió en Excel): arriba de la lista se ve "Hay 1
  fórmulas sin valor calculado (ej. D3)…" y "Luz" queda en "Filas incompletas", sin monto.
- **CA-58.4** El mismo contenido guardado con Excel o LibreOffice (archivo de prueba en
  `tests/`): "Luz" viene con monto 300 y sin aviso.

---

## 8. Fuera de alcance (v1 y v2)

La importación de la planilla de Excel salió de esta lista: es la primera funcionalidad de la
v2 (Módulo K, RF-49 a RF-58). Lo que sigue queda para más adelante o se decidió no hacerlo:

- Cotización automática desde internet.
- Cuotas (planes de cuotas) en dólares. Los gastos fijos mensuales y de pago único en dólares
  **sí** están en la v1 (RF-43 a RF-48).
- Cálculo automático de impuestos o recargos sobre el dólar (dólar tarjeta, percepciones):
  el usuario carga la cotización que corresponda (RN-58).
- Ajuste por inflación en previsiones.
- Sueldo en pesos, para familiares que no cobran en USD (funcionalidad futura). Mientras
  tanto, la importación toma el sueldo siempre en USD (RN-70).
- Deshacer una importación ya confirmada: **no se hace** (decisión del usuario). Los errores
  se corrigen a mano (RN-76).

---

## 9. Orden de construcción

| Paso | Contenido | Requisitos |
|---|---|---|
| 1 | Base de datos + ABM de gastos de un mes | RF-01 (un mes), RF-04, RF-06 a RF-12 (sin CA-08.2/08.3); RN-01 a RN-07, RN-49 a RN-51 |
| 1c | Gastos en dólares (alta, edición, cambio de moneda, lista, formato de cotizaciones) y migración de la base existente con respaldo y versión | RF-43 a RF-46, RF-48; RN-04 (cotizaciones), RN-53 a RN-56, RN-58, RN-59. CA-43.1 a CA-43.4, CA-44.x, CA-45.1 a CA-45.5, CA-45.8, CA-46.x, CA-48.x. Las partes de los CA que dependen de pasos posteriores se verifican en ese paso: pesos a cubrir/ahorro (CA-43.1, 43.2, 45.1) y formato de la cotización del mes y de los cambios (CA-25.4, CA-26.4) en el paso 3; pagos (CA-43.5, 45.4, 45.6) en el paso 2; capacidad (CA-43.7) en el paso 3/4; compartidos (CA-43.6, 45.7) en el paso 5; copia al mes nuevo (RF-47, RN-57, CA-47.1 a CA-47.6) en el paso 4; reparto de partes al copiar (RN-37, CA-47.7, CA-47.8) en el paso 5; previsión con fijos en USD (CA-38.8 a CA-38.11) en el paso 6. |
| 2 | Pagos (tilde y parciales) y pendiente | RF-13 a RF-15; RN-20 a RN-23 |
| 3 | Sueldo, cotización, cambios, ahorro (pantalla resumen) | RF-23 a RF-27, RF-35 a RF-37; RN-12 a RN-19, RN-38 a RN-40 (las cuotas de la capacidad valen 0 hasta el paso 4) |
| 4 | Cuotas e historial de meses | RF-01 a RF-05, RF-16 a RF-22, RF-47 (sin partes compartidas), CA-08.2/08.3; RN-08 a RN-11, RN-24 a RN-31, RN-52, RN-57 |
| 5 | Gastos compartidos y "me deben" | RF-28 a RF-34, RF-47 (partes de fijos en USD compartidos); RN-32 a RN-37 |
| 6 | Previsiones | RF-38, RF-39; RN-41 a RN-45 |
| 7 | Gráficos | RF-40 a RF-42; RN-46 a RN-48 |
| 8 | Importar Excel (v2). Sin cambios en la base (§5.13). Usa lo construido en los pasos 1 a 5 (gastos, pagos, sueldo, meses, planes de cuotas, personas y "me deben"). Se divide en cinco sub-pasos que se prueban por separado: 8a es solo lógica; 8b a 8e son la interfaz y siguen, en el mismo orden, los sub-pasos del Paso 8 de `docs/diseno.md` §6. Los CA que tienen una parte de lógica y una de pantalla se prueban primero en 8a (datos y textos que devuelve la lógica) y después en el sub-paso de interfaz que los muestra. | RF-49 a RF-58; RN-60 a RN-78; CA-49.1 a CA-58.4. |
| 8a | Lógica de la importación, **sin interfaz** (en `app/logica/`, probada con pytest): lectura del `.xlsx` y de sus hojas; detección de filas con su número de fila, columnas de pagado y de cobrado (RN-64) y título de bloque (títulos, filas pegadas y bloques, RN-65); tipos propuestos; la lista de revisión en memoria con sus operaciones (cambiar tipo, tilde, datos, categoría por defecto, mes destino, personas y categorías nuevas, acciones de bloque); notas, avisos y errores por fila con sus textos; "ya existe", "repetida" y posible gasto compartido; textos del pie y del resumen previo; guardado todo o nada (incluido crear el mes destino) y texto del resultado. | RN-60 a RN-78. CA-50.2, CA-51.1 a CA-51.9, CA-52.1 a CA-52.8, CA-53.x, CA-54.x, CA-55.x, CA-56.x, CA-57.1, CA-57.4 a CA-57.11, CA-58.1, CA-58.3, CA-58.4. |
| 8b | Entradas y elegir archivo: línea "¿Tenés una planilla? [Importar Excel]" en el primer uso, pestaña "Importar Excel" de Ajustes, pantalla completa de elegir archivo y hoja, y avisos de archivo. Termina mostrando la cantidad de filas detectadas. | RF-49, RF-50, RF-58. CA-49.1, CA-49.2, CA-50.1, CA-58.1, CA-58.2. |
| 8c | Lista de revisión de solo lectura: bloques, filas, tipos propuestos, notas y avisos, "Filas incompletas", controles generales (mes destino y categoría por defecto), pie con conteo. Tilde, tipo, "Tildar/Destildar todas las filas" y "Cobrado" ya editables. | RF-51, RF-52, RF-54 (sin crear categorías), RF-55, RF-56. CA-51.1, CA-51.2, CA-51.6, CA-51.7, CA-52.1, CA-52.6 a CA-52.8, CA-55.1, CA-55.3, CA-56.x, CA-58.3 (en pantalla). |
| 8d | Edición: diálogo de edición de fila, "Cambiar tipo o categoría de todas...", creación de categorías y personas nuevas, errores por fila y bloqueo de "Confirmar importación". | RF-53, RF-54. CA-53.x, CA-54.x, CA-57.5 a CA-57.8 (en pantalla). |
| 8e | Confirmar y cancelar: resumen previo, guardado todo o nada, resultado y pantalla final (Gastos o Resumen), error al guardar, cancelar con confirmación y cierre de la ventana sin pregunta. | RF-57. CA-55.2, CA-55.4, CA-57.1 a CA-57.4, CA-57.9 a CA-57.13 (en pantalla). |

Cada paso termina cuando pasan los criterios de aceptación de sus RF.

---

## 10. Preguntas abiertas

Sin preguntas abiertas.

- Las cinco preguntas sobre la importación de Excel se respondieron el 2026-10-13 y están
  incorporadas en RN-64, RN-70, RN-72, RN-76, RN-77 y §8.
- Las decisiones del usuario sobre el diseño de la importación (observaciones 21, 22, 26, 29,
  30 y 31 de `docs/diseno.md` §7) están en RF-49, RF-57, RN-72, RN-75, RN-76 y RN-78.
- La pregunta sobre cómo se arman los bloques cuando hay celdas vacías o filas incompletas en
  el medio se respondió el 2026-10-13 (opción "c": un bloque se corta solo en una fila del
  Excel totalmente vacía o en el título siguiente, y un texto sin monto pegado a la fila de
  arriba no abre un bloque nuevo). Está en RN-65 y CA-51.7 y CA-51.8.
- También el 2026-10-13, el usuario confirmó que al sacar una fila de "ignorar" se tilda sola
  aunque esté marcada "ya existe" (RN-68, CA-52.7).
