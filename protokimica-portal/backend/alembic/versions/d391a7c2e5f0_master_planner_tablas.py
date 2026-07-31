"""master planner: proyectos, presupuesto, tareas

Revision ID: d391a7c2e5f0
Revises: c7a1f4e8b2d3
Create Date: 2026-07-30 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd391a7c2e5f0'
down_revision = 'c7a1f4e8b2d3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mp_proyectos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('objetivo', sa.Text(), nullable=True),
        sa.Column('alcance', sa.Text(), nullable=True),
        sa.Column('lider_id', sa.Integer(), nullable=True),
        sa.Column('area', sa.String(length=100), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('prioridad', sa.String(length=20), nullable=False),
        sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_fin_estimada', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_fin_real', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['lider_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mp_proyectos_tenant_id'), 'mp_proyectos', ['tenant_id'])
    op.create_index(op.f('ix_mp_proyectos_id'), 'mp_proyectos', ['id'])

    op.create_table(
        'mp_items_presupuesto',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proyecto_id', sa.Integer(), nullable=False),
        sa.Column('concepto', sa.String(length=200), nullable=False),
        sa.Column('detalle', sa.String(length=300), nullable=True),
        sa.Column('valor_unitario', sa.Numeric(14, 2), nullable=False),
        sa.Column('cantidad', sa.Numeric(10, 2), nullable=False),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['proyecto_id'], ['mp_proyectos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mp_items_presupuesto_proyecto_id'), 'mp_items_presupuesto', ['proyecto_id'])
    op.create_index(op.f('ix_mp_items_presupuesto_id'), 'mp_items_presupuesto', ['id'])

    op.create_table(
        'mp_tareas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('proyecto_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('titulo', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('area', sa.String(length=100), nullable=True),
        sa.Column('asignado_a', sa.Integer(), nullable=True),
        sa.Column('estado', sa.String(length=20), nullable=False),
        sa.Column('prioridad', sa.String(length=20), nullable=False),
        sa.Column('avance_pct', sa.Integer(), nullable=False),
        sa.Column('riesgos', sa.Text(), nullable=True),
        sa.Column('fecha_inicio', sa.DateTime(timezone=True), nullable=True),
        sa.Column('fecha_fin', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['proyecto_id'], ['mp_proyectos.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['mp_tareas.id']),
        sa.ForeignKeyConstraint(['asignado_a'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mp_tareas_proyecto_id'), 'mp_tareas', ['proyecto_id'])
    op.create_index(op.f('ix_mp_tareas_parent_id'), 'mp_tareas', ['parent_id'])
    op.create_index(op.f('ix_mp_tareas_id'), 'mp_tareas', ['id'])

    op.create_table(
        'mp_tarea_actualizaciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tarea_id', sa.Integer(), nullable=False),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('avance_pct_nuevo', sa.Integer(), nullable=True),
        sa.Column('adjunto_evidencia', sa.String(length=255), nullable=True),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['tarea_id'], ['mp_tareas.id']),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_mp_tarea_actualizaciones_tarea_id'), 'mp_tarea_actualizaciones', ['tarea_id'])
    op.create_index(op.f('ix_mp_tarea_actualizaciones_id'), 'mp_tarea_actualizaciones', ['id'])


def downgrade() -> None:
    op.drop_table('mp_tarea_actualizaciones')
    op.drop_table('mp_tareas')
    op.drop_table('mp_items_presupuesto')
    op.drop_table('mp_proyectos')
