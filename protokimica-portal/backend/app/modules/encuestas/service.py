"""
Lógica del módulo de Encuestas: consolidar respuestas y resumirlas.

Todo lo que sea contar, promediar o agrupar se resuelve aquí. El frontend
recibe números listos, igual que en el resto del portal — si recalculara,
tarde o temprano un reporte y una pantalla dirían cosas distintas.
"""
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.encuestas import Plantilla, Pregunta, Respuesta, RespuestaItem
from app.modules.encuestas.origenes import (
    ESCALA_MAX, ORIGENES, RespuestaVista, todas_las_respuestas,
)


def _aware(f: datetime | None) -> datetime | None:
    """
    Postgres devuelve las fechas con zona y SQLite sin ella; restarlas revienta.
    Es el mismo helper que ya hay en `resumen.py` y `fuentes.py`.
    """
    if f is None:
        return None
    return f if f.tzinfo else f.replace(tzinfo=timezone.utc)


def filtrar(respuestas: list[RespuestaVista], origen: str | None = None,
            desde: datetime | None = None, hasta: datetime | None = None,
            sujeto: str | None = None) -> list[RespuestaVista]:
    salida = respuestas
    if origen:
        salida = [r for r in salida if r.origen == origen]
    if sujeto:
        salida = [r for r in salida if (r.sujeto or "") == sujeto]
    if desde:
        limite = _aware(desde)
        salida = [r for r in salida if _aware(r.respondida_en) and _aware(r.respondida_en) >= limite]
    if hasta:
        limite = _aware(hasta)
        salida = [r for r in salida if _aware(r.respondida_en) and _aware(r.respondida_en) <= limite]
    return salida


def resumir(respuestas: list[RespuestaVista]) -> dict:
    """
    El encabezado del módulo: cuántas, qué calificación promedio y cómo se
    reparten las notas.

    La distribución importa tanto como el promedio: un 3.0 de puros treses y
    un 3.0 de mitad cincos y mitad unos son problemas distintos, y el
    promedio solo los muestra iguales.
    """
    calificadas = [r for r in respuestas if r.calificacion is not None]
    distribucion = {n: 0 for n in range(1, ESCALA_MAX + 1)}
    for r in calificadas:
        casilla = min(ESCALA_MAX, max(1, round(r.calificacion)))
        distribucion[casilla] += 1

    promedio = (
        round(sum(r.calificacion for r in calificadas) / len(calificadas), 2)
        if calificadas else None
    )
    # Detractores: 1 y 2 sobre 5. Es el número que de verdad hay que mirar,
    # porque el promedio se lleva bien con unos cuantos clientes furiosos.
    detractores = distribucion[1] + distribucion[2]

    return {
        "total": len(respuestas),
        "calificadas": len(calificadas),
        "promedio": promedio,
        "escala_max": ESCALA_MAX,
        "distribucion": distribucion,
        "detractores": detractores,
        "detractores_pct": (
            round((detractores / len(calificadas)) * 100, 1) if calificadas else None
        ),
        "con_comentario": sum(1 for r in respuestas if r.comentario),
    }


def resumir_por_sujeto(respuestas: list[RespuestaVista]) -> list[dict]:
    """
    Promedio por vendedor, punto de venta o área, según qué califique cada
    encuesta. Peor primero: un ranking sirve para actuar sobre la cola.
    """
    grupos: dict[str, list[float]] = {}
    for r in respuestas:
        if r.calificacion is None or not r.sujeto:
            continue
        grupos.setdefault(r.sujeto, []).append(r.calificacion)

    filas = [
        {
            "sujeto": sujeto,
            "respuestas": len(notas),
            "promedio": round(sum(notas) / len(notas), 2),
        }
        for sujeto, notas in grupos.items()
    ]
    return sorted(filas, key=lambda f: f["promedio"])


def listar_origenes(db: Session, tenant_id: int) -> list[dict]:
    """
    Los orígenes para el filtro. Las plantillas aportan uno cada una: para
    quien usa el portal, "Calificación de vendedores" es un origen, no una
    fila dentro de "Encuestas del portal".
    """
    salida = [{
        "clave": "pqrs",
        "nombre": ORIGENES["pqrs"]["nombre"],
        "descripcion": ORIGENES["pqrs"]["descripcion"],
    }]
    plantillas = db.query(Plantilla).filter(Plantilla.tenant_id == tenant_id).all()
    salida.extend({
        "clave": p.slug,
        "nombre": p.nombre,
        "descripcion": p.descripcion,
    } for p in plantillas)
    return salida


def respuesta_a_dict(r: RespuestaVista) -> dict:
    return {
        "id": r.id,
        "origen": r.origen,
        "origen_nombre": r.origen_nombre,
        "respondida_en": r.respondida_en,
        "calificacion": r.calificacion,
        "comentario": r.comentario,
        "sujeto": r.sujeto,
        "referencia": r.referencia,
        "items": [
            {"pregunta": i.pregunta, "valor": i.valor, "numero": i.numero}
            for i in r.items
        ],
    }


