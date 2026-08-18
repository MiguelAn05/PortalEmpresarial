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

export default function TarjetasKPI({ tarjetas }) {
  return (
    <div className={`grid grid-cols-2 gap-4 ${COLUMNAS[tarjetas.length] ?? 'md:grid-cols-4'}`}>
      {tarjetas.map(({ label, value, nota, alerta }) => (
        <article
          key={label}
          className="bg-superficie rounded-xl border border-borde shadow-sm p-4
            transition-shadow duration-150 ease-suave hover:shadow-md"
        >
          <div className="etiqueta truncate">{label}</div>
          <div className={`cifra text-[28px] leading-none font-semibold tracking-tight mt-2
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
        </article>
      ))}
    </div>
  )
}
