import { useState } from 'react'
import { IconoAlDia, IconoAlerta, IconoPapelera } from '../../../core/components/Iconos.jsx'
import { formatValor } from '../constants'
import {
  MAX_ETIQUETA, MAX_VARIABLES, SIMBOLOS, mostrarPieza, numeroDePieza,
  piezasDeTexto, siguienteLetra, textoDePiezas,
} from '../formula'
import { usePruebaFormula } from '../usePruebaFormula'

const boton = 'min-w-9 h-9 px-2.5 rounded-lg border text-sm font-semibold transition-colors duration-150'

/**
 * Armar la fórmula de un indicador con piezas, no escribiéndola.
 *
 * Tres pasos en el orden en que se piensa: qué números se van a digitar cada
 * mes (las variables), cómo se combinan (la fórmula), y una prueba con
 * valores de ejemplo para ver que da lo que se espera ANTES de guardar.
 *
 * La vista en palabras y el resultado de la prueba los calcula el servidor:
 * lo que se ve aquí es lo mismo que va a quedar en el tablero.
 */
export default function ConstructorFormula({ formula, variables, unidad, onCambiar }) {
  const piezas = piezasDeTexto(formula)
  const [numero, setNumero] = useState('')
  const [valoresPrueba, setValoresPrueba] = useState({})

  const cambiarPiezas = (nuevas) => onCambiar({ formula: textoDePiezas(nuevas), variables })
  const agregarPieza = (pieza) => cambiarPiezas([...piezas, pieza])

  const agregarVariable = () => {
    const letra = siguienteLetra(variables)
    if (!letra) return
    onCambiar({ formula, variables: [...variables, { letra, etiqueta: '' }] })
  }
  const renombrar = (letra, etiqueta) => onCambiar({
    formula, variables: variables.map(v => (v.letra === letra ? { ...v, etiqueta } : v)),
  })
  const quitarVariable = (letra) => onCambiar({
    // La quita también de la fórmula: dejarla ahí sería un error que la
    // persona tendría que ir a buscar.
    formula: textoDePiezas(piezas.filter(p => !(p.tipo === 'var' && p.texto === letra))),
    variables: variables.filter(v => v.letra !== letra),
  })

  const agregarNumero = () => {
    const limpio = numeroDePieza(numero)
    if (!limpio) return
    agregarPieza({ tipo: 'num', texto: limpio })
    setNumero('')
  }

  const valores = Object.fromEntries(
    variables.map(v => [v.letra, valoresPrueba[v.letra] === '' || valoresPrueba[v.letra] === undefined
      ? null : Number(String(valoresPrueba[v.letra]).replace(',', '.'))]),
  )
  const { prueba, actualizando } = usePruebaFormula(formula, variables, valores)
  const etiqueta = (letra) => variables.find(v => v.letra === letra)?.etiqueta || letra

  return (
    <div className="bg-superficie-2 rounded-xl p-4 space-y-4">
      {/* 1. Variables */}
      <div>
        <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1">
          Variables <span className="normal-case font-normal text-texto-3">· lo que se digita cada mes</span>
        </p>
        <div className="space-y-2">
          {variables.map(v => (
            <div key={v.letra} className="flex items-center gap-2">
              <span className="cifra w-8 h-8 shrink-0 rounded-lg bg-acento text-white text-sm font-bold flex items-center justify-center">
                {v.letra}
              </span>
              <input
                value={v.etiqueta}
                onChange={(e) => renombrar(v.letra, e.target.value)}
                maxLength={MAX_ETIQUETA}
                placeholder="Qué se cuenta, ej: Quejas atendidas a tiempo"
                aria-label={`Nombre de la variable ${v.letra}`}
                className="flex-1 min-w-0 rounded-lg border border-borde bg-white px-3 py-2 text-sm"
              />
              <button
                type="button"
                onClick={() => quitarVariable(v.letra)}
                aria-label={`Quitar la variable ${v.letra}`}
                className="p-2 rounded-lg text-texto-3 hover:text-negativo hover:bg-negativo-bg transition-colors duration-150"
              >
                <IconoPapelera tam={15} />
              </button>
            </div>
          ))}
        </div>
        {variables.length < MAX_VARIABLES && (
          <button
            type="button"
            onClick={agregarVariable}
            className="mt-2 text-sm font-semibold text-acento hover:underline"
          >
            + Agregar variable
          </button>
        )}
      </div>

      {/* 2. Fórmula */}
      <div>
        <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-1">Fórmula</p>
        <div className="min-h-12 bg-white border border-borde rounded-lg px-2 py-2 flex flex-wrap items-center gap-1.5">
          {piezas.length === 0 && (
            <span className="text-sm text-texto-3 px-1">Usa los botones de abajo para armarla.</span>
          )}
          {piezas.map((p, i) => (
            <span
              key={i}
              title={p.tipo === 'var' ? etiqueta(p.texto) : undefined}
              className={`cifra inline-flex items-center justify-center h-8 min-w-8 px-2 rounded-md text-sm font-semibold ${
                p.tipo === 'var' ? 'bg-acento text-white'
                  : p.tipo === 'num' ? 'bg-acento-suave text-acento-fuerte'
                    : 'text-texto'
              }`}
            >
              {mostrarPieza(p)}
            </span>
          ))}
          {piezas.length > 0 && (
            <div className="ml-auto flex gap-1">
              <button type="button" onClick={() => cambiarPiezas(piezas.slice(0, -1))}
                className="text-xs font-semibold text-texto-2 hover:text-texto px-2 py-1 rounded hover:bg-superficie-2">
                Borrar último
              </button>
              <button type="button" onClick={() => cambiarPiezas([])}
                className="text-xs font-semibold text-texto-2 hover:text-negativo px-2 py-1 rounded hover:bg-negativo-bg">
                Limpiar
              </button>
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 mt-2">
          {variables.map(v => (
            <button key={v.letra} type="button" title={v.etiqueta || `Variable ${v.letra}`}
              onClick={() => agregarPieza({ tipo: 'var', texto: v.letra })}
              className={`${boton} border-acento/40 bg-white text-acento hover:bg-acento-suave`}>
              {v.letra}
            </button>
          ))}
          <span className="w-px h-6 bg-borde mx-1" aria-hidden="true" />
          {Object.entries(SIMBOLOS).map(([op, simbolo]) => (
            <button key={op} type="button" onClick={() => agregarPieza({ tipo: 'op', texto: op })}
              aria-label={{ '+': 'Sumar', '-': 'Restar', '*': 'Multiplicar', '/': 'Dividir' }[op]}
              className={`${boton} border-borde bg-white text-texto hover:bg-superficie-2`}>
              {simbolo}
            </button>
          ))}
          <button type="button" onClick={() => agregarPieza({ tipo: 'abre', texto: '(' })}
            aria-label="Abrir paréntesis" className={`${boton} border-borde bg-white text-texto hover:bg-superficie-2`}>(</button>
          <button type="button" onClick={() => agregarPieza({ tipo: 'cierra', texto: ')' })}
            aria-label="Cerrar paréntesis" className={`${boton} border-borde bg-white text-texto hover:bg-superficie-2`}>)</button>
          <span className="w-px h-6 bg-borde mx-1" aria-hidden="true" />
          <div className="flex items-center gap-1">
            <input
              value={numero}
              onChange={(e) => setNumero(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); agregarNumero() } }}
              inputMode="decimal"
              placeholder="Número"
              aria-label="Número para agregar a la fórmula"
              className="cifra w-24 h-9 rounded-lg border border-borde bg-white px-2 text-sm"
            />
            <button type="button" onClick={agregarNumero} disabled={!numeroDePieza(numero)}
              className={`${boton} border-borde bg-white text-acento hover:bg-acento-suave disabled:opacity-40`}>
              Agregar
            </button>
          </div>
        </div>
      </div>

      {/* En palabras, o qué corregir. Lo dice el servidor. */}
      {piezas.length > 0 && prueba && (
        prueba.valida ? (
          <div className="flex items-start gap-2 bg-white border border-positivo/25 rounded-lg px-3 py-2.5">
            <IconoAlDia tam={16} className="text-positivo mt-0.5" />
            <p className="text-sm text-texto">
              <span className="text-texto-2">Resultado =</span> {prueba.legible}
            </p>
          </div>
        ) : (
          <div role="alert" className="flex items-start gap-2 bg-alerta-bg border border-ambar/30 rounded-lg px-3 py-2.5">
            <IconoAlerta tam={16} className="text-alerta mt-0.5" />
            <p className="text-sm text-texto">{prueba.error}</p>
          </div>
        )
      )}

      {unidad === 'porcentaje' && (
        <p className="text-[11px] text-texto-3">
          El resultado es exactamente lo que da la fórmula. Si es un porcentaje, inclúyele × 100.
        </p>
      )}

      {/* 3. Probar con valores de ejemplo */}
      {prueba?.valida && variables.length > 0 && (
        <div className="bg-white border border-borde rounded-lg p-3">
          <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide mb-2">
            Pruébala con valores de ejemplo
          </p>
          <div className="grid grid-cols-2 gap-2">
            {variables.map(v => (
              <label key={v.letra} className="block">
                <span className="block text-[11px] text-texto-2 mb-0.5 truncate">
                  <span className="cifra font-bold text-acento">{v.letra}</span> · {v.etiqueta || 'sin nombre'}
                </span>
                <input
                  value={valoresPrueba[v.letra] ?? ''}
                  onChange={(e) => setValoresPrueba({ ...valoresPrueba, [v.letra]: e.target.value })}
                  inputMode="decimal"
                  className="cifra w-full rounded-lg border border-borde px-2 py-1.5 text-sm"
                />
              </label>
            ))}
          </div>
          <p className="text-sm mt-2">
            <span className="text-texto-2">Daría: </span>
            <strong className="cifra text-acento-fuerte">
              {prueba.divide_por_cero
                ? 'sin dato (divide por cero)'
                : prueba.resultado !== null && prueba.resultado !== undefined
                  ? formatValor(Math.round(prueba.resultado * 100) / 100, unidad)
                  : 'completa los valores'}
            </strong>
            {actualizando && <span className="text-xs text-texto-3"> · calculando…</span>}
          </p>
        </div>
      )}
    </div>
  )
}
