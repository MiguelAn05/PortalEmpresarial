import api from '../../core/api.js'

/**
 * Oportunidades de Mejora.
 *
 * El filtro por área lo impone el servidor: pedir `?area=` de otra no la
 * abre, y una OMP ajena responde 404. Aquí no se decide nada de eso.
 */
export const listarOportunidades = (params = {}) =>
  api.get('/mejora', { params }).then(r => r.data)

export const obtenerOportunidad = (id) =>
  api.get(`/mejora/${id}`).then(r => r.data)

export const crearOportunidad = (datos) =>
  api.post('/mejora', datos).then(r => r.data)

export const actualizarOportunidad = (id, datos) =>
  api.patch(`/mejora/${id}`, datos).then(r => r.data)

export const cambiarEstado = (id, estado) =>
  api.patch(`/mejora/${id}/estado`, { estado }).then(r => r.data)

export const eliminarOportunidad = (id) =>
  api.delete(`/mejora/${id}`).then(r => r.data)

/**
 * Si ya hay medición del mes siguiente y si eso fue una mejora — ya resuelto
 * por el servidor, porque saber si subir es bueno depende de la dirección
 * del indicador y esa regla vive junto al semáforo.
 */
export const consultarVerificacion = (id) =>
  api.get(`/mejora/${id}/verificacion`).then(r => r.data)

export const registrarVerificacion = (id, datos) =>
  api.post(`/mejora/${id}/verificacion`, datos).then(r => r.data)

// ── Acciones del plan ─────────────────────────────────────────
export const agregarAccion = (ompId, datos) =>
  api.post(`/mejora/${ompId}/acciones`, datos).then(r => r.data)

export const actualizarAccion = (ompId, accionId, datos) =>
  api.patch(`/mejora/${ompId}/acciones/${accionId}`, datos).then(r => r.data)

export const eliminarAccion = (ompId, accionId) =>
  api.delete(`/mejora/${ompId}/acciones/${accionId}`).then(r => r.data)
