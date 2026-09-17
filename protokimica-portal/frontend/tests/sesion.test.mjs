// Donde se guarda la sesion decide si el siguiente que prenda ese computador
// entra con la cuenta del anterior. En los puntos de venta el computador es
// compartido, asi que la casilla «Mantener sesion iniciada» tiene que hacer
// algo de verdad: sin marcar, la sesion muere con la pestana.
//
// Node no tiene localStorage, asi que se falsean los dos almacenes. Lo que se
// prueba no es el navegador: es la regla de en cual de los dos se escribe y,
// sobre todo, que el OTRO quede limpio.
import assert from 'node:assert'

function almacenFalso(rompe = false) {
  const datos = new Map()
  return {
    datos,
    getItem: (k) => { if (rompe) throw new Error('bloqueado'); return datos.has(k) ? datos.get(k) : null },
    setItem: (k, v) => { if (rompe) throw new Error('bloqueado'); datos.set(k, String(v)) },
    removeItem: (k) => { if (rompe) throw new Error('bloqueado'); datos.delete(k) },
  }
}

let local = almacenFalso()
let sesion = almacenFalso()
globalThis.window = { get localStorage() { return local }, get sessionStorage() { return sesion } }

const {
  CLAVE_TOKEN, CLAVE_USUARIO,
  guardarSesion, limpiarSesion, tokenGuardado, usuarioGuardado,
  recordarPreferido, guardarPreferenciaRecordar,
} = await import('../src/core/sesion.js')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}
const reiniciar = () => { local = almacenFalso(); sesion = almacenFalso() }

const USUARIO = { id: 7, nombre: 'Ana', rol: 'lider' }

console.log('\n== Marcada: sobrevive cerrar el navegador ==')
reiniciar()
guardarSesion('tok-1', USUARIO, true)
check('el token queda en el almacen persistente', local.datos.get(CLAVE_TOKEN) === 'tok-1', [...local.datos])
check('y no en el de la pestana', !sesion.datos.has(CLAVE_TOKEN), [...sesion.datos])
check('se lee de vuelta', tokenGuardado() === 'tok-1')
check('el usuario vuelve convertido', usuarioGuardado()?.nombre === 'Ana', usuarioGuardado())

console.log('\n== Sin marcar: muere con la pestana ==')
reiniciar()
guardarSesion('tok-2', USUARIO, false)
check('el token queda solo en la pestana', sesion.datos.get(CLAVE_TOKEN) === 'tok-2', [...sesion.datos])
check('nada persistente', local.datos.size === 0, [...local.datos])
check('se lee igual', tokenGuardado() === 'tok-2')

console.log('\n== Guardar limpia el otro almacen ==')
// El caso peligroso: alguien entro marcando la casilla y despues entra sin
// marcarla. Si el token viejo se quedara, al cerrar la pestana seguiria
// dentro — justo lo contrario de lo que acaba de elegir.
reiniciar()
guardarSesion('tok-viejo', USUARIO, true)
guardarSesion('tok-nuevo', { ...USUARIO, id: 9 }, false)
check('no queda rastro del recordado', !local.datos.has(CLAVE_TOKEN), [...local.datos])
check('manda el nuevo', tokenGuardado() === 'tok-nuevo')
check('y el usuario es el nuevo', usuarioGuardado()?.id === 9, usuarioGuardado())

reiniciar()
guardarSesion('tok-pestana', USUARIO, false)
guardarSesion('tok-recordado', USUARIO, true)
check('y al contrario tambien', !sesion.datos.has(CLAVE_TOKEN), [...sesion.datos])
check('manda el recordado', tokenGuardado() === 'tok-recordado')

console.log('\n== Cerrar sesion borra en los dos lados ==')
reiniciar()
guardarSesion('tok-a', USUARIO, true)
sesion.datos.set(CLAVE_TOKEN, 'tok-b')   // como si otra pestana hubiera entrado
sesion.datos.set(CLAVE_USUARIO, JSON.stringify(USUARIO))
limpiarSesion()
check('no queda token en ninguno', tokenGuardado() === null, [[...local.datos], [...sesion.datos]])
check('ni usuario', usuarioGuardado() === null)

console.log('\n== Un navegador que no deja guardar no deja a nadie fuera ==')
// En modo privado tocar localStorage LANZA. Si eso subiera, nadie podria
// entrar: la sesion se queda en memoria y recargar pide entrar otra vez.
local = almacenFalso(true)
sesion = almacenFalso(true)
let reventó = false
try {
  guardarSesion('tok', USUARIO, true)
  check('leer no revienta', tokenGuardado() === null)
  check('el usuario tampoco', usuarioGuardado() === null)
  limpiarSesion()
  check('la preferencia cae en el valor por defecto', recordarPreferido() === true)
  guardarPreferenciaRecordar(false)
} catch (e) {
  reventó = e.message
}
check('nada de esto lanza', reventó === false, reventó)

console.log('\n== La casilla se recuerda ==')
reiniciar()
check('por defecto viene marcada', recordarPreferido() === true)
guardarPreferenciaRecordar(false)
check('si dijo que no, se respeta', recordarPreferido() === false, [...local.datos])
guardarPreferenciaRecordar(true)
check('y se puede volver a marcar', recordarPreferido() === true)

console.log('\n== Un JSON corrupto no tumba el arranque ==')
reiniciar()
local.datos.set(CLAVE_USUARIO, '{"nombre": "Ana"')   // se corto a medias
check('se ignora en vez de reventar', usuarioGuardado() === null)

console.log('\n== Un 401 del login no es una sesion vencida ==')
// Son el mismo codigo y no la misma cosa: al entrar, el 401 es la respuesta
// esperada a una contrasena equivocada y la pantalla ya lo muestra. Mandar
// ahi a /login recargaba la pagina y se llevaba el mensaje por delante.
const { esPeticionDeLogin } = await import('../src/core/api.js')
check('el inicio de sesion se reconoce', esPeticionDeLogin('/auth/login') === true)
check('tambien con la base delante', esPeticionDeLogin('/api/auth/login') === true)
check('cualquier otra cosa no', esPeticionDeLogin('/pqrs') === false)
check('ni una ruta que solo lo contenga', esPeticionDeLogin('/auth/login/intentos') === false)
check('ni undefined', esPeticionDeLogin(undefined) === false)

console.log('')
if (fallos.length) {
  console.log(`FALLARON ${fallos.length}: ${fallos.join(' | ')}`)
  process.exit(1)
}
assert.ok(true)
console.log('Todo bien.')
