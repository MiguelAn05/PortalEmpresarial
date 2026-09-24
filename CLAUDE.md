# Portal Empresarial Protokimica

Portal de gestión interna. Módulos: **Inicio**, **PQRS**, **Master Planner**
(proyectos), **Indicadores**, **Mejora** (oportunidades de mejora, OMP),
**Encuestas**, **Catálogo** de productos, autenticación y administración.

## Estructura

```
protokimica-portal/
  backend/          FastAPI + SQLAlchemy + Alembic + PostgreSQL
    app/
      core/         config, database, deps (permisos), security, areas,
                    dias_habiles, rate_limit, graph (Microsoft 365)
      models/       tablas SQLAlchemy, una por módulo
      modules/      un paquete por módulo: router.py, schemas.py, service.py
    alembic/versions/   migraciones, en orden
    tests/          pruebas end-to-end contra la API real
  n8n/              flujos de automatización, versionados como JSON
  integraciones/    scripts que corren FUERA del portal (ver ERP)
  frontend/         React + Vite + Tailwind + React Query
    src/
      core/         api.js, AuthContext, Layout, errores.js, areas.js,
                    modulos.js, componentes compartidos
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

### Qué se cachea y qué no

**Lo que lleva hash en el nombre se guarda un año; lo demás se revalida
siempre.** Las cabeceras las pone `frontend/nginx.conf` y no son una
afinación: `index.html` es el único archivo cuyo nombre no cambia entre
versiones, y es el que dice qué bundle cargar. Servirlo sin `Cache-Control`
deja que el navegador aplique su heurística —una fracción del tiempo que el
archivo lleva sin cambiar, que en un archivo copiado dentro de una imagen son
días— y siga pidiendo el JS de la versión anterior contra un backend nuevo.

Eso costó dos casos de «no me sirven los filtros / no me cambia el mes / no
conecta con Outlook» que solo se arreglaban borrando la caché a mano, y que
por eso parecían problemas del computador de esa persona.

- `index.html`: `no-store`. Lo demás sin hash (logo…): `no-cache`, que
  revalida y responde 304 si no cambió.
- `/assets/`: `immutable`, un año. Para eso Vite les pone el hash.
- `/api/`: `no-store`, salvo cuando el backend ya mandó su propia
  `Cache-Control` (los QR, que son públicos y valen un día). Lo resuelve un
  `map` sobre `$upstream_http_cache_control`.
- `/uploads/`: un día. Los nombres son UUID, así que un archivo nunca cambia
  de contenido.
- El botón «Recargar» del aviso de versión usa `recargarDeVerdad()` de
  `core/version.js`: `location.reload()` a secas vuelve a leer el HTML
  guardado, que es justo el que está viejo.

**Al desplegar esto la primera vez, los navegadores que ya tienen el HTML
viejo guardado no se enteran solos**: necesitan una recarga (F5) para
preguntar de nuevo. De ahí en adelante ya no vuelve a pasar.

### Cómo se entra al portal

Hay **dos puertas**, y la de todos los días es la primera:

| | Desde dónde | Cifrado |
|---|---|---|
| `https://portal.protokimica.com` | Cualquier lugar con internet | HTTPS |
| `http://172.20.70.47:8080` | Solo red interna, y solo VLAN con política | HTTP plano |

**La URL pública es la oficial para todo el mundo**, incluidos los puntos de
venta. El túnel de Cloudflare (`cloudflared` en `docker-compose.prod.yml`)
publica el portal sin abrir un solo puerto hacia internet, así que sirve igual
desde una sede, desde la casa o desde un celular con datos — que es
justamente lo que necesitan los QR de los puntos de venta.

**Los puntos de venta están en otras VLAN** y el FortiGate no tiene política
hacia zeus, así que por la IP interna NO llegan (a MORFEO sí, porque para eso
sí existe la regla). Eso ya causó un «no puedo entrar al portal» que resultó
ser gente intentando por la IP: la respuesta es el dominio, no una regla de
firewall.

La IP interna se queda como respaldo cuando el túnel se cae, y para entrar por
VPN. **Va en HTTP plano**, así que una contraseña escrita ahí viaja sin
cifrar: no es el camino para el uso diario.

La IP pública de la empresa (`190.14.231.91`) es solo la salida a internet.
No hay NAT hacia zeus y no debe haberlo: el túnel existe para no exponer la
VM.

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

**Indicadores son TRES vistas del mismo mes, con un solo contexto**
(`PESTANAS` en `modules/indicadores/constants.js`): «Cómo vamos» para leer el
estado, «Tablero» para registrar y consultar, y «El año» para la matriz de
doce meses. La matriz vivía dentro de «Cómo vamos» y ahí no cabe —73 filas ×
12 meses empujan fuera de pantalla lo que alguien entra a ver—.

El mes, el alcance, el área y la búsqueda viven **arriba de las pestañas**
(`BarraContexto`) y valen para las tres; los cinco conteos también son únicos
(`KpisPeriodo`). Antes el interruptor empresa/área vivía DENTRO de una
pestaña, así que cambiar de pestaña cambiaba en silencio qué parte de la
empresa se estaba mirando, y los conteos estaban duplicados con rótulos
distintos para lo mismo.

- **`alcance` es el límite y `area` la elección**, igual que en el tablero:
  se intersecan, nunca se reemplazan. Mandar un `?area=` ajeno no abre nada.
- **El delta contra el mes pasado lo calcula el servidor**
  (`cumplimiento_del_mes_anterior` en `indicadores/como_vamos.py`), con la
  MISMA regla del mes actual — comparar dos porcentajes calculados distinto
  no compara nada. Restarlos en el frontend es fácil, y por eso mismo es la
  clase de cuenta que un día deja de coincidir con el reporte.
- **La matriz agrupa lo que nadie lee de a uno**: los «Gestión de OMP» son
  uno por área y las filas sin un solo registro del año son otra cosa
  distinta (la pregunta de si ese indicador sigue vivo). Se reconocen por la
  **fuente**, nunca por el nombre: renombrar uno desde Administración no
  puede romper la agrupación.
- **Se busca también por responsable**, que es la pregunta del cierre de mes
  —«qué le falta a Hoover»—, y sin tildes: nadie las escribe en un buscador.

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

**PQRS — cada punto de venta ve las suyas:** todo el portal ve todas las
PQRS, **menos el área `Puntos de Venta`**. A una sede le interesan las de su
mostrador; las de las otras cinco y las de Venta institucional son ruido.
El área es una sola para las seis sedes, así que cada usuario lleva
`users.punto_venta` con el **prefijo** (`PVG`, `PVC`…), que se elige en
Admin › Usuarios y solo aparece si el área es `Puntos de Venta`:

| Usuario | Ve |
|---|---|
| Área `Puntos de Venta` con punto | Las de su punto + las que le asignen |
| Área `Puntos de Venta` sin punto (coordinador) | Las de los seis puntos + las pasadas al área + las asignadas |
| Cualquier otra área, `admin`, `gerencia` | Todas, como siempre |

