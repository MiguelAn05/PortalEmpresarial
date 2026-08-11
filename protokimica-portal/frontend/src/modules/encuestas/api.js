import api from '../../core/api.js'

// ── Panel ─────────────────────────────────────────────────────
/**
 * Todas las respuestas, vengan de PQRS o de las encuestas del módulo.
 * Promedios, ranking y distribución llegan calculados del servidor.
 */
export const obtenerPanel = (params = {}) =>
  api.get('/encuestas/panel', { params }).then(r => r.data)

// ── Plantillas ────────────────────────────────────────────────
export const listarPlantillas = () =>
  api.get('/encuestas').then(r => r.data)

export const crearPlantilla = (payload) =>
  api.post('/encuestas', payload).then(r => r.data)

export const actualizarPlantilla = (id, payload) =>
  api.patch(`/encuestas/${id}`, payload).then(r => r.data)

/** Solo si no tiene respuestas; si las tiene, responde 409. */
export const eliminarPlantilla = (id) =>
  api.delete(`/encuestas/${id}`)

// ── Formulario público (sin sesión) ───────────────────────────
export const obtenerEncuestaPublica = (slug) =>
  api.get(`/public/encuestas/${slug}`).then(r => r.data)

export const responderEncuestaPublica = (slug, payload) =>
  api.post(`/public/encuestas/${slug}`, payload).then(r => r.data)
