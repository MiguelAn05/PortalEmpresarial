// El aviso de "datos sin guardar" se dibuja DENTRO del modal que protege, y
// ese modal cierra al hacer clic en su fondo. Sin frenar el clic, pulsar
// "Seguir editando" llegaba tambien al fondo, que reabria el aviso al
// instante: parecia que el boton no funcionaba y solo "Descartar" cerraba.
//
// Node no puede importar .jsx, asi que se verifica sobre el texto del archivo
// que la proteccion sigue puesta. Es una prueba de regresion, no de render.
import { readFileSync } from 'node:fs'

const RUTA = new URL('../src/core/components/ConfirmarDescarte.jsx', import.meta.url)
const fuente = readFileSync(RUTA, 'utf8')

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== El clic no se escapa al modal de abajo ==')
check('el contenedor frena la propagacion del clic',
  /className="fixed inset-0[^"]*"[\s\S]{0,120}onClick=\{\(e\) => e\.stopPropagation\(\)\}/.test(fuente),
  'falta onClick={(e) => e.stopPropagation()} en el div de fondo')

console.log('\n== Los dos botones siguen ahi ==')
check('hay boton de seguir editando', /Seguir editando/.test(fuente))
check('conectado a onSeguir', /onClick=\{onSeguir\}/.test(fuente))
check('hay boton de descartar', /Descartar/.test(fuente))
check('conectado a onDescartar', /onClick=\{onDescartar\}/.test(fuente))

console.log('\n== Queda por encima del modal que protege ==')
// El modal usa z-50 y el confirmador de cambios z-[60]; este tiene que ir
// por encima de los dos o quedaria tapado.
check('z-index por encima de 60', /z-\[70\]/.test(fuente), 'deberia ser z-[70]')

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
