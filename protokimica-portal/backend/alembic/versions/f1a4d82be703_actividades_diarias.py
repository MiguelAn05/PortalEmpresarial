"""Actividades diarias: lo que se repite y no pertenece a un proyecto

Dos tablas, y **ninguna guarda las ocurrencias**:

- `mp_actividades` — la definición: qué se hace, quién responde y con qué
  frecuencia. `desde`/`hasta` acotan desde cuándo se espera y hasta cuándo,
  para que apagar una actividad no deje el resto del mes en rojo.
- `mp_actividad_registros` — una fila por (actividad, día) diciendo que ese
  día se hizo. **La fila existe o no existe**: no hay columna «hecho»,
  porque un booleano daría tres estados —sí, no, y sin fila— a una pregunta
  con dos respuestas.

Qué se esperaba de cada día se deduce de la frecuencia (ver
`master_planner/actividades.py`). Materializar un pendiente por día habría
obligado a un proceso programado cada madrugada, y el día que no corriera la
gente entraría a una pantalla vacía sin que nadie supiera por qué.

Revision ID: f1a4d82be703
Revises: e7b2a940cf1f
"""
import sqlalchemy as sa
from alembic import op

revision = "f1a4d82be703"
down_revision = "e7b2a940cf1f"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mp_actividades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("asignado_a", sa.Integer(), nullable=True),
        sa.Column("area", sa.String(length=100), nullable=True),
        sa.Column("frecuencia", sa.String(length=20), nullable=False,
                  server_default="diaria"),
        sa.Column("dias_semana", sa.String(length=20), nullable=True),
        sa.Column("dia_mes", sa.Integer(), nullable=True),
        sa.Column("solo_dias_habiles", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("desde", sa.Date(), nullable=False),
        sa.Column("hasta", sa.Date(), nullable=True),
        sa.Column("activa", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("creado_por", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["asignado_a"], ["users.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mp_actividades_id", "mp_actividades", ["id"])
    op.create_index("ix_mp_actividades_tenant_id", "mp_actividades", ["tenant_id"])
    op.create_index("ix_mp_actividades_asignado_a", "mp_actividades", ["asignado_a"])
    op.create_index("ix_mp_actividades_area", "mp_actividades", ["area"])

    op.create_table(
        "mp_actividad_registros",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actividad_id", sa.Integer(), nullable=False),
        sa.Column("fecha", sa.Date(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=True),
        sa.Column("comentario", sa.Text(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["actividad_id"], ["mp_actividades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["usuario_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        # Un día se registra una sola vez: sin esto, dos clics seguidos en el
        # botón dejarían la actividad cumplida dos veces y el indicador
        # pasaría del 100%.
        sa.UniqueConstraint("actividad_id", "fecha", name="uq_actividad_dia"),
    )
    op.create_index("ix_mp_actividad_registros_id", "mp_actividad_registros", ["id"])
    op.create_index(
        "ix_mp_actividad_registros_actividad_id", "mp_actividad_registros", ["actividad_id"],
    )
    op.create_index("ix_mp_actividad_registros_fecha", "mp_actividad_registros", ["fecha"])


def downgrade():
    op.drop_table("mp_actividad_registros")
    op.drop_table("mp_actividades")
