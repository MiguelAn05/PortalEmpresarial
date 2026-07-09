export default function ProgressBar({ value }) {

    let color = "#22C55E"

    if(value < 30)
        color="#EF4444"

    else if(value < 70)
        color="#F59E0B"

    return (

        <div className="flex items-center gap-3">

            <div className="w-36 bg-gray-200 rounded-full h-2">

                <div

                    className="h-2 rounded-full"

                    style={{
                        width:`${value}%`,
                        background:color
                    }}

                />

            </div>

            <span className="text-sm font-semibold">

                {value}%

            </span>

        </div>

    )

}