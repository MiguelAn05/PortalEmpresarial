"""Capacidades otorgadas

Revision ID: b3d81e9f2c47
Revises: a7f3e2b81c04
Create Date: 2026-09-05

Fase 1 del sistema de permisos por capacidad (ver core/capacidades.py).

Hoy "quién autoriza notas crédito" o "quién cierra una PQRS" vive en una
constante de Python repetida en cinco módulos, y la única excepción posible
es cambiarle el área a una persona — con lo que le das también todo lo demás
que esa área decide en otros módulos. Esta tabla reemplaza esa constante por
un otorgamiento explícito: a un ÁREA (lo normal, se hereda solo) o a una
PERSONA (la excepción, con quién y cuándo la dio).

Esta migración SOLO crea la tabla. No toca ningún permiso existente: los
cinco módulos siguen con su constante de siempre hasta que cada uno migre
por separado, con su propia prueba comparativa demostrando que nadie perdió
un permiso en el camino.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3d81e9f2c47"
down_revision = "a7f3e2b81c04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "capacidades_otorgadas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("capacidad", sa.String(length=60), nullable=False),
        sa.Column("area", sa.String(length=100), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("otorgada_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("otorgada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint(
            "(area IS NOT NULL) != (usuario_id IS NOT NULL)",
            name="ck_capacidad_area_xor_usuario",
        ),
    )
    op.create_index("ix_capacidades_otorgadas_tenant_id", "capacidades_otorgadas", ["tenant_id"])
    op.create_index("ix_capacidades_otorgadas_capacidad", "capacidades_otorgadas", ["capacidad"])


def downgrade() -> None:
    op.drop_index("ix_capacidades_otorgadas_capacidad", table_name="capacidades_otorgadas")
    op.drop_index("ix_capacidades_otorgadas_tenant_id", table_name="capacidades_otorgadas")
    op.drop_table("capacidades_otorgadas")
