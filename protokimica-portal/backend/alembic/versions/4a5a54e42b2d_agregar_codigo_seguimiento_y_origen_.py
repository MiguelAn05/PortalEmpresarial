"""agregar codigo seguimiento y origen publico

Revision ID: 4a5a54e42b2d
Revises: 0001_initial
Create Date: 2026-07-01

"""
from alembic import op
import sqlalchemy as sa

revision = '4a5a54e42b2d'
down_revision = '0001_initial'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # codigo_seguimiento: nullable porque registros viejos no lo tienen
    op.add_column('pqrs_solicitudes',
        sa.Column('codigo_seguimiento', sa.String(30), nullable=True)
    )

    # origen_publico: agregamos con valor por defecto primero,
    # así los registros existentes quedan como "interno"
    op.add_column('pqrs_solicitudes',
        sa.Column('origen_publico', sa.String(20),
                  nullable=False, server_default='interno')
    )

    # Índice para buscar rápido por código de seguimiento
    op.create_index(
        'ix_pqrs_solicitudes_codigo_seguimiento',
        'pqrs_solicitudes',
        ['codigo_seguimiento'],
        unique=True
    )


def downgrade() -> None:
    op.drop_index('ix_pqrs_solicitudes_codigo_seguimiento',
                  table_name='pqrs_solicitudes')
    op.drop_column('pqrs_solicitudes', 'origen_publico')
    op.drop_column('pqrs_solicitudes', 'codigo_seguimiento')