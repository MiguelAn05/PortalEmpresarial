// Pruebas de la lógica pura de PQRS: con qué nombre se reconoce cada una y
// qué viaja al servidor al corregir sus datos.
import { readFileSync } from 'node:fs'
import {
  nombrePrincipal, cambiosDeDatos, datosEditables, aplicaProducto, LIMITES_DATOS,
  LIMITES_RADICACION, MAX_PRODUCTOS, productoVacio, productosParaEnviar, faltaEnProductos,
  AREA_SIN_ASIGNAR, areasParaFiltrar, coincideAreaAsignada,
  ESTADOS_CON_PLAZO, plazoCorriendo, estadoDelPlazo, estaVencida,
  FOCOS, cumpleFoco, contarPorFoco,
} from '../src/modules/pqrs/constants.js'
import { AREAS } from '../src/core/areas.js'

const PY = readFileSync(new URL('../../backend/app/modules/pqrs/schemas.py', import.meta.url), 'utf8')
  .replaceAll('\r', '')  // schemas.py viene con CRLF de Windows

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Nombre principal ==')
let n = nombrePrincipal({ empresa: 'Industrias del Valle', cliente_nombre: 'Juan Pérez' })
check('una empresa se reconoce por la empresa', n.titulo === 'Industrias del Valle', n)
check('y el contacto baja a la segunda línea', n.subtitulo === 'Juan Pérez', n)

n = nombrePrincipal({ empresa: 'María Gómez', cliente_nombre: 'María Gómez' })
check('persona natural: su nombre', n.titulo === 'María Gómez', n)
check('sin repetirlo debajo', n.subtitulo === null, n)

n = nombrePrincipal({ empresa: ' maría  GÓMEZ ', cliente_nombre: 'María Gómez' })
check('coinciden aunque cambien mayúsculas y espacios', n.subtitulo === null, n)

n = nombrePrincipal({ empresa: '', cliente_nombre: 'Pedro' })
check('sin empresa: el contacto', n.titulo === 'Pedro' && n.subtitulo === null, n)

n = nombrePrincipal({ empresa: null, cliente_nombre: 'Pedro' })
check('empresa null tampoco revienta', n.titulo === 'Pedro', n)

n = nombrePrincipal({ empresa: 'Solo Empresa', cliente_nombre: '' })
check('sin contacto: la empresa sola', n.titulo === 'Solo Empresa' && n.subtitulo === null, n)

console.log('\n== Sección de producto ==')
check('un reclamo la lleva', aplicaProducto({ tipo: 'reclamo' }))
check('una queja no', !aplicaProducto({ tipo: 'queja' }))
check('una felicitación no', !aplicaProducto({ tipo: 'felicitacion' }))
check('pero si la queja ya trae factura, sí (hay que poder corregirla)',
  aplicaProducto({ tipo: 'queja', factura_numero: 'FV-1' }))

console.log('\n== Qué se manda al corregir ==')
const pqrs = { empresa: 'ACME', cliente_email: 'a@b.com', ciudad: null, factura_numero: 'FV-1' }
const form = datosEditables(pqrs)
check('el formulario arranca sin null', form.ciudad === '', form)
check('sin tocar nada no viaja nada', Object.keys(cambiosDeDatos(pqrs, form)).length === 0)

let c = cambiosDeDatos(pqrs, { ...form, cliente_email: 'nuevo@b.com' })
check('viaja solo lo que cambió', JSON.stringify(c) === JSON.stringify({ cliente_email: 'nuevo@b.com' }), c)

c = cambiosDeDatos(pqrs, { ...form, empresa: '  ACME  ' })
check('agregar espacios no es un cambio', Object.keys(c).length === 0, c)

c = cambiosDeDatos(pqrs, { ...form, factura_numero: '' })
check('vaciar un campo viaja como cadena vacía', c.factura_numero === '', c)

c = cambiosDeDatos(pqrs, { ...form, ciudad: 'Bello' })
check('llenar uno que estaba vacío', c.ciudad === 'Bello', c)

