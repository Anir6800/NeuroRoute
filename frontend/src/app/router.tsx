import { createBrowserRouter, type RouteObject } from 'react-router-dom'
import { AppShell } from '../components/layout/AppShell'
import { Comparison } from '../pages/Comparison'
import { Experiments } from '../pages/Experiments'
import { NotFound } from '../pages/NotFound'
import { Overview } from '../pages/Overview'
import { Topology } from '../pages/Topology'
import { Training } from '../pages/Training'

/** Paths here must stay in sync with NAV_ITEMS (a test enforces it). Every route renders inside AppShell. */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <Overview /> },
      { path: 'topology', element: <Topology /> },
      { path: 'training', element: <Training /> },
      { path: 'experiments', element: <Experiments /> },
      { path: 'comparison', element: <Comparison /> },
      // Code-split: the sign-in page pulls in the Firebase SDK, which the other screens do not need.
      { path: 'login', lazy: async () => ({ Component: (await import('../pages/Login')).Login }) },
      { path: '*', element: <NotFound /> },
    ],
  },
]

export const createAppRouter = () => createBrowserRouter(routes)
