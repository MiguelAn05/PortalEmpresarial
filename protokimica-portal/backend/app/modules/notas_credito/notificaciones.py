"""
Los correos de las notas crédito.

Sin esto la función no sirve: hoy el punto de venta manda un correo y alguien
de Contabilidad lo ve llegar. Si el portal solo guardara la solicitud en una
pantalla, nadie sabría que hay algo esperando — habríamos cambiado un correo
que funciona por un tablero que nadie mira.

Se apoya en la maquinaria de avisos de PQRS (`enviar_avisos`, los correos por
área y el envoltorio que impide que notificar tumbe la petición) porque es
exactamente la misma y duplicarla sería tener dos sitios donde arreglar el
próximo webhook con un salto de línea al final.
"""
from sqlalchemy.orm import Session

from app.core import canales
from app.core.capacidades import correos_de, usuarios_con
from app.core.config import settings
from app.models.nota_credito import ESTADO_APROBADA, ESTADO_EN_BODEGA
from app.models.user import User
from app.modules.pqrs.notificaciones import Aviso, _protegido
from app.modules.notas_credito import flujo
from app.modules.notas_credito.permisos import CAP_REGISTRAR

# El nombre del evento ES el path del webhook en n8n. Una prueba compara esta
# lista contra los flujos de `backend/n8n/`: un path mal escrito no falla, n8n
# contesta 404 y el correo simplemente no llega.
EVENTO_RESPONDIDA = "nc-respondida"
EVENTO_POR_EMITIR = "nc-por-emitir"

# «Te toca a ti», en cualquier etapa de la cadena. Es UN solo evento y no uno
# por etapa a propósito: el correo dice qué hacer leyendo `que_hacer` del
# payload, así que agregar un paso mañana no obliga a construir, importar y
# activar otro flujo en n8n — que es trabajo manual y es donde se olvida uno.
EVENTO_EN_TURNO = "nc-en-turno"

# Devuelta para corregir. Va aparte de `nc-respondida` porque no es una
# decisión final: el correo tiene que pedir una acción («corrige y reenvía»),
# no comunicar un resultado.
EVENTO_DEVUELTA = "nc-devuelta"

EVENTOS = frozenset({
    EVENTO_RESPONDIDA, EVENTO_POR_EMITIR,
    EVENTO_EN_TURNO, EVENTO_DEVUELTA,
})


def _base(solicitud) -> dict:
    """Lo que ambos correos necesitan decir de la solicitud."""
    return {
        "solicitud_id": solicitud.id,
        "codigo": solicitud.codigo,
        "punto_venta": solicitud.punto_venta,
        "factura_afectada": solicitud.factura_afectada,
        "factura_reemplaza": solicitud.factura_reemplaza,
        "valor": str(solicitud.valor) if solicitud.valor is not None else "",
        "motivo": solicitud.motivo_nombre or "",
        "observaciones": (solicitud.observaciones or "")[:280],
        # El soporte se ANUNCIA, no se enlaza: /uploads no pide sesión, así que
        # una URL en un correo se reenvía sola. El botón lleva al portal.
        "tiene_adjunto": bool(solicitud.adjunto),
        "link_portal": f"{settings.FRONTEND_URL}/notas-credito",
    }


def _aviso_respondida(db: Session, tenant_id: int, solicitud, decision: str,
                      respondida_por: str) -> list[Aviso]:
    """
    Le avisa a QUIEN la pidió, no al área.

    Es una persona concreta la que está esperando para atender a su cliente;
    mandarlo al área entera sería que el aviso le llegue a todo el almacén
    menos, en la práctica, a quien tiene que actuar.
    """
    solicitante = db.get(User, solicitud.solicitado_por)
    if not solicitante or not solicitante.email or not solicitante.activo:
        return []
    return [(EVENTO_RESPONDIDA, {
        **_base(solicitud),
        "decision": decision,
        "respondida_por": respondida_por,
        "numero_nc": solicitud.numero_nc or "",
        "comentario": (solicitud.comentario_respuesta or "")[:280],
        "destinatarios": [solicitante.email],
    })]


