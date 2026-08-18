"""
Genera los flujos de n8n que mandan los correos de PQRS.

Se generan con un script y no se escriben a mano porque los cuatro correos
comparten la misma plantilla: si el encabezado o el pie cambian, se cambian
aquí una vez y se regeneran los cuatro. Un JSON de n8n editado a mano en
cuatro sitios termina con cuatro correos que no se parecen.

    python n8n/generar_flujos.py

Los archivos resultantes se importan en n8n (Workflows › Import from File).
El payload de cada webhook lo arma `backend/app/modules/pqrs/notificaciones.py`:
si allá se agrega un campo, aquí se puede usar como {{ $json.body.campo }}.
"""
import json
import os

# Ajusta esto a la cuenta desde la que salen los correos.
REMITENTE = "notificaciones@protokimica.com"

AZUL = "#0D2B5E"
GRIS = "#55607A"
BORDE = "#E2E8F2"


def plantilla(titulo: str, cuerpo: str, boton: tuple[str, str] | None = None) -> str:
    """
    El correo entero. Tablas y estilos en línea a propósito: Outlook ignora
    las hojas de estilo y flexbox, y este correo se lee sobre todo en Outlook.
    """
    llamado = ""
    if boton:
        texto, enlace = boton
        llamado = f"""
        <tr><td style="padding:8px 24px 24px 24px">
          <a href="{enlace}" style="display:inline-block;background:{AZUL};color:#ffffff;
             text-decoration:none;padding:12px 22px;border-radius:8px;
             font-weight:600;font-size:14px">{texto}</a>
        </td></tr>"""

    return f"""<!doctype html>
<html><body style="margin:0;padding:24px;background:#F3F6FB;
  font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#121A2B">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0"
  style="max-width:560px;margin:0 auto;background:#ffffff;border:1px solid {BORDE};
  border-radius:12px;overflow:hidden">
  <tr><td style="padding:20px 24px;border-bottom:1px solid {BORDE}">
    <span style="font-size:15px;font-weight:600;color:{AZUL}">Protokimica</span>
    <span style="font-size:13px;color:{GRIS}"> · Portal de gestión</span>
  </td></tr>
  <tr><td style="padding:24px 24px 8px 24px">
    <h1 style="margin:0 0 12px 0;font-size:19px;font-weight:600">{titulo}</h1>
    <div style="font-size:14px;line-height:1.55;color:{GRIS}">{cuerpo}</div>
  </td></tr>{llamado}
  <tr><td style="padding:16px 24px;border-top:1px solid {BORDE};
    font-size:12px;color:#8A93A9">
    Este mensaje es automático, no hace falta responderlo.
  </td></tr>
</table></body></html>"""


def dato(etiqueta: str, valor: str) -> str:
    return (f'<p style="margin:4px 0"><span style="color:#8A93A9">{etiqueta}:</span> '
            f'<strong style="color:#121A2B">{valor}</strong></p>')


def flujo(nombre: str, path: str, para: str, asunto: str, html: str) -> dict:
    """Un flujo = webhook que escucha + correo que sale."""
    return {
        "name": nombre,
        "nodes": [
            {
                "parameters": {
                    "httpMethod": "POST",
                    "path": path,
                    # Responder al recibir: el portal no espera el correo, y si
                    # esperara, radicar una PQRS tardaría lo que tarde el SMTP.
                    "responseMode": "onReceived",
                    "options": {},
                },
                "id": f"webhook-{path}",
                "name": "Entra la notificación",
                "type": "n8n-nodes-base.webhook",
                "typeVersion": 2,
                "position": [0, 0],
                "webhookId": path,
            },
            {
                "parameters": {
                    "fromEmail": REMITENTE,
                    "toEmail": para,
                    "subject": asunto,
                    "emailFormat": "html",
                    "html": html,
                    "options": {},
                },
                "id": f"correo-{path}",
                "name": "Enviar correo",
                "type": "n8n-nodes-base.emailSend",
                "typeVersion": 2.1,
                "position": [260, 0],
            },
        ],
        "connections": {
            "Entra la notificación": {
                "main": [[{"node": "Enviar correo", "type": "main", "index": 0}]]
            }
        },
        "settings": {"executionOrder": "v1"},
        "active": False,
    }


B = "$json.body"   # el cuerpo que manda el portal

