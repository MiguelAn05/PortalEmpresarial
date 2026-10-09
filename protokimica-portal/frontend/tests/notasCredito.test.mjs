// La cadena de las notas credito tiene dos ramas y la pantalla tiene que
// preguntar lo justo: la bodega solo cuando hay producto de por medio Y la
// pide Ventas Institucionales. Preguntarla de mas seria un campo obligatorio
// que un punto de venta no sabe responder; de menos, una solicitud que el
// servidor rechaza despues de haberla escrito toda.
//
// Las bodegas ya no son una lista aqui: son una sola tabla para todo el
// portal, con sus responsables (Administracion > Bodegas), y la pantalla las
// pide al servidor. Lo que se prueba es que nadie vuelva a escribir su lista.
import { readFileSync } from 'node:fs'
import { nombresDeBodegas } from '../src/core/bodegas.js'
import {
  ESTADOS, ESTADOS_ABIERTOS, FILTROS, clavesDeFiltro, esInstitucional,
  describirPaso, estaAbierta, etiquetaEstado, faltaEnSolicitud, pideBodega,
  MAX_FACTURA, MAX_NUMERO_NC, MAX_OBSERVACIONES,
} from '../src/modules/notas_credito/constants.js'

const NC_PANTALLA = readFileSync(new URL('../src/modules/notas_credito/NotasCredito.jsx', import.meta.url), 'utf8')
const ADMIN = readFileSync(new URL('../src/modules/admin/Admin.jsx', import.meta.url), 'utf8')
const CORE_BODEGAS = readFileSync(new URL('../src/core/bodegas.js', import.meta.url), 'utf8')
const PY_MODELO = readFileSync(new URL('../../backend/app/models/nota_credito.py', import.meta.url), 'utf8')
const PY_SCHEMAS = readFileSync(new URL('../../backend/app/modules/notas_credito/schemas.py', import.meta.url), 'utf8')
const PY_FLUJO = readFileSync(new URL('../../backend/app/modules/notas_credito/flujo.py', import.meta.url), 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const PUNTO = 'Punto de venta Guayabal'
const INSTITUCIONAL = 'Venta institucional'
// Los canales llegan del servidor; aquí, como los siembra Protokimica.
const CANALES = [
  { nombre: INSTITUCIONAL, tipo: 'institucional', prefijo: 'VI' },
  { nombre: PUNTO, tipo: 'sede', prefijo: 'PVG' },
  { nombre: 'WhatsApp', tipo: 'general', prefijo: null },
]
const CON_PRODUCTO = { id: 1, nombre: 'Devolución de mercancía', requiere_bodega: true }
const SIN_PRODUCTO = { id: 2, nombre: 'Error de digitación', requiere_bodega: false }

console.log('\n== Una sola lista de bodegas, la del servidor ==')
// Habia dos listas que no se conocian: esta, escrita a mano con Guayabal y
// La 65 (sin el CD), y la de despacho de PQRS. Una bodega nueva aparecia en
// una pantalla y en la otra no.
check('core/bodegas.js no trae una lista escrita a mano',
  !/['"](Guayabal|La 65|CD)['"]/.test(CORE_BODEGAS))
check('el formulario de nota credito las pide al servidor',
  /useBodegas\(\)/.test(NC_PANTALLA) && !/BODEGAS\b/.test(NC_PANTALLA))
check('los nombres salen de lo que llega',
  JSON.stringify(nombresDeBodegas([{ id: 1, nombre: 'CD' }, { id: 2, nombre: 'Guayabal' }])) === '["CD","Guayabal"]')
check('sin lista todavia, ninguna', nombresDeBodegas(undefined).length === 0)
// El responsable se elige en la bodega, no en cada usuario.
check('Administracion > Usuarios ya no marca la bodega de cada persona',
  !/SelectBodega|u\.bodega/.test(ADMIN))

console.log('\n== Cuando se pregunta la bodega ==')
check('institucional y con producto: se pregunta',
  pideBodega(INSTITUCIONAL, CON_PRODUCTO, CANALES) === true)
check('institucional sin producto: no',
  pideBodega(INSTITUCIONAL, SIN_PRODUCTO, CANALES) === false)
check('un punto de venta, aunque el motivo traiga producto: tampoco',
  pideBodega(PUNTO, CON_PRODUCTO, CANALES) === false)
check('sin motivo elegido: tampoco', pideBodega(INSTITUCIONAL, undefined, CANALES) === false)
// Lo que mordía: comparar con el NOMBRE. Renombrado el canal, la pantalla
// dejaba de preguntar la bodega y el servidor la seguía exigiendo.
const RENOMBRADO = [{ nombre: 'Ventas Institucionales', tipo: 'institucional', prefijo: 'VI' }]
check('institucional es por el TIPO: renombrado, se sigue preguntando',
  pideBodega('Ventas Institucionales', CON_PRODUCTO, RENOMBRADO) === true)
check('y un canal con ese nombre pero de otro tipo no lo es',
  esInstitucional(INSTITUCIONAL, [{ nombre: INSTITUCIONAL, tipo: 'general' }]) === false)
check('sin la lista de canales todavía, no pregunta', pideBodega(INSTITUCIONAL, CON_PRODUCTO, []) === false)
const PANTALLA = readFileSync(new URL('../src/modules/notas_credito/constants.js', import.meta.url), 'utf8')
check('nadie vuelve a comparar con el nombre escrito a mano',
  !/['"]Venta institucional['"]/.test(PANTALLA))

console.log('\n== Que le falta al formulario ==')
const base = {
  punto_venta: INSTITUCIONAL,
  factura_afectada: 'FV-1',
  observaciones: 'Devolvieron dos canecas.',
  bodega: '',
}
check('sin canal, lo dice', /punto de venta|canal/i.test(faltaEnSolicitud({ ...base, punto_venta: '' }, SIN_PRODUCTO, CANALES)))
check('sin factura, lo dice', /factura/i.test(faltaEnSolicitud({ ...base, factura_afectada: '  ' }, SIN_PRODUCTO, CANALES)))
check('sin relato, lo dice', /pas/i.test(faltaEnSolicitud({ ...base, observaciones: '' }, SIN_PRODUCTO, CANALES)))
check('con producto y sin bodega, lo dice',
  /bodega/i.test(faltaEnSolicitud(base, CON_PRODUCTO, CANALES)), faltaEnSolicitud(base, CON_PRODUCTO, CANALES))
check('con la bodega puesta, ya no falta nada',
  faltaEnSolicitud({ ...base, bodega: 'Guayabal' }, CON_PRODUCTO, CANALES) === null)
check('sin producto no se exige bodega',
  faltaEnSolicitud(base, SIN_PRODUCTO, CANALES) === null)
check('lo que falta se dice con palabras, no con un booleano',
  typeof faltaEnSolicitud({ ...base, punto_venta: '' }, SIN_PRODUCTO, CANALES) === 'string')

console.log('\n== Los estados dicen lo mismo que el modelo ==')
const estadosPy = [...PY_MODELO.matchAll(/^ESTADO_[A-Z_]+ = "([a-z_]+)"/gm)].map(m => m[1])
check('la pantalla sabe pintar todos los estados del backend',
  estadosPy.every(e => e in ESTADOS), { python: estadosPy, pantalla: Object.keys(ESTADOS) })
check('y no se inventa ninguno',
  Object.keys(ESTADOS).every(e => estadosPy.includes(e)), Object.keys(ESTADOS))

const abiertosPy = [...PY_MODELO.match(/^ESTADOS_ABIERTOS = \((.*?)\)/ms)[1]
  .matchAll(/ESTADO_([A-Z_]+)/g)].map(m => m[1])
// Se comparan los NOMBRES y no solo cuántos son: dos listas del mismo largo
// pueden decir cosas distintas, que es justo lo que pasa cuando se quita un
// estado de un lado y se agrega otro del otro.
const abiertosJs = [...ESTADOS_ABIERTOS].sort()
check('los abiertos son exactamente los mismos',
  JSON.stringify(abiertosPy.map(e => e.toLowerCase()).sort()) === JSON.stringify(abiertosJs),
  { python: abiertosPy, js: ESTADOS_ABIERTOS })
check('y «solicitada» ya no es uno de ellos: ese turno no existe',
  !ESTADOS_ABIERTOS.includes('solicitada'), ESTADOS_ABIERTOS)
check('una devuelta sigue ABIERTA: espera a quien la pidio', estaAbierta('devuelta') === true)
check('una cancelada no', estaAbierta('cancelada') === false)
check('una aplicada tampoco', estaAbierta('aplicada') === false)

console.log('\n== Los filtros van en el orden del flujo ==')
// Salian «Contabilidad, bodega, Comercial» porque la lista se armaba
// recorriendo los estados tal como estaban declarados. El orden de una lista
// es una afirmacion sobre el proceso aunque nadie la escriba, y esa decia que
// el flujo empieza por Contabilidad.
const esperando = FILTROS.find(f => f.grupo === 'Esperando a').opciones.map(o => o.clave)
check('bodega, comercial, contabilidad, emitir, corregir',
  JSON.stringify(esperando) ===
  JSON.stringify(['bodega', 'comercial', 'contabilidad', 'por_emitir', 'devueltas']), esperando)

const estadosEnOrden = Object.keys(ESTADOS)
check('y los estados tambien: la bodega antes que Comercial',
  estadosEnOrden.indexOf('en_bodega') < estadosEnOrden.indexOf('en_comercial'), estadosEnOrden)
check('y Comercial antes que Contabilidad',
  estadosEnOrden.indexOf('en_comercial') < estadosEnOrden.indexOf('en_contabilidad'), estadosEnOrden)

console.log('\n== Cada filtro existe en el servidor ==')
const gruposPy = [...PY_FLUJO.match(/^GRUPOS_FILTRO: dict\[str, tuple\[str, \.\.\.\]\] = \{(.*?)^\}/ms)[1]
  .matchAll(/^\s+"([a-z_]+)":/gm)].map(m => m[1])
const claves = clavesDeFiltro().filter(c => c && c !== 'mi_turno')
check('la pantalla no pide un grupo que el backend no conoce',
  claves.every(c => gruposPy.includes(c)), { pantalla: claves, servidor: gruposPy })
check('ni el backend define uno que nadie ofrece',
  gruposPy.every(g => claves.includes(g)), { servidor: gruposPy, pantalla: claves })
check('«Todas» va sin filtro', clavesDeFiltro().includes(''))
check('y «lo que me toca» lo resuelve el servidor', clavesDeFiltro().includes('mi_turno'))

console.log('\n== En el mostrador Contabilidad ya no tiene turno ==')
// Tenia uno —el estado `solicitada`— entre Comercial y la emision, y sobraba:
// la decision comercial ya estaba tomada y ante la DIAN no hay nada que
// verificar en una venta de mostrador.
check('la cadena del mostrador son dos pasos',
  /if not institucional:\s*\n\s*return \(ESTADO_EN_COMERCIAL, ESTADO_APROBADA\)/
    .test(PY_FLUJO))
check('el filtro de Contabilidad cubre solo el turno de la DIAN',
  /"contabilidad":\s*\(ESTADO_EN_CONTABILIDAD,\)/.test(PY_FLUJO))
// `solicitada` sigue teniendo etiqueta: es una etapa del HISTORIAL, y las que
// paso por ella en su dia tienen que poder decir en que paso fue.
check('«solicitada» conserva su nombre para el historial',
  etiquetaEstado('solicitada') === etiquetaEstado('en_contabilidad'),
  [etiquetaEstado('solicitada'), etiquetaEstado('en_contabilidad')])
check('ninguna etiqueta menciona la DIAN: eso es QUE hacer, no donde esta',
  !Object.values(ESTADOS).some(e => /DIAN/i.test(e.label)))

console.log('\n== Ningun estado se muestra con su nombre de columna ==')
for (const estado of Object.keys(ESTADOS)) {
  check(`«${estado}» se dice en palabras`,
    !etiquetaEstado(estado).includes('_'), etiquetaEstado(estado))
}

console.log('\n== El historial se lee, no se descifra ==')
// «Aprobar» no significa lo mismo en cada paso: en la bodega es que el
// producto llego, en Contabilidad que la factura tiene saldo en la DIAN.
// Decir «aprobo» las cuatro veces haria ilegible justo lo que se audita.
const enBodega = describirPaso({ etapa: 'en_bodega', accion: 'aprobar', usuario_nombre: 'Ana' })
const enDian = describirPaso({ etapa: 'en_contabilidad', accion: 'aprobar', usuario_nombre: 'Ana' })
check('la bodega confirma que el producto está bien', /producto/i.test(enBodega) && /bien/i.test(enBodega), enBodega)
check('Contabilidad verifica en la DIAN', /DIAN/i.test(enDian), enDian)
check('y no dicen lo mismo', enBodega !== enDian)
check('devolver se distingue de rechazar',
  describirPaso({ etapa: 'en_comercial', accion: 'devolver', usuario_nombre: 'Ana' })
  !== describirPaso({ etapa: 'en_comercial', accion: 'rechazar', usuario_nombre: 'Ana' }))
check('sin nombre no queda un renglon huerfano',
  describirPaso({ etapa: 'en_bodega', accion: 'creada' }).startsWith('Alguien'),
  describirPaso({ etapa: 'en_bodega', accion: 'creada' }))

console.log('\n== Las acciones son las del flujo del backend ==')
const accionesPy = [...PY_FLUJO.matchAll(/^ACCION_[A-Z]+ = "([a-z]+)"/gm)].map(m => m[1])
for (const accion of accionesPy) {
  const texto = describirPaso({ etapa: 'en_comercial', accion, usuario_nombre: 'Ana' })
  check(`«${accion}» se redacta`, !texto.includes(' · '), texto)
}

console.log('\n== Los topes son los mismos del schema ==')
const tope = (nombre) => Number(PY_SCHEMAS.match(new RegExp(`^${nombre} = (\\d+)`, 'm'))[1])
check('factura', tope('MAX_FACTURA') === MAX_FACTURA, [tope('MAX_FACTURA'), MAX_FACTURA])
check('observaciones', tope('MAX_OBSERVACIONES') === MAX_OBSERVACIONES)
check('numero de la NC', tope('MAX_NUMERO_NC') === MAX_NUMERO_NC)

console.log('')
if (fallos.length) {
  console.log(`FALLARON ${fallos.length}: ${fallos.join(' | ')}`)
  process.exit(1)
}
console.log('Todo bien.')
