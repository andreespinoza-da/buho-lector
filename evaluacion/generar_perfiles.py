"""
generar_perfiles.py

Generador de perfiles sintéticos de estudiantes para Búho Lector
(sección 3 de spec_perfiles_sinteticos_simulacion.md).

Produce, para cada estudiante:
    - atributos demográficos (edad, grado escolar, país)
    - arquetipo (nicho / mainstream / nuevo) y el alpha de Dirichlet asociado
    - vector de afinidad sobre los 8 géneros objetivo + "general"

También incluye la función de aceptación/rechazo (sección 3.5), que se
reutiliza después en el harness de simulación.

ALCANCE -- qué NO hace este script:
    El historial de interacciones de cada estudiante se construye DURANTE
    la simulación (T rondas, sección 5), no aquí. Este generador produce
    el estado en t=0: atributos fijos + historial vacío. La semántica
    operacional del arquetipo "nuevo" (cómo se garantiza que tenga
    historial=0 en el momento relevante de la simulación, cuando otros
    estudiantes ya acumularon rondas) se decide al implementar el harness
    -- ver registro_decisiones_chat1.md, sección pendiente.

USO:
    python generar_perfiles.py
"""

import json
import random
from collections import Counter

import numpy as np

# ---------------------------------------------------------------------------
# PARÁMETROS -- valores por defecto dentro de los rangos de la spec
# ---------------------------------------------------------------------------

N_ESTUDIANTES = 400  # spec: rango 300-500; 400 como punto medio, ajustable

GENEROS_OBJETIVO = [
    "aventura", "fantasia", "misterio", "ciencia_ficcion",
    "humor", "historia", "biografia", "poesia_folclore",
]

PROPORCION_ARQUETIPO = {"nicho": 0.35, "mainstream": 0.50, "nuevo": 0.15}
ALPHA_POR_GUSTO = {"nicho": 0.3, "mainstream": 3.0}

# T = número de rondas del harness de simulación (sección 5.1 de la spec).
# Se necesita aquí solo para sortear la ronda de ingreso de los estudiantes
# "nuevo" (entrada escalonada -- ver registro_decisiones_chat1.md, sección 6).
T_RONDAS_SIMULACION = 20

# Decisión #4 de la spec (sección 8, abierta): pesos de país.
# Sin datos reales de población escolar latinoamericana a mano -> uniforme,
# tal como la propia spec contempla como fallback ("uniforme si no [se
# dispone del dato]"). Ajustar aquí si se consigue el dato real.
PAISES = {
    "México": 0.25,
    "Colombia": 0.25,
    "Argentina": 0.25,
    "Ecuador": 0.25,
}

RUIDO_ACEPTACION = 0.05  # sección 3.5: ruido_uniforme(-0.05, +0.05)


# ---------------------------------------------------------------------------
# Demografía
# ---------------------------------------------------------------------------

def asignar_grado_escolar(edad):
    """
    Mapeo determinístico edad -> grado escolar. Aproximación genérica
    latinoamericana (varía por país en la realidad): primaria 1-6 grado
    (edades 6-11), secundaria/bachillerato 7-12 (edades 12-17).
    Para el rango de este proyecto (8-17): grado = edad - 5.
    """
    grado = edad - 5
    nivel = "primaria" if grado <= 6 else "secundaria"
    return grado, nivel


def generar_demografia(rng):
    edad = rng.randint(8, 17)
    grado, nivel = asignar_grado_escolar(edad)
    pais = rng.choices(list(PAISES.keys()), weights=list(PAISES.values()))[0]
    return {"edad": edad, "grado_escolar": grado, "nivel": nivel, "pais": pais}


# ---------------------------------------------------------------------------
# Arquetipo y vector de afinidad
# ---------------------------------------------------------------------------

