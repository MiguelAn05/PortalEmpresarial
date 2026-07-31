import { ESTADOS_TAREA } from '../constants'

export default function StatusBadge({ status }) {
  const item = ESTADOS_TAREA[status] || { label: status, color: 'bg-gray-100 text-gray-700' }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}
