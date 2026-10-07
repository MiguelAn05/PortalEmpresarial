// El área de una PQRS no se pide al radicar, ni se le muestra al cliente.
//
// Los dos formularios —el público y el interno— pedían el área responsable,
// y ni el cliente ni el vendedor tienen con qué criterio escogerla:
// adivinaban, y el caso arrancaba en un área que no le tocaba con su reloj de
// tres días corriendo. Hoy toda PQRS nace con quien reparte (Servicio al
// Cliente) y ahí se asigna — ver `permisos.area_de_entrada` en el backend.
//
// Y la consulta pública no dice qué área tiene el caso: es organización
// interna, y al cliente solo lo pone a preguntar por qué la tiene «esa».
import { readFileSync } from 'node:fs'

let fallos = []
const check = (n, cond, extra = '') => {
  console.log((cond ? '  OK   ' : '  FALLA') + `  ${n}` + (!cond && extra ? `  -> ${JSON.stringify(extra)}` : ''))
  if (!cond) fallos.push(n)
}

const sinComentarios = (texto) => texto
  .replace(/\/\*[\s\S]*?\*\//g, '')
  .replace(/"""[\s\S]*?"""/g, '')
  .replace(/^\s*(\/\/|#).*$/gm, '')

const leer = (ruta) => sinComentarios(readFileSync(new URL(ruta, import.meta.url), 'utf8'))

const FORMULARIO_PUBLICO = leer('../src/modules/publico/FormularioPQRS.jsx')
const SEGUIMIENTO = leer('../src/modules/publico/SeguimientoPQRS.jsx')
const LISTA = readFileSync(new URL('../src/modules/pqrs/PQRSList.jsx', import.meta.url), 'utf8')
const PY_PUBLICO = readFileSync(
  new URL('../../backend/app/modules/pqrs/router_public.py', import.meta.url), 'utf8')

console.log('\n== Ningún formulario pide el área ==')
check('el formulario público no la pide',
  !/area_responsable/.test(FORMULARIO_PUBLICO),
  (FORMULARIO_PUBLICO.match(/.{0,60}area_responsable.{0,60}/) || [])[0])
// En PQRSList.jsx la lista sí pinta el área (es interna); lo que no puede
// es pedirla el modal de crear.
const modalCrear = sinComentarios(LISTA.match(/function ModalCrear\(([\s\S]*?)\n}\n/)[1])
check('el formulario interno no la pide',
  !/area_responsable/.test(modalCrear),
  (modalCrear.match(/.{0,60}area_responsable.{0,60}/) || [])[0])

console.log('\n== El cliente no ve qué área tiene su caso ==')
check('la pantalla de seguimiento no la pinta',
  !/area_responsable/.test(SEGUIMIENTO),
  (SEGUIMIENTO.match(/.{0,60}area_responsable.{0,60}/) || [])[0])
// Esconderla solo en la pantalla la deja viajando igual.
for (const schema of ['PQRSConsultaOut', 'PQRSPublicaOut']) {
  const cuerpo = PY_PUBLICO.match(new RegExp(`class ${schema}\\(BaseModel\\):([\\s\\S]*?)\\n\\n\\n`))[1]
  check(`${schema} no tiene area_responsable`,
    !/^\s{4}area_responsable/m.test(cuerpo), cuerpo)
}

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
