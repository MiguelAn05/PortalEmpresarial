# Del ERP al portal: productos y clientes

El portal **no se conecta a Oracle**. Un script que corre en MORFEO
(`sincronizar_erp.ps1`) lee el ERP y le manda al portal dos cosas por HTTP:

1. **El catálogo de productos**: código, nombre, presentación, grupo y fecha
   de la última venta. Con eso funciona el buscador de los formularios de
   PQRS y se agrupan los informes por producto.
2. **Las huellas de los clientes**: un HMAC-SHA256 de cada NIT, calculado
   en MORFEO. Sirve para una sola pregunta —«¿quien radica ya es cliente
   nuestro?»— sin copiar ningún cliente al portal (ver más abajo).

La dirección es lo que importa: el portal está expuesto a internet, así que
si algún día lo comprometen, ahí no hay ninguna credencial ni ruta hacia la
base del ERP. El tráfico va de la red interna hacia afuera, y el firewall de
MORFEO no tiene que abrirle el 1521 a nadie.

Además, así deja de importar que Oracle sea 11.2: no hace falta ningún driver
ni el Instant Client dentro del contenedor.

**El script solo hace `SELECT`.** No crea, no modifica y no borra nada en
Oracle, y tampoco crea vistas: no hay que tocar el esquema del ERP.

## Lo que hay que hacer una sola vez

### 1. En Oracle (MORFEO)

#### Qué esquema es cuál — ojo con esto

En MORFEO conviven **dos entornos completos** del ERP. Confirmado con
`all_objects`:

| Esquema | Objetos | Qué es |
|---|--:|---|
| **`GEMIMUS01`** | 1222 | **Producción. Es el que se usa.** |
| `PRUEBAS` | 1214 | Copia de pruebas. Se ve igual de real: 7.774 productos con códigos y nombres creíbles |
| `ADMIN_GEM` | 54 | El usuario administrador, no los datos |
| `CRM01` | 133 | Otro módulo |

También hay `GEMIMUS01_LOGS` y `PRUEBAS_LOGS` en paralelo, que es lo que
delata que son dos entornos y no dos esquemas del mismo.

> **Apuntar a `PRUEBAS` no da ningún error.** El portal quedaría sirviéndole a
> los clientes un catálogo de mentira, y eso solo se nota cuando alguien
> reclama por un producto cuyo código no existe en la base real.

#### Qué lee el script

| Tabla de `GEMIMUS01` | Columnas | Para qué |
|---|---|---|
| `PRODUCTOS` | `PR_PRODUCTO`, `PR_DESCRIPCION`, `PR_UNIDADDEMEDIDA`, `PR_GRUPO`, `PR_ESTADO`, `PR_FECHAULTIMAVENTA` | El catálogo (solo `PR_ESTADO = 'A'`) |
| `UNIDADESDEMEDIDA` | `UM_CODIGO`, `UM_DESCRIPCION` | La presentación |
| `GRUPOS` | `GR_GRUPO`, `GR_DESCRIPCION` | El grupo, para los informes |
| `NITS` | `NIT`, `CLASE`, `ESTADO` | Solo el número, de los clientes activos (`CLASE LIKE '%C%'`) |

Columnas nombradas una por una, nunca `SELECT *`. **Nada de costos**
(`PR_COSTOULTIMO` y compañía) ni, de `NITS`, nada que no sea el número:
ni nombre, ni ciudad, ni datos bancarios.

**Por qué los productos salen de la tabla y no de `V_PRODUCTOS`.** La
primera versión de este LEEME proponía crear una vista de tres columnas
(`V_PRODUCTOS_PORTAL`) encima de `V_PRODUCTOS`. Se cambió porque crear una
vista **es escribir en el esquema del ERP**, y la regla es solo lectura. El
precio: Oracle no limita un `SELECT` por columnas, así que el usuario de
lectura PODRÍA leer `PR_COSTOULTIMO` si alguien cambiara el script. Como la
clave vive solo en MORFEO —nunca en el portal—, se aceptó. Si TI prefiere
cerrarlo del todo, la salida son vistas creadas por TI con el `GRANT` sobre
ellas; el script solo tendría que cambiar los nombres de las tablas.

#### Los clientes no se copian: se copia una huella

El ERP tiene unos 167.000 terceros clientes, muchos personas naturales con su
cédula. El portal no necesita saber quiénes son, solo si el NIT que alguien
escribe en una PQRS es de un cliente. Así que el script:

1. Lee solo el NIT de los clientes activos.
2. Lo deja en cifras y sin ceros a la izquierda (el ERP lo guarda sin dígito
   de verificación).
3. Calcula `HMAC-SHA256(CLAVE_HUELLA_NIT, nit)` y manda **solo eso**.

