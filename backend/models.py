from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, ForeignKeyConstraint
from sqlalchemy.orm import relationship
from database import Base

class Usuario(Base):
    __tablename__ = "usuario"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    edad = Column(Integer)
    grado_escolar = Column(Integer)
    ciudad = Column(String)
    pais = Column(String)
    rol = Column(String)

class Clase(Base):
    __tablename__ = "clase"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    prof = Column(Integer, ForeignKey("usuario.id"))

class Catalogo(Base):
    __tablename__ = "catalogo"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String)
    creador = Column(Integer, ForeignKey("usuario.id"))

class Libro(Base):
    __tablename__ = "libro"
    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String)
    autor = Column(String)
    sinopsis = Column(String)
    portada = Column(String)
    paginas = Column(Integer)
    generos = Column(String)
    ISBN = Column(String, unique=True)
    fuente = Column(String)

class Conexiones(Base):
    __tablename__ = "conexiones"
    id = Column(Integer, primary_key=True, index=True)
    estudiante_id_1 = Column(Integer, ForeignKey("usuario.id"))
    estudiante_id_2 = Column(Integer, ForeignKey("usuario.id"))
    estado = Column(Integer)

class EstudianteLibro(Base):
    __tablename__ = "estudiante_libro"
    estudiante_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    libro_id = Column(Integer, ForeignKey("libro.id"), primary_key=True)
    estado = Column(String)

class Recomendaciones(Base):
    __tablename__ = "recomendaciones"
    estudiante_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    catalogo_id = Column(Integer, primary_key=True)
    libro_id = Column(Integer, primary_key=True)
    posicion = Column(Integer)
    fecha_generacion = Column(DateTime)
    __table_args__ = (
        ForeignKeyConstraint(
            ["catalogo_id", "libro_id"],
            ["catalogo_libro.catalogo_id", "catalogo_libro.libro_id"]
        ),
    )

class RecomendacionesHistorial(Base):
    __tablename__ = "recomendaciones_historial"
    estudiante_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    catalogo_id = Column(Integer, primary_key=True)
    libro_id = Column(Integer, primary_key=True)
    posicion = Column(Integer)
    fecha_generacion = Column(DateTime)
    version = Column(String)
    __table_args__ = (
        ForeignKeyConstraint(
            ["catalogo_id", "libro_id"],
            ["catalogo_libro.catalogo_id", "catalogo_libro.libro_id"]
        ),
    )

class EstudianteClase(Base):
    __tablename__ = "estudiante_clase"
    estudiante_id = Column(Integer, ForeignKey("usuario.id"), primary_key=True)
    clase_id = Column(Integer, ForeignKey("clase.id"), primary_key=True)

class ClaseCatalogo(Base):
    __tablename__ = "clase_catalogo"
    clase_id = Column(Integer, ForeignKey("clase.id"), primary_key=True)
    catalogo_id = Column(Integer, ForeignKey("catalogo.id"), primary_key=True)

class CatalogoLibro(Base):
    __tablename__ = "catalogo_libro"
    catalogo_id = Column(Integer, ForeignKey("catalogo.id"), primary_key=True)
    libro_id = Column(Integer, ForeignKey("libro.id"), primary_key=True)