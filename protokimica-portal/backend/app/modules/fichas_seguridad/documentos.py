"""
Documentos generados por Fichas de seguridad: leer, validar, generar, listar.

Reglas que importan:

- **Solo `producto` es obligatorio.** La lectura no siempre entiende todo y quien revisa
  completa lo que falte; un campo vacío no bloquea. El servidor dice qué
  quedó sin leer (`faltantes`) pero no decide por la persona.
- **El código sale del repositorio de fichas**, no de otro módulo: si el
  producto coincide con una ficha (mismo nombre sin tildes), se toma su código
  y se enlaza. Sin coincidencia el código queda vacío y se puede escribir.
- **Lo que se genera se guarda tal como se firmó** (`datos`), con su PDF en
  `DOCUMENTOS_DIR`: el historial vuelve a bajar el mismo archivo, no uno
  regenerado con una plantilla que quizá ya cambió.
- **El nombre del archivo** es `CODIGO_RMC_AAAAMMDD_NNN.pdf` y el NNN sale del
  MÁXIMO del día (nunca de un conteo, que repite números si algo se borró).
"""
import os
import re
import uuid

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from pydantic import ValidationError

from app.core.archivos import ruta_documento_privado
from app.core.config import settings
from app.core.dias_habiles import hoy
from app.models.fichas_seguridad import FdsDocumento, FdsFicha
from app.models.user import User
from app.modules.fichas_seguridad import pdf_documentos
from app.modules.fichas_seguridad.esquemas_documentos import MODELO_POR_TIPO, TIPOS, faltantes
from app.modules.fichas_seguridad.service import SUBCARPETA, normalizar

SUBCARPETA_DOCUMENTOS = f"{SUBCARPETA}/generados"
MAX_BYTES_LECTURA = 20 * 1024 * 1024
LIMITE_HISTORIAL = 100   # tope de la lista; el historial se busca, no se pagina a mano


def exigir_tipo(tipo: str) -> str:
    if tipo not in TIPOS:
        raise HTTPException(
            status_code=400,
            detail=f"El tipo de documento «{tipo}» no existe. Usa uno de: {', '.join(TIPOS)}.",
        )
    return tipo


def validar_datos(tipo: str, datos: dict) -> dict:
    """Los datos limpios y con la forma del tipo, o 400 diciendo qué campo."""
    try:
        limpio = MODELO_POR_TIPO[tipo].model_validate(datos or {}).model_dump()
    except ValidationError as e:
        primero = e.errors()[0]
        campo = ".".join(str(p) for p in primero["loc"])
        raise HTTPException(
            status_code=400,
            detail=f"El dato «{campo}» no es válido ({primero['msg']}). Corrígelo y vuelve a intentar.",
        ) from e
    for clave, valor in limpio.items():
        if isinstance(valor, str):
            limpio[clave] = valor.strip()
    if not limpio["producto"]:
        raise HTTPException(
            status_code=400,
            detail="Falta el nombre del producto. Escríbelo para poder generar el documento.",
        )
    return limpio


def ficha_del_producto(db: Session, tenant_id: int, producto: str) -> FdsFicha | None:
    """La ficha del repositorio con ese nombre (sin tildes ni mayúsculas), si hay."""
    clave = normalizar(producto)
    if not clave:
        return None
    for ficha in db.query(FdsFicha).filter(FdsFicha.tenant_id == tenant_id).all():
        if normalizar(ficha.nombre_producto) == clave:
            return ficha
    return None


def completar_codigo(db: Session, tenant_id: int, datos: dict) -> FdsFicha | None:
    """Si no trae código y el producto coincide con una ficha, toma el suyo."""
    ficha = ficha_del_producto(db, tenant_id, datos["producto"])
    if ficha and not datos.get("codigo_producto") and ficha.codigo_producto:
        datos["codigo_producto"] = ficha.codigo_producto
    return ficha


