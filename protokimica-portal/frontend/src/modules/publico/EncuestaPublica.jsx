import { useState } from "react"
import { useParams, useSearchParams } from "react-router-dom"
import { useQuery } from "@tanstack/react-query"
import { obtenerEncuestaPublica, responderEncuestaPublica } from "../encuestas/api"
import { ESCALA_MAX } from "../encuestas/constants"
import {
  IconoBuscar, IconoCheck, IconoEstrella,
} from '../../core/components/Iconos.jsx'

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
  const [sujeto, setSujeto] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [listo, setListo] = useState(null)   // mensaje final cuando ya respondió

  const { data: encuesta, isLoading, isError } = useQuery({
    queryKey: ["encuesta-publica", slug],
    queryFn: () => obtenerEncuestaPublica(slug),
    retry: false,
  })

  // El enlace del QR puede traer ya a quién califica; si lo trae, no se le
  // pregunta nada al cliente, que es lo más limpio de todo. Si no, y la
  // encuesta tiene lista, se elige de ahí — nunca se escribe a mano.
  const hayQueElegirSujeto = !params.get('nombre') && (encuesta?.sujetos?.length > 0)

  const responder = (preguntaId, valor) => {
    setRespuestas(r => ({ ...r, [preguntaId]: valor }))
    setError('')
  }

  const enviar = async (e) => {
    e.preventDefault()
    setError('')

    // Si la encuesta trae lista y el enlace no dice a quién califica, hay
    // que elegirlo. Escribirlo a mano no es opción: el reporte por punto de
    // venta se rompe con cada variante de escritura.
    if (hayQueElegirSujeto && !sujeto) {
      setError(`Elige ${encuesta.sujeto_tipo || 'una opción'} de la lista.`)
      return
    }

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
        sujeto_nombre: params.get('nombre') || sujeto || null,
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
    return <Marco><p className="text-center text-texto-2 py-12">Cargando...</p></Marco>
  }

  if (isError) {
    return (
      <Marco>
        <div className="text-center py-10">
          <p className="flex justify-center mb-3 text-texto-3" aria-hidden="true">
            <IconoBuscar tam={30} />
          </p>
          <h1 className="text-xl font-semibold text-texto mb-2">Encuesta no disponible</h1>
          <p className="text-texto-2 text-sm">
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
          <p className="flex justify-center mb-4" aria-hidden="true">
            <span className="w-14 h-14 rounded-full bg-positivo-bg text-positivo
              flex items-center justify-center">
              <IconoCheck tam={26} />
            </span>
          </p>
          <h1 className="text-2xl font-semibold text-texto mb-2">¡Listo!</h1>
          <p className="text-texto-2">{listo}</p>
        </div>
      </Marco>
    )
  }

  const quien = params.get('nombre')

  return (
    <Marco>
      <form onSubmit={enviar} className="space-y-6">
        <header>
          <h1 className="text-2xl font-bold text-acento-fuerte">{encuesta.nombre}</h1>
          {encuesta.descripcion && (
            <p className="text-texto-2 mt-1 text-sm">{encuesta.descripcion}</p>
          )}
          {quien && (
            <p className="mt-3 inline-block bg-superficie-2 border border-borde rounded-full px-3 py-1 text-sm text-texto-2">
              Estás calificando a <b>{quien}</b>
            </p>
          )}
        </header>

        {/* Lista cerrada, nunca texto libre: cada forma distinta de escribir
            el mismo punto de venta lo convertiría en otro lugar en el reporte. */}
        {hayQueElegirSujeto && (
          <fieldset className="border-0 p-0 m-0">
            <legend className="text-base font-semibold text-texto mb-2">
              ¿{encuesta.sujeto_tipo ? `Cuál ${encuesta.sujeto_tipo}` : 'Dónde'} te atendió?
              <span className="text-negativo-vivo ml-1" aria-hidden="true">*</span>
            </legend>
            <select
              value={sujeto}
              onChange={(e) => { setSujeto(e.target.value); setError('') }}
              className="w-full rounded-xl border border-borde px-4 py-3 text-base bg-white focus:outline-none focus:ring-2 focus:ring-acento"
            >
              <option value="">Selecciona una opción</option>
              {encuesta.sujetos.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </fieldset>
        )}

        {encuesta.preguntas.map(p => (
          <fieldset key={p.id} className="border-0 p-0 m-0">
            <legend className="text-base font-semibold text-texto mb-2">
              {p.texto}
              {p.obligatoria && <span className="text-negativo-vivo ml-1" aria-hidden="true">*</span>}
            </legend>
            {p.ayuda && <p className="text-xs text-texto-3 mb-2 -mt-1">{p.ayuda}</p>}

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
                className="w-full rounded-xl border border-borde px-4 py-3 text-base focus:outline-none focus:ring-2 focus:ring-acento"
              />
            )}
          </fieldset>
        ))}

        {error && (
          <div role="alert" className="bg-negativo-bg border border-negativo/25 text-negativo text-sm rounded-xl px-4 py-3">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={enviando}
          className="w-full bg-ambar hover:bg-ambar-claro text-acento-fuerte font-bold text-lg py-4 rounded-xl shadow-sm transition disabled:opacity-60"
        >
          {enviando ? 'Enviando...' : 'Enviar'}
        </button>
      </form>
    </Marco>
  )
}

function Marco({ children }) {
  return (
    <div className="min-h-screen bg-superficie-2 py-8 px-4">
      <div className="max-w-md mx-auto bg-white rounded-2xl border border-borde shadow-sm p-6">
        {children}
      </div>
      <p className="text-center text-xs text-texto-3 mt-6">Protokimica</p>
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
            className={`flex-1 aspect-square rounded-xl border-2 flex flex-col items-center
              justify-center gap-0.5 transition-colors duration-150 ease-suave ${
              elegida
                ? 'border-acento bg-acento text-white'
                : 'border-borde bg-superficie text-texto-3 hover:border-acento'
            }`}
          >
            <IconoEstrella tam={20} relleno={elegida} />
            <span className="cifra text-sm font-semibold">{nota}</span>
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
                ? 'border-acento bg-acento text-white'
                : 'border-borde bg-white text-texto-2 hover:border-acento'
            }`}
          >
            {o}
          </button>
        )
      })}
    </div>
  )
}
