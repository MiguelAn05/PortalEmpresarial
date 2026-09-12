"""PQRS: solución al resolver, con soporte múltiple, y plazo de confirmación

Revision ID: b8d4f21a6c93
Revises: f5b3c8a01d6e
Create Date: 2026-09-12

Marcar una PQRS como "resuelto" guardaba el estado y nada más: el cliente
nunca se enteraba de QUÉ se le solucionó. El correo de cierre solo traía la
encuesta. Ahora, al entrar a "resuelto" hay que escribir qué se hizo, y eso
es lo que se le manda — con foto o PDF si hace falta — pidiéndole que
confirme si quedó bien.

`solucion` es texto libre y va con Text porque puede incluir varios párrafos.
`fecha_resuelto` es de dónde sale el plazo de 3 días hábiles antes del cierre
automático (`pqrs/cierre_automatico.py`): se pone al entrar a "resuelto" y se
BORRA si se reabre, para que una PQRS reabierta y resuelta de nuevo no
herede el reloj de la primera vez.

El soporte va en tabla aparte (`pqrs_adjuntos_solucion`), no en una columna:
puede ser más de un archivo — varias fotos, o fotos más un PDF — y una sola
columna de texto solo alcanza para uno.

Las PQRS que ya estaban en "resuelto" o "cerrado" antes de este cambio se
quedan con `solucion` y `fecha_resuelto` en NULL: no hay con qué rellenarlas
sin inventar un dato que nadie escribió, y por eso las dos columnas son
`nullable=True` a pesar de que el endpoint las vuelve obligatorias de aquí
en adelante.
"""
from alembic import op
import sqlalchemy as sa

revision = "b8d4f21a6c93"
down_revision = "f5b3c8a01d6e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pqrs_solicitudes",
        sa.Column("solucion", sa.Text(), nullable=True),
    )
    op.add_column(
        "pqrs_solicitudes",
        sa.Column("fecha_resuelto", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "pqrs_adjuntos_solucion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "pqrs_id", sa.Integer(),
            sa.ForeignKey("pqrs_solicitudes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ruta", sa.String(length=500), nullable=False),
        sa.Column("creado_en", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index(
        "ix_pqrs_adjuntos_solucion_pqrs_id", "pqrs_adjuntos_solucion", ["pqrs_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_pqrs_adjuntos_solucion_pqrs_id", table_name="pqrs_adjuntos_solucion")
    op.drop_table("pqrs_adjuntos_solucion")
    op.drop_column("pqrs_solicitudes", "fecha_resuelto")
    op.drop_column("pqrs_solicitudes", "solucion")
