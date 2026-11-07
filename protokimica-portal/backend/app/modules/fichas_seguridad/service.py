"""
Fichas de seguridad: la lógica que no es de un endpoint.

Reglas que importan:

- **Se valida antes de guardar el archivo.** Subir un PDF de 10 MB para
  enterarse después de que el nombre ya existe deja un archivo huérfano; por
  eso el router llama primero a `validar_*` y solo después a `guardar_pdf`.
  Si aun así el guardado en base falla, el archivo se borra.
- **Solo PDF.** `guardar_documento_privado` también acepta Excel y mira el
  CONTENIDO, no la extensión; aquí se rechaza lo que no sea PDF y se borra lo
  que ya se hubiera escrito.
- **Una versión nueva queda vigente y las demás se conservan.** Nunca se
  borra una versión por subir otra: lo que se entregó a un cliente hace un
  año tiene que poder consultarse.
- **Borrar protege el histórico**: 409 diciendo cuántas versiones se
  perderían y ofreciendo desactivar; el borrado total se pide a propósito con
  `incluir_versiones=true`.
"""
import os
import re
import unicodedata
from datetime import date

from fastapi import HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.core.archivos import guardar_documento_privado, ruta_documento_privado
from app.core.dias_habiles import hoy
from app.models.fichas_seguridad import (
    MAX_CODIGO, MAX_NOMBRE, MAX_OBSERVACIONES, MAX_VERSION, MIN_NOMBRE, FdsFicha, FdsVersion,
)
from app.models.user import User
from app.modules.fichas_seguridad.schemas import FichaEditar, VersionEditar

# Carpeta dentro de DOCUMENTOS_DIR.
SUBCARPETA = "fichas_seguridad"
ESTADOS_LISTA = ("activas", "inactivas", "todas")


# ── Texto ─────────────────────────────────────────────────────

