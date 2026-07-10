export default function Avatar({ name, compact }) {

    const initials = name
        .split(" ")
        .map(n => n[0])
        .join("")
        .substring(0,2)
        .toUpperCase()

    if (compact) {
        return (
            <div className="flex items-center gap-1.5" title={name}>
                <div className="w-6 h-6 rounded-full bg-[#1A4FA0] text-white flex items-center justify-center font-semibold text-[10px]">
                    {initials}
                </div>
                <span className="text-[11px] text-[#6B7EA8] truncate max-w-[90px]">{name}</span>
            </div>
        )
    }

    return (

        <div className="flex items-center gap-3">

            <div
                className="
                w-9
                h-9
                rounded-full
                bg-[#1A4FA0]
                text-white
                flex
                items-center
                justify-center
                font-semibold
                text-sm"
            >

                {initials}

            </div>

            <span className="text-sm">

                {name}

            </span>

        </div>

    )

}