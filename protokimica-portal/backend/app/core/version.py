"""
La versión del portal y qué trajo cada una.

**Este archivo es la única fuente.** El backend la sirve en `/version` y el
frontend la lee al compilar (ver `frontend/vite.config.js`), así que no hay
un segundo número que se pueda quedar atrás.

Cómo subir de versión:

1. Cambiar `VERSION` y `FECHA` aquí.
2. Agregar la entrada nueva **al principio** de `HISTORIAL`.
3. `npm run build` en el frontend — sin esto el navegador sigue anunciando
   la versión anterior y el portal avisa que están desfasados.

Numeración `MAYOR.MENOR.PARCHE`:
- **PARCHE** — correcciones. Nada cambia de sitio.
- **MENOR** — funciones nuevas. Es lo normal aquí.
- **MAYOR** — 1.0.0 el día que el portal se entregue a una empresa distinta
  de Protokimica. Antes de eso el esquema todavía se mueve.
"""
VERSION = "0.13.0"
FECHA = "2026-08-18"

# Cómo se rotula cada cambio. El punto de color nunca va solo: el ámbar de la
# marca no alcanza el contraste mínimo sobre blanco, así que siempre va con su
# etiqueta.
TIPOS_DE_CAMBIO = {
    "nuevo": {"etiqueta": "Nuevo", "color": "#2E9E6B"},
    "mejora": {"etiqueta": "Mejora", "color": "#1A4FA0"},
    "correccion": {"etiqueta": "Corrección", "color": "#F5A800"},
}

