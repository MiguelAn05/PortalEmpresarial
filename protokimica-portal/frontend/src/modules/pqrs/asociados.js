/**
 * «Asociado a»: la causa de una PQRS (Mala entrega, Calidad del producto…).
 *
 * El catálogo es de cada empresa y lo trae el servidor (`GET
 * /pqrs/asociados`); aquí solo está cómo se ofrece. Junto con el área
 * causante es «la causa», la marca quien reparte (`pqrs.cerrar`) y es
 * obligatoria para cerrar a mano. Ver `backend/app/modules/pqrs/asociados.py`.
 *
 * Nunca declares una lista de asociados dentro de un componente.
 */
import { useQuery } from '@tanstack/react-query'
import api from '../../core/api.js'

// Atados a `MAX_*_ASOCIADO` de `backend/app/models/pqrs.py`.
export const LIMITES_ASOCIADO = { codigo: 20, nombre: 150, grupo: 60 }

// Valor del filtro de la lista para las que todavía no tienen causa. No es
// un id: ninguno lo puede ser.
export const SIN_CAUSA = '__sin_causa__'

const SIN_ASOCIADOS = []

/** Los activos, en el orden del catálogo. Vacío mientras llegan. */
export function useAsociados() {
  const { data } = useQuery({
    queryKey: ['pqrs', 'asociados'],
    queryFn: () => api.get('/pqrs/asociados').then(r => r.data),
    staleTime: 10 * 60 * 1000,
  })
  return data ?? SIN_ASOCIADOS
}

/** Sin tildes ni mayúsculas: nadie las escribe en un buscador. */
export function sinTildes(texto) {
  return (texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim()
}

/** «(ME) Mala Entrega (CEDI)», como lo imprime el formato de Calidad. */
export function etiquetaAsociado(asociado) {
  return asociado ? `(${asociado.codigo}) ${asociado.nombre}` : ''
}

/**
 * La lista agrupada como se ofrece: por grupo, en el orden del catálogo, y
 * dentro de cada grupo primero los que son de la variante del canal por el
 * que entró la PQRS («Mala Entrega (Pventa)» cuando entró por una sede).
 *
 * `busqueda` filtra por código, nombre o grupo, sin tildes. «me» encuentra
 * las dos malas entregas; «entrega», las cuatro del grupo.
 */
export function agruparAsociados(lista, { aplicaA = null, busqueda = '' } = {}) {
  const q = sinTildes(busqueda)
  const grupos = []
  const porGrupo = new Map()
  for (const a of lista) {
    if (q && ![a.codigo, a.nombre, a.grupo].some(t => sinTildes(t).includes(q))) continue
    if (!porGrupo.has(a.grupo)) {
      const g = { grupo: a.grupo, items: [] }
      porGrupo.set(a.grupo, g)
      grupos.push(g)
    }
    porGrupo.get(a.grupo).items.push(a)
  }
  if (aplicaA) {
    for (const g of grupos) {
      // sort es estable: fuera de la variante del canal se respeta el orden.
      g.items.sort((x, y) => Number(y.aplica_a === aplicaA) - Number(x.aplica_a === aplicaA))
    }
  }
  return grupos
}

/**
 * El tipo de canal por el que entró la PQRS (`sede`, `institucional` o
 * null), para poner primero la variante que le corresponde.
 */
export function tipoDeCanal(canales, nombreCanal) {
  const canal = (canales || []).find(c => c.nombre === nombreCanal)
  return canal && canal.tipo !== 'general' ? canal.tipo : null
}

/**
 * Qué área causante proponer al cambiar de asociado. Solo PROPONE, y solo
 * pisa lo que todavía no decidió nadie: si el área está vacía, o si es la
 * que había sugerido el asociado anterior (o sea, la puso el portal y nadie
 * la cambió). Si quien clasifica eligió otra a propósito, se respeta.
 */
export function areaPropuesta(nuevo, anterior, areaActual) {
  if (!nuevo?.area_sugerida) return areaActual
  if (!areaActual || areaActual === anterior?.area_sugerida) return nuevo.area_sugerida
  return areaActual
}

/** ¿La PQRS pasa el filtro «Asociado a» de la lista? */
export function coincideAsociado(pqrs, filtro) {
  if (!filtro) return true
  if (filtro === SIN_CAUSA) return !pqrs.asociado_id
  return String(pqrs.asociado_id) === String(filtro)
}
