"""
Endpoints del módulo de Indicadores.

Reutiliza `guardar_archivo` de PQRS para la evidencia y las dependencias de
permisos del core: `gerencia` consulta todo el tablero pero no registra ni
configura nada, igual que en el resto del portal.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.models.indicadores import Indicador, Medicion, HistorialMedicion
from app.models.user import User
from app.modules.indicadores import fuentes, service
from app.modules.indicadores.como_vamos import construir_como_vamos
from app.modules.indicadores.schemas import (
    IndicadorCreate, IndicadorUpdate, IndicadorOut, MedicionOut, HistorialOut,
)
from app.modules.pqrs.service import guardar_archivo

router = APIRouter(prefix="/indicadores", tags=["Indicadores"])


def _get_indicador_o_404(db: Session, indicador_id: int, tenant_id: int) -> Indicador:
    indicador = db.query(Indicador).filter(
        Indicador.id == indicador_id, Indicador.tenant_id == tenant_id,
    ).first()
    if not indicador:
        raise HTTPException(status_code=404, detail="Indicador no encontrado.")
    return indicador


def _validar_periodo(anio: int, mes: int) -> None:
    if not (1 <= mes <= 12):
        raise HTTPException(status_code=400, detail="El mes debe estar entre 1 y 12.")
    if not (2000 <= anio <= 2100):
        raise HTTPException(status_code=400, detail="Año fuera de rango.")


# ── Catálogo y tablero ──────────────────────────────────────────

@router.get("/catalogo")
def catalogo_automatico(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    Indicadores que el portal sabe calcular solo, con su fórmula y unidad
    sugerida. Alimenta el desplegable al crear un indicador automático.

    Incluye una entrada por cada encuesta activa: esas no se pueden escribir
    de antemano porque se crean desde la interfaz, así que se leen de la base.
    """
    return fuentes.catalogo_publico(db, tenant_id)


