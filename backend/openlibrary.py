"""
openlibrary.py
Cliente reutilizable para consultar la Open Library API.
Usado por seed.py y disponible para el backend en producción.
"""

import httpx
import time

BASE_URL = "https://openlibrary.org"


def buscar_libro(titulo: str, autor: str, reintentos: int = 3) -> dict | None:
    """
    Busca un libro en Open Library por título y autor.
    Devuelve un dict con los campos del modelo Libro, o None si no se encuentra.
    """
    params = {
        "title":  titulo,
        "author": autor,
        "limit":  1,
        "fields": "title,author_name,isbn,cover_i,number_of_pages_median,subject,first_sentence",
    }

    for intento in range(reintentos):
        try:
            response = httpx.get(
                f"{BASE_URL}/search.json",
                params=params,
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()

            docs = data.get("docs", [])
            if not docs:
                print(f"  [!] No encontrado: {titulo} — {autor}")
                return None

            doc = docs[0]
            return _parsear_doc(doc, titulo, autor)

        except httpx.TimeoutException:
            print(f"  [timeout] Reintento {intento + 1}/{reintentos}: {titulo}")
            time.sleep(2 ** intento)  # backoff exponencial
        except httpx.HTTPError as e:
            print(f"  [error HTTP] {e}: {titulo}")
            time.sleep(2 ** intento)

    print(f"  [fallo] No se pudo obtener: {titulo} — {autor}")
    return None


def _parsear_doc(doc: dict, titulo_original: str, autor_original: str) -> dict:
    """Extrae y normaliza los campos relevantes de un documento de Open Library."""

    # ISBN — tomar el primero disponible
    isbns = doc.get("isbn", [])
    isbn = isbns[0] if isbns else None

    # Portada — construir URL si hay cover_i
    cover_i = doc.get("cover_i")
    portada = f"https://covers.openlibrary.org/b/id/{cover_i}-L.jpg" if cover_i else None

    # Sinopsis — first_sentence viene como dict o string según la edición
    first_sentence = doc.get("first_sentence")
    if isinstance(first_sentence, dict):
        sinopsis = first_sentence.get("value", "")
    elif isinstance(first_sentence, str):
        sinopsis = first_sentence
    else:
        sinopsis = None

    # Géneros — subjects, limitado a los 3 primeros para no saturar el campo
    subjects = doc.get("subject", [])
    generos = ", ".join(subjects[:3]) if subjects else None

    return {
        "titulo":  doc.get("title", titulo_original),
        "autor":   ", ".join(doc.get("author_name", [autor_original])),
        "sinopsis": sinopsis,
        "portada": portada,
        "paginas": doc.get("number_of_pages_median"),
        "generos": generos,
        "ISBN":    isbn,
        "fuente":  "openlibrary",
    }
