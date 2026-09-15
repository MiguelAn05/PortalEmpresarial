"""OMP: la fecha original comprometida de cada acción del plan

Revision ID: f7a2c4e81b39
Revises: e1b7c3d9a2f4
Create Date: 2026-09-15

El indicador «Gestión de OMP» mide si las acciones se cumplen a tiempo. Si
midiera contra `fecha_limite`, bastaría con correr la fecha para cumplir,
así que se guarda aparte la primera fecha comprometida.

Las acciones existentes toman su fecha actual como original: no hay forma
de saber si ya se habían aplazado, y es preferible a dejarlas sin fecha de
referencia.
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a2c4e81b39"
down_revision = "e1b7c3d9a2f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "omp_acciones",
        sa.Column("fecha_limite_original", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE omp_acciones SET fecha_limite_original = fecha_limite")


def downgrade() -> None:
    op.drop_column("omp_acciones", "fecha_limite_original")
