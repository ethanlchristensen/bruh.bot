import { createFileRoute } from '@tanstack/react-router'
import { CooldownsSection } from './cooldowns-section'
import { defaultConfig } from '@/lib/default-config'
import { useState } from 'react'

export const Route = createFileRoute('/_main/cooldowns')({
  component: CooldownsPage,
})

function CooldownsPage() {
  const [config, setConfig] = useState(defaultConfig)

  const updateConfig = (updates: Partial<typeof defaultConfig>) => {
    setConfig((prev) => ({ ...prev, ...updates }))
  }

  return <CooldownsSection config={config} onUpdate={updateConfig} />
}
