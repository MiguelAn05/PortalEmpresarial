/**
 * Los canales de atención de la empresa: por dónde entra una PQRS, cuáles son
 * sedes y con qué prefijo numeran sus casos.
 *
 * Ya no hay una lista aquí: cada empresa tiene los suyos y los administra en
 * Administración › Canales. La pantalla los pide al servidor con
 * `useCanales()` (`GET /canales`, o `/public/canales` en el formulario del
 * cliente). Cada canal llega como `{ nombre, prefijo, tipo }`, con `tipo`
 * `sede` | `institucional` | `general` (ver `backend/app/models/canal.py`).
 *
 * Las funciones de abajo reciben la lista: no tienen una propia.
 */
import { useQuery } from '@tanstack/react-query'
import api from './api.js'

const SIN_CANALES = []

export function useCanales({ publico = false } = {}) {
  const { data } = useQuery({
    queryKey: ['canales', publico ? 'publico' : 'interno'],
    queryFn: () => api.get(publico ? '/public/canales' : '/canales').then(r => r.data),
    staleTime: 10 * 60 * 1000,
  })
  return data ?? SIN_CANALES
}

// Nombres viejos que pueden quedar en datos guardados y a qué canal
// corresponden hoy. Gemelo de `EQUIVALENCIAS_HISTORICAS` en
// `backend/app/core/canales.py`.
export const EQUIVALENCIAS_HISTORICAS = {
  'Llamada telefónica': 'Línea telefónica',
}

export function normalizarCanal(canal) {
  if (!canal || !canal.trim()) return null
  const limpio = canal.trim()
  return EQUIVALENCIAS_HISTORICAS[limpio] ?? limpio
}

/** Los nombres, para un desplegable. */
export function nombresDe(canales) {
  return canales.map(c => c.nombre)
}

export function prefijoDe(canales, canal) {
  const nombre = (canal ?? '').trim()
  return canales.find(c => c.nombre === nombre)?.prefijo ?? null
}

/**
 * El canal al que apunta un código de QR (`PVG` → «Punto de venta
 * Guayabal»), o null. Sin distinguir mayúsculas: el código va impreso en un
 * letrero y alguien lo va a teclear a mano.
 */
export function canalPorCodigo(canales, codigo) {
  if (!codigo) return null
  const buscado = codigo.trim().toUpperCase()
  return canales.find(c => c.prefijo === buscado)?.nombre ?? null
}

/** Las sedes: los canales que se le asignan a un usuario como su punto de venta. */
export function puntosDeVenta(canales) {
  return canales.filter(c => c.tipo === 'sede')
}

/** Los que numeran con prefijo propio, para filtrar por el prefijo del radicado. */
export function canalesConPrefijo(canales) {
  return canales.filter(c => c.prefijo).map(c => ({ prefijo: c.prefijo, label: c.nombre }))
}
