"""tarea: id del evento de outlook

Guarda el id que devuelve Microsoft Graph al crear el evento de una tarea
en el calendario del responsable. Es lo que permite mover o borrar ESE
evento después, en vez de ir dejando duplicados en la agenda de la gente
cada vez que alguien corrige una fecha.

Revision ID: d4f81c60a7e3
Revises: c5a71e3b9d82
Create Date: 2026-08-10 09:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd4f81c60a7e3'
down_revision = 'c5a71e3b9d82'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'mp_tareas',
        sa.Column('outlook_evento_id', sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('mp_tareas', 'outlook_evento_id')
