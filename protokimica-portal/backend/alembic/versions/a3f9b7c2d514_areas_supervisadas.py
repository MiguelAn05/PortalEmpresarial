"""Usuarios: las áreas que supervisa cada persona

Revision ID: a3f9b7c2d514
Revises: f7a2c4e81b39
Create Date: 2026-09-16

El portal filtra por área exacta, así que un director que responde por varias
áreas —Dirección Técnica sobre IDI y Salvak— no vería nada de su gente. Aquí
quedan las áreas que cada persona supervisa **además** de la suya.

Es de una sola vía: el jefe ve hacia abajo y el equipo sigue viendo solo su
área. Nace vacía para todo el mundo, así que nadie cambia de alcance hasta
que un administrador lo configure.
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f9b7c2d514"
down_revision = "f7a2c4e81b39"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usuario_areas_supervisadas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "usuario_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("area", sa.String(length=100), nullable=False),
        sa.UniqueConstraint("usuario_id", "area", name="uq_area_supervisada"),
    )
    op.create_index(
        "ix_usuario_areas_supervisadas_usuario_id",
        "usuario_areas_supervisadas", ["usuario_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_usuario_areas_supervisadas_usuario_id",
                  table_name="usuario_areas_supervisadas")
    op.drop_table("usuario_areas_supervisadas")
