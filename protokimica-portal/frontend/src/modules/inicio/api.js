import api from '../../core/api.js'

/**
 * El inicio completo en una sola llamada: quién eres, qué te toca, a qué
 * módulos entras y —si te corresponde— cómo va la empresa y tu área.
 *
 * Un solo endpoint a propósito: si el frontend pidiera cinco y armara el
 * rompecabezas, cada pantalla tendría su propia versión de "está vencida".
 */
export const obtenerInicio = () => api.get('/inicio').then(r => r.data)
