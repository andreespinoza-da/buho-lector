# Resultados de la simulación iterativa (n=15)

*Borrador de texto corrido para la sección de Resultados/Evaluación del
TFM. Integra las tablas y figuras generadas a partir de
`resultado_n15.json` (ver `resultados_n15_tablas_analisis.md` y
`registro_decisiones_chat3.md` para el detalle técnico completo). Las
referencias a Mansoury et al. (2020) y Naghiaei et al. (2022) siguen el
formato autor-año ya usado en la spec del proyecto; conviene verificar
que las entradas bibliográficas completas de ambos trabajos ya están en
la lista de referencias del TFM, o añadirlas si no lo están — este
documento no inventa los datos de publicación (título, venue, DOI) por
no tenerlos disponibles en los archivos del proyecto.*

---

Siguiendo el protocolo de simulación iterativa descrito en la sección
[X.X] (T=20 rondas, k=10 recomendaciones por ronda, cohorte de 400
estudiantes sintéticos con incorporación escalonada, catálogo de 1.500
libros), se evaluaron los tres sistemas de recomendación del proyecto —
el baseline de popularidad (B1), el baseline de SVD sin bandit (B2) y el
sistema completo de dos fases, bandit contextual en frío y SVD en
caliente (en adelante, Sistema completo)— bajo el umbral de transición
n=15 interacciones, fijado en la fase de calibración previa (sección
[X.X], barrido de n).

## Resultados globales

La Tabla [X] resume la evolución de las tres métricas de evaluación
—precisión@10, NDCG@10 y cobertura acumulada del catálogo— a lo largo de
las 20 rondas de simulación, para cada uno de los tres sistemas (tabla
completa por ronda en `resultados_n15_tablas_analisis.md`, sección 1).

| Sistema | Precisión@10 (ronda 20) | NDCG@10 (ronda 20) | Cobertura (ronda 20) |
|---|---|---|---|
| B1 — Popularidad | 0.107 | 0.357 | 0.030 |
| B2 — SVD puro | 0.165 | 0.453 | 0.927 |
| Sistema completo | 0.146 | 0.415 | 0.112 |

El baseline de popularidad (B1) mantiene un desempeño bajo y estable
durante toda la simulación (precisión@10 entre 0.10 y 0.13), consistente
con su naturaleza no personalizada: al no usar información del estudiante
individual, su techo de precisión está limitado por la popularidad
agregada de la cohorte completa. Su cobertura del catálogo es,
además, la más baja de los tres sistemas (3.0% al final de la
simulación), ya que por construcción concentra las recomendaciones en
un conjunto reducido de libros con más aceptaciones acumuladas.

El baseline de SVD sin bandit (B2) es el único de los tres sistemas que
muestra una mejora sostenida a lo largo de la simulación: la
precisión@10 pasa de 0.121 (ronda 1) a 0.165 (ronda 20), y el NDCG@10 de
0.389 a 0.453. Esta mejora progresiva es consistente con un modelo que
acumula, ronda tras ronda, más datos de entrenamiento sobre una base de
candidatos amplia: su cobertura ya alcanza 89.3% del catálogo en la
primera ronda —por el mecanismo de cold-start aleatorio descrito en la
sección [X.X]— y crece hasta 92.7% al final.

El Sistema completo presenta el patrón más complejo de los tres y es el
que requiere una explicación más detallada (Figura 1, panel izquierdo y
derecho). Durante las dos primeras rondas, mientras la mayoría de la
cohorte permanece en fase fría (bandit contextual), el sistema alcanza
el desempeño más alto de toda la simulación: precisión@10 = 0.332 y
NDCG@10 = 0.623, muy por encima de B1 y B2 en ese mismo punto temporal.
A partir de la ronda 3, sin embargo, el desempeño cae de forma abrupta a
precisión@10 = 0.107 — por debajo incluso de B1 — y se mantiene en un
rango de 0.11 a 0.18 durante el resto de la simulación, sin recuperar el
nivel alcanzado en las dos primeras rondas. Este patrón se examina en
detalle en la subsección siguiente.

## La fase fría del Sistema completo: por qué dura solo dos rondas

El comportamiento descrito arriba se explica por la interacción entre
dos parámetros del diseño experimental, no por un fallo de
implementación. El umbral n=15 cuenta toda interacción registrada
(aceptaciones y rechazos), y con k=10 recomendaciones fijas por ronda,
el contador de interacciones de cualquier estudiante avanza en bloques
de 10 por ronda. Esto implica que:

