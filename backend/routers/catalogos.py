from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from pydantic import BaseModel

router = APIRouter(prefix="/catalogos", tags=["catalogos"])

class CatalogoCreate(BaseModel):
    nombre: str
    creador: int

@router.post("/")
def crear_catalogo(catalogo: CatalogoCreate, db: Session = Depends(get_db)):
    nuevo = models.Catalogo(**catalogo.dict())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/")
def listar_catalogos(db: Session = Depends(get_db)):
    return db.query(models.Catalogo).all()

@router.get("/{catalogo_id}")
def obtener_catalogo(catalogo_id: int, db: Session = Depends(get_db)):
    catalogo = db.query(models.Catalogo).filter(models.Catalogo.id == catalogo_id).first()
    if not catalogo:
        raise HTTPException(status_code=404, detail="Catálogo no encontrado")
    return catalogo