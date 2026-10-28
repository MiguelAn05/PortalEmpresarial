// Corregir el texto de un avance de tarea.
//
// La regla (solo quien lo escribió, solo el texto) vive en el servidor; aquí
// se prueba que la pantalla la PREGUNTA en vez de decidirla, que manda solo lo
// que el endpoint espera, y que el historial sabe nombrar la corrección.
import { readFileSync } from 'node:fs'
import { CAMPOS_HISTORIAL, etiquetaCampo } from '../src/modules/masterPlanner/constants.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}
const leer = (r) => readFileSync(new URL(`../src/modules/masterPlanner/${r}`, import.meta.url), 'utf8')

console.log('\n== El permiso lo da el servidor ==')
const modal = leer('components/TareaDetailModal.jsx')
check('el botón depende de puede_corregir', modal.includes('entrada.puede_corregir'))
check('la pantalla no compara ids para decidirlo', !/usuario_id\s*===\s*user/.test(modal))
check('avances y respuestas usan la misma pieza', (modal.match(/<TextoCorregible/g) || []).length === 2)

console.log('\n== Solo viaja el texto ==')
const api = leer('api.js')
const llamada = api.slice(api.indexOf('export const corregirActualizacion'))
check('PATCH a la entrada de la tarea', llamada.includes('api.patch(') && llamada.includes('/actualizaciones/${actualizacionId}'))
check('con el comentario y nada más', /\{\s*comentario\s*\}/.test(llamada.split('.then')[0]))

console.log('\n== El historial lo nombra ==')
for (const campo of ['avance_corregido', 'respuesta_corregida']) {
  check(`${campo} tiene etiqueta`, etiquetaCampo(campo) !== campo, etiquetaCampo(campo))
  check(`${campo} se muestra antes → después`, CAMPOS_HISTORIAL[campo]?.tipo === 'texto')
}

if (fallos.length) { console.log(`\n${fallos.length} FALLARON`); process.exit(1) }
