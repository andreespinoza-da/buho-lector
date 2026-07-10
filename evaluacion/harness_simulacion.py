"""
harness_simulacion.py

Harness de simulación iterativa (sección 5 de la spec). Implementa el
protocolo de Mansoury et al. (2020) tal como lo describe el pseudocódigo
de la sección 5.1:

    Para cada ronda t = 1..T:
        Para cada estudiante activo u:
            recomendaciones = motor.generar(u, k=10)
            Para cada libro i en recomendaciones:
                resultado = funcion_aceptacion(u, i)
                actualizar_historial(u, i, resultado)
        recalcular_metricas(t)
        motor.reentrenar(historial_actualizado)

DECISIONES DE DISEÑO (no especificadas por la spec, documentadas aquí y en
el registro de decisiones):

1. SIMULACIONES INDEPENDIENTES POR SISTEMA. B1, B2 y SistemaCompleto se
   corren en 3 simulaciones separadas sobre la MISMA cohorte inicial
   (mismos estudiantes, mismo catálogo), pero cada una mantiene su propio
   estado: su propio historial, su propio conjunto de libros ya aceptados
   por estudiante, su propio modelo entrenado. Necesario porque lo que un
   estudiante acepta depende de lo que SE LE RECOMENDÓ, y eso depende del
   sistema -- si las 3 corrieran sobre un único "mundo" compartido, las
   decisiones de un sistema contaminarían el historial de otro (un libro
   aceptado bajo B1 quedaría excluido también para B2, aunque B2 nunca lo
   haya recomendado). Sigue la práctica estándar de Mansoury et al. (2020,
   citados en la spec): cada algoritmo comparado se simula en una corrida
   independiente sobre la misma población sintética inicial.

2. EXCLUSIÓN DE LIBROS ACEPTADOS vive en el harness, no en
   motor_recomendacion.py. Las clases del motor reciben `candidatos` como
   parámetro y no tienen noción propia de "ya aceptado" -- es el harness
   quien filtra, antes de cada llamada a top_k/recomendar, los libros que
   ESE estudiante ya aceptó EN ESA simulación (decisión #3 del módulo del
   motor). Los rechazados NO se filtran (pueden volver a recomendarse,
   decisión ya tomada en motor_recomendacion.py).

3. REENTRENAMIENTO DE SVD: cada ronda, sobre el historial acumulado
   completo -- lectura directa del pseudocódigo de la sección 5.1
   ("motor.reentrenar(historial_actualizado)" al final de cada ronda), no
   es una decisión abierta.

4. AGREGACIÓN DE MÉTRICAS POR RONDA: promedio simple sobre los estudiantes
   ACTIVOS en esa ronda (ronda_ingreso <= t); cada estudiante activo pesa
   igual. La desagregación por arquetipo (sección 5.4) usa el mismo
   promedio pero solo dentro de cada grupo.

5. NDCG@10: relevancia binaria (1 aceptado, 0 rechazado) sobre las k
   recomendaciones de la ronda, en el orden en que se recomendaron. IDCG =
   ranking ideal con todos los aceptados al frente. Si ningún libro de la
   lista fue aceptado, NDCG=0 (convención estándar para evitar NaN).

6. COBERTURA DEL CATÁLOGO: acumulada hasta la ronda t (no aislada por
   ronda), tal como dice la spec ("a través de todos los estudiantes HASTA
   la ronda t") -- % de libros distintos que aparecieron en AL MENOS UNA
   lista de recomendación (recomendados, no necesariamente aceptados),
   sobre el tamaño del catálogo. Por sistema, y también desagregada por
   arquetipo (solo libros recomendados a estudiantes de ese arquetipo).
"""

import json
import math
import random
from collections import defaultdict
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend", "motor"))

from motor_recomendacion import (
    BaselinePopularidad,
    BaselineSVDIngenuo,
    SistemaCompleto,
)
from generar_perfiles import funcion_aceptacion

