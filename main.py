import os
import csv
from typing import Annotated
from contextlib import asynccontextmanager
from datetime import datetime, date

from fastapi import Depends, FastAPI, HTTPException
from sqlmodel import Field, Session, SQLModel, create_engine, select
from dotenv import load_dotenv

# ============= MODELOS =============
class Confederations(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)

class Countries(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    confederation_id: int = Field(foreign_key="confederations.id")
    emoji: str = Field(default="🌍")

class Matches(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    home_team_id: int = Field(foreign_key="countries.id")
    away_team_id: int = Field(foreign_key="countries.id")
    home_team_score: int
    away_team_score: int
    date: datetime
    stage: str

# ============= CONFIGURACIÓN =============
load_dotenv()

postgresql_url = os.getenv("DATABASE_URL")

# ✅ Para PostgreSQL NO usamos connect_args
# check_same_thread es SOLO para SQLite
engine = create_engine(postgresql_url)

# ============= FUNCIONES DE BD =============
def create_db_and_tables():
    """Crea todas las tablas en la base de datos"""
    print("🔄 Creando tablas en la base de datos...")
    SQLModel.metadata.create_all(engine)
    print("✅ Tablas creadas exitosamente")

def load_countries_from_csv(csv_path: str = "data.csv"):
    """
    Lee el CSV y carga los países y confederaciones en la BD.
    CSV esperado:
        Country,Confederation,Emoji
        Algeria,CAF,🇦🇱
        Argentina,CONMEBOL,🇦🇷
    
    El campo Emoji es opcional (por defecto: 🌍)
    """
    if not os.path.exists(csv_path):
        print(f"⚠️  Advertencia: {csv_path} no encontrado. Saltando carga de datos.")
        return
    
    print(f"📥 Cargando datos desde {csv_path}...")
    
    with Session(engine) as session:
        confederations_map = {}
        
        # Primero, crear confederaciones únicas
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                confederation_name = row["Confederation"].strip()
                
                if confederation_name not in confederations_map:
                    existing = session.exec(
                        select(Confederations).where(
                            Confederations.name == confederation_name
                        )
                    ).first()
                    
                    if existing:
                        confederations_map[confederation_name] = existing.id
                    else:
                        new_confederation = Confederations(name=confederation_name)
                        session.add(new_confederation)
                        session.commit()
                        session.refresh(new_confederation)
                        confederations_map[confederation_name] = new_confederation.id
                        print(f"  ✓ Confederación creada: {confederation_name}")
        
        # Ahora, insertar países
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            for row in reader:
                country_name = row["Country"].strip()
                confederation_name = row["Confederation"].strip()
                emoji = row.get("Emoji", "🌍").strip() if "Emoji" in row else "🌍"
                
                existing_country = session.exec(
                    select(Countries).where(Countries.name == country_name)
                ).first()
                
                if not existing_country:
                    new_country = Countries(
                        name=country_name,
                        confederation_id=confederations_map[confederation_name],
                        emoji=emoji
                    )
                    session.add(new_country)
            
            session.commit()
        
        print(f"✅ Datos cargados desde {csv_path}")

def get_session():
    with Session(engine) as session:
        yield session

SessionDep = Annotated[Session, Depends(get_session)]

# ============= LIFESPAN (MODERNO) =============
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manejador de ciclo de vida para startup y shutdown"""
    # STARTUP
    create_db_and_tables()
    load_countries_from_csv("data.csv")
    yield
    # SHUTDOWN
    print("🛑 Aplicación cerrada")

# ============= APLICACIÓN =============
app = FastAPI(lifespan=lifespan)

# ============= ENDPOINTS =============

@app.post("/matches/")
def create_match(match: Matches, session: SessionDep) -> Matches:
    """Crear un nuevo partido"""
    session.add(match)
    session.commit()
    session.refresh(match)
    return match

@app.get("/countries/")
def list_countries(session: SessionDep) -> list[Countries]:
    """Listar todos los países con sus emojis"""
    countries = session.exec(select(Countries)).all()
    return countries

@app.get("/confederations/")
def list_confederations(session: SessionDep) -> list[Confederations]:
    """Listar todas las confederaciones"""
    confederations = session.exec(select(Confederations)).all()
    return confederations

@app.get("/countries/{country_id}")
def get_country(country_id: int, session: SessionDep) -> Countries:
    """Obtener un país específico con su emoji"""
    country = session.get(Countries, country_id)
    if not country:
        raise HTTPException(status_code=404, detail="País no encontrado")
    return country
@app.put("/matches/{match_id}")
def update_match(match_id: int, match_data: Matches, session: SessionDep) -> Matches:
    """Actualizar un partido existente"""
    match = session.get(Matches, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    
    match.home_team_id = match_data.home_team_id
    match.away_team_id = match_data.away_team_id
    match.home_team_score = match_data.home_team_score
    match.away_team_score = match_data.away_team_score
    match.date = match_data.date
    match.stage = match_data.stage
    
    session.add(match)
    session.commit()
    session.refresh(match)
    
    return match
@app.delete("/matches/{match_id}")
def delete_match(match_id: int, session: SessionDep):
    """Eliminar un partido existente"""
    match = session.get(Matches, match_id)
    if not match:
        raise HTTPException(status_code=404, detail="Partido no encontrado")
    
    session.delete(match)
    session.commit()
    
    return {"detail": "Partido eliminado exitosamente"}