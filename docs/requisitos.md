# Requisitos – App de gastos personales (v1)

> Documento de requisitos. Sale de la entrevista (/grill-me) confirmada por el usuario,
> de sus respuestas a dos rondas de preguntas abiertas, de la entrevista sobre gastos en
> dólares (y sus preguntas abiertas) y de la planilla de referencia
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

---

## 3. Requisitos funcionales

Numeración: RF-xx. Los criterios de aceptación de cada RF están en la sección 7 con el
número CA-xx.y, donde xx es el número del RF.

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
- **RN-29 – Validaciones del plan.** Cantidad de cuotas: entero ≥ 1. Monto de cuota > 0, en
  ARS (las cuotas en dólares están fuera de la v1). La primera cuota puede ser un mes pasado
  (deudas ya empezadas, ej. Avant en 3/3).
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

---

## 8. Fuera de la v1

- Importar la planilla de Excel.
- Cotización automática desde internet.
- Cuotas (planes de cuotas) en dólares. Los gastos fijos mensuales y de pago único en dólares
  **sí** están en la v1 (RF-43 a RF-48).
- Cálculo automático de impuestos o recargos sobre el dólar (dólar tarjeta, percepciones):
  el usuario carga la cotización que corresponda (RN-58).
- Ajuste por inflación en previsiones.

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

Cada paso termina cuando pasan los criterios de aceptación de sus RF.

---

## 10. Preguntas abiertas

Sin preguntas abiertas.
