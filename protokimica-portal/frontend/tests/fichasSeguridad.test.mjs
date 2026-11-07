// Fichas de seguridad: topes atados al servidor, validaciones del formulario y
// formatos de fecha y tamaño (sin el corrimiento de un día por UTC).
import {
  CAPACIDAD_GESTIONAR, ESTADOS_LISTA, FILTROS_FICHAS, MAX_CODIGO, MAX_MB, MAX_NOMBRE, MAX_OBSERVACIONES,
  MAX_VERSION, MIN_NOMBRE,
} from '../src/modules/fichasSeguridad/constants.js'
import {
  formatoFechaEmision, formatoFechaSubida, formatoTamano, hoyISO, puedeGestionarFichas, validarArchivo,
  validarCampos, versionSugerida, datosVacios, datosParaFormulario, validarDocumento, validarArchivoLectura,
  recortarLote, procesarConConcurrencia, ordenarLote,
} from '../src/modules/fichasSeguridad/resumen.js'
import { CONCURRENCIA_LOTE, MAX_LOTE, SECCIONES_FDS, TIPOS_DOCUMENTO } from '../src/modules/fichasSeguridad/constants.js'
import { readFileSync } from 'node:fs'

let fallos = []
function check(nombre, condicion, detalle) {
  if (condicion) console.log(`  OK  ${nombre}`)
  else { fallos.push(nombre); console.log(`  FALLA ${nombre}`, detalle ?? '') }
}

console.log('== Topes (iguales a los del servidor) ==')
check('topes', MAX_NOMBRE === 200 && MIN_NOMBRE === 3 && MAX_CODIGO === 40 && MAX_VERSION === 20
  && MAX_OBSERVACIONES === 500 && MAX_MB === 20)
check('capacidad', CAPACIDAD_GESTIONAR === 'fichas_seguridad.gestionar')
check('estados de la lista', ESTADOS_LISTA.map(e => e.clave).join() === 'activas,inactivas,todas')
check('filtros por defecto', FILTROS_FICHAS.estado === 'activas' && FILTROS_FICHAS.buscar === '' && FILTROS_FICHAS.ficha === '')

console.log('\n== Quién puede escribir ==')
const con = { capacidades: [CAPACIDAD_GESTIONAR] }
check('admin con la capacidad', puedeGestionarFichas({ rol: 'admin', ...con }))
check('líder sin la capacidad no', !puedeGestionarFichas({ rol: 'lider', capacidades: [] }))
check('lectura no, ni con la capacidad', !puedeGestionarFichas({ rol: 'lectura', ...con }))
check('gerencia no, ni con la capacidad', !puedeGestionarFichas({ rol: 'gerencia', ...con }))
check('sin usuario no', !puedeGestionarFichas(null))

console.log('\n== Corregir los datos de una versión ==')
check('corregir versión no pide producto', validarCampos({ version: '10', fecha_emision: '2023-09-21' }, 'corregir_version', '2026-11-06') === null)
check('corregir versión pide número', /versión/.test(validarCampos({ version: ' ', fecha_emision: '2023-09-21' }, 'corregir_version', '2026-11-06') ?? ''))
check('corregir versión rechaza fecha futura', /futura/.test(validarCampos({ version: '10', fecha_emision: '2027-01-01' }, 'corregir_version', '2026-11-06') ?? ''))

console.log('\n== Documentos generados ==')
check('lote: 10 y de a 3, como el servidor', MAX_LOTE === 10 && CONCURRENCIA_LOTE === 3)
check('tipos y formatos', TIPOS_DOCUMENTO.map(t => `${t.clave}:${t.formato}`).join() === 'certificado_analisis:AP-F-06,fds:AP-F-08')
const PY = readFileSync(new URL('../../backend/app/modules/fichas_seguridad/esquemas_documentos.py', import.meta.url), 'utf8').replace(/\r\n/g, '\n')
const titulosPy = [...PY.match(/SECCIONES_FDS = \[([\s\S]*?)\n\]/)[1].matchAll(/"([^"]+)"/g)].map(m => m[1])
check('las 16 secciones son las mismas del servidor', titulosPy.length === 16 && titulosPy.join('|') === SECCIONES_FDS.join('|'), titulosPy.length)
check('FDS en blanco trae 16 secciones numeradas', datosVacios('fds').secciones.length === 16 && datosVacios('fds').secciones[15].numero === 16)
const leida = datosParaFormulario('fds', { producto: 'Ácido', version: null, secciones: [{ numero: 4, contenido: 'Lavar con agua' }, { numero: 99, contenido: 'x' }] })
check('la lectura de una FDS siempre da 16 en orden y sin null', leida.secciones.length === 16 && leida.secciones[3].contenido === 'Lavar con agua' && leida.version === '' && leida.secciones[0].contenido === '')
const cert = datosParaFormulario('certificado_analisis', { producto: 'X', parametros: [{ nombre: 'pH', resultado: '7' }] })
check('un parámetro leído a medias se completa con vacíos', cert.parametros[0].unidad === '' && cert.parametros[0].resultado === '7')
check('sin producto no se genera', /producto/.test(validarDocumento({ producto: '  ' })) && validarDocumento({ producto: 'Soda' }) === null)
check('lectura: solo PDF', validarArchivoLectura({ name: 'a.PDF', size: 10 }) === null && /PDF/.test(validarArchivoLectura({ name: 'foto.jpeg', size: 10 })))
check('lectura: Word no, vacío no, grande no', /Word o Excel/.test(validarArchivoLectura({ name: 'a.docx', size: 10 })) && /vacío/.test(validarArchivoLectura({ name: 'a.pdf', size: 0 })) && /20 MB/.test(validarArchivoLectura({ name: 'a.pdf', size: 21 * 1024 * 1024 })))
const doce = recortarLote(Array.from({ length: 12 }, (_, i) => ({ name: `${i}.pdf` })))
check('un lote de 12 se recorta a 10 y avisa cuántos sobran', doce.archivos.length === 10 && doce.sobran === 2)
let activas = 0, maxima = 0
const res = await procesarConConcurrencia([1, 2, 3, 4, 5, 6, 7], 3, async (n) => {
  activas++; maxima = Math.max(maxima, activas)
  await new Promise(r => setTimeout(r, 5))
  activas--
  if (n === 4) throw new Error('falló el 4')
  return n * 2
})
check('nunca más de 3 a la vez', maxima === 3, maxima)
check('uno que falla no detiene al resto y todo queda en su lugar', res.length === 7 && res[3].ok === false && res[6].valor === 14 && res.filter(r => r.ok).length === 6)
check('los generados bajan al final sin mover el resto', ordenarLote([{ id: 1, estado: 'generado' }, { id: 2, estado: 'listo' }, { id: 3, estado: 'error' }]).map(x => x.id).join() === '2,3,1')

