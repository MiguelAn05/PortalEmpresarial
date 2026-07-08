"""
Conexión a PostgreSQL vía SQLAlchemy.
Toda la app (PQRS, Indicadores, Proyectos...) usa el mismo engine y la misma Base.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    Dependency de FastAPI: abre una sesión de BD por request y la cierra al terminar.
    Se usa en cada router así: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
