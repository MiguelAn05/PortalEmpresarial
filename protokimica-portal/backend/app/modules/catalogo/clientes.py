"""
«¿Este NIT es cliente nuestro?», sin copiar clientes.

El ERP tiene unos 167.000 terceros con nombre, cédula, ciudad y datos
bancarios. El portal no necesita nada de eso: solo saber si quien radica una
PQRS ya nos compra. Así que el script de MORFEO no manda clientes sino una
HUELLA de cada NIT —un HMAC-SHA256 con `CLAVE_HUELLA_NIT`— y aquí se guarda
solo eso. Al radicar se calcula la huella del NIT escrito y se busca.

Reglas:

  - **Nunca frena nada.** Un NIT que no aparece no es un error: puede ser un
    cliente nuevo, una persona natural o un NIT mal escrito. La PQRS se
    radica igual y la marca solo la ven los agentes.
  - **Al cliente no se le dice.** Ni el formulario público ni la consulta
    del radicado llevan la marca: si no, el formulario serviría para
    averiguar quién es cliente de la empresa.
  - **Se pregunta al leer, no se guarda en la PQRS.** Así un cliente que el
    ERP crea después aparece verificado sin migrar nada.

Una huella sin la clave no se puede revertir; y como la clave vive en el
`.env` y no en la base, una copia de la base sola no revela ningún NIT.
"""
import hmac
import re
from hashlib import sha256

from fastapi import HTTPException
from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.catalogo import HuellaClienteERP

# Lo que se le aplica a un texto fijo para comprobar que el portal y MORFEO
# usan la MISMA clave. Si no coinciden, ninguna huella va a coincidir nunca,
# y eso se vería como «nadie es cliente» sin ningún error en ninguna parte.
TEXTO_DE_CONTROL = "control-portal-protokimica"

_HUELLA = re.compile(r"^[0-9a-f]{64}$")

# Pesos del dígito de verificación de la DIAN, de derecha a izquierda.
_PESOS_DV = (3, 7, 13, 17, 19, 23, 29, 37, 41, 43, 47, 53, 59, 67, 71)


def digito_verificacion(numero: str) -> int:
    """El dígito de verificación de un NIT colombiano (algoritmo de la DIAN)."""
    suma = sum(int(d) * p for d, p in zip(reversed(numero), _PESOS_DV))
    resto = suma % 11
    return resto if resto < 2 else 11 - resto


def candidatos(nit: str | None) -> list[str]:
    """
    Las formas en que pudo quedar guardado en el ERP lo que escribió alguien.

    El ERP guarda el número sin dígito de verificación, y la gente lo escribe
    de todas las formas: «900.123.456-7», «900123456 7», «9001234567». Con
    guion o espacio, lo de antes es el número. Pegado, no hay cómo saberlo,
    así que si la última cifra ES el dígito de verificación del resto se
    prueban las dos.
    """
    texto = (nit or "").strip()
    if not texto:
        return []

    separado = re.match(r"^([\d.\s]+?)\s*[-\s]\s*(\d)$", texto)
    if separado:
        base = re.sub(r"\D", "", separado.group(1)).lstrip("0")
        return [base] if base else []

    cifras = re.sub(r"\D", "", texto).lstrip("0")
    if not cifras:
        return []
    salida = [cifras]
    if len(cifras) >= 6 and digito_verificacion(cifras[:-1]) == int(cifras[-1]):
        salida.append(cifras[:-1])
    return salida


def huella(nit: str, clave: str | None = None) -> str:
    """El HMAC-SHA256 en hexadecimal. Igual al que calcula el script de MORFEO."""
    clave = clave if clave is not None else settings.CLAVE_HUELLA_NIT
    return hmac.new(clave.encode("utf-8"), nit.encode("utf-8"), sha256).hexdigest()


def es_cliente(db: Session, tenant_id: int, nit: str | None) -> bool | None:
    """
    True si el NIT está en el ERP, False si no, None si no se puede saber.

    None es distinto de False y la pantalla lo trata distinto: sin clave
    configurada, o sin haber recibido nunca la lista, decir «no es cliente»
    sería afirmar algo que nadie revisó.
    """
    if not settings.CLAVE_HUELLA_NIT:
        return None
    opciones = candidatos(nit)
    if not opciones:
        return None
    hay_lista = db.query(HuellaClienteERP.id).filter(
        HuellaClienteERP.tenant_id == tenant_id
    ).first()
    if not hay_lista:
        return None

    return db.query(HuellaClienteERP.id).filter(
        HuellaClienteERP.tenant_id == tenant_id,
        HuellaClienteERP.huella.in_([huella(c) for c in opciones]),
    ).first() is not None


def sincronizar(db: Session, tenant_id: int, huellas: list[str], control: str) -> dict:
    """
    Deja la lista igual a la recibida, en una sola transacción.

    A diferencia de los productos, lo que deja de venir SE BORRA: es una
    huella, nada la referencia, y guardarla solo haría que un tercero que el
    ERP ya no tiene como cliente siguiera apareciendo verificado.
    """
    if not settings.CLAVE_HUELLA_NIT:
        raise HTTPException(
            status_code=503,
            detail=(
                "La verificación de clientes no está configurada. Falta "
                "CLAVE_HUELLA_NIT en el .env del servidor (la misma del script de MORFEO)."
            ),
        )
    if not hmac.compare_digest((control or "").lower(), huella(TEXTO_DE_CONTROL)):
        raise HTTPException(
            status_code=409,
            detail=(
                "La clave de huellas del script de MORFEO no es la misma "
                "CLAVE_HUELLA_NIT del portal. Copia la del .env al script: con "
                "claves distintas ningún NIT coincidiría nunca."
            ),
        )

    recibidas = {h.strip().lower() for h in huellas}
    malas = [h for h in recibidas if not _HUELLA.match(h)]
    if malas:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{len(malas)} huellas no tienen el formato esperado (64 cifras "
                "hexadecimales). No se aplicó nada: revisa el script de MORFEO."
            ),
        )

    existentes = {
        h for (h,) in db.query(HuellaClienteERP.huella).filter(
            HuellaClienteERP.tenant_id == tenant_id
        )
    }
    nuevas = recibidas - existentes
    sobran = list(existentes - recibidas)

    if nuevas:
        db.execute(insert(HuellaClienteERP), [
            {"tenant_id": tenant_id, "huella": h} for h in nuevas
        ])
    for i in range(0, len(sobran), 1000):
        db.query(HuellaClienteERP).filter(
            HuellaClienteERP.tenant_id == tenant_id,
            HuellaClienteERP.huella.in_(sobran[i:i + 1000]),
        ).delete(synchronize_session=False)

    return {
        "recibidos": len(huellas),
        "nuevos": len(nuevas),
        "retirados": len(sobran),
        "total": len(recibidas),
    }
