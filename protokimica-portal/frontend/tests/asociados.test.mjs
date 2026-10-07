// «Asociado a»: cómo se ofrece la lista y qué área causante se propone.
//
// La lista viene del servidor; aquí se prueba lo que hace la pantalla con
// ella: agrupar, buscar sin tildes, poner primero la variante del canal y
// proponer el área sin pisar la que alguien eligió a propósito.
import { readFileSync } from 'node:fs'
import {
  LIMITES_ASOCIADO, SIN_CAUSA, agruparAsociados, areaPropuesta, coincideAsociado,
  etiquetaAsociado, tipoDeCanal,
} from '../src/modules/pqrs/asociados.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const LISTA = [
  { id: 1, codigo: 'CP', nombre: 'Calidad del Producto', grupo: 'Producto y empaque', area_sugerida: null, aplica_a: null },
  { id: 2, codigo: 'DP', nombre: 'Diferencia en peso', grupo: 'Producto y empaque', area_sugerida: null, aplica_a: null },
  { id: 3, codigo: 'ME', nombre: 'Mala Entrega (CEDI)', grupo: 'Entrega', area_sugerida: 'Logística', aplica_a: null },
  { id: 4, codigo: 'ME', nombre: 'Mala Entrega (Pventa)', grupo: 'Entrega', area_sugerida: 'Puntos de Venta', aplica_a: 'sede' },
  { id: 5, codigo: 'TR', nombre: 'Transportadora', grupo: 'Entrega', area_sugerida: 'Logística', aplica_a: null },
]
const nombres = (grupos) => grupos.flatMap(g => g.items.map(a => a.nombre))

console.log('\n== Agrupar y buscar ==')
const todos = agruparAsociados(LISTA)
check('respeta el orden de los grupos', todos.map(g => g.grupo).join('|') === 'Producto y empaque|Entrega',
  todos.map(g => g.grupo))
check('y no pierde ninguno', nombres(todos).length === LISTA.length)
check('la sigla encuentra las dos malas entregas',
  nombres(agruparAsociados(LISTA, { busqueda: 'me' })).join('|') === 'Mala Entrega (CEDI)|Mala Entrega (Pventa)',
  nombres(agruparAsociados(LISTA, { busqueda: 'me' })))
check('el nombre del grupo también busca',
  nombres(agruparAsociados(LISTA, { busqueda: 'entrega' })).length === 3)
check('sin tildes ni mayúsculas', nombres(agruparAsociados(LISTA, { busqueda: 'PESÓ' }))[0] === 'Diferencia en peso')
check('nada que coincida, ningún grupo', agruparAsociados(LISTA, { busqueda: 'zzz' }).length === 0)

console.log('\n== La variante del canal va primero ==')
const enSede = agruparAsociados(LISTA, { aplicaA: 'sede' }).find(g => g.grupo === 'Entrega')
check('la del punto de venta sube', enSede.items[0].nombre === 'Mala Entrega (Pventa)', enSede.items.map(a => a.nombre))
check('y las demás siguen en su orden', enSede.items[1].nombre === 'Mala Entrega (CEDI)' && enSede.items[2].nombre === 'Transportadora')
check('no cambia la lista original', LISTA[3].nombre === 'Mala Entrega (Pventa)' && LISTA[2].nombre === 'Mala Entrega (CEDI)')
const canales = [{ nombre: 'Punto de venta Guayabal', tipo: 'sede' }, { nombre: 'WhatsApp', tipo: 'general' }]
check('una sede es sede', tipoDeCanal(canales, 'Punto de venta Guayabal') === 'sede')
check('un canal general no prefiere nada', tipoDeCanal(canales, 'WhatsApp') === null)
check('sin canal tampoco', tipoDeCanal(canales, null) === null)

console.log('\n== El área causante se propone, no se impone ==')
const [cp, , meCedi, mePv] = LISTA
check('vacía, toma la sugerida', areaPropuesta(meCedi, null, '') === 'Logística')
check('la que puso el asociado anterior se reemplaza', areaPropuesta(mePv, meCedi, 'Logística') === 'Puntos de Venta')
check('la que alguien eligió a propósito se respeta', areaPropuesta(mePv, meCedi, 'Producción') === 'Producción')
check('un asociado sin sugerida no la borra', areaPropuesta(cp, meCedi, 'Logística') === 'Logística')

console.log('\n== Filtro y etiqueta ==')
check('sin filtro pasa todo', coincideAsociado({ asociado_id: null }, ''))
check('«Sin causa» encuentra las que faltan', coincideAsociado({ asociado_id: null }, SIN_CAUSA)
  && !coincideAsociado({ asociado_id: 3 }, SIN_CAUSA))
check('por asociado, aunque el select mande texto', coincideAsociado({ asociado_id: 3 }, '3')
  && !coincideAsociado({ asociado_id: 4 }, '3'))
check('la etiqueta lleva la sigla como el formato', etiquetaAsociado(meCedi) === '(ME) Mala Entrega (CEDI)')

console.log('\n== Los topes coinciden con el modelo ==')
const PY = readFileSync(new URL('../../backend/app/models/pqrs.py', import.meta.url), 'utf8')
for (const [campo, tope] of Object.entries(LIMITES_ASOCIADO)) {
  const m = PY.match(new RegExp(`MAX_${campo.toUpperCase()}_ASOCIADO = (\\d+)`))
  check(`${campo}: ${tope}`, m && Number(m[1]) === tope, m && m[1])
}

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
