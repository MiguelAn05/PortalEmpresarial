# Plantilla de la configuración local de sincronizar_erp.ps1.
#
# Cópiala como `sincronizar_erp.config.ps1` (al lado del script) y llénala.
# Esa copia NO va a git: así las claves nunca terminan en el repositorio.
# Lo que no pongas aquí se queda con lo del bloque CONFIGURACIÓN del script.

# Para probar contra el Docker de un equipo de desarrollo:
#   $PortalApi = "http://localhost:8000"      (sin /api: eso lo quita nginx)
# En MORFEO, contra el portal de verdad:
#   $PortalApi = "https://portal.protokimica.com/api"
$PortalApi   = "http://localhost:8000"

# Las mismas del backend/.env (o .env.prod) del portal al que se manda.
$ClaveSync   = ""
$ClaveHuella = ""

$OracleUser  = "USR_LECTURA"
# Vacía: el script la pide al correr y no queda escrita en ningún lado.
# Solo para la tarea programada hace falta escribirla.
$OraclePass  = ""
$OracleTns   = "MORFEO.ppal.protokimica.com:1521/XE"

# Si sqlplus no está en el PATH (Instant Client descomprimido a mano):
# $SqlPlus   = "C:\oracle\instantclient_19_27\sqlplus.exe"
