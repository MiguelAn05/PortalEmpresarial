import { PRIORIDADES } from '../constants'

export default function PriorityBadge({ priority }) {
  const item = PRIORIDADES[priority] || { label: priority, color: 'bg-gray-100 text-gray-700' }
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-semibold ${item.color}`}>
      {item.label}
    </span>
  )
}
