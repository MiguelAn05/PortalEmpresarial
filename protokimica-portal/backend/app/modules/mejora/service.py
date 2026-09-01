"""
Las reglas del ciclo de una OMP.

Aquí vive lo que hace que el módulo sirva para una auditoría y no sea una
lista de tareas con otro nombre: no se avanza sin entender el hallazgo, no
se cierra sin comparar el indicador contra el periodo que la disparó, y no
se da por cerrada sin que el SGC lo valide.

Qué se exige depende del **tratamiento**: una Acción de Mejora no tiene
causa raíz que buscar, tiene un beneficio que justificar. Antes se pedía
causa raíz siempre, y la salida era escribir «no aplica» para poder avanzar
— que es como se le enseña a la gente a mentirle a un formulario.
"""
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.indicadores import Indicador, Medicion
from app.models.mejora import (
    ESTADO_DESCARTADA, ESTADOS, CambioMejora, ItemCatalogo, Oportunidad,
)
from app.modules.mejora import catalogos as cat

INTENTOS_CODIGO = 5


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


# ── Catálogos ────────────────────────────────────────────────────────

def sembrar_catalogos(db: Session, tenant_id: int) -> None:
    """
    Deja los catálogos del formato listos para esta empresa.

    Solo agrega lo que falta, nunca reescribe ni reactiva: Calidad administra
    estas listas desde el portal y una siembra que pisara sus cambios le
    devolvería en cada arranque los procesos que ya había desactivado.

    Se llama al pedir los catálogos y al crear una OMP en vez de al arrancar
    el servidor, para que una empresa nueva funcione sin un paso manual.
    """
    existentes = {
        (fila.tipo, fila.nombre)
        for fila in db.query(ItemCatalogo.tipo, ItemCatalogo.nombre)
        .filter(ItemCatalogo.tenant_id == tenant_id)
        .all()
    }

    nuevos = []
    for tipo, valores in cat.SEMILLA.items():
        for orden, (codigo, nombre) in enumerate(valores):
            if (tipo, nombre) not in existentes:
                nuevos.append(ItemCatalogo(
                    tenant_id=tenant_id, tipo=tipo, codigo=codigo,
                    nombre=nombre, orden=orden, activo=True,
                ))

    if nuevos:
        db.add_all(nuevos)
        db.commit()


def listar_catalogos(db: Session, tenant_id: int, incluir_inactivos: bool = False) -> dict:
    """Los tres catálogos agrupados por tipo, en el orden en que se muestran."""
    sembrar_catalogos(db, tenant_id)

    query = db.query(ItemCatalogo).filter(ItemCatalogo.tenant_id == tenant_id)
    if not incluir_inactivos:
        query = query.filter(ItemCatalogo.activo.is_(True))

    agrupado = {tipo: [] for tipo in cat.TIPOS}
    for item in query.order_by(ItemCatalogo.tipo, ItemCatalogo.orden, ItemCatalogo.id).all():
        agrupado.setdefault(item.tipo, []).append(item)
    return agrupado


def item_por_nombre(db: Session, tenant_id: int, tipo: str, nombre: str | None):
    if not nombre:
        return None
    return (
        db.query(ItemCatalogo)
        .filter(ItemCatalogo.tenant_id == tenant_id,
                ItemCatalogo.tipo == tipo,
                ItemCatalogo.nombre == nombre)
        .first()
    )


def proceso_propuesto(db: Session, tenant_id: int, area: str | None):
    """
    Qué proceso del SGC le corresponde a un área del portal.

    Es una PROPUESTA para ahorrar un clic, no una equivalencia: el área
    decide permisos y el proceso rotula el reporte, y hay áreas del portal
    que no existen como proceso. Cuando no hay equivalente se devuelve None
    y la persona elige — adivinar mal manda la acción al reporte de otro.
    """
    nombre = cat.PROCESO_SEGUN_AREA.get(area or "")
    return item_por_nombre(db, tenant_id, "proceso", nombre)


def fuente_propuesta(db: Session, tenant_id: int, origen: str | None):
    nombre = cat.FUENTE_SEGUN_ORIGEN.get(origen or "")
    return item_por_nombre(db, tenant_id, "fuente", nombre)