Se decidió **por punto y no solo por área** porque con el área sola Guayabal
vería las de Belén y tendría que filtrar cada vez — y el filtro que hay que
acordarse de poner es el que un día no se pone. La PQRS se reconoce por el
canal **o** por el prefijo del radicado (con cuidado: `PVCR0001` también
empieza por `PVC`). Fuera de alcance responde **404**. Todo endpoint que
reciba un `pqrs_id` —incluidas las autorizaciones— pasa por
`obtener_visible()` de `modules/pqrs/permisos.py`; la lista usa
`filtrar_visibles()`. `GET /pqrs/visibilidad` le dice a la pantalla qué se
está viendo, para que una lista acotada no se lea como «solo hay estas».
«Venta institucional» tiene prefijo pero **no es un punto de venta**: no se
le asigna a nadie. Salir del área borra el punto, para que no reaparezca
acotando a alguien el día que vuelva.

**PQRS — corregir datos y adjuntos:** quien gestiona el caso
(`alcance.puede_editar_datos`) corrige los datos del cliente y de la factura
(`PATCH /pqrs/{id}/datos`; el lote y las cantidades, en cada producto) y cambia o quita la foto del producto, la factura
y el video (`PUT`/`DELETE /pqrs/{id}/adjuntos/{campo}`). Nunca con la PQRS
cerrada. Cada corrección queda en el historial **con el valor anterior**.
Lo que **no** se corrige ahí, a propósito (ver `pqrs/edicion.py`): el tipo
(se reclasifica), el producto (se confirma contra el catálogo), el canal (de
él salió el prefijo) y la descripción (es lo que el cliente radicó y lo que
se audita; una aclaración va como comentario). Quitar un adjunto **no borra
el archivo del servidor**: se desvincula y su ruta queda en el historial,
por si se quitó el de la fila equivocada.

**PQRS — varios productos:** un reclamo puede ser por varios productos de la
misma compra, cada uno con **su** lote, presentación y cantidades. Van en
`pqrs_productos` (una fila por producto), no en columnas de la solicitud; la
**factura y los adjuntos siguen siendo de la solicitud**, porque la compra es
una. Los formularios mandan `productos` como JSON en el multipart, y los
campos sueltos del formato viejo se siguen aceptando (un formulario cacheado
en el celular del cliente no puede quedarse sin radicar). La lógica vive en
`modules/pqrs/productos.py`: `por_confirmar` se deduce **por producto**,
`producto_por_confirmar` de la solicitud es una propiedad derivada (no una
columna), no se cierra mientras quede uno por confirmar, y quitar un producto
deja todos sus datos escritos en el historial. El nombre y el código de un
producto radicado no se editan a mano: se confirman contra el catálogo
(`PATCH /pqrs/{id}/productos/{producto_id}/confirmar`); lote y cantidades sí.
Tope: `MAX_PRODUCTOS = 20`, atado al `constants.js` del módulo.

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

**El módulo replica el formato oficial `RCN-F-13` del SGC** y lo reemplaza sin
perder ninguna de sus 23 columnas. El **proceso** pasó a ser un campo: antes
cada proceso llevaba su propio Excel y nadie podía cruzarlos.

**Proceso ≠ área.** El área decide permisos; el proceso rotula el reporte del
SGC y son listas distintas (`TIC's` contra `TICS`, `SGC` contra `Calidad`, y
`Direccionamiento Estratégico` no existe como área). Mezclarlas rompería
permisos en silencio, así que el proceso vive en su propio catálogo y solo se
*propone* desde el área con `PROCESO_SEGUN_AREA` de `mejora/catalogos.py`.
Las áreas sin equivalente no se adivinan: adivinar mal manda la acción al
archivo de otro proceso.

**Y se nombran como lo que hacen, porque se confunden solos.** En el
formulario el proceso decía «Proceso al que se remite», que se lee como «a
quién se la remito» —no se remite a nadie: es la carpeta del `RCN-F-13` donde
la busca un auditor—, y el área decía «Área», con la opción vacía escrita
«Area», sin decir que dejarla vacía es asignarla a TODA la empresa. Hoy son
«Proceso del SGC» y «Área a la que se asigna», cada uno con su línea de
ayuda. **A quién se le encarga el trabajo no es ninguno de los dos: son los
responsables.**

**Quien abre una OMP la sigue viendo, aunque la asigne a otra área**
(`creado_por` en `aplicar_filtro_area` y en `exigir_acceso`). El área es a
quién se le asigna, y no siempre es la de quien detecta el problema; sin esto,
escribirla completa y guardarla la hacía desaparecer de la pantalla de su
autor, que ni siquiera podía consultarla. Es lo mismo que en Master Planner
con el proyecto sin líder. **Lo que se ve es la que uno abrió, no el área
entera**: si abrir una para TICS destapara todas las de TICS, sería la forma
más fácil de mirar la gestión de otro.

**Los catálogos son tabla, no enum** (`omp_catalogos`, con discriminador
`tipo`): proceso, fuente y tratamiento. Calidad los cambia sin avisarle a
TIC's, y agregar un proceso no puede pedir un despliegue. Se siembran solos y
de forma idempotente al pedirlos o al crear una OMP. **La lógica cuelga del
`codigo` del tratamiento (`OMP`/`AC`/`AM`), nunca del nombre** — el histórico
ya trae «Acción de mejora» y «Acción de Mejora» escritos distinto, y
renombrar un catálogo desde Admin no puede apagar una regla de negocio.

**Dos consecutivos, a propósito:** `codigo` (`OMP-2026-0001`) es la identidad
única del portal, y `consecutivo` es el 1, 2, 3… **dentro de cada proceso**,
que es el que citan los auditores. Los dos salen del MÁXIMO. Se guarda en vez
de renumerar al exportar: si se recalculara, descartar una fila correría todas
las siguientes y una referencia de auditoría dejaría de apuntar a lo mismo.

**El ciclo se defiende solo:** una OMP nace de un indicador que no cumplió
—o de una auditoría, un comité, una PQR— y recorre
`abierta → analisis → ejecucion → verificacion → cerrada`.

**Qué se exige para avanzar depende del TRATAMIENTO**, y así lo declara el
propio formato: causa raíz y análisis de causas para `OMP` y `AC`, corrección
solo para `AC`, beneficio solo para `AM`. Antes se pedía causa raíz siempre, y
la salida era escribir «no aplica» para poder avanzar — que es como se le
enseña a la gente a mentirle a un formulario. **Sin tratamiento elegido se
sigue pidiendo causa raíz**, que es el comportamiento viejo. Quien decide es
el servidor: `pide_causa`, `pide_correccion` y `pide_beneficio` llegan ya
resueltos en la respuesta, y el frontend esconde lo que no aplica en vez de
deshabilitarlo.

Cerrar exige **dos firmas distintas**: la verificación de eficacia (quien
ejecutó dice si el indicador mejoró) y la **validación del SGC** (Calidad dice
si la evidencia alcanza). Un solo botón dejaba que el mismo que hizo el
trabajo lo diera por bueno. Va por ÁREA —`AREA_SGC = "Calidad"` en
`mejora/permisos.py`, más `admin`— como el cierre de PQRS. Una verificación
que dice que NO fue eficaz **anula el visto bueno anterior**: si quedara, la
siguiente vuelta se cerraría con la firma de una evidencia ya descartada. Y
si no fue eficaz, vuelve a `analisis` — nunca se cierra.

