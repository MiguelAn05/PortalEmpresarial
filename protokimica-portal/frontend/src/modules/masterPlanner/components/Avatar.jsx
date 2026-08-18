export default function Avatar({ name, compact }) {
  if (!name) {
    return compact ? (
      <span className="text-[11px] text-texto-3 italic">Sin asignar</span>
    ) : (
      <span className="text-sm text-texto-3 italic">Sin asignar</span>
    )
  }

  const initials = name
    .split(" ")
    .map(n => n[0])
    .join("")
    .substring(0, 2)
    .toUpperCase()

  if (compact) {
    return (
      <div className="flex items-center gap-1.5" title={name}>
        <div className="w-6 h-6 rounded-full bg-acento text-white flex items-center justify-center font-semibold text-[10px]">
          {initials}
        </div>
        <span className="text-[11px] text-texto-2 truncate max-w-[90px]">{name}</span>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-3">
      <div className="w-9 h-9 rounded-full bg-acento text-white flex items-center justify-center font-semibold text-sm">
        {initials}
      </div>
      <span className="text-sm">{name}</span>
    </div>
  )
}
