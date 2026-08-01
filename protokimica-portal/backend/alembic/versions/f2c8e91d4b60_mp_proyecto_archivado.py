"""master planner: archivar proyectos en vez de borrarlos

Revision ID: f2c8e91d4b60
Revises: d391a7c2e5f0
Create Date: 2026-07-31 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2c8e91d4b60'
down_revision = 'd391a7c2e5f0'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'mp_proyectos',
        sa.Column('archivado', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )


def downgrade() -> None:
    op.drop_column('mp_proyectos', 'archivado')
