import { PageHeader } from '../components/ui/PageHeader'
import { TopologyStudio } from '../features/topology/TopologyStudio'
import type { TopologyApi } from '../features/topology/api'

export function Topology({ api }: { api?: TopologyApi }) {
  return (
    <>
      <PageHeader title="Topology Studio"
        icon="topology" description="Draw the network, check it, and save it to the local API." />
      <TopologyStudio api={api} />
    </>
  )
}
