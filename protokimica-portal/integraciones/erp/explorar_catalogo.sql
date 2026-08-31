-- ============================================================================
-- Encontrar la tabla de productos del ERP
--
-- Se corre UNA VEZ, a mano, en MORFEO, para averiguar de dónde va a leer la
-- vista `V_PRODUCTOS_PORTAL`. No modifica nada: son todas consultas.
--
--     sqlplus system@localhost:1521/XE @explorar_catalogo.sql
--
-- Los pasos 1 a 4 no piden nada: se corren y se lee el resultado. Del 5 en
-- adelante hay que llenar el bloque DEFINE de abajo con lo que encontraste.
--
-- Si el resultado no es claro, la ruta más corta es preguntarle al proveedor
-- del ERP cuál es el maestro de productos. Nadie da un premio por adivinarlo.
-- ============================================================================

SET LINESIZE 200
SET PAGESIZE 100
SET TRIMSPOOL ON
-- Deja el resultado en un archivo, para poder mandarlo o revisarlo con calma.
SPOOL explorar_catalogo.txt

-- Llenar DESPUÉS de correr los pasos 1 a 4.
DEFINE esquema = 'CAMBIAME'
DEFINE tabla   = 'CAMBIAME'


PROMPT
PROMPT ############ 1. Qué esquemas hay (cuál es el del ERP) ############
PROMPT

-- Se descartan los esquemas que trae Oracle de fábrica. Lo que quede suele
-- ser uno o dos: el del ERP es el que tiene cientos de tablas.
SELECT u.username AS esquema, COUNT(t.table_name) AS tablas
FROM all_users u
LEFT JOIN all_tables t ON t.owner = u.username
WHERE u.username NOT IN (
    'SYS','SYSTEM','OUTLN','DBSNMP','APPQOSSYS','ANONYMOUS','XDB','CTXSYS',
    'MDSYS','ORDSYS','ORDDATA','ORDPLUGINS','SI_INFORMTN_SCHEMA','OLAPSYS',
    'WMSYS','EXFSYS','FLOWS_FILES','APEX_PUBLIC_USER','HR','SCOTT','OE','PM',
    'IX','SH','BI','LBACSYS','OWBSYS','ORACLE_OCM','DIP','SPATIAL_CSW_ADMIN_USR',
    'SPATIAL_WFS_ADMIN_USR','MDDATA','ORDDATA'
)
GROUP BY u.username
HAVING COUNT(t.table_name) > 0
ORDER BY tablas DESC;


PROMPT
PROMPT ############ 2. Tablas cuyo NOMBRE suena a productos ############
PROMPT

-- `num_rows` sale de las estadísticas del optimizador: puede venir vacío o
-- desactualizado. Sirve para ordenar candidatas, no como conteo real — el
-- conteo de verdad se hace en el paso 6.
SELECT owner AS esquema, table_name AS tabla, num_rows AS filas_aprox
FROM all_tables
WHERE owner NOT IN ('SYS','SYSTEM','XDB','CTXSYS','MDSYS','WMSYS','OLAPSYS')
  AND (   table_name LIKE '%PRODUCT%'
       OR table_name LIKE '%ARTIC%'      -- artículos: lo más común en ERP local
       OR table_name LIKE '%ITEM%'
       OR table_name LIKE '%MATERIAL%'
       OR table_name LIKE '%REFEREN%'
       OR table_name LIKE '%MERCAN%'
       OR table_name LIKE '%INVENT%')
ORDER BY num_rows DESC NULLS LAST, owner, table_name;


PROMPT
PROMPT ############ 3. Tablas que TIENEN código y descripción ############
PROMPT

-- Más confiable que el nombre: la tabla buena tiene una columna de código y
-- otra de descripción, se llame como se llame la tabla. Muchos ERP le ponden
-- nombres que no dicen nada (T_MAE_001), y este paso las encuentra igual.
SELECT owner AS esquema, table_name AS tabla,
       LISTAGG(column_name, ', ') WITHIN GROUP (ORDER BY column_id) AS columnas
FROM all_tab_columns
WHERE owner NOT IN ('SYS','SYSTEM','XDB','CTXSYS','MDSYS','WMSYS','OLAPSYS')
  AND (   column_name LIKE '%CODIGO%'
       OR column_name LIKE 'COD%'
       OR column_name LIKE '%REFEREN%'
       OR column_name LIKE '%DESCRIP%'
       OR column_name LIKE '%NOMBRE%')
