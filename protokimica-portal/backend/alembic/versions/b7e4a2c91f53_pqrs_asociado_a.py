"""PQRS: «Asociado a», la causa de cada PQRS

Revision ID: b7e4a2c91f53
Revises: a1d5c8e3f702
Create Date: 2026-10-06

- `pqrs_asociados`: el catálogo de causas de cada empresa (Mala entrega,
  Calidad del producto, Toma de pedido…), el mismo con el que Calidad
  clasificaba en Excel. Se siembra solo la primera vez que se pide
  (`pqrs/asociados.del_tenant`), así que aquí no se insertan filas.
- `pqrs_solicitudes.asociado_id`: a cuál está asociada cada PQRS. Las que ya
  existen quedan vacías («Sin causa») y se clasifican desde la lista.
"""
from alembic import op
import sqlalchemy as sa

revision = "b7e4a2c91f53"
down_revision = "a1d5c8e3f702"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pqrs_asociados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo", sa.String(20), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("grupo", sa.String(60), nullable=False),
        sa.Column("area_sugerida", sa.String(100), nullable=True),
        sa.Column("sugiere_omp", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("aplica_a", sa.String(20), nullable=True),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_pqrs_asociado_tenant_nombre"),
    )
    op.create_index("ix_pqrs_asociados_id", "pqrs_asociados", ["id"])
    op.create_index("ix_pqrs_asociados_tenant_id", "pqrs_asociados", ["tenant_id"])

    op.add_column("pqrs_solicitudes", sa.Column(
        "asociado_id", sa.Integer(), sa.ForeignKey("pqrs_asociados.id"), nullable=True,
    ))
    op.create_index("ix_pqrs_solicitudes_asociado_id", "pqrs_solicitudes", ["asociado_id"])


def downgrade() -> None:
    op.drop_index("ix_pqrs_solicitudes_asociado_id", table_name="pqrs_solicitudes")
    op.drop_column("pqrs_solicitudes", "asociado_id")
    op.drop_index("ix_pqrs_asociados_tenant_id", table_name="pqrs_asociados")
    op.drop_index("ix_pqrs_asociados_id", table_name="pqrs_asociados")
    op.drop_table("pqrs_asociados")
