from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
import models
from pydantic import BaseModel

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

class UsuarioCreate(BaseModel):
    nombre: str
    edad: int
    grado_escolar: int
    ciudad: str
    pais: str
    rol: str

@router.post("/")
def crear_usuario(usuario: UsuarioCreate, db: Session = Depends(get_db)):
    nuevo = models.Usuario(**usuario.dict())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo

@router.get("/")
def listar_usuarios(db: Session = Depends(get_db)):
    return db.query(models.Usuario).all()

@router.get("/{usuario_id}")
def obtener_usuario(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    return usuario

@router.get("/{usuario_id}/catalogos")
def obtener_catalogos_estudiante(usuario_id: int, db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if usuario.rol != "estudiante":
        raise HTTPException(status_code=400, detail="El usuario no es estudiante")

    clases = db.query(models.EstudianteClase).filter(
        models.EstudianteClase.estudiante_id == usuario_id
    ).all()

    clase_ids = [ec.clase_id for ec in clases]

    catalogos = db.query(models.Catalogo).join(
        models.ClaseCatalogo,
        models.Catalogo.id == models.ClaseCatalogo.catalogo_id
    ).filter(
        models.ClaseCatalogo.clase_id.in_(clase_ids)
    ).all()

    return catalogos