import { Button } from '../components/ui/Button'
import { PageHeader } from '../components/ui/PageHeader'
import { ScreenState, type ScreenStatus } from '../components/ui/ScreenState'

export function Topology({ status = 'empty' }: { status?: ScreenStatus }) {
  return (
    <>
      <PageHeader title="Topology Studio"
        icon="topology" description="View and validate the network scenario that experiments run on." />
      <ScreenState
        status={status}
        loadingLabel="Loading scenario"
        empty={{
          icon: 'topology',
          title: 'No scenario loaded',
          description:
            'Scenario files live in experiments/configs/. Loading them needs a scenario API that has not been built yet.',
          action: (
            <Button variant="primary" disabledReason="The scenario API does not exist yet.">
              Load example scenario
            </Button>
          ),
        }}
        error={{ title: 'Could not load the scenario', message: 'The scenario service did not respond.' }}
      />
    </>
  )
}
