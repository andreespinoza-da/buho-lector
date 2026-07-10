"""
motor_recomendacion.py

Motor de recomendación de Búho Lector (sección 4 del arranque del chat;
la spec deliberadamente NO especifica la implementación interna -- ver
spec_perfiles_sinteticos_simulacion.md línea 15: "No cubre la
implementación del motor (SVD + LinUCB) en sí". Las decisiones de diseño
de este archivo están documentadas inline y en registro_decisiones_chat1.md.

Componentes:
    - MotorSVD: wrapper sobre `surprise.SVD`, entrenado sobre el historial
      acumulado (estudiante, libro, resultado_binario).
    - LinUCB: bandit contextual compartido (un solo modelo, no uno por
      estudiante -- el contexto ya codifica al estudiante, ver más abajo).
    - BaselinePopularidad (B1): ranking global por aceptaciones acumuladas.
    - BaselineSVDIngenuo (B2): SVD puro, con fallback aleatorio en frío.
    - SistemaCompleto: LinUCB en fase fría (< n interacciones) -> SVD en
      fase cálida (>= n interacciones), según sección 4 de la spec.

DECISIONES DE DISEÑO (no especificadas por la spec, documentadas aquí y en
el registro de decisiones):

1. Codificación de aceptación/rechazo como rating para SVD: 1.0 si
   aceptado, 0.0 si rechazado (escala explícita [0,1], no implícita
   solo-positivos) -- el rechazo SÍ es información y se usa.

2. Contexto de LinUCB: producto elemento-a-elemento entre el vector de
   afinidad del estudiante (9 dims: 8 géneros + "general") y el vector de
   género del libro (mismo espacio, ver normalizar_generos.py /
   generar_perfiles.py). Esto permite un ÚNICO modelo LinUCB compartido
   entre todos los estudiantes -- el contexto ya es específico al par
   (estudiante, libro), evitando el cold-start-del-cold-start de tener un
   bandit separado por estudiante.

3. Libros ya ACEPTADOS por un estudiante se excluyen de futuras
   recomendaciones para ese estudiante (en los 3 sistemas). Libros
   previamente RECHAZADOS pueden volver a recomendarse (se interpreta el
   rechazo como ruido/contexto momentáneo, no como exclusión permanente).

4. El umbral n cuenta TODAS las interacciones logueadas (aceptadas +
   rechazadas), no solo las aceptadas -- "interacciones" en la spec se
   lee como exposición+respuesta, no como éxito.

5. B2 (SVD sin bandit, cold start ingenuo): cuando el estudiante tiene
   cero ratings en el modelo SVD entrenado, se usa SELECCIÓN ALEATORIA
   (no imputación de valor medio global) -- la spec ofrece ambas opciones
   ("valor medio global o selección aleatoria"); se elige aleatoria para
   maximizar el contraste con la exploración dirigida de LinUCB. Si se
   usara valor medio global, B2 en frío colapsaría a recomendar lo mismo
   que B1 (popularidad), diluyendo la comparación que la sección 4 de la
   spec quiere aislar.
"""

import random
from collections import Counter, defaultdict

import numpy as np
from surprise import Dataset, Reader, SVD
from surprise.prediction_algorithms.predictions import PredictionImpossible

GENEROS_Y_GENERAL = [
    "aventura", "fantasia", "misterio", "ciencia_ficcion",
    "humor", "historia", "biografia", "poesia_folclore", "general",
]


# ---------------------------------------------------------------------------
# Utilidad de contexto compartida
# ---------------------------------------------------------------------------

def construir_contexto(vector_estudiante, vector_libro, generos=GENEROS_Y_GENERAL):
    """
    Producto elemento-a-elemento entre afinidad del estudiante y vector de
    género del libro. Vector denso de longitud len(generos) (9).
    """
    return np.array(
        [vector_estudiante.get(g, 0.0) * vector_libro.get(g, 0.0) for g in generos],
        dtype=float,
    )


# ---------------------------------------------------------------------------
# MotorSVD
# ---------------------------------------------------------------------------