def asignar_arquetipo(rng):
    """
    Devuelve (categoria, gusto_subyacente, alpha, es_nuevo).

    categoria: "nicho" | "mainstream" | "nuevo" -- la etiqueta reportada
               en el desagregado por arquetipo (sección 5.4).
    gusto_subyacente: "nicho" | "mainstream" -- determina el alpha de
               Dirichlet, incluso si categoria == "nuevo" (sección 3.4,
               nota de diseño: nuevo no es excluyente con el tipo de gusto).
    es_nuevo: bool -- bandera aparte para la dimensión de historial inicial.
    """
    categoria = rng.choices(
        list(PROPORCION_ARQUETIPO.keys()),
        weights=list(PROPORCION_ARQUETIPO.values()),
    )[0]

    if categoria == "nuevo":
        gusto_subyacente = rng.choice(["nicho", "mainstream"])
        es_nuevo = True
    else:
        gusto_subyacente = categoria
        es_nuevo = False

    alpha = ALPHA_POR_GUSTO[gusto_subyacente]
    return categoria, gusto_subyacente, alpha, es_nuevo


def asignar_ronda_ingreso(es_nuevo, rng, t_rondas=T_RONDAS_SIMULACION):
    """
    Decisión (registro_decisiones_chat1.md, sección 6): "nuevo" se
    operacionaliza como ENTRADA ESCALONADA. Cada estudiante "nuevo" recibe
    una ronda de ingreso aleatoria uniforme en [1, T]; no participa del
    harness (no recibe recomendaciones, no acumula historial) antes de esa
    ronda. Los demás arquetipos ingresan en la ronda 1, como siempre.
    """
    if es_nuevo:
        return rng.randint(1, t_rondas)
    return 1


def generar_vector_afinidad(alpha, np_rng, generos=GENEROS_OBJETIVO):
    """
    Vector de afinidad sobre los géneros objetivo vía Dirichlet([alpha]*8).
    Se añade una entrada "general" = promedio del vector, para poder
    evaluar libros que cayeron en la categoría catch-all del catálogo
    (ver normalizar_generos.py) sin afinidad específica de género.
    Esto es una decisión nueva, no cubierta por la spec original -- queda
    registrada en registro_decisiones_chat1.md.
    """
    pesos = np_rng.dirichlet([alpha] * len(generos))
    vector = dict(zip(generos, pesos.tolist()))
    vector["general"] = sum(vector.values()) / len(generos)
    return vector


# ---------------------------------------------------------------------------
# Generación de un perfil completo
# ---------------------------------------------------------------------------

def generar_estudiante(id_estudiante, rng, np_rng):
    demografia = generar_demografia(rng)
    categoria, gusto_subyacente, alpha, es_nuevo = asignar_arquetipo(rng)
    vector_afinidad = generar_vector_afinidad(alpha, np_rng)
    ronda_ingreso = asignar_ronda_ingreso(es_nuevo, rng)

    return {
        "id": id_estudiante,
        **demografia,
        "arquetipo": categoria,
        "gusto_subyacente": gusto_subyacente,
        "alpha_dirichlet": alpha,
        "es_nuevo": es_nuevo,
        "ronda_ingreso": ronda_ingreso,
        "vector_afinidad": vector_afinidad,
        "historial": [],  # se llena durante la simulación (sección 5), a partir de ronda_ingreso
    }


def generar_cohorte(n=N_ESTUDIANTES, semilla=42):
    rng = random.Random(semilla)
    np_rng = np.random.default_rng(semilla)
    return [generar_estudiante(i, rng, np_rng) for i in range(n)]


# ---------------------------------------------------------------------------
# Función de aceptación/rechazo (sección 3.5) -- reutilizada por el harness
# ---------------------------------------------------------------------------

def afinidad_estudiante_libro(vector_estudiante, vector_libro):
    """
    Afinidad base = producto punto entre el vector de afinidad del
    estudiante y el vector de género del libro (que ya viene de
    normalizar_generos.py con el tratamiento "promedio" para libros
    multi-género, o {"general": 1.0} si no tiene género narrativo).
    Esto generaliza automáticamente el caso multi-género de la sección 3.5
    (promedio de afinidades) porque el peso ya está repartido en el vector
    del libro.
    """
    return sum(
        vector_estudiante.get(g, 0.0) * peso
        for g, peso in vector_libro.items()
    )


