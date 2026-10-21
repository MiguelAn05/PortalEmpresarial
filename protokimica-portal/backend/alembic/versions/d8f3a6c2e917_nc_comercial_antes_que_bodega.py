"""Nota crédito institucional: Comercial antes que la bodega

La cadena de una nota crédito institucional con producto era
`en_bodega → en_comercial → en_contabilidad → aprobada`, y pasa a ser
`en_comercial → en_bodega → en_contabilidad → aprobada`: si Comercial la
rechaza, la bodega no tenía nada que confirmar.

El estado dice de quién es el turno, así que hay que mirar las que van en
camino:

- **Esperando a la bodega (`en_bodega`)**: no han pasado por Comercial. Si
  se dejaran ahí, al confirmar la bodega seguirían a Contabilidad y **se
  saltarían a Comercial**. Van a `en_comercial`; después de Comercial vuelven
  a la bodega, que es el orden nuevo.
- **Esperando a Comercial (`en_comercial`)** con bodega ya confirmada: están
  en el sitio correcto. Al aprobar, el orden nuevo las manda a la bodega otra
  vez —una confirmación de más, nunca un paso saltado—. Se dejan así.
- Las demás no cambian: Contabilidad y emitir van después de los dos.

Cada solicitud movida deja su renglón en el historial, como en
`c4d81e73ab20`: una que ayer decía «Esperando a la bodega» y hoy dice
«Esperando a Comercial» sin explicación se lee como un error.

Revision ID: d8f3a6c2e917
Revises: b7d41e9a2c63
"""
import sqlalchemy as sa
from alembic import op

revision = "d8f3a6c2e917"
down_revision = "b7d41e9a2c63"
branch_labels = None
depends_on = None

# Con este texto exacto el downgrade reconoce las que movió esta migración.
NOTA = ("Cambió el orden del flujo: Comercial aprueba antes de que la bodega "
        "confirme. Todavía no había pasado por Comercial, así que vuelve a su turno.")


def upgrade():
    conexion = op.get_bind()
    # El renglón del historial va ANTES del UPDATE: después ya no habría forma
    # de saber cuáles se movieron en esta corrida.
    conexion.execute(sa.text("""
        INSERT INTO nc_historial
            (tenant_id, solicitud_id, etapa, accion, usuario_id, usuario_nombre, comentario)
        SELECT tenant_id, id, 'en_bodega', 'omitido', NULL, 'El portal', :nota
        FROM nc_solicitudes WHERE estado = 'en_bodega'
    """), {"nota": NOTA})
    conexion.execute(sa.text(
        "UPDATE nc_solicitudes SET estado = 'en_comercial' WHERE estado = 'en_bodega'"
    ))


def downgrade():
    """
    Devuelve a la bodega exactamente las que movió esta migración y que
    siguen esperando a Comercial: una que Comercial ya aprobó después no se
    toca.
    """
    conexion = op.get_bind()
    conexion.execute(sa.text("""
        UPDATE nc_solicitudes SET estado = 'en_bodega'
        WHERE estado = 'en_comercial'
          AND EXISTS (
              SELECT 1 FROM nc_historial h
              WHERE h.solicitud_id = nc_solicitudes.id
                AND h.accion = 'omitido' AND h.comentario = :nota
          )
    """), {"nota": NOTA})
    conexion.execute(sa.text(
        "DELETE FROM nc_historial WHERE accion = 'omitido' AND comentario = :nota"
    ), {"nota": NOTA})
