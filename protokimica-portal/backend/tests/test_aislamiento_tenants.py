"""
Aislamiento entre empresas.

Si el portal se le vende a varias empresas, esta es LA prueba: que nada de
una se vea desde la otra, ni siquiera adivinando el número de un registro.
Un fallo aquí no es un error de interfaz, es una fuga de datos entre
clientes.

Se prueba pidiendo los recursos de la empresa B con la sesión de la A, por
id directo — que es justo lo que haría alguien curioso cambiando el número
en la URL.
"""
import pytest

from app.models.indicadores import Indicador
from app.models.master_planner import Proyecto, Tarea
from app.models.mejora import Oportunidad
from app.models.pqrs import PQRSSolicitud
from app.models.tenant import Tenant
from app.models.user import User


@pytest.fixture
def otra_empresa(entorno):
    """Una segunda empresa con datos propios, creada por debajo de la API."""
    db = entorno.Session()

    tenant = Tenant(nombre="Otra Empresa SAS", slug="otra-empresa")
    db.add(tenant)
    db.commit()

    intruso = User(
        tenant_id=tenant.id, nombre="Ajeno", email="ajeno@otra.com",
        password_hash="x", rol="admin", area="TICS", activo=True,
    )
    proyecto = Proyecto(tenant_id=tenant.id, nombre="Secreto industrial",
                        area="TICS", estado="en_ejecucion")
    pqrs = PQRSSolicitud(tenant_id=tenant.id, tipo="queja",
                         cliente_nombre="Cliente ajeno", descripcion="Confidencial",
                         estado="recibido", codigo_seguimiento="XX-9999")
    indicador = Indicador(tenant_id=tenant.id, nombre="Margen de la otra empresa",
                          unidad="porcentaje", direccion="arriba")
    omp = Oportunidad(tenant_id=tenant.id, titulo="Mejora ajena", codigo="OMP-9999-9999")
    db.add_all([intruso, proyecto, pqrs, indicador, omp])
    db.commit()

    tarea = Tarea(proyecto_id=proyecto.id, titulo="Tarea ajena")
    db.add(tarea)
    db.commit()

    datos = {
        "proyecto": proyecto.id, "tarea": tarea.id, "pqrs": pqrs.id,
        "indicador": indicador.id, "omp": omp.id, "tenant": tenant.id,
    }
    db.close()
    return datos


# El admin de la empresa A es el peor caso: si alguien puede cruzar la
# frontera, es quien más permisos tiene dentro de la suya.
RECURSOS = [
    ("proyecto", "/master-planner/proyectos/{}"),
    ("tarea", "/master-planner/tareas/{}"),
    ("pqrs", "/pqrs/{}"),
    ("indicador", "/indicadores/{}"),
    ("omp", "/mejora/{}"),
]


@pytest.mark.parametrize("clave,ruta", RECURSOS)
def test_no_se_abre_un_registro_de_otra_empresa(entorno, otra_empresa, clave, ruta):
    entorno.como("admin")
    r = entorno.get(ruta.format(otra_empresa[clave]))

    assert r.status_code == 404, (
        f"FUGA: {ruta} devolvió {r.status_code} para un registro de otra "
        f"empresa. Respuesta: {r.text[:200]}"
    )


LISTADOS = [
    ("/master-planner/proyectos", "Secreto industrial"),
    ("/pqrs", "Cliente ajeno"),
    ("/mejora", "Mejora ajena"),
]


@pytest.mark.parametrize("ruta,texto_ajeno", LISTADOS)
def test_los_listados_no_traen_nada_de_otra_empresa(entorno, otra_empresa, ruta, texto_ajeno):
    entorno.como("admin")
    r = entorno.get(ruta)

    assert r.status_code == 200, r.text
    assert texto_ajeno not in r.text, f"FUGA: {ruta} incluyó datos de otra empresa"


def test_no_se_pueden_listar_los_usuarios_de_otra_empresa(entorno, otra_empresa):
    entorno.como("admin")
    correos = {u["email"] for u in entorno.get("/auth/usuarios").json()}

    assert "ajeno@otra.com" not in correos, "FUGA: se ven usuarios de otra empresa"


def test_no_se_puede_editar_un_registro_de_otra_empresa(entorno, otra_empresa):
    """Leer es grave; escribir en los datos de otro cliente es peor."""
    entorno.como("admin")
    r = entorno.patch(
        f"/master-planner/proyectos/{otra_empresa['proyecto']}",
        json={"nombre": "Intervenido"},
    )
    assert r.status_code == 404, f"FUGA DE ESCRITURA: {r.status_code}"


def test_el_inicio_no_cuenta_datos_de_otra_empresa(entorno, otra_empresa):
    """
    Los totales son la fuga silenciosa: no muestran el dato ajeno, pero lo
    suman. Un competidor sabría cuántos proyectos mueve el otro.
    """
    entorno.como("admin")
    empresa = entorno.get("/inicio").json().get("empresa") or {}

    # La empresa A no tiene proyectos propios en este entorno: si el conteo
    # trae alguno, viene del otro tenant.
    assert empresa.get("proyectos_activos", 0) == 0, (
        f"FUGA EN TOTALES: el inicio contó {empresa.get('proyectos_activos')} "
        "proyectos, y ninguno es de esta empresa"
    )
