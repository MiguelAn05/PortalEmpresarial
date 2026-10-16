/**
 * `useState` para filtros, pero en la URL y recordado por la pestaña. La
 * regla y el porqué están en `filtrosEnUrl.js`.
 *
 *   const [filtros, cambiar, limpiar] = useFiltrosEnUrl({ vista: 'abiertas', area: '' })
 *   cambiar({ area: 'Calidad' })      // solo lo que cambia
 *   limpiar()                         // todo a su valor por defecto
 *
 * Los valores son TEXTO, como en la URL: un número o un `null` se guardan
 * como texto y vuelven como texto (o como el valor por defecto).
 *
 * `prefijo` separa dos listas que comparten ruta (las vistas de Master
 * Planner): sin él, el `estado` de proyectos y el de tareas serían el mismo.
 *
 * **Se escribe con `replace`**: cada letra del buscador no puede ser una
 * entrada del historial, o «atrás» recorrería la búsqueda letra por letra en
 * vez de volver a donde se venía.
 *
 * **La URL se lee de `window.location` al escribir**, no del render. Dos
 * listas en la misma pantalla que escriben en el mismo instante (al
 * restaurar, por ejemplo) se pisaban: la segunda partía de la URL de antes de
 * la primera y la borraba.
 */
import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import {
  escribirFiltros, filtrosGuardados, guardarFiltros, leerFiltros, soloFiltros, tieneFiltros,
} from './filtrosEnUrl.js'

export function useFiltrosEnUrl(porDefecto, { prefijo = '' } = {}) {
  // El valor por defecto se fija al montar: suele llegar como un objeto
  // literal, nuevo en cada render, y no puede disparar los efectos.
  const [defecto] = useState(porDefecto)
  const [params] = useSearchParams()
  const { pathname } = useLocation()
  const navigate = useNavigate()

  const enUrl = tieneFiltros(params, defecto, prefijo)
  // Sin nada en la URL se pinta lo guardado desde el primer render: si no,
  // la lista se dibuja sin filtros y un instante después salta.
  const fuente = enUrl ? params : filtrosGuardados(pathname, prefijo)
  const texto = soloFiltros(fuente, defecto, prefijo).toString()
  const filtros = useMemo(
    () => leerFiltros(new URLSearchParams(texto), defecto, prefijo),
    [texto, defecto, prefijo],
  )

  const aplicar = useCallback((cambios) => {
    const actuales = new URLSearchParams(window.location.search)
    // Si la URL no traía nada, se parte de lo que se estaba viendo.
    const base = tieneFiltros(actuales, defecto, prefijo)
      ? actuales
      : new URLSearchParams([...actuales, ...filtrosGuardados(pathname, prefijo)])
    const siguientes = escribirFiltros(base, cambios, defecto, prefijo)
    guardarFiltros(pathname, prefijo, soloFiltros(siguientes, defecto, prefijo))
    const busqueda = siguientes.toString()
    navigate({ pathname, search: busqueda ? `?${busqueda}` : '' },
      { replace: true, state: window.history.state?.usr })
  }, [defecto, prefijo, pathname, navigate])

  // Entrar por el menú (URL limpia) con algo guardado: se pone en la URL,
  // para que F5 y «atrás» lo conserven y se pueda copiar el enlace.
  useEffect(() => {
    if (!enUrl && texto) aplicar({})
    else if (enUrl) guardarFiltros(pathname, prefijo, soloFiltros(params, defecto, prefijo))
  }, [enUrl, texto, aplicar, params, pathname, prefijo, defecto])

  const cambiar = useCallback((cambios) => aplicar(cambios), [aplicar])
  const limpiar = useCallback(() => aplicar(defecto), [aplicar, defecto])

  return [filtros, cambiar, limpiar]
}
