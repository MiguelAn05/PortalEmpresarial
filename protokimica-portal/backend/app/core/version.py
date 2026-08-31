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
VERSION = "0.19.0"
FECHA = "2026-08-31"

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
        "version": "0.19.0",
        "fecha": "2026-08-31",
        "titulo": "Un QR en cada punto de venta",
        "cambios": [
            ("nuevo", "Cada punto de venta tiene su código QR para imprimir y "
                      "pegar en el mostrador. El cliente apunta la cámara y "
                      "entra directo al formulario."),
            ("nuevo", "Al entrar por el QR, la solicitud ya queda marcada con "
                      "ese punto de venta: el cliente no tiene que elegirlo de "
                      "una lista, así que el radicado sale con el número de la "
                      "sede correcta y los reportes por punto cuadran."),
            ("nuevo", "Los carteles se imprimen desde Administración, uno por "
                      "hoja, con el nombre de la sede y la dirección escrita "
                      "debajo por si la cámara no lee el código."),
            ("correccion", "El formulario de felicitaciones decía «Llamada "
                           "telefónica» y el resto del portal «Línea "
                           "telefónica»: era el mismo canal contado dos veces "
                           "en los informes. Ahora es uno solo, y las "
                           "solicitudes viejas se leen con el nombre nuevo."),
        ],
    },
    {
        "version": "0.18.0",
        "fecha": "2026-08-31",
        "titulo": "El producto, del catálogo",
        "cambios": [
            ("nuevo", "El formulario público ya busca los productos en el "
                      "catálogo real que llega del ERP, no en una lista de "
                      "prueba."),
            ("nuevo", "Si el cliente no encuentra su producto, ahora puede "
                      "escribirlo y seguir. Antes se quedaba trabado sin poder "
                      "radicar."),
            ("nuevo", "Las solicitudes con el producto escrito a mano quedan "
                      "señaladas, y Servicio al Cliente lo busca en el "
                      "catálogo y lo confirma antes de cerrarlas — igual que "
                      "ya se hace con el tipo."),
            ("mejora", "Una solicitud no se puede cerrar con el producto sin "
                       "confirmar: así el informe de qué producto da más "
                       "problemas no cuenta el mismo dos veces por estar "
                       "escrito distinto."),
            ("correccion", "Los productos de nombre largo ya no se cortan al "
                           "radicar."),
        ],
    },
    {
        "version": "0.17.0",
        "fecha": "2026-08-31",
        "titulo": "Mejora, con el formato del SGC",
        "cambios": [
            ("nuevo", "Las oportunidades de mejora ya llevan el formato oficial "
                      "de Calidad: proceso al que se remite, fuente del "
                      "hallazgo y tipo de acción. Un solo registro para toda la "
                      "empresa en vez de un Excel por proceso."),
            ("nuevo", "Cada acción se numera dentro de su proceso, como en el "
                      "archivo de siempre, así que «la 6 de TIC's» se sigue "
                      "encontrando por ese número."),
            ("nuevo", "Ahora se elige si es una oportunidad de mejora, una "
                      "acción correctiva o una acción de mejora, y el "
                      "formulario pide solo lo que aplica a cada una: a una "
                      "acción de mejora ya no se le exige causa raíz."),
            ("nuevo", "El análisis de causas se escribe por las 6M —efecto, "
                      "método, mano de obra, maquinaria, material, medidas y "
                      "medio ambiente— en vez de un solo cuadro de texto."),
            ("nuevo", "El seguimiento es una bitácora con fecha y autor: se "
                      "agregan entradas y se leen en orden, en vez de irlas "
                      "amontonando dentro de una misma celda."),
            ("nuevo", "Una acción se cierra solo después de que Calidad le da "
                      "el visto bueno, y queda registrado quién la validó y "
                      "cuándo."),
            ("nuevo", "Las tareas del plan ya tienen «en curso», no solo hecho "
                      "o pendiente, y quedan numeradas en su orden."),
            ("nuevo", "Se pueden enlazar dos acciones que tratan el mismo "
                      "hallazgo, y cada una muestra quién cambió qué y cuándo."),
            ("nuevo", "Una acción puede tener varios responsables de resolver y "
                      "de hacerle seguimiento, incluido un comité."),
            ("mejora", "Los procesos y las fuentes los administra Calidad desde "
                       "el portal: agregar uno nuevo ya no necesita que TIC's "
                       "haga nada."),
        ],
    },
    {
        "version": "0.16.0",
        "fecha": "2026-08-30",
        "titulo": "Cada quien ve lo suyo",
        "cambios": [
            ("mejora", "En Master Planner cada quien ve lo suyo: los proyectos "
                       "que lidera y en los que tiene tareas. Antes salían todos "
                       "los del área y había que buscar el propio entre veinte."),
            ("mejora", "El líder de área sigue viendo lo de su equipo, incluso "
                       "si el proyecto se lo encargaron a alguien que no es jefe "
                       "o si es de otra área."),
            ("nuevo", "En Administración se puede buscar un usuario por nombre o "
                      "correo, y desactivarlo cuando sale de la empresa. Los "
                      "inactivos quedan escondidos salvo que se pidan."),
            ("mejora", "Al crear un proyecto sin líder queda a nombre de quien "
                       "lo creó, para que no desaparezca de su lista."),
            ("mejora", "Las oportunidades de mejora quedaron para los líderes de "
                       "área, que son quienes responden por ellas."),
        ],
    },
    {
        "version": "0.15.0",
        "fecha": "2026-08-30",
        "titulo": "Oportunidades de mejora",
        "cambios": [
            ("nuevo", "Ya se pueden llevar las oportunidades de mejora en el "
                      "portal, con su número, quién la abrió, el área y en qué "
                      "va cada una. Reemplaza el archivo de Excel."),
            ("nuevo", "Desde un indicador que no cumplió sale un botón para "
                      "abrir la oportunidad, con el indicador, el mes y el "
                      "valor ya cargados."),
            ("nuevo", "Cada oportunidad lleva su plan: qué se hace, quién "
                      "responde y para cuándo. El avance sale solo de lo que "
                      "ya está hecho."),
            ("nuevo", "Al cerrar, el portal compara el indicador de antes con "
                      "el del mes siguiente y muestra si de verdad mejoró. Si "
                      "no funcionó, la oportunidad vuelve a análisis en vez de "
                      "cerrarse."),
            ("mejora", "Los líderes de cada área manejan las oportunidades de "
                       "su área; gerencia las ve todas."),
        ],
    },
    {
        "version": "0.14.0",
        "fecha": "2026-08-19",
        "titulo": "El inicio ahora muestra cómo va la empresa",
        "cambios": [
            ("nuevo", "El inicio trae una gráfica de la ejecución del presupuesto "
                      "mes a mes: cuánto aprobó Administración y cuánto pagó "
                      "Tesorería, uno al lado del otro."),
            ("nuevo", "Aparece la lista de proyectos al frente, con el que vence "
                      "primero arriba y su avance. Se entra al proyecto con un clic."),
            ("mejora", "Las cifras de arriba ya dicen si son buenas o malas: PQRS "
                       "cerradas en el mes, proyectos nuevos, y si los indicadores "
                       "en rojo subieron o bajaron frente al mes pasado."),
            ("mejora", "El presupuesto pagado se mide sobre lo APROBADO y no sobre "
                       "lo planeado: lo planeado puede no aprobarse nunca, y la "
                       "deuda real es lo aprobado."),
            ("mejora", "Los accesos rápidos bajaron al final de la página y «cómo "
                       "va la empresa» subió al segundo lugar."),
        ],
    },
    {
        "version": "0.13.0",
        "fecha": "2026-08-18",
        "titulo": "Radicar PQRS sin errores y entrar directo a lo tuyo",
        "cambios": [
            ("correccion", "Radicar una PQRS ya no falla con el error rojo del final. "
                           "El código de seguimiento se repetía cuando se había "
                           "borrado alguna solicitud, y la que se estaba radicando "
                           "quedaba guardada pero sin código."),
            ("correccion", "Por lo mismo dejaron de salir los correos de aviso: se "
                           "enviaban justo después de asignar el código. Ya vuelven "
                           "a salir."),
            ("correccion", "Dos personas radicando al mismo tiempo ya no se pisan el "
                           "número: cada solicitud recibe el suyo."),
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
