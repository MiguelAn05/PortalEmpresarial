// Lo que el portal NO le dice al cliente sobre el plazo de su solicitud.
//
// La pantalla de seguimiento le mostraba la fecha limite de respuesta y, al
// pasar, un aviso en rojo: «El plazo de respuesta esta vencido». Los terminos
// de una PQRS salen de la Ley 1755 de 2015, asi que eso es la empresa
// comprometiendose por escrito ante un tercero con una fecha y despues
// dejandole constancia de que no la cumplio — redactada por nosotros y
// consultable cuando quiera.
//
// Que un plazo se venza es un problema INTERNO y se avisa por dentro, antes
// (/pqrs/por-vencer). Al cliente se le responde.
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

const VISTA = sinComentarios(readFileSync(
  new URL('../src/modules/publico/SeguimientoPQRS.jsx', import.meta.url), 'utf8'))
const PY_PUBLICO = readFileSync(
  new URL('../../backend/app/modules/pqrs/router_public.py', import.meta.url), 'utf8')

console.log('\n== La pantalla de seguimiento no habla de plazos ==')
check('no le anuncia al cliente que algo se vencio',
  !/vencid|incumpl/i.test(VISTA), (VISTA.match(/.{0,60}(vencid|incumpl).{0,60}/i) || [])[0])
check('ni le muestra una fecha limite',
  !/fecha_limite_sla|fecha l[ií]mite/i.test(VISTA),
  (VISTA.match(/.{0,60}(fecha_limite_sla|fecha l[ií]mite).{0,60}/i) || [])[0])

console.log('\n== Y el servidor tampoco la manda ==')
// Igual que con el comentario del seguimiento: no es que llegue y no se
// pinte, es que no existe en el schema publico. Esconderlo solo en la
// pantalla deja el dato viajando igual.
const schemaPublico = PY_PUBLICO.match(
  /class PQRSConsultaOut\(BaseModel\):([\s\S]*?)\n\n\n/)[1]
check('PQRSConsultaOut no tiene fecha_limite_sla',
  !/^\s{4}fecha_limite_sla/m.test(schemaPublico), schemaPublico)
check('pero si trae lo que el cliente viene a ver',
  /^\s{4}estado:/m.test(schemaPublico) && /^\s{4}historial:/m.test(schemaPublico))
// Solo en la CONSULTA: al radicar, el SLA si se calcula y se guarda — es el
// plazo interno, y de el viven los recordatorios de «por vencer».
const respuestaDeConsulta = PY_PUBLICO.match(/return PQRSConsultaOut\(([\s\S]*?)\n    \)/)[1]
check('la respuesta de la consulta no se la arma aparte',
  !/fecha_limite_sla/.test(respuestaDeConsulta), respuestaDeConsulta)

console.log()
if (fallos.length) { console.log(`FALLARON ${fallos.length}: ${fallos.join(', ')}`); process.exit(1) }
console.log('TODAS LAS PRUEBAS PASARON')
