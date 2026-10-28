"""avances de tarea: cuándo se corrigió el texto

`editado_en` marca que el comentario de un avance (o de una respuesta) se
corrigió. El texto anterior no va aquí: queda en `mp_historial`, como todo
cambio de una tarea.

Revision ID: e4b7c2a9f513
Revises: c5e8a1f2d740
Create Date: 2026-10-28 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e4b7c2a9f513'
down_revision = 'c5e8a1f2d740'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mp_tarea_actualizaciones',
                  sa.Column('editado_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('mp_tarea_actualizaciones', 'editado_en')
