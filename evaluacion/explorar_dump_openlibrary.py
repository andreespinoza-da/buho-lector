"""
explorar_dump_openlibrary.py

Explora los dumps de Open Library (works + editions) SIN descomprimirlos
por completo. Filtra una muestra de libros relevantes (infantil/juvenil),
cruza contra el dump de editions para obtener el idioma REAL (no heurística
basada en subjects), y genera un reporte de qué subjects aparecen con más
frecuencia, para resolver las decisiones pendientes de la especificación
(número de géneros, cobertura real, tratamiento de libros sin género).

POR QUÉ SE NECESITAN DOS DUMPS:
El campo 'languages' casi nunca está poblado en el dump de WORKS -- vive en
el dump de EDITIONS, y cada edition referencia a su work mediante el campo
'works' (lista de objetos con 'key', ej. {"key": "/works/OL18417W"}).
Por eso este script ahora opera en DOS PASADAS:

  PASADA 1 (sobre works):    filtra works juveniles, guarda su 'key' y subjects.
  PASADA 2 (sobre editions):  para cada edition, mira su 'works[].key' -- si
                               coincide con un work de la Pasada 1, extrae el
                               idioma real de esa edition y lo asocia al work.

USO:
    python explorar_dump_openlibrary.py ol_dump_works_latest.txt.gz ol_dump_editions_latest.txt.gz

    (el segundo argumento es opcional -- si se omite, el script hace solo
    la Pasada 1 y avisa que el idioma no pudo verificarse)

SALIDA:
    - muestra_libros.jsonl        -> muestra de libros filtrados, con idioma real si se cruzó
    - reporte_subjects.txt        -> ranking de subjects más frecuentes en la muestra
    - reporte_idiomas.txt         -> ranking de idiomas reales encontrados (Pasada 2)
    - resumen.txt                 -> conteos generales

NOTA: el dump de works tiene ~10-12 millones de líneas; el de editions es
considerablemente más pesado (~9 GB comprimido, decenas de millones de
líneas). Este script NO carga ningún dump completo en memoria -- lee línea
por línea directamente desde el .gz. Para una primera exploración, ambas
pasadas se limitan a un número máximo de líneas escaneadas (parámetros
MAX_LINEAS_ESCANEAR_WORKS / MAX_LINEAS_ESCANEAR_EDITIONS) para que termine
en minutos, no en horas. Subir esos números una vez se sepa que el filtro
funciona bien.
"""

import gzip
import json
import sys
from collections import Counter

# ---------------------------------------------------------------------------
# CONFIGURACIÓN -- ajustar según se necesite
# ---------------------------------------------------------------------------

MAX_LINEAS_ESCANEAR_WORKS = 999_999_999_999
MAX_LINEAS_ESCANEAR_EDITIONS = 999_999_999_999
MAX_LIBROS_EN_MUESTRA = 3000                # tope de libros guardados en la muestra
MIN_OCURRENCIAS_PARA_REPORTE = 10           # un subject debe aparecer >= N veces para listarse

# Palabras clave que sugieren audiencia infantil/juvenil en el campo subjects
# (Open Library usa estas etiquetas de forma relativamente consistente)
PALABRAS_CLAVE_JUVENIL = [
    "juvenile fiction",
    "juvenile literature",
    "children's stories",
    "children's literature",
    "young adult fiction",
    "juvenile",
]

# Códigos de idioma español tal como aparecen en el campo 'languages' de
# un EDITION (no de un work -- ahí casi nunca está poblado)
CODIGOS_ESPANOL = {"spa", "/languages/spa"}


def es_juvenil(subjects):
    """True si algún subject contiene una palabra clave de audiencia juvenil."""
    texto = " ".join(s.lower() for s in subjects)
    return any(palabra in texto for palabra in PALABRAS_CLAVE_JUVENIL)