def funcion_aceptacion(vector_estudiante, vector_libro, rng=random,
                        ruido=RUIDO_ACEPTACION):
    """
    Implementa sección 3.5:
        P(aceptar) = afinidad + ruido_uniforme(-0.05, +0.05), recortado a [0,1]
        resultado = Bernoulli(P(aceptar))

    Devuelve (aceptado: bool, p_usada: float) -- se devuelve p_usada para
    poder auditar/depurar la simulación.
    """
    afinidad = afinidad_estudiante_libro(vector_estudiante, vector_libro)
    p = afinidad + rng.uniform(-ruido, ruido)
    p = min(max(p, 0.0), 1.0)
    aceptado = rng.random() < p
    return aceptado, p


# ---------------------------------------------------------------------------
# Validación / reporte
# ---------------------------------------------------------------------------

def validar_cohorte(cohorte):
    n = len(cohorte)
    arquetipos = Counter(e["arquetipo"] for e in cohorte)
    paises = Counter(e["pais"] for e in cohorte)
    edades = [e["edad"] for e in cohorte]

    sumas_vector = [sum(e["vector_afinidad"][g] for g in GENEROS_OBJETIVO) for e in cohorte]

    rondas_ingreso_no_nuevos = [e["ronda_ingreso"] for e in cohorte if not e["es_nuevo"]]
    rondas_ingreso_nuevos = [e["ronda_ingreso"] for e in cohorte if e["es_nuevo"]]

    return {
        "n_estudiantes": n,
        "arquetipos_pct": {k: round(v / n, 3) for k, v in arquetipos.items()},
        "paises_pct": {k: round(v / n, 3) for k, v in paises.items()},
        "edad_min": min(edades),
        "edad_max": max(edades),
        "vector_suma_min": round(min(sumas_vector), 6),
        "vector_suma_max": round(max(sumas_vector), 6),
        "ronda_ingreso_no_nuevos_todos_1": all(r == 1 for r in rondas_ingreso_no_nuevos),
        "ronda_ingreso_nuevos_min": min(rondas_ingreso_nuevos),
        "ronda_ingreso_nuevos_max": max(rondas_ingreso_nuevos),
        "ronda_ingreso_nuevos_n": len(rondas_ingreso_nuevos),
    }


def main():
    cohorte = generar_cohorte()

    with open("estudiantes_sinteticos.jsonl", "w", encoding="utf-8") as out:
        for e in cohorte:
            out.write(json.dumps(e, ensure_ascii=False) + "\n")

    stats = validar_cohorte(cohorte)
    with open("reporte_perfiles.txt", "w", encoding="utf-8") as out:
        out.write("REPORTE DE GENERACIÓN DE PERFILES SINTÉTICOS\n")
        out.write("=" * 60 + "\n\n")
        out.write(f"N estudiantes generados: {stats['n_estudiantes']}\n\n")
        out.write("Distribución por arquetipo (objetivo: nicho 35%, mainstream 50%, nuevo 15%):\n")
        for k, v in stats["arquetipos_pct"].items():
            out.write(f"  {k:>12}: {v:.1%}\n")
        out.write("\nDistribución por país (objetivo: uniforme 25% cada uno -- decisión #4, pendiente de pesos reales):\n")
        for k, v in stats["paises_pct"].items():
            out.write(f"  {k:>12}: {v:.1%}\n")
        out.write(f"\nEdad: rango [{stats['edad_min']}, {stats['edad_max']}] (objetivo: [8, 17])\n")
        out.write(
            f"\nValidación de vectores Dirichlet (deben sumar 1.0 sobre los 8 géneros, "
            f"sin contar 'general'):\n  min={stats['vector_suma_min']}  max={stats['vector_suma_max']}\n"
        )
        out.write(
            f"\nValidación ronda_ingreso (decisión: entrada escalonada):\n"
            f"  No-nuevos, todos ronda_ingreso=1: {stats['ronda_ingreso_no_nuevos_todos_1']}\n"
            f"  Nuevos (n={stats['ronda_ingreso_nuevos_n']}), rango ronda_ingreso: "
            f"[{stats['ronda_ingreso_nuevos_min']}, {stats['ronda_ingreso_nuevos_max']}] (objetivo: [1, {T_RONDAS_SIMULACION}])\n"
        )

    print(f"Cohorte generada: {stats['n_estudiantes']} estudiantes")
    print(f"Arquetipos: {stats['arquetipos_pct']}")
    print("Archivos generados: estudiantes_sinteticos.jsonl, reporte_perfiles.txt")


if __name__ == "__main__":
    main()
