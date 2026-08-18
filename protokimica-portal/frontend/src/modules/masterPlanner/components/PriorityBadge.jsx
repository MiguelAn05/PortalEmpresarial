import { PRIORIDADES } from '../constants'

export default function PriorityBadge({ priority }) {
  const item = PRIORIDADES[priority] || { label: priority, color: 'bg-superficie-2 text-texto-2' }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}
