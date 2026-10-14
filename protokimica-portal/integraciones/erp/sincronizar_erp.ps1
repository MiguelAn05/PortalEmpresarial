<#
    Manda al Portal Empresarial lo que necesita del ERP:

      1. El catálogo de productos (código, nombre, presentación, grupo y
         última venta). Nada de precios, costos ni existencias.
      2. Las HUELLAS de los NIT de clientes: un HMAC-SHA256 de cada NIT,
         calculado aquí. Ni los NIT ni ningún otro dato de un cliente salen
         de este servidor.

    Corre en MORFEO (el servidor de Oracle), no en el portal. La dirección
    importa: el portal —que está expuesto a internet— nunca abre una
    conexión hacia la base del ERP, y allá no existe ninguna credencial de
    Oracle.

    Solo hace SELECT. No crea, no modifica y no borra nada en Oracle.

    Uso:
      powershell -ExecutionPolicy Bypass -File sincronizar_erp.ps1
      powershell -ExecutionPolicy Bypass -File sincronizar_erp.ps1 -SoloProductos
      powershell -ExecutionPolicy Bypass -File sincronizar_erp.ps1 -SoloClientes

    Requisitos: sqlplus (viene con Oracle) y PowerShell 3 o superior.
    Ver LEEME.md, en esta misma carpeta.
#>
param(
    [switch]$SoloProductos,
    [switch]$SoloClientes
)

# ── CONFIGURACIÓN ────────────────────────────────────────────────────────
# Por el dominio va cifrado (HTTPS). Si MORFEO no tiene salida a internet,
# la IP interna también sirve, pero la clave viaja en HTTP plano por la red.
$PortalApi    = "https://portal.protokimica.com/api"
# $PortalApi  = "http://172.20.70.47:8080/api"

# Las dos tienen que ser IGUALES a las del backend/.env.prod del portal.
$ClaveSync    = "PEGA-AQUI-CLAVE_SINCRONIZACION"
$ClaveHuella  = "PEGA-AQUI-CLAVE_HUELLA_NIT"

# El usuario de SOLO LECTURA. Nunca el del ERP, nunca SYSTEM.
$OracleUser   = "USR_LECTURA"
$OraclePass   = "LA-CLAVE-DEL-USUARIO-DE-SOLO-LECTURA"
$OracleTns    = "MORFEO.ppal.protokimica.com:1521/XE"

# Producción. NO «PRUEBAS»: tiene datos igual de creíbles y apuntar ahí no
# da ningún error (ver LEEME.md).
$Esquema      = "GEMIMUS01"

# Registro de cada corrida, al lado del script. El Programador de tareas no
# guarda lo que imprime: sin esto, un fallo de madrugada no deja rastro.
$Log          = Join-Path $PSScriptRoot "sincronizar_erp.log"

# ── PREPARACIÓN ──────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
# PowerShell 5 habla TLS 1.0 por defecto y Cloudflare lo rechaza.
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
# Que sqlplus escriba en UTF-8: con la página de códigos de Windows las
# tildes y la Ñ llegan rotas («ÃCIDO»).
$env:NLS_LANG = "AMERICAN_AMERICA.AL32UTF8"

Start-Transcript -Path $Log -Append | Out-Null
$todoBien = $true

function Columna($expresion) {
    # Sin tabuladores ni saltos de línea adentro: son los separadores.
    "REPLACE(REPLACE(REPLACE(TRIM($expresion), CHR(9), ' '), CHR(10), ' '), CHR(13), ' ')"
}

function Consultar-Oracle([string]$consulta) {
    <#
        Corre una consulta y devuelve sus filas, una por línea.

        La conexión va DENTRO de un .sql temporal y no en la línea de
        comandos: así la clave no queda a la vista en la lista de procesos.
        El archivo se borra al terminar, salga bien o mal.
    #>
    $sql    = [IO.Path]::GetTempFileName() + ".sql"
    $salida = [IO.Path]::GetTempFileName()
    try {
        $script = @"
WHENEVER SQLERROR EXIT FAILURE
WHENEVER OSERROR EXIT FAILURE
CONNECT $OracleUser/"$OraclePass"@$OracleTns
SET PAGESIZE 0
SET FEEDBACK OFF
SET HEADING OFF
SET ECHO OFF
SET VERIFY OFF
SET TERMOUT OFF
SET TAB OFF
SET LINESIZE 2000
SET TRIMSPOOL ON
SPOOL "$salida"
$consulta;
SPOOL OFF
EXIT
"@
        [IO.File]::WriteAllText($sql, $script, (New-Object Text.UTF8Encoding $false))
        $consola = & sqlplus -S -L /nolog "@$sql" 2>&1
        if ($LASTEXITCODE -ne 0 -or ($consola -match "ORA-\d+|SP2-\d+")) {
            throw "sqlplus falló (código $LASTEXITCODE). Revisa usuario, clave y cadena de conexión:`n$consola"
        }
        $filas = Get-Content -Path $salida -Encoding UTF8
        if ($filas -match "ORA-\d+") {
            throw "Oracle devolvió un error:`n$filas"
        }
        return $filas
    }
    finally {
        Remove-Item -Path $sql, $salida -ErrorAction SilentlyContinue
    }
}

function Enviar([string]$ruta, [string]$cuerpo) {
    $respuesta = Invoke-RestMethod -Uri "$PortalApi$ruta" -Method Post `
        -Headers @{ "X-Clave-Sincronizacion" = $ClaveSync } `
        -ContentType "application/json; charset=utf-8" `
        -Body ([Text.Encoding]::UTF8.GetBytes($cuerpo)) `
        -TimeoutSec 300
    return $respuesta
}

