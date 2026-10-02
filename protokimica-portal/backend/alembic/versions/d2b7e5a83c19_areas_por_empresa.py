"""Las áreas pasan a ser de cada empresa

Revision ID: d2b7e5a83c19
Revises: c3f8a2d61e94
Create Date: 2026-10-01

Hasta hoy las áreas eran una lista en el código (`core/areas.py`), repetida
en el frontend e igual para cualquier empresa. Ahora cada empresa tiene las
suyas en `areas` y las administra en Administración › Áreas.

Cada empresa existente recibe exactamente la lista que regía hasta hoy, en el
mismo orden: los desplegables quedan iguales. Las demás tablas siguen
guardando el área como texto, así que no hay datos que mover.

La lista va escrita aquí y no importada de `AREAS_INICIALES`: una migración
describe el estado de un momento.
"""
from alembic import op
import sqlalchemy as sa

revision = "d2b7e5a83c19"
down_revision = "c3f8a2d61e94"
branch_labels = None
depends_on = None

AREAS_AL_MIGRAR = [
    "TICS", "Calidad", "SST", "Facturación", "Ventas Institucionales", "Mercadeo",
    "Servicio al Cliente", "Infraestructura", "Logística", "Gestión Humana",
    "Contabilidad", "Producción", "Control Interno", "Aseguramiento",
    "Abastecimiento", "Comercial", "Administración", "Tesorería",
    "Puntos de Venta", "Ambiental", "Dirección Técnica",
    "Investigación y Desarrollo (IDI)", "Salvak",
]


def upgrade() -> None:
    op.create_table(
        "areas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("orden", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_area_tenant_nombre"),
    )
    op.create_index("ix_areas_tenant_id", "areas", ["tenant_id"])

    conexion = op.get_bind()
    for (tenant_id,) in conexion.execute(sa.text("SELECT id FROM tenants")).fetchall():
        for orden, nombre in enumerate(AREAS_AL_MIGRAR):
            conexion.execute(sa.text(
                "INSERT INTO areas (tenant_id, nombre, orden) VALUES (:t, :n, :o)"
            ), {"t": tenant_id, "n": nombre, "o": orden})


def downgrade() -> None:
    op.drop_index("ix_areas_tenant_id", table_name="areas")
    op.drop_table("areas")
