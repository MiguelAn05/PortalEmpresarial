import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { crearIndicador, actualizarIndicador, obtenerCatalogo } from "../api"
import { UNIDADES, TIPOS_CAPTURA, DIRECCIONES, formatValor } from "../constants"
import { useCierreSeguro } from "../../../core/components/cierreSeguro"
import { AREAS } from "../../../core/areas.js"
import { tieneDatos } from "../../../core/components/tieneDatos"
import { IconoCerrar } from '../../../core/components/Iconos.jsx'



const VACIO = {
  nombre: "", descripcion: "", formula_texto: "",
  unidad: "porcentaje", tipo_captura: "razon", fuente_automatica: "",
  etiqueta_numerador: "", etiqueta_denominador: "",
  area: "", responsable_id: "",
  meta: "", direccion: "arriba", umbral_verde: "", umbral_amarillo: "",
  requiere_evidencia: false,
}

function aFormulario(ind) {
  if (!ind) return VACIO
  return Object.fromEntries(
    Object.entries(VACIO).map(([k, def]) => [k, ind[k] ?? def]),
  )
}

/**
 * Crear o editar la ficha de un indicador. Es la pantalla que decide si el
 * módulo "es fácil de agregar": por eso va explicando en cada paso qué
 * implica cada opción, en vez de asumir que quien lo llena sabe de métricas.
 */