**El análisis de causas son siete campos (6M), no un textarea:** efecto,
método, mano de obra, maquinaria, material, medidas y medio ambiente. El
Excel ya venía escribiendo esas etiquetas a mano dentro de la celda — la
estructura existía, solo que sin nada que la garantizara. Al exportar,
`bloque_6m()` reconstruye el texto en ese orden y rellena con `N/A` las
vacías, porque así lo imprime el formato; en pantalla las vacías no se
muestran, que siete «N/A» seguidos no le dicen nada a nadie.

**El seguimiento es una tabla, no tres columnas.** En el Excel son
`SEGUIMIENTO`, `...2` y `...3` con hasta veinticinco entradas concatenadas
dentro de una celda de seis mil caracteres. Aquí es una fila por entrada, con
fecha y autor, y **lo escribe cualquiera que vea la OMP, no solo el líder**:
quien ejecuta la acción es quien sabe cómo va, y obligarlo a contárselo al
líder para que él lo escriba es cómo estos registros se llenan de resúmenes de
segunda mano. Un seguimiento ajeno no se borra.

Las tareas del plan tienen **tres estados** (`pendiente`/`en_curso`/`cumplida`)
y no un booleano: sin «en curso», la gente marca cumplido antes de tiempo para
que el avance se mueva. `completada` es una propiedad derivada del estado — dos
columnas que dicen lo mismo terminan diciendo cosas distintas.

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

**«Gestión de OMP»: el indicador que mide al propio módulo.** Uno por área,
automático (fuente `mejora_gestion_omp`), creado con el botón «Gestión de OMP
en las áreas» de Indicadores (`POST /indicadores/gestion-omp/crear-en-areas`,
solo quien ve toda la empresa; no duplica). Una OMP es texto y el texto no se
califica: **se miden los hechos que deja la gestión.** La regla vive en
`modules/mejora/gestion.py`:

- **Se evalúa cada OMP viva, todos los meses que está abierta** — no las
  acciones que vencen en el mes. Medir solo eso dejaba ciega a una OMP de un
  año con una acción al final. «Viva» sale del historial de estados
  (`omp_historial`, campo «Estado»), así los meses en que estuvo descartada
  no se le cobran.
- Está **al día** si: (1) no tiene acciones vencidas ni cumplidas tarde ese
  mes, **contra `fecha_limite_original`** (aplazar se permite pero no mejora
  el indicador; la original se fija la primera vez que la acción tiene fecha y
  no se vuelve a tocar); (2) tuvo **algún avance** en el mes —seguimiento,
  cambio de etapa, acción cumplida o creada—, salvo si se registró a menos de
  15 días del corte o el mes aún no termina; (3) no pasó su fecha estimada de
  solución estando abierta.
- Valor = al día ÷ vivas × 100, guardando los dos números. Sin OMP vivas es
  «sin dato». El análisis del mes **nombra las atrasadas y el motivo**: es lo
  que permite auditar el número.
- Queda **fuera de `indicadores_en_rojo_sin_omp()`**: pedir una OMP sobre la
  gestión de las OMP sería un círculo.
- Las fuentes automáticas pueden ser **por área** (`"por_area": True` en el
  `CATALOGO` de `indicadores/fuentes.py`): reciben el área del indicador, y
  crear o editar uno sin área responde 400.


**Áreas supervisadas: el jefe ve hacia abajo, el equipo no hacia arriba.**
El portal filtra por área EXACTA, así que una dirección que responde por
varias áreas —Dirección Técnica sobre IDI y Salvak— no vería nada de su
gente. Cada usuario puede tener **áreas que supervisa además de la suya**
(`usuario_areas_supervisadas`), y se configuran en Admin › Usuarios con el
botón «Supervisa», sin desplegar. La regla vive en `core/supervision.py`
(`areas_visibles()`, `supervisa()`, `condicion_area()`) y la usan Indicadores,
Mejora, Master Planner e Inicio — **es la única fuente**: si cada módulo
armara su lista, el día que se agregue otra jefatura el que se olvide es el
que le esconde a alguien lo suyo.

- **Una sola vía a propósito:** quien está en IDI sigue viendo solo IDI, así
  que la gestión de la dirección no se le muestra. Lo ajeno responde 404,
  como siempre.
- **La propia no se guarda como supervisada** (ya la ve), y cambiar de área
  limpia la que quedó redundante.
- **PQRS no cambia:** ahí todos siguen viendo todas, salvo los puntos de
  venta. Si algún día se acota, la supervisión ya está lista para usarse.
- En el tablero de Indicadores, `area` es el filtro que eligió la persona y
  `areas` el LÍMITE que impone el router: un director puede mirar solo IDI
  sin dejar de tener Salvak en su alcance, y el selector solo ofrece sus áreas.
- `User.areas_supervisadas` se carga con `lazy="selectin"`: perezosa reventaba
  con `DetachedInstanceError` cuando la sesión que trajo al usuario ya se
  cerró, que es justo lo que hace la dependencia de sesión en cada petición.
**Visibilidad por participación (Master Planner; PQRS tiene la suya por
punto de venta, ver arriba):** ves un proyecto si
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

### Errores y validación

- **Ningún componente lee `data.detail` directo.** Todo error de API pasa por
  `mensajeDeError(err, 'texto por defecto')` de `core/errores.js`. Un 422 trae
  una lista de objetos y pintarla tumba la página (ver «Cosas que ya
  mordieron»).
- **Los mensajes del backend dicen qué hacer**, y por eso llegan tal cual a la
  pantalla: `mensajeDeError` respeta el texto cuando el backend mandó uno.
- **Validar en los dos lados, con el mismo número.** El backend es la
  autoridad; el frontend evita que el error ocurra. Los límites se declaran en
  el `constants.js` del módulo y se anota que están atados al schema.

### Permisos: por área, no por cargo

- **Cuando el permiso depende del trabajo, va por ÁREA; cuando depende de la
  responsabilidad, por PERSONA.** Nunca por cargo:
  - Cerrar y reclasificar PQRS → área `Servicio al Cliente`
  - Aprobar presupuesto → `Administración`; pagar → `Tesorería`
  - Responder una autorización → el área autorizadora del tipo
  - Cerrar un proyecto → su líder (más `admin`)
  Amarrarlo al rol dejaba fuera a quien hace el trabajo y obligaba a cambiarle
  el cargo a alguien solo para que pudiera firmar.
- `admin` siempre puede: es quien destraba cuando el responsable está de
  vacaciones o alguien quedó mal configurado.
- `solo_lectura_no` sigue protegiendo toda escritura, y bloquea también a
  `gerencia`. Ese control va aparte del permiso por área, no en vez de él.
- **El frontend no decide permisos**, los pregunta. El backend responde qué
  puede hacer cada quien (por ejemplo `alcance.puede_cambiar`) y la interfaz
  esconde lo que no aplica. Un control deshabilitado que nadie puede usar solo
  genera la pregunta de por qué no funciona.

### Borrar cosas

