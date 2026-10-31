"""master planner: una observación del PDF puede ser un recuadro

`ancho` y `alto` en `mp_documento_observaciones`, como fracción de la página
igual que `pos_x`/`pos_y`. Nulos = la observación es un punto, que es lo que
son todas las anteriores.

Revision ID: e5a9c3d7b104
Revises: d4e8b1f6a2c9
Create Date: 2026-10-31 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e5a9c3d7b104'
down_revision = 'd4e8b1f6a2c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mp_documento_observaciones', sa.Column('ancho', sa.Float(), nullable=True))
    op.add_column('mp_documento_observaciones', sa.Column('alto', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('mp_documento_observaciones', 'alto')
    op.drop_column('mp_documento_observaciones', 'ancho')
