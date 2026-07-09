export default function StatusBadge({ status }) {

    const styles = {
        "Planeación":
            "bg-blue-100 text-blue-700",

        "En ejecución":
            "bg-emerald-100 text-emerald-700",

        "En riesgo":
            "bg-red-100 text-red-700",

        "Pausado":
            "bg-yellow-100 text-yellow-700",

        "Finalizado":
            "bg-gray-200 text-gray-700",
    }

    return (

        <span
            className={`
                px-3
                py-1
                rounded-full
                text-xs
                font-semibold
                ${styles[status] || "bg-gray-100 text-gray-700"}
            `}
        >
            {status}
        </span>

    )

}