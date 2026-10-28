"""actividades diarias: cuánto toma cada vez

`mp_actividades.minutos_estimados` — cuánto le toma a la persona hacerla
cada vez que toca. Opcional: vacío es «no se sabe», nunca cero.

Revision ID: a3d6f8c2e471
Revises: e4b7c2a9f513
Create Date: 2026-10-28 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3d6f8c2e471'
down_revision = 'e4b7c2a9f513'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mp_actividades', sa.Column('minutos_estimados', sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column('mp_actividades', 'minutos_estimados')
