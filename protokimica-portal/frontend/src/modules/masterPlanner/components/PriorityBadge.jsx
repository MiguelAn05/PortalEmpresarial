export default function PriorityBadge({ priority }) {

    const styles = {

        Alta:
            "bg-red-100 text-red-700",

        Media:
            "bg-yellow-100 text-yellow-700",

        Baja:
            "bg-green-100 text-green-700"

    }

    return (

        <span
            className={`
                px-3
                py-1
                rounded-full
                text-xs
                font-semibold
                ${styles[priority]}
            `}
        >
            {priority}
        </span>

    )

}