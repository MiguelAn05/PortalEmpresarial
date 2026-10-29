"""master planner: aprobación de documentos en una tarea

Una tarea puede pedir que su documento (PDF o Excel) lo aprueben otras
personas en orden antes de darse por cumplida:

- `mp_plantillas_revision` + `mp_plantilla_revision_pasos`: qué pasos tiene
  cada cadena («Revisión contable»: Contador → Revisora Fiscal). Se siembran
  solas al pedirlas.
- `mp_revision_pasos`: la cadena COPIADA a cada tarea, con quién firma.
- `mp_documento_versiones`: cada versión subida, con su estado.
- `mp_revision_eventos`: enviado, aprobado, devuelto.
- `mp_documento_observaciones`: lo que señala cada revisor, anclado a un
  punto de la página (PDF) o a una celda de una hoja (Excel).

Solo tablas nuevas: no toca filas existentes.

Revision ID: c7f1a9d3e582
Revises: b8e2d5f17c93
Create Date: 2026-10-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c7f1a9d3e582'
down_revision = 'b8e2d5f17c93'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'mp_plantillas_revision',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('activa', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_mp_plantillas_revision_id', 'mp_plantillas_revision', ['id'])
    op.create_index('ix_mp_plantillas_revision_tenant_id', 'mp_plantillas_revision', ['tenant_id'])

    op.create_table(
        'mp_plantilla_revision_pasos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('plantilla_id', sa.Integer(),
                  sa.ForeignKey('mp_plantillas_revision.id', ondelete='CASCADE'), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
    )
    op.create_index('ix_mp_plantilla_revision_pasos_id', 'mp_plantilla_revision_pasos', ['id'])
    op.create_index('ix_mp_plantilla_revision_pasos_plantilla_id', 'mp_plantilla_revision_pasos', ['plantilla_id'])

    op.create_table(
        'mp_revision_pasos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tarea_id', sa.Integer(), sa.ForeignKey('mp_tareas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False),
        sa.Column('nombre', sa.String(100), nullable=False),
        sa.Column('revisor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.UniqueConstraint('tarea_id', 'orden', name='uq_revision_paso_orden'),
    )
    op.create_index('ix_mp_revision_pasos_id', 'mp_revision_pasos', ['id'])
    op.create_index('ix_mp_revision_pasos_tarea_id', 'mp_revision_pasos', ['tarea_id'])
    op.create_index('ix_mp_revision_pasos_revisor_id', 'mp_revision_pasos', ['revisor_id'])

    op.create_table(
        'mp_documento_versiones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('tarea_id', sa.Integer(), sa.ForeignKey('mp_tareas.id', ondelete='CASCADE'), nullable=False),
        sa.Column('numero', sa.Integer(), nullable=False),
        sa.Column('nombre_original', sa.String(255), nullable=False),
        sa.Column('ruta', sa.String(255), nullable=False),
        sa.Column('tipo', sa.String(10), nullable=False),
        sa.Column('tamano', sa.Integer(), nullable=False),
        sa.Column('estado', sa.String(20), nullable=False),
        sa.Column('paso_actual', sa.Integer(), nullable=True),
        sa.Column('subido_por', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('subido_en', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('enviado_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('cerrado_en', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('tarea_id', 'numero', name='uq_documento_numero'),
    )
    op.create_index('ix_mp_documento_versiones_id', 'mp_documento_versiones', ['id'])
    op.create_index('ix_mp_documento_versiones_tarea_id', 'mp_documento_versiones', ['tarea_id'])

    op.create_table(
        'mp_revision_eventos',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('version_id', sa.Integer(),
                  sa.ForeignKey('mp_documento_versiones.id', ondelete='CASCADE'), nullable=False),
        sa.Column('accion', sa.String(20), nullable=False),
        sa.Column('paso_orden', sa.Integer(), nullable=True),
        sa.Column('paso_nombre', sa.String(100), nullable=True),
        sa.Column('comentario', sa.Text(), nullable=True),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('fecha', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_mp_revision_eventos_id', 'mp_revision_eventos', ['id'])
    op.create_index('ix_mp_revision_eventos_version_id', 'mp_revision_eventos', ['version_id'])

    op.create_table(
        'mp_documento_observaciones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('version_id', sa.Integer(),
                  sa.ForeignKey('mp_documento_versiones.id', ondelete='CASCADE'), nullable=False),
        sa.Column('usuario_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('paso_orden', sa.Integer(), nullable=True),
        sa.Column('paso_nombre', sa.String(100), nullable=True),
        sa.Column('pagina', sa.Integer(), nullable=True),
        sa.Column('pos_x', sa.Float(), nullable=True),
        sa.Column('pos_y', sa.Float(), nullable=True),
        sa.Column('hoja', sa.String(100), nullable=True),
        sa.Column('celda', sa.String(12), nullable=True),
        sa.Column('texto', sa.Text(), nullable=False),
        sa.Column('atendida', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('atendida_por', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('atendida_en', sa.DateTime(timezone=True), nullable=True),
        sa.Column('creado_en', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_mp_documento_observaciones_id', 'mp_documento_observaciones', ['id'])
    op.create_index('ix_mp_documento_observaciones_version_id', 'mp_documento_observaciones', ['version_id'])


def downgrade() -> None:
    op.drop_table('mp_documento_observaciones')
    op.drop_table('mp_revision_eventos')
    op.drop_table('mp_documento_versiones')
    op.drop_table('mp_revision_pasos')
    op.drop_table('mp_plantilla_revision_pasos')
    op.drop_table('mp_plantillas_revision')
