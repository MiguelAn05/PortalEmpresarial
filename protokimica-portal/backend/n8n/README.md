# Flujos de n8n — los correos del portal

El portal **no manda correos**: cuando pasa algo (se radica una PQRS, se
cierra, se asigna a un área) le pega a un webhook de n8n y sigue con lo suyo.
n8n es el que arma y envía el correo. Por eso, si n8n no está configurado o el
flujo no existe, el portal funciona igual pero nadie recibe nada.

Aquí están los cuatro flujos listos para importar.

| Archivo | Cuándo se dispara | A quién le llega |
|---|---|---|
| `pqrs-creada-cliente.json` | El cliente radica una PQRS | Al cliente, con su código |
| `pqrs-nueva-servicio-cliente.json` | Cualquier PQRS nueva | A Servicio al Cliente |
| `pqrs-notificacion-area.json` | Se asigna o reasigna un área | A los usuarios de esa área |
| `pqrs-cerrada.json` | Se cierra la PQRS | Al cliente, con la encuesta |

El nombre del archivo es el **path del webhook**, y tiene que coincidir con el
evento que dispara el portal. `tests/test_flujos_n8n.py` lo verifica: si
alguien lo cambia de un lado y no del otro, la prueba revienta en vez de
dejar un correo que no llega.

## Entrar a n8n

Corre en el puerto **5679** del servidor (dentro del contenedor usa el 5678):
`http://<servidor>:5679`.

> ⚠️ **Nuestro contenedor es `protokimica_n8n`.** En esa máquina vive también
> un `n8n` de otra empresa. Confirma el nombre antes de cada comando:
> `sudo docker ps --format '{{.Names}}\t{{.Ports}}' | grep -i n8n`
> Un reset en el contenedor equivocado le borra los usuarios a la otra empresa.

### La contraseña no está en el `.env`

`docker-compose.prod.yml` todavía pasa `N8N_BASIC_AUTH_USER/PASSWORD`, pero
**n8n 1.x ignora esas variables**: quitaron la autenticación básica y ahora
cada instancia tiene su propio registro de usuarios (email + contraseña, la
que se creó en el navegador la primera vez). Buscar la clave en el `.env` es
perder el tiempo — esas dos líneas quedaron sin efecto.

### Recuperar el acceso

El reset borra **los usuarios**, no los flujos ni las credenciales:

```bash
# 1. Respaldo del volumen, por si acaso (mira antes cómo se llama)
sudo docker volume ls | grep n8n
sudo docker run --rm -v <volumen_n8n>:/datos -v "$PWD":/respaldo alpine \
  tar czf /respaldo/n8n-$(date +%F).tar.gz -C /datos .

# 2. Restablecer el dueño de la instancia
sudo docker exec -it protokimica_n8n n8n user-management:reset
```

Después entra a `http://<servidor>:5679` y crea la cuenta otra vez.

**Hazlo de una vez, no lo dejes para después:** mientras no haya dueño, quien
abra ese puerto se queda con la instancia. Y anota la contraseña donde la
puedas volver a encontrar.

Si `user-management:reset` no existe en esa versión, mira qué comandos hay con
`sudo docker exec protokimica_n8n n8n --help`.

### Importar sin entrar a la interfaz

También se puede dejar todo listo por línea de comandos:

```bash
cd ~/PortalEmpresarial/protokimica-portal
for f in backend/n8n/pqrs-*.json; do
  sudo docker cp "$f" protokimica_n8n:/tmp/
  sudo docker exec protokimica_n8n n8n import:workflow --input="/tmp/$(basename "$f")"
done
```

Quedan importados pero **inactivos y sin credencial de correo**: eso sí hay
que hacerlo desde la interfaz.

## Importar

Por cada archivo: **Workflows › ⋯ › Import from File**.

Luego, en el nodo **Enviar correo** de cada flujo, elegir la credencial SMTP
(si no existe: **Credentials › New › SMTP**, con los datos del correo
corporativo). Los flujos se importan sin credencial a propósito — una
contraseña de correo no se guarda en el repositorio.

### La credencial SMTP con Microsoft 365

| Campo | Valor |
|---|---|
| Host | `smtp.office365.com` |
| Port | `587` |
| SSL/TLS | **desactivado** |
| Ignore SSL Issues | desactivado |
| User | la dirección completa del buzón |

El toggle *SSL/TLS* significa «SSL directo», que es el puerto 465 — y
**Exchange Online no lo soporta**. En el 587 la conexión arranca en claro y
sube a TLS con STARTTLS; con el toggle encendido n8n lo intenta al revés y
Microsoft responde:

    451 5.7.3 STARTTLS is required to send mail

### «Con mi cuenta sí manda y con la otra no»

No es la credencial: Microsoft trae el **SMTP autenticado apagado por buzón**
en los tenants nuevos, y las cuentas de administrador suelen tenerlo
habilitado de antes.

