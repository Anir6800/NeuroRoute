import { Button } from '../components/ui/Button'
import { PageHeader } from '../components/ui/PageHeader'
import { ScreenState, type ScreenStatus } from '../components/ui/ScreenState'

export function Comparison({ status = 'empty' }: { status?: ScreenStatus }) {
  return (
    <>
      <PageHeader
        title="Model Comparison"
        description="Compare routing policies on the same scenario with confidence intervals."
        actions={
          <Button variant="primary" disabledReason="No simulator or baselines exist yet.">
            Run benchmark suite
          </Button>
        }
      />
      <ScreenState
        status={status}
        loadingLabel="Loading comparison"
        empty={{
          title: 'No comparable runs yet',
          description:
            'A comparison needs at least two policies evaluated on the same scenario (same config hash and seeds). Results will be labelled simulated.',
        }}
        error={{ title: 'Could not load the comparison', message: 'The evaluation service did not respond.' }}
      />
    </>
  )
}