def construir_panel(db: Session, tenant_id: int, origen: str | None = None,
                    desde: datetime | None = None, hasta: datetime | None = None,
                    sujeto: str | None = None, limite: int = 200) -> dict:
    """El módulo completo: resumen, ranking y las respuestas ya filtradas."""
    respuestas = filtrar(todas_las_respuestas(db, tenant_id), origen, desde, hasta, sujeto)
    return {
        "resumen": resumir(respuestas),
        "por_sujeto": resumir_por_sujeto(respuestas),
        "origenes": listar_origenes(db, tenant_id),
        "respuestas": [respuesta_a_dict(r) for r in respuestas[:limite]],
        "hay_mas": len(respuestas) > limite,
    }


# ── Responder una encuesta ───────────────────────────────────────────────

def opciones_de_sujeto(plantilla: Plantilla) -> list[str]:
    """Lo que se puede calificar, si la encuesta trae lista cerrada."""
    return [s.strip() for s in (plantilla.sujetos or "").split("|") if s.strip()]

def guardar_respuesta(db: Session, plantilla: Plantilla, payload: dict) -> Respuesta:
    """
    Registra una respuesta validando contra las preguntas de la plantilla.

    Se valida aquí y no en el schema porque las preguntas son datos: qué es
    obligatorio y qué valores acepta cada una solo se sabe leyendo la
    plantilla, y eso cambia sin desplegar nada.
    """
    por_id = {p.id: p for p in plantilla.preguntas}
    recibidas = {int(k): v for k, v in (payload.get("respuestas") or {}).items()}

    faltantes = [
        p.texto for p in plantilla.preguntas
        if p.obligatoria and (
            recibidas.get(p.id) is None or str(recibidas.get(p.id)).strip() == ""
        )
    ]
    if faltantes:
        raise ValueError(
            "Faltan respuestas obligatorias: " + "; ".join(faltantes) +
            ". Complétalas y vuelve a enviar."
        )

    # Si la encuesta tiene lista cerrada, el sujeto tiene que salir de ahí.
    # Es lo que evita que el mismo punto de venta llegue escrito de cinco
    # formas y el reporte lo cuente como cinco lugares.
    opciones_sujeto = opciones_de_sujeto(plantilla)
    if opciones_sujeto:
        elegido = (payload.get("sujeto_nombre") or "").strip()
        if not elegido:
            raise ValueError(
                f"Falta indicar {plantilla.sujeto_tipo or 'a quién califica'}. "
                "Elige una opción de la lista."
            )
        if elegido not in opciones_sujeto:
            raise ValueError(
                f"«{elegido}» no está en la lista. "
                f"Elige una de: {', '.join(opciones_sujeto)}."
            )

    respuesta = Respuesta(
        tenant_id=plantilla.tenant_id,
        plantilla_id=plantilla.id,
        sujeto_ref=payload.get("sujeto_ref"),
        sujeto_nombre=payload.get("sujeto_nombre"),
    )
    db.add(respuesta)
    db.flush()

    for pregunta_id, valor in recibidas.items():
        pregunta = por_id.get(pregunta_id)
        if pregunta is None or valor is None or str(valor).strip() == "":
            continue
        db.add(_item_para(respuesta.id, pregunta, valor))

    db.commit()
    db.refresh(respuesta)
    return respuesta


def _item_para(respuesta_id: int, pregunta: Pregunta, valor) -> RespuestaItem:
    """
    Guarda el número aparte del texto: los promedios se calculan en la base,
    sin convertir texto en cada consulta.
    """
    if pregunta.tipo == "escala":
        try:
            numero = float(valor)
        except (TypeError, ValueError):
            raise ValueError(
                f"«{pregunta.texto}» espera una calificación numérica de 1 a {ESCALA_MAX}."
            )
        if not 1 <= numero <= ESCALA_MAX:
            raise ValueError(
                f"«{pregunta.texto}» debe estar entre 1 y {ESCALA_MAX}."
            )
        return RespuestaItem(respuesta_id=respuesta_id, pregunta_id=pregunta.id,
                             valor_numero=numero, valor_texto=None)

    if pregunta.tipo == "si_no":
        texto = "Sí" if str(valor).strip().lower() in ("si", "sí", "true", "1") else "No"
        return RespuestaItem(respuesta_id=respuesta_id, pregunta_id=pregunta.id,
                             valor_texto=texto)

    if pregunta.tipo == "opcion":
        opciones = [o.strip() for o in (pregunta.opciones or "").split("|") if o.strip()]
        if opciones and str(valor) not in opciones:
            raise ValueError(
                f"«{pregunta.texto}» solo acepta: {', '.join(opciones)}."
            )

    return RespuestaItem(respuesta_id=respuesta_id, pregunta_id=pregunta.id,
                         valor_texto=str(valor).strip())
