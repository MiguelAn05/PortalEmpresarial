"""
Qué módulos tiene contratados cada empresa, y cambiarlo.

    docker exec protokimica_backend python -m app.scripts.modulos                       # ver todas
    docker exec protokimica_backend python -m app.scripts.modulos protokimica           # ver una
    docker exec protokimica_backend python -m app.scripts.modulos protokimica --activar mejora
    docker exec protokimica_backend python -m app.scripts.modulos protokimica --desactivar encuestas

Es de consola y no una pantalla a propósito: el `admin` de una empresa
administra SU portal, pero qué módulos tiene es lo que la empresa compró, y
eso no se lo puede cambiar ella misma.

Activar un módulo activa también los que requiere (Mejora trae Indicadores).
Desactivar no borra nada: los datos siguen ahí y vuelven a verse el día que
se reactive. Desactivar uno del que otro depende avisa y no lo hace.
"""
import argparse
import sys

from app.core.database import SessionLocal
from app.core.modulos import BASE, CONTRATABLES, contratados_de, contratar
from app.main import app  # noqa: F401  (carga todos los modelos)
from app.models.tenant import Tenant, TenantModulo


def _mostrar(tenant: Tenant) -> None:
    abiertos = contratados_de(tenant)
    print(f"\n{tenant.nombre} ({tenant.slug})")
    for clave, cfg in CONTRATABLES.items():
        marca = "sí" if clave in abiertos else "no"
        print(f"  [{marca:>2}] {clave:<15} {cfg['nombre']}")
    print(f"  Siempre incluidos: {', '.join(BASE)}")


def _desactivar(db, tenant: Tenant, clave: str) -> None:
    if clave not in CONTRATABLES:
        sys.exit(f"«{clave}» no es un módulo contratable. Los que hay: {', '.join(CONTRATABLES)}.")
    dependientes = [
        c for c, cfg in CONTRATABLES.items()
        if clave in cfg["requiere"] and c in tenant.modulos_contratados
    ]
    if dependientes:
        sys.exit(
            f"No se desactivó: {', '.join(dependientes)} necesita «{clave}». "
            "Desactiva primero ese."
        )
    fila = db.query(TenantModulo).filter_by(tenant_id=tenant.id, modulo=clave).first()
    if fila and fila.activo:
        fila.activo = False
        print(f"Desactivado: {clave}. Sus datos se conservan.")
    else:
        print(f"«{clave}» ya estaba desactivado.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Módulos contratados por empresa.")
    parser.add_argument("slug", nargs="?", help="la empresa; sin esto se listan todas")
    parser.add_argument("--activar", nargs="+", default=[], metavar="MODULO")
    parser.add_argument("--desactivar", nargs="+", default=[], metavar="MODULO")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if not args.slug:
            for tenant in db.query(Tenant).order_by(Tenant.id).all():
                _mostrar(tenant)
            return

        tenant = db.query(Tenant).filter(Tenant.slug == args.slug).first()
        if not tenant:
            sys.exit(f"No existe la empresa «{args.slug}».")

        if args.activar:
            try:
                activados = contratar(db, tenant.id, args.activar)
            except ValueError as e:
                sys.exit(str(e))
            print(f"Activados: {', '.join(activados) or 'ninguno nuevo'}")
        for clave in args.desactivar:
            _desactivar(db, tenant, clave)
        db.commit()
        db.refresh(tenant)
        _mostrar(tenant)
    finally:
        db.close()


if __name__ == "__main__":
    main()
