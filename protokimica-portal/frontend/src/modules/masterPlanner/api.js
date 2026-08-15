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
// ── Cierre de proyectos ──────────────────────────────────────
/** Finaliza o cancela. Va como FormData porque puede llevar evidencia. */
export const cerrarProyecto = (id, formData) =>
  api.post(`/master-planner/proyectos/${id}/cerrar`, formData).then(r => r.data)

/** Vuelve a ejecución. El acta anterior queda anulada, no se borra. */
export const retomarProyecto = (id) =>
  api.post(`/master-planner/proyectos/${id}/retomar`).then(r => r.data)

export const listarCierres = (id) =>
  api.get(`/master-planner/proyectos/${id}/cierres`).then(r => r.data)

export const eliminarProyecto = (id) =>
  api.delete(`/master-planner/proyectos/${id}`)

// ── Resumen gerencial ─────────────────────────────────────────
/** Todo viene calculado del servidor: KPIs, presupuesto, semáforo, cumplimiento y carga. */
export const obtenerResumen = (params = {}) =>
  api.get('/master-planner/resumen', { params }).then(r => r.data)

// ── Presupuesto ───────────────────────────────────────────────
export const listarPresupuesto = (proyectoId) =>
  api.get(`/master-planner/proyectos/${proyectoId}/presupuesto`).then(r => r.data)

export const agregarItemPresupuesto = (proyectoId, payload) =>
  api.post(`/master-planner/proyectos/${proyectoId}/presupuesto`, payload).then(r => r.data)

export const actualizarItemPresupuesto = (itemId, payload) =>
  api.patch(`/master-planner/presupuesto/${itemId}`, payload).then(r => r.data)

// ── Aprobación y pago ─────────────────────────────────────────
// Administración aprueba cuánto se puede desembolsar; Tesorería registra los
// abonos. Son dos manos distintas y cada endpoint exige su área.
export const aprobarItem = (itemId, payload) =>
  api.patch(`/master-planner/presupuesto/${itemId}/aprobar`, payload).then(r => r.data)

export const revocarAprobacion = (itemId) =>
  api.delete(`/master-planner/presupuesto/${itemId}/aprobar`).then(r => r.data)

export const registrarPago = (itemId, formData) =>
  api.post(`/master-planner/presupuesto/${itemId}/pagos`, formData).then(r => r.data)

export const anularPago = (pagoId) =>
  api.delete(`/master-planner/pagos/${pagoId}`)

export const eliminarItemPresupuesto = (itemId) =>
  api.delete(`/master-planner/presupuesto/${itemId}`)

// ── Historial de cambios ──────────────────────────────────────
export const listarHistorialProyecto = (proyectoId, params = {}) =>
  api.get(`/master-planner/proyectos/${proyectoId}/historial`, { params }).then(r => r.data)

export const listarHistorialTarea = (tareaId) =>
  api.get(`/master-planner/tareas/${tareaId}/historial`).then(r => r.data)

export const listarHistorialGeneral = (params = {}) =>
  api.get('/master-planner/historial', { params }).then(r => r.data)

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

// ── Calendario de Outlook ────────────────────────────────────
// Siempre el propio: el backend lo saca del token y no acepta otro usuario.
export const listarEventosOutlook = (desde, hasta) =>
  api.get('/master-planner/calendario/outlook', { params: { desde, hasta } })
    .then(r => r.data)
