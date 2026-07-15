"""
test_motor_b1_b2_sistema.py

Validación con casos pequeños y controlados de las 3 piezas de
motor_recomendacion.py que estaban implementadas pero SIN PROBAR:

    1. BaselinePopularidad (B1)
    2. BaselineSVDIngenuo (B2) -- fallback aleatorio en frío vs. transición a SVD
    3. SistemaCompleto -- switch de fase fría/cálida al cruzar el umbral n

Mismo criterio que se usó para validar MotorSVD y LinUCB en el chat anterior:
casos diseñados para que el resultado correcto sea conocido de antemano, no
solo "se ve razonable".
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "motor"))

import numpy as np

from motor_recomendacion import (
    BaselinePopularidad,
    BaselineSVDIngenuo,
    SistemaCompleto,
    GENEROS_Y_GENERAL,
)

FALLOS = []


def check(nombre, condicion, detalle=""):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}" + (f" -- {detalle}" if detalle else ""))
    if not condicion:
        FALLOS.append(nombre)


# ===========================================================================
# 1. BaselinePopularidad (B1)
# ===========================================================================
print("=" * 70)
print("1. BaselinePopularidad (B1)")
print("=" * 70)

b1 = BaselinePopularidad()
candidatos_b1 = ["A", "B", "C", "D"]

# A: 5 aceptaciones: B: 2 aceptaciones; C: 0; D: 3 RECHAZOS (no deben contar)
for _ in range(5):
    b1.actualizar("A", 1.0)
for _ in range(2):
    b1.actualizar("B", 1.0)
for _ in range(3):
    b1.actualizar("D", 0.0)  # rechazo -- NO debe incrementar el conteo

conteos = {lid: b1.conteo_aceptaciones.get(lid, 0) for lid in candidatos_b1}
check(
    "Rechazos (reward=0.0) no incrementan el conteo de popularidad",
    conteos["D"] == 0,
    f"conteo D = {conteos['D']} (esperado 0)",
)
check(
    "Conteos de aceptación correctos",
    conteos == {"A": 5, "B": 2, "C": 0, "D": 0},
    f"conteos = {conteos}",
)

top3 = b1.top_k(candidatos_b1, k=3)
check(
    "top_k ordena por aceptaciones descendente (A > B > resto)",
    top3[0] == "A" and top3[1] == "B",
    f"top3 = {top3}",
)
check(
    "Empate (C=0, D=0) se resuelve por orden de aparición en candidatos (sort estable)",
    top3[2] == "C",
    f"top3 = {top3} (C aparece antes que D en candidatos_b1)",
)

top_all = b1.top_k(candidatos_b1, k=10)
check(
    "k > len(candidatos) devuelve todos los candidatos, sin error",
    len(top_all) == len(candidatos_b1),
    f"len = {len(top_all)}",
)

# Caso sin ninguna interacción registrada todavía (cobertura del cold start de B1)
b1_vacio = BaselinePopularidad()
top_vacio = b1_vacio.top_k(candidatos_b1, k=4)
check(
    "B1 sin interacciones devuelve los candidatos sin error (orden original, todos empatados en 0)",
    top_vacio == candidatos_b1,
    f"top_vacio = {top_vacio}",
)


# ===========================================================================
# 2. BaselineSVDIngenuo (B2)
# ===========================================================================
print()
print("=" * 70)
print("2. BaselineSVDIngenuo (B2)")
print("=" * 70)

# --- 2a. Cold start ingenuo: selección aleatoria, NO imputación de media ---
import random as random_module

b2_frio = BaselineSVDIngenuo(rng=random_module.Random(123))
b2_frio.entrenar([])  # sin historial -> ningún estudiante "tiene_historial"

candidatos_b2 = [f"libro_{i}" for i in range(8)]
top_frio_1 = b2_frio.top_k("estudiante_x", candidatos_b2, k=4)

check(
    "Cold start (sin historial) devuelve k candidatos",
    len(top_frio_1) == 4,
    f"top = {top_frio_1}",
)
check(
    "Cold start es una selección de candidatos válidos (subconjunto de candidatos_b2)",
    set(top_frio_1).issubset(set(candidatos_b2)),
    f"top = {top_frio_1}",
)
check(
    "Cold start NO sigue el orden original de candidatos (evidencia de que es aleatorio, no un slice fijo)",
    top_frio_1 != candidatos_b2[:4],
    f"top = {top_frio_1} vs orden original {candidatos_b2[:4]}",
)

# Determinismo: misma semilla -> mismo resultado
b2_frio_repetido = BaselineSVDIngenuo(rng=random_module.Random(123))
b2_frio_repetido.entrenar([])
top_frio_repetido = b2_frio_repetido.top_k("estudiante_x", candidatos_b2, k=4)
check(
    "Cold start es determinístico dada la misma semilla (reproducibilidad para el TFM)",
    top_frio_1 == top_frio_repetido,
    f"{top_frio_1} vs {top_frio_repetido}",
)

# Semilla distinta -> resultado distinto (confirma que SÍ depende del rng, no es un bug que
# ignore la semilla)
b2_frio_otra_semilla = BaselineSVDIngenuo(rng=random_module.Random(999))
b2_frio_otra_semilla.entrenar([])
top_frio_otra_semilla = b2_frio_otra_semilla.top_k("estudiante_x", candidatos_b2, k=4)
check(
    "Cold start con semilla distinta produce orden distinto",
    top_frio_1 != top_frio_otra_semilla,
    f"{top_frio_1} vs {top_frio_otra_semilla}",
)

# --- 2b. Transición a SVD una vez hay historial: 2 clusters de gusto claros ---
# Mismo patrón que la validación previa de MotorSVD (registro_decisiones_chat1.md):
# estudiantes 1 y 2 SOLO aceptan libros del cluster_1 y rechazan del cluster_2;
# estudiantes 3 y 4 al revés. Esto deja un patrón inequívoco para verificar
# que B2 EN CALIENTE delega correctamente en MotorSVD (no en aleatorio).
historial_b2 = []
cluster_1 = ["libro_c1_a", "libro_c1_b", "libro_c1_c"]
cluster_2 = ["libro_c2_a", "libro_c2_b", "libro_c2_c"]

for est in [1, 2]:
    for lib in cluster_1:
        historial_b2.append({"estudiante_id": est, "libro_id": lib, "rating": 1.0})
    for lib in cluster_2:
        historial_b2.append({"estudiante_id": est, "libro_id": lib, "rating": 0.0})

for est in [3, 4]:
    for lib in cluster_1:
        historial_b2.append({"estudiante_id": est, "libro_id": lib, "rating": 0.0})
    for lib in cluster_2:
        historial_b2.append({"estudiante_id": est, "libro_id": lib, "rating": 1.0})

b2_caliente = BaselineSVDIngenuo(rng=random_module.Random(123))
b2_caliente.entrenar(historial_b2)
check(
    "BaselineSVDIngenuo hereda los defaults calibrados de MotorSVD (n_factors=5, n_epochs=100), "
    "no sus antiguos defaults sin calibrar (20/20)",
    b2_caliente.motor.n_factors == 5 and b2_caliente.motor.n_epochs == 100,
    f"n_factors={b2_caliente.motor.n_factors}, n_epochs={b2_caliente.motor.n_epochs}",
)

check(
    "Tras entrenar con historial, tiene_historial() es True para estudiantes con ratings",
    b2_caliente.motor.tiene_historial(1) and b2_caliente.motor.tiene_historial(3),
    "",
)
check(
    "tiene_historial() sigue False para un estudiante SIN ratings en el historial entrenado",
    not b2_caliente.motor.tiene_historial(999),
    "",
)

candidatos_mixtos = cluster_1 + cluster_2
top_est1 = b2_caliente.top_k(1, candidatos_mixtos, k=3)
top_est3 = b2_caliente.top_k(3, candidatos_mixtos, k=3)

check(
    "B2 en caliente (estudiante 1, afín a cluster_1): top-3 son todos del cluster_1",
    set(top_est1) == set(cluster_1),
    f"top_est1 = {top_est1}",
)
check(
    "B2 en caliente (estudiante 3, afín a cluster_2): top-3 son todos del cluster_2",
    set(top_est3) == set(cluster_2),
    f"top_est3 = {top_est3}",
)

# Estudiante sin ratings en el historial entrenado: aunque el MODELO sí está
# entrenado, ESTE estudiante específico debe caer en el fallback aleatorio
# (decisión #5 del módulo: el chequeo es por estudiante, no global).
top_est_nuevo = b2_caliente.top_k(999, candidatos_mixtos, k=3)
check(
    "Estudiante sin historial propio cae en fallback aleatorio AUNQUE el modelo SVD ya esté entrenado "
    "(el cold start es por estudiante, no por estado global del motor)",
    len(top_est_nuevo) == 3 and set(top_est_nuevo).issubset(set(candidatos_mixtos)),
    f"top_est_nuevo = {top_est_nuevo}",
)


# ===========================================================================
# 3. SistemaCompleto -- switch fría/cálida
# ===========================================================================
print()
print("=" * 70)
print("3. SistemaCompleto -- switch de fase")
print("=" * 70)

N_UMBRAL = 3
sistema = SistemaCompleto(n_umbral=N_UMBRAL, alpha_ucb=1.0)

# Vector de estudiante y vector de libro simples para construir contexto no nulo
vector_estudiante = {g: 0.0 for g in GENEROS_Y_GENERAL}
vector_estudiante["fantasia"] = 1.0
vector_estudiante["general"] = 0.125

candidatos_libros = []
for i in range(5):
    v = {g: 0.0 for g in GENEROS_Y_GENERAL}
    v["fantasia"] = 1.0 if i % 2 == 0 else 0.0
    v["aventura"] = 0.0 if i % 2 == 0 else 1.0
    candidatos_libros.append((f"libro_{i}", v))

# --- 3a. Fase inicial: fría (conteo=0 < n_umbral=3) ---
check(
    "fase() inicial es 'fria' (conteo 0 < n_umbral 3)",
    sistema.fase("u1") == "fria",
    "",
)
recs, metodo = sistema.recomendar("u1", vector_estudiante, candidatos_libros, k=3)
check(
    "recomendar() en fase fría usa el bandit (método 'linucb')",
    metodo == "linucb",
    f"método = {metodo}",
)

# --- 3b. Registrar interacciones una por una, vigilando el límite exacto ---
# Decisión #4 del módulo: el contador cuenta accept+reject, y fase() se evalúa
# ANTES de incrementar en registrar_interaccion -- la interacción que cruza el
# umbral todavía se trata como ocurrida en frío (y por tanto actualiza el bandit).
A_antes = sistema.bandit.A.copy()
b_antes = sistema.bandit.b.copy()

sistema.registrar_interaccion("u1", vector_estudiante, candidatos_libros[0][1], reward=1.0)
check(
    "Tras 1 interacción (umbral=3): conteo=1, fase sigue 'fria'",
    sistema.conteo_interacciones["u1"] == 1 and sistema.fase("u1") == "fria",
    f"conteo={sistema.conteo_interacciones['u1']}, fase={sistema.fase('u1')}",
)
check(
    "La interacción #1 (ocurrida en frío) SÍ actualizó la matriz A del bandit",
    not np.allclose(sistema.bandit.A, A_antes),
    "",
)

sistema.registrar_interaccion("u1", vector_estudiante, candidatos_libros[1][1], reward=0.0)
check(
    "Tras 2 interacciones (umbral=3): conteo=2, fase sigue 'fria'",
    sistema.conteo_interacciones["u1"] == 2 and sistema.fase("u1") == "fria",
    f"conteo={sistema.conteo_interacciones['u1']}, fase={sistema.fase('u1')}",
)

A_justo_antes_del_cruce = sistema.bandit.A.copy()
# Esta es la interacción #3: conteo pasa de 2 a 3. fase() se evalúa con
# conteo=2 (< 3, "fria") ANTES de incrementar -> debe actualizar el bandit.
sistema.registrar_interaccion("u1", vector_estudiante, candidatos_libros[2][1], reward=1.0)
check(
    "Interacción #3 (la que CRUZA el umbral): conteo pasa a 3",
    sistema.conteo_interacciones["u1"] == 3,
    f"conteo={sistema.conteo_interacciones['u1']}",
)
check(
    "Interacción #3 SÍ actualizó el bandit (se evaluó fase() con conteo=2, todavía fría, "
    "antes del incremento) -- comportamiento documentado en decisión #4, confirmado aquí",
    not np.allclose(sistema.bandit.A, A_justo_antes_del_cruce),
    "",
)
check(
    "Tras la interacción #3, fase('u1') ya es 'calida' (conteo=3, no es < 3)",
    sistema.fase("u1") == "calida",
    f"fase = {sistema.fase('u1')}",
)

# --- 3c. En fase cálida: recomendar() debe usar SVD, no el bandit ---
recs_calido, metodo_calido = sistema.recomendar(
    "u1", vector_estudiante, candidatos_libros, k=3
)
check(
    "recomendar() en fase cálida usa SVD (método 'svd'), no el bandit",
    metodo_calido == "svd",
    f"método = {metodo_calido}",
)

# --- 3d. En fase cálida, registrar_interaccion ya NO debe tocar el bandit ---
A_antes_calido = sistema.bandit.A.copy()
b_antes_calido = sistema.bandit.b.copy()
sistema.registrar_interaccion("u1", vector_estudiante, candidatos_libros[3][1], reward=1.0)
check(
    "En fase cálida, registrar_interaccion() YA NO actualiza el bandit (A y b sin cambios)",
    np.allclose(sistema.bandit.A, A_antes_calido) and np.allclose(sistema.bandit.b, b_antes_calido),
    "",
)
check(
    "Pero el contador de interacciones SIGUE incrementando en fase cálida (conteo=4)",
    sistema.conteo_interacciones["u1"] == 4,
    f"conteo={sistema.conteo_interacciones['u1']}",
)

# --- 3e. La fase es POR ESTUDIANTE: otro estudiante sin interacciones sigue frío ---
check(
    "Un estudiante distinto (u2), sin interacciones propias, sigue en fase 'fria' "
    "aunque u1 ya esté en 'calida' (el contador es por estudiante, no global)",
    sistema.fase("u2") == "fria",
    f"fase(u2) = {sistema.fase('u2')}",
)

# --- 3f. Caso límite: n_umbral=0 -> el estudiante nace directamente en fase cálida ---
sistema_umbral_cero = SistemaCompleto(n_umbral=0)
check(
    "n_umbral=0: un estudiante nuevo (conteo=0) ya está en fase 'calida' desde el inicio "
    "(0 < 0 es False)",
    sistema_umbral_cero.fase("u_nuevo") == "calida",
    f"fase = {sistema_umbral_cero.fase('u_nuevo')}",
)

# --- 3g. entrenar_svd() debe alimentar correctamente a motor_svd interno ---
sistema_svd = SistemaCompleto(n_umbral=1)  # umbral bajo para llegar rápido a fase cálida
sistema_svd.entrenar_svd(historial_b2)  # reusa el historial de 2 clusters de la sección 2b
sistema_svd.conteo_interacciones[1] = 1  # forzar fase cálida para estudiante 1 (umbral=1)
check(
    "fase(1) es 'calida' tras forzar conteo>=n_umbral",
    sistema_svd.fase(1) == "calida",
    "",
)
recs_svd, metodo_svd = sistema_svd.recomendar(
    1, vector_estudiante,
    [(lid, {**{g: 0.0 for g in GENEROS_Y_GENERAL}}) for lid in candidatos_mixtos],
    k=3,
)
check(
    "Con motor_svd entrenado y estudiante en fase cálida con historial real, "
    "recomendar() delega en SVD y respeta el patrón aprendido (cluster_1 para estudiante 1)",
    metodo_svd == "svd" and set(recs_svd) == set(cluster_1),
    f"método={metodo_svd}, recs={recs_svd}",
)


# ===========================================================================
# Resumen
# ===========================================================================
print()
print("=" * 70)
if FALLOS:
    print(f"RESULTADO: {len(FALLOS)} FALLO(S) -- revisar antes de continuar")
    for f in FALLOS:
        print(f"  - {f}")
else:
    print("RESULTADO: TODOS LOS CASOS PASARON")
print("=" * 70)
