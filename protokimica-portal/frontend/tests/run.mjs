/**
 * Corre todas las pruebas del frontend.
 *
 * Son pruebas de lógica pura (fechas, formatos, permisos, cálculo de
 * cambios): lo que se puede romper en silencio y no se nota hasta que un
 * número sale mal en pantalla. Los componentes no se prueban aquí — para eso
 * está el build y la revisión visual.
 *
 * Node importa .js y .mjs pero no .jsx, así que la lógica que quiera
 * probarse tiene que vivir en un archivo sin JSX.
 */
import { readdirSync } from 'node:fs'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const aqui = dirname(fileURLToPath(import.meta.url))
const suites = readdirSync(aqui).filter(f => f.endsWith('.test.mjs')).sort()

let fallidas = 0

for (const suite of suites) {
  const r = spawnSync(process.execPath, [join(aqui, suite)], { encoding: 'utf8' })
  const salida = (r.stdout || '') + (r.stderr || '')
  const ok = r.status === 0

  if (ok) {
    const pasaron = (salida.match(/^ {2}OK/gm) || []).length
    console.log(`  ✓ ${suite.padEnd(26)} ${pasaron} comprobaciones`)
  } else {
    fallidas++
    console.log(`  ✗ ${suite}`)
    // Solo las líneas que importan: las fallas y el error, no el ruido.
    salida.split('\n')
      .filter(l => l.includes('FALLA') || l.includes('Error') || l.includes('FALLARON'))
      .forEach(l => console.log(`      ${l.trim()}`))
  }
}

console.log('')
if (fallidas) {
  console.log(`${fallidas} de ${suites.length} suites fallaron.`)
  process.exit(1)
}
console.log(`Las ${suites.length} suites pasaron.`)