function Mensaje-De-Error($error_) {
    # El portal explica qué hacer en `detail`; eso es lo que sirve leer.
    if ($error_.ErrorDetails -and $error_.ErrorDetails.Message) {
        try { return ($error_.ErrorDetails.Message | ConvertFrom-Json).detail } catch { }
        return $error_.ErrorDetails.Message
    }
    return $error_.Exception.Message
}

Write-Host "=== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ==="

# ── 1. PRODUCTOS ─────────────────────────────────────────────────────────
if (-not $SoloClientes) {
    try {
        Write-Host "Productos: consultando Oracle..."
        $filas = Consultar-Oracle @"
SELECT $(Columna 'p.PR_PRODUCTO') || CHR(9) ||
       $(Columna 'p.PR_DESCRIPCION') || CHR(9) ||
       $(Columna 'u.UM_DESCRIPCION') || CHR(9) ||
       $(Columna 'g.GR_DESCRIPCION') || CHR(9) ||
       TO_CHAR(p.PR_FECHAULTIMAVENTA, 'YYYY-MM-DD')
FROM $Esquema.PRODUCTOS p
LEFT JOIN $Esquema.UNIDADESDEMEDIDA u ON u.UM_CODIGO = p.PR_UNIDADDEMEDIDA
LEFT JOIN $Esquema.GRUPOS g           ON g.GR_GRUPO  = p.PR_GRUPO
WHERE p.PR_ESTADO = 'A'
"@
        # Toma la columna i de la fila actual, o $null si viene vacía.
        function Opcional($i) { if ($p.Count -gt $i -and $p[$i].Trim() -ne "") { $p[$i].Trim() } else { $null } }

        $productos = New-Object System.Collections.Generic.List[object]
        foreach ($linea in $filas) {
            if ([string]::IsNullOrWhiteSpace($linea)) { continue }
            $p = $linea -split "`t"
            if ($p.Count -lt 2) { continue }
            $codigo = $p[0].Trim(); $nombre = $p[1].Trim()
            if ($codigo -eq "" -or $nombre -eq "") { continue }

            $productos.Add([ordered]@{
                codigo             = $codigo
                nombre             = $nombre
                presentacion       = Opcional 2
                grupo              = Opcional 3
                fecha_ultima_venta = Opcional 4
            })
        }
        Write-Host "Productos leídos: $($productos.Count)"

        # Un lote vacío casi siempre es una consulta que falló, no una
        # empresa sin productos. El portal lo rechaza igual.
        if ($productos.Count -eq 0) { throw "La consulta no devolvió productos. No se envía nada." }

        $cuerpo = @{ productos = $productos } | ConvertTo-Json -Depth 4 -Compress
        $r = Enviar "/catalogo/sincronizar" $cuerpo
        Write-Host "Productos listos. Nuevos: $($r.nuevos) · Actualizados: $($r.actualizados) · Descontinuados: $($r.descontinuados) · Activos: $($r.total_activos)"
    }
    catch {
        $todoBien = $false
        Write-Host "ERROR en productos: $(Mensaje-De-Error $_)"
    }
}

# ── 2. HUELLAS DE CLIENTES ───────────────────────────────────────────────
if (-not $SoloProductos) {
    try {
        Write-Host "Clientes: consultando Oracle..."
        # Solo el NIT, y solo de los terceros que son clientes activos. Ni el
        # nombre ni nada más sale de Oracle.
        $filas = Consultar-Oracle @"
SELECT TO_CHAR(NIT)
FROM $Esquema.NITS
WHERE CLASE LIKE '%C%' AND ESTADO = 'A'
"@
        $hmac = New-Object System.Security.Cryptography.HMACSHA256 (, [Text.Encoding]::UTF8.GetBytes($ClaveHuella))
        function Huella([string]$texto) {
            $bytes = $hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes($texto))
            ([BitConverter]::ToString($bytes) -replace '-', '').ToLower()
        }

        # Igual que `candidatos()` del portal: solo cifras y sin ceros a la
        # izquierda. Si se cambia aquí, se cambia allá.
        $huellas = New-Object 'System.Collections.Generic.HashSet[string]'
        foreach ($linea in $filas) {
            $nit = ($linea -replace '\D', '').TrimStart('0')
            if ($nit -ne "") { [void]$huellas.Add((Huella $nit)) }
        }
        Write-Host "Clientes leídos: $($huellas.Count)"
        if ($huellas.Count -eq 0) { throw "La consulta no devolvió clientes. No se envía nada." }

        # Prueba de que esta clave es la misma del portal (ver clientes.py).
        $control = Huella "control-portal-protokimica"

        # Armado a mano: son 167.000 cadenas hexadecimales, sin nada que
        # escapar, y ConvertTo-Json tarda minutos con eso.
        $cuerpo = '{"control":"' + $control + '","huellas":["' + (($huellas | ForEach-Object { $_ }) -join '","') + '"]}'
        $r = Enviar "/catalogo/sincronizar-clientes" $cuerpo
        Write-Host "Clientes listos. Nuevos: $($r.nuevos) · Retirados: $($r.retirados) · Total: $($r.total)"
    }
    catch {
        $todoBien = $false
        Write-Host "ERROR en clientes: $(Mensaje-De-Error $_)"
    }
    finally {
        if ($hmac) { $hmac.Dispose() }
    }
}

Stop-Transcript | Out-Null
# Código distinto de cero para que el Programador de tareas marque la
# corrida como fallida.
if ($todoBien) { exit 0 } else { exit 1 }
