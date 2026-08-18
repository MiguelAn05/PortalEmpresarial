import { useMemo, useState } from "react"
import { useQuery } from "@tanstack/react-query"
import CalendarioTareas from "../components/CalendarioTareas"
import { listarTareas, listarEventosOutlook } from "../api"
import { AREAS, ESTADOS_TAREA, filtrarTareas } from "../constants"

// Se pide una ventana amplia de una sola vez (mes anterior y tres
// siguientes) en vez de recargar cada vez que alguien pasa de mes: moverse
// por el calendario es lo más común que se hace aquí, y una espera en cada
// flecha se siente rota.
function ventanaConsulta() {
  const hoy = new Date()
  const desde = new Date(hoy.getFullYear(), hoy.getMonth() - 1, 1)
  const hasta = new Date(hoy.getFullYear(), hoy.getMonth() + 4, 0)
  const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}T00:00:00`
  return { desde: iso(desde), hasta: iso(hasta) }
}

// Los eventos de Outlook se disfrazan de tarea para que el calendario los
// pinte con el mismo layout de barras y rejilla, sin duplicar esa lógica.
// La marca `es_outlook` es lo que cambia el estilo y el clic.
function comoTarea(evento) {
  return {
    id: `outlook-${evento.id}`,
    titulo: evento.titulo,
    fecha_inicio: evento.inicio,
    fecha_fin: evento.fin,
    estado: null,
    es_outlook: true,
    privado: evento.privado,
    enlace: evento.enlace_teams || evento.enlace_outlook,
    es_reunion_teams: evento.es_reunion_teams,
  }
}

// El calendario responde a "¿quién está haciendo qué y cuándo?", así que
// filtra por persona y proyecto, no por todo lo que filtra el tablero.
const FILTROS_VACIOS = { busqueda: "", proyecto_id: "", asignado_a: "", area: "", estado: "", prioridad: "", vencimiento: "" }

export default function CalendarioView({ proyectos, usuarios, onSelectTarea }) {
  const [filtros, setFiltros] = useState(FILTROS_VACIOS)
  const [ocultarCompletadas, setOcultarCompletadas] = useState(false)
  const [verOutlook, setVerOutlook] = useState(true)
  const ventana = useMemo(() => ventanaConsulta(), [])

  // Si Microsoft 365 no está configurado, el backend devuelve lista vacía:
  // el calendario funciona igual y el interruptor simplemente no muestra nada.
  const { data: eventos = [] } = useQuery({
    queryKey: ["mp-outlook", ventana],
    queryFn: () => listarEventosOutlook(ventana.desde, ventana.hasta),
    staleTime: 5 * 60 * 1000,
    retry: false,
  })

  const { data: tareas = [], isLoading } = useQuery({
    queryKey: ["mp-tareas", { calendario: true }],
    // El calendario sí incluye subtareas: si alguien tiene una subtarea con
    // fecha, esa fecha ocupa su tiempo igual que cualquier otra tarea.
    queryFn: () => listarTareas({ incluir_subtareas: true }),
  })

  const set = (campo) => (e) => setFiltros({ ...filtros, [campo]: e.target.value })

  const visibles = useMemo(() => {
    const base = filtrarTareas(tareas, filtros)
    return ocultarCompletadas ? base.filter(t => t.estado !== 'completada') : base
  }, [tareas, filtros, ocultarCompletadas])

  // Los filtros de arriba (responsable, proyecto, área) son de tareas y no
  // aplican a un evento de Outlook, que no tiene ninguno de esos datos.
  // Por eso los eventos se agregan al final y se controlan con su interruptor.
  const enElCalendario = useMemo(
    () => verOutlook ? [...visibles, ...eventos.map(comoTarea)] : visibles,
    [visibles, eventos, verOutlook],
  )

  if (isLoading) {
    return <div className="text-center py-16 text-texto-3 text-sm">Cargando calendario...</div>
  }

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-borde p-5 shadow-sm">
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Responsable</label>
            <select value={filtros.asignado_a} onChange={set('asignado_a')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todos</option>
              <option value="sin_asignar">Sin asignar</option>
              {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Proyecto</label>
            <select value={filtros.proyecto_id} onChange={set('proyecto_id')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todos</option>
              {proyectos.map(p => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Área</label>
            <select value={filtros.area} onChange={set('area')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todas</option>
              {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Estado</label>
            <select value={filtros.estado} onChange={set('estado')} className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
              <option value="">Todos</option>
              {Object.entries(ESTADOS_TAREA).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
            </select>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 mt-4">
          <label className="flex items-center gap-2 text-sm text-texto-2 cursor-pointer select-none">
            <input
              type="checkbox" checked={ocultarCompletadas}
              onChange={(e) => setOcultarCompletadas(e.target.checked)}
              className="rounded border-borde accent-acento"
            />
            Ocultar completadas
          </label>

          {eventos.length > 0 && (
            <label className="flex items-center gap-2 text-sm text-texto-2 cursor-pointer select-none">
              <input
                type="checkbox" checked={verOutlook}
                onChange={(e) => setVerOutlook(e.target.checked)}
                className="rounded border-borde accent-acento"
              />
              <span className="inline-flex items-center gap-1.5">
                <span
                  className="inline-block w-3 h-3 rounded-sm border-2 border-dashed border-texto-2"
                  aria-hidden="true"
                />
                Mi calendario de Outlook
              </span>
            </label>
          )}

          <span className="text-xs text-texto-3">
            {visibles.length} de {tareas.length} tarea{tareas.length === 1 ? '' : 's'}
            {verOutlook && eventos.length > 0 && ` · ${eventos.length} evento${eventos.length === 1 ? '' : 's'} de Outlook`}
          </span>
        </div>
      </div>

      <CalendarioTareas tareas={enElCalendario} onSelect={onSelectTarea} />
    </div>
  )
}