Los NIT nunca salen de MORFEO. En el portal queda una lista de cadenas de 64
caracteres que, sin la clave, no se pueden convertir de vuelta en un NIT; y la
clave vive en el `.env`, no en la base, así que una copia de la base sola no
revela nada.

Al abrir una PQRS, el portal calcula la huella del NIT escrito (acepta
`900.123.456-7`, `900123456 7` o `9001234567`) y la busca. El detalle muestra
**«Cliente en el ERP»** o **«No aparece en el ERP»**. Lo que el portal
**nunca** hace con esto:

- **Frenar la PQRS.** No aparecer puede ser un cliente nuevo, una persona
  natural o un NIT mal escrito.
- **Decírselo al cliente.** Ni el formulario público ni la consulta del
  radicado lo muestran: si no, el formulario serviría para averiguar quién le
  compra a la empresa.

#### El usuario de solo lectura

Lo crea TI. Hoy `USR_LECTURA` tiene el rol `DBA` (control total) y hay que
reducirlo **antes** de poner su clave en el script:

```sql
REVOKE DBA FROM USR_LECTURA;
REVOKE UNLIMITED TABLESPACE FROM USR_LECTURA;
-- CREATE SESSION se mantiene
GRANT SELECT ON GEMIMUS01.PRODUCTOS        TO USR_LECTURA;
GRANT SELECT ON GEMIMUS01.UNIDADESDEMEDIDA TO USR_LECTURA;
GRANT SELECT ON GEMIMUS01.GRUPOS           TO USR_LECTURA;
GRANT SELECT ON GEMIMUS01.NITS             TO USR_LECTURA;
```

Nada de `SELECT ANY TABLE` ni de roles como `DBA` o `RESOURCE`.

Y pedir que tenga un **perfil sin vencimiento de contraseña**: el de fábrica
de 11g la vence a los 180 días, y ese día la sincronización se cae de
madrugada sin que nadie se entere.

Para comprobar que quedó bien, conectado como `USR_LECTURA`:

```sql
SELECT COUNT(*) FROM GEMIMUS01.PRODUCTOS WHERE PR_ESTADO = 'A';   -- ~7.848
SELECT COUNT(*) FROM GEMIMUS01.NITS WHERE CLASE LIKE '%C%' AND ESTADO = 'A';
SELECT * FROM SESSION_ROLES;   -- no debe aparecer DBA
```

### 2. En el portal

Dos claves largas y distintas en `backend/.env.prod`:

```
CLAVE_SINCRONIZACION=<clave larga y aleatoria>
CLAVE_HUELLA_NIT=<otra clave larga y aleatoria>
```

Se generan con `python3 -c "import secrets; print(secrets.token_hex(32))"`.

- `CLAVE_SINCRONIZACION` es la que deja entrar al script. Si se filtra, se
  cambia sin más.
- `CLAVE_HUELLA_NIT` es con la que se calculan las huellas. **Si se cambia,
  hay que volver a correr el script**: las huellas viejas dejan de coincidir.

Y recrear el contenedor (nunca `restart`: no relee el `.env`):

```bash
sudo docker compose -f docker-compose.prod.yml up -d backend
docker exec protokimica_backend env | grep CLAVE_
```

### 3. En MORFEO

Copiar `sincronizar_erp.ps1` y ajustar el bloque CONFIGURACIÓN: las dos claves
del `.env` (copiadas igual, sin espacios), el usuario de Oracle y la dirección
del portal.

**La dirección:** por defecto va a `https://portal.protokimica.com/api`,
cifrado. Si MORFEO no tiene salida a internet, sirve la IP interna
(`http://172.20.70.47:8080/api`), pero la clave viaja en texto plano por la
red interna.

Probarlo a mano, primero solo los productos:

```powershell
powershell -ExecutionPolicy Bypass -File C:\ruta\sincronizar_erp.ps1 -SoloProductos
powershell -ExecutionPolicy Bypass -File C:\ruta\sincronizar_erp.ps1
```

Imprime cuántos leyó y qué cambió, y lo deja también en
`sincronizar_erp.log`, al lado del script.

Cuando funcione, programarlo en el **Programador de tareas de Windows**. Es
barato —medido con 8.000 productos y 167.000 huellas: menos de un segundo
para los productos y medio segundo para las huellas una vez cargadas—, así
que puede correr **cada hora de 7 a. m. a 7 p. m.**; como mínimo, una vez de
madrugada:

```
Programa:   powershell.exe
Argumentos: -ExecutionPolicy Bypass -File C:\ruta\sincronizar_erp.ps1
```

Cada corrida es completa: no hace falta una incremental, y así un producto
que el ERP desactivó también se entera.

