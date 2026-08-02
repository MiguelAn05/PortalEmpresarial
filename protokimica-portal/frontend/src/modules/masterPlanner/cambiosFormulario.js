/**
 * Compara el formulario contra los valores originales y devuelve solo lo
 * que de verdad cambió, en el formato que espera `ConfirmarCambios`.
 *
 * `campos` mapea nombre del campo → cómo leer su valor original, para poder
 * comparar manzanas con manzanas (por ejemplo, una fecha ISO contra el
 * valor de un input datetime-local).
 */
export function calcularCambios(form, original, campos) {
  return Object.entries(campos).reduce((lista, [campo, leerOriginal]) => {
    const antes = leerOriginal(original)
    const despues = form[campo]
    const iguales = (antes ?? '') === (despues ?? '')
    if (!iguales) lista.push({ campo, antes: antes || null, despues: despues || null })
    return lista
  }, [])
}
