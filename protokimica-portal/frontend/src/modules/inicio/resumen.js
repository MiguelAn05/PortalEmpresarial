/**
 * Reglas del inicio que se pueden probar sin pintar nada.
 *
 * Vive en un .js sin JSX a propósito: es lo que se rompe en silencio —un
 * plazo mal contado, una tarjeta en el orden equivocado— y no se nota hasta
 * que alguien se queja de que "ayer decía otra cosa".
 */

/** Saludo según la hora. Recibe la fecha para poder probarse. */
export function saludo(fecha = new Date()) {
  const h = fecha.getHours()
  if (h < 12) return 'Buenos días'
  if (h < 19) return 'Buenas tardes'
  return 'Buenas noches'
}

/**
 * Qué tan cerca está un plazo, en palabras.
 *
 * Se cuenta por días de calendario, no por horas: algo que vence hoy a las
 * 8 a.m. y algo que vence hoy a las 6 p.m. son los dos "hoy" para quien lo
 * lee. Contar horas haría que una tarea de esta tarde apareciera como
 * "vence mañana" solo por caer a más de 24 horas.
 */
export function plazoRelativo(iso, ahora = new Date()) {
  if (!iso) return { texto: 'Sin fecha', vencido: false, urgente: false }

  const aMedianoche = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const dias = Math.round(
    (aMedianoche(new Date(iso)) - aMedianoche(ahora)) / 86400000,
  )

  if (dias < 0) {
    const n = Math.abs(dias)
    return { texto: n === 1 ? 'Venció ayer' : `Venció hace ${n} días`, vencido: true, urgente: true }
  }
  if (dias === 0) return { texto: 'Vence hoy', vencido: false, urgente: true }
  if (dias === 1) return { texto: 'Vence mañana', vencido: false, urgente: true }
  return { texto: `Vence en ${dias} días`, vencido: false, urgente: false }
}

/**
 * En qué orden se apilan las tarjetas.
 *
 * Gerencia entra a leer los números; los demás entran a trabajar. Mandar a
 * todos a la misma pantalla obliga a la mitad a bajar cada vez que abren el
 * portal. Es la misma decisión que `pestanaInicial` en Indicadores.
 */
export function ordenTarjetas(usuario) {
  return usuario?.rol === 'gerencia'
    ? ['empresa', 'pendientes', 'area', 'accesos']
    : ['pendientes', 'accesos', 'area', 'empresa']
}

/**
 * El tono de la tarjeta de pendientes. Nunca es solo color: quien lo lee
 * recibe además el texto, porque el ámbar de la marca no alcanza el
 * contraste mínimo sobre blanco.
 */
export function tonoPendientes(inicio) {
  if (!inicio) return { borde: 'border-t-[#D6E0F0]', titulo: 'Lo que te toca hoy' }
  if (inicio.total_urgente > 0) {
    return {
      borde: 'border-t-[#D93B3B]',
      titulo: `Tienes ${inicio.total_urgente} ${inicio.total_urgente === 1 ? 'cosa vencida' : 'cosas vencidas'}`,
    }
  }
  if (inicio.total_pendiente > 0) {
    return { borde: 'border-t-[#F5A800]', titulo: 'Lo que te toca esta semana' }
  }
  return { borde: 'border-t-[#2E9E6B]', titulo: 'Estás al día' }
}

/** El nombre de pila basta para saludar; el completo satura el encabezado. */
export function primerNombre(nombre) {
  if (!nombre) return ''
  return String(nombre).trim().split(/\s+/)[0]
}
