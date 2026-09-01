/**
 * La marca del portal, en un solo sitio.
 *
 * Antes el logo estaba escrito a mano en cinco pantallas —menú, login,
 * formulario público, consulta de seguimiento y encuesta— así que cambiarlo
 * era buscarlo en cinco archivos y confiar en no dejar ninguno atrás.
 *
 * **Para volver al logo de Protokimica: cambia `LOGO` a `/logo.png`.** Eso
 * es todo; no hay que tocar ninguna pantalla.
 *
 * Los archivos viven en `frontend/public/`, que es lo que Vite copia a
 * `dist/`. Poner una imagen directamente en `dist/` no sirve: `npm run
 * build` borra esa carpeta entera y la vuelve a generar.
 *
 * El día que el portal se instale en otra empresa, esto deja de ser una
 * constante y pasa a ser una columna de la empresa que el servidor sirve al
 * arrancar. Mientras tanto, un archivo es mejor que cinco.
 */

/** El logo que se muestra hoy. */
export const LOGO = '/logoMetria.png'

/** El logo anterior, para volver atrás sin buscar el nombre del archivo. */
export const LOGO_ANTERIOR = '/logo.png'

/**
 * El nombre que se muestra en pantalla.
 *
 * **Solo para mostrar.** No tiene nada que ver con el `slug` de la empresa en
 * la base de datos ni con el dominio de los correos: eso sigue siendo
 * `protokimica` y cambiarlo rompería el formulario público, el catálogo y el
 * inicio de sesión. Esto es únicamente el texto que lee una persona.
 */
export const NOMBRE_EMPRESA = 'Metria'

/**
 * El texto alternativo de la imagen. Va aparte del nombre comercial porque
 * lo lee un lector de pantalla, no un cliente.
 */
export const LOGO_ALT = 'Logo de la empresa'