def _aviso_por_emitir(db: Session, tenant_id: int, solicitud, aprobada_por: str) -> list[Aviso]:
    """
    Aprobada y sin emitir: le avisa AL PUNTO DE VENTA de la solicitud.

    Quien la emite y escribe su número es el punto de venta al que pertenece
    la factura, así que el aviso va a la gente de ESE punto que tenga la
    capacidad de registrar —no a todo el que pueda hacerlo: una nota crédito
    de Guayabal no es trabajo de Belén—. Se reconoce por el prefijo del
    canal, igual que las PQRS de cada sede.

    A quien la pidió no se le manda por aquí: ya recibe el aviso de la
    decisión y serían dos correos para una sola cosa.

    **Si en ese punto no hay nadie que pueda emitirla, no se descarta**: se
    manda a todos los que tienen el permiso. Una nota crédito aprobada que
    nadie emite deja al cliente esperando, y el silencio es el peor final.
    """
    prefijo = canales.prefijo_de(solicitud.punto_venta)
    con_permiso = usuarios_con(db, tenant_id, CAP_REGISTRAR)
    del_punto = [u for u in con_permiso if prefijo and u.punto_venta == prefijo]

    destinatarios = sorted({
        u.email for u in (del_punto or con_permiso)
        if u.email and u.id != solicitud.solicitado_por
    })
    if not destinatarios:
        return []
    return [(EVENTO_POR_EMITIR, {
        **_base(solicitud),
        "aprobada_por": aprobada_por,
        "es_del_punto": bool(del_punto),
        "destinatarios": destinatarios,
    })]


def avisos_respondida(db: Session, tenant_id: int, solicitud, decision: str,
                      respondida_por: str) -> list[Aviso]:
    return _protegido(_aviso_respondida, db, tenant_id, solicitud, decision, respondida_por)


def avisos_por_emitir(db: Session, tenant_id: int, solicitud, aprobada_por: str) -> list[Aviso]:
    return _protegido(_aviso_por_emitir, db, tenant_id, solicitud, aprobada_por)


def _lideres_del_solicitante(db: Session, tenant_id: int, solicitud) -> list[str]:
    """
    Los líderes del área de quien radicó, para ponerlos en copia.

    No es un paso del flujo: el líder no aprueba nada aquí y la solicitud no
    lo espera. Es enterarse de que su gente está pidiendo notas crédito —el
    jefe del punto de venta quiere saber que su sede pidió una, no firmarla—,
    y por eso va como copia del primer aviso y no como un turno más. Meterlo
    en la cadena habría sido una firma que nadie pidió y un paso donde una
    solicitud se queda quieta si el líder está de vacaciones.

    Un área sin nadie con rol de líder simplemente no suma a nadie: que no
    haya jefe configurado no puede impedir que la solicitud avance.
    """
    solicitante = db.get(User, solicitud.solicitado_por)
    if not solicitante or not solicitante.area:
        return []
    lideres = db.query(User).filter(
        User.tenant_id == tenant_id,
        User.area == solicitante.area,
        User.rol == "lider",
        User.activo.is_(True),
    ).all()
    return sorted({
        u.email for u in lideres
        if u.email and u.id != solicitud.solicitado_por
    })


