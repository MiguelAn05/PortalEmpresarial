import api from '../../core/api.js'

export const listarFichas = (params = {}) =>
  api.get('/fichas-seguridad', { params }).then(r => r.data)

export const obtenerFicha = (id) =>
  api.get(`/fichas-seguridad/${id}`).then(r => r.data)

/** Los campos vacíos no se mandan: el servidor los toma como «no escrito». */
function formulario(campos, archivo) {
  const datos = new FormData()
  Object.entries(campos).forEach(([clave, valor]) => {
    if (valor !== '' && valor != null) datos.append(clave, typeof valor === 'string' ? valor.trim() : valor)
  })
  datos.append('archivo', archivo)
  return datos
}

export const crearFicha = (campos, archivo) =>
  api.post('/fichas-seguridad', formulario(campos, archivo)).then(r => r.data)

export const subirVersion = (fichaId, campos, archivo) =>
  api.post(`/fichas-seguridad/${fichaId}/versiones`, formulario(campos, archivo)).then(r => r.data)

export const editarFicha = (fichaId, datos) =>
  api.patch(`/fichas-seguridad/${fichaId}`, datos).then(r => r.data)

/** Corrige número, fecha u observaciones de una versión ya subida. El PDF no cambia. */
export const editarVersion = (versionId, datos) =>
  api.patch(`/fichas-seguridad/versiones/${versionId}`, datos).then(r => r.data)

export const hacerVigente = (versionId) =>
  api.post(`/fichas-seguridad/versiones/${versionId}/vigente`).then(r => r.data)

/** Sin `incluirVersiones` el servidor responde 409 explicando qué se perdería. */
export const eliminarFicha = (fichaId, incluirVersiones = false) =>
  api.delete(`/fichas-seguridad/${fichaId}`, { params: incluirVersiones ? { incluir_versiones: true } : {} })

/**
 * Con `responseType: 'blob'` el cuerpo de un error también llega como blob y
 * `mensajeDeError` no encontraría el `detail`. Se lee y se deja como JSON.
 */
async function errorLegible(error) {
  try {
    if (error?.response?.data instanceof Blob) {
      error.response.data = JSON.parse(await error.response.data.text())
    }
  } catch { /* si no era JSON, mensajeDeError usa su texto por defecto */ }
  return error
}

/**
 * Abre el PDF en una pestaña nueva. Va por axios para que lleve la sesión: el
 * archivo no está en `/uploads` y el endpoint pide usuario como cualquier otro.
 *
 * La pestaña se abre ANTES de pedir el archivo: el navegador solo permite abrir
 * ventanas como respuesta directa a un clic, y después de un `await` ya no lo
 * es (lo bloquearía como ventana emergente). Si aun así no se pudo, se descarga.
 */
export async function abrirPdf(version) {
  const ventana = window.open('', '_blank')
  try {
    const r = await api.get(`/fichas-seguridad/versiones/${version.id}/archivo`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
    if (ventana) {
      ventana.location.href = url
    } else {
      const a = document.createElement('a')
      a.href = url
      a.download = version.nombre_original || 'ficha-de-seguridad.pdf'
      document.body.appendChild(a)
      a.click()
      a.remove()
    }
    // El navegador necesita el enlace vivo mientras carga el visor.
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    ventana?.close()
    throw await errorLegible(error)
  }
}

// ── Documentos generados ──────────────────────────────────────

export const listarDocumentos = (params = {}) =>
  api.get('/fichas-seguridad/documentos', { params }).then(r => r.data)

/** Lee el PDF y PROPONE los datos: no guarda nada y el documento no sale del servidor. */
export const extraerDocumento = (tipo, archivo) => {
  const datos = new FormData()
  datos.append('tipo', tipo)
  datos.append('archivo', archivo)
  return api.post('/fichas-seguridad/documentos/extraer', datos).then(r => r.data)
}

export const generarDocumento = (tipo, datos) =>
  api.post('/fichas-seguridad/documentos/generar', { tipo, datos }).then(r => r.data)

/** Baja el PDF por axios (lleva la sesión) y lo guarda con su nombre. */
export async function descargarDocumento(documento) {
  try {
    const r = await api.get(`/fichas-seguridad/documentos/${documento.id}/archivo`, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
    const a = document.createElement('a')
    a.href = url
    a.download = documento.nombre_archivo || 'documento.pdf'
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    throw await errorLegible(error)
  }
}

/** El PDF con lo que hay en pantalla, en una pestaña nueva y sin guardar nada. */
export async function abrirVistaPrevia(tipo, datos) {
  const ventana = window.open('', '_blank')
  try {
    const r = await api.post('/fichas-seguridad/documentos/vista-previa', { tipo, datos }, { responseType: 'blob' })
    const url = URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }))
    if (ventana) ventana.location.href = url
    setTimeout(() => URL.revokeObjectURL(url), 60_000)
  } catch (error) {
    ventana?.close()
    throw await errorLegible(error)
  }
}
