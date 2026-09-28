"""Quitar el área «Controlados»: era la misma que «Control Interno»

Dos áreas para lo mismo parten el reporte en dos: la mitad de los registros
quedan en una y la mitad en la otra, y ninguna de las dos cifras es la del
área. Se conserva **Control Interno**.

Quitarla de `core/areas.py` no basta: la lista es solo lo que se OFRECE.
El área ya escrita en un usuario, un indicador o una PQRS se queda ahí, y
entonces esa persona deja de ver lo suyo —el portal filtra por área exacta—
sin que nada falle y sin que nadie sepa por qué. Por eso esta migración
**mueve las filas**, como manda la regla de las áreas.

Son once columnas en diez tablas. Tres de ellas guardan **una fila por área**
(áreas participantes de un proyecto, áreas supervisadas de un usuario,
capacidades otorgadas a un área): ahí no se puede actualizar a ciegas, porque
quien ya tuviera las dos terminaría con «Control Interno» repetido —y en las
áreas supervisadas eso además revienta contra su restricción de unicidad—.
En esas se borra primero la fila duplicada y después se mueve la que queda.

Revision ID: e7b2a940cf1f
Revises: d5c9f31ea784
"""
import sqlalchemy as sa
from alembic import op

revision = "e7b2a940cf1f"
down_revision = "d5c9f31ea784"
branch_labels = None
depends_on = None

VIEJA = "Controlados"
NUEVA = "Control Interno"

# (tabla, columna) donde el área es un dato más de la fila: se actualiza.
COLUMNAS = [
    ("users", "area"),
    ("ind_indicadores", "area"),
    ("mp_proyectos", "area"),
    ("mp_tareas", "area"),
    ("omp_oportunidades", "area"),
    ("pqrs_solicitudes", "area_responsable"),
    ("pqrs_solicitudes", "area_causante"),
    ("tipos_autorizacion", "area_autorizadora"),
]

# (tabla, columna, columna que agrupa) donde hay UNA FILA POR ÁREA: si la
# fila hermana con el área nueva ya existe, esta sobra.
UNA_FILA_POR_AREA = [
    ("mp_proyecto_areas", "area", "proyecto_id"),
    ("usuario_areas_supervisadas", "area", "usuario_id"),
    ("capacidades_otorgadas", "area", "capacidad"),
]


def _mover(conexion, de: str, a: str) -> None:
    for tabla, columna, grupo in UNA_FILA_POR_AREA:
        conexion.execute(sa.text(f"""
            DELETE FROM {tabla} t
            WHERE t.{columna} = :de
              AND EXISTS (
                  SELECT 1 FROM {tabla} otra
                  WHERE otra.{grupo} = t.{grupo} AND otra.{columna} = :a
              )
        """), {"de": de, "a": a})

    for tabla, columna, _ in UNA_FILA_POR_AREA:
        conexion.execute(
            sa.text(f"UPDATE {tabla} SET {columna} = :a WHERE {columna} = :de"),
            {"de": de, "a": a},
        )

    for tabla, columna in COLUMNAS:
        conexion.execute(
            sa.text(f"UPDATE {tabla} SET {columna} = :a WHERE {columna} = :de"),
            {"de": de, "a": a},
        )


def upgrade():
    _mover(op.get_bind(), VIEJA, NUEVA)


def downgrade():
    """
    No se puede deshacer, y decirlo es más honesto que fingirlo.

    Las dos áreas quedaron fundidas en una: nada guarda cuáles registros
    estaban en «Controlados» antes, así que devolverlos sería repartirlos al
    azar. Volver a tener el área es agregarla a `core/areas.py`; lo que no
    vuelve es saber qué era de cuál.
    """
    pass
