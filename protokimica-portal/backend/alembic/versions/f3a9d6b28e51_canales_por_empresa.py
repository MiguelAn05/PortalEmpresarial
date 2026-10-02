"""Los canales y las sedes pasan a ser de cada empresa

Revision ID: f3a9d6b28e51
Revises: e8c1f4a62b70
Create Date: 2026-10-01

Tres cosas que salen del código y pasan a la base:

1. **Los canales** (`canales`), con su prefijo y su tipo (`sede`,
   `institucional`, `general`). Cada empresa recibe los nueve que regían hasta
   hoy, con los MISMOS prefijos: son los códigos de los QR ya impresos y el
   comienzo de los consecutivos de cada sede.
2. **El área de las sedes** (`areas.es_de_sedes`). Era la constante
   `AREA_PUNTOS_DE_VENTA`; se marca el área «Puntos de Venta» de cada empresa.
3. **La rama de cada nota crédito** (`nc_solicitudes.institucional`). Se
   decidía comparando el canal con «Venta institucional»; ahora se guarda al
   crearla. Las existentes la toman de esa misma comparación, así que ninguna
   cambia de cadena.
"""
from alembic import op
import sqlalchemy as sa

revision = "f3a9d6b28e51"
down_revision = "e8c1f4a62b70"
branch_labels = None
depends_on = None

CANALES_AL_MIGRAR = [
    ("Venta institucional", "VI", "institucional"),
    ("WhatsApp", None, "general"),
    ("Punto de venta Centro", "PVC", "sede"),
    ("Punto de venta Belén", "PVB", "sede"),
    ("Punto de venta Guayabal", "PVG", "sede"),
    ("Punto de venta La 65", "PV65", "sede"),
    ("Punto de venta Cristo Rey", "PVCR", "sede"),
    ("Punto de venta Itagüí", "PVI", "sede"),
    ("Línea telefónica", None, "general"),
]


def upgrade() -> None:
    op.create_table(
        "canales",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=False),
        sa.Column("prefijo", sa.String(10), nullable=True),
        sa.Column("tipo", sa.String(20), nullable=False, server_default="general"),
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "nombre", name="uq_canal_tenant_nombre"),
        sa.UniqueConstraint("tenant_id", "prefijo", name="uq_canal_tenant_prefijo"),
    )
    op.create_index("ix_canales_tenant_id", "canales", ["tenant_id"])

    op.add_column("areas", sa.Column(
        "es_de_sedes", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("nc_solicitudes", sa.Column(
        "institucional", sa.Boolean(), nullable=False, server_default=sa.false()))

    conexion = op.get_bind()
    for (tenant_id,) in conexion.execute(sa.text("SELECT id FROM tenants")).fetchall():
        for nombre, prefijo, tipo in CANALES_AL_MIGRAR:
            conexion.execute(sa.text(
                "INSERT INTO canales (tenant_id, nombre, prefijo, tipo) VALUES (:t, :n, :p, :ti)"
            ), {"t": tenant_id, "n": nombre, "p": prefijo, "ti": tipo})

    conexion.execute(sa.text("UPDATE areas SET es_de_sedes = true WHERE nombre = 'Puntos de Venta'"))
    conexion.execute(sa.text(
        "UPDATE nc_solicitudes SET institucional = true WHERE punto_venta = 'Venta institucional'"
    ))


def downgrade() -> None:
    op.drop_column("nc_solicitudes", "institucional")
    op.drop_column("areas", "es_de_sedes")
    op.drop_index("ix_canales_tenant_id", table_name="canales")
    op.drop_table("canales")