El borrado por defecto **protege el histórico**. Cuando algo tiene datos
asociados se responde 409 explicando qué se perdería y ofreciendo la salida
suave (desactivar, archivar). El borrado total existe, pero hay que pedirlo a
propósito con un parámetro explícito, y la interfaz solo lo ofrece **después**
de decir cuántos registros se van a perder.

Ejemplos: `DELETE /indicadores/{id}?incluir_mediciones=true`, cancelar un
proyecto lo archiva sin borrar nada, retomar anula el acta pero no la elimina.

### Datos que vienen de fuera

- **Listas cerradas, no texto libre**, cuando el dato alimenta un reporte. Si
  el cliente escribe el punto de venta a mano, «Centro», «centro» y «Sede
  Centro» son tres lugares distintos y el informe deja de servir; y eso no se
  arregla después, porque los datos ya entraron mal.
- **Pero nunca a costa de que alguien no pueda radicar.** En PQRS, si el
  cliente no encuentra su producto, lo escribe y sigue. La solicitud queda con
  `producto_por_confirmar` y **el servidor no la deja cerrar** hasta que
  Servicio al Cliente la amarre a un producto del catálogo — igual que ya se
  hace con el tipo. El botón «No encuentro mi producto» se ofrece **siempre**,
  no solo cuando la búsqueda falla: quien no sabe el nombre exacto no tiene por
  qué adivinar dos veces antes de que el formulario le dé una salida.
- **Esa marca se DEDUCE, no se recibe.** `producto_por_confirmar` sale de
  «hay nombre y no hay código», nunca de una bandera del formulario: una
  bandera puede llegar diciendo lo contrario de lo que muestran los campos y
  entonces un nombre a mano entraría a los informes disfrazado de producto
  identificado. Al confirmar, el nombre se toma **del catálogo** a partir del
  código; aceptarlo escrito sería volver al problema que esto resuelve.
  Lo que el cliente escribió queda en el seguimiento: si mucha gente pide el
  mismo producto con un nombre que no está, eso dice algo del catálogo.
- **Lo que se copia de otro sistema se copia mínimo.** El catálogo trae código,
  nombre y presentación. Nada de precios ni existencias: la tabla del portal ni
  siquiera tiene esas columnas, así que no hay forma de que se filtren por un
  endpoint público.

### Áreas

**Una sola fuente por lado**: `backend/app/core/areas.py` y
`frontend/src/core/areas.js`. Una prueba verifica que coincidan. Nunca
declarar una lista de áreas dentro de un componente.

### Canales de atención

Mismo trato que las áreas: `backend/app/core/canales.py` y
`frontend/src/core/canales.js`, con `tests/canales.test.mjs` verificando que
coincidan. Estaban repetidos en cuatro archivos y ya se habían separado —el
formulario de felicitaciones ofrecía «Llamada telefónica» donde el resto del
portal dice «Línea telefónica», así que la misma llamada caía en dos canales
y el reporte las contaba aparte. `normalizar()` traduce el nombre viejo al
radicar, en los dos routers.

**El canal decide el prefijo del código de seguimiento** (`PVG0010`), y de
ese prefijo salen los reportes por sede. Cambiar cómo se escribe un canal
deja a ese punto de venta sin su consecutivo propio, en silencio.

**Los QR de los puntos de venta.** `/q/PVG` abre el formulario público ya
marcado como Guayabal — el canal viene del letrero que el cliente tiene
enfrente en vez de una lista donde tiene que acertar, y eso importa porque
después de radicar el prefijo ya no se corrige. El código del QR **es** el
prefijo del radicado, así que no se cambia: un cartel impreso y pegado en una
sede no se actualiza solo.

Se generan en `modules/pqrs/qr.py` con `segno` (Python puro, sin
dependencias del sistema) y se imprimen desde Administración. La URL la arma
el SERVIDOR con `FRONTEND_URL`: si la pantalla la armara con el dominio del
navegador, un administrador entrando por la IP interna imprimiría carteles
que apuntan a `172.20.…` y ningún cliente podría abrirlos.

Los endpoints de QR son públicos a propósito —solo contienen una URL pública,
y así la pantalla los muestra con un `<img>`, que no manda la cabecera de
sesión— y el código se valida contra la lista cerrada, de modo que de ahí no
sale un QR con el dominio del portal apuntando a otra parte.

**Un QR no se vence.** Lo que caduca es generarlo en un sitio que crea un
enlace intermedio suyo y lo apaga si dejas de pagar. Estos apuntan directo al
portal: no hay servicio de terceros que se pueda caer ni cobrar.

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
- **El inicio de sesión es panel dividido.** A la izquierda la marca (el
  logo, qué es el portal y qué se hace adentro) y a la derecha el formulario;
  debajo de `lg` el panel desaparece y el logo se sube encima. Mucha gente
  llega por un enlace de un correo o por el QR de una sede, y una tarjeta
  suelta en una pantalla vacía no dice a dónde llegó ni que es interno. El
  degradado y la retícula del panel son utilidades de `index.css`
  (`panel-marca`, `reticula`), no estilos dentro del componente: son color de
  marca. **No hay «¿Olvidaste tu contraseña?»** porque el portal no tiene cómo
  restablecerla; el pie manda a `CORREO_SOPORTE` de `marca.js`, que es quien
  sí la cambia. Un enlace que no lleva a ninguna parte es peor que no tenerlo.
- **«Mantener sesión iniciada» decide dónde vive el token.** Marcada,
  `localStorage`; sin marcar, `sessionStorage` — y muere al cerrar el
  navegador. Antes iba siempre a `localStorage`, así que en un computador
  compartido —los de los puntos de venta lo son— el siguiente que lo prendiera
  entraba con la cuenta del anterior. La regla vive en `core/sesion.js` y es
  la **única** que toca esos almacenes: `AuthContext` y `api.js` pasan por
  ella. Al guardar se limpia el otro almacén, o quien entró recordado y luego
  entra sin marcar la casilla seguiría dentro después de cerrar la pestaña.
  Todo va en try/catch: en modo privado tocar `localStorage` **lanza**, y eso
  no puede dejar a nadie sin poder entrar.
- **El 401 del login no es una sesión vencida.** Son el mismo código y no la
  misma cosa: el interceptor de `api.js` mandaba a `/login` ante cualquier
  401, así que una contraseña equivocada recargaba la página y se llevaba por
  delante el mensaje de error — el formulario parpadeaba y volvía en blanco.
  `esPeticionDeLogin()` lo exceptúa, y la redirección no se dispara si ya se
  está en `/login`.
- **Un archivo elegido se puede quitar antes de enviar.** En los formularios
  de radicación (público: `CampoAdjunto`; interno: `ArchivoElegido`) cada
  adjunto ofrece «Cambiar» y «Quitar», y el `<input>` se limpia al quitar: si
  no, volver a elegir el mismo archivo no dispara `onChange`.
