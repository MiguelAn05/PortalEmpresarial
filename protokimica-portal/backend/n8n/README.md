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

El usuario y la contraseña salen del `.env`, no hay que adivinarlos:

```bash
grep -E "^N8N_(USER|PASSWORD)=" ~/PortalEmpresarial/protokimica-portal/.env
```

Si esas credenciales no entran, es porque la versión nueva de n8n ignora
`N8N_BASIC_AUTH_*` y usa su propio registro de usuarios. En ese caso se
restablece el dueño de la instancia — **esto borra los usuarios de n8n, no los
flujos**:

```bash
sudo docker exec protokimica_n8n n8n user-management:reset
```

Después se entra a `http://<servidor>:5679` y se crea la cuenta otra vez.

> El contenedor es `protokimica_n8n`. En esa máquina vive también un `n8n` de
> otra empresa que **no se toca nunca**.

## Importar

Por cada archivo: **Workflows › ⋯ › Import from File**.

Luego, en el nodo **Enviar correo** de cada flujo, elegir la credencial SMTP
(si no existe: **Credentials › New › SMTP**, con los datos del correo
corporativo). Los flujos se importan sin credencial a propósito — una
contraseña de correo no se guarda en el repositorio.

Ajusta también el remitente si no es `notificaciones@protokimica.com`: está en
`generar_flujos.py`, se cambia ahí y se regenera.

**Al final hay que activar cada flujo** (el interruptor de arriba a la
derecha). Un flujo importado pero inactivo no responde: n8n devuelve 404 y el
portal lo anota en el log como error.

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