GROUP BY owner, table_name
HAVING COUNT(DISTINCT CASE WHEN column_name LIKE '%CODIGO%'
                             OR column_name LIKE 'COD%'
                             OR column_name LIKE '%REFEREN%' THEN 1 END) > 0
   AND COUNT(DISTINCT CASE WHEN column_name LIKE '%DESCRIP%'
                             OR column_name LIKE '%NOMBRE%' THEN 2 END) > 0
ORDER BY owner, table_name;


PROMPT
PROMPT ############ 4. Vistas que el ERP ya trae ############
PROMPT

-- Si el ERP ya expone una vista de productos, se usa esa y nos ahorramos
-- adivinar cómo se arma el maestro.
SELECT owner AS esquema, view_name AS vista
FROM all_views
WHERE owner NOT IN ('SYS','SYSTEM','XDB','CTXSYS','MDSYS','WMSYS','OLAPSYS')
  AND (   view_name LIKE '%PRODUCT%'
       OR view_name LIKE '%ARTIC%'
       OR view_name LIKE '%ITEM%')
ORDER BY owner, view_name;


PROMPT
PROMPT ############ 5. Las columnas de la tabla elegida ############
PROMPT ############    (llena el DEFINE de arriba primero)     ############
PROMPT

SELECT column_id AS n, column_name AS columna, data_type AS tipo,
       data_length AS largo, nullable AS acepta_nulos
FROM all_tab_columns
WHERE owner = '&esquema' AND table_name = '&tabla'
ORDER BY column_id;


PROMPT
PROMPT ############ 6. Cuántas filas tiene de verdad ############
PROMPT

-- El maestro de productos tiene miles de filas. Si esto da 12, es una tabla
-- de categorías o de tipos, no la que buscamos.
SELECT COUNT(*) AS filas_reales FROM &esquema..&tabla;


PROMPT
PROMPT ############ 7. Diez filas para ver cómo se ven los datos ############
PROMPT

-- Aquí es donde se confirma cuál columna es el código que el cliente ve en
-- la factura y cuál la descripción que reconoce del empaque.
SELECT * FROM &esquema..&tabla WHERE ROWNUM <= 10;


PROMPT
PROMPT ############ 8. Qué columna dice si el producto sigue vigente ############
PROMPT

-- El portal solo debe traer los que se venden hoy. Casi siempre hay una
-- columna ACTIVO / ESTADO / VIGENTE con 'S'/'N' o 1/0. Este paso lista las
-- candidatas; después hay que mirar qué valores tiene con un GROUP BY:
--
--     SELECT la_columna, COUNT(*) FROM esquema.tabla GROUP BY la_columna;
--
-- Ojo: si casi todo está en 'N', esa columna no es la que crees.
SELECT column_name AS columna, data_type AS tipo, data_length AS largo
FROM all_tab_columns
WHERE owner = '&esquema' AND table_name = '&tabla'
  AND (   column_name LIKE '%ACTIV%'
       OR column_name LIKE '%ESTADO%'
       OR column_name LIKE '%VIGEN%'
       OR column_name LIKE '%ANULA%'
       OR column_name LIKE '%INACTIV%'
       OR column_name LIKE '%BAJA%')
ORDER BY column_name;


PROMPT
PROMPT ############ 9. Que el código no esté repetido ############
PROMPT

-- El portal usa el código como identidad del producto (`uq_producto_codigo`).
-- Si aquí sale algo, la vista tiene que filtrar o agrupar, o el catálogo
-- entraría con duplicados. Cambiar CODIGO por el nombre real de la columna.
--
-- SELECT codigo, COUNT(*) FROM &esquema..&tabla
-- GROUP BY codigo HAVING COUNT(*) > 1;


SPOOL OFF

PROMPT
PROMPT ================================================================
PROMPT Resultado guardado en explorar_catalogo.txt
PROMPT
PROMPT Con eso ya se puede escribir la vista del LEEME.md:
PROMPT   codigo       -> el que aparece en la factura del cliente
PROMPT   nombre       -> la descripcion que el cliente reconoce del empaque
PROMPT   presentacion -> unidad de medida o presentacion, si existe
PROMPT ================================================================
