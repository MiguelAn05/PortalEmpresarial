import { useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '../../core/AuthContext.jsx'
import api from '../../core/api.js'
import { AREAS } from '../../core/areas.js'
import {
  IconoAlDia, IconoAlerta, IconoBuscar, IconoCandado, IconoClip,
  IconoComentario, IconoEmpresa, IconoEscalar, IconoEstrella, IconoEtiqueta,
  IconoRecargar, IconoRechazo, IconoRecibo, IconoReloj, IconoUsuario,
} from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'

// Mismos números que el buscador público y que el servidor.
const MINIMO_BUSQUEDA = 2
const ESPERA_BUSQUEDA_MS = 300

/**
 * El cliente escribió su producto porque no lo encontró: aquí se cambia por
 * el del catálogo.
 *
 * Se hace ANTES de cerrar —y el servidor no deja cerrar sin esto— porque
 * después ya no se puede corregir, y el informe de qué producto da más
 * problemas quedaría contando «hipoclorito el de 20 litros» como si fuera un
 * producto aparte.
 *
 * Lo que el cliente escribió se conserva a la vista mientras se busca: es la
 * única pista de qué quiso decir.
 */
function ConfirmarProducto({ pqrs, puedeConfirmar, onConfirmado }) {
  const [busqueda, setBusqueda] = useState('')
  const [resultados, setResultados] = useState([])
  const [buscando, setBuscando] = useState(false)
  const [error, setError] = useState('')
  const temporizador = useRef(null)
  const turno = useRef(0)

  const buscar = (texto) => {
    setBusqueda(texto)
    setError('')
    clearTimeout(temporizador.current)

    if (texto.trim().length < MINIMO_BUSQUEDA) {
      setResultados([])
      setBuscando(false)
      return
    }

    setBuscando(true)
    const mio = ++turno.current
    temporizador.current = setTimeout(async () => {
      try {
        const { data } = await api.get('/catalogo/productos',
                                       { params: { q: texto.trim() } })
        if (mio === turno.current) setResultados(data)
      } catch (err) {
        if (mio === turno.current) {
          setResultados([])
          setError(mensajeDeError(err, 'No se pudo consultar el catálogo.'))
        }
      } finally {
        if (mio === turno.current) setBuscando(false)
      }
    }, ESPERA_BUSQUEDA_MS)
  }

  const confirmar = useMutation({
    mutationFn: (codigo) => {
      const datos = new FormData()
      datos.append('producto_codigo', codigo)
      return api.patch(`/pqrs/${pqrs.id}/producto`, datos)
    },
    onSuccess: () => { setError(''); onConfirmado() },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo confirmar el producto.')),
  })

  return (
    <div className="rounded-xl border border-alerta/30 bg-alerta-bg p-4 mb-4">
      {/* El estado no se comunica solo con color: el ámbar de la marca no
          alcanza el contraste mínimo sobre blanco. */}
      <div className="flex items-start gap-2">
        <IconoAlerta tam={16} className="text-alerta mt-0.5 flex-shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-semibold text-alerta">Producto sin confirmar</p>
          <p className="text-sm text-texto-2 mt-0.5">
            El cliente escribió «<b className="text-texto">{pqrs.producto_nombre}</b>»
            porque no lo encontró en el buscador.
            {puedeConfirmar
              ? ' Búscalo en el catálogo: no se puede cerrar hasta confirmarlo.'
              : ' Servicio al Cliente lo confirma antes de cerrar la solicitud.'}
          </p>
        </div>
      </div>

      {puedeConfirmar && (
        <div className="mt-3">
          <input
            value={busqueda}
            onChange={(e) => buscar(e.target.value)}
            placeholder="Buscar en el catálogo por nombre o código…"
            className="w-full px-3 py-2 rounded-lg border border-borde-fuerte bg-white text-sm
              text-texto placeholder-texto-3 focus:outline-none focus:border-acento"
          />

          {buscando && <p className="text-xs text-texto-3 mt-2">Buscando…</p>}

          {!buscando && resultados.length > 0 && (
            <ul className="mt-2 bg-white border border-borde rounded-lg divide-y divide-borde
              overflow-hidden max-h-56 overflow-y-auto">
              {resultados.map((p) => (
                <li key={p.codigo}>
                  <button
                    onClick={() => confirmar.mutate(p.codigo)}
                    disabled={confirmar.isPending}
                    className="w-full text-left px-3 py-2 hover:bg-superficie-2
                      disabled:opacity-50 transition-colors duration-150"
                  >
                    <div className="text-sm text-texto">{p.nombre}</div>
                    <div className="text-xs text-texto-3">
                      <span className="cifra">{p.codigo}</span>
                      {p.presentacion && ` · ${p.presentacion}`}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}

          {!buscando && busqueda.trim().length >= MINIMO_BUSQUEDA
            && resultados.length === 0 && !error && (
            <p className="text-xs text-texto-2 mt-2">
              No hay nada con «{busqueda.trim()}» en el catálogo. Si el producto
              existe pero no aparece, avísale a TIC's: puede que la
              sincronización con el ERP esté detenida.
            </p>
          )}

          {error && <p role="alert" className="text-sm text-negativo mt-2">{error}</p>}
        </div>
      )}
    </div>
  )
}

// El color de un badge es una escala de gravedad, no un arcoíris: morado,
// naranja y teal elegidos al azar obligan a mirar la palabra igual, así que
// el color no estaba diciendo nada. Ahora sube con la gravedad real.
const TIPOS = {
  peticion:     { label: 'Petición',     color: 'bg-superficie-2 text-texto-2' },
  queja:        { label: 'Queja',        color: 'bg-alerta-bg text-alerta'     },
  reclamo:      { label: 'Reclamo',      color: 'bg-negativo-bg text-negativo' },
  sugerencia:   { label: 'Sugerencia',   color: 'bg-info-bg text-info'         },
  felicitacion: { label: 'Felicitación', color: 'bg-positivo-bg text-positivo' },
}

const ESTADOS = {
  recibido:   { label: 'Recibido',   color: 'bg-superficie-2 text-texto-2' },
  asignado:   { label: 'Asignado',   color: 'bg-info-bg text-info'         },
  en_proceso: { label: 'En proceso', color: 'bg-alerta-bg text-alerta'     },
  resuelto:   { label: 'Resuelto',   color: 'bg-positivo-bg text-positivo' },
  cerrado:    { label: 'Cerrado',    color: 'bg-superficie-2 text-texto-2' },
}

const PRIORIDADES = {
  baja:    { label: 'Baja',    color: 'text-positivo' },
  media:   { label: 'Media',   color: 'text-texto-2'  },
  alta:    { label: 'Alta',    color: 'text-alerta'   },
  critica: { label: 'Crítica', color: 'text-negativo' },
}

const EVENTOS = {
  cambio_estado:           { Icono: IconoRecargar,  label: 'Cambio de estado'       },
  asignacion:              { Icono: IconoUsuario,   label: 'Asignación'             },
  asignacion_area:         { Icono: IconoEmpresa,   label: 'Área asignada'          },
  comentario:              { Icono: IconoComentario,label: 'Comentario'             },
  escalamiento:            { Icono: IconoEscalar,   label: 'Escalamiento'           },
  autorizacion_solicitada: { Icono: IconoCandado,   label: 'Autorización solicitada'},
  autorizacion_respondida: { Icono: IconoAlDia,     label: 'Autorización respondida'},
  reclasificacion:         { Icono: IconoEtiqueta,  label: 'Reclasificación'        },
  confirmacion_producto:   { Icono: IconoRecibo,    label: 'Producto confirmado'    },
}

// Las áreas viven en un solo sitio: src/core/areas.js

function Badge({ map, value }) {
  const item = map[value] || { label: value, color: 'bg-superficie-2 text-texto-2' }
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}

function formatFecha(fecha) {
  if (!fecha) return '—'
  return new Date(fecha).toLocaleString('es-CO', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

function SLALabel({ fechaLimite, cerrado }) {
  if (!fechaLimite || cerrado) return null
  const diff = new Date(fechaLimite) - new Date()
  const dias = Math.ceil(diff / (1000 * 60 * 60 * 24))
  // Punto y palabra, no solo color: el rojo no se lee en voz alta.
  const linea = (Icono, clase, texto) => (
    <span className={`inline-flex items-center gap-1.5 text-sm ${clase}`}>
      <Icono tam={15} />
      {texto}
    </span>
  )
  if (dias < 0)   return linea(IconoAlerta, 'font-semibold text-negativo', `Vencida hace ${Math.abs(dias)} día(s)`)
  if (dias === 0) return linea(IconoAlerta, 'font-semibold text-negativo', 'Vence hoy')
  if (dias <= 2)  return linea(IconoReloj, 'font-semibold text-alerta', `Vence en ${dias} día(s)`)
  return linea(IconoAlDia, 'text-positivo', `Vence en ${dias} días`)
}

// ── Panel de gestión ───────────────────────────────────────────────
/**
 * Mover el área, cambiar el estado, comentar y adjuntar: un solo formulario
 * y un solo guardado.
 *
 * Antes eran dos tarjetas separadas en la columna angosta. Para pasar un caso
 * a Calidad explicando por qué había que escribir el motivo arriba, al
 * asignar el área, y volver a escribirlo abajo, al cambiar el estado — y el
 * historial terminaba con el mismo texto dos veces.
 *
 * Qué campos se muestran lo dice el `alcance` que manda el servidor. La
 * pantalla no repite las reglas de permisos: las pregunta.
 */
function PanelGestion({ pqrs, alcance, hayPendiente, invalidar }) {
  const [area, setArea]             = useState('')
  const [estado, setEstado]         = useState('')
  const [comentario, setComentario] = useState('')
  const [evidencia, setEvidencia]   = useState(null)
  const [error, setError]           = useState('')
  const archivoRef = useRef(null)

  const mutacion = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      // Solo viaja lo que cambió: un campo vacío no es "ponlo en vacío",
      // es "no lo toques".
      if (area) datos.append('area', area)
      if (estado) datos.append('estado', estado)
      if (comentario.trim()) datos.append('comentario', comentario.trim())
      if (evidencia) datos.append('evidencia', evidencia)
      return api.patch(`/pqrs/${pqrs.id}/gestion`, datos)
    },
    onSuccess: () => {
      invalidar()
      setArea(''); setEstado(''); setComentario(''); setEvidencia(null)
      setError('')
      if (archivoRef.current) archivoRef.current.value = ''
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar la gestión.')),
  })

  const hayAlgoQueGuardar = Boolean(area || estado || comentario.trim() || evidencia)

  return (
    <div className="bg-white rounded-xl border border-borde p-5 shadow-sm">
      <h3 className="font-semibold text-acento-fuerte mb-4 text-sm">Gestionar solicitud</h3>

      {hayPendiente && (
        <div className="bg-alerta-bg border border-ambar/30 rounded-lg p-3 text-sm text-alerta mb-4">
          Hay una autorización pendiente y el estado queda congelado hasta que
          se responda. Sí puedes dejar un comentario o adjuntar un soporte.
        </div>
      )}

      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        {alcance?.puede_cambiar_area && (
          <div>
            <label htmlFor="gestion-area" className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
              Área responsable
            </label>
            <select
              id="gestion-area"
              value={area}
              onChange={(e) => setArea(e.target.value)}
              className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento"
            >
              <option value="">Sin cambio — {pqrs.area_responsable || 'sin asignar'}</option>
              {AREAS.filter(a => a !== pqrs.area_responsable).map(a => (
                <option key={a} value={a}>{a}</option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label htmlFor="gestion-estado" className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
            Estado
          </label>
          <select
            id="gestion-estado"
            value={estado}
            onChange={(e) => setEstado(e.target.value)}
            disabled={hayPendiente}
            className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento disabled:bg-superficie-2 disabled:text-texto-3"
          >
            <option value="">Sin cambio — {ESTADOS[pqrs.estado]?.label}</option>
            {Object.entries(ESTADOS)
              .filter(([clave]) => clave !== pqrs.estado)
              // 'cerrado' solo aparece si esta persona puede cerrar: mejor no
              // ofrecerlo que dar un 403 al guardar.
              .filter(([clave]) => clave !== 'cerrado' || alcance?.puede_cerrar)
              .map(([clave, { label }]) => (
                <option key={clave} value={clave}>{label}</option>
              ))
            }
          </select>
        </div>
      </div>

      {!alcance?.puede_cerrar && (
        <p className="text-xs text-texto-2 bg-superficie-2 rounded-lg px-3 py-2 mb-3">
          Márcala como <strong>Resuelto</strong> cuando termines. El cierre lo hace
          Servicio al Cliente, que revisa y clasifica antes de cerrar.
        </p>
      )}

      {!alcance?.puede_cambiar_area && (
        <p className="text-xs text-texto-2 bg-superficie-2 rounded-lg px-3 py-2 mb-3">
          El área la reparte Servicio al Cliente. Si este caso no es de tu área,
          escríbelo en el comentario y ellos lo mueven.
        </p>
      )}

      <label htmlFor="gestion-comentario" className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
        Comentario
      </label>
      <textarea
        id="gestion-comentario"
        value={comentario}
        onChange={(e) => setComentario(e.target.value)}
        placeholder="Qué pasó, qué hiciste, qué falta..."
        rows={3}
        className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none mb-3"
      />

      <label htmlFor="gestion-evidencia" className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
        Evidencia (opcional)
      </label>
      <input
        id="gestion-evidencia"
        ref={archivoRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        onChange={(e) => setEvidencia(e.target.files?.[0] || null)}
        className="w-full text-xs text-texto-2 mb-3 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde"
      />
      {evidencia && (
        <p className="text-xs text-texto-2 mb-3 -mt-2">{evidencia.name}</p>
      )}

      {error && <p role="alert" className="text-sm text-negativo mb-3">{error}</p>}

      <button
        onClick={() => mutacion.mutate()}
        disabled={!hayAlgoQueGuardar || mutacion.isPending}
        className="w-full bg-acento-fuerte hover:bg-acento text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50"
      >
        {mutacion.isPending ? 'Guardando...' : 'Guardar gestión'}
      </button>
    </div>
  )
}

// ── Panel de autorizaciones ────────────────────────────────────────
function PanelAutorizaciones({ pqrsId, pqrsEstado, user, tipos, autorizaciones, hayPendiente, invalidar }) {
  const [tipoId, setTipoId]         = useState('')
  const [comentario, setComentario] = useState('')
  const [adjunto, setAdjunto]       = useState(null)
  const [respuesta, setRespuesta]   = useState({ id: null, comentario: '', adjunto: null })
  const [error, setError]           = useState('')
  const archivoRef = useRef(null)

  const mutSolicitar = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.append('tipo_id', tipoId)
      if (comentario.trim()) datos.append('comentario_solicitud', comentario.trim())
      if (adjunto) datos.append('adjunto', adjunto)
      return api.post(`/autorizaciones/pqrs/${pqrsId}/solicitar`, datos)
    },
    onSuccess: () => {
      invalidar()
      setTipoId(''); setComentario(''); setAdjunto(null); setError('')
      if (archivoRef.current) archivoRef.current.value = ''
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo solicitar la autorización.')),
  })

  const mutResponder = useMutation({
    mutationFn: ({ autId, decision, comentario, adjunto }) => {
      const datos = new FormData()
      datos.append('decision', decision)
      if (comentario?.trim()) datos.append('comentario_respuesta', comentario.trim())
      if (adjunto) datos.append('adjunto', adjunto)
      return api.post(`/autorizaciones/pqrs/${pqrsId}/${autId}/responder`, datos)
    },
    onSuccess: () => {
      invalidar()
      setRespuesta({ id: null, comentario: '', adjunto: null })
      setError('')
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo registrar la decisión.')),
  })

  // Quién firma lo decide el servidor por ÁREA y llega en `puede_responder`.
  // Esto miraba el ROL y le escondía los botones a los agentes del área
  // autorizadora, que son quienes hacen ese trabajo.
  const puedeSolicitar = ['admin', 'lider', 'agente'].includes(user?.rol)

  // Para avisar a dónde se va a mover la PQRS antes de que la persona pulse:
  // que el caso cambie de área es una consecuencia y no una sorpresa.
  const tipoSeleccionado = tipos.find(t => String(t.id) === String(tipoId))

  return (
    <div className="bg-white rounded-xl border border-borde p-5">
      <h3 className="font-semibold text-acento-fuerte mb-4 text-sm flex items-center gap-2">
        Autorizaciones
        {hayPendiente && (
          <span className="bg-alerta-bg text-alerta text-xs font-bold px-2 py-0.5 rounded-full">
            Pendiente — PQRS bloqueada
          </span>
        )}
      </h3>

      {/* Lista de autorizaciones existentes */}
      {autorizaciones.length > 0 && (
        <div className="space-y-3 mb-4">
          {autorizaciones.map((aut) => (
            <div key={aut.id} className={`rounded-xl p-4 border ${
              aut.estado === 'pendiente'  ? 'bg-alerta-bg border-ambar/30' :
              aut.estado === 'aprobada'   ? 'bg-positivo-bg border-positivo/25'  :
                                            'bg-negativo-bg border-negativo/25'
            }`}>
              <div className="flex items-start justify-between gap-2 mb-2">
                <div>
                  <div className="text-sm font-bold text-texto">{aut.tipo.nombre}</div>
                  <div className="text-xs text-texto-2">Área: {aut.tipo.area_autorizadora}</div>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full flex-shrink-0 ${
                  aut.estado === 'pendiente'  ? 'bg-alerta-bg text-alerta' :
                  aut.estado === 'aprobada'   ? 'bg-positivo-bg text-positivo'  :
                                                'bg-negativo-bg text-negativo'
                }`}>
                  {aut.estado === 'pendiente' ? 'Pendiente' :
                   aut.estado === 'aprobada' ? 'Aprobada' : 'Rechazada'}
                </span>
              </div>

              {aut.comentario_solicitud && (
                <p className="text-xs text-texto-2 mb-2">
                  Solicitud{aut.solicitante_nombre ? ` de ${aut.solicitante_nombre}` : ''}: {aut.comentario_solicitud}
                </p>
              )}

              {aut.adjunto_solicitud && (
                <a
                  href={aut.adjunto_solicitud} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-acento font-medium hover:underline mb-2"
                >
                  <IconoClip tam={14} /> Soporte de la solicitud
                </a>
              )}

              {aut.comentario_respuesta && (
                <p className="text-xs text-texto-2">
                  Respuesta{aut.autorizador_nombre ? ` de ${aut.autorizador_nombre}` : ''}: {aut.comentario_respuesta}
                </p>
              )}

              {aut.adjunto_respuesta && (
                <a
                  href={aut.adjunto_respuesta} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-1.5 text-xs text-acento font-medium hover:underline mt-1"
                >
                  <IconoClip tam={14} /> Soporte de la respuesta
                </a>
              )}

              {/* Firma quien pertenece al área autorizadora, sea líder o
                  agente. El servidor ya lo resolvió en `puede_responder`. */}
              {aut.puede_responder && (
                <div className="mt-3 space-y-2">
                  <textarea
                    value={respuesta.id === aut.id ? respuesta.comentario : ''}
                    onChange={(e) => setRespuesta({
                      id: aut.id,
                      comentario: e.target.value,
                      adjunto: respuesta.id === aut.id ? respuesta.adjunto : null,
                    })}
                    placeholder="Comentario de la decisión (opcional)..."
                    rows={2}
                    className="w-full px-3 py-2 rounded-lg border border-borde text-xs text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none"
                  />
                  <input
                    type="file"
                    accept=".jpg,.jpeg,.png,.webp,.pdf"
                    aria-label="Soporte de la decisión (opcional)"
                    onChange={(e) => setRespuesta({
                      id: aut.id,
                      comentario: respuesta.id === aut.id ? respuesta.comentario : '',
                      adjunto: e.target.files?.[0] || null,
                    })}
                    className="w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde"
                  />
                  <div className="flex gap-2">
                    <button
                      onClick={() => mutResponder.mutate({
                        autId: aut.id,
                        decision: 'aprobada',
                        comentario: respuesta.id === aut.id ? respuesta.comentario : '',
                        adjunto: respuesta.id === aut.id ? respuesta.adjunto : null,
                      })}
                      disabled={mutResponder.isPending}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 bg-positivo-vivo hover:bg-positivo-vivo text-white font-bold py-2 rounded-lg text-xs transition disabled:opacity-50"
                    >
                      <IconoAlDia tam={15} /> Aprobar
                    </button>
                    <button
                      onClick={() => mutResponder.mutate({
                        autId: aut.id,
                        decision: 'rechazada',
                        comentario: respuesta.id === aut.id ? respuesta.comentario : '',
                        adjunto: respuesta.id === aut.id ? respuesta.adjunto : null,
                      })}
                      disabled={mutResponder.isPending}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 bg-negativo-vivo hover:bg-negativo-vivo text-white font-bold py-2 rounded-lg text-xs transition disabled:opacity-50"
                    >
                      <IconoRechazo tam={15} /> Rechazar
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Solicitar nueva autorización */}
      {puedeSolicitar && pqrsEstado !== 'cerrado' && !hayPendiente && (
        <div className="border-t border-borde pt-4">
          <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-3">
            Solicitar autorización
          </p>
          <select
            value={tipoId}
            onChange={(e) => setTipoId(e.target.value)}
            className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento mb-3"
          >
            <option value="">Seleccionar tipo...</option>
            {tipos.map(t => (
              <option key={t.id} value={t.id}>
                {t.nombre} — {t.area_autorizadora}
              </option>
            ))}
          </select>
          <textarea
            value={comentario}
            onChange={(e) => setComentario(e.target.value)}
            placeholder="Motivo de la solicitud (opcional)..."
            rows={2}
            className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none mb-3"
          />
          <label htmlFor="autorizacion-adjunto" className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
            Soporte (opcional)
          </label>
          <input
            id="autorizacion-adjunto"
            ref={archivoRef}
            type="file"
            accept=".jpg,.jpeg,.png,.webp,.pdf"
            onChange={(e) => setAdjunto(e.target.files?.[0] || null)}
            className="w-full text-xs text-texto-2 mb-3 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde"
          />
          {adjunto && (
            <p className="text-xs text-texto-2 mb-3 -mt-2">{adjunto.name}</p>
          )}
          {/* El área se mueve sola: el caso viaja con la pregunta, así le
              aparece en la bandeja a quien puede firmarla. */}
          {tipoSeleccionado && (
            <p className="text-xs text-texto-2 bg-superficie-2 rounded-lg px-3 py-2 mb-3">
              La solicitud pasa a <strong>{tipoSeleccionado.area_autorizadora}</strong>,
              que es quien la responde. Al responderla vuelve a Servicio al Cliente.
            </p>
          )}
          <button
            onClick={() => mutSolicitar.mutate()}
            disabled={!tipoId || mutSolicitar.isPending}
            className="w-full bg-acento-fuerte hover:bg-acento text-white font-bold py-2.5 rounded-lg text-sm transition disabled:opacity-50"
          >
            {mutSolicitar.isPending ? 'Solicitando…' : 'Solicitar autorización'}
          </button>
        </div>
      )}

      {error && <p role="alert" className="text-sm text-negativo mt-3">{error}</p>}

      {tipos.length === 0 && (
        <p className="text-xs text-texto-3 text-center py-2">
          No hay tipos de autorización configurados. Ve a Administración para crearlos.
        </p>
      )}
    </div>
  )
}

// ── Encuesta (solo lectura para el agente) ──────────────────────────
// El agente no debe poder auto-registrar la satisfacción del cliente.
// Esto solo debe verse si el cliente ya la respondió (vía el link de
// encuesta que le llega por correo al cerrarse la PQRS).
// Colapsada por defecto para no saturar el detalle: muestra un resumen
// de una línea y se expande con clic para ver las 6 respuestas completas.
const SOLUCIONADA_LABEL = { si: 'Sí', parcial: 'Parcialmente', no: 'No' }
const TIEMPO_LABEL = { excelente: 'Excelente', bueno: 'Bueno', regular: 'Regular', malo: 'Malo' }
const TIPO_ENCUESTA_LABEL = {
  peticion: 'Petición', queja: 'Queja', reclamo: 'Reclamo',
  sugerencia: 'Sugerencia', felicitacion: 'Felicitación',
}

function EncuestaSection({ encuesta }) {
  const [abierta, setAbierta] = useState(false)

  if (!encuesta?.respondida_en) {
    // La PQRS está cerrada pero el cliente aún no ha respondido —
    // igual vale la pena que el agente lo sepa de un vistazo.
    if (encuesta) {
      return (
        <div className="bg-fondo rounded-xl p-5">
          <h3 className="font-semibold text-acento-fuerte mb-1 text-sm">Encuesta de satisfacción</h3>
          <p className="text-xs text-texto-2">Enviada al cliente, esperando respuesta.</p>
        </div>
      )
    }
    return null
  }

  return (
    <div className="bg-fondo rounded-xl overflow-hidden">
      <button
        onClick={() => setAbierta(!abierta)}
        className="w-full flex items-center justify-between p-5 text-left"
      >
        <div>
          <h3 className="font-semibold text-acento-fuerte text-sm mb-1">Encuesta de satisfacción</h3>
          <div className="flex items-center gap-1">
            {[1,2,3,4,5].map(n => (
              <IconoEstrella
                key={n}
                tam={17}
                relleno={n <= encuesta.calificacion}
                className={n <= encuesta.calificacion ? 'text-ambar' : 'text-borde-fuerte'}
              />
            ))}
            <span className="text-xs text-texto-2 ml-1">
              {encuesta.calificacion}/5 · respondida el {formatFecha(encuesta.respondida_en)}
            </span>
          </div>
        </div>
        <span className={`text-texto-2 transition-transform ${abierta ? 'rotate-180' : ''}`}>▾</span>
      </button>

      {abierta && (
        <div className="px-5 pb-5 space-y-3 border-t border-borde pt-4">
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-texto-2 font-semibold uppercase tracking-wide block mb-0.5">Tipo de solicitud</span>
              <span className="text-texto font-medium">{TIPO_ENCUESTA_LABEL[encuesta.tipo_solicitud] || encuesta.tipo_solicitud}</span>
            </div>
            <div>
              <span className="text-texto-2 font-semibold uppercase tracking-wide block mb-0.5">¿Solucionada?</span>
              <span className="text-texto font-medium">{SOLUCIONADA_LABEL[encuesta.solucionada] || '—'}</span>
            </div>
            <div>
              <span className="text-texto-2 font-semibold uppercase tracking-wide block mb-0.5">Tiempo de respuesta</span>
              <span className="text-texto font-medium">{TIEMPO_LABEL[encuesta.calificacion_tiempo_respuesta] || '—'}</span>
            </div>
            <div>
              <span className="text-texto-2 font-semibold uppercase tracking-wide block mb-0.5">¿Recomendaría?</span>
              <span className="text-texto font-medium">{encuesta.recomendaria ? 'Sí' : 'No'}</span>
            </div>
          </div>
          {encuesta.comentario && (
            <div>
              <span className="text-texto-2 font-semibold uppercase tracking-wide block mb-1 text-xs">Comentario</span>
              <p className="text-sm text-texto italic">"{encuesta.comentario}"</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Pantalla principal ─────────────────────────────────────────────
export default function PQRSDetail() {
  const { id }      = useParams()
  const navigate    = useNavigate()
  const queryClient = useQueryClient()
  const { user }    = useAuth()

  const { data: pqrs, isLoading, isError } = useQuery({
    queryKey: ['pqrs', id],
    queryFn: async () => { const { data } = await api.get(`/pqrs/${id}`); return data },
  })

  const { data: tipos = [] } = useQuery({
    queryKey: ['tipos-autorizacion'],
    queryFn: async () => { const { data } = await api.get('/autorizaciones/tipos'); return data },
  })

  const { data: autorizaciones = [] } = useQuery({
    queryKey: ['autorizaciones', id],
    queryFn: async () => { const { data } = await api.get(`/autorizaciones/pqrs/${id}`); return data },
  })

  const hayPendiente = autorizaciones.some(a => a.estado === 'pendiente')

  // Única fuente de invalidación: la usan tanto el panel de autorizaciones
  // como el resto de la pantalla, así todo se refresca al instante.
  const invalidarAutorizaciones = () => {
    queryClient.invalidateQueries({ queryKey: ['autorizaciones', id] })
    queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
    queryClient.invalidateQueries({ queryKey: ['pqrs'] })
  }

  const mutAreaCausante = useMutation({
    mutationFn: (area_causante) => api.patch(`/pqrs/${id}/area-causante`, { area_causante }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', id] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
    },
  })

  if (isLoading) return (
    <div className="flex items-center justify-center py-20 text-texto-2 text-sm">Cargando...</div>
  )
  if (isError || !pqrs) return (
    <div className="flex flex-col items-center justify-center py-20 text-texto-2">
      <IconoBuscar tam={26} className="mb-3 text-texto-3" />
      <span className="text-sm">No se encontró esta PQRS. Puede que la hayan borrado o que el enlace esté mal.</span>
      <button onClick={() => navigate('/pqrs')} className="mt-4 text-acento text-sm font-medium hover:underline">Volver al listado</button>
    </div>
  )

  // Qué puede hacer esta persona lo decide el servidor y llega en `alcance`.
  // Mientras carga el detalle no hay alcance, así que no se ofrece nada:
  // mejor un botón que aparece un instante después que uno que se ofrece y
  // luego resulta rechazado.
  const alcance = pqrs.alcance
  const puedeEditar = Boolean(alcance?.puede_gestionar)
  // Cerrar y reclasificar son de Servicio al cliente: el tipo que elige el
  // cliente al radicar suele estar mal, y esa clasificación alimenta los
  // indicadores. Admin siempre puede, para destrabar.
  const esServicioCliente = Boolean(alcance?.puede_reclasificar)

  return (
    <div className="max-w-5xl mx-auto">
      <button onClick={() => navigate('/pqrs')} className="flex items-center gap-2 text-sm text-texto-2 hover:text-acento-fuerte mb-5 transition">
        ← Volver a PQRS
      </button>

      {/* Header */}
      <div className="bg-gradient-to-r from-acento-fuerte to-acento rounded-2xl p-6 mb-5 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="text-white/60 text-xs font-semibold uppercase tracking-wide mb-1">
              {pqrs.codigo_seguimiento || `PQRS #${pqrs.id}`}
              {pqrs.radicado_calidad && ` · Calidad: ${pqrs.radicado_calidad}`}
            </div>
            <h1 className="text-xl font-bold mb-1">{pqrs.empresa || pqrs.cliente_nombre}</h1>
            {pqrs.empresa && (
              <p className="text-white/70 text-sm mb-2">{pqrs.cliente_nombre}</p>
            )}
            <div className="flex gap-2 flex-wrap">
              <Badge map={TIPOS} value={pqrs.tipo} />
              <Badge map={ESTADOS} value={pqrs.estado} />
              <span className={`text-xs font-semibold ${PRIORIDADES[pqrs.prioridad]?.color}`}>
                ● {PRIORIDADES[pqrs.prioridad]?.label}
              </span>
              {hayPendiente && (
                <span className="bg-ambar/30 text-ambar text-xs font-bold px-2 py-0.5 rounded-full">
                  Autorización pendiente
                </span>
              )}
              <span className="bg-white/10 text-white/70 text-xs px-2 py-0.5 rounded-full">
                {pqrs.origen_publico === 'publico' ? 'Formulario web' : 'Interno'}
              </span>
            </div>

            {/* En qué área está el caso ahora mismo. Va en la cabecera y no
                dentro del control de reasignar, que es donde estaba: quien no
                puede mover el área tampoco veía cuál era, y esa es la primera
                pregunta de cualquiera que abre una PQRS ajena. */}
            <div className="flex items-center gap-1.5 text-sm text-white/80 mt-3">
              <IconoEmpresa tam={15} />
              <span>
                Área responsable:{' '}
                <strong className="text-white">
                  {pqrs.area_responsable || 'Sin asignar'}
                </strong>
              </span>
            </div>
          </div>
          <div className="text-right text-sm text-white/70 flex-shrink-0">
            <div>{formatFecha(pqrs.fecha_creacion)}</div>
            <div className="mt-1">
              <SLALabel fechaLimite={pqrs.fecha_limite_sla} cerrado={pqrs.estado === 'cerrado'} />
            </div>
            {/* Área causante — distinta del área que gestiona el caso.
                Solo de uso interno, para poder sacar reportes de "qué área
                fue la responsable del problema" más adelante en Indicadores. */}
            {puedeEditar ? (
              <select
                value={pqrs.area_causante || ''}
                onChange={(e) => mutAreaCausante.mutate(e.target.value)}
                className="mt-2 bg-white/10 hover:bg-white/20 text-white text-xs rounded-lg px-2 py-1 border border-white/20 focus:outline-none cursor-pointer transition"
                title="Área causante del problema (uso interno)"
              >
                <option value="" className="text-texto">Área causante: sin definir</option>
                {AREAS.map(a => <option key={a} value={a} className="text-texto">Causante: {a}</option>)}
              </select>
            ) : (
              pqrs.area_causante && (
                <div className="mt-2 text-xs text-white/60">Causante: {pqrs.area_causante}</div>
              )
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-5">

        {/* Columna izquierda */}
        <div className="col-span-1 space-y-5">

          {/* Datos del cliente */}
          <div className="bg-white rounded-xl border border-borde p-5">
            <h3 className="font-semibold text-acento-fuerte mb-4 text-sm">Datos del cliente</h3>
            <div className="space-y-3">
              {[
                { label: 'Empresa',        value: pqrs.empresa          },
                { label: 'NIT / Cédula',   value: pqrs.nit_cedula       },
                { label: 'Contacto',       value: pqrs.cliente_nombre   },
                { label: 'Teléfono',       value: pqrs.cliente_telefono },
                { label: 'Email',          value: pqrs.cliente_email    },
                { label: 'Ciudad',         value: pqrs.ciudad           },
                { label: 'Departamento',   value: pqrs.departamento     },
              ].map(({ label, value }) => value && (
                <div key={label}>
                  <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">{label}</div>
                  <div className="text-sm text-texto font-medium mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Datos del producto */}
          <div className="bg-white rounded-xl border border-borde p-5">
            <h3 className="font-semibold text-acento-fuerte mb-4 text-sm">Producto y factura</h3>

            {/* El cliente no encontró su producto y lo escribió. Se corrige
                aquí porque después de cerrar ya no se puede, y un nombre
                suelto vuelve inservible el informe por producto. */}
            {pqrs.producto_por_confirmar && (
              <ConfirmarProducto
                pqrs={pqrs} puedeConfirmar={esServicioCliente && pqrs.estado !== 'cerrado'}
                onConfirmado={() => queryClient.invalidateQueries({ queryKey: ['pqrs', id] })}
              />
            )}

            <div className="space-y-3">
              {[
                { label: 'Producto',         value: pqrs.producto_nombre  },
                { label: 'Código',           value: pqrs.producto_codigo  },
                { label: 'Presentación',     value: pqrs.presentacion
                                                ? `${pqrs.presentacion}${pqrs.cantidad_presentacion ? ' - ' + pqrs.cantidad_presentacion : ''}`
                                                : null },
                { label: 'Canal de atención', value: pqrs.canal_atencion  },
                { label: 'Lote',             value: pqrs.lote             },
                { label: 'Factura',          value: pqrs.factura_numero   },
                { label: 'Cant. factura',    value: pqrs.cantidad_factura },
                { label: 'Cant. reclamo',    value: pqrs.cantidad_reclamo },
              ].map(({ label, value }) => value && (
                <div key={label}>
                  <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide">{label}</div>
                  <div className="text-sm text-texto font-medium mt-0.5">{value}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Adjuntos */}
          {(pqrs.adjunto_producto || pqrs.adjunto_factura || pqrs.adjunto_video) && (
            <div className="bg-white rounded-xl border border-borde p-5">
              <h3 className="font-semibold text-acento-fuerte mb-4 text-sm">Evidencias adjuntas</h3>
              <div className="space-y-3">
                {pqrs.adjunto_producto && (
                  <div>
                    <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide mb-2">
                      Foto del producto
                    </div>
                    <a href={`${pqrs.adjunto_producto}`} target="_blank" rel="noreferrer">
                      <img
                        src={`${pqrs.adjunto_producto}`}
                        alt="Producto"
                        className="w-full rounded-lg border border-borde object-cover max-h-40 hover:opacity-90 transition cursor-pointer"
                        onError={(e) => { e.target.style.display='none' }}
                      />
                    </a>
                  </div>
                )}
                {pqrs.adjunto_factura && (
                  <div>
                    <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide mb-2">
                      Factura
                    </div>
                    
                      <a
                      href={`${pqrs.adjunto_factura}`}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-2 p-3 bg-fondo rounded-lg hover:bg-borde transition"
                    >
                      <IconoRecibo tam={20} className="text-texto-2" />
                      <span className="text-sm font-medium text-acento underline">Ver factura adjunta</span>
                    </a>
                  </div>
                )}
                {pqrs.adjunto_video && (
                  <div>
                    <div className="text-xs text-texto-2 font-semibold uppercase tracking-wide mb-2">
                      Video de evidencia
                    </div>
                    <video
                      src={`${pqrs.adjunto_video}`}
                      controls
                      className="w-full rounded-lg border border-borde max-h-52"
                    />
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Reclasificar el tipo — solo Servicio al cliente y antes de cerrar */}
          {esServicioCliente && pqrs.estado !== 'cerrado' && (
            <ReclasificarTipo pqrs={pqrs} />
          )}

          {/* Encuesta si está cerrada y el cliente ya respondió */}
          {pqrs.estado === 'cerrado' && (
            <EncuestaSection encuesta={pqrs.encuesta} />
          )}
        </div>

        {/* Columna derecha */}
        <div className="col-span-2 space-y-5">

          {/* Descripción: primero se lee de qué se trata el caso y después se
              actúa sobre él. Al revés, la pantalla pedía decidir el estado
              antes de haber leído lo que el cliente escribió. */}
          <div className="bg-white rounded-xl border border-borde p-5">
            <h3 className="font-semibold text-acento-fuerte mb-3 text-sm">Descripción del caso</h3>
            <p className="text-sm text-texto leading-relaxed whitespace-pre-wrap">{pqrs.descripcion}</p>
          </div>

          {/* Gestionar: área, estado, comentario y evidencia en un solo guardado. */}
          {puedeEditar && pqrs.estado !== 'cerrado' && (
            <PanelGestion
              pqrs={pqrs}
              alcance={alcance}
              hayPendiente={hayPendiente}
              invalidar={invalidarAutorizaciones}
            />
          )}

          {/* Autorizaciones */}
          <PanelAutorizaciones
            pqrsId={pqrs.id}
            pqrsEstado={pqrs.estado}
            user={user}
            tipos={tipos}
            autorizaciones={autorizaciones}
            hayPendiente={hayPendiente}
            invalidar={invalidarAutorizaciones}
          />

          {/* Historial */}
          <div className="bg-white rounded-xl border border-borde p-5">
            <h3 className="font-semibold text-acento-fuerte mb-4 text-sm">
              Historial interno
              <span className="ml-2 bg-fondo text-texto-2 text-xs font-semibold px-2 py-0.5 rounded-full">
                {pqrs.seguimientos?.length || 0} eventos
              </span>
            </h3>

            {pqrs.seguimientos?.length === 0 ? (
              <p className="text-sm text-texto-2 text-center py-4">Sin eventos registrados.</p>
            ) : (
              <div className="relative">
                <div className="absolute left-4 top-0 bottom-0 w-px bg-borde" />
                <div className="space-y-4">
                  {[...pqrs.seguimientos].reverse().map((seg) => {
                    const evento = EVENTOS[seg.tipo_evento] || { Icono: IconoEtiqueta, label: seg.tipo_evento }
                    return (
                      <div key={seg.id} className="flex gap-4 relative">
                        <div className="w-8 h-8 rounded-full bg-superficie border-2 border-borde
                          text-texto-2 flex items-center justify-center flex-shrink-0 z-10">
                          <evento.Icono tam={15} />
                        </div>
                        <div className="flex-1 bg-superficie-2 rounded-lg p-3 min-w-0">
                          <div className="flex items-center justify-between gap-2 mb-1">
                            <span className="text-xs font-semibold text-acento-fuerte">{evento.label}</span>
                            <span className="text-xs text-texto-3 flex-shrink-0">{formatFecha(seg.fecha)}</span>
                          </div>
                          <div className="text-xs text-texto-2 mb-1">
                            {seg.usuario_nombre
                              ? `${seg.usuario_nombre}${seg.usuario_area ? ` · ${seg.usuario_area}` : ''}`
                              : 'Cliente (formulario público)'}
                          </div>
                          {seg.comentario && (
                            <p className="text-sm text-texto">{seg.comentario}</p>
                          )}
                          {seg.adjunto_evidencia && (
                            /\.(jpg|jpeg|png|webp)$/i.test(seg.adjunto_evidencia) ? (
                              <a href={seg.adjunto_evidencia} target="_blank" rel="noreferrer" className="inline-block mt-2">
                                <img
                                  src={seg.adjunto_evidencia}
                                  alt="Evidencia"
                                  className="max-h-32 rounded-lg border border-borde hover:opacity-90 transition cursor-pointer"
                                  onError={(e) => { e.target.style.display='none' }}
                                />
                              </a>
                            ) : (
                              <a
                                href={seg.adjunto_evidencia}
                                target="_blank"
                                rel="noreferrer"
                                className="inline-block mt-2 text-xs text-acento font-semibold underline"
                              >
                                <IconoClip tam={13} /> Ver evidencia adjunta
                              </a>
                            )
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Corrige el tipo de una PQRS antes de cerrarla.
 *
 * El cliente casi nunca acierta al radicar: pone "petición" lo que en
 * realidad es un reclamo. Y esa clasificación es la que alimenta los
 * indicadores y los reportes de Calidad, así que Servicio al cliente la
 * ajusta como paso previo al cierre.
 *
 * El motivo es obligatorio y queda en la trazabilidad de la PQRS.
 */
function ReclasificarTipo({ pqrs }) {
  const queryClient = useQueryClient()
  const [abierto, setAbierto] = useState(false)
  const [tipo, setTipo] = useState(pqrs.tipo)
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')

  const mut = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append('tipo', tipo)
      fd.append('motivo', motivo)
      return api.patch(`/pqrs/${pqrs.id}/tipo`, fd)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pqrs', String(pqrs.id)] })
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
      setAbierto(false); setMotivo(''); setError('')
    },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo reclasificar.')),
  })

  const cambio = tipo !== pqrs.tipo
  // El SLA y la prioridad se recalculan solos en el servidor; se avisa aquí
  // para que nadie se sorprenda al ver la fecha límite moverse.
  const avisoSLA = cambio
    ? 'Se recalculará la fecha límite con el plazo del tipo nuevo, contando desde que se radicó. Puede quedar vencida.'
    : null

  if (!abierto) {
    return (
      <div className="bg-white rounded-xl border border-borde p-5">
        <h3 className="font-semibold text-acento-fuerte mb-1 text-sm">Clasificación</h3>
        <p className="text-xs text-texto-2 mb-3">
          Está registrada como <strong>{TIPOS[pqrs.tipo]?.label || pqrs.tipo}</strong>.
          Si no corresponde, corrígela antes de cerrar.
        </p>
        <button
          onClick={() => setAbierto(true)}
          className="w-full border border-borde hover:bg-superficie-2 text-acento-fuerte font-semibold py-2.5 rounded-lg text-sm transition"
        >
          Cambiar tipo de solicitud
        </button>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl border border-acento p-5">
      <h3 className="font-semibold text-acento-fuerte mb-3 text-sm">Reclasificar</h3>

      {error && (
        <div className="bg-negativo-bg border border-negativo/25 rounded-lg px-3 py-2 text-sm text-negativo mb-3">
          {error}
        </div>
      )}

      <label className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
        ¿Qué fue en realidad?
      </label>
      <select
        value={tipo}
        onChange={(e) => setTipo(e.target.value)}
        className="w-full px-3 py-2.5 rounded-lg border border-borde text-sm text-texto focus:outline-none focus:ring-2 focus:ring-acento mb-3"
      >
        {Object.entries(TIPOS).map(([key, { label }]) => (
          <option key={key} value={key}>
            {label}{key === pqrs.tipo ? ' — actual' : ''}
          </option>
        ))}
      </select>

      <label className="block text-xs text-texto-2 font-semibold uppercase tracking-wide mb-1">
        ¿Por qué? <span className="text-negativo">·  obligatorio</span>
      </label>
      <textarea
        value={motivo}
        onChange={(e) => setMotivo(e.target.value)}
        placeholder="Ej: el cliente pide devolución de dinero, es un reclamo"
        rows={2}
        className="w-full px-3 py-2 rounded-lg border border-borde text-sm text-texto placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento resize-none mb-2"
      />

      {avisoSLA && (
        <p className="text-xs text-alerta bg-alerta-bg border border-ambar/30 rounded-lg px-3 py-2 mb-3">
          {avisoSLA}
        </p>
      )}
      <p className="text-xs text-texto-3 mb-3">
        Queda registrado en el seguimiento con tu nombre y la fecha.
      </p>

      <div className="flex gap-2">
        <button
          onClick={() => { setAbierto(false); setTipo(pqrs.tipo); setMotivo(''); setError('') }}
          className="flex-1 border border-borde hover:bg-superficie-2 text-acento-fuerte font-semibold py-2.5 rounded-lg text-sm transition"
        >
          Cancelar
        </button>
        <button
          onClick={() => { setError(''); mut.mutate() }}
          disabled={!cambio || !motivo.trim() || mut.isPending}
          className="flex-1 bg-acento-fuerte hover:bg-acento disabled:opacity-40 text-white font-bold py-2.5 rounded-lg text-sm transition"
        >
          {mut.isPending ? 'Guardando...' : 'Reclasificar'}
        </button>
      </div>
    </div>
  )
}