Se prende en **Microsoft 365 Admin › Usuarios › la cuenta › Correo ›
Administrar aplicaciones de correo electrónico › SMTP autenticado**, o con
`Set-CasMailbox -Identity <buzón> -SmtpClientAuthenticationDisabled $false`.

Además, esa cuenta necesita **licencia de Exchange Online**; si tiene MFA hace
falta una *contraseña de aplicación*; y si el tenant tiene **Security
Defaults** activo, la autenticación básica está bloqueada para todos y no hay
excepción por buzón (ahí toca el camino de Graph, abajo).

Para saber cuál de los tres es, sin pasar por n8n:

```bash
sudo docker run --rm alpine sh -c "apk add --no-cache swaks >/dev/null 2>&1 && \
swaks --to alguien@protokimica.com --from <buzón> \
      --server smtp.office365.com:587 --tls \
      --auth LOGIN --auth-user <buzón> --auth-password 'CLAVE'"
```

- Llega el correo → la cuenta está bien; revisa la credencial de n8n.
- `535 5.7.139 ... not enabled for the tenant` → falta prender SMTP autenticado.
- `535 5.7.3 Authentication unsuccessful` → contraseña o MFA.

### Si Microsoft cierra el SMTP básico

Está en camino: Microsoft viene apagando la autenticación básica. El portal ya
tiene una app de Entra ID registrada (`MS_TENANT_ID`, `MS_CLIENT_ID`,
`MS_CLIENT_SECRET`, hoy con permiso `Calendars.ReadWrite` para el calendario
de Master Planner). Agregándole el permiso de aplicación **`Mail.Send`** con
consentimiento del administrador, los correos pueden salir por Microsoft Graph
—sin contraseñas de buzón y sin depender del SMTP— cambiando en cada flujo el
nodo *Enviar correo* por un *HTTP Request* a
`https://graph.microsoft.com/v1.0/users/<buzón>/sendMail`.

Ajusta también el remitente si no es `notificaciones@protokimica.com`: está en
`generar_flujos.py`, se cambia ahí y se regenera.

**Al final hay que activar cada flujo** (el interruptor de arriba a la
derecha). Un flujo importado pero inactivo no responde: n8n devuelve 404 y el
portal lo anota en el log como error.

### Van cuatro flujos separados, no uno con cuatro ramas

Se puede meter todo en un solo workflow con cuatro nodos Webhook, pero no
conviene:

- Un correo roto no tumba los otros tres.
- Se activan y silencian por separado (callar los avisos internos sin tocar
  el que recibe el cliente).
- El historial de ejecuciones se lee: «confirmación al cliente, 40 veces» en
  vez de 160 ejecuciones mezcladas que hay que abrir una por una.

La plantilla común ya está compartida en `generar_flujos.py`, del lado del
repositorio, así que juntarlos en n8n no ahorraría nada.

### Cuidado con la URL de prueba

n8n muestra dos URLs por webhook y solo una sirve:

| | URL | Cuándo responde |
|---|---|---|
| Prueba | `/webhook-test/<evento>` | solo con «Listen for test event» abierto |
| **Producción** | `/webhook/<evento>` | siempre, **pero solo si el flujo está activo** |

El portal llama a la de producción. Probar con «Execute workflow» y olvidar
activarlo es la forma más común de que todo parezca bien y no llegue ningún
correo.

## Probar sin radicar nada

```bash
curl -X POST http://localhost:5679/webhook/pqrs-creada-cliente \
  -H "Content-Type: application/json" \
  -d '{"cliente_nombre":"Prueba","cliente_email":"tu@correo.com",
       "codigo_seguimiento":"PK-2026-9999","tipo":"queja",
       "link_seguimiento":"https://portal/seguimiento"}'
```

Si el correo llega, el flujo está bien y lo que falte está del lado del
portal. Para ver ese lado:

```bash
sudo docker logs protokimica_backend --tail 100 | grep -i n8n
```

- `n8n webhook '...' disparado OK` → el portal cumplió su parte.
- `n8n respondió error ... (HTTP 404)` → el flujo no existe o está inactivo.
- `N8N_WEBHOOK_URL está vacío` → falta configurarlo; con `up -d`, no `restart`.

## Cambiar los correos

No edites los JSON a mano: los cuatro comparten la plantilla (encabezado, pie,
botón). Se cambia en `generar_flujos.py` y se regenera todo:

```bash
python backend/n8n/generar_flujos.py
```

Los campos disponibles en cada correo son los que arma
`backend/app/modules/pqrs/notificaciones.py`. Se usan como
`{{ $json.body.nombre_del_campo }}`.

## Lo que todavía no tiene flujo

- `mp-tarea-asignada` — avisar a quien le asignan una tarea.
- Alertas de indicadores en rojo.
- El disparo mensual de `POST /indicadores/calcular-periodo`.
