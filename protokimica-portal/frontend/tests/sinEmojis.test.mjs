/**
 * La interfaz no lleva emojis.
 *
 * No es una manía de estilo. Un emoji se dibuja distinto en cada sistema
 * operativo (el mismo 📋 es gris en Windows y beige en Android), no hereda el
 * color del texto, no se puede alinear con el resto de los iconos y es lo
 * primero que delata que una pantalla es un prototipo. Los iconos del portal
 * son SVG de `core/components/Iconos.jsx`: una familia, un grosor, y se
 * pintan con `text-...` como cualquier otra cosa.
 *
 * Esta prueba existe porque el barrido de emojis se hizo una vez, a mano, y
 * sin algo que lo vigile vuelven de a uno, en cualquier `git pull`.
 *
 * Los símbolos de puntuación de verdad —la flecha «→», el guion largo «—», el
 * punto «·»— no cuentan: son texto y se componen con la fuente. Lo que no
 * entra son las caritas, los objetos y los símbolos de colores.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'

const aqui = dirname(fileURLToPath(import.meta.url))
const raiz = join(aqui, '..', 'src')

// Los rangos donde viven emojis y pictogramas de colores.
//
// Deliberadamente NO incluye flechas (U+2190…), rayas de dibujo (U+2500…, las
// de los comentarios `// ── Sección ──`) ni signos matemáticos: eso es
// puntuación, se compone con la fuente del texto y no tiene nada de emoji.
const EMOJI = new RegExp(
  '[' +
  '⌚-⌛' +          // relojes
  '⏩-⏺' +          // controles de reproducción, reloj de arena
  '☀-➿' +          // símbolos varios y dingbats: ⚠ ✅ ✕ ⭐ ✂
  '⬀-⯿' +          // flechas y formas de colores
  '️' +                 // el selector que vuelve emoji al símbolo anterior
  '\u{1F000}-\u{1FAFF}' +    // el grueso: caritas, objetos, banderas
  ']',
  'gu',
)

function archivos(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => {
    const ruta = join(dir, e.name)
    if (e.isDirectory()) return archivos(ruta)
    return /\.(jsx?|css)$/.test(e.name) ? [ruta] : []
  })
}

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${extra}` : ''))
  if (!cond) fallos.push(n)
}

const encontrados = []
for (const ruta of archivos(raiz)) {
  const lineas = readFileSync(ruta, 'utf8').split('\n')
  lineas.forEach((linea, i) => {
    for (const s of linea.match(EMOJI) || []) {
      encontrados.push(`${relative(raiz, ruta)}:${i + 1}  ${s}`)
    }
  })
}

console.log('\n== La interfaz no lleva emojis ==')
check(
  'ningun emoji en src/',
  encontrados.length === 0,
  encontrados.length ? `\n     ${encontrados.slice(0, 25).join('\n     ')}` : '',
)

// Que la prueba de verdad esté mirando algo: si el recorrido se rompe y no
// lee ningún archivo, pasaría siempre y no nos enteraríamos.
check('recorre el arbol de src', archivos(raiz).length > 20)
// Y que sepa reconocer un emoji cuando lo ve.
check('reconoce un emoji de prueba', (['\u{1F4CB}'].join('').match(EMOJI) || []).length === 1)
check('no confunde una flecha con un emoji', !('→'.match(EMOJI)))
check('ni las rayas de los comentarios', !('──'.match(EMOJI)))

console.log()
if (fallos.length) {
  console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`)
  process.exit(1)
}
console.log('TODAS LAS PRUEBAS PASARON')
