"""PQRS: producto escrito a mano queda marcado para confirmar

Revision ID: c1d05b83e7f2
Revises: b7c94e2f81a3
Create Date: 2026-08-31

El buscador de productos no tenía salida de escape: si el cliente no
encontraba el suyo, no podía radicar. Ahora puede escribirlo, y la PQRS queda
marcada para que Servicio al Cliente lo corrija contra el catálogo antes de
cerrarla — el mismo trato que ya recibe el tipo, que el cliente casi nunca
acierta.

De paso se amplía `producto_nombre` de 200 a 300, que es el largo que tiene
`cat_productos.nombre`: un producto del catálogo con nombre largo no cabía y
se truncaba al radicar.

Las PQRS que ya existen quedan en `false`. Es correcto: hasta hoy el producto
salía de una lista cerrada, así que no hay nada pendiente de confirmar.
"""
from alembic import op
import sqlalchemy as sa

revision = "c1d05b83e7f2"
down_revision = "b7c94e2f81a3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pqrs_solicitudes",
        sa.Column("producto_por_confirmar", sa.Boolean(), nullable=False,
                  server_default="false"),
    )
    op.alter_column(
        "pqrs_solicitudes", "producto_nombre",
        existing_type=sa.String(length=200), type_=sa.String(length=300),
        existing_nullable=True,
    )


def downgrade() -> None:
    # Se recorta a 200 antes de encoger la columna: si hay un nombre más
    # largo, el ALTER falla y deja la migración a medias.
    op.execute(
        "UPDATE pqrs_solicitudes SET producto_nombre = LEFT(producto_nombre, 200) "
        "WHERE producto_nombre IS NOT NULL AND LENGTH(producto_nombre) > 200"
    )
    op.alter_column(
        "pqrs_solicitudes", "producto_nombre",
        existing_type=sa.String(length=300), type_=sa.String(length=200),
        existing_nullable=True,
    )
    op.drop_column("pqrs_solicitudes", "producto_por_confirmar")