console.log('\n== Topes atados al schema del backend ==')
const bloque = PY.match(/class PQRSEditarDatos\(BaseModel\):(.*?)\n\n\n/s)?.[1] ?? ''
const topesPy = Object.fromEntries(
  [...bloque.matchAll(/^\s+(\w+): str \| None = Field\(None, max_length=(\d+)\)/gm)]
    .map(m => [m[1], Number(m[2])]),
)
check('se encontró el schema', Object.keys(topesPy).length > 0, bloque.slice(0, 80))
check('los mismos campos en los dos lados',
  JSON.stringify(Object.keys(topesPy)) === JSON.stringify(Object.keys(LIMITES_DATOS)),
  { python: Object.keys(topesPy), javascript: Object.keys(LIMITES_DATOS) })
for (const [campo, tope] of Object.entries(LIMITES_DATOS)) {
  check(`${campo}: ${tope} en los dos lados`, topesPy[campo] === tope, { python: topesPy[campo] })
}

console.log('\n== Topes al radicar atados a las columnas ==')
// Sin estos topes, un texto largo tumbaba el registro con un 500 en
// Postgres. Se leen de models/pqrs.py para que un cambio de columna avise.
const MODELO = readFileSync(new URL('../../backend/app/models/pqrs.py', import.meta.url), 'utf8')
for (const [campo, tope] of Object.entries(LIMITES_RADICACION)) {
  const col = MODELO.match(new RegExp(`^\\s+${campo} = Column\\(String\\((\\d+)\\)`, 'm'))
  check(`${campo}: ${tope} como la columna`, col && Number(col[1]) === tope, { columna: col?.[1] })
}

console.log('\n== Filtro por área asignada ==')
// El filtro mira `area_responsable` (quién la tiene HOY), no `area_causante`,
// que es un dato de indicadores y que una PQRS abierta casi nunca tiene.
const enCalidad = { area_responsable: 'Calidad', area_causante: 'Producción' }
check('filtra por el área que la tiene', coincideAreaAsignada(enCalidad, 'Calidad'))
check('y no por la causante', !coincideAreaAsignada(enCalidad, 'Producción'))
check('sin filtro entran todas', coincideAreaAsignada(enCalidad, ''))

// El área se compara normalizada: lo guardado antes de unificar el catálogo
// tiene que aparecer al filtrar por el nombre de hoy.
check('un área histórica cae en la actual',
  coincideAreaAsignada({ area_responsable: 'Servicio al cliente' }, 'Servicio al Cliente'))

// La que no tiene dueño es la que hay que poder pescar: el plazo corre igual.
check('«sin asignar» encuentra las que no tienen área',
  coincideAreaAsignada({ area_responsable: null }, AREA_SIN_ASIGNAR))
check('y deja fuera las que sí lo tienen',
  !coincideAreaAsignada(enCalidad, AREA_SIN_ASIGNAR))

const opciones = areasParaFiltrar([
  { area_responsable: 'Calidad' },
  { area_responsable: 'Área que ya no existe' },
  { area_responsable: null },
])
check('ofrece el catálogo completo', AREAS.every(a => opciones.includes(a)))
check('más un área retirada que aún aparece en los datos',
  opciones.includes('Área que ya no existe'), opciones)
check('sin repetir las del catálogo',
  opciones.length === AREAS.length + 1, opciones.length)

console.log('\n== Una PQRS cerrada deja de contar el tiempo ==')
// El reloj se paraba solo al cerrar, y ni siquiera en todas partes: la lista
// no miraba el estado, asi que una PQRS cerrada hace meses aparecia hoy
// «Vencida» para siempre, contra el reloj del calendario.
const AHORA = new Date('2026-09-24T10:00:00')
const enDias = (d) => new Date(AHORA.getTime() + d * 24 * 60 * 60 * 1000).toISOString()
const conPlazo = (estado, dias) => ({ estado, fecha_limite_sla: enDias(dias) })

check('una cerrada con el plazo pasado no esta vencida',
  estaVencida(conPlazo('cerrado', -30), AHORA) === false)
check('y no muestra nada en la columna',
  estadoDelPlazo(conPlazo('cerrado', -30), AHORA) === null)
