/**
 * El vocabulario de las Oportunidades de Mejora.
 *
 * Los estados, cómo se llaman en pantalla y qué se puede hacer desde cada
 * uno. Vive sin JSX para poder probarlo: el paso siguiente de una OMP es
 * justo lo que se rompe en silencio cuando alguien agrega un estado y se le
 * olvida un sitio.
 *
 * Ojo: aquí se decide qué se OFRECE, no qué se permite. El permiso de verdad
 * lo impone el servidor —`modules/mejora/service.py`— y esconder un botón no
 * impide llamar a la API. Esto es cortesía, para no ofrecer algo que va a
 * responder 400.
 */

export const ESTADOS = {
  abierta: {
    label: 'Abierta',
    tono: 'neutro',
    ayuda: 'Registrada. Falta entender por qué pasó.',
  },
  analisis: {
    label: 'En análisis',
    tono: 'info',
    ayuda: 'Buscando la causa raíz antes de actuar.',
  },
  ejecucion: {
    label: 'En ejecución',
    tono: 'alerta',
    ayuda: 'Las acciones están en marcha.',
  },
  verificacion: {
    label: 'En verificación',
    tono: 'info',
    ayuda: 'Comprobando si el indicador mejoró.',
  },
  cerrada: {
    label: 'Cerrada',
    tono: 'positivo',
    ayuda: 'Verificada y terminada.',
  },
  descartada: {
    label: 'Descartada',
    tono: 'neutro',
    ayuda: 'Se evaluó y no se siguió. Queda el registro.',
  },
}

/** El orden del ciclo. `descartada` no está: es una salida, no un paso. */
export const CICLO = ['abierta', 'analisis', 'ejecucion', 'verificacion', 'cerrada']

export const ORIGENES = {
  indicador: 'Un indicador que no cumplió',
  pqrs: 'Una PQRS',
  auditoria: 'Una auditoría',
  sugerencia: 'Una sugerencia',
  otro: 'Otro',
}

export const PRIORIDADES = {
  baja: { label: 'Baja', tono: 'neutro' },
  media: { label: 'Media', tono: 'info' },
  alta: { label: 'Alta', tono: 'alerta' },
  critica: { label: 'Crítica', tono: 'negativo' },
}

/** Una OMP terminada ya no se mueve ni admite acciones nuevas. */
export function estaCerrada(omp) {
  return omp?.estado === 'cerrada' || omp?.estado === 'descartada'
}

/**
 * El siguiente paso del ciclo, o null si no hay.
 *
 * Solo se avanza de a uno: saltarse la verificación es exactamente lo que
 * hace que un registro de mejora no sirva como evidencia.
 */
export function siguienteEstado(omp) {
  if (!omp || estaCerrada(omp)) return null
  const i = CICLO.indexOf(omp.estado)
  return i >= 0 && i < CICLO.length - 1 ? CICLO[i + 1] : null
}

/**
 * Qué falta para poder dar el siguiente paso, en palabras.
 *
 * Devuelve null cuando no falta nada. Se dice ANTES de que la persona toque
 * el botón: enterarse de que falta la causa raíz por un mensaje de error, con
 * el formulario ya cerrado, es la forma más rápida de que alguien abandone
 * el módulo y vuelva al Excel.
 */
export function loQueFaltaPara(omp, estado) {
  if (estado === 'ejecucion' && !(omp?.causa_raiz || '').trim()) {
    return 'Escribe la causa raíz antes de pasar a ejecución.'
  }
  if (estado === 'verificacion' && !omp?.total_acciones) {
    return 'Agrega al menos una acción: sin acciones no hay nada que verificar.'
  }
  if (estado === 'cerrada' && (omp?.eficaz === null || omp?.eficaz === undefined)) {
    return 'Registra la verificación de eficacia antes de cerrar.'
  }
  return null
}

/** El texto del botón que avanza el ciclo. */
export function textoDeAvance(estado) {
  return {
    analisis: 'Pasar a análisis',
    ejecucion: 'Pasar a ejecución',
    verificacion: 'Pasar a verificación',
    cerrada: 'Cerrar la oportunidad',
  }[estado] ?? 'Avanzar'
}

/**
 * Cómo va una OMP frente a su fecha límite.
 *
 * Una cerrada nunca está vencida aunque la fecha haya pasado: terminó, y
 * pintarla de rojo para siempre solo entrena a la gente a ignorar el rojo.
 */
export function estadoDelPlazo(omp, ahora = new Date()) {
  if (!omp?.fecha_limite || estaCerrada(omp)) return 'sin_plazo'

  const aMedianoche = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())
  const dias = Math.round(
    (aMedianoche(new Date(omp.fecha_limite)) - aMedianoche(ahora)) / 86400000,
  )
  if (dias < 0) return 'vencida'
  if (dias <= 3) return 'por_vencer'
  return 'en_plazo'
}

/**
 * Tope de caracteres de una acción del plan.
 *
 * Es el mismo `max_length` que declara `AccionCrear` en el backend. Sin este
 * límite en el input, escribir de más devolvía un 422 — y como el detalle de
 * un 422 es una lista de objetos, la página se quedaba en blanco en vez de
 * avisar. El tope aquí evita que el error llegue a ocurrir.
 *
 * Si algún día se amplía en el schema, hay que subirlo aquí también.
 */
export const MAX_ACCION = 300
