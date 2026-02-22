import { createFileRoute } from '@tanstack/react-router'
import { useMemo } from 'react'
import { AISection } from '../../../components/sections/ai-section'
import type { AIConfig, UpdateAIProviderRequest } from '@/lib/api-client'
import { useConfig } from '@/hooks/use-config'
import { Spinner } from '@/components/ui/spinner'
import { useConfigChanges } from '@/contexts/config-changes-context'

export const Route = createFileRoute('/_main/ai')({
  component: AIPage,
})

function AIPage() {
  const { data, isLoading, error } = useConfig()
  const { addConfigChange, addAIProviderChange } = useConfigChanges()

  // Merge server data with pending changes to show optimistic updates
  const config = useMemo(() => {
    if (!data?.config) return null
    // For AI config, we don't merge here since it's handled by provider updates
    return data.config.aiConfig
  }, [data?.config])

  const handleUpdate = (updates: Partial<AIConfig>) => {
    // Store AI config updates as general config updates if needed
    // For now, most AI updates go through handleUpdateProvider
    addConfigChange({ aiConfig: { ...config, ...updates } } as any)
  }

  const handleUpdateProvider = (providerUpdates: UpdateAIProviderRequest) => {
    addAIProviderChange(providerUpdates)
  }

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Spinner />
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-destructive font-medium">
            Failed to load AI configuration
          </p>
          <p className="text-sm text-muted-foreground">{error.message}</p>
        </div>
      </div>
    )
  }

  if (!config) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <p className="text-muted-foreground">No configuration found</p>
      </div>
    )
  }

  return (
    <AISection
      config={config}
      onUpdate={handleUpdate}
      onUpdateProvider={handleUpdateProvider}
    />
  )
}
