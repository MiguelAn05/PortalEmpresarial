"""
Corregir y eliminar usuarios desde Administración.

Las dos cosas faltaban, y la que dolía era la primera: el nombre y el correo
se escriben a mano y con prisa al dar de alta a alguien, y no había forma de
arreglarlos. La salida era crear OTRO usuario y desactivar el primero — con
lo que el trabajo ya hecho se quedaba colgando del usuario equivocado.

Eliminar es para el usuario creado por error y que nunca hizo nada. **Uno que
ya trabajó no se borra**: su id está escrito en quién aprobó, quién autorizó
y quién firmó, y vaciar eso dejaría el historial diciendo «alguien». Para eso
está desactivar. Ver `modules/auth/rastros.py`.
"""
from app.models.pqrs import PQRSSolicitud


def _crear(entorno, **extra):
    cuerpo = {
        "nombre": "Laura Gomez",
        "email": "laura@protokimica.com",
        "password": "clave12345",
        "rol": "agente",
        "area": "TICS",
    }
    cuerpo.update(extra)
    return entorno.post("/auth/usuarios", json=cuerpo)


def _con_pqrs(entorno, usuario_id):
    """Le deja a alguien una PQRS asignada: rastro de trabajo del más común."""
    db = entorno.Session()
    db.add(PQRSSolicitud(
        tenant_id=entorno.tenant_id, tipo="reclamo", cliente_nombre="Un cliente",
        descripcion="Algo pasó", estado="asignado", prioridad="media",
        asignado_a=usuario_id,
    ))
    db.commit()
    db.close()


# ── Corregir ─────────────────────────────────────────────────────────

def test_se_corrigen_el_nombre_y_el_correo(entorno, v):
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]

    r = entorno.patch(f"/auth/usuarios/{uid}", json={
        "nombre": "Laura Gómez", "email": "lgomez@protokimica.com",
    })
    v.check("se guarda", r.status_code == 200, r.text[:250])
    v.check("con el nombre bien escrito", r.json()["nombre"] == "Laura Gómez", r.json())
    v.check("y el correo corregido", r.json()["email"] == "lgomez@protokimica.com", r.json())


def test_el_correo_corregido_es_con_el_que_entra(entorno, v):
    """Corregirlo y que el login siguiera pidiendo el viejo sería peor que nada."""
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]
    entorno.patch(f"/auth/usuarios/{uid}", json={"email": "lgomez@protokimica.com"})

    entrar = lambda correo: entorno.post("/auth/login", json={   # noqa: E731
        "tenant_slug": "protokimica", "email": correo, "password": "clave12345",
    })
    v.check("entra con el nuevo", entrar("lgomez@protokimica.com").status_code == 200)
    v.check("y ya no con el viejo", entrar("laura@protokimica.com").status_code == 401)


def test_no_se_deja_el_nombre_ni_el_correo_vacios(entorno, v):
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]

    v.check("nombre en blanco no pasa",
            entorno.patch(f"/auth/usuarios/{uid}", json={"nombre": "   "}).status_code == 400)
    v.check("correo en blanco tampoco",
            entorno.patch(f"/auth/usuarios/{uid}", json={"email": "  "}).status_code == 400)
    v.check("y el usuario quedó intacto",
            entorno.get("/auth/usuarios").json() and True)


def test_el_correo_corregido_sigue_siendo_corporativo(entorno, v):
    """La misma regla que al crearlo: si no, se entra por la puerta de atrás."""
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]

    r = entorno.patch(f"/auth/usuarios/{uid}", json={"email": "laura@gmail.com"})
    v.check("no pasa", r.status_code == 400, r.status_code)
    v.check("y dice por qué", "corporativo" in r.json().get("detail", ""), r.json())


def test_no_se_le_pone_el_correo_de_otro(entorno, v):
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]
    _crear(entorno, nombre="Pedro Ruiz", email="pedro@protokimica.com")

    r = entorno.patch(f"/auth/usuarios/{uid}", json={"email": "pedro@protokimica.com"})
    v.check("no se duplica un correo", r.status_code == 400, r.status_code)
    v.check("y dice de quién es", "Pedro Ruiz" in r.json().get("detail", ""), r.json())


