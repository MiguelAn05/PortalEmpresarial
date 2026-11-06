"""Marcaciones: en qué biométrico se hizo cada marcación

Cada sede tiene su propio biométrico. La marcación guarda la serie del equipo
y `mar_dispositivos` dice cuál es (nombre y sede), lleno por el script.
Las marcaciones viejas quedan sin dispositivo hasta que el script las reenvíe.

Revision ID: e8a3c5f71b20
Revises: d5f2b8e1a347
Create Date: 2026-11-06 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'e8a3c5f71b20'
down_revision = 'd5f2b8e1a347'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("mar_marcaciones", sa.Column("dispositivo", sa.String(40), nullable=True))
    op.create_table(
        "mar_dispositivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("serie", sa.String(40), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=True),
        sa.Column("sede", sa.String(100), nullable=True),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "serie", name="uq_mar_dispositivo_serie"),
    )
    op.create_index("ix_mar_dispositivos_tenant_id", "mar_dispositivos", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_mar_dispositivos_tenant_id", table_name="mar_dispositivos")
    op.drop_table("mar_dispositivos")
    op.drop_column("mar_marcaciones", "dispositivo")
