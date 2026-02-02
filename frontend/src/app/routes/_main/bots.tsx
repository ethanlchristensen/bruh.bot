import { createFileRoute } from '@tanstack/react-router'
import { BotsSection } from './bots-section'
import { defaultConfig } from '@/lib/default-config'
import { useState } from 'react'

export const Route = createFileRoute('/_main/bots')({
  component: BotsPage,
})

function BotsPage() {
  const [config, setConfig] = useState(defaultConfig)

  const updateConfig = (updates: Partial<typeof defaultConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }))
  }

  return <BotsSection config={config} onUpdate={updateConfig} />
}
