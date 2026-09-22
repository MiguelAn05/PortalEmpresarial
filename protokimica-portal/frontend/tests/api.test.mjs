// Cuándo se repite una petición que falló.
//
// Reintentar lo que el servidor ya contestó con un 403 o un 404 es pedir tres
// veces lo mismo para recibir la misma negativa, y además retrasa el mensaje
// de error: la pantalla se queda cargando mientras espera entre intentos.
const { debeReintentar, esPeticionDeLogin } = await import('../src/core/api.js')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const con = (status) => ({ response: { status } })

console.log('\n== Lo que el servidor ya decidió no se vuelve a preguntar ==')
check('un 404 no se reintenta', debeReintentar(0, con(404)) === false)
check('un 403 tampoco', debeReintentar(0, con(403)) === false)
check('ni un 422 de validación', debeReintentar(0, con(422)) === false)

console.log('\n== Lo que puede cambiar solo se intenta una vez más ==')
check('un 500 se reintenta una vez', debeReintentar(0, con(500)) === true)
check('pero no dos', debeReintentar(1, con(500)) === false)
check('sin respuesta (red caída) también', debeReintentar(0, { request: {} }) === true)
check('un error sin forma no revienta', typeof debeReintentar(0, undefined) === 'boolean')

console.log('\n== El login sigue siendo un caso aparte ==')
check('se reconoce la petición de login', esPeticionDeLogin('/auth/login'))
check('y no cualquier otra', !esPeticionDeLogin('/pqrs'))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
