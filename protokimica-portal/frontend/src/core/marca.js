/**
 * La marca del portal: el logo y el nombre que se ven en pantalla.
 *
 * Antes esto estaba escrito a mano en siete sitios —menú, login, formulario
 * público, consulta de seguimiento, dos encuestas y los carteles QR— así que
 * cambiarlo era buscarlo en siete archivos y confiar en no dejar ninguno
 * atrás. Como toca cambiarlo cada cierto tiempo, vive aquí.
 *
 * ─────────────────────────────────────────────────────────────────────
 *  PARA CAMBIAR DE MARCA: cambia `ACTIVA` y corre `npm run build`.
 *  Nada más. No hay que tocar ninguna pantalla.
 * ─────────────────────────────────────────────────────────────────────
 *
 * Los logos viven en `frontend/public/`, que es lo que Vite copia a `dist/`
 * al compilar. **Poner una imagen directamente en `dist/` no sirve:**
 * `npm run build` borra esa carpeta entera y la vuelve a generar, así que el
 * archivo desaparecería en la siguiente compilación sin que nadie entienda
 * por qué.
 *
 * Esto es SOLO lo que se muestra. No tiene nada que ver con el `slug` de la
 * empresa en la base de datos, ni con el dominio de los correos, ni con la
 * URL que llevan dentro los QR ya impresos: eso sigue siendo `protokimica` y
 * cambiarlo rompería el formulario público, el catálogo y el inicio de
 * sesión. El nombre visible y la identidad técnica son dos cosas distintas.
 *
 * El día que el portal se instale en otra empresa, esto deja de ser una
 * constante y pasa a ser una columna de la empresa que el servidor sirve al
 * arrancar. Mientras tanto, un archivo es mejor que siete.
 */

const MARCAS = {
  protokimica: { nombre: 'Protokimica', logo: '/logo.png' },
  metria: { nombre: 'Metria', logo: '/logoMetria.png' },
}

/** ← La única línea que se cambia. Tiene que ser una llave de `MARCAS`. */
const ACTIVA = 'protokimica'

// Si alguien escribe una marca que no existe, mejor reventar al compilar que
// dejar el portal sin logo y sin nombre en producción.
if (!MARCAS[ACTIVA]) {
  throw new Error(
    `La marca «${ACTIVA}» no existe. Las que hay: ${Object.keys(MARCAS).join(', ')}.`,
  )
}

/** El logo que se muestra hoy. */
export const LOGO = MARCAS[ACTIVA].logo

/** El nombre que se muestra hoy. */
export const NOMBRE_EMPRESA = MARCAS[ACTIVA].nombre

/**
 * El texto alternativo de la imagen. Genérico a propósito: lo lee un lector
 * de pantalla, y si nombrara una empresa quedaría mintiendo cada vez que se
 * cambia la marca.
 */
export const LOGO_ALT = 'Logo de la empresa'
