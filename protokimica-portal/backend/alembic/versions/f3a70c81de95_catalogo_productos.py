"""catalogo de productos sincronizado desde el ERP

Copia local de los productos. El portal no consulta Oracle en vivo: un
proceso del lado del ERP empuja el catálogo, y las búsquedas salen de aquí.

Revision ID: f3a70c81de95
Revises: a3f7c21b9d55
Create Date: 2026-08-29 12:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3a70c81de95'
# Va después de la de Oportunidades de Mejora. Las dos se escribieron el
# mismo día colgando del mismo padre, y eso deja a Alembic con dos cabezas y
# el backend sin arrancar. Como esta todavía no se había aplicado en ningún
# lado, se reencadena en vez de fusionar: la historia queda lineal.
down_revision = 'a3f7c21b9d55'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'cat_productos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tenant_id', sa.Integer(), nullable=False),
        sa.Column('codigo', sa.String(length=60), nullable=False),
        sa.Column('nombre', sa.String(length=300), nullable=False),
        sa.Column('presentacion', sa.String(length=60), nullable=True),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'codigo', name='uq_producto_codigo'),
    )
    op.create_index('ix_cat_productos_tenant_id', 'cat_productos', ['tenant_id'])
    op.create_index('ix_cat_productos_codigo', 'cat_productos', ['codigo'])


def downgrade() -> None:
    op.drop_table('cat_productos')
