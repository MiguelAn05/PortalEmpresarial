// Lógica pura del módulo de Encuestas: slug del QR, niveles y formato.
const BASE = '../src/modules/encuestas/constants.js'
const {
  normalizarSlug, nivelCalificacion, formatNota, urlPublica,
  NIVELES, TIPOS_PREGUNTA, ESCALA_MAX,
} = await import(BASE)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Direccion del enlace (va impresa en el QR) ==')
check('quita las tildes',
  normalizarSlug('Calificación Vendedores') === 'calificacion-vendedores',
  normalizarSlug('Calificación Vendedores'))
check('los espacios se vuelven guiones',
  normalizarSlug('encuesta de proveedores') === 'encuesta-de-proveedores',
  normalizarSlug('encuesta de proveedores'))
check('quita signos que romperian la URL',
  normalizarSlug('¿Cómo vamos?') === 'como-vamos', normalizarSlug('¿Cómo vamos?'))
check('no deja guiones sueltos en los extremos',
  normalizarSlug('  vendedores  ') === 'vendedores', normalizarSlug('  vendedores  '))
check('no encadena guiones repetidos',
  normalizarSlug('a   b') === 'a-b', normalizarSlug('a   b'))
check('la ñ no se pierde entera',
  normalizarSlug('Año 2026') === 'ano-2026', normalizarSlug('Año 2026'))
check('vacio no revienta', normalizarSlug('') === '' && normalizarSlug(null) === '')
check('se recorta a 60 caracteres',
  normalizarSlug('a'.repeat(80)).length === 60, normalizarSlug('a'.repeat(80)).length)

console.log('\n== Niveles de calificacion ==')
check('4 o mas esta bien', nivelCalificacion(4) === 'bueno' && nivelCalificacion(5) === 'bueno')
check('entre 3 y 4 es regular',
  nivelCalificacion(3) === 'regular' && nivelCalificacion(3.9) === 'regular')
check('por debajo de 3 esta mal',
  nivelCalificacion(2.9) === 'malo' && nivelCalificacion(1) === 'malo')
check('sin nota se distingue de una nota mala',
  nivelCalificacion(null) === 'sin_datos' && nivelCalificacion(undefined) === 'sin_datos')
check('cada nivel trae etiqueta, no solo color',
  Object.values(NIVELES).every(n => n.label && n.punto))

console.log('\n== Formato ==')
check('una nota se muestra con un decimal', formatNota(4.35) === '4.3', formatNota(4.35))
check('un entero tambien lleva decimal', formatNota(5) === '5.0', formatNota(5))
check('sin nota muestra guion', formatNota(null) === '—')
check('el cero es una nota, no un vacio', formatNota(0) === '0.0', formatNota(0))

console.log('\n== Configuracion ==')
check('la escala es de 5', ESCALA_MAX === 5)
check('los tipos de pregunta coinciden con los del backend',
  ['escala', 'opcion', 'si_no', 'texto'].every(t => TIPOS_PREGUNTA[t]?.label))
check('cada tipo se explica', Object.values(TIPOS_PREGUNTA).every(t => t.ayuda))
check('la url publica es corta', urlPublica('vendedores').endsWith('/e/vendedores'),
  urlPublica('vendedores'))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
