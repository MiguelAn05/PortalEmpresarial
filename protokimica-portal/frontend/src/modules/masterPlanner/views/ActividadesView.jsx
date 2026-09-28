/**
 * Actividades diarias: lo que se repite y no pertenece a ningún proyecto.
 *
 * La pantalla contesta una sola pregunta primero —**qué me toca hoy**— y
 * después deja mirar el resto. Una lista de todo lo definido, con la de hoy
 * mezclada entre veinte que no tocan, convierte un chequeo de treinta
 * segundos en una búsqueda.
 *
 * Qué tocaba cada día lo decide el SERVIDOR (`toca_hoy`, `registrada_hoy` y
 * `frecuencia_texto` llegan resueltos). Aquí no se calcula ninguna fecha: la
 * regla de días hábiles y festivos vive en un solo sitio, y si la pantalla la
 * repitiera, un festivo nuevo dejaría el portal diciendo dos cosas.
 */
import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useAuth } from "../../../core/AuthContext"
import {
  IconoAlDia, IconoCerrar, IconoRepetir,
} from "../../../core/components/Iconos.jsx"
import { mensajeDeError } from "../../../core/errores.js"
import {
  listarActividades, registrarActividad, quitarRegistroActividad,
  eliminarActividad, actualizarActividad,
} from "../api"
import { isoDeHoy, puedeEditar } from "../constants"
import ActividadFormModal from "../components/ActividadFormModal"
import RegistroActividadModal from "../components/RegistroActividadModal"

function Casilla({ actividad, onMarcar, onDesmarcar, ocupado }) {
  const marcada = actividad.registrada_hoy

  return (
    <button
      onClick={() => (marcada ? onDesmarcar(actividad) : onMarcar(actividad))}
      disabled={ocupado}
      aria-pressed={marcada}
      aria-label={`${marcada ? 'Desmarcar' : 'Marcar'} ${actividad.titulo}`}
      className={`w-6 h-6 rounded-md border flex items-center justify-center flex-shrink-0
        transition-colors duration-150 disabled:opacity-40 ${
        marcada
          ? 'bg-positivo-vivo border-positivo-vivo text-white'
          : 'bg-superficie border-borde-fuerte hover:border-acento'
      }`}
    >
      {marcada && <IconoAlDia tam={14} />}
    </button>
  )
}