def _limpiar_para_nombre(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", normalizar(texto)).strip("-").upper()[:30] or "SC"


def _siguiente_consecutivo(db: Session, tenant_id: int, tipo: str, dia) -> int:
    maximo = db.query(func.max(FdsDocumento.consecutivo)).filter(
        FdsDocumento.tenant_id == tenant_id, FdsDocumento.tipo == tipo, FdsDocumento.dia == dia,
    ).scalar()
    return (maximo or 0) + 1


def nombre_de_archivo(datos: dict, dia, consecutivo: int) -> str:
    return f"{_limpiar_para_nombre(datos.get('codigo_producto') or '')}_RMC_{dia:%Y%m%d}_{consecutivo:03d}.pdf"


def vista_previa(tipo: str, datos: dict) -> bytes:
    return pdf_documentos.generar(tipo, datos, "VISTA PREVIA")


def generar(db: Session, usuario: User, tipo: str, datos: dict) -> FdsDocumento:
    """Valida, dibuja el PDF, lo guarda y deja el registro. Reintenta si dos personas sacan el mismo número."""
    exigir_tipo(tipo)
    datos = validar_datos(tipo, datos)
    ficha = completar_codigo(db, usuario.tenant_id, datos)
    dia = hoy()

    for intento in range(3):
        consecutivo = _siguiente_consecutivo(db, usuario.tenant_id, tipo, dia)
        nombre = nombre_de_archivo(datos, dia, consecutivo)
        contenido = pdf_documentos.generar(tipo, datos, nombre.removesuffix(".pdf"))
        relativa = f"{SUBCARPETA_DOCUMENTOS}/{uuid.uuid4().hex}.pdf"
        absoluta = os.path.join(settings.DOCUMENTOS_DIR, relativa)
        os.makedirs(os.path.dirname(absoluta), exist_ok=True)
        with open(absoluta, "wb") as f:
            f.write(contenido)
        documento = FdsDocumento(
            tenant_id=usuario.tenant_id, tipo=tipo, producto=datos["producto"],
            codigo_producto=datos.get("codigo_producto") or None, proveedor=datos.get("proveedor") or None,
            lote=(datos.get("lote_fabricante") or datos.get("version") or None), datos=datos, dia=dia,
            consecutivo=consecutivo, nombre_archivo=nombre, ruta=relativa, tamano=len(contenido),
            ficha_id=ficha.id if ficha else None, generado_por=usuario.id,
        )
        db.add(documento)
        try:
            db.commit()
            return documento
        except IntegrityError:
            db.rollback()
            _borrar(relativa)
            if intento == 2:
                raise HTTPException(
                    status_code=409,
                    detail="Otra persona estaba generando un documento al mismo tiempo. Pulsa generar de nuevo.",
                ) from None
        except Exception:
            db.rollback()
            _borrar(relativa)
            raise
    raise RuntimeError("inalcanzable")


def _borrar(relativa: str) -> None:
    try:
        os.remove(ruta_documento_privado(relativa))
    except (HTTPException, OSError):
        pass


def serializar(d: FdsDocumento, con_datos: bool = False) -> dict:
    salida = {
        "id": d.id, "tipo": d.tipo, "producto": d.producto, "codigo_producto": d.codigo_producto,
        "proveedor": d.proveedor, "lote": d.lote, "nombre_archivo": d.nombre_archivo, "tamano": d.tamano,
        "generado_por_nombre": d.autor.nombre if d.autor else None,
        "generado_en": d.generado_en.isoformat() if d.generado_en else None,
    }
    if con_datos:
        salida["datos"] = d.datos
    return salida


def listar(db: Session, tenant_id: int, q: str | None, tipo: str | None) -> dict:
    consulta = db.query(FdsDocumento).filter(FdsDocumento.tenant_id == tenant_id)
    if tipo:
        consulta = consulta.filter(FdsDocumento.tipo == exigir_tipo(tipo))
    docs = consulta.order_by(FdsDocumento.id.desc()).all()
    palabras = normalizar(q).split()
    if palabras:
        docs = [
            d for d in docs
            if all(p in normalizar(f"{d.producto} {d.codigo_producto or ''} {d.proveedor or ''} {d.lote or ''}") for p in palabras)
        ]
    return {"total": len(docs), "documentos": [serializar(d) for d in docs[:LIMITE_HISTORIAL]]}


def obtener(db: Session, tenant_id: int, documento_id: int) -> FdsDocumento:
    d = db.query(FdsDocumento).filter(FdsDocumento.id == documento_id, FdsDocumento.tenant_id == tenant_id).first()
    if d is None:
        raise HTTPException(
            status_code=404,
            detail="No encontramos ese documento. Puede que no sea de tu empresa: actualiza el historial.",
        )
    return d


def propuesta(tipo: str, leidos: dict, db: Session, tenant_id: int, avisos: list[str] | None = None) -> dict:
    """
    Lo que devuelve la lectura: datos limpios, código del repositorio si lo hay,
    lo que no se leyó (`faltantes`) y lo que conviene saber de CÓMO se leyó
    (`avisos`: por ejemplo, que no se tradujo).
    """
    datos = MODELO_POR_TIPO[tipo].model_validate(_tolerante(tipo, leidos)).model_dump()
    if datos["producto"]:
        completar_codigo(db, tenant_id, datos)
    return {"datos": datos, "faltantes": faltantes(tipo, datos), "avisos": avisos or []}


def _tolerante(tipo: str, leidos: dict) -> dict:
    """Un texto puede pasarse de largo: se recorta en vez de perder la lectura entera."""
    def recortar(valor, largo):
        return valor[:largo] if isinstance(valor, str) else ("" if valor is None else str(valor)[:largo])

    salida = {k: recortar(v, 300) for k, v in leidos.items() if isinstance(v, (str, int, float)) or v is None}
    if tipo == "certificado_analisis":
        salida["producto"] = recortar(leidos.get("producto"), 200)
        salida["parametros"] = [
            {k: recortar(p.get(k), 300) for k in ("nombre", "unidad", "requisito", "metodo", "resultado")}
            for p in (leidos.get("parametros") or []) if isinstance(p, dict)
        ][:80]
    else:
        salida["producto"] = recortar(leidos.get("producto"), 200)
        salida["secciones"] = [
            {"numero": int(s.get("numero")), "titulo": recortar(s.get("titulo"), 300), "contenido": recortar(s.get("contenido"), 6000)}
            for s in (leidos.get("secciones") or [])
            if isinstance(s, dict) and str(s.get("numero", "")).isdigit() and 1 <= int(s["numero"]) <= 16
        ][:16]
    return salida
