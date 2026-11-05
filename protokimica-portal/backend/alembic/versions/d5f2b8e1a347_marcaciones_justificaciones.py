"""Marcaciones: justificaciones de las novedades

El líder (o Gestión Humana) explica una novedad de una persona un día. Es lo
único que el módulo escribe desde la pantalla.

Revision ID: d5f2b8e1a347
Revises: c4e7a1b9d256
Create Date: 2026-11-05 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd5f2b8e1a347'
down_revision = 'c4e7a1b9d256'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "mar_justificaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emp_code", sa.String(30), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("tipo", sa.String(30), nullable=False),
        sa.Column("texto", sa.String(500), nullable=False),
        sa.Column("autor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("autor_nombre", sa.String(150), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("actualizada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "emp_code", "fecha", "tipo", name="uq_mar_justificacion"),
    )
    op.create_index("ix_mar_justificaciones_tenant_id", "mar_justificaciones", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("mar_justificaciones")
