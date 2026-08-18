/**
 * El aviso de tratamiento de datos de las pantallas públicas.
 *
 * Vive aquí y no dentro de cada formulario porque es un texto legal: si
 * cambia la política, cambia en un solo sitio y no en cuatro pantallas donde
 * alguna se queda con la versión vieja.
 *
 * El enlace abre en una pestaña nueva **a propósito**. Alguien que va por el
 * paso 3 del formulario y toca la política en la misma pestaña vuelve y
 * encuentra todo en blanco — y no vuelve a llenarlo.
 */

// La URL de la política de la empresa. Junto con el logo y los colores, es
// de lo que hay que cambiar el día que el portal se entregue a otra empresa.
export const URL_POLITICA_DATOS =
  'https://protokimica.com/politica-de-proteccion-de-datos-personales/'

export default function AvisoDatos({ accion = 'enviar', className = '' }) {
  return (
    <p className={`text-center text-xs text-texto-3 ${className}`}>
      Al {accion} aceptas que tus datos sean usados para gestionar tu solicitud,
      conforme a nuestra{' '}
      <a
        href={URL_POLITICA_DATOS}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium text-acento underline underline-offset-2
          hover:text-acento-fuerte transition-colors duration-150 ease-suave"
      >
        política de protección de datos personales
      </a>
      .
    </p>
  )
}
