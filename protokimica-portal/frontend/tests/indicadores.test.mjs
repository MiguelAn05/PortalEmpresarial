// Pruebas del formato y la navegacion de periodos del modulo de Indicadores.
const BASE = '../src/modules/indicadores/constants.js'
const {
  formatValor, formatVariacion, tonoVariacion,
  periodoAnterior, periodoSiguiente, periodoPorDefecto, pestanaInicial,
  SEMAFOROS, UNIDADES, TIPOS_CAPTURA, DIRECCIONES, MESES, MESES_CORTOS,
} = await import(BASE)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Formato de valores ==')
check('un porcentaje entero no lleva decimales', formatValor(90, 'porcentaje') === '90%', formatValor(90, 'porcentaje'))
check('un porcentaje con decimal los conserva', formatValor(95.45, 'porcentaje') === '95.45%', formatValor(95.45, 'porcentaje'))
check('los dias llevan su palabra', formatValor(9, 'dias') === '9 días', formatValor(9, 'dias'))
check('el dinero sale en pesos', formatValor(2400000, 'moneda').includes('2.400.000'), formatValor(2400000, 'moneda'))
check('una cantidad va pelada', formatValor(3, 'cantidad') === '3', formatValor(3, 'cantidad'))
check('una razon va pelada', formatValor(4.3, 'razon') === '4.3', formatValor(4.3, 'razon'))
check('sin valor muestra guion', formatValor(null, 'porcentaje') === '—')
check('el cero es un dato, no un vacio', formatValor(0, 'cantidad') === '0', formatValor(0, 'cantidad'))

console.log('\n== Variaciones ==')
check('una subida lleva mas', formatVariacion(5, 'porcentaje') === '+5%', formatVariacion(5, 'porcentaje'))
check('una bajada lleva menos', formatVariacion(-5, 'porcentaje') === '−5%', formatVariacion(-5, 'porcentaje'))
check('sin cambio dice igual', formatVariacion(0, 'porcentaje') === 'igual')
check('sin comparacion no muestra nada', formatVariacion(null, 'porcentaje') === null)

console.log('\n== El tono depende de hacia donde mejora ==')
// Subir la satisfaccion es bueno; subir los accidentes es malo.
// Se compara contra el token, no contra un hex ni contra "green": los
// colores viven en index.css y aquí solo importa cuál de los tres es.
check('subir en un indicador "mejor arriba" es verde',
  tonoVariacion(5, 'arriba').includes('positivo'), tonoVariacion(5, 'arriba'))
check('bajar en un indicador "mejor arriba" es rojo',
  tonoVariacion(-5, 'arriba').includes('negativo'), tonoVariacion(-5, 'arriba'))
check('subir en un indicador "mejor abajo" es rojo',
  tonoVariacion(5, 'abajo').includes('negativo'), tonoVariacion(5, 'abajo'))
check('bajar en un indicador "mejor abajo" es verde',
  tonoVariacion(-5, 'abajo').includes('positivo'), tonoVariacion(-5, 'abajo'))
check('sin cambio es neutro', tonoVariacion(0, 'arriba') === 'text-texto-3')
// Ningun color quemado: si vuelve un hex, esto lo caza.
check('el tono no trae un hex encima', !tonoVariacion(5, 'arriba').includes('#'))

console.log('\n== Navegacion de periodos ==')
check('retrocede dentro del año',
  JSON.stringify(periodoAnterior(2026, 7)) === JSON.stringify({ anio: 2026, mes: 6 }))
check('enero retrocede a diciembre del año anterior',
  JSON.stringify(periodoAnterior(2026, 1)) === JSON.stringify({ anio: 2025, mes: 12 }),
  periodoAnterior(2026, 1))
check('avanza dentro del año',
  JSON.stringify(periodoSiguiente(2026, 7)) === JSON.stringify({ anio: 2026, mes: 8 }))
check('diciembre avanza a enero del siguiente',
  JSON.stringify(periodoSiguiente(2026, 12)) === JSON.stringify({ anio: 2027, mes: 1 }),
  periodoSiguiente(2026, 12))
const ida = periodoSiguiente(...Object.values(periodoAnterior(2026, 1)))
check('ir y volver deja donde estaba',
  JSON.stringify(periodoSiguiente(2025, 12)) === JSON.stringify({ anio: 2026, mes: 1 }))

const def = periodoPorDefecto()
const hoy = new Date()
check('el periodo por defecto no es el mes en curso',
  !(def.anio === hoy.getFullYear() && def.mes === hoy.getMonth() + 1), def)
check('y es un mes valido', def.mes >= 1 && def.mes <= 12, def)

console.log('\n== Catalogos de la interfaz ==')
check('los 4 estados del semaforo del backend existen',
  ['verde', 'amarillo', 'rojo', 'sin_datos'].every(k => SEMAFOROS[k]?.label))
check('cada semaforo tiene etiqueta de texto, no solo color',
  Object.values(SEMAFOROS).every(s => s.label && s.label.length > 2))
// El punto se dibuja en SVG, donde no hay clases de Tailwind: va como
// var(--...) para que siga saliendo de index.css y no de un hex a mano.
check('cada semaforo tiene su color de punto',
  Object.values(SEMAFOROS).every(s => /^var\(--color-[\w-]+\)$/.test(s.punto)))
check('las unidades cubren las del backend',
  ['porcentaje', 'moneda', 'dias', 'cantidad', 'razon'].every(u => UNIDADES[u]?.label))
check('los tipos de captura cubren los del backend',
  ['automatico', 'valor', 'razon'].every(t => TIPOS_CAPTURA[t]?.label))
check('cada tipo de captura se explica', Object.values(TIPOS_CAPTURA).every(t => t.ayuda))
check('las dos direcciones existen', DIRECCIONES.arriba && DIRECCIONES.abajo)
check('hay 12 meses', MESES.length === 12 && MESES_CORTOS.length === 12)
check('los meses cortos son de 3 letras', MESES_CORTOS.every(m => m.length === 3))

console.log('\n== Pestaña con la que abre cada rol ==')
check('gerencia entra a leer como va la empresa',
  pestanaInicial({ rol: 'gerencia' }) === 'como-vamos', pestanaInicial({ rol: 'gerencia' }))
check('un lider entra donde registra',
  pestanaInicial({ rol: 'lider' }) === 'tablero', pestanaInicial({ rol: 'lider' }))
check('un agente tambien',
  pestanaInicial({ rol: 'agente' }) === 'tablero', pestanaInicial({ rol: 'agente' }))
check('admin entra al tablero: tambien opera',
  pestanaInicial({ rol: 'admin' }) === 'tablero', pestanaInicial({ rol: 'admin' }))
check('lectura entra al tablero',
  pestanaInicial({ rol: 'lectura' }) === 'tablero', pestanaInicial({ rol: 'lectura' }))
check('sin usuario no revienta',
  pestanaInicial(undefined) === 'tablero', pestanaInicial(undefined))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
