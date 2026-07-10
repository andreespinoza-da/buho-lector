# Especificación técnica: generador de perfiles sintéticos y protocolo de simulación
## Búho Lector — Entrega 3

> **Estado:** especificación de diseño, previa a implementación. Este documento define qué se va a construir y por qué, antes de escribir código. Una vez aprobado, se traduce a un generador de datos sintéticos y un harness de simulación.

---

## 1. Alcance de este documento

Esta especificación cubre dos componentes que se diseñan juntos porque se alimentan mutuamente:

1. **El generador de perfiles sintéticos** — estudiantes simulados con preferencias y comportamiento de aceptación/rechazo.
2. **El protocolo de simulación** — cómo esos perfiles interactúan con el motor a lo largo de múltiples rondas, qué se mide, y qué comparaciones se reportan.

No cubre la implementación del motor (SVD + LinUCB) en sí, que es un componente separado consumido por este harness.

---

## 2. Catálogo de libros

### 2.1. Decisión de tamaño

Se amplía el catálogo de 160 libros (Iteración 1) a un rango de **1000–2000 libros**, para dar al motor SVD suficiente densidad de catálogo y hacer más realista el problema de cobertura (O6) — con 160 libros, un sistema mediocre podría alcanzar cobertura alta por simple casualidad; con 1000+, la cobertura mide algo real.

### 2.2. Fuente de datos — arquitectura de dos vías de ingestión

Open Library **prohíbe explícitamente el harvesting masivo vía su API en tiempo real** ("Harvest data in bulk" está en su lista de "Please Do Not", developers/api). Esto se resuelve distinguiendo dos contextos de uso completamente distintos, que conviene documentar como una arquitectura deliberada de dos vías de ingestión — no como dos soluciones ad hoc:

| Contexto | Volumen | Mecanismo |
|---|---|---|
| **Evaluación/simulación del TFM** (este protocolo) | 1000–2000 libros, una sola vez | Data dump mensual descargado y filtrado localmente |
| **Catálogo inicial de una institución real** (caso de uso de producción) | Variable — puede ser pequeño o grande según la institución | Si es grande: misma vía del dump, filtrado y carga en bloque. Si es pequeño: API en tiempo real es aceptable (es el "low-volume, high-value use" que Open Library prioriza) |
| **Operación normal post-carga inicial** | Libro por libro o en lotes pequeños, cuando un administrador añade contenido | API en tiempo real (`search.json` / `/api/books`) — uso normal y documentado, sin restricción |

Esto es coherente con el patrón de uso real de Búho Lector: el catálogo de una institución se carga una vez de forma masiva al inicio, y crece después por adiciones puntuales del administrador. La carga masiva nunca vuelve a ocurrir vía API en tiempo real — ni en la simulación del TFM ni en producción — evitando exactamente el patrón que Open Library pide no hacer.

**El mecanismo del data dump:** Open Library publica mensualmente archivos completos de su catálogo para descarga directa (formato TSV, cada línea es un registro con su JSON completo). El relevante para Búho Lector es el **works dump** (~2.9 GB comprimido, `ol_dump_works_latest.txt.gz`), que incluye título, autor y el campo `subjects` necesario para el mapeo de géneros. No se necesitan los dumps de ediciones, autores ni el dump completo.

**Flujo de obtención para la simulación:**
1. Descargar `ol_dump_works_latest.txt.gz` una sola vez.
2. Filtrar localmente (sin más llamadas a la API) por idioma español y/o por subjects que sugieran audiencia infantil/juvenil (ej. "juvenile fiction", "children's literature") — esto también adelanta parte del mapeo de géneros, ya que muchos subjects incluyen marcador de audiencia.
3. Tomar una muestra aleatoria o estratificada de 1000–2000 libros del subconjunto filtrado.
4. Aplicar el pipeline de normalización de géneros (sección 2.3) sobre esa muestra reducida.

**Opción complementaria a explorar:** la colección curada **K-12 Student Library** (`openlibrary.org/k-12`) podría reducir el trabajo de filtrado por audiencia — **pendiente de verificar tamaño real y cobertura de géneros** antes de decidir si sustituye o solo complementa el filtrado del dump.