class MotorSVD:
    """
    Wrapper sobre surprise.SVD. Se reentrena desde cero sobre todo el
    historial acumulado en cada llamada a entrenar() -- consistente con
    el pseudocódigo de la spec (sección 5.1: "motor.reentrenar(historial_actualizado)").

    NOTA DE CALIBRACIÓN (encontrada al validar este wrapper, no estaba en
    la spec): los hiperparámetros por defecto de surprise.SVD
    (lr_all=0.005, n_epochs=20) están calibrados para la escala de rating
    típica 1-5. Con nuestra escala (0.0, 1.0) -- mucho más angosta -- esos
    defaults NO convergen: en una prueba de validación con 20
    estudiantes / 2 clusters de gusto claros, el modelo con defaults
    predecía prácticamente el mismo score (~0.61) para libros preferidos
    y no preferidos (diff ≈ -0.005, es decir, ni siquiera en la dirección
    correcta). Subir lr_all a 0.01 y n_epochs a 100 corrige esto
    (diff ≈ +0.58 en la misma prueba). Documentado en
    registro_decisiones_chat1.md.
    """

    def __init__(self, n_factors=5, n_epochs=100, lr_all=0.01, reg_all=0.02, random_state=42):
        self.n_factors = n_factors
        self.n_epochs = n_epochs
        self.lr_all = lr_all
        self.reg_all = reg_all
        self.random_state = random_state
        self.modelo = None
        self.usuarios_con_rating = set()
        self.media_global = 0.5  # fallback si no hay historial todavía

    def entrenar(self, historial):
        """
        historial: lista de dicts {"estudiante_id", "libro_id", "rating"}
        rating en {0.0, 1.0} (decisión #1 del módulo).
        """
        if not historial:
            self.modelo = None
            self.usuarios_con_rating = set()
            return

        filas = [(h["estudiante_id"], h["libro_id"], h["rating"]) for h in historial]
        reader = Reader(rating_scale=(0.0, 1.0))
        dataset = Dataset.load_from_df(
            __import__("pandas").DataFrame(filas, columns=["uid", "iid", "rating"]),
            reader,
        )
        trainset = dataset.build_full_trainset()

        self.modelo = SVD(
            n_factors=self.n_factors, n_epochs=self.n_epochs,
            lr_all=self.lr_all, reg_all=self.reg_all,
            random_state=self.random_state,
        )
        self.modelo.fit(trainset)
        self.usuarios_con_rating = {h["estudiante_id"] for h in historial}
        self.media_global = float(np.mean([h["rating"] for h in historial]))

    def predecir(self, estudiante_id, libro_id):
        if self.modelo is None:
            return self.media_global
        try:
            return self.modelo.predict(estudiante_id, libro_id).est
        except PredictionImpossible:
            return self.media_global

    def top_k(self, estudiante_id, candidatos, k=10):
        """candidatos: lista de libro_id. Devuelve los k con mayor score predicho."""
        scored = [(lid, self.predecir(estudiante_id, lid)) for lid in candidatos]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [lid for lid, _ in scored[:k]]

    def tiene_historial(self, estudiante_id):
        return estudiante_id in self.usuarios_con_rating


# ---------------------------------------------------------------------------
# LinUCB -- bandit contextual compartido (decisión #2 del módulo)
# ---------------------------------------------------------------------------

