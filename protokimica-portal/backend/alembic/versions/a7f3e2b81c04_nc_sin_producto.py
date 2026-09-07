"""Nota crédito: se quita el producto

Revision ID: a7f3e2b81c04
Revises: e4a1c72d09b6
Create Date: 2026-09-05

Una factura trae varios renglones, así que un solo campo de producto miente
más de lo que ayuda: o se llena con uno de los tres que venían —y el informe
por producto queda contando mal— o se deja vacío y solo estorba en el
formulario. Lo que identifica el caso es la factura, y esa ya está.

Se quita ahora, antes de que la función llegue a producción y haya datos que
migrar. Si algún día hace falta el detalle por renglón, será una tabla hija
de `nc_solicitudes` y no dos columnas sueltas.
"""
from alembic import op
import sqlalchemy as sa

revision = "a7f3e2b81c04"
down_revision = "e4a1c72d09b6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("nc_solicitudes", "producto_nombre")
    op.drop_column("nc_solicitudes", "producto_codigo")


def downgrade() -> None:
    op.add_column(
        "nc_solicitudes",
        sa.Column("producto_codigo", sa.String(length=60), nullable=True),
    )
    op.add_column(
        "nc_solicitudes",
        sa.Column("producto_nombre", sa.String(length=300), nullable=True),
    )
