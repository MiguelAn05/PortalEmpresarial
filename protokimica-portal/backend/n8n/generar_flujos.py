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

# De qué buzón sale cada correo.
#
# Son DOS y no uno porque no todos los correos vienen del mismo sitio: los que
# ve el cliente —y el reparto de PQRS a las áreas— salen del buzón de Servicio
# al Cliente, que es quien responde si alguien contesta; los avisos internos
# del portal salen del de recepción.
#
# **El remitente tiene que ser el mismo buzón de la credencial SMTP del nodo.**
# Exchange rechaza con `554 5.2.252 SendAsDenied` cuando la cuenta autenticada
# no coincide con el `From`, y el correo no sale: no es que llegue a spam, es
# que nunca se manda. Si aquí se cambia una dirección, hay que cambiar la
# credencial del nodo en n8n con ella.
REMITENTE_SERVICIO_CLIENTE = "sacliente@protokimica.com"
REMITENTE_INTERNO = "recepcion@protokimica.com"

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
        # Un '=' al principio del enlace ya rompió estos cuatro correos.
        #
        # El campo HTML entero es una expresión de n8n —empieza por '='—, y
        # dentro de una expresión solo se evalúan las {{ }}. Un '=' escrito
        # después de href=" se queda como texto, así que el botón apunta a
        # "=https://portal..." : una ruta relativa que no lleva a ningún lado.
        # El correo se ve perfecto y el botón no hace nada, que es la peor
        # forma de fallar.
        if enlace.startswith("="):
            raise ValueError(
                f"El enlace del botón «{texto}» empieza por '='. Quítaselo: "
                "aquí adentro solo van las llaves {{ }}, el '=' lo pone una "
                "sola vez el campo HTML completo."
            )
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


