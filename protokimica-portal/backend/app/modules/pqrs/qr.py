"""
Los códigos QR que se imprimen y se pegan en cada punto de venta.

**Un QR no se vence.** Es un dibujo que contiene un texto — aquí, una URL del
portal. Lo que caduca es cuando se genera en un sitio de internet que crea un
enlace intermedio suyo: ese enlace es de ellos y lo apagan cuando quieren.
Estos apuntan directo a `FRONTEND_URL`, así que funcionan mientras el portal
exista y no dependen de ningún servicio de terceros.

Cada punto de venta lleva el suyo, y eso es lo que le da valor:
`/q/PVG` abre el formulario **ya marcado como Guayabal**. El canal deja de ser
algo que el cliente elige de una lista —donde se equivoca— y pasa a venir del
letrero que tiene enfrente. Importa porque el canal decide el prefijo del
código de seguimiento (`PVG0010`) y de él salen los reportes por sede: si el
cliente se equivoca ahí, el número queda mal para siempre.
"""
import io

import segno

from app.core import canales
from app.core.config import settings

# Nivel de corrección de errores. `Q` recupera hasta un 25% del código
# dañado: es lo que corresponde a algo impreso y pegado en un mostrador, que
# se raya, se moja y le pegan cinta encima. Con la URL que manejamos el
# código sigue siendo pequeño (versión 4, 33×33 módulos).
CORRECCION = "q"

# Tamaño de cada módulo en el SVG. El SVG es vectorial y se reescala sin
# perder nada, así que esto solo fija el tamaño natural.
ESCALA_SVG = 8

# El PNG sí es de tamaño fijo, y existe para quien tenga que meter el código
# en un diseño o en un documento. 20 deja un archivo de ~660px de lado, que
# imprime bien a tamaño de media carta.
ESCALA_PNG = 20


def url_del_canal(codigo: str) -> str:
    """
    La URL que queda dentro del QR.

    Se arma en el servidor a partir de `FRONTEND_URL` y del código validado,
    nunca con algo que llegue en la petición: así este endpoint no puede
    usarse para fabricar un QR con el dominio del portal que lleve a otra
    parte.
    """
    base = (settings.FRONTEND_URL or "").strip().rstrip("/")
    return f"{base}/q/{codigo.strip().upper()}"


def validar_codigo(codigo: str) -> tuple[str, str]:
    """
    Devuelve `(codigo_normalizado, nombre_del_canal)`.

    Levanta `ValueError` si el código no es de un canal conocido — no se
    generan QR de canales inventados: un letrero impreso apuntando a un canal
    que el servidor no reconoce mandaría las PQRS al radicado genérico sin
    que nadie se entere.
    """
    canal = canales.canal_por_codigo(codigo)
    if canal is None:
        raise ValueError(codigo)
    return canales.PREFIJOS_POR_CANAL[canal], canal


def svg(codigo: str) -> bytes:
    """El QR como SVG, listo para imprimir a cualquier tamaño."""
    normalizado, _ = validar_codigo(codigo)
    qr = segno.make(url_del_canal(normalizado), error=CORRECCION)

    buffer = io.BytesIO()
    # `xmldecl` y `svgclass` fuera: así el SVG se puede incrustar dentro de
    # otra página sin arrastrar una declaración XML ni clases que choquen.
    qr.save(buffer, kind="svg", scale=ESCALA_SVG, border=4,
            xmldecl=False, svgclass=None, lineclass=None,
            dark="#000000", light="#ffffff")
    return buffer.getvalue()


def png(codigo: str) -> bytes:
    """El QR como PNG, para meterlo en un diseño o en un documento."""
    normalizado, _ = validar_codigo(codigo)
    qr = segno.make(url_del_canal(normalizado), error=CORRECCION)

    buffer = io.BytesIO()
    qr.save(buffer, kind="png", scale=ESCALA_PNG, border=4)
    return buffer.getvalue()


def listar() -> list[dict]:
    """
    Todos los canales que tienen QR, con su código y la URL que llevan
    dentro.

    Lo consume la pantalla de impresión. La URL viene resuelta del servidor
    para que lo impreso sea exactamente lo que el QR contiene: si la pantalla
    la armara por su cuenta con el dominio del navegador, un administrador
    entrando por la IP interna imprimiría letreros que apuntan a `172.20…` y
    ningún cliente podría abrirlos desde su celular.
    """
    return [
        {
            "codigo": prefijo,
            "canal": canal,
            "url": url_del_canal(prefijo),
            "es_punto_de_venta": canal.startswith("Punto de venta"),
        }
        for canal, prefijo in canales.PREFIJOS_POR_CANAL.items()
    ]
