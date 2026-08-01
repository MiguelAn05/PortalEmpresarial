import api from '../../core/api.js'

// ── Proyectos ─────────────────────────────────────────────────
export const listarProyectos = (params = {}) =>
  api.get('/master-planner/proyectos', { params }).then(r => r.data)

export const obtenerProyecto = (id) =>
  api.get(`/master-planner/proyectos/${id}`).then(r => r.data)

export const crearProyecto = (payload) =>
  api.post('/master-planner/proyectos', payload).then(r => r.data)

export const actualizarProyecto = (id, payload) =>
  api.patch(`/master-planner/proyectos/${id}`, payload).then(r => r.data)

/** Archivar/desarchivar es solo un PATCH: saca el proyecto de la vista sin borrar nada. */
export const archivarProyecto = (id, archivado = true) =>
  api.patch(`/master-planner/proyectos/${id}`, { archivado }).then(r => r.data)

/** Solo funciona si el proyecto no tiene tareas; si las tiene, el backend responde 409. */
export const eliminarProyecto = (id) =>
  api.delete(`/master-planner/proyectos/${id}`)

// ── Presupuesto ───────────────────────────────────────────────
export const listarPresupuesto = (proyectoId) =>
  api.get(`/master-planner/proyectos/${proyectoId}/presupuesto`).then(r => r.data)

export const agregarItemPresupuesto = (proyectoId, payload) =>
  api.post(`/master-planner/proyectos/${proyectoId}/presupuesto`, payload).then(r => r.data)

export const eliminarItemPresupuesto = (itemId) =>
  api.delete(`/master-planner/presupuesto/${itemId}`)

// ── Tareas ────────────────────────────────────────────────────
export const listarTareas = (params = {}) =>
  api.get('/master-planner/tareas', { params }).then(r => r.data)

export const listarMisTareas = () =>
  api.get('/master-planner/tareas/mias').then(r => r.data)

export const listarTareasDeProyecto = (proyectoId) =>
  api.get(`/master-planner/proyectos/${proyectoId}/tareas`).then(r => r.data)

export const obtenerTarea = (id) =>
  api.get(`/master-planner/tareas/${id}`).then(r => r.data)

export const crearTarea = (proyectoId, payload) =>
  api.post(`/master-planner/proyectos/${proyectoId}/tareas`, payload).then(r => r.data)

export const crearSubtarea = (tareaId, payload) =>
  api.post(`/master-planner/tareas/${tareaId}/subtareas`, payload).then(r => r.data)

export const actualizarTarea = (id, payload) =>
  api.patch(`/master-planner/tareas/${id}`, payload).then(r => r.data)

export const eliminarTarea = (id) =>
  api.delete(`/master-planner/tareas/${id}`)

// ── Línea de tiempo de actualizaciones ───────────────────────
export const listarActualizaciones = (tareaId) =>
  api.get(`/master-planner/tareas/${tareaId}/actualizaciones`).then(r => r.data)

export const agregarActualizacion = (tareaId, formData) =>
  api.post(`/master-planner/tareas/${tareaId}/actualizaciones`, formData).then(r => r.data)

// ── Usuarios asignables ──────────────────────────────────────
export const listarUsuariosAsignables = () =>
  api.get('/master-planner/usuarios-asignables').then(r => r.data)
