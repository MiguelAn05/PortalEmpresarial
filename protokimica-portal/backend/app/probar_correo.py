"""
Prueba si una cuenta puede enviar correo por SMTP, y traduce el error.

Sirve para separar dos cosas que se confunden todo el tiempo: si el correo no
sale, ¿es la configuración de n8n o es que ese buzón no tiene permiso? Esto
habla directo con Microsoft, sin n8n de por medio: si aquí funciona, el
problema está en n8n; si aquí falla, no hay nada que arreglar en n8n.

    docker exec -i -e SMTP_PASS protokimica_backend \
        python -m app.probar_correo <buzón> <destinatario>

La contraseña se pasa por variable de entorno, no como argumento: los
argumentos quedan en el historial del shell y en la lista de procesos.

    read -rsp "Contraseña: " SMTP_PASS; export SMTP_PASS; echo
"""
import os
import smtplib
import ssl
import sys
from email.message import EmailMessage

HOST = os.environ.get("SMTP_HOST", "smtp.office365.com")
PUERTO = int(os.environ.get("SMTP_PORT", "587"))

# Lo que contesta Microsoft y lo que de verdad significa. El código de error
# es lo único que distingue "la clave está mal" de "esta cuenta tiene el SMTP
# apagado", y en la interfaz de n8n solo se ve un mensaje rojo genérico.
PISTAS = [
    ("5.7.139", "authentication unsuccessful",
     "El buzón tiene el SMTP autenticado APAGADO.\n"
     "   Microsoft 365 Admin › Usuarios › esa cuenta › Correo ›\n"
     "   Administrar aplicaciones de correo electrónico › marcar «SMTP autenticado».\n"
     "   Tarda unos minutos en hacer efecto."),
    ("5.7.3", "authentication unsuccessful",
     "Usuario o contraseña incorrectos, o la cuenta tiene MFA.\n"
     "   Con MFA hace falta una contraseña de aplicación, no la normal."),
    ("5.7.3", "starttls",
     "La conexión no cifró. En n8n: puerto 587 y el toggle SSL/TLS APAGADO\n"
     "   (encendido significa SSL directo, que es el 465, y Microsoft no lo usa)."),
    ("5.7.60", "",
     "El remitente no coincide con la cuenta que autenticó.\n"
     "   El «from» debe ser ese mismo buzón, o tener permiso «Send As»."),
    ("5.2.0", "mailbox",
     "La cuenta autenticó pero no tiene buzón utilizable.\n"
     "   Revisa que tenga licencia de Exchange Online."),
]


def explicar(error: str) -> str:
    bajo = error.lower()
    for codigo, texto, ayuda in PISTAS:
        if codigo in bajo and (not texto or texto in bajo):
            return ayuda
    return ("No es un error conocido. Cópialo tal cual: el código (5.x.x) es\n"
            "   lo que dice qué pasó.")


def main(buzon: str, destinatario: str, clave: str) -> int:
    print(f"Servidor    : {HOST}:{PUERTO}")
    print(f"Autenticando: {buzon}")
    print(f"Enviando a  : {destinatario}\n")

    mensaje = EmailMessage()
    mensaje["From"] = buzon
    mensaje["To"] = destinatario
    mensaje["Subject"] = "Prueba de correo del portal"
    mensaje.set_content(
        "Si estás leyendo esto, la cuenta puede enviar correo por SMTP y el "
        "portal podrá avisar de las PQRS.\n\nPortal Protokimica"
    )

    try:
        with smtplib.SMTP(HOST, PUERTO, timeout=20) as smtp:
            smtp.ehlo()
            print("1/4  Conectado")

            # STARTTLS es obligatorio en Exchange Online: la conexión empieza
            # en claro y se sube a TLS aquí mismo.
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            print("2/4  Conexión cifrada (STARTTLS)")

            smtp.login(buzon, clave)
            print("3/4  Autenticado")

            smtp.send_message(mensaje)
            print("4/4  Correo entregado al servidor de Microsoft\n")

        print("FUNCIONA. Revisa la bandeja (y el correo no deseado).")
        print("Si el portal sigue sin mandar, el problema está en n8n:")
        print("  · la credencial SMTP con estos mismos datos,")
        print("  · el puerto 587 con SSL/TLS apagado,")
        print("  · y el flujo ACTIVO, no solo importado.")
        return 0

    except Exception as exc:
        detalle = str(exc)
        print(f"FALLÓ en {type(exc).__name__}:\n   {detalle}\n")
        print(f"→  {explicar(detalle)}")
        return 1


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)

    contrasena = os.environ.get("SMTP_PASS")
    if not contrasena:
        print("Falta la contraseña. Antes de correr esto:\n")
        print('  read -rsp "Contraseña: " SMTP_PASS; export SMTP_PASS; echo')
        sys.exit(2)

    sys.exit(main(sys.argv[1], sys.argv[2], contrasena))
