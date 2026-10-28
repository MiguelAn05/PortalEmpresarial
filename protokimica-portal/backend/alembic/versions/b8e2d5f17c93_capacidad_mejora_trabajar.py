"""Servicio al Cliente entra a Oportunidades de Mejora

Siembra la capacidad `mejora.trabajar` para el área `Servicio al Cliente` de
cada empresa. Va en la migración y no solo en `sembrar_capacidades_iniciales`
porque esa siembra corre cuando alguien abre Administración › Capacidades: si
nadie la abre, el área seguiría sin entrar después de desplegar.

Revision ID: b8e2d5f17c93
Revises: a3d6f8c2e471
Create Date: 2026-10-28 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b8e2d5f17c93'
down_revision = 'a3d6f8c2e471'
branch_labels = None
depends_on = None

CAPACIDAD = "mejora.trabajar"
AREA = "Servicio al Cliente"


def upgrade() -> None:
    conexion = op.get_bind()
    # Un otorgamiento necesita quién lo otorgó: el admin más antiguo de cada
    # empresa, que es quien habría entrado a darlo a mano.
    for (tenant_id,) in conexion.execute(sa.text("SELECT id FROM tenants")).fetchall():
        admin = conexion.execute(sa.text(
            "SELECT id FROM users WHERE tenant_id = :t AND rol = 'admin' ORDER BY id LIMIT 1"
        ), {"t": tenant_id}).fetchone()
        if not admin:
            continue
        ya = conexion.execute(sa.text(
            "SELECT 1 FROM capacidades_otorgadas WHERE tenant_id = :t "
            "AND capacidad = :c AND area = :a"
        ), {"t": tenant_id, "c": CAPACIDAD, "a": AREA}).fetchone()
        if ya:
            continue
        conexion.execute(sa.text(
            "INSERT INTO capacidades_otorgadas (tenant_id, capacidad, area, otorgada_por) "
            "VALUES (:t, :c, :a, :por)"
        ), {"t": tenant_id, "c": CAPACIDAD, "a": AREA, "por": admin[0]})


def downgrade() -> None:
    op.get_bind().execute(sa.text(
        "DELETE FROM capacidades_otorgadas WHERE capacidad = :c AND area = :a"
    ), {"c": CAPACIDAD, "a": AREA})
