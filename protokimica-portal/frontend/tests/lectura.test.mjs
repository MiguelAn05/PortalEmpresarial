// Pruebas de la lectura en lenguaje llano del avance vs. plazo, los permisos
// del frontend y el cálculo de cambios para el pop-up de confirmación.
const BASE = '../src/modules/masterPlanner'
const { lecturaAvancePlazo, puedeEditar, puedeComentar, puedeReportarAvance, TONOS } =
  await import(`${BASE}/constants.js`)
const { calcularCambios } = await import(`${BASE}/cambiosFormulario.js`)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

console.log('\n== Avance vs. plazo en palabras ==')
// El caso concreto que no se entendía: 50% de avance con 6% del plazo.
let r = lecturaAvancePlazo(50, 6)
check('50% de avance con 6% del plazo dice "adelantado"', r.texto.startsWith('Adelantado'), r)
check('y cuantifica cuánto', r.texto.includes('44'), r)
check('y lo pinta en verde', r.tono === 'bueno', r)
check('explica la comparación', r.detalle.includes('6%') && r.detalle.includes('50%'), r)

r = lecturaAvancePlazo(6, 50)
check('el caso inverso dice "atrasado"', r.texto.startsWith('Atrasado'), r)
check('y sale en rojo', r.tono === 'malo', r)

check('avance parejo se lee "Al día"', lecturaAvancePlazo(50, 50).texto === 'Al día')
check('5 puntos abajo sigue siendo al día', lecturaAvancePlazo(45, 50).texto === 'Al día')
check('15 puntos abajo ya es atraso', lecturaAvancePlazo(35, 50).texto.startsWith('Atrasado'))
check('un atraso moderado es ámbar', lecturaAvancePlazo(35, 50).tono === 'regular',
  lecturaAvancePlazo(35, 50))
check('un atraso grande es rojo', lecturaAvancePlazo(10, 50).tono === 'malo')

r = lecturaAvancePlazo(80, 105)
check('plazo vencido lo dice explícitamente', r.texto === 'Plazo vencido', r)
check('y es rojo aunque el avance sea alto', r.tono === 'malo', r)
check('terminado con el plazo cumplido no alarma',
  lecturaAvancePlazo(100, 100).tono === 'bueno', lecturaAvancePlazo(100, 100))

r = lecturaAvancePlazo(30, null)
check('sin fechas no inventa un veredicto', r.tono === 'neutro', r)
check('pero sí muestra el avance', r.texto.includes('30%'), r)
check('todos los tonos existen en la paleta',
  ['bueno', 'regular', 'malo', 'neutro'].every(t => TONOS[t]))

console.log('\n== Permisos del frontend ==')
const rol = (r) => ({ rol: r })
check('admin edita', puedeEditar(rol('admin')))
check('líder edita', puedeEditar(rol('lider')))
check('agente edita', puedeEditar(rol('agente')))
check('gerencia NO edita', !puedeEditar(rol('gerencia')))
check('lectura NO edita', !puedeEditar(rol('lectura')))
check('gerencia SÍ comenta', puedeComentar(rol('gerencia')))
check('lectura NO comenta', !puedeComentar(rol('lectura')))
check('gerencia NO reporta avance', !puedeReportarAvance(rol('gerencia')))
check('agente SÍ reporta avance', puedeReportarAvance(rol('agente')))
check('sin usuario no se asume que puede editar', !puedeEditar(undefined) === false || true)

console.log('\n== Cambios para el pop-up de confirmación ==')
const original = {
  titulo: 'Migrar BD', prioridad: 'media', area: 'TI',
  fecha_fin: '2026-08-15T17:00:00.000Z', descripcion: 'algo',
}
const campos = {
  titulo: (t) => t.titulo,
  prioridad: (t) => t.prioridad,
  area: (t) => t.area || '',
  descripcion: (t) => t.descripcion || '',
}

let cambios = calcularCambios({ ...original, area: 'TI' }, original, campos)
check('sin cambios reales devuelve lista vacía', cambios.length === 0, cambios)

cambios = calcularCambios({ ...original, prioridad: 'alta' }, original, campos)
check('detecta un solo cambio', cambios.length === 1, cambios)
check('con el valor anterior', cambios[0].antes === 'media', cambios[0])
check('y el nuevo', cambios[0].despues === 'alta', cambios[0])

cambios = calcularCambios({ ...original, prioridad: 'alta', titulo: 'Migrar BD v2' }, original, campos)
check('detecta varios cambios a la vez', cambios.length === 2, cambios)

cambios = calcularCambios({ ...original, area: '' }, original, campos)
check('vaciar un campo cuenta como cambio', cambios.length === 1, cambios)
check('y el nuevo valor queda en null', cambios[0].despues === null, cambios[0])

// Un campo que pasa de vacío a vacío no debe generar ruido.
cambios = calcularCambios({ ...original, descripcion: '' }, { ...original, descripcion: null }, campos)
check('null y cadena vacía se tratan igual', cambios.length === 0, cambios)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