**Nota para el TFM:** esta arquitectura de dos vías (carga masiva única vía dump + carga incremental vía API) es un punto a documentar explícitamente en la sección 6 (Código y Datos) — muestra una decisión de ingeniería de datos consciente de las restricciones de uso de la fuente externa, no solo el uso de una API "porque está disponible".

### 2.2.1. Corrección metodológica: verificación real de idioma (no heurística)

Un primer intento de filtrar libros en español usando el campo `languages` del **works dump** confirmó lo anticipado: ese campo casi nunca está poblado a nivel de work (0 de 31,587 works juveniles en una muestra de 2,000,000 líneas escaneadas tenían `languages` con código español). Esto **no significa ausencia de libros en español** — significa que el dato vive en otro lugar de la estructura de datos de Open Library.

**Estructura real (confirmada en la documentación de la API):** cada **edition** (no work) tiene su propio campo `languages`, y referencia a su work mediante un campo `works: [{"key": "/works/OL...W"}]`. Es decir, el idioma es una propiedad de la edición física/digital específica, no de la obra abstracta — lo cual tiene sentido, ya que una misma obra (ej. "Crimen y Castigo") puede tener cientos de ediciones en idiomas distintos.

**Solución implementada:** se descartó la heurística inicial (buscar palabras clave en español dentro de subjects, como "spanish language materials" o "literatura juvenil") en favor de un **cruce real de datos en dos pasadas**:

1. **Pasada 1** sobre el works dump: filtra works juveniles por subjects, guarda su `key` y subjects en memoria.
2. **Pasada 2** sobre el editions dump: para cada edition, revisa su campo `works[].key`; si coincide con un work ya filtrado en la Pasada 1, extrae el código de idioma real de esa edición y lo asocia al work correspondiente.

Esto da el idioma real verificado por edición, no una proxy basada en texto libre. El script que implementa este cruce (`explorar_dump_openlibrary.py`) ya está construido y validado contra datos sintéticos que imitan el formato exacto de ambos dumps (incluyendo casos de prueba para libros con múltiples ediciones en idiomas distintos, libros sin coincidencia, y libros sin subjects) — pendiente de ejecutar contra el editions dump real (~9 GB comprimido, descarga en curso).

### 2.3. El problema de los géneros — resuelto con datos reales del dump

El campo `subjects` de Open Library es **texto libre generado por la comunidad**, no una taxonomía controlada. Un libro puede tener un subject como `"Venice (Italy) -- Description and travel -- Juvenile literature"`. Esto significa que no se podía asumir que los libros llegarían con géneros limpios.

**Hallazgo tras explorar 2,000,000 líneas reales del works dump (31,587 works juveniles encontrados, 25,409 subjects distintos):** los subjects de mayor frecuencia mezclan **tres dimensiones distintas** que deben separarse antes de construir cualquier mapeo de géneros:

| Dimensión | Ejemplos reales encontrados | ¿Sirve como género objetivo? |
|---|---|---|
| **Audiencia / formato** | juvenile literature (14,231), juvenile fiction (8,596), children's fiction (4,184), picture books, board books, readers | No — describe a quién va dirigido o el formato físico, no el contenido narrativo |
| **Género narrativo** | fiction (5,327), fantasy fiction (313), mystery and detective stories, adventure stories, fairy tales, science fiction (208), humorous stories, poetry (170) | **Sí — esta es la dimensión que define el vector de afinidad del estudiante** |
| **Tema / contenido transversal** | animals (1,151), history (2,049), biography (1,743), friendship (759), dogs, family life, schools | Parcialmente — history y biography tienen suficiente volumen e identidad propia para tratarse como géneros; el resto son temas que cruzan cualquier género y se descartan como dimensión de clasificación |

Intentar mapear el campo `subjects` completo sin esta separación habría producido géneros contaminados — por ejemplo, tratar "fiction" y "picture books" como si fueran categorías del mismo tipo.

### 2.3.1. Géneros objetivo — confirmados con datos reales

