from typing import Annotated
from pydantic import BaseModel, BeforeValidator, EmailStr


def _solo_nombres(valor):
    """
    El modelo devuelve filas de `usuario_areas_supervisadas`; hacia afuera
    solo importan los nombres de las áreas.
    """
    if valor is None:
        return []
    return [a if isinstance(a, str) else a.area for a in valor]


# Las áreas que alguien supervisa ADEMÁS de la suya. Ver core/supervision.py.
AreasSupervisadas = Annotated[list[str], BeforeValidator(_solo_nombres)]


class RegisterRequest(BaseModel):
    tenant_slug: str          # ej: "protokimica" -> a qué empresa pertenece
    nombre: str
    email: EmailStr
    password: str
    rol: str = "agente"
    area: str | None = None
    setup_key: str            # llave de configuración inicial — ver REGISTER_SETUP_KEY


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    tenant_slug: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str
    area: str | None
    # Prefijo del punto de venta (`PVG`…). Ver `models/user.py`.
    punto_venta: str | None = None
    # Bodega que maneja («Guayabal», «La 65»). Solo significa algo con la
    # capacidad notas_credito.confirmar_producto. Ver core/bodegas.py.
    bodega: str | None = None
    # Áreas que supervisa ADEMÁS de la suya. Ver core/supervision.py.
    areas_supervisadas: AreasSupervisadas = []
    tenant_id: int

    class Config:
        from_attributes = True


class UsuarioCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    rol: str = "agente"
    area: str | None = None
    punto_venta: str | None = None
    # Bodega que maneja («Guayabal», «La 65»). Solo significa algo con la
    # capacidad notas_credito.confirmar_producto. Ver core/bodegas.py.
    bodega: str | None = None
    # Áreas que supervisa ADEMÁS de la suya. Ver core/supervision.py.
    areas_supervisadas: AreasSupervisadas = []


class UsuarioUpdate(BaseModel):
    rol: str | None = None
    area: str | None = None
    # A diferencia de `area`, aquí `null` SÍ significa «quítaselo»: se mira
    # si el campo llegó (`model_fields_set`), no si trae valor. Quitarle el
    # punto a alguien es justamente convertirlo en coordinador.
    punto_venta: str | None = None
    # Igual que `punto_venta`: se mira si llegó, no si trae valor. Null es
    # «responde por todas las bodegas», no «sin cambios».
    bodega: str | None = None
    # Igual que `punto_venta`: se mira si el campo llegó, no si trae valor.
    # Mandar una lista vacía es quitarle toda la supervisión; no mandarlo, dejarla como está.
    areas_supervisadas: list[str] | None = None
    activo: bool | None = None
    password: str | None = None  # para que un admin pueda restablecerla si alguien la olvidó


class CambiarPasswordRequest(BaseModel):
    password_actual: str
    password_nueva: str


class UsuarioOut(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str
    area: str | None
    punto_venta: str | None = None
    # Bodega que maneja («Guayabal», «La 65»). Solo significa algo con la
    # capacidad notas_credito.confirmar_producto. Ver core/bodegas.py.
    bodega: str | None = None
    # Áreas que supervisa ADEMÁS de la suya. Ver core/supervision.py.
    areas_supervisadas: AreasSupervisadas = []
    activo: bool

    class Config:
        from_attributes = True
