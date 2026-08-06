"""recalcular el SLA de las PQRS abiertas en dias habiles

Los plazos se venian calculando en dias CALENDARIO (`timedelta(days=n)`),
incluidos sabados, domingos y festivos. Los 15 dias de una peticion salen de
la Ley 1755 de 2015, que habla de dias HABILES, asi que el sistema venia
declarando vencido lo que legalmente no lo estaba — y el indicador de
oportunidad media contra un plazo equivocado.

Esta migracion recalcula la fecha limite de las PQRS TODAVIA ABIERTAS,
tomando su fecha de radicacion original. Las cerradas se dejan intactas: su
cumplimiento ya se reporto y reescribirlo cambiaria indicadores de meses
pasados.

Revision ID: f1c6d80a5b47
Revises: d4a8c1f70b32
Create Date: 2026-08-05 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f1c6d80a5b47'
down_revision = 'd4a8c1f70b32'
branch_labels = None
depends_on = None

# Se copia aqui a proposito en vez de importarlo del codigo: una migracion
# tiene que seguir dando el mismo resultado dentro de un año, aunque para
# entonces los plazos del negocio hayan cambiado.
SLA_DIAS_POR_TIPO = {
    "peticion": 15,
    "queja": 5,
    "reclamo": 8,
    "sugerencia": 10,
}
SLA_POR_DEFECTO = 10


def upgrade() -> None:
    from app.core.dias_habiles import limite_en_habiles

    conn = op.get_bind()
    abiertas = conn.execute(sa.text(
        "SELECT id, tipo, fecha_creacion FROM pqrs_solicitudes "
        "WHERE estado <> 'cerrado' AND fecha_creacion IS NOT NULL"
    )).fetchall()

    for fila in abiertas:
        dias = SLA_DIAS_POR_TIPO.get(fila.tipo, SLA_POR_DEFECTO)
        nuevo_limite = limite_en_habiles(fila.fecha_creacion, dias)
        conn.execute(
            sa.text("UPDATE pqrs_solicitudes SET fecha_limite_sla = :limite WHERE id = :id"),
            {"limite": nuevo_limite, "id": fila.id},
        )


def downgrade() -> None:
    """Vuelve a los dias calendario, tambien solo en las abiertas."""
    from datetime import timedelta

    conn = op.get_bind()
    abiertas = conn.execute(sa.text(
        "SELECT id, tipo, fecha_creacion FROM pqrs_solicitudes "
        "WHERE estado <> 'cerrado' AND fecha_creacion IS NOT NULL"
    )).fetchall()

    for fila in abiertas:
        dias = SLA_DIAS_POR_TIPO.get(fila.tipo, SLA_POR_DEFECTO)
        conn.execute(
            sa.text("UPDATE pqrs_solicitudes SET fecha_limite_sla = :limite WHERE id = :id"),
            {"limite": fila.fecha_creacion + timedelta(days=dias), "id": fila.id},
        )
