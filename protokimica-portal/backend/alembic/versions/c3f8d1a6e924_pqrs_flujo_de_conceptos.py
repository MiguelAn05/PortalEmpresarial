"""PQRS: flujo de conceptos (plantillas, bodegas de despacho y cadena)

Revision ID: c3f8d1a6e924
Revises: b7e4a2c91f53
Create Date: 2026-10-08

El recorrido de una PQRS es una cadena de conceptos (autorizaciones) que
hoy se pide a mano y se equivoca. Ver `modules/pqrs/flujo.py`.

- `pqrs_bodegas_despacho`: desde dónde salió el producto y qué concepto pide.
- `pqrs_flujos` + `pqrs_flujo_pasos`: las plantillas, por tipo de canal.
- `pqrs_cadena_pasos`: la cadena de cada PQRS, ya resuelta.
- `pqrs_asociados.concepto_tecnico_id`: el concepto técnico de cada causa.
- `pqrs_solicitudes.bodega_despacho_id`.

Las plantillas y las bodegas se siembran solas la primera vez que se piden
(`flujo.sembrar`), así que aquí no se insertan filas.
"""
from alembic import op
import sqlalchemy as sa

revision = "c3f8d1a6e924"
down_revision = "b7e4a2c91f53"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pqrs_bodegas_despacho",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("tipo_autorizacion_id", sa.Integer(), sa.ForeignKey("tipos_autorizacion.id"), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_pqrs_bodega_despacho_nombre"),
    )
    op.create_index("ix_pqrs_bodegas_despacho_id", "pqrs_bodegas_despacho", ["id"])
    op.create_index("ix_pqrs_bodegas_despacho_tenant_id", "pqrs_bodegas_despacho", ["tenant_id"])

    op.create_table(
        "pqrs_flujos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("aplica_a", sa.String(20), nullable=True),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pqrs_flujos_id", "pqrs_flujos", ["id"])
    op.create_index("ix_pqrs_flujos_tenant_id", "pqrs_flujos", ["tenant_id"])

    op.create_table(
        "pqrs_flujo_pasos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("flujo_id", sa.Integer(), sa.ForeignKey("pqrs_flujos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clase", sa.String(20), nullable=False, server_default="concepto"),
        sa.Column("tipo_autorizacion_id", sa.Integer(), sa.ForeignKey("tipos_autorizacion.id"), nullable=True),
    )
    op.create_index("ix_pqrs_flujo_pasos_id", "pqrs_flujo_pasos", ["id"])
    op.create_index("ix_pqrs_flujo_pasos_flujo_id", "pqrs_flujo_pasos", ["flujo_id"])

    op.create_table(
        "pqrs_cadena_pasos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pqrs_id", sa.Integer(), sa.ForeignKey("pqrs_solicitudes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tipo_autorizacion_id", sa.Integer(), sa.ForeignKey("tipos_autorizacion.id"), nullable=False),
        sa.Column("origen", sa.String(20), nullable=False, server_default="concepto"),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("autorizacion_id", sa.Integer(), sa.ForeignKey("autorizaciones_pqrs.id"), nullable=True),
        sa.Column("creado_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_pqrs_cadena_pasos_id", "pqrs_cadena_pasos", ["id"])
    op.create_index("ix_pqrs_cadena_pasos_pqrs_id", "pqrs_cadena_pasos", ["pqrs_id"])

    op.add_column("pqrs_asociados", sa.Column(
        "concepto_tecnico_id", sa.Integer(), sa.ForeignKey("tipos_autorizacion.id"), nullable=True,
    ))
    op.add_column("pqrs_solicitudes", sa.Column(
        "bodega_despacho_id", sa.Integer(), sa.ForeignKey("pqrs_bodegas_despacho.id"), nullable=True,
    ))


def downgrade() -> None:
    op.drop_column("pqrs_solicitudes", "bodega_despacho_id")
    op.drop_column("pqrs_asociados", "concepto_tecnico_id")
    op.drop_index("ix_pqrs_cadena_pasos_pqrs_id", table_name="pqrs_cadena_pasos")
    op.drop_index("ix_pqrs_cadena_pasos_id", table_name="pqrs_cadena_pasos")
    op.drop_table("pqrs_cadena_pasos")
    op.drop_index("ix_pqrs_flujo_pasos_flujo_id", table_name="pqrs_flujo_pasos")
    op.drop_index("ix_pqrs_flujo_pasos_id", table_name="pqrs_flujo_pasos")
    op.drop_table("pqrs_flujo_pasos")
    op.drop_index("ix_pqrs_flujos_tenant_id", table_name="pqrs_flujos")
    op.drop_index("ix_pqrs_flujos_id", table_name="pqrs_flujos")
    op.drop_table("pqrs_flujos")
    op.drop_index("ix_pqrs_bodegas_despacho_tenant_id", table_name="pqrs_bodegas_despacho")
    op.drop_index("ix_pqrs_bodegas_despacho_id", table_name="pqrs_bodegas_despacho")
    op.drop_table("pqrs_bodegas_despacho")