def extraer_subjects(record):
    """Devuelve la lista de subjects de un work, normalizada a texto plano."""
    subjects = record.get("subjects", [])
    out = []
    for s in subjects:
        if isinstance(s, str):
            out.append(s.strip())
        elif isinstance(s, dict) and "value" in s:
            out.append(str(s["value"]).strip())
    return out


def extraer_codigos_idioma(record):
    """
    Devuelve un set de códigos de idioma (ej. {'eng', 'spa'}) a partir del
    campo 'languages' de un EDITION. El formato típico es:
        "languages": [{"key": "/languages/eng"}]
    """
    codigos = set()
    for lang in record.get("languages", []):
        key = lang.get("key", "") if isinstance(lang, dict) else str(lang)
        codigo = key.rsplit("/", 1)[-1] if key else ""
        if codigo:
            codigos.add(codigo)
    return codigos


def extraer_work_keys(record):
    """
    Devuelve el set de work keys (ej. {'/works/OL18417W'}) que referencia
    un EDITION mediante su campo 'works'.
    """
    keys = set()
    for w in record.get("works", []):
        key = w.get("key", "") if isinstance(w, dict) else str(w)
        if key:
            keys.add(key)
    return keys


def pasada_1_works(ruta_works):
    """
    Escanea el dump de WORKS, filtra los que parecen juveniles por subjects,
    y devuelve:
        - works_filtrados: dict {work_key: {title, subjects}}
        - contador_subjects: Counter de subjects normalizados (lowercase)
        - stats: dict con conteos generales de esta pasada
    """
    works_filtrados = {}
    contador_subjects = Counter()

    total_lineas = 0
    total_con_subjects = 0
    total_juvenil = 0
    errores_json = 0

    print(f"[Pasada 1/2] Escaneando hasta {MAX_LINEAS_ESCANEAR_WORKS:,} líneas de {ruta_works} ...")

    with gzip.open(ruta_works, "rt", encoding="utf-8") as f:
        for linea in f:
            total_lineas += 1
            if total_lineas > MAX_LINEAS_ESCANEAR_WORKS:
                break

            if total_lineas % 200_000 == 0:
                print(f"  ... {total_lineas:,} líneas procesadas (works)")

            partes = linea.rstrip("\n").split("\t")
            if len(partes) != 5:
                continue

            tipo, key, revision, last_modified, json_str = partes

            try:
                record = json.loads(json_str)
            except json.JSONDecodeError:
                errores_json += 1
                continue

            subjects = extraer_subjects(record)
            if not subjects:
                continue
            total_con_subjects += 1

            if not es_juvenil(subjects):
                continue
            total_juvenil += 1

            for s in subjects:
                contador_subjects[s.lower()] += 1

            if len(works_filtrados) < MAX_LIBROS_EN_MUESTRA:
                works_filtrados[key] = {
                    "title": record.get("title", ""),
                    "subjects": subjects,
                }

    stats = {
        "total_lineas_works": total_lineas,
        "errores_json_works": errores_json,
        "total_con_subjects": total_con_subjects,
        "total_juvenil": total_juvenil,
    }
    return works_filtrados, contador_subjects, stats


