/**
 * La fila de cifras de resumen. La usan Master Planner, PQRS e Inicio, y por
 * eso vive en `core`: es el mismo lenguaje visual en los tres, no una copia
 * por módulo que se va separando con cada retoque.
 *
 * Ya no llevan borde superior de color. Cinco tarjetas con cinco colores
 * distintos convierten la fila en un tablero de bingo donde ninguna resalta;
 * el color quedó reservado para lo que de verdad es una señal —lo vencido, lo
 * que está en riesgo— y la jerarquía la hacen el tamaño y la elevación.
 *
 * Cada tarjeta lleva `nota`: un número sin contexto obliga a preguntar
 * «¿eso es bueno?». Un cero que es *buena* noticia debe decirlo con palabras
 * («ninguna fuera de plazo»), porque un 0 pelado se lee como «no hay datos».
 */

// Cuántas caben por fila en pantalla ancha. Van escritas enteras porque
// Tailwind lee las clases del código: `grid-cols-${n}` no existiría.
const COLUMNAS = {
  3: 'md:grid-cols-3',
  4: 'md:grid-cols-4',
  5: 'md:grid-cols-3 xl:grid-cols-5',
}

/**
 * Una tarjeta puede ser solo una cifra o, si trae `onClick`, un filtro.
 *
 * Es opcional a propósito: donde la cifra no lleva a ninguna parte —el
 * resumen de un proyecto, por ejemplo— una tarjeta que se puede pulsar solo
 * genera la pregunta de qué hace. Sin `onClick` se pinta un `<article>`, sin
 * cursor de mano y sin foco de teclado, exactamente como antes.
 */
// Con `conPrincipal`, la primera tarjeta es más ancha: es la cifra que se
// lee primero (en PQRS, las abiertas) y las demás la desglosan.
const COLUMNAS_PRINCIPAL = {
  3: 'md:grid-cols-[1.8fr_1fr_1fr]',
  4: 'md:grid-cols-[1.8fr_1fr_1fr_1fr]',
}

// El punto del rótulo dice qué clase de cifra es antes de leerla. Es opcional
// y nunca va solo: la etiqueta sigue diciendo lo mismo con palabras.
const PUNTOS = {
  negativo: 'bg-negativo-vivo',
  alerta: 'bg-ambar',
  positivo: 'bg-positivo-vivo',
  neutro: 'bg-texto-3',
}

export default function TarjetasKPI({ tarjetas, conPrincipal = false }) {
  const columnas = (conPrincipal && COLUMNAS_PRINCIPAL[tarjetas.length])
    || COLUMNAS[tarjetas.length] || 'md:grid-cols-4'
  return (
    <div className={`grid grid-cols-2 gap-4 ${columnas}`}>
      {tarjetas.map(({ label, value, nota, alerta, onClick, activa, punto }, i) => {
        const principal = conPrincipal && i === 0
        const Caja = onClick ? 'button' : 'article'
        const interactiva = onClick
          ? 'text-left w-full cursor-pointer hover:border-borde-fuerte'
          : ''
        // La tarjeta activa se marca con borde y anillo, no solo con un tono
        // de fondo: es el estado que dice POR QUÉ la lista de abajo está
        // recortada, y perderlo de vista deja a alguien creyendo que faltan
        // PQRS.
        const marcada = activa ? 'border-acento ring-1 ring-acento' : 'border-borde'

        return (
          <Caja
            key={label}
            onClick={onClick}
            {...(onClick ? { type: 'button', 'aria-pressed': Boolean(activa) } : {})}
            className={`bg-superficie rounded-xl border shadow-sm p-4
              transition-shadow duration-150 ease-suave hover:shadow-md
              ${marcada} ${interactiva}`}
          >
            <div className="etiqueta truncate flex items-center gap-1.5">
              {punto && <span aria-hidden="true" className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PUNTOS[punto]}`} />}
              {label}
            </div>
            <div className={`cifra ${principal ? 'text-[34px]' : 'text-[28px]'} leading-none font-semibold tracking-tight mt-2
              ${alerta ? 'text-negativo' : 'text-texto'}`}>
              {value}
            </div>
            {nota && (
              <div className={`flex items-center gap-1.5 text-[11px] mt-2
                ${alerta ? 'text-negativo font-medium' : 'text-texto-3'}`}>
                {/* Punto y palabra: el rojo solo no se lee en voz alta. */}
                {alerta && (
                  <span className="w-1.5 h-1.5 rounded-full bg-current flex-shrink-0" aria-hidden="true" />
                )}
                <span className="truncate">{nota}</span>
              </div>
            )}
          </Caja>
        )
      })}
    </div>
  )
}
