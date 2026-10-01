"""
Lo que Mejora sabe medir sola, para el módulo de Indicadores.

Indicadores las reúne de cada módulo instalado (ver `core/registro.py`).
"""
from app.core.fuentes import Resultado
from app.modules.mejora import gestion


# La clave con la que se reconoce el indicador en todo el portal: la usa el
# botón que lo crea en cada área y el detector de «indicadores en rojo sin
# OMP», que lo excluye para no pedir una OMP sobre la gestión de las OMP.
CLAVE_GESTION_OMP = "mejora_gestion_omp"


def mejora_gestion_omp(db, tenant_id, anio, mes, area) -> Resultado:
    """
    % de OMP del área que estuvieron al día en el mes. La regla completa, y
    por qué se mide cada OMP viva y no solo las acciones del mes, está en
    `modules/mejora/gestion.py`.
    """
    al_dia, total, detalle = gestion.resumir(gestion.evaluar_mes(db, tenant_id, area, anio, mes))
    if not total:
        return Resultado(valor=None, numerador=0, denominador=0, detalle=detalle)
    return Resultado(
        valor=round(al_dia / total * 100, 2),
        numerador=al_dia, denominador=total, detalle=detalle,
    )


FUENTES = {
    CLAVE_GESTION_OMP: {
        "nombre": "Gestión de OMP",
        "modulo": "Mejora",
        "descripcion": (
            "Qué tanto lleva el área al día sus oportunidades de mejora: plan "
            "cumplido en su fecha original, avances cada mes y sin pasarse del plazo."
        ),
        "formula": "(OMP del área al día en el mes ÷ OMP del área abiertas en el mes) × 100",
        "unidad": "porcentaje", "direccion": "arriba", "fn": mejora_gestion_omp,
        # Se calcula con las OMP del área del indicador, no de toda la empresa.
        "por_area": True,
        # Uno en cada área, creado con el botón «Gestión de OMP en las áreas»
        # de Indicadores. La meta es la sugerida; cada área la ajusta.
        "una_por_area": {
            "nombre": "Gestión de OMP",
            "meta": 80, "umbral_verde": 80, "umbral_amarillo": 60,
        },
    },
}
