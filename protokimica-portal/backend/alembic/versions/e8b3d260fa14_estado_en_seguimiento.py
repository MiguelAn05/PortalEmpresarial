"""seguimiento de pqrs: a qué estado pasó

El historial que ve el cliente mostraba el comentario del seguimiento, que
es donde el área escribe sus notas internas. Con el estado guardado aparte,
la consulta pública redacta el movimiento por su cuenta y el comentario deja
de salir del portal.

Los seguimientos anteriores quedan sin estado (NULL) a propósito: no se puede
adivinar a qué estado pasó cada uno leyendo un texto libre, y suponerlo sería
peor que mostrar un rótulo genérico.

Revision ID: e8b3d260fa14
Revises: c7e2a91d5f38
Create Date: 2026-08-28 21:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8b3d260fa14'
down_revision = 'c7e2a91d5f38'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'pqrs_seguimientos',
        sa.Column('estado_nuevo', sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('pqrs_seguimientos', 'estado_nuevo')
