import { RouterProvider, createRouter } from '@tanstack/react-router'
import { AppProvider } from './provider'

import { routeTree } from '@/routeTree.gen'

const router = createRouter({ routeTree: routeTree })

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}

export const App = () => {
  return (
    <AppProvider>
      <RouterProvider router={router} />
    </AppProvider>
  )
}
