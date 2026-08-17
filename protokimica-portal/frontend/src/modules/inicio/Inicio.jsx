import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../../core/AuthContext.jsx'
import { RUTA_DE_MODULO } from '../../core/modulos.js'
import { formatMoneda } from '../masterPlanner/constants.js'
import { obtenerInicio } from './api.js'
import {
  ordenTarjetas, plazoRelativo, primerNombre, saludo, tonoPendientes,
} from './resumen.js'

const ROLES = {
  admin: 'Administrador',
  gerencia: 'Gerencia',
  lider: 'Líder de área',
  agente: 'Agente',
  lectura: 'Solo lectura',
}

const ACCESOS = {
  pqrs: { icono: '📨', titulo: 'PQRS', nota: 'Radicar, responder y cerrar solicitudes' },
  master_planner: { icono: '🗂️', titulo: 'Master Planner', nota: 'Proyectos, tareas y presupuesto' },
  indicadores: { icono: '📈', titulo: 'Indicadores', nota: 'Registrar el mes y ver cómo vamos' },
  encuestas: { icono: '⭐', titulo: 'Encuestas', nota: 'Satisfacción del cliente' },
  admin: { icono: '⚙️', titulo: 'Administración', nota: 'Usuarios, áreas y configuración' },
}

const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]

function Tarjeta({ borde = 'border-t-[#D6E0F0]', titulo, extra, children }) {
  return (
    <section className={`bg-white rounded-xl border border-[#D6E0F0] border-t-4 ${borde} p-5`}>
      {titulo && (
        <div className="flex items-baseline justify-between gap-3 mb-4">
          <h2 className="font-bold text-[#0D2B5E]">{titulo}</h2>
          {extra}
        </div>
      )}
      {children}
    </section>
  )
}

function Cifra({ label, valor, nota, alerta = false }) {
  return (
    <div>
      <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide">{label}</div>
      <div className={`text-3xl font-bold mt-1 ${alerta ? 'text-[#D93B3B]' : 'text-[#0D2B5E]'}`}>
        {valor}
      </div>
      {nota && <div className="text-[11px] text-[#9BACC8] mt-0.5">{nota}</div>}
    </div>
  )
}

/** El plazo con punto y texto: el color solo nunca alcanza para leerlo. */
function Plazo({ fecha }) {
  const { texto, vencido, urgente } = plazoRelativo(fecha)
  const color = vencido ? '#D93B3B' : urgente ? '#F5A800' : '#9BACC8'
  const tono = vencido ? 'text-[#D93B3B] font-semibold' : urgente ? 'text-[#8A6000]' : 'text-[#9BACC8]'
  return (
    <span className={`flex items-center gap-1.5 text-xs whitespace-nowrap ${tono}`}>
      <span className="w-1.5 h-1.5 rounded-full flex-shrink-0" style={{ background: color }} />
      {texto}
    </span>
  )
}

