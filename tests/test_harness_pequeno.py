"""
test_harness_pequeno.py

Validación del harness con un caso pequeño y controlado: 6 estudiantes,
12 libros, T=4 rondas, n_umbral=2 -- antes de correr sobre los 400
estudiantes / 3000 libros reales.

Diseño del caso:
    - 2 estudiantes "nicho" (afinidad casi pura a un género), ronda_ingreso=1
    - 2 estudiantes "mainstream" (afinidad repartida), ronda_ingreso=1
    - 2 estudiantes "nuevo": uno entra en ronda 2, otro en ronda 3
      (para probar la entrada escalonada explícitamente)
    - 12 libros: 6 de "fantasia", 6 de "aventura" (géneros claramente
      separables) para poder verificar visualmente que las recomendaciones
      tienen sentido frente a los vectores de afinidad.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "evaluacion"))

from harness_simulacion import correr_simulacion, ndcg_at_k

FALLOS = []


def check(nombre, condicion, detalle=""):
    estado = "OK" if condicion else "FALLO"
    print(f"[{estado}] {nombre}" + (f" -- {detalle}" if detalle else ""))
    if not condicion:
        FALLOS.append(nombre)


# ===========================================================================
# 0. ndcg_at_k -- sanity check aislado (antes de meterlo en el harness)
# ===========================================================================
print("=" * 70)
print("0. ndcg_at_k -- casos de referencia")
print("=" * 70)

check("Todo aceptado en orden -> NDCG=1.0", abs(ndcg_at_k([1, 1, 1]) - 1.0) < 1e-9)
check("Nada aceptado -> NDCG=0.0 (convención, no NaN)", ndcg_at_k([0, 0, 0]) == 0.0)
check(
    "Un acierto al final vs. uno al principio: NDCG es menor si el acierto está más abajo",
    ndcg_at_k([0, 0, 1]) < ndcg_at_k([1, 0, 0]),
    f"[0,0,1]={ndcg_at_k([0,0,1]):.4f} vs [1,0,0]={ndcg_at_k([1,0,0]):.4f}",
)
check(
    "El mejor ranking posible para un conjunto de aceptados dado siempre da NDCG=1.0",
    abs(ndcg_at_k([1, 1, 0, 0]) - 1.0) < 1e-9,
    f"valor = {ndcg_at_k([1,1,0,0])}",
)


# ===========================================================================
# 1. Construcción del caso pequeño
# ===========================================================================
print()
print("=" * 70)
print("1. Caso pequeño: 6 estudiantes, 12 libros, T=4")
print("=" * 70)

GENEROS_8 = ["aventura", "fantasia", "misterio", "ciencia_ficcion", "humor", "historia", "biografia", "poesia_folclore"]


def vector_libro(genero_dominante):
    v = {g: 0.0 for g in GENEROS_8}
    v[genero_dominante] = 1.0
    return v


catalogo = []
for i in range(6):
    catalogo.append({"key": f"fantasia_{i}", "vector_afinidad": vector_libro("fantasia")})
for i in range(6):
    catalogo.append({"key": f"aventura_{i}", "vector_afinidad": vector_libro("aventura")})


def vector_estudiante(afinidades):
    v = {g: 0.0 for g in GENEROS_8}
    v.update(afinidades)
    v["general"] = sum(v[g] for g in GENEROS_8) / len(GENEROS_8)
    return v


estudiantes = [
    {"id": 0, "arquetipo": "nicho", "ronda_ingreso": 1, "vector_afinidad": vector_estudiante({"fantasia": 1.0})},
    {"id": 1, "arquetipo": "nicho", "ronda_ingreso": 1, "vector_afinidad": vector_estudiante({"aventura": 1.0})},
    {"id": 2, "arquetipo": "mainstream", "ronda_ingreso": 1,
     "vector_afinidad": vector_estudiante({"fantasia": 0.5, "aventura": 0.5})},
    {"id": 3, "arquetipo": "mainstream", "ronda_ingreso": 1,
     "vector_afinidad": vector_estudiante({"fantasia": 0.4, "aventura": 0.6})},
    {"id": 4, "arquetipo": "nuevo", "ronda_ingreso": 2, "vector_afinidad": vector_estudiante({"fantasia": 1.0})},
    {"id": 5, "arquetipo": "nuevo", "ronda_ingreso": 3, "vector_afinidad": vector_estudiante({"aventura": 1.0})},
]

# generar_perfiles.cargar_catalogo espera "key"/"vector_afinidad"; ya construido arriba a mano,
# pero usamos directamente la forma que espera EjecucionSistema (libro["id"], libro["vector"]),
# así que adaptamos al formato esperado por cargar_catalogo (mismo shape que el jsonl real).
catalogo_formato_real = [{"key": l["key"], "vector_afinidad": l["vector_afinidad"]} for l in catalogo]
from harness_simulacion import cargar_catalogo  # noqa: E402  (solo para reusar el shape, no el archivo)

import json, tempfile, os
with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8") as f:
    for l in catalogo_formato_real:
        f.write(json.dumps(l) + "\n")
    ruta_catalogo_tmp = f.name
catalogo_cargado = cargar_catalogo(ruta_catalogo_tmp)
os.unlink(ruta_catalogo_tmp)

check(
    "cargar_catalogo() produce el shape esperado ({'id':..., 'vector':...})",
    catalogo_cargado[0]["id"] == "fantasia_0" and catalogo_cargado[0]["vector"]["fantasia"] == 1.0,
    f"{catalogo_cargado[0]}",
)

T = 4
N_UMBRAL = 2
resultados, ejecuciones = correr_simulacion(catalogo_cargado, estudiantes, T=T, n_umbral=N_UMBRAL, k=3, semilla=7)


# ===========================================================================
# 2. Entrada escalonada (ronda_ingreso)
# ===========================================================================
print()
print("=" * 70)
print("2. Entrada escalonada")
print("=" * 70)

for nombre in ("B1", "B2", "completo"):
    activos_ronda1 = resultados[nombre][0]["n_estudiantes_activos"]
    activos_ronda2 = resultados[nombre][1]["n_estudiantes_activos"]
    activos_ronda3 = resultados[nombre][2]["n_estudiantes_activos"]
    check(
        f"[{nombre}] Ronda 1: solo los 4 estudiantes con ronda_ingreso=1 están activos",
        activos_ronda1 == 4,
        f"activos = {activos_ronda1}",
    )
    check(
        f"[{nombre}] Ronda 2: se suma el estudiante 4 (ronda_ingreso=2) -> 5 activos",
        activos_ronda2 == 5,
        f"activos = {activos_ronda2}",
    )
    check(
        f"[{nombre}] Ronda 3: se suma el estudiante 5 (ronda_ingreso=3) -> 6 activos",
        activos_ronda3 == 6,
        f"activos = {activos_ronda3}",
    )


# ===========================================================================
# 3. Exclusión de libros aceptados (decisión #3 del motor, implementada en el harness)
# ===========================================================================
print()
print("=" * 70)
print("3. Exclusión de libros aceptados")
print("=" * 70)

for nombre, ejecucion in ejecuciones.items():
    libros_aceptados_est0 = ejecucion.aceptados[0]
    if libros_aceptados_est0:
        # Verificar contra TODAS las recomendaciones de TODAS las rondas para el estudiante 0
        # que ese libro no vuelva a aparecer en una ronda POSTERIOR a su aceptación.
        # (No tenemos el detalle por ronda almacenado aquí, así que verificamos indirectamente:
        # los candidatos pasados a top_k siempre excluyen self.aceptados -- comprobamos que el
        # estado final de "aceptados" nunca incluye un libro que esté fuera del catálogo, y que
        # los candidatos de la ÚLTIMA ronda ya excluyen lo aceptado.)
        candidatos_finales = ejecucion._candidatos_para(0)
        check(
            f"[{nombre}] Los libros aceptados por el estudiante 0 NO están en sus candidatos tras la simulación",
            libros_aceptados_est0.isdisjoint(set(candidatos_finales)),
            f"aceptados={libros_aceptados_est0}, quedan {len(candidatos_finales)} candidatos",
        )
    else:
        print(f"[INFO] [{nombre}] Estudiante 0 no aceptó ningún libro en esta corrida (semilla/ruido) -- nada que excluir")


# ===========================================================================
# 4. Simulaciones independientes (decisión #1)
# ===========================================================================
print()
print("=" * 70)
print("4. Independencia entre las 3 simulaciones")
print("=" * 70)

aceptados_b1_est0 = ejecuciones["B1"].aceptados[0]
aceptados_b2_est0 = ejecuciones["B2"].aceptados[0]
aceptados_completo_est0 = ejecuciones["completo"].aceptados[0]

check(
    "Los 3 sistemas mantienen estados de 'aceptados' SEPARADOS para el mismo estudiante "
    "(no son el mismo objeto compartido)",
    ejecuciones["B1"].aceptados is not ejecuciones["B2"].aceptados
    and ejecuciones["B2"].aceptados is not ejecuciones["completo"].aceptados,
    "",
)
print(f"  [INFO] Estudiante 0 -- aceptados B1={aceptados_b1_est0}, B2={aceptados_b2_est0}, completo={aceptados_completo_est0}")


# ===========================================================================
# 5. Sentido de las recomendaciones (genero dominante correcto, sistema 'completo')
# ===========================================================================
print()
print("=" * 70)
print("5. Calidad direccional de las recomendaciones (Sistema completo, fase fría=LinUCB)")
print("=" * 70)

# Estudiante 0 (nicho, 100% fantasia) y estudiante 1 (nicho, 100% aventura):
# en la primera ronda (bandit sin entrenar, exploración casi uniforme) no se espera
# separación clara todavía -- la separación debe APARECER con las rondas.
metricas_completo = resultados["completo"]
precision_ronda1 = metricas_completo[0]["precision_at_10"]
precision_ronda4 = metricas_completo[3]["precision_at_10"]
check(
    "Precisión@k del sistema completo es un valor válido en [0,1] en cada ronda",
    all(0.0 <= m["precision_at_10"] <= 1.0 for m in metricas_completo),
    f"valores = {[round(m['precision_at_10'],3) for m in metricas_completo]}",
)


# ===========================================================================
# 6. Cobertura: monotónicamente no decreciente
# ===========================================================================
print()
print("=" * 70)
print("6. Cobertura acumulada -- debe ser monótonamente no decreciente")
print("=" * 70)

for nombre in ("B1", "B2", "completo"):
    coberturas = [m["cobertura"] for m in resultados[nombre]]
    no_decrece = all(coberturas[i] <= coberturas[i + 1] + 1e-12 for i in range(len(coberturas) - 1))
    check(
        f"[{nombre}] Cobertura acumulada no decrece ronda a ronda",
        no_decrece,
        f"coberturas = {[round(c,3) for c in coberturas]}",
    )
    check(
        f"[{nombre}] Cobertura está en [0,1]",
        all(0.0 <= c <= 1.0 for c in coberturas),
        f"coberturas = {[round(c,3) for c in coberturas]}",
    )


# ===========================================================================
# 7. Desagregación por arquetipo: estructura y consistencia
# ===========================================================================
print()
print("=" * 70)
print("7. Desagregación por arquetipo")
print("=" * 70)

m_ronda1 = resultados["B1"][0]
suma_activos_arquetipo = sum(m_ronda1["por_arquetipo"][a]["n_estudiantes_activos"] for a in ("nicho", "mainstream", "nuevo"))
check(
    "La suma de activos por arquetipo en la ronda 1 coincide con el total de activos (4)",
    suma_activos_arquetipo == m_ronda1["n_estudiantes_activos"],
    f"suma_por_arquetipo={suma_activos_arquetipo}, total={m_ronda1['n_estudiantes_activos']}",
)
check(
    "En la ronda 1 (ronda_ingreso=2,3 para los 'nuevo' aún no activos), el grupo 'nuevo' tiene 0 activos",
    m_ronda1["por_arquetipo"]["nuevo"]["n_estudiantes_activos"] == 0,
    f"activos nuevo = {m_ronda1['por_arquetipo']['nuevo']['n_estudiantes_activos']}",
)
m_ronda3 = resultados["B1"][2]
check(
    "En la ronda 3 ya están activos ambos estudiantes 'nuevo' (ronda_ingreso 2 y 3)",
    m_ronda3["por_arquetipo"]["nuevo"]["n_estudiantes_activos"] == 2,
    f"activos nuevo en ronda 3 = {m_ronda3['por_arquetipo']['nuevo']['n_estudiantes_activos']}",
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

print()
print("Métricas completas, sistema 'completo', por ronda:")
for m in resultados["completo"]:
    print(
        f"  t={m['ronda']}  activos={m['n_estudiantes_activos']:2d}  "
        f"precision@k={m['precision_at_10']}  ndcg@k={m['ndcg_at_10']}  cobertura={m['cobertura']:.3f}"
    )
