import api from '../../core/api.js'

// ── Tablero ───────────────────────────────────────────────────
/** Todo llega calculado del servidor: semáforo, acumulados y comparaciones. */
export const obtenerTablero = (params = {}) =>
  api.get('/indicadores/tablero', { params }).then(r => r.data)

/** Fuentes que el portal sabe calcular solo (PQRS, Master Planner). */
export const obtenerCatalogo = () =>
  api.get('/indicadores/catalogo').then(r => r.data)

// ── Definición de indicadores ─────────────────────────────────
export const listarIndicadores = (params = {}) =>
  api.get('/indicadores', { params }).then(r => r.data)

export const obtenerIndicador = (id, params = {}) =>
  api.get(`/indicadores/${id}`, { params }).then(r => r.data)

export const crearIndicador = (payload) =>
  api.post('/indicadores', payload).then(r => r.data)

export const actualizarIndicador = (id, payload) =>
  api.patch(`/indicadores/${id}`, payload).then(r => r.data)

/** Solo funciona si el indicador no tiene mediciones; si no, responde 409. */
export const eliminarIndicador = (id) =>
  api.delete(`/indicadores/${id}`)

// ── Mediciones ────────────────────────────────────────────────
export const registrarMedicion = (id, formData) =>
  api.post(`/indicadores/${id}/mediciones`, formData).then(r => r.data)

export const recalcularIndicador = (id, anio, mes) =>
  api.post(`/indicadores/${id}/calcular`, null, { params: { anio, mes } }).then(r => r.data)

/** Recalcula de un golpe todos los automáticos del periodo. */
export const recalcularPeriodo = (anio, mes) =>
  api.post('/indicadores/calcular-periodo', null, { params: { anio, mes } }).then(r => r.data)

export const listarHistorial = (id) =>
  api.get(`/indicadores/${id}/historial`).then(r => r.data)
