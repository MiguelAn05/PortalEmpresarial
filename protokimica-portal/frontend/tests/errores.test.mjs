// El mensaje de error que se le muestra a la persona.
//
// Nace de un fallo real: un 422 de FastAPI trae `detail` como lista de
// objetos, y al pintarlo React lanzaba el error #31 — pantalla en blanco.
const BASE = '../src/core/errores.js'
const { mensajeDeError } = await import(BASE)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const conDetalle = (detail) => ({ response: { data: { detail } }, request: {} })

console.log('\n== Lo normal: el backend manda un texto ==')
check('se muestra tal cual',
  mensajeDeError(conDetalle('Este indicador tiene 3 mediciones.')) === 'Este indicador tiene 3 mediciones.')
check('un texto vacío cae al mensaje por defecto',
  mensajeDeError(conDetalle('   '), 'Algo salió mal.') === 'Algo salió mal.')

console.log('\n== 422: la lista de objetos que rompía la página ==')
const validacion422 = conDetalle([
  { type: 'string_too_long', loc: ['body', 'descripcion'],
    msg: 'String should have at most 300 characters', input: 'texto largo', ctx: { max_length: 300 } },
])
const salida = mensajeDeError(validacion422)
check('devuelve un texto, no un objeto', typeof salida === 'string', typeof salida)
check('nombra el campo', salida.includes('Descripcion'), salida)
check('y explica el límite en español', salida.includes('300 caracteres'), salida)
check('sin letras sueltas del inglés', !salida.includes('caracteress'), salida)
check('sin dejar rastro del inglés', !salida.includes('String should'), salida)

console.log('\n== Varios campos a la vez ==')
const dos = mensajeDeError(conDetalle([
  { type: 'missing', loc: ['body', 'titulo'], msg: 'Field required' },
  { type: 'int_parsing', loc: ['body', 'responsable_id'], msg: 'Input should be a valid integer' },
]))
check('menciona los dos', dos.includes('Titulo') && dos.includes('Responsable id'), dos)
check('traduce el obligatorio', dos.includes('obligatorio'), dos)

console.log('\n== Casos límite ==')
check('sin respuesta del servidor avisa de la conexión',
  mensajeDeError({ request: {} }).includes('conectar'), mensajeDeError({ request: {} }))
check('un error cualquiera usa el mensaje por defecto',
  mensajeDeError({}, 'No se pudo guardar.') === 'No se pudo guardar.')
check('undefined no revienta',
  typeof mensajeDeError(undefined) === 'string')
check('una lista vacía cae al por defecto',
  mensajeDeError(conDetalle([]), 'Por defecto.') === 'Por defecto.')
check('un objeto suelto con msg también se entiende',
  typeof mensajeDeError(conDetalle({ msg: 'Field required', loc: ['body', 'area'] })) === 'string')
check('un objeto sin msg no imprime [object Object]',
  !mensajeDeError(conDetalle({ cualquier: 'cosa' }), 'Falló.').includes('object'),
  mensajeDeError(conDetalle({ cualquier: 'cosa' }), 'Falló.'))

console.log('\n== El campo se lee como palabra, no como código ==')
const anidado = mensajeDeError(conDetalle([
  { type: 'missing', loc: ['body', 'acciones', 0, 'fecha_limite'], msg: 'Field required' },
]))
check('toma el último nivel y quita los guiones bajos',
  anidado.includes('Fecha limite'), anidado)
check('no muestra "body" ni el índice',
  !anidado.includes('body') && !anidado.includes('0'), anidado)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
