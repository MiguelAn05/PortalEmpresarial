import { ESTADOS_TAREA } from '../constants'

export default function StatusBadge({ status }) {
  const item = ESTADOS_TAREA[status] || { label: status, color: 'bg-superficie-2 text-texto-2' }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}