ARQUETIPOS = ("nicho", "mainstream", "nuevo")


# ---------------------------------------------------------------------------
# Carga de datos
# ---------------------------------------------------------------------------

def cargar_catalogo(path):
    libros = []
    with open(path, encoding="utf-8") as f:
        for linea in f:
            d = json.loads(linea)
            libros.append({"id": d["key"], "vector": d["vector_afinidad"]})
    return libros


def cargar_estudiantes(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(linea) for linea in f]


# ---------------------------------------------------------------------------
# NDCG
# ---------------------------------------------------------------------------

def ndcg_at_k(resultados_binarios):
    """resultados_binarios: lista de 0/1 en el orden de recomendación (posición 1 primero)."""
    dcg = sum(r / math.log2(i + 2) for i, r in enumerate(resultados_binarios))
    m = int(sum(resultados_binarios))
    idcg = sum(1.0 / math.log2(i + 2) for i in range(m))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Una corrida independiente de un sistema
# ---------------------------------------------------------------------------

class EjecucionSistema:
    """
    Corrida independiente del protocolo de la sección 5.1 para UN sistema
    (B1, B2 o "completo") sobre una cohorte y catálogo dados.
    """

    def __init__(self, nombre, recomendador, catalogo, estudiantes, k=10, semilla=42):
        assert nombre in ("B1", "B2", "completo")
        self.nombre = nombre
        self.recomendador = recomendador
        self.catalogo = catalogo
        self.libros_por_id = {l["id"]: l["vector"] for l in catalogo}
        self.todos_los_ids = [l["id"] for l in catalogo]
        self.estudiantes = {e["id"]: e for e in estudiantes}
        self.k = k
        self.rng = random.Random(semilla)

        self.aceptados = defaultdict(set)              # estudiante_id -> {libro_id}
        self.historial_svd = []                          # para MotorSVD (B2 / completo)
        self.recomendados_acumulado = set()
        self.recomendados_acumulado_por_arquetipo = defaultdict(set)

        self.metricas_por_ronda = []

    def _candidatos_para(self, estudiante_id):
        excluidos = self.aceptados[estudiante_id]
        return [lid for lid in self.todos_los_ids if lid not in excluidos]

    def _generar_recomendaciones(self, estudiante):
        eid = estudiante["id"]
        candidatos_ids = self._candidatos_para(eid)

        if self.nombre == "B1":
            return self.recomendador.top_k(candidatos_ids, k=self.k)
        elif self.nombre == "B2":
            return self.recomendador.top_k(eid, candidatos_ids, k=self.k)
        else:  # "completo"
            candidatos_con_vector = [(lid, self.libros_por_id[lid]) for lid in candidatos_ids]
            recs, _metodo = self.recomendador.recomendar(
                eid, estudiante["vector_afinidad"], candidatos_con_vector, k=self.k
            )
            return recs

    def _registrar_resultado(self, estudiante, libro_id, aceptado):
        eid = estudiante["id"]
        reward = 1.0 if aceptado else 0.0
        if aceptado:
            self.aceptados[eid].add(libro_id)
        self.historial_svd.append({"estudiante_id": eid, "libro_id": libro_id, "rating": reward})

        if self.nombre == "B1":
            self.recomendador.actualizar(libro_id, reward)
        elif self.nombre == "completo":
            vector_libro = self.libros_por_id[libro_id]
            self.recomendador.registrar_interaccion(eid, estudiante["vector_afinidad"], vector_libro, reward)
        # B2 no tiene actualización incremental por interacción -- se reentrena en bloque

    def correr_ronda(self, t):
        estudiantes_activos = [e for e in self.estudiantes.values() if e["ronda_ingreso"] <= t]
        registros_ronda = []  # (estudiante, [resultados binarios en orden], recs)

        for estudiante in estudiantes_activos:
            recs = self._generar_recomendaciones(estudiante)
            resultados = []
            for libro_id in recs:
                vector_libro = self.libros_por_id[libro_id]
                aceptado, _p = funcion_aceptacion(estudiante["vector_afinidad"], vector_libro, rng=self.rng)
                self._registrar_resultado(estudiante, libro_id, aceptado)
                resultados.append(1 if aceptado else 0)

            self.recomendados_acumulado.update(recs)
            self.recomendados_acumulado_por_arquetipo[estudiante["arquetipo"]].update(recs)
            registros_ronda.append((estudiante, resultados, recs))

        # Reentrenar al final de la ronda (sección 5.1)
        if self.nombre == "B2":
            self.recomendador.entrenar(self.historial_svd)
        elif self.nombre == "completo":
            self.recomendador.entrenar_svd(self.historial_svd)

        metricas = self._calcular_metricas(t, registros_ronda)
        self.metricas_por_ronda.append(metricas)
        return metricas

    def _calcular_metricas(self, t, registros_ronda):
        def agregados(sub):
            precisiones, ndcgs = [], []
            for _est, resultados, _recs in sub:
                if not resultados:
                    continue
                precisiones.append(sum(resultados) / len(resultados))
                ndcgs.append(ndcg_at_k(resultados))
            precision = sum(precisiones) / len(precisiones) if precisiones else None
            ndcg = sum(ndcgs) / len(ndcgs) if ndcgs else None
            return precision, ndcg

        precision_global, ndcg_global = agregados(registros_ronda)
        cobertura_global = len(self.recomendados_acumulado) / len(self.todos_los_ids)

        por_arquetipo = {}
        for arquetipo in ARQUETIPOS:
            sub = [r for r in registros_ronda if r[0]["arquetipo"] == arquetipo]
            p, n = agregados(sub)
            cobertura_arq = len(self.recomendados_acumulado_por_arquetipo[arquetipo]) / len(self.todos_los_ids)
            por_arquetipo[arquetipo] = {
                "precision_at_10": p,
                "ndcg_at_10": n,
                "cobertura": cobertura_arq,
                "n_estudiantes_activos": len(sub),
            }

        return {
            "ronda": t,
            "n_estudiantes_activos": len(registros_ronda),
            "precision_at_10": precision_global,
            "ndcg_at_10": ndcg_global,
            "cobertura": cobertura_global,
            "por_arquetipo": por_arquetipo,
        }