def pasada_2_editions(ruta_editions, works_filtrados):
    """
    Escanea el dump de EDITIONS. Para cada edition, si referencia a uno de
    los works_filtrados (Pasada 1), extrae sus códigos de idioma reales y
    los asocia a ese work.

    Devuelve:
        - idiomas_por_work: dict {work_key: set(codigos_idioma)}
        - contador_idiomas: Counter de códigos de idioma encontrados
        - stats: dict con conteos generales de esta pasada
    """
    idiomas_por_work = {}
    contador_idiomas = Counter()

    total_lineas = 0
    total_con_works_ref = 0
    total_matches = 0
    errores_json = 0

    print(f"\n[Pasada 2/2] Escaneando hasta {MAX_LINEAS_ESCANEAR_EDITIONS:,} líneas de {ruta_editions} ...")
    print("(este dump es más pesado -- puede tardar más que la pasada 1)\n")

    with gzip.open(ruta_editions, "rt", encoding="utf-8") as f:
        for linea in f:
            total_lineas += 1
            if total_lineas > MAX_LINEAS_ESCANEAR_EDITIONS:
                break

            if total_lineas % 500_000 == 0:
                print(f"  ... {total_lineas:,} líneas procesadas (editions)")

            partes = linea.rstrip("\n").split("\t")
            if len(partes) != 5:
                continue

            tipo, key, revision, last_modified, json_str = partes

            try:
                record = json.loads(json_str)
            except json.JSONDecodeError:
                errores_json += 1
                continue

            work_keys = extraer_work_keys(record)
            if not work_keys:
                continue
            total_con_works_ref += 1

            # ¿Alguno de los works que referencia esta edition está en nuestro filtro?
            coincidencias = work_keys & works_filtrados.keys()
            if not coincidencias:
                continue
            total_matches += 1

            codigos = extraer_codigos_idioma(record)
            for codigo in codigos:
                contador_idiomas[codigo] += 1

            for wk in coincidencias:
                idiomas_por_work.setdefault(wk, set()).update(codigos)

    stats = {
        "total_lineas_editions": total_lineas,
        "errores_json_editions": errores_json,
        "total_con_works_ref": total_con_works_ref,
        "total_matches": total_matches,
    }
    return idiomas_por_work, contador_idiomas, stats


