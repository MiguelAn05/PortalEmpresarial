"""
Fichas de datos de seguridad (FDS): el repositorio de las que tiene la empresa.

Una **ficha** es el documento de UN producto (en Protokimica, el formato
`AP-F-08`) y vive aunque cambie de versión; cada **versión** es un PDF con el
número y la fecha que el propio documento trae en su encabezado. Hay una sola
vigente por ficha, y las anteriores se conservan: lo que se entregó a un
cliente hace un año tiene que poder consultarse.

- **El producto es texto, no una llave al catálogo.** Un módulo no depende de
  las tablas de otro (ver `tests/test_modularidad.py`), y una empresa puede
  contratar Fichas sin PQRS ni Catálogo. El código es opcional: hay fichas de
  materias primas y de productos que no están en el ERP.
- **El archivo no va en `/uploads`**, que se sirve sin preguntar quién pide.
  Va a `DOCUMENTOS_DIR` (ver `core/archivos.guardar_documento_privado`) y se
  baja por un endpoint que revisa el módulo contratado y el rol.
- **`version` es el texto del documento** («10», «10.1»), no un contador
  nuestro: quien busca la ficha compara contra lo que dice el PDF impreso.
  Dentro de una ficha no se repite.
- **`nombre_busqueda`** es el nombre y el código sin tildes ni mayúsculas, para
  que el buscador encuentre «ácido acético» escribiendo «acido acetico».
  Lo calcula el servicio al guardar; nadie lo escribe a mano.
- Borrar una ficha pierde todas sus versiones; por eso el borrado por defecto
  responde 409 y ofrece desactivarla (ver `modules/fichas_seguridad/service.py`).
"""
from sqlalchemy import (
    JSON, Boolean, Column, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Los topes son los del formulario (`frontend/src/modules/fichasSeguridad/constants.js`):
# un valor más largo se rechaza con un 400 que dice cuál, en vez de reventar en
# el commit con un error de Postgres.
MAX_NOMBRE = 200
MIN_NOMBRE = 3
MAX_CODIGO = 40
MAX_VERSION = 20
MAX_OBSERVACIONES = 500
MAX_ARCHIVO = 255


class FdsFicha(Base):
    __tablename__ = "fds_fichas"
    # Dos filas sin código no chocan (NULL no se compara): el código es opcional.
    __table_args__ = (UniqueConstraint("tenant_id", "codigo_producto", name="uq_fds_ficha_codigo"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    codigo_producto = Column(String(MAX_CODIGO), nullable=True)
    nombre_producto = Column(String(MAX_NOMBRE), nullable=False)
    nombre_busqueda = Column(String(MAX_NOMBRE + MAX_CODIGO + 1), nullable=False, index=True)
    # Se desactiva, no se borra: deja de ofrecerse pero conserva su historia.
    activa = Column(Boolean, nullable=False, default=True, server_default="true")

    creada_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    creada_en = Column(DateTime(timezone=True), server_default=func.now())

    versiones = relationship(
        "FdsVersion", back_populates="ficha",
        cascade="all, delete-orphan", order_by="FdsVersion.id.desc()",
    )

    @property
    def vigente(self):
        """La versión que hoy vale, o None si todavía no tiene ninguna."""
        return next((v for v in self.versiones if v.vigente), None)


class FdsVersion(Base):
    __tablename__ = "fds_versiones"
    __table_args__ = (UniqueConstraint("ficha_id", "version", name="uq_fds_version"),)

    id = Column(Integer, primary_key=True, index=True)
    ficha_id = Column(Integer, ForeignKey("fds_fichas.id", ondelete="CASCADE"), nullable=False, index=True)
    # Como la escribe el documento, no un consecutivo propio.
    version = Column(String(MAX_VERSION), nullable=False)
    # La fecha del encabezado del PDF, no la de subida.
    fecha_emision = Column(Date, nullable=False)

    nombre_original = Column(String(MAX_ARCHIVO), nullable=False)
    # Relativa a DOCUMENTOS_DIR. Nunca una URL: no hay URL pública que dar.
    ruta = Column(String(MAX_ARCHIVO), nullable=False)
    tamano = Column(Integer, nullable=False)

    # Una sola por ficha; la pone el servicio al subir una versión nueva.
    vigente = Column(Boolean, nullable=False, default=False, server_default="false")
    observaciones = Column(String(MAX_OBSERVACIONES), nullable=True)

    subida_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    subida_en = Column(DateTime(timezone=True), server_default=func.now())

    ficha = relationship("FdsFicha", back_populates="versiones")
    autor = relationship("User", foreign_keys=[subida_por])

    @property
    def subida_por_nombre(self):
        return self.autor.nombre if self.autor else None


TIPOS_DOCUMENTO = ("certificado_analisis", "fds")


class FdsDocumento(Base):
    """
    Un documento oficial GENERADO por el portal a partir del de un proveedor:
    el certificado de análisis (AP-F-06) o la ficha de datos de seguridad
    (AP-F-08). Es el historial: guarda los datos tal como se firmaron y el PDF
    resultante, para poder bajarlo de nuevo sin volver a generarlo.

    `consecutivo` es el NNN del nombre del archivo, por empresa + tipo + día, y
    sale del MÁXIMO, nunca de un conteo.
    """
    __tablename__ = "fds_documentos"
    __table_args__ = (UniqueConstraint("tenant_id", "tipo", "dia", "consecutivo", name="uq_fds_documento_consecutivo"),)

    id = Column(Integer, primary_key=True, index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    tipo = Column(String(30), nullable=False)
    producto = Column(String(MAX_NOMBRE), nullable=False)
    codigo_producto = Column(String(MAX_CODIGO), nullable=True)
    proveedor = Column(String(MAX_NOMBRE), nullable=True)
    lote = Column(String(100), nullable=True)
    # Lo que se firmó, tal cual: si cambia la plantilla, esto sigue diciendo lo de ese día.
    datos = Column(JSON, nullable=False)
    dia = Column(Date, nullable=False)
    consecutivo = Column(Integer, nullable=False)
    nombre_archivo = Column(String(MAX_ARCHIVO), nullable=False)
    ruta = Column(String(MAX_ARCHIVO), nullable=False)
    tamano = Column(Integer, nullable=False)
    ficha_id = Column(Integer, ForeignKey("fds_fichas.id", ondelete="SET NULL"), nullable=True)
    generado_por = Column(Integer, ForeignKey("users.id"), nullable=True)
    generado_en = Column(DateTime(timezone=True), server_default=func.now())

    autor = relationship("User", foreign_keys=[generado_por])
