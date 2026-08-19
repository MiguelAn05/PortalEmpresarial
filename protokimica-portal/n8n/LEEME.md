# Flujos de n8n

Los flujos viven aquí, versionados, y no solo dentro de n8n. Así se sabe qué
automatizaciones existen sin entrar a la herramienta, y si alguien rompe una
se puede volver a la anterior.

## Importar uno

En n8n: **Workflows → ⋯ → Import from File** y elegir el `.json`.

Al importar hay que hacer **tres cosas a mano**, porque n8n nunca exporta
credenciales (y está bien que no lo haga):

1. **Elegir la credencial SMTP** en cada nodo de correo — la misma que ya usan
   los flujos de PQRS (`smtp.office365.com`, puerto 587, STARTTLS activo).
2. **Poner la contraseña** del usuario de servicio en el nodo *Entrar al
   portal* de los flujos que consultan datos.
3. **Activar** el flujo con el interruptor de arriba a la derecha. Mientras
   esté inactivo solo responde a las pruebas manuales del editor.

## El usuario de servicio

Los flujos que consultan el portal entran con una cuenta propia:

```
Admin › Usuarios › Nuevo
Correo: automatizaciones@protokimica.com
Rol:    agente
```

Nunca con la cuenta de una persona: el día que cambie su contraseña se caen
todas las automatizaciones, y los registros quedarían a su nombre.

## Cómo se hablan n8n y el portal

Los dos viven en la misma red de Docker, así que n8n llama al backend por su
nombre de servicio:

```
http://backend:8000
```

No por `portal.protokimica.com`: esa ruta sale a internet, pasa por Cloudflare
y volvería a entrar, con el riesgo de tropezar con las políticas de Access.

En sentido contrario, el backend llama a n8n con `N8N_WEBHOOK_URL`
(`http://n8n:5678/webhook`) más el nombre del evento. Por eso **el campo
`Path` del nodo Webhook tiene que ser exactamente el nombre del evento**, sin
barras ni prefijos. Si no coincide, el backend recibe un 404 y en el log
aparece `... is not registered`.

## Los flujos

| Archivo | Qué hace | Cuándo corre |
|---|---|---|
| `pqrs-por-vencer.json` | Avisa a cada responsable de sus PQRS a punto de vencer el plazo de ley | Diario, 7:00 a.m. |
| `indicadores-pendientes.json` | Recuerda a cada quien los indicadores que le faltan del mes | Días 2, 3 y 4, 8:00 a.m. |
| `tareas-vencidas.json` | Resumen de tareas vencidas de cada persona | Lunes, 7:00 a.m. |

Todos siguen el mismo criterio: **a cada quien solo lo suyo**. Un correo que
dice "tienes 3 pendientes" se atiende; uno con la lista de los 40 de la
empresa se archiva sin abrir, y a partir de ahí nadie lee ninguno.

El backend entrega los datos ya agrupados por destinatario y con el correo
resuelto (`/pqrs/por-vencer`, `/indicadores/pendientes-de-registro`,
`/master-planner/tareas-vencidas-por-persona`), así que los flujos solo
recorren la lista y mandan. Nada de cruzar datos dentro de n8n: esa lógica
tiene pruebas en el backend, y dentro de un flujo se rompería en silencio.

## Al escribir el HTML de un correo

El campo `html` es una expresión, así que empieza con `=`. **Dentro no se
vuelve a escribir `=`**: un `href="={{ $json.link }}"` produce
`href="=https://..."` y el enlace queda roto. Lo correcto es
`href="{{ $json.link }}"`.