def flujo(nombre: str, path: str, para: str, asunto: str, html: str,
          remitente: str) -> dict:
    """
    Un flujo = webhook que escucha + correo que sale.

    `remitente` va sin valor por defecto a propósito: un flujo nuevo tiene que
    decir de qué buzón sale. Con un defecto, el que se olvide de ponerlo hereda
    el del vecino y falla con SendAsDenied el día que corra de madrugada.
    """
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
                    "fromEmail": remitente,
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
        # Lo lee el cliente y puede responderlo: sale del buzón donde alguien
        # atiende esa respuesta.
        remitente=REMITENTE_SERVICIO_CLIENTE,
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
            boton=("Consultar mi solicitud", f"{{{{ {B}.link_seguimiento }}}}"),
        ),
    ),
    flujo(
        # Aviso interno: le llega al propio equipo de Servicio al Cliente, así
        # que no puede salir de su mismo buzón.
        remitente=REMITENTE_INTERNO,
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
            boton=("Abrir en el portal", f"{{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        # Repartir la PQRS a un área es trabajo de Servicio al Cliente, y el
        # área le responde a ellos si algo no cuadra.
        remitente=REMITENTE_SERVICIO_CLIENTE,
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
            boton=("Abrir en el portal", f"{{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        # Aviso interno entre áreas: quien pide y quien firma son de la casa.
        remitente=REMITENTE_INTERNO,
        nombre="PQRS · autorización pedida o respondida",
        path="pqrs-autorizacion",
        para=f"={{{{ {B}.destinatarios.join(', ') }}}}",
        asunto=(
            f"={{{{ {B}.motivo === 'pendiente' "
            f"? 'Autorización pendiente · ' + {B}.autorizacion "
            f": 'Autorización ' + {B}.decision + ' · ' + {B}.autorizacion }}}}"
            f" · {{{{ {B}.codigo_seguimiento }}}}"
        ),
        html="=" + plantilla(
            titulo=(
                f"{{{{ {B}.motivo === 'pendiente' "
                f"? 'Necesitan que autoricen: ' + {B}.autorizacion "
                f": 'Autorización ' + {B}.decision + ': ' + {B}.autorizacion }}}}"
            ),
            cuerpo=(
                # Quién pidió o quién firmó, con la etiqueta que corresponde:
                # un correo que no dice de quién viene obliga a abrir el portal
                # solo para averiguarlo.
                f"{{{{ ({B}.motivo === 'pendiente' ? 'La pidió' : 'La respondió') }}}}"
                f": <strong>{{{{ {B}.persona }}}}</strong>"
                + dato("Solicitud", f"{{{{ {B}.codigo_seguimiento }}}}")
                + dato("Tipo", f"{{{{ {B}.tipo }}}}")
                + dato("Cliente", f"{{{{ {B}.cliente_nombre }}}}")
                + f"{{{{ {B}.comentario "
                  f"? '<p style=\"margin:14px 0 0 0;padding:12px;background:#EFF3F9;"
                  f"border-radius:8px\">' + {B}.comentario + '</p>' : '' }}}}"
                # El adjunto se anuncia, no se enlaza: /uploads no pide sesión.
                + f"{{{{ {B}.tiene_adjunto "
                  f"? '<p style=\"margin:10px 0 0 0;font-size:13px\">Adjuntaron un "
                  f"soporte; se ve en el portal.</p>' : '' }}}}"
            ),
            boton=("Abrir en el portal", f"{{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        # Entre el punto de venta y Contabilidad: puro interno.
        remitente=REMITENTE_INTERNO,
        nombre="Nota crédito · pedida a Contabilidad",
        path="nc-solicitada",
        para=f"={{{{ {B}.destinatarios.join(', ') }}}}",
        asunto=f"=Nota crédito por autorizar · {{{{ {B}.codigo }}}} · {{{{ {B}.punto_venta }}}}",
        html="=" + plantilla(
            titulo=f"{{{{ {B}.punto_venta }}}} pide una nota crédito",
            cuerpo=(
                dato("Solicitud", f"{{{{ {B}.codigo }}}}")
                + dato("La pidió", f"{{{{ {B}.solicitada_por }}}}")
                + dato("Factura", f"{{{{ {B}.factura_afectada }}}}")
                + f"{{{{ {B}.factura_reemplaza "
                  f"? '{dato('La reemplaza', '@@V@@')}'.replace('@@V@@', {B}.factura_reemplaza) "
                  f": '' }}}}"
                + f"{{{{ {B}.producto "
                  f"? '{dato('Producto', '@@V@@')}'.replace('@@V@@', {B}.producto) "
                  f": '' }}}}"
                + f"{{{{ {B}.valor "
                  f"? '{dato('Valor', '@@V@@')}'.replace('@@V@@', {B}.valor) "
                  f": '' }}}}"
                + f"{{{{ {B}.motivo "
                  f"? '{dato('Motivo', '@@V@@')}'.replace('@@V@@', {B}.motivo) "
                  f": '' }}}}"
                + f'<p style="margin:14px 0 0 0;padding:12px;background:#EFF3F9;'
                  f'border-radius:8px">{{{{ {B}.observaciones }}}}</p>'
                # El soporte se anuncia, no se enlaza: /uploads no pide sesión.
                + f"{{{{ {B}.tiene_adjunto "
                  f"? '<p style=\"margin:10px 0 0 0;font-size:13px\">Adjuntaron un "
                  f"soporte; se ve en el portal.</p>' : '' }}}}"
            ),
            boton=("Revisar en el portal", f"{{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        remitente=REMITENTE_INTERNO,
        nombre="Nota crédito · respondida a quien la pidió",
        path="nc-respondida",
        # A la PERSONA que la pidió, no al área: es quien está esperando para
        # atender a su cliente.
        para=f"={{{{ {B}.destinatarios.join(', ') }}}}",
        asunto=f"=Tu nota crédito {{{{ {B}.codigo }}}} quedó {{{{ {B}.decision }}}}",
        html="=" + plantilla(
            titulo=(
                f"{{{{ {B}.decision === 'aplicada' "
                f"? 'Ya se emitió la nota crédito' "
                f": 'Tu solicitud quedó ' + {B}.decision }}}}"
            ),
            cuerpo=(
                dato("Solicitud", f"{{{{ {B}.codigo }}}}")
                + dato("Factura", f"{{{{ {B}.factura_afectada }}}}")
                + dato("La respondió", f"{{{{ {B}.respondida_por }}}}")
                + f"{{{{ {B}.numero_nc "
                  f"? '{dato('Número de la nota crédito', '@@V@@')}'.replace('@@V@@', {B}.numero_nc) "
                  f": '' }}}}"
                + f"{{{{ {B}.comentario "
                  f"? '<p style=\"margin:14px 0 0 0;padding:12px;background:#EFF3F9;"
                  f"border-radius:8px\">' + {B}.comentario + '</p>' : '' }}}}"
            ),
            boton=("Ver en el portal", f"{{{{ {B}.link_portal }}}}"),
        ),
    ),
    flujo(
        # Va al cliente y lo invita a calificar: mismo buzón que su confirmación.
        remitente=REMITENTE_SERVICIO_CLIENTE,
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
            boton=("Calificar la atención", f"{{{{ {B}.link_encuesta }}}}"),
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
