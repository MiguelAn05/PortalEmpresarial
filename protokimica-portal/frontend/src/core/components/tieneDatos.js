/**
 * ¿El formulario tiene algo escrito que valga la pena proteger?
 * Compara contra los valores iniciales e ignora los campos que el formulario
 * trae ya rellenos por defecto.
 */
export function tieneDatos(form, inicial = {}) {
  return Object.entries(form).some(([campo, valor]) => {
    const original = inicial[campo]
    if (Array.isArray(valor)) return valor.length !== (original?.length ?? 0)
    if (typeof valor === 'boolean') return valor !== (original ?? false)
    return (valor ?? '') !== (original ?? '')
  })
}
