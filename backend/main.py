from fastapi import FastAPI
from database import engine, Base
import models
from routers import usuarios, catalogos, libros, recomendaciones
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Búho Lector")
app.include_router(usuarios.router)
app.include_router(catalogos.router)
app.include_router(libros.router)
app.include_router(recomendaciones.router)

app.mount("/static", StaticFiles(directory="../frontend"), name="static")

@app.get("/app")
def frontend():
    return FileResponse("../frontend/index.html")

@app.get("/")
def root():
    return {"mensaje": "Búho Lector API funcionando"}