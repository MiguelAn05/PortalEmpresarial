import { useState } from "react"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import {
  listarPresupuesto, agregarItemPresupuesto, eliminarItemPresupuesto,
  aprobarItem, revocarAprobacion, registrarPago, anularPago,
} from "../api"
import {
  ESTADOS_PAGO, formatMoneda, puedeAprobarPagos, puedeRegistrarPagos,
} from "../constants"
import { useAuth } from "../../../core/AuthContext"
import { IconoCerrar, IconoClip } from '../../../core/components/Iconos.jsx'
import { mensajeDeError } from '../../../core/errores.js'

/**
 * Presupuesto del proyecto con su flujo de plata: planeado → aprobado → pagado.
 *
 * Administración aprueba cuánto se puede desembolsar y Tesorería registra los
 * abonos. Son dos manos distintas a propósito, así que cada quien solo ve el
 * botón que le corresponde.
 */
export default function PanelPresupuesto({ proyectoId, editable, onCambio }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const aprueba = puedeAprobarPagos(user)
  const registra = puedeRegistrarPagos(user)

  const [itemForm, setItemForm] = useState({ concepto: "", detalle: "", valor_unitario: "", cantidad: "1" })
  const [expandido, setExpandido] = useState(null)   // id del ítem abierto
  const [error, setError] = useState(null)

  const { data: items = [] } = useQuery({
    queryKey: ["mp-presupuesto", proyectoId],
    queryFn: () => listarPresupuesto(proyectoId),
  })

  const total = items.reduce((s, i) => s + i.valor_total, 0)
  const aprobado = items.reduce((s, i) => s + (i.valor_aprobado || 0), 0)
  const pagado = items.reduce((s, i) => s + i.valor_pagado, 0)
  const pendiente = items.reduce((s, i) => s + i.pendiente_de_pago, 0)
  const pagadoPct = aprobado ? Math.round((pagado / aprobado) * 100) : 0
  const porAprobar = items.filter(i => !i.esta_aprobado).length

  const refrescar = () => {
    queryClient.invalidateQueries({ queryKey: ["mp-presupuesto", proyectoId] })
    setError(null)
    onCambio?.()
  }
  const alFallar = (e) => setError(mensajeDeError(e, "No se pudo completar la operación."))

  const mutAgregar = useMutation({
    mutationFn: () => agregarItemPresupuesto(proyectoId, {
      ...itemForm,
      valor_unitario: Number(itemForm.valor_unitario) || 0,
      cantidad: Number(itemForm.cantidad) || 1,
    }),
    onSuccess: () => { setItemForm({ concepto: "", detalle: "", valor_unitario: "", cantidad: "1" }); refrescar() },
    onError: alFallar,
  })

  const mutEliminar = useMutation({
    mutationFn: (id) => eliminarItemPresupuesto(id),
    onSuccess: refrescar, onError: alFallar,
  })

  return (
    <div className="bg-white rounded-2xl border border-borde shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-borde">
        <h3 className="text-sm font-bold text-acento-fuerte">Presupuesto del proyecto</h3>
        <p className="text-xs text-texto-3 mt-0.5">
          Cada ítem pasa por tres etapas: se presupuesta, Administración lo aprueba
          y Tesorería registra los pagos.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-superficie-2 border-b border-borde">
        <Cifra titulo="Planeado" valor={formatMoneda(total)} />
        <Cifra titulo="Aprobado" valor={formatMoneda(aprobado)}
          nota={porAprobar > 0 ? `${porAprobar} ítem(s) sin aprobar` : null} />
        <Cifra titulo="Pagado" valor={formatMoneda(pagado)} />
        <Cifra titulo="Pendiente de pago" valor={formatMoneda(pendiente)}
          alerta={pendiente > 0} />
        {/* El % se mide sobre lo APROBADO: es lo que de verdad se debe. */}
        <Cifra titulo="% pagado" valor={aprobado ? `${pagadoPct}%` : '—'}
          nota={aprobado ? 'de lo aprobado' : 'nada aprobado aún'} />
      </div>

      {error && (
        <div className="mx-6 mt-4 bg-negativo-bg border border-negativo/25 text-negativo text-sm rounded-xl px-4 py-3 flex justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="font-semibold shrink-0">Cerrar</button>
        </div>
      )}

      <div className="divide-y divide-borde">
        {items.length === 0 && (
          <p className="px-6 py-10 text-center text-sm text-texto-3">
            Sin ítems de presupuesto todavía.
          </p>
        )}
        {items.map(item => (
          <FilaItem
            key={item.id}
            item={item}
            abierto={expandido === item.id}
            onAlternar={() => setExpandido(expandido === item.id ? null : item.id)}
            aprueba={aprueba}
            registra={registra}
            editable={editable}
            onRefrescar={refrescar}
            onError={alFallar}
            onEliminar={() => {
              if (confirm(`¿Quitar "${item.concepto}" del presupuesto?`)) mutEliminar.mutate(item.id)
            }}
          />
        ))}
      </div>

      {editable && (
        <div className="p-6 border-t border-borde bg-superficie-2">
          <p className="text-xs font-semibold text-texto-2 uppercase mb-2">Agregar ítem</p>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
            <input placeholder="Concepto" value={itemForm.concepto}
              onChange={(e) => setItemForm({ ...itemForm, concepto: e.target.value })}
              className="md:col-span-2 rounded-lg border border-borde px-3 py-2 text-sm" />
            <input placeholder="Detalle (opcional)" value={itemForm.detalle}
              onChange={(e) => setItemForm({ ...itemForm, detalle: e.target.value })}
              className="rounded-lg border border-borde px-3 py-2 text-sm" />
            <input placeholder="Valor unitario" type="number" value={itemForm.valor_unitario}
              onChange={(e) => setItemForm({ ...itemForm, valor_unitario: e.target.value })}
              className="rounded-lg border border-borde px-3 py-2 text-sm" />
            <input placeholder="Cantidad" type="number" value={itemForm.cantidad}
              onChange={(e) => setItemForm({ ...itemForm, cantidad: e.target.value })}
              className="rounded-lg border border-borde px-3 py-2 text-sm" />
          </div>
          <button onClick={() => mutAgregar.mutate()}
            disabled={!itemForm.concepto || mutAgregar.isPending}
            className="mt-3 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-sm font-semibold px-5 py-2 rounded-lg transition">
            + Agregar ítem
          </button>
        </div>
      )}
    </div>
  )
}

