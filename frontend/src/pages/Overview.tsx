import { BackendStatus } from '../components/BackendStatus'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { ScreenState, type ScreenStatus } from '../components/ui/ScreenState'

/** Only the backend status is live. Everything else waits for real runs; no sample numbers are shown. */
export function Overview({ status = 'empty' }: { status?: ScreenStatus }) {
  return (
    <>
      <PageHeader
        title="Overview"
        icon="overview"
        description="Local research console. Results appear here only after real runs exist."
        actions={
          <Button variant="primary" disabledReason="No simulator or trainer exists yet.">
            Start new experiment
          </Button>
        }
      />
      <Card title="Backend">
        <BackendStatus />
      </Card>
      <Card title="Latest results">
        <ScreenState
          status={status}
          loadingLabel="Loading results"
          empty={{
            icon: 'experiments',
            title: 'No experiments recorded yet',
            description:
              'Run an experiment to see latency, loss and comparisons here. Nothing is displayed until a real run exists.',
          }}
          error={{ title: 'Could not load results', message: 'The results service did not respond.' }}
        />
      </Card>
    </>
  )
}