def validar_item(db: Session, tenant_id: int, tipo: str, item_id: int | None):
    """Comprueba que el id sea de un catálogo del tipo correcto y de esta empresa."""
    if item_id is None:
        return None
    item = (
        db.query(ItemCatalogo)
        .filter(ItemCatalogo.id == item_id,
                ItemCatalogo.tenant_id == tenant_id,
                ItemCatalogo.tipo == tipo)
        .first()
    )
    if item is None:
        raise HTTPException(
            status_code=400,
            detail=f"El {tipo} elegido ya no existe. Vuelve a abrir la lista y escógelo de nuevo.",
        )
    return item


# ── Consecutivos ─────────────────────────────────────────────────────

def generar_codigo(db: Session, tenant_id: int) -> str:
    """
    OMP-{año}-{consecutivo}.

    Sale del MÁXIMO ya usado, nunca de un conteo: con OMP-2026-0001 y
    OMP-2026-0003 en la tabla —porque alguien borró la del medio— contar da 2
    y el siguiente saldría repetido, reventando contra el índice único. Es
    exactamente lo que pasó con los códigos de PQRS.
    """
    prefijo = f"OMP-{_ahora().year}-"
    codigos = (
        db.query(Oportunidad.codigo)
        .filter(Oportunidad.tenant_id == tenant_id,
                Oportunidad.codigo.isnot(None),
                Oportunidad.codigo.like(f"{prefijo}%"))
        .all()
    )
    mayor = 0
    for (codigo,) in codigos:
        sufijo = (codigo or "")[len(prefijo):]
        if sufijo.isdigit():
            mayor = max(mayor, int(sufijo))
    return f"{prefijo}{mayor + 1:04d}"


def siguiente_consecutivo(db: Session, tenant_id: int, proceso_id: int | None) -> int:
    """
    El número que la acción lleva DENTRO de su proceso: 1, 2, 3…

    Es el que el SGC y los auditores citan, porque hasta hoy cada proceso
    llevaba su propio archivo. Sale del MÁXIMO por la misma razón de siempre:
    contar las filas del proceso devuelve un número ya usado en cuanto se
    borra una del medio.
    """
    # Las que todavía no tienen proceso comparten su propia numeración: es
    # temporal, hasta que alguien se lo asigne.
    del_proceso = (
        Oportunidad.proceso_id.is_(None) if proceso_id is None
        else Oportunidad.proceso_id == proceso_id
    )
    consecutivos = (
        db.query(Oportunidad.consecutivo)
        .filter(Oportunidad.tenant_id == tenant_id,
                del_proceso,
                Oportunidad.consecutivo.isnot(None))
        .all()
    )
    mayor = max((c for (c,) in consecutivos), default=0)
    return mayor + 1


def asignar_codigo(db: Session, oportunidad: Oportunidad, tenant_id: int) -> str:
    """Le pone el código y el consecutivo, y reintenta si dos personas
    abrieron una a la vez."""
    for _ in range(INTENTOS_CODIGO):
        oportunidad.codigo = generar_codigo(db, tenant_id)
        oportunidad.consecutivo = siguiente_consecutivo(
            db, tenant_id, oportunidad.proceso_id,
        )
        try:
            db.commit()
            db.refresh(oportunidad)
            return oportunidad.codigo
        except IntegrityError:
            db.rollback()
            db.refresh(oportunidad)

    raise HTTPException(
        status_code=500,
        detail=("La oportunidad quedó registrada pero sin código. Informa a un "
                "administrador; no la vuelvas a crear."),
    )


# ── Trazabilidad ─────────────────────────────────────────────────────

# Los campos cuyo cambio vale la pena guardar. No se registra todo: el
# historial sirve para responder «¿por qué esto se aplazó tres veces?», y
# una bitácora con cada corrección de ortografía en la descripción entierra
# justamente esa pregunta.
CAMPOS_CON_HISTORIAL = {
    "estado": "Estado",
    "prioridad": "Prioridad",
    "fecha_limite": "Fecha estimada de solución",
    "causa_raiz": "Causa raíz",
    "proceso_id": "Proceso",
    "tratamiento_id": "Tratamiento",
    "area": "Área",
    "eficaz": "Resultado de la verificación",
}


