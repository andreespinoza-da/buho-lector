"""
seed.py
Puebla la base de datos de Búho Lector con datos de prueba.
Ejecutar desde la raíz del proyecto: python seed.py

Requisitos:
  - Backend configurado (.env con DATABASE_URL)
  - openlibrary.py en el mismo directorio
  - pip install httpx
"""

import random
import time
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database import engine
import models
from openlibrary import buscar_libro

random.seed(42)  # reproducibilidad


# ── DATOS BASE ────────────────────────────────────────────────────────────────

NOMBRES = [
    "Andrés", "Camila", "Diego", "Valeria", "Sebastián", "Gabriela",
    "Mateo", "Isabella", "Santiago", "Daniela", "Emilio", "Sofía",
    "Nicolás", "Luciana", "Ricardo", "Fernanda", "Joaquín", "Natalia",
    "Alejandro", "Paula", "Cristóbal", "Mariana", "Felipe", "Verónica",
    "Rafael", "Carolina", "Esteban", "Melissa", "Iván", "Karina",
    "Luis", "Patricia", "Carlos", "Andrea", "Javier", "Mónica",
    "Eduardo", "Lorena", "Miguel", "Vanessa", "Pablo", "Stephanie",
    "David", "Priscila", "Jorge", "Estefanía", "Álvaro", "Claudia",
    "Rodrigo", "Diana",
]

APELLIDOS = [
    "García", "Rodríguez", "Martínez", "López", "González", "Pérez",
    "Sánchez", "Ramírez", "Torres", "Flores", "Rivera", "Gómez",
    "Díaz", "Reyes", "Cruz", "Morales", "Ortiz", "Herrera",
    "Medina", "Castillo", "Vargas", "Ramos", "Jiménez", "Moreno",
    "Álvarez", "Romero", "Suárez", "Vega", "Mendoza", "Ruiz",
    "Aguirre", "Cabrera", "Paredes", "Espinosa", "Guerrero", "Salinas",
    "Ríos", "Ponce", "Naranjo", "Muñoz", "Andrade", "Cevallos",
    "Zambrano", "Carrillo", "Villacís", "Benítez", "Coronel", "Delgado",
    "Enríquez", "Freire",
]

CIUDADES_ECUADOR = [
    ("Quito", "Ecuador"),
    ("Guayaquil", "Ecuador"),
    ("Cuenca", "Ecuador"),
    ("Ambato", "Ecuador"),
    ("Riobamba", "Ecuador"),
    ("Loja", "Ecuador"),
    ("Ibarra", "Ecuador"),
    ("Esmeraldas", "Ecuador"),
    ("Portoviejo", "Ecuador"),
    ("Machala", "Ecuador"),
]

EDAD_POR_GRADO = {8: (12, 13), 9: (13, 14), 10: (14, 15)}

