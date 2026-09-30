"""
Ningún módulo puede depender de PQRS para lo que es de todo el portal.

Guardar archivos y avisar a n8n vivían dentro de PQRS, y Master Planner,
Indicadores, Notas crédito y Autorizaciones los importaban de ahí: ninguno se
podía instalar sin PQRS. Hoy están en `core/archivos.py` y
`core/notificaciones.py`. Esta prueba falla si alguien vuelve a importar de
PQRS desde otro módulo, que es la forma más fácil de deshacerlo sin notarlo.

Las excepciones van escritas con su motivo. Quitar una es la meta; agregar
una debería doler.
"""
import re
from pathlib import Path

MODULOS = Path(__file__).resolve().parent.parent / "app" / "modules"

IMPORTA_PQRS = re.compile(r"^\s*(?:from|import)\s+app\.modules\.pqrs\b", re.M)

EXCEPCIONES = {
    # Las autorizaciones son parte de PQRS: se piden sobre una PQRS y se
    # venden con ella.
    "autorizaciones",
    # Inicio resume todos los módulos. Pasa a que cada módulo aporte sus
    # propias tarjetas en la fase 2 del plan de modularización.
    "inicio",
}


def test_ningun_modulo_importa_de_pqrs_salvo_las_excepciones():
    culpables = []
    for archivo in MODULOS.rglob("*.py"):
        modulo = archivo.relative_to(MODULOS).parts[0]
        if modulo in ("pqrs", *EXCEPCIONES):
            continue
        if IMPORTA_PQRS.search(archivo.read_text(encoding="utf-8")):
            culpables.append(str(archivo.relative_to(MODULOS)))
    assert not culpables, (
        f"Estos archivos importan de app.modules.pqrs: {culpables}. "
        "Si es para guardar archivos o avisar a n8n, usa app.core.archivos o "
        "app.core.notificaciones; si es otra cosa que usan varios módulos, "
        "súbela a app/core."
    )


def test_las_utilidades_compartidas_no_volvieron_a_pqrs():
    """Que nadie las vuelva a definir dentro de PQRS «para tenerlas a mano»."""
    for archivo in (MODULOS / "pqrs").rglob("*.py"):
        texto = archivo.read_text(encoding="utf-8")
        for nombre in ("guardar_archivo", "disparar_webhook_n8n", "enviar_avisos", "con_zona"):
            assert not re.search(rf"^(?:async\s+)?def {nombre}\(", texto, re.M), (
                f"{archivo.name} vuelve a definir {nombre}(); vive en app/core."
            )