def _texto(valor) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    return str(valor)


def registrar_cambio(db: Session, omp_id: int, campo: str,
                     anterior, nuevo, usuario_id: int | None) -> None:
    """Deja constancia de un cambio. No hace commit: lo hace quien llama."""
    if campo not in CAMPOS_CON_HISTORIAL:
        return
    antes, despues = _texto(anterior), _texto(nuevo)
    if antes == despues:
        return
    db.add(CambioMejora(
        omp_id=omp_id, campo=CAMPOS_CON_HISTORIAL[campo],
        valor_anterior=antes, valor_nuevo=despues, usuario_id=usuario_id,
    ))


# ── Análisis de causas (6M) ──────────────────────────────────────────

# El orden y las etiquetas con las que el formato imprime el bloque. Se
# respetan al exportar para que el .xlsx siga leyéndose igual que siempre.
CAMPOS_6M = [
    ("causa_efecto", "Efecto"),
    ("causa_metodo", "Método"),
    ("causa_mano_obra", "Mano de Obra"),
    ("causa_maquinaria", "Maquinaria"),
    ("causa_material", "Material"),
    ("causa_medidas", "Medidas"),
    ("causa_medio_ambiente", "Medio Ambiente"),
]


def bloque_6m(oportunidad: Oportunidad) -> str | None:
    """
    Reconstruye el texto que el Excel lleva en la columna de análisis de
    causas, a partir de los siete campos.

    Las 6M que quedaron vacías salen como «N/A», que es como el formato las
    escribe: una M ausente y una M que no aplica se leen distinto, y el
    auditor pregunta por la ausente.
    """
    lineas = []
    for campo, etiqueta in CAMPOS_6M:
        valor = (getattr(oportunidad, campo, None) or "").strip()
        lineas.append(f"{etiqueta}: {valor or 'N/A'}")
    if all(linea.endswith(": N/A") for linea in lineas):
        return None
    return "\n".join(lineas)


def tiene_analisis(oportunidad: Oportunidad) -> bool:
    """¿Se escribió al menos una de las 6M?"""
    return any((getattr(oportunidad, campo, None) or "").strip()
               for campo, _ in CAMPOS_6M)


# ── El ciclo ─────────────────────────────────────────────────────────

def validar_transicion(oportunidad: Oportunidad, nuevo: str) -> None:
    """
    Deja pasar solo los cambios de estado que tienen sentido.

    No es burocracia: cada guarda evita un caso real. Sin causa raíz las
    acciones atacan el síntoma; sin verificación se cierra sin saber si
    funcionó, que es la observación clásica de una auditoría.

    Qué se exige depende del tratamiento — el formato lo declara en sus
    propios encabezados: el análisis de causas aplica a OMP y AC, la
    corrección solo a AC, el beneficio solo a AM.
    """
    if nuevo == ESTADO_DESCARTADA:
        if oportunidad.estado == "cerrada":
            raise HTTPException(
                status_code=400,
                detail="Una oportunidad ya cerrada no se puede descartar.",
            )
        return

    if nuevo not in ESTADOS:
        raise HTTPException(
            status_code=400,
            detail=f"Estado inválido. Usa uno de: {', '.join(ESTADOS)}.",
        )

    if oportunidad.estado == "cerrada":
        raise HTTPException(
            status_code=400,
            detail=("Esta oportunidad ya está cerrada. Si el problema volvió, "
                    "abre una nueva: el historial de la anterior no se toca."),
        )

    if nuevo == "ejecucion":
        if oportunidad.pide_causa and not (oportunidad.causa_raiz or "").strip():
            raise HTTPException(
                status_code=400,
                detail=("Falta la causa raíz. Escríbela antes de pasar a ejecución: "
                        "sin ella las acciones atacan el síntoma y el problema "
                        "vuelve a aparecer."),
            )
        if oportunidad.pide_correccion and not (oportunidad.correccion or "").strip():
            raise HTTPException(
                status_code=400,
                detail=("Falta la corrección. Una acción correctiva dice primero "
                        "qué se hizo para tapar el hueco de inmediato, y aparte "
                        "qué se hará para que no vuelva a pasar."),
            )
        if oportunidad.pide_beneficio and not (oportunidad.beneficio_mejora or "").strip():
            raise HTTPException(
                status_code=400,
                detail=("Falta el beneficio de la mejora. Una acción de mejora no "
                        "corrige un problema, así que lo que hay que justificar "
                        "es para qué vale la pena hacerla."),
            )

    if nuevo == "verificacion" and not oportunidad.acciones:
        raise HTTPException(
            status_code=400,
            detail=("No hay acciones registradas. Agrega al menos una antes de "
                    "verificar: no hay nada cuya eficacia se pueda medir."),
        )

    if nuevo == "cerrada":
        if oportunidad.eficaz is None:
            raise HTTPException(
                status_code=400,
                detail=("Antes de cerrar hay que verificar si funcionó. Registra la "
                        "verificación de eficacia con el resultado del indicador."),
            )
        if oportunidad.validado_sgc_en is None:
            raise HTTPException(
                status_code=400,
                detail=("Falta que Calidad valide el cierre. En el formato del SGC "
                        "el cierre lo firma alguien: solicítale a Calidad que revise "
                        "la evidencia y la dé por cerrada."),
            )


