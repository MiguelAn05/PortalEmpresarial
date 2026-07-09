export default function Avatar({ name }) {

    const initials = name
        .split(" ")
        .map(n => n[0])
        .join("")
        .substring(0,2)
        .toUpperCase()

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