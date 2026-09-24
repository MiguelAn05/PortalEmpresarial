"""Las notas crédito del mostrador ya no pasan por Contabilidad

En la rama del punto de venta, Contabilidad tenía un turno —el estado
`solicitada`— entre la aprobación de Comercial y la emisión. Era una firma de
más: la decisión comercial ya está tomada, el punto emite contra su propia
factura y no hay nada que verificar ante la DIAN. La cadena del mostrador
queda en `en_comercial → aprobada`. La institucional no cambia.

Aquí lo único que hay que mover son las solicitudes que estaban paradas en
ese turno, y no todas significan lo mismo:

- **Las que Comercial ya había aprobado** quedan `aprobada`: bajo la cadena
  de hoy ya estarían listas para que el punto las emita, y devolverlas a
  Comercial sería pedirle que firme dos veces lo mismo.
- **Las que nunca pasaron por Comercial** —las del flujo viejo, cuando una
  del mostrador nacía directo en Contabilidad— van a `en_comercial`. Darlas
  por aprobadas sería aprobar en silencio algo que nadie miró, que es
  exactamente lo que este módulo existe para impedir.

La diferencia se lee del historial, no se adivina: `nc_historial` guarda cada
mano con su etapa y su acción.

Cada solicitud movida deja su renglón en el historial. Una que ayer decía
«Esperando a Contabilidad» y hoy dice «Aprobada» sin explicación se lee como
que alguien la aprobó a escondidas — y la cadena auditable es la razón de ser
del módulo.

El estado `solicitada` no se borra de ninguna parte: sigue siendo una etapa
válida DEL HISTORIAL para las que en su día sí autorizó Contabilidad.

Revision ID: c4d81e73ab20
Revises: b7e4c1a90d26
"""
import sqlalchemy as sa
from alembic import op

revision = "c4d81e73ab20"
down_revision = "b7e4c1a90d26"
branch_labels = None
depends_on = None

NOTA = ("Contabilidad dejó de autorizar las notas crédito de los puntos de "
        "venta: la decisión es de Comercial y el punto emite. ")

# Quien mira el historial tiene que entender por qué se movió sola.
NOTA_APROBADA = NOTA + "Comercial ya la había aprobado, así que queda lista para emitir."
NOTA_A_COMERCIAL = NOTA + "Todavía no había pasado por Comercial, así que vuelve a su turno."

# Una solicitud aprobada por Comercial deja este rastro exacto.
APROBO_COMERCIAL = sa.text("""
    EXISTS (
        SELECT 1 FROM nc_historial h
        WHERE h.solicitud_id = nc_solicitudes.id
          AND h.etapa = 'en_comercial'
          AND h.accion = 'aprobar'
    )
""")


def _mover(conexion, destino: str, comentario: str, ya_paso_comercial: bool) -> None:
    condicion = "" if ya_paso_comercial else "NOT "
    filtro = f"estado = 'solicitada' AND {condicion}{APROBO_COMERCIAL.text}"

    # El renglón del historial va ANTES del UPDATE: después ya no habría
    # forma de saber cuáles se movieron en esta corrida.
    conexion.execute(sa.text(f"""
        INSERT INTO nc_historial
            (tenant_id, solicitud_id, etapa, accion, usuario_id, usuario_nombre, comentario)
        SELECT tenant_id, id, 'solicitada', 'omitido', NULL, 'El portal', :comentario
        FROM nc_solicitudes WHERE {filtro}
    """), {"comentario": comentario})

    conexion.execute(sa.text(
        f"UPDATE nc_solicitudes SET estado = :destino WHERE {filtro}"
    ), {"destino": destino})


def upgrade():
    conexion = op.get_bind()
    _mover(conexion, "aprobada", NOTA_APROBADA, ya_paso_comercial=True)
    _mover(conexion, "en_comercial", NOTA_A_COMERCIAL, ya_paso_comercial=False)


def downgrade():
    """
    Devuelve a `solicitada` exactamente las que esta migración movió — se
    reconocen por el renglón que dejó en el historial, no por su estado
    actual: una que alguien aprobó o emitió de verdad después no se toca.
    """
    conexion = op.get_bind()
    conexion.execute(sa.text("""
        UPDATE nc_solicitudes SET estado = 'solicitada'
        WHERE estado IN ('aprobada', 'en_comercial')
          AND EXISTS (
              SELECT 1 FROM nc_historial h
              WHERE h.solicitud_id = nc_solicitudes.id AND h.accion = 'omitido'
          )
    """))
    conexion.execute(sa.text("DELETE FROM nc_historial WHERE accion = 'omitido'"))
