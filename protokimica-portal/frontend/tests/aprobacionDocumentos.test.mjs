// Aprobación de documentos en Master Planner.
//
// La regla vive en el servidor (`master_planner/revision.py`) y ahí tiene sus
// pruebas. Lo que se prueba aquí es lo que se rompe en silencio del lado del
// navegador: los gemelos, el punto de una observación y cómo se carga el visor.
import { readFileSync } from 'node:fs'
import {
  ESTADOS_DOCUMENTO, MAX_DOCUMENTO_MB, MAX_NOMBRE_PLANTILLA, MAX_OBSERVACION, MAX_PASOS_PLANTILLA,
  documentoDemasiadoGrande,
  estadoDocumentoDeTarea, textoTamano, unMesDespues,
} from '../src/modules/masterPlanner/constants.js'
import {
  claveCelda, lugarObservacion, marcaEnPagina, numerarObservaciones, problemaRevisores, puntoEnPagina,
  textoCelda,
} from '../src/modules/masterPlanner/revision.js'

const leer = (ruta) => readFileSync(new URL(ruta, import.meta.url), 'utf8')
const PY_MODELO = leer('../../backend/app/models/master_planner.py')
const PY_ARCHIVOS = leer('../../backend/app/core/archivos.py')
const PY_SCHEMAS = leer('../../backend/app/modules/master_planner/schemas.py')
const VISOR = leer('../src/modules/masterPlanner/VisorDocumento.jsx')
const APP = leer('../src/App.jsx')
const HOJA = leer('../src/modules/masterPlanner/components/HojaExcel.jsx')
const CARD = leer('../src/modules/masterPlanner/components/TareaCard.jsx')
const PY_REVISION = leer('../../backend/app/modules/master_planner/revision.py')
const CADENAS = leer('../src/modules/admin/CadenasRevision.jsx')
const ADMIN = leer('../src/modules/admin/Admin.jsx')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Los estados del documento son los del servidor ==')
const estadosPy = [...PY_MODELO.match(/ESTADOS_DOCUMENTO = \(([^)]*)\)/)[1].matchAll(/"([a-z_]+)"/g)].map(m => m[1])
check('cada estado del servidor tiene su nombre en pantalla',
  estadosPy.every(e => e in ESTADOS_DOCUMENTO), { servidor: estadosPy })
check('y la pantalla solo agrega «sin documento»',
  Object.keys(ESTADOS_DOCUMENTO).filter(e => !estadosPy.includes(e)).join() === 'sin_documento')
check('cada uno lleva palabra, no solo color',
  Object.values(ESTADOS_DOCUMENTO).every(c => c.label && c.dot))

console.log('\n== Los topes son los mismos ==')
check('el tamaño máximo coincide con core/archivos.py',
  Number(PY_ARCHIVOS.match(/^MAX_DOCUMENTO_MB = (\d+)/m)?.[1]) === MAX_DOCUMENTO_MB)
check('el largo de una observación coincide con el schema',
  Number(PY_SCHEMAS.match(/^MAX_OBSERVACION = (\d+)/m)?.[1]) === MAX_OBSERVACION)
check('un archivo de 25 MB se avisa antes de subirlo',
  documentoDemasiadoGrande({ size: 25 * 1024 * 1024 }) !== null)
check('uno de 2 MB pasa', documentoDemasiadoGrande({ size: 2 * 1024 * 1024 }) === null)
check('el tamaño se dice en MB con coma', textoTamano(1.5 * 1024 * 1024) === '1,5 MB', textoTamano(1.5 * 1024 * 1024))

console.log('\n== Quién firma: las mismas reglas que el servidor ==')
const plantilla = { pasos: [{ orden: 1, nombre: 'Contador' }, { orden: 2, nombre: 'Revisora Fiscal' }] }
check('sin elegir a nadie dice a quién falta',
  /Contador y Revisora Fiscal/.test(problemaRevisores(plantilla, [null, null]) || ''))
check('la misma persona en los dos pasos no sirve',
  problemaRevisores(plantilla, [4, 4]) !== null)
check('quien tiene la tarea no firma su documento',
  problemaRevisores(plantilla, [4, 5], 5) !== null)
check('dos personas distintas está bien', problemaRevisores(plantilla, [4, 5], 7) === null)

console.log('\n== El punto de una observación no depende del zoom ==')
const rect = { left: 100, top: 50, width: 800, height: 1000 }
const p = puntoEnPagina(500, 550, rect)
check('cae como fracción de la página', p.pos_x === 0.5 && p.pos_y === 0.5, p)
const fuera = puntoEnPagina(2000, -10, rect)
check('un clic en el borde no se sale de la página', fuera.pos_x === 1 && fuera.pos_y === 0, fuera)
check('el número del punto es el de la lista',
  numerarObservaciones([{ id: 9 }, { id: 3 }]).map(o => o.numero).join() === '1,2')

console.log('\n== Arrastrar enmarca una zona ==')
const ini = { x: 500, y: 550 }
check('un clic quieto sigue siendo un punto', marcaEnPagina(ini, { x: 503, y: 552 }, rect).ancho === undefined)
const caja = marcaEnPagina(ini, { x: 900, y: 1050 }, rect)
check('arrastrar deja un recuadro con su tamaño',
  caja.pos_x === 0.5 && caja.pos_y === 0.5 && caja.ancho === 0.5 && caja.alto === 0.5, caja)