LIBROS = [
    # Literatura ecuatoriana y andina
    ("Huasipungo", "Jorge Icaza"),
    ("Cumandá", "Juan León Mera"),
    ("Baldomera", "Alfredo Pareja Diezcanseco"),
    ("Aves sin nido", "Clorinda Matto de Turner"),
    ("El chulla Romero y Flores", "Jorge Icaza"),
    ("Las cruces sobre el agua", "Joaquín Gallegos Lara"),
    ("Siete lunas y siete serpientes", "Demetrio Aguilera Malta"),
    ("El éxodo de Yangana", "Ángel Felicísimo Rojas"),
    ("Plata y bronce", "Fernando Chaves"),
    ("Media vida deslumbrados", "José de la Cuadra"),
    ("Un hombre muerto a puntapiés", "Pablo Palacio"),
    ("Débora", "Pablo Palacio"),
    ("La emancipada", "Miguel Riofrío"),
    ("El mundo es ancho y ajeno", "Ciro Alegría"),
    ("Los ríos profundos", "José María Arguedas"),
    ("El zorro de arriba y el zorro de abajo", "José María Arguedas"),
    ("Tungsteno", "César Vallejo"),
    ("El señor presidente", "Miguel Ángel Asturias"),
    # Literatura latinoamericana — boom y clásicos
    ("Cien años de soledad", "Gabriel García Márquez"),
    ("Crónica de una muerte anunciada", "Gabriel García Márquez"),
    ("El amor en los tiempos del cólera", "Gabriel García Márquez"),
    ("El coronel no tiene quien le escriba", "Gabriel García Márquez"),
    ("La casa de los espíritus", "Isabel Allende"),
    ("Eva Luna", "Isabel Allende"),
    ("Rayuela", "Julio Cortázar"),
    ("Bestiario", "Julio Cortázar"),
    ("Pedro Páramo", "Juan Rulfo"),
    ("El llano en llamas", "Juan Rulfo"),
    ("La ciudad y los perros", "Mario Vargas Llosa"),
    ("La fiesta del chivo", "Mario Vargas Llosa"),
    ("Ficciones", "Jorge Luis Borges"),
    ("El Aleph", "Jorge Luis Borges"),
    ("El túnel", "Ernesto Sabato"),
    ("Sobre héroes y tumbas", "Ernesto Sabato"),
    ("La vorágine", "José Eustasio Rivera"),
    ("Doña Bárbara", "Rómulo Gallegos"),
    ("María", "Jorge Isaacs"),
    ("Don Segundo Sombra", "Ricardo Güiraldes"),
    ("Martín Fierro", "José Hernández"),
    ("La tía Julia y el escribidor", "Mario Vargas Llosa"),
    ("El laberinto de la soledad", "Octavio Paz"),
    # Poesía latinoamericana
    ("Veinte poemas de amor y una canción desesperada", "Pablo Neruda"),
    ("Canto general", "Pablo Neruda"),
    ("Residencia en la tierra", "Pablo Neruda"),
    ("Poemas humanos", "César Vallejo"),
    ("Los heraldos negros", "César Vallejo"),
    ("Altazor", "Vicente Huidobro"),
    ("Obra poética", "Gabriela Mistral"),
    ("Poeta en Nueva York", "Federico García Lorca"),
    # Literatura española
    ("Don Quijote de la Mancha", "Miguel de Cervantes"),
    ("La Celestina", "Fernando de Rojas"),
    ("Lazarillo de Tormes", "Anónimo"),
    ("Bodas de sangre", "Federico García Lorca"),
    ("La casa de Bernarda Alba", "Federico García Lorca"),
    ("Yerma", "Federico García Lorca"),
    ("Niebla", "Miguel de Unamuno"),
    ("San Manuel Bueno mártir", "Miguel de Unamuno"),
    ("Nada", "Carmen Laforet"),
    ("El camino", "Miguel Delibes"),
    ("La familia de Pascual Duarte", "Camilo José Cela"),
    ("Platero y yo", "Juan Ramón Jiménez"),
    ("Rimas y leyendas", "Gustavo Adolfo Bécquer"),
    ("El árbol de la ciencia", "Pío Baroja"),
    ("Fortunata y Jacinta", "Benito Pérez Galdós"),
    # Literatura universal — clásicos
    ("El principito", "Antoine de Saint-Exupéry"),
    ("Romeo y Julieta", "William Shakespeare"),
    ("Hamlet", "William Shakespeare"),
    ("Macbeth", "William Shakespeare"),
    ("Otelo", "William Shakespeare"),
    ("La Odisea", "Homero"),
    ("La Ilíada", "Homero"),
    ("Los miserables", "Victor Hugo"),
    ("El conde de Montecristo", "Alexandre Dumas"),
    ("Los tres mosqueteros", "Alexandre Dumas"),
    ("Crimen y castigo", "Fiódor Dostoyevski"),
    ("El idiota", "Fiódor Dostoyevski"),
    ("Anna Karenina", "León Tolstói"),
    ("El proceso", "Franz Kafka"),
    ("La metamorfosis", "Franz Kafka"),
    ("Madame Bovary", "Gustave Flaubert"),
    ("Grandes esperanzas", "Charles Dickens"),
    ("Oliver Twist", "Charles Dickens"),
    ("Jane Eyre", "Charlotte Brontë"),
    ("Cumbres borrascosas", "Emily Brontë"),
    ("Orgullo y prejuicio", "Jane Austen"),
    ("Sentido y sensibilidad", "Jane Austen"),
    ("La letra escarlata", "Nathaniel Hawthorne"),
    ("Moby Dick", "Herman Melville"),
    ("Las aventuras de Huckleberry Finn", "Mark Twain"),
    # Literatura de aventuras
    ("La isla del tesoro", "Robert Louis Stevenson"),
    ("El extraño caso del Dr. Jekyll y Mr. Hyde", "Robert Louis Stevenson"),
    ("Robinson Crusoe", "Daniel Defoe"),
    ("Viaje al centro de la Tierra", "Jules Verne"),
    ("Veinte mil leguas de viaje submarino", "Jules Verne"),
    ("La vuelta al mundo en 80 días", "Jules Verne"),
    ("El libro de la selva", "Rudyard Kipling"),
    ("El llamado de lo salvaje", "Jack London"),
    ("Colmillo Blanco", "Jack London"),
    ("Sandokán", "Emilio Salgari"),
    # Ciencia ficción y distopía
    ("1984", "George Orwell"),
    ("Rebelión en la granja", "George Orwell"),
    ("Un mundo feliz", "Aldous Huxley"),
    ("Fahrenheit 451", "Ray Bradbury"),
    ("Crónicas marcianas", "Ray Bradbury"),
    ("Fundación", "Isaac Asimov"),
    ("Yo robot", "Isaac Asimov"),
    ("2001 Una odisea del espacio", "Arthur C. Clarke"),
    ("La guerra de los mundos", "H.G. Wells"),
    ("La máquina del tiempo", "H.G. Wells"),
    ("El hombre invisible", "H.G. Wells"),
    # Misterio y terror
    ("Frankenstein", "Mary Shelley"),
    ("Drácula", "Bram Stoker"),
    ("El retrato de Dorian Gray", "Oscar Wilde"),
    ("El sabueso de los Baskerville", "Arthur Conan Doyle"),
    ("Cuentos de lo grotesco y arabesco", "Edgar Allan Poe"),
    ("Asesinato en el Orient Express", "Agatha Christie"),
    ("Diez negritos", "Agatha Christie"),
    ("Rebecca", "Daphne du Maurier"),
    ("El nombre de la rosa", "Umberto Eco"),
    ("El Club Dumas", "Arturo Pérez-Reverte"),
    ("La tabla de Flandes", "Arturo Pérez-Reverte"),
    # Literatura juvenil — clásicos
    ("El guardián entre el centeno", "J.D. Salinger"),
    ("El diario de Ana Frank", "Ana Frank"),
    ("Matar a un ruiseñor", "Harper Lee"),
    ("El viejo y el mar", "Ernest Hemingway"),
    ("El señor de las moscas", "William Golding"),
    ("El alquimista", "Paulo Coelho"),
    ("Siddhartha", "Hermann Hesse"),
    ("Demian", "Hermann Hesse"),
    ("Alicia en el País de las Maravillas", "Lewis Carroll"),
    ("Momo", "Michael Ende"),
    ("La historia interminable", "Michael Ende"),
    ("El hobbit", "J.R.R. Tolkien"),
    ("Manolito Gafotas", "Elvira Lindo"),
    ("Memorias de Idhún", "Laura Gallego García"),
    # No ficción y ensayo
    ("Ética para Amador", "Fernando Savater"),
    ("Política para Amador", "Fernando Savater"),
    ("El mundo de Sofía", "Jostein Gaarder"),
    ("Una breve historia del tiempo", "Stephen Hawking"),
    ("Sapiens", "Yuval Noah Harari"),
    ("Me llamo Rigoberta Menchú", "Rigoberta Menchú"),
    ("El hombre en busca de sentido", "Viktor Frankl"),
    ("Mi planta de naranja lima", "José Mauro de Vasconcelos"),
    ("Carta a un joven novelista", "Mario Vargas Llosa"),
    # Literatura contemporánea
    ("El perfume", "Patrick Süskind"),
    ("El nombre del viento", "Patrick Rothfuss"),
    ("La sombra del viento", "Carlos Ruiz Zafón"),
    ("Tokio blues", "Haruki Murakami"),
    ("Kafka en la orilla", "Haruki Murakami"),
    ("El código Da Vinci", "Dan Brown"),
    ("Ángeles y demonios", "Dan Brown"),
    ("Charlie y la fábrica de chocolate", "Roald Dahl"),
    ("Las brujas", "Roald Dahl"),
    ("El gran cuaderno", "Ágota Kristóf"),
]