- al finalizar la ronda 1, el contador de cada estudiante activo se
  encuentra en 10 (todavía por debajo de n=15, fase fría);
- durante la ronda 2, el contador cruza el umbral de 15 a mitad de las
  10 interacciones de esa ronda;
- a partir de la ronda 3, el contador de todos los estudiantes ya
  incorporados se encuentra en 20 (≥ n=15), por lo que el sistema opera
  exclusivamente en fase cálida (SVD) durante el resto de la simulación.

En la práctica, esto significa que la fase fría —el componente del
diseño pensado para mitigar el sesgo de popularidad mediante exploración
dirigida— solo está activa durante 2 de las 20 rondas (10% del tiempo de
simulación) para n=15 con k=10 fijo. Esta misma causa estructural ya
había sido identificada en el barrido del umbral n (sección [X.X]),
donde se observó que n=15 y n=20 transicionan en el mismo punto de la
simulación: con k=10 fijo, cualquier valor de n entre 11 y 20 produce
exactamente dos rondas de fase fría. Los resultados de la presente
sección muestran el efecto completo de esa restricción sobre las
métricas de desempeño, no solo sobre el punto de transición.

## Cobertura: el mecanismo del deterioro posterior a la fase fría

La Figura 2 muestra la cobertura acumulada del catálogo por ronda para
los tres sistemas. B2 mantiene una cobertura cercana al 90% desde la
primera ronda y continúa creciendo hasta 92.7%. El Sistema completo, en
contraste, alcanza apenas 9.9% de cobertura al finalizar su breve fase
fría (ronda 2) y permanece esencialmente congelado en ese nivel durante
trece rondas consecutivas (rondas 2 a 14), antes de crecer muy
lentamente hasta 11.2% al final de la simulación —impulsado
exclusivamente por los estudiantes que se incorporan tarde a la
cohorte y atraviesan, cada uno, su propia fase fría breve.

Dado que el componente SVD es idéntico en B2 y en la fase cálida del
Sistema completo (mismos hiperparámetros calibrados, ver corrección
documentada en chat 2 del registro de decisiones), la diferencia de
desempeño entre ambos sistemas a partir de la ronda 3 no puede atribuirse
al modelo de factorización en sí, sino a la diversidad del historial
sobre el que se reentrena en cada ronda. El Sistema completo reentrena su
SVD sobre un historial que cubrió, como máximo, alrededor del 10% del
catálogo, mientras que B2 lo hace sobre un historial que cubrió cerca
del 90%. Con menos diversidad de libros vistos durante el entrenamiento,
las recomendaciones de la fase cálida son sistemáticamente menos
precisas — y este efecto domina el resultado final porque el 90% de la
simulación ocurre en esa fase.

Este mecanismo es consistente con el fenómeno de sesgo de
popularidad/diversidad descrito en la literatura (Mansoury et al., 2020):
una vez que el sistema entra en un régimen de explotación pura (aquí, la
fase cálida basada en SVD, combinada con la exclusión de libros ya
aceptados), tiende a reforzar la exposición de un conjunto reducido de
ítems, limitando la diversidad de las recomendaciones futuras y, con
ello, la calidad del propio modelo que se reentrena sobre esa
exposición limitada.

## Desagregación por arquetipo: ¿se reproduce el sesgo de popularidad?

La sección 5.4 de la especificación técnica plantea directamente la
pregunta que motiva este análisis: ¿el motor sirve igual de bien a
lectores de nicho que a lectores mainstream, o reproduce el sesgo de
popularidad documentado en la literatura (Naghiaei et al., 2022)? La
Tabla [X] y las Figuras 3 y 4 permiten responderla con matices.

| Sistema | Arquetipo | Precisión@10 (ronda 20) | Cobertura (ronda 20) |
|---|---|---|---|
| B1 | nicho | 0.084 | 0.030 |
| B1 | mainstream | 0.120 | 0.029 |
| B1 | nuevo | 0.113 | 0.025 |
| B2 | nicho | 0.177 | 0.679 |
| B2 | mainstream | 0.153 | 0.778 |
| B2 | nuevo | 0.180 | 0.459 |
| Sistema completo | nicho | 0.143 | 0.112 |
| Sistema completo | mainstream | 0.143 | 0.100 |
| Sistema completo | nuevo | 0.167 | 0.104 |

En B1, el patrón es el esperado según la literatura del estado del arte:
los lectores de nicho obtienen la precisión más baja de los tres
arquetipos (0.084, frente a 0.120 de mainstream), un caso directo de
sesgo de popularidad en un sistema sin personalización.

