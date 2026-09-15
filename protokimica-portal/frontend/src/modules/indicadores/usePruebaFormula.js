import { useEffect, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { probarFormula } from './api'

// Cuánto se espera después de la última tecla antes de preguntarle al
// servidor. Sin esto, digitar «450» son tres consultas.
const ESPERA_MS = 350

/**
 * Lo que dice el servidor de una fórmula: si es válida, cómo se lee y, con
 * valores, cuánto da.
 *
 * El cálculo no se repite en el navegador a propósito: una segunda
 * implementación tarde o temprano redondea distinto o lee la precedencia de
 * otra forma, y la pantalla mostraría un número que no es el que se guarda.
 */
export function usePruebaFormula(formula, variables, valores = {}) {
  const firma = JSON.stringify({ formula, variables, valores })
  const [consulta, setConsulta] = useState(firma)

  useEffect(() => {
    const t = setTimeout(() => setConsulta(firma), ESPERA_MS)
    return () => clearTimeout(t)
  }, [firma])

  const datos = JSON.parse(consulta)
  const { data, isFetching } = useQuery({
    queryKey: ['formula-probar', consulta],
    queryFn: () => probarFormula(datos.formula, datos.variables, datos.valores),
    enabled: Boolean(datos.formula?.trim()),
    staleTime: 60_000,
    placeholderData: (anterior) => anterior,
  })

  return {
    prueba: formula?.trim() ? data : null,
    // Mientras se escribe, lo que se ve puede ser de hace un instante.
    actualizando: isFetching || consulta !== firma,
  }
}