check('una resuelta tampoco: la respuesta ya salio',
  estaVencida(conPlazo('resuelto', -30), AHORA) === false)
check('una en proceso con el plazo pasado SI esta vencida',
  estaVencida(conPlazo('en_proceso', -1), AHORA) === true)
check('y lo dice con palabra, no solo con color',
  estadoDelPlazo(conPlazo('en_proceso', -1), AHORA).texto === 'Vencida')

console.log('\n== Y lo que si corre se sigue avisando ==')
check('vence hoy', estadoDelPlazo(conPlazo('recibido', 0), AHORA).texto === 'Vence hoy')
check('faltando dos dias avisa en ambar',
  estadoDelPlazo(conPlazo('asignado', 2), AHORA).tono === 'alerta')
check('con holgura va neutro',
  estadoDelPlazo(conPlazo('asignado', 9), AHORA).tono === 'neutro')
check('sin fecha limite no hay plazo que contar',
  plazoCorriendo({ estado: 'recibido' }) === false)
check('y sin PQRS no revienta', estadoDelPlazo(undefined, AHORA) === null)

console.log('\n== La regla es la misma que la del servidor ==')
const PY_PENDIENTES = readFileSync(
  new URL('../../backend/app/modules/pqrs/pendientes.py', import.meta.url), 'utf8')
const abiertosPy = [...PY_PENDIENTES
  .match(/^ESTADOS_ABIERTOS = \(([^)]*)\)/m)[1]
  .matchAll(/"([a-z_]+)"/g)].map(m => m[1])
check('los estados con plazo coinciden con pendientes.py',
  JSON.stringify([...abiertosPy].sort()) === JSON.stringify([...ESTADOS_CON_PLAZO].sort()),
  { python: abiertosPy, js: ESTADOS_CON_PLAZO })

console.log('\n== Las tarjetas del encabezado filtran ==')
// Leer «4 vencidas» y no poder llegar a esas cuatro obligaba a ir al panel de
// filtros a reconstruir a mano la misma condicion. Y dos de estas ni siquiera
// se podian reconstruir alli: «Abiertas» no es un estado y «Vencidas» no es
// un campo, es una cuenta contra el reloj.
const LISTA = [
  { id: 1, estado: 'cerrado',   prioridad: 'alta',    fecha_limite_sla: enDias(-9) },
  { id: 2, estado: 'recibido',  prioridad: 'critica', fecha_limite_sla: enDias(-2) },
  { id: 3, estado: 'en_proceso',prioridad: 'media',   fecha_limite_sla: enDias(5) },
  { id: 4, estado: 'resuelto',  prioridad: 'baja',    fecha_limite_sla: enDias(-1) },
]
const cuenta = contarPorFoco(LISTA, AHORA)

check('Total las cuenta todas', cuenta.null === 4, cuenta)
check('Abiertas es todo menos cerrado', cuenta.abiertas === 3, cuenta)
check('Alta prioridad junta alta y critica', cuenta.prioridad === 2, cuenta)
check('Vencidas no incluye la cerrada ni la resuelta', cuenta.vencidas === 1, cuenta)

console.log('\n== La cifra de la tarjeta es lo que muestra al pulsarla ==')
// Si el conteo y el filtro se escribieran aparte, el dia que una regla cambie
// la tarjeta diria un numero y la lista mostraria otro.
for (const { clave } of FOCOS) {
  const filtradas = LISTA.filter(p => cumpleFoco(p, clave, AHORA)).length
  check(`«${clave ?? 'Total'}» cuadra`, filtradas === cuenta[String(clave)],
    { clave, filtradas, tarjeta: cuenta[String(clave)] })
}

console.log('\n== Casos limite ==')
check('sin foco entran todas', cumpleFoco(LISTA[0], null, AHORA) === true)
check('un foco que no existe no esconde nada',
  cumpleFoco(LISTA[0], 'inventado', AHORA) === true)
check('una lista vacia no revienta', contarPorFoco([], AHORA).abiertas === 0)
check('y sin lista tampoco', contarPorFoco(undefined, AHORA).null === 0)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
