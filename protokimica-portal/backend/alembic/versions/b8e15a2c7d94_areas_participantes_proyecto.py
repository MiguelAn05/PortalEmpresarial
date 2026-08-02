"""master planner: áreas participantes de un proyecto

Un proyecto puede involucrar a varias áreas. `mp_proyectos.area` sigue
siendo el ÁREA RESPONSABLE (la dueña del presupuesto, para que los
totales por área no se dupliquen) y esta tabla guarda las áreas
adicionales que participan, que es lo que otorga visibilidad.

Revision ID: b8e15a2c7d94
Revises: a4d7f30c9e21
Create Date: 2026-08-02 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e15a2c7d94'
down_revision = 'a4d7f30c9e21'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mp_proyecto_areas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proyecto_id', sa.Integer(), nullable=False),
        sa.Column('area', sa.String(length=100), nullable=False),
        sa.ForeignKeyConstraint(['proyecto_id'], ['mp_proyectos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # Un área no puede estar dos veces en el mismo proyecto.
        sa.UniqueConstraint('proyecto_id', 'area', name='uq_mp_proyecto_area'),
    )
    op.create_index(op.f('ix_mp_proyecto_areas_proyecto_id'), 'mp_proyecto_areas', ['proyecto_id'])
    # La consulta caliente es la inversa: "qué proyectos ve alguien de esta área".
    op.create_index(op.f('ix_mp_proyecto_areas_area'), 'mp_proyecto_areas', ['area'])


def downgrade() -> None:
    op.drop_index(op.f('ix_mp_proyecto_areas_area'), table_name='mp_proyecto_areas')
    op.drop_index(op.f('ix_mp_proyecto_areas_proyecto_id'), table_name='mp_proyecto_areas')
    op.drop_table('mp_proyecto_areas')
