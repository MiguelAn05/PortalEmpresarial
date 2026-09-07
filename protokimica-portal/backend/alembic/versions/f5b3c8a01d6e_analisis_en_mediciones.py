"""Mediciones: observación pasa a ser análisis obligatorio

Revision ID: f5b3c8a01d6e
Revises: d81f6a4c92e3
Create Date: 2026-09-08

`observación` era un campo opcional de contexto. Pasa a llamarse `análisis`
y a ser obligatorio al registrar: no basta con guardar el número, hay que
explicar qué lo explica — es lo que sirve seis meses después, cuando alguien
mira el histórico y no se acuerda de qué pasó ese mes.

Es un RENOMBRE de columna, no una columna nueva: los análisis que ya se
habían escrito bajo `observacion` no se pierden. La obligatoriedad la
impone el endpoint (`indicadores/router.py`) desde este mismo commit, no
esta migración — por eso la columna sigue `nullable=True`: los meses
registrados antes de hoy se quedan sin análisis, y no hay con qué
rellenarlo sin inventar un dato que nadie escribió.
"""
from alembic import op

revision = "f5b3c8a01d6e"
down_revision = "d81f6a4c92e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("ind_mediciones", "observacion", new_column_name="analisis")


def downgrade() -> None:
    op.alter_column("ind_mediciones", "analisis", new_column_name="observacion")