**Cómo se sabe que sigue corriendo:** `GET /api/catalogo/estado` (solo
`admin`) dice cuándo llegó lo último de cada cosa y si salió bien.

## Cómo se encontró la tabla de productos

Lo que sigue es cómo se exploró el ERP la primera vez. Ya está resuelto (ver
«Qué lee el script»), pero sirve si el proveedor cambia el esquema en una
actualización.


Para eso está **`explorar_catalogo.sql`**, en esta misma carpeta. Solo hace
consultas: no modifica nada de la base del ERP.

### Entrar a la base

Estando **en MORFEO** no hace falta red: SQL\*Plus se conecta directo a la
instancia local sin pasar por el listener. Es la forma con menos cosas que
puedan salir mal.

```
sqlplus admin_gem
```

**El usuario es `admin_gem`**, el del ERP — `SYSTEM` responde
`ORA-01017`. Y es mejor así: `admin_gem` ve el esquema de Geminus, que es lo
único que hace falta mirar, y no la administración de la base.

Datos de esta instalación, ya confirmados con `lsnrctl status`:

| | |
|---|---|
| Servicio / SID | `XE` (instancia `xe`, en READY) |
| Puerto | `1521` |
| Host que publica el listener | `MORFEO.ppal.protokimica.com` |
| Oracle Home | `E:\oracle\product\11.2.0\db_1` |

Por red hay que usar **el host que publica el listener**, no `localhost`
—que responde `ORA-12504`— y con la sintaxis de barras dobles:

```
sqlplus admin_gem@//MORFEO.ppal.protokimica.com:1521/XE
```

Si `sqlplus` no se reconoce, no está en el PATH. Suele vivir en
`C:\oraclexe\app\oracle\product\11.2.0\server\bin\sqlplus.exe`.

### Correr el script

Ojo con el `cd`: en CMD, `cd C:\temp` desde otra unidad **no cambia de
unidad** — el prompt se queda en `U:\>` y el script no aparece. Va con `/d`:

```
cd /d C:\temp
dir explorar*
sqlplus admin_gem @explorar_catalogo.sql
```

El `dir` no sobra: si el archivo se creó con el Bloc de notas suele quedar
como `explorar_catalogo.sql.txt`, y SQL\*Plus responde `SP2-0310`.

Deja el resultado en `explorar_catalogo.txt`, al lado del script, para poder
revisarlo con calma o mandarlo por correo.

**Los pasos 1 a 4 se corren solos** y responden dónde está el catálogo:

1. **Qué esquemas hay.** Descarta los que trae Oracle de fábrica. El del ERP
   es el que tiene cientos de tablas.
2. **Tablas cuyo nombre suena a productos** (`%ARTIC%`, `%PRODUCT%`,
   `%ITEM%`…), ordenadas por tamaño aproximado.
3. **Tablas que tienen código Y descripción.** Este es el más útil: encuentra
   la tabla buena aunque se llame `T_MAE_001`, porque busca por las columnas
   y no por el nombre.
4. **Vistas que el ERP ya trae.** Si ya existe una de productos, se usa esa y
   nos ahorramos armar el maestro a mano.

Del 5 en adelante hay que llenar el bloque `DEFINE` del principio del script
con el esquema y la tabla que encontraste, y volverlo a correr. Esos pasos
muestran las columnas, cuántas filas tiene de verdad, diez filas de ejemplo,
qué columna dice si el producto sigue vigente, y si el código está repetido.

### Cómo saber cuál es la correcta

- **Miles de filas, no doce.** Si tiene doce, es una tabla de categorías o de
  tipos, no el maestro.
- **El `codigo` es el que el cliente ve en su factura**, no una llave interna
  tipo `ID_PRODUCTO` autonumérico. Si el cliente no lo reconoce, no le sirve
  para buscar.
- **El `nombre` es la descripción que el cliente reconoce del empaque.**
- **La columna de vigencia** (`ACTIVO`, `ESTADO`, `VIGENTE`) hay que mirarla
  con un `GROUP BY` antes de creerle: si casi todo está en `'N'`, esa columna
  no es la que parece, y la vista traería un catálogo vacío.
- **El código no puede venir repetido.** El portal lo usa como identidad del
  producto (`uq_producto_codigo`); si hay duplicados, la vista tiene que
  filtrarlos o agruparlos.

> Si el resultado no es claro, la ruta más corta es **preguntarle al proveedor
> del ERP** cuál es el maestro de productos y cómo se marca uno descontinuado.
> Nadie da un premio por adivinarlo, y equivocarse aquí se nota meses después
> en un informe.

## Qué se copia y qué no

De productos: **código, nombre, presentación, grupo y fecha de la última
venta**. Nada de precios, costos ni existencias — y no es solo que no se
envíen: la tabla del portal no tiene esas columnas, así que no hay forma de
que salgan por el buscador público aunque alguien se equivoque. El buscador
público sigue devolviendo solo código, nombre y presentación.

