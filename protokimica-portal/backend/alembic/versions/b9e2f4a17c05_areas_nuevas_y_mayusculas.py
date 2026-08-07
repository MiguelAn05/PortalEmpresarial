"""areas nuevas y unificacion de mayusculas

Se agregaron cinco areas (Produccion, Control Interno, Aseguramiento,
Abastecimiento, Comercial) y se unifico la escritura a Mayuscula Inicial en
cada palabra.

El cambio de mayusculas NO es cosmetico: el area se compara como texto en
varios sitios. En particular, quien puede cerrar una PQRS se decide con
`usuario.area == "Servicio al Cliente"`, asi que dejar registros con
"Servicio al cliente" (c minuscula) haria que esas personas perdieran el
permiso sin ningun error visible.

Revision ID: b9e2f4a17c05
Revises: f1c6d80a5b47
Create Date: 2026-08-07 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b9e2f4a17c05'
down_revision = 'f1c6d80a5b47'
branch_labels = None
depends_on = None

COLUMNAS_DE_AREA = {
    'users': ['area'],
    'pqrs_solicitudes': ['area_responsable', 'area_causante'],
    'mp_proyectos': ['area'],
    'mp_proyecto_areas': ['area'],
    'mp_tareas': ['area'],
    'ind_indicadores': ['area'],
}

RENOMBRES = {
    'Servicio al cliente': 'Servicio al Cliente',
    'Ventas institucionales': 'Ventas Institucionales',
    'Gestión humana': 'Gestión Humana',
    # Por si quedo algun rezagado de la migracion anterior.
    'Talento Humano': 'Gestión Humana',
    'TI': 'TICS',
    'Sistemas': 'TICS',
}


def _existe(tabla: str) -> bool:
    return tabla in sa.inspect(op.get_bind()).get_table_names()


def _aplicar(mapa: dict[str, str]) -> None:
    conn = op.get_bind()
    for tabla, columnas in COLUMNAS_DE_AREA.items():
        if not _existe(tabla):
            continue
        for columna in columnas:
            for viejo, nuevo in mapa.items():
                conn.execute(
                    sa.text(f"UPDATE {tabla} SET {columna} = :nuevo WHERE {columna} = :viejo"),
                    {"nuevo": nuevo, "viejo": viejo},
                )


def upgrade() -> None:
    _aplicar(RENOMBRES)


def downgrade() -> None:
    """
    Vuelve a la escritura anterior. TICS no se revierte: fusiono "TI" y
    "Sistemas" y no hay forma de saber cual era cual.
    """
    _aplicar({
        'Servicio al Cliente': 'Servicio al cliente',
        'Ventas Institucionales': 'Ventas institucionales',
        'Gestión Humana': 'Gestión humana',
    })
