"""Módulos contratados por empresa

Revision ID: a6c2e9f41d07
Revises: f1a4d82be703
Create Date: 2026-10-01

El portal se vende por módulos: cada empresa abre solo los que tiene en
`tenant_modulos` (ver `core/modulos.py`). Una empresa sin filas tiene solo la
base —Inicio y Administración—, así que las que ya existen reciben aquí
TODOS los módulos: hasta hoy los usaban todos, y sin esta siembra el
despliegue les cerraría el portal entero.

La lista va escrita aquí y no importada de `CONTRATABLES`: una migración
describe el estado de un momento, y si mañana se agrega un módulo, esta no
tiene por qué regalárselo a nadie.
"""
from alembic import op
import sqlalchemy as sa

revision = "a6c2e9f41d07"
down_revision = "f1a4d82be703"
branch_labels = None
depends_on = None

MODULOS_EN_USO = (
    "pqrs", "notas_credito", "master_planner", "indicadores", "mejora", "encuestas",
)


def upgrade() -> None:
    op.create_table(
        "tenant_modulos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modulo", sa.String(40), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("desde", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "modulo", name="uq_tenant_modulo"),
    )
    op.create_index("ix_tenant_modulos_tenant_id", "tenant_modulos", ["tenant_id"])

    for modulo in MODULOS_EN_USO:
        op.execute(sa.text(
            "INSERT INTO tenant_modulos (tenant_id, modulo, activo) "
            "SELECT id, :modulo, true FROM tenants"
        ).bindparams(modulo=modulo))


def downgrade() -> None:
    op.drop_index("ix_tenant_modulos_tenant_id", table_name="tenant_modulos")
    op.drop_table("tenant_modulos")
