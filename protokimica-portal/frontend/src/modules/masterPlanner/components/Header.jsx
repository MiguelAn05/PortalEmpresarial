export default function Header() {

    return (

        <div className="flex justify-between items-start">

            <div>

                <h1 className="text-3xl font-bold text-[#0D2B5E]">
                    Master Planner
                </h1>

                <p className="text-[#6B7EA8] mt-2">
                    Planeación, seguimiento y control de proyectos estratégicos.
                </p>

            </div>

            <button
                className="
                bg-[#F5A800]
                hover:bg-[#FFC840]
                text-[#0D2B5E]
                font-semibold
                px-6
                py-3
                rounded-xl
                shadow-sm
                transition
                "
            >

                + Nuevo Proyecto

            </button>

        </div>

    )

}