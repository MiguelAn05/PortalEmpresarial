"""Migración inicial: tenants, users, pqrs

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-30

"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ─── tenants ───
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False, unique=True, index=True),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── users ───
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("email", sa.String(180), nullable=False, index=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("rol", sa.String(40), nullable=False, server_default="agente"),
        sa.Column("area", sa.String(100), nullable=True),
        sa.Column("activo", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    # ─── pqrs_solicitudes ───
    op.create_table(
        "pqrs_solicitudes",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("tenant_id", sa.Integer, sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("tipo", sa.String(20), nullable=False),
        sa.Column("cliente_nombre", sa.String(150), nullable=False),
        sa.Column("cliente_email", sa.String(180), nullable=True),
        sa.Column("cliente_telefono", sa.String(40), nullable=True),
        sa.Column("descripcion", sa.Text, nullable=False),
        sa.Column("area_responsable", sa.String(100), nullable=True),
        sa.Column("asignado_a", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("estado", sa.String(20), nullable=False, server_default="recibido"),
        sa.Column("prioridad", sa.String(20), nullable=False, server_default="media"),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("fecha_limite_sla", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
    )

    # ─── pqrs_seguimientos ───
    op.create_table(
        "pqrs_seguimientos",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("pqrs_id", sa.Integer, sa.ForeignKey("pqrs_solicitudes.id"), nullable=False, index=True),
        sa.Column("usuario_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tipo_evento", sa.String(30), nullable=False),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("fecha", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ─── pqrs_encuestas ───
    op.create_table(
        "pqrs_encuestas",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column("pqrs_id", sa.Integer, sa.ForeignKey("pqrs_solicitudes.id"), nullable=False, unique=True),
        sa.Column("calificacion", sa.Integer, nullable=True),
        sa.Column("comentario", sa.Text, nullable=True),
        sa.Column("respondida_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("pqrs_encuestas")
    op.drop_table("pqrs_seguimientos")
    op.drop_table("pqrs_solicitudes")
    op.drop_table("users")
    op.drop_table("tenants")