export default function ActividadesView({ usuarios = [] }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const editable = puedeEditar(user)

  const [creando, setCreando] = useState(false)
  const [viendoRegistro, setViendoRegistro] = useState(null)
  const [verTodas, setVerTodas] = useState(false)

  const { data: actividades = [], isLoading } = useQuery({
    queryKey: ["mp-actividades", verTodas],
    queryFn: () => listarActividades(verTodas ? {} : { solo_mias: true }),
  })

  const invalidar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-actividades"] })
    // El cumplimiento de actividades alimenta un indicador: al marcar algo,
    // el resumen de Inicio deja de estar al día.
    queryClient.invalidateQueries({ queryKey: ["inicio"] })
  }

  const conError = (accion) => ({
    mutationFn: accion,
    onSuccess: invalidar,
    onError: (err) => alert(mensajeDeError(err, 'No se pudo guardar.')),
  })

  const mutMarcar = useMutation(conError((a) => registrarActividad(a.id)))
  const mutDesmarcar = useMutation(conError(
    //  da la fecha en UTC: después de las 7 p. m. en Colombia
    // ya es la de mañana, y desmarcar buscaba un día que no existe.
    (a) => quitarRegistroActividad(a.id, isoDeHoy()),
  ))
  const mutEliminar = useMutation(conError((a) => eliminarActividad(a.id)))
  const mutDesactivar = useMutation(conError(
    (a) => actualizarActividad(a.id, { activa: false }),
  ))

  const deHoy = actividades.filter(a => a.toca_hoy)
  const pendientes = deHoy.filter(a => !a.registrada_hoy).length
  const otras = actividades.filter(a => !a.toca_hoy)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-texto">Actividades diarias</h2>
          {/* La diferencia con las tareas, dicha donde se necesita: quien
              duda de dónde va algo, lo lee aquí y no tiene que preguntar. */}
          <p className="text-sm text-texto-2 mt-1">
            Lo que se repite y no termina nunca — la ronda, el informe, la
            revisión semanal. Lo que tiene un final va en Tareas de proyecto.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-texto-2">
            <input
              type="checkbox" checked={verTodas}
              onChange={(e) => setVerTodas(e.target.checked)}
              className="rounded border-borde-fuerte"
            />
            Ver las de mi área
          </label>
          {editable && (
            <button
              onClick={() => setCreando(true)}
              className="bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold
                px-4 py-2.5 rounded-lg text-sm transition"
            >
              + Nueva actividad
            </button>
          )}
        </div>
      </div>

      {/* Lo de hoy primero y aparte: es la única pregunta que alguien entra
          a resolver todos los días. */}
      <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
        <header className="px-5 py-3.5 border-b border-borde flex items-center justify-between">
          <h3 className="text-sm font-semibold text-texto">Hoy</h3>
          <span className={`text-xs font-semibold ${
            pendientes ? 'text-alerta' : 'text-positivo'
          }`}>
            {deHoy.length === 0
              ? 'Nada programado para hoy'
              : pendientes === 0
                ? 'Todas registradas'
                : `${pendientes} sin registrar`}
          </span>
        </header>

        {isLoading ? (
          <p className="px-5 py-8 text-center text-sm text-texto-2">Cargando…</p>
        ) : deHoy.length === 0 ? (
          <div className="px-5 py-8 text-center">
            <div className="flex justify-center mb-3 text-texto-3"><IconoRepetir tam={24} /></div>
            <p className="text-sm text-texto-2">
              Hoy no toca ninguna. Puede ser fin de semana, festivo, o que
              todavía no hayas creado ninguna actividad.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-borde">
            {deHoy.map(a => (
              <li key={a.id} className="flex items-center gap-3 px-5 py-3">
                <Casilla
                  actividad={a}
                  onMarcar={(x) => mutMarcar.mutate(x)}
                  onDesmarcar={(x) => mutDesmarcar.mutate(x)}
                  ocupado={mutMarcar.isPending || mutDesmarcar.isPending}
                />
                <span className="min-w-0 flex-1">
                  <span className={`block text-sm ${
                    a.registrada_hoy ? 'text-texto-3 line-through' : 'text-texto font-medium'
                  }`}>
                    {a.titulo}
                  </span>
                  <span className="block text-xs text-texto-3">
                    {a.asignado_nombre}{a.area && ` · ${a.area}`}
                  </span>
                </span>
                <button
                  onClick={() => setViendoRegistro(a)}
                  className="text-xs font-semibold text-acento hover:underline flex-shrink-0"
                >
                  Ver registro
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Las demás: las que no tocan hoy. Se ven para poder administrarlas,
          no para trabajar con ellas. */}
      {otras.length > 0 && (
        <section className="bg-superficie rounded-xl border border-borde shadow-sm overflow-hidden">
          <header className="px-5 py-3.5 border-b border-borde">
            <h3 className="text-sm font-semibold text-texto">Las demás</h3>
            <p className="text-xs text-texto-3 mt-0.5">
              No tocan hoy. Aquí se administran.
            </p>
          </header>
          <ul className="divide-y divide-borde">
            {otras.map(a => (
              <li key={a.id} className="flex items-center gap-3 px-5 py-3">
                <span className="min-w-0 flex-1">
                  <span className="block text-sm text-texto">{a.titulo}</span>
                  <span className="block text-xs text-texto-3">
                    {a.frecuencia_texto} · {a.asignado_nombre}
                  </span>
                </span>
                <button
                  onClick={() => setViendoRegistro(a)}
                  className="text-xs font-semibold text-acento hover:underline flex-shrink-0"
                >
                  Ver registro
                </button>
                {editable && (
                  <button
                    onClick={() => {
                      if (!window.confirm(
                        `¿Desactivar «${a.titulo}»?\n\n` +
                        'Deja de pedirse desde hoy. Lo ya registrado se conserva, ' +
                        'y se puede volver a activar cuando haga falta.'
                      )) return
                      mutDesactivar.mutate(a)
                    }}
                    title="Desactivar"
                    className="text-texto-3 hover:text-negativo p-1.5 rounded-lg flex-shrink-0
                      hover:bg-negativo-bg transition-colors duration-150"
                  >
                    <IconoCerrar tam={14} />
                  </button>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {creando && (
        <ActividadFormModal
          usuarios={usuarios}
          onClose={() => setCreando(false)}
          onCreada={invalidar}
        />
      )}

      {viendoRegistro && (
        <RegistroActividadModal
          actividad={viendoRegistro}
          onClose={() => setViendoRegistro(null)}
          onCambio={invalidar}
          onEliminar={editable ? (a) => { mutEliminar.mutate(a); setViendoRegistro(null) } : null}
        />
      )}
    </div>
  )
}
