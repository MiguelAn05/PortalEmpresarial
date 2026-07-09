import projects from "../data/mockProjects"
import StatusBadge from "./StatusBadge"
import PriorityBadge from "./PriorityBadge"
import ProgressBar from "./ProgressBar"
import Avatar from "./Avatar"

export default function ProjectsTable(){

return(

<div className="bg-white rounded-2xl border border-[#D6E0F0] shadow-sm overflow-hidden">

<div className="overflow-x-auto">

<table className="min-w-full">

<thead className="bg-[#F7F9FC] border-b border-[#D6E0F0]">

<tr className="text-xs uppercase tracking-wider text-[#6B7EA8]">

<th className="text-left px-5 py-4">Proyecto</th>

<th className="text-left px-5 py-4">Área</th>

<th className="text-left px-5 py-4">Responsable</th>

<th className="text-left px-5 py-4">Estado</th>

<th className="text-left px-5 py-4">Prioridad</th>

<th className="text-left px-5 py-4">Avance</th>

<th className="text-left px-5 py-4">Inicio</th>

<th className="text-left px-5 py-4">Fin</th>

</tr>

</thead>

<tbody>

{projects.map(project=>(

<tr
key={project.id}
className="border-b border-[#EDF2F7] hover:bg-[#F9FBFD] transition">

<td className="px-5 py-4">

<div>

<p className="font-semibold text-[#0D2B5E]">

{project.nombre}

</p>

<p className="text-xs text-gray-400">

{project.codigo}

</p>

</div>

</td>

<td className="px-5 py-4">

{project.area}

</td>

<td className="px-5 py-4">

<Avatar
    name={project.responsable}
/>

</td>

<td className="px-5 py-4">

<StatusBadge
    status={project.estado}
/>

</td>

<td className="px-5 py-4">

<PriorityBadge
    priority={project.prioridad}
/>

</td>

<td className="px-5 py-4">

<div className="flex items-center gap-3">

<div className="w-32 bg-gray-200 rounded-full h-2">


<ProgressBar
    value={project.avance}
/>
</div>


</div>

</td>

<td className="px-5 py-4">

{project.inicio}

</td>

<td className="px-5 py-4">

{project.fin}

</td>

</tr>

))}

</tbody>

</table>

</div>

</div>

)

}