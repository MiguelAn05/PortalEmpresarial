"""
Cada empresa abre solo los módulos que tiene contratados.

El portal se vende por módulos. Antes de esto el único control era el rol:
cualquier empresa con el código instalado abría todo. Ahora manda el
contrato (`tenant_modulos`, ver `core/modulos.py`), y lo que se prueba aquí
es que un módulo no contratado no se abre por NINGUNA puerta: ni su
pantalla, ni su API, ni sus páginas públicas, ni sus fuentes en Indicadores,
ni su tarjeta en Inicio.
"""
from fastapi.routing import APIRoute

from app.core.modulos import CONTRATABLE_DE_PAQUETE, contratados_de
from app.main import app
from app.models.indicadores import Indicador
from app.models.tenant import Tenant, TenantModulo


def _apagar(entorno, *modulos):
    db = entorno.Session()
    db.query(TenantModulo).filter(
        TenantModulo.tenant_id == entorno.tenant_id,
        TenantModulo.modulo.in_(modulos),
    ).update({"activo": False}, synchronize_session=False)
    db.commit()
    db.close()


# ── Lo que se cierra ──────────────────────────────────────────

def test_sin_pqrs_no_se_abre_ni_por_la_api_ni_por_lo_publico(entorno, v):
    _apagar(entorno, "pqrs")

    r = entorno.get("/pqrs")
    v.check("la lista de PQRS -> 403", r.status_code == 403, r.status_code)
    v.check("y dice qué pasa y qué hacer", "no tiene contratado" in r.text, r.text[:150])
    v.check("las autorizaciones van con PQRS",
            entorno.get("/autorizaciones/tipos").status_code == 403)
    v.check("el buscador interno del catálogo también",
            entorno.get("/catalogo/productos?q=a").status_code == 403)

    # Lo público responde como si no existiera: un cliente con un QR viejo
    # no tiene por qué enterarse de qué contrató la empresa.
    v.check("los QR públicos -> 404", entorno.get("/public/qr").status_code == 404)
    v.check("la consulta pública -> 404", entorno.get("/public/pqrs/PVG0001").status_code == 404)
    v.check("el catálogo público -> 404",
            entorno.get("/public/catalogo/productos?q=a").status_code == 404)


def test_ni_admin_entra_a_lo_que_no_se_contrato(entorno, v):
    _apagar(entorno, "encuestas")
    entorno.como("admin")
    v.check("admin no abre Encuestas", entorno.get("/encuestas").status_code == 403)
    v.check("y lo demás sigue abierto", entorno.get("/pqrs").status_code == 200)


def test_requiere_modulo_mira_el_contrato_antes_que_el_rol(entorno, v):
    _apagar(entorno, "indicadores", "mejora")
    entorno.como("tics")
    r = entorno.get("/indicadores")
    v.check("un líder sin Indicadores contratado -> 403", r.status_code == 403)
    v.check("y el motivo es el contrato, no el rol", "no tiene contratado" in r.text, r.text[:150])


def test_mejora_sin_indicadores_no_cuenta(entorno, v):
    """Mejora verifica contra un indicador: sin Indicadores no sirve."""
    _apagar(entorno, "indicadores")
    db = entorno.Session()
    abiertos = contratados_de(db.get(Tenant, entorno.tenant_id))
    db.close()
    v.check("Mejora queda cerrado aunque su fila esté activa", "mejora" not in abiertos, abiertos)
    v.check("el endpoint lo confirma", entorno.get("/mejora").status_code == 403)


def test_una_empresa_sin_contrato_tiene_solo_la_base(entorno, v):
    db = entorno.Session()
    nueva = Tenant(nombre="Recién llegada", slug="recien")
    db.add(nueva)
    db.commit()
    abiertos = contratados_de(nueva)
    db.close()
    v.check("solo Inicio y Administración", abiertos == {"inicio", "admin"}, abiertos)


# ── Lo que se esconde dentro de los módulos que sí están ─────

def test_inicio_no_trae_la_tarjeta_de_un_modulo_no_contratado(entorno, v):
    _apagar(entorno, "pqrs")
    r = entorno.get("/inicio")
    v.check("Inicio responde", r.status_code == 200, r.text[:150])
    datos = r.json()
    v.check("sin la tarjeta de PQRS", "mis_pqrs" not in datos, list(datos))
    v.check("con la del Master Planner", "mis_tareas" in datos, list(datos))
    v.check("PQRS no sale entre los módulos", "pqrs" not in datos["modulos"], datos["modulos"])
    v.check("ni sus cifras en el titular", "pqrs_abiertas" not in (datos["empresa"] or {}),
            datos["empresa"])


