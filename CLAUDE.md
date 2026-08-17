# Portal Empresarial Protokimica

Portal de gestión interna. Módulos: **PQRS**, **Master Planner** (proyectos),
**Indicadores**, autenticación y administración.

## Estructura

```
protokimica-portal/
  backend/          FastAPI + SQLAlchemy + Alembic + PostgreSQL
    app/
      core/         config, database, deps (permisos), security, areas
      models/       tablas SQLAlchemy, una por módulo
      modules/      un paquete por módulo: router.py, schemas.py, service.py
    alembic/versions/   migraciones, en orden
    tests/          pruebas end-to-end contra la API real
  frontend/         React + Vite + Tailwind + React Query
    src/
      core/         api.js, AuthContext, Layout, componentes compartidos
      modules/      un directorio por módulo
    dist/           SE COMMITEA (ver despliegue)
    tests/          pruebas de la lógica pura del frontend
```

## Cómo correr las pruebas

**El backend se prueba dentro del contenedor**, que tiene las dependencias
exactas de producción (Python 3.11). En Windows no hay venv local que sirva:
Python 3.14 no tiene ruedas para `pydantic 2.9`.

```bash
# Todas las pruebas del backend
docker exec protokimica_backend pytest tests -q

# Una sola
docker exec protokimica_backend pytest tests/test_permisos.py -q

# Frontend (lógica pura: fechas, formatos, permisos)
cd protokimica-portal/frontend && npm test

# Lint y build
cd protokimica-portal/frontend && npx eslint src && npm run build
```

`src/core/AuthContext.jsx` tiene un error de lint preexistente
(`react-refresh/only-export-components`). No es de ningún cambio nuevo.

**Antes de dar algo por terminado**: pruebas del backend + `npm test` +
`eslint` + `npm run build`. No basta con `py_compile`.

## Base de datos

```bash
docker exec protokimica_backend alembic upgrade head
docker exec protokimica_db psql -U protokimica -d protokimica_portal -c "..."
```

Cada cambio de modelo necesita su migración en `alembic/versions/`, encadenada
por `down_revision`. Si el cambio renombra valores que ya existen en columnas
de datos (por ejemplo un área), la migración **también** tiene que actualizar
las filas, no solo el esquema.

## Despliegue

Servidor Ubuntu `zeus` (VM interna, se llega por VPN FortiClient).
Comparte máquina con otra empresa: el contenedor `n8n` y el proyecto Compose
`n8n` **no se tocan nunca** — el nuestro es `protokimica_n8n`.

```bash
git add -A && git stash && git pull origin Develop && git stash pop
sudo docker compose -f docker-compose.prod.yml up -d              # solo código
sudo docker compose -f docker-compose.prod.yml up -d --build backend  # deps o migraciones
```

**Regla de oro:** si cambió un `.env`, nunca `restart` — no relee variables de
entorno. Siempre `up -d`, que recrea el contenedor. Confirmar después con
`docker exec <contenedor> env | grep <VARIABLE>`.

**El frontend se compila en local** (`npm run build`) y `dist/` se commitea:
el servidor no tiene internet estable para `npm ci`.

## Convenciones

- **Todo en español**: nombres de variables, funciones, comentarios, textos de
  interfaz y mensajes de error. El código se lee como el dominio.
- **El backend calcula, el frontend presenta.** Semáforos, acumulados,
  porcentajes y comparaciones se resuelven en el servidor. Si el frontend
  recalcula, tarde o temprano los números dejan de coincidir con un reporte.
- **Los mensajes de error dicen qué hacer**, no solo qué falló.
- Módulo nuevo: `models/<modulo>.py`, `modules/<modulo>/{router,schemas,service}.py`,
  registrar en `main.py` (import del router + `include_router` + el modelo en la
  línea de `from app.models import ...`).

### Roles y permisos

| Rol | Qué puede |
|---|---|
| `admin` | Todo, incluida la configuración |
| `gerencia` | Ve TODAS las áreas sin límite; no modifica nada; solo comenta |
| `lider` | Opera su área |
| `agente` | Opera lo que le asignan |
| `lectura` | No escribe nada |

**Qué módulo abre cada rol** — `backend/app/core/modulos.py` es la fuente, con
gemelo en `frontend/src/core/modulos.js` (una prueba verifica que coincidan).

| Módulo | admin | gerencia | lider | agente | lectura |
|---|:-:|:-:|:-:|:-:|:-:|
| Inicio, PQRS, Master Planner, Encuestas | ✓ | ✓ | ✓ | ✓ | ✓ |
| Indicadores | ✓ | ✓ | ✓ | — | — |
| Administración | ✓ | — | — | — | — |

**El rol decide a qué módulo entras; el área decide qué ves dentro.** Un líder
entra a Indicadores pero solo ve los de su área — el filtro se impone en el
servidor y mandar otro `?area=` no lo abre. Un indicador ajeno responde 404.

Se aplica con `Depends(requiere_modulo("indicadores"))` en **todos** los
endpoints del módulo, incluidas las lecturas. El menú del frontend también se
filtra, pero eso es cortesía: esconder un botón no impide escribir la URL.

- `solo_lectura_no` bloquea a `lectura` **y** a `gerencia`. Se usa en todo
  endpoint de escritura, lo que protege también los módulos viejos sin tocarlos.
- `puede_comentar` solo bloquea a `lectura`. Es para comentarios y
  actualizaciones de seguimiento.

