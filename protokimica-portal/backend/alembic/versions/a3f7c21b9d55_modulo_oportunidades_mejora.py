"""Módulo de Oportunidades de Mejora (OMP)

Revision ID: a3f7c21b9d55
Revises: e8b3d260fa14
Create Date: 2026-08-19

Las dos tablas del ciclo de mejora. La OMP apunta al indicador que la
disparó con ondelete=SET NULL y no CASCADE: si alguien borra un indicador,
el registro de que hubo un problema y qué se hizo NO se puede evaporar —
es justamente lo que se audita. Las acciones sí van en CASCADE: sin su
oportunidad no significan nada.
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f7c21b9d55"
down_revision = "e8b3d260fa14"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "omp_oportunidades",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=20), nullable=True),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=True),
        sa.Column("origen", sa.String(length=20), nullable=False, server_default="indicador"),
        sa.Column("indicador_id", sa.Integer(), nullable=True),
        sa.Column("periodo_anio", sa.Integer(), nullable=True),
        sa.Column("periodo_mes", sa.Integer(), nullable=True),
        sa.Column("valor_inicial", sa.Numeric(16, 4), nullable=True),
        sa.Column("meta_esperada", sa.Numeric(16, 4), nullable=True),
        sa.Column("pqrs_id", sa.Integer(), nullable=True),
        sa.Column("area", sa.String(length=100), nullable=True),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("estado", sa.String(length=20), nullable=False, server_default="abierta"),
        sa.Column("prioridad", sa.String(length=20), nullable=False, server_default="media"),
        sa.Column("fecha_limite", sa.DateTime(timezone=True), nullable=True),
        sa.Column("causa_raiz", sa.Text(), nullable=True),
        sa.Column("eficaz", sa.Boolean(), nullable=True),
        sa.Column("valor_verificado", sa.Numeric(16, 4), nullable=True),
        sa.Column("nota_eficacia", sa.Text(), nullable=True),
        sa.Column("fecha_cierre", sa.DateTime(timezone=True), nullable=True),
        sa.Column("creado_por", sa.Integer(), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["indicador_id"], ["ind_indicadores.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["pqrs_id"], ["pqrs_solicitudes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["responsable_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["creado_por"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_omp_oportunidades_id"), "omp_oportunidades", ["id"])
    op.create_index(op.f("ix_omp_oportunidades_tenant_id"), "omp_oportunidades", ["tenant_id"])
    op.create_index(op.f("ix_omp_oportunidades_indicador_id"), "omp_oportunidades", ["indicador_id"])
    op.create_index(op.f("ix_omp_oportunidades_pqrs_id"), "omp_oportunidades", ["pqrs_id"])
    op.create_index(op.f("ix_omp_oportunidades_area"), "omp_oportunidades", ["area"])
    op.create_index(op.f("ix_omp_oportunidades_estado"), "omp_oportunidades", ["estado"])
    # Único: el código es el número con el que se habla de la oportunidad en
    # una reunión. Dos iguales harían imposible saber de cuál se habla.
    op.create_index(
        op.f("ix_omp_oportunidades_codigo"), "omp_oportunidades", ["codigo"], unique=True,
    )

    op.create_table(
        "omp_acciones",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("omp_id", sa.Integer(), nullable=False),
        sa.Column("descripcion", sa.String(length=300), nullable=False),
        sa.Column("responsable_id", sa.Integer(), nullable=True),
        sa.Column("fecha_limite", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completada", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("fecha_completada", sa.DateTime(timezone=True), nullable=True),
        sa.Column("evidencia", sa.String(length=255), nullable=True),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["omp_id"], ["omp_oportunidades.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["responsable_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_omp_acciones_id"), "omp_acciones", ["id"])
    op.create_index(op.f("ix_omp_acciones_omp_id"), "omp_acciones", ["omp_id"])


def downgrade() -> None:
    op.drop_table("omp_acciones")
    op.drop_table("omp_oportunidades")
