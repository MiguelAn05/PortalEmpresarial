"""Solicitudes de nota crédito y su catálogo de motivos

Revision ID: e4a1c72d09b6
Revises: d2b6e94f13ca
Create Date: 2026-09-05

Hoy la nota crédito se pide por correo: el punto de venta le escribe a
Contabilidad, cuenta qué pasó y adjunta la factura. Eso funciona hasta que
alguien pregunta cuántas se hicieron el mes pasado, por qué, o si la que se
aprobó llegó a existir — y un buzón no responde ninguna de las tres.

Dos tablas:

`nc_motivos` es el porqué, y va en tabla y no en un enum por lo mismo que los
catálogos de Mejora: la lista la define Contabilidad y agregar un motivo no
puede exigir un despliegue. La semilla se siembra sola al pedir los motivos.

`nc_solicitudes` es la solicitud. No cuelga de `pqrs_solicitudes` a propósito:
una PQRS arrastra el plazo de la Ley 1755, la encuesta al cliente y el cierre
por Servicio al Cliente, y nada de eso aplica a un trámite entre el almacén y
Contabilidad. Colgarla ahí además metería estos registros en los indicadores
de quejas.

`numero_nc` es lo que cierra el ciclo: sin él, una solicitud aprobada y una
realmente ejecutada se ven idénticas.
"""
from alembic import op
import sqlalchemy as sa

revision = "e4a1c72d09b6"
down_revision = "d2b6e94f13ca"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "nc_motivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("nombre", sa.String(length=150), nullable=False),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_nc_motivos_tenant_id", "nc_motivos", ["tenant_id"])

    op.create_table(
        "nc_solicitudes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("codigo", sa.String(length=30), nullable=True),
        sa.Column("punto_venta", sa.String(length=100), nullable=False),
        sa.Column("factura_afectada", sa.String(length=60), nullable=False),
        sa.Column("factura_reemplaza", sa.String(length=60), nullable=True),
        sa.Column("producto_codigo", sa.String(length=60), nullable=True),
        sa.Column("producto_nombre", sa.String(length=300), nullable=True),
        sa.Column("valor", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("motivo_id", sa.Integer(), sa.ForeignKey("nc_motivos.id"), nullable=True),
        sa.Column("observaciones", sa.Text(), nullable=False),
        sa.Column("adjunto", sa.String(length=255), nullable=True),
        sa.Column("solicitado_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="solicitada"),
        sa.Column("autorizado_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("comentario_respuesta", sa.Text(), nullable=True),
        sa.Column("fecha_respuesta", sa.DateTime(timezone=True), nullable=True),
        sa.Column("numero_nc", sa.String(length=60), nullable=True),
        sa.Column("aplicada_por", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("fecha_aplicacion", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_nc_solicitudes_tenant_id", "nc_solicitudes", ["tenant_id"])
    op.create_index("ix_nc_solicitudes_codigo", "nc_solicitudes", ["codigo"])


def downgrade() -> None:
    op.drop_index("ix_nc_solicitudes_codigo", table_name="nc_solicitudes")
    op.drop_index("ix_nc_solicitudes_tenant_id", table_name="nc_solicitudes")
    op.drop_table("nc_solicitudes")
    op.drop_index("ix_nc_motivos_tenant_id", table_name="nc_motivos")
    op.drop_table("nc_motivos")