**PQRS — cerrar y reclasificar:** solo el área `Servicio al cliente` (más
`admin`). Se resuelve por ÁREA, no por rol, porque el área ya existe y así se
administra desde Admin › Usuarios. Ver `modules/pqrs/permisos.py`.
El tipo (petición/queja/reclamo/…) se corrige **antes de cerrar**: el cliente
casi nunca acierta al radicar y esa clasificación alimenta los indicadores.
Al reclasificar se recalcula el SLA **desde la radicación** y la prioridad se
ajusta al tipo nuevo salvo que alguien la haya cambiado a mano.

**Master Planner — aprobar y pagar:** el presupuesto recorre
`planeado → aprobado → pagado`. `Administración` aprueba cuánto se desembolsa
y `Tesorería` registra los abonos: dos manos distintas a propósito. Las dos
áreas ven TODOS los proyectos (si no, no podrían hacer su trabajo), pero eso
no les da permiso de editarlos. Ver `modules/master_planner/permisos.py`.
Los pagos se guardan uno por uno (`mp_pagos`) y `valor_pagado` es su suma —
nunca un campo aparte que se edite en paralelo.

**Visibilidad por área (solo Master Planner):** ves un proyecto si es de tu
área, tu área participa en él, lo lideras, tienes una tarea asignada ahí, o el
proyecto no tiene área. Se responde **404, no 403**, para no confirmar que
existe. Ver `modules/master_planner/permisos.py`.

El presupuesto es aparte: tener una tarea en un proyecto ajeno no da acceso a
su plata.

### Áreas

**Una sola fuente por lado**: `backend/app/core/areas.py` y
`frontend/src/core/areas.js`. Una prueba verifica que coincidan. Nunca
declarar una lista de áreas dentro de un componente.

### Interfaz

- Paleta: `#0D2B5E` azul oscuro · `#1A4FA0` azul · `#F5A800` ámbar ·
  `#D93B3B` rojo · `#2E9E6B` verde · `#6B7EA8` texto secundario ·
  `#D6E0F0` bordes · `#F7F9FC` fondos suaves.
- **El estado nunca se comunica solo con color.** El ámbar de la marca no
  alcanza el contraste mínimo sobre fondo blanco (1.95, se necesitan 3), así
  que todo semáforo lleva punto **y** etiqueta de texto.
- Tarjetas de resumen: blancas con borde superior de color (`border-t-4`),
  etiqueta pequeña en mayúsculas, número grande. Igual en los tres módulos.
- Formularios en modal: usar `useCierreSeguro` de
  `core/components/cierreSeguro.jsx` para que un clic fuera no borre lo escrito.
- Gráficas: SVG a mano, sin librería (el servidor no reinstala dependencias con
  fiabilidad). Una serie = un color y sin leyenda; la meta es una anotación
  punteada, no una segunda serie; nunca doble eje.

## Cosas que ya mordieron

- **Fechas con y sin zona horaria.** Postgres las devuelve con zona y SQLite
  sin ella; restarlas revienta. Usar el helper `_aware()` que hay en
  `resumen.py` y en `fuentes.py`.
- **Los porcentajes no se promedian.** El acumulado de un porcentaje suma
  numeradores y denominadores y divide al final. Por eso los indicadores de
  proporción guardan los dos números, no el resultado.
- **Orden de rutas en FastAPI.** `/tareas/mias` y `/indicadores/tablero` van
  declaradas *antes* que `/{id}`, o el path variable se las come.
- **Cascadas.** Borrar un proyecto arrastra tareas, actualizaciones, historial
  y presupuesto. Toda relación nueva que apunte a `mp_proyectos` necesita su
  cascada o el borrado falla contra la llave foránea.
- **Los plazos de PQRS son en días HÁBILES**, no calendario: los 15 días de
  una petición salen de la Ley 1755 de 2015. Usar `core/dias_habiles.py`,
  que calcula los festivos colombianos (incluida la Ley Emiliani que los
  corre al lunes). Contarlos corridos declaraba vencido lo que no lo estaba.
- **El % pagado se mide sobre lo APROBADO, no sobre lo planeado.** Lo
  planeado puede no aprobarse nunca; la deuda real es lo aprobado.
- **La escritura del área importa.** Se compara como texto para decidir
  permisos (`Servicio al Cliente`, `Administración`, `Tesorería`). Cambiar
  mayúsculas o tildes rompe permisos en silencio: va con migración de datos
  y las constantes de `permisos.py` lo verifican al arrancar.
- **Un mes sin datos no es un cero.** En indicadores y en cumplimiento, la
  ausencia de dato se muestra como "sin dato" y no baja los porcentajes.

## Pendientes conocidos

- Flujos de n8n sin construir: `pqrs-nueva-servicio-cliente`,
  `mp-tarea-asignada`, alertas de indicadores en rojo, y el disparo mensual de
  `POST /indicadores/calcular-periodo`.
- `/uploads` sin control de acceso real; `UPLOAD_DIR` quemado en 3 sitios.
- `router_public.py` y `seed.py` tienen `slug == "protokimica"` quemado: el
  formulario público solo sirve para una empresa.
- Marca (colores, logo) quemada en el frontend.
- Indicadores: faltan la vista de año en matriz, la portada de "cómo vamos",
  el interruptor empresa/mi área y la exportación.