# ── HELPERS ───────────────────────────────────────────────────────────────────

def nombre_aleatorio() -> str:
    return f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}"

def ciudad_aleatoria() -> tuple[str, str]:
    return random.choice(CIUDADES_ECUADOR)


# ── LIMPIEZA ──────────────────────────────────────────────────────────────────

def limpiar_tablas(db: Session):
    print("Limpiando tablas...")
    db.query(models.RecomendacionesHistorial).delete()
    db.query(models.Recomendaciones).delete()
    db.query(models.EstudianteLibro).delete()
    db.query(models.EstudianteClase).delete()
    db.query(models.ClaseCatalogo).delete()
    db.query(models.CatalogoLibro).delete()
    db.query(models.Catalogo).delete()
    db.query(models.Clase).delete()
    db.query(models.Conexiones).delete()
    db.query(models.Libro).delete()
    db.query(models.Usuario).delete()
    db.commit()
    print("  Tablas limpias.")


# ── USUARIOS ──────────────────────────────────────────────────────────────────

def crear_usuarios(db: Session) -> tuple[list, list]:
    print("Creando usuarios...")
    profesores = []
    estudiantes = []

    for _ in range(3):
        ciudad, pais = ciudad_aleatoria()
        prof = models.Usuario(
            nombre=nombre_aleatorio(),
            edad=random.randint(28, 55),
            grado_escolar=0,
            ciudad=ciudad,
            pais=pais,
            rol="administrador",
        )
        db.add(prof)
        profesores.append(prof)

    grados = [8] * 34 + [9] * 33 + [10] * 33
    random.shuffle(grados)

    for grado in grados:
        ciudad, pais = ciudad_aleatoria()
        edad_min, edad_max = EDAD_POR_GRADO[grado]
        est = models.Usuario(
            nombre=nombre_aleatorio(),
            edad=random.randint(edad_min, edad_max),
            grado_escolar=grado,
            ciudad=ciudad,
            pais=pais,
            rol="estudiante",
        )
        db.add(est)
        estudiantes.append(est)

    db.commit()
    for p in profesores:
        db.refresh(p)
    for e in estudiantes:
        db.refresh(e)

    print(f"  {len(profesores)} profesores, {len(estudiantes)} estudiantes creados.")
    return profesores, estudiantes


