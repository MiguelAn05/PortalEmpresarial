"""master planner: una tarea ya no necesita proyecto

- `mp_tareas.proyecto_id` y `mp_historial.proyecto_id` pasan a aceptar nulo:
  una tarea suelta (el cierre contable del mes, un documento que se aprueba)
  no tiene por qué inventarse un proyecto.
- `mp_tareas.tenant_id`: hasta ahora la empresa de una tarea se sabía por su
  proyecto. Sin proyecto hace falta guardarla, y se llena desde el proyecto
  para las que ya existen.
- `mp_tareas.creado_por`: quien crea una tarea suelta la sigue viendo aunque
  se la asigne a otro. Las que ya existen quedan sin autor (nulo): sus
  proyectos ya deciden quién las ve.

Revision ID: d4e8b1f6a2c9
Revises: c7f1a9d3e582
Create Date: 2026-10-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e8b1f6a2c9'
down_revision = 'c7f1a9d3e582'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('mp_tareas', sa.Column('tenant_id', sa.Integer(), sa.ForeignKey('tenants.id'), nullable=True))
    op.add_column('mp_tareas', sa.Column('creado_por', sa.Integer(), sa.ForeignKey('users.id'), nullable=True))
    op.execute(
        "UPDATE mp_tareas SET tenant_id = p.tenant_id "
        "FROM mp_proyectos p WHERE p.id = mp_tareas.proyecto_id"
    )
    op.alter_column('mp_tareas', 'tenant_id', nullable=False)
    op.create_index('ix_mp_tareas_tenant_id', 'mp_tareas', ['tenant_id'])

    op.alter_column('mp_tareas', 'proyecto_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('mp_historial', 'proyecto_id', existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Volver atrás exige que toda tarea tenga proyecto: las sueltas se
    # perderían, así que se niega en vez de borrarlas en silencio.
    sueltas = op.get_bind().execute(
        sa.text("SELECT count(*) FROM mp_tareas WHERE proyecto_id IS NULL")
    ).scalar()
    if sueltas:
        raise RuntimeError(
            f"Hay {sueltas} tareas sin proyecto. Asígnales uno antes de bajar esta migración."
        )
    op.execute("DELETE FROM mp_historial WHERE proyecto_id IS NULL")
    op.alter_column('mp_historial', 'proyecto_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('mp_tareas', 'proyecto_id', existing_type=sa.Integer(), nullable=False)
    op.drop_index('ix_mp_tareas_tenant_id', table_name='mp_tareas')
    op.drop_column('mp_tareas', 'creado_por')
    op.drop_column('mp_tareas', 'tenant_id')
