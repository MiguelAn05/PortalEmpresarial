// Pruebas de la lógica pura de PQRS: con qué nombre se reconoce cada una y
// qué viaja al servidor al corregir sus datos.
import { readFileSync } from 'node:fs'
import {
  nombrePrincipal, cambiosDeDatos, datosEditables, aplicaProducto, LIMITES_DATOS,
  LIMITES_RADICACION, MAX_PRODUCTOS, productoVacio, productosParaEnviar, faltaEnProductos,
  AREA_SIN_ASIGNAR, areasParaFiltrar, coincideAreaAsignada,
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

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
