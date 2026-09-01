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
 *
 * Los catálogos del formato (proceso, fuente, tratamiento) NO están aquí:
 * son tablas que Calidad administra, y se piden a `/mejora/catalogos`. Lo
 * único que se queda quemado es el CÓDIGO del tratamiento, porque de él
 * cuelga qué campos aplican y renombrarlo desde Admin no puede cambiar eso.
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
    ayuda: 'Verificada, validada por Calidad y terminada.',
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

/**
 * Riesgo u oportunidad (columna K del formato).
 *
 * Va quemado y no en el catálogo porque no es un parámetro de la empresa:
 * cambiarlo no sería configurar el portal, sería cambiar la norma.
 */
export const CLASIFICACIONES = {
  riesgo: 'Un riesgo que hay que controlar',
  oportunidad: 'Una oportunidad que hay que aprovechar',
}

/**
 * Los códigos de tratamiento y qué significa cada uno.
 *
 * El NOMBRE lo administra Calidad y puede cambiar; el código no. Todo lo que
 * dependa del tratamiento se decide por código — el histórico del Excel ya
 * trae «Acción de mejora» y «Acción de Mejora» escritos distinto.
 */
export const TRATAMIENTOS = {
  OMP: 'Algo que se puede hacer mejor, sin que nadie haya incumplido.',
  AC: 'Algo falló: primero se corrige, y aparte se ataca la causa.',
  AM: 'No hay problema que resolver; se hace porque deja un beneficio.',
}

/**
 * Las 6M del análisis de causas, en el orden en que el formato las imprime.
 *
 * Son campos separados y no un textarea porque en el Excel ya venían estas
 * mismas etiquetas escritas a mano dentro de la celda: la estructura existía,
 * solo que sin nada que la garantizara.
 */
export const CAMPOS_6M = [
  { campo: 'causa_efecto', label: 'Efecto', ayuda: 'Qué se está viendo.' },
  { campo: 'causa_metodo', label: 'Método', ayuda: 'El procedimiento, ¿lo hay y se sigue?' },
  { campo: 'causa_mano_obra', label: 'Mano de obra', ayuda: 'Personas: carga, entrenamiento.' },
  { campo: 'causa_maquinaria', label: 'Maquinaria', ayuda: 'Equipos y herramientas.' },
  { campo: 'causa_material', label: 'Material', ayuda: 'Insumos y proveedores.' },
  { campo: 'causa_medidas', label: 'Medidas', ayuda: 'Qué se mide y con qué.' },
  { campo: 'causa_medio_ambiente', label: 'Medio ambiente', ayuda: 'Entorno: espacio, ruido, clima.' },
]

/** Los tres estados de una tarea del plan de acción. */
export const ESTADOS_ACCION = {
  pendiente: { label: 'Pendiente', tono: 'neutro' },
  en_curso: { label: 'En curso', tono: 'info' },
  cumplida: { label: 'Cumplida', tono: 'positivo' },
}

/**
 * Los estados en los que una OMP ya no se trabaja.
 *
 * La lista los esconde por defecto —un tablero de trabajo muestra lo que
 * pide algo de alguien— pero **elegir uno en el filtro manda sobre eso**:
 * pedir «descartada» es justamente querer verlas. Sin esta distinción, el
 * filtro devolvía vacío hasta que además se marcaba «ver las terminadas»,
 * y parecía que no hubiera ninguna.
 */
export const ESTADOS_TERMINALES = ['cerrada', 'descartada']

/** Una OMP terminada ya no se mueve ni admite acciones nuevas. */
export function estaCerrada(omp) {
  return ESTADOS_TERMINALES.includes(omp?.estado)
}

/** ¿Este estado del filtro es uno de los que la lista esconde por defecto? */
export function esEstadoTerminal(estado) {
  return ESTADOS_TERMINALES.includes(estado)
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
 *
 * Qué se exige depende del tratamiento, y quien lo decide es el SERVIDOR:
 * `pide_causa`, `pide_correccion` y `pide_beneficio` vienen resueltos en la
 * respuesta. Aquí no se mira el nombre del tratamiento — si se mirara,
 * renombrarlo desde Admin escondería un campo obligatorio en silencio.
 *
 * Cuando esas banderas no vienen se pide causa raíz, que es el comportamiento
 * que el módulo tenía antes de conocer los tratamientos.
 */
export function loQueFaltaPara(omp, estado) {
  if (estado === 'ejecucion') {
    if (omp?.pide_causa !== false && !(omp?.causa_raiz || '').trim()) {
      return 'Escribe la causa raíz antes de pasar a ejecución.'
    }
    if (omp?.pide_correccion && !(omp?.correccion || '').trim()) {
      return 'Falta la corrección: qué se hizo para tapar el hueco de inmediato.'
    }
    if (omp?.pide_beneficio && !(omp?.beneficio_mejora || '').trim()) {
      return 'Falta el beneficio: para qué vale la pena hacer esta mejora.'
    }
  }
  if (estado === 'verificacion' && !omp?.total_acciones) {
    return 'Agrega al menos una acción: sin acciones no hay nada que verificar.'
  }
  if (estado === 'cerrada') {
    if (omp?.eficaz === null || omp?.eficaz === undefined) {
      return 'Registra la verificación de eficacia antes de cerrar.'
    }
    if (!omp?.validado_sgc_en) {
      return 'Falta que Calidad valide el cierre.'
    }
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
 * Reconstruye el bloque de texto que el formato imprime en el análisis de
 * causas, para mostrarlo de corrido cuando no se está editando.
 *
 * Solo devuelve las 6M que se escribieron: al EXPORTAR, el servidor rellena
 * las vacías con «N/A» porque así lo hace el formato, pero en pantalla una
 * lista de siete «N/A» no le dice nada a nadie.
 */
export function resumen6M(omp) {
  return CAMPOS_6M
    .map(({ campo, label }) => ({ label, texto: (omp?.[campo] || '').trim() }))
    .filter(x => x.texto)
}

/**
 * Topes de caracteres, atados a los `max_length` del schema del backend.
 *
 * Sin el tope en el input, escribir de más devolvía un 422 — y como el
 * detalle de un 422 es una lista de objetos, la página se quedaba en blanco
 * en vez de avisar. El tope aquí evita que el error llegue a ocurrir.
 *
 * Si alguno se amplía en `modules/mejora/schemas.py`, hay que subirlo aquí.
 */
export const MAX_ACCION = 300
export const MAX_TITULO = 200
export const MAX_TEXTO_LARGO = 4000
export const MAX_SEGUIMIENTO = 6000
export const MAX_NOMBRE = 150
