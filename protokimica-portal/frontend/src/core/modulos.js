/**
 * Qué módulos puede abrir cada rol — gemelo de `backend/app/core/modulos.py`.
 *
 * Vive dos veces porque el frontend no puede importar Python. Una prueba
 * (`tests/modulos.test.mjs`) verifica que las dos listas digan lo mismo.
 *
 * Esto es SOLO para no mostrar un menú que no lleva a ninguna parte. El
 * bloqueo de verdad está en el backend: esconder un botón no impide escribir
 * la URL a mano.
 *
 * Regla general: **el rol decide a qué módulo entras, el área decide qué ves
 * dentro.** Un líder entra a Indicadores, pero solo ve los de su área.
 *
 * **Y antes que el rol, el contrato:** la empresa abre solo los módulos que
 * tiene contratados. Eso lo dice el servidor en `/auth/me`
 * (`modulos_contratados`); aquí no hay una lista propia que se pueda quedar
 * atrás.
 */
export const ACCESO_POR_MODULO = {
  inicio: ['admin', 'gerencia', 'lider', 'agente', 'lectura'],
  pqrs: ['admin', 'gerencia', 'lider', 'agente', 'lectura'],
  // Entra cualquiera: qué puede hacer adentro lo deciden las capacidades.
  notas_credito: ['admin', 'gerencia', 'lider', 'agente', 'lectura'],
  master_planner: ['admin', 'gerencia', 'lider', 'agente', 'lectura'],
  indicadores: ['admin', 'gerencia', 'lider'],
  // La mejora es trabajo de los líderes de área. Gerencia queda fuera: el
  // avance se le reporta, no es un tablero más que mirar.
  mejora: ['admin', 'lider'],
  encuestas: ['admin', 'gerencia', 'lider', 'agente', 'lectura'],
  admin: ['admin'],
}

/** Ruta de cada módulo, para filtrar el menú y proteger las rutas. */
export const RUTA_DE_MODULO = {
  inicio: '/',
  pqrs: '/pqrs',
  notas_credito: '/notas-credito',
  master_planner: '/master-planner',
  indicadores: '/indicadores',
  mejora: '/mejora',
  encuestas: '/encuestas',
  admin: '/admin',
}

/**
 * ¿La empresa del usuario tiene este módulo? Sin el dato —una sesión guardada
 * antes de que el servidor lo mandara— no se esconde nada: el que bloquea de
 * verdad es el servidor, y esconder de más dejaría a alguien sin su menú.
 */
export function estaContratado(usuario, modulo) {
  const contratados = usuario?.modulos_contratados
  if (!Array.isArray(contratados)) return true
  return contratados.includes(modulo)
}

export function puedeVerModulo(usuario, modulo) {
  const permitidos = ACCESO_POR_MODULO[modulo]
  if (!permitidos) return false
  return permitidos.includes(usuario?.rol) && estaContratado(usuario, modulo)
}

/** Los módulos que este usuario puede abrir, en orden de menú. */
export function modulosDe(usuario) {
  return Object.keys(ACCESO_POR_MODULO).filter(m => puedeVerModulo(usuario, m))
}

/**
 * A qué módulo pertenece una ruta. `/pqrs/12` es del módulo `pqrs`.
 * Devuelve null si la ruta no está mapeada — esas no se bloquean, porque
 * bloquear por omisión dejaría fuera pantallas nuevas sin avisar.
 */
export function moduloDeRuta(ruta) {
  const limpia = (ruta || '/').split('?')[0]
  if (limpia === '/' || limpia === '') return 'inicio'
  const encontrado = Object.entries(RUTA_DE_MODULO)
    .filter(([, r]) => r !== '/')
    .find(([, r]) => limpia === r || limpia.startsWith(`${r}/`))
  return encontrado ? encontrado[0] : null
}

/**
 * A dónde mandar a alguien que llegó a un módulo que no le corresponde.
 * Al inicio, que todos pueden ver — nunca a una pantalla que también le
 * cerraría la puerta, porque eso sería un ciclo de redirecciones.
 */
export const RUTA_POR_DEFECTO = '/'