const alReves = marcaEnPagina({ x: 900, y: 1050 }, ini, rect)
check('arrastrado hacia arriba a la izquierda, la esquina es la misma', JSON.stringify(alReves) === JSON.stringify(caja), alReves)
const afuera = marcaEnPagina(ini, { x: 5000, y: 5000 }, rect)
check('no se sale de la página', afuera.pos_x + afuera.ancho <= 1 && afuera.pos_y + afuera.alto <= 1, afuera)
check('por fuera del borde, sin ancho, queda en punto',
  marcaEnPagina({ x: 950, y: 100 }, { x: 990, y: 400 }, rect).ancho === undefined)

console.log('\n== Repetir propone el mismo día del mes siguiente ==')
const sig = new Date(unMesDespues(new Date(2026, 8, 10, 17, 0).toISOString()))
check('el 10 de septiembre pasa al 10 de octubre',
  sig.getMonth() === 9 && sig.getDate() === 10 && sig.getHours() === 17, sig.toString())
const feb = new Date(unMesDespues(new Date(2027, 0, 31, 9, 0).toISOString()))
check('un 31 de enero cae el último día de febrero, no en marzo',
  feb.getMonth() === 1 && feb.getDate() === 28, feb.toString())
check('sin fecha no inventa una', unMesDespues(null) === null)

console.log('\n== El visor no se trae nada de fuera ni ejecuta lo del archivo ==')
check('pdf.js no compila código del PDF', /isEvalSupported: false/.test(VISOR))
check('el worker sale del propio build, no de un CDN',
  /pdf\.worker\.min\.mjs\?url/.test(VISOR) && !/https?:\/\//.test(VISOR.match(/workerSrc = .*/)?.[0] || ''))
check('y el visor se carga aparte del bundle principal',
  /lazy\(\(\) => import\('\.\/modules\/masterPlanner\/VisorDocumento\.jsx'\)\)/.test(APP))
check('el archivo se pide con la sesión, no con una URL pública',
  /descargarArchivoDocumento/.test(VISOR) && !/\/uploads\//.test(VISOR))

console.log('\n== La tarjeta dice en qué va el documento ==')
check('una tarea sin flujo no lleva chip', estadoDocumentoDeTarea({ requiere_revision: false, estado_documento: null }) === null)
check('con flujo y sin archivo dice «sin documento»',
  estadoDocumentoDeTarea({ requiere_revision: true, estado_documento: null }) === 'sin_documento')
check('con archivo, el estado del servidor',
  estadoDocumentoDeTarea({ requiere_revision: true, estado_documento: 'devuelta' }) === 'devuelta')
check('la tarjeta lo pinta', /estadoDocumentoDeTarea\(tarea\)/.test(CARD) && /ChipDocumento/.test(CARD))

console.log('\n== Un Excel se señala por celda ==')
check('la celda se dice como en Excel', claveCelda('Balance', 'C14') === 'Balance!C14')
check('un número se escribe con puntos de miles y coma decimal', textoCelda(1250000.5) === '1.250.000,5', textoCelda(1250000.5))
check('una fecha del servidor se escribe día/mes/año', textoCelda('2026-10-01') === '01/10/2026', textoCelda('2026-10-01'))
check('una celda vacía no dice «null»', textoCelda(null) === '')
check('el texto pasa tal cual', textoCelda('Total pasivos') === 'Total pasivos')
check('el lugar de una observación en un Excel', lugarObservacion({ hoja: 'Balance', celda: 'C14' }) === 'Balance · C14')
check('en un PDF', lugarObservacion({ pagina: 3 }) === 'página 3')
check('y la general', lugarObservacion({}) === 'general')
check('la hoja no se queda en la memoria de la pestaña', /gcTime: 0/.test(HOJA))
check('y se pide al servidor, no se abre el archivo en el navegador',
  /obtenerHojaDocumento/.test(HOJA) && !/import .*xlsx/.test(HOJA))

console.log('\n== Las cadenas de revisión ==')
check('el tope de firmas es el del servidor',
  Number(PY_REVISION.match(/^MAX_PASOS_PLANTILLA = (\d+)/m)?.[1]) === MAX_PASOS_PLANTILLA)
check('y el largo del nombre, el del schema',
  /class PlantillaGuardar[\s\S]*?nombre: str = Field\(min_length=1, max_length=(\d+)\)/.exec(PY_SCHEMAS)?.[1] === String(MAX_NOMBRE_PLANTILLA))
check('la pantalla usa los dos topes', /maxLength=\{MAX_NOMBRE_PLANTILLA\}/.test(CADENAS) && /MAX_PASOS_PLANTILLA/.test(CADENAS))
check('se muestra solo con Master Planner contratado',
  /estaContratado\(user, 'master_planner'\) && <CadenasRevision \/>/.test(ADMIN))
check('no se borra: se desactiva', !/api\.delete/.test(CADENAS))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
