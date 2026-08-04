"""
Infraestructura compartida de las pruebas.

Todo corre contra la API real con TestClient y una base SQLite en memoria
(StaticPool para que todas las sesiones vean la misma). No se toca Postgres:
las pruebas tienen que poder correrse mil veces sin ensuciar nada.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from tests.verificador import Verificador

# Importar los modelos registra sus tablas en Base.metadata.
from app.models import pqrs, master_planner, indicadores, autorizacion  # noqa: F401


class Entorno:
    """
    Un portal recién instalado con usuarios de todos los roles, y la
    posibilidad de cambiar de usuario en mitad de la prueba con `como()`.
    """

    def __init__(self, client, Session, ids, tenant_id):
        self.client = client
        self.Session = Session
        self.ids = ids
        self.tenant_id = tenant_id
        self._actual = {"id": ids["admin"]}

    def como(self, quien: str) -> None:
        """Cambia el usuario autenticado: 'admin', 'gerencia', 'tics', ..."""
        if quien not in self.ids:
            raise KeyError(f"No existe el usuario de prueba '{quien}'. Hay: {sorted(self.ids)}")
        self._actual["id"] = self.ids[quien]

    @property
    def usuario_actual_id(self) -> int:
        return self._actual["id"]

    # Atajos: e.get(...) en vez de e.client.get(...)
    def get(self, *a, **k): return self.client.get(*a, **k)
    def post(self, *a, **k): return self.client.post(*a, **k)
    def patch(self, *a, **k): return self.client.patch(*a, **k)
    def delete(self, *a, **k): return self.client.delete(*a, **k)


USUARIOS = [
    # clave,       nombre,     rol,         area
    ("admin",     "Admin",     "admin",     "TICS"),
    ("gerencia",  "Gerente",   "gerencia",  None),
    ("tics",      "Tico",      "lider",     "TICS"),
    ("calidad",   "Cali",      "lider",     "Calidad"),
    ("logistica", "Logi",      "agente",    "Logística"),
    ("lectura",   "Lector",    "lectura",   "TICS"),
]


@pytest.fixture
def entorno():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)

    db = Session()
    tenant = Tenant(nombre="Protokimica", slug="protokimica")
    db.add(tenant)
    db.commit()

    ids = {}
    for clave, nombre, rol, area in USUARIOS:
        u = User(
            tenant_id=tenant.id, nombre=nombre, email=f"{clave}@p.com",
            password_hash="x", rol=rol, area=area, activo=True,
        )
        db.add(u)
        db.commit()
        ids[clave] = u.id
    tenant_id = tenant.id
    db.close()

    e = Entorno(None, Session, ids, tenant_id)
    app.dependency_overrides[get_db] = lambda: Session()
    app.dependency_overrides[get_current_user] = lambda: Session().get(User, e.usuario_actual_id)

    with TestClient(app) as client:
        e.client = client
        yield e

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def v():
    """Acumula comprobaciones y las reporta todas juntas al terminar."""
    verificador = Verificador()
    yield verificador
    verificador.listo()