def cambiar_estado(db: Session, oportunidad: Oportunidad, nuevo: str,
                   usuario_id: int | None = None) -> Oportunidad:
    validar_transicion(oportunidad, nuevo)

    anterior = oportunidad.estado
    oportunidad.estado = nuevo
    if nuevo in ("cerrada", ESTADO_DESCARTADA):
        oportunidad.fecha_cierre = _ahora()
    else:
        oportunidad.fecha_cierre = None

    registrar_cambio(db, oportunidad.id, "estado", anterior, nuevo, usuario_id)
    db.commit()
    db.refresh(oportunidad)
    return oportunidad


def validar_cierre_sgc(db: Session, oportunidad: Oportunidad, usuario_id: int,
                       nota: str | None = None) -> Oportunidad:
    """
    El visto bueno de Calidad sobre la evidencia.

    Es un paso aparte de la verificación de eficacia a propósito: quien
    ejecuta la acción dice si el indicador mejoró, y el SGC dice si la
    evidencia de eso alcanza. Juntarlos en un solo botón era dejar que el
    mismo que hizo el trabajo lo diera por bueno.
    """
    if oportunidad.esta_cerrada:
        raise HTTPException(
            status_code=400,
            detail="Esta oportunidad ya está cerrada: no hay nada que validar.",
        )
    if oportunidad.eficaz is None:
        raise HTTPException(
            status_code=400,
            detail=("Todavía no hay verificación de eficacia. Calidad valida sobre "
                    "un resultado, no sobre una promesa."),
        )

    oportunidad.validado_sgc_por = usuario_id
    oportunidad.validado_sgc_en = _ahora()
    if nota is not None:
        oportunidad.nota_sgc = nota

    db.commit()
    db.refresh(oportunidad)
    return oportunidad


# ── Verificación de eficacia ─────────────────────────────────────────

def periodo_siguiente(anio: int, mes: int) -> tuple[int, int]:
    return (anio + 1, 1) if mes == 12 else (anio, mes + 1)


def medicion_de_verificacion(db: Session, oportunidad: Oportunidad):
    """
    La medición con la que se juzga si la OMP funcionó: la del mes siguiente
    al que la disparó.

    Devuelve None mientras no exista — y eso no es un error, es que todavía
    no se puede verificar. Es la diferencia entre pedirle a alguien que
    espere y hacerle creer que se le olvidó algo.
    """
    if not oportunidad.indicador_id or not oportunidad.periodo_anio:
        return None

    anio, mes = periodo_siguiente(oportunidad.periodo_anio, oportunidad.periodo_mes)
    return (
        db.query(Medicion)
        .filter(Medicion.indicador_id == oportunidad.indicador_id,
                Medicion.anio == anio, Medicion.mes == mes)
        .first()
    )


