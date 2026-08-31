# Catálogo de productos desde el ERP

El portal **no se conecta a Oracle**. Un script que corre en MORFEO lee el
catálogo y se lo manda al portal por HTTP.

La dirección es lo que importa: el portal está expuesto a internet, así que
si algún día lo comprometen, ahí no hay ninguna credencial ni ruta hacia la
base del ERP. El tráfico va de la red interna hacia afuera.

Además, así deja de importar que Oracle sea 11.2: no hace falta ningún driver
ni el Instant Client dentro del contenedor.

## Lo que hay que hacer una sola vez

### 1. En Oracle (MORFEO), como SYSTEM

**La vista.** El portal nunca lee una tabla del ERP directamente: si el
proveedor renombra una columna en una actualización, se ajusta la vista y
nada más se entera.

```sql
CREATE OR REPLACE VIEW V_PRODUCTOS_PORTAL AS
SELECT
    p.codigo_producto   AS codigo,
    p.descripcion       AS nombre,
    p.unidad_medida     AS presentacion
FROM esquema_del_erp.productos p
WHERE p.activo = 'S';
```

> Los nombres de arriba son de ejemplo. Hay que reemplazarlos por los reales
> — ver "Cómo encontrar la tabla" más abajo.

**El usuario de solo lectura.** No se usa el usuario del ERP ni `SYSTEM`.
Este solo puede hacer `SELECT`, y solo sobre esa vista: aunque su clave se
filtrara, eso es todo lo que alcanzaría.

```sql
CREATE USER PORTAL_LECTURA IDENTIFIED BY "una-clave-larga-y-aleatoria";
GRANT CREATE SESSION TO PORTAL_LECTURA;
GRANT SELECT ON V_PRODUCTOS_PORTAL TO PORTAL_LECTURA;
```

Nada de `GRANT SELECT ANY TABLE` ni de roles como `DBA` o `RESOURCE`.

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

Con `sqlplus system@XE`:

```sql
SELECT owner, table_name
FROM all_tables
WHERE table_name LIKE '%PRODUCT%'
   OR table_name LIKE '%ARTIC%'
   OR table_name LIKE '%ITEM%'
ORDER BY owner, table_name;
```

Y para ver las columnas de la que parezca correcta:

```sql
SELECT column_name, data_type
FROM all_tab_columns
WHERE owner = 'ESQUEMA' AND table_name = 'LA_TABLA'
ORDER BY column_id;
```

## Qué se copia y qué no

Solo **código, nombre y presentación**. Nada de precios, costos ni
existencias — y no es solo que no se envíen: la tabla del portal no tiene
esas columnas, así que no hay forma de que salgan por el buscador público
aunque alguien se equivoque.

## Si algo falla

**El script dice que sqlplus falló** → usuario, clave o cadena de conexión.
Pruébalo a mano: `sqlplus PORTAL_LECTURA/clave@localhost:1521/XE`

**Responde 403** → la clave del script no coincide con `CLAVE_SINCRONIZACION`
del `.env`. Ojo con los espacios al copiar.

**Responde 503** → falta la variable en el `.env`, o el contenedor se
reinició con `restart` en vez de `up -d` y no la releyó.

**Responde 400 diciendo que el lote llegó vacío** → la consulta no devolvió
nada. El portal lo rechaza a propósito: un error en la consulta dejaría el
buscador sin ningún producto, y es peor que quedarse con el catálogo de ayer.