# ---------------------------------------------------------------------------
# Orquestación: las 3 simulaciones independientes
# ---------------------------------------------------------------------------

def correr_simulacion(catalogo, estudiantes, T, n_umbral, k=10, semilla=42):
    """
    Corre B1, B2 y Sistema completo como 3 simulaciones INDEPENDIENTES
    (decisión #1 del módulo) sobre la misma cohorte/catálogo iniciales.
    Devuelve (resultados, ejecuciones):
        resultados: {"B1": [metricas_ronda_1, ...], "B2": [...], "completo": [...]}
        ejecuciones: {"B1": EjecucionSistema, ...} -- por si se necesita inspeccionar estado interno
    """
    ejecuciones = {
        "B1": EjecucionSistema("B1", BaselinePopularidad(), catalogo, estudiantes, k=k, semilla=semilla),
        "B2": EjecucionSistema(
            "B2", BaselineSVDIngenuo(rng=random.Random(semilla)), catalogo, estudiantes, k=k, semilla=semilla
        ),
        "completo": EjecucionSistema(
            "completo", SistemaCompleto(n_umbral=n_umbral), catalogo, estudiantes, k=k, semilla=semilla
        ),
    }

    resultados = {nombre: [] for nombre in ejecuciones}
    for t in range(1, T + 1):
        for nombre, ejecucion in ejecuciones.items():
            resultados[nombre].append(ejecucion.correr_ronda(t))
    return resultados, ejecuciones