def evaluar_mejora(indicador: Indicador, valor_inicial, valor_nuevo) -> bool | None:
    """
    ¿El indicador mejoró?

    Depende de hacia dónde mejora: subir los reprocesos es malo y subir la
    satisfacción es bueno. Es la misma regla que usa el semáforo, no una
    interpretación nueva.
    """
    if valor_inicial is None or valor_nuevo is None or indicador is None:
        return None
    inicial, nuevo = float(valor_inicial), float(valor_nuevo)
    if nuevo == inicial:
        return False
    return nuevo > inicial if indicador.direccion == "arriba" else nuevo < inicial


def sugerir_verificacion(db: Session, oportunidad: Oportunidad) -> dict:
    """
    Lo que la pantalla necesita para proponer la verificación ya resuelta:
    el valor de antes, el de después y si eso es una mejora.

    El backend calcula y el frontend presenta: si la pantalla decidiera sola
    si un valor mejoró, tendría que conocer la dirección del indicador y
    tarde o temprano diría lo contrario que el semáforo.
    """
    medicion = medicion_de_verificacion(db, oportunidad)
    if medicion is None:
        anio = mes = None
        if oportunidad.periodo_anio:
            anio, mes = periodo_siguiente(oportunidad.periodo_anio, oportunidad.periodo_mes)
        return {
            "hay_medicion": False,
            "periodo_esperado": {"anio": anio, "mes": mes},
            "valor_inicial": oportunidad.valor_inicial,
            "valor_nuevo": None,
            "mejoro": None,
            "verificacion_planeada": oportunidad.verificacion_planeada,
        }

    mejoro = evaluar_mejora(oportunidad.indicador, oportunidad.valor_inicial, medicion.valor)
    return {
        "hay_medicion": True,
        "periodo_esperado": {"anio": medicion.anio, "mes": medicion.mes},
        "valor_inicial": oportunidad.valor_inicial,
        "valor_nuevo": medicion.valor,
        "mejoro": mejoro,
        "verificacion_planeada": oportunidad.verificacion_planeada,
    }


def registrar_verificacion(db: Session, oportunidad: Oportunidad,
                           eficaz: bool, nota: str | None,
                           valor_verificado=None,
                           usuario_id: int | None = None) -> Oportunidad:
    """
    Deja constancia de si funcionó.

    Si NO fue eficaz la oportunidad vuelve a análisis en vez de cerrarse: el
    problema sigue ahí, y darlo por cerrado es exactamente lo que un auditor
    busca. Si fue eficaz queda lista para que Calidad valide, pero no se
    cierra sola — cerrar es una decisión de alguien, con nombre.
    """
    anterior = oportunidad.eficaz
    oportunidad.eficaz = eficaz
    oportunidad.nota_eficacia = nota
    if valor_verificado is not None:
        oportunidad.valor_verificado = valor_verificado

    if not eficaz:
        oportunidad.estado = "analisis"
        # Una verificación que dice que no funcionó invalida el visto bueno
        # anterior: si quedara, la siguiente vuelta se cerraría con la firma
        # de una evidencia que ya se sabe insuficiente.
        oportunidad.validado_sgc_por = None
        oportunidad.validado_sgc_en = None
    elif oportunidad.estado != "cerrada":
        oportunidad.estado = "verificacion"

    registrar_cambio(db, oportunidad.id, "eficaz", anterior, eficaz, usuario_id)
    db.commit()
    db.refresh(oportunidad)
    return oportunidad


# ── Lo que se muestra en Indicadores y en el inicio ───────────────────

def indicadores_en_rojo_sin_omp(db: Session, tenant_id: int,
                                ids_en_rojo: list[int]) -> list[int]:
    """
    De los indicadores en rojo, cuáles no tienen ninguna OMP abierta.

    Es el dato que hoy no existe en ninguna parte: un indicador en rojo sin
    oportunidad es un problema que nadie está trabajando.
    """
    if not ids_en_rojo:
        return []

    con_omp = (
        db.query(Oportunidad.indicador_id)
        .filter(Oportunidad.tenant_id == tenant_id,
                Oportunidad.indicador_id.in_(ids_en_rojo),
                Oportunidad.estado.notin_(["cerrada", ESTADO_DESCARTADA]))
        .distinct()
        .all()
    )
    atendidos = {fila[0] for fila in con_omp}
    return [i for i in ids_en_rojo if i not in atendidos]
