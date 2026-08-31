"""
Los catálogos del formato RCN-F-13: proceso, fuente y tratamiento.

Van en tabla y no en una constante de Python porque **Calidad los cambia sin
avisarle a TIC's**: agregar un proceso nuevo no puede requerir un despliegue.
Lo que sí vive aquí es la SEMILLA — los valores con los que arranca cada
empresa, tomados del `Listado` del Excel oficial.

Ojo con el `codigo` del tratamiento (`OMP`, `AC`, `AM`): la lógica de qué
campos aplican se decide por ese código, **nunca por el nombre**. El histórico
ya trae «Acción de mejora» y «Acción de Mejora» escritos distinto, y si el
comportamiento dependiera del texto, renombrar un catálogo desde Admin
apagaría una regla de negocio en silencio.
"""

TIPOS = ("proceso", "fuente", "tratamiento")

# Los tres tratamientos, por código. El código es la llave estable.
TRATAMIENTO_OMP = "OMP"   # Oportunidad de Mejora
TRATAMIENTO_AC = "AC"     # Acción Correctiva
TRATAMIENTO_AM = "AM"     # Acción de Mejora

# Qué tratamientos exigen análisis de causas y causa raíz. Una Acción de
# Mejora no nace de un problema: no tiene causa que buscar, tiene un
# beneficio que justificar.
TRATAMIENTOS_CON_CAUSA = (TRATAMIENTO_OMP, TRATAMIENTO_AC)

# (codigo, nombre) en el orden en que Calidad los lista.
SEMILLA = {
    "proceso": [
        (None, "Direccionamiento Estratégico"),
        (None, "Abastecimiento y Negocios Internacionales"),
        (None, "Puntos de Ventas"),
        (None, "Ventas Institucionales"),
        (None, "Producción"),
        (None, "Logística"),
        (None, "Infraestructura"),
        (None, "Aseguramiento de producto"),
        (None, "Mercadeo"),
        (None, "Gestión Administrativa"),
        (None, "TIC's"),
        (None, "Gestión Contable"),
        (None, "Gestión Humana"),
        (None, "Control Interno"),
        (None, "SST"),
        (None, "SGAmbiental"),
        (None, "SGC"),
    ],
    "fuente": [
        (None, "Seguimiento al proceso"),
        (None, "Auditoría interna"),
        (None, "Auditoría externa"),
        (None, "Informes Gerenciales"),
        (None, "Revisión por la dirección"),
        (None, "Salida no conforme"),
        (None, "PQR"),
        (None, "Reunión / Comité"),
        (None, "Análisis de contexto"),
    ],
    "tratamiento": [
        (TRATAMIENTO_OMP, "Oportunidad de Mejora"),
        (TRATAMIENTO_AC, "Acción Correctiva"),
        (TRATAMIENTO_AM, "Acción de Mejora"),
    ],
}

# El área del portal y el proceso del SGC son ejes distintos: el área decide
# permisos, el proceso rotula el reporte. Esta tabla solo sirve para PROPONER
# el proceso al abrir una OMP y ahorrarle un clic a la gente; se puede
# cambiar en el formulario.
#
# Las áreas que no están aquí no tienen equivalente en el listado del SGC
# (Servicio al Cliente, Facturación, Controlados, Tesorería, Comercial): en
# esos casos no se propone nada y la persona elige. Adivinar mal es peor que
# no adivinar — el proceso es lo que decide en qué archivo cae la acción.
PROCESO_SEGUN_AREA = {
    "TICS": "TIC's",
    "Calidad": "SGC",
    "SST": "SST",
    "Ventas Institucionales": "Ventas Institucionales",
    "Mercadeo": "Mercadeo",
    "Infraestructura": "Infraestructura",
    "Logística": "Logística",
    "Gestión Humana": "Gestión Humana",
    "Contabilidad": "Gestión Contable",
    "Producción": "Producción",
    "Control Interno": "Control Interno",
    "Aseguramiento": "Aseguramiento de producto",
    "Abastecimiento": "Abastecimiento y Negocios Internacionales",
    "Administración": "Gestión Administrativa",
}

# El origen que ya usaba el portal y la fuente del SGC que le corresponde.
# Son dos preguntas distintas —«a qué registro está amarrada» y «de dónde
# salió el hallazgo»— pero la segunda casi siempre se deduce de la primera.
FUENTE_SEGUN_ORIGEN = {
    "indicador": "Seguimiento al proceso",
    "pqrs": "PQR",
    "auditoria": "Auditoría interna",
    "sugerencia": "Reunión / Comité",
}

# Lo que el Excel escribe cuando un campo no aplica. Se guarda como NULL: el
# literal «N/A» en una columna de texto obliga después a filtrarlo en cada
# consulta y en cada reporte.
NO_APLICA = {"n/a", "na", "n.a.", "no aplica", "no aplica.", "-", "--"}


def limpiar_no_aplica(texto: str | None) -> str | None:
    """Convierte los «N/A» del Excel en None. Devuelve None si viene vacío."""
    if texto is None:
        return None
    limpio = texto.strip()
    if not limpio or limpio.lower() in NO_APLICA:
        return None
    return limpio
