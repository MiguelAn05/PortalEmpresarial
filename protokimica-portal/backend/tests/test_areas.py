"""
Reglas de las áreas.

La verificación de que el backend y el frontend digan lo mismo NO está aquí:
el contenedor solo monta `backend/`, así que no puede leer `areas.js`. Esa
comprobación vive en `frontend/tests/areas.test.mjs`, que corre en la máquina
y sí ve los dos archivos.
"""
from app.core.areas import AREAS, EQUIVALENCIAS_HISTORICAS, normalizar, es_valida

def test_no_hay_areas_repetidas():
    assert len(AREAS) == len(set(AREAS)), "Hay áreas duplicadas en la lista"


def test_toda_equivalencia_apunta_a_un_area_real():
    for viejo, nuevo in EQUIVALENCIAS_HISTORICAS.items():
        assert nuevo in AREAS, f"'{viejo}' apunta a '{nuevo}', que no está en la lista de áreas"
        assert viejo not in AREAS, f"'{viejo}' es un nombre viejo y no debería estar en la lista"


def test_normalizar_traduce_los_nombres_viejos():
    assert normalizar("TI") == "TICS"
    assert normalizar("Sistemas") == "TICS"
    assert normalizar("Talento Humano") == "Gestión humana"


def test_normalizar_deja_pasar_las_areas_actuales():
    for area in AREAS:
        assert normalizar(area) == area


def test_normalizar_limpia_los_vacios():
    # Cadena vacía y espacios vienen de formularios que envían "" en vez de nada.
    assert normalizar("") is None
    assert normalizar("   ") is None
    assert normalizar(None) is None
    assert normalizar("  Calidad  ") == "Calidad"


def test_es_valida():
    assert es_valida("Calidad")
    assert es_valida(None), "No tener área asignada es válido"
    assert not es_valida("TI"), "El nombre viejo ya no es un área válida"
    assert not es_valida("Inventada")


def test_las_areas_que_pidio_el_negocio_estan_todas():
    esperadas = {
        "TICS", "Calidad", "SST", "Controlados", "Facturación",
        "Ventas institucionales", "Mercadeo", "Servicio al cliente",
        "Infraestructura", "Logística", "Gestión humana", "Contabilidad",
    }
    assert set(AREAS) == esperadas
