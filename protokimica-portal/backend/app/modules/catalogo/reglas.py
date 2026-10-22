"""
Qué productos del ERP se le ofrecen al cliente en el formulario público.

El ERP tiene unos 7.800 productos activos, y la mayoría no es algo por lo
que un cliente reclame: envases, tapas, etiquetas, cuentas de costos, o
productos que no se venden hace diez años. Las reglas salieron del análisis
de `integraciones/erp/analisis/explorar_productos.ipynb`.

**Esto solo decide qué ve el CLIENTE.** El catálogo guarda todos los
activos, y Servicio al Cliente los busca todos al confirmar un producto que
el cliente escribió a mano: un reclamo por algo comprado hace tres años es
raro pero existe, y si ese producto no estuviera, la PQRS no se podría
cerrar nunca (no se cierra con un producto sin confirmar). Por eso el filtro
no va en la consulta a Oracle.

Un producto va al formulario si cumple las tres:

  1. Es de una familia de producto (`FAMILIAS`, por el prefijo del código).
     Es una lista de las que SÍ: una familia nueva en el ERP no aparece en el
     formulario hasta que alguien decida que debe.
  2. Su grupo no es de envases, empaques ni costos (`GRUPOS_FUERA`). Hay
     materias primas y repuestos clasificados así aunque su prefijo sea de
     producto.
  3. Se vendió en los últimos `MESES_SIN_VENTA` meses.
"""
import re
from datetime import date

from app.core.periodos import meses_atras

# MP materias primas · DI · LR laboratorio · FS perfumería · AE equipos de
# laboratorio · IP seguridad · SK Salvak. Fuera, entre otras: ET envases y
# etiquetas, CO/CP/GA/AN costos y gastos, SV chatarra, MQ y ML.
FAMILIAS = ("MP", "DI", "LR", "FS", "AE", "IP", "SK")

GRUPOS_FUERA = re.compile(
    r"ENVASE|EMPAQUE|BOLSA|ETIQUETA|COSTO|GASTO|DESECHO|PAPELERIA|CAFETERIA|ASEO",
    re.IGNORECASE,
)

MESES_SIN_VENTA = 24


def va_al_formulario(codigo: str, grupo: str | None,
                     fecha_ultima_venta: date | None, hoy: date) -> bool:
    if (codigo or "")[:2].upper() not in FAMILIAS:
        return False
    if grupo and GRUPOS_FUERA.search(grupo):
        return False
    if fecha_ultima_venta is None:
        return False
    return fecha_ultima_venta >= meses_atras(hoy, MESES_SIN_VENTA)
