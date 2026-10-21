import { Button } from '../components/ui/Button'
import { PageHeader } from '../components/ui/PageHeader'
import { ScreenState, type ScreenStatus } from '../components/ui/ScreenState'

export function Experiments({ status = 'empty' }: { status?: ScreenStatus }) {
  return (
    <>
      <PageHeader
        title="Experiments"
        description="Browse, filter and compare past runs."
        actions={<Button disabledReason="There are no runs to compare yet.">Compare selected</Button>}
      />
      <ScreenState
        status={status}
        loadingLabel="Loading runs"
        empty={{
          title: 'No experiments recorded yet',
          description: 'Run history appears here once experiments have been run. Search and filters stay off until then.',
        }}
        error={{ title: 'Could not load runs', message: 'The runs service did not respond.' }}
      />
    </>
  )
}
