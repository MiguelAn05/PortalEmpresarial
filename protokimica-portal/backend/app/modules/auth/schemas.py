from pydantic import BaseModel, EmailStr


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


class UsuarioUpdate(BaseModel):
    rol: str | None = None
    area: str | None = None
    # A diferencia de `area`, aquí `null` SÍ significa «quítaselo»: se mira
    # si el campo llegó (`model_fields_set`), no si trae valor. Quitarle el
    # punto a alguien es justamente convertirlo en coordinador.
    punto_venta: str | None = None
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
    activo: bool

    class Config:
        from_attributes = True
