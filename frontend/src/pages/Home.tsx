import { BackendStatus } from '../components/BackendStatus'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'

export function Home() {
  return (
    <>
      <PageHeader title="Overview" description="Local research console. No results are shown until real runs exist." />
      <Card title="Backend">
        <BackendStatus />
      </Card>
    </>
  )
}