- **Una PQRS se nombra por la empresa**, con el contacto debajo: así se
  reconoce al cliente en la lista. Una persona natural escribe su nombre en
  «Empresa / Persona», así que cuando coinciden sale una sola vez. La regla
  vive en `nombrePrincipal()` de `modules/pqrs/constants.js`; no la repitas
  en un componente.
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
- **Esperar tiene cuatro capas, y cada una es para un momento distinto**
  (`core/components/Cargando.jsx`). Un «Cargando…» centrado servía para las
  cuatro y no sirve para ninguna: el layout salta cuando llegan los datos, y
  un texto en medio de la pantalla no dice si falta un segundo o un minuto.

  | Cuándo | Qué se usa |
  |---|---|
  | Al abrir el portal | El bloque de `index.html` — **no** un componente |
  | Cambiar de módulo o de mes | `BarraDeCarga`, 2,5 px arriba, sin tapar nada |
  | Datos de una vista | `Esqueleto`, `EsqueletoKPIs`, `EsqueletoFilas`… |
  | Guardar, recalcular | `Boton` con `cargando`, o `Spinner` suelto |

  **El arranque vive en `index.html` a propósito.** El bundle pesa ~860 KB:
  entre que llega el HTML y React monta hay una espera real, y escrito en
  React solo aparecería DESPUÉS de descargarlo — o sea, cuando ya no hace
  falta. Es la única excepción a «los colores viven en index.css»: van en
  línea porque el CSS también se descarga, y esto tiene que estar pintado en
  el primer frame. `main.jsx` lo retira al montar.

  **`BarraDeCarga` no recibe props**: lee `useIsFetching()` de React Query,
  así que una pantalla nueva no tiene que acordarse de encender nada.

  **Nunca reemplaces datos ya visibles por un esqueleto.** Al cambiar de mes
  o filtrar, lo anterior se atenúa con `Atenuado` y se queda; taparlo obliga
  a esperar para volver a ver algo que ya se estaba leyendo. El esqueleto es
  solo para cuando no hay NADA que mostrar, y tiene la forma exacta de lo que
  viene: si no coincide, la página salta y se percibe peor que el blanco.

  **El spinner va DENTRO del botón que lo disparó**, con el botón inerte
  (`Boton` lo hace solo). Un overlay de pantalla completa para guardar un
  formulario tapa justo lo que se acaba de escribir, y un botón que sigue
  pulsable mientras viaja la petición termina en dos registros iguales.
- **Quien scrollea es la PÁGINA, no un panel de adentro.** El contenido vivía
  en un `<main>` de altura fija con su propio `overflow-y`, y en las listas
  largas —PQRS con todo el histórico— el navegador dejaba de pintar el final:
  media pantalla en blanco, como si la página se cortara, y volvía sola al
  mover el mouse. Es un fallo de repintado de esos paneles: no se arregla
  desde la vista, se arregla no teniendo el panel. El menú y la cabecera se
  quedan arriba con `sticky` —que ocupa su lugar en la fila, a diferencia de
  `fixed`— y `Layout.jsx` sube al tope al cambiar de módulo. **Una vista
  nueva no crea su propio contenedor con scroll**; los que quedan
  (modales, el Gantt, la matriz del año) son cajas acotadas a propósito.
- Gráficas: SVG a mano, sin librería (el servidor no reinstala dependencias con
  fiabilidad). Una serie = un color y sin leyenda; la meta es una anotación
  punteada, no una segunda serie; nunca doble eje.

## Cosas que ya mordieron

- **Fechas con y sin zona horaria.** Postgres las devuelve con zona y SQLite
  sin ella; restarlas revienta. Usar el helper `_aware()` que hay en
  `resumen.py` y en `fuentes.py`.
- **Indicadores de fórmula (`tipo_captura="formula"`).** Para cuentas que no
  caben en valor ni en razón: `80 * A / B`, `(A - B) / A * 100`. La fórmula
  se guarda como texto en una gramática cerrada (números, letras A–Z, `+ - *
  /`, paréntesis) y la evalúa `modules/indicadores/formula.py` con un
  analizador propio — **nunca `eval`**. Cada letra es una fila de
  `ind_variables` con su etiqueta, y lo digitado cada mes va en
  `ind_valores_variable`. Reglas: la fórmula usa exactamente las variables
  declaradas; dividir por cero rechaza el registro (el mes queda sin dato,
  igual que el denominador en cero); **el acumulado suma cada variable y
  aplica la fórmula una vez**; con meses registrados no se agregan ni quitan
  variables (409), pero sí se renombran y se cambia la fórmula, que recalcula
  cada mes y deja el cambio en `ind_historial`. La fórmula NO multiplica por
  100 sola: si es porcentaje, el `× 100` va dentro. La pantalla arma piezas
  (`indicadores/formula.js`) pero no valida ni calcula: pregunta a
  `POST /indicadores/formula/probar`, con espera de 350 ms entre teclas.
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
- **Un 422 dejaba la página en blanco.** Cuando FastAPI rechaza un dato,
  `detail` NO es texto: es una lista de objetos `{type, loc, msg, input, ctx}`.
  El patrón `setError(e.response?.data?.detail || '...')` guardaba esa lista y,
  al pintarla, React lanzaba el error #31 y desmontaba la pantalla — el usuario
  no veía el mensaje, veía la nada. **Todo error de API pasa por
  `mensajeDeError()` de `core/errores.js`**, que además traduce los mensajes de
  Pydantic al español. Nunca leas `data.detail` directo en un componente.
- **Un límite del schema sin su tope en el input.** El caso anterior se disparó
  porque un `<input>` no tenía `maxLength` y el schema exigía 300 caracteres. Si
  un campo tiene `min_length` o `max_length` en el backend, el formulario lleva
  el mismo tope, y la constante vive en el `constants.js` del módulo con un
  comentario que recuerde que están sincronizados.
- **Un texto más largo que su columna no dejaba radicar una PQRS.** Ni el
  formulario interno ni el público tenían `maxLength`, y el servidor no
  revisaba largos: «5 galones de 20 litros» en una cantidad (`String(20)`)
  llegaba al `commit` y Postgres respondía `value too long for type
  character varying(20)` — un 500 que la pantalla mostraba como «Error al
  crear la PQRS», sin decir qué campo. **Las pruebas no lo veían porque
  SQLite no aplica el largo de un VARCHAR.** Ahora `validar_largos()` de
  `pqrs/service.py` lee el tope de la propia columna y responde 400 con el
  nombre del campo, antes de guardar adjuntos; y los dos formularios usan
  `LIMITES_RADICACION` de `modules/pqrs/constants.js`, que una prueba ata a
  `models/pqrs.py`. Todo endpoint que guarde texto libre en un `String(n)`
  necesita las dos cosas.
- **Una prueba que manda un parámetro que la pantalla no manda no prueba
  nada.** Reenviar y cancelar una nota crédito reusaban el schema de
  responder, donde `decision` es obligatoria y en esas dos no significa nada.
  La prueba del backend pasaba —mandaba un `decision` inventado— y el botón
  respondía 422 en el navegador. Es la otra cara de «un arreglo solo en el
  servidor no arregla la pantalla»: si el endpoint acepta algo que la pantalla
  nunca va a mandar, **pruébalo con lo que de verdad viaja** (aquí, cuerpo
  vacío). Y un endpoint que no usa un campo no comparte schema con uno que sí.
