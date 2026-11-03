"""
El permiso de registrar, en las sedes, vale solo para SU mostrador.

Para que un punto de venta emita sus notas crédito, `notas_credito.registrar`
se le otorga al área de las sedes. Ese mismo permiso es el que le abre a
Contabilidad las institucionales y el módulo completo, así que sin un corte
darle a las sedes lo que necesitan para emitir:

  - les mostraba las notas de los otros cinco puntos y las institucionales;
  - y las dejaba registrar el número de una institucional.

Lo que se protege aquí:
  - el punto ve y emite las de su mostrador, nada más (lo ajeno, 404);
  - el coordinador (sin punto) ve las de todos los puntos, no las
    institucionales;
  - las institucionales las sigue emitiendo Contabilidad, nunca una sede;
  - Contabilidad sigue viéndolo todo.
"""
from app.core.capacidades import otorgar_a_area
from app.models.nota_credito import SolicitudNotaCredito
from app.models.user import User
from app.modules.notas_credito.permisos import CAP_REGISTRAR, emisores

GUAYABAL = "Punto de venta Guayabal"
BELEN = "Punto de venta Belén"
INSTITUCIONAL = "Venta institucional"


def _usuario(entorno, clave, punto=None, area="Puntos de Venta"):
    db = entorno.Session()
    u = User(tenant_id=entorno.tenant_id, nombre=clave.title(), email=f"{clave}@p.com",
             password_hash="x", rol="agente", area=area, punto_venta=punto, activo=True)
    db.add(u)
    db.commit()
    entorno.ids[clave] = u.id
    db.close()


def _registrar_a(entorno, area):
    db = entorno.Session()
    otorgar_a_area(db, entorno.tenant_id, CAP_REGISTRAR, area, entorno.ids["admin"])
    db.commit()
    db.close()


def _aprobada(entorno, punto, codigo):
    """Una solicitud ya aprobada por Comercial: lo que falta es emitirla."""
    db = entorno.Session()
    s = SolicitudNotaCredito(
        tenant_id=entorno.tenant_id, codigo=codigo, punto_venta=punto,
        factura_afectada="FV-100", observaciones="Producto devuelto.",
        solicitado_por=entorno.ids["admin"], estado="aprobada",
        institucional=punto == INSTITUCIONAL,
    )
    db.add(s)
    db.commit()
    sid = s.id
    db.close()
    return sid


def _tres_solicitudes(entorno):
    return (
        _aprobada(entorno, GUAYABAL, "NC-2026-0001"),
        _aprobada(entorno, BELEN, "NC-2026-0002"),
        _aprobada(entorno, INSTITUCIONAL, "NC-2026-0003"),
    )


def _codigos(entorno, **params):
    return sorted(s["codigo"] for s in entorno.get("/notas-credito", params=params).json())


def test_el_punto_ve_y_emite_solo_las_de_su_mostrador(entorno, v):
    _registrar_a(entorno, "Puntos de Venta")
    _usuario(entorno, "guayabal1", punto="PVG")
    guayabal, belen, institucional = _tres_solicitudes(entorno)

    entorno.como("guayabal1")
    v.check("en su lista solo la de Guayabal", _codigos(entorno) == ["NC-2026-0001"], _codigos(entorno))
    v.check("y en «Mi turno» también",
            _codigos(entorno, estado="mi_turno") == ["NC-2026-0001"], _codigos(entorno, estado="mi_turno"))
    v.check("la de Belén no la abre -> 404",
            entorno.get(f"/notas-credito/{belen}").status_code == 404)
    v.check("ni la institucional -> 404",
            entorno.get(f"/notas-credito/{institucional}").status_code == 404)

    r = entorno.post(f"/notas-credito/{institucional}/aplicar", json={"numero_nc": "NC-1"})
    v.check("no registra el número de una institucional", r.status_code == 404, r.text[:200])
    r = entorno.post(f"/notas-credito/{guayabal}/aplicar", json={"numero_nc": "NC-2"})
    v.check("la suya sí la emite", r.status_code == 200, r.text[:200])


def test_el_coordinador_ve_todos_los_puntos_pero_no_las_institucionales(entorno, v):
    _registrar_a(entorno, "Puntos de Venta")
    _usuario(entorno, "coord", punto=None)
    _tres_solicitudes(entorno)

    entorno.como("coord")
    v.check("las dos del mostrador, sin la institucional",
            _codigos(entorno) == ["NC-2026-0001", "NC-2026-0002"], _codigos(entorno))


def test_las_institucionales_las_emite_contabilidad_y_no_una_sede(entorno, v):
    _registrar_a(entorno, "Puntos de Venta")
    _registrar_a(entorno, "Contabilidad")
    _usuario(entorno, "guayabal1", punto="PVG")
    _usuario(entorno, "coord", punto=None)
    _usuario(entorno, "conta1", area="Contabilidad")
    _, _, institucional = _tres_solicitudes(entorno)

    db = entorno.Session()
    quienes = sorted(u.email for u in emisores(db, entorno.tenant_id,
                                                db.get(SolicitudNotaCredito, institucional)))
    db.close()
    v.check("solo Contabilidad", quienes == ["conta1@p.com"], quienes)


def test_contabilidad_lo_sigue_viendo_todo(entorno, v):
    _registrar_a(entorno, "Puntos de Venta")
    _registrar_a(entorno, "Contabilidad")
    _usuario(entorno, "conta1", area="Contabilidad")
    _tres_solicitudes(entorno)

    entorno.como("conta1")
    v.check("las tres", len(_codigos(entorno)) == 3, _codigos(entorno))
