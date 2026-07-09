import KPICards from "./components/KPICards"
import Filters from "./components/Filters"
import ProjectsTable from "./components/ProjectsTable"

export default function MasterPlanner(){

return(

<div className="space-y-6">

<div>

<h1 className="text-3xl font-bold text-[#0D2B5E]">

Master Planner

</h1>

<p className="text-gray-500">

Planeación estratégica y seguimiento de proyectos

</p>

</div>

<KPICards/>

<Filters/>

<ProjectsTable/>

</div>

)

}