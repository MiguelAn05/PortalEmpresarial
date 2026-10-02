/**
 * Las áreas de la empresa: crearlas, renombrarlas y desactivarlas. Salen en
 * orden alfabético: el servidor las ordena, aquí no se elige un orden.
 *
 * Antes eran una lista escrita en el código, igual para cualquier empresa:
 * agregar un área pedía un despliegue. Ver `backend/app/core/areas.py`.
 *
 * - **Renombrar cambia el nombre en todo** lo que lo lleva: usuarios, PQRS,
 *   proyectos, indicadores, capacidades… El servidor lo hace en una sola
 *   transacción y responde cuánto cambió; aquí se avisa antes y se dice
 *   después.
 * - **No hay borrar: se desactiva.** Deja de ofrecerse en los desplegables,
 *   pero lo que ya la tenía —una PQRS de hace un año— la conserva.
 */
import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import api from '../../core/api.js'
import { mensajeDeError } from '../../core/errores.js'
import { IconoEditar, IconoEmpresa } from '../../core/components/Iconos.jsx'

// Atado a `MAX_NOMBRE_AREA` de backend/app/models/area.py.
const MAX_NOMBRE = 100

function resumenDeCambios(cambios) {
  const total = Object.values(cambios || {}).reduce((a, n) => a + n, 0)
  if (!total) return 'No había nada más con ese nombre.'
  return `Se actualizó en ${total} ${total === 1 ? 'registro' : 'registros'}.`
}