FLUJOS = [
    flujo(
        nombre="PQRS · confirmación al cliente",
        path="pqrs-creada-cliente",
        para=f"={{{{ {B}.cliente_email }}}}",
        asunto=f"=Recibimos tu solicitud · {{{{ {B}.codigo_seguimiento }}}}",
        html="=" + plantilla(
            titulo=f"Hola {{{{ {B}.cliente_nombre }}}}, ya tenemos tu solicitud",
            cuerpo=(
                f"Registramos tu {{{{ {B}.tipo }}}}. Guarda este código: es lo único "
                "que necesitas para consultar en qué va."
                f'<p style="margin:16px 0;padding:14px;background:#EFF3F9;border-radius:8px;'
                f'text-align:center;font-size:22px;font-weight:600;letter-spacing:2px;'
                f'color:{AZUL}">{{{{ {B}.codigo_seguimiento }}}}</p>'
                "Te responderemos dentro del plazo de ley."
            ),
            boton=("Consultar mi solicitud", f"={{{{ {B}.link_seguimiento }}}}"),
        ),
    ),
    flujo(
        nombre="PQRS · aviso a Servicio al Cliente",
        path="pqrs-nueva-servicio-cliente",
        para=f"={{{{ {B}.destinatarios.join(', ') }}}}",
        asunto=f"=PQRS nueva · {{{{ {B}.tipo }}}} · {{{{ {B}.codigo_seguimiento }}}}",
        html="=" + plantilla(
            titulo="Entró una PQRS nueva",
            cuerpo=(
                dato("Código", f"{{{{ {B}.codigo_seguimiento }}}}")
                + dato("Tipo", f"{{{{ {B}.tipo }}}}")
                + dato("Cliente", f"{{{{ {B}.cliente_nombre }}}}")
                + dato("Canal", f"{{{{ {B}.canal_atencion || 'No indicado' }}}}")
                + dato("Área asignada", f"{{{{ {B}.area_responsable || 'Sin asignar' }}}}")
                + f'<p style="margin:14px 0 0 0;padding:12px;background:#EFF3F9;'
                  f'border-radius:8px">{{{{ {B}.descripcion }}}}</p>'
            ),
            boton=("Abrir en el portal", f"={{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        nombre="PQRS · aviso al área responsable",
        path="pqrs-notificacion-area",
        para=f"={{{{ {B}.destinatarios.join(', ') }}}}",
        asunto=f"=PQRS para {{{{ {B}.area }}}} · {{{{ {B}.codigo_seguimiento }}}}",
        html="=" + plantilla(
            titulo=(f"{{{{ {B}.motivo === 'reasignacion' "
                    f"? 'Les reasignaron una PQRS' : 'Les asignaron una PQRS' }}}}"),
            cuerpo=(
                dato("Código", f"{{{{ {B}.codigo_seguimiento }}}}")
                + dato("Tipo", f"{{{{ {B}.tipo }}}}")
                + dato("Cliente", f"{{{{ {B}.cliente_nombre }}}}")
                + f"{{{{ {B}.radicado_calidad ? "
                  f"'{dato('Radicado de Calidad', '@@RC@@')}'.replace('@@RC@@', {B}.radicado_calidad) "
                  f": '' }}}}"
                + f'<p style="margin:14px 0 0 0;padding:12px;background:#EFF3F9;'
                  f'border-radius:8px">{{{{ {B}.descripcion }}}}</p>'
            ),
            boton=("Abrir en el portal", f"={{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        nombre="PQRS · cierre y encuesta al cliente",
        path="pqrs-cerrada",
        para=f"={{{{ {B}.cliente_email }}}}",
        asunto=f"=Cerramos tu solicitud · {{{{ {B}.codigo_seguimiento }}}}",
        html="=" + plantilla(
            titulo=f"Hola {{{{ {B}.cliente_nombre }}}}, cerramos tu solicitud",
            cuerpo=(
                f"Tu {{{{ {B}.tipo }}}} con código "
                f"<strong>{{{{ {B}.codigo_seguimiento }}}}</strong> quedó cerrada. "
                "Nos ayudarías mucho contándonos cómo te fue: es menos de un minuto."
            ),
            boton=("Calificar la atención", f"={{{{ {B}.link_encuesta }}}}"),
        ),
    ),
]


if __name__ == "__main__":
    destino = os.path.dirname(os.path.abspath(__file__))
    for f in FLUJOS:
        ruta = os.path.join(destino, f"{f['nodes'][0]['parameters']['path']}.json")
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(f, fh, ensure_ascii=False, indent=2)
        print("escrito:", os.path.basename(ruta))
