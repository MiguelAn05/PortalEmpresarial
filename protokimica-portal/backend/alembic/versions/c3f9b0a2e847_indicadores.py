"""modulo de indicadores: definiciones, mediciones e historial

Revision ID: c3f9b0a2e847
Revises: b8e15a2c7d94
Create Date: 2026-08-03 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c3f9b0a2e847'
down_revision = 'b8e15a2c7d94'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'ind_indicadores',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(length=200), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('formula_texto', sa.Text(), nullable=True),
        sa.Column('unidad', sa.String(length=20), nullable=False),
        sa.Column('tipo_captura', sa.String(length=20), nullable=False),
        sa.Column('fuente_automatica', sa.String(length=60), nullable=True),
        sa.Column('etiqueta_numerador', sa.String(length=120), nullable=True),
        sa.Column('etiqueta_denominador', sa.String(length=120), nullable=True),
        sa.Column('area', sa.String(length=100), nullable=True),
        sa.Column('responsable_id', sa.Integer(), nullable=True),
        sa.Column('meta', sa.Numeric(14, 2), nullable=True),
        sa.Column('direccion', sa.String(length=10), nullable=False),
        sa.Column('umbral_verde', sa.Numeric(14, 2), nullable=True),
        sa.Column('umbral_amarillo', sa.Numeric(14, 2), nullable=True),
        sa.Column('requiere_evidencia', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('orden', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.ForeignKeyConstraint(['responsable_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ind_indicadores_id'), 'ind_indicadores', ['id'])
    op.create_index(op.f('ix_ind_indicadores_tenant_id'), 'ind_indicadores', ['tenant_id'])

    op.create_table(
        'ind_mediciones',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('indicador_id', sa.Integer(), nullable=False),
        sa.Column('anio', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('valor', sa.Numeric(16, 4), nullable=True),
        sa.Column('numerador', sa.Numeric(16, 4), nullable=True),
        sa.Column('denominador', sa.Numeric(16, 4), nullable=True),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('evidencia', sa.String(length=255), nullable=True),
        sa.Column('registrado_por', sa.Integer(), nullable=True),
        sa.Column('registrado_en', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        # Preparadas para un futuro flujo de validación; hoy nadie las escribe.
        sa.Column('validado_por', sa.Integer(), nullable=True),
        sa.Column('validado_en', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['indicador_id'], ['ind_indicadores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['registrado_por'], ['users.id']),
        sa.ForeignKeyConstraint(['validado_por'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        # Un solo valor por indicador y mes: si se corrige, se actualiza el
        # existente y el cambio queda en ind_historial.
        sa.UniqueConstraint('indicador_id', 'anio', 'mes', name='uq_medicion_periodo'),
    )
    op.create_index(op.f('ix_ind_mediciones_id'), 'ind_mediciones', ['id'])
    op.create_index(op.f('ix_ind_mediciones_indicador_id'), 'ind_mediciones', ['indicador_id'])

    op.create_table(
        'ind_historial',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('indicador_id', sa.Integer(), nullable=False),
        sa.Column('anio', sa.Integer(), nullable=False),
        sa.Column('mes', sa.Integer(), nullable=False),
        sa.Column('valor_anterior', sa.Numeric(16, 4), nullable=True),
        sa.Column('valor_nuevo', sa.Numeric(16, 4), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), nullable=True),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['indicador_id'], ['ind_indicadores.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ind_historial_id'), 'ind_historial', ['id'])
    op.create_index(op.f('ix_ind_historial_indicador_id'), 'ind_historial', ['indicador_id'])


def downgrade() -> None:
    op.drop_table('ind_historial')
    op.drop_table('ind_mediciones')
    op.drop_table('ind_indicadores')