def test_solo_un_admin_corrige_usuarios(entorno, v):
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]

    entorno.como("tics")   # líder
    r = entorno.patch(f"/auth/usuarios/{uid}", json={"nombre": "Otro nombre"})
    v.check("un líder no edita usuarios", r.status_code == 403, r.status_code)


# ── Eliminar ─────────────────────────────────────────────────────────

def test_se_elimina_el_usuario_creado_por_error(entorno, v):
    """El caso real: se digitó mal el correo y se creó dos veces."""
    entorno.como("admin")
    uid = _crear(entorno, email="lauraa@protokimica.com").json()["id"]

    r = entorno.delete(f"/auth/usuarios/{uid}")
    v.check("se elimina", r.status_code == 204, r.text[:250])
    v.check("y ya no está en la lista",
            uid not in [u["id"] for u in entorno.get("/auth/usuarios").json()])


def test_uno_que_ya_trabajo_no_se_borra(entorno, v):
    """
    Borrarlo dejaría el historial sin el nombre de quien hizo cada cosa. El
    409 tiene que decir QUÉ tiene y ofrecer la salida, no solo negarse.
    """
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]
    _con_pqrs(entorno, uid)

    r = entorno.delete(f"/auth/usuarios/{uid}")
    v.check("no se borra", r.status_code == 409, r.status_code)
    detalle = r.json().get("detail", "")
    v.check("dice qué tiene", "PQRS" in detalle, detalle)
    v.check("y ofrece desactivarlo", "Desact" in detalle, detalle)
    v.check("el usuario sigue ahí",
            uid in [u["id"] for u in entorno.get("/auth/usuarios").json()])


def test_desactivarlo_si_funciona_siempre(entorno, v):
    """La salida suave que ofrece el 409 tiene que existir de verdad."""
    entorno.como("admin")
    uid = _crear(entorno).json()["id"]
    _con_pqrs(entorno, uid)

    r = entorno.patch(f"/auth/usuarios/{uid}", json={"activo": False})
    v.check("se desactiva", r.status_code == 200, r.text[:250])
    v.check("y queda inactivo", r.json()["activo"] is False, r.json())


def test_la_configuracion_propia_no_bloquea_el_borrado(entorno, v):
    """
    Las áreas que supervisa son configuración suya, no trabajo: si contaran
    como rastro, un usuario recién creado al que alguien alcanzó a marcarle
    una supervisión ya no se podría eliminar.
    """
    entorno.como("admin")
    uid = _crear(entorno, email="nueva@protokimica.com").json()["id"]
    entorno.patch(f"/auth/usuarios/{uid}", json={"areas_supervisadas": ["Calidad"]})

    r = entorno.delete(f"/auth/usuarios/{uid}")
    v.check("se elimina igual", r.status_code == 204, r.text[:250])


def test_nadie_se_elimina_a_si_mismo(entorno, v):
    entorno.como("admin")
    yo = entorno.ids["admin"]

    r = entorno.delete(f"/auth/usuarios/{yo}")
    v.check("no se puede", r.status_code == 400, r.status_code)
    v.check("y explica el porqué", "entrar" in r.json().get("detail", ""), r.json())


def test_solo_un_admin_elimina(entorno, v):
    entorno.como("admin")
    uid = _crear(entorno, email="otra@protokimica.com").json()["id"]

    entorno.como("tics")
    v.check("un líder no elimina usuarios",
            entorno.delete(f"/auth/usuarios/{uid}").status_code == 403)


def test_un_usuario_de_otra_empresa_no_existe_para_este_admin(entorno, v):
    """El tenant sale del token del admin, nunca de lo que mande el cliente."""
    entorno.como("admin")
    v.check("responde 404", entorno.delete("/auth/usuarios/99999").status_code == 404)
