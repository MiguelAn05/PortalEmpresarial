/**
 * El botón del portal, con su estado de espera dentro.
 *
 * Existe por una razón concreta: el spinner tiene que vivir DENTRO del botón
 * que lo disparó. Un overlay de pantalla completa para guardar un formulario
 * tapa justamente lo que la persona acaba de escribir, y un botón que sigue
 * pulsable mientras la petición viaja termina en dos registros iguales — que
 * es como aparecen las notas crédito duplicadas.
 *
 * Mientras `cargando` está activo el botón queda inerte (`disabled`) y anuncia
 * `aria-busy`, así que quien usa lector de pantalla se entera de que algo está
 * pasando sin tener que adivinar por el color.
 *
 * El ancho NO cambia al entrar en espera: el texto de carga sustituye al
 * normal y el botón conserva su tamaño. Si se encogiera, los botones de al
 * lado se moverían justo cuando alguien va a hacer clic en ellos.
 */
import { Spinner } from './Cargando.jsx'

// Los tonos salen de index.css, nunca de un hex. `primario` es la acción de
// la pantalla —una sola por vista—, `secundario` todo lo demás, y `peligro`
// lo que no se puede deshacer.
const TONOS = {
  primario: 'bg-acento-fuerte text-white border-transparent shadow-xs hover:bg-acento',
  secundario: 'bg-superficie text-texto border-borde-fuerte hover:bg-superficie-2',
  marca: 'bg-ambar text-acento-fuerte border-transparent shadow-xs hover:bg-ambar-claro',
  peligro: 'bg-negativo text-white border-transparent shadow-xs hover:brightness-110',
  fantasma: 'bg-transparent text-texto-2 border-transparent hover:bg-superficie-2',
}

// Altura mínima de 36 px: es el área táctil que se puede acertar con el dedo
// sin ampliar la página.
const TAMANOS = {
  sm: 'h-8 px-3 text-xs gap-1.5',
  md: 'h-9 px-3.5 text-sm gap-2',
  lg: 'h-11 px-5 text-sm gap-2',
}

export default function Boton({
  children,
  tono = 'secundario',
  tam = 'md',
  cargando = false,
  textoCargando,
  icono: Icono,
  className = '',
  disabled,
  type = 'button',
  ...resto
}) {
  const claro = tono === 'primario' || tono === 'peligro'

  return (
    <button
      type={type}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      className={`inline-flex items-center justify-center rounded-lg border font-semibold
        whitespace-nowrap transition duration-150 ease-suave
        disabled:opacity-50 disabled:cursor-not-allowed
        ${TONOS[tono]} ${TAMANOS[tam]} ${className}`}
      {...resto}
    >
      {cargando
        ? <><Spinner claro={claro} tam={tam === 'sm' ? 13 : 15} />{textoCargando || children}</>
        : <>{Icono && <Icono tam={tam === 'sm' ? 14 : 16} />}{children}</>}
    </button>
  )
}
