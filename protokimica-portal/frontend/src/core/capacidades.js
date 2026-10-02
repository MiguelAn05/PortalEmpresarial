/**
 * ¿Puede esta persona hacer algo que no depende de su rol? Cerrar una PQRS,
 * validar el SGC, aprobar o pagar un presupuesto.
 *
 * Lo decide el servidor (`backend/app/core/capacidades.py`) y lo manda en
 * `/auth/me` como `capacidades`; aquí solo se pregunta. Antes la pantalla
 * comparaba el área con un nombre escrito a mano —«Calidad», «Tesorería»—,
 * que es justo lo que no puede pasar en un portal que se instala en otra
 * empresa: allá esas áreas se llaman distinto, y quién hace cada cosa se
 * configura en Administración › Capacidades.
 *
 * Esto solo esconde un botón. El permiso de verdad lo impone la API.
 */
export function tieneCapacidad(usuario, capacidad) {
  if (usuario?.rol === 'admin') return true
  const capacidades = usuario?.capacidades
  // Sin el dato —una sesión guardada de antes— no se ofrece: `AuthContext`
  // lo trae apenas abre el portal, y ofrecer un botón que el servidor va a
  // rechazar es peor que esperar un segundo.
  return Array.isArray(capacidades) && capacidades.includes(capacidad)
}