# ── CLASES ────────────────────────────────────────────────────────────────────

def crear_clases(db: Session, profesores: list) -> list:
    print("Creando clases...")
    definiciones = [
        (profesores[0], "8vo A"),
        (profesores[0], "8vo B"),
        (profesores[1], "9no A"),
        (profesores[1], "10mo A"),
        (profesores[2], "9no B"),
    ]
    clases = []
    for prof, nombre in definiciones:
        clase = models.Clase(nombre=nombre, prof=prof.id)
        db.add(clase)
        clases.append(clase)

    db.commit()
    for c in clases:
        db.refresh(c)

    print(f"  {len(clases)} clases creadas.")
    return clases


# ── CATÁLOGO ──────────────────────────────────────────────────────────────────

def crear_catalogo(db: Session, profesores: list) -> models.Catalogo:
    print("Creando catálogo...")
    catalogo = models.Catalogo(
        nombre="Biblioteca del Colegio",
        creador=profesores[0].id,
    )
    db.add(catalogo)
    db.commit()
    db.refresh(catalogo)
    print(f"  Catálogo '{catalogo.nombre}' (id={catalogo.id}) creado.")
    return catalogo


# ── LIBROS ────────────────────────────────────────────────────────────────────

def crear_libros(db: Session, catalogo: models.Catalogo) -> list:
    print(f"Consultando Open Library y creando {len(LIBROS)} libros...")
    libros_creados = []
    isbns_vistos = set()

    for i, (titulo, autor) in enumerate(LIBROS, 1):
        print(f"  [{i}/{len(LIBROS)}] {titulo}")
        datos = buscar_libro(titulo, autor)

        if datos is None:
            datos = {
                "titulo": titulo,
                "autor": autor,
                "sinopsis": None,
                "portada": None,
                "paginas": None,
                "generos": None,
                "ISBN": None,
                "fuente": "manual",
            }

        isbn = datos.get("ISBN")
        if isbn and isbn in isbns_vistos:
            datos["ISBN"] = None
        elif isbn:
            isbns_vistos.add(isbn)

        libro = models.Libro(**datos)
        db.add(libro)
        db.flush()

        cl = models.CatalogoLibro(catalogo_id=catalogo.id, libro_id=libro.id)
        db.add(cl)
        libros_creados.append(libro)

        time.sleep(0.3)

    db.commit()
    for l in libros_creados:
        db.refresh(l)

    print(f"  {len(libros_creados)} libros insertados.")
    return libros_creados


