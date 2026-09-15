"""
Endpoints del módulo de Indicadores.

Reutiliza `guardar_archivo` de PQRS para la evidencia y las dependencias de
permisos del core: `gerencia` consulta todo el tablero pero no registra ni
configura nada, igual que en el resto del portal.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.areas import AREAS
from app.core.database import get_db
from app.core.deps import get_current_user, get_current_tenant_id, solo_lectura_no
from app.core.modulos import requiere_modulo, ve_todos_los_indicadores
from app.models.indicadores import (
    Indicador, Medicion, HistorialMedicion, ValorVariable, VariableIndicador,
)
from app.models.user import User
from app.modules.indicadores import formula as formulas
from app.modules.indicadores import fuentes, service
from app.modules.indicadores.como_vamos import construir_como_vamos
from app.modules.indicadores.schemas import (
    FormulaPrueba, FormulaResultado, IndicadorCreate, IndicadorUpdate, IndicadorOut,
    MedicionOut, HistorialOut,
)
from app.modules.pqrs.service import guardar_archivo

router = APIRouter(prefix="/indicadores", tags=["Indicadores"])


def _get_indicador_o_404(
    db: Session, indicador_id: int, tenant_id: int, usuario: User | None = None,
) -> Indicador:
    indicador = db.query(Indicador).filter(
        Indicador.id == indicador_id, Indicador.tenant_id == tenant_id,
    ).first()
    if not indicador:
        raise HTTPException(status_code=404, detail="Indicador no encontrado.")
    # 404 y no 403: un 403 confirmaría que el indicador existe.
    if (
        usuario is not None
        and not ve_todos_los_indicadores(usuario)
        and indicador.area != usuario.area
    ):
        raise HTTPException(status_code=404, detail="Indicador no encontrado.")
    return indicador


def _exigir_area_si_es_por_area(fuente: str | None, area: str | None) -> None:
    """Una fuente por área sin área no tiene con qué calcular: se dice al guardar, no meses después."""
    if fuentes.es_por_area(fuente) and not area:
        raise HTTPException(
            status_code=400,
            detail=(
                "Este indicador se calcula con los datos de un área: elige el área "
                "antes de guardarlo."
            ),
        )


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
    _: User = Depends(requiere_modulo("indicadores")),
):
    """
    Indicadores que el portal sabe calcular solo, con su fórmula y unidad
    sugerida. Alimenta el desplegable al crear un indicador automático.

    Incluye una entrada por cada encuesta activa: esas no se pueden escribir
    de antemano porque se crean desde la interfaz, así que se leen de la base.
    """
    return fuentes.catalogo_publico(db, tenant_id)


@router.post("/formula/probar", response_model=FormulaResultado)
def probar_formula(
    payload: FormulaPrueba,
    _: User = Depends(requiere_modulo("indicadores")),
):
    """
    Valida una fórmula a medio armar, la dice en palabras y, si vienen
    valores, la calcula.

    La pantalla la usa mientras se arma el indicador y mientras se digita un
    mes, para que el resultado que se ve sea el que calcula el servidor. No
    guarda nada. Va antes que `/{indicador_id}`.
    """
    letras = [v.letra.upper() for v in payload.variables]
    etiquetas = {v.letra.upper(): v.etiqueta for v in payload.variables}
    try:
        formulas.validar(payload.formula, letras)
        legible = formulas.legible(payload.formula, etiquetas)
    except formulas.ErrorFormula as e:
        return FormulaResultado(valida=False, error=str(e))

    valores = {k.upper(): v for k, v in payload.valores.items() if v is not None}
    if not set(letras) <= set(valores):
        return FormulaResultado(valida=True, legible=legible)
    try:
        return FormulaResultado(valida=True, legible=legible,
                                resultado=formulas.evaluar(payload.formula, valores))
    except formulas.DivisionPorCero:
        return FormulaResultado(valida=True, legible=legible, divide_por_cero=True)


# ── Gestión de OMP en cada área ─────────────────────────────────
#
# El indicador «Gestión de OMP» es uno por área, todos iguales salvo el área.
# Crearlos uno por uno con 21 áreas es la forma de que siempre falte alguno,
# así que hay un botón que crea los que falten. Van antes que `/{indicador_id}`.

NOMBRE_GESTION_OMP = "Gestión de OMP"
# Meta sugerida al crearlos; cada área la ajusta después en su ficha.
META_GESTION_OMP = {"meta": 80, "umbral_verde": 80, "umbral_amarillo": 60}


def _areas_con_gestion_omp(db: Session, tenant_id: int) -> set[str]:
    """Las áreas que ya lo tienen, activo o no: uno desactivado también cuenta."""
    return {
        area for (area,) in db.query(Indicador.area).filter(
            Indicador.tenant_id == tenant_id,
            Indicador.fuente_automatica == fuentes.CLAVE_GESTION_OMP,
        ).all() if area
    }


def _exigir_ver_toda_la_empresa(usuario: User) -> None:
    if not ve_todos_los_indicadores(usuario):
        raise HTTPException(
            status_code=403,
            detail=(
                "Crear el indicador en todas las áreas es de un administrador. "
                "Para tu área, créalo como cualquier indicador automático."
            ),
        )


@router.get("/gestion-omp")
def estado_gestion_omp(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    """En qué áreas falta el indicador, para decirlo antes de crearlo."""
    _exigir_ver_toda_la_empresa(current_user)
    existentes = _areas_con_gestion_omp(db, tenant_id)
    return {
        "faltantes": [a for a in AREAS if a not in existentes],
        "existentes": sorted(existentes),
    }


@router.post("/gestion-omp/crear-en-areas")
def crear_gestion_omp_en_areas(
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    """
    Crea «Gestión de OMP» en las áreas que no lo tienen. Pulsarlo dos veces
    no duplica: las que ya lo tienen se saltan, incluso si está desactivado
    — reactivarlo es decisión de esa área, no de este botón.
    """
    _exigir_ver_toda_la_empresa(current_user)
    existentes = _areas_con_gestion_omp(db, tenant_id)
    cfg = fuentes.CATALOGO[fuentes.CLAVE_GESTION_OMP]
    creados = []
    for area in AREAS:
        if area in existentes:
            continue
        db.add(Indicador(
            tenant_id=tenant_id, nombre=NOMBRE_GESTION_OMP, area=area,
            descripcion=cfg["descripcion"], formula_texto=cfg["formula"],
            unidad=cfg["unidad"], direccion=cfg["direccion"],
            tipo_captura="automatico", fuente_automatica=fuentes.CLAVE_GESTION_OMP,
            **META_GESTION_OMP,
        ))
        creados.append(area)
    db.commit()
    return {"creados": creados, "ya_tenian": sorted(existentes)}


@router.get("/tablero")
def tablero(
    anio: int | None = None,
    mes: int | None = None,
    area: str | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(requiere_modulo("indicadores")),
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

    # Un líder solo ve los indicadores de su área: son los que responde. El
    # filtro se impone aquí y no se puede saltar mandando otro `area`.
    if not ve_todos_los_indicadores(current_user):
        area = current_user.area

    return service.construir_tablero(db, tenant_id, anio, mes, area)


@router.get("/pendientes-de-registro")
def pendientes_de_registro(
    anio: int | None = None,
    mes: int | None = None,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(get_current_user),
):
    """
    Los indicadores manuales que faltan por registrar, agrupados por
    responsable y con su correo.

    Lo consume el recordatorio de cierre de mes. Devuelve a cada quien solo
    lo suyo: un correo con "te faltan 2" se atiende, uno con la lista de los
    40 de la empresa se archiva sin abrir.

    Los que no tienen responsable asignado van aparte — si nadie los reclama,
    nadie los registra.
    """
    if anio is None or mes is None:
        anio_def, mes_def = service.periodo_por_defecto()
        anio, mes = anio or anio_def, mes or mes_def
    _validar_periodo(anio, mes)

    tablero = service.construir_tablero(db, tenant_id, anio, mes)

    por_persona: dict[int, dict] = {}
    sin_responsable = []
    for ficha in tablero["pendientes"]:
        indicador = db.get(Indicador, ficha["id"])
        if indicador is None or not indicador.responsable_id:
            sin_responsable.append(ficha)
            continue
        grupo = por_persona.setdefault(indicador.responsable_id, [])
        grupo.append(ficha)

    destinatarios = []
    for usuario_id, fichas in por_persona.items():
        usuario = db.get(User, usuario_id)
        if not usuario or not usuario.email or not usuario.activo:
            sin_responsable.extend(fichas)
            continue
        destinatarios.append({
            "email": usuario.email,
            "nombre": usuario.nombre,
            "total": len(fichas),
            "indicadores": fichas,
        })

    destinatarios.sort(key=lambda d: -d["total"])
    return {
        "anio": anio,
        "mes": mes,
        "mes_nombre": service.MESES[mes - 1],
        "total": len(tablero["pendientes"]),
        "destinatarios": destinatarios,
        "sin_responsable": sin_responsable,
    }


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
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    query = db.query(Indicador).filter(Indicador.tenant_id == tenant_id)
    if not ve_todos_los_indicadores(current_user):
        query = query.filter(Indicador.area == current_user.area)
    if not incluir_inactivos:
        query = query.filter(Indicador.activo.is_(True))
    return query.order_by(Indicador.orden, Indicador.nombre).all()


@router.post("", response_model=IndicadorOut, status_code=status.HTTP_201_CREATED)
def crear_indicador(
    payload: IndicadorCreate,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
    __: User = Depends(requiere_modulo("indicadores")),
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
        _exigir_area_si_es_por_area(payload.fuente_automatica, payload.area)

    datos = payload.model_dump(exclude={"variables", "formula"})
    indicador = Indicador(tenant_id=tenant_id, **datos)
    if payload.tipo_captura == "formula":
        formula, variables = service.preparar_formula(
            payload.formula, [v.model_dump() for v in payload.variables],
        )
        indicador.formula = formula
        indicador.variables = [VariableIndicador(**v) for v in variables]
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
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    """Ficha completa con la serie del año, para la vista de detalle."""
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id, current_user)
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
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id, current_user)
    cambios = payload.model_dump(exclude_unset=True)

    fuente = cambios.get("fuente_automatica", indicador.fuente_automatica)
    captura = cambios.get("tipo_captura", indicador.tipo_captura)
    if captura == "automatico" and not fuentes.existe_fuente(fuente or "", db, tenant_id):
        raise HTTPException(
            status_code=400,
            detail="Un indicador automático necesita una fuente válida del catálogo.",
        )
    if captura == "automatico":
        _exigir_area_si_es_por_area(fuente, cambios.get("area", indicador.area))

    formula = cambios.pop("formula", None)
    variables = cambios.pop("variables", None)
    tenia_formula = indicador.tipo_captura == "formula"
    va_con_formula = captura == "formula"

    # Pasar a fórmula o dejar de serlo con meses ya registrados dejaría esos
    # meses con números que la nueva forma de captura no sabe leer.
    if tenia_formula != va_con_formula and indicador.mediciones:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Este indicador ya tiene {len(indicador.mediciones)} mes(es) registrados, "
                "así que no se puede cambiar entre fórmula y otra forma de captura. "
                "Crea un indicador nuevo con la forma correcta y desactiva este."
            ),
        )

    for campo, valor in cambios.items():
        setattr(indicador, campo, valor)

    if va_con_formula:
        service.aplicar_formula(
            db, indicador, formula,
            [v for v in variables] if variables is not None else None,
            current_user.id,
        )
    elif tenia_formula:
        indicador.formula = None
        indicador.variables = []
    db.commit()
    db.refresh(indicador)
    return indicador


@router.delete("/{indicador_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_indicador(
    indicador_id: int,
    incluir_mediciones: bool = False,
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    _: User = Depends(solo_lectura_no),
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    """
    Borra el indicador.

    Si tiene mediciones responde 409 y no borra nada: perder la serie
    histórica es irreversible, y casi siempre lo que se quiere es
    desactivarlo (activo=false), que lo saca del tablero sin perder datos.

    Con `incluir_mediciones=true` se borra con todo su histórico. Es para lo
    que de verdad hay que eliminar —los indicadores de prueba antes de salir
    a producción— y por eso hay que pedirlo a propósito: si el borrado total
    fuera lo que pasa por defecto, un clic de más se llevaría años de
    mediciones sin forma de recuperarlas.
    """
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id, current_user)
    total = db.query(Medicion).filter(Medicion.indicador_id == indicador_id).count()

    if total and not incluir_mediciones:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Este indicador tiene {total} medición(es) registradas. "
                "Desactívalo para sacarlo del tablero sin perder el histórico, "
                "o elimínalo con todo si son datos de prueba."
            ),
        )

    # Se borran a mano y no solo con la cascada de la base: así el resultado
    # es el mismo en Postgres y en SQLite, donde el borrado en cascada
    # depende de un PRAGMA que no siempre está activo.
    if total:
        db.query(HistorialMedicion).filter(
            HistorialMedicion.indicador_id == indicador_id
        ).delete(synchronize_session=False)
        ids_mediciones = db.query(Medicion.id).filter(Medicion.indicador_id == indicador_id)
        db.query(ValorVariable).filter(
            ValorVariable.medicion_id.in_(ids_mediciones)
        ).delete(synchronize_session=False)
        db.query(Medicion).filter(
            Medicion.indicador_id == indicador_id
        ).delete(synchronize_session=False)

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
    # Indicadores de fórmula: {"A": 45, "B": 50}, en JSON.
    variables: str | None = Form(None),
    analisis: str = Form(...),
    motivo: str | None = Form(None),
    evidencia: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    tenant_id: int = Depends(get_current_tenant_id),
    current_user: User = Depends(solo_lectura_no),
    _: User = Depends(requiere_modulo("indicadores")),
):
    """
    Registra o corrige el valor de un mes. Si ya existía, se actualiza y el
    cambio queda en el historial con su motivo.
    """
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id, current_user)
    _validar_periodo(anio, mes)

    analisis = analisis.strip()
    if not analisis:
        raise HTTPException(
            status_code=400,
            detail="Escribe el análisis del resultado: qué lo explica, para que quede en el histórico.",
        )

    if indicador.es_automatico:
        raise HTTPException(
            status_code=400,
            detail="Este indicador se calcula solo. Usa 'Recalcular' en vez de registrarlo a mano.",
        )

    valores_variables = None
    if indicador.tipo_captura == "formula":
        try:
            recibidos = json.loads(variables) if variables else {}
        except ValueError:
            recibidos = None
        if not isinstance(recibidos, dict):
            raise HTTPException(
                status_code=400,
                detail="No se entendieron los valores de las variables. Recarga la página e inténtalo de nuevo.",
            )
        valor, valores_variables = service.valor_por_formula(indicador, recibidos)
        numerador = denominador = None
    elif indicador.tipo_captura == "razon":
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
    if valores_variables is not None:
        service.guardar_variables(medicion, valores_variables)
    medicion.analisis = analisis
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
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    indicador = _get_indicador_o_404(db, indicador_id, tenant_id, current_user)
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
    __: User = Depends(requiere_modulo("indicadores")),
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
    current_user: User = Depends(requiere_modulo("indicadores")),
):
    _get_indicador_o_404(db, indicador_id, tenant_id, current_user)
    return (
        db.query(HistorialMedicion)
        .filter(HistorialMedicion.indicador_id == indicador_id)
        .order_by(HistorialMedicion.fecha.desc())
        .all()
    )
