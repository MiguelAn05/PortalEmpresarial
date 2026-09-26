"""Tareas: entregable, horas estimadas y respuestas a los avances

Cuatro observaciones sobre las tareas de proyecto, tres de ellas con columna
nueva y una que sale de lo que ya se guardaba:

- `mp_tareas.entregable` — qué tiene que quedar hecho para darla por
  cumplida. Se pide al crearla: escrito después, se escribe para justificar
  lo que ya se hizo.
- `mp_tareas.horas_estimadas` — cuántas horas se piensa dedicarle. `Numeric`
  porque media hora existe.
- `mp_tarea_actualizaciones.parent_id` — a qué avance responde un comentario.
  Sin esto, responder obligaba a escribir OTRO avance y el historial quedaba
  con conversación mezclada, sin decir a cuál contestaba.
- Cuántas veces se movió la fecha de una tarea **no necesita columna**: ya
  está en `mp_historial`, que además dice de qué fecha a cuál y quién la
  movió.

Ese conteo ahora viaja en el SELECT de cada tarea, así que necesita un índice
por donde entrar — y **ya existe**: `ix_mp_historial_entidad` sobre
`(entidad, entidad_id)`, que puso la migración `a4d7f30c9e21`. Con esas dos
columnas la búsqueda ya queda en las pocas filas de esa tarea; agregarle
`campo` no cambiaría nada y solo habría duplicado un índice.

Revision ID: d5c9f31ea784
Revises: c4d81e73ab20
"""
import sqlalchemy as sa
from alembic import op

revision = "d5c9f31ea784"
down_revision = "c4d81e73ab20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("mp_tareas", sa.Column("entregable", sa.String(length=300), nullable=True))
    op.add_column("mp_tareas", sa.Column("horas_estimadas", sa.Numeric(6, 2), nullable=True))

    op.add_column(
        "mp_tarea_actualizaciones",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "ix_mp_tarea_actualizaciones_parent_id",
        "mp_tarea_actualizaciones", ["parent_id"],
    )
    op.create_foreign_key(
        "fk_mp_actualizacion_parent",
        "mp_tarea_actualizaciones", "mp_tarea_actualizaciones",
        ["parent_id"], ["id"], ondelete="CASCADE",
    )


def downgrade():
    op.drop_constraint(
        "fk_mp_actualizacion_parent", "mp_tarea_actualizaciones", type_="foreignkey",
    )
    op.drop_index(
        "ix_mp_tarea_actualizaciones_parent_id", table_name="mp_tarea_actualizaciones",
    )
    op.drop_column("mp_tarea_actualizaciones", "parent_id")
    op.drop_column("mp_tareas", "horas_estimadas")
    op.drop_column("mp_tareas", "entregable")
