/**
 * Constantes y lógica pura del módulo PQRS.
 *
 * Vive en un .js y no dentro de los .jsx para que `tests/pqrs.test.mjs` pueda
 * importarlo: Node no lee JSX.
 */

/**
 * Tope de cada dato corregible. ATADOS a `PQRSEditarDatos` en
 * `backend/app/modules/pqrs/schemas.py`, que a su vez copia el largo de las
 * columnas: si uno cambia, cambian los tres. Un campo sin su `maxLength` en
 * pantalla es el 422 que ya dejó una página en blanco una vez.
 */
export const LIMITES_DATOS = {
  empresa: 150,
  nit_cedula: 30,
  cliente_nombre: 150,
  cliente_email: 180,
  cliente_telefono: 40,
  ciudad: 100,
  departamento: 100,
  presentacion: 30,
  cantidad_presentacion: 20,
  lote: 50,
  factura_numero: 50,
  cantidad_factura: 20,
  cantidad_reclamo: 20,
}

/**
 * Topes al RADICAR (formulario interno y público): los corregibles más el
 * producto. Atados a las columnas de `pqrs_solicitudes`, que el servidor
 * vuelve a revisar en `validar_largos()`. Sin el tope en pantalla, escribir
 * «5 galones de 20 litros» en una cantidad no dejaba registrar la PQRS.
 */
export const LIMITES_RADICACION = {
  ...LIMITES_DATOS,
  producto_codigo: 50,
  producto_nombre: 300,
}

/** Los datos corregibles, en el orden de la pantalla. */
export const CAMPOS_EDITABLES = Object.keys(LIMITES_DATOS)

export const DEPARTAMENTOS = [
  'Amazonas', 'Antioquia', 'Arauca', 'Atlántico', 'Bolívar', 'Boyacá', 'Caldas',
  'Caquetá', 'Casanare', 'Cauca', 'Cesar', 'Chocó', 'Córdoba', 'Cundinamarca',
  'Guainía', 'Guaviare', 'Huila', 'La Guajira', 'Magdalena', 'Meta', 'Nariño',
  'Norte de Santander', 'Putumayo', 'Quindío', 'Risaralda', 'San Andrés',
  'Santander', 'Sucre', 'Tolima', 'Valle del Cauca', 'Vaupés', 'Vichada',
]

export const PRESENTACIONES = ['Unidad', 'Kilo', 'Gramo', 'Litro', 'Mililitro']

const normalizar = (texto) => (texto ?? '').trim().toLowerCase().replace(/\s+/g, ' ')

/**
 * Con qué nombre se reconoce una PQRS en la lista y en la cabecera.
 *
 * Una empresa se reconoce por la empresa, no por quién llamó: «Industrias del
 * Valle» se encuentra de un vistazo, «Juan Pérez» obliga a abrirla para saber
 * de qué cliente es. El contacto baja a la segunda línea.
 *
 * Una persona natural escribe su propio nombre en «Empresa / Persona» — el
 * formulario público lo pide obligatorio —, así que empresa y contacto
 * coinciden. Ahí se muestra el nombre una sola vez: repetirlo debajo es
 * ruido. Lo mismo si la empresa viene vacía (PQRS internas viejas).
 *
 * Devuelve `{ titulo, subtitulo }`; `subtitulo` es null cuando no aporta.
 */
export function nombrePrincipal(pqrs) {
  const empresa = (pqrs?.empresa ?? '').trim()
  const contacto = (pqrs?.cliente_nombre ?? '').trim()
  if (empresa && normalizar(empresa) !== normalizar(contacto)) {
    return { titulo: empresa, subtitulo: contacto || null }
  }
  return { titulo: contacto || empresa, subtitulo: null }
}

/**
 * Si a esta PQRS le aplica la sección de producto y factura.
 *
 * Una queja es sobre el servicio y una felicitación no trae producto — el
 * formulario público ni los pide —, así que ahí no se ofrecen. Salvo que ya
 * tenga algo de eso escrito: lo que existe tiene que poder corregirse.
 */
export function aplicaProducto(pqrs) {
  if (!['queja', 'felicitacion'].includes(pqrs?.tipo)) return true
  return ['presentacion', 'lote', 'factura_numero', 'cantidad_factura', 'cantidad_reclamo',
    'adjunto_producto', 'adjunto_factura'].some(c => pqrs[c])
}

/** Los valores de la PQRS que se ponen en el formulario de corrección. */
export function datosEditables(pqrs) {
  return Object.fromEntries(CAMPOS_EDITABLES.map(c => [c, pqrs?.[c] ?? '']))
}

/**
 * Solo lo que de verdad cambió, listo para `PATCH /pqrs/{id}/datos`.
 *
 * Mandar el formulario entero haría que el servidor anotara en el historial
 * «Ciudad: Bello → Bello» por cada campo que nadie tocó. Se compara sin los
 * espacios de los extremos, que es como el servidor lo guarda; un campo
 * vaciado viaja como cadena vacía, que el servidor entiende como «bórralo».
 */
export function cambiosDeDatos(pqrs, form) {
  const cambios = {}
  for (const campo of CAMPOS_EDITABLES) {
    const antes = (pqrs?.[campo] ?? '').trim()
    const ahora = (form?.[campo] ?? '').trim()
    if (antes !== ahora) cambios[campo] = ahora
  }
  return cambios
}
