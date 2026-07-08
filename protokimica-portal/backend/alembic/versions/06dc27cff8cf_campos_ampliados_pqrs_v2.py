"""campos_ampliados_pqrs_v2

Revision ID: 06dc27cff8cf
Revises: 4a5a54e42b2d
Create Date: 2026-07-04

"""
from alembic import op
import sqlalchemy as sa

revision = '06dc27cff8cf'
down_revision = '4a5a54e42b2d'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('pqrs_solicitudes', sa.Column('empresa', sa.String(150), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('nit_cedula', sa.String(30), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('ciudad', sa.String(100), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('departamento', sa.String(100), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('producto_codigo', sa.String(50), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('producto_nombre', sa.String(200), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('lote', sa.String(50), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('factura_numero', sa.String(50), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('cantidad_factura', sa.String(20), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('cantidad_reclamo', sa.String(20), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('adjunto_producto', sa.String(500), nullable=True))
    op.add_column('pqrs_solicitudes', sa.Column('adjunto_factura', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('pqrs_solicitudes', 'adjunto_factura')
    op.drop_column('pqrs_solicitudes', 'adjunto_producto')
    op.drop_column('pqrs_solicitudes', 'cantidad_reclamo')
    op.drop_column('pqrs_solicitudes', 'cantidad_factura')
    op.drop_column('pqrs_solicitudes', 'factura_numero')
    op.drop_column('pqrs_solicitudes', 'lote')
    op.drop_column('pqrs_solicitudes', 'producto_nombre')
    op.drop_column('pqrs_solicitudes', 'producto_codigo')
    op.drop_column('pqrs_solicitudes', 'departamento')
    op.drop_column('pqrs_solicitudes', 'ciudad')
    op.drop_column('pqrs_solicitudes', 'nit_cedula')
    op.drop_column('pqrs_solicitudes', 'empresa')