def _aviso_en_turno(db: Session, tenant_id: int, solicitud) -> list[Aviso]:
    """
    Le avisa a quien le toca AHORA, sea la etapa que sea.

    Los destinatarios salen de la capacidad que atiende el turno, así que
    cambiar quién aprueba se hace desde Administración › Capacidades y no
    tocando este archivo.

    Dos reglas propias:

    - **La bodega se acota a la suya**, con el mismo fallback de siempre: si
      en esa bodega no hay nadie marcado, va a todos los que pueden
      confirmar. Una solicitud parada porque su destinatario no existe es
      peor que un correo de más.
    - **Quien atiende el turno SIGUIENTE va en copia.** No decide todavía,
      pero puede ir mirando: cuando una llega a Comercial, Contabilidad
      empieza a revisar la factura en vez de arrancar de cero cuando le
      toque. Sale de la cadena y no de una capacidad escrita a mano, porque
      el «siguiente» no es el mismo en las dos ramas —en la del mostrador
      Contabilidad autoriza, en la institucional verifica ante la DIAN— y
      nombrar una sola dejaba la otra sin copia en silencio.
      Se excluye el último turno, el de emitir: para eso está `nc-por-emitir`,
      y adelantarlo sería pedirle a alguien que prepare algo que todavía
      puede rechazarse.
    - **En el PRIMER turno, el líder del área de quien pidió va en copia**,
      para que se entere de que su sede radicó una. Solo en el primero: en
      los siguientes ya no aporta nada y serían cuatro correos por una nota.
      Una devuelta que se reenvía vuelve al primer turno, así que el líder
      también se entera de que volvió a entrar — que es correcto, porque es
      una solicitud nueva sobre datos corregidos.
    """
    capacidad = flujo.capacidad_de(solicitud.estado)
    if capacidad is None:
        return []

    candidatos = usuarios_con(db, tenant_id, capacidad)
    if solicitud.estado == ESTADO_EN_BODEGA:
        de_la_bodega = [u for u in candidatos if flujo.atiende_la_bodega(u, solicitud.bodega)]
        candidatos = de_la_bodega or candidatos

    destinatarios = sorted({u.email for u in candidatos if u.email})
    if not destinatarios:
        return []

    en_copia = []
    turno_siguiente = flujo.siguiente(
        solicitud.estado, solicitud.punto_venta, bool(solicitud.bodega),
    )
    if turno_siguiente and turno_siguiente != ESTADO_APROBADA:
        capacidad_siguiente = flujo.capacidad_de(turno_siguiente)
        en_copia = [c for c in correos_de(db, tenant_id, capacidad_siguiente)
                    if c not in destinatarios]

    es_el_primer_turno = solicitud.estado == flujo.estado_inicial(
        solicitud.punto_venta, bool(solicitud.bodega),
    )
    if es_el_primer_turno:
        en_copia += [c for c in _lideres_del_solicitante(db, tenant_id, solicitud)
                     if c not in destinatarios and c not in en_copia]

    return [(EVENTO_EN_TURNO, {
        **_base(solicitud),
        "etapa": solicitud.estado,
        "etapa_nombre": flujo.etiqueta(solicitud.estado),
        "que_hacer": flujo.QUE_HACER.get(solicitud.estado, ""),
        "bodega": solicitud.bodega or "",
        "destinatarios": destinatarios,
        "en_copia": en_copia,
    })]


def _aviso_devuelta(db: Session, tenant_id: int, solicitud, etapa: str,
                    devuelta_por: str, comentario: str | None) -> list[Aviso]:
    """
    Le avisa a QUIEN LA PIDIÓ que se la devolvieron para corregir.

    El comentario viaja completo hasta el tope de siempre: una devolución sin
    decir qué corregir obliga a una llamada, que es justo el ir y venir que
    este módulo vino a quitar.
    """
    solicitante = db.get(User, solicitud.solicitado_por)
    if not solicitante or not solicitante.email or not solicitante.activo:
        return []
    return [(EVENTO_DEVUELTA, {
        **_base(solicitud),
        "devuelta_en": flujo.etiqueta(etapa),
        "devuelta_por": devuelta_por,
        "comentario": (comentario or "")[:280],
        "destinatarios": [solicitante.email],
    })]


def avisos_en_turno(db: Session, tenant_id: int, solicitud) -> list[Aviso]:
    return _protegido(_aviso_en_turno, db, tenant_id, solicitud)


def avisos_devuelta(db: Session, tenant_id: int, solicitud, etapa: str,
                    devuelta_por: str, comentario: str | None) -> list[Aviso]:
    return _protegido(_aviso_devuelta, db, tenant_id, solicitud, etapa,
                      devuelta_por, comentario)
