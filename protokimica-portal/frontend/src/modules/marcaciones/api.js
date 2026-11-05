import api from '../../core/api.js'

/** Un día completo: personas, resumen por área y líder, y si el reloj está enviando. Sin fecha, hoy. */
export const obtenerDia = (params = {}) =>
  api.get('/marcaciones/dia', { params }).then(r => r.data)

export const obtenerPersona = (empCode, params = {}) =>
  api.get(`/marcaciones/persona/${encodeURIComponent(empCode)}`, { params }).then(r => r.data)

export const obtenerInforme = (params) =>
  api.get('/marcaciones/informe', { params }).then(r => r.data)

/**
 * Baja el CSV y lo entrega al navegador. Va por axios (y no con un enlace)
 * para que lleve la sesión: el endpoint pide usuario como cualquier otro.
 */
export async function descargarCsv(params) {
  const r = await api.get('/marcaciones/informe.csv', { params, responseType: 'blob' })
  const url = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = url
  a.download = `marcaciones_${params.desde}_${params.hasta}.csv`
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

/** El motivo de una novedad de una persona un día. Repetirlo lo corrige. */
export const justificarNovedad = (datos) =>
  api.put('/marcaciones/justificacion', datos).then(r => r.data)

export const quitarJustificacion = (params) =>
  api.delete('/marcaciones/justificacion', { params })