class LinUCB:
    def __init__(self, dimension=len(GENEROS_Y_GENERAL), alpha=1.0):
        self.d = dimension
        self.alpha = alpha
        self.A = np.identity(self.d)
        self.b = np.zeros(self.d)

    def _theta(self):
        A_inv = np.linalg.inv(self.A)
        return A_inv @ self.b, A_inv

    def score_ucb(self, contexto):
        theta, A_inv = self._theta()
        media = float(theta @ contexto)
        incertidumbre = self.alpha * float(np.sqrt(contexto @ A_inv @ contexto))
        return media + incertidumbre

    def top_k(self, vector_estudiante, candidatos_con_vector, k=10):
        """
        candidatos_con_vector: lista de (libro_id, vector_genero_libro).
        Devuelve los k libro_id con mayor score UCB.
        """
        scored = []
        for libro_id, vector_libro in candidatos_con_vector:
            contexto = construir_contexto(vector_estudiante, vector_libro)
            scored.append((libro_id, self.score_ucb(contexto)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [lid for lid, _ in scored[:k]]

    def actualizar(self, vector_estudiante, vector_libro, reward):
        contexto = construir_contexto(vector_estudiante, vector_libro)
        self.A += np.outer(contexto, contexto)
        self.b += reward * contexto


# ---------------------------------------------------------------------------
# B1 -- Popularidad
# ---------------------------------------------------------------------------

class BaselinePopularidad:
    def __init__(self):
        self.conteo_aceptaciones = Counter()

    def actualizar(self, libro_id, reward):
        if reward == 1.0:
            self.conteo_aceptaciones[libro_id] += 1

    def top_k(self, candidatos, k=10):
        candidatos_ordenados = sorted(
            candidatos, key=lambda lid: self.conteo_aceptaciones.get(lid, 0), reverse=True
        )
        return candidatos_ordenados[:k]


# ---------------------------------------------------------------------------
# B2 -- SVD sin bandit, cold start ingenuo (decisión #5 del módulo)
# ---------------------------------------------------------------------------

class BaselineSVDIngenuo:
    """
    NOTA (registro_decisiones, sección de validación motor -- chat 2): este
    wrapper YA NO sobrescribe n_factors/n_epochs -- hereda los defaults ya
    calibrados de MotorSVD (n_factors=5, n_epochs=100, lr_all=0.01). Antes
    tenía sus propios defaults (n_factors=20, n_epochs=20) que reintroducían
    el problema de no-convergencia que la calibración de MotorSVD ya había
    resuelto, además de romper la comparación limpia B2-vs-SistemaCompleto
    al usar una configuración de SVD distinta al resto del motor.
    """

    def __init__(self, random_state=42, rng=None, **kwargs_svd):
        self.motor = MotorSVD(random_state=random_state, **kwargs_svd)
        self.rng = rng or random.Random(42)

    def entrenar(self, historial):
        self.motor.entrenar(historial)

    def top_k(self, estudiante_id, candidatos, k=10):
        if self.motor.tiene_historial(estudiante_id):
            return self.motor.top_k(estudiante_id, candidatos, k=k)
        # Cold start ingenuo: selección aleatoria, no imputación de media global.
        candidatos_shuffle = list(candidatos)
        self.rng.shuffle(candidatos_shuffle)
        return candidatos_shuffle[:k]


# ---------------------------------------------------------------------------
# Sistema completo -- LinUCB en frío, SVD en caliente (sección 4 de la spec)
# ---------------------------------------------------------------------------

class SistemaCompleto:
    """
    NOTA (registro_decisiones, sección de validación motor -- chat 2): igual
    que BaselineSVDIngenuo, ya NO sobrescribe n_factors/n_epochs del
    MotorSVD interno -- hereda los defaults calibrados (n_factors=5,
    n_epochs=100, lr_all=0.01) para que la fase cálida use exactamente la
    misma configuración de SVD que B2 y que el MotorSVD validado de forma
    independiente, manteniendo limpia la comparación entre los 3 sistemas.
    """

    def __init__(self, n_umbral, random_state=42, alpha_ucb=1.0, **kwargs_svd):
        self.n_umbral = n_umbral
        self.motor_svd = MotorSVD(random_state=random_state, **kwargs_svd)
        self.bandit = LinUCB(alpha=alpha_ucb)
        self.conteo_interacciones = defaultdict(int)  # decisión #4: cuenta accept+reject

    def fase(self, estudiante_id):
        return "fria" if self.conteo_interacciones[estudiante_id] < self.n_umbral else "calida"

    def entrenar_svd(self, historial):
        self.motor_svd.entrenar(historial)

    def recomendar(self, estudiante_id, vector_estudiante, candidatos_con_vector, k=10):
        if self.fase(estudiante_id) == "fria":
            return self.bandit.top_k(vector_estudiante, candidatos_con_vector, k=k), "linucb"
        candidatos_ids = [lid for lid, _ in candidatos_con_vector]
        return self.motor_svd.top_k(estudiante_id, candidatos_ids, k=k), "svd"

    def registrar_interaccion(self, estudiante_id, vector_estudiante, vector_libro, reward):
        """Llamar después de cada resultado de funcion_aceptacion -- actualiza
        LinUCB si la interacción ocurrió en fase fría, y siempre incrementa
        el contador de interacciones (decisión #4)."""
        if self.fase(estudiante_id) == "fria":
            self.bandit.actualizar(vector_estudiante, vector_libro, reward)
        self.conteo_interacciones[estudiante_id] += 1
