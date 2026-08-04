// Pruebas de la deteccion de "hay datos sin guardar" al cerrar un formulario.
const { tieneDatos } = await import(
  '../src/core/components/tieneDatos.js'
)

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

// Igual que el formulario de Nueva tarea de Master Planner.
const VACIO_TAREA = {
  titulo: "", descripcion: "", area: "", asignado_a: "",
  prioridad: "media", riesgos: "", fecha_inicio: "", fecha_fin: "",
}

console.log('\n== Formulario nuevo ==')
check('recien abierto no pide confirmacion',
  tieneDatos({ ...VACIO_TAREA }, VACIO_TAREA) === false)
check('con el titulo escrito SI pide confirmacion',
  tieneDatos({ ...VACIO_TAREA, titulo: 'Migrar BD' }, VACIO_TAREA) === true)
check('con solo una descripcion tambien',
  tieneDatos({ ...VACIO_TAREA, descripcion: 'algo' }, VACIO_TAREA) === true)
check('cambiar la prioridad por defecto cuenta como dato',
  tieneDatos({ ...VACIO_TAREA, prioridad: 'alta' }, VACIO_TAREA) === true)
check('dejar la prioridad por defecto NO cuenta',
  tieneDatos({ ...VACIO_TAREA, prioridad: 'media' }, VACIO_TAREA) === false)
check('elegir un responsable cuenta',
  tieneDatos({ ...VACIO_TAREA, asignado_a: '5' }, VACIO_TAREA) === true)
check('poner una fecha cuenta',
  tieneDatos({ ...VACIO_TAREA, fecha_fin: '2026-09-30T17:00' }, VACIO_TAREA) === true)

console.log('\n== Formulario de edicion ==')
// Al editar, el formulario arranca lleno: eso NO es "datos sin guardar".
const proyecto = {
  nombre: 'Portal Web', objetivo: 'Digitalizar', area: 'TI',
  areas_participantes: ['Calidad'], prioridad: 'alta',
}
check('abrir a editar sin tocar nada no pide confirmacion',
  tieneDatos({ ...proyecto }, proyecto) === false)
check('cambiar el nombre si pide confirmacion',
  tieneDatos({ ...proyecto, nombre: 'Portal Web v2' }, proyecto) === true)
check('borrar un campo que tenia valor tambien',
  tieneDatos({ ...proyecto, objetivo: '' }, proyecto) === true)

console.log('\n== Listas y booleanos ==')
check('agregar un area participante cuenta',
  tieneDatos({ ...proyecto, areas_participantes: ['Calidad', 'Logistica'] }, proyecto) === true)
check('quitar un area participante cuenta',
  tieneDatos({ ...proyecto, areas_participantes: [] }, proyecto) === true)
check('la misma lista no cuenta',
  tieneDatos({ ...proyecto, areas_participantes: ['Calidad'] }, proyecto) === false)
check('marcar una casilla cuenta',
  tieneDatos({ requiere_evidencia: true }, { requiere_evidencia: false }) === true)
check('una casilla sin tocar no cuenta',
  tieneDatos({ requiere_evidencia: false }, { requiere_evidencia: false }) === false)
check('una casilla sin valor inicial se asume en false',
  tieneDatos({ requiere_evidencia: false }, {}) === false)

console.log('\n== Casos borde ==')
check('null y cadena vacia se tratan igual',
  tieneDatos({ area: '' }, { area: null }) === false)
check('undefined y cadena vacia tambien',
  tieneDatos({ area: '' }, {}) === false)
check('un numero distinto cuenta',
  tieneDatos({ meta: 90 }, { meta: 80 }) === true)
check('el mismo numero no cuenta',
  tieneDatos({ meta: 90 }, { meta: 90 }) === false)
check('un formulario vacio contra nada no pide confirmacion',
  tieneDatos({}, {}) === false)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
