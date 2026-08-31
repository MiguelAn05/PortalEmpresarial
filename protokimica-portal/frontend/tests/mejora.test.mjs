// El ciclo de una Oportunidad de Mejora, sin pintar nada.
// Lo que se prueba es que la pantalla no ofrezca un paso que el servidor va
// a rechazar, y que diga QUE FALTA antes de que la persona toque el boton.
import {
  CICLO, ESTADOS, ESTADOS_ACCION, CAMPOS_6M, TRATAMIENTOS, estaCerrada,
  siguienteEstado, loQueFaltaPara, textoDeAvance, estadoDelPlazo, resumen6M,
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
// Verificar ya no basta: el cierre lo firma Calidad. Un cierre sin firma es
// justo lo que el formato del SGC escribe a mano en cada fila cerrada.
check('verificada pero sin la firma de Calidad, tampoco se cierra',
  loQueFaltaPara(omp({ eficaz: false }), 'cerrada').includes('Calidad'))
check('con la validacion de Calidad ya no falta nada',
  loQueFaltaPara(omp({ eficaz: false, validado_sgc_en: '2026-08-31T10:00:00Z' }), 'cerrada') === null)

console.log('\n== Que se pide segun el tratamiento ==')
// Quien decide es el SERVIDOR: llegan pide_causa / pide_correccion /
// pide_beneficio ya resueltos. Aqui nunca se mira el nombre del tratamiento.
check('una accion de mejora no pide causa raiz',
  loQueFaltaPara(omp({ pide_causa: false, pide_beneficio: true, beneficio_mejora: 'Ahorra dos horas' }), 'ejecucion') === null)
check('pero si pide su beneficio',
  loQueFaltaPara(omp({ pide_causa: false, pide_beneficio: true }), 'ejecucion').includes('beneficio'))
check('una accion correctiva pide causa Y correccion',
  loQueFaltaPara(omp({ pide_causa: true, pide_correccion: true, causa_raiz: 'El instructivo estaba mal' }), 'ejecucion').includes('corrección'))
check('con las dos, avanza',
  loQueFaltaPara(omp({ pide_causa: true, pide_correccion: true, causa_raiz: 'Mal instructivo', correccion: 'Se rehizo el lote' }), 'ejecucion') === null)
// Sin banderas se sigue pidiendo causa: es como se comportaba antes.
check('sin tratamiento elegido se sigue pidiendo la causa raiz',
  loQueFaltaPara(omp(), 'ejecucion').includes('causa raíz'))

console.log('\n== El vocabulario del formato ==')
check('los tres tratamientos se explican en palabras',
  ['OMP', 'AC', 'AM'].every(c => TRATAMIENTOS[c]?.length > 20))
check('las 6M estan completas y en orden',
  CAMPOS_6M.length === 7 && CAMPOS_6M[0].label === 'Efecto')
check('cada M tiene su campo y su ayuda',
  CAMPOS_6M.every(m => m.campo.startsWith('causa_') && m.ayuda?.length > 5))
check('una tarea del plan tiene tres estados',
  Object.keys(ESTADOS_ACCION).length === 3 && ESTADOS_ACCION.en_curso.label === 'En curso')
check('ningun estado de tarea trae un color quemado',
  !JSON.stringify(ESTADOS_ACCION).includes('#'))

console.log('\n== Resumen de las 6M ==')
check('solo salen las que se escribieron',
  resumen6M({ causa_efecto: 'Reprocesos', causa_metodo: 'Sin instructivo' }).length === 2)
check('con la etiqueta del formato',
  resumen6M({ causa_mano_obra: 'Falta entrenamiento' })[0].label === 'Mano de obra')
// En pantalla, siete «N/A» seguidos no le dicen nada a nadie: los rellena
// el servidor al exportar, que es donde el formato los exige.
check('las vacias no se pintan', resumen6M({}).length === 0)
check('ni las de puros espacios', resumen6M({ causa_material: '   ' }).length === 0)
check('sin datos no revienta', resumen6M(null).length === 0)

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