function Cifra({ titulo, valor, nota, alerta }) {
  return (
    <div className="bg-white px-5 py-4">
      <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide">{titulo}</p>
      <p className={`text-lg font-bold mt-1 ${alerta ? 'text-negativo-vivo' : 'text-acento-fuerte'}`}>{valor}</p>
      {nota && <p className="text-[11px] text-texto-3 mt-0.5">{nota}</p>}
    </div>
  )
}

function ChipEstado({ estado }) {
  const cfg = ESTADOS_PAGO[estado] || ESTADOS_PAGO.por_aprobar
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${cfg.chip}`}>
      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: cfg.punto }} />
      {cfg.label}
    </span>
  )
}

function FilaItem({ item, abierto, onAlternar, aprueba, registra, editable, onRefrescar, onError, onEliminar }) {
  return (
    <div>
      <div className="px-6 py-4 flex flex-wrap items-center gap-4 hover:bg-superficie-2 transition">
        <button onClick={onAlternar} className="flex-1 text-left min-w-[180px]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-acento-fuerte">{item.concepto}</span>
            <ChipEstado estado={item.estado_pago} />
          </div>
          {item.detalle && <p className="text-xs text-texto-3 mt-0.5">{item.detalle}</p>}
          <p className="text-[11px] text-texto-3 mt-0.5">
            {item.cantidad} × {formatMoneda(item.valor_unitario)}
            {item.pagos.length > 0 && ` · ${item.pagos.length} pago(s)`}
          </p>
        </button>

        <div className="text-right shrink-0">
          <p className="text-sm font-bold text-acento-fuerte">{formatMoneda(item.valor_total)}</p>
          <p className="text-[11px] text-texto-3">planeado</p>
        </div>

        <div className="text-right shrink-0 w-32">
          {item.esta_aprobado ? (
            <>
              <p className="text-sm font-semibold text-texto">{formatMoneda(item.valor_pagado)}</p>
              <div className="w-full bg-superficie-2 rounded-full h-1.5 mt-1">
                <div className="h-1.5 rounded-full bg-positivo-vivo transition-all"
                  style={{ width: `${Math.min(item.pagado_pct, 100)}%` }} />
              </div>
              <p className="text-[11px] text-texto-3 mt-0.5">
                {item.pagado_pct}% de {formatMoneda(item.valor_aprobado)}
              </p>
            </>
          ) : (
            <p className="text-[11px] text-borde-fuerte">Sin aprobar</p>
          )}
        </div>

        <button onClick={onAlternar}
          className="text-texto-3 hover:text-acento text-sm shrink-0 w-6"
          aria-label={abierto ? 'Cerrar detalle' : 'Ver detalle'}>
          {abierto ? '▲' : '▼'}
        </button>
      </div>

      {abierto && (
        <div className="px-6 pb-5 bg-superficie-2 border-t border-borde space-y-4 pt-4">
          <BloqueAprobacion item={item} aprueba={aprueba} onRefrescar={onRefrescar} onError={onError} />
          <BloquePagos item={item} registra={registra} onRefrescar={onRefrescar} onError={onError} />

          {editable && (
            <button onClick={onEliminar}
              className="text-xs text-negativo hover:text-negativo font-semibold">
              Quitar ítem del presupuesto
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function BloqueAprobacion({ item, aprueba, onRefrescar, onError }) {
  const [editando, setEditando] = useState(false)
  const [valor, setValor] = useState(String(item.valor_aprobado ?? item.valor_total))
  const [nota, setNota] = useState(item.nota_aprobacion || "")

  const mut = useMutation({
    mutationFn: () => aprobarItem(item.id, { valor_aprobado: Number(valor), nota: nota || null }),
    onSuccess: () => { setEditando(false); onRefrescar() },
    onError,
  })
  const mutRevocar = useMutation({
    mutationFn: () => revocarAprobacion(item.id),
    onSuccess: onRefrescar, onError,
  })

  return (
    <div className="bg-white rounded-xl border border-borde p-4">
      <div className="flex justify-between items-start gap-3 mb-2">
        <div>
          <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide">Aprobación</p>
          {item.esta_aprobado ? (
            <p className="text-sm text-texto mt-1">
              <strong>{formatMoneda(item.valor_aprobado)}</strong>
              {item.aprobado_por_nombre && (
                <span className="text-texto-3"> · aprobado por {item.aprobado_por_nombre}</span>
              )}
            </p>
          ) : (
            <p className="text-sm text-texto-2 mt-1">
              Pendiente de que Administración apruebe el desembolso.
            </p>
          )}
          {item.nota_aprobacion && !editando && (
            <p className="text-xs text-texto-2 mt-1">{item.nota_aprobacion}</p>
          )}
        </div>
        {aprueba && !editando && (
          <div className="flex gap-2 shrink-0">
            <button onClick={() => setEditando(true)}
              className="border border-borde hover:bg-superficie-2 text-acento-fuerte text-xs font-semibold px-3 py-1.5 rounded-lg transition">
              {item.esta_aprobado ? 'Cambiar' : 'Aprobar'}
            </button>
            {item.esta_aprobado && (
              <button onClick={() => { if (confirm('¿Revocar la aprobación de este ítem?')) mutRevocar.mutate() }}
                className="text-xs text-negativo hover:text-negativo font-semibold px-2">
                Revocar
              </button>
            )}
          </div>
        )}
      </div>

      {editando && (
        <div className="space-y-2 mt-3">
          <div>
            <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">
              Valor a aprobar
            </label>
            <input type="number" value={valor} onChange={(e) => setValor(e.target.value)} autoFocus
              className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
            <p className="text-[11px] text-texto-3 mt-1">
              Puede ser menor que el planeado ({formatMoneda(item.valor_total)}) si se negoció otro precio.
            </p>
          </div>
          <input value={nota} onChange={(e) => setNota(e.target.value)}
            placeholder="Nota de la aprobación (opcional)"
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
          <div className="flex gap-2">
            <button onClick={() => setEditando(false)}
              className="flex-1 border border-borde text-xs font-semibold py-2 rounded-lg hover:bg-superficie-2">
              Cancelar
            </button>
            <button onClick={() => mut.mutate()} disabled={mut.isPending || valor === ""}
              className="flex-1 bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg">
              {mut.isPending ? 'Guardando...' : 'Aprobar'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function BloquePagos({ item, registra, onRefrescar, onError }) {
  const [abriendo, setAbriendo] = useState(false)
  const [pago, setPago] = useState({ valor: "", concepto: "", fecha: "" })
  const [soporte, setSoporte] = useState(null)

  const mut = useMutation({
    mutationFn: () => {
      const fd = new FormData()
      fd.append("valor", pago.valor)
      if (pago.concepto) fd.append("concepto", pago.concepto)
      if (pago.fecha) fd.append("fecha", new Date(pago.fecha).toISOString())
      if (soporte) fd.append("soporte", soporte)
      return registrarPago(item.id, fd)
    },
    onSuccess: () => {
      setPago({ valor: "", concepto: "", fecha: "" }); setSoporte(null); setAbriendo(false)
      onRefrescar()
    },
    onError,
  })

  const mutAnular = useMutation({
    mutationFn: (id) => anularPago(id),
    onSuccess: onRefrescar, onError,
  })

  return (
    <div className="bg-white rounded-xl border border-borde p-4">
      <div className="flex justify-between items-center mb-2">
        <p className="text-xs font-semibold text-texto-2 uppercase tracking-wide">
          Pagos {item.pagos.length > 0 && `(${item.pagos.length})`}
        </p>
        {registra && item.esta_aprobado && item.pendiente_de_pago > 0 && (
          <button onClick={() => setAbriendo(v => !v)}
            className="text-xs font-semibold text-acento hover:underline">
            {abriendo ? 'Cancelar' : '+ Registrar pago'}
          </button>
        )}
      </div>

      {!item.esta_aprobado ? (
        <p className="text-xs text-texto-3">
          No se puede pagar un ítem que Administración no ha aprobado.
        </p>
      ) : item.pagos.length === 0 ? (
        <p className="text-xs text-texto-3">
          Aprobado por {formatMoneda(item.valor_aprobado)}, sin pagos registrados.
        </p>
      ) : (
        <div className="space-y-1.5">
          {item.pagos.map(p => (
            <div key={p.id} className="group flex items-center gap-3 bg-superficie-2 rounded-lg px-3 py-2">
              <span className="text-sm font-semibold text-acento-fuerte w-32 shrink-0">
                {formatMoneda(p.valor)}
              </span>
              <span className="text-xs text-texto-2 flex-1 truncate">
                {p.concepto || 'Pago'}
                {p.registrado_por_nombre && ` · ${p.registrado_por_nombre}`}
              </span>
              <span className="text-[11px] text-texto-3 shrink-0">
                {new Date(p.fecha).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })}
              </span>
              {p.soporte && (
                <a href={p.soporte} target="_blank" rel="noreferrer"
                  className="text-acento shrink-0" title="Ver soporte"><IconoClip tam={14} /></a>
              )}
              {registra && (
                <button
                  onClick={() => { if (confirm(`¿Anular el pago de ${formatMoneda(p.valor)}?`)) mutAnular.mutate(p.id) }}
                  className="text-xs text-borde-fuerte hover:text-negativo shrink-0 opacity-0 group-hover:opacity-100 transition"
                  aria-label="Anular pago"><IconoCerrar tam={14} /></button>
              )}
            </div>
          ))}
          {item.pendiente_de_pago > 0 && (
            <p className="text-xs text-alerta pt-1">
              Falta por pagar: <strong>{formatMoneda(item.pendiente_de_pago)}</strong>
            </p>
          )}
        </div>
      )}

      {abriendo && (
        <div className="mt-3 pt-3 border-t border-borde space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">Valor</label>
              <input type="number" value={pago.valor} autoFocus
                onChange={(e) => setPago({ ...pago, valor: e.target.value })}
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-texto-2 uppercase mb-1">Fecha</label>
              <input type="date" value={pago.fecha}
                onChange={(e) => setPago({ ...pago, fecha: e.target.value })}
                className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
            </div>
          </div>
          <input value={pago.concepto} onChange={(e) => setPago({ ...pago, concepto: e.target.value })}
            placeholder="Concepto — ej: Anticipo 50%, Saldo"
            className="w-full rounded-lg border border-borde px-3 py-2 text-sm" />
          <input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
            onChange={(e) => setSoporte(e.target.files?.[0] || null)}
            className="w-full text-xs text-texto-2 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-acento-suave file:text-acento hover:file:bg-borde" />
          {soporte && <p className="flex items-center gap-1.5 text-xs text-texto-2"><IconoClip tam={12} /> {soporte.name}</p>}
          <p className="text-[11px] text-texto-3">
            Máximo {formatMoneda(item.pendiente_de_pago)}, que es lo que falta por pagar.
          </p>
          <button onClick={() => mut.mutate()} disabled={!pago.valor || mut.isPending}
            className="w-full bg-acento hover:bg-acento-fuerte disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg transition">
            {mut.isPending ? 'Guardando...' : 'Registrar pago'}
          </button>
        </div>
      )}
    </div>
  )
}
