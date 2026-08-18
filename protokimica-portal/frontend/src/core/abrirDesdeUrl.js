/**
 * Abrir una ficha concreta desde la URL: `/master-planner?tarea=42`.
 *
 * El inicio lista tus tareas y tus indicadores pendientes, y desde ahí hay
 * que poder entrar a ESE, no a la pantalla donde vuelve a buscarse en una
 * lista de cuarenta. Master Planner e Indicadores son pantallas de una sola
 * ruta con el detalle en un modal, así que la ficha viaja en la query en vez
 * de en el path.
 *
 * Que esté en la URL además la hace enlazable: se puede pegar en un correo o
 * en un chat y quien lo abra cae en la misma tarea.
 *
 * Ojo con el parámetro pegado: si no se borra al cerrar el modal, el modal
 * se vuelve a abrir solo en el siguiente render y la ficha no hay forma de
 * cerrarla. Por eso `cerrar()` limpia la URL además del estado.
 */
import { useCallback, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'

export function useAbrirDesdeUrl(parametro, abrir) {
  const [params, setParams] = useSearchParams()
  const valor = params.get(parametro)

  useEffect(() => {
    const id = Number(valor)
    // Un `?tarea=abc` no abre nada: mejor la pantalla normal que un modal
    // cargando una ficha que no existe.
    if (Number.isInteger(id) && id > 0) abrir(id)
  }, [valor, abrir])

  const limpiar = useCallback(() => {
    setParams(actuales => {
      const siguientes = new URLSearchParams(actuales)
      siguientes.delete(parametro)
      return siguientes
    }, { replace: true })   // replace: el "atrás" del navegador no debe reabrirlo
  }, [parametro, setParams])

  return { limpiar, vinoDeUrl: Boolean(valor) }
}
