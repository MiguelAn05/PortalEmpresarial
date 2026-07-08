"""
Script de datos iniciales (seed). Crea el tenant de Protokimica y un usuario
admin de prueba para poder loguearse de inmediato.

Uso (con el contenedor backend corriendo):
    docker compose exec backend python -m app.seed
"""
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.tenant import Tenant
from app.models.user import User


def run():
    db = SessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == "protokimica").first()
        if not tenant:
            tenant = Tenant(nombre="Protokimica", slug="protokimica")
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"✅ Tenant creado: {tenant.nombre} (id={tenant.id})")
        else:
            print(f"ℹ️  Tenant ya existía: {tenant.nombre} (id={tenant.id})")

        admin = (
            db.query(User)
            .filter(User.tenant_id == tenant.id, User.email == "admin@protokimica.com")
            .first()
        )
        if not admin:
            admin = User(
                tenant_id=tenant.id,
                nombre="Administrador",
                email="admin@protokimica.com",
                password_hash=hash_password("Admin123!"),
                rol="admin",
                area="Sistemas",
            )
            db.add(admin)
            db.commit()
            print("✅ Usuario admin creado:")
            print("   email: admin@protokimica.com")
            print("   password: Admin123!")
            print("   ⚠️  Cambia esta contraseña apenas puedas entrar.")
        else:
            print("ℹ️  Usuario admin ya existía.")

    finally:
        db.close()


if __name__ == "__main__":
    run()