def normalizar(texto: str | None) -> str:
    """Sin tildes, sin mayúsculas y con los espacios colapsados: «Ácido  Acético» -> «acido acetico»."""
    sin = unicodedata.normalize("NFKD", texto or "")
    sin = "".join(c for c in sin if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", sin).strip().casefold()


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def _iso(valor) -> str | None:
    return valor.isoformat() if valor else None


# ── Búsqueda de lo que ya existe ──────────────────────────────

def obtener_ficha(db: Session, tenant_id: int, ficha_id: int) -> FdsFicha:
    ficha = (
        db.query(FdsFicha)
        .options(selectinload(FdsFicha.versiones).selectinload(FdsVersion.autor))
        .filter(FdsFicha.id == ficha_id, FdsFicha.tenant_id == tenant_id)
        .first()
    )
    if ficha is None:
        raise HTTPException(
            status_code=404,
            detail="No encontramos esa ficha de seguridad. Puede que la hayan eliminado: actualiza la lista.",
        )
    return ficha


def obtener_version(db: Session, tenant_id: int, version_id: int) -> FdsVersion:
    """La versión, solo si su ficha es de la empresa de quien pregunta."""
    version = (
        db.query(FdsVersion).join(FdsFicha, FdsFicha.id == FdsVersion.ficha_id)
        .filter(FdsVersion.id == version_id, FdsFicha.tenant_id == tenant_id)
        .first()
    )
    if version is None:
        raise HTTPException(
            status_code=404,
            detail="No encontramos esa versión de la ficha. Puede que la hayan eliminado: actualiza la lista.",
        )
    return version


# ── Serialización ─────────────────────────────────────────────

def serializar_version(v: FdsVersion) -> dict:
    return {
        "id": v.id,
        "version": v.version,
        "fecha_emision": _iso(v.fecha_emision),
        "nombre_original": v.nombre_original,
        "tamano": v.tamano,
        "vigente": bool(v.vigente),
        "observaciones": v.observaciones,
        "subida_por_nombre": v.subida_por_nombre,
        "subida_en": _iso(v.subida_en),
    }


def serializar_ficha(f: FdsFicha, con_versiones: bool = False) -> dict:
    vigente = f.vigente
    datos = {
        "id": f.id,
        "codigo_producto": f.codigo_producto,
        "nombre_producto": f.nombre_producto,
        "activa": bool(f.activa),
        "total_versiones": len(f.versiones),
        "vigente": serializar_version(vigente) if vigente else None,
        "creada_en": _iso(f.creada_en),
    }
    if con_versiones:
        datos["versiones"] = [serializar_version(v) for v in f.versiones]
    return datos


# ── Lista ─────────────────────────────────────────────────────

def _escapar_like(palabra: str) -> str:
    return palabra.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def listar(db: Session, tenant_id: int, q: str | None, estado: str) -> dict:
    """
    Cada palabra del buscador tiene que estar, en cualquier orden y sin
    tildes, en el nombre o el código: quien busca «acetico acido» y quien
    busca «AC-10» encuentran la misma ficha.
    """
    if estado not in ESTADOS_LISTA:
        raise HTTPException(
            status_code=400,
            detail=f"El estado «{estado}» no existe. Usa uno de: {', '.join(ESTADOS_LISTA)}.",
        )
    consulta = (
        db.query(FdsFicha)
        .options(selectinload(FdsFicha.versiones).selectinload(FdsVersion.autor))
        .filter(FdsFicha.tenant_id == tenant_id)
    )
    if estado == "activas":
        consulta = consulta.filter(FdsFicha.activa.is_(True))
    elif estado == "inactivas":
        consulta = consulta.filter(FdsFicha.activa.is_(False))
    for palabra in normalizar(q).split():
        consulta = consulta.filter(FdsFicha.nombre_busqueda.like(f"%{_escapar_like(palabra)}%", escape="\\"))
    fichas = consulta.order_by(FdsFicha.nombre_busqueda, FdsFicha.id).all()
    return {"total": len(fichas), "fichas": [serializar_ficha(f) for f in fichas]}


# ── Validación de lo que escribe la gente ─────────────────────

def _limpiar_nombre(nombre: str | None) -> str:
    nombre = re.sub(r"\s+", " ", (nombre or "").strip())
    if len(nombre) < MIN_NOMBRE:
        raise HTTPException(
            status_code=400,
            detail=f"Escribe el nombre del producto (mínimo {MIN_NOMBRE} letras): así se encuentra la ficha en el buscador.",
        )
    if len(nombre) > MAX_NOMBRE:
        raise HTTPException(status_code=400, detail=f"El nombre del producto no puede pasar de {MAX_NOMBRE} caracteres.")
    return nombre


def _limpiar_codigo(codigo: str | None) -> str | None:
    """Opcional. En mayúsculas: «mp01» y «MP01» son el mismo código y no deben convivir."""
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    if len(codigo) > MAX_CODIGO:
        raise HTTPException(status_code=400, detail=f"El código del producto no puede pasar de {MAX_CODIGO} caracteres.")
    return codigo


def _limpiar_version(version: str | None) -> str:
    version = (version or "").strip()
    if not version:
        raise HTTPException(
            status_code=400,
            detail="Escribe la versión tal como aparece en el encabezado de la ficha (por ejemplo «10»).",
        )
    if len(version) > MAX_VERSION:
        raise HTTPException(status_code=400, detail=f"La versión no puede pasar de {MAX_VERSION} caracteres.")
    return version


def _limpiar_fecha(fecha: date | None) -> date:
    if fecha is None:
        raise HTTPException(
            status_code=400,
            detail="Indica la fecha de emisión que aparece en el encabezado de la ficha.",
        )
    if fecha > hoy():
        raise HTTPException(
            status_code=400,
            detail="La fecha de emisión no puede ser futura. Revisa la que trae el encabezado de la ficha.",
        )
    return fecha


def _limpiar_observaciones(texto: str | None) -> str | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    if len(texto) > MAX_OBSERVACIONES:
        raise HTTPException(status_code=400, detail=f"Las observaciones no pueden pasar de {MAX_OBSERVACIONES} caracteres.")
    return texto


def _exigir_unica(db: Session, tenant_id: int, nombre: str, codigo: str | None, excepto_id: int | None = None) -> None:
    """409 si ya hay una ficha con ese producto o ese código: lo que falta es una versión, no otra ficha."""
    consulta = db.query(FdsFicha).filter(FdsFicha.tenant_id == tenant_id)
    if excepto_id is not None:
        consulta = consulta.filter(FdsFicha.id != excepto_id)
    clave = normalizar(nombre)
    for existente in consulta.all():
        if normalizar(existente.nombre_producto) == clave:
            raise HTTPException(
                status_code=409,
                detail=f"Ya existe una ficha para «{existente.nombre_producto}». "
                       "Ábrela y súbele la versión nueva en vez de crear otra.",
            )
        if codigo and existente.codigo_producto == codigo:
            raise HTTPException(
                status_code=409,
                detail=f"El código {codigo} ya es de la ficha «{existente.nombre_producto}». "
                       "Si es el mismo producto, súbele la versión nueva a esa ficha.",
            )


def validar_ficha(
    db: Session, tenant_id: int, nombre_producto, codigo_producto, version, fecha_emision, observaciones,
) -> dict:
    """Todo lo de una ficha nueva, limpio y comprobado ANTES de guardar el archivo."""
    nombre = _limpiar_nombre(nombre_producto)
    codigo = _limpiar_codigo(codigo_producto)
    datos = {
        "nombre_producto": nombre,
        "codigo_producto": codigo,
        "version": _limpiar_version(version),
        "fecha_emision": _limpiar_fecha(fecha_emision),
        "observaciones": _limpiar_observaciones(observaciones),
    }
    _exigir_unica(db, tenant_id, nombre, codigo)
    return datos


def validar_version(ficha: FdsFicha, version, fecha_emision, observaciones) -> dict:
    if not ficha.activa:
        raise HTTPException(
            status_code=409,
            detail="Esta ficha está desactivada. Reactívala para subirle una versión nueva.",
        )
    version = _limpiar_version(version)
    for existente in ficha.versiones:
        if normalizar(existente.version) == normalizar(version):
            raise HTTPException(
                status_code=409,
                detail=f"Esta ficha ya tiene la versión {existente.version}. "
                       "Si es una corrección, súbela con el número de versión nuevo que trae el documento.",
            )
    return {
        "version": version,
        "fecha_emision": _limpiar_fecha(fecha_emision),
        "observaciones": _limpiar_observaciones(observaciones),
    }


# ── Archivos ──────────────────────────────────────────────────

def _borrar_archivo(ruta_relativa: str) -> None:
    """Quita un archivo del disco; si ya no está, no pasa nada: se llama al limpiar."""
    try:
        os.remove(ruta_documento_privado(ruta_relativa))
    except (HTTPException, OSError):
        pass


async def guardar_pdf(archivo: UploadFile) -> dict:
    """Guarda el PDF fuera de lo público. Cualquier otra cosa se rechaza y no queda en disco."""
    info = await guardar_documento_privado(archivo, SUBCARPETA)
    if info["tipo"] != "pdf":
        _borrar_archivo(info["ruta"])
        raise HTTPException(
            status_code=400,
            detail="Las fichas de seguridad se suben en PDF. Si la tienes en Excel o Word, "
                   "expórtala a PDF y vuelve a subirla.",
        )
    return info


# ── Escritura ─────────────────────────────────────────────────

def _nueva_version(usuario: User, datos: dict, info: dict) -> FdsVersion:
    return FdsVersion(
        version=datos["version"], fecha_emision=datos["fecha_emision"],
        nombre_original=info["nombre_original"], ruta=info["ruta"], tamano=info["tamano"],
        vigente=True, observaciones=datos["observaciones"], subida_por=usuario.id,
    )


def registrar_ficha(db: Session, usuario: User, datos: dict, info: dict) -> FdsFicha:
    ficha = FdsFicha(
        tenant_id=usuario.tenant_id,
        codigo_producto=datos["codigo_producto"],
        nombre_producto=datos["nombre_producto"],
        nombre_busqueda=normalizar(f"{datos['nombre_producto']} {datos['codigo_producto'] or ''}"),
        creada_por=usuario.id,
    )
    ficha.versiones.append(_nueva_version(usuario, datos, info))
    db.add(ficha)
    try:
        db.commit()
    except Exception:
        db.rollback()
        _borrar_archivo(info["ruta"])
        raise
    return obtener_ficha(db, usuario.tenant_id, ficha.id)


def registrar_version(db: Session, usuario: User, ficha: FdsFicha, datos: dict, info: dict) -> FdsFicha:
    """La nueva queda vigente; las anteriores se conservan, solo dejan de serlo."""
    for anterior in ficha.versiones:
        anterior.vigente = False
    ficha.versiones.append(_nueva_version(usuario, datos, info))
    try:
        db.commit()
    except Exception:
        db.rollback()
        _borrar_archivo(info["ruta"])
        raise
    return obtener_ficha(db, usuario.tenant_id, ficha.id)


def hacer_vigente(db: Session, ficha: FdsFicha, version: FdsVersion) -> FdsFicha:
    """Devuelve una versión anterior a vigente (por ejemplo, si se subió una por error). No borra nada."""
    for v in ficha.versiones:
        v.vigente = v.id == version.id
    db.commit()
    return obtener_ficha(db, ficha.tenant_id, ficha.id)


def editar(db: Session, ficha: FdsFicha, datos: FichaEditar) -> FdsFicha:
    enviados = datos.model_fields_set
    nombre = _limpiar_nombre(datos.nombre_producto) if "nombre_producto" in enviados else ficha.nombre_producto
    codigo = _limpiar_codigo(datos.codigo_producto) if "codigo_producto" in enviados else ficha.codigo_producto
    if "nombre_producto" in enviados or "codigo_producto" in enviados:
        _exigir_unica(db, ficha.tenant_id, nombre, codigo, excepto_id=ficha.id)
        ficha.nombre_producto = nombre
        ficha.codigo_producto = codigo
        ficha.nombre_busqueda = normalizar(f"{nombre} {codigo or ''}")
    if datos.activa is not None:
        ficha.activa = datos.activa
    db.commit()
    return obtener_ficha(db, ficha.tenant_id, ficha.id)


def editar_version(db: Session, ficha: FdsFicha, version: FdsVersion, datos: VersionEditar) -> FdsFicha:
    """
    Corrige el número, la fecha o las observaciones de una versión ya subida.
    El archivo no se toca (eso es subir otra versión) y el número sigue sin
    poder repetirse dentro de la ficha. Se permite aunque la ficha esté
    desactivada: corregir un dato mal escrito no es seguir usándola.
    """
    enviados = datos.model_fields_set
    if "version" in enviados:
        nuevo = _limpiar_version(datos.version)
        for otra in ficha.versiones:
            if otra.id != version.id and normalizar(otra.version) == normalizar(nuevo):
                raise HTTPException(
                    status_code=409,
                    detail=f"Esta ficha ya tiene la versión {otra.version}. "
                           "Revisa el número que trae el encabezado del documento.",
                )
        version.version = nuevo
    if "fecha_emision" in enviados:
        version.fecha_emision = _limpiar_fecha(datos.fecha_emision)
    if "observaciones" in enviados:
        version.observaciones = _limpiar_observaciones(datos.observaciones)
    db.commit()
    return obtener_ficha(db, ficha.tenant_id, ficha.id)


def eliminar(db: Session, ficha: FdsFicha, incluir_versiones: bool) -> None:
    n = len(ficha.versiones)
    if not incluir_versiones:
        raise HTTPException(
            status_code=409,
            detail=f"Esta ficha tiene {_plural(n, 'versión guardada', 'versiones guardadas')} y borrarla las pierde "
                   "todas. Si solo dejó de usarse, desactívala: deja de ofrecerse y conserva su historia. "
                   f"Si de verdad hay que borrarla, confírmalo y se eliminan {_plural(n, 'la versión', 'las versiones')}.",
        )
    rutas = [v.ruta for v in ficha.versiones]
    db.delete(ficha)
    db.commit()
    for ruta in rutas:
        _borrar_archivo(ruta)
