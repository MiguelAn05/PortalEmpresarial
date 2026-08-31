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
 *
 * Los accesos rápidos van SIEMPRE al final: son un atajo para quien ya sabe
 * a dónde va, no información. Ponerlos arriba empujaba hacia abajo lo único
 * que hay que leer. Y «cómo va la empresa» queda de segundo para todos, que
 * es la pregunta que sigue después de «qué me toca a mí».
 */
export function ordenTarjetas(usuario) {
  return usuario?.rol === 'gerencia'
    ? ['empresa', 'pendientes', 'area', 'accesos']
    : ['pendientes', 'empresa', 'area', 'accesos']
}

/**
 * El tono de la tarjeta de pendientes. Nunca es solo color: quien lo lee
 * recibe además el texto, porque el ámbar de la marca no alcanza el
 * contraste mínimo sobre blanco.
 *
 * Devuelve el nombre del estado, no una clase de CSS: esta función decide
 * *qué tan grave es*, y de pintarlo se encarga el componente. Cuando devolvía
 * una clase de Tailwind con el rojo adentro, la paleta vivía repartida
 * entre archivos de lógica.
 */
export function tonoPendientes(inicio) {
  if (!inicio) return { tono: 'neutro', titulo: 'Lo que te toca hoy' }
  if (inicio.total_urgente > 0) {
    return {
      tono: 'negativo',
      titulo: `Tienes ${inicio.total_urgente} ${inicio.total_urgente === 1 ? 'cosa vencida' : 'cosas vencidas'}`,
    }
  }
  if (inicio.total_pendiente > 0) {
    return { tono: 'alerta', titulo: 'Lo que te toca esta semana' }
  }
  return { tono: 'positivo', titulo: 'Estás al día' }
}

/**
 * El monto corto de una tarjeta de resumen: `$ 36,0 M`.
 *
 * En una tarjeta de 220px un `$ 67.500.770` completo obliga a bajar la cifra
 * a un tamaño que ya no se lee de un vistazo. El valor exacto no se pierde:
 * va en el `title` de la tarjeta.
 */
export function montoCorto(valor) {
  if (valor === null || valor === undefined) return '—'
  const n = Number(valor)
  if (!Number.isFinite(n)) return '—'
  if (Math.abs(n) < 1000000) return `$ ${Math.round(n).toLocaleString('es-CO')}`
  return `$ ${(n / 1000000).toLocaleString('es-CO', {
    minimumFractionDigits: 1, maximumFractionDigits: 1,
  })} M`
}

/** El nombre de pila basta para saludar; el completo satura el encabezado. */
export function primerNombre(nombre) {
  if (!nombre) return ''
  return String(nombre).trim().split(/\s+/)[0]
}
