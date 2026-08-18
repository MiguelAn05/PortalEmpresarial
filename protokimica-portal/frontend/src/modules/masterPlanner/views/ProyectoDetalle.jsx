import { useMemo, useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import KanbanBoard from "../components/KanbanBoard"
import TareasTable from "../components/TareasTable"
import GanttView from "../components/GanttView"
import CalendarioTareas from "../components/CalendarioTareas"
import KPICards from "../components/KPICards"
import PriorityBadge from "../components/PriorityBadge"
import Avatar from "../components/Avatar"
import HistorialPanel from "../components/HistorialPanel"
import PanelPresupuesto from "../components/PanelPresupuesto"
import ConfirmarCambios from "../components/ConfirmarCambios"
import CierreProyectoModal from "../components/CierreProyectoModal"
import PanelCierre from "../components/PanelCierre"
import { useAuth } from "../../../core/AuthContext"
import {
  obtenerProyecto, listarTareasDeProyecto, actualizarTarea, actualizarProyecto,
  listarHistorialProyecto,
} from "../api"
import {
  IconoBandera, IconoCalendario, IconoCronograma, IconoDinero,
  IconoHistorial, IconoInfo, IconoProyectos, IconoTabla,
} from '../../../core/components/Iconos.jsx'
import {
  ESTADOS_PROYECTO, ESTADOS_TAREA, PRIORIDADES,
  FILTROS_TAREAS_VACIOS, filtrarTareas, alertaVencimiento,
  colorAvance, formatFecha, formatMoneda, puedeEditar,
} from "../constants"

const SUBVISTAS = [
  { id: 'tablero',     label: 'Tablero',     Icono: IconoProyectos  },
  { id: 'tabla',       label: 'Tabla',       Icono: IconoTabla      },
  { id: 'cronograma',  label: 'Cronograma',  Icono: IconoCronograma },
  { id: 'calendario',  label: 'Calendario',  Icono: IconoCalendario },
  { id: 'presupuesto', label: 'Presupuesto', Icono: IconoDinero     },
  { id: 'historial',   label: 'Historial',   Icono: IconoHistorial  },
  { id: 'informacion', label: 'Información', Icono: IconoInfo       },
  { id: 'cierre',      label: 'Cierre',      Icono: IconoBandera    },
]

/**
 * Quién puede finalizar o cancelar: el líder del proyecto, y admin.
 *
 * Es la misma regla que aplica el backend. Aquí solo decide si se muestra el
 * botón — quien lo intente igual pasa por la validación del servidor.
 */
function puedeCerrarProyecto(user, proyecto) {
  if (!user || !proyecto) return false
  return user.rol === 'admin' || proyecto.lider_id === user.id
}

export default function ProyectoDetalle({ proyectoId, usuarios, onVolver, onSelectTarea, onNuevaTarea, onEditar }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)
  const [subvista, setSubvista] = useState('tablero')
  const [filtros, setFiltros] = useState(FILTROS_TAREAS_VACIOS)
  const [confirmacion, setConfirmacion] = useState(null)
  const [cerrando, setCerrando] = useState(false)

  const { data: proyecto, isLoading: cargandoProyecto } = useQuery({
    queryKey: ["mp-proyecto", proyectoId],
    queryFn: () => obtenerProyecto(proyectoId),
  })

  const { data: tareas = [], isLoading: cargandoTareas } = useQuery({
    queryKey: ["mp-tareas", { proyecto: proyectoId }],
    queryFn: () => listarTareasDeProyecto(proyectoId),
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-tareas"] })
    queryClient.invalidateQueries({ queryKey: ["mp-proyecto", proyectoId] })
    queryClient.invalidateQueries({ queryKey: ["mp-proyectos"] })
    queryClient.invalidateQueries({ queryKey: ["mp-historial-proyecto", proyectoId] })
    queryClient.invalidateQueries({ queryKey: ["mp-historial-general"] })
    queryClient.invalidateQueries({ queryKey: ["mp-resumen"] })
  }

  const mutCambiarEstadoTarea = useMutation({
    mutationFn: ({ id, estado }) => actualizarTarea(id, { estado }),
    onSuccess: invalidar,
  })

  const mutCampoProyecto = useMutation({
    mutationFn: (payload) => actualizarProyecto(proyectoId, payload),
    onSuccess: () => { invalidar(); setConfirmacion(null) },
  })

  const visibles = useMemo(() => filtrarTareas(tareas, filtros), [tareas, filtros])
  const set = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value })
  const hayFiltros = Object.values(filtros).some(v => v !== "")

  if (cargandoProyecto || !proyecto) {
    return <div className="text-center py-16 text-texto-3 text-sm">Cargando proyecto...</div>
  }

  const estadoCfg = ESTADOS_PROYECTO[proyecto.estado] || {}
  const vencidas = tareas.filter(t => alertaVencimiento(t) === 'vencida').length
  const necesitaFiltros = ['tablero', 'tabla', 'cronograma', 'calendario'].includes(subvista)

  return (
    <div className="space-y-5">
      <button onClick={onVolver} className="text-sm font-semibold text-acento hover:underline">
        ← Volver a proyectos
      </button>

      {/* Cabecera del proyecto */}
      <div className="bg-white rounded-2xl border border-borde shadow-sm overflow-hidden">
        <div className="p-6">
          <div className="flex flex-wrap justify-between items-start gap-4">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 mb-2">
                <select
                  value={proyecto.estado}
                  disabled={!editable}
                  onChange={(e) => setConfirmacion({
                    cambios: [{ campo: 'estado', antes: proyecto.estado, despues: e.target.value }],
                    ejecutar: () => mutCampoProyecto.mutate({ estado: e.target.value }),
                  })}
                  className={`text-xs font-semibold rounded-full px-3 py-1 border-0 ${editable ? 'cursor-pointer' : ''} ${estadoCfg.color || 'bg-superficie-2'}`}
                >
                  {Object.entries(ESTADOS_PROYECTO).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                </select>
                <PriorityBadge priority={proyecto.prioridad} />
                {proyecto.area && (
                  <span
                    className="px-3 py-1 rounded-full text-xs font-semibold bg-acento-suave border border-borde text-acento"
                    title="Area responsable: es la duena del presupuesto"
                  >
                    {proyecto.area}
                  </span>
                )}
                {proyecto.areas_participantes?.map(a => (
                  <span key={a} title="Area participante"
                    className="px-3 py-1 rounded-full text-xs font-semibold bg-superficie-2 border border-borde text-texto-2">
                    {a}
                  </span>
                ))}
                {proyecto.archivado && (
                  <span className="px-3 py-1 rounded-full text-xs font-semibold bg-superficie-2 text-texto-2">Archivado</span>
                )}
              </div>
              <h2 className="text-2xl font-bold text-acento-fuerte">{proyecto.nombre}</h2>
              {proyecto.objetivo && <p className="text-sm text-texto-2 mt-1 max-w-2xl">{proyecto.objetivo}</p>}
            </div>

            {editable && (
              <div className="flex gap-2 shrink-0">
                {/* Solo mientras siga abierto: un proyecto cerrado se retoma
                    desde su acta, no se vuelve a cerrar. */}
                {!proyecto.cierre_tipo && puedeCerrarProyecto(user, proyecto) && (
                  <button
                    onClick={() => setCerrando(true)}
                    className="border border-borde hover:bg-superficie-2 text-acento-fuerte text-sm font-semibold px-4 py-2.5 rounded-xl transition"
                  >
                    Cerrar proyecto
                  </button>
                )}
                <button
                  onClick={() => onEditar(proyecto)}
                  className="border border-borde hover:bg-superficie-2 text-acento-fuerte text-sm font-semibold px-4 py-2.5 rounded-xl transition"
                >
                  Editar proyecto
                </button>
                <button
                  onClick={onNuevaTarea}
                  className="bg-acento hover:bg-acento-fuerte text-white text-sm font-semibold px-4 py-2.5 rounded-xl transition"
                >
                  + Nueva tarea
                </button>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-5 gap-5 mt-6 pt-5 border-t border-borde">
            <Dato titulo="Líder"><Avatar name={proyecto.lider_nombre} compact /></Dato>
            <Dato titulo="Inicio">{formatFecha(proyecto.fecha_inicio)}</Dato>
            <Dato titulo="Fin estimado">{formatFecha(proyecto.fecha_fin_estimada)}</Dato>
            <Dato titulo="Presupuesto">
              {formatMoneda(proyecto.presupuesto_total)}
              {proyecto.presupuesto_total > 0 && (
                <span className="block text-[11px] text-texto-3">
                  {proyecto.presupuesto_aprobado > 0
                    ? `${proyecto.pagado_pct}% pagado de lo aprobado`
                    : 'sin aprobar'}
                  {proyecto.items_por_aprobar > 0 && ` · ${proyecto.items_por_aprobar} por aprobar`}
                </span>
              )}
            </Dato>
            <Dato titulo={`Avance · ${proyecto.tareas_completadas}/${proyecto.total_tareas} tareas`}>
              <div className="flex items-center gap-2">
                <div className="flex-1 bg-superficie-2 rounded-full h-2">
                  <div className="h-2 rounded-full" style={{ width: `${proyecto.avance_pct}%`, background: colorAvance(proyecto.avance_pct) }} />
                </div>
                <span className="text-sm font-bold text-acento-fuerte">{proyecto.avance_pct}%</span>
              </div>
            </Dato>
          </div>

          {vencidas > 0 && (
            <div className="mt-4 bg-negativo-bg border border-negativo/25 text-negativo text-sm rounded-xl px-4 py-2.5 font-semibold">
              {vencidas} tarea{vencidas === 1 ? '' : 's'} de este proyecto {vencidas === 1 ? 'está vencida' : 'están vencidas'}.
            </div>
          )}
        </div>

        <div className="border-t border-borde px-6 flex gap-1 overflow-x-auto">
          {SUBVISTAS.map(v => (
            <button
              key={v.id}
              onClick={() => setSubvista(v.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 -mb-px
                whitespace-nowrap transition-colors duration-150 ease-suave ${
                subvista === v.id
                  ? 'border-acento text-texto font-semibold'
                  : 'border-transparent text-texto-2 hover:text-texto'
              }`}
            >
              <v.Icono tam={15} />
              {v.label}
            </button>
          ))}
        </div>
      </div>

      {/* Filtros de tareas dentro del proyecto (sin filtro de proyecto, ya estamos en uno) */}
      {necesitaFiltros && tareas.length > 0 && (
        <div className="bg-white rounded-2xl border border-borde p-4 shadow-sm">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-3">
            <input
              value={filtros.busqueda} onChange={set('busqueda')}
              placeholder="Buscar tarea..."
              className="rounded-lg border border-borde px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-acento"
            />
            <select value={filtros.asignado_a} onChange={set('asignado_a')} className="rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todos los responsables</option>
              <option value="sin_asignar">Sin asignar</option>
              {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
            <select value={filtros.estado} onChange={set('estado')} className="rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todos los estados</option>
              {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
            <select value={filtros.prioridad} onChange={set('prioridad')} className="rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todas las prioridades</option>
              {Object.entries(PRIORIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
            <select value={filtros.vencimiento} onChange={set('vencimiento')} className="rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todo vencimiento</option>
              <option value="vencida">Solo vencidas</option>
              <option value="por_vencer">Solo por vencer</option>
              <option value="en_riesgo">Vencidas y por vencer</option>
              <option value="sin_fecha">Sin fecha de fin</option>
            </select>
          </div>
          {hayFiltros && (
            <div className="flex justify-between items-center mt-3">
              <span className="text-xs text-texto-3">{visibles.length} de {tareas.length} tareas</span>
              <button onClick={() => setFiltros(FILTROS_TAREAS_VACIOS)} className="text-xs font-semibold text-acento hover:underline">
                Limpiar filtros
              </button>
            </div>
          )}
        </div>
      )}

      {cargandoTareas && necesitaFiltros ? (
        <div className="text-center py-16 text-texto-3 text-sm">Cargando tareas...</div>
      ) : necesitaFiltros && tareas.length === 0 ? (
        <div className="bg-white rounded-2xl border border-dashed border-borde p-16 text-center">
          <p className="text-texto-2 mb-4">Este proyecto todavía no tiene tareas.</p>
          <button
            onClick={onNuevaTarea}
            className="bg-acento hover:bg-acento-fuerte text-white font-semibold px-6 py-3 rounded-xl shadow-sm transition"
          >
            + Crear la primera tarea
          </button>
        </div>
      ) : (
        <>
          {subvista === 'tablero' && (
            <div className="space-y-5">
              <KPICards tareas={tareas} />
              <KanbanBoard
                tareas={visibles}
                mostrarProyecto={false}
                onChangeEstado={(id, estado) => mutCambiarEstadoTarea.mutate({ id, estado })}
                onSelect={onSelectTarea}
              />
            </div>
          )}
          {subvista === 'tabla' && <TareasTable tareas={visibles} onSelect={onSelectTarea} mostrarProyecto={false} />}
          {subvista === 'cronograma' && <GanttView tareas={visibles} onSelect={onSelectTarea} mostrarProyecto={false} />}
          {subvista === 'calendario' && <CalendarioTareas tareas={visibles} onSelect={onSelectTarea} />}
          {subvista === 'presupuesto' && <PanelPresupuesto proyectoId={proyectoId} editable={editable} onCambio={invalidar} />}
          {subvista === 'historial' && <PanelHistorial proyectoId={proyectoId} />}
          {subvista === 'informacion' && <PanelInformacion proyecto={proyecto} editable={editable} onEditar={() => onEditar(proyecto)} />}
          {subvista === 'cierre' && (
            <PanelCierre proyecto={proyecto} puedeCerrar={editable && puedeCerrarProyecto(user, proyecto)} />
          )}
        </>
      )}

      {confirmacion && (
        <ConfirmarCambios
          titulo="Cambiar el estado del proyecto?"
          cambios={confirmacion.cambios}
          guardando={mutCampoProyecto.isPending}
          onConfirmar={confirmacion.ejecutar}
          onCancelar={() => setConfirmacion(null)}
        />
      )}

      {cerrando && (
        <CierreProyectoModal
          proyecto={proyecto}
          onCerrar={() => { setCerrando(false); setSubvista('cierre') }}
        />
      )}
    </div>
  )
}

function Dato({ titulo, children }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-texto-3 uppercase tracking-wide mb-1.5">{titulo}</p>
      <div className="text-sm text-texto">{children}</div>
    </div>
  )
}

function PanelInformacion({ proyecto, editable, onEditar }) {
  return (
    <div className="bg-white rounded-2xl border border-borde shadow-sm p-6 space-y-5">
      <div className="flex justify-between items-start">
        <h3 className="text-sm font-bold text-acento-fuerte">Información del proyecto</h3>
        {editable && (
          <button onClick={onEditar} className="text-xs font-semibold text-acento hover:underline">Editar</button>
        )}
      </div>
      <Campo titulo="Objetivo" valor={proyecto.objetivo} />
      <Campo titulo="Alcance" valor={proyecto.alcance} />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2 border-t border-borde">
        <Campo titulo="Fecha de inicio" valor={formatFecha(proyecto.fecha_inicio)} />
        <Campo titulo="Fin estimado" valor={formatFecha(proyecto.fecha_fin_estimada)} />
        <Campo titulo="Fin real" valor={proyecto.fecha_fin_real ? formatFecha(proyecto.fecha_fin_real) : 'Aún abierto'} />
      </div>
      <p className="text-[11px] text-texto-3 pt-2 border-t border-borde">
        Creado el {formatFecha(proyecto.creado_en)}
      </p>
    </div>
  )
}

function Campo({ titulo, valor }) {
  return (
    <div>
      <p className="text-[11px] font-semibold text-texto-3 uppercase tracking-wide mb-1">{titulo}</p>
      <p className="text-sm text-texto whitespace-pre-line">{valor || <span className="text-borde-fuerte italic">Sin definir</span>}</p>
    </div>
  )
}

function PanelHistorial({ proyectoId }) {
  const [soloProyecto, setSoloProyecto] = useState(false)

  const { data: historial = [], isLoading } = useQuery({
    queryKey: ["mp-historial-proyecto", proyectoId, soloProyecto],
    queryFn: () => listarHistorialProyecto(proyectoId, { solo_proyecto: soloProyecto }),
  })

  return (
    <div className="bg-white rounded-2xl border border-borde shadow-sm overflow-hidden">
      <div className="flex flex-wrap justify-between items-center gap-3 px-6 py-4 border-b border-borde">
        <div>
          <h3 className="text-sm font-bold text-acento-fuerte">Historial de cambios</h3>
          <p className="text-xs text-texto-3 mt-0.5">
            Quién cambió qué y cuándo, en el proyecto y en sus tareas.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-texto-2 cursor-pointer select-none">
          <input
            type="checkbox" checked={soloProyecto}
            onChange={(e) => setSoloProyecto(e.target.checked)}
            className="rounded border-borde accent-acento"
          />
          Solo cambios del proyecto
        </label>
      </div>

      <div className="p-6">
        {isLoading ? (
          <p className="text-sm text-texto-3 text-center py-6">Cargando historial...</p>
        ) : (
          <HistorialPanel
            entradas={historial}
            mostrarEntidad={!soloProyecto}
            vacio={soloProyecto
              ? 'Este proyecto no ha tenido cambios desde que se creó.'
              : 'Todavía no hay cambios registrados en este proyecto ni en sus tareas.'}
          />
        )}
      </div>
    </div>
  )
}