def test_indicadores_no_ofrece_fuentes_de_lo_no_contratado(entorno, v):
    _apagar(entorno, "pqrs")
    claves = [f["clave"] for f in entorno.get("/indicadores/catalogo").json()]
    v.check("ninguna fuente de PQRS", not any(c.startswith("pqrs_") for c in claves), claves)
    v.check("las del Master Planner siguen", "mp_avance_proyectos" in claves, claves)

    r = entorno.post("/indicadores", json={
        "nombre": "Oportunidad PQRS", "unidad": "porcentaje", "tipo_captura": "automatico",
        "fuente_automatica": "pqrs_oportunidad_sla", "area": "Calidad",
        "meta": 90, "direccion": "arriba", "umbral_verde": 90, "umbral_amarillo": 75,
    })
    v.check("no se puede crear un indicador con esa fuente -> 400",
            r.status_code == 400, r.text[:150])


def test_un_indicador_de_un_modulo_que_se_dejo_de_tener_queda_sin_dato(entorno, v):
    """Creado cuando se tenía PQRS; si se deja de tener, no revienta ni dice cero."""
    from app.modules.indicadores import fuentes

    _apagar(entorno, "pqrs")
    db = entorno.Session()
    r = fuentes.calcular("pqrs_recibidas", db, entorno.tenant_id, 2026, 9)
    db.close()
    v.check("sin valor", r.valor is None, r)
    v.check("y dice por qué", "no está contratado" in (r.detalle or ""), r.detalle)


def test_gestion_omp_sin_mejora_responde_404(entorno, v):
    _apagar(entorno, "mejora")
    r = entorno.get("/indicadores/gestion-omp")
    v.check("404", r.status_code == 404, r.status_code)
    db = entorno.Session()
    v.check("y no crea nada",
            db.query(Indicador).filter(Indicador.fuente_automatica == "mejora_gestion_omp").count() == 0)
    db.close()


# ── Lo que ve la pantalla ─────────────────────────────────────

def test_me_le_dice_a_la_pantalla_que_modulos_tiene_la_empresa(entorno, v):
    _apagar(entorno, "encuestas")
    r = entorno.get("/auth/me")
    modulos = r.json()["modulos_contratados"]
    v.check("trae la base", {"inicio", "admin"} <= set(modulos), modulos)
    v.check("trae lo contratado", "pqrs" in modulos, modulos)
    v.check("y no lo apagado", "encuestas" not in modulos, modulos)


# ── Que ningún endpoint quede por fuera ───────────────────────

# Endpoints de módulos contratables que no pueden llevar la dependencia de
# router, cada uno con su motivo y su control propio.
SIN_DEPENDENCIA_DE_ROUTER = {
    # El ERP sincroniza con una clave, sin sesión de usuario: el contrato se
    # revisa adentro, contra la empresa del portal.
    "/catalogo/sincronizar",
}


def _dependencias(dependant):
    for d in dependant.dependencies:
        yield d.call
        yield from _dependencias(d)


def test_todo_endpoint_de_un_modulo_contratable_revisa_el_contrato():
    """
    El control va en el `APIRouter(dependencies=[...])` para que un endpoint
    nuevo quede cubierto el día que se escribe. Esta prueba falla si alguien
    arma un router nuevo de un módulo y se le olvida.
    """
    sin_control = []
    for ruta in app.routes:
        if not isinstance(ruta, APIRoute):
            continue
        partes = ruta.endpoint.__module__.split(".")
        if partes[:2] != ["app", "modules"] or partes[2] not in CONTRATABLE_DE_PAQUETE:
            continue
        if ruta.path in SIN_DEPENDENCIA_DE_ROUTER:
            continue
        nombres = {getattr(c, "__qualname__", "") for c in _dependencias(ruta.dependant)}
        if not any(n.startswith(("contratado", "requiere_modulo")) for n in nombres):
            sin_control.append(f"{sorted(ruta.methods)} {ruta.path}")
    assert not sin_control, (
        f"Estos endpoints no revisan si la empresa contrató el módulo: {sin_control}. "
        "Agrega dependencies=[Depends(contratado(...))] a su APIRouter, o "
        "contratado_en_publico(...) si es público."
    )