# Lo más reciente primero. Se escribe pensando en quién usa el portal, no en
# quién lo programa: "ya se pueden cerrar proyectos", no "se agregó el campo
# fecha_cierre a mp_proyectos".
HISTORIAL = [
    {
        "version": "0.13.0",
        "fecha": "2026-08-18",
        "titulo": "Radicar PQRS sin errores y entrar directo a lo tuyo",
        "cambios": [
            ("correccion", "Radicar una PQRS ya no muestra el error rojo al final. "
                           "La solicitud se guardaba igual, así que quien lo veía "
                           "volvía a enviarla y quedaba repetida."),
            ("correccion", "El aviso por correo de una PQRS nueva vuelve a salir: "
                           "un espacio de más en la configuración lo estaba "
                           "impidiendo sin decir nada."),
            ("mejora", "Radicar ya no se queda esperando: la confirmación con el "
                       "código aparece de inmediato y los correos salen detrás."),
            ("nuevo", "Desde el inicio se entra directo a la tarea, al indicador o "
                      "al proyecto que aparece en la lista, sin volver a buscarlo."),
            ("nuevo", "Los formularios del cliente enlazan la política de "
                      "protección de datos personales, que abre en otra pestaña "
                      "para no perder lo que se estaba llenando."),
        ],
    },
    {
        "version": "0.12.0",
        "fecha": "2026-08-18",
        "titulo": "Nueva imagen del portal",
        "cambios": [
            ("mejora", "El portal se ve distinto: menú más sobrio, tarjetas con "
                       "profundidad y todo alineado a la misma cuadrícula."),
            ("mejora", "Los iconos ya no son emojis. Ahora son de una sola familia y "
                       "se ven igual en Windows, en el celular y al imprimir."),
            ("mejora", "Los números del inicio y de los resúmenes vienen con contexto: "
                       "cuánto falta para la meta, si subió o bajó, y si eso es bueno."),
            ("mejora", "El inicio destaca lo vencido y lo de esta semana antes que "
                       "cualquier otra cosa, con el conteo a la vista."),
            ("mejora", "Los colores de estado dicen gravedad: lo vencido en rojo, lo "
                       "próximo en ámbar, lo que va bien en verde — y siempre con su "
                       "palabra al lado, no solo el color."),
            ("mejora", "El portal ya se puede usar desde el celular: el menú se abre "
                       "y se cierra encima del contenido."),
        ],
    },
    {
        "version": "0.11.0",
        "fecha": "2026-08-17",
        "titulo": "Inicio propio y permisos por módulo",
        "cambios": [
            ("nuevo", "El portal abre en una página de inicio con lo que te toca hoy: "
                      "tus tareas y PQRS por vencer, y accesos directos a lo tuyo."),
            ("nuevo", "Gerencia y los líderes ven además cómo va la empresa y su área."),
            ("mejora", "Los indicadores quedaron para gerencia y líderes. Un líder ve "
                       "los de su área, que son los que responde."),
        ],
    },
    {
        "version": "0.10.0",
        "fecha": "2026-08-15",
        "titulo": "Cierre de proyectos",
        "cambios": [
            ("nuevo", "Un proyecto se puede cerrar o cancelar dejando el acta: qué se "
                      "logró, qué quedó pendiente y con qué presupuesto terminó."),
        ],
    },
    {
        "version": "0.9.0",
        "fecha": "2026-08-12",
        "titulo": "Encuestas de satisfacción",
        "cambios": [
            ("nuevo", "Encuestas para el cliente, con enlace corto para imprimir en un QR."),
            ("nuevo", "Los resultados alimentan los indicadores sin digitar nada."),
        ],
    },
    {
        "version": "0.8.0",
        "fecha": "2026-08-11",
        "titulo": "Indicadores completos",
        "cambios": [
            ("nuevo", "Tablero mensual con semáforo, acumulados y comparación contra el mes anterior."),
            ("nuevo", "Portada «cómo vamos» para gerencia."),
            ("mejora", "Los indicadores de proporción guardan los dos números, para que "
                       "el acumulado del trimestre salga bien."),
        ],
    },
    {
        "version": "0.7.0",
        "fecha": "2026-08-10",
        "titulo": "Conexión con Microsoft 365",
        "cambios": [
            ("nuevo", "Las tareas con fecha aparecen en el calendario de Outlook."),
            ("correccion", "Las horas se guardaban corridas por la zona horaria del servidor."),
        ],
    },
    {
        "version": "0.6.1",
        "fecha": "2026-08-07",
        "titulo": "Correcciones",
        "cambios": [
            ("correccion", "«Seguir editando» no cerraba el aviso y tocaba descartar lo escrito."),
            ("correccion", "Un indicador ya registrado no se dejaba corregir."),
            ("correccion", "El formulario pedía «numerador» y «denominador» y salían al "
                           "revés. Ahora pregunta qué se logró y de cuánto."),
        ],
    },
    {
        "version": "0.6.0",
        "fecha": "2026-08-07",
        "titulo": "Aprobación y pago del presupuesto",
        "cambios": [
            ("nuevo", "El presupuesto va de planeado a aprobado y de aprobado a pagado: "
                      "Administración aprueba y Tesorería registra los abonos."),
            ("nuevo", "Vista de presupuesto de todos los proyectos, con filtro por área."),
            ("mejora", "El porcentaje pagado se mide sobre lo aprobado, que es la deuda real."),
        ],
    },
    {
        "version": "0.5.0",
        "fecha": "2026-08-05",
        "titulo": "PQRS: reclasificar y días hábiles",
        "cambios": [
            ("nuevo", "Servicio al Cliente corrige el tipo de la solicitud antes de "
                      "cerrarla, y queda la trazabilidad del cambio."),
            ("correccion", "Los plazos se contaban corridos y declaraban vencido lo que "
                           "no lo estaba. Ahora son días hábiles, con los festivos "
                           "colombianos."),
        ],
    },
    {
        "version": "0.4.0",
        "fecha": "2026-08-03",
        "titulo": "Áreas unificadas",
        "cambios": [
            ("mejora", "Una sola lista de áreas en todo el portal."),
            ("nuevo", "Gerencia ve todas las áreas sin límite; comenta, pero no modifica."),
            ("nuevo", "En Master Planner cada quien ve los proyectos de su área."),
        ],
    },
    {
        "version": "0.3.0",
        "fecha": "2026-08-02",
        "titulo": "Primer módulo de indicadores",
        "cambios": [
            ("nuevo", "Indicadores por área, con meta y registro mensual."),
        ],
    },
    {
        "version": "0.2.0",
        "fecha": "2026-07-31",
        "titulo": "Master Planner",
        "cambios": [
            ("nuevo", "Proyectos, tareas, seguimientos y vista de calendario."),
        ],
    },
    {
        "version": "0.1.0",
        "fecha": "2026-07-30",
        "titulo": "Primera versión",
        "cambios": [
            ("nuevo", "PQRS: formulario público, radicación, respuesta y cierre."),
            ("nuevo", "Usuarios, roles y áreas."),
        ],
    },
]


def historial_publico() -> list[dict]:
    """El historial listo para pintar: cada cambio con su etiqueta y su color."""
    return [
        {
            "version": v["version"],
            "fecha": v["fecha"],
            "titulo": v["titulo"],
            "cambios": [
                {
                    "tipo": tipo,
                    "etiqueta": TIPOS_DE_CAMBIO[tipo]["etiqueta"],
                    "color": TIPOS_DE_CAMBIO[tipo]["color"],
                    "texto": texto,
                }
                for tipo, texto in v["cambios"]
            ],
        }
        for v in HISTORIAL
    ]


# Olvidar una de las dos mitades es el error obvio: se sube VERSION y el
# historial no dice qué trajo, o al revés. Revienta al arrancar, no en
# producción tres días después.
assert HISTORIAL, "El historial de versiones no puede estar vacío."
assert HISTORIAL[0]["version"] == VERSION, (
    f"VERSION es {VERSION} pero el historial empieza en "
    f"{HISTORIAL[0]['version']}. Agrega la entrada nueva al principio de HISTORIAL."
)
assert HISTORIAL[0]["fecha"] == FECHA, "La fecha de la versión y la del historial no coinciden."
assert all(
    tipo in TIPOS_DE_CAMBIO for v in HISTORIAL for tipo, _ in v["cambios"]
), f"Cada cambio va rotulado como uno de: {sorted(TIPOS_DE_CAMBIO)}."
