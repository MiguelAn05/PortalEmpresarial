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
VERSION = "0.35.0"
FECHA = "2026-09-19"

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
        "version": "0.35.0",
        "fecha": "2026-09-19",
        "titulo": "Indicadores se rehizo entero, y el portal ya no se queda en blanco al abrir",
        "cambios": [
            ("nuevo", "Indicadores tiene ahora tres pestañas: «Cómo vamos» "
                      "para ver el estado del mes, «Tablero» para registrar y "
                      "consultar, y «El año» para la matriz de los doce "
                      "meses, que antes estaba metida en medio de todo y "
                      "empujaba el resto fuera de la pantalla."),
            ("mejora", "El mes, el área, el alcance y la búsqueda viven ahora "
                       "arriba y valen para las tres pestañas. Antes cambiar "
                       "de pestaña cambiaba en silencio qué parte de la "
                       "empresa se estaba mirando."),
            ("nuevo", "Se puede buscar un indicador por su nombre, su área o "
                      "su responsable, sin preocuparse por las tildes."),
            ("mejora", "El cumplimiento del mes dice ahora cuánto subió o "
                       "bajó respecto del mes pasado, y avisa cuando está "
                       "calculado sobre unos pocos indicadores porque el "
                       "resto no se ha registrado."),
            ("nuevo", "La franja de pendientes dice quién debe registrar qué, "
                      "agrupado por persona, y desde ahí se abre cada "
                      "indicador."),
            ("mejora", "En la matriz del año, los «Gestión de OMP» y los "
                       "indicadores sin ningún registro se pliegan en un "
                       "renglón que se puede abrir, y la columna del nombre "
                       "ya no se pierde al desplazarse hasta diciembre."),
            ("nuevo", "Al abrir el portal aparece el logo mientras carga, en "
                      "vez de una pantalla en blanco."),
            ("mejora", "Los botones que guardan o recalculan muestran el "
                       "avance dentro del propio botón y dejan de responder "
                       "al segundo clic, así que ya no se puede registrar dos "
                       "veces lo mismo por impaciencia."),
            ("mejora", "Al cambiar de mes, lo que ya estaba en pantalla se "
                       "queda mientras llegan los datos nuevos, en vez de "
                       "desaparecer y volver."),
        ],
    },
    {
        "version": "0.34.0",
        "fecha": "2026-09-19",
        "titulo": "Toda nota crédito pasa primero por Coordinación Comercial",
        "cambios": [
            ("nuevo", "Las notas crédito que piden los puntos de venta ahora "
                      "las aprueba Coordinación Comercial antes de que las "
                      "vea Contabilidad. Antes entraban directo a "
                      "Contabilidad, que terminaba decidiendo sola si se le "
                      "devolvía la plata al cliente."),
            ("mejora", "Coordinación Comercial ve ahora las solicitudes de "
                       "los puntos de venta además de las institucionales, "
                       "porque le toca aprobarlas todas."),
            ("nuevo", "Al líder del área de quien pide la nota crédito le "
                      "llega copia del primer correo, para que sepa que su "
                      "sede solicitó una. No tiene que aprobar nada: es solo "
                      "para enterarse."),
        ],
    },
    {
        "version": "0.33.1",
        "fecha": "2026-09-18",
        "titulo": "En PQRS ahora se filtra por el área que la tiene hoy",
        "cambios": [
            ("mejora", "El filtro de área de la lista de PQRS ya no busca por "
                       "el área causante sino por el área a la que está "
                       "asignada la solicitud, que es lo que uno quiere ver "
                       "para saber qué le toca a su equipo."),
            ("nuevo", "El mismo filtro trae la opción «Sin asignar», para "
                      "encontrar de una las PQRS que todavía no tienen área "
                      "responsable y a las que el plazo ya les está corriendo."),
        ],
    },
    {
        "version": "0.33.0",
        "fecha": "2026-09-17",
        "titulo": "Las notas crédito de Ventas Institucionales pasan por su cadena",
        "cambios": [
            ("nuevo", "Cuando la nota crédito la pide Ventas Institucionales, "
                      "ahora recorre su camino: primero la aprueba "
                      "Coordinación Comercial y después Contabilidad verifica "
                      "ante la DIAN si la factura tiene saldo a favor. Las de "
                      "los puntos de venta siguen exactamente igual que antes."),
            ("nuevo", "Si el motivo implica producto devuelto, antes que nadie "
                      "confirma la bodega donde entró —Guayabal o La 65— que "
                      "llegó y en qué estado. Cada bodega ve solo lo suyo."),
            ("nuevo", "Además de aprobar y rechazar hay un botón de «devolver "
                      "para corregir»: la solicitud vuelve a quien la pidió sin "
                      "morirse, él la arregla y la vuelve a mandar. Es la misma "
                      "solicitud, no hay que radicar otra."),
            ("nuevo", "Cada solicitud muestra en qué paso va, qué se espera de "
                      "quien la tiene y por qué manos ya pasó, con fecha y "
                      "nombre. El filtro «Lo que me toca» deja ver de una vez "
                      "lo que está esperando por uno."),
            ("nuevo", "Quien la pidió puede retirarla mientras esté en trámite. "
                      "Retirada y rechazada se cuentan aparte: no es lo mismo "
                      "que uno se arrepienta a que la empresa la niegue."),
            ("mejora", "El filtro de la lista es un desplegable, agrupado y en "
                       "el orden del proceso: bodega, Comercial, Contabilidad, "
                       "falta emitir. Antes eran once botones en dos "
                       "renglones."),
            ("mejora", "En Administración › Capacidades están los tres permisos "
                       "nuevos, y en Admin › Usuarios se elige qué bodega "
                       "maneja cada quien."),
        ],
    },
    {
        "version": "0.32.0",
        "fecha": "2026-09-17",
        "titulo": "Pantalla de inicio de sesión nueva",
        "cambios": [
            ("mejora", "La pantalla para entrar al portal se rehízo: al lado "
                       "izquierdo la marca y qué es esto, y al derecho el "
                       "formulario. En celular el formulario ocupa toda la "
                       "pantalla."),
            ("nuevo", "El ojo al lado de la contraseña la muestra, para "
                      "revisarla antes de entrar sin tener que escribirla en "
                      "otra parte."),
            ("nuevo", "La casilla «Mantener sesión iniciada» ahora decide de "
                      "verdad: si se deja sin marcar, la sesión se cierra al "
                      "cerrar el navegador. Importa en los computadores que "
                      "se comparten, como los de los puntos de venta."),
            ("correccion", "Escribir mal la contraseña mostraba la pantalla "
                           "en blanco un momento y no decía nada. Ahora sale "
                           "el mensaje de que el correo o la contraseña no "
                           "coinciden."),
        ],
    },
    {
        "version": "0.31.0",
        "fecha": "2026-09-16",
        "titulo": "Aviso al punto de venta cuando falta emitir una nota crédito",
        "cambios": [
            ("nuevo", "Cuando una nota crédito queda aprobada, le llega un "
                      "correo al punto de venta de la factura avisando que "
                      "falta emitirla y registrar su número. Antes solo se "
                      "enteraba quien la había pedido."),
            ("mejora", "Si en ese punto de venta no hay nadie con permiso "
                       "para registrarla, el aviso va a todos los que sí "
                       "pueden: una nota crédito aprobada que nadie emite "
                       "deja al cliente esperando."),
        ],
    },
    {
        "version": "0.30.0",
        "fecha": "2026-09-16",
        "titulo": "Áreas nuevas y jefaturas que ven a su gente",
        "cambios": [
            ("nuevo", "Tres áreas nuevas: Dirección Técnica, Investigación y "
                      "Desarrollo (IDI) y Salvak."),
            ("nuevo", "En Admin › Usuarios, a cada persona se le pueden marcar "
                      "las áreas que supervisa. Verá los indicadores, las "
                      "oportunidades de mejora y los proyectos de esas áreas, "
                      "además de los de la suya."),
            ("mejora", "La supervisión es de una sola vía: el jefe ve lo de su "
                       "gente y el equipo sigue viendo solo su área, así que "
                       "la gestión de la dirección no se le muestra."),
        ],
    },
    {
        "version": "0.29.0",
        "fecha": "2026-09-15",
        "titulo": "Gestión de OMP se mide sola en cada área",
        "cambios": [
            ("nuevo", "Nuevo indicador automático «Gestión de OMP»: cada mes "
                      "dice qué parte de las OMP del área estuvo al día — sin "
                      "acciones vencidas, con algún avance en el mes y sin "
                      "pasarse de la fecha estimada. Su análisis nombra las "
                      "que quedaron atrasadas y por qué."),
            ("nuevo", "Desde Indicadores, un botón lo crea en todas las áreas "
                      "que todavía no lo tienen."),
            ("mejora", "Las acciones del plan de una OMP muestran su fecha, y "
                       "si se aplazó, cuál era la fecha comprometida: contra "
                       "esa se mide si se cumplió a tiempo."),
        ],
    },
    {
        "version": "0.28.1",
        "fecha": "2026-09-15",
        "titulo": "El filtro de proyectos cerrados ya muestra los cerrados",
        "cambios": [
            ("correccion", "Filtrar los proyectos por «Cerrado» o «Cancelado» "
                           "seguía mostrando la lista vacía: el arreglo de la "
                           "versión 0.19.4 había quedado solo en el servidor "
                           "y la pantalla nunca lo usaba. Ahora aparecen sin "
                           "tener que marcar «Ver proyectos archivados»."),
        ],
    },
    {
        "version": "0.28.0",
        "fecha": "2026-09-14",
        "titulo": "Indicadores con fórmula propia",
        "cambios": [
            ("nuevo", "Los indicadores pueden tener una fórmula personalizada, "
                      "como 80 × A ÷ B o (A − B) ÷ A × 100. Se arma con "
                      "botones, se lee en palabras y se prueba con valores de "
                      "ejemplo antes de guardar."),
            ("nuevo", "Cada mes se digitan las variables y el portal calcula "
                      "el resultado. El acumulado del trimestre y del año "
                      "suma las variables en vez de promediar resultados, "
                      "así que da el número correcto."),
        ],
    },
    {
        "version": "0.27.0",
        "fecha": "2026-09-14",
        "titulo": "Varios productos por PQRS, y corregirla sin empezar de nuevo",
        "cambios": [
            ("nuevo", "Un reclamo puede tener varios productos, cada uno con "
                      "su lote y sus cantidades, desde el formulario del "
                      "cliente y desde el interno. En el detalle se corrige "
                      "el lote de cada uno, se quita el que no era o se "
                      "agrega el que faltó."),
            ("mejora", "Un archivo elegido por error se puede quitar antes de "
                       "enviar, en los dos formularios. Antes solo se podía "
                       "cambiar por otro."),
            ("correccion", "Escribir un dato más largo de lo permitido (por "
                           "ejemplo una cantidad larga) no dejaba registrar "
                           "la PQRS y no decía por qué. Ahora el formulario "
                           "no deja pasarse y, si pasa, dice qué campo "
                           "acortar."),
            ("nuevo", "Los datos del cliente y de la factura ya se pueden "
                      "corregir desde el detalle con el botón «Editar»: un "
                      "correo mal escrito ya no deja al cliente sin la "
                      "solución ni la encuesta. Cada corrección queda en el "
                      "historial con el dato anterior."),
            ("nuevo", "La foto del producto, la factura y el video se pueden "
                      "cambiar por otro o quitar si se adjuntaron por error. "
                      "También se puede adjuntar lo que el cliente olvidó."),
            ("nuevo", "Cada punto de venta ve solo las PQRS de su sede. En "
                      "Administración › Usuarios se elige el punto de cada "
                      "persona; quien coordina todas las sedes las ve todas."),
            ("mejora", "En la lista de PQRS aparece primero el nombre de la "
                       "empresa, que es como se reconoce al cliente, y el "
                       "contacto debajo. Una persona natural sale con su "
                       "nombre, como antes."),
        ],
    },
    {
        "version": "0.26.1",
        "fecha": "2026-09-12",
        "titulo": "Cerrar una PQRS ahora pregunta antes",
        "cambios": [
            ("correccion", "Elegir «Cerrado» y guardar mandaba la encuesta al "
                           "cliente de una vez, sin avisar — un clic de más "
                           "y ya estaba enviada. Ahora pide confirmar antes "
                           "de guardar el cierre."),
        ],
    },
    {
        "version": "0.26.0",
        "fecha": "2026-09-12",
        "titulo": "El cliente ya sabe qué le solucionamos",
        "cambios": [
            ("nuevo", "Al marcar una PQRS como «resuelto» ahora hay que "
                      "escribir qué se le solucionó al cliente, con foto o "
                      "PDF si hace falta. Antes solo cambiaba el estado y el "
                      "cliente nunca se enteraba de nada hasta la encuesta."),
            ("nuevo", "Esa solución se le envía por correo, con dos botones: "
                      "«Quedó resuelto» o «Sigue el problema». Si dice que "
                      "sigue, la PQRS vuelve a quedar en proceso con su "
                      "comentario. Si no responde en 3 días hábiles, la "
                      "solicitud se cierra sola."),
            ("correccion", "Cambiar el estado de una PQRS desde el listado a "
                           "veces no hacía nada y no avisaba por qué — el "
                           "servidor rechazaba el cambio y la pantalla se "
                           "quedaba callada. Ahora dice qué pasó."),
            ("nuevo", "El correo de cierre ahora recuerda cuál fue la "
                      "solución, no solo la encuesta."),
        ],
    },
    {
        "version": "0.25.0",
        "fecha": "2026-09-08",
        "titulo": "El análisis ya no es opcional",
        "cambios": [
            ("nuevo", "Al registrar el valor mensual de un indicador ya no "
                      "basta con el número: hay que escribir qué lo explica. "
                      "Antes era una observación opcional; ahora es "
                      "obligatoria, para que el histórico sirva seis meses "
                      "después."),
        ],
    },
    {
        "version": "0.24.0",
        "fecha": "2026-09-07",
        "titulo": "Darle notas crédito a otra área, y que funcione de verdad",
        "cambios": [
            ("correccion", "Otorgarle a otra área el permiso de notas crédito "
                           "desde Administración › Capacidades no tenía "
                           "ningún efecto: la pantalla guardaba el permiso, "
                           "pero nadie lo comprobaba todavía. Ya funciona."),
            ("mejora", "El mensaje de «no tienes permiso» al autorizar una "
                      "nota crédito ahora dice quién sí puede en este "
                      "momento, en vez de nombrar siempre a Contabilidad."),
        ],
    },
    {
        "version": "0.23.0",
        "fecha": "2026-09-05",
        "titulo": "Quién puede qué, sin depender del área",
        "cambios": [
            ("nuevo", "Administración tiene una sección nueva, «Capacidades», "
                      "para decidir quién autoriza notas crédito, aprueba "
                      "presupuesto, cierra PQRS y las demás cosas que antes "
                      "solo podía hacer una sola área."),
            ("nuevo", "Se puede dar el permiso a un área completa, o a una "
                      "persona puntual cuando su área no alcanza — sin tener "
                      "que cambiarle el área a nadie ni tocar código."),
        ],
    },
    {
        "version": "0.22.0",
        "fecha": "2026-09-05",
        "titulo": "Las notas crédito ya no se piden por correo",
        "cambios": [
            ("nuevo", "Los puntos de venta y los vendedores institucionales "
                      "piden la nota crédito desde el portal: la factura, qué "
                      "pasó, el motivo y el soporte, en un solo formulario. "
                      "Está en la pestaña «Notas crédito», al lado de PQRS."),
            ("nuevo", "Contabilidad recibe el correo con la solicitud, la "
                      "aprueba o la rechaza desde el portal, y quien la pidió "
                      "se entera por correo de la respuesta."),
            ("nuevo", "Al final se registra el número de la nota crédito que se "
                      "emitió. Eso es lo que deja ver de un vistazo cuáles se "
                      "aprobaron y todavía no se han hecho — algo que por "
                      "correo era invisible."),
            ("nuevo", "Los motivos son una lista que Administración puede "
                      "cambiar, para poder responder después por qué se están "
                      "haciendo las notas crédito."),
            ("mejora", "El punto de venta se elige de una lista, no se escribe: "
                       "así el informe por almacén no queda partido entre tres "
                       "formas de escribir el mismo nombre."),
        ],
    },
    {
        "version": "0.21.0",
        "fecha": "2026-09-05",
        "titulo": "Los correos de autorización",
        "cambios": [
            ("nuevo", "Cuando alguien pide una autorización, al área que tiene "
                      "que firmarla le llega un correo diciendo cuál es, quién "
                      "la pidió y por qué. Antes había que estar mirando el "
                      "portal para enterarse."),
            ("nuevo", "Y cuando la responden, el aviso vuelve con el sí o el no "
                      "a quien está esperando para seguir con el caso."),
            ("correccion", "El botón de los correos automáticos no abría nada. "
                           "Afectaba a los cuatro, incluido el de calificar la "
                           "atención que se manda al cerrar una PQRS: el enlace "
                           "de la encuesta llevaba a una página en blanco."),
            ("correccion", "Los correos automáticos salían de una cuenta que ya "
                           "no se usa y el servidor de correo los rechazaba, así "
                           "que no llegaban."),
        ],
    },
    {
        "version": "0.20.0",
        "fecha": "2026-09-04",
        "titulo": "Gestionar una PQRS de una sola vez",
        "cambios": [
            ("mejora", "Cambiar el área, cambiar el estado, comentar y adjuntar "
                       "la evidencia ahora se hace en un solo formulario y con "
                       "un solo botón. Estaban repartidos por la pantalla y "
                       "había que escribir el mismo motivo dos veces."),
            ("correccion", "El área responsable de una PQRS solo se veía si "
                           "podías cambiarla, así que un agente no sabía en qué "
                           "área estaba el caso. Ahora se ve siempre, arriba "
                           "junto al estado."),
            ("correccion", "Aprobar o rechazar una autorización estaba limitado "
                           "a los líderes. Ahora la responde cualquiera del área "
                           "autorizadora, que es lo que el portal ya decía que "
                           "hacía."),
            ("nuevo", "Al pedir una autorización, la solicitud pasa sola al área "
                      "que la firma, y al responderla vuelve a Servicio al "
                      "Cliente. Ya no hay que moverla a mano ni acordarse."),
            ("nuevo", "A esa área le llega el correo diciéndole qué autorización "
                      "está esperando su firma y quién la pidió; y cuando "
                      "responde, el aviso vuelve con el sí o el no."),
            ("nuevo", "La solicitud de autorización y su respuesta admiten un "
                      "archivo de soporte: la factura o el concepto van con la "
                      "pregunta, no por correo aparte."),
            ("nuevo", "Se puede dejar un comentario en una PQRS sin tener que "
                      "cambiarle el estado para poder escribir."),
            ("correccion", "Cambiar el estado desde el listado de PQRS no "
                           "guardaba nada."),
        ],
    },
    {
        "version": "0.19.4",
        "fecha": "2026-09-01",
        "titulo": "Los filtros de terminados",
        "cambios": [
            ("correccion", "Filtrar los proyectos por «cerrado» o «cancelado» "
                           "devolvía una lista vacía: al cerrarlos también se "
                           "archivan, y la lista escondía lo archivado. Ya "
                           "aparecen sin tener que marcar nada más."),
            ("correccion", "Lo mismo en Mejora: filtrar por «descartada» o "
                           "«cerrada» no mostraba ninguna hasta marcar además "
                           "«ver las terminadas». Ahora elegir el estado basta."),
        ],
    },
    {
        "version": "0.19.3",
        "fecha": "2026-09-01",
        "titulo": "Descartar una oportunidad, con freno",
        "cambios": [
            ("correccion", "El botón «Descartar» de una oportunidad de mejora se "
                           "confundía con descartar lo que uno acababa de "
                           "escribir. Ahora dice «Descartar la oportunidad» y "
                           "pregunta antes de hacerlo."),
            ("nuevo", "Al descartar hay que decir por qué. Queda en la ficha y "
                      "en el historial, con el nombre de quien lo decidió."),
            ("nuevo", "Una oportunidad descartada se puede retomar. Antes no "
                      "había forma de volver atrás desde la pantalla."),
            ("mejora", "El aviso aclara que descartar NO borra la oportunidad: "
                       "queda registrada como evaluada y no seguida."),
        ],
    },
    {
        "version": "0.19.2",
        "fecha": "2026-09-01",
        "titulo": "Correcciones en proyectos",
        "cambios": [
            ("correccion", "La lista de proyectos decía «Sin asignar» en todos, "
                           "aunque tuvieran líder. Ya muestra quién lidera cada "
                           "uno."),
            ("correccion", "El líder de un área ya ve los proyectos donde su área "
                           "participa, no solo aquellos donde es la responsable. "
                           "Antes desaparecían de su lista."),
            ("mejora", "La lista de proyectos carga más rápido: traía el nombre "
                       "del líder con una consulta por proyecto."),
        ],
    },
    {
        "version": "0.19.1",
        "fecha": "2026-09-01",
        "titulo": "Lenguaje más formal",
        "cambios": [
            ("correccion", "El inicio decía «tienes 2 cosas vencidas». Ahora dice "
                           "«actividades», que además explica qué son."),
            ("mejora", "Todo lo que ve el cliente —el formulario de PQRS, la "
                       "consulta de su solicitud, las encuestas y los carteles "
                       "de los puntos de venta— pasó a tratarlo de usted."),
            ("correccion", "Se corrigieron tildes y signos de interrogación que "
                           "faltaban en textos de Master Planner."),
            ("nuevo", "Se agregó el área «Puntos de Venta»."),
        ],
    },
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