function FilaArea({ area, onCambiar, ocupado }) {
  const [editando, setEditando] = useState(false)
  const [nombre, setNombre] = useState(area.nombre)
  const [confirmando, setConfirmando] = useState(null)   // 'renombrar' | 'desactivar' | null

  const limpio = nombre.trim().replace(/\s+/g, ' ')
  const cambio = limpio.length >= 2 && limpio !== area.nombre

  if (editando) {
    return (
      <div className="px-5 py-3 space-y-2">
        <div className="flex gap-2">
          <input
            id={`area-${area.id}`}
            value={nombre}
            maxLength={MAX_NOMBRE}
            onChange={e => { setNombre(e.target.value); setConfirmando(null) }}
            className="flex-1 rounded-lg border border-borde px-3 py-1.5 text-sm"
            autoFocus
          />
          <button
            type="button"
            disabled={!cambio || ocupado}
            onClick={() => setConfirmando('renombrar')}
            className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40"
          >
            Renombrar
          </button>
          <button
            type="button"
            onClick={() => { setEditando(false); setNombre(area.nombre); setConfirmando(null) }}
            className="px-3 py-1.5 rounded-lg text-sm text-texto-2 hover:bg-superficie-2"
          >
            Cancelar
          </button>
        </div>
        {confirmando === 'renombrar' && (
          <div className="rounded-lg bg-alerta-bg text-sm text-texto px-3 py-2 flex flex-wrap items-center gap-3">
            <span className="flex-1 min-w-0">
              «{area.nombre}» pasa a llamarse «{limpio}» en todo el portal: usuarios,
              PQRS, proyectos, indicadores y permisos. Hoy la tienen {area.personas}{' '}
              {area.personas === 1 ? 'persona' : 'personas'}.
            </span>
            <button
              type="button"
              disabled={ocupado}
              onClick={() => onCambiar({ nombre: limpio }, () => setEditando(false))}
              className="px-3 py-1 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40"
            >
              Sí, renombrar
            </button>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="px-5 py-2.5 flex items-center gap-3">
      <div className="flex-1 min-w-0">
        <div className={`text-sm font-medium truncate ${area.activa ? 'text-texto' : 'text-texto-3 line-through'}`}>
          {area.nombre}
        </div>
        <div className="text-xs text-texto-3 cifra">
          {area.personas} {area.personas === 1 ? 'persona' : 'personas'}
          {area.es_de_sedes && ' · área de las sedes: su gente lleva punto de venta y ve solo sus PQRS'}
          {!area.activa && ' · desactivada: no se ofrece para lo nuevo'}
        </div>
      </div>

      {confirmando === 'desactivar' ? (
        <span className="flex items-center gap-2 text-xs text-texto-2">
          {area.personas > 0
            ? `${area.personas} la conservan, pero ya no se podrá asignar.`
            : 'Ya no se podrá asignar.'}
          <button
            type="button" disabled={ocupado}
            onClick={() => onCambiar({ activa: false }, () => setConfirmando(null))}
            className="px-2.5 py-1 rounded-lg font-semibold bg-negativo text-white disabled:opacity-40"
          >
            Desactivar
          </button>
          <button type="button" onClick={() => setConfirmando(null)} className="px-2 py-1 rounded-lg hover:bg-superficie-2">
            No
          </button>
        </span>
      ) : (
        <span className="flex items-center gap-1">
          {area.activa && !area.es_de_sedes && (
            <button
              type="button" disabled={ocupado}
              onClick={() => onCambiar({ es_de_sedes: true })}
              title="Quien esté en esta área llevará su punto de venta y verá solo las PQRS de su sede"
              className="px-2.5 py-1 rounded-lg text-xs text-texto-3 hover:bg-superficie-2"
            >
              Es la de las sedes
            </button>
          )}
          {area.activa && (
            <button
              type="button" onClick={() => setEditando(true)}
              className="p-1.5 rounded-lg text-texto-2 hover:bg-superficie-2" aria-label={`Renombrar ${area.nombre}`}
            >
              <IconoEditar tam={15} />
            </button>
          )}
          <button
            type="button" disabled={ocupado}
            onClick={() => (area.activa ? setConfirmando('desactivar') : onCambiar({ activa: true }))}
            className="px-2.5 py-1 rounded-lg text-xs font-semibold text-texto-2 hover:bg-superficie-2"
          >
            {area.activa ? 'Desactivar' : 'Reactivar'}
          </button>
        </span>
      )}
    </div>
  )
}

export default function Areas() {
  const queryClient = useQueryClient()
  const [nueva, setNueva] = useState('')
  const [aviso, setAviso] = useState(null)   // { tono, texto }

  const { data: areas = [], isLoading } = useQuery({
    queryKey: ['areas', 'admin'],
    queryFn: () => api.get('/areas/todas').then(r => r.data),
  })

  // Las áreas salen en todos los desplegables del portal: cualquier cambio
  // los refresca todos (`['areas']` cubre la lista de los formularios).
  const refrescar = () => queryClient.invalidateQueries({ queryKey: ['areas'] })

  const crear = useMutation({
    mutationFn: () => api.post('/areas', { nombre: nueva }),
    onSuccess: ({ data }) => {
      setNueva('')
      setAviso({ tono: 'positivo', texto: `Se creó «${data.nombre}». Ya aparece en los formularios.` })
      refrescar()
    },
    onError: err => setAviso({ tono: 'negativo', texto: mensajeDeError(err, 'No se pudo crear el área.') }),
  })

  const cambiar = useMutation({
    mutationFn: ({ id, cambios }) => api.patch(`/areas/${id}`, cambios),
    onError: err => setAviso({ tono: 'negativo', texto: mensajeDeError(err, 'No se pudo guardar el cambio.') }),
  })

  function onCambiar(area) {
    return (cambios, alTerminar) => {
      cambiar.mutate({ id: area.id, cambios }, {
        onSuccess: ({ data }) => {
          if (cambios.nombre) {
            setAviso({ tono: 'positivo', texto: `Renombrada a «${data.area.nombre}». ${resumenDeCambios(data.cambios)}` })
          } else {
            setAviso(null)
          }
          alTerminar?.()
          refrescar()
        },
      })
    }
  }

  const ocupado = crear.isPending || cambiar.isPending

  return (
    <div className="bg-white rounded-xl border border-borde overflow-hidden">
      <div className="px-5 py-4 border-b border-borde">
        <h3 className="font-bold text-acento-fuerte flex items-center gap-2">
          <IconoEmpresa tam={18} /> Áreas
        </h3>
        <p className="text-xs text-texto-2 mt-0.5">
          Las que se ofrecen en todo el portal, en orden alfabético. Renombrar cambia el
          nombre en todo lo que la tiene; desactivar la deja de ofrecer sin quitársela
          a nadie.
        </p>
      </div>

      <form
        className="px-5 py-3 border-b border-borde flex gap-2"
        onSubmit={e => { e.preventDefault(); if (nueva.trim().length >= 2) crear.mutate() }}
      >
        <input
          id="area-nueva"
          value={nueva}
          maxLength={MAX_NOMBRE}
          onChange={e => setNueva(e.target.value)}
          placeholder="Nombre del área nueva"
          className="flex-1 rounded-lg border border-borde px-3 py-1.5 text-sm"
        />
        <button
          type="submit" disabled={nueva.trim().length < 2 || ocupado}
          className="px-3 py-1.5 rounded-lg text-sm font-semibold bg-acento-fuerte text-white disabled:opacity-40"
        >
          Crear
        </button>
      </form>

      {aviso && (
        <div className={`px-5 py-2 text-sm border-b border-borde ${
          aviso.tono === 'negativo' ? 'bg-negativo-bg text-negativo' : 'bg-positivo-bg text-positivo'
        }`}>
          {aviso.texto}
        </div>
      )}

      <div className="divide-y divide-borde">
        {isLoading ? (
          <div className="px-5 py-8 text-center text-sm text-texto-2">Cargando...</div>
        ) : (
          areas.map(a => (
            <FilaArea
              key={`${a.id}-${a.nombre}`}
              area={a}
              ocupado={ocupado}
              onCambiar={onCambiar(a)}
            />
          ))
        )}
      </div>
    </div>
  )
}