def main():
    if len(sys.argv) < 2:
        print("Uso:")
        print("  python explorar_dump_openlibrary.py ol_dump_works_latest.txt.gz")
        print("  python explorar_dump_openlibrary.py ol_dump_works_latest.txt.gz ol_dump_editions_latest.txt.gz")
        sys.exit(1)

    ruta_works = sys.argv[1]
    ruta_editions = sys.argv[2] if len(sys.argv) > 2 else None

    # --- Pasada 1: works ---
    works_filtrados, contador_subjects, stats_works = pasada_1_works(ruta_works)

    print(f"\n[Pasada 1 completa] {len(works_filtrados):,} works juveniles guardados en memoria.")

    # --- Pasada 2: editions (opcional) ---
    idiomas_por_work = {}
    contador_idiomas = Counter()
    stats_editions = None

    if ruta_editions:
        idiomas_por_work, contador_idiomas, stats_editions = pasada_2_editions(ruta_editions, works_filtrados)
        print(f"\n[Pasada 2 completa] Idioma real encontrado para {len(idiomas_por_work):,} works.")
    else:
        print("\n[Aviso] No se proporcionó dump de editions -- el idioma real NO se verificará.")
        print("        Vuelve a correr el script con el segundo argumento cuando tengas ese archivo.")

    # -----------------------------------------------------------------------
    # Construir la muestra final, con idioma real si está disponible
    # -----------------------------------------------------------------------
    muestra = []
    total_espanol_real = 0

    for work_key, datos in works_filtrados.items():
        codigos_idioma = sorted(idiomas_por_work.get(work_key, set()))
        es_espanol_real = bool(idiomas_por_work.get(work_key, set()) & CODIGOS_ESPANOL)
        if es_espanol_real:
            total_espanol_real += 1

        muestra.append({
            "key": work_key,
            "title": datos["title"],
            "subjects": datos["subjects"],
            "idiomas_reales": codigos_idioma,
            "es_espanol_real": es_espanol_real,
            "idioma_verificado": ruta_editions is not None,
        })

    # -----------------------------------------------------------------------
    # Guardar muestra de libros
    # -----------------------------------------------------------------------
    with open("muestra_libros.jsonl", "w", encoding="utf-8") as out:
        for libro in muestra:
            out.write(json.dumps(libro, ensure_ascii=False) + "\n")

    # -----------------------------------------------------------------------
    # Guardar reporte de subjects más frecuentes
    # -----------------------------------------------------------------------
    with open("reporte_subjects.txt", "w", encoding="utf-8") as out:
        out.write("SUBJECTS MÁS FRECUENTES EN LIBROS JUVENILES\n")
        out.write("=" * 60 + "\n\n")
        for subject, count in contador_subjects.most_common():
            if count >= MIN_OCURRENCIAS_PARA_REPORTE:
                out.write(f"{count:>8}  {subject}\n")

    # -----------------------------------------------------------------------
    # Guardar reporte de idiomas reales (solo si se hizo la Pasada 2)
    # -----------------------------------------------------------------------
    with open("reporte_idiomas.txt", "w", encoding="utf-8") as out:
        out.write("IDIOMAS REALES ENCONTRADOS (cruce con dump de editions)\n")
        out.write("=" * 60 + "\n\n")
        if ruta_editions:
            for codigo, count in contador_idiomas.most_common():
                out.write(f"{count:>8}  {codigo}\n")
        else:
            out.write("(No se ejecutó la Pasada 2 -- no se proporcionó dump de editions)\n")

    # -----------------------------------------------------------------------
    # Resumen general
    # -----------------------------------------------------------------------
    with open("resumen.txt", "w", encoding="utf-8") as out:
        out.write("RESUMEN DE EXPLORACIÓN DEL DUMP\n")
        out.write("=" * 60 + "\n")
        out.write("-- Pasada 1 (works) --\n")
        out.write(f"Líneas escaneadas (works):           {stats_works['total_lineas_works']:,}\n")
        out.write(f"Errores de parseo JSON (works):       {stats_works['errores_json_works']:,}\n")
        out.write(f"Works con al menos un subject:        {stats_works['total_con_subjects']:,}\n")
        out.write(f"Works marcados como juvenil:          {stats_works['total_juvenil']:,}\n")
        out.write(f"Subjects distintos (en el filtro):    {len(contador_subjects):,}\n")
        out.write(f"Libros guardados en muestra_libros.jsonl: {len(muestra):,}\n")

        if ruta_editions and stats_editions:
            out.write("\n-- Pasada 2 (editions) --\n")
            out.write(f"Líneas escaneadas (editions):         {stats_editions['total_lineas_editions']:,}\n")
            out.write(f"Errores de parseo JSON (editions):    {stats_editions['errores_json_editions']:,}\n")
            out.write(f"Editions con referencia a un work:    {stats_editions['total_con_works_ref']:,}\n")
            out.write(f"Editions que coinciden con la muestra: {stats_editions['total_matches']:,}\n")
            out.write(f"Works con idioma real verificado:     {len(idiomas_por_work):,}\n")
            out.write(f"Works en ESPAÑOL (idioma real):       {total_espanol_real:,}\n")
        else:
            out.write("\n-- Pasada 2 (editions) --\n")
            out.write("NO EJECUTADA. El idioma de los libros en muestra_libros.jsonl\n")
            out.write("quedó sin verificar (campo 'idioma_verificado': false).\n")
            out.write("Vuelve a correr el script pasando el dump de editions como\n")
            out.write("segundo argumento para resolver esto.\n")

    print("\n--- Listo ---")
    print(f"Works juveniles encontrados:     {len(works_filtrados):,}")
    if ruta_editions:
        print(f"Works con idioma verificado:      {len(idiomas_por_work):,}")
        print(f"Works en español (real):         {total_espanol_real:,}")
    print("\nArchivos generados:")
    print("  - muestra_libros.jsonl   (libros filtrados, uno por línea)")
    print("  - reporte_subjects.txt   (ranking de subjects más frecuentes)")
    print("  - reporte_idiomas.txt    (ranking de idiomas reales, si se cruzó con editions)")
    print("  - resumen.txt            (conteos generales de ambas pasadas)")


if __name__ == "__main__":
    main()
