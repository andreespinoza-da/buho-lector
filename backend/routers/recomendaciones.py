from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
import models
from motor.recomendador import generar_recomendaciones
from datetime import datetime

router = APIRouter(prefix="/recomendaciones", tags=["recomendaciones"])

def actualizar_recomendaciones(estudiante_id: int, catalogo_id: int, db: Session):
    top10 = generar_recomendaciones(estudiante_id, catalogo_id, db)

    # Borrar lista operacional anterior
    db.query(models.Recomendaciones).filter(
        models.Recomendaciones.estudiante_id == estudiante_id
    ).delete()

    # Guardar nueva lista operacional
    for posicion, libro_id in enumerate(top10, start=1):
        rec = models.Recomendaciones(
            estudiante_id=estudiante_id,
            catalogo_id=catalogo_id,
            libro_id=libro_id,
            posicion=posicion,
            fecha_generacion=datetime.now()
        )
        db.add(rec)

    # Guardar en historial de auditoría
    version = datetime.now().strftime("%Y%m%d%H%M%S")
    for posicion, libro_id in enumerate(top10, start=1):
        hist = models.RecomendacionesHistorial(
            estudiante_id=estudiante_id,
            catalogo_id=catalogo_id,
            libro_id=libro_id,
            posicion=posicion,
            fecha_generacion=datetime.now(),
            version=version
        )
        db.add(hist)

    db.commit()

@router.post("/generar/{estudiante_id}/{catalogo_id}")
def generar(estudiante_id: int, catalogo_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(actualizar_recomendaciones, estudiante_id, catalogo_id, db)
    return {"mensaje": "Generando recomendaciones en segundo plano"}

@router.get("/{estudiante_id}")
def obtener_recomendaciones(estudiante_id: int, db: Session = Depends(get_db)):
    recs = db.query(models.Recomendaciones).filter(
        models.Recomendaciones.estudiante_id == estudiante_id
    ).order_by(models.Recomendaciones.posicion).all()
    return recs