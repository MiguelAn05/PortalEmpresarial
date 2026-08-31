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

## Pendientes conocidos

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

