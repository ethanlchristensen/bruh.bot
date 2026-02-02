import { createFileRoute } from '@tanstack/react-router'
import { DatabaseSection } from './database-section'
import { defaultConfig } from '@/lib/default-config'
import { useState } from 'react'

export const Route = createFileRoute('/_main/database')({
  component: DatabasePage,
})

function DatabasePage() {
  const [config, setConfig] = useState(defaultConfig)

  const updateConfig = (updates: Partial<typeof defaultConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }))
  }

  return <DatabaseSection config={config} onUpdate={updateConfig} />
}
