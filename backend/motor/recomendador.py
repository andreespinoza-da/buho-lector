from sqlalchemy.orm import Session
import models

def generar_recomendaciones(estudiante_id: int, catalogo_id: int, db: Session):
    # Obtener libros del catálogo
    entradas = db.query(models.CatalogoLibro).filter(
        models.CatalogoLibro.catalogo_id == catalogo_id
    ).all()
    libro_ids = [e.libro_id for e in entradas]

    # Obtener historial del estudiante
    historial = db.query(models.EstudianteLibro).filter(
        models.EstudianteLibro.estudiante_id == estudiante_id
    ).all()
    leidos = [h.libro_id for h in historial]

    # Filtrar libros no leídos
    candidatos = [lid for lid in libro_ids if lid not in leidos]

    # Popularidad: contar cuántos estudiantes tienen cada libro en su historial
    popularidad = {}
    for lid in candidatos:
        count = db.query(models.EstudianteLibro).filter(
            models.EstudianteLibro.libro_id == lid
        ).count()
        popularidad[lid] = count

    # Ordenar por popularidad
    ordenados = sorted(candidatos, key=lambda lid: popularidad[lid], reverse=True)
    top10 = ordenados[:10]

    return top10