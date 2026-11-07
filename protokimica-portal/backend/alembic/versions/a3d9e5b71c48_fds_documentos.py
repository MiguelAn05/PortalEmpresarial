"""Fichas de seguridad: documentos generados (certificados AP-F-06 y FDS AP-F-08)

Crea `fds_documentos`, el historial de lo que el portal generó a partir de los
documentos de los proveedores.

Revision ID: a3d9e5b71c48
Revises: f1a7d3c9b265
Create Date: 2026-11-06 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3d9e5b71c48'
down_revision = 'f1a7d3c9b265'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fds_documentos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("producto", sa.String(200), nullable=False),
        sa.Column("codigo_producto", sa.String(40), nullable=True),
        sa.Column("proveedor", sa.String(200), nullable=True),
        sa.Column("lote", sa.String(100), nullable=True),
        sa.Column("datos", sa.JSON(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("consecutivo", sa.Integer(), nullable=False),
        sa.Column("nombre_archivo", sa.String(255), nullable=False),
        sa.Column("ruta", sa.String(255), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("ficha_id", sa.Integer(), sa.ForeignKey("fds_fichas.id", ondelete="SET NULL"), nullable=True),
        sa.Column("generado_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("generado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "tipo", "dia", "consecutivo", name="uq_fds_documento_consecutivo"),
    )
    op.create_index("ix_fds_documentos_id", "fds_documentos", ["id"])
    op.create_index("ix_fds_documentos_tenant_id", "fds_documentos", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("fds_documentos")
