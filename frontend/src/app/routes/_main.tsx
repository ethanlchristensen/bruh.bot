import {
  Navigate,
  Outlet,
  createFileRoute,
  useLocation,
} from '@tanstack/react-router'
import { Save } from 'lucide-react'
import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { AppSidebar } from '@/components/sidebar/app-sidebar-new'
import { ContentLayout } from '@/components/layouts/content-layout'
import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/hooks/use-auth'
import {
  ConfigChangesProvider,
  useConfigChanges,
} from '@/contexts/config-changes-context'
import { useUpdateAIProvider, useUpdateConfig } from '@/hooks/use-config'

export const Route = createFileRoute('/_main')({
  component: ProtectedLayoutWrapper,
})

function ProtectedLayoutWrapper() {
  return (
    <ConfigChangesProvider>
      <ProtectedLayout />
    </ConfigChangesProvider>
  )
}

function ProtectedLayout() {
  const { isAuthenticated, isLoading } = useAuth()
  const location = useLocation()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [activeSection, setActiveSection] = useState('general')
  const { hasPendingChanges, getPendingChanges, clearChanges } =
    useConfigChanges()
  const updateConfigMutation = useUpdateConfig()
  const updateAIProviderMutation = useUpdateAIProvider()
  const [isSaving, setIsSaving] = useState(false)

  // Update active section based on current path
  useEffect(() => {
    const path = location.pathname
    const section = path.replace('/', '') || 'general'
    setActiveSection(section)
  }, [location.pathname])

  // Show loading spinner while checking auth
  if (isLoading) {
    return (
      <div className="flex h-screen w-screen items-center justify-center">
        <Spinner />
      </div>
    )
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" />
  }

  const handleSave = async () => {
    const changes = getPendingChanges()

    if (!hasPendingChanges) {
      toast.info('No changes to save')
      return
    }

    setIsSaving(true)
    try {
      // Save config changes
      if (changes.config && Object.keys(changes.config).length > 0) {
        await updateConfigMutation.mutateAsync(changes.config)
      }

      // Save AI provider changes
      if (changes.aiProvider && Object.keys(changes.aiProvider).length > 0) {
        await updateAIProviderMutation.mutateAsync(changes.aiProvider)
      }

      clearChanges()
      toast.success('Configuration saved successfully')
    } catch (error) {
      toast.error(
        error instanceof Error ? error.message : 'Failed to save configuration',
      )
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="flex w-full">
      <AppSidebar
        activeSection={activeSection}
        onSectionChange={setActiveSection}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
      <ContentLayout fullHeight={false}>
        <div className="flex items-center justify-end mb-6">
          <Button
            onClick={handleSave}
            className="gap-2"
            disabled={!hasPendingChanges || isSaving}
          >
            <Save className="h-4 w-4" />
            {isSaving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
        <Outlet />
      </ContentLayout>
    </div>
  )
}
