import { useQuery } from '@tanstack/react-query'
import api from '../../core/api.js'

/**
 * El flujo de conceptos de una PQRS. Lo usan el panel Gestionar (para
 * moverlo) y la tarjeta «Conceptos» (para decir en qué paso va): la misma
 * clave, así React Query hace una sola petición.
 */
export function useFlujo(pqrsId) {
  return useQuery({
    queryKey: ['pqrs', String(pqrsId), 'flujo'],
    queryFn: () => api.get(`/pqrs/${pqrsId}/flujo`).then(r => r.data),
  })
}