En el Sistema completo, el patrón es más matizado y constituye uno de
los hallazgos más relevantes de esta evaluación. Durante la fase fría
(ronda 1), el lector de nicho obtiene una precisión@10 de 0.500, frente
a 0.222 del lector mainstream — el bandit contextual identifica con
mayor rapidez las preferencias de los lectores de nicho, porque su
vector de afinidad (generado con un parámetro de concentración de
Dirichlet bajo, α=0.3) produce una señal de contexto más nítida que la
de un lector mainstream (α=3.0, afinidad distribuida entre más géneros).
Esta ventaja inicial, sin embargo, se pierde casi por completo al entrar
en fase cálida: para la ronda 3, la precisión del lector de nicho cae a
0.082, la más baja de los tres arquetipos en ese momento, y no recupera
el nivel inicial durante el resto de la simulación.

El resultado más significativo de esta desagregación es que, en estado
estacionario (ronda 20), **el baseline B2 supera al Sistema completo en
los tres arquetipos**, con la brecha más amplia precisamente en el
lector de nicho (0.177 frente a 0.143, una diferencia relativa del 24%,
frente a un 7% en mainstream). El mecanismo causal es el descrito en la
subsección anterior: la cobertura colapsada del Sistema completo afecta
de forma desproporcionada a los lectores de nicho, cuyos libros
relevantes constituyen, por definición, una porción más pequeña y menos
"popular" del catálogo — exactamente el tipo de ítem que un modelo SVD
entrenado sobre un historial poco diverso tiene menor probabilidad de
haber observado.

## Discusión

Estos resultados muestran que el mecanismo de mitigación del sesgo de
popularidad incorporado en el diseño del Sistema completo —exploración
dirigida vía bandit contextual durante la fase fría— es real y
demostrablemente efectivo mientras está activo: durante sus dos
primeras rondas de operación, el sistema no solo supera a ambos
baselines en las métricas globales, sino que beneficia en mayor medida
al arquetipo que la literatura identifica como más vulnerable al sesgo
de popularidad (Naghiaei et al., 2022). Sin embargo, la duración de esa
fase está determinada por la combinación de dos parámetros —el umbral n
y el tamaño de lote k— de forma que, para los valores fijados en este
proyecto (n=15, k=10), la fase fría ocupa solo el 10% de la simulación.
El resultado neto es que, en estado estacionario, el Sistema completo no
solo no logra preservar la ventaja observada en la fase fría, sino que
termina por debajo del baseline más simple (B2) en los tres arquetipos
evaluados.

Este hallazgo no debe interpretarse como una falla del componente
bandit ni del componente SVD por separado —ambos están validados de
forma independiente (registro de decisiones, chat 1 y chat 2)— sino como
evidencia de que la arquitectura de dos fases, tal como está
parametrizada actualmente, traslada el problema de sesgo de popularidad
de la fase fría a la fase cálida en lugar de resolverlo: la propia
estrechez de exploración que define a la fase cálida (agravada por la
exclusión de libros ya aceptados y la representación one-hot de género
ya documentada en evaluaciones previas) limita la diversidad del
historial sobre el que se reentrena el SVD, y ese efecto golpea con
mayor severidad a los lectores de nicho — el grupo que, paradójicamente,
el diseño del sistema buscaba proteger mejor.

## Limitaciones de esta evaluación

- Los resultados corresponden a una única corrida con semilla fija
  (semilla=42) sobre una cohorte y catálogo sintéticos; no se evaluó
  variabilidad entre semillas para este umbral n=15 específico.
- El hallazgo de la fase fría de 2 rondas es una consecuencia
  determinística de n=15 combinado con k=10 fijo, no una observación
  empírica sujeta a variabilidad — pero su magnitud de impacto sobre las
  métricas finales sí depende de la dinámica estocástica de la
  simulación (función de aceptación, orden de incorporación de
  estudiantes) y podría variar en corridas adicionales.
- No se exploró en esta evaluación si valores de k distintos a 10
  (manteniendo n=15) mitigarían el problema descrito, ya que ambos
  parámetros (n=15, k=10) están fijados como decisiones cerradas de
  fases anteriores del proyecto.

---

*Pendiente: revisar numeración de secciones/tablas/figuras ([X.X], [X])
contra la numeración real del TFM una vez disponible
`checklist_maestro_entrega3.md` y/o `busho_lector_documentacion_v3.md`.
Verificar también que las entradas bibliográficas completas de Mansoury
et al. (2020) y Naghiaei et al. (2022) estén en la lista de referencias
del documento final.*
