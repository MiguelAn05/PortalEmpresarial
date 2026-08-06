/**
 * Las áreas de la empresa. Fuente única del frontend.
 *
 * Antes esta lista estaba repetida en seis archivos y con contenidos
 * distintos entre módulos. Nunca declares una lista de áreas dentro de un
 * componente: impórtala de aquí.
 *
 * El gemelo es `backend/app/core/areas.py`, y una prueba verifica que los dos
 * digan exactamente lo mismo.
 */
export const AREAS = [
  'TICS',
  'Calidad',
  'SST',
  'Controlados',
  'Facturación',
  'Ventas Institucionales',
  'Mercadeo',
  'Servicio al Cliente',
  'Infraestructura',
  'Logística',
  'Gestión Humana',
  'Contabilidad',
  'Producción',
  'Control Interno',
  'Control Interno',
  'Aseguramiento',
  'Abastecimiento',
  'Comercial',

]

/**
 * Nombres viejos que pueden quedar en datos guardados antes de la
 * unificación, y su área actual. Sirve para que un registro histórico no se
 * muestre con un área que ya no existe.
 */
export const EQUIVALENCIAS_HISTORICAS = {
  'TI': 'TICS',
  'Sistemas': 'TICS',
  'Talento Humano': 'Gestión humana',
}

export function normalizarArea(area) {
  if (!area || !area.trim()) return null
  const limpia = area.trim()
  return EQUIVALENCIAS_HISTORICAS[limpia] ?? limpia
}

/**
 * Las áreas a ofrecer en un desplegable, incluyendo el valor actual aunque
 * ya no esté en la lista. Sin esto, editar un registro viejo le borraría el
 * área en silencio al guardar.
 */
export function areasParaSelect(valorActual) {
  if (!valorActual || AREAS.includes(valorActual)) return AREAS
  return [...AREAS, valorActual]
}