De clientes: **nada**, solo la huella de cada NIT.

## Si algo falla

### Explorando la base

**`ORA-00942: table or view does not exist` en los pasos 5 a 9** → el bloque
`DEFINE` sigue diciendo `CAMBIAME`, o el nombre va con comillas. Va en
MAYÚSCULAS y sin comillas: Oracle guarda los identificadores en mayúscula, y
SQL\*Plus pega el texto tal cual.

**El paso 1 no devuelve nada** → estás conectado a una base que no es la del
ERP, o el usuario no ve `all_users`. Confirma con
`SELECT name FROM v$database;`.

**`ORA-01489: result of string concatenation is too long` en el paso 3** →
alguna tabla tiene demasiadas columnas que casan con el filtro. Reemplaza el
`LISTAGG(...)` por `COUNT(*) AS columnas_que_casan` y mira esa tabla aparte
con el paso 5.

**`ORA-12504: el listener no ha recibido el SERVICE_NAME`** → el listener está
vivo (por eso responde), pero el servicio que le pediste no es suyo. `XE` es
una suposición: mira el real con `lsnrctl status`, o mejor conéctate en local
con `sqlplus system` a secas, que no usa el listener.

**El script «no aparece» aunque hiciste `cd`** → en CMD hay que usar
`cd /d C:\temp`. Sin `/d`, viniendo de otra unidad, el prompt se queda en
`U:\>` y SQL\*Plus busca el archivo donde no está.

**`SP2-0310: unable to open file`** → conectó bien, pero el archivo no está
donde estás parado. Comprueba con `dir explorar*`. Si el Bloc de notas lo
guardó como `explorar_catalogo.sql.txt` —pasa cuando no se elige «Todos los
archivos» en el tipo—, renómbralo:
`ren explorar_catalogo.sql.txt explorar_catalogo.sql`.
También se pueden pegar las consultas a mano en el `SQL>`, encerrándolas
entre `SPOOL C:\temp\salida.txt` y `SPOOL OFF`.

**`ORA-01031: privilegios insuficientes` al crear la vista** → no es que falte
el `SELECT`: es que llega por un rol, y Oracle los desactiva dentro de la
definición de una vista. La vista va creada **dentro de `GEMIMUS01`**, que es
el dueño de los datos.

**`ORA-01017: invalid username/password` con `system`** → en MORFEO el usuario
que sirve es **`admin_gem`**, el del ERP. Es mejor que `SYSTEM` para esto:
ve el esquema de Geminus, que es justo el que interesa, y nada de la
administración de la base.

**`lsnrctl` o `sqlplus` no se reconocen** → no están en el PATH. Búscalos en
`C:\oraclexe\app\oracle\product\11.2.0\server\bin\`.

**Encontraste varias tablas parecidas** (`ARTICULOS`, `ARTICULOS_TMP`,
`ARTICULOS_HIST`) → la buena es la que tiene más filas y la fecha de
modificación más reciente. Las `TMP` y `HIST` no.

### Sincronizando

**El script dice que sqlplus falló** → usuario, clave o cadena de conexión.
Pruébalo a mano: `sqlplus USR_LECTURA@//MORFEO.ppal.protokimica.com:1521/XE`

**Responde 403** → la clave del script no coincide con `CLAVE_SINCRONIZACION`
del `.env`. Ojo con los espacios al copiar.

**Responde 503** → falta la variable en el `.env`, o el contenedor se
reinició con `restart` en vez de `up -d` y no la releyó.

**Responde 400 diciendo que el lote llegó vacío** → la consulta no devolvió
nada. El portal lo rechaza a propósito: un error en la consulta dejaría el
buscador sin ningún producto, y es peor que quedarse con el catálogo de ayer.

**Responde 409 hablando de `CLAVE_HUELLA_NIT`** → la clave de huellas del
script no es la del `.env`. El portal lo rechaza a propósito: con claves
distintas ningún NIT coincidiría y todos los clientes saldrían «No aparece en
el ERP», sin ningún error.

**Las tildes o la Ñ llegan rotas («ÃCIDO»)** → sqlplus no está escribiendo en
UTF-8. El script fija `NLS_LANG=AMERICAN_AMERICA.AL32UTF8`; si alguien lo
quitó, ahí está.

**`ORA-28001: the password has expired`** → el perfil del usuario sigue
venciendo la contraseña. Ver «El usuario de solo lectura».

**El Programador de tareas dice que corrió bien pero nada cambia** → mira
`sincronizar_erp.log`. El script sale con código 1 si algo falló, así que la
tarea debería aparecer como fallida.
