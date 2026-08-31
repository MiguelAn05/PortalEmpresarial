/**
 * La geometría de la gráfica de ejecución presupuestal.
 *
 * Vive aparte del componente porque es donde se rompen las gráficas hechas a
 * mano: una escala que no cubre el valor más alto recorta la barra sin avisar,
 * y una división por cero deja la pantalla en blanco el día que un mes no
 * tiene movimiento. Eso se prueba; el SVG se mira.
 *
 * No se usa librería de gráficas a propósito: el servidor no reinstala
 * dependencias con fiabilidad (misma razón que los iconos).
 */

/** Los cortes del eje vertical, en números redondos. */
const PASOS = [1, 2, 2.5, 5, 10]

/**
 * Escala del eje Y: hasta dónde llega y dónde van las líneas.
 *
 * El tope SIEMPRE queda por encima del valor más alto —si no, la barra más
 * alta se sale del área— y cae en un número redondo, porque "$ 40 M" se lee
 * y "$ 36,4 M" obliga a hacer cuentas.
 */
export function escalaY(maximo, divisiones = 4) {
  if (!Number.isFinite(maximo) || maximo <= 0) {
    return { tope: 0, ticks: [0] }
  }

  const bruto = maximo / divisiones
  const magnitud = 10 ** Math.floor(Math.log10(bruto))
  const normalizado = bruto / magnitud
  const paso = (PASOS.find(p => normalizado <= p) ?? 10) * magnitud

  const tope = paso * divisiones
  const ticks = []
  for (let i = 0; i <= divisiones; i++) ticks.push(paso * i)
  return { tope, ticks }
}

/** El valor más alto de toda la serie, mirando las dos medidas. */
export function maximoDeLaSerie(serie) {
  return (serie || []).reduce(
    (mayor, punto) => Math.max(mayor, punto.aprobado || 0, punto.pagado || 0),
    0,
  )
}

/** ¿Hay algo que dibujar? Un mes sin movimiento no es lo mismo que sin datos. */
export function hayMovimiento(serie) {
  return maximoDeLaSerie(serie) > 0
}

/**
 * Dónde va cada barra dentro del área de dibujo.
 *
 * Devuelve coordenadas ya resueltas para que el componente solo las pinte.
 * Las dos barras de un mes van LADO A LADO, nunca una encima de la otra:
 * lo aprobado en marzo puede pagarse en mayo, así que una no contiene a la
 * otra y superponerlas afirmaría algo falso.
 */
export function geometriaBarras(serie, { ancho, alto, anchoBarra = 14, separacion = 2 }) {
  const puntos = serie || []
  if (!puntos.length || ancho <= 0 || alto <= 0) return []

  const { tope } = escalaY(maximoDeLaSerie(puntos))
  const anchoGrupo = ancho / puntos.length
  const anchoPar = anchoBarra * 2 + separacion

  // Con el tope en cero todas las barras miden cero: se dibuja la línea base
  // y ya. Sin este guarda, dividir por el tope da NaN y el SVG desaparece.
  const altoDe = (valor) => (tope > 0 ? Math.max(0, ((valor || 0) / tope) * alto) : 0)

  return puntos.map((punto, i) => {
    const centro = anchoGrupo * i + anchoGrupo / 2
    const izquierda = centro - anchoPar / 2
    const altoAprobado = altoDe(punto.aprobado)
    const altoPagado = altoDe(punto.pagado)

    return {
      ...punto,
      centro,
      grupoX: anchoGrupo * i,
      anchoGrupo,
      aprobadoRect: {
        x: izquierda, y: alto - altoAprobado, ancho: anchoBarra, alto: altoAprobado,
      },
      pagadoRect: {
        x: izquierda + anchoBarra + separacion, y: alto - altoPagado,
        ancho: anchoBarra, alto: altoPagado,
      },
    }
  })
}

/**
 * El contorno de una barra con las esquinas de ARRIBA redondeadas.
 *
 * Un `<rect rx>` redondea las cuatro y la barra se despega de la línea base,
 * como si flotara. El dato empieza en el cero y eso tiene que verse.
 */
export function contornoBarra({ x, y, ancho, alto }, radio = 3) {
  if (alto <= 0) return ''
  const r = Math.min(radio, ancho / 2, alto)
  const base = y + alto
  return [
    `M${x} ${base}`,
    `V${y + r}`,
    `A${r} ${r} 0 0 1 ${x + r} ${y}`,
    `H${x + ancho - r}`,
    `A${r} ${r} 0 0 1 ${x + ancho} ${y + r}`,
    `V${base}`,
    'Z',
  ].join(' ')
}