- **Un arreglo solo en el servidor no arregla la pantalla.** La 0.19.4
  anunció que filtrar proyectos por «cerrado»/«cancelado» ya funcionaba: el
  endpoint ignora el archivo cuando recibe un estado terminal. Pero
  `ProyectosView.jsx` nunca le mandaba el estado — pedía siempre
  `archivados=false` y filtraba en el navegador —, así que la lista siguió
  vacía y la prueba del backend pasaba igual. Ahora la consulta se arma con
  `parametrosListaProyectos()` de `masterPlanner/constants.js`, y
  `tests/filtroProyectos.test.mjs` verifica que la vista la use y que los
  estados terminales coincidan con el modelo. En Mejora el mismo arreglo sí
  estaba en la pantalla (`esEstadoTerminal()` en `Mejora.jsx`). **Cuando un
  arreglo depende de un parámetro, hay que comprobar que la pantalla lo
  manda**, no solo que el endpoint lo acepta.
- **Dos migraciones el mismo día = Alembic con dos cabezas y el backend sin
  arrancar.** Pasa cuando dos personas crean su migración colgando del mismo
  padre; el síntoma es `Multiple head revisions are present` en bucle. Si tu
  migración todavía no se aplicó en ningún lado, **reencadénala** cambiando su
  `down_revision` a la otra cabeza: la historia queda lineal y no hace falta
  `alembic merge`. Antes de crear una migración, `git pull`.
- **El `build` pasa con variables no definidas.** esbuild no las revisa; quien
  las caza es `eslint`. Un `MAX_ACCION` sin importar compiló limpio y habría
  reventado en el navegador. Por eso van los tres pasos —pruebas, eslint,
  build— y ninguno reemplaza a otro.
- **Los comentarios `//` no van entre atributos de JSX.** Ahí solo sirve
  `{/* ... */}`, o el comentario arriba del elemento.
- **Una lista devolvía el registro entero para pintar ocho columnas.** `GET
  /pqrs` mandaba la PQRS completa —descripción de hasta 4.000 caracteres,
  productos, rutas de adjuntos, la solución— por cada solicitud del
  histórico, y la pantalla usaba trece campos. Peor: los productos son otra
  tabla, así que serializarlos era **una consulta POR FILA**. Medido con
  5.000 PQRS: 14,1 MB y 2,2 s contra 1,7 MB y 0,1 s con `PQRSResumenOut` +
  `load_only`. **Una lista manda lo que la lista pinta**; el detalle lo pide
  el detalle. La regla se prueba en `tests/test_pqrs_lista.py`, que cuenta
  las consultas y falla si vuelve a haber una por fila. Con unos cientos de
  registros nada de esto se nota — y por eso se descubre tarde.
- **El radicado de Calidad salía de un `count()`.** El mismo defecto que ya
  había mordido en el código de seguimiento: con un hueco en el medio, el
  siguiente número ya existe y el `commit` revienta por la restricción de
  unicidad *después* de haber guardado la solicitud. Todo consecutivo sale del
  MÁXIMO, nunca de un conteo.
- **El historial público mostraba los comentarios internos.** La consulta del
  cliente enviaba el `comentario` del seguimiento, que es donde el área escribe
  sus notas de trabajo. Ahora el movimiento se REDACTA a partir de
  `estado_nuevo` (ver `pqrs/historial_publico.py`), y el schema público no tiene
  campo de comentario: no es que llegue vacío, es que no existe.
- **Filtrar por área ignoraba las áreas participantes.** Un proyecto de TICS
  donde Mercadeo trabaja se le mostraba a Mercadeo en la lista general y
  desaparecía apenas filtraba por su área. Para filtrar se usa `condicion_area()`
  en el backend y `perteneceAlArea()` en el frontend. **Pero el presupuesto se
  le sigue atribuyendo solo al área responsable**: repartirlo entre las
  participantes multiplicaría los totales.

## Integraciones

Todo lo que habla con algo de fuera falla en silencio y nunca tumba una
petición: si Microsoft, n8n o el ERP están caídos, el portal sigue trabajando.

- **Microsoft 365 (calendario).** Las tareas del Master Planner con responsable
  y fecha aparecen en el Outlook de esa persona. Va en una sola dirección:
  portal → Outlook. `core/graph.py` autentica como aplicación; con
  `MS_TENANT_ID`, `MS_CLIENT_ID` y `MS_CLIENT_SECRET` vacíos la integración
  queda apagada. **La hora se convierte a la zona local antes de enviarla**:
  Postgres devuelve UTC, y mandar ese valor diciéndole a Graph que es hora de
  Bogotá corría los eventos cinco horas.
- **n8n.** Los flujos viven versionados en `n8n/*.json`, no solo dentro de la
  herramienta. El `Path` del nodo Webhook tiene que ser EXACTAMENTE el nombre
  del evento que dispara el backend, o el log muestra `... is not registered`.
  Los webhooks mandan el CORREO del destinatario, nunca su id: obligar a n8n a
  autenticarse para resolver un id es pedirle que averigüe algo que el backend
  ya tenía a la mano. Y en el HTML de un correo, `href="{{ $json.link }}"` — el
  campo ya es una expresión, y un `=` de más deja el enlace roto.
- **Catálogo de productos (Oracle del ERP).** El portal NO se conecta a Oracle.
  Un script en el servidor del ERP (`integraciones/erp/`) lee una vista de solo
  lectura y **empuja** el catálogo al portal por HTTP. La dirección es lo que
  importa: el portal está expuesto a internet, así que ahí no puede haber ni
  credenciales ni rutas hacia la base del ERP. De paso, el buscador responde en
  milisegundos y sigue funcionando aunque el ERP esté caído.

## Cómo se le sirven los datos a una automatización

Los endpoints que alimentan recordatorios (`/pqrs/por-vencer`,
`/indicadores/pendientes-de-registro`,
`/master-planner/tareas-vencidas-por-persona`) devuelven la información **ya
agrupada por destinatario y con el correo resuelto**. n8n solo recorre y manda.

Dos razones: un correo que dice «tienes 3 pendientes» se atiende, y uno con la
lista de los 40 de la empresa se archiva sin abrir; y la lógica de agrupar y de
contar días hábiles tiene pruebas en el backend, mientras que dentro de un flujo
de n8n se rompe en silencio.

Lo que no tiene responsable **sale aparte, nunca se descarta**: una PQRS sin
asignar con el plazo corriendo es el caso más peligroso de todos.

