import { createFileRoute } from '@tanstack/react-router'
import { BotsSection } from './bots-section'
import { useConfig } from "@/hooks/use-config"
import { Spinner } from "@/components/ui/spinner"
import type { DynamicConfig } from "@/lib/api-client"
import { useConfigChanges } from "@/contexts/config-changes-context"
import { useMemo } from "react"

export const Route = createFileRoute('/_main/bots')({
  component: BotsPage,
})

function BotsPage() {
  const { data, isLoading, error } = useConfig()
  const { addConfigChange, pendingChanges } = useConfigChanges()

  // Merge server data with pending changes to show optimistic updates
  const config = useMemo(() => {
    if (!data?.config) return null;
    return {
      ...data.config,
      ...pendingChanges.config,
    };
  }, [data?.config, pendingChanges.config]);

  const handleUpdate = (updates: Partial<DynamicConfig>) => {
    addConfigChange(updates);
  }

  if (isLoading) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <Spinner/>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex h-[50vh] items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-destructive font-medium">Failed to load configuration</p>
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

  return <BotsSection config={config} onUpdate={handleUpdate} />
}
