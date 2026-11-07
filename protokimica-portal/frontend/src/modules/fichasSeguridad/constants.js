/**
 * Fichas de seguridad: los topes, los filtros y las palabras de la pantalla.
 *
 * Qué ficha es la vigente, cuántas versiones tiene y si está activa lo
 * calcula el servidor y llega hecho (`backend/app/modules/fichas_seguridad`);
 * aquí solo se da nombre a lo que llega.
 */

// Atados al servidor (`models/fichas_seguridad.py` y `core/archivos.py`): el
// backend es la autoridad y esto solo evita que el error ocurra. Si cambian
// allá, cambian aquí; `tests/fichasSeguridad.test.mjs` los fija.
export const MAX_NOMBRE = 200
export const MIN_NOMBRE = 3
export const MAX_CODIGO = 40
export const MAX_VERSION = 20
export const MAX_OBSERVACIONES = 500
export const MAX_MB = 20

/** La capacidad que da escribir. Se otorga en Administración › Capacidades. */
export const CAPACIDAD_GESTIONAR = 'fichas_seguridad.gestionar'

/** Qué fichas lista el servidor. Las claves son las del backend (`ESTADOS_LISTA`). */
export const ESTADOS_LISTA = [
  { clave: 'activas', label: 'Activas' },
  { clave: 'inactivas', label: 'Desactivadas' },
  { clave: 'todas', label: 'Todas' },
]

/** Los filtros de la lista, que viven en la URL (`ficha` es la que está abierta). */
export const FILTROS_FICHAS = { buscar: '', estado: 'activas', ficha: '', vista: 'fichas', dq: '', dtipo: '' }

/** Las dos pestañas del módulo. */
export const VISTAS = [
  { clave: 'fichas', label: 'Fichas' },
  { clave: 'documentos', label: 'Documentos generados' },
]

/**
 * Los documentos que genera el módulo. Las claves son las del backend
 * (`esquemas_documentos.TIPOS`); el código es el del formato oficial.
 */
export const TIPOS_DOCUMENTO = [
  { clave: 'certificado_analisis', label: 'Certificado de análisis', formato: 'AP-F-06',
    ayuda: 'Del certificado que manda el proveedor: lotes, fechas y tabla de parámetros.' },
  { clave: 'fds', label: 'Ficha de datos de seguridad', formato: 'AP-F-08',
    ayuda: 'De la FDS del proveedor: sus 16 secciones, traducidas al español.' },
]

// Atados al servidor (`esquemas_documentos.py` y `documentos.py`).
export const MAX_LOTE = 10
export const CONCURRENCIA_LOTE = 3
export const MAX_PARAMETROS = 80
export const MAX_TEXTO = 300
export const MAX_SECCION = 6000
export const MAX_MB_LECTURA = 20

/** Las 16 secciones de la FDS, con los títulos de la plantilla AP-F-08 (SGA). Gemelo de `SECCIONES_FDS` del backend; una prueba lo ata. */
export const SECCIONES_FDS = [
  'Identificación del producto',
  'Identificación de los peligros',
  'Composición – información de los componentes',
  'Primeros auxilios',
  'Medidas de lucha contra incendio',
  'Medidas a tomar en caso de vertido accidental',
  'Manipulación y almacenamiento',
  'Controles de exposición – equipo de protección personal',
  'Propiedades físicas y químicas',
  'Estabilidad y reactividad',
  'Información toxicológica',
  'Información ecotoxicológica',
  'Consideración sobre eliminación',
  'Información relativa al transporte',
  'Información reglamentaria',
  'Otras informaciones',
]

export const ESPERA_BUSQUEDA_MS = 300