Con base en las frecuencias reales del dump (no estimaciones), se confirman **8 géneros objetivo**, cada uno con volumen suficiente para sostener un catálogo de 1000–2000 libros sin categorías vacías:

| Género objetivo | Subjects reales que mapean | Volumen real observado |
|---|---|---|
| Aventura | adventure and adventurers (fiction), adventure stories | 250–349 menciones |
| Fantasía | fantasy fiction, fantasy, fairy tales, magic | 247–313 menciones |
| Misterio | mystery and detective stories, detective and mystery stories | 181–343 menciones |
| Ciencia ficción | science fiction | 208 menciones |
| Humor | humorous stories | 333 menciones |
| Historia | history, history and criticism, world war 1939-1945 | 169–2,049 menciones |
| Biografía | biography | 1,743 menciones |
| Poesía/Folclore | poetry, stories in rhyme, folklore, short stories | 170–389 menciones |

Esto **confirma la decisión pendiente #2** de la sección 8 (ver más abajo): se mantienen 8 géneros, no 6 — los datos reales sostienen las 8 categorías con volumen razonable.

**Pipeline de normalización aplicado:**
1. Géneros objetivo fijados según la tabla anterior (ya no son provisionales).
2. Subjects de audiencia/formato y de tema transversal se descartan como dimensión de clasificación de género (aunque algunos, como historia/biografía, se promueven a género propio por su volumen y especificidad).
3. Libros cuyo único subject mapeable cae en "tema transversal" sin ningún género narrativo asociado quedan pendientes de decisión (ver punto #5 de la sección 8 — aún abierto).

Este paso debe documentarse explícitamente en la sección de Código y Datos del TFM (ya marcada completa, pero requiere actualización) — es exactamente el tipo de decisión metodológica que un tribunal de análisis de datos espera ver justificada, no oculta.

---

## 3. Generador de perfiles sintéticos (estudiantes)

### 3.1. Géneros objetivo — confirmados (ver sección 2.3.1 para el detalle de mapeo)

```
aventura, fantasia, misterio, ciencia_ficcion, humor, historia, biografia, poesia_folclore
```

8 géneros, confirmados con datos reales del dump (sección 2.3.1) — ya no son provisionales.

### 3.2. Tamaño de la muestra

**N = 300–500 estudiantes sintéticos**, justificado por:
- Suficiente para que la fase SVD tenga densidad razonable de interacciones por género una vez se acumulen rondas.
- Suficiente granularidad para reportar resultados desagregados por arquetipo (3 arquetipos × ~100-170 estudiantes cada uno es estadísticamente razonable).
- No tan grande que la simulación se vuelva computacionalmente pesada para el plazo de Entrega 3.

### 3.3. Atributos demográficos

| Atributo | Distribución |
|---|---|
| `edad` | Uniforme discreta en [8, 17] |
| `grado_escolar` | Determinístico a partir de `edad` (mapeo fijo edad→grado) |
| `pais` | Categórica ponderada sobre 3–4 países latinoamericanos (pesos a definir, ej. reflejando proporciones reales de población escolar si se dispone del dato, o uniforme si no) |

### 3.4. Vector de preferencia — diseño híbrido (arquetipos + Dirichlet)

Cada estudiante recibe un vector de afinidad sobre los géneros objetivo, generado por una **distribución de Dirichlet** parametrizada por un valor α que depende del arquetipo asignado:

| Arquetipo | % de la muestra | α | Interpretación |
|---|---|---|---|
| **Nicho** | ~35% | 0.3 | Afinidad concentrada en 1–2 géneros; el resto casi nulo |
| **Mainstream** | ~50% | 3.0 | Afinidad moderadamente repartida, sin extremos marcados |
| **Nuevo / cold start** | ~15% | variable (cualquiera de los anteriores) | La variable definitoria no es la preferencia sino el **historial inicial = 0 interacciones**; se usa para aislar el comportamiento del motor en frío independientemente del tipo de gusto |

**Nota de diseño:** el arquetipo "nuevo" no es mutuamente excluyente con los otros dos en términos de preferencia — es una dimensión distinta (historial inicial) que se cruza con nicho/mainstream. En la práctica, los perfiles "nuevos" pueden generarse con α de nicho o mainstream indistintamente, y lo que se mide es el comportamiento del motor durante sus primeras interacciones, sin importar el tipo de gusto subyacente.

```python
# Pseudocódigo del generador de un perfil
def generar_perfil(generos, arquetipo):
    alpha = ALPHA_POR_ARQUETIPO[arquetipo]  # 0.3 nicho, 3.0 mainstream
    vector_afinidad = np.random.dirichlet([alpha] * len(generos))
    return dict(zip(generos, vector_afinidad))
```

### 3.5. Función de aceptación/rechazo (cómo "lee" el estudiante sintético)

Dado un libro recomendado con género(s) g, la probabilidad de aceptación es:

```
P(aceptar) = vector_afinidad[g] + ruido_uniforme(-0.05, +0.05), recortado a [0, 1]
resultado = Bernoulli(P(aceptar))
```

Si el resultado es aceptación → estado = "terminado" (feedback = 1).
Si el resultado es rechazo → estado = "abandonado" (feedback = −1).

El término de ruido evita que el SVD aprenda un patrón perfectamente determinista, que sería artificial y produciría métricas de precisión irrealistamente altas.

**Libros con múltiples géneros:** si un libro tiene más de un género asignado, se usa el promedio de las afinidades correspondientes, o el máximo (decisión a confirmar — el promedio es más conservador y se recomienda como default).

---

## 4. Baselines

Conforme a la retroalimentación del director [F2], se comparan tres sistemas:

| Sistema | Descripción |
|---|---|
| **B1 — Popularidad** | Recomienda los k=10 libros con más interacciones acumuladas en el catálogo, igual para todos los estudiantes, sin personalización |
| **B2 — SVD sin bandit (cold start ingenuo)** | SVD entrenado únicamente sobre el historial disponible; en ausencia de historial (cold start), usa imputación simple (valor medio global o selección aleatoria) en lugar de exploración dirigida |
| **Sistema completo (Búho Lector)** | LinUCB en fase fría (< n interacciones) → SVD en fase cálida (≥ n interacciones) |

Esto aísla específicamente el efecto del componente bandit: la comparación **Sistema completo vs. B2** mide qué gana el motor por tener LinUCB en lugar de un cold start ingenuo; la comparación **Sistema completo vs. B1** mide qué gana cualquier personalización frente a no personalizar en absoluto.

---

## 5. Protocolo de simulación iterativa

### 5.1. Estructura general

Siguiendo la metodología de Mansoury et al. (2020) de simulación de ciclos de retroalimentación:

```
Para cada ronda t = 1 … T:
    Para cada estudiante sintético u:
        recomendaciones = motor.generar(u, k=10)
        Para cada libro i en recomendaciones:
            resultado = funcion_aceptacion(u, i)
            actualizar_historial(u, i, resultado)
    recalcular_metricas(t)
    motor.reentrenar(historial_actualizado)
```

### 5.2. Número de rondas

**T = 20 rondas.**

Justificación: con 20 rondas y k=10 recomendaciones por ronda, un estudiante puede acumular hasta 200 interacciones potenciales — más que suficiente para cruzar cualquier umbral n razonable (n se determina empíricamente, ver sección 6) y dejar rondas de margen en ambos lados de la transición para poder comparar fases con suficientes puntos de datos.

### 5.3. Métricas por ronda

Calculadas en cada ronda t, no solo al final, para poder graficar curvas de convergencia:

- **Precisión@10** — fracción de las 10 recomendaciones aceptadas
- **NDCG@10** — precisión ponderada por posición
- **Cobertura del catálogo** — % de libros distintos recomendados a través de todos los estudiantes hasta la ronda t

Estas métricas se calculan para los tres sistemas (B1, B2, Sistema completo) en cada ronda, permitiendo graficar tres curvas comparables.

### 5.4. Desagregación por arquetipo

Las mismas métricas se calculan también separadas por arquetipo (nicho / mainstream / nuevo), lo cual permite responder directamente la pregunta que motiva la sección de sesgo de popularidad del estado del arte: **¿el motor sirve igual de bien a lectores de nicho que a lectores mainstream, o reproduce el sesgo documentado en la literatura (Naghiaei et al., 2022)?**

---

## 6. Determinación experimental del umbral n

Conforme a la decisión de hacer n un hiperparámetro explorado experimentalmente (no fijo):

**Barrido de valores:** n ∈ {5, 10, 15, 20}

Para cada valor de n, se ejecuta el protocolo completo (sección 5) y se mide:
- Precisión@10 de la fase bandit en las rondas inmediatamente anteriores a la transición
- Precisión@10 de la fase SVD en las rondas inmediatamente posteriores a la transición
- El punto en que la curva de Precisión@10 de SVD supera de forma sostenida (no solo puntual) a la del bandit

**Criterio de selección del n óptimo:** el valor de n que minimiza el número de interacciones necesarias para que SVD supere consistentemente al bandit, sin sacrificar la calidad de las recomendaciones durante la fase fría (es decir, no se quiere un n tan bajo que SVD entre en juego con datos insuficientes y produzca recomendaciones erráticas).

Este barrido en sí mismo es un resultado reportable en la sección de evaluación — no es solo un paso de calibración interna, sino evidencia de rigor metodológico que responde directamente a [F2].

---

## 7. Qué resultados se reportan (conectando con la retroalimentación del director)

| Pregunta del director | Cómo se responde con este protocolo |
|---|---|
| ¿Cuántos perfiles sintéticos, qué variables, cómo se construyen? | Sección 3 — 300-500 perfiles, 3 arquetipos vía Dirichlet, variables demográficas explícitas |
| ¿Cuántas rondas de simulación? | Sección 5.2 — 20 rondas, justificado |
| ¿Contra qué se compara el motor? | Sección 4 — dos baselines explícitos (popularidad, SVD sin bandit) |
| ¿Tablas de métricas reales? | Sección 5.3/5.4 — Precisión@10, NDCG@10, cobertura, por ronda y por arquetipo, para los 3 sistemas |
| ¿Análisis de errores? | Habilitado por la desagregación por arquetipo (sección 5.4) — permite identificar para qué perfiles el motor falla más, y por qué (conectando con sesgo de popularidad del estado del arte) |

---

## 8. Decisiones pendientes de confirmar antes de implementar

**Resueltas con datos reales:**

1. ~~Número final de géneros~~ — **Resuelto: 8 géneros** (sección 2.3.1), confirmado con frecuencias reales del dump.
2. ~~Cómo verificar idioma español~~ — **Resuelto: cruce real vía editions dump**, no heurística sobre subjects (sección 2.2.1). Script construido y validado; pendiente de ejecutar contra el archivo real.

**Aún abiertas:**

3. **Tamaño final del catálogo** (1000 vs. 1500 vs. 2000) — depende de cuántos works en español resulten del cruce con editions.
4. **Pesos de distribución de país** — uniforme vs. ponderado por datos reales de población escolar latinoamericana, si están disponibles.
5. **Tratamiento de libros con múltiples géneros** — promedio vs. máximo de afinidad (sección 3.5).
6. **Tratamiento de libros sin género narrativo mapeable** (solo audiencia/formato o tema transversal sin género claro) — exclusión vs. categoría "general" (sección 2.3.1).
7. **K-12 Student Library como fuente única vs. complementaria** — aún no explorada en detalle; con el cruce de editions ya resolviendo el problema de idioma, su relevancia como fuente puede ser menor de lo previsto.

---

> **Estado actual:** el works dump fue explorado (2,000,000 líneas escaneadas, 31,587 works juveniles encontrados) y permitió confirmar los 8 géneros objetivo con datos reales. El editions dump (~9 GB) está en descarga para resolver el cruce de idioma real — la descarga se interrumpió una vez y se reanudó. El script de exploración de dos pasadas (works + editions) ya está construido y validado contra datos sintéticos; queda pendiente correrlo contra el archivo real de editions una vez termine de descargar, para resolver los puntos 3 y 7 de esta lista.
