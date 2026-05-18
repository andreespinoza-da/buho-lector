from fastapi import FastAPI
from database import engine, Base
import models
from routers import usuarios, catalogos, libros, recomendaciones

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Búho Lector")
app.include_router(usuarios.router)
app.include_router(catalogos.router)
app.include_router(libros.router)
app.include_router(recomendaciones.router)

@app.get("/")
def root():
    return {"mensaje": "Búho Lector API funcionando"}