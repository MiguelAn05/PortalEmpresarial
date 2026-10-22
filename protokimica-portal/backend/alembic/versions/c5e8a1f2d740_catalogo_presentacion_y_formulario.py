"""catalogo: presentacion traducida y que productos van al formulario

- `unidad` y `cantidad_unidad`: la presentación del ERP traducida a la del
  formulario (`catalogo/presentaciones.py`).
- `en_formulario`: si se le ofrece al cliente (`catalogo/reglas.py`).

No se rellenan aquí: las tres salen de reglas que viven en la aplicación y
que una migración no debe copiar. Las llena la siguiente sincronización del
ERP —que reescribe cada producto—, y mientras tanto el formulario público no
ofrece ninguno y el cliente usa «No encuentro mi producto». En producción no
hay catálogo todavía; en desarrollo, correr `sincronizar_erp.ps1` otra vez.

Revision ID: c5e8a1f2d740
Revises: d8f3a6c2e917
Create Date: 2026-10-22 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c5e8a1f2d740'
down_revision = 'd8f3a6c2e917'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('cat_productos', sa.Column('unidad', sa.String(length=20), nullable=True))
    op.add_column('cat_productos', sa.Column('cantidad_unidad', sa.String(length=20), nullable=True))
    op.add_column('cat_productos', sa.Column(
        'en_formulario', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('cat_productos', 'en_formulario')
    op.drop_column('cat_productos', 'cantidad_unidad')
    op.drop_column('cat_productos', 'unidad')
