# Catálogo de productos desde el ERP

El portal **no se conecta a Oracle**. Un script que corre en MORFEO lee el
catálogo y se lo manda al portal por HTTP.

La dirección es lo que importa: el portal está expuesto a internet, así que
si algún día lo comprometen, ahí no hay ninguna credencial ni ruta hacia la
base del ERP. El tráfico va de la red interna hacia afuera.

Además, así deja de importar que Oracle sea 11.2: no hace falta ningún driver
ni el Instant Client dentro del contenedor.

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

#### La vista

El portal nunca lee la tabla del ERP directamente: si el proveedor renombra
una columna en una actualización, se ajusta la vista y nada más se entera.
Geminus ya expone `V_PRODUCTOS` con 250 columnas —incluidos precios, costos,
márgenes y diez listas de precios—, así que **encima de esa se crea una de
tres columnas**, y el `GRANT` va solo sobre la nuestra:

Antes de crearla, **comprobar que el nombre está libre**. Es el único paso de
todo esto que podría hacer daño: un `CREATE OR REPLACE` sobre un objeto que ya
existe lo pisa.

```sql
SELECT owner, object_name, object_type
FROM all_objects WHERE object_name LIKE 'V_PRODUCTOS%';
```

Y se crea con `CREATE VIEW`, no con `CREATE OR REPLACE`: si el nombre estuviera
ocupado, es mejor que reviente a que lo reemplace.

```sql
CREATE VIEW GEMIMUS01.V_PRODUCTOS_PORTAL AS
SELECT p.PROD_CODIGO                   AS codigo,
       p.PROD_DESCRIPCION              AS nombre,
       p.PROD_DESCRIPCIONUNIDADMEDIDA  AS presentacion
FROM GEMIMUS01.V_PRODUCTOS p
WHERE p.PROD_ESTADO = 'A'
  AND p.PROD_ESPARAVENTA = 'S';
```

Debe devolver **7.802** de los 7.841 que tiene `V_PRODUCTOS`.

Equivalencias ya verificadas, con los tamaños de cada lado:

| Geminus | Portal | |
|---|---|---|
| `PROD_CODIGO` VARCHAR2(30) | `cat_productos.codigo` String(60) | cabe |
| `PROD_DESCRIPCION` VARCHAR2(250) | `cat_productos.nombre` String(300) | cabe |
| `PROD_DESCRIPCIONUNIDADMEDIDA` VARCHAR2(30) | `presentacion` String(60) | cabe |

Los códigos vienen únicos (7.774 de 7.774), así que
`uq_producto_codigo` no va a estorbar.

#### De dónde salió el filtro

Así se reparten los 7.841 productos de producción:

| `ESTADO` | `ESPARAVENTA` | `EMPAQUE` | `DOTACION` | `SERVICIO` | Cuántos |
|:-:|:-:|:-:|:-:|:-:|--:|
| A | S | N | N | N | 7790 |
| I | S | N | N | N | 37 |
| A | S | N | N | S | 7 |
| A | S | S | N | N | 5 |
| A | N | N | N | S | 1 |
| I | S | N | N | S | 1 |

`PROD_ESTADO` es `A`/`I` y `PROD_ESPARAVENTA` es `S`/`N`. Con esas dos basta.

**Los empaques y los servicios NO se excluyen**, aunque se podría: son doce
productos, un cliente sí puede reclamar por un envase o por un servicio, y
filtrar de más es cerrarle la puerta a alguien por ahorrar doce filas. Para
lo que quede fuera está el «no encuentro mi producto» del formulario.

#### Quién crea la vista

Va **dentro de `GEMIMUS01`**, el dueño de los datos. Crearla desde otro
usuario falla con `ORA-01031` aunque ese usuario sí pueda consultar la tabla:
Oracle desactiva los privilegios que llegan por un rol dentro de la
definición de una vista, y ahí el `SELECT` tiene que estar concedido directo.