# ── RELACIONES CLASE ──────────────────────────────────────────────────────────

def asignar_catalogo_a_clases(db: Session, clases: list, catalogo: models.Catalogo):
    print("Asignando catálogo a clases...")
    for clase in clases:
        cc = models.ClaseCatalogo(clase_id=clase.id, catalogo_id=catalogo.id)
        db.add(cc)
    db.commit()
    print(f"  Catálogo asignado a {len(clases)} clases.")


def asignar_estudiantes_a_clases(db: Session, clases: list, estudiantes: list):
    print("Asignando estudiantes a clases...")
    clases_8  = [c for c in clases if "8vo"  in c.nombre]
    clases_9  = [c for c in clases if "9no"  in c.nombre]
    clases_10 = [c for c in clases if "10mo" in c.nombre]

    for est in estudiantes:
        if est.grado_escolar == 8:
            clase = random.choice(clases_8)
        elif est.grado_escolar == 9:
            clase = random.choice(clases_9)
        else:
            clase = random.choice(clases_10)

        ec = models.EstudianteClase(estudiante_id=est.id, clase_id=clase.id)
        db.add(ec)

    db.commit()
    print(f"  {len(estudiantes)} estudiantes asignados.")


# ── HISTORIAL DE LECTURA ──────────────────────────────────────────────────────

def crear_historial(db: Session, estudiantes: list, libros: list):
    print("Generando historial de lectura...")
    total = 0

    for est in estudiantes:
        grado = est.grado_escolar

        if grado in (9, 10):
            n = random.randint(8, 20)
            for libro in random.sample(libros, min(n, len(libros))):
                db.add(models.EstudianteLibro(
                    estudiante_id=est.id,
                    libro_id=libro.id,
                    estado="leido",
                ))
                total += 1

        elif grado == 8 and random.random() < 0.5:
            n = random.randint(3, 10)
            for libro in random.sample(libros, min(n, len(libros))):
                db.add(models.EstudianteLibro(
                    estudiante_id=est.id,
                    libro_id=libro.id,
                    estado="leido",
                ))
                total += 1

    db.commit()
    print(f"  {total} registros de historial creados.")


# ── MAIN ──────────────────────────────────────────────────────────────────────

def main():
    print("=" * 50)
    print("Búho Lector — Seed")
    print("=" * 50)

    with Session(engine) as db:
        limpiar_tablas(db)
        profesores, estudiantes = crear_usuarios(db)
        clases = crear_clases(db, profesores)
        catalogo = crear_catalogo(db, profesores)
        libros = crear_libros(db, catalogo)
        asignar_catalogo_a_clases(db, clases, catalogo)
        asignar_estudiantes_a_clases(db, clases, estudiantes)
        crear_historial(db, estudiantes, libros)

    print("=" * 50)
    print("Seed completado.")
    print("=" * 50)


if __name__ == "__main__":
    main()
