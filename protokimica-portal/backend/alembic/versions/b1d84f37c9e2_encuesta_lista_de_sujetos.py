"""encuestas: lista cerrada de qué se califica

Para que el cliente elija el punto de venta de una lista en vez de
escribirlo. Con texto libre, "Centro", "centro" y "Sede Centro" entran como
tres lugares distintos y el reporte por punto deja de servir — y eso no se
arregla después, porque los datos ya entraron mal.

Revision ID: b1d84f37c9e2
Revises: a9c2e5f71b40
Create Date: 2026-08-10 17:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1d84f37c9e2'
down_revision = 'a9c2e5f71b40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('enc_plantillas', sa.Column('sujetos', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('enc_plantillas', 'sujetos')
