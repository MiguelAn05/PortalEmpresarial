"""Módulo de Fichas de seguridad (FDS)

Crea las dos tablas del módulo: `fds_fichas` (una por producto) y
`fds_versiones` (cada PDF, con el número y la fecha que trae el documento; una
sola vigente por ficha).

Esta migración NO otorga ninguna capacidad: quién sube y versiona las fichas
(`fichas_seguridad.gestionar`) lo decide la empresa en Administración ›
Capacidades. Y el módulo NO queda contratado: se activa por empresa con
`python -m app.scripts.modulos <empresa> --activar fichas_seguridad`.

Revision ID: f1a7d3c9b265
Revises: e8a3c5f71b20
Create Date: 2026-11-06 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f1a7d3c9b265'
down_revision = 'e8a3c5f71b20'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fds_fichas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("codigo_producto", sa.String(40), nullable=True),
        sa.Column("nombre_producto", sa.String(200), nullable=False),
        sa.Column("nombre_busqueda", sa.String(241), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creada_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "codigo_producto", name="uq_fds_ficha_codigo"),
    )
    op.create_index("ix_fds_fichas_id", "fds_fichas", ["id"])
    op.create_index("ix_fds_fichas_tenant_id", "fds_fichas", ["tenant_id"])
    op.create_index("ix_fds_fichas_nombre_busqueda", "fds_fichas", ["nombre_busqueda"])

    op.create_table(
        "fds_versiones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("ficha_id", sa.Integer(), sa.ForeignKey("fds_fichas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=False),
        sa.Column("nombre_original", sa.String(255), nullable=False),
        sa.Column("ruta", sa.String(255), nullable=False),
        sa.Column("tamano", sa.Integer(), nullable=False),
        sa.Column("vigente", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("observaciones", sa.String(500), nullable=True),
        sa.Column("subida_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("subida_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("ficha_id", "version", name="uq_fds_version"),
    )
    op.create_index("ix_fds_versiones_id", "fds_versiones", ["id"])
    op.create_index("ix_fds_versiones_ficha_id", "fds_versiones", ["ficha_id"])


def downgrade() -> None:
    op.drop_table("fds_versiones")
    op.drop_table("fds_fichas")
