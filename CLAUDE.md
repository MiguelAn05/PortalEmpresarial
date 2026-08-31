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

### Versiones

`backend/app/core/version.py` es la **única fuente**: el backend la sirve en
`/version` y Vite la lee al compilar. No hay un segundo número que se quede
atrás — `package.json` no cuenta.

Para subir de versión: cambiar `VERSION` y `FECHA`, agregar la entrada nueva
al principio de `HISTORIAL`, y **`npm run build`**. Sin el build, el navegador
sigue anunciando la anterior y el portal muestra el aviso de desfase (que es
justamente para lo que sirve). Un `assert` al arrancar revienta si se sube
`VERSION` y no se agrega su entrada al historial.

`MENOR` sube con cada función nueva, `PARCHE` con correcciones, y `1.0.0`
queda para el día que el portal se entregue a una empresa distinta.

El historial se escribe para quien **usa** el portal, no para quien lo
programa: «ya se pueden cerrar proyectos», no «se agregó `fecha_cierre` a
`mp_proyectos`». Una prueba exige que cada cambio pase de 15 caracteres para
que el historial no termine siendo un `git log`.

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
| Mejora | ✓ | — | ✓ | — | — |
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

**Oportunidades de Mejora (OMP)** las manejan los **líderes de área**, que son
quienes responden por que un indicador vuelva a su meta. Gerencia queda fuera
del módulo a propósito: el avance se le reporta, no se le deja como un tablero
más que mirar.

**El ciclo se defiende solo:** una OMP nace
de un indicador que no cumplió y recorre
`abierta → analisis → ejecucion → verificacion → cerrada`. Dos guardas no son
negociables: **no se pasa a ejecución sin causa raíz** (sin ella las acciones
atacan el síntoma y el indicador vuelve a caer) y **no se cierra sin
verificar** (cerrar sin saber si funcionó es la observación clásica de una
auditoría). Si la verificación dice que NO fue eficaz, vuelve a `analisis` —
nunca se cierra.

La verificación se hace **con dato, no con opinión**: se compara el valor que
disparó la OMP contra la medición del mes siguiente, y si eso es una mejora
depende de la `direccion` del indicador (subir los reprocesos es malo). Esa
regla vive en el servidor, en `modules/mejora/service.py`, junto al semáforo
— si el frontend la repitiera, tarde o temprano diría lo contrario.

Por eso el **periodo es obligatorio** cuando la OMP nace de un indicador: sin
él no hay contra qué comparar. Y `valor_inicial` se congela al abrirla, para
que corregir la medición después no invalide la comparación.

Lo que se intentó y no sirvió se **descarta**, no se borra: el historial de
mejora es justamente lo que se audita. Borrar es solo de admin y para lo que
se abrió por error.

`indicadores_en_rojo_sin_omp()` responde lo que hoy no está en ninguna parte:
**un indicador en rojo sin OMP abierta es un problema que nadie está
trabajando.**

**Visibilidad por participación (solo Master Planner):** ves un proyecto si
**lo lideras** o si **tienes una tarea asignada** dentro. Nada más. Ser del
área responsable ya no basta, y un proyecto sin área tampoco se le muestra a
todo el mundo: eso llenaba la lista de proyectos ajenos y la gente entraba a
buscar lo suyo entre veinte que no le tocaban. Se responde **404, no 403**,
para no confirmar que existe. Ver `modules/master_planner/permisos.py`.

El precio de esta regla: **un proyecto sin líder y sin tareas no lo ve nadie.**
Por eso al crear uno sin líder se pone a quien lo creó — si no, desaparecería
apenas se guarda.

Siguen viendo todo `admin`, `gerencia`, y las áreas `Administración` y
`Tesorería`: aprueban y desembolsan la plata de TODOS los proyectos.

El presupuesto es aparte y más estrecho: solo lo ve **quien lidera** (más las
dos áreas financieras). Tener una tarea en un proyecto deja trabajar en él,
no mirar cuánta plata mueve.

### Áreas

**Una sola fuente por lado**: `backend/app/core/areas.py` y
`frontend/src/core/areas.js`. Una prueba verifica que coincidan. Nunca
declarar una lista de áreas dentro de un componente.

### Interfaz

