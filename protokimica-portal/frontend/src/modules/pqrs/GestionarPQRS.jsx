/**
 * «Gestionar»: el único lugar del detalle donde se ACTÚA sobre una PQRS.
 *
 * Antes eran cinco tarjetas apiladas —causa, flujo de conceptos, gestionar,
 * autorizaciones y clasificación— con su propio botón cada una, y para hacer
 * una sola cosa había que encontrar primero cuál de ellas era. Ahora es un
 * panel con cuatro modos (`MODOS_GESTION`), y debajo queda lo que se LEE.
 *
 * - **Avanzar**: estado, área, solución, comentario y evidencia en un solo
 *   guardado. Elegir «Cerrado» con requisitos pendientes lo dice y no deja
 *   guardar; los requisitos llegan del servidor.
 * - **Conceptos**: el flujo automático (`FlujoPQRS`) y, aparte, pedir un
 *   concepto suelto. Las dos cosas responden a lo mismo: quién tiene que
 *   opinar antes de responderle al cliente.
 * - **Clasificar**: el tipo (antes de cerrar) y la causa.
 * - **Comentar**: una nota interna, sin tocar nada más.
 *
 * Qué modos ve cada quien sale de `modosDeGestion()`; qué puede hacer dentro
 * de cada uno, del `alcance` que manda el servidor.
 */
import { useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { useAreas } from '../../core/areas.js'
import { mensajeDeError } from '../../core/errores.js'
import Boton from '../../core/components/Boton.jsx'
import {
  IconoAlerta, IconoCandado, IconoComentario, IconoEtiqueta, IconoFlecha, IconoInfo, IconoReloj,
} from '../../core/components/Iconos.jsx'
import { ESTADOS, MODOS_GESTION, TIPOS, avanceDeCierre, modosDeGestion } from './constants.js'
import CausaPQRS from './CausaPQRS.jsx'
import FlujoPQRS from './FlujoPQRS.jsx'
import { useFlujo } from './useFlujo.js'

const claseCampo = 'w-full px-3 py-2 rounded-lg border border-borde-fuerte text-sm text-texto bg-white placeholder-texto-3 focus:outline-none focus:ring-2 focus:ring-acento'
const claseArchivo = 'w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde'
const ICONOS = { avanzar: IconoFlecha, conceptos: IconoCandado, clasificar: IconoEtiqueta, comentar: IconoComentario }

/** Lo que va a pasar al guardar, dicho antes de guardar. */
function Efecto({ tono = 'info', children }) {
  const estilos = {
    info: 'bg-info-bg text-info',
    alerta: 'bg-alerta-bg text-alerta',
    neutro: 'bg-superficie-2 text-texto-2',
  }
  const Icono = tono === 'alerta' ? IconoAlerta : tono === 'neutro' ? IconoInfo : IconoReloj
  return (
    <div className={`flex items-start gap-2 rounded-lg px-3 py-2.5 text-xs leading-relaxed ${estilos[tono]}`}>
      <Icono tam={14} className="mt-0.5 flex-shrink-0" />
      <span>{children}</span>
    </div>
  )
}

function Campo({ id, etiqueta, opcional, obligatorio, children }) {
  return (
    <div>
      <label htmlFor={id} className="flex items-center gap-1.5 text-xs font-semibold text-texto-2 mb-1.5">
        {etiqueta}
        {obligatorio && <span className="text-negativo">*</span>}
        {opcional && <span className="font-normal text-texto-3">{opcional}</span>}
      </label>
      {children}
    </div>
  )
}

// ── Avanzar ───────────────────────────────────────────────────────

/**
 * El freno antes de cerrar por error. Cerrar no es un cambio de estado
 * cualquiera: dispara la encuesta al cliente EN EL ACTO, y reabrir la PQRS
 * después no deshace el correo.
 */
function ConfirmarCierre({ pqrs, guardando, onConfirmar, onCancelar }) {
  return (
    <div className="fixed inset-0 bg-texto/50 flex items-center justify-center z-[70] p-4" onClick={onCancelar}>
      <div onClick={(e) => e.stopPropagation()} className="bg-white rounded-2xl shadow-lg w-full max-w-md">
        <div className="px-6 py-4 border-b border-borde">
          <h3 className="text-base font-bold text-acento-fuerte">¿Cerrar esta PQRS?</h3>
          {pqrs.codigo_seguimiento && <p className="cifra text-xs text-texto-3 mt-0.5">{pqrs.codigo_seguimiento}</p>}
        </div>
        <div className="px-6 py-5">
          <div className="rounded-xl border border-borde bg-superficie-2 p-3">
            <p className="text-sm text-texto">Se le manda la encuesta de satisfacción al cliente de inmediato.</p>
            <p className="text-sm text-texto-2 mt-1">
              Si la cierras por error, puedes volver a abrirla desde aquí — pero el correo ya se habrá enviado.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 bg-superficie-2 border-t border-borde">
          <Boton onClick={onCancelar}>Cancelar</Boton>
          <Boton tono="primario" autoFocus cargando={guardando} textoCargando="Cerrando…" onClick={onConfirmar}>
            Sí, cerrar
          </Boton>
        </div>
      </div>
    </div>
  )
}

function ModoAvanzar({ pqrs, alcance, hayPendiente, invalidar }) {
  const listaAreas = useAreas()
  const [area, setArea] = useState('')
  const [estado, setEstado] = useState('')
  const [comentario, setComentario] = useState('')
  const [evidencia, setEvidencia] = useState(null)
  const [solucion, setSolucion] = useState('')
  const [adjuntosSolucion, setAdjuntosSolucion] = useState([])
  const [error, setError] = useState('')
  const [confirmandoCierre, setConfirmandoCierre] = useState(false)
  const archivoRef = useRef(null)
  const archivosSolucionRef = useRef(null)

  const esResuelto = estado === 'resuelto'
  const { faltan } = avanceDeCierre(pqrs.requisitos_cierre)
  const cierreBloqueado = estado === 'cerrado' && faltan.length > 0

  const mutacion = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      // Solo viaja lo que cambió: un campo vacío no es «ponlo en vacío»,
      // es «no lo toques».
      if (area) datos.append('area', area)
      if (estado) datos.append('estado', estado)
      if (comentario.trim()) datos.append('comentario', comentario.trim())
      if (evidencia) datos.append('evidencia', evidencia)
      if (esResuelto) {
        datos.append('solucion', solucion.trim())
        adjuntosSolucion.forEach((archivo) => datos.append('adjuntos_solucion', archivo))
      }
      return api.patch(`/pqrs/${pqrs.id}/gestion`, datos)
    },
    onSuccess: () => {
      invalidar()
      setArea(''); setEstado(''); setComentario(''); setEvidencia(null)
      setSolucion(''); setAdjuntosSolucion([]); setError('')
      if (archivoRef.current) archivoRef.current.value = ''
      if (archivosSolucionRef.current) archivosSolucionRef.current.value = ''
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar la gestión.')),
  })

  const hayAlgo = Boolean(area || estado || comentario.trim() || evidencia)
  const listo = hayAlgo && (!esResuelto || solucion.trim() !== '') && !cierreBloqueado

  return (
    <div className="space-y-3">
      {hayPendiente && (
        <Efecto tono="alerta">
          Hay un concepto esperando respuesta: el estado queda congelado hasta que lo respondan.
          Sí puedes comentar o adjuntar un soporte.
        </Efecto>
      )}

      <div className="grid sm:grid-cols-2 gap-3">
        <Campo id="gestion-estado" etiqueta="Estado" opcional={`hoy: ${ESTADOS[pqrs.estado]?.label}`}>
          <select id="gestion-estado" value={estado} onChange={(e) => setEstado(e.target.value)} disabled={hayPendiente}
                  className={`${claseCampo} disabled:bg-superficie-2 disabled:text-texto-3`}>
            <option value="">Sin cambio</option>
            {Object.entries(ESTADOS)
              .filter(([clave]) => clave !== pqrs.estado)
              // «Cerrado» solo para quien puede cerrar: mejor no ofrecerlo
              // que dar un 403 al guardar.
              .filter(([clave]) => clave !== 'cerrado' || alcance?.puede_cerrar)
              .map(([clave, { label }]) => <option key={clave} value={clave}>{label}</option>)}
          </select>
        </Campo>
        {alcance?.puede_cambiar_area ? (
          <Campo id="gestion-area" etiqueta="Área responsable" opcional={`hoy: ${pqrs.area_responsable || 'sin asignar'}`}>
            <select id="gestion-area" value={area} onChange={(e) => setArea(e.target.value)} className={claseCampo}>
              <option value="">Sin cambio</option>
              {listaAreas.filter(a => a !== pqrs.area_responsable).map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </Campo>
        ) : (
          <p className="text-xs text-texto-2 bg-superficie-2 rounded-lg px-3 py-2 self-end">
            El área la reparte Servicio al Cliente. Si este caso no es de tu área, escríbelo y ellos lo mueven.
          </p>
        )}
      </div>

      {/* La solución solo aparece al elegir «Resuelto»: es lo que se le manda
          al cliente pidiéndole que confirme, y el servidor la exige. */}
      {esResuelto && (
        <div className="bg-superficie-2 rounded-lg p-3 space-y-2">
          <Campo id="gestion-solucion" etiqueta="Solución para el cliente" obligatorio>
            <textarea id="gestion-solucion" value={solucion} onChange={(e) => setSolucion(e.target.value)} rows={3}
                      placeholder="Qué se hizo para solucionar el caso…" className={`${claseCampo} resize-y`} />
          </Campo>
          <Campo id="gestion-adjuntos-solucion" etiqueta="Soporte para el cliente" opcional="opcional, varios archivos">
            <input id="gestion-adjuntos-solucion" ref={archivosSolucionRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf" multiple
                   onChange={(e) => setAdjuntosSolucion(Array.from(e.target.files || []))} className={claseArchivo} />
          </Campo>
        </div>
      )}

      <Campo id="gestion-comentario" etiqueta="Qué pasó, qué hiciste, qué falta" opcional="queda en el historial interno">
        <textarea id="gestion-comentario" value={comentario} onChange={(e) => setComentario(e.target.value)} rows={3}
                  placeholder="Queda en el expediente del caso…" className={`${claseCampo} resize-y`} />
      </Campo>
      <Campo id="gestion-evidencia" etiqueta="Evidencia" opcional="opcional">
        <input id="gestion-evidencia" ref={archivoRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
               onChange={(e) => setEvidencia(e.target.files?.[0] || null)} className={claseArchivo} />
      </Campo>

      {/* Lo que va a pasar, antes de pulsar. */}
      {esResuelto && (
        <Efecto>
          Pasar a <strong>Resuelto</strong> detiene el plazo y le envía la solución al cliente pidiéndole que
          confirme. Si no responde en 3 días hábiles, se cierra sola.
        </Efecto>
      )}
      {cierreBloqueado && (
        <Efecto tono="alerta">
          Todavía no se puede cerrar. Falta: {faltan.map(r => r.etiqueta.toLowerCase()).join(', ')}.
          Está arriba, en «Para cerrar».
        </Efecto>
      )}
      {estado === 'cerrado' && !cierreBloqueado && (
        <Efecto tono="neutro">Al cerrar se le manda la encuesta de satisfacción al cliente de inmediato.</Efecto>
      )}
      {area && (
        <Efecto tono="neutro">
          El caso pasa a <strong>{area}</strong>, que tiene 3 días hábiles para moverlo. Su reloj empieza en cero.
        </Efecto>
      )}
      {!alcance?.puede_cerrar && (
        <p className="text-xs text-texto-3">
          Márcala como <strong>Resuelto</strong> cuando termines: el cierre lo hace Servicio al Cliente, que revisa y clasifica.
        </p>
      )}

      {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
      <div className="flex justify-end">
        <Boton tono="primario" disabled={!listo} cargando={mutacion.isPending} textoCargando="Guardando…"
               onClick={() => (estado === 'cerrado' ? setConfirmandoCierre(true) : mutacion.mutate())}>
          Guardar gestión
        </Boton>
      </div>

      {confirmandoCierre && (
        <ConfirmarCierre pqrs={pqrs} guardando={mutacion.isPending}
                         onConfirmar={() => { setConfirmandoCierre(false); mutacion.mutate() }}
                         onCancelar={() => setConfirmandoCierre(false)} />
      )}
    </div>
  )
}

// ── Conceptos ─────────────────────────────────────────────────────

/** Pedir UN concepto, por fuera de la plantilla. */
function ConceptoSuelto({ pqrsId, tipos, invalidar }) {
  const [tipoId, setTipoId] = useState('')
  const [comentario, setComentario] = useState('')
  const [adjunto, setAdjunto] = useState(null)
  const [error, setError] = useState('')
  const archivoRef = useRef(null)

  const mut = useMutation({
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
    onError: (err) => setError(mensajeDeError(err, 'No se pudo pedir el concepto.')),
  })

  if (!tipos.length) {
    return <p className="text-xs text-texto-2">No hay tipos de autorización configurados. Un administrador los crea en Administración.</p>
  }
  const elegido = tipos.find(t => String(t.id) === String(tipoId))

  return (
    <div className="space-y-3">
      <Campo id="concepto-tipo" etiqueta="Qué concepto" obligatorio>
        <select id="concepto-tipo" value={tipoId} onChange={(e) => setTipoId(e.target.value)} className={claseCampo}>
          <option value="">Elige el concepto…</option>
          {tipos.map(t => <option key={t.id} value={t.id}>{t.nombre} — {t.area_autorizadora}</option>)}
        </select>
      </Campo>
      <Campo id="concepto-comentario" etiqueta="Qué necesitas que respondan" opcional="opcional">
        <textarea id="concepto-comentario" value={comentario} onChange={(e) => setComentario(e.target.value)} rows={2}
                  placeholder="Sé concreto: qué decisión se necesita y por qué…" className={`${claseCampo} resize-y`} />
      </Campo>
      <Campo id="concepto-adjunto" etiqueta="Soporte para quien responde" opcional="opcional">
        <input id="concepto-adjunto" ref={archivoRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
               onChange={(e) => setAdjunto(e.target.files?.[0] || null)} className={claseArchivo} />
      </Campo>
      {/* El área se mueve sola: el caso viaja con la pregunta. */}
      {elegido && (
        <Efecto>
          La PQRS queda <strong>esperando a {elegido.area_autorizadora}</strong>, que tiene 3 días hábiles para responder.
          El estado se congela mientras tanto, y al responder vuelve a Servicio al Cliente.
        </Efecto>
      )}
      {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
      <div className="flex justify-end">
        <Boton tono="primario" disabled={!tipoId} cargando={mut.isPending} textoCargando="Pidiendo…" onClick={() => mut.mutate()}>
          Pedir concepto
        </Boton>
      </div>
    </div>
  )
}

function ModoConceptos({ pqrs, tipos, puedeSolicitar, hayPendiente, autorizaciones, invalidar }) {
  const { data: flujo } = useFlujo(pqrs.id)
  const [suelto, setSuelto] = useState(false)
  const mueveElFlujo = Boolean(flujo?.puede_gestionar)
  const ofrecerSuelto = puedeSolicitar && !hayPendiente
  const esperando = autorizaciones.find(a => a.estado === 'pendiente')

  return (
    <div className="space-y-4">
      {/* Lo pendiente se responde en la tarjeta «Conceptos», donde lo ve el
          área que firma. Aquí solo se dice que hay que esperar. */}
      {esperando && (
        <Efecto tono="alerta">
          Esperando a <strong>{esperando.tipo.area_autorizadora}</strong> ({esperando.tipo.nombre}). Lo responden en la
          tarjeta «Conceptos», más abajo.
        </Efecto>
      )}

      {mueveElFlujo && <FlujoPQRS pqrs={pqrs} tipos={tipos} />}

      {ofrecerSuelto && (mueveElFlujo ? (
        <div className="border-t border-borde pt-4">
          {suelto ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-2">
                <span className="etiqueta">Un concepto suelto</span>
                <button type="button" onClick={() => setSuelto(false)} className="text-xs font-semibold text-acento hover:underline">
                  Cancelar
                </button>
              </div>
              <ConceptoSuelto pqrsId={pqrs.id} tipos={tipos} invalidar={invalidar} />
            </div>
          ) : (
            <button type="button" onClick={() => setSuelto(true)} className="text-sm font-semibold text-acento hover:underline">
              Pedir un solo concepto, por fuera del flujo
            </button>
          )}
        </div>
      ) : (
        <ConceptoSuelto pqrsId={pqrs.id} tipos={tipos} invalidar={invalidar} />
      ))}

      {!mueveElFlujo && !ofrecerSuelto && !esperando && (
        <p className="text-sm text-texto-2">No hay nada que pedir ahora.</p>
      )}
    </div>
  )
}

// ── Clasificar ────────────────────────────────────────────────────

/**
 * Corrige el tipo antes de cerrar. El cliente casi nunca acierta al radicar,
 * y esa clasificación alimenta los indicadores y decide qué flujo de
 * conceptos se propone. El motivo es obligatorio y queda en el historial.
 */
function Reclasificar({ pqrs }) {
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
      queryClient.invalidateQueries({ queryKey: ['pqrs'] })
      setAbierto(false); setMotivo(''); setError('')
    },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo reclasificar.')),
  })
  const cambio = tipo !== pqrs.tipo

  if (!abierto) {
    return (
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg bg-superficie-2 px-3 py-2.5">
        <p className="text-sm text-texto-2">
          Registrada como <strong className="text-texto">{TIPOS[pqrs.tipo]?.label || pqrs.tipo}</strong>.
          Si no corresponde, corrígela antes de cerrar.
        </p>
        <Boton tam="sm" onClick={() => setAbierto(true)}>Cambiar el tipo</Boton>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-acento p-3 space-y-3">
      <div className="grid sm:grid-cols-2 gap-3">
        <Campo id="reclasificar-tipo" etiqueta="¿Qué fue en realidad?">
          <select id="reclasificar-tipo" value={tipo} onChange={(e) => setTipo(e.target.value)} className={claseCampo}>
            {Object.entries(TIPOS).map(([clave, { label }]) => (
              <option key={clave} value={clave}>{label}{clave === pqrs.tipo ? ' — actual' : ''}</option>
            ))}
          </select>
        </Campo>
        <Campo id="reclasificar-motivo" etiqueta="¿Por qué?" obligatorio>
          <input id="reclasificar-motivo" value={motivo} onChange={(e) => setMotivo(e.target.value)}
                 placeholder="Ej: pide devolución de dinero, es un reclamo" className={claseCampo} />
        </Campo>
      </div>
      {/* El plazo, la prioridad y el flujo propuesto los recalcula el
          servidor; se avisa para que nadie se sorprenda al verlos moverse. */}
      {cambio && (
        <Efecto tono="alerta">
          Se recalcula la fecha límite con el plazo del tipo nuevo, contando desde que se radicó (puede quedar
          vencida), y el flujo de conceptos que se propone pasa a ser el de ese tipo.
        </Efecto>
      )}
      {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
      <div className="flex justify-end gap-2">
        <Boton onClick={() => { setAbierto(false); setTipo(pqrs.tipo); setMotivo(''); setError('') }}>Cancelar</Boton>
        <Boton tono="primario" disabled={!cambio || !motivo.trim()} cargando={mut.isPending} textoCargando="Guardando…"
               onClick={() => mut.mutate()}>
          Reclasificar
        </Boton>
      </div>
    </div>
  )
}

function ModoClasificar({ pqrs, alcance }) {
  return (
    <div className="space-y-4">
      {alcance?.puede_reclasificar && pqrs.estado !== 'cerrado' && <Reclasificar pqrs={pqrs} />}
      <CausaPQRS pqrs={pqrs} puedeMarcar={Boolean(alcance?.puede_marcar_causa)} />
    </div>
  )
}

// ── Comentar ──────────────────────────────────────────────────────

function ModoComentar({ pqrs, invalidar }) {
  const [comentario, setComentario] = useState('')
  const [evidencia, setEvidencia] = useState(null)
  const [error, setError] = useState('')
  const archivoRef = useRef(null)

  // Es el mismo endpoint de gestionar con solo el comentario: un comentario
  // suelto es una gestión válida y queda en el mismo historial.
  const mut = useMutation({
    mutationFn: () => {
      const datos = new FormData()
      datos.append('comentario', comentario.trim())
      if (evidencia) datos.append('evidencia', evidencia)
      return api.patch(`/pqrs/${pqrs.id}/gestion`, datos)
    },
    onSuccess: () => {
      invalidar()
      setComentario(''); setEvidencia(null); setError('')
      if (archivoRef.current) archivoRef.current.value = ''
    },
    onError: (err) => setError(mensajeDeError(err, 'No se pudo guardar el comentario.')),
  })

  return (
    <div className="space-y-3">
      <Campo id="comentario-interno" etiqueta="Comentario interno" obligatorio>
        <textarea id="comentario-interno" value={comentario} onChange={(e) => setComentario(e.target.value)} rows={3}
                  placeholder="Lo ve solo el equipo…" className={`${claseCampo} resize-y`} />
      </Campo>
      <Campo id="comentario-evidencia" etiqueta="Adjunto" opcional="opcional">
        <input id="comentario-evidencia" ref={archivoRef} type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
               onChange={(e) => setEvidencia(e.target.files?.[0] || null)} className={claseArchivo} />
      </Campo>
      <Efecto tono="neutro">No le llega al cliente, no cambia el estado ni el área, y no detiene el plazo.</Efecto>
      {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
      <div className="flex justify-end">
        <Boton tono="primario" disabled={!comentario.trim()} cargando={mut.isPending} textoCargando="Guardando…"
               onClick={() => mut.mutate()}>
          Comentar
        </Boton>
      </div>
    </div>
  )
}

// ── El panel ──────────────────────────────────────────────────────

export default function GestionarPQRS({
  pqrs, user, tipos, autorizaciones, hayPendiente, modo, onModo, invalidar,
}) {
  const { data: flujo } = useFlujo(pqrs.id)
  const alcance = pqrs.alcance
  // Quién pide autorizaciones es regla del rol, igual que antes en la tarjeta.
  const puedeSolicitar = ['admin', 'lider', 'agente'].includes(user?.rol)
  const modos = modosDeGestion(pqrs, puedeSolicitar)
  const actual = modos.includes(modo) ? modo : modos[0]
  const soloLectura = modos.length === 1

  // El modo que pide atención lleva una marca: la causa que falta para
  // cerrar y el flujo detenido esperando que alguien decida.
  const sinCausa = !pqrs.asociado_id || !pqrs.area_causante
  const alertas = {
    clasificar: sinCausa && Boolean(alcance?.puede_marcar_causa),
    conceptos: flujo?.estado === 'detenida' && Boolean(flujo?.puede_gestionar),
  }

  return (
    <section id="gestionar" className="bg-superficie rounded-xl border border-borde shadow-md overflow-hidden scroll-mt-20">
      <div className="flex items-center gap-2.5 px-5 py-3 border-b border-borde">
        {soloLectura ? <IconoEtiqueta tam={16} className="text-acento" /> : <IconoComentario tam={16} className="text-acento" />}
        <h3 className="text-sm font-semibold text-texto">{soloLectura ? 'Clasificación' : 'Gestionar'}</h3>
        <span className="text-xs text-texto-3 ml-auto hidden sm:inline">{MODOS_GESTION[actual]?.ayuda}</span>
      </div>

      {!soloLectura && (
        <div role="tablist" aria-label="Qué quieres hacer" className="flex gap-1 bg-superficie-2 rounded-lg p-1 mx-5 mt-4 overflow-x-auto">
          {modos.map(m => {
            const Icono = ICONOS[m]
            return (
              <button key={m} type="button" role="tab" aria-selected={m === actual} onClick={() => onModo(m)}
                      className={`flex-1 inline-flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md text-sm whitespace-nowrap transition ${
                        m === actual ? 'bg-superficie text-texto font-semibold shadow-sm' : 'text-texto-2 hover:text-texto'
                      }`}>
                <Icono tam={14} />
                {MODOS_GESTION[m].label}
                {alertas[m] && (
                  <span className="text-[10px] font-bold leading-none px-1.5 py-0.5 rounded-full bg-alerta-bg text-alerta"
                        title="Necesita atención">!</span>
                )}
              </button>
            )
          })}
        </div>
      )}

      <div role="tabpanel" className="p-5">
        {actual === 'avanzar' && (
          <ModoAvanzar pqrs={pqrs} alcance={alcance} hayPendiente={hayPendiente} invalidar={invalidar} />
        )}
        {actual === 'conceptos' && (
          <ModoConceptos pqrs={pqrs} tipos={tipos} puedeSolicitar={puedeSolicitar} hayPendiente={hayPendiente}
                         autorizaciones={autorizaciones} invalidar={invalidar} />
        )}
        {actual === 'clasificar' && <ModoClasificar pqrs={pqrs} alcance={alcance} />}
        {actual === 'comentar' && <ModoComentar pqrs={pqrs} invalidar={invalidar} />}
      </div>

      {!soloLectura && user && (
        <div className="px-5 py-2.5 border-t border-borde bg-superficie-2 text-xs text-texto-3">
          Queda registrado a nombre de <strong className="text-texto-2">{user.nombre}</strong>
          {user.area ? ` · ${user.area}` : ''}
        </div>
      )}
    </section>
  )
}