@router.get("/tablero")
def tablero(
    anio: int | None = None,
    mes: int | None = None,
    area: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    El tablero de un periodo. Sin parámetros abre en el último mes cerrado:
    el mes en curso siempre está incompleto y mostrarlo por defecto haría ver
    todo en rojo sin motivo.
    """
    if anio is None or mes is None:
        anio_def, mes_def = service.periodo_por_defecto()
        anio, mes = anio or anio_def, mes or mes_def
    _validar_periodo(anio, mes)
    return service.construir_tablero(db, tenant_id, anio, mes, area)


@router.get("/como-vamos")
def como_vamos(
    anio: int | None = None,
    mes: int | None = None,
    alcance: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    usuario: User = Depends(get_current_user),
):
    """
    La portada gerencial: estado del mes, qué se movió, cómo va cada área y
    el año en matriz. Todo calculado aquí — el frontend solo pinta.

    `alcance` es "empresa" o "area". A quien no le corresponde ver la empresa
    se le devuelve su área sin protestar; la respuesta trae `puede_cambiar`
    para que la interfaz sepa si mostrar el interruptor.
    """
    if anio is None or mes is None:
        anio_def, mes_def = service.periodo_por_defecto()
        anio, mes = anio or anio_def, mes or mes_def
    _validar_periodo(anio, mes)
    return construir_como_vamos(db, tenant_id, anio, mes, usuario, alcance)


# ── Definición de indicadores ───────────────────────────────────

@router.get("", response_model=list[IndicadorOut])
def listar_indicadores(
    incluir_inactivos: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    query = db.query(Indicador).filter(Indicador.tenant_id == tenant_id)
    if not incluir_inactivos:
        query = query.filter(Indicador.activo.is_(True))
    return query.order_by(Indicador.orden, Indicador.nombre).all()


@router.post("", response_model=IndicadorOut, status_code=status.HTTP_201_CREATED)
def crear_indicador(
    payload: IndicadorCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    if payload.tipo_captura == "automatico":
        if not payload.fuente_automatica:
            raise HTTPException(
                status_code=400,
                detail="Un indicador automático necesita una fuente del catálogo.",
            )
        # Se valida contra el catálogo COMPLETO, que incluye las encuestas:
        # esas no están en CATALOGO porque se crean desde la interfaz.
        if not fuentes.existe_fuente(payload.fuente_automatica, db, tenant_id):
            raise HTTPException(
                status_code=400,
                detail=f"La fuente '{payload.fuente_automatica}' no existe en el catálogo.",
            )

    indicador = Indicador(tenant_id=tenant_id, **payload.model_dump())
    db.add(indicador)
    db.commit()
    db.refresh(indicador)
    return indicador


@router.get("/{indicador_id}")
def obtener_indicador(
    indicador_id: int,
    anio: int | None = None,
    mes: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """Ficha completa con la serie del año, para la vista de detalle."""
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id)
    if anio is None or mes is None:
        anio_def, mes_def = service.periodo_por_defecto()
        anio, mes = anio or anio_def, mes or mes_def
    _validar_periodo(anio, mes)
    return service.resumen_indicador(indicador, anio, mes)


@router.patch("/{indicador_id}", response_model=IndicadorOut)
def actualizar_indicador(
    indicador_id: int,
    payload: IndicadorUpdate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id)
    cambios = payload.model_dump(exclude_unset=True)

    fuente = cambios.get("fuente_automatica", indicador.fuente_automatica)
    captura = cambios.get("tipo_captura", indicador.tipo_captura)
    if captura == "automatico" and not fuentes.existe_fuente(fuente or "", db, tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Un indicador automático necesita una fuente válida del catálogo.",
        )

    for campo, valor in cambios.items():
        setattr(indicador, campo, valor)
    db.commit()
    db.refresh(indicador)
    return indicador


@router.delete("/{indicador_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_indicador(
    indicador_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    """
    Borra el indicador y todo su histórico. Si ya tiene mediciones responde
    409: perder la serie histórica de un indicador es irreversible y casi
    siempre lo que se quiere es desactivarlo (`activo=false`), que lo saca
    del tablero conservando los datos.
    """
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id)
    total = db.query(Medicion).filter(Medicion.indicador_id == indicador_id).count()
    if total:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Este indicador tiene {total} medición(es) registradas. "
                "Desactívalo para sacarlo del tablero sin perder el histórico."
            ),
        )
    db.delete(indicador)
    db.commit()


# ── Mediciones ──────────────────────────────────────────────────

@router.post("/{indicador_id}/mediciones", response_model=MedicionOut,
             status_code=status.HTTP_201_CREATED)
async def registrar_medicion(
    indicador_id: int,
    anio: int = Form(...),
    mes: int = Form(...),
    valor: float | None = Form(None),
    numerador: float | None = Form(None),
    denominador: float | None = Form(None),
    observacion: str | None = Form(None),
    motivo: str | None = Form(None),
    evidencia: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
):
    """
    Registra o corrige el valor de un mes. Si ya existía, se actualiza y el
    cambio queda en el historial con su motivo.
    """
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id)
    _validar_periodo(anio, mes)

    if indicador.es_automatico:
        raise HTTPException(
            status_code=400,
            detail="Este indicador se calcula solo. Usa 'Recalcular' en vez de registrarlo a mano.",
        )

    if indicador.tipo_captura == "razon":
        if numerador is None or denominador is None:
            raise HTTPException(
                status_code=400,
                detail="Este indicador se captura con numerador y denominador; faltan datos.",
            )
        if denominador == 0:
            raise HTTPException(
                status_code=400,
                detail="El denominador no puede ser cero. Si en el periodo no hubo casos, deja el mes sin registrar.",
            )
        bruto = numerador / denominador
        valor = round(bruto * 100, 4) if indicador.unidad == "porcentaje" else round(bruto, 4)
    elif valor is None:
        raise HTTPException(status_code=400, detail="Falta el valor del indicador.")

    ruta = None
    if evidencia is not None:
        ruta = await guardar_archivo(evidencia, "indicadores")
    elif indicador.requiere_evidencia:
        existente = (
            db.query(Medicion)
            .filter(Medicion.indicador_id == indicador_id,
                    Medicion.anio == anio, Medicion.mes == mes)
            .first()
        )
        if not (existente and existente.evidencia):
            raise HTTPException(
                status_code=400,
                detail="Este indicador exige adjuntar la evidencia del cálculo.",
            )

    medicion = (
        db.query(Medicion)
        .filter(Medicion.indicador_id == indicador_id,
                Medicion.anio == anio, Medicion.mes == mes)
        .first()
    )
    es_correccion = medicion is not None
    valor_anterior = float(medicion.valor) if es_correccion and medicion.valor is not None else None

    if not medicion:
        medicion = Medicion(indicador_id=indicador_id, anio=anio, mes=mes)
        db.add(medicion)

    medicion.valor = valor
    medicion.numerador = numerador
    medicion.denominador = denominador
    medicion.observacion = observacion
    medicion.registrado_por = current_user.id
    medicion.registrado_en = datetime.now(timezone.utc)
    if ruta:
        medicion.evidencia = ruta

    # Solo se registra en el historial cuando el número cambia de verdad:
    # volver a guardar lo mismo no es un cambio que a gerencia le interese.
    if es_correccion and valor_anterior != valor:
        db.add(HistorialMedicion(
            indicador_id=indicador_id, anio=anio, mes=mes,
            valor_anterior=valor_anterior, valor_nuevo=valor,
            motivo=motivo, usuario_id=current_user.id,
        ))

    db.commit()
    db.refresh(medicion)
    return medicion


@router.post("/{indicador_id}/calcular", response_model=MedicionOut)
def calcular_indicador(
    indicador_id: int,
    anio: int,
    mes: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id)
    if not indicador.es_automatico:
        raise HTTPException(
            status_code=400,
            detail="Este indicador se captura a mano; no hay nada que recalcular.",
        )
    _validar_periodo(anio, mes)

    medicion = service.calcular_automatico(db, indicador, tenant_id, anio, mes)
    db.commit()
    db.refresh(medicion)
    return medicion


@router.post("/calcular-periodo")
def calcular_periodo(
    anio: int,
    mes: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
):
    """
    Recalcula de una sola vez todos los indicadores automáticos del periodo.
    Es lo que se dispararía desde n8n el día 1 de cada mes.
    """
    _validar_periodo(anio, mes)
    automaticos = (
        db.query(Indicador)
        .filter(Indicador.tenant_id == tenant_id,
                Indicador.activo.is_(True),
                Indicador.tipo_captura == "automatico")
        .all()
    )

    calculados, errores = [], []
    for indicador in automaticos:
        try:
            medicion = service.calcular_automatico(db, indicador, tenant_id, anio, mes)
            calculados.append({
                "id": indicador.id, "nombre": indicador.nombre,
                "valor": float(medicion.valor) if medicion.valor is not None else None,
            })
        except Exception as e:
            # Un indicador roto no debe impedir que se calculen los demás.
            errores.append({"id": indicador.id, "nombre": indicador.nombre, "error": str(e)})

    db.commit()
    return {"periodo": f"{anio}-{mes:02d}", "calculados": calculados, "errores": errores}


@router.get("/{indicador_id}/historial", response_model=list[HistorialOut])
def historial_indicador(
    indicador_id: int,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    _get_indicador_o_404(db, indicador_id, tenant_id)
    return (
        db.query(HistorialMedicion)
        .filter(HistorialMedicion.indicador_id == indicador_id)
        .order_by(HistorialMedicion.fecha.desc())
        .all()
    )
