// El ciclo de una Oportunidad de Mejora, sin pintar nada.
// Lo que se prueba es que la pantalla no ofrezca un paso que el servidor va
// a rechazar, y que diga QUE FALTA antes de que la persona toque el boton.
import {
  CICLO, ESTADOS, estaCerrada, siguienteEstado, loQueFaltaPara, textoDeAvance,
  estadoDelPlazo,
} from '../src/modules/mejora/constants.js'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const omp = (extra = {}) => ({
  estado: 'abierta', causa_raiz: null, total_acciones: 0, eficaz: null, ...extra,
})

console.log('\n== El vocabulario ==')
check('todo estado del ciclo tiene etiqueta',
  CICLO.every(e => ESTADOS[e]?.label))
check('y una ayuda que explica que significa',
  CICLO.every(e => ESTADOS[e]?.ayuda?.length > 10))
check('descartada existe pero no es un paso del ciclo',
  ESTADOS.descartada && !CICLO.includes('descartada'))
check('ningun estado trae un color quemado',
  !JSON.stringify(ESTADOS).includes('#'))

console.log('\n== El siguiente paso ==')
check('una abierta pasa a analisis', siguienteEstado(omp()) === 'analisis')
check('de analisis a ejecucion', siguienteEstado(omp({ estado: 'analisis' })) === 'ejecucion')
check('de ejecucion a verificacion', siguienteEstado(omp({ estado: 'ejecucion' })) === 'verificacion')
check('de verificacion a cerrada', siguienteEstado(omp({ estado: 'verificacion' })) === 'cerrada')
// Lo importante: de una cerrada no se sale.
check('una cerrada ya no avanza', siguienteEstado(omp({ estado: 'cerrada' })) === null)
check('una descartada tampoco', siguienteEstado(omp({ estado: 'descartada' })) === null)
check('sin datos no revienta', siguienteEstado(null) === null)
check('un estado raro no inventa un paso',
  siguienteEstado(omp({ estado: 'inventado' })) === null)

console.log('\n== Que falta para avanzar ==')
check('sin causa raiz no se ejecuta',
  loQueFaltaPara(omp(), 'ejecucion').includes('causa raíz'))
check('con causa raiz ya no falta nada',
  loQueFaltaPara(omp({ causa_raiz: 'El proveedor entrega tarde' }), 'ejecucion') === null)
// Una causa raiz de puros espacios no es una causa raiz.
check('una causa raiz en blanco no cuenta',
  loQueFaltaPara(omp({ causa_raiz: '   ' }), 'ejecucion') !== null)
check('sin acciones no se verifica',
  loQueFaltaPara(omp(), 'verificacion').includes('acción'))
check('con acciones si',
  loQueFaltaPara(omp({ total_acciones: 2 }), 'verificacion') === null)
check('sin verificar no se cierra',
  loQueFaltaPara(omp(), 'cerrada').includes('eficacia'))
check('verificada como NO eficaz ya deja cerrar el paso',
  loQueFaltaPara(omp({ eficaz: false }), 'cerrada') === null)

console.log('\n== Texto del boton ==')
check('cada paso tiene su texto',
  ['analisis', 'ejecucion', 'verificacion', 'cerrada']
    .every(e => textoDeAvance(e).length > 5))
check('un estado desconocido no deja el boton vacio',
  textoDeAvance('loquesea') === 'Avanzar')

console.log('\n== Estado del plazo ==')
const hoy = new Date(2026, 7, 19)
const con = (fecha, estado = 'ejecucion') => ({ ...omp({ estado }), fecha_limite: fecha })
check('sin fecha no hay plazo', estadoDelPlazo(omp(), hoy) === 'sin_plazo')
check('la de ayer esta vencida',
  estadoDelPlazo(con(new Date(2026, 7, 18)), hoy) === 'vencida')
check('la de hoy esta por vencer',
  estadoDelPlazo(con(new Date(2026, 7, 19)), hoy) === 'por_vencer')
check('en dos dias tambien',
  estadoDelPlazo(con(new Date(2026, 7, 21)), hoy) === 'por_vencer')
check('en un mes va en plazo',
  estadoDelPlazo(con(new Date(2026, 8, 19)), hoy) === 'en_plazo')
// Una cerrada no se pinta de rojo para siempre: entrena a ignorar el rojo.
check('una cerrada con fecha pasada no sale vencida',
  estadoDelPlazo(con(new Date(2026, 7, 1), 'cerrada'), hoy) === 'sin_plazo')

console.log('\n== Cerrada ==')
check('cerrada esta cerrada', estaCerrada({ estado: 'cerrada' }) === true)
check('descartada tambien', estaCerrada({ estado: 'descartada' }) === true)
check('en ejecucion no', estaCerrada({ estado: 'ejecucion' }) === false)
check('sin datos no revienta', estaCerrada(null) === false)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
