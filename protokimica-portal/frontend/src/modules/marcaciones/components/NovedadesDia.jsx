import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { mensajeDeError } from '../../../core/errores.js'
import Boton from '../../../core/components/Boton.jsx'
import { justificarNovedad, quitarJustificacion } from '../api.js'
import { MAX_JUSTIFICACION, MIN_JUSTIFICACION } from '../constants.js'

/**
 * Las novedades de UNA persona UN día, con el detalle de las horas y el
 * espacio para justificarlas.
 *
 * Justificar no borra la novedad: la acompaña con el motivo, quién lo escribió
 * y cuándo. Quien no puede justificar (el agente) ve el motivo, no el cuadro.
 * Lo usan el cuadro que abre «Novedades» y el detalle por días de la persona.
 */
export default function NovedadesDia({ empCode, fecha, novedades, puede }) {
  return (
    <ul className="space-y-3">
      {novedades.map(n => (
        <ItemNovedad key={n.tipo} empCode={empCode} fecha={fecha} novedad={n} puede={puede} />
      ))}
    </ul>
  )
}

function ItemNovedad({ empCode, fecha, novedad, puede }) {
  const queryClient = useQueryClient()
  const j = novedad.justificacion
  const [editando, setEditando] = useState(false)
  const [texto, setTexto] = useState(j?.texto ?? '')
  const [error, setError] = useState('')

  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['marcaciones'] })

  const guardar = useMutation({
    mutationFn: () => justificarNovedad({ emp_code: empCode, fecha, tipo: novedad.tipo, texto }),
    onSuccess: () => { setEditando(false); setError(''); refrescar() },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo guardar la justificación.')),
  })
  const quitar = useMutation({
    mutationFn: () => quitarJustificacion({ emp_code: empCode, fecha, tipo: novedad.tipo }),
    onSuccess: () => { setTexto(''); setEditando(false); setError(''); refrescar() },
    onError: (e) => setError(mensajeDeError(e, 'No se pudo quitar la justificación.')),
  })

  const mostrarForm = puede && (editando || !j)
  const corto = texto.trim().length < MIN_JUSTIFICACION

  return (
    <li className="rounded-xl border border-borde p-3 space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1.5 text-sm font-semibold ${j ? 'text-positivo' : 'text-negativo'}`}>
          <span className={`w-2 h-2 rounded-full ${j ? 'bg-positivo-vivo' : 'bg-negativo-vivo'}`} aria-hidden="true" />
          {novedad.etiqueta}
        </span>
        <span className="text-xs text-texto-2">{j ? 'Justificada' : 'Sin justificar'}</span>
      </div>
      <p className="text-sm text-texto">{novedad.detalle}</p>

      {j && !editando && (
        <div className="bg-positivo-bg rounded-lg px-3 py-2 text-sm text-texto">
          <p>{j.texto}</p>
          <p className="text-[11px] text-texto-2 mt-1">{j.autor}{j.cuando && <> · {j.cuando}</>}</p>
          {puede && (
            <div className="flex gap-2 mt-2">
              <Boton tam="sm" onClick={() => setEditando(true)}>Corregir</Boton>
              <Boton tam="sm" tono="fantasma" cargando={quitar.isPending} onClick={() => quitar.mutate()}>Quitar</Boton>
            </div>
          )}
        </div>
      )}

      {mostrarForm && (
        <form onSubmit={(e) => { e.preventDefault(); setError(''); guardar.mutate() }} className="space-y-2">
          <label className="block text-xs font-semibold text-texto-2 uppercase" htmlFor={`just-${empCode}-${fecha}-${novedad.tipo}`}>
            Justificación
          </label>
          <textarea id={`just-${empCode}-${fecha}-${novedad.tipo}`} value={texto} rows={2} maxLength={MAX_JUSTIFICACION}
                    onChange={(e) => setTexto(e.target.value)}
                    placeholder="Por qué ocurrió: cita médica, permiso autorizado, falla del bus…"
                    className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
          <div className="flex items-center justify-between gap-2">
            <span className="text-[11px] text-texto-3">{texto.length}/{MAX_JUSTIFICACION} · queda con tu nombre y la hora</span>
            <div className="flex gap-2">
              {editando && <Boton tam="sm" tono="fantasma" onClick={() => { setEditando(false); setTexto(j?.texto ?? ''); setError('') }}>Cancelar</Boton>}
              <Boton tam="sm" tono="primario" type="submit" disabled={corto} cargando={guardar.isPending} textoCargando="Guardando…">
                Guardar justificación
              </Boton>
            </div>
          </div>
        </form>
      )}

      {!puede && !j && <p className="text-[11px] text-texto-3">Solo el líder del área o Gestión Humana pueden justificarla.</p>}
      {error && <p role="alert" className="text-sm text-negativo">{error}</p>}
    </li>
  )
}
