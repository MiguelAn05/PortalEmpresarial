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
  const alFallar = (e) => setError(e?.response?.data?.detail || "No se pudo completar la operación.")

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
    <div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-[#D6E0F0]">
        <h3 className="text-sm font-bold text-[#0D2B5E]">Presupuesto del proyecto</h3>
        <p className="text-xs text-[#9BACC8] mt-0.5">
          Cada ítem pasa por tres etapas: se presupuesta, Administración lo aprueba
          y Tesorería registra los pagos.
        </p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-[#EDF2F7] border-b border-[#D6E0F0]">
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
        <div className="mx-6 mt-4 bg-red-50 border border-red-200 text-red-700 text-sm rounded-xl px-4 py-3 flex justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => setError(null)} className="font-semibold shrink-0">Cerrar</button>
        </div>
      )}

      <div className="divide-y divide-[#EDF2F7]">
        {items.length === 0 && (
          <p className="px-6 py-10 text-center text-sm text-[#9BACC8]">
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
        <div className="p-6 border-t border-[#D6E0F0] bg-[#F7F9FC]">
          <p className="text-xs font-semibold text-[#6B7EA8] uppercase mb-2">Agregar ítem</p>
          <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
            <input placeholder="Concepto" value={itemForm.concepto}
              onChange={(e) => setItemForm({ ...itemForm, concepto: e.target.value })}
              className="md:col-span-2 rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            <input placeholder="Detalle (opcional)" value={itemForm.detalle}
              onChange={(e) => setItemForm({ ...itemForm, detalle: e.target.value })}
              className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            <input placeholder="Valor unitario" type="number" value={itemForm.valor_unitario}
              onChange={(e) => setItemForm({ ...itemForm, valor_unitario: e.target.value })}
              className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            <input placeholder="Cantidad" type="number" value={itemForm.cantidad}
              onChange={(e) => setItemForm({ ...itemForm, cantidad: e.target.value })}
              className="rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
          </div>
          <button onClick={() => mutAgregar.mutate()}
            disabled={!itemForm.concepto || mutAgregar.isPending}
            className="mt-3 bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white text-sm font-semibold px-5 py-2 rounded-lg transition">
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
      <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">{titulo}</p>
      <p className={`text-lg font-bold mt-1 ${alerta ? 'text-[#D93B3B]' : 'text-[#0D2B5E]'}`}>{valor}</p>
      {nota && <p className="text-[11px] text-[#9BACC8] mt-0.5">{nota}</p>}
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
      <div className="px-6 py-4 flex flex-wrap items-center gap-4 hover:bg-[#F9FBFD] transition">
        <button onClick={onAlternar} className="flex-1 text-left min-w-[180px]">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-[#0D2B5E]">{item.concepto}</span>
            <ChipEstado estado={item.estado_pago} />
          </div>
          {item.detalle && <p className="text-xs text-[#9BACC8] mt-0.5">{item.detalle}</p>}
          <p className="text-[11px] text-[#9BACC8] mt-0.5">
            {item.cantidad} × {formatMoneda(item.valor_unitario)}
            {item.pagos.length > 0 && ` · ${item.pagos.length} pago(s)`}
          </p>
        </button>

        <div className="text-right shrink-0">
          <p className="text-sm font-bold text-[#0D2B5E]">{formatMoneda(item.valor_total)}</p>
          <p className="text-[11px] text-[#9BACC8]">planeado</p>
        </div>

        <div className="text-right shrink-0 w-32">
          {item.esta_aprobado ? (
            <>
              <p className="text-sm font-semibold text-[#1A2B47]">{formatMoneda(item.valor_pagado)}</p>
              <div className="w-full bg-gray-200 rounded-full h-1.5 mt-1">
                <div className="h-1.5 rounded-full bg-[#2E9E6B] transition-all"
                  style={{ width: `${Math.min(item.pagado_pct, 100)}%` }} />
              </div>
              <p className="text-[11px] text-[#9BACC8] mt-0.5">
                {item.pagado_pct}% de {formatMoneda(item.valor_aprobado)}
              </p>
            </>
          ) : (
            <p className="text-[11px] text-[#C3CFE2]">Sin aprobar</p>
          )}
        </div>

        <button onClick={onAlternar}
          className="text-[#9BACC8] hover:text-[#1A4FA0] text-sm shrink-0 w-6"
          aria-label={abierto ? 'Cerrar detalle' : 'Ver detalle'}>
          {abierto ? '▲' : '▼'}
        </button>
      </div>

      {abierto && (
        <div className="px-6 pb-5 bg-[#F7F9FC] border-t border-[#EDF2F7] space-y-4 pt-4">
          <BloqueAprobacion item={item} aprueba={aprueba} onRefrescar={onRefrescar} onError={onError} />
          <BloquePagos item={item} registra={registra} onRefrescar={onRefrescar} onError={onError} />

          {editable && (
            <button onClick={onEliminar}
              className="text-xs text-red-500 hover:text-red-700 font-semibold">
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
    <div className="bg-white rounded-xl border border-[#D6E0F0] p-4">
      <div className="flex justify-between items-start gap-3 mb-2">
        <div>
          <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">Aprobación</p>
          {item.esta_aprobado ? (
            <p className="text-sm text-[#1A2B47] mt-1">
              <strong>{formatMoneda(item.valor_aprobado)}</strong>
              {item.aprobado_por_nombre && (
                <span className="text-[#9BACC8]"> · aprobado por {item.aprobado_por_nombre}</span>
              )}
            </p>
          ) : (
            <p className="text-sm text-[#6B7EA8] mt-1">
              Pendiente de que Administración apruebe el desembolso.
            </p>
          )}
          {item.nota_aprobacion && !editando && (
            <p className="text-xs text-[#6B7EA8] mt-1">{item.nota_aprobacion}</p>
          )}
        </div>
        {aprueba && !editando && (
          <div className="flex gap-2 shrink-0">
            <button onClick={() => setEditando(true)}
              className="border border-[#D6E0F0] hover:bg-[#F7F9FC] text-[#0D2B5E] text-xs font-semibold px-3 py-1.5 rounded-lg transition">
              {item.esta_aprobado ? 'Cambiar' : 'Aprobar'}
            </button>
            {item.esta_aprobado && (
              <button onClick={() => { if (confirm('¿Revocar la aprobación de este ítem?')) mutRevocar.mutate() }}
                className="text-xs text-red-500 hover:text-red-700 font-semibold px-2">
                Revocar
              </button>
            )}
          </div>
        )}
      </div>

      {editando && (
        <div className="space-y-2 mt-3">
          <div>
            <label className="block text-[11px] font-semibold text-[#6B7EA8] uppercase mb-1">
              Valor a aprobar
            </label>
            <input type="number" value={valor} onChange={(e) => setValor(e.target.value)} autoFocus
              className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            <p className="text-[11px] text-[#9BACC8] mt-1">
              Puede ser menor que el planeado ({formatMoneda(item.valor_total)}) si se negoció otro precio.
            </p>
          </div>
          <input value={nota} onChange={(e) => setNota(e.target.value)}
            placeholder="Nota de la aprobación (opcional)"
            className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
          <div className="flex gap-2">
            <button onClick={() => setEditando(false)}
              className="flex-1 border border-[#D6E0F0] text-xs font-semibold py-2 rounded-lg hover:bg-gray-50">
              Cancelar
            </button>
            <button onClick={() => mut.mutate()} disabled={mut.isPending || valor === ""}
              className="flex-1 bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg">
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
    <div className="bg-white rounded-xl border border-[#D6E0F0] p-4">
      <div className="flex justify-between items-center mb-2">
        <p className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">
          Pagos {item.pagos.length > 0 && `(${item.pagos.length})`}
        </p>
        {registra && item.esta_aprobado && item.pendiente_de_pago > 0 && (
          <button onClick={() => setAbriendo(v => !v)}
            className="text-xs font-semibold text-[#1A4FA0] hover:underline">
            {abriendo ? 'Cancelar' : '+ Registrar pago'}
          </button>
        )}
      </div>

      {!item.esta_aprobado ? (
        <p className="text-xs text-[#9BACC8]">
          No se puede pagar un ítem que Administración no ha aprobado.
        </p>
      ) : item.pagos.length === 0 ? (
        <p className="text-xs text-[#9BACC8]">
          Aprobado por {formatMoneda(item.valor_aprobado)}, sin pagos registrados.
        </p>
      ) : (
        <div className="space-y-1.5">
          {item.pagos.map(p => (
            <div key={p.id} className="group flex items-center gap-3 bg-[#F7F9FC] rounded-lg px-3 py-2">
              <span className="text-sm font-semibold text-[#0D2B5E] w-32 shrink-0">
                {formatMoneda(p.valor)}
              </span>
              <span className="text-xs text-[#6B7EA8] flex-1 truncate">
                {p.concepto || 'Pago'}
                {p.registrado_por_nombre && ` · ${p.registrado_por_nombre}`}
              </span>
              <span className="text-[11px] text-[#9BACC8] shrink-0">
                {new Date(p.fecha).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })}
              </span>
              {p.soporte && (
                <a href={p.soporte} target="_blank" rel="noreferrer"
                  className="text-xs text-[#1A4FA0] shrink-0" title="Ver soporte">📎</a>
              )}
              {registra && (
                <button
                  onClick={() => { if (confirm(`¿Anular el pago de ${formatMoneda(p.valor)}?`)) mutAnular.mutate(p.id) }}
                  className="text-xs text-[#C3CFE2] hover:text-red-500 shrink-0 opacity-0 group-hover:opacity-100 transition"
                  aria-label="Anular pago">✕</button>
              )}
            </div>
          ))}
          {item.pendiente_de_pago > 0 && (
            <p className="text-xs text-amber-800 pt-1">
              Falta por pagar: <strong>{formatMoneda(item.pendiente_de_pago)}</strong>
            </p>
          )}
        </div>
      )}

      {abriendo && (
        <div className="mt-3 pt-3 border-t border-[#EDF2F7] space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-[#6B7EA8] uppercase mb-1">Valor</label>
              <input type="number" value={pago.valor} autoFocus
                onChange={(e) => setPago({ ...pago, valor: e.target.value })}
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            </div>
            <div>
              <label className="block text-[11px] font-semibold text-[#6B7EA8] uppercase mb-1">Fecha</label>
              <input type="date" value={pago.fecha}
                onChange={(e) => setPago({ ...pago, fecha: e.target.value })}
                className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
            </div>
          </div>
          <input value={pago.concepto} onChange={(e) => setPago({ ...pago, concepto: e.target.value })}
            placeholder="Concepto — ej: Anticipo 50%, Saldo"
            className="w-full rounded-lg border border-[#D6E0F0] px-3 py-2 text-sm" />
          <input type="file" accept=".jpg,.jpeg,.png,.webp,.pdf"
            onChange={(e) => setSoporte(e.target.files?.[0] || null)}
            className="w-full text-xs text-[#6B7EA8] file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-[#EAF0FB] file:text-[#1A4FA0] hover:file:bg-[#D6E0F0]" />
          {soporte && <p className="text-xs text-[#6B7EA8]">📎 {soporte.name}</p>}
          <p className="text-[11px] text-[#9BACC8]">
            Máximo {formatMoneda(item.pendiente_de_pago)}, que es lo que falta por pagar.
          </p>
          <button onClick={() => mut.mutate()} disabled={!pago.valor || mut.isPending}
            className="w-full bg-[#1A4FA0] hover:bg-[#0D2B5E] disabled:opacity-40 text-white text-xs font-semibold py-2 rounded-lg transition">
            {mut.isPending ? 'Guardando...' : 'Registrar pago'}
          </button>
        </div>
      )}
    </div>
  )
}
