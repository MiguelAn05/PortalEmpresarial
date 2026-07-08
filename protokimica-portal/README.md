# Portal de Gestión Empresarial — Protokimica

Monorepo: `backend/` (FastAPI + PostgreSQL) y `frontend/` (próximo paso, React + Vite).

Arquitectura modular: cada funcionalidad de negocio (PQRS, y luego Indicadores,
Proyectos, etc.) vive aislada en `backend/app/modules/<nombre>/` y se conecta
a la app con una sola línea en `main.py`. No hay que tocar otros módulos para
agregar uno nuevo.

---

## 1. Requisitos previos

- Docker Desktop instalado y corriendo
- Nada más — Python, PostgreSQL y Redis viven dentro de los contenedores

---

## 2. Levantar el entorno

Desde la raíz del proyecto:

```bash
docker compose up --build
```

Esto levanta 3 servicios:
- `db` → PostgreSQL en el puerto 5432
- `redis` → Redis en el puerto 6379
- `backend` → FastAPI en el puerto 8000 (con auto-reload al guardar cambios)

Cuando termine de construir, verifica que esté vivo:

```bash
curl http://localhost:8000/health
```

Debe responder: `{"status":"ok","app":"Protokimica Portal API","environment":"development"}`

También puedes abrir la documentación interactiva automática de la API en:
**http://localhost:8000/docs**

---

## 3. Crear las tablas en la base de datos (primera vez)

En otra terminal, con los contenedores corriendo:

```bash
docker compose exec backend alembic upgrade head
```

Esto crea las tablas: `tenants`, `users`, `pqrs_solicitudes`, `pqrs_seguimientos`, `pqrs_encuestas`.

---

## 4. Crear el tenant de Protokimica + usuario admin de prueba

```bash
docker compose exec backend python -m app.seed
```

Esto te va a dar un usuario para probar el login de inmediato:

```
email: admin@protokimica.com
password: Admin123!
tenant_slug: protokimica
```

⚠️ Cambia esta contraseña en cuanto tengas el flujo de "cambiar contraseña" o
crea tu propio usuario por `/auth/register` y desactiva este.

---

## 5. Probar el flujo completo en /docs

1. Ve a `http://localhost:8000/docs`
2. Abre `POST /auth/login`, prueba con las credenciales de arriba
3. Copia el `access_token` que te devuelve
4. Arriba a la derecha, click en **Authorize** y pega el token
5. Ya puedes probar `POST /pqrs` para crear una solicitud, `GET /pqrs` para listarlas, etc.

---

## 6. Registrar un nuevo usuario con cualquier correo

Cualquier persona puede registrarse con el correo que prefiera (corporativo o
personal), no depende de Microsoft Entra ID:

```
POST /auth/register
{
  "tenant_slug": "protokimica",
  "nombre": "Juan Rodríguez",
  "email": "juan.rodriguez@gmail.com",
  "password": "unaClaveSegura123",
  "rol": "agente",
  "area": "Comercial"
}
```

---

## 7. Estructura del proyecto

```
backend/
├── app/
│   ├── core/              ← compartido por TODOS los módulos (BD, seguridad, config)
│   ├── models/             ← modelos SQLAlchemy (tablas)
│   ├── modules/
│   │   ├── auth/           ← login, registro
│   │   └── pqrs/           ← módulo PQRS completo, aislado
│   ├── main.py             ← ensambla todos los módulos
│   └── seed.py              ← datos iniciales de prueba
├── alembic/                ← migraciones de base de datos
└── requirements.txt

frontend/                   ← próximo paso: React + Vite + Tailwind
```

### Cómo agregar el módulo de Indicadores más adelante (sin romper nada)

1. Crear `backend/app/modules/indicadores/` con su propio `router.py`, `schemas.py`, `service.py`
2. Crear `backend/app/models/indicador.py` con los modelos
3. En `main.py`, agregar:
   ```python
   from app.modules.indicadores.router import router as indicadores_router
   app.include_router(indicadores_router)
   ```
4. Generar la migración: `docker compose exec backend alembic revision --autogenerate -m "indicadores"`
5. Aplicarla: `docker compose exec backend alembic upgrade head`

PQRS no se toca en ningún momento de este proceso.

---

## 8. Comandos útiles

| Comando | Qué hace |
|---|---|
| `docker compose up` | Levanta todo |
| `docker compose down` | Apaga todo (los datos de Postgres persisten) |
| `docker compose down -v` | Apaga todo y BORRA los datos (reinicio total) |
| `docker compose logs -f backend` | Ver logs del backend en vivo |
| `docker compose exec backend bash` | Entrar a una terminal dentro del contenedor backend |
| `docker compose exec backend alembic revision --autogenerate -m "mensaje"` | Crear nueva migración tras cambiar modelos |
| `docker compose exec backend alembic upgrade head` | Aplicar migraciones pendientes |
