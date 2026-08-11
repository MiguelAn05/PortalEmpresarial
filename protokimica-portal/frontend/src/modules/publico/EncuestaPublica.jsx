import { useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { obtenerEncuestaPublica, responderEncuestaPublica } from "../encuestas/api"
import { ESCALA_MAX } from "../encuestas/constants"

/**
 * La encuesta que responde el cliente. Sin sesión.
 *
 * Se abre desde un QR en el punto de venta, así que se diseña para un celular
 * con una mano: controles grandes, una pantalla sin scroll infinito y nada
 * que obligue a escribir si no quiere.
 *
 * A quién califica puede venir en el enlace (?ref=V-014&nombre=Andrea) para
 * que cada vendedor tenga su propio QR y el cliente no tenga que elegir a
 * nadie de una lista.
 */
export default function EncuestaPublica() {
  const { slug } = useParams()
  const [params] = useSearchParams()

  const [respuestas, setRespuestas] = useState({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [listo, setListo] = useState(null)   // mensaje final cuando ya respondió

  const { data: encuesta, isLoading, isError } = useQuery({
    queryKey: ["encuesta-publica", slug],
    queryFn: () => obtenerEncuestaPublica(slug),
    retry: false,
  })

  const responder = (preguntaId, valor) => {
    setRespuestas(r => ({ ...r, [preguntaId]: valor }))
    setError('')
  }

  const enviar = async (e) => {
    e.preventDefault()
    setError('')

    const faltan = encuesta.preguntas.filter(
      p => p.obligatoria && (respuestas[p.id] === undefined || respuestas[p.id] === '')
    )
    if (faltan.length) {
      setError(`Falta responder: ${faltan.map(p => p.texto).join(', ')}`)
      return
    }

    setEnviando(true)
    try {
      const data = await responderEncuestaPublica(slug, {
        sujeto_ref: params.get('ref'),
        sujeto_nombre: params.get('nombre'),
        respuestas,
      })
      setListo(data.mensaje)
    } catch (err) {
      setError(err.response?.data?.detail || 'No se pudo enviar. Revisa tu conexión e intenta de nuevo.')
    } finally {
      setEnviando(false)
    }
  }

  if (isLoading) {
    return <Marco><p className="text-center text-[#6B7EA8] py-12">Cargando...</p></Marco>
  }

  if (isError) {
    return (
      <Marco>
        <div className="text-center py-10">
          <p className="text-4xl mb-3" aria-hidden="true">🔍</p>
          <h1 className="text-xl font-bold text-[#0D2B5E] mb-2">Encuesta no disponible</h1>
          <p className="text-[#6B7EA8] text-sm">
            Verifica el enlace o vuelve a escanear el código QR.
          </p>
        </div>
      </Marco>
    )
  }

  if (listo) {
    return (
      <Marco>
        <div className="text-center py-10">
          <p className="text-5xl mb-4" aria-hidden="true">✅</p>
          <h1 className="text-2xl font-bold text-[#0D2B5E] mb-2">¡Listo!</h1>
          <p className="text-[#42557A]">{listo}</p>
        </div>
      </Marco>
    )
  }

  const quien = params.get('nombre')

  return (
    <Marco>
      <form onSubmit={enviar} className="space-y-6">
        <header>
          <h1 className="text-2xl font-bold text-[#0D2B5E]">{encuesta.nombre}</h1>
          {encuesta.descripcion && (
            <p className="text-[#6B7EA8] mt-1 text-sm">{encuesta.descripcion}</p>
          )}
          {quien && (
            <p className="mt-3 inline-block bg-[#F7F9FC] border border-[#D6E0F0] rounded-full px-3 py-1 text-sm text-[#42557A]">
              Estás calificando a <b>{quien}</b>
            </p>
          )}
        </header>

        {encuesta.preguntas.map(p => (
          <fieldset key={p.id} className="border-0 p-0 m-0">
            <legend className="text-base font-semibold text-[#1A2B47] mb-2">
              {p.texto}
              {p.obligatoria && <span className="text-[#D93B3B] ml-1" aria-hidden="true">*</span>}
            </legend>
            {p.ayuda && <p className="text-xs text-[#9BACC8] mb-2 -mt-1">{p.ayuda}</p>}

            {p.tipo === 'escala' && (
              <Escala valor={respuestas[p.id]} onCambio={(v) => responder(p.id, v)} />
            )}

            {p.tipo === 'si_no' && (
              <Botones
                opciones={['Sí', 'No']}
                valor={respuestas[p.id]}
                onCambio={(v) => responder(p.id, v)}
              />
            )}

            {p.tipo === 'opcion' && (
              <Botones
                opciones={p.opciones}
                valor={respuestas[p.id]}
                onCambio={(v) => responder(p.id, v)}
              />
            )}

            {p.tipo === 'texto' && (
              <textarea
                value={respuestas[p.id] || ''}
                onChange={(e) => responder(p.id, e.target.value)}
                rows={3}
                placeholder="Escribe aquí (opcional)"
                className="w-full rounded-xl border border-[#D6E0F0] px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-[#1A4FA0]"
              />
            )}
          </fieldset>
        ))}

        {error && (
          <div role="alert" className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={enviando}
          className="w-full bg-[#F5A800] hover:bg-[#FFC840] text-[#0D2B5E] font-bold text-lg py-4 rounded-xl shadow-sm transition disabled:opacity-60"
        >
          {enviando ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </Marco>
  )
}

function Marco({ children }) {
  return (
    <div className="min-h-screen bg-[#F7F9FC] py-8 px-4">
      <div className="max-w-md mx-auto bg-white rounded-2xl border border-[#D6E0F0] shadow-sm p-6">
        {children}
      </div>
      <p className="text-center text-xs text-[#9BACC8] mt-6">Protokimica</p>
    </div>
  )
}

/**
 * La calificación de 1 a 5.
 *
 * Cada botón lleva su número además de la estrella: si alguien no distingue
 * las estrellas llenas de las vacías —o la pantalla está al sol— el número
 * sigue diciendo qué eligió.
 */
function Escala({ valor, onCambio }) {
  return (
    <div className="flex gap-2" role="radiogroup">
      {[...Array(ESCALA_MAX)].map((_, i) => {
        const nota = i + 1
        const elegida = valor === nota
        return (
          <button
            key={nota}
            type="button"
            role="radio"
            aria-checked={elegida}
            aria-label={`${nota} de ${ESCALA_MAX}`}
            onClick={() => onCambio(nota)}
            className={`flex-1 aspect-square rounded-xl border-2 flex flex-col items-center justify-center gap-0.5 transition ${
              elegida
                ? 'border-[#1A4FA0] bg-[#1A4FA0] text-white'
                : 'border-[#D6E0F0] bg-white text-[#6B7EA8] hover:border-[#1A4FA0]'
            }`}
          >
            <span className="text-xl leading-none" aria-hidden="true">{elegida ? '★' : '☆'}</span>
            <span className="text-sm font-bold tabular-nums">{nota}</span>
          </button>
        )
      })}
    </div>
  )
}

function Botones({ opciones, valor, onCambio }) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup">
      {opciones.map(o => {
        const elegida = valor === o
        return (
          <button
            key={o}
            type="button"
            role="radio"
            aria-checked={elegida}
            onClick={() => onCambio(o)}
            className={`px-5 py-3 rounded-xl border-2 text-base font-semibold transition ${
              elegida
                ? 'border-[#1A4FA0] bg-[#1A4FA0] text-white'
                : 'border-[#D6E0F0] bg-white text-[#42557A] hover:border-[#1A4FA0]'
            }`}
          >
            {o}
          </button>
        )
      })}
    </div>
  )
}
