import { Button } from '../components/ui/Button'
import { PageHeader } from '../components/ui/PageHeader'
import { ScreenState, type ScreenStatus } from '../components/ui/ScreenState'

export function Training({ status = 'empty' }: { status?: ScreenStatus }) {
  return (
    <>
      <PageHeader title="Training Lab"
        icon="training" description="Configure, start and monitor reinforcement-learning training runs." />
      <ScreenState
        status={status}
        loadingLabel="Checking training status"
        empty={{
          icon: 'training',
          title: 'Idle: no training configuration',
          description:
            'Training will run MaskablePPO in the separate .venv-rl environment. The environment and trainer have not been built yet.',
          action: (
            <Button variant="primary" disabledReason="No trainer exists yet.">
              Start training run
            </Button>
          ),
        }}
        error={{ title: 'Could not read training status', message: 'The training service did not respond.' }}
      />
    </>
  )
}