`ADMIN_GEM` tiene el rol `DBA`, así que alcanza para todo esto. Pero **avísale
al proveedor de Geminus antes**, no por trámite: una actualización suya puede
recrear o borrar `V_PRODUCTOS`, y si nadie sabe que hay una vista colgando de
ahí, el catálogo del portal se cae en silencio y nadie sabe por qué.

**El usuario de solo lectura.** No se usa el usuario del ERP ni `SYSTEM`.
Este solo puede hacer `SELECT`, y solo sobre esa vista: aunque su clave se
filtrara, eso es todo lo que alcanzaría.

```sql
CREATE USER PORTAL_LECTURA IDENTIFIED BY "una-clave-larga-y-aleatoria";
GRANT CREATE SESSION TO PORTAL_LECTURA;
GRANT SELECT ON GEMIMUS01.V_PRODUCTOS_PORTAL TO PORTAL_LECTURA;
```

Nada de `GRANT SELECT ANY TABLE` ni de roles como `DBA` o `RESOURCE`. Y el
`GRANT` va sobre `V_PRODUCTOS_PORTAL`, **nunca sobre `V_PRODUCTOS`**: esa
última trae `PROD_PRECIOBASESINIMPUESTOS`, `PROD_COSTOULTCOMPRASINIMPUESTO`,
`PROD_PORCRENTABILIDADMINIMA` y diez listas de precios completas.

### 2. En el portal

Generar una clave larga y ponerla en `backend/.env.prod`:

```
CLAVE_SINCRONIZACION=<pega aquí una clave larga y aleatoria>
```

Y recrear el contenedor (nunca `restart`: no relee el `.env`):

```bash
sudo docker compose -f docker-compose.prod.yml up -d backend
```

### 3. En MORFEO

Copiar `sincronizar_productos.ps1`, ajustar el bloque CONFIGURACIÓN (la misma
clave del `.env`, el usuario de Oracle y el nombre de la vista) y probarlo a
mano:

```powershell
powershell -ExecutionPolicy Bypass -File C:\ruta\sincronizar_productos.ps1
```

Debe imprimir cuántos productos leyó y cuántos quedaron activos.

Cuando funcione, programarlo en el **Programador de tareas de Windows**, una
vez al día de madrugada:

```
Programa:   powershell.exe
Argumentos: -ExecutionPolicy Bypass -File C:\ruta\sincronizar_productos.ps1
```

## Cómo encontrar la tabla de productos

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

### Probar la vista antes de dejarla

Con la vista ya creada, vale la pena verla como la va a ver el portal:

```sql
SELECT COUNT(*) FROM V_PRODUCTOS_PORTAL;
SELECT * FROM V_PRODUCTOS_PORTAL WHERE ROWNUM <= 10;
```

Y con el usuario de solo lectura, para confirmar que le alcanzan los permisos
y que **no** alcanza nada más:

```
sqlplus PORTAL_LECTURA/clave@localhost:1521/XE
SQL> SELECT COUNT(*) FROM SYSTEM.V_PRODUCTOS_PORTAL;
```

## Qué se copia y qué no

Solo **código, nombre y presentación**. Nada de precios, costos ni
existencias — y no es solo que no se envíen: la tabla del portal no tiene
esas columnas, así que no hay forma de que salgan por el buscador público
aunque alguien se equivoque.

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
Pruébalo a mano: `sqlplus PORTAL_LECTURA/clave@localhost:1521/XE`

**Responde 403** → la clave del script no coincide con `CLAVE_SINCRONIZACION`
del `.env`. Ojo con los espacios al copiar.

**Responde 503** → falta la variable en el `.env`, o el contenedor se
reinició con `restart` en vez de `up -d` y no la releyó.

**Responde 400 diciendo que el lote llegó vacío** → la consulta no devolvió
nada. El portal lo rechaza a propósito: un error en la consulta dejaría el
buscador sin ningún producto, y es peor que quedarse con el catálogo de ayer.
