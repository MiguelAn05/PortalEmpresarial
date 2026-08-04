"""unificar las areas de la empresa en una sola lista

Las areas estaban repetidas en seis archivos del frontend y con contenidos
distintos entre modulos. Al unificarlas, algunos nombres cambian:

    TI              -> TICS
    Sistemas        -> TICS
    Talento Humano  -> Gestion humana

Esta migracion NO solo cambia una lista: reescribe los valores ya guardados
en todas las columnas de area. Sin esto, un usuario con area "TI" dejaria de
ver los proyectos de "TICS" — en Master Planner el area decide la visibilidad,
asi que un rename a medias deja gente sin acceso a su propio trabajo.

Tambien limpia las cadenas vacias, que se comportan distinto a NULL en los
filtros y venian de formularios que enviaban "" en vez de nada.

Revision ID: d4a8c1f70b32
Revises: e7b3d9c1a204
Create Date: 2026-08-04 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4a8c1f70b32'
# Va despues de e7b3d9c1a204 (canal_atencion), no de c3f9b0a2e847: las dos
# salian del mismo punto y Alembic quedaba con dos cabezas.
down_revision = 'e7b3d9c1a204'
branch_labels = None
depends_on = None

# tabla -> columnas de area que tiene
COLUMNAS_DE_AREA = {
    'users': ['area'],
    'pqrs_solicitudes': ['area_responsable', 'area_causante'],
    'mp_proyectos': ['area'],
    'mp_proyecto_areas': ['area'],
    'mp_tareas': ['area'],
    'ind_indicadores': ['area'],
}

RENOMBRES = {
    'TI': 'TICS',
    'Sistemas': 'TICS',
    'Talento Humano': 'Gestión humana',
}


def _existe(tabla: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return tabla in inspector.get_table_names()


def upgrade() -> None:
    conn = op.get_bind()
    for tabla, columnas in COLUMNAS_DE_AREA.items():
        if not _existe(tabla):
            continue
        for columna in columnas:
            for viejo, nuevo in RENOMBRES.items():
                conn.execute(
                    sa.text(f"UPDATE {tabla} SET {columna} = :nuevo WHERE {columna} = :viejo"),
                    {"nuevo": nuevo, "viejo": viejo},
                )
            # Cadena vacia y espacios en blanco pasan a NULL: "sin area" tiene
            # que ser un solo valor, no tres que se filtran distinto.
            conn.execute(
                sa.text(f"UPDATE {tabla} SET {columna} = NULL WHERE TRIM({columna}) = ''")
            )


def downgrade() -> None:
    """
    Deshace los renombres. `Sistemas` no se puede recuperar: se fusiono con
    `TI` en `TICS` y no hay forma de saber cual era cual, asi que todo lo que
    estaba en TICS vuelve como TI.
    """
    conn = op.get_bind()
    inverso = {'TICS': 'TI', 'Gestión humana': 'Talento Humano'}
    for tabla, columnas in COLUMNAS_DE_AREA.items():
        if not _existe(tabla):
            continue
        for columna in columnas:
            for nuevo, viejo in inverso.items():
                conn.execute(
                    sa.text(f"UPDATE {tabla} SET {columna} = :viejo WHERE {columna} = :nuevo"),
                    {"viejo": viejo, "nuevo": nuevo},
                )
