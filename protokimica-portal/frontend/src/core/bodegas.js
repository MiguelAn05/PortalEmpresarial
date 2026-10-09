/**
 * Las bodegas de la empresa: una sola lista para todo el portal.
 *
 * Ya no hay una lista aquí. Antes había dos —la de Notas crédito, fija en
 * este archivo con Guayabal y La 65, y la de despacho de PQRS— y no se
 * conocían: una bodega nueva aparecía en una pantalla y en la otra no. Ahora
 * se administran en Administración › Bodegas, cada una con sus responsables,
 * y la pantalla las pide al servidor (`GET /bodegas`). Ver
 * `backend/app/models/bodega.py`.
 *
 * Nunca declares una lista de bodegas dentro de un componente.
 */
import { useQuery } from '@tanstack/react-query'
import api from './api.js'

const SIN_BODEGAS = []

/** Las bodegas activas, en su orden. Vacío mientras llegan. */
export function useBodegas() {
  const { data } = useQuery({
    queryKey: ['bodegas'],
    queryFn: () => api.get('/bodegas').then(r => r.data),
    staleTime: 10 * 60 * 1000,
  })
  return data ?? SIN_BODEGAS
}

/** Los nombres, para los formularios que guardan la bodega por su nombre. */
export function nombresDeBodegas(lista) {
  return (lista || []).map(b => b.nombre)
}
