"""Módulo de Marcaciones (reloj biométrico ZKBio)

Crea las cinco tablas del módulo y otorga la capacidad `marcaciones.ver_todo`
a Gestión Humana y TICS de cada empresa, que son quienes revisan la
asistencia de toda la empresa. Va en la migración y no solo en
`sembrar_capacidades_iniciales` por la misma razón que `mejora.trabajar`: esa
siembra corre cuando alguien abre Administración › Capacidades.

El módulo NO queda contratado por esta migración: se activa por empresa con
`python -m app.scripts.modulos <empresa> --activar marcaciones`.

Revision ID: c4e7a1b9d256
Revises: a9d4e7c2b158
Create Date: 2026-11-05 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c4e7a1b9d256'
down_revision = 'a9d4e7c2b158'
branch_labels = None
depends_on = None

CAPACIDAD = "marcaciones.ver_todo"
AREAS = ("Gestión Humana", "TICS")


def upgrade() -> None:
    op.create_table(
        "mar_empleados",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emp_code", sa.String(30), nullable=False),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("area", sa.String(100), nullable=True),
        sa.Column("correo", sa.String(180), nullable=True),
        *[sa.Column(d, sa.String(80), nullable=False, server_default="") for d in
          ("lun", "mar", "mie", "jue", "vie", "sab", "dom")],
        sa.Column("activo", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("actualizado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "emp_code", name="uq_mar_empleado_codigo"),
    )
    op.create_index("ix_mar_empleados_id", "mar_empleados", ["id"])
    op.create_index("ix_mar_empleados_tenant_id", "mar_empleados", ["tenant_id"])

    op.create_table(
        "mar_marcaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emp_code", sa.String(30), nullable=False),
        sa.Column("momento", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(1), nullable=False),
        sa.Column("recibida_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "emp_code", "momento", "estado", name="uq_mar_marcacion"),
    )
    op.create_index("ix_mar_marcaciones_tenant_momento", "mar_marcaciones", ["tenant_id", "momento"])

    op.create_table(
        "mar_festivos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("nombre", sa.String(100), nullable=True),
        sa.UniqueConstraint("tenant_id", "fecha", name="uq_mar_festivo"),
    )
    op.create_index("ix_mar_festivos_tenant_id", "mar_festivos", ["tenant_id"])

    op.create_table(
        "mar_excepciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("emp_code", sa.String(30), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("motivo", sa.String(100), nullable=True),
        sa.UniqueConstraint("tenant_id", "emp_code", "fecha", name="uq_mar_excepcion"),
    )
    op.create_index("ix_mar_excepciones_tenant_id", "mar_excepciones", ["tenant_id"])

    op.create_table(
        "mar_sincronizaciones",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("empleados", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("marcaciones_nuevas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("ultima_marcacion", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mar_sincronizaciones_tenant_id", "mar_sincronizaciones", ["tenant_id"])
    op.create_index("ix_mar_sincronizaciones_creada_en", "mar_sincronizaciones", ["creada_en"])

    conexion = op.get_bind()
    for (tenant_id,) in conexion.execute(sa.text("SELECT id FROM tenants")).fetchall():
        admin = conexion.execute(sa.text(
            "SELECT id FROM users WHERE tenant_id = :t AND rol = 'admin' ORDER BY id LIMIT 1"
        ), {"t": tenant_id}).fetchone()
        if not admin:
            continue
        for area in AREAS:
            ya = conexion.execute(sa.text(
                "SELECT 1 FROM capacidades_otorgadas WHERE tenant_id = :t "
                "AND capacidad = :c AND area = :a"
            ), {"t": tenant_id, "c": CAPACIDAD, "a": area}).fetchone()
            if ya:
                continue
            conexion.execute(sa.text(
                "INSERT INTO capacidades_otorgadas (tenant_id, capacidad, area, otorgada_por) "
                "VALUES (:t, :c, :a, :por)"
            ), {"t": tenant_id, "c": CAPACIDAD, "a": area, "por": admin[0]})


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM capacidades_otorgadas WHERE capacidad = :c"), {"c": CAPACIDAD})
    for tabla in ("mar_sincronizaciones", "mar_excepciones", "mar_festivos", "mar_marcaciones", "mar_empleados"):
        op.drop_table(tabla)
