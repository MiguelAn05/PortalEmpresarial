"""PQRS: varios productos por solicitud, cada uno con su lote y cantidades

Revision ID: d9e4a7b2c1f3
Revises: c7d2e9a41f58
Create Date: 2026-09-14

Una PQRS tenía un solo producto en columnas de `pqrs_solicitudes`. Un reclamo
por varios productos de la misma compra —cada uno con su lote y sus
cantidades— no cabía: había que radicar varias PQRS para un solo problema, o
esconder los demás productos en la descripción, donde ningún informe los ve.

Ahora los productos van en `pqrs_productos`, una fila por producto.

**Los datos se mueven, no se pierden.** Cada PQRS que tenía algo escrito en
los campos de producto recibe UNA fila con esos mismos valores, y solo
después se borran las columnas viejas. Se toma como «tenía algo» cualquier
campo con texto que no sea puros espacios: el formulario interno mandaba
cadenas vacías en todo lo que no se llenaba, y copiar eso crearía productos
fantasma sin nombre ni lote.

`factura_numero` se queda en la solicitud: la factura es una por compra.

Downgrade: devuelve las columnas y copia de vuelta el PRIMER producto de cada
PQRS. Los demás no tienen dónde caber en el esquema viejo y se pierden — por
eso bajar esta migración con datos reales de varios productos es destructivo.
"""
from alembic import op
import sqlalchemy as sa

revision = "d9e4a7b2c1f3"
down_revision = "c7d2e9a41f58"
branch_labels = None
depends_on = None

CAMPOS = [
    "producto_codigo", "producto_nombre", "presentacion", "cantidad_presentacion",
    "lote", "cantidad_factura", "cantidad_reclamo",
]


def upgrade() -> None:
    op.create_table(
        "pqrs_productos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pqrs_id", sa.Integer(),
            sa.ForeignKey("pqrs_solicitudes.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("producto_codigo", sa.String(length=50), nullable=True),
        sa.Column("producto_nombre", sa.String(length=300), nullable=True),
        sa.Column("por_confirmar", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("presentacion", sa.String(length=30), nullable=True),
        sa.Column("cantidad_presentacion", sa.String(length=20), nullable=True),
        sa.Column("lote", sa.String(length=50), nullable=True),
        sa.Column("cantidad_factura", sa.String(length=20), nullable=True),
        sa.Column("cantidad_reclamo", sa.String(length=20), nullable=True),
    )
    op.create_index("ix_pqrs_productos_pqrs_id", "pqrs_productos", ["pqrs_id"])

    limpios = ", ".join(f"NULLIF(TRIM({c}), '')" for c in CAMPOS)
    alguno = " OR ".join(f"NULLIF(TRIM({c}), '') IS NOT NULL" for c in CAMPOS)
    op.execute(f"""
        INSERT INTO pqrs_productos
            (pqrs_id, orden, {", ".join(CAMPOS)}, por_confirmar)
        SELECT id, 0, {limpios}, producto_por_confirmar
        FROM pqrs_solicitudes
        WHERE {alguno}
    """)

    for campo in CAMPOS + ["producto_por_confirmar"]:
        op.drop_column("pqrs_solicitudes", campo)


def downgrade() -> None:
    op.add_column("pqrs_solicitudes", sa.Column("producto_codigo", sa.String(50), nullable=True))
    op.add_column("pqrs_solicitudes", sa.Column("producto_nombre", sa.String(300), nullable=True))
    op.add_column("pqrs_solicitudes", sa.Column(
        "producto_por_confirmar", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("pqrs_solicitudes", sa.Column("presentacion", sa.String(30), nullable=True))
    op.add_column("pqrs_solicitudes", sa.Column("cantidad_presentacion", sa.String(20), nullable=True))
    op.add_column("pqrs_solicitudes", sa.Column("lote", sa.String(50), nullable=True))
    op.add_column("pqrs_solicitudes", sa.Column("cantidad_factura", sa.String(20), nullable=True))
    op.add_column("pqrs_solicitudes", sa.Column("cantidad_reclamo", sa.String(20), nullable=True))

    asignaciones = ", ".join(f"{c} = p.{c}" for c in CAMPOS)
    op.execute(f"""
        UPDATE pqrs_solicitudes s
        SET {asignaciones}, producto_por_confirmar = p.por_confirmar
        FROM pqrs_productos p
        WHERE p.pqrs_id = s.id
          AND p.id = (SELECT MIN(id) FROM pqrs_productos WHERE pqrs_id = s.id)
    """)

    op.drop_index("ix_pqrs_productos_pqrs_id", table_name="pqrs_productos")
    op.drop_table("pqrs_productos")