- **Notas crédito: toda solicitud empieza por COMERCIAL.** La cadena vive
  en `modules/notas_credito/flujo.py` y es la **única fuente**; el router, los
  correos y la pantalla preguntan ahí.

  | Quién pide | Recorrido |
  |---|---|
  | Un punto de venta | Comercial aprueba → el punto emite |
  | Ventas Institucionales | Comercial aprueba → Contabilidad verifica en la DIAN → se emite |
  | Ventas Institucionales, motivo con producto | **La bodega confirma que llegó** y después lo anterior |

  Antes las del punto de venta entraban directo a Contabilidad —era el flujo
  heredado de cuando esto se pedía por correo— y el resultado era que
  **Contabilidad terminaba decidiendo un asunto comercial**. Quien decide si
  se le devuelve la plata al cliente es Comercial, y eso no cambia porque la
  venta se haya hecho en un mostrador.

  **En el mostrador Contabilidad ya no autoriza.** Tuvo un turno —el estado
  `solicitada`— entre Comercial y la emisión, y era una firma de más: la
  decisión comercial ya está tomada, el punto emite contra su propia factura
  y ante la DIAN no hay nada que verificar. Dos manos para lo que decide una
  solo agregan el tiempo que la solicitud pasa esperando. En la institucional
  Contabilidad sigue igual, porque ahí sí verifica algo.

  `solicitada` sobrevive como **etapa del historial** —las que autorizó en su
  día lo siguen diciendo— pero no es el estado de ninguna solicitud viva: no
  está en `ESTADOS` ni en ningún grupo de filtro. La migración
  `c4d81e73ab20` movió las que estaban ahí, y **no todas significaban lo
  mismo**: las que Comercial ya había aprobado quedaron `aprobada`, y las que
  nunca pasaron por él —del flujo viejo, cuando una del mostrador nacía
  directo en Contabilidad— volvieron a `en_comercial`. Darlas todas por
  aprobadas habría aprobado en silencio algo que nadie miró. La diferencia se
  lee de `nc_historial`, no se adivina, y cada solicitud movida dejó ahí su
  renglón: una que ayer decía «Esperando a Contabilidad» y hoy dice
  «Aprobada» sin explicación se lee como que alguien la firmó a escondidas.

  Consecuencia que sale sola de que la copia salga de la CADENA: cuando una
  del mostrador llega a Comercial, **Contabilidad ya no va en copia** — no le
  toca después, así que sería un correo sobre algo en lo que no tiene nada
  que hacer. En la institucional sigue yendo.

  `notas_credito.autorizar` **ya no atiende ningún turno**. Se dejó la
  capacidad porque es la que decide quién ve el módulo COMPLETO (`ve_todas`),
  que es lo que Contabilidad necesita para trabajar las institucionales;
  conserva el nombre viejo porque renombrarla le quitaría el permiso a todo
  el que hoy lo tiene, por nada a cambio.

  **Comercial ve las dos ramas**, justamente porque abre las dos: mientras
  solo intervenía en las institucionales se le escondían las del mostrador, y
  dejarlo así habría hecho que el primer turno de esas no lo pudiera atender
  nadie —ni en la lista ni abriéndolas por id (404)—. La bodega y la
  verificación ante la DIAN sí siguen viendo solo las institucionales: son
  pasos que las del mostrador no tienen.

  **El estado dice de quién es el turno** (`en_bodega`, `en_comercial`,
  `en_contabilidad`…) y no hay un campo `etapa` aparte: dos columnas que
  describen lo mismo terminan diciendo cosas distintas. Por eso quitar un
  paso del flujo es mover solicitudes, y eso va con migración de datos.

  **Un solo endpoint mueve toda la cadena** (`POST /{id}/responder` con
  `aprobar` | `rechazar` | `devolver`). Con uno por etapa, aprobar «por
  comercial» algo que está en la bodega sería cuestión de escribir la otra
  URL; así el orden lo impone el servidor y no la memoria de la gente.

  **Qué motivos traen producto lo define el MOTIVO**
  (`nc_motivos.requiere_bodega`), no una pregunta del formulario: es una
  propiedad del motivo —«devolución de mercancía» siempre trae producto— y
  preguntándolo cada vez la respuesta dependería de quién radica. Lo
  administra Contabilidad desde el portal, sin desplegar.

  **La bodega no es el punto de venta, aunque Guayabal y La 65 se llamen
  igual en los dos catálogos.** `core/bodegas.py` (gemelo en
  `frontend/src/core/bodegas.js`, con prueba que los ata) y `users.bodega`:
  quien tiene bodega marcada atiende la suya, quien no la tiene responde por
  las dos — igual que el coordinador sin punto de venta ve los seis. Lo ajeno
  responde **404**.

  **Devolver no es rechazar.** Rechazar cierra el caso; devolver lo deja vivo
  en manos de quien lo pidió, con el comentario de qué corregir (obligatorio:
  una devolución muda obliga a una llamada). **Al reenviarla vuelve al
  PRINCIPIO de su cadena**, porque quien ya había aprobado lo hizo sobre unos
  datos que acaban de cambiar. Y `cancelada` —la retira quien la pidió— se
  cuenta aparte de `rechazada`: una que el vendedor retira no es un caso que
  la empresa negó.

  **Los filtros son GRUPOS con nombre y van en el orden del flujo**
  (`flujo.GRUPOS_FILTRO`, gemelo en `FILTROS` de `notas_credito/constants.js`,
  con prueba que los ata). Dos razones: «Contabilidad» cubre los **dos**
  estados en que le toca a ella —`solicitada` y `en_contabilidad` son dos
  permisos distintos pero una sola mano esperando, y con etiquetas distintas
  la pantalla aparentaba cinco pasos donde hay cuatro—; y armar la lista
  recorriendo los estados tal como se declararon la sacaba en el orden
  equivocado. **El orden de una lista afirma cómo va el proceso aunque nadie
  lo escriba**: la que empezaba por Contabilidad decía que el proceso empieza
  ahí. Un `assert` exige que todo estado esté en algún grupo — uno que no lo
  esté es una solicitud que no aparece por ningún lado.

  **Las cuatro manos van en `nc_historial`, no en columnas.** Con la
  devolución una solicitud puede pasar dos veces por la misma etapa, y eso no
  cabe en tres columnas. `autorizado_por` quedó como la ÚLTIMA firma.

  **Un solo evento de n8n para todas las etapas** (`nc-en-turno`): el correo
  dice qué hacer leyendo `que_hacer` del payload. Uno por etapa obligaría a
  construir, importar y activar otro flujo a mano cada vez que se agregue un
  paso. Cuando la solicitud llega a Comercial, **Contabilidad va en copia**
  (`en_copia` → `ccEmail`) para que vaya mirando la DIAN sin decidir todavía.
  `nc-solicitada` se retiró: `nc-en-turno` lo cubre.

  **El líder del área de quien radica va en COPIA del primer correo**, para
  que sepa que su sede pidió una nota crédito. No es un paso del flujo: no
  firma nada y la solicitud no lo espera. Meterlo en la cadena habría sido una
  firma que nadie pidió y un sitio donde todo se queda quieto cuando el líder
  está de vacaciones. Solo en el PRIMER turno — en los siguientes no aporta
  nada y serían cuatro correos por una sola nota, que es como se aprende a no
  abrirlos. Un área sin nadie con rol `lider` simplemente no suma a nadie.

  **En copia va siempre quien atiende el turno SIGUIENTE**, y sale de la
  cadena, no de una capacidad escrita a mano: el «siguiente» no es el mismo en
  las dos ramas (en la del mostrador Contabilidad *autoriza*, en la
  institucional *verifica ante la DIAN*), así que nombrar una sola dejaba la
  otra sin copia en silencio. Se excluye el último turno, el de emitir: para
  eso está `nc-por-emitir`, y adelantarlo sería pedirle a alguien que prepare
  algo que todavía puede rechazarse.

  Las tres capacidades nuevas (`notas_credito.confirmar_producto`,
  `.aprobar_comercial`, `.verificar_dian`) las siembra la migración a
  Logística + Producción, Comercial y Contabilidad. **Se siembran en la
  migración y no solo en `sembrar_capacidades_iniciales`** porque esa siembra
  corre cuando alguien abre Administración › Capacidades: si nadie la abre, la
  primera solicitud institucional se queda esperando a alguien que todavía no
  tiene el permiso. Para acotar las bodegas a sus dos coordinadores se revoca
  el área y se otorga por nombre, sin tocar código.

