"""
El portal es interno: los usuarios se crean solo con correo corporativo.

Importa porque un usuario con correo personal no tiene buzón de la empresa,
y todo lo que dependa de esa cuenta (calendario de Outlook, notificaciones)
nunca le llega. El error se ve al crear el usuario, no meses después.
"""
from app.core.config import settings


def test_no_deja_crear_usuario_con_correo_personal(entorno, v):
    e = entorno
    e.como("admin")

    r = e.post("/auth/usuarios", json={
        "nombre": "Externo",
        "email": "alguien@gmail.com",
        "password": "clave12345",
        "rol": "agente",
        "area": "TICS",
    })
    v.check("un correo personal no puede crear usuario", r.status_code == 400, r.status_code)
    v.check(
        "el error explica que hace falta el correo de la empresa",
        "corporativo" in r.json().get("detail", ""),
        r.json(),
    )


def test_deja_crear_usuario_con_correo_corporativo(entorno, v):
    e = entorno
    e.como("admin")

    r = e.post("/auth/usuarios", json={
        "nombre": "Nuevo Interno",
        "email": "nuevo.interno@protokimica.com",
        "password": "clave12345",
        "rol": "agente",
        "area": "TICS",
    })
    v.check("el correo corporativo sí entra", r.status_code == 201, r.text)


def test_el_dominio_no_distingue_mayusculas(entorno, v):
    e = entorno
    e.como("admin")

    r = e.post("/auth/usuarios", json={
        "nombre": "Mayusculas",
        "email": "Otro.Interno@PROTOKIMICA.COM",
        "password": "clave12345",
        "rol": "agente",
        "area": "TICS",
    })
    v.check("PROTOKIMICA.COM vale igual que protokimica.com", r.status_code == 201, r.text)


def test_la_lista_de_dominios_se_normaliza(v):
    """La config se escribe a mano; tolera espacios, arrobas y mayúsculas."""
    original = settings.DOMINIOS_EMAIL_PERMITIDOS
    try:
        settings.DOMINIOS_EMAIL_PERMITIDOS = " @Protokimica.com , OTRA.CO "
        v.check(
            "quita espacios y arrobas, y pasa a minúscula",
            settings.dominios_email_list == ["protokimica.com", "otra.co"],
            settings.dominios_email_list,
        )

        settings.DOMINIOS_EMAIL_PERMITIDOS = ""
        v.check(
            "vacío significa que no hay restricción de dominio",
            settings.dominios_email_list == [],
            settings.dominios_email_list,
        )
    finally:
        settings.DOMINIOS_EMAIL_PERMITIDOS = original
