<#
    Manda el catálogo de productos del ERP al Portal Empresarial.

    Corre en MORFEO (el servidor de Oracle), no en el portal. La dirección
    importa: así el portal —que está expuesto a internet— nunca abre una
    conexión hacia la base del ERP, y no existe ninguna credencial de Oracle
    del lado de afuera.

    Se programa con el Programador de tareas de Windows, una vez al día.

    Requisitos en este servidor:
      - sqlplus disponible en el PATH (viene con Oracle)
      - PowerShell 3 o superior

    Antes de usarlo hay que ajustar la sección CONFIGURACIÓN y crear en
    Oracle el usuario de solo lectura y la vista (ver LEEME.md).
#>

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────
$PortalUrl   = "http://172.20.70.47:8080/api/catalogo/sincronizar"
$ClaveSync   = "PEGA-AQUI-LA-MISMA-CLAVE-DEL-ENV-DEL-PORTAL"

$OracleUser  = "PORTAL_LECTURA"
$OraclePass  = "LA-CLAVE-DEL-USUARIO-DE-SOLO-LECTURA"
$OracleTns   = "localhost:1521/XE"

# La vista que se creó para el portal. Nunca una tabla del ERP directamente:
# si el proveedor cambia el esquema en una actualización, se ajusta la vista
# y este script no se entera.
$Vista       = "V_PRODUCTOS_PORTAL"

# ── CONSULTA ─────────────────────────────────────────────────────────────
# Se pide el resultado separado por barras verticales, sin encabezados ni
# adornos, para poder partirlo sin ambigüedad.
$consulta = @"
SET PAGESIZE 0
SET FEEDBACK OFF
SET HEADING OFF
SET LINESIZE 500
SET TRIMSPOOL ON
SET COLSEP '|'
SELECT codigo || '|' || nombre || '|' || NVL(presentacion, ' ')
FROM $Vista;
EXIT;
"@

Write-Host "Consultando Oracle..."
$salida = $consulta | sqlplus -S "$OracleUser/$OraclePass@$OracleTns"

if ($LASTEXITCODE -ne 0) {
    Write-Error "sqlplus falló. Revisa usuario, clave y cadena de conexión."
    exit 1
}

# Un error de Oracle sale por la salida normal, no como código de error.
if ($salida -match "ORA-\d+") {
    Write-Error "Oracle devolvió un error:`n$salida"
    exit 1
}

# ── ARMAR EL LOTE ────────────────────────────────────────────────────────
$productos = @()
foreach ($linea in $salida) {
    $texto = $linea.Trim()
    if ([string]::IsNullOrWhiteSpace($texto)) { continue }

    $partes = $texto -split '\|'
    if ($partes.Count -lt 2) { continue }

    $codigo = $partes[0].Trim()
    $nombre = $partes[1].Trim()
    $present = if ($partes.Count -ge 3) { $partes[2].Trim() } else { "" }

    if ($codigo -eq "" -or $nombre -eq "") { continue }

    $productos += @{
        codigo       = $codigo
        nombre       = $nombre
        presentacion = if ($present -eq "") { $null } else { $present }
    }
}

Write-Host "Productos leídos: $($productos.Count)"

# Un lote vacío casi siempre significa que la consulta falló, no que la
# empresa se quedó sin productos. El portal lo rechaza igual, pero mejor ni
# mandarlo.
if ($productos.Count -eq 0) {
    Write-Error "La consulta no devolvió productos. No se envía nada."
    exit 1
}

# ── ENVIAR AL PORTAL ─────────────────────────────────────────────────────
$cuerpo = @{ productos = $productos } | ConvertTo-Json -Depth 4 -Compress

try {
    $respuesta = Invoke-RestMethod -Uri $PortalUrl -Method Post `
        -Headers @{ "X-Clave-Sincronizacion" = $ClaveSync } `
        -ContentType "application/json; charset=utf-8" `
        -Body ([System.Text.Encoding]::UTF8.GetBytes($cuerpo)) `
        -TimeoutSec 120

    Write-Host "Listo."
    Write-Host "  Recibidos:      $($respuesta.recibidos)"
    Write-Host "  Nuevos:         $($respuesta.nuevos)"
    Write-Host "  Actualizados:   $($respuesta.actualizados)"
    Write-Host "  Descontinuados: $($respuesta.descontinuados)"
    Write-Host "  Activos ahora:  $($respuesta.total_activos)"
}
catch {
    Write-Error "No se pudo enviar al portal: $_"
    exit 1
}