function Fila({ to, titulo, detalle, fecha }) {
  return (
    <Link
      to={to}
      className="flex items-center justify-between gap-3 py-2 px-2 -mx-2 rounded-lg
        hover:bg-[#F7F9FC] transition"
    >
      <div className="min-w-0">
        <div className="text-sm text-[#1A2B47] truncate">{titulo}</div>
        {detalle && <div className="text-xs text-[#6B7EA8] truncate">{detalle}</div>}
      </div>
      <Plazo fecha={fecha} />
    </Link>
  )
}

// ── Las cuatro tarjetas ───────────────────────────────────────

function Pendientes({ inicio }) {
  const tono = tonoPendientes(inicio)
  const { mis_tareas: tareas, mis_pqrs: pqrs, indicadores_por_registrar: indicadores } = inicio
  const vacio = inicio.total_pendiente === 0

  return (
    <Tarjeta
      borde={tono.borde}
      titulo={tono.titulo}
      extra={
        inicio.total_pendiente > 0 && (
          <span className="text-xs text-[#6B7EA8]">
            {inicio.total_pendiente} en total
          </span>
        )
      }
    >
      {vacio ? (
        <p className="text-sm text-[#6B7EA8]">
          No tienes tareas ni PQRS con plazo esta semana. Lo que sigue lo
          encuentras en cada módulo.
        </p>
      ) : (
        <div className="space-y-5">
          {tareas.lista.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1">
                Mis tareas · {tareas.abiertas} abiertas
              </div>
              <div className="divide-y divide-[#EEF2F8]">
                {tareas.lista.map(t => (
                  <Fila
                    key={t.id}
                    to="/master-planner"
                    titulo={t.titulo}
                    detalle={t.proyecto}
                    fecha={t.fecha_fin}
                  />
                ))}
              </div>
              {tareas.abiertas > tareas.lista.length && (
                <Link to="/master-planner" className="text-xs text-[#1A4FA0] hover:underline">
                  Ver todas mis tareas →
                </Link>
              )}
            </div>
          )}

          {pqrs.lista.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1">
                Mis PQRS · {pqrs.abiertas} sin cerrar
              </div>
              <div className="divide-y divide-[#EEF2F8]">
                {pqrs.lista.map(p => (
                  <Fila
                    key={p.id}
                    to={`/pqrs/${p.id}`}
                    titulo={`${p.codigo} — ${p.tipo}`}
                    detalle={p.cliente}
                    fecha={p.fecha_limite_sla}
                  />
                ))}
              </div>
              {pqrs.abiertas > pqrs.lista.length && (
                <Link to="/pqrs" className="text-xs text-[#1A4FA0] hover:underline">
                  Ver todas mis PQRS →
                </Link>
              )}
            </div>
          )}

          {indicadores.length > 0 && (
            <div>
              <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1">
                Indicadores sin registrar
              </div>
              <div className="divide-y divide-[#EEF2F8]">
                {indicadores.map(i => (
                  <Link
                    key={i.id}
                    to="/indicadores"
                    className="flex items-center justify-between gap-3 py-2 px-2 -mx-2
                      rounded-lg hover:bg-[#F7F9FC] transition"
                  >
                    <span className="text-sm text-[#1A2B47] truncate">{i.nombre}</span>
                    <span className="text-xs text-[#6B7EA8] whitespace-nowrap">
                      falta {MESES[i.mes - 1]} {i.anio}
                    </span>
                  </Link>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Tarjeta>
  )
}

function Accesos({ modulos }) {
  const visibles = modulos.filter(m => m !== 'inicio' && ACCESOS[m])
  if (visibles.length === 0) return null

  return (
    <Tarjeta titulo="Accesos rápidos">
      <div className="grid gap-3 sm:grid-cols-2">
        {visibles.map(m => (
          <Link
            key={m}
            to={RUTA_DE_MODULO[m]}
            className="flex items-start gap-3 p-3 rounded-lg border border-[#D6E0F0]
              hover:border-[#1A4FA0] hover:bg-[#F7F9FC] transition"
          >
            <span className="text-xl leading-none">{ACCESOS[m].icono}</span>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-[#0D2B5E]">{ACCESOS[m].titulo}</span>
              <span className="block text-xs text-[#6B7EA8]">{ACCESOS[m].nota}</span>
            </span>
          </Link>
        ))}
      </div>
    </Tarjeta>
  )
}

function MiArea({ area }) {
  return (
    <Tarjeta
      titulo={`Mi área · ${area.area}`}
      extra={<span className="text-xs text-[#6B7EA8]">{area.personas} personas</span>}
    >
      <div className="grid grid-cols-3 gap-4 mb-4">
        <Cifra label="Proyectos" valor={area.total_proyectos} />
        <Cifra label="Tareas abiertas" valor={area.tareas_abiertas_equipo} />
        <Cifra
          label="Vencidas"
          valor={area.tareas_vencidas_equipo}
          alerta={area.tareas_vencidas_equipo > 0}
          nota={area.tareas_vencidas_equipo > 0 ? 'del equipo' : 'ninguna'}
        />
      </div>

      {area.proyectos.length === 0 ? (
        <p className="text-sm text-[#6B7EA8]">Tu área todavía no tiene proyectos activos.</p>
      ) : (
        <>
          <div className="text-xs font-semibold text-[#6B7EA8] uppercase tracking-wide mb-1">
            Los que menos han avanzado
          </div>
          <div className="divide-y divide-[#EEF2F8]">
            {area.proyectos.map(p => (
              <Link
                key={p.id}
                to="/master-planner"
                className="flex items-center gap-3 py-2 px-2 -mx-2 rounded-lg
                  hover:bg-[#F7F9FC] transition"
              >
                <span className="text-sm text-[#1A2B47] truncate flex-1">{p.nombre}</span>
                <span className="w-24 h-1.5 bg-[#EEF2F8] rounded-full overflow-hidden flex-shrink-0">
                  <span
                    className="block h-full bg-[#1A4FA0]"
                    style={{ width: `${Math.min(100, p.avance_pct || 0)}%` }}
                  />
                </span>
                <span className="text-xs text-[#6B7EA8] w-10 text-right flex-shrink-0">
                  {Math.round(p.avance_pct || 0)}%
                </span>
              </Link>
            ))}
          </div>
        </>
      )}
    </Tarjeta>
  )
}

function Empresa({ empresa }) {
  return (
    <Tarjeta
      titulo="Cómo va la empresa"
      extra={
        <Link to="/indicadores" className="text-xs text-[#1A4FA0] hover:underline">
          Ver el detalle →
        </Link>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Cifra label="Proyectos activos" valor={empresa.proyectos_activos} />
        <Cifra
          label="PQRS sin cerrar"
          valor={empresa.pqrs_abiertas}
          alerta={empresa.pqrs_abiertas > 0}
        />
        <Cifra
          label="Presupuesto pagado"
          valor={formatMoneda(empresa.presupuesto_pagado)}
          nota={
            empresa.pagado_pct === null
              ? 'sin presupuesto planeado'
              : `${empresa.pagado_pct}% de ${formatMoneda(empresa.presupuesto_planeado)}`
          }
        />
        {empresa.indicadores_en_rojo !== null && (
          <Cifra
            label="Indicadores en rojo"
            valor={empresa.indicadores_en_rojo}
            alerta={empresa.indicadores_en_rojo > 0}
            nota={empresa.periodo_indicadores}
          />
        )}
      </div>
    </Tarjeta>
  )
}

// ── La página ─────────────────────────────────────────────────

export default function Inicio() {
  const { user } = useAuth()
  const { data: inicio, isLoading, isError } = useQuery({
    queryKey: ['inicio'],
    queryFn: obtenerInicio,
  })

  if (isLoading) {
    return <div className="text-sm text-[#6B7EA8]">Cargando tu inicio…</div>
  }
  if (isError || !inicio) {
    return (
      <div className="bg-white rounded-xl border border-[#D6E0F0] border-t-4 border-t-[#D93B3B] p-5">
        <h2 className="font-bold text-[#0D2B5E]">No se pudo cargar el inicio</h2>
        <p className="text-sm text-[#6B7EA8] mt-1">
          Vuelve a cargar la página. Si sigue igual, entra directo al módulo que
          necesites desde el menú de la izquierda y avísale a un administrador.
        </p>
      </div>
    )
  }

  const tarjetas = {
    pendientes: <Pendientes key="pendientes" inicio={inicio} />,
    accesos: <Accesos key="accesos" modulos={inicio.modulos} />,
    area: inicio.mi_area ? <MiArea key="area" area={inicio.mi_area} /> : null,
    empresa: inicio.empresa ? <Empresa key="empresa" empresa={inicio.empresa} /> : null,
  }

  return (
    <div className="max-w-5xl mx-auto space-y-5">
      <header>
        <h1 className="text-2xl font-bold text-[#0D2B5E]">
          {saludo()}, {primerNombre(inicio.usuario.nombre)}
        </h1>
        <p className="text-sm text-[#6B7EA8]">
          {ROLES[inicio.usuario.rol] ?? inicio.usuario.rol}
          {inicio.usuario.area && ` · ${inicio.usuario.area}`}
        </p>
      </header>

      {ordenTarjetas(user).map(nombre => tarjetas[nombre])}
    </div>
  )
}