export default function FormIndicador({ indicador, usuarios = [], onCerrar, onGuardado }) {
  const queryClient = useQueryClient()
  const [form, setForm] = useState(() => aFormulario(indicador))
  const [error, setError] = useState(null)

  const { data: catalogo = [] } = useQuery({
    queryKey: ["ind-catalogo"],
    queryFn: obtenerCatalogo,
  })

  const hayCambios = tieneDatos(form, aFormulario(indicador))
  const { intentarCerrar, dialogoDescarte } = useCierreSeguro({ hayCambios, onCerrar: onCerrar })

  const set = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })
  const esAutomatico = form.tipo_captura === "automatico"
  const esRazon = form.tipo_captura === "razon"

  /** Elegir una fuente del catálogo rellena nombre, fórmula y unidad sugeridos. */
  const elegirFuente = (clave) => {
    const f = catalogo.find(c => c.clave === clave)
    if (!f) { setForm({ ...form, fuente_automatica: "" }); return }
    setForm({
      ...form,
      fuente_automatica: clave,
      nombre: form.nombre || f.nombre,
      descripcion: form.descripcion || f.descripcion,
      formula_texto: f.formula,
      unidad: f.unidad,
      direccion: f.direccion,
    })
  }

  const mut = useMutation({
    mutationFn: () => {
      const numero = (v) => (v === "" || v === null ? null : Number(v))
      const payload = {
        ...form,
        responsable_id: form.responsable_id ? Number(form.responsable_id) : null,
        meta: numero(form.meta),
        umbral_verde: numero(form.umbral_verde),
        umbral_amarillo: numero(form.umbral_amarillo),
        area: form.area || null,
        fuente_automatica: esAutomatico ? form.fuente_automatica : null,
      }
      return indicador ? actualizarIndicador(indicador.id, payload) : crearIndicador(payload)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["ind-tablero"] })
      queryClient.invalidateQueries({ queryKey: ["ind-lista"] })
      onGuardado()
    },
    onError: (e) => setError(e?.response?.data?.detail || "No se pudo guardar el indicador."),
  })

  const completo = form.nombre && (!esAutomatico || form.fuente_automatica)
  const comparador = form.direccion === "arriba" ? "≥" : "≤"

  return (
    <div className="fixed inset-0 bg-acento-fuerte/40 backdrop-blur-sm flex items-center justify-center p-4 z-50" onClick={intentarCerrar}>
      <div className="bg-white rounded-2xl w-full max-w-2xl max-h-[92vh] overflow-y-auto shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="bg-gradient-to-r from-acento-fuerte to-acento rounded-t-2xl p-6 text-white sticky top-0 z-10">
          <button onClick={intentarCerrar} aria-label="Cerrar" className="absolute top-4 right-4 text-white/70 hover:text-white"><IconoCerrar tam={18} /></button>
          <h2 className="text-lg font-bold">{indicador ? 'Editar indicador' : 'Nuevo indicador'}</h2>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <p className="bg-negativo-bg border border-negativo/25 text-negativo text-sm rounded-lg px-3 py-2">{error}</p>
          )}

          {/* Paso 1: de dónde sale el dato */}
          <Seccion numero="1" titulo="¿De dónde sale el dato?">
            <div className="space-y-2">
              {Object.entries(TIPOS_CAPTURA).map(([valor, cfg]) => (
                <label key={valor}
                  className={`flex gap-3 items-start rounded-xl border p-3 cursor-pointer transition ${
                    form.tipo_captura === valor
                      ? 'border-acento bg-acento-suave' : 'border-borde hover:border-acento/50'
                  }`}>
                  <input type="radio" name="tipo_captura" value={valor}
                    checked={form.tipo_captura === valor}
                    onChange={set('tipo_captura')}
                    className="mt-0.5 accent-acento" />
                  <div>
                    <p className="text-sm font-semibold text-acento-fuerte">{cfg.label}</p>
                    <p className="text-xs text-texto-2 mt-0.5">{cfg.ayuda}</p>
                  </div>
                </label>
              ))}
            </div>

            {esAutomatico && (
              <div className="mt-3">
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                  ¿Cuál de los que el sistema ya sabe calcular?
                </label>
                <select value={form.fuente_automatica}
                  onChange={(e) => elegirFuente(e.target.value)}
                  className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                  <option value="">Elige una fuente...</option>
                  {['PQRS', 'Master Planner'].map(modulo => (
                    <optgroup key={modulo} label={modulo}>
                      {catalogo.filter(c => c.modulo === modulo).map(c => (
                        <option key={c.clave} value={c.clave}>{c.nombre}</option>
                      ))}
                    </optgroup>
                  ))}
                </select>
              </div>
            )}
          </Seccion>

          {/* Paso 2: qué es */}
          <Seccion numero="2" titulo="¿Qué mide?">
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Nombre</label>
                <input value={form.nombre} onChange={set('nombre')}
                  placeholder="Oportunidad en la respuesta de PQRS"
                  className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
                  Qué mide, en una frase
                </label>
                <input value={form.descripcion} onChange={set('descripcion')}
                  placeholder="Qué tanto respondemos dentro del plazo comprometido"
                  className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Fórmula</label>
                <textarea value={form.formula_texto} onChange={set('formula_texto')} rows={2}
                  disabled={esAutomatico}
                  placeholder="(PQRS cerradas a tiempo ÷ PQRS cerradas) × 100"
                  className="w-full rounded-lg border border-borde px-3 py-2 text-sm resize-none disabled:bg-superficie-2 disabled:text-texto-2" />
              </div>

              {esRazon && <CamposDeLaDivision form={form} set={set} />}

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Unidad</label>
                  <select value={form.unidad} onChange={set('unidad')} disabled={esAutomatico}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm disabled:bg-superficie-2">
                    {Object.entries(UNIDADES).map(([v, cfg]) => <option key={v} value={v}>{cfg.label}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Área</label>
                  <select value={form.area} onChange={set('area')}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                    <option value="">Sin área</option>
                    {AREAS.map(a => <option key={a} value={a}>{a}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Responsable</label>
                  <select value={form.responsable_id} onChange={set('responsable_id')}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm">
                    <option value="">Sin asignar</option>
                    {usuarios.map(u => <option key={u.id} value={u.id}>{u.nombre}</option>)}
                  </select>
                </div>
              </div>
            </div>
          </Seccion>

          {/* Paso 3: contra qué se juzga */}
          <Seccion numero="3" titulo="¿Cuándo está bien y cuándo está mal?">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
                {Object.entries(DIRECCIONES).map(([valor, cfg]) => (
                  <label key={valor}
                    className={`rounded-xl border p-3 cursor-pointer transition ${
                      form.direccion === valor
                        ? 'border-acento bg-acento-suave' : 'border-borde hover:border-acento/50'
                    }`}>
                    <input type="radio" name="direccion" value={valor}
                      checked={form.direccion === valor} onChange={set('direccion')}
                      className="accent-acento mr-2" />
                    <span className="text-sm font-semibold text-acento-fuerte">{cfg.label}</span>
                    <p className="text-[11px] text-texto-2 mt-0.5">{cfg.ayuda}</p>
                  </label>
                ))}
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">Meta</label>
                  <input type="number" step="any" value={form.meta} onChange={set('meta')}
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-positivo uppercase mb-1">Cumple si</label>
                  <div className="flex items-center gap-1">
                    <span className="text-sm text-texto-2 w-4">{comparador}</span>
                    <input type="number" step="any" value={form.umbral_verde} onChange={set('umbral_verde')}
                      className="w-full rounded-lg border border-positivo/25 px-3 py-2 text-sm" />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-alerta uppercase mb-1">Alerta si</label>
                  <div className="flex items-center gap-1">
                    <span className="text-sm text-texto-2 w-4">{comparador}</span>
                    <input type="number" step="any" value={form.umbral_amarillo} onChange={set('umbral_amarillo')}
                      className="w-full rounded-lg border border-ambar/30 px-3 py-2 text-sm" />
                  </div>
                </div>
              </div>

              {/* Traducción en palabras de lo que se acaba de configurar */}
              {form.umbral_verde !== "" && form.umbral_amarillo !== "" && (
                <p className="text-xs text-texto-2 bg-superficie-2 rounded-lg px-3 py-2">
                  Quedará así: <strong>cumple</strong> con {comparador} {formatValor(Number(form.umbral_verde), form.unidad)},
                  {' '}<strong>en alerta</strong> con {comparador} {formatValor(Number(form.umbral_amarillo), form.unidad)},
                  {' '}y <strong>no cumple</strong> por debajo de eso.
                </p>
              )}
              {(form.umbral_verde === "" || form.umbral_amarillo === "") && (
                <p className="text-xs text-alerta bg-alerta-bg border border-ambar/30 rounded-lg px-3 py-2">
                  Sin umbrales, el semáforo solo dirá "cumple o no cumple" comparando contra la meta.
                </p>
              )}

              <label className="flex items-center gap-2 text-sm text-texto-2 cursor-pointer select-none">
                <input type="checkbox" checked={form.requiere_evidencia}
                  onChange={(e) => setForm({ ...form, requiere_evidencia: e.target.checked })}
                  className="rounded border-borde accent-acento" />
                Exigir evidencia adjunta al registrar el valor
              </label>
            </div>
          </Seccion>
        </div>

        <div className="flex gap-2 px-6 py-4 bg-superficie-2 border-t border-borde sticky bottom-0">
          <button onClick={onCerrar}
            className="flex-1 border border-borde bg-white hover:bg-superficie-2 text-sm font-semibold text-acento-fuerte py-2.5 rounded-lg transition">
            Cancelar
          </button>
          <button onClick={() => { setError(null); mut.mutate() }}
            disabled={!completo || mut.isPending}
            className="flex-1 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold py-2.5 rounded-lg transition">
            {mut.isPending ? 'Guardando...' : indicador ? 'Guardar cambios' : 'Crear indicador'}
          </button>
        </div>
      </div>

      {dialogoDescarte}
    </div>
  )
}

function Seccion({ numero, titulo, children }) {
  return (
    <div>
      <div className="flex items-center gap-2 mb-3">
        <span className="w-6 h-6 rounded-full bg-acento-fuerte text-white text-xs font-bold flex items-center justify-center shrink-0">
          {numero}
        </span>
        <h3 className="text-sm font-bold text-acento-fuerte">{titulo}</h3>
      </div>
      {children}
    </div>
  )
}


/**
 * Los dos lados de la división, en lenguaje llano.
 *
 * Pedir "numerador" y "denominador" es jerga: la gente los escribe en el
 * orden en que ocurre el proceso (primero se reciben los casos, después se
 * atienden) y termina con la fracción al revés — 30/20 = 150% en vez de
 * 20/30 = 67%. Aquí se pregunta "qué se logró" y "de cuántos", que es como
 * se piensa, y debajo se muestra la fórmula y un ejemplo con números para
 * que el error sea visible antes de guardar.
 */
function CamposDeLaDivision({ form, set }) {
  const logrado = form.etiqueta_numerador || 'lo que se logró'
  const total = form.etiqueta_denominador || 'el total'
  const esPorcentaje = form.unidad === 'porcentaje'

  return (
    <div className="bg-superficie-2 rounded-xl p-4 space-y-3">
      <p className="text-xs text-texto-2">
        Este indicador es una división. Escribe qué se cuenta en cada lado.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_1fr] gap-3 items-end">
        <div>
          <label className="block text-xs font-semibold text-positivo uppercase mb-1">
            Lo que se logró
          </label>
          <input value={form.etiqueta_numerador} onChange={set('etiqueta_numerador')}
            placeholder="casos atendidos"
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
          <p className="text-[11px] text-texto-3 mt-1">La parte. Va arriba.</p>
        </div>

        <div className="text-center text-2xl text-texto-3 pb-6 hidden md:block">÷</div>

        <div>
          <label className="block text-xs font-semibold text-texto-2 uppercase mb-1">
            De un total de
          </label>
          <input value={form.etiqueta_denominador} onChange={set('etiqueta_denominador')}
            placeholder="casos recibidos"
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
          <p className="text-[11px] text-texto-3 mt-1">El total. Va abajo.</p>
        </div>
      </div>

      <div className="bg-white rounded-lg border border-borde px-3 py-2.5">
        <p className="text-[11px] font-semibold text-texto-2 uppercase tracking-wide mb-1">
          Así quedará la fórmula
        </p>
        <p className="text-sm text-texto">
          ({logrado} ÷ {total}){esPorcentaje && ' × 100'}
        </p>
        <p className="text-xs text-texto-2 mt-1.5">
          Por ejemplo: 20 {logrado} de 30 {total} ={' '}
          <strong>{esPorcentaje ? '66.67%' : '0.67'}</strong>
        </p>
      </div>
    </div>
  )
}