"""master planner: historial de cambios, presupuesto ejecutado y fecha de cierre de tarea

Revision ID: a4d7f30c9e21
Revises: f2c8e91d4b60
Create Date: 2026-08-02 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a4d7f30c9e21'
down_revision = 'f2c8e91d4b60'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ejecución presupuestal: lo planeado ya existía (valor_unitario × cantidad),
    # faltaba con qué compararlo.
    op.add_column(
        'mp_items_presupuesto',
        sa.Column('valor_ejecutado', sa.Numeric(14, 2), nullable=False, server_default='0'),
    )

    # Sin esta fecha no se puede calcular cumplimiento: hay que saber CUÁNDO se
    # completó una tarea para compararlo contra su fecha de fin comprometida.
    op.add_column(
        'mp_tareas',
        sa.Column('fecha_completada', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'mp_historial',
        sa.Column('id', sa.Integer(), nullable=False),
        # 'proyecto' | 'tarea' — una sola tabla para los dos, porque el
        # historial se lee siempre igual y así no se duplica la lógica.
        sa.Column('entidad', sa.String(length=20), nullable=False),
        sa.Column('entidad_id', sa.Integer(), nullable=False),
        # Nombre de la tarea/proyecto al momento del cambio. Denormalizado a
        # propósito: el historial tiene que seguir leyéndose aunque después
        # se renombre o se borre la tarea.
        sa.Column('entidad_nombre', sa.String(length=200), nullable=True),
        sa.Column('proyecto_id', sa.Integer(), nullable=False),
        sa.Column('campo', sa.String(length=50), nullable=False),
        sa.Column('valor_anterior', sa.Text(), nullable=True),
        sa.Column('valor_nuevo', sa.Text(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['proyecto_id'], ['mp_proyectos.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mp_historial_id'), 'mp_historial', ['id'])
    op.create_index(op.f('ix_mp_historial_proyecto_id'), 'mp_historial', ['proyecto_id'])
    # El índice compuesto es el que importa: la consulta real siempre es
    # "dame el historial de ESTA tarea" o "de ESTE proyecto".
    op.create_index('ix_mp_historial_entidad', 'mp_historial', ['entidad', 'entidad_id'])


def downgrade() -> None:
    op.drop_index('ix_mp_historial_entidad', table_name='mp_historial')
    op.drop_index(op.f('ix_mp_historial_proyecto_id'), table_name='mp_historial')
    op.drop_index(op.f('ix_mp_historial_id'), table_name='mp_historial')
    op.drop_table('mp_historial')
    op.drop_column('mp_tareas', 'fecha_completada')
    op.drop_column('mp_items_presupuesto', 'valor_ejecutado')
