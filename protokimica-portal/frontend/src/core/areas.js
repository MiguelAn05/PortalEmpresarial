/**
 * Las áreas de la empresa.
 *
 * Ya no hay una lista aquí: cada empresa tiene las suyas y las administra en
 * Administración › Áreas. La pantalla las pide al servidor con `useAreas()`
 * (`GET /areas`, o `/public/areas` en el formulario del cliente). Antes eran
 * una lista escrita en este archivo y en `backend/app/core/areas.py`, igual
 * para cualquier empresa que instalara el portal.
 *
 * Nunca declares una lista de áreas dentro de un componente.
 */
import { useQuery } from '@tanstack/react-query'
import api from './api.js'

/**
 * Las áreas activas de la empresa, en el orden de los desplegables. Mientras
 * llegan es una lista vacía: el desplegable se llena un instante después, y
 * React Query las guarda para el resto de la sesión.
 *
 * `publico` es para el formulario del cliente, que no tiene sesión.
 */
export function useAreas({ publico = false } = {}) {
  const { data } = useQuery({
    queryKey: ['areas', publico ? 'publico' : 'interno'],
    queryFn: () => api.get(publico ? '/public/areas' : '/areas').then(r => r.data),
    // Las áreas cambian casi nunca; pedirlas en cada pantalla sería ruido.
    staleTime: 10 * 60 * 1000,
  })
  return data ?? SIN_AREAS
}

/**
 * El área donde trabajan las sedes (la marcada en Administración › Áreas), o
 * null. Quien está en ella lleva su punto de venta.
 */
export function useAreaDeSedes() {
  const { data } = useQuery({
    queryKey: ['areas', 'de-sedes'],
    queryFn: () => api.get('/areas/de-sedes').then(r => r.data.area),
    staleTime: 10 * 60 * 1000,
  })
  return data ?? null
}

// Una sola referencia para «todavía no llegan»: un `[]` nuevo en cada render
// haría que cualquier `useMemo` que dependa de la lista se recalculara siempre.
const SIN_AREAS = []

// Nombres viejos que pueden quedar en datos guardados y a qué área corresponden
// hoy. Gemelo de `EQUIVALENCIAS_HISTORICAS` en `backend/app/core/areas.py`.
export const EQUIVALENCIAS_HISTORICAS = {
  'TI': 'TICS',
  'Sistemas': 'TICS',
  'Talento Humano': 'Gestión Humana',
  'Gestión humana': 'Gestión Humana',
  'Servicio al cliente': 'Servicio al Cliente',
  'Ventas institucionales': 'Ventas Institucionales',
}

export function normalizarArea(area) {
  if (!area || !area.trim()) return null
  const limpia = area.trim()
  return EQUIVALENCIAS_HISTORICAS[limpia] ?? limpia
}

/**
 * Las áreas a ofrecer en un desplegable, incluyendo el valor actual aunque
 * ya no esté en la lista (un área desactivada, un nombre viejo). Sin esto,
 * editar un registro viejo le borraría el área en silencio al guardar.
 */
export function areasParaSelect(areas, valorActual) {
  if (!valorActual || areas.includes(valorActual)) return areas
  return [...areas, valorActual]
}
