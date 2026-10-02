/**
 * La pantalla no decide permisos comparando el área con un nombre.
 *
 * Quién cierra una PQRS, valida el SGC, aprueba o paga lo decide una
 * capacidad que manda el servidor (`core/capacidades.js`). Antes había
 * `user.area === 'Calidad'` y `AREA_APRUEBA_PAGOS = 'Administración'`
 * sueltos en los componentes: en otra empresa esas áreas se llaman distinto,
 * el botón no aparecía y nadie sabía por qué. Esta prueba falla si vuelve a
 * entrar uno.
 */
import { readdirSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join, relative } from 'node:path'
import { tieneCapacidad } from '../src/core/capacidades.js'

const aqui = dirname(fileURLToPath(import.meta.url))
const raiz = join(aqui, '..', 'src')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

function archivos(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e =>
    e.isDirectory() ? archivos(join(dir, e.name))
      : /\.(js|jsx)$/.test(e.name) ? [join(dir, e.name)] : [])
}

// `algo.area === 'Calidad'` o `area !== "Tesorería"`: un permiso por nombre.
const COMPARA_AREA = /\barea\s*[!=]==?\s*['"`]/

// Las que todavía viven aquí con motivo. Quitar una es la meta.
// Hoy ninguna: el área de las sedes también dejó de estar escrita aquí y la
// dice el servidor (`useAreaDeSedes`).
const PERMITIDAS = {}

console.log('\n== Ningún componente decide un permiso por el nombre del área ==')
const culpables = []
for (const archivo of archivos(raiz)) {
  const ruta = relative(raiz, archivo).replaceAll('\\', '/')
  const texto = readFileSync(archivo, 'utf8')
  texto.split('\n').forEach((linea, i) => {
    // `AREA_SIN_ASIGNAR = '__sin_asignar__'` es un marcador del filtro, no
    // un nombre de área: los que empiezan por `__` no cuentan.
    const declara = /\bconst AREA_[A-Z_]+\s*=\s*['"](?!__)/.test(linea)
    if (!COMPARA_AREA.test(linea) && !declara) return
    if (PERMITIDAS[ruta]?.test(linea)) return
    culpables.push(`${ruta}:${i + 1}`)
  })
}
check('sin comparaciones ni constantes de área sueltas', culpables.length === 0, culpables)

console.log('\n== tieneCapacidad pregunta lo que dijo el servidor ==')
check('admin siempre', tieneCapacidad({ rol: 'admin' }, 'pqrs.cerrar'))
check('con la capacidad, sí',
  tieneCapacidad({ rol: 'agente', capacidades: ['presupuesto.pagar'] }, 'presupuesto.pagar'))
check('sin ella, no',
  !tieneCapacidad({ rol: 'lider', capacidades: ['presupuesto.pagar'] }, 'presupuesto.aprobar'))
check('el área no cuenta: «Calidad» sin la capacidad no valida',
  !tieneCapacidad({ rol: 'lider', area: 'Calidad', capacidades: [] }, 'mejora.validar_sgc'))
check('sin el dato no se ofrece', !tieneCapacidad({ rol: 'lider' }, 'pqrs.cerrar'))

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
