"""master planner: acta de cierre de proyectos

Guarda cómo terminó un proyecto —finalizado o cancelado— con sus entregables
o su motivo, y la foto de los números de ese momento.

Los números se congelan porque un acta dice lo que era verdad el día que se
firmó: si se recalcularan, dentro de seis meses mostraría otras cifras
porque alguien corrigió un pago viejo.

Revision ID: c7e2a91d5f38
Revises: b1d84f37c9e2
Create Date: 2026-08-13 15:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e2a91d5f38'
down_revision = 'b1d84f37c9e2'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mp_cierres',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proyecto_id', sa.Integer(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),

        sa.Column('entregables', sa.Text(), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('evidencia', sa.String(length=255), nullable=True),

        sa.Column('tareas_total', sa.Integer(), nullable=True),
        sa.Column('tareas_completadas', sa.Integer(), nullable=True),
        sa.Column('presupuesto_planeado', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('presupuesto_aprobado', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('presupuesto_pagado', sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column('dias_de_duracion', sa.Integer(), nullable=True),

        sa.Column('cerrado_por', sa.Integer(), nullable=True),
        sa.Column('cerrado_en', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('anulado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('anulado_por', sa.Integer(), nullable=True),

        sa.ForeignKeyConstraint(['proyecto_id'], ['mp_proyectos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cerrado_por'], ['users.id']),
        sa.ForeignKeyConstraint(['anulado_por'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_mp_cierres_proyecto_id', 'mp_cierres', ['proyecto_id'])


def downgrade() -> None:
    op.drop_table('mp_cierres')