- **Los colores salen de `frontend/src/index.css`, nunca de un hex suelto.**
  Ahí viven los tokens: `bg-superficie`, `text-texto-2`, `border-borde`,
  `bg-acento`, `text-negativo`, `bg-nav`… Un hex escrito dentro de un
  componente es un color que nadie podrá cambiar cuando el portal se entregue
  a otra empresa. Los archivos de lógica pura (`resumen.js` y compañía)
  devuelven el nombre del estado (`'negativo'`), no una clase.
- Cada estado semántico tiene **dos tonos**: el vivo (`positivo-vivo`,
  `ambar`, `negativo-vivo`) para puntos y barras, y el profundo (`positivo`,
  `alerta`, `negativo`) para texto — los vivos de la marca no llegan a 4.5:1
  sobre blanco.
- **El estado nunca se comunica solo con color.** El ámbar de la marca no
  alcanza el contraste mínimo sobre fondo blanco (1.95, se necesitan 3), así
  que todo semáforo lleva punto **y** etiqueta de texto.
- **Cero emojis en la interfaz.** Los iconos son SVG de
  `core/components/Iconos.jsx`: una sola familia, trazo de 1.5, `currentColor`.
  Dibujados a mano por lo mismo que las gráficas — el servidor no reinstala
  dependencias con fiabilidad. `tests/sinEmojis.test.mjs` revienta si vuelve a
  entrar uno; la puntuación tipográfica (`→ — · …`) no cuenta, es texto.
  Icono nuevo: se agrega a `Iconos.jsx` con el mismo trazo, nunca suelto en el
  componente.
- **Toda cifra lleva contexto y `cifra`** (la utilidad de `tabular-nums`). Un
  número sin meta, delta ni estado obliga a preguntar «¿eso es bueno?»: un 0
  de PQRS sin cerrar se acompaña de «Ninguna pendiente» en verde.
- Profundidad en tres niveles y sin saltárselos: fondo de página (`bg-fondo`)
  → tarjeta (`shadow-sm`) → tarjeta principal o modal (`shadow-md`/`lg`). La
  jerarquía se declara con elevación y tamaño, no pintando cada tarjeta de un
  color distinto.
- Radios: `rounded-md` en badges, `rounded-lg` en controles, `rounded-xl` en
  tarjetas. Espaciado en la escala de 4 (`gap-2`/`gap-3` dentro de un bloque,
  `gap-6` entre bloques).
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
- **Un consecutivo se saca del MÁXIMO, nunca de un `count()`.** El código de
  seguimiento se calculaba contando las PQRS del prefijo: con `VI0001` y
  `VI0003` en la tabla (alguien borró la del medio), contar da 2 y el
  siguiente sale `VI0003` — que ya existe. Reventaba el `commit` con
  `UniqueViolation` *después* de guardar la solicitud, así que la PQRS quedaba
  radicada **sin código** —el cliente no podía consultarla— y los correos, que
  se mandan justo después, no salían. Un solo defecto, tres síntomas.
  `asignar_codigo_seguimiento()` además reintenta: dos personas radicando a la
  vez leen el mismo número. Para reparar las que quedaron sin código:
  `docker exec protokimica_backend python -m app.reparar_codigos --aplicar`.
- **Notificar no puede tumbar la petición.** Cuando se avisa por correo, la
  PQRS ya está guardada: si la excepción sube, el cliente ve un 500 sobre algo
  que sí se radicó, vuelve a enviar el formulario y queda duplicado. Se captura
  `except Exception`, no `except httpx.HTTPError` — `httpx.InvalidURL` **no**
  hereda de `HTTPError`, así que un `N8N_WEBHOOK_URL` con un salto de línea
  invisible al final se escapaba. Armar el payload también va protegido, y
  ojo: un argumento se evalúa *antes* de entrar a la función que lo protege.
- **La URL del webhook se limpia antes de usarla** (`.strip().rstrip("/")`).
  Un `.env` escrito a mano trae espacios, saltos de línea o una barra de más,
  y `.../webhook//evento` responde 404 en n8n: otro "no llega el correo" sin
  causa visible. Si `N8N_WEBHOOK_URL` está vacío se avisa una vez en WARNING
  al arrancar; el silencio total costaba días de diagnóstico.
- **Los webhooks se mandan con `BackgroundTasks`,** después de responder.
  Radicar disparaba tres llamadas HTTP en serie de hasta 10 s cada una: medio
  minuto esperando. El aviso se *arma* dentro de la petición (necesita la
  sesión de base de datos) y se *manda* después.

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