- **Notas crédito: aprobada es «falta emitirla».** Al aprobar sale un aviso
  más (`nc-por-emitir`) **al punto de venta de la factura**, que es quien la
  emite y escribe su número —los puntos tienen la capacidad
  `notas_credito.registrar`—. Se reconocen por el prefijo del canal
  (`canales.prefijo_de` contra `users.punto_venta`), igual que las PQRS de
  cada sede: una nota crédito de Guayabal no es trabajo de Belén. A quien la
  pidió no se le manda por ahí, que ya recibe `nc-respondida` y serían dos
  correos por lo mismo. **Si en ese punto no hay nadie que pueda emitirla, no
  se descarta**: va a todos los que tienen la capacidad, y el correo lo
  advierte. `core/capacidades.usuarios_con()` es lo que permite filtrar por
  algo más que el correo.

## Pendientes conocidos

- **Las listas todavía se traen enteras, y se filtran en el navegador.** PQRS,
  proyectos y OMP piden TODO el histórico y buscan en memoria. Aligerar la
  fila (arriba) compró tiempo, no resolvió el fondo: a partir de unos pocos
  miles de registros lo que pesa es pintar la tabla. El paso siguiente es
  filtrar y paginar **en el servidor** —búsqueda, fechas y punto de venta
  incluidos, porque un filtro que solo mira la página actual miente— y
  empezar por PQRS, que es la que más crece. Para saber cuándo toca, medir en
  vez de opinar: `docker exec protokimica_backend python -m
  app.medir_lista_pqrs --filas 20000` siembra, mide y borra (solo contra la
  base de desarrollo; se niega si encuentra demasiadas PQRS de verdad).
- **Catálogo de productos: falta el lado del ERP.** El portal ya está
  completo (tabla, sincronización, buscador con límite por IP, pruebas, y el
  formulario público conectado al catálogo real). Lo que falta es **fuera del
  repositorio**: en MORFEO hay que crear la vista `V_PRODUCTOS_PORTAL` y el
  usuario `PORTAL_LECTURA`, poner `CLAVE_SINCRONIZACION` en el `.env.prod` y
  programar `integraciones/erp/sincronizar_productos.ps1`, que todavía trae
  nombres de tabla de ejemplo. Hasta que eso corra, **el buscador no devuelve
  nada** — y por eso la salida de escape no es opcional. Ver
  `integraciones/erp/LEEME.md`.
- **Mejora: falta el exportador y el importador.** El modelo ya cubre las 23
  columnas del `RCN-F-13`, pero todavía no se puede **regenerar el .xlsx** con
  el encabezado, la fila 5 de numeración, los anchos de columna y el pie de
  confidencialidad que Calidad y los auditores externos esperan (necesita
  `openpyxl` en `requirements.txt`, y por tanto desplegar con `--build`).
  Tampoco existe el script que importe el histórico de los Excel por proceso;
  para eso están `requiere_revision` en `omp_oportunidades` y en
  `omp_seguimientos`, y `limpiar_no_aplica()` en `mejora/catalogos.py`. La
  regla del importador: **cuando el parseo falle, meter el bloque completo y
  marcarlo — nunca perder texto por intentar ser exacto.**
- **Mejora: los adjuntos son una ruta, no un archivo.** `omp_seguimientos.adjunto`
  y `omp_acciones.evidencia` guardan texto; subir el archivo depende de que
  antes se arregle `/uploads`, que hoy no tiene control de acceso — y las
  evidencias de auditoría no pueden quedar en una URL adivinable.
- **PQRS: los adjuntos quitados o reemplazados se acumulan en `/uploads`.**
  Es a propósito (se pueden recuperar desde la ruta del historial), pero no
  hay limpieza periódica.
- **Inicio: la cifra de PQRS abiertas no respeta el punto de venta.** Un
  líder de `Puntos de Venta` ve en el resumen el total de la empresa aunque
  en PQRS solo vea las de su sede.
- **Las PQRS anteriores a `estado_nuevo`** no tienen el estado guardado en sus
  seguimientos, así que el historial público les muestra «Actualización de tu
  solicitud» en vez del movimiento concreto.
- **Los proyectos cerrados antes del acta** no tienen `mp_cierres`, así que su
  pestaña de Cierre dice que siguen abiertos.
- **`mp_proyectos_cerrados`** cuenta por `fecha_fin_real`, así que suma también
  los cancelados. Habría que separar los que se finalizaron de los que se
  abandonaron.
- Flujos de n8n: quedan las alertas de indicadores en rojo y el disparo mensual
  de `POST /indicadores/calcular-periodo` (necesita el usuario de servicio
  `automatizaciones@protokimica.com`).
- `/uploads` sin control de acceso real; `UPLOAD_DIR` quemado en 3 sitios.
- `router_public.py` y `seed.py` tienen `slug == "protokimica"` quemado: lo
  público solo sirve para una empresa.
- Marca (colores, logo) quemada en el frontend.
- Indicadores: falta la exportación.
- `src/core/AuthContext.jsx` tiene un error de lint preexistente
  (`react-refresh/only-export-components`). No es de ningún cambio nuevo.

## Si estás retomando esto en otra conversación

Lo primero, en este orden:

1. **`git pull`.** Se trabaja sobre `Backend-MasterPlanner`, no sobre `main`.
2. **Levantar el entorno** y confirmar que arranca:
   ```bash
   cd protokimica-portal
   docker compose up -d
   docker compose logs backend --tail 20
   ```
   Si aparece `Multiple head revisions`, hay dos migraciones colgando del mismo
   padre — ver «Cosas que ya mordieron».
3. **Correr todo antes de tocar nada**, para saber de qué punto se parte:
   ```bash
   docker exec protokimica_backend pytest tests -q
   cd frontend && npm test && npx eslint src && npm run build
   ```

Detalles del entorno que ahorran tiempo:

- Docker Desktop en Windows se cae solo cada tanto. Si `docker` no responde,
  hay que volver a abrirlo:
  `C:\Users\<usuario>\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`
- `pytest` no está en `requirements.txt`: dentro del contenedor,
  `pip install pytest` antes de la primera corrida.
- En Windows, `git` no está en el PATH de PowerShell; sí en Git Bash.
- El servidor es `zeus` (`172.20.70.47`), se llega por VPN FortiClient. El
  portal responde en `http://172.20.70.47:8080` sin pasar por Cloudflare, y n8n
  en el `5679` (que exige túnel SSH por su cookie segura).

