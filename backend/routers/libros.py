from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/libros", tags=["libros"])

class LibroCreate(BaseModel):
    titulo: str
    autor: str
    sinopsis: str
    portada: Optional[str] = None
    paginas: int
    generos: str
    ISBN: Optional[str] = None
    fuente: str

@router.post("/")
def crear_libro(libro: LibroCreate, db: Session = Depends(get_db)):
    nuevo = models.Libro(**libro.dict())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/")
def listar_libros(db: Session = Depends(get_db)):
    return db.query(models.Libro).all()

@router.get("/{libro_id}")
def obtener_libro(libro_id: int, db: Session = Depends(get_db)):
    libro = db.query(models.Libro).filter(models.Libro.id == libro_id).first()
    if not libro:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return libro

@router.post("/{catalogo_id}/{libro_id}")
def agregar_libro_catalogo(catalogo_id: int, libro_id: int, db: Session = Depends(get_db)):
    entrada = models.CatalogoLibro(catalogo_id=catalogo_id, libro_id=libro_id)
    db.add(entrada)
    db.commit()
    return {"mensaje": "Libro agregado al catálogo"}

@router.get("/catalogo/{catalogo_id}")
def listar_libros_catalogo(catalogo_id: int, db: Session = Depends(get_db)):
    entradas = db.query(models.CatalogoLibro).filter(
        models.CatalogoLibro.catalogo_id == catalogo_id
    ).all()
    libro_ids = [e.libro_id for e in entradas]
    libros = db.query(models.Libro).filter(models.Libro.id.in_(libro_ids)).all()
    return libros