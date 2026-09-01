import { useQuery } from '@tanstack/react-query'
import api from '../../core/api.js'
import { IconoRecibo } from '../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../core/errores.js'

/**
 * Los carteles con el QR de cada punto de venta, listos para imprimir.
 *
 * **Un QR no se vence.** Es un dibujo que contiene una URL; lo que caduca es
 * cuando se genera en un sitio que crea un enlace intermedio suyo y lo apaga
 * si dejas de pagarle. Estos apuntan directo al portal, así que sirven
 * mientras el portal exista.
 *
 * Cada sede lleva el suyo y eso es lo que vale: `/q/PVG` abre el formulario
 * **ya marcado como Guayabal**. El canal deja de ser algo que el cliente
 * elige de una lista —donde se equivoca— y pasa a venir del letrero que tiene
 * enfrente. Importa porque el canal decide el prefijo de su código de
 * seguimiento (`PVG0010`) y de ahí salen los reportes por sede.
 *
 * La URL la resuelve el SERVIDOR, no esta pantalla: si se armara con el
 * dominio del navegador, un administrador entrando por la IP interna
 * imprimiría carteles que apuntan a `172.20.…` y ningún cliente podría
 * abrirlos desde su celular.
 */

// Solo se imprime el pliego de carteles: lo demás de la página se esconde.
// Va aquí y no en `index.css` porque es lo único del portal que se imprime.
const ESTILOS_IMPRESION = `
@media print {
  body * { visibility: hidden; }
  #carteles-qr, #carteles-qr * { visibility: visible; }
  #carteles-qr { position: absolute; left: 0; top: 0; width: 100%; }
  .cartel-qr { break-after: page; }
  .cartel-qr:last-child { break-after: auto; }
}
`

function Cartel({ punto }) {
  return (
    <div className="cartel-qr flex flex-col items-center text-center gap-4
      rounded-xl border border-borde bg-superficie p-8">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-texto-2">
          Protokimica
        </p>
        <h3 className="text-lg font-bold text-texto mt-1">
          ¿Tiene una petición, queja, reclamo o sugerencia?
        </h3>
        <p className="text-sm text-texto-2 mt-1">
          Apunte la cámara de su celular a este código.
        </p>
      </div>

      {/* El SVG viene del backend. Va como <img> y no incrustado porque el
          endpoint es público y así el navegador lo cachea como cualquier
          imagen. */}
      <img
        src={`${api.defaults.baseURL}/public/qr/${punto.codigo}.svg`}
        alt={`Código QR para radicar una PQRS desde ${punto.canal}`}
        className="w-56 h-56"
      />

      <div>
        <p className="text-base font-semibold text-texto">{punto.canal}</p>
        {/* El texto de la URL no sobra: si la cámara no lee el código —vidrio
            sucio, poca luz, un celular viejo— todavía se puede escribir. */}
        <p className="text-xs text-texto-2 mt-1 break-all">{punto.url}</p>
      </div>
    </div>
  )
}

export default function CodigosQR() {
  const { data: puntos, isLoading, isError, error } = useQuery({
    queryKey: ['qr-puntos'],
    queryFn: () => api.get('/public/qr').then(r => r.data),
  })

  return (
    <section className="bg-superficie rounded-xl border border-borde p-5">
      <style>{ESTILOS_IMPRESION}</style>

      <div className="flex items-start justify-between gap-3 flex-wrap mb-1">
        <div className="flex items-center gap-2">
          <IconoRecibo tam={18} className="text-texto-3" />
          <h2 className="font-semibold text-acento-fuerte text-sm">
            Códigos QR de los puntos de venta
          </h2>
        </div>
        <button
          onClick={() => window.print()}
          disabled={!puntos?.length}
          className="px-4 py-2 rounded-lg bg-acento-fuerte text-white text-sm
            font-semibold hover:bg-acento disabled:opacity-40
            transition-colors duration-150"
        >
          Imprimir los carteles
        </button>
      </div>

      <p className="text-sm text-texto-2 mb-4">
        Cada sede tiene el suyo: al escanearlo, el formulario ya queda marcado
        con ese punto de venta, así que el cliente no tiene que elegirlo de una
        lista. Estos códigos <b>no se vencen</b> — apuntan directo al portal, sin
        ningún servicio de por medio.
      </p>

      {isLoading && <p className="text-sm text-texto-3">Cargando…</p>}

      {isError && (
        <p role="alert" className="text-sm text-negativo bg-negativo-bg
          border border-negativo/25 rounded-lg px-3 py-2">
          {mensajeDeError(error, 'No se pudieron cargar los códigos.')}
        </p>
      )}

      {puntos && (
        <div id="carteles-qr" className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {puntos.map(p => <Cartel key={p.codigo} punto={p} />)}
        </div>
      )}

      {puntos && (
        <div className="mt-4 pt-4 border-t border-borde">
          <p className="etiqueta mb-2">Descargar en PNG</p>
          <p className="text-xs text-texto-2 mb-2">
            Para meterlo en un diseño o en un documento. El SVG de arriba es
            mejor para imprimir: se agranda sin perder nitidez.
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1">
            {puntos.map(p => (
              <a
                key={p.codigo}
                href={`${api.defaults.baseURL}/public/qr/${p.codigo}.png`}
                target="_blank" rel="noreferrer"
                className="text-sm text-acento hover:underline"
              >
                {p.canal}
              </a>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