console.log('\n== Fechas, tamaño y versión ==')
check('hoyISO con ceros', hoyISO(new Date(2026, 0, 5)) === '2026-01-05')
check('emisión sin corrimiento de día', /^21\s/.test(formatoFechaEmision('2023-09-21')) && formatoFechaEmision('2023-09-21').includes('2023'))
check('1 de enero no pasa a 31 de diciembre', /^01\s/.test(formatoFechaEmision('2024-01-01')) && formatoFechaEmision('2024-01-01').includes('2024'))
check('emisión inválida', formatoFechaEmision(null) === '—' && formatoFechaEmision('x') === '—')
check('subida inválida', formatoFechaSubida('x') === '—' && formatoFechaSubida('2026-11-06T15:00:00Z').includes('2026'))
check('tamaños', formatoTamano(500) === '500 B' && formatoTamano(2048) === '2 KB' && formatoTamano(1.5 * 1024 * 1024) === '1,5 MB' && formatoTamano(-1) === '—')
check('versión sugerida entera', versionSugerida([{ version: '9', vigente: false }, { version: '10', vigente: true }]) === '11')
check('versión sugerida no adivina formatos raros', versionSugerida([{ version: '10.1', vigente: true }]) === '' && versionSugerida([]) === '')

console.log('\n== Archivo ==')
check('sin archivo', validarArchivo(null) !== null)
check('no es PDF', validarArchivo({ name: 'ficha.xlsx', size: 10 }).includes('PDF'))
check('vacío', validarArchivo({ name: 'a.pdf', size: 0 }).includes('vacío'))
check('muy grande', validarArchivo({ name: 'a.pdf', size: MAX_MB * 1024 * 1024 + 1 }).includes('20 MB'))
check('PDF en mayúsculas vale', validarArchivo({ name: 'A.PDF', size: 100 }) === null)

console.log('\n== Campos ==')
const ok = { nombre_producto: 'Ácido acético', version: '10', fecha_emision: '2023-09-21' }
check('crear correcto', validarCampos(ok, 'crear', '2026-11-06') === null)
check('nombre corto', validarCampos({ ...ok, nombre_producto: 'ab' }, 'crear').includes('nombre'))
check('nombre largo', validarCampos({ ...ok, nombre_producto: 'a'.repeat(MAX_NOMBRE + 1) }, 'crear').includes('200'))
check('código largo', validarCampos({ ...ok, codigo_producto: 'a'.repeat(MAX_CODIGO + 1) }, 'crear').includes('código'))
check('sin versión', validarCampos({ ...ok, version: ' ' }, 'crear').includes('versión'))
check('sin fecha', validarCampos({ ...ok, fecha_emision: '' }, 'crear').includes('fecha'))
check('fecha futura', validarCampos({ ...ok, fecha_emision: '2027-01-01' }, 'crear', '2026-11-06').includes('futura'))
check('observaciones largas', validarCampos({ ...ok, observaciones: 'x'.repeat(501) }, 'crear').includes('500'))
check('modo versión no pide nombre', validarCampos({ version: '11', fecha_emision: '2026-11-01' }, 'version', '2026-11-06') === null)
check('modo editar solo pide nombre', validarCampos({ nombre_producto: 'Soda cáustica' }, 'editar') === null
  && validarCampos({ nombre_producto: '' }, 'editar') !== null)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